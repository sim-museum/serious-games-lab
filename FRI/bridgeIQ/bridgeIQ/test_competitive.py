#!/usr/bin/env python3
"""M2 — competitive-bidding truth-table (step 2 of plan_biq_competitive_rework).

Scripted contested positions → the call biq SHOULD make. Like
test_gf_established.py: hard-asserts what biq does NOW (regression guard) and
documents the desired call; the gap is the rework's to-do. Seeded from the
2/1-isolation run's losing deals (seed 2428). As each U-fix lands, flip the
row's `current` to the desired action.

Run: python3 test_competitive.py    (exit 0 = all current calls hold)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.models import (Bid, Seat, Suit, Hand, Card, Rank,        # noqa: E402
                            Vulnerability)
from backend.native_bidder import (parse_auction, evaluate_hand,      # noqa: E402
                                   decide_bid)
from backend.bidding_systems import get_system                        # noqa: E402

_R = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK,
      'T': Rank.TEN, '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
      '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
      '2': Rank.TWO}
_SC = {'c': Suit.CLUBS, 'd': Suit.DIAMONDS, 'h': Suit.HEARTS,
       's': Suit.SPADES, 'n': Suit.NOTRUMP}
_S = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
_SEAT = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_VUL = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
        "EW": Vulnerability.EW, "Both": Vulnerability.BOTH}


def _mk(tok):
    t = tok.lower()
    if t == "p":
        return Bid(is_pass=True)
    if t == "x":
        return Bid(is_double=True)
    if t == "xx":
        return Bid(is_redouble=True)
    m = re.match(r"(\d)(nt|n|[cdhs])", t)
    suit = Suit.NOTRUMP if m.group(2) in ("nt", "n") else _SC[m.group(2)]
    return Bid(level=int(m.group(1)), suit=suit)


def _hand(s):
    cards = []
    for su, part in zip(_S, s.split(".")):
        for c in part:
            if c != '-':
                cards.append(Card(su, _R[c]))
    return Hand(cards=cards)


def _bidstr(b):
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{b.suit.to_char() if b.suit is not None else '?'}"


def call_for(dealer, vul, prefix, seat, hand, system):
    bids = [_mk(t) for t in prefix.split()] if prefix else []
    st = parse_auction(_SEAT[seat], _SEAT[dealer], bids,
                       vulnerability=_VUL[vul])
    return _bidstr(decide_bid(st, evaluate_hand(_hand(hand)),
                              get_system(system)))


# (label, dealer, vul, prefix, seat, hand, system, current, {desired}, note)
CASES = [
    ("2428-19 S overcall 3C preempt", "E", "NS", "3c", "S",
     "Q97642.A3.AJT83.", "TwoOverOne", "3S", {"3S", "X"},
     "U1 FIXED: 6-5 + void-in-their-suit → distributional 3S overcall"),
    ("2428-25 S act over 1S-2S w/ 15", "W", "None", "1s p 2s", "S",
     "A76.AK9.J84.AQ86", "TwoOverOne", "P", {"2N", "X"},
     "U2: 15 HCP balanced + spade stopper must double/2NT, not pass"),
    ("2428-31 N X over 3S preempt", "E", "None", "p p 3s", "N",
     "K7.J432.A5.AJ532", "TwoOverOne", "P", {"X"},
     "U1: 12 HCP, 4-5 in the other suits = takeout double of 3S (ddNS=10)"),
    ("2428-54 N raise 4H over 3S", "N", "NS", "p 1c 1h 1s p 2s 3h 3s", "N",
     "6.76543.K853.984", "TwoOverOne", "4H", {"4H"},
     "U3 FIXED: 5-card support + fit → LAW raise 4H over 3S (Case C)"),
]


def main():
    fails, todos = [], []
    for label, dealer, vul, prefix, seat, hand, system, cur, des, note in CASES:
        got = call_for(dealer, vul, prefix, seat, hand, system)
        if got != cur:
            fails.append((label, cur, got, note))
        if cur not in des:
            todos.append((label, cur, des, note))
    print(f"competitive truth-table — {len(CASES)} positions\n")
    if fails:
        print("✗ CURRENT-CALL REGRESSIONS:")
        for label, cur, got, note in fails:
            print(f"   {label:34} expected {cur}, got {got}\n      {note}")
    else:
        print(f"✓ all {len(CASES)} current calls hold\n")
    print(f"REWORK TO-DO — {len(todos)} positions where biq under-competes:")
    for label, cur, des, note in todos:
        print(f"   {label:34} now={cur} want∈{sorted(des)}  — {note}")
    print("\n(As each U-fix lands, set `current` to the action it now makes.)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
