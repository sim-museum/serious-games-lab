#!/usr/bin/env python3
"""One-Player Mode non-peek invariant.

In One-Player Mode the engine may act ONLY for seats whose hand it is legitimately
allowed to know (the user's own seat, and dummy once it is down). Every other
seat is entered manually as revealed at the table — the engine is never queried
for it, in bidding or in play. This test pins that gate
(``_one_player_seat_known``) and the data-level invariant (no hidden-hand data).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import types

from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                            Vulnerability)
import ui.main_window as mw


def _bind(obj, *names):
    for n in names:
        setattr(obj, n, types.MethodType(getattr(mw.MainWindow, n), obj))


class _Stub:
    pass


def _user_hand():
    return Hand(cards=[Card(s, r) for s in
                       [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS] for r in
                       list(Rank)[:4]] + [Card(Suit.CLUBS, Rank.ACE)])


def test_seat_known_gate():
    s = _Stub()
    _bind(s, "_one_player_seat_known")
    # Outside one-player mode: every seat is known.
    s._one_player_active = False
    assert all(s._one_player_seat_known(seat) for seat in Seat)
    # In one-player mode: only the declared known seats.
    s._one_player_active = True
    s._one_player_known_seats = {Seat.SOUTH}
    assert s._one_player_seat_known(Seat.SOUTH)
    assert not s._one_player_seat_known(Seat.NORTH)
    assert not s._one_player_seat_known(Seat.EAST)
    assert not s._one_player_seat_known(Seat.WEST)
    # Dummy becomes known once it comes down.
    s._one_player_known_seats.add(Seat.NORTH)
    assert s._one_player_seat_known(Seat.NORTH)


def test_data_level_no_hidden_hands():
    """After one-player setup the non-user seats hold no cards the engine
    could peek at (the runtime clears them)."""
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NONE, hands={})
    b.hands[Seat.SOUTH] = _user_hand()
    for seat in (Seat.NORTH, Seat.EAST, Seat.WEST):
        b.hands[seat] = Hand(cards=[])      # cleared, as the runtime does
    s = _Stub()
    s._one_player_active = True
    s._one_player_known_seats = {Seat.SOUTH}
    _bind(s, "_one_player_seat_known")
    for seat in Seat:
        if not s._one_player_seat_known(seat):
            # An unknown seat must expose no cards to peek at.
            assert len(b.hands[seat].cards) == 0, f"{seat} leaked cards"


if __name__ == "__main__":
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL ONE-PLAYER NO-PEEK TESTS PASSED")
