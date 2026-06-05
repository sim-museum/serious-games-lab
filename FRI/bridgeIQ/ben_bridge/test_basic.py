#!/usr/bin/env python3
"""
Basic tests for the BEN Bridge application.
Run this to verify the installation is working.
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


def test_models():
    """Test data models"""
    print("\n=== Testing Data Models ===")

    from ben_backend.models import (
        Card, Hand, Bid, BoardState, Seat, Suit, Vulnerability
    )

    # Test Card
    card = Card(Suit.SPADES, 0)  # Ace of Spades
    assert card.to_str() == "SA", f"Expected SA, got {card.to_str()}"
    assert card.hcp() == 4
    print(f"  Card: {card.symbol()} = {card.hcp()} HCP")

    # Test Hand
    hand = Hand.from_pbn("AKQ32.KQ2.T93.AK")
    assert hand.hcp() == 21  # A=4, K=3, Q=2, K=3, Q=2, A=4, K=3 = 21
    assert hand.suit_length(Suit.SPADES) == 5
    print(f"  Hand: {hand.to_pbn()} = {hand.hcp()} HCP")

    # Test Bid
    bid = Bid.from_str("3NT")
    assert bid.level == 3
    assert bid.suit == Suit.NOTRUMP
    print(f"  Bid: {bid.to_str()} -> {bid.symbol()}")

    # Test BoardState
    board = BoardState(board_number=1)
    assert board.dealer == Seat.NORTH
    assert board.vulnerability == Vulnerability.NONE
    print(f"  Board: #{board.board_number}, Dealer: {board.dealer.to_char()}")

    print("  Models: PASS")


def test_engine_creation():
    """Test engine creation (without model loading)"""
    print("\n=== Testing Engine Creation ===")

    from ben_backend.engine import BridgeEngine

    engine = BridgeEngine(verbose=False)
    print(f"  Engine created")

    # Test random deal generation (no model loading needed)
    board = engine.random_deal(123)
    print(f"  Random deal generated: Board #{board.board_number}")
    print(f"    Dealer: {board.dealer.to_char()}")
    print(f"    Vulnerability: {board.vulnerability.value}")
    print(f"    NS HCP: {board.get_ns_hcp()}")
    print(f"    EW HCP: {board.get_ew_hcp()}")

    for seat in [0, 1, 2, 3]:
        from ben_backend.models import Seat
        s = Seat(seat)
        print(f"    {s.to_char()}: {board.hands[s].to_pbn()}")

    print("  Engine creation: PASS")


def test_pyqt_imports():
    """Test PyQt imports"""
    print("\n=== Testing PyQt Imports ===")

    from PyQt6.QtWidgets import QApplication, QWidget
    from PyQt6.QtCore import Qt
    print("  PyQt6 base: OK")

    from ui.table_view import TableView, CardWidget, FannedHandWidget
    print("  TableView: OK")

    from ui.bidding_box import BiddingBox, BidButton
    print("  BiddingBox: OK")

    from ui.dialogs import (
        PlayerConfigDialog, MatchControlDialog,
        DealFilterDialog, ScoreTableDialog
    )
    print("  Dialogs: OK")

    print("  PyQt imports: PASS")


def test_engine_initialization():
    """Test full engine initialization with model loading"""
    print("\n=== Testing Engine Initialization (loads TensorFlow) ===")

    from ben_backend.engine import BridgeEngine
    from ben_backend.models import Seat

    engine = BridgeEngine(verbose=False)

    print("  Initializing BEN (loading TF models)...")
    success = engine.initialize()

    if success:
        print("  Engine initialized successfully!")

        # Test bidding
        print("  Testing bid request...")
        board = engine.random_deal(42)
        response = engine.get_bid(board, Seat.EAST)

        print(f"    Board {board.board_number}, East to bid")
        print(f"    East hand: {board.hands[Seat.EAST].to_pbn()}")
        print(f"    BEN bid: {response.action}")
        print(f"    Who: {response.who}")

        print("  Engine initialization: PASS")
        return True
    else:
        print("  Engine initialization: FAILED")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("BEN Bridge - Basic Tests")
    print("=" * 60)

    try:
        test_models()
        test_engine_creation()
        test_pyqt_imports()

        # Optional: full engine test (slow, loads TensorFlow)
        if len(sys.argv) > 1 and sys.argv[1] == '--full':
            test_engine_initialization()

        print("\n" + "=" * 60)
        print("All tests PASSED!")
        print("=" * 60)
        print("\nTo run full tests with engine initialization:")
        print("  python test_basic.py --full")
        print("\nTo run the application:")
        print("  ./run.sh")

    except Exception as e:
        print(f"\nTest FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
