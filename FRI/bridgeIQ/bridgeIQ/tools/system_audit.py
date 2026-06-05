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

    # ---- Splinter: jump in shortness suit over 1M ----
    Test("sayc-splinter-1s-4c", "Splinter 1S-4C: 4+ spades + "
         "singleton clubs + 13-15 HCP",
         Seat.NORTH,
         hand("KQ87", "AQ32", "K983", "5"),  # 13 HCP, 4S 1C
         Seat.SOUTH, [parse_bid("1S")],
         ["4C"]),

    # ---- Michaels cue bid (5+/5+ unbid suits) ----
    Test("sayc-michaels-1h", "Michaels (1H)-2H: 5+ spades + 5+ "
         "in a minor",
         Seat.SOUTH,
         hand("KJ872", "5", "Q9543", "K76"),  # 5-1-5-3, 9 HCP
         Seat.WEST, [parse_bid("1H")],  # I am S, RHO E opened...
         # Actually dealer is W for this test; my seat is S which is
         # to W's right. Let me adjust the seating: it's (1H by W)
         # then we're acting as N's overcall direct.
         # Simpler: dealer W opens 1H, I am N (LHO) — but N would
         # play 2nd. Let me just place the auction.
         ["2H"]),

    # ---- Unusual 2NT: both minors 5-5+ ----
    Test("sayc-unusual-2nt", "Unusual 2NT over 1S: 5-5 in the "
         "two lower unbid suits (clubs + diamonds for SAYC)",
         Seat.NORTH,  # 2nd seat overcaller (after dealer W's 1S)
         hand("4", "A4", "KJ873", "KQ876"),  # 1-2-5-5, 11 HCP
         Seat.WEST, [parse_bid("1S")],
         ["2NT"]),

    # ---- Fourth-suit forcing ----
    Test("sayc-4sf", "Fourth-suit forcing: 1C-1H-1S-2D = 4SF "
         "(GF artificial inquiry)",
         Seat.NORTH,
         hand("4", "AKJ87", "Q872", "Q63"),  # 13 HCP, 5H 4D 3C
         Seat.SOUTH,
         [parse_bid("1C"), parse_bid("P"),
          parse_bid("1H"), parse_bid("P"),
          parse_bid("1S"), parse_bid("P")],
         ["2D", "3NT"]),  # 2D 4SF or 3NT direct

    # ---- Opener's reverse (16+ HCP, second suit higher rank) ----
    Test("sayc-reverse", "Reverse: 1D-1H-2S shows 16+ HCP + "
         "longer diamonds than spades",
         Seat.SOUTH,
         hand("KQ87", "5", "AKQ872", "A4"),  # 17 HCP, 4-1-6-2
         Seat.SOUTH,
         [parse_bid("1D"), parse_bid("P"),
          parse_bid("1H"), parse_bid("P")],
         ["2S"]),

    # ---- Strong 2C opening (22+ HCP or 9+ playing tricks) ----
    Test("sayc-strong-2c", "Strong 2C: 22+ HCP balanced",
         Seat.SOUTH,
         hand("AKQ", "AKQ4", "AK4", "K94"),  # 25 HCP balanced
         Seat.SOUTH, [], ["2C"]),

    # ---- 2C-2D waiting response ----
    Test("sayc-2c-waiting", "2C-2D: standard waiting response (or "
         "double-neg with 0-3 HCP)",
         Seat.NORTH,
         hand("Q72", "843", "T9876", "T8"),  # 2 HCP
         Seat.SOUTH, [parse_bid("2C")],
         ["2D"]),

    # ---- Takeout double ----
    Test("sayc-takeout-dbl", "Takeout double of 1H: 12+ HCP, "
         "support for other 3 suits",
         Seat.NORTH,  # 2nd-seat overcaller (RHO=West opens 1H)
         hand("KQ72", "5", "AJ94", "K982"),  # 13 HCP, 4-1-4-4
         Seat.WEST, [parse_bid("1H")],
         ["X"]),

    # ---- Cuebid response to takeout double (GF, 13+ HCP) ----
    Test("sayc-cuebid-to-takeout",
         "Cuebid response to partner's takeout dbl: 13+ HCP GF",
         Seat.NORTH,  # 4th seat: LHO=E opens, partner=S X, RHO=W P
         hand("KJ72", "K84", "AQ94", "J8"),  # 14 HCP
         Seat.EAST,
         [parse_bid("1H"), parse_bid("X"), parse_bid("P")],
         ["2H", "3NT"]),  # cuebid or 3NT direct

    # ---- RKC Blackwood after major-suit fit ----
    Test("sayc-rkc-after-fit", "RKC 4NT after 1S-3S: 17+ HCP + "
         "4-card support → slam try",
         Seat.SOUTH,
         hand("AKQ72", "AQ4", "KQ4", "K2"),  # 21 HCP, 5cS
         Seat.SOUTH, [parse_bid("1S"), parse_bid("P"),
                      parse_bid("3S"), parse_bid("P")],
         ["4NT", "4S"]),  # 4NT RKC slam try or 4S signoff

    # ---- Negative double with 4-card unbid major ----
    Test("sayc-neg-dbl-1s",
         "Negative dbl over 1C-(1S): 4+ hearts, 6+ HCP",
         Seat.NORTH,
         hand("Q72", "KJ84", "Q94", "J82"),  # 9 HCP, 4cH
         Seat.SOUTH,
         [parse_bid("1C"), parse_bid("1S")],
         ["X"]),

    # ---- 2NT opening: 20-21 balanced ----
    Test("sayc-2nt-open", "2NT open: 20-21 balanced",
         Seat.SOUTH,
         hand("AKQ", "AJ4", "KQT2", "Q94"),  # 21 HCP balanced (3-3-4-3)
         Seat.SOUTH, [], ["2NT"]),

    # ---- 2NT response (Jacoby 2NT) follow-up by opener ----
    Test("sayc-j2nt-opener-rebid-mini",
         "After 1H-2NT (Jacoby), minimum opener (12-14) rebids 4H",
         Seat.SOUTH,
         hand("Q83", "AKJ72", "Q94", "K4"),  # 13 HCP, 5cH
         Seat.SOUTH, [parse_bid("1H"), parse_bid("P"),
                      parse_bid("2NT"), parse_bid("P")],
         # Minimum opener can sign off in 4H (no slam interest),
         # show a singleton (3C/3D/3S), or rebid 3NT (no short).
         ["4H", "3NT", "3H"]),

    # ---- Stayman follow-up after 1NT-2C-2D (no major) ----
    Test("sayc-stayman-followup-no-fit",
         "1NT-2C-2D: no major fit, 8-9 HCP balanced → 2NT inv",
         Seat.NORTH,
         hand("KJ72", "Q943", "Q98", "94"),  # 8 HCP, 4-4 majors
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P"),
                      parse_bid("2C"), parse_bid("P"),
                      parse_bid("2D"), parse_bid("P")],
         ["2NT", "P"]),  # 2NT inv or pass with min

    # ---- Jacoby transfer follow-up: 5H + 6-7 HCP → pass ----
    Test("sayc-transfer-pass",
         "Jacoby transfer 1NT-2D-2H: 6 HCP 5cH → pass (signoff)",
         Seat.NORTH,
         hand("843", "KJ872", "Q92", "84"),  # 6 HCP, 5cH
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P"),
                      parse_bid("2D"), parse_bid("P"),
                      parse_bid("2H"), parse_bid("P")],
         ["P"]),

    # ---- Preempt: 3-of-suit opening with 7-card suit ----
    Test("sayc-preempt-3c",
         "3C preempt: 7-card suit with top honor, 5-9 HCP",
         Seat.SOUTH,
         hand("8", "97", "K84", "AT98762"),  # 7 HCP, 7cC suit-HCP=4
         Seat.SOUTH, [], ["3C"]),

    # ---- Penalty redouble after 1-of-major doubled by RHO ----
    Test("sayc-redouble-after-X",
         "1H-(X)-XX: 10+ HCP, no major fit shown",
         Seat.NORTH,
         hand("KQ72", "84", "AJ92", "K84"),  # 13 HCP, 2cH (no fit)
         Seat.SOUTH, [parse_bid("1H"), parse_bid("X")],
         ["XX"]),

    # ---- 1NT response to 1m (forcing in 2/1, semi-forcing in SAYC) ----
    Test("sayc-1nt-response-to-1m",
         "1m-1NT: 6-10 HCP balanced, no 4-card major",
         Seat.NORTH,
         hand("843", "K84", "QJ92", "Q982"),  # 8 HCP, no 4cM
         Seat.SOUTH, [parse_bid("1D")],
         ["1NT"]),

    # ---- Stayman finds 4-4 spade fit ----
    Test("sayc-stayman-finds-spade-fit",
         "After 1NT-2C-2S: 4cS + 10+ HCP → raise to 4S",
         Seat.NORTH,
         hand("KJ72", "Q943", "Q92", "94"),  # 9 HCP, 4-4 majors
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P"),
                      parse_bid("2C"), parse_bid("P"),
                      parse_bid("2S"), parse_bid("P")],
         # 9 HCP, 4cS fit. Invitational raise (3S) or game (4S) ok.
         ["3S", "4S"]),

    # ---- Splinter in hearts (1H-4D = singleton diamonds) ----
    Test("sayc-splinter-1h-4d",
         "Splinter 1H-4D: 4+ hearts + singleton/void D + 13-15 HCP",
         Seat.NORTH,
         hand("AQ52", "KQ32", "5", "A983"),  # 14 HCP, 4cH 1cD
         Seat.SOUTH, [parse_bid("1H")],
         ["4D"]),

    # ---- Limit raise (jump to 3-of-major with 10-12 HCP) ----
    Test("sayc-limit-raise",
         "1S-3S: limit raise (10-12 HCP, 4-card support)",
         Seat.NORTH,
         hand("KJ72", "K84", "Q94", "Q92"),  # 11 HCP, 4cS
         Seat.SOUTH, [parse_bid("1S")],
         # SAYC mainstream: 3S (direct limit). 2/1 with Bergen
         # raises: 3C (constructive limit). Both standard.
         ["3S", "3C"]),

    # ---- Strong jump shift (1m-2M, 17+ HCP) ----
    Test("sayc-jump-shift",
         "1D-2S: jump shift, 17+ HCP, 5+ spades",
         Seat.NORTH,
         hand("AKQ72", "AQ4", "Q92", "K4"),  # 19 HCP, 5cS
         Seat.SOUTH, [parse_bid("1D")],
         # SAYC: jump shift (strong); 2/1: many play this as
         # weak — accept either 2S (jump) or 1S (forcing 1-level).
         ["2S", "1S"]),

    # ---- 1NT response when opener bid 1m ----
    Test("sayc-2nt-response-invitational",
         "1S-2NT in SAYC (Jacoby 2NT) — but with only 3-card support",
         Seat.NORTH,
         hand("K72", "Q84", "AQ92", "QJ82"),  # 13 HCP balanced, 3cS
         Seat.SOUTH, [parse_bid("1S")],
         # With 3-card support + 13 HCP + balanced, options are
         # 2NT (Jacoby — but promises 4+ trumps) OR 2C/2D (new
         # suit, F1) OR 3NT direct. Mainstream SAYC: 2-of-a-minor
         # natural F1 then NT later. Accept any sensible call.
         ["2C", "2D", "3NT", "2NT"]),

    # ---- Quantitative 4NT after 1NT (invite to 6NT) ----
    Test("sayc-quant-4nt",
         "1NT-4NT: quantitative slam invite, 16-17 HCP balanced",
         Seat.NORTH,
         hand("AQ72", "K84", "AQ92", "K8"),  # 17 HCP balanced, 4cS
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         # 17 HCP + 1NT (15-17) = 32-34, slam-invitational.
         # Style 1: 4NT quantitative directly.
         # Style 2: Stayman first (check 4-4 spade fit) then 4NT.
         # Both textbook for 16-17 with a 4-card major.
         ["4NT", "6NT", "2C"]),

    # ---- Texas transfer to 4H ----
    Test("sayc-texas-transfer",
         "1NT-4D Texas (transfer to 4H, 6+ hearts, game values)",
         Seat.NORTH,
         hand("K3", "KQJ872", "Q9", "843"),  # 11 HCP, 6cH
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         # Standard: 4D Texas transfer to 4H (preempt-style),
         # or 2D transfer (Jacoby) then bid 4H. Accept either.
         ["4D", "2D"]),

    # ---- Smolen: 5cM after Stayman with no fit ----
    Test("sayc-smolen-5-4",
         "1NT-2C-2D-3H: Smolen (5cS+4cH GF, asks opener to bid game)",
         Seat.NORTH,
         hand("KJ872", "AQ43", "Q9", "84"),  # 12 HCP, 5cS 4cH
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P"),
                      parse_bid("2C"), parse_bid("P"),
                      parse_bid("2D"), parse_bid("P")],
         # Smolen treatment: 3H = 5cS+4cH (lower-suit jump). Or
         # natural 3S (own 5-card) is also acceptable in many
         # styles. Game-force values.
         ["3H", "3S", "3NT"]),

    # ---- Gerber 4C over 1NT (ace ask) ----
    Test("sayc-gerber-4c",
         "1NT-4C: Gerber ace-ask, 16+ HCP slam-try with 6+ suit",
         Seat.NORTH,
         hand("AKQJ72", "K8", "A9", "K84"),  # 19 HCP, 6cS
         Seat.SOUTH, [parse_bid("1NT"), parse_bid("P")],
         # Several treatments: Gerber 4C, Texas 4D (transfer to
         # 4H — wait we have spades, so 4H transfer to 4S),
         # Jacoby 2H transfer to 2S then slam-try.
         ["4C", "4H", "4S", "2C", "2H", "6S", "6NT"]),

    # ---- Lebensohl: 2NT after weak-2-doubled ----
    Test("sayc-lebensohl-after-weak2-x",
         "2H-(X)-?: 8 HCP, 4cS — bid 2S natural (no Lebensohl needed)",
         Seat.NORTH,  # 4th seat advancer to partner's takeout X
         hand("KJ72", "5", "Q9843", "Q84"),  # 8 HCP, 4cS
         Seat.EAST,  # E opens weak 2H, S X, W P, N bids
         [parse_bid("2H"), parse_bid("X"), parse_bid("P")],
         # 4-card spade with 8 HCP after partner's takeout X
         # of weak 2H: simple 2S advance.
         ["2S"]),

    # ---- Truscott/Jordan 2NT: limit raise of partner's major
    # after RHO doubles for takeout ----
    Test("sayc-truscott-2nt",
         "1H-(X)-2NT: 4+ heart support, 10-12 HCP, limit raise",
         Seat.NORTH,
         hand("Q72", "KJ84", "AT9", "Q92"),  # 11 HCP, 4cH
         Seat.SOUTH,
         [parse_bid("1H"), parse_bid("X")],
         # Modern style: 2NT shows 4-card limit raise (Truscott
         # or Jordan 2NT). Bridgemate-style alternatives: redouble
         # (10+, no fit) or direct 3H (preemptive). Accept either
         # 2NT (textbook) or 3H (raise) or XX (redouble).
         ["2NT", "3H", "XX"]),

    # ---- Reopening double in 4th seat ----
    Test("sayc-reopening-double",
         "1H-(P)-(P)-X: reopening takeout double, 11+ HCP, shortness",
         Seat.SOUTH,  # 4th seat
         hand("KJ72", "5", "AQ983", "K984"),  # 13 HCP, 1H
         Seat.WEST,
         [parse_bid("1H"), parse_bid("P"), parse_bid("P")],
         # In 4th seat after 1H-P-P, partner is marked with values
         # (couldn't act over 1H because of shape, not strength).
         # Reopen with takeout X showing shortness in opener's suit.
         ["X"]),

    # ---- 1NT response in competition ----
    Test("sayc-1nt-competitive",
         "1S-(2C)-2NT: invitational raise/NT, 11+ HCP, stopper in C",
         Seat.NORTH,
         hand("Q72", "K84", "K92", "KJ82"),  # 13 HCP, 3cS, C stopper
         Seat.SOUTH,
         [parse_bid("1S"), parse_bid("2C")],
         # With 13 HCP + 3-card spade support + balanced + club
         # stopper, standard is 2NT (natural invitational, 11-12).
         # Could also bid 3S (3-card support, limit raise) or
         # negative-X for takeout. Accept any sensible call.
         ["2NT", "3NT", "3S", "X"]),

    # ---- Strong 2C rebid: 2NT shows 22-24 balanced ----
    Test("sayc-2c-2nt-rebid",
         "2C-2D-2NT: 22-24 balanced (opener's NT rebid)",
         Seat.SOUTH,
         hand("AKJ4", "AQ3", "KQ2", "KJ4"),  # 23 HCP balanced
         Seat.SOUTH,
         [parse_bid("2C"), parse_bid("P"),
          parse_bid("2D"), parse_bid("P")],
         ["2NT"]),

    # ---- Strong jump rebid by opener (16-17 HCP, 6+ suit) ----
    Test("sayc-jump-rebid",
         "1H-1S-3H: jump rebid of own suit (16-17 HCP, 6+ hearts)",
         Seat.SOUTH,
         hand("Q3", "AKQT72", "K94", "AQ"),  # 18 HCP, 6cH
         Seat.SOUTH,
         [parse_bid("1H"), parse_bid("P"),
          parse_bid("1S"), parse_bid("P")],
         # With 16-17 HCP + 6-card suit, jump rebid 3H. With 18+,
         # might force to game (4H or 3NT). 18 is borderline.
         ["3H", "4H", "2NT"]),

    # ---- Invitational jump raise (3-of-major direct invitational) ----
    # Already covered by sayc-limit-raise. Add the inverse: weak jump
    # raise. Modern SAYC: 1S-3S = limit raise (10-12); preemptive
    # raise = 1S-3S in some styles (mixed-raise) or different bid.
    # Test: ensure bridgeIQ doesn't preempt-raise with limit values.

    # ---- 2/1 GF: continue describing without major fit ----
    Test("2o1-gf-rebid-no-fit",
         "1H-2C-2D-?: 2/1 GF continuation, balanced with stop → 2NT",
         Seat.NORTH,
         hand("Q72", "Q4", "K987", "AKJ8"),  # 14 HCP, 4cC 4cD
         Seat.SOUTH,
         [parse_bid("1H"), parse_bid("P"),
          parse_bid("2C"), parse_bid("P"),
          parse_bid("2D"), parse_bid("P")],
         # 2/1 GF context, opener showed minor side-suit. Balanced
         # 14 HCP with stoppers — 2NT (or 3NT) for game.
         ["2NT", "3NT", "3D", "3C"]),

    # ---- Penalty double of low-level overcall in matchpoint style ----
    Test("sayc-penalty-x-overcall",
         "1H-(2C)-X: 12 HCP, 4+ clubs behind — penalty X via "
         "negative double substitute or direct penalty",
         Seat.NORTH,
         hand("Q72", "K84", "QJ92", "KJ87"),  # 13 HCP, 4cC behind 2C
         Seat.SOUTH,
         [parse_bid("1H"), parse_bid("2C")],
         # Modern SAYC: X is NEGATIVE (takeout-style asking for
         # the unbid major). With 4 spades + 4 clubs and no
         # spades here, options vary. Accept X (negative or
         # penalty) or 2D (own suit) or 2NT (balanced inv).
         ["X", "2NT", "3NT", "2D"]),
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

    # ---- Drury: passed-hand 2C showing 3-card support of partner's major ----
    Test("2o1-drury",
         "Drury (3rd seat): passed hand bids 2C to show 3-card "
         "support + 10-12 HCP for partner's 3rd-seat 1M opening",
         Seat.WEST,  # I am W; partner E opened 1H in 3rd seat
         hand("Q72", "K84", "QJ92", "KJ8"),  # 11 HCP, 3cH
         Seat.WEST,  # W (me, dealer) P, N P, E (partner) 1H, S P, W?
         [parse_bid("P"), parse_bid("P"),
          parse_bid("1H"), parse_bid("P")],
         # Modern Drury: passed-hand 2C = 3+ card limit raise. Or
         # natural 1NT (forcing) is fine if Drury not enabled.
         # 3H direct (limit raise) is also playable.
         ["2C", "1NT", "3H"]),

    # ---- Bergen-style 4-card raise of 1M (10-11 HCP) ----
    Test("2o1-bergen-raise",
         "10-11 HCP + 4-card heart support: Bergen or limit raise",
         Seat.NORTH,
         hand("Q72", "K842", "Q98", "QJ4"),  # 10 HCP, 4cH
         Seat.SOUTH, [parse_bid("1H")],
         # SAYC mainstream: 3H direct limit raise (10-12).
         # Bergen textbook: 3C constructive (7-9), 3D limit (10-12).
         # Q-Plus's Bergen variant: 3C constructive (10-11),
         # 3D limit (12-13). All three styles are textbook for
         # 4-card 10-11 HCP support.
         ["3H", "3D", "3C"]),

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

    # ---- Acol 2C (strong artificial) ----
    Test("acol-strong-2c",
         "Acol 2C: 23+ HCP or game-forcing strength",
         Seat.SOUTH,
         hand("AKQ", "AKQ4", "AKQ", "K94"),  # 26 HCP balanced
         Seat.SOUTH, [], ["2C", "2NT"]),  # 2C strong or 2NT (23-24)

    # ---- Acol weak NT range upper bound ----
    Test("acol-no-1nt-12-vul",
         "Acol 1NT 12-14 vulnerable: still bid 1NT at 12",
         Seat.SOUTH,
         hand("KJ4", "K76", "QJ92", "Q74"),  # 12 HCP, balanced
         Seat.SOUTH, [], ["1NT"]),

    # ---- Acol 4-card 1S opening ----
    Test("acol-1s-4card-balanced",
         "1S open with 4 spades + balanced 15+ (above 1NT range)",
         Seat.SOUTH,
         hand("AQ72", "KJ4", "K94", "A82"),  # 16 HCP, 4-3-3-3
         Seat.SOUTH, [], ["1S", "1NT"]),  # 1S or 1NT if range allows
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

    # ---- Precision 1C — 1D negative response (0-7 HCP) ----
    Test("prec-1c-1d-neg",
         "Precision 1C-1D: negative response, 0-7 HCP",
         Seat.NORTH,
         hand("Q72", "843", "Q98", "T9876"),  # 4 HCP
         Seat.SOUTH, [parse_bid("1C")],
         ["1D"]),

    # ---- Precision 1C — 1H positive response (8+ HCP, 5+ hearts) ----
    Test("prec-1c-positive-1h",
         "Precision 1C-1H: positive response 8+ HCP + 5+ hearts",
         Seat.NORTH,
         hand("Q72", "AKJ87", "Q9", "T82"),  # 11 HCP, 5cH
         Seat.SOUTH, [parse_bid("1C")],
         ["1H"]),

    # ---- Precision 2-of-major (weak two) ----
    Test("prec-weak-2h",
         "Precision weak 2H: 5-10 HCP + 6+ hearts",
         Seat.SOUTH,
         hand("Q3", "KQT972", "T84", "75"),  # 7 HCP, 6cH
         Seat.SOUTH, [], ["2H"]),

    # ---- Precision 1NT response over weak 1D ----
    # Skipped — Precision 1D is a catch-all, not standard 1NT
    # response framework.

    # ---- Precision 1C — 2C positive response (5+ clubs, GF) ----
    Test("prec-1c-positive-2c",
         "Precision 1C-2C: positive 8+ HCP + 5+ clubs",
         Seat.NORTH,
         hand("Q72", "94", "K8", "AKJ876"),  # 13 HCP, 6cC
         Seat.SOUTH, [parse_bid("1C")],
         # 8+ HCP positive with 5+ clubs. Could be 2C (natural) or
         # an artificial step-response. Accept either.
         ["2C", "1H", "1S", "1NT"]),
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
