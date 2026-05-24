"""Score-based comparison: did bridgeIQ pick a contract that
scores at least as well as Q-Plus's?

For each deal we compute three scores (all from NS's perspective):

  qp_actual    Q-Plus's actual result from the BDL log
               (their contract + their actual tricks).
  qp_dd        Q-Plus's contract played double-dummy
               (their contract + DDS-optimal tricks).
  bIQ_dd       bridgeIQ's contract played double-dummy
               (bridgeIQ's derived contract + DDS-optimal tricks).

Comparing `bIQ_dd` vs `qp_dd` factors out card-play noise and
isolates the question: **did the bidder land on a better
contract?** Comparing `bIQ_dd` vs `qp_actual` answers a harder
question: **does bridgeIQ's contract played perfectly beat
Q-Plus's actual play?**

For passed-out deals score = 0. Doubles / redoubles are
preserved in the contract object.

Per-deal output: NS score for each variant + delta. Aggregate
output: total NS, mean per board, board wins/losses/ties.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

PKG = Path("/home/h/sgl/FRI/bridgeIQ/bridgeIQ")
sys.path.insert(0, str(PKG))

from backend.bdl_reader import load_bdl_file
from backend.dds import DDSolver
from backend.models import (
    BoardState, Bid, Card, Contract, Hand, Rank, Seat, Suit,
    Vulnerability,
)
from backend.native_bidder import (
    decide_bid, evaluate_hand, parse_auction,
)
from backend.bidding_systems import get_system
from backend.scoring import calculate_contract_score
from tools.qplus_diff import _drive_bridgeIQ


SUITS_PBN = "SHDC"  # PBN order for solve_dd_table


def _deal_to_pbn(board: BoardState) -> str:
    """Convert a BoardState's hands to PBN deal string starting at N."""
    hand_strs = []
    for s in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
        h = board.hands[s]
        suits = {Suit.SPADES: "", Suit.HEARTS: "",
                 Suit.DIAMONDS: "", Suit.CLUBS: ""}
        rank_char = "AKQJT98765432"
        for c in sorted(h.cards, key=lambda c: (c.suit.value, c.rank.value)):
            suits[c.suit] += rank_char[c.rank.value]
        parts = [suits[Suit.SPADES] or "-", suits[Suit.HEARTS] or "-",
                 suits[Suit.DIAMONDS] or "-", suits[Suit.CLUBS] or "-"]
        hand_strs.append(".".join(parts))
    return "N:" + " ".join(hand_strs)


def _determine_contract(board: BoardState,
                        auction: List[Bid]) -> Optional[Contract]:
    """Identify declarer + final-strain contract from an auction."""
    level = 0
    suit = None
    declarer = None
    doubled = False
    redoubled = False
    for i, b in enumerate(auction):
        if not b.is_pass and not b.is_double and not b.is_redouble:
            level = b.level
            suit = b.suit
            bidder = Seat((board.dealer.value + i) % 4)
            side_ns = bidder.is_ns()
            for j, bj in enumerate(auction[:i + 1]):
                if (not bj.is_pass and not bj.is_double
                        and not bj.is_redouble and bj.suit == suit):
                    j_seat = Seat((board.dealer.value + j) % 4)
                    if j_seat.is_ns() == side_ns:
                        declarer = j_seat
                        break
            doubled = False
            redoubled = False
        elif b.is_double:
            doubled = True
            redoubled = False
        elif b.is_redouble:
            redoubled = True
    if level == 0 or declarer is None:
        return None
    return Contract(level=level, suit=suit, declarer=declarer,
                    doubled=doubled, redoubled=redoubled)


def _dd_tricks(dds: DDSolver, board: BoardState,
               contract: Contract) -> int:
    """Look up double-dummy tricks for a given contract."""
    pbn = _deal_to_pbn(board)
    table = dds.solve_dd_table(pbn)
    declarer_char = "NESW"[contract.declarer.value]
    strain_char = ("S" if contract.suit == Suit.SPADES else
                   "H" if contract.suit == Suit.HEARTS else
                   "D" if contract.suit == Suit.DIAMONDS else
                   "C" if contract.suit == Suit.CLUBS else "NT")
    return table[declarer_char][strain_char]


def _ns_score(contract: Optional[Contract], tricks: int,
              vul: Vulnerability) -> int:
    """Return NS's signed score: positive if NS profits."""
    if contract is None:
        return 0
    declarer_vul = vul.is_vulnerable(contract.declarer)
    raw = calculate_contract_score(contract, tricks, declarer_vul)
    if contract.declarer.is_ns():
        return raw
    return -raw


def _imp_lookup(diff: int) -> int:
    """IMP scale (ACBL): convert score difference to IMPs."""
    bands = [
        (20, 0), (40, 1), (80, 2), (120, 3), (160, 4),
        (210, 5), (260, 6), (310, 7), (360, 8), (420, 9),
        (490, 10), (590, 11), (740, 12), (890, 13), (1090, 14),
        (1290, 15), (1490, 16), (1740, 17), (1990, 18),
        (2240, 19), (2490, 20), (2990, 21), (3490, 22),
        (3990, 23),
    ]
    sign = 1 if diff >= 0 else -1
    d = abs(diff)
    imps = 24
    for hi, imp in bands:
        if d < hi:
            imps = imp
            break
    return sign * imps


def diff_block(bdl_path: Path, block_text: str,
               system_name: str) -> dict:
    """Compute score deltas for one system's session block."""
    # Save block to a temp BDL file the loader can read.
    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bdl", delete=False,
            encoding="latin-1") as f:
        f.write("DOCTYPE: BDL 7.1\n")
        f.write(block_text)
        tmp = Path(f.name)
    try:
        deals = load_bdl_file(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)

    dds = DDSolver()
    results = []
    sum_qp_actual = 0
    sum_qp_dd = 0
    sum_biq_dd = 0
    biq_wins = 0
    biq_losses = 0
    ties = 0
    sum_imp_actual = 0
    sum_imp_dd = 0
    for qdeal in deals:
        if not qdeal.hands or len(qdeal.hands) < 4:
            continue
        board = qdeal.to_board_state()
        qp_contract = qdeal.contract

        # bridgeIQ contract + DD tricks
        our_auction = _drive_bridgeIQ(board, system_name)
        biq_contract = _determine_contract(board, our_auction)
        try:
            biq_dd_tricks = (_dd_tricks(dds, board, biq_contract)
                             if biq_contract is not None else 0)
        except Exception:
            biq_dd_tricks = 0
        biq_dd_score = _ns_score(biq_contract, biq_dd_tricks,
                                 qdeal.vulnerability)

        # Q-Plus actual: contract + actual tricks (from BDL).
        # BDLDeal stores tricks_made as declarer's tricks.
        qp_actual_tricks = qdeal.tricks_made
        qp_actual_score = _ns_score(qp_contract, qp_actual_tricks,
                                    qdeal.vulnerability)

        # Q-Plus DD: contract + DD tricks.
        try:
            qp_dd_tricks = (_dd_tricks(dds, board, qp_contract)
                            if qp_contract is not None else 0)
        except Exception:
            qp_dd_tricks = 0
        qp_dd_score = _ns_score(qp_contract, qp_dd_tricks,
                                qdeal.vulnerability)

        delta_actual = biq_dd_score - qp_actual_score
        delta_dd = biq_dd_score - qp_dd_score
        imp_actual = _imp_lookup(delta_actual)
        imp_dd = _imp_lookup(delta_dd)
        if biq_dd_score > qp_actual_score:
            biq_wins += 1
        elif biq_dd_score < qp_actual_score:
            biq_losses += 1
        else:
            ties += 1
        sum_qp_actual += qp_actual_score
        sum_qp_dd += qp_dd_score
        sum_biq_dd += biq_dd_score
        sum_imp_actual += imp_actual
        sum_imp_dd += imp_dd
        results.append({
            "label": getattr(qdeal, "pavlicek_id", "")
                     or f"deal-{len(results)+1}",
            "qp_contract": qp_contract,
            "qp_actual_tricks": qp_actual_tricks,
            "qp_dd_tricks": qp_dd_tricks,
            "biq_contract": biq_contract,
            "biq_dd_tricks": biq_dd_tricks,
            "qp_actual_score": qp_actual_score,
            "qp_dd_score": qp_dd_score,
            "biq_dd_score": biq_dd_score,
            "delta_actual": delta_actual,
            "delta_dd": delta_dd,
            "imp_actual": imp_actual,
            "imp_dd": imp_dd,
        })
    return {
        "results": results,
        "sum_qp_actual": sum_qp_actual,
        "sum_qp_dd": sum_qp_dd,
        "sum_biq_dd": sum_biq_dd,
        "sum_imp_actual": sum_imp_actual,
        "sum_imp_dd": sum_imp_dd,
        "biq_wins": biq_wins,
        "biq_losses": biq_losses,
        "ties": ties,
        "n": len(results),
    }


def _contract_str(c: Optional[Contract]) -> str:
    if c is None:
        return "PASS-OUT"
    suit_str = "NT" if c.suit == Suit.NOTRUMP else c.suit.to_char()
    xx = "XX" if c.redoubled else "X" if c.doubled else ""
    return f"{c.level}{suit_str}{xx} by {c.declarer.name[0]}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bdl",
                   default="/home/h/sgl/FRI/WP/drive_c/games/"
                           "qbridge17/DATA/LOG/log-033.bdl",
                   help="path to the shared BDL log")
    p.add_argument("--brief", action="store_true",
                   help="suppress per-deal lines, just print summary")
    args = p.parse_args()
    bdl = Path(args.bdl)
    text = bdl.read_text(encoding="latin-1", errors="replace")
    lines = text.split("\n")
    section_starts = []
    for i, line in enumerate(lines):
        m = re.match(r"\.Bidding cnv\s*:\s*N/S:\s*([A-Z0-9-]+)", line)
        if m:
            section_starts.append((i, m.group(1)))
    section_starts.append((len(lines), None))
    latest = {}
    for k in range(len(section_starts) - 1):
        i_start, tag = section_starts[k]
        i_end, _ = section_starts[k + 1]
        latest[tag] = "\n".join(lines[i_start:i_end])

    TAG_TO_SYS = {
        "A-SAYC-I":  "SAYC",
        "A-2-1-A":   "TwoOverOne",
        "B-ACL-S":   "StandardAcol",
        "F-FRA-M":   "StandardFrench",
        "P-P90M-A":  "Precision90M",
    }
    print(f"# Score-based diff — {bdl.name}\n")
    grand = {"n": 0, "sum_qp_actual": 0, "sum_qp_dd": 0,
             "sum_biq_dd": 0, "biq_wins": 0, "biq_losses": 0,
             "ties": 0, "sum_imp_actual": 0, "sum_imp_dd": 0}
    for tag, system_name in TAG_TO_SYS.items():
        if tag not in latest:
            continue
        print(f"## {system_name} ({tag})")
        r = diff_block(bdl, latest[tag], system_name)
        if r["n"] == 0:
            print("  (no deals)\n")
            continue
        if not args.brief:
            for d in r["results"]:
                qc = _contract_str(d["qp_contract"])
                bc = _contract_str(d["biq_contract"])
                marker = "≥" if d["biq_dd_score"] >= d["qp_actual_score"] else "<"
                print(f"  {qc:14s} {d['qp_actual_score']:+5d} "
                      f"(dd:{d['qp_dd_score']:+5d})    →    "
                      f"{bc:14s} dd:{d['biq_dd_score']:+5d}    "
                      f"Δ_actual={d['delta_actual']:+5d} "
                      f"({d['imp_actual']:+2d} IMP)   {marker}")
        n = r["n"]
        print(f"\n  Deals: {n}")
        print(f"  bridgeIQ ≥ Q-Plus (actual): "
              f"{r['biq_wins']+r['ties']}/{n}  "
              f"(wins {r['biq_wins']}, ties {r['ties']}, "
              f"losses {r['biq_losses']})")
        print(f"  NS total (Q-Plus actual):  {r['sum_qp_actual']:+6d}")
        print(f"  NS total (Q-Plus DD):      {r['sum_qp_dd']:+6d}")
        print(f"  NS total (bridgeIQ DD):    {r['sum_biq_dd']:+6d}")
        print(f"  IMP delta vs actual:       {r['sum_imp_actual']:+5d}  "
              f"({r['sum_imp_actual']/max(1,n):+.2f} / board)")
        print(f"  IMP delta vs DD:           {r['sum_imp_dd']:+5d}  "
              f"({r['sum_imp_dd']/max(1,n):+.2f} / board)")
        print()
        for k in grand:
            grand[k] += r[k]

    n = grand["n"]
    print("## Aggregate")
    print(f"  Total deals: {n}")
    print(f"  bridgeIQ ≥ Q-Plus (actual): "
          f"{grand['biq_wins']+grand['ties']}/{n}  "
          f"({(grand['biq_wins']+grand['ties'])*100//max(1,n)}%)")
    print(f"  NS total (Q-Plus actual):  {grand['sum_qp_actual']:+6d}")
    print(f"  NS total (Q-Plus DD):      {grand['sum_qp_dd']:+6d}")
    print(f"  NS total (bridgeIQ DD):    {grand['sum_biq_dd']:+6d}")
    print(f"  IMP delta vs actual:       {grand['sum_imp_actual']:+5d}  "
          f"({grand['sum_imp_actual']/max(1,n):+.2f} / board)")
    print(f"  IMP delta vs DD:           {grand['sum_imp_dd']:+5d}  "
          f"({grand['sum_imp_dd']/max(1,n):+.2f} / board)")


if __name__ == "__main__":
    sys.exit(main())
