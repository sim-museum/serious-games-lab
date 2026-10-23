#!/usr/bin/env python3
"""Monte-Carlo declarer (nopeek._DECL_PIMC, default on).

The declarer side picks its card by double-dummy averaging over sampled
defender layouts. Pins: the branch is taken, the card is legal, and it never
peeks (swapping the defenders' hidden cards leaves the decision unchanged)."""
import random

from backend import nopeek
from backend.models import BoardState, Contract, Hand, Seat, Suit, Vulnerability

# N dummy, S declarer in 3NT; West leads the spade queen.
N = "A32.KQ4.AJ952.83"
S = "K54.A73.KT4.AK72"
EW = ("QJT98.J9.Q6.QJ94", "76.T8652.873.T65")   # West, East
EW_SWAP = ("QJT98.T86.873.T9", "76.J952.Q6.QJ654")


def _board(west, east):
    hands = {Seat.NORTH: Hand.from_pbn(N), Seat.SOUTH: Hand.from_pbn(S),
             Seat.WEST: Hand.from_pbn(west), Seat.EAST: Hand.from_pbn(east)}
    return BoardState(board_number=1, dealer=Seat.SOUTH,
                      vulnerability=Vulnerability.NONE, hands=hands,
                      auction=[], tricks=[],
                      contract=Contract(level=3, suit=Suit.NOTRUMP,
                                        declarer=Seat.SOUTH))


def _dummy_card(west, east):
    b = _board(west, east)
    lead = next(c for c in b.hands[Seat.WEST].cards
                if c.suit == Suit.SPADES and c.rank.name == "QUEEN")
    b.hands[Seat.WEST].cards.remove(lead)
    random.seed(7)
    ex = {}
    card = nopeek.decide(b, Seat.NORTH, [lead], explain=ex)
    return card, ex, b


def test_branch_and_legal():
    assert nopeek._DECL_PIMC > 0
    card, ex, b = _dummy_card(*EW)
    assert ex.get("tag") == "Monte-Carlo search", ex
    assert card in b.hands[Seat.NORTH].cards and card.suit == Suit.SPADES


def test_no_peek():
    # Same unseen cards, different split between the defenders.
    for i in range(4):
        assert sorted(EW[0].split(".")[i] + EW[1].split(".")[i]) == \
            sorted(EW_SWAP[0].split(".")[i] + EW_SWAP[1].split(".")[i])
    a, _, _ = _dummy_card(*EW)
    b, _, _ = _dummy_card(*EW_SWAP)
    assert a == b


if __name__ == "__main__":
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL MONTE-CARLO DECLARER TESTS PASSED")
