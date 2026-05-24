"""Audit bridgeIQ against textbook rules for each of the 5
bidding systems. Each test crafts a specific hand + auction
context and checks that the bidder makes the textbook call.

Tests are grouped by system. The same test_id can appear in
multiple systems (e.g. "1NT-opener" appears in all five but the
HCP threshold differs). Tests should be PRINCIPLED — they
correspond to specific rules from standard textbooks (SAYC
Yellow Card; "Standard Bidding with SAYC" by Ned Downey;
"Standard French" by Robert Berthe; etc.).

Run:
    python3 tools/system_audit.py
    python3 tools/system_audit.py --system Precision90M
    python3 tools/system_audit.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional, Tuple

PKG = Path("/home/h/sgl/FRI/bridgeIQ/bridgeIQ")
sys.path.insert(0, str(PKG))

from backend.native_bidder import (
    decide_bid, evaluate_hand, parse_auction,
)
from backend.models import (
    Bid, Card, Hand, Rank, Seat, Suit, Vulnerability,
)
from backend.bidding_systems import get_system


# ---------------------------------------------------------------------------
# Hand construction helpers
# ---------------------------------------------------------------------------

RANK_CHAR_TO_RANK = {
    'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN,
    'J': Rank.JACK, 'T': Rank.TEN, '9': Rank.NINE,
    '8': Rank.EIGHT, '7': Rank.SEVEN, '6': Rank.SIX,
    '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
    '2': Rank.TWO,
}


def hand(spades: str = "", hearts: str = "", diamonds: str = "",
         clubs: str = "") -> Hand:
    """Make a Hand from suit strings like 'AKQ', 'JT9', '8642', '5'."""
    cards = []
    for suit, s in ((Suit.SPADES, spades), (Suit.HEARTS, hearts),
                    (Suit.DIAMONDS, diamonds), (Suit.CLUBS, clubs)):
        for ch in s:
            cards.append(Card(suit, RANK_CHAR_TO_RANK[ch]))
    return Hand(cards=cards)


def bid_str(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    suit_c = ("S" if b.suit == Suit.SPADES else
              "H" if b.suit == Suit.HEARTS else
              "D" if b.suit == Suit.DIAMONDS else
              "C" if b.suit == Suit.CLUBS else
              "NT" if b.suit == Suit.NOTRUMP else "?")
    return f"{b.level}{suit_c}"


def parse_bid(s: str) -> Bid:
    s = s.upper().strip()
    if s in ('P', 'PASS'):
        return Bid.make_pass()
    if s == 'X':
        return Bid.make_double()
    if s == 'XX':
        return Bid.make_redouble()
    level = int(s[0])
    suit_c = s[1:]
    suit = {'C': Suit.CLUBS, 'D': Suit.DIAMONDS, 'H': Suit.HEARTS,
            'S': Suit.SPADES, 'NT': Suit.NOTRUMP, 'N': Suit.NOTRUMP}[suit_c]
    return Bid(level=level, suit=suit)


def bid_in_one_of(b: Bid, acceptable: List[str]) -> bool:
    return bid_str(b) in [s.upper() for s in acceptable]


# ---------------------------------------------------------------------------
# Test type: each test runs the bidder with a given hand + auction
# prefix and checks the result against an acceptable set.
# ---------------------------------------------------------------------------

class Test:
    def __init__(self, test_id: str, description: str,
                 my_seat: Seat, my_hand: Hand,
                 dealer: Seat, auction_prefix: List[Bid],
                 accept: List[str],
                 vulnerability: Vulnerability = Vulnerability.NONE):
        self.id = test_id
        self.description = description
        self.my_seat = my_seat
        self.my_hand = my_hand
        self.dealer = dealer
        self.auction_prefix = auction_prefix
        self.accept = accept
        self.vulnerability = vulnerability

    def run(self, system_name: str) -> Tuple[bool, Bid, str]:
        sys_ = get_system(system_name)
        state = parse_auction(self.my_seat, self.dealer,
                              list(self.auction_prefix),
                              vulnerability=self.vulnerability)
        e = evaluate_hand(self.my_hand)
        b = decide_bid(state, e, sys_)
        ok = bid_in_one_of(b, self.accept)
        return ok, b, f"{system_name}: expected ∈ {self.accept}, got {bid_str(b)}"


# ---------------------------------------------------------------------------
# Tests, organised by system. Each system inherits a "common SAYC-like"
# baseline; system-specific tests override / extend.
#
# The hand for each test is hand-picked to illustrate a single rule.
# Multiple acceptable bids are allowed where bridge style permits
# variation (e.g. 1NT opener with 5cM could be 1NT or 1M depending
# on flag).
# ---------------------------------------------------------------------------

def common_tests() -> List[Test]:
    """Tests that should pass for all 5 systems with minor variations.
    Each test's `accept` list will be tweaked per system below."""
    return []  # systems define their own tests below


SAYC_TESTS: List[Test] = [
    # ---- 1NT opening, 15-17 balanced ----
    Test("sayc-1nt-flat", "1NT open: 16 HCP 4-3-3-3",
         Seat.SOUTH,
         hand("AQ43", "K76", "Q92", "AJ4"),
         Seat.SOUTH, [], ["1NT"]),
    Test("sayc-1nt-5332", "1NT open: 5-3-3-2 with 5 spades is "
         "allowed by flag",
         Seat.SOUTH,
         hand("AQ432", "K7", "Q92", "AJ4"),
         Seat.SOUTH, [], ["1NT", "1S"]),
    Test("sayc-no-1nt-too-strong", "Don't open 1NT with 18+",
         Seat.SOUTH,
         hand("AQ43", "K76", "AJ2", "AJ4"),  # 18 HCP
         Seat.SOUTH, [], ["1C", "1D", "1H", "1S"]),

    # ---- 1 of major (5+ cards) ----
    Test("sayc-1h-5cards", "1H open: 12+ HCP, 5+ hearts",
         Seat.SOUTH,
         hand("Q3", "AKJ52", "Q72", "T84"),
         Seat.SOUTH, [], ["1H"]),
    Test("sayc-1s-5cards", "1S open: 12+ HCP, 5+ spades",
         Seat.SOUTH,
         hand("AKJ52", "Q72", "T84", "Q3"),
         Seat.SOUTH, [], ["1S"]),

    # ---- 1 of minor: open the longer minor (when below 1NT range) ----
    Test("sayc-better-minor-D", "1D open: 12 HCP, 5+ diamonds, "
         "below 1NT range",
         Seat.SOUTH,
         hand("Q3", "K94", "AJ872", "Q84"),  # 11 HCP, 2-3-5-3
         Seat.SOUTH, [], ["1D"]),
    Test("sayc-better-minor-C", "1C open: 13 HCP balanced no "
         "5cM, longer clubs (3-card clubs vs 2-card diamonds)",
         Seat.SOUTH,
         hand("KQ72", "AJ87", "98", "K43"),  # 13 HCP, 4-4-2-3
         Seat.SOUTH, [], ["1C"]),

    # ---- Strong 2C ----
    Test("sayc-2c-22hcp", "2C open: 22+ HCP",
         Seat.SOUTH,
         hand("AKQ", "AKQ", "AKQ", "AKQ4"),  # 28 HCP — huge
         Seat.SOUTH, [], ["2C"]),

    # ---- Weak twos ----
    Test("sayc-weak-2h-6card", "Weak 2H: 6+ hearts, 5-10 HCP",
         Seat.SOUTH,
         hand("Q3", "KQJ872", "T84", "75"),  # 8 HCP, 6H
         Seat.SOUTH, [], ["2H"]),
    Test("sayc-weak-2h-10hcp", "Weak 2H: 10 HCP + 6H still weak-2",
         Seat.SOUTH,
         hand("K3", "KQ8732", "Q974", "6"),  # 10 HCP, 6H — exemplar bd 2
         Seat.SOUTH, [], ["2H"]),
    Test("sayc-no-weak-2-junk", "Don't open weak-2 with junk suit",
         Seat.SOUTH,
         hand("Q3", "J86432", "AT4", "K5"),  # 8 HCP, suit J-high
         Seat.SOUTH, [], ["P"]),

    # ---- Rule of 20 ----
    Test("sayc-rule-of-20-1S", "Rule of 20: 10 HCP + 6-card spade "
         "+ 4-card heart → open 1S",
         Seat.SOUTH,
         hand("AKJ742", "Q943", "8", "65"),  # 10 HCP, 6+4=10, R20=20
         Seat.SOUTH, [], ["1S"]),

    # ---- Negative double over interference ----
    Test("sayc-neg-dbl", "Neg double: 6+ HCP, 4+ unbid major after "
         "1m-(1H)",
         Seat.NORTH,
         hand("KJ72", "9", "T872", "AJ95"),  # 4S + 4C, 11 HCP
         Seat.SOUTH,
         [parse_bid("1D"), parse_bid("1H")],
         ["X"]),

    # ---- Stayman ----
    Test("sayc-stayman", "Stayman over 1NT: 4-card major + 8+ HCP",
         Seat.NORTH,
         hand("KJ72", "Q943", "Q8", "K94"),
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         ["2C"]),

    # ---- Jacoby transfer ----
    Test("sayc-transfer-H", "Jacoby transfer to hearts: 5+H",
         Seat.NORTH,
         hand("Q9", "KJ872", "Q92", "843"),
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         ["2D"]),
    Test("sayc-transfer-S", "Jacoby transfer to spades: 5+S",
         Seat.NORTH,
         hand("KJ872", "Q9", "Q92", "843"),
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         ["2H"]),

    # ---- Jacoby 2NT ----
    Test("sayc-j2nt", "Jacoby 2NT: 4+ support + 13+ HCP GF",
         Seat.NORTH,
         hand("AK87", "Q943", "AQ2", "94"),  # 13 HCP, 4cH
         Seat.SOUTH, [parse_bid("1H")],
         ["2NT"]),
]


TWO_OVER_ONE_TESTS: List[Test] = [
    # 2/1 inherits most SAYC opening rules but key differences:
    # forcing-1NT response, 2/1 GF responses.
    Test("2o1-1nt-flat", "1NT 15-17 balanced",
         Seat.SOUTH,
         hand("AQ43", "K76", "Q92", "AJ4"),
         Seat.SOUTH, [], ["1NT"]),
    Test("2o1-weak-2h", "Weak 2H 5-10 HCP, 6+ suit",
         Seat.SOUTH,
         hand("Q3", "KQJ872", "T84", "75"),
         Seat.SOUTH, [], ["2H"]),

    # ---- 2/1 GF responses ----
    Test("2o1-forcing-1nt", "Forcing 1NT response: 6-12 HCP, no "
         "3-card+ major support raise possible",
         Seat.NORTH,
         hand("Q72", "843", "KJ9", "QT82"),  # 9 HCP, 3cH (acceptable
                                                # to bid 2H or 1NT-F)
         Seat.SOUTH, [parse_bid("1H")],
         ["1NT", "2H"]),  # both standard
    Test("2o1-gf-2c", "2/1 GF: 13+ HCP, 5+ clubs over 1H",
         Seat.NORTH,
         hand("Q72", "84", "K9", "AKQT82"),  # 14 HCP, 6c
         Seat.SOUTH, [parse_bid("1H")],
         ["2C"]),

    # ---- Forcing-1NT + opener's rebid ----
    Test("2o1-forcing-1nt-opener-rebid",
         "Opener rebids over forcing-1NT (cannot pass)",
         Seat.SOUTH,
         hand("Q3", "AKJ52", "Q72", "T84"),  # 12 HCP, 5cH
         Seat.SOUTH, [parse_bid("1H"), parse_bid("P"),
                      parse_bid("1NT"), parse_bid("P")],
         ["2H", "2C", "2D"]),  # any rebid OK, not P
]


ACOL_TESTS: List[Test] = [
    # Acol-specific: weak NT 12-14, 4-card majors, strong twos.
    Test("acol-1nt-weak", "1NT open: 12-14 (weak NT)",
         Seat.SOUTH,
         hand("KJ4", "K76", "QJ92", "Q74"),  # 12 HCP
         Seat.SOUTH, [], ["1NT"]),
    Test("acol-no-1nt-15", "Don't open 1NT with 15 (out of range)",
         Seat.SOUTH,
         hand("AQ43", "K76", "Q92", "AJ4"),  # 15 HCP
         Seat.SOUTH, [], ["1S", "1C", "1D", "1H"]),

    Test("acol-1h-4card", "1H open: 4-card heart allowed in Acol",
         Seat.SOUTH,
         hand("K72", "AKJ4", "Q982", "Q4"),  # 13 HCP, 4cH, balanced
         Seat.SOUTH, [], ["1H", "1NT"]),  # either 1H or 1NT acceptable

    Test("acol-strong-2h", "Strong 2H: 16+ HCP + 5+ hearts (Acol two)",
         Seat.SOUTH,
         hand("AK", "AKQT72", "AKJ", "94"),  # 20 HCP, 6cH, strong
         Seat.SOUTH, [], ["2H", "2C"]),  # 2H Acol-two or 2C strong artificial

    Test("acol-no-weak-2", "Don't open weak 2H in Acol (strong twos)",
         Seat.SOUTH,
         hand("Q3", "KQJ872", "T84", "75"),  # 8 HCP, 6cH — weak
         Seat.SOUTH, [], ["P"]),
]


FRENCH_TESTS: List[Test] = [
    # Standard French — close to SAYC with French quirks. French
    # doesn't have Jacoby 2NT, so we override the SAYC test by
    # giving an alternative accepted call.
    Test("sayc-j2nt", "French: 1H-X (13 HCP 4cH balanced) - either "
         "natural 2NT or 4H game raise",
         Seat.NORTH,
         hand("AK87", "Q943", "AQ2", "94"),
         Seat.SOUTH, [parse_bid("1H")],
         ["2NT", "4H"]),  # French: no Jacoby 2NT, so 4H jump OK
    Test("french-1nt-flat", "1NT 15-17 balanced",
         Seat.SOUTH,
         hand("AQ43", "K76", "Q92", "AJ4"),
         Seat.SOUTH, [], ["1NT"]),
    Test("french-natural-2nt-resp",
         "1H-2NT: natural invite (11-12 balanced, 3-card support)",
         Seat.NORTH,
         hand("Q72", "K84", "AT9", "QJ82"),  # 11 HCP, 3cH balanced
         Seat.SOUTH, [parse_bid("1H")],
         ["2NT"]),
    Test("french-weak-2d", "Weak 2D allowed in French",
         Seat.SOUTH,
         hand("Q3", "T84", "KQJ872", "75"),  # 8 HCP, 6cD
         Seat.SOUTH, [], ["2D"]),
]


PRECISION_TESTS: List[Test] = [
    # Precision90M — strong 1C, limited other openings.
    Test("prec-strong-1c", "Strong 1C: 16+ HCP, any shape",
         Seat.SOUTH,
         hand("AQ43", "AJ72", "K92", "K4"),  # 17 HCP balanced — strong NT range
         Seat.SOUTH, [], ["1NT", "1C"]),  # could be either by NT-range gate
    Test("prec-1c-unbalanced-17",
         "1C: 17 HCP unbalanced (above NT range)",
         Seat.SOUTH,
         hand("AKQJ7", "AJ72", "K92", "4"),  # 17 HCP, 5-4-3-1
         Seat.SOUTH, [], ["1C"]),

    Test("prec-1nt-14-16", "1NT open: 14-16 balanced (Precision90M)",
         Seat.SOUTH,
         hand("AKJ3", "K76", "QJ92", "Q4"),  # 14 HCP — A+K+J+K+Q+J+Q=15... let me redo
         Seat.SOUTH, [], ["1NT", "1C"]),  # could be 1C strong if too strong, 1NT in range

    Test("prec-1d-catchall",
         "1D catch-all: 11-13 unbalanced, no 5cM, fewer clubs",
         Seat.SOUTH,
         hand("Q72", "94", "AQJ852", "K4"),  # 11 HCP, 6D — out of NT range
         Seat.SOUTH, [], ["1D"]),

    Test("prec-2c-longclub",
         "2C long-club: 11-15 + 6+ clubs",
         Seat.SOUTH,
         hand("Q3", "84", "K72", "AKJ872"),  # 12 HCP, 6cC
         Seat.SOUTH, [], ["2C"]),

    Test("prec-2d-3suiter",
         "2D three-suiter: 11-15 + 4+/3+ majors + 0-1 diamonds",
         Seat.SOUTH,
         hand("AQJ7", "K972", "8", "Q432"),  # 12 HCP, 4-4-1-4
         Seat.SOUTH, [], ["2D"]),
]


ALL_TESTS = {
    "SAYC":           SAYC_TESTS,
    "TwoOverOne":     TWO_OVER_ONE_TESTS + SAYC_TESTS,
    "StandardAcol":   ACOL_TESTS,
    "StandardFrench": FRENCH_TESTS + SAYC_TESTS,
    "Precision90M":   PRECISION_TESTS,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", help="filter to one system")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    total_pass = 0
    total_fail = 0
    fails_by_system = defaultdict(list)
    for system_name, tests in ALL_TESTS.items():
        if args.system and system_name != args.system:
            continue
        # De-dup tests (SAYC tests included in 2/1 etc.)
        seen = set()
        unique = []
        for t in tests:
            if t.id in seen:
                continue
            seen.add(t.id)
            unique.append(t)
        print(f"\n## {system_name} — {len(unique)} tests")
        n_pass = n_fail = 0
        for t in unique:
            ok, b, msg = t.run(system_name)
            if ok:
                n_pass += 1
                if args.verbose:
                    print(f"  ✓ {t.id:30s}  → {bid_str(b)}  "
                          f"({t.description})")
            else:
                n_fail += 1
                fails_by_system[system_name].append((t.id, b, t))
                print(f"  ✗ {t.id:30s}  → {bid_str(b)}  "
                      f"(expected ∈ {t.accept}) — {t.description}")
        print(f"  {n_pass}/{n_pass+n_fail} pass")
        total_pass += n_pass
        total_fail += n_fail
    print(f"\n# Aggregate: {total_pass}/{total_pass+total_fail} pass")
    if fails_by_system:
        print("\n# Failure summary:")
        for s, fs in fails_by_system.items():
            print(f"  {s}: {len(fs)} failures")
            for tid, b, _t in fs[:5]:
                print(f"    - {tid}: got {bid_str(b)}")


if __name__ == "__main__":
    sys.exit(main())
