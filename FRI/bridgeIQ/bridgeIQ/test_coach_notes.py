#!/usr/bin/env python3
"""Tests for ui/coach_notes.py — situation-specific coaching notes.

Verifies the notes are specific to (a) the active bidding system's real
parameters and (b) vulnerability, that the play notes NEVER peek at hidden
hands, and that there is always a non-empty deterministic fallback.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                            Contract, Trick, Vulnerability)
from backend.bidding_systems import get_system
from ui.coach_notes import coaching_note


def _c(s, r):
    return Card(Suit.from_char(s), Rank.from_char(r))


def _hand(cards_str):
    return Hand(cards=[_c(t[0], t[1]) for t in cards_str.split()])


def _deal(south_str):
    """Full legal 4-hand board: South gets the given 13, the rest are split
    N/E/W (contents irrelevant to bidding-of-South tests)."""
    south = _hand(south_str)
    south_ids = {c.suit * 13 + c.rank for c in south.cards}
    assert len(south.cards) == 13, "south must have 13 cards"
    rest = [Card(s, r) for s in
            [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS] for r in Rank
            if (s * 13 + r) not in south_ids]
    hands = {Seat.SOUTH: south,
             Seat.WEST: Hand(cards=rest[0:13]),
             Seat.NORTH: Hand(cards=rest[13:26]),
             Seat.EAST: Hand(cards=rest[26:39])}
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE, hands=hands)
    b.auction = []
    return b


class _HandsGuard(dict):
    """A board.hands that asserts no hidden seat is ever read (no-peek spy)."""
    def __init__(self, src, allowed):
        super().__init__(src)
        self._allowed = set(allowed)

    def __getitem__(self, k):
        assert k in self._allowed, f"PEEKED at hidden hand {k!r}"
        return super().__getitem__(k)

    def get(self, k, default=None):
        assert k in self._allowed, f"PEEKED at hidden hand {k!r}"
        return super().get(k, default)


# ---- Bidding: specificity to the system parameters -----------------------
def test_note_specific_to_system_1nt_range():
    # 14 HCP, balanced 3-3-3-4: opens 1NT under Precision (14-16) but NOT
    # under SAYC (15-17). The note must reflect the actual system in use.
    b = _deal("SK SQ S5 HA H4 H3 DK DJ D5 CJ C6 C4 C3")
    sayc = get_system("SAYC")
    prec = get_system("Precision90M")
    note_sayc = coaching_note(b, Seat.SOUTH, "bidding", sayc, sayc, set())
    note_prec = coaching_note(b, Seat.SOUTH, "bidding", prec, prec, set())
    assert note_sayc and note_prec
    assert note_sayc != note_prec
    # Precision opens this 14-count 1NT and names its real range.
    assert "14-16" in note_prec and "1NT" in note_prec


def test_note_names_balanced_1nt_for_sayc():
    # 16 HCP balanced (♠AK5 ♥QJ4 ♦K54 ♣K643) -> textbook 1NT in SAYC.
    b = _deal("SA SK S5 HQ HJ H4 DK D5 D4 CK C6 C4 C3")
    sayc = get_system("SAYC")
    note = coaching_note(b, Seat.SOUTH, "bidding", sayc, sayc, set())
    assert "1NT" in note and "15-17" in note


# ---- Bidding: vulnerability colours the advice ---------------------------
def test_note_reflects_vulnerability_on_preempt():
    # 8 HCP with a 6-card spade suit -> weak two; the note's vuln clause flips.
    b = _deal("SA SQ S9 S7 S5 S3 H6 H4 D8 D5 D3 C7 C2")
    sayc = get_system("SAYC")
    b.vulnerability = Vulnerability.NONE
    n_white = coaching_note(b, Seat.SOUTH, "bidding", sayc, sayc, set())
    b.vulnerability = Vulnerability.NS          # South is N/S -> vulnerable
    n_red = coaching_note(b, Seat.SOUTH, "bidding", sayc, sayc, set())
    assert n_white != n_red
    assert "Vulnerable" in n_red
    assert "stretch" in n_white


# ---- Play: declarer note is specific, defender note differs --------------
def _nt_board():
    """3NT by South; West has led, so a trick exists and threat suit is set."""
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE, hands={
        Seat.SOUTH: _hand("SA SK SQ S4 HA H3 H2 DK D4 D3 C5 C4 C2"),
        Seat.NORTH: _hand("S5 S3 S2 HK H4 DA DQ D5 D2 C9 C8 C7 C3"),
        Seat.EAST:  _hand("S9 S8 HQ HJ HT H9 H8 D9 D8 CA CK CQ CJ"),
        Seat.WEST:  _hand("SJ ST S7 S6 H7 H6 H5 DJ DT D7 D6 CT C6"),
    })
    b.contract = Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
    # West leads a heart (their long suit); all follow.
    b.tricks = [Trick(cards=[_c('H', '5'), _c('H', 'K'), _c('H', '8'), _c('H', '2')],
                      leader=Seat.WEST, winner=Seat.NORTH)]
    for seat, c in zip([Seat.WEST, Seat.NORTH, Seat.EAST, Seat.SOUTH],
                       b.tricks[0].cards):
        b.hands[seat].cards.remove(c)
    return b


def test_play_declarer_note_nonempty_and_specific():
    b = _nt_board()
    visible = {Seat.SOUTH, Seat.NORTH}
    note = coaching_note(b, Seat.SOUTH, "play", None, None, visible)
    assert note and len(note) > 10
    # mentions a concrete suit symbol (specific to the cards)
    assert any(sym in note for sym in ("♠", "♥", "♦", "♣"))


def test_play_defender_note_differs_from_declarer():
    b = _nt_board()
    decl = coaching_note(b, Seat.SOUTH, "play", None, None,
                         {Seat.SOUTH, Seat.NORTH})
    deff = coaching_note(b, Seat.WEST, "play", None, None,
                         {Seat.WEST, Seat.NORTH})
    assert decl != deff
    assert "beat it" in deff or "set" in deff.lower()


def test_play_note_never_peeks():
    b = _nt_board()
    visible = {Seat.SOUTH, Seat.NORTH}
    b.hands = _HandsGuard(b.hands, allowed=visible)   # raise on E/W access
    note = coaching_note(b, Seat.SOUTH, "play", None, None, visible)
    assert note                                       # produced without peeking


# ---- Always returns something --------------------------------------------
def test_fallback_on_degenerate_state():
    b = _deal("SK SQ S5 HA H4 H3 DK DJ D5 CJ C6 C4 C3")
    b.contract = None
    note = coaching_note(b, Seat.SOUTH, "play", None, None, set())
    assert note and len(note) > 10


if __name__ == "__main__":
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL TESTS PASSED")
