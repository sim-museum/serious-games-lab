"""Tests for backend.explain — the action-explanation presentation layer."""

import unittest

from backend.models import Bid, Card, Seat, Suit, Rank, Contract
from backend import explain
from backend.bidding_systems import get_system


class TestExplainBid(unittest.TestCase):
    def setUp(self):
        self.sys = get_system('SAYC')

    def test_opening_uses_engine_reason_and_system_meaning(self):
        b = Bid(level=1, suit=Suit.NOTRUMP, explanation='15-17 balanced')
        ex = explain.explain_bid(b, [], Seat.SOUTH, Seat.SOUTH,
                                 self.sys, engine_who='native')
        self.assertEqual(ex.title, 'South bids 1NT')
        self.assertIn('SAYC', ex.subtitle)
        self.assertEqual(ex.headline, '15-17 balanced')
        # System-grounded meaning surfaces as a supporting line.
        self.assertTrue(any('SAYC' in p for p in ex.points))
        # biq's call → engine attribution present.
        self.assertTrue(ex.note)

    def test_conventional_call_is_cited_and_flagged(self):
        auction = [Bid(level=1, suit=Suit.NOTRUMP)]
        b = Bid(level=2, suit=Suit.CLUBS, alert=True,
                explanation='Stayman, asks for 4cM')
        ex = explain.explain_bid(b, auction, Seat.NORTH, Seat.SOUTH,
                                 self.sys, engine_who='native')
        self.assertEqual(ex.citation, 'Stayman')
        self.assertTrue(any('Conventional' in p or 'alertable' in p
                            for p in ex.points))

    def test_human_call_gets_no_engine_attribution(self):
        b = Bid(level=1, suit=Suit.SPADES)  # no explanation -> not biq's
        ex = explain.explain_bid(b, [], Seat.SOUTH, Seat.SOUTH,
                                 self.sys, engine_who='')
        self.assertEqual(ex.note, '')


class TestExplainCard(unittest.TestCase):
    def setUp(self):
        self.contract = Contract(level=4, suit=Suit.HEARTS,
                                 declarer=Seat.SOUTH)

    def _c(self, suit, rank):
        return Card(suit, Rank.from_char(rank))

    def test_opening_lead(self):
        ex = explain.explain_card(self._c(Suit.SPADES, 'Q'), Seat.WEST,
                                  [], Seat.WEST, self.contract, True,
                                  engine_who='no-peek')
        self.assertIn('Opening lead', ex.headline)
        self.assertIn('no-peek', ex.note)
        self.assertEqual(ex.citation, 'Opening-lead conventions')

    def test_second_hand_low(self):
        led = [self._c(Suit.DIAMONDS, 'A')]   # West (defender) led DA
        ex = explain.explain_card(self._c(Suit.DIAMONDS, '3'), Seat.NORTH,
                                  led, Seat.WEST, self.contract, False)
        self.assertIn('Second hand low', ex.headline)

    def test_ruff_when_void(self):
        led = [self._c(Suit.DIAMONDS, 'A')]   # diamonds led
        ex = explain.explain_card(self._c(Suit.HEARTS, '2'), Seat.NORTH,
                                  led, Seat.WEST, self.contract, False)
        self.assertIn('Ruff', ex.headline)
        self.assertEqual(ex.citation, 'Ruff')

    def test_partner_winning_play_low(self):
        # West (defender) led DA and is winning; East (partner) plays low.
        led = [self._c(Suit.DIAMONDS, 'A')]
        ex = explain.explain_card(self._c(Suit.DIAMONDS, '4'), Seat.EAST,
                                  led, Seat.WEST, self.contract, False)
        self.assertIn('Partner is winning', ex.headline)
        # A defender's low spot also signals.
        self.assertTrue(any('signal' in p.lower() for p in ex.points))

    def test_winning_to_the_trick(self):
        # West led D2; North (declarer side) wins with DA, third hand.
        led = [self._c(Suit.DIAMONDS, '2'), self._c(Suit.DIAMONDS, '5')]
        ex = explain.explain_card(self._c(Suit.DIAMONDS, 'A'), Seat.SOUTH,
                                  led, Seat.WEST, self.contract, False)
        self.assertIn('win', ex.headline.lower())


if __name__ == '__main__':
    unittest.main()
