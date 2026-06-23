#!/usr/bin/env python3
"""Instrumented-view length inference: when one hidden hand is void in a suit
and the rest of that suit is visible, the OTHER hidden hand's count is EXACT,
not a range. Pins both the forced-placement (known_layout) and the max-length
formula (suit_length_text)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                            Contract, Trick, Vulnerability)
import ui.teaching_view as tv


def _c(s, r):
    return Card(Suit.from_char(s), Rank.from_char(r))


def _hand(cs):
    return Hand(cards=[_c(t[0], t[1]) for t in cs.split()])


# ---- Direct test of the max-length formula (no double counting) ----------
def test_suit_length_formula_exact_when_all_placed():
    # Fake layout: East proven to hold both unseen diamonds; none uncertain.
    DIA = Suit.DIAMONDS
    layout = {
        "known": {s: {su: [] for su in tv.SUIT_ROWS} for s in Seat},
        "voids": {s: set() for s in Seat},
        "unseen_by_suit": {su: 0 for su in tv.SUIT_ROWS},
        "remaining_count": {s: 4 for s in Seat},
    }
    layout["known"][Seat.EAST][DIA] = [Rank.JACK, Rank.TEN]   # 2 proven in East
    layout["voids"][Seat.WEST].add(DIA)
    layout["unseen_by_suit"][DIA] = 2                          # both are East's
    visible = {Seat.SOUTH, Seat.NORTH}
    # East: exact 2 (not "2-4")
    assert tv.suit_length_text(Seat.EAST, DIA, visible, layout, {}) == "2"
    # West: void
    assert tv.suit_length_text(Seat.WEST, DIA, visible, layout, {}) == "void"


def test_suit_length_formula_range_when_uncertain():
    DIA = Suit.DIAMONDS
    layout = {
        "known": {s: {su: [] for su in tv.SUIT_ROWS} for s in Seat},
        "voids": {s: set() for s in Seat},
        "unseen_by_suit": {su: 0 for su in tv.SUIT_ROWS},
        "remaining_count": {s: 4 for s in Seat},
    }
    layout["unseen_by_suit"][DIA] = 2     # 2 diamonds out, could be E or W
    visible = {Seat.SOUTH, Seat.NORTH}
    # Neither void/placed → East can hold 0..2.
    assert tv.suit_length_text(Seat.EAST, DIA, visible, layout, {}) == "0-2"


# ---- End-to-end: a SHOWN void forces the other hand exact -----------------
def _void_board():
    """Full 52-card deal; West holds no diamonds. One trick is played in which
    a diamond is led and West shows out, so voids[West] = {diamonds}."""
    hands = {
        Seat.NORTH: _hand("SA SK SQ SJ ST S9 S8 S7 S6 S5 S4 S3 S2"),  # spades
        Seat.SOUTH: _hand("DA DK DQ DJ DT D9 D8 D7 CA CK CQ CJ CT"),  # 8♦ + 5♣
        Seat.EAST:  _hand("D6 D5 D4 D3 D2 HA HK HQ HJ HT H9 H8 H7"),  # 5♦ + 8♥
        Seat.WEST:  _hand("C9 C8 C7 C6 C5 C4 C3 C2 H6 H5 H4 H3 H2"),  # 8♣ + 5♥
    }
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE, hands=hands)
    b.contract = Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
    # Trick: South leads ♦7; order S, W, N, E. West discards a club (void!),
    # North a spade, East follows with ♦2.
    t = Trick(cards=[_c('D', '7'), _c('C', '2'), _c('S', '2'), _c('D', '2')],
              leader=Seat.SOUTH, winner=Seat.SOUTH)
    b.tricks = [t]
    for seat, c in zip([Seat.SOUTH, Seat.WEST, Seat.NORTH, Seat.EAST], t.cards):
        b.hands[seat].cards.remove(c)
    return b


def test_shown_void_makes_other_hand_exact():
    b = _void_board()
    visible = {Seat.SOUTH, Seat.NORTH}
    _, voids, _ = tv.collect_play(b)
    assert Suit.DIAMONDS in voids[Seat.WEST], "West should be void in diamonds"
    layout = tv.known_layout(b, visible)
    # All remaining diamonds (East's ♦6543) are forced to East.
    east_d = layout["known"][Seat.EAST][Suit.DIAMONDS]
    assert len(east_d) == 4
    # And the count panel shows an EXACT 4, not a range.
    txt = tv.suit_length_text(Seat.EAST, Suit.DIAMONDS, visible, layout, {})
    assert txt == "4", f"expected exact '4', got {txt!r}"
    assert tv.suit_length_text(Seat.WEST, Suit.DIAMONDS, visible,
                               layout, {}) == "void"


if __name__ == "__main__":
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL COUNT-INFERENCE TESTS PASSED")
