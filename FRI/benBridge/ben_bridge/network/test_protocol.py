#!/usr/bin/env python3
"""
Simple test for network protocol serialization.
Run with: python -m network.test_protocol
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.protocol import (
    MessageType, NetworkMessage,
    make_connect_request, make_connect_accept, make_bid_made, make_card_played,
    make_deal_start
)
from ben_backend.models import Seat, Suit, Card, Bid, Hand, BoardState, Vulnerability


def test_message_serialization():
    """Test basic message serialization/deserialization."""
    print("Testing message serialization...")

    # Test connect request
    msg = make_connect_request("TestPlayer")
    json_str = msg.to_json()
    restored = NetworkMessage.from_json(json_str)
    assert restored.type == MessageType.CONNECT_REQUEST
    assert restored.payload["player_name"] == "TestPlayer"
    print("  - Connect request: OK")

    # Test connect accept
    msg = make_connect_accept("Host", "S", "N", "S")
    json_str = msg.to_json()
    restored = NetworkMessage.from_json(json_str)
    assert restored.type == MessageType.CONNECT_ACCEPT
    assert restored.payload["server_seat"] == "S"
    assert restored.payload["client_seat"] == "N"
    print("  - Connect accept: OK")

    # Test bid made
    bid = Bid(level=1, suit=Suit.HEARTS)
    msg = make_bid_made("S", bid.to_dict())
    json_str = msg.to_json()
    restored = NetworkMessage.from_json(json_str)
    assert restored.type == MessageType.BID_MADE
    assert restored.payload["bidder"] == "S"
    assert restored.payload["bid"]["level"] == 1
    print("  - Bid made: OK")

    # Test card played
    card = Card(Suit.SPADES, Suit.SPADES)  # Note: intentional - Card uses rank, not suit for second param
    card = Card.from_str("SA")  # Ace of Spades
    msg = make_card_played("W", card.to_dict())
    json_str = msg.to_json()
    restored = NetworkMessage.from_json(json_str)
    assert restored.type == MessageType.CARD_PLAYED
    assert restored.payload["player"] == "W"
    assert restored.payload["card"]["suit"] == "S"
    print("  - Card played: OK")

    print("All message serialization tests passed!")


def test_model_serialization():
    """Test model serialization methods."""
    print("\nTesting model serialization...")

    # Test Card
    card = Card.from_str("HK")
    d = card.to_dict()
    restored = Card.from_dict(d)
    assert restored.suit == card.suit
    assert restored.rank == card.rank
    print("  - Card: OK")

    # Test Bid
    bid = Bid(level=3, suit=Suit.NOTRUMP)
    d = bid.to_dict()
    restored = Bid.from_dict(d)
    assert restored.level == bid.level
    assert restored.suit == bid.suit
    print("  - Bid: OK")

    # Test special bids
    pass_bid = Bid.make_pass()
    d = pass_bid.to_dict()
    restored = Bid.from_dict(d)
    assert restored.is_pass == True
    print("  - Pass bid: OK")

    double_bid = Bid.make_double()
    d = double_bid.to_dict()
    restored = Bid.from_dict(d)
    assert restored.is_double == True
    print("  - Double bid: OK")

    # Test Hand
    hand = Hand.from_pbn("AKQ.JT9.876.5432")
    d = hand.to_dict()
    restored = Hand.from_dict(d)
    assert len(restored.cards) == len(hand.cards)
    print("  - Hand: OK")

    # Test hidden hand
    d = hand.to_dict(hidden=True)
    assert d["hidden"] == True
    assert d["count"] == 13
    print("  - Hidden hand: OK")

    # Test BoardState
    board = BoardState(
        board_number=7,
        dealer=Seat.SOUTH,
        vulnerability=Vulnerability.NS,
    )
    board.hands = {
        Seat.NORTH: Hand.from_pbn("AKQ.JT9.876.5432"),
        Seat.EAST: Hand.from_pbn("JT9.876.5432.AKQ"),
        Seat.SOUTH: Hand.from_pbn("876.5432.AKQ.JT9"),
        Seat.WEST: Hand.from_pbn("5432.AKQ.JT9.876"),
    }
    board.auction = [Bid(level=1, suit=Suit.CLUBS), Bid.make_pass()]

    d = board.to_dict()
    restored = BoardState.from_dict(d)
    assert restored.board_number == 7
    assert restored.dealer == Seat.SOUTH
    assert restored.vulnerability == Vulnerability.NS
    assert len(restored.auction) == 2
    print("  - BoardState: OK")

    # Test with hidden seats
    d = board.to_dict(hidden_seats=[Seat.EAST, Seat.WEST])
    assert d["hands"]["E"]["hidden"] == True
    assert d["hands"]["W"]["hidden"] == True
    assert d["hands"]["N"].get("hidden") is not True  # Not hidden, so no key or False
    assert "cards" in d["hands"]["N"]  # Has cards
    print("  - BoardState with hidden hands: OK")

    print("All model serialization tests passed!")


def test_deal_start_message():
    """Test deal start message with hidden hands."""
    print("\nTesting deal start message...")

    board = BoardState(
        board_number=1,
        dealer=Seat.NORTH,
        vulnerability=Vulnerability.NONE,
    )
    board.hands = {
        Seat.NORTH: Hand.from_pbn("AKQ.JT9.876.5432"),
        Seat.EAST: Hand.from_pbn("JT9.876.5432.AKQ"),
        Seat.SOUTH: Hand.from_pbn("876.5432.AKQ.JT9"),
        Seat.WEST: Hand.from_pbn("5432.AKQ.JT9.876"),
    }

    # Server (South) sends to client (North)
    # Hide South and West hands from North
    hidden_seats = [Seat.SOUTH, Seat.WEST]
    hands_dict = {
        seat.to_char(): board.hands[seat].to_dict(hidden=seat in hidden_seats)
        for seat in board.hands
    }

    msg = make_deal_start(
        board_number=1,
        dealer="N",
        vulnerability="None",
        hands=hands_dict,
        sequence=1
    )

    json_str = msg.to_json()
    restored = NetworkMessage.from_json(json_str)

    assert restored.type == MessageType.DEAL_START
    assert restored.payload["board_number"] == 1
    assert restored.payload["hands"]["S"]["hidden"] == True
    assert restored.payload["hands"]["W"]["hidden"] == True
    assert "cards" in restored.payload["hands"]["N"]
    assert "cards" in restored.payload["hands"]["E"]

    print("  - Deal start with hidden hands: OK")
    print("Deal start message tests passed!")


if __name__ == "__main__":
    test_message_serialization()
    test_model_serialization()
    test_deal_start_message()
    print("\n=== All tests passed! ===")
