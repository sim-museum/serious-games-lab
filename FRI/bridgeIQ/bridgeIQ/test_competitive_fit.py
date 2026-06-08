#!/usr/bin/env python3
"""Competitive fit-finding truth-table (Phase-3 #1 fix — see PHASE3_SCOPE.md).

Seeded from the first clean closed-room SAYC/Precision baselines (biq −2.5/deal
vs Q-Plus). Reading the disaster AUCTIONS showed the dominant leak is COMPETITIVE
bidding: once an opponent interferes or biq uses a 2-suited convention, biq loses
its fit and lands in the wrong STRAIN/LEVEL — producing both the under-bids and
the over-bid tail.

Each row scripts a real disaster decision point → the call biq SHOULD make. Like
test_competitive.py / test_gf_established.py: hard-asserts what biq does NOW
(regression guard) and documents the desired call in a set. As each fix lands,
flip the row's `current` to the desired call.

Run: python3 test_competitive_fit.py   (exit 0 = all current calls hold)
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
        "EW": Vulnerability.EW, "All": Vulnerability.BOTH,
        "Both": Vulnerability.BOTH}


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
    ("RANDOM-019 opener after partner's neg-dbl", "S", "EW",
     "1s 2d x p", "S", "KT853.AJT.J.A762", "SAYC",
     "3H", {"3H", "4H"},  # FIXED: was 3C
     "Fix#1: opener has 3-card support for the major partner's negative double "
     "implies (9-card heart fit); raise hearts, do not rebid own clubs (3C)."),
    ("RANDOM-025 raise game w/ 10-card fit (LAW)", "N", "EW",
     "p 1s 2c 3s p", "E", "KQ542.K7.QJ73.65", "SAYC",
     "P", {"4S"},
     "Fix#1/LAW: 11 HCP + 5 spades + a 10-card fit over partner's 3s raise → "
     "bid 4S; passing concedes a cold game."),
    ("RANDOM-043 advance partner's Michaels", "S", "None",
     "p 1d 2d 3c", "S", "T87.A843.JT73.65", "SAYC",
     "P", {"3H", "4H"},
     "Fix#1: partner's 2D is Michaels (both majors); with 4 hearts + 3 spades "
     "compete in the heart fit, do not pass the opponents' 3C."),
    ("RANDOM-039 show slam heart-raise not penalty-X", "S", "All",
     "p 1h 2d", "E", "KJ876.A753.Q.AQJ", "SAYC",
     "X", {"3D", "3H", "4H"},
     "Fix#3: 17 HCP + 4-card support for partner's opened hearts → cuebid/strong "
     "raise toward slam, not a penalty double of 2D."),
    ("RANDOM-010 don't rebid a singleton suit", "E", "All",
     "1s p 2c p 2s x 2nt p", "E", "AK962.2.42.QJ852", "SAYC",
     "3S", {"3C", "3S", "4C"},  # FIXED: was 3H (singleton)
     "Fix#2: 5-5 spades/clubs with a SINGLETON heart — show the club fit (or "
     "spades), never introduce 3H on a singleton (the 3H-5 wrong-strain disaster)."),
    ("RANDOM-020 show 6-card suit not 2NT on a freak", "W", "All",
     "p 1c p 1h p 1s p", "S", "8.AQ962.KQT874.6", "SAYC",
     "2N", {"2D", "3D"},
     "Fix#4: 1-5-6-1 shape (singleton in partner's spades + own club) — rebid "
     "the 6-card diamond suit, not 2NT."),
    ("RANDOM-004 slam try over a limit raise", "W", "All",
     "1s p 3s p", "W", "AKT973.QT95.Q.A6", "SAYC",
     "4S", {"4N", "4C", "4D"},
     "Fix#5: 15 HCP + 6 spades opposite a limit raise (10-card fit) → slam try "
     "(RKC/cuebid), not sign-off 4S (missed cold 6S)."),
]


def main():
    bad = 0
    todo = 0
    for (label, dealer, vul, prefix, seat, hand, system,
         current, desired, note) in CASES:
        got = call_for(dealer, vul, prefix, seat, hand, system)
        status = "ok " if got == current else "CHG"
        fixed = "  <-- FIXED (now desired)" if got in desired else ""
        if got != current:
            bad += 1
        if current not in desired:
            todo += 1
        print(f"[{status}] {label}")
        print(f"        biq now={got!r}  (pinned current={current!r}, "
              f"desired={sorted(desired)}){fixed}")
        if got != current:
            print(f"        !! regression: code changed this call "
                  f"{current!r} -> {got!r}; review.")
    print(f"\n{len(CASES)} cases · {todo} still wrong (current not desired) · "
          f"{bad} moved since pinned")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
