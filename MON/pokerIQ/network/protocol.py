"""Network protocol for poker LAN play.

JSON-based newline-delimited messages for client-server communication.
"""

import json
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import Any, Dict, Optional


DEFAULT_PORT = 7778
HEARTBEAT_INTERVAL_MS = 5000
CONNECTION_TIMEOUT_MS = 10000

# Player name constraints — keep names short so seat labels / ToM tabs fit.
MAX_NAME_LEN = 12


class MessageType(Enum):
    """Message types for poker network protocol."""
    # Connection
    CONNECT_REQUEST = auto()
    CONNECT_ACCEPT = auto()
    CONNECT_REJECT = auto()
    DISCONNECT = auto()
    HEARTBEAT = auto()
    HEARTBEAT_ACK = auto()

    # Lobby
    SEAT_LIST = auto()          # Server sends available seats
    SEAT_REQUEST = auto()       # Client requests a seat
    SEAT_CONFIRM = auto()       # Server confirms seat assignment
    SEAT_TAKEN = auto()         # Server rejects - seat already taken
    PLAYER_JOINED = auto()      # Broadcast: new player joined
    PLAYER_LEFT = auto()        # Broadcast: player left

    # Game control
    GAME_START = auto()         # Server starts the game
    HAND_START = auto()         # New hand begins
    HAND_END = auto()           # Hand ends with results

    # Dealing
    HOLE_CARDS = auto()         # Private: player's hole cards
    COMMUNITY_CARDS = auto()    # Public: board cards

    # Actions
    ACTION_REQUEST = auto()     # Server requests action from player
    PLAYER_ACTION = auto()      # Player submits action
    ACTION_BROADCAST = auto()   # Server broadcasts action to all

    # Game state
    POT_UPDATE = auto()         # Pot size changed
    STACK_UPDATE = auto()       # Player stack changed
    BUTTON_MOVE = auto()        # Dealer button moved
    BLINDS_POSTED = auto()      # Blinds posted
    ACTIVE_PLAYER = auto()      # Server broadcasts whose turn it is

    # Features
    FEATURE_TOGGLE = auto()    # Broadcast feature activation (God Mode, Tells, ToM)

    # Theory of Mind - host sends per-client personalized advice
    TOM_ADVICE = auto()

    # Claude hand analysis - host computes per-player critiques, ships bundle
    HAND_ANALYSIS = auto()

    # Spectator support: server pushes every active player's hole cards to a
    # client that just folded so its God-mode display is meaningful.
    ALL_HOLE_CARDS = auto()

    # Spectator nav: server snapshots board cards as each street is dealt so
    # folded clients can scroll back/forward through past streets.
    BOARD_SNAPSHOT = auto()

    # Host's narrative hand interpretation (the green-Claude-blocks dialog).
    HAND_INTERPRETATION = auto()

    # Chat
    CHAT_MESSAGE = auto()


@dataclass
class NetworkMessage:
    """A network message with type, payload, and sequence number."""
    type: MessageType
    payload: Dict[str, Any]
    sequence: int = 0

    def to_json(self) -> str:
        """Serialize to JSON string with newline delimiter."""
        data = {
            'type': self.type.name,
            'payload': self.payload,
            'sequence': self.sequence
        }
        return json.dumps(data) + '\n'

    def to_bytes(self) -> bytes:
        """Serialize to bytes for network transmission."""
        return self.to_json().encode('utf-8')

    @classmethod
    def from_json(cls, json_str: str) -> Optional['NetworkMessage']:
        """Deserialize from JSON string."""
        try:
            data = json.loads(json_str.strip())
            msg_type = MessageType[data['type']]
            return cls(
                type=msg_type,
                payload=data.get('payload', {}),
                sequence=data.get('sequence', 0)
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Failed to parse message: {e}")
            return None


# Helper functions for creating common messages

def make_connect_request(player_name: str) -> NetworkMessage:
    """Create a connection request message."""
    return NetworkMessage(
        type=MessageType.CONNECT_REQUEST,
        payload={'player_name': player_name}
    )


def make_connect_accept(client_id: str, server_name: str) -> NetworkMessage:
    """Create a connection acceptance message."""
    return NetworkMessage(
        type=MessageType.CONNECT_ACCEPT,
        payload={'client_id': client_id, 'server_name': server_name}
    )


def make_connect_reject(reason: str, code: str = "") -> NetworkMessage:
    """Create a connection rejection message.

    Args:
        reason: Human-readable reason.
        code: Machine-readable tag. One of "name_taken", "name_empty",
            "name_too_long", "full", or "" for other errors.
    """
    return NetworkMessage(
        type=MessageType.CONNECT_REJECT,
        payload={'reason': reason, 'code': code}
    )


def make_hand_analysis(analyses: list, hand_number: int = 0) -> NetworkMessage:
    """Bundle of per-player Claude critiques for the most-recent hand.

    Args:
        analyses: list of {'player': str, 'seat': int, 'text': str}
        hand_number: Hand index (for sanity checks on the client side)
    """
    return NetworkMessage(
        type=MessageType.HAND_ANALYSIS,
        payload={'analyses': list(analyses), 'hand_number': hand_number}
    )


def make_tom_advice(advice: str, notation: str = "", for_seat: int = -1) -> NetworkMessage:
    """Personalized Theory-of-Mind advice from host for one client.

    Args:
        advice: Prose advice (plain text, one screen worth).
        notation: Optional PokerStove-style range notation to display.
        for_seat: The recipient's seat index (for client-side sanity check).
    """
    return NetworkMessage(
        type=MessageType.TOM_ADVICE,
        payload={'advice': advice, 'notation': notation, 'for_seat': for_seat}
    )


def make_seat_list(seats: Dict[int, Optional[str]]) -> NetworkMessage:
    """Create a seat list message.

    Args:
        seats: Dict mapping seat index to player name (None if empty)
    """
    return NetworkMessage(
        type=MessageType.SEAT_LIST,
        payload={'seats': seats}
    )


def make_seat_request(seat_index: int) -> NetworkMessage:
    """Create a seat request message."""
    return NetworkMessage(
        type=MessageType.SEAT_REQUEST,
        payload={'seat_index': seat_index}
    )


def make_seat_confirm(seat_index: int) -> NetworkMessage:
    """Confirm seat assignment."""
    return NetworkMessage(
        type=MessageType.SEAT_CONFIRM,
        payload={'seat_index': seat_index}
    )


def make_hole_cards(cards: list) -> NetworkMessage:
    """Send private hole cards to a player."""
    return NetworkMessage(
        type=MessageType.HOLE_CARDS,
        payload={'cards': cards}
    )


def make_community_cards(cards: list, street: str) -> NetworkMessage:
    """Broadcast community cards."""
    return NetworkMessage(
        type=MessageType.COMMUNITY_CARDS,
        payload={'cards': cards, 'street': street}
    )


def make_action_request(
    seat_index: int,
    valid_actions: list,
    to_call: float,
    min_raise: float,
    max_raise: float,
    pot: float,
    timeout_seconds: int = 30
) -> NetworkMessage:
    """Request action from a player."""
    return NetworkMessage(
        type=MessageType.ACTION_REQUEST,
        payload={
            'seat_index': seat_index,
            'valid_actions': valid_actions,
            'to_call': to_call,
            'min_raise': min_raise,
            'max_raise': max_raise,
            'pot': pot,
            'timeout_seconds': timeout_seconds
        }
    )


def make_player_action(action: str, amount: float = 0) -> NetworkMessage:
    """Player submits their action."""
    return NetworkMessage(
        type=MessageType.PLAYER_ACTION,
        payload={'action': action, 'amount': amount}
    )


def make_action_broadcast(
    seat_index: int,
    player_name: str,
    action: str,
    amount: float,
    pot: float
) -> NetworkMessage:
    """Broadcast a player's action to all clients."""
    return NetworkMessage(
        type=MessageType.ACTION_BROADCAST,
        payload={
            'seat_index': seat_index,
            'player_name': player_name,
            'action': action,
            'amount': amount,
            'pot': pot
        }
    )


def make_hand_start(
    hand_number: int,
    button_seat: int,
    blinds: tuple,
    stacks: Dict[int, float]
) -> NetworkMessage:
    """Signal start of a new hand."""
    return NetworkMessage(
        type=MessageType.HAND_START,
        payload={
            'hand_number': hand_number,
            'button_seat': button_seat,
            'small_blind': blinds[0],
            'big_blind': blinds[1],
            'stacks': stacks
        }
    )


def make_hand_end(
    winners: list,
    pot: float,
    shown_hands: Dict[int, list],
    hand_summary: Dict = None
) -> NetworkMessage:
    """Signal end of hand with results."""
    payload = {
        'winners': winners,
        'pot': pot,
        'shown_hands': shown_hands
    }
    if hand_summary:
        payload['hand_summary'] = hand_summary
    return NetworkMessage(
        type=MessageType.HAND_END,
        payload=payload
    )


def make_heartbeat() -> NetworkMessage:
    """Create heartbeat message."""
    return NetworkMessage(type=MessageType.HEARTBEAT, payload={})


def make_heartbeat_ack() -> NetworkMessage:
    """Create heartbeat acknowledgment."""
    return NetworkMessage(type=MessageType.HEARTBEAT_ACK, payload={})


def make_all_hole_cards(cards_by_seat: Dict[int, list]) -> NetworkMessage:
    """Reveal every active seat's hole cards to a single (folded) client.

    Args:
        cards_by_seat: {seat_index: [card_str, card_str]}
    """
    return NetworkMessage(
        type=MessageType.ALL_HOLE_CARDS,
        payload={'cards_by_seat': {int(k): list(v) for k, v in cards_by_seat.items()}}
    )


def make_board_snapshot(street: str, street_idx: int, board: list,
                        action_log: list) -> NetworkMessage:
    """Snapshot of a street the host just dealt — lets folded clients
    navigate back and forth between past streets.
    """
    return NetworkMessage(
        type=MessageType.BOARD_SNAPSHOT,
        payload={
            'street': street,
            'street_idx': street_idx,
            'board': list(board),
            'action_log': list(action_log),
        }
    )


def make_hand_interpretation(text: str, hand_number: int = 0,
                              assists_used: Optional[Dict[str, list]] = None
                              ) -> NetworkMessage:
    """Host's narrative interpretation text (Hand #N Analysis) plus the
    bright-coloured assists-used flags so all clients can render the same
    dialog the host sees.
    """
    return NetworkMessage(
        type=MessageType.HAND_INTERPRETATION,
        payload={
            'text': text,
            'hand_number': hand_number,
            'assists_used': assists_used or {},
        }
    )


def make_chat_message(sender: str, text: str) -> NetworkMessage:
    """Create a chat message."""
    return NetworkMessage(
        type=MessageType.CHAT_MESSAGE,
        payload={'sender': sender, 'text': text}
    )
