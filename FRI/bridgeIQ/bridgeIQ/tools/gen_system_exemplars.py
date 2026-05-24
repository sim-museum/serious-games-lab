"""Generate 20 deals per bidding system, biased toward each
system's signature conventions, so the cross-system diff
exercises bidder breadth rather than over-fitting to one corpus.

For each system, we scan seeds and pick deals where at least one
hand exemplifies a convention or pattern that DISTINGUISHES the
system from the others. Examples:

  SAYC          15-17 NT openers; Jacoby 2NT; Stayman / Smolen
  TwoOverOne    11-12 + 3-card support → forcing-1NT path;
                13+ + 5-card side suit → real 2/1 GF
  StandardAcol  12-14 NT (weak NT); 4-card major openings;
                strong-two openings (20+ HCP / 5+ suit)
  StandardFrench    11-12 balanced + 3-card support → natural-2NT;
                standard 5cM bidding
  Precision90M  16+ HCP → strong 1C; 11-15 with 4-4 majors +
                0-1 D → 2D three-suiter; 11-15 with 6+ C →
                2C long-club; 11-15 + 1D catch-all

The generator writes one BDE file per system to Q-Plus's
OWN-DEALS dir, plus a copy in the repo's test_probes/ folder so
the user can re-run the test corpus deterministically.

Usage:
    python3 tools/gen_system_exemplars.py
"""
from __future__ import annotations

import sys
import random
from pathlib import Path

PKG = Path("/home/h/sgl/FRI/bridgeIQ/bridgeIQ")
sys.path.insert(0, str(PKG))

from backend.models import (
    BoardState, Card, Hand, Rank, Seat, Suit, Vulnerability,
)
from backend.native_bidder import evaluate_hand
from backend.qplus_driver import write_multi_deal_bde, qplus_own_deals_dir


N_PER_SYSTEM = 20


def make_deal(seed: int, board_num: int) -> BoardState:
    rng = random.Random(seed)
    cards = [Card(Suit(s), Rank(r))
             for s in range(4) for r in range(13)]
    rng.shuffle(cards)
    dealers = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
    vuls = [Vulnerability.NONE, Vulnerability.NS,
            Vulnerability.EW, Vulnerability.BOTH]
    return BoardState(
        board_number=board_num,
        dealer=dealers[(board_num - 1) % 4],
        vulnerability=vuls[((board_num - 1) // 4) % 4],
        hands={
            Seat.NORTH: Hand(cards=cards[0:13]),
            Seat.EAST:  Hand(cards=cards[13:26]),
            Seat.SOUTH: Hand(cards=cards[26:39]),
            Seat.WEST:  Hand(cards=cards[39:52]),
        },
    )


# Per-system "is this deal interesting?" predicates. They check each
# hand against the system's distinctive patterns and return True if
# any hand exercises that pattern.

def _all_seats(board):
    return [board.hands[s] for s in
            (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)]


def is_sayc_exemplar(board) -> bool:
    """SAYC: 15-17 NT openers; Jacoby 2NT slam tries; Stayman;
    NMF auctions; strong 2C openings."""
    for h in _all_seats(board):
        e = evaluate_hand(h)
        # 1NT opener (15-17 balanced)
        if e.is_balanced and 15 <= e.hcp <= 17:
            return True
        # Strong 2C opener (22+ HCP)
        if e.hcp >= 22:
            return True
        # Jacoby 2NT candidate: 13-15 HCP + 4+ trump support behind
        # a 1M opener. We'll check whether *some* pair has this
        # shape: 5-card major + matching 4-card support across the
        # partnership.
        if 13 <= e.hcp <= 15 and (
                e.suit_lengths[Suit.HEARTS] >= 4
                or e.suit_lengths[Suit.SPADES] >= 4):
            # Coupled with a partner who could open 1H/1S — rare to
            # be sure here, but the 13-15 + 4cM is a good proxy.
            return True
    return False


def is_2_over_1_exemplar(board) -> bool:
    """2/1 GF: 11-12 HCP + 3-card major support (forcing-1NT path)
    OR 13+ HCP + 4-5 card minor + responder seat. We look for
    hands where one player has 11-12 balanced and a partner with
    a 5-card major to open."""
    seats = list(_all_seats(board))
    for i, h in enumerate(seats):
        e = evaluate_hand(h)
        # Forcing-1NT candidate: 11-12 HCP, balanced/semi-balanced,
        # 3-card support possible (any 3-card major).
        if (11 <= e.hcp <= 12
                and (e.is_balanced or e.is_semi_balanced)
                and (e.suit_lengths[Suit.HEARTS] == 3
                     or e.suit_lengths[Suit.SPADES] == 3)):
            return True
        # True 2/1 GF: 13+ HCP, 5+ minor, 1M partner.
        if (e.hcp >= 13 and
                (e.suit_lengths[Suit.CLUBS] >= 5
                 or e.suit_lengths[Suit.DIAMONDS] >= 5)):
            return True
    return False


def is_acol_exemplar(board) -> bool:
    """Acol: 12-14 NT (weak NT), 4-card major openings, strong
    two openings. We accept deals where some hand has 12-14
    balanced (would open 1NT in Acol) OR a 4-card major with
    no 5-card suit + 12+ HCP (4cM open) OR 20+ HCP (strong two
    candidate)."""
    for h in _all_seats(board):
        e = evaluate_hand(h)
        # 1NT opener in Acol
        if e.is_balanced and 12 <= e.hcp <= 14:
            return True
        # 4-card major opening (not 5+ in any suit)
        if (e.hcp >= 12
                and max(e.suit_lengths.values()) == 4
                and (e.suit_lengths[Suit.HEARTS] == 4
                     or e.suit_lengths[Suit.SPADES] == 4)):
            return True
        # Strong 2H/2S (Acol two)
        if e.hcp >= 20 and (e.suit_lengths[Suit.HEARTS] >= 5
                            or e.suit_lengths[Suit.SPADES] >= 5):
            return True
    return False


def is_french_exemplar(board) -> bool:
    """Standard French: natural 2NT-invite (11-12 balanced +
    3-card major support); standard 5cM bidding. We look for
    11-12 balanced hands with 3-card heart/spade support OR
    standard 5cM auction triggers."""
    for h in _all_seats(board):
        e = evaluate_hand(h)
        # Natural 2NT-invite candidate
        if (11 <= e.hcp <= 12
                and e.is_balanced
                and (e.suit_lengths[Suit.HEARTS] == 3
                     or e.suit_lengths[Suit.SPADES] == 3)):
            return True
        # Standard 1M opener (5+ major, 11+ HCP)
        if e.hcp >= 11 and (e.suit_lengths[Suit.HEARTS] >= 5
                            or e.suit_lengths[Suit.SPADES] >= 5):
            return True
    return False


def is_precision_exemplar(board) -> bool:
    """Precision 90M: strong 1C (16+); 2D three-suiter (11-15 +
    4-4 majors + 0-1 D); 2C long-club (11-15 + 6+ C); 14-16 NT."""
    for h in _all_seats(board):
        e = evaluate_hand(h)
        # Strong 1C opener (16+ HCP)
        if e.hcp >= 16:
            return True
        # 1NT opener (14-16 balanced)
        if e.is_balanced and 14 <= e.hcp <= 16:
            return True
        # 2D three-suiter (11-15 + 4+/3+ majors + 0-1 D)
        if (11 <= e.hcp <= 15
                and e.suit_lengths[Suit.DIAMONDS] <= 1
                and e.suit_lengths[Suit.HEARTS] >= 3
                and e.suit_lengths[Suit.SPADES] >= 3
                and (e.suit_lengths[Suit.HEARTS] >= 4
                     or e.suit_lengths[Suit.SPADES] >= 4)):
            return True
        # 2C long-club (11-15 + 6+ clubs)
        if 11 <= e.hcp <= 15 and e.suit_lengths[Suit.CLUBS] >= 6:
            return True
    return False


SYSTEMS = [
    ("SAYC",            is_sayc_exemplar,        "SAYC_EX.BDE"),
    ("TwoOverOne",      is_2_over_1_exemplar,    "TWO1_EX.BDE"),
    ("StandardAcol",    is_acol_exemplar,        "ACOL_EX.BDE"),
    ("StandardFrench",  is_french_exemplar,      "FRENCH_EX.BDE"),
    ("Precision90M",    is_precision_exemplar,   "PREC_EX.BDE"),
]


def collect_deals(predicate, n=N_PER_SYSTEM, base_seed=10000):
    """Scan seeds from base_seed until we have n deals satisfying
    the predicate."""
    out = []
    seed = base_seed
    tries = 0
    while len(out) < n and tries < 100_000:
        board = make_deal(seed, len(out) + 1)
        tries += 1
        if predicate(board):
            out.append(board)
        seed += 1
    return out, tries


def main():
    own_dir = qplus_own_deals_dir()
    if own_dir is None:
        print("Q-Plus install not found.", file=sys.stderr)
        return 1
    repo_probes = PKG / "test_probes"
    repo_probes.mkdir(exist_ok=True)

    # Different base seed per system so the deals don't overlap.
    base_seeds = {
        "SAYC":           10000,
        "TwoOverOne":     20000,
        "StandardAcol":   30000,
        "StandardFrench": 40000,
        "Precision90M":   50000,
    }

    for system_name, predicate, bde_name in SYSTEMS:
        deals, tries = collect_deals(
            predicate, N_PER_SYSTEM, base_seeds[system_name])
        out_qplus = own_dir / bde_name
        write_multi_deal_bde(
            deals, out_qplus,
            description=f"{system_name} exemplars (20 deals)")
        out_repo = repo_probes / bde_name
        write_multi_deal_bde(
            deals, out_repo,
            description=f"{system_name} exemplars (20 deals)")
        seed_first = base_seeds[system_name]
        seed_last = seed_first + tries - 1
        print(f"  {system_name:18s} → {bde_name:14s} "
              f"({len(deals)} deals from seeds "
              f"{seed_first}-{seed_last}, "
              f"{tries} candidates scanned)")

    print("\nWrote to Q-Plus and repo. To use:")
    print("  1. In Q-Plus, set both pairs to the system's RCE file:")
    print("       SAYC → A-SAYC-I, 2/1 → A-2-1-A, Acol → B-ACL-S,")
    print("       French → F-FRA-M, Precision → P-P90M-A")
    print("  2. Open Own deals → SAYC_EX.BDE (etc.) and autoplay.")
    print("  3. After each session, share the new log-NNN.bdl.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
