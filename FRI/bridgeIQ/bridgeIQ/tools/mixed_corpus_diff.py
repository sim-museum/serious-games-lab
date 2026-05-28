"""Compare Q-Plus's mixed-system corpus run against bridgeIQ.

For each deal Q-Plus played (BDL), drive bridgeIQ's bidder with the
SAME deal cards + the SAME N/S system + E/W system the manifest
records. Compare auctions and DD-scored contracts.

This is the data that drives "what does bridgeIQ get wrong vs
Q-Plus" — the file the user runs after a Q-Plus session to find
patterns worth fixing.

Output: per-deal lines, plus aggregate IMP delta (NS-signed)
broken down by NS-system, EW-system, and contract-match status.

Usage:
    python3 tools/mixed_corpus_diff.py \\
        --bdl LOG/log-040.bdl \\
        --manifest OWN-DEALS/86049_9777.manifest.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.dds import DDSolver  # noqa: E402
from backend.models import (  # noqa: E402
    BoardState, Bid, Card, Contract, Hand, Rank, Seat, Suit,
    Vulnerability,
)
from backend.bidding_systems import get_system  # noqa: E402
from backend.native_bidder import (  # noqa: E402
    decide_bid, evaluate_hand, parse_auction,
)
from backend.scoring import calculate_contract_score  # noqa: E402

from tools.qplus_mixed_corpus import (  # noqa: E402
    SYSTEM_TAG, _SYSTEM_BY_TAG, gen_random_deals,
    parse_bdl_with_systems,
)
from tools.score_diff import (  # noqa: E402
    _deal_to_pbn, _determine_contract, _dd_tricks, _ns_score,
    _imp_lookup,
)


_VUL_TAG_MAP = {
    "None": Vulnerability.NONE,
    "NONE": Vulnerability.NONE,
    "Both": Vulnerability.BOTH,
    "BOTH": Vulnerability.BOTH,
    "All": Vulnerability.BOTH,
    "N/S": Vulnerability.NS,
    "NS": Vulnerability.NS,
    "E/W": Vulnerability.EW,
    "EW": Vulnerability.EW,
}


def _board_from_bdl_hands(n: int, bd: Dict) -> BoardState:
    """Build a BoardState from a `parse_bdl_with_systems` deal dict.

    Why: the QSS-recorded hands are what Q-Plus actually played, so
    they're the only correct hands to feed the bidder + DDS when
    cross-comparing. Re-generating from manifest seed is wrong for
    non-vanilla corpora (slam-eligible, future curated variants)."""
    hands: Dict[Seat, Hand] = {}
    seat_map = {"N": Seat.NORTH, "E": Seat.EAST,
                "S": Seat.SOUTH, "W": Seat.WEST}
    for k, suits in bd["hands"].items():
        seat = seat_map[k]
        # `suits` is {'S': 'AKQ', 'H': 'JT9', 'D': '...', 'C': '...'}
        pbn = ".".join(suits.get(s, "") or "-"
                       for s in ("S", "H", "D", "C"))
        hands[seat] = Hand.from_pbn(pbn)
    dealer_raw = (bd.get("dealer") or "N").strip()
    dealer = seat_map.get(dealer_raw[0].upper(), Seat.NORTH)
    vul_raw = (bd.get("vul") or "None").strip()
    vul = _VUL_TAG_MAP.get(vul_raw, Vulnerability.NONE)
    return BoardState(board_number=n, dealer=dealer,
                      vulnerability=vul, hands=hands)


def drive_bridgeIQ_mixed(board: BoardState, ns_system_name: str,
                         ew_system_name: str) -> List[Bid]:
    """Same bidding loop as tools.qplus_diff._drive_bridgeIQ, but
    each seat uses the system its side plays (NS or EW)."""
    ns_sys = get_system(ns_system_name)
    ew_sys = get_system(ew_system_name)
    auction: List[Bid] = []
    seat = board.dealer
    illegal_streak = 0
    _SUIT_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2,
                  Suit.SPADES: 3, Suit.NOTRUMP: 4}

    def _legal(b: Bid, auc: List[Bid]) -> bool:
        if b.is_pass:
            return True
        if b.is_double:
            last = next((x for x in reversed(auc) if not x.is_pass), None)
            return (last is not None and not last.is_double
                    and not last.is_redouble)
        if b.is_redouble:
            last = next((x for x in reversed(auc) if not x.is_pass), None)
            return last is not None and last.is_double
        if b.suit is None:
            return False
        if b.level < 1 or b.level > 7:
            return False
        last_suit = next((x for x in reversed(auc)
                          if not x.is_pass and not x.is_double
                          and not x.is_redouble), None)
        if last_suit is None:
            return True
        if b.level > last_suit.level:
            return True
        if b.level == last_suit.level:
            return _SUIT_RANK[b.suit] > _SUIT_RANK[last_suit.suit]
        return False

    for _ in range(80):
        state = parse_auction(seat, board.dealer, list(auction),
                              vulnerability=board.vulnerability)
        e = evaluate_hand(board.hands[seat])
        sys_ = ns_sys if seat.is_ns() else ew_sys
        b = decide_bid(state, e, sys_)
        if not _legal(b, auction):
            b = Bid.make_pass()
            illegal_streak += 1
            if illegal_streak >= 4:
                break
        else:
            illegal_streak = 0
        auction.append(b)
        if (len(auction) >= 4
                and all(x.is_pass for x in auction[-3:])
                and any(not x.is_pass for x in auction[:-3])):
            break
        if len(auction) >= 4 and all(x.is_pass for x in auction):
            break
        seat = seat.next()
    return auction


def _bid_str(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    suit = {Suit.CLUBS: "C", Suit.DIAMONDS: "D",
            Suit.HEARTS: "H", Suit.SPADES: "S",
            Suit.NOTRUMP: "NT"}.get(b.suit, "?")
    return f"{b.level}{suit}"


def _bdl_auction(bdl_bids_block: List[str], dealer: Seat) -> List[Bid]:
    """Reconstruct a bid list from the BDL's Bids table.
    Q-Plus writes one row per row of 4 calls, prefixed with the
    bidder columns header. We just collect non-empty tokens in
    reading order."""
    out: List[Bid] = []
    for raw in bdl_bids_block:
        # Strip column-headers like "N    E    S    W"
        if re.search(r"[NESW]\s+[NESW]\s+[NESW]\s+[NESW]", raw):
            continue
        if "=====" in raw or "-----" in raw:
            continue
        parts = raw.split(":", 1)
        if len(parts) < 2:
            continue
        body = parts[1]
        # Remove alert/explanation markers (~ ! ? ^ * etc.)
        tokens = body.split()
        for tok in tokens:
            # Q-Plus renders PASS as a bare '-' (or '--') in the bids
            # column. Capture BEFORE rstrip — the '-' suffix-strip below
            # would otherwise erase the token entirely and the parser
            # would skip the pass, causing all subsequent bids to be
            # mis-attributed to the next seat. Before this fix, a 6-bid
            # auction like 1NT-P-3D-P-P-P got parsed as just [1NT, 3D]
            # and _determine_contract picked the WRONG declarer
            # (3D-W instead of 3D-N for dealer=S).
            if tok in ("-", "--"):
                out.append(Bid.make_pass())
                continue
            tok = tok.rstrip("~!?^*+-")
            if not tok:
                continue
            if tok.upper() == "P" or tok.upper() == "PASS":
                out.append(Bid.make_pass())
            elif tok.upper() == "X":
                out.append(Bid.make_double())
            elif tok.upper() in ("XX", "RDBL", "RX"):
                out.append(Bid.make_redouble())
            else:
                # Parse like "1S", "3nt", "4c~", "2d"
                m = re.match(r"([1-7])(nt|NT|[csdhCSDH])$", tok)
                if not m:
                    continue
                lvl = int(m.group(1))
                suit_c = m.group(2).upper()
                suit_map = {"C": Suit.CLUBS, "D": Suit.DIAMONDS,
                            "H": Suit.HEARTS, "S": Suit.SPADES,
                            "NT": Suit.NOTRUMP}
                out.append(Bid(level=lvl, suit=suit_map[suit_c]))
    return out


def _parse_bdl_bids_per_deal(bdl_path: Path) -> Dict[str, List[Bid]]:
    """Return {deal_label: [Bid, …]} for each deal in the BDL.
    Uses simple line-state-machine on Bids blocks.

    Q-Plus 17.1 savescore.qss prefixes every embedded BDL line with
    `D1 ` — auto-strip that prefix when the file is .qss so the
    parser sees a normal BDL.
    """
    out: Dict[str, List[Bid]] = {}
    current_label: Optional[str] = None
    in_bids = False
    bids_lines: List[str] = []
    is_qss = str(bdl_path).lower().endswith(".qss")
    with open(bdl_path, encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if is_qss:
                if not line.startswith("D1 "):
                    continue
                line = line[3:]
            if line.startswith("Deal "):
                if current_label and bids_lines:
                    out[current_label] = _bdl_auction(bids_lines,
                                                     Seat.NORTH)
                current_label = line.split(":", 1)[1].strip()
                in_bids = False
                bids_lines = []
                continue
            if line.startswith("Bids "):
                in_bids = True
                bids_lines = [line]
                continue
            if in_bids:
                if line.startswith("             :"):
                    bids_lines.append(line)
                    if "=====" in line:
                        in_bids = False
                        if current_label:
                            out[current_label] = _bdl_auction(
                                bids_lines, Seat.NORTH)
                            bids_lines = []
                else:
                    in_bids = False
                    if current_label and bids_lines:
                        out[current_label] = _bdl_auction(bids_lines,
                                                          Seat.NORTH)
                        bids_lines = []
    if current_label and bids_lines:
        out[current_label] = _bdl_auction(bids_lines, Seat.NORTH)
    return out


def _auction_match(a: List[Bid], b: List[Bid]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.is_pass and y.is_pass:
            continue
        if x.is_double and y.is_double:
            continue
        if x.is_redouble and y.is_redouble:
            continue
        if x.is_pass or y.is_pass or x.is_double or y.is_double \
                or x.is_redouble or y.is_redouble:
            return False
        if x.level != y.level or x.suit != y.suit:
            return False
    return True


def _contract_str(c: Optional[Contract]) -> str:
    if c is None:
        return "PASS"
    suit_str = "NT" if c.suit == Suit.NOTRUMP else c.suit.to_char()
    xx = "XX" if c.redoubled else "X" if c.doubled else ""
    return f"{c.level}{suit_str}{xx}-{c.declarer.name[0]}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bdl", required=True, help="path to Q-Plus BDL")
    p.add_argument("--manifest", required=True,
                   help="path to bridgeIQ manifest JSON")
    p.add_argument("--brief", action="store_true",
                   help="aggregate-only output")
    p.add_argument("--worst", type=int, default=10,
                   help="show this many worst (largest IMP-loss) deals")
    args = p.parse_args(argv)

    bdl = Path(args.bdl)
    mani = Path(args.manifest)
    manifest = json.loads(mani.read_text())
    # NOTE: do NOT regenerate hands from manifest["deal_seed"] — that only
    # works for a vanilla `gen_random_deals` corpus. Slam-eligible
    # corpora skip non-qualifying hands from the random stream, so the
    # nth deal of a slam corpus is NOT the nth deal of gen_random_deals.
    # The QSS file holds the hands that Q-Plus actually played; use
    # those (`_board_from_bdl_hands` below) and avoid the mismatch.
    pair_by_n = {d["deal"]: (d["ns_system"], d["ew_system"])
                 for d in manifest["deals"]}

    print(f"# Mixed-corpus diff — bridgeIQ vs Q-Plus")
    print(f"# BDL:      {bdl}")
    print(f"# manifest: {mani}")
    print()

    bdl_deals = parse_bdl_with_systems(bdl)
    bdl_by_n: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_n:
                bdl_by_n[n] = bd
    bdl_bids_by_label = _parse_bdl_bids_per_deal(bdl)

    dds = DDSolver()

    rows: List[Dict] = []
    skipped = 0
    for n in sorted(bdl_by_n.keys()):
        if n not in pair_by_n:
            skipped += 1
            continue
        bd = bdl_by_n[n]
        ns, ew = pair_by_n[n]
        # Override with what BDL actually recorded if it differs
        # (system-mismatched deals are still usable; we want to
        # compare against what Q-Plus actually played).
        bdl_ns_name = _SYSTEM_BY_TAG.get(bd["ns_tag"])
        bdl_ew_name = _SYSTEM_BY_TAG.get(bd["ew_tag"])
        actual_ns = bdl_ns_name or ns
        actual_ew = bdl_ew_name or ew
        # Skip deals whose system tag isn't one of our 5.
        if actual_ns not in {s[0] for s in [
                ("SAYC",), ("TwoOverOne",), ("StandardAcol",),
                ("StandardFrench",), ("Precision90M",)]}:
            skipped += 1
            continue
        board = _board_from_bdl_hands(n, bd)
        qp_auction = bdl_bids_by_label.get(bd["label"]) or []
        biq_auction = drive_bridgeIQ_mixed(board, actual_ns, actual_ew)
        qp_contract = _determine_contract(board, qp_auction)
        biq_contract = _determine_contract(board, biq_auction)
        qp_dd_tricks = (_dd_tricks(dds, board, qp_contract)
                        if qp_contract else 0)
        biq_dd_tricks = (_dd_tricks(dds, board, biq_contract)
                         if biq_contract else 0)
        qp_dd_score = _ns_score(qp_contract, qp_dd_tricks,
                                board.vulnerability)
        biq_dd_score = _ns_score(biq_contract, biq_dd_tricks,
                                 board.vulnerability)
        delta = biq_dd_score - qp_dd_score
        imp = _imp_lookup(delta)
        rows.append({
            "n": n,
            "ns": actual_ns, "ew": actual_ew,
            "qp_auction": qp_auction,
            "biq_auction": biq_auction,
            "qp_contract": qp_contract,
            "biq_contract": biq_contract,
            "qp_dd_score": qp_dd_score,
            "biq_dd_score": biq_dd_score,
            "delta": delta, "imp": imp,
            "auction_match": _auction_match(qp_auction, biq_auction),
            "contract_match": (
                qp_contract is None and biq_contract is None
                or (qp_contract is not None and biq_contract is not None
                    and qp_contract.level == biq_contract.level
                    and qp_contract.suit == biq_contract.suit
                    and qp_contract.declarer == biq_contract.declarer)),
        })

    if not args.brief:
        print(f"{'#':>3}  {'NS':<14} {'EW':<14}  "
              f"{'Q-Plus':<12} {'bridgeIQ':<12}  "
              f"{'qp_dd':>6} {'biq_dd':>6}  {'delta':>6} {'imp':>4}  "
              f"{'auc':>3} {'ct':>3}")
        for r in rows:
            print(
                f"{r['n']:>3}  {r['ns']:<14} {r['ew']:<14}  "
                f"{_contract_str(r['qp_contract']):<12} "
                f"{_contract_str(r['biq_contract']):<12}  "
                f"{r['qp_dd_score']:>+6d} {r['biq_dd_score']:>+6d}  "
                f"{r['delta']:>+6d} {r['imp']:>+4d}  "
                f"{'.' if r['auction_match'] else 'X':>3} "
                f"{'.' if r['contract_match'] else 'X':>3}")
        print()

    # Aggregate
    n = len(rows)
    if n == 0:
        print("No comparable deals.")
        return 0
    sum_imp = sum(r["imp"] for r in rows)
    sum_delta = sum(r["delta"] for r in rows)
    auction_match = sum(1 for r in rows if r["auction_match"])
    contract_match = sum(1 for r in rows if r["contract_match"])
    wins = sum(1 for r in rows if r["delta"] > 0)
    ties = sum(1 for r in rows if r["delta"] == 0)
    losses = sum(1 for r in rows if r["delta"] < 0)
    print(f"## Aggregate ({n} deals)")
    print(f"  Auction exact match: {auction_match}/{n} "
          f"({auction_match*100//n}%)")
    print(f"  Contract match:      {contract_match}/{n} "
          f"({contract_match*100//n}%)")
    print(f"  bridgeIQ wins:       {wins}, ties: {ties}, "
          f"losses: {losses}")
    print(f"  NS score delta:      {sum_delta:+d} "
          f"({sum_delta/n:+.1f}/deal)")
    print(f"  NS IMP delta:        {sum_imp:+d} "
          f"({sum_imp/n:+.2f}/deal)")

    # Per-system breakdown
    print("\n## By NS system")
    by_ns = defaultdict(list)
    for r in rows:
        by_ns[r["ns"]].append(r)
    for ns_name in sorted(by_ns.keys()):
        sub = by_ns[ns_name]
        if not sub:
            continue
        imp = sum(r["imp"] for r in sub)
        am = sum(1 for r in sub if r["auction_match"])
        cm = sum(1 for r in sub if r["contract_match"])
        print(f"  {ns_name:<16} n={len(sub):>3}  "
              f"auction={am}/{len(sub)}  contract={cm}/{len(sub)}  "
              f"IMP={imp:+d} ({imp/len(sub):+.2f}/deal)")

    print("\n## By EW system")
    by_ew = defaultdict(list)
    for r in rows:
        by_ew[r["ew"]].append(r)
    for ew_name in sorted(by_ew.keys()):
        sub = by_ew[ew_name]
        if not sub:
            continue
        imp = sum(r["imp"] for r in sub)
        print(f"  {ew_name:<16} n={len(sub):>3}  "
              f"IMP={imp:+d} ({imp/len(sub):+.2f}/deal)")

    # Worst losses (negative IMP for NS = bridgeIQ was worse)
    rows_by_imp = sorted(rows, key=lambda r: r["imp"])
    print(f"\n## Worst {args.worst} deals for bridgeIQ")
    print(f"{'#':>3}  {'NS':<14} {'EW':<14}  "
          f"{'Q-Plus':<12} {'bridgeIQ':<12}  "
          f"{'imp':>4}  Q-Plus-auction  →  bridgeIQ-auction")
    for r in rows_by_imp[:args.worst]:
        qauc = " ".join(_bid_str(b) for b in r["qp_auction"])
        bauc = " ".join(_bid_str(b) for b in r["biq_auction"])
        print(f"{r['n']:>3}  {r['ns']:<14} {r['ew']:<14}  "
              f"{_contract_str(r['qp_contract']):<12} "
              f"{_contract_str(r['biq_contract']):<12}  "
              f"{r['imp']:>+4d}  {qauc}  →  {bauc}")

    if skipped:
        print(f"\n(skipped {skipped} deals — not in manifest or "
              "non-modeled bidding system)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
