#!/usr/bin/env python3
"""
Comprehensive test suite for BEN Bridge application.
Tests edge cases including falsy enum values (Seat.NORTH=0, Suit.SPADES=0, Rank.ACE=0).
"""

import os
import sys

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Ensure we can find our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

ben_src = os.path.join(os.path.dirname(script_dir), 'ben', 'src')
if os.path.exists(ben_src):
    sys.path.insert(0, ben_src)

import unittest
from ben_backend.models import (
    Card, Hand, Bid, BoardState, Contract, Trick,
    Seat, Suit, Rank, Vulnerability, PlayerType, Player
)


class TestFalsyEnumValues(unittest.TestCase):
    """Test that enum values of 0 are handled correctly (not as falsy)."""

    def test_seat_north_is_zero(self):
        """Seat.NORTH has value 0 - ensure it's not treated as falsy."""
        self.assertEqual(Seat.NORTH.value, 0)
        self.assertEqual(Seat.NORTH, Seat.NORTH)
        # This should be True, not False
        self.assertTrue(Seat.NORTH is not None)
        # Direct comparison should work
        self.assertTrue(Seat.NORTH == Seat.NORTH)
        self.assertFalse(Seat.NORTH != Seat.NORTH)

    def test_suit_spades_is_zero(self):
        """Suit.SPADES has value 0 - ensure it's not treated as falsy."""
        self.assertEqual(Suit.SPADES.value, 0)
        self.assertTrue(Suit.SPADES is not None)
        self.assertTrue(Suit.SPADES == Suit.SPADES)

    def test_rank_ace_is_zero(self):
        """Rank.ACE has value 0 - ensure it's not treated as falsy."""
        self.assertEqual(Rank.ACE.value, 0)
        self.assertTrue(Rank.ACE is not None)

    def test_seat_iteration(self):
        """Test that all seats are iterable and NORTH is included."""
        all_seats = list(Seat)
        self.assertEqual(len(all_seats), 4)
        self.assertIn(Seat.NORTH, all_seats)
        self.assertEqual(all_seats[0], Seat.NORTH)

    def test_suit_iteration(self):
        """Test that all suits are iterable and SPADES is included."""
        all_suits = list(Suit)
        self.assertEqual(len(all_suits), 5)  # Including NOTRUMP
        self.assertIn(Suit.SPADES, all_suits)
        self.assertEqual(all_suits[0], Suit.SPADES)


class TestSeatOperations(unittest.TestCase):
    """Test Seat enum operations."""

    def test_seat_next(self):
        """Test Seat.next() cycles correctly."""
        self.assertEqual(Seat.NORTH.next(), Seat.EAST)
        self.assertEqual(Seat.EAST.next(), Seat.SOUTH)
        self.assertEqual(Seat.SOUTH.next(), Seat.WEST)
        self.assertEqual(Seat.WEST.next(), Seat.NORTH)

    def test_seat_partner(self):
        """Test Seat.partner() returns correct partner."""
        self.assertEqual(Seat.NORTH.partner(), Seat.SOUTH)
        self.assertEqual(Seat.SOUTH.partner(), Seat.NORTH)
        self.assertEqual(Seat.EAST.partner(), Seat.WEST)
        self.assertEqual(Seat.WEST.partner(), Seat.EAST)

    def test_seat_is_ns(self):
        """Test Seat.is_ns() returns correct values."""
        self.assertTrue(Seat.NORTH.is_ns())
        self.assertTrue(Seat.SOUTH.is_ns())
        self.assertFalse(Seat.EAST.is_ns())
        self.assertFalse(Seat.WEST.is_ns())

    def test_seat_from_char(self):
        """Test Seat.from_char() for all directions."""
        self.assertEqual(Seat.from_char('N'), Seat.NORTH)
        self.assertEqual(Seat.from_char('E'), Seat.EAST)
        self.assertEqual(Seat.from_char('S'), Seat.SOUTH)
        self.assertEqual(Seat.from_char('W'), Seat.WEST)
        # Lowercase should also work
        self.assertEqual(Seat.from_char('n'), Seat.NORTH)

    def test_seat_to_char(self):
        """Test Seat.to_char() for all seats."""
        self.assertEqual(Seat.NORTH.to_char(), 'N')
        self.assertEqual(Seat.EAST.to_char(), 'E')
        self.assertEqual(Seat.SOUTH.to_char(), 'S')
        self.assertEqual(Seat.WEST.to_char(), 'W')


class TestCardOperations(unittest.TestCase):
    """Test Card operations including edge cases."""

    def test_ace_of_spades(self):
        """Test Ace of Spades (both suit and rank are 0)."""
        card = Card(Suit.SPADES, Rank.ACE)
        self.assertEqual(card.suit, Suit.SPADES)
        self.assertEqual(card.rank, Rank.ACE)
        self.assertEqual(card.to_str(), "SA")
        self.assertEqual(card.hcp(), 4)
        self.assertEqual(card.code52(), 0)  # 0*13 + 0 = 0

    def test_card_from_code52(self):
        """Test Card.from_code52() for edge cases."""
        # Ace of Spades (code 0)
        card = Card.from_code52(0)
        self.assertEqual(card.suit, Suit.SPADES)
        self.assertEqual(card.rank, Rank.ACE)

        # Two of Clubs (code 51)
        card = Card.from_code52(51)
        self.assertEqual(card.suit, Suit.CLUBS)
        self.assertEqual(card.rank, Rank.TWO)

    def test_card_hcp(self):
        """Test HCP calculation for face cards."""
        self.assertEqual(Card(Suit.SPADES, Rank.ACE).hcp(), 4)
        self.assertEqual(Card(Suit.HEARTS, Rank.KING).hcp(), 3)
        self.assertEqual(Card(Suit.DIAMONDS, Rank.QUEEN).hcp(), 2)
        self.assertEqual(Card(Suit.CLUBS, Rank.JACK).hcp(), 1)
        self.assertEqual(Card(Suit.SPADES, Rank.TEN).hcp(), 0)
        self.assertEqual(Card(Suit.SPADES, Rank.TWO).hcp(), 0)


class TestHandOperations(unittest.TestCase):
    """Test Hand operations."""

    def test_hand_from_pbn(self):
        """Test parsing hand from PBN format."""
        hand = Hand.from_pbn("AK.QJ2.T987.6543")
        self.assertEqual(len(hand.cards), 13)
        self.assertEqual(hand.suit_length(Suit.SPADES), 2)
        self.assertEqual(hand.suit_length(Suit.HEARTS), 3)
        self.assertEqual(hand.suit_length(Suit.DIAMONDS), 4)
        self.assertEqual(hand.suit_length(Suit.CLUBS), 4)

    def test_hand_to_pbn(self):
        """Test converting hand to PBN format."""
        hand = Hand.from_pbn("AKQ.JT9.876.5432")
        pbn = hand.to_pbn()
        # Should be in same order (S.H.D.C)
        self.assertEqual(pbn, "AKQ.JT9.876.5432")

    def test_hand_hcp(self):
        """Test HCP calculation for entire hand."""
        hand = Hand.from_pbn("AKQ.AKQ.AKQ.AKQ")  # 36 HCP (impossible but tests calc)
        self.assertEqual(hand.hcp(), 36)

        # Valid 13-card hand with all clubs
        hand = Hand.from_pbn("-.-.-.AKQJT9876543")
        self.assertEqual(hand.hcp(), 10)  # A+K+Q+J = 4+3+2+1 = 10

    def test_hand_void(self):
        """Test hand with void suit."""
        hand = Hand.from_pbn("AKQJT98765432.-.-.-")  # 13 spades (A K Q J T 9 8 7 6 5 4 3 2)
        # Note: '-' represents a void
        self.assertEqual(hand.suit_length(Suit.SPADES), 13)
        self.assertEqual(hand.suit_length(Suit.HEARTS), 0)


class TestBidOperations(unittest.TestCase):
    """Test Bid operations."""

    def test_bid_from_str(self):
        """Test parsing bids from string."""
        # Regular bids
        bid = Bid.from_str("1S")
        self.assertEqual(bid.level, 1)
        self.assertEqual(bid.suit, Suit.SPADES)

        bid = Bid.from_str("3NT")
        self.assertEqual(bid.level, 3)
        self.assertEqual(bid.suit, Suit.NOTRUMP)

        # Special bids
        self.assertTrue(Bid.from_str("PASS").is_pass)
        self.assertTrue(Bid.from_str("P").is_pass)
        self.assertTrue(Bid.from_str("X").is_double)
        self.assertTrue(Bid.from_str("XX").is_redouble)

    def test_bid_to_str(self):
        """Test converting bid to string."""
        self.assertEqual(Bid(level=1, suit=Suit.SPADES).to_str(), "1S")
        self.assertEqual(Bid(level=3, suit=Suit.NOTRUMP).to_str(), "3NT")
        self.assertEqual(Bid.make_pass().to_str(), "PASS")
        self.assertEqual(Bid.make_double().to_str(), "X")
        self.assertEqual(Bid.make_redouble().to_str(), "XX")

    def test_1_spades_bid(self):
        """Test 1 Spades bid specifically (suit value is 0)."""
        bid = Bid.from_str("1S")
        self.assertEqual(bid.level, 1)
        self.assertEqual(bid.suit, Suit.SPADES)
        self.assertEqual(bid.suit.value, 0)
        self.assertFalse(bid.is_pass)
        self.assertEqual(bid.to_str(), "1S")
        self.assertEqual(bid.symbol(), "1♠")


class TestContractOperations(unittest.TestCase):
    """Test Contract operations."""

    def test_contract_to_str(self):
        """Test contract string representation."""
        contract = Contract(level=4, suit=Suit.HEARTS, declarer=Seat.SOUTH)
        self.assertEqual(contract.to_str(), "4H")

        contract = Contract(level=3, suit=Suit.NOTRUMP, doubled=True, declarer=Seat.NORTH)
        self.assertEqual(contract.to_str(), "3NTX")

        contract = Contract(level=6, suit=Suit.SPADES, redoubled=True, declarer=Seat.EAST)
        self.assertEqual(contract.to_str(), "6SXX")

    def test_contract_target_tricks(self):
        """Test target tricks calculation."""
        for level in range(1, 8):
            contract = Contract(level=level, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
            self.assertEqual(contract.target_tricks(), 6 + level)


class TestTrickWinner(unittest.TestCase):
    """Test trick winner determination."""

    def test_trick_winner_no_trump(self):
        """Test trick winner without trump suit."""
        trick = Trick(leader=Seat.NORTH)
        # North leads SA, East plays S2, South plays SK, West plays SQ
        trick.add_card(Card(Suit.SPADES, Rank.ACE), trump=None)
        trick.add_card(Card(Suit.SPADES, Rank.TWO), trump=None)
        trick.add_card(Card(Suit.SPADES, Rank.KING), trump=None)
        trick.add_card(Card(Suit.SPADES, Rank.QUEEN), trump=None)

        self.assertTrue(trick.is_complete())
        self.assertEqual(trick.winner, Seat.NORTH)  # Ace wins

    def test_trick_winner_with_trump(self):
        """Test trick winner with trump suit."""
        trick = Trick(leader=Seat.NORTH)
        # North leads HA, East trumps with S2
        trick.add_card(Card(Suit.HEARTS, Rank.ACE), trump=Suit.SPADES)
        trick.add_card(Card(Suit.SPADES, Rank.TWO), trump=Suit.SPADES)  # Small trump
        trick.add_card(Card(Suit.HEARTS, Rank.KING), trump=Suit.SPADES)
        trick.add_card(Card(Suit.HEARTS, Rank.QUEEN), trump=Suit.SPADES)

        self.assertEqual(trick.winner, Seat.EAST)  # Trump wins

    def test_trick_winner_spades_trump(self):
        """Test with Spades as trump (Suit.SPADES = 0)."""
        trick = Trick(leader=Seat.SOUTH)
        # Play order: South -> West -> North -> East
        # South leads HA, West trumps with SA (Ace of Spades)
        trick.add_card(Card(Suit.HEARTS, Rank.ACE), trump=Suit.SPADES)   # South leads
        trick.add_card(Card(Suit.SPADES, Rank.ACE), trump=Suit.SPADES)   # West trumps with SA
        trick.add_card(Card(Suit.HEARTS, Rank.KING), trump=Suit.SPADES)  # North follows
        trick.add_card(Card(Suit.HEARTS, Rank.QUEEN), trump=Suit.SPADES) # East follows

        self.assertEqual(trick.winner, Seat.WEST)  # Spade ace wins


class TestBoardState(unittest.TestCase):
    """Test BoardState operations."""

    def test_board_dealer_vuln(self):
        """Test dealer and vulnerability rotation."""
        # Board 1: N deals, none vul
        dealer, vuln = BoardState._board_dealer_vuln(1)
        self.assertEqual(dealer, Seat.NORTH)
        self.assertEqual(vuln, Vulnerability.NONE)

        # Board 2: E deals, N-S vul
        dealer, vuln = BoardState._board_dealer_vuln(2)
        self.assertEqual(dealer, Seat.EAST)
        self.assertEqual(vuln, Vulnerability.NS)

    def test_get_current_bidder(self):
        """Test current bidder calculation."""
        board = BoardState(board_number=1)  # North deals
        self.assertEqual(board.get_current_bidder(), Seat.NORTH)

        board.auction.append(Bid.make_pass())
        self.assertEqual(board.get_current_bidder(), Seat.EAST)

        board.auction.append(Bid.from_str("1S"))
        self.assertEqual(board.get_current_bidder(), Seat.SOUTH)

    def test_is_auction_complete(self):
        """Test auction completion detection."""
        board = BoardState(board_number=1)
        self.assertFalse(board.is_auction_complete())

        # Add 1S - Pass - Pass - Pass
        board.auction = [
            Bid.from_str("1S"),
            Bid.make_pass(),
            Bid.make_pass(),
            Bid.make_pass()
        ]
        self.assertTrue(board.is_auction_complete())

    def test_is_passed_out(self):
        """Test passed-out detection."""
        board = BoardState(board_number=1)
        board.auction = [
            Bid.make_pass(),
            Bid.make_pass(),
            Bid.make_pass(),
            Bid.make_pass()
        ]
        self.assertTrue(board.is_passed_out())


class TestVulnerability(unittest.TestCase):
    """Test Vulnerability operations."""

    def test_vulnerability_is_vulnerable(self):
        """Test is_vulnerable() for different vulnerabilities."""
        # None
        self.assertFalse(Vulnerability.NONE.is_vulnerable(Seat.NORTH))
        self.assertFalse(Vulnerability.NONE.is_vulnerable(Seat.EAST))

        # N-S
        self.assertTrue(Vulnerability.NS.is_vulnerable(Seat.NORTH))
        self.assertTrue(Vulnerability.NS.is_vulnerable(Seat.SOUTH))
        self.assertFalse(Vulnerability.NS.is_vulnerable(Seat.EAST))

        # E-W
        self.assertFalse(Vulnerability.EW.is_vulnerable(Seat.NORTH))
        self.assertTrue(Vulnerability.EW.is_vulnerable(Seat.EAST))

        # Both
        self.assertTrue(Vulnerability.BOTH.is_vulnerable(Seat.NORTH))
        self.assertTrue(Vulnerability.BOTH.is_vulnerable(Seat.EAST))


class TestDictionaryWithEnumKeys(unittest.TestCase):
    """Test that dictionaries work correctly with enum keys (especially value=0)."""

    def test_hands_dict_with_seat_north(self):
        """Test that Seat.NORTH works as a dict key."""
        hands = {}
        hands[Seat.NORTH] = Hand.from_pbn("AKQ.JT9.876.5432")
        hands[Seat.SOUTH] = Hand.from_pbn("JT9.AKQ.543.876")

        self.assertIn(Seat.NORTH, hands)
        self.assertEqual(hands[Seat.NORTH].suit_length(Suit.SPADES), 3)

        # Verify 'in' operator works for Seat.NORTH
        self.assertTrue(Seat.NORTH in hands)

    def test_dd_results_with_all_enums(self):
        """Test dictionary with both Seat and Suit as keys."""
        results = {}
        for seat in Seat:
            results[seat] = {}
            for suit in [Suit.NOTRUMP, Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]:
                results[seat][suit] = 7  # All make 7 tricks

        # Verify all entries are accessible
        self.assertEqual(results[Seat.NORTH][Suit.SPADES], 7)
        self.assertEqual(results[Seat.SOUTH][Suit.NOTRUMP], 7)


def run_tests():
    """Run all tests."""
    print("=" * 70)
    print("BEN Bridge - Comprehensive Test Suite")
    print("=" * 70)

    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestFalsyEnumValues,
        TestSeatOperations,
        TestCardOperations,
        TestHandOperations,
        TestBidOperations,
        TestContractOperations,
        TestTrickWinner,
        TestBoardState,
        TestVulnerability,
        TestDictionaryWithEnumKeys,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"All {result.testsRun} tests PASSED!")
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
        print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
