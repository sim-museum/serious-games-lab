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


def _parse_qplus_results(bdl_path: Path) -> Dict[str, int]:
    """Return {deal_label: declarer_tricks_taken} from the QSS.

    Q-Plus writes a per-deal summary line of the form
        D1 Result       :  2nt   West     -3     -150      BB-mixed-001
    The third field is the result delta (e.g. -3 = down three,
    +1 = made one overtrick); declarer tricks = (level + 6) + delta.
    Returning tricks directly avoids inverting the scoring tables.
    """
    import re as _re
    pat = _re.compile(
        r'^D1\s+Result\s+:\s+(\S+)\s+\S+\s+([+\-]\d+)\s+'
        r'[+\-]?\d+\s+(\S+)\s*$')
    out: Dict[str, int] = {}
    with open(bdl_path, encoding="latin-1", errors="replace") as f:
        for raw in f:
            m = pat.match(raw.rstrip("\r\n"))
            if not m:
                continue
            contract_str = m.group(1)
            delta = int(m.group(2))
            label = m.group(3)
            if not contract_str[0].isdigit():
                continue
            level = int(contract_str[0])
            tricks = level + 6 + delta
            if 0 <= tricks <= 13:
                out[label] = tricks
    return out


def _parse_qplus_play_per_deal(bdl_path: Path
                                ) -> Dict[str, List[Dict]]:
    """Plan 1 — per-deal trick-by-trick play extracted from the QSS.

    Each deal's `D1 Tricks` block looks like:
        D1 Tricks       :  1  S    sQ   sT   s9   sA+     S
        D1              :  2  S    s2   s7   sK-  s3          S
        D1              :  3  N    s5   s4   s6   sT+     S
    Format per trick:
        <trick#> <leader-seat-char> <card> <card> <card> <card> <suit>
    Cards are in clockwise order starting from the leader, one
    per seat. The card with `+` is the winner; `-` may appear on
    other tricks (just a separator/loser-marker per Q-Plus's
    convention). Card prefix = lowercase suit char ('s' / 'h' /
    'd' / 'c').

    Returns {deal_label: [{leader: Seat, cards: [Card x 4]}, ...]}.
    """
    import re as _re
    out: Dict[str, List[Dict]] = {}
    current_label: Optional[str] = None
    in_tricks = False
    current_tricks: List[Dict] = []
    label_pat = _re.compile(r'^D1\s+Deal\s+:\s+(\S+)\s*$')
    tricks_start = _re.compile(r'^D1\s+Tricks\s+:\s+(.+)$')
    cont_line = _re.compile(r'^D1\s+:\s+(.+)$')
    trick_pat = _re.compile(
        r'^\s*(\d+)\s+([NESW])\s+'
        r'([shdc])([AKQJT2-9])[+\-]?\s+'
        r'([shdc])([AKQJT2-9])[+\-]?\s+'
        r'([shdc])([AKQJT2-9])[+\-]?\s+'
        r'([shdc])([AKQJT2-9])[+\-]?\s')
    suit_char = {'s': Suit.SPADES, 'h': Suit.HEARTS,
                 'd': Suit.DIAMONDS, 'c': Suit.CLUBS}
    rank_char = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN,
                 'J': Rank.JACK, 'T': Rank.TEN, '9': Rank.NINE,
                 '8': Rank.EIGHT, '7': Rank.SEVEN, '6': Rank.SIX,
                 '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
                 '2': Rank.TWO}
    seat_char = {'N': Seat.NORTH, 'E': Seat.EAST,
                 'S': Seat.SOUTH, 'W': Seat.WEST}

    def _try_parse_trick(rest: str) -> Optional[Dict]:
        m = trick_pat.match(rest)
        if not m:
            return None
        leader = seat_char[m.group(2)]
        cards = []
        for i in range(4):
            s = suit_char[m.group(3 + i * 2)]
            r = rank_char[m.group(4 + i * 2)]
            cards.append(Card(suit=s, rank=r))
        return {"leader": leader, "cards": cards}

    with open(bdl_path, encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            m = label_pat.match(line)
            if m:
                # commit prior deal, start new
                if current_label is not None and current_tricks:
                    out[current_label] = current_tricks
                current_label = m.group(1)
                in_tricks = False
                current_tricks = []
                continue
            ms = tricks_start.match(line)
            if ms:
                in_tricks = True
                t = _try_parse_trick(ms.group(1))
                if t:
                    current_tricks.append(t)
                continue
            if in_tricks:
                mc = cont_line.match(line)
                if mc:
                    t = _try_parse_trick(mc.group(1))
                    if t:
                        current_tricks.append(t)
                    continue
                # leaving tricks block (e.g., D1 Result line)
                if "Result" in line or line.strip() == "D1":
                    in_tricks = False
    if current_label is not None and current_tricks:
        out[current_label] = current_tricks
    return out


def _trick_winner(cards: List[Card],
                  trump: Optional[Suit]) -> int:
    """Index (0..3) of the card that wins the trick.

    Trump=None → highest card of lead suit wins.
    Trump set → highest trump beats non-trump; if no trumps,
    highest card of lead suit wins.
    """
    if not cards:
        return 0
    lead = cards[0].suit
    best_idx = 0
    best_card = cards[0]
    for i in range(1, 4):
        c = cards[i]
        # Trump rules first
        if trump is not None and trump != Suit.NOTRUMP:
            if c.suit == trump and best_card.suit != trump:
                best_idx, best_card = i, c
                continue
            if best_card.suit == trump and c.suit != trump:
                continue
        # Same suit comparison — higher rank wins (Rank.ACE = 0,
        # so LOWER rank-value beats higher)
        if c.suit == best_card.suit and c.rank.value < best_card.rank.value:
            best_idx, best_card = i, c
    return best_idx


def biq_play_contract(engine, board_template: BoardState,
                      contract: Contract,
                      qplus_auction: List[Bid],
                      num_samples: int = 5) -> Optional[int]:
    """Drive biq's MC+DDS card-play engine through all 13 tricks of
    the given contract on the given deal. Returns the declarer's
    trick count, or None on failure.

    Q-Plus's auction is threaded into the BoardState that biq's MC
    engine receives, so the MC sampling uses Q-Plus's inferences
    (HCP / distribution ranges implied by Q-Plus's bids) — the
    cardplay comparison is genuinely "same contract, same auction
    inferences, but biq plays the cards."
    """
    declarer = contract.declarer
    trump = contract.suit
    leader = Seat((declarer + 1) % 4)  # LHO of declarer leads
    declarer_tricks = 0
    # Make a mutable copy of each hand.
    from backend.models import Trick
    hands_state: Dict[Seat, List[Card]] = {
        s: list(board_template.hands[s].cards) for s in
        (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)
    }
    # Completed-tricks log — the engine reads board.tricks to know
    # which cards have already been played. Without this it sees
    # 52 - 24 = 28 "unknown" cards but only 24 slots in unknown
    # seats, the per-card distribution overflows on every sample,
    # and MC falls back to get_card_play on every decision.
    completed_tricks: List[Trick] = []
    for _trick_num in range(13):
        trick_cards: List[Card] = []
        trick_seats: List[Seat] = []
        seat = leader
        for _play_num in range(4):
            sub_board = BoardState(
                board_number=board_template.board_number,
                dealer=board_template.dealer,
                vulnerability=board_template.vulnerability,
                hands={s: Hand(cards=list(hands_state[s])) for s in
                       (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)},
                auction=list(qplus_auction),
                contract=contract,
                tricks=list(completed_tricks),
            )
            try:
                resp = engine.get_mc_card_play(
                    sub_board, seat,
                    current_trick_cards=list(trick_cards),
                    num_samples=num_samples)
            except Exception:
                return None
            card = resp.action if resp is not None else None
            if card is None:
                # Fallback: any legal card from this seat's hand
                lead_suit = trick_cards[0].suit if trick_cards else None
                legal = [c for c in hands_state[seat]
                         if lead_suit is None or c.suit == lead_suit]
                if not legal:
                    legal = hands_state[seat]
                if not legal:
                    return None
                card = legal[0]
            # Remove the played card from this seat's hand
            try:
                hands_state[seat].remove(card)
            except ValueError:
                # Card not in hand — engine returned a phantom; bail.
                return None
            trick_cards.append(card)
            trick_seats.append(seat)
            seat = Seat((seat + 1) % 4)
        winner_idx = _trick_winner(trick_cards, trump)
        winner_seat = trick_seats[winner_idx]
        if winner_seat in (declarer,
                           Seat((declarer + 2) % 4)):
            declarer_tricks += 1
        completed_tricks.append(Trick(
            cards=list(trick_cards),
            leader=trick_seats[0],
            winner=winner_seat))
        leader = winner_seat
    return declarer_tricks


def biq_replay_at_seat(engine, board_template: BoardState,
                         contract: Contract,
                         qp_auction: List[Bid],
                         qp_play_data: List[Dict],
                         biq_seat: Seat,
                         num_samples: int = 40) -> Optional[int]:
    """Plan 1 — replay a recorded deal with biq playing one seat.

    The other 3 seats play their Q-Plus recorded cards (looked up
    per trick by seat). When biq's intervention makes a recorded
    Q-Plus card illegal in the current state, fall back to any
    legal card from the affected seat.

    Returns the declarer-side trick count for this replay (so the
    caller can compare to Q-Plus's recorded declarer-tricks).
    """
    from backend.models import Trick

    declarer = contract.declarer
    trump = contract.suit
    # Build per-trick, per-seat card lookup
    qp_card_by_trick = []
    for trick in qp_play_data:
        leader = trick["leader"]
        cards = trick["cards"]
        m = {}
        for i in range(4):
            m[Seat((leader.value + i) % 4)] = cards[i]
        qp_card_by_trick.append(m)
    hands_state = {s: list(board_template.hands[s].cards) for s in
                   (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)}
    completed_tricks: List = []
    if not qp_play_data:
        return None
    leader = qp_play_data[0]["leader"]
    declarer_tricks = 0
    for trick_num in range(min(13, len(qp_play_data))):
        trick_cards: List[Card] = []
        trick_seats: List[Seat] = []
        seat = leader
        for _i in range(4):
            if seat == biq_seat:
                sub_board = BoardState(
                    board_number=board_template.board_number,
                    dealer=board_template.dealer,
                    vulnerability=board_template.vulnerability,
                    hands={s: Hand(cards=list(hands_state[s])) for s in
                           (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)},
                    auction=list(qp_auction),
                    contract=contract,
                    tricks=list(completed_tricks),
                )
                try:
                    resp = engine.get_mc_card_play(
                        sub_board, seat,
                        current_trick_cards=list(trick_cards),
                        num_samples=num_samples)
                except Exception:
                    return None
                card = resp.action if resp is not None else None
            else:
                card = qp_card_by_trick[trick_num].get(seat)
            # Validate + fallback to any legal card if needed
            if card is None or card not in hands_state[seat]:
                lead_suit = trick_cards[0].suit if trick_cards else None
                legal = [c for c in hands_state[seat]
                         if lead_suit is None or c.suit == lead_suit]
                if not legal:
                    legal = hands_state[seat]
                if not legal:
                    return None
                card = legal[0]
            try:
                hands_state[seat].remove(card)
            except ValueError:
                return None
            trick_cards.append(card)
            trick_seats.append(seat)
            seat = Seat((seat.value + 1) % 4)
        winner_idx = _trick_winner(trick_cards, trump)
        winner_seat = trick_seats[winner_idx]
        if winner_seat in (declarer,
                           Seat((declarer.value + 2) % 4)):
            declarer_tricks += 1
        completed_tricks.append(Trick(
            cards=list(trick_cards),
            leader=trick_seats[0],
            winner=winner_seat))
        leader = winner_seat
    return declarer_tricks


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


def _run_cardplay_mode(bdl: Path, mani: Path, *,
                       brief: bool = False, worst: int = 10,
                       limit: int = 0, mc_samples: int = 5) -> int:
    """Compare Q-Plus's recorded tricks against biq's MC+DDS-played
    tricks on the SAME contract (Q-Plus's contract used for both).

    Q-Plus's auction is fed to biq's MC card-play engine via the
    BoardState.auction field so the MC's hand-sampling uses
    Q-Plus's inferences — the cardplay comparison is genuinely
    "same contract, same auction context, different cardplay
    engine."
    """
    import time as _time
    print(f"# Cardplay diff — Q-Plus contract played by both sides")
    print(f"# BDL:      {bdl}")
    print(f"# manifest: {mani}")
    print(f"# biq cardplay: BridgeEngine MC+DDS (num_samples={mc_samples})")
    if limit:
        print(f"# limit:    first {limit} deals")
    print()
    manifest = json.loads(mani.read_text())
    pair_by_n = {d["deal"]: (d["ns_system"], d["ew_system"])
                 for d in manifest["deals"]}
    bdl_deals = parse_bdl_with_systems(bdl)
    bdl_by_n: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_n:
                bdl_by_n[n] = bd
    bdl_bids_by_label = _parse_bdl_bids_per_deal(bdl)
    qplus_scores_by_label = _parse_qplus_results(bdl)
    # Spin up biq's engine ONCE (initializes DDS, expensive).
    # Relax HCP inference by 3 points and drop shape constraints —
    # without this, Q-Plus's looser bidding gets every MC sample
    # rejected by biq's textbook inference, and the engine falls
    # back to a weak `get_card_play` picker.
    # (Phase 27 — try relax=5 — regressed -0.054 tricks/-0.243 IMP.
    # Looser constraints accept more implausible distributions.
    # relax=3 is the sweet spot.)
    from backend.engine import BridgeEngine
    engine = BridgeEngine()
    engine.cardplay_relax_inference = 3
    if not engine.initialize():
        print("[cardplay] failed to initialize BridgeEngine — abort",
              file=sys.stderr)
        return 1
    rows: List[Dict] = []
    skipped = 0
    t_start = _time.time()
    deal_keys = sorted(bdl_by_n.keys())
    if limit:
        deal_keys = deal_keys[:limit]
    for i, n in enumerate(deal_keys, 1):
        bd = bdl_by_n[n]
        if n not in pair_by_n:
            skipped += 1
            continue
        # Match biq's auction-inference system to the deal's NS-side
        # system. Without this, the MC sampler reads every Q-Plus
        # auction under SAYC rules even when Q-Plus actually bid
        # Precision/Acol/French/2-over-1 — wrong HCP ranges →
        # wrong sample rejections → wrong DDS guidance.
        ns_sys, _ew_sys = pair_by_n[n]
        bdl_ns_name = _SYSTEM_BY_TAG.get(bd["ns_tag"])
        engine.set_bidding_system(bdl_ns_name or ns_sys)
        board = _board_from_bdl_hands(n, bd)
        qp_auction = bdl_bids_by_label.get(bd["label"]) or []
        qp_contract = _determine_contract(board, qp_auction)
        if qp_contract is None:
            skipped += 1
            continue
        # Q-Plus's actual tricks come from the D1 Result line
        qp_tricks = qplus_scores_by_label.get(bd["label"])
        if qp_tricks is None:
            skipped += 1
            continue
        # biq plays the same contract
        biq_tricks = biq_play_contract(engine, board, qp_contract,
                                        qp_auction,
                                        num_samples=mc_samples)
        if biq_tricks is None:
            skipped += 1
            continue
        # Score both sides via the same scoring table
        qp_score = _ns_score(qp_contract, qp_tricks, board.vulnerability)
        biq_score = _ns_score(qp_contract, biq_tricks, board.vulnerability)
        delta = biq_score - qp_score
        imp = _imp_lookup(delta)
        rows.append({
            "n": n,
            "contract": qp_contract,
            "qp_tricks": qp_tricks,
            "biq_tricks": biq_tricks,
            "qp_score": qp_score,
            "biq_score": biq_score,
            "delta": delta, "imp": imp,
        })
        if i % 10 == 0:
            elapsed = _time.time() - t_start
            print(f"# … {i}/{len(deal_keys)} deals "
                  f"({elapsed:.0f}s elapsed)", file=sys.stderr)
    if not brief:
        print(f"{'#':>3}  {'contract':<10}  "
              f"{'qp_tr':>5} {'biq_tr':>6}  "
              f"{'qp_$':>6} {'biq_$':>6}  "
              f"{'delta':>6} {'imp':>4}")
        for r in rows:
            c = r["contract"]
            ctxt = (f"{c.level}{c.suit.to_char()}-{c.declarer.to_char()}"
                    if c else "?")
            print(f"{r['n']:>3}  {ctxt:<10}  "
                  f"{r['qp_tricks']:>5} {r['biq_tricks']:>6}  "
                  f"{r['qp_score']:>+6d} {r['biq_score']:>+6d}  "
                  f"{r['delta']:>+6d} {r['imp']:>+4d}")
    n_deals = len(rows)
    print()
    print(f"## Aggregate ({n_deals} deals)")
    if n_deals:
        wins = sum(1 for r in rows if r["imp"] > 0)
        ties = sum(1 for r in rows if r["imp"] == 0)
        losses = sum(1 for r in rows if r["imp"] < 0)
        total_imp = sum(r["imp"] for r in rows)
        total_score = sum(r["delta"] for r in rows)
        total_tr_delta = sum(r["biq_tricks"] - r["qp_tricks"]
                             for r in rows)
        print(f"  biq wins:  {wins}, ties: {ties}, losses: {losses}")
        print(f"  Tricks delta:  {total_tr_delta:+d} "
              f"({total_tr_delta / n_deals:+.2f}/deal)")
        print(f"  NS score delta: {total_score:+d} "
              f"({total_score / n_deals:+.1f}/deal)")
        print(f"  NS IMP delta:  {total_imp:+d} "
              f"({total_imp / n_deals:+.2f}/deal)")
    if skipped:
        print(f"  (skipped: {skipped})")
    # Breakdown: declarer-side and strain.
    # Trick-delta = biq_tricks − qp_tricks (declarer's perspective).
    # A reliably-negative trick-delta in BOTH subgroups means biq's
    # engine takes the declaring side fewer tricks than Q-Plus's —
    # the cleanest measure of cardplay-engine strength, since it's
    # invariant to which seat happens to be declaring.
    if rows:
        def _bucket(predicate):
            sub = [r for r in rows if predicate(r)]
            if not sub:
                return None
            tr = sum(r["biq_tricks"] - r["qp_tricks"] for r in sub)
            imp = sum(r["imp"] for r in sub)
            return (len(sub), tr, imp)
        print()
        print("## Breakdown by declarer side")
        for label, pred in (
                ("declarer N/S", lambda r: r["contract"].declarer
                 in (Seat.NORTH, Seat.SOUTH)),
                ("declarer E/W", lambda r: r["contract"].declarer
                 in (Seat.EAST, Seat.WEST))):
            b = _bucket(pred)
            if b is None:
                continue
            cnt, tr, imp = b
            print(f"  {label:<14} n={cnt:>3}  "
                  f"tricks_delta={tr:+d} ({tr/cnt:+.2f}/deal)  "
                  f"NS IMP={imp:+d} ({imp/cnt:+.2f}/deal)")
        print()
        print("## Breakdown by strain")
        for label, pred in (
                ("NT contracts",
                 lambda r: r["contract"].suit == Suit.NOTRUMP),
                ("suit contracts",
                 lambda r: r["contract"].suit != Suit.NOTRUMP)):
            b = _bucket(pred)
            if b is None:
                continue
            cnt, tr, imp = b
            print(f"  {label:<14} n={cnt:>3}  "
                  f"tricks_delta={tr:+d} ({tr/cnt:+.2f}/deal)  "
                  f"NS IMP={imp:+d} ({imp/cnt:+.2f}/deal)")
    if rows and not brief:
        worst_rows = sorted(rows, key=lambda r: r["imp"])[:worst]
        print()
        print(f"## Worst {min(worst, len(rows))} deals for biq")
        for r in worst_rows:
            c = r["contract"]
            ctxt = (f"{c.level}{c.suit.to_char()}-{c.declarer.to_char()}"
                    if c else "?")
            print(f"  Deal {r['n']:>3}  {ctxt:<10}  "
                  f"qp_tricks={r['qp_tricks']} biq_tricks={r['biq_tricks']} "
                  f"imp={r['imp']:+d}")
    return 0


def _run_end_to_end_mode(bdl: Path, mani: Path, *,
                          brief: bool = False, worst: int = 10,
                          limit: int = 0, mc_samples: int = 5) -> int:
    """Full-pipeline comparison: each side bids its own contract
    AND plays it.

    biq pipeline: drive_bridgeIQ_mixed → biq's auction → biq's
    contract → biq_play_contract uses biq's OWN auction (passed via
    BoardState.auction so the MC sampler sees biq's bidding
    inferences).
    Q-Plus pipeline: parsed auction + parsed Result line → contract
    + actual tricks taken.
    Scoring: each side at its own (contract, tricks); IMP delta.
    """
    import time as _time
    print(f"# End-to-end diff — biq bids+plays vs Q-Plus bids+plays")
    print(f"# BDL:      {bdl}")
    print(f"# manifest: {mani}")
    print(f"# biq cardplay: BridgeEngine MC+DDS (num_samples={mc_samples})")
    if limit:
        print(f"# limit:    first {limit} deals")
    print()
    manifest = json.loads(mani.read_text())
    pair_by_n = {d["deal"]: (d["ns_system"], d["ew_system"])
                 for d in manifest["deals"]}
    bdl_deals = parse_bdl_with_systems(bdl)
    bdl_by_n: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_n:
                bdl_by_n[n] = bd
    bdl_bids_by_label = _parse_bdl_bids_per_deal(bdl)
    qplus_tricks_by_label = _parse_qplus_results(bdl)
    from backend.engine import BridgeEngine
    engine = BridgeEngine()
    # End-to-end mode: biq's bidder produces biq's auction (textbook),
    # but biq plays Q-Plus's contract on Q-Plus's actual hands. Use
    # the same inference relaxation as cardplay mode for symmetry.
    engine.cardplay_relax_inference = 3
    if not engine.initialize():
        print("[end-to-end] failed to initialize BridgeEngine — abort",
              file=sys.stderr)
        return 1
    rows: List[Dict] = []
    skipped = 0
    t_start = _time.time()
    deal_keys = sorted(bdl_by_n.keys())
    if limit:
        deal_keys = deal_keys[:limit]
    for i, n in enumerate(deal_keys, 1):
        bd = bdl_by_n[n]
        if n not in pair_by_n:
            skipped += 1
            continue
        ns, ew = pair_by_n[n]
        bdl_ns_name = _SYSTEM_BY_TAG.get(bd["ns_tag"])
        bdl_ew_name = _SYSTEM_BY_TAG.get(bd["ew_tag"])
        actual_ns = bdl_ns_name or ns
        actual_ew = bdl_ew_name or ew
        if actual_ns not in {"SAYC", "TwoOverOne", "StandardAcol",
                              "StandardFrench", "Precision90M"}:
            skipped += 1
            continue
        # Auction-inference system for biq's MC sampler — NS side
        # (matches biq's bidding-mode convention).
        engine.set_bidding_system(actual_ns)
        board = _board_from_bdl_hands(n, bd)
        qp_auction = bdl_bids_by_label.get(bd["label"]) or []
        biq_auction = drive_bridgeIQ_mixed(board, actual_ns, actual_ew)
        qp_contract = _determine_contract(board, qp_auction)
        biq_contract = _determine_contract(board, biq_auction)
        # Q-Plus's actual tricks (from D1 Result)
        qp_tricks = qplus_tricks_by_label.get(bd["label"])
        if qp_contract is not None and qp_tricks is None:
            # Q-Plus bid a contract but the corpus has no Result line
            # (passed-out hands also lack Result; those have qp_contract
            # = None and are handled below).
            skipped += 1
            continue
        # biq plays its OWN contract, using its OWN auction history
        if biq_contract is None:
            biq_tricks: Optional[int] = 0  # passed out
        else:
            biq_tricks = biq_play_contract(engine, board, biq_contract,
                                            biq_auction,
                                            num_samples=mc_samples)
            if biq_tricks is None:
                skipped += 1
                continue
        # Scoring (passed-out hands score 0/0)
        qp_score = (_ns_score(qp_contract, qp_tricks or 0,
                              board.vulnerability)
                    if qp_contract is not None else 0)
        biq_score = (_ns_score(biq_contract, biq_tricks or 0,
                               board.vulnerability)
                     if biq_contract is not None else 0)
        delta = biq_score - qp_score
        imp = _imp_lookup(delta)
        rows.append({
            "n": n,
            "ns": actual_ns, "ew": actual_ew,
            "qp_contract": qp_contract,
            "biq_contract": biq_contract,
            "qp_tricks": qp_tricks or 0,
            "biq_tricks": biq_tricks or 0,
            "qp_score": qp_score, "biq_score": biq_score,
            "delta": delta, "imp": imp,
        })
        if i % 10 == 0:
            elapsed = _time.time() - t_start
            print(f"# … {i}/{len(deal_keys)} deals "
                  f"({elapsed:.0f}s elapsed)", file=sys.stderr)
    if not brief:
        print(f"{'#':>3}  {'NS':<14} {'EW':<14}  "
              f"{'Q-Plus':<12} {'bridgeIQ':<12}  "
              f"{'qp_tr':>5} {'biq_tr':>6}  "
              f"{'qp_$':>6} {'biq_$':>6}  {'imp':>4}")
        for r in rows:
            print(
                f"{r['n']:>3}  {r['ns']:<14} {r['ew']:<14}  "
                f"{_contract_str(r['qp_contract']):<12} "
                f"{_contract_str(r['biq_contract']):<12}  "
                f"{r['qp_tricks']:>5} {r['biq_tricks']:>6}  "
                f"{r['qp_score']:>+6d} {r['biq_score']:>+6d}  "
                f"{r['imp']:>+4d}")
        print()
    n_deals = len(rows)
    print(f"## Aggregate ({n_deals} deals)")
    if n_deals:
        wins = sum(1 for r in rows if r["imp"] > 0)
        ties = sum(1 for r in rows if r["imp"] == 0)
        losses = sum(1 for r in rows if r["imp"] < 0)
        total_imp = sum(r["imp"] for r in rows)
        total_score = sum(r["delta"] for r in rows)
        print(f"  biq wins:       {wins}, ties: {ties}, losses: {losses}")
        print(f"  NS score delta: {total_score:+d} "
              f"({total_score / n_deals:+.1f}/deal)")
        print(f"  NS IMP delta:   {total_imp:+d} "
              f"({total_imp / n_deals:+.2f}/deal)")
    if skipped:
        print(f"  (skipped: {skipped})")
    if rows:
        by_ns = defaultdict(list)
        for r in rows:
            by_ns[r["ns"]].append(r)
        print("\n## By NS system")
        for ns_name in sorted(by_ns.keys()):
            sub = by_ns[ns_name]
            imp = sum(r["imp"] for r in sub)
            print(f"  {ns_name:<16} n={len(sub):>3}  "
                  f"IMP={imp:+d} ({imp/len(sub):+.2f}/deal)")
    if rows and not brief:
        worst_rows = sorted(rows, key=lambda r: r["imp"])[:worst]
        print()
        print(f"## Worst {min(worst, len(rows))} deals for biq")
        for r in worst_rows:
            print(f"  Deal {r['n']:>3}  "
                  f"qp={_contract_str(r['qp_contract'])} "
                  f"({r['qp_tricks']}tr) vs "
                  f"biq={_contract_str(r['biq_contract'])} "
                  f"({r['biq_tricks']}tr)  imp={r['imp']:+d}")
    return 0


def biq_play_contract_multi(engine, board_template: BoardState,
                              contract: Contract,
                              qplus_auction: List[Bid],
                              configs_by_seat: Dict,
                              num_samples: int = 40) -> Optional[Dict[Seat, int]]:
    """Plan 2 — play a deal with 4 different biq variants at the 4
    seats. Each seat's card decision uses its assigned PlannerConfig.

    Returns {seat: trick_count} or None on failure. Declarer's-side
    tricks is derivable from the contract.declarer + partner totals.
    """
    from backend.models import Trick
    from backend.cardplay_plan import set_planner_config
    declarer = contract.declarer
    trump = contract.suit
    leader = Seat((declarer.value + 1) % 4)
    hands_state = {s: list(board_template.hands[s].cards) for s in
                   (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)}
    completed_tricks: List = []
    tricks_won = {s: 0 for s in (Seat.NORTH, Seat.EAST,
                                  Seat.SOUTH, Seat.WEST)}
    for _trick_num in range(13):
        trick_cards: List[Card] = []
        trick_seats: List[Seat] = []
        seat = leader
        for _play in range(4):
            # Plan 2 hook: swap the planner config for this seat.
            cfg = configs_by_seat.get(seat)
            if cfg is not None:
                set_planner_config(cfg)
            sub_board = BoardState(
                board_number=board_template.board_number,
                dealer=board_template.dealer,
                vulnerability=board_template.vulnerability,
                hands={s: Hand(cards=list(hands_state[s])) for s in
                       (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)},
                auction=list(qplus_auction),
                contract=contract,
                tricks=list(completed_tricks),
            )
            try:
                resp = engine.get_mc_card_play(
                    sub_board, seat,
                    current_trick_cards=list(trick_cards),
                    num_samples=num_samples)
            except Exception:
                return None
            card = resp.action if resp is not None else None
            if card is None or card not in hands_state[seat]:
                lead_suit = trick_cards[0].suit if trick_cards else None
                legal = [c for c in hands_state[seat]
                         if lead_suit is None or c.suit == lead_suit]
                if not legal:
                    legal = hands_state[seat]
                if not legal:
                    return None
                card = legal[0]
            try:
                hands_state[seat].remove(card)
            except ValueError:
                return None
            trick_cards.append(card)
            trick_seats.append(seat)
            seat = Seat((seat.value + 1) % 4)
        winner_idx = _trick_winner(trick_cards, trump)
        winner_seat = trick_seats[winner_idx]
        tricks_won[winner_seat] += 1
        completed_tricks.append(Trick(
            cards=list(trick_cards),
            leader=trick_seats[0],
            winner=winner_seat))
        leader = winner_seat
    return tricks_won


def _make_standard_variants():
    """Plan 2 — four planner-config variants for self-play."""
    from backend.cardplay_plan import PlannerConfig
    variant_A = PlannerConfig()  # baseline = current committed-best
    variant_B = PlannerConfig(phase_25_k_loc_finesse=True)
    variant_C = PlannerConfig(phase_11_return_partner=False)
    variant_D = PlannerConfig(phase_13_4th_best=False)
    return {"A": variant_A, "B": variant_B,
            "C": variant_C, "D": variant_D}


def _run_multi_bot_mode(bdl: Path, mani: Path, *,
                         brief: bool = False, limit: int = 0,
                         mc_samples: int = 40) -> int:
    """Plan 2 mode — play deals with 4 variants at the 4 seats.

    Variant assignment (fixed for MVP):
      N = A (baseline)
      E = B (A + Phase 25 enabled)
      S = C (A − Phase 11)
      W = D (A − Phase 13)

    Per-deal output: tricks won by each seat. Aggregate output:
    average tricks per variant, when variant was declarer-side vs
    defender-side.
    """
    import time as _time
    print(f"# Multi-bot diff — 4 biq variants at the 4 seats")
    print(f"# BDL:      {bdl}")
    print(f"# manifest: {mani}")
    print(f"# biq cardplay: BridgeEngine MC+DDS "
          f"(num_samples={mc_samples})")
    variants = _make_standard_variants()
    seat_to_variant = {Seat.NORTH: "A", Seat.EAST: "B",
                       Seat.SOUTH: "C", Seat.WEST: "D"}
    print("# Variant assignment:")
    for s, v in seat_to_variant.items():
        print(f"#   {s.name:<5} = variant {v}")
    print("#   A=baseline B=+P25-K-loc-finesse "
          "C=-P11-return-partner D=-P13-4th-best")
    if limit:
        print(f"# limit:    first {limit} deals")
    print()
    manifest = json.loads(mani.read_text())
    pair_by_n = {d["deal"]: (d["ns_system"], d["ew_system"])
                 for d in manifest["deals"]}
    bdl_deals = parse_bdl_with_systems(bdl)
    bdl_by_n: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_n:
                bdl_by_n[n] = bd
    bdl_bids_by_label = _parse_bdl_bids_per_deal(bdl)
    from backend.engine import BridgeEngine
    engine = BridgeEngine()
    engine.cardplay_relax_inference = 3
    if not engine.initialize():
        print("[multi-bot] failed to initialize", file=sys.stderr)
        return 1
    configs_by_seat = {s: variants[v]
                        for s, v in seat_to_variant.items()}
    rows: List[Dict] = []
    skipped = 0
    t_start = _time.time()
    deal_keys = sorted(bdl_by_n.keys())
    if limit:
        deal_keys = deal_keys[:limit]
    for i, n in enumerate(deal_keys, 1):
        bd = bdl_by_n[n]
        if n not in pair_by_n:
            skipped += 1
            continue
        ns_sys, _ew_sys = pair_by_n[n]
        bdl_ns_name = _SYSTEM_BY_TAG.get(bd["ns_tag"])
        engine.set_bidding_system(bdl_ns_name or ns_sys)
        board = _board_from_bdl_hands(n, bd)
        qp_auction = bdl_bids_by_label.get(bd["label"]) or []
        qp_contract = _determine_contract(board, qp_auction)
        if qp_contract is None:
            skipped += 1
            continue
        tricks_won = biq_play_contract_multi(
            engine, board, qp_contract, qp_auction,
            configs_by_seat, num_samples=mc_samples)
        if tricks_won is None:
            skipped += 1
            continue
        rows.append({
            "n": n,
            "contract": qp_contract,
            "tricks_won": tricks_won,
        })
        if i % 10 == 0:
            elapsed = _time.time() - t_start
            print(f"# … {i}/{len(deal_keys)} deals "
                  f"({elapsed:.0f}s elapsed)", file=sys.stderr)
    print()
    if not brief:
        print(f"{'#':>3}  {'contract':<10}  "
              f"{'A-N':>4} {'B-E':>4} {'C-S':>4} {'D-W':>4}")
        for r in rows:
            c = r["contract"]
            ctxt = (f"{c.level}{c.suit.to_char()}-{c.declarer.to_char()}"
                    if c else "?")
            tw = r["tricks_won"]
            print(f"{r['n']:>3}  {ctxt:<10}  "
                  f"{tw[Seat.NORTH]:>4} {tw[Seat.EAST]:>4} "
                  f"{tw[Seat.SOUTH]:>4} {tw[Seat.WEST]:>4}")
        print()
    # Aggregate: per-variant declarer-side and defender-side tricks
    print(f"## Aggregate ({len(rows)} deals)")
    role_tricks = {v: {"decl": [], "def": []} for v in variants}
    for r in rows:
        decl = r["contract"].declarer
        decl_partner = Seat((decl.value + 2) % 4)
        for seat in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
            variant = seat_to_variant[seat]
            tricks = r["tricks_won"][seat]
            if seat == decl or seat == decl_partner:
                role_tricks[variant]["decl"].append(tricks)
            else:
                role_tricks[variant]["def"].append(tricks)
    for v, data in role_tricks.items():
        decl_count = len(data["decl"])
        def_count = len(data["def"])
        decl_avg = (sum(data["decl"]) / decl_count
                    if decl_count else 0.0)
        def_avg = (sum(data["def"]) / def_count
                   if def_count else 0.0)
        print(f"  Variant {v}: "
              f"declarer-side avg tricks = {decl_avg:.3f} "
              f"(n={decl_count}), "
              f"defender-side avg tricks = {def_avg:.3f} "
              f"(n={def_count})")
    if skipped:
        print(f"  (skipped: {skipped})")
    return 0


def _run_replay_mode(bdl: Path, mani: Path, *,
                      brief: bool = False, worst: int = 10,
                      limit: int = 0, mc_samples: int = 40) -> int:
    """Plan 1 mode — replay each deal 4× with biq at each seat.

    For each deal × each of the 4 seats, biq plays that seat and
    Q-Plus's recorded cards play the other 3. We compute the
    declarer-side trick count for that replay and compare to
    Q-Plus's recorded declarer-trick count. The trick-delta tells
    us biq's skill AT THAT SEAT in isolation — no biq-vs-biq
    symmetry cancellation.

    Aggregate by:
    - Per-seat delta (biq-as-N vs Q-Plus, etc.).
    - Per-role (biq-as-declarer-side vs biq-as-defender-side).
    """
    import time as _time
    print(f"# Replay diff — biq plays one seat, Q-Plus's recorded "
          f"cards play the other three")
    print(f"# BDL:      {bdl}")
    print(f"# manifest: {mani}")
    print(f"# biq cardplay: BridgeEngine MC+DDS "
          f"(num_samples={mc_samples})")
    if limit:
        print(f"# limit:    first {limit} deals")
    print()
    manifest = json.loads(mani.read_text())
    pair_by_n = {d["deal"]: (d["ns_system"], d["ew_system"])
                 for d in manifest["deals"]}
    bdl_deals = parse_bdl_with_systems(bdl)
    bdl_by_n: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_n:
                bdl_by_n[n] = bd
    bdl_bids_by_label = _parse_bdl_bids_per_deal(bdl)
    qplus_tricks_by_label = _parse_qplus_results(bdl)
    qp_play_by_label = _parse_qplus_play_per_deal(bdl)
    from backend.engine import BridgeEngine
    engine = BridgeEngine()
    engine.cardplay_relax_inference = 3
    if not engine.initialize():
        print("[replay] failed to initialize BridgeEngine — abort",
              file=sys.stderr)
        return 1
    rows: List[Dict] = []
    skipped = 0
    t_start = _time.time()
    deal_keys = sorted(bdl_by_n.keys())
    if limit:
        deal_keys = deal_keys[:limit]
    for i, n in enumerate(deal_keys, 1):
        bd = bdl_by_n[n]
        if n not in pair_by_n:
            skipped += 1
            continue
        ns_sys, _ew_sys = pair_by_n[n]
        bdl_ns_name = _SYSTEM_BY_TAG.get(bd["ns_tag"])
        engine.set_bidding_system(bdl_ns_name or ns_sys)
        board = _board_from_bdl_hands(n, bd)
        qp_auction = bdl_bids_by_label.get(bd["label"]) or []
        qp_contract = _determine_contract(board, qp_auction)
        if qp_contract is None:
            skipped += 1
            continue
        qp_tricks = qplus_tricks_by_label.get(bd["label"])
        qp_play = qp_play_by_label.get(bd["label"])
        if qp_tricks is None or qp_play is None or len(qp_play) < 13:
            skipped += 1
            continue
        per_seat_tricks: Dict[Seat, Optional[int]] = {}
        for biq_seat in (Seat.NORTH, Seat.EAST,
                          Seat.SOUTH, Seat.WEST):
            per_seat_tricks[biq_seat] = biq_replay_at_seat(
                engine, board, qp_contract, qp_auction,
                qp_play, biq_seat, num_samples=mc_samples)
        rows.append({
            "n": n,
            "contract": qp_contract,
            "qp_tricks": qp_tricks,
            "by_seat": per_seat_tricks,
        })
        if i % 5 == 0:
            elapsed = _time.time() - t_start
            print(f"# … {i}/{len(deal_keys)} deals "
                  f"({elapsed:.0f}s elapsed)", file=sys.stderr)
    print()
    if not brief:
        print(f"{'#':>3}  {'contract':<10}  {'qp':>4}  "
              f"{'biq-N':>5} {'biq-E':>5} {'biq-S':>5} {'biq-W':>5}")
        for r in rows:
            c = r["contract"]
            ctxt = (f"{c.level}{c.suit.to_char()}-{c.declarer.to_char()}"
                    if c else "?")
            n_tr = r["by_seat"][Seat.NORTH]
            e_tr = r["by_seat"][Seat.EAST]
            s_tr = r["by_seat"][Seat.SOUTH]
            w_tr = r["by_seat"][Seat.WEST]
            print(f"{r['n']:>3}  {ctxt:<10}  {r['qp_tricks']:>4}  "
                  f"{str(n_tr):>5} {str(e_tr):>5} "
                  f"{str(s_tr):>5} {str(w_tr):>5}")
        print()
    # Aggregate per-seat
    print(f"## Aggregate ({len(rows)} deals)")
    for seat in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
        scored = [r for r in rows
                  if r["by_seat"][seat] is not None]
        if not scored:
            continue
        delta_sum = sum(r["by_seat"][seat] - r["qp_tricks"]
                        for r in scored)
        n_scored = len(scored)
        print(f"  biq-as-{seat.to_char()}: n={n_scored:>3}  "
              f"trick-delta={delta_sum:+d} "
              f"({delta_sum/n_scored:+.3f}/deal)")
    print()
    # Aggregate per-role
    print(f"## By role")
    decl_side_deltas = []
    def_side_deltas = []
    for r in rows:
        decl = r["contract"].declarer
        decl_partner = Seat((decl.value + 2) % 4)
        for seat, tricks in r["by_seat"].items():
            if tricks is None:
                continue
            delta = tricks - r["qp_tricks"]
            if seat == decl or seat == decl_partner:
                decl_side_deltas.append(delta)
            else:
                def_side_deltas.append(delta)
    if decl_side_deltas:
        s = sum(decl_side_deltas)
        n_d = len(decl_side_deltas)
        print(f"  biq plays declarer-side  n={n_d:>3}  "
              f"trick-delta={s:+d} ({s/n_d:+.3f}/deal — "
              f"positive = biq's declarer-side beats Q-Plus's)")
    if def_side_deltas:
        s = sum(def_side_deltas)
        n_d = len(def_side_deltas)
        print(f"  biq plays defender-side  n={n_d:>3}  "
              f"trick-delta={s:+d} ({s/n_d:+.3f}/deal — "
              f"NEGATIVE = biq's defense holds declarer down)")
    if skipped:
        print(f"  (skipped: {skipped})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bdl", required=True, help="path to Q-Plus BDL")
    p.add_argument("--manifest", required=True,
                   help="path to bridgeIQ manifest JSON")
    p.add_argument("--brief", action="store_true",
                   help="aggregate-only output")
    p.add_argument("--worst", type=int, default=10,
                   help="show this many worst (largest IMP-loss) deals")
    p.add_argument("--limit", type=int, default=0,
                   help="cardplay/end-to-end: stop after this many "
                        "deals (0 = all). Useful for smoke-testing.")
    p.add_argument("--mc-samples", type=int, default=5,
                   help="cardplay: MC samples per card decision "
                        "(default 5; higher = stronger but slower).")
    p.add_argument("--enable-p25", action="store_true",
                   help="enable Phase 25 (K-loc-gated AQ finesse) "
                        "in replay/cardplay modes. Default off "
                        "since biq-vs-biq benchmark hid its effect.")
    p.add_argument(
        "--mode",
        choices=("bidding", "cardplay", "end-to-end",
                 "replay", "multi-bot"),
        default="bidding",
        help=("Comparison axis. "
              "'bidding' (default): biq's bidder vs Q-Plus's bidder. "
              "'cardplay': Q-Plus's recorded contract played by BOTH "
              "biq engines (biq-vs-biq, no asymmetric signal). "
              "'end-to-end': each side bids and plays. "
              "'replay': Plan 1 — biq plays one seat at a time vs "
              "Q-Plus's recorded other-three-seat play. Isolates "
              "biq's per-seat skill without biq-vs-biq symmetry "
              "cancellation."))
    args = p.parse_args(argv)
    if args.mode == "cardplay":
        return _run_cardplay_mode(Path(args.bdl), Path(args.manifest),
                                   brief=args.brief, worst=args.worst,
                                   limit=args.limit,
                                   mc_samples=args.mc_samples)
    if args.mode == "end-to-end":
        return _run_end_to_end_mode(
            Path(args.bdl), Path(args.manifest),
            brief=args.brief, worst=args.worst,
            limit=args.limit, mc_samples=args.mc_samples)
    if args.mode == "replay":
        if args.enable_p25:
            from backend.cardplay_plan import (PlannerConfig,
                                                set_planner_config)
            set_planner_config(PlannerConfig(phase_25_k_loc_finesse=True))
        return _run_replay_mode(
            Path(args.bdl), Path(args.manifest),
            brief=args.brief, worst=args.worst,
            limit=args.limit, mc_samples=args.mc_samples)
    if args.mode == "multi-bot":
        return _run_multi_bot_mode(
            Path(args.bdl), Path(args.manifest),
            brief=args.brief, limit=args.limit,
            mc_samples=args.mc_samples)

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
