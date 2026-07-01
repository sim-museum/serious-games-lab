#!/usr/bin/env python3
"""Tests for ui/whole_deal_plan.py — the no-peek 13-trick plan."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                            Contract, Vulnerability)
from ui.whole_deal_plan import whole_deal_plan, render_whole_deal_plan


def _c(s, r):
    return Card(Suit.from_char(s), Rank.from_char(r))


def _hand(cs):
    return Hand(cards=[_c(t[0], t[1]) for t in cs.split()])


def _board(level, strain, declarer=Seat.SOUTH):
    b = BoardState(board_number=1, dealer=Seat.SOUTH,
                   vulnerability=Vulnerability.NS, hands={
        Seat.SOUTH: _hand("SA SK SQ SJ S5 HA HK D4 D3 C7 C6 C5 C2"),
        Seat.NORTH: _hand("S9 S8 S7 H5 H4 H3 DA DK DQ C9 C8 C4 C3"),
        Seat.EAST:  _hand("S6 S4 HQ HJ H9 H8 D9 D8 D7 CA CK CQ CJ"),
        Seat.WEST:  _hand("ST S3 S2 HT H7 H6 H2 DJ DT D6 D5 D2 CT"),
    })
    b.contract = Contract(level=level, suit=strain, declarer=declarer)
    return b


class _HandsGuard(dict):
    def __init__(self, src, allowed):
        super().__init__(src)
        self._allowed = set(allowed)

    def __getitem__(self, k):
        assert k in self._allowed, f"PEEKED at hidden hand {k!r}"
        return super().__getitem__(k)

    def get(self, k, default=None):
        assert k in self._allowed, f"PEEKED at hidden hand {k!r}"
        return super().get(k, default)


def test_declarer_plan_has_counts_and_steps():
    b = _board(4, Suit.SPADES)
    p = whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, b.contract,
                        {Seat.SOUTH, Seat.NORTH})
    assert p is not None
    assert p.perspective == "declarer"
    assert p.target == 10                       # 6 + level
    assert p.top_tricks is not None
    assert p.steps
    # A suit contract leads with the trump-drawing decision.
    assert any(s.kind == "draw_trumps" for s in p.steps)


def test_nt_declarer_plan_mentions_establishment():
    b = _board(3, Suit.NOTRUMP)
    p = whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, b.contract,
                        {Seat.SOUTH, Seat.NORTH})
    assert p is not None and p.trump is None
    kinds = {s.kind for s in p.steps}
    assert "count" in kinds


def test_returns_none_without_dummy_visible():
    b = _board(4, Suit.SPADES)
    # Declarer plan but dummy not face-up -> must NOT peek; returns None.
    p = whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, b.contract,
                        {Seat.SOUTH})
    assert p is None


def test_declarer_plan_never_peeks():
    b = _board(4, Suit.SPADES)
    visible = {Seat.SOUTH, Seat.NORTH}
    b.hands = _HandsGuard(b.hands, allowed=visible)
    p = whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, b.contract, visible)
    assert p is not None                        # built without touching E/W


def test_defender_perspective():
    b = _board(4, Suit.SPADES)
    p = whole_deal_plan(b, Seat.WEST, Seat.SOUTH, Seat.NORTH, b.contract,
                        {Seat.WEST, Seat.NORTH})
    assert p is not None and p.perspective == "defender"
    assert p.target == 4                        # 14 - 10
    assert any(s.kind == "lead_philosophy" for s in p.steps)


def test_render_is_short_and_nonempty():
    b = _board(4, Suit.SPADES)
    p = whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, b.contract,
                        {Seat.SOUTH, Seat.NORTH})
    txt = render_whole_deal_plan(p)
    assert txt and len(txt.split()) < 130       # short
    html = render_whole_deal_plan(p, html=True)
    assert "<br>" in html and "<b>" in html


def test_no_contract_returns_none():
    b = _board(4, Suit.SPADES)
    b.contract = None
    assert whole_deal_plan(b, Seat.SOUTH, Seat.SOUTH, Seat.NORTH, None,
                           {Seat.SOUTH, Seat.NORTH}) is None


if __name__ == "__main__":
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL TESTS PASSED")
