"""
Network protocol definitions for LAN bridge play.

Messages are JSON objects with newline delimiter:
{"type": "bid_made", "payload": {...}, "sequence": 42}
"""

import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class MessageType(Enum):
    """Network message types for bridge protocol."""
    # Connection management
    CONNECT_REQUEST = "connect_request"
    CONNECT_ACCEPT = "connect_accept"
    CONNECT_REJECT = "connect_reject"
    DISCONNECT = "disconnect"

    # Keep-alive
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"

    # Game state
    DEAL_START = "deal_start"

    # Bidding
    BID_MADE = "bid_made"

    # Card play
    CARD_PLAYED = "card_played"
    TRICK_COMPLETE = "trick_complete"
    TRICK_CLEAR = "trick_clear"  # Signal to clear trick area (sync "next card")
    BOARD_COMPLETE = "board_complete"

    # Sync/recovery
    STATE_REQUEST = "state_request"
    STATE_RESPONSE = "state_response"

    # Chat/misc
    CHAT_MESSAGE = "chat_message"


class NetworkRole(Enum):
    """Role in network game."""
    SERVER = auto()
    CLIENT = auto()


@dataclass
class NetworkMessage:
    """A network message with type, payload, and sequence number."""
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    sequence: int = 0

    def to_json(self) -> str:
        """Serialize to JSON string with newline delimiter."""
        data = {
            "type": self.type.value,
            "payload": self.payload,
            "sequence": self.sequence,
        }
        return json.dumps(data) + "\n"

    def to_bytes(self) -> bytes:
        """Serialize to bytes for network transmission."""
        return self.to_json().encode('utf-8')

    @classmethod
    def from_json(cls, json_str: str) -> 'NetworkMessage':
        """Deserialize from JSON string."""
        data = json.loads(json_str.strip())
        return cls(
            type=MessageType(data["type"]),
            payload=data.get("payload", {}),
            sequence=data.get("sequence", 0),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NetworkMessage':
        """Deserialize from bytes."""
        return cls.from_json(data.decode('utf-8'))


# Connection protocol messages

def make_connect_request(player_name: str, role: str = "partner") -> NetworkMessage:
    """Create a connection request message.

    Args:
        player_name: Name of the connecting player
        role: Either "partner" (play with host) or "opponent" (play against host)
    """
    return NetworkMessage(
        type=MessageType.CONNECT_REQUEST,
        payload={
            "player_name": player_name,
            "role": role,
        }
    )


def make_connect_accept(
    server_name: str,
    server_seat: str,
    client_seat: str,
    client_partner_seat: str,
    role: str = "partner"
) -> NetworkMessage:
    """Create a connection acceptance message with seat assignments.

    Args:
        server_name: Host player's name
        server_seat: Host player's primary seat (e.g., "S")
        client_seat: Client player's primary seat (e.g., "N" for partner, "E" for opponent)
        client_partner_seat: Client player's partner seat
        role: "partner" or "opponent" - echoed back for confirmation
    """
    return NetworkMessage(
        type=MessageType.CONNECT_ACCEPT,
        payload={
            "server_name": server_name,
            "server_seat": server_seat,
            "client_seat": client_seat,
            "client_partner_seat": client_partner_seat,
            "role": role,
        }
    )


def make_connect_reject(reason: str) -> NetworkMessage:
    """Create a connection rejection message."""
    return NetworkMessage(
        type=MessageType.CONNECT_REJECT,
        payload={"reason": reason}
    )


def make_disconnect(reason: str = "") -> NetworkMessage:
    """Create a disconnect message."""
    return NetworkMessage(
        type=MessageType.DISCONNECT,
        payload={"reason": reason}
    )


def make_heartbeat() -> NetworkMessage:
    """Create a heartbeat message."""
    return NetworkMessage(type=MessageType.HEARTBEAT)


def make_heartbeat_ack() -> NetworkMessage:
    """Create a heartbeat acknowledgment."""
    return NetworkMessage(type=MessageType.HEARTBEAT_ACK)


# Game protocol messages

def make_deal_start(
    board_number: int,
    dealer: str,
    vulnerability: str,
    hands: Dict[str, Any],
    sequence: int = 0
) -> NetworkMessage:
    """Create a deal start message.

    Args:
        board_number: Board number
        dealer: Dealer seat character (N/E/S/W)
        vulnerability: Vulnerability string
        hands: Dict mapping seat chars to hand data (hidden hands have {"hidden": true, "count": 13})
        sequence: Message sequence number
    """
    return NetworkMessage(
        type=MessageType.DEAL_START,
        payload={
            "board_number": board_number,
            "dealer": dealer,
            "vulnerability": vulnerability,
            "hands": hands,
        },
        sequence=sequence
    )


def make_bid_made(
    bidder: str,
    bid: Dict[str, Any],
    sequence: int = 0
) -> NetworkMessage:
    """Create a bid made message.

    Args:
        bidder: Bidder seat character (N/E/S/W)
        bid: Serialized bid dict
        sequence: Message sequence number
    """
    return NetworkMessage(
        type=MessageType.BID_MADE,
        payload={
            "bidder": bidder,
            "bid": bid,
        },
        sequence=sequence
    )


def make_card_played(
    player: str,
    card: Dict[str, Any],
    sequence: int = 0
) -> NetworkMessage:
    """Create a card played message.

    Args:
        player: Player seat character (N/E/S/W)
        card: Serialized card dict
        sequence: Message sequence number
    """
    return NetworkMessage(
        type=MessageType.CARD_PLAYED,
        payload={
            "player": player,
            "card": card,
        },
        sequence=sequence
    )


def make_trick_complete(
    winner: str,
    trick_cards: list,
    declarer_tricks: int,
    defense_tricks: int,
    sequence: int = 0
) -> NetworkMessage:
    """Create a trick complete message."""
    return NetworkMessage(
        type=MessageType.TRICK_COMPLETE,
        payload={
            "winner": winner,
            "trick_cards": trick_cards,
            "declarer_tricks": declarer_tricks,
            "defense_tricks": defense_tricks,
        },
        sequence=sequence
    )


def make_trick_clear(sequence: int = 0) -> NetworkMessage:
    """Create a trick clear message (sync 'next card' between players)."""
    return NetworkMessage(
        type=MessageType.TRICK_CLEAR,
        payload={},
        sequence=sequence
    )


def make_board_complete(
    contract: Dict[str, Any],
    declarer_tricks: int,
    ns_score: int,
    ew_score: int,
    sequence: int = 0
) -> NetworkMessage:
    """Create a board complete message."""
    return NetworkMessage(
        type=MessageType.BOARD_COMPLETE,
        payload={
            "contract": contract,
            "declarer_tricks": declarer_tricks,
            "ns_score": ns_score,
            "ew_score": ew_score,
        },
        sequence=sequence
    )


def make_state_request() -> NetworkMessage:
    """Create a state sync request."""
    return NetworkMessage(type=MessageType.STATE_REQUEST)


def make_state_response(
    board_state: Dict[str, Any],
    sequence: int = 0
) -> NetworkMessage:
    """Create a state sync response with full board state."""
    return NetworkMessage(
        type=MessageType.STATE_RESPONSE,
        payload={"board_state": board_state},
        sequence=sequence
    )


def make_chat_message(sender: str, message: str) -> NetworkMessage:
    """Create a chat message."""
    return NetworkMessage(
        type=MessageType.CHAT_MESSAGE,
        payload={"sender": sender, "message": message}
    )


# Protocol constants
DEFAULT_PORT = 7777
HEARTBEAT_INTERVAL_MS = 5000  # 5 seconds
HEARTBEAT_TIMEOUT_MS = 15000  # 15 seconds
CONNECTION_TIMEOUT_MS = 10000  # 10 seconds
