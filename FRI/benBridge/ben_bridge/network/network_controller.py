"""
High-level network game controller.

Manages network game state and coordinates between the server/client
and the game engine.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List

from .server import BridgeServer
from .client import BridgeClient
from .protocol import (
    NetworkMessage, MessageType, NetworkRole,
    make_deal_start, make_bid_made, make_card_played,
    make_trick_complete, make_trick_clear, make_board_complete,
)
from ben_backend.models import Seat, Bid, Card, BoardState, Hand, PlayerType

import logging

logger = logging.getLogger(__name__)


class NetworkGameController(QObject):
    """
    High-level controller for network bridge games.

    Handles both server and client modes, providing a unified interface
    for the main window to interact with network play.

    Supports two client roles:
    - partner: Client plays on the same team as host (cooperative)
    - opponent: Client plays against the host (competitive)
    """

    # Connection signals
    connection_established = pyqtSignal(str, str, str, str)  # mode, my_seat, partner_seat, client_role
    connection_lost = pyqtSignal(str)  # reason
    client_joined = pyqtSignal(str, str)  # client_name, client_role
    server_started = pyqtSignal(int)  # port

    # Game signals
    deal_received = pyqtSignal(object)  # BoardState
    dummy_revealed = pyqtSignal(object, object)  # dummy_seat (Seat), dummy_hand (Hand)
    remote_bid_received = pyqtSignal(str, object)  # seat_char, Bid
    remote_card_received = pyqtSignal(str, object)  # seat_char, Card
    trick_completed = pyqtSignal(str, int, int)  # winner_seat, declarer_tricks, defense_tricks
    trick_clear_received = pyqtSignal()  # Remote player clicked "next card"
    board_completed = pyqtSignal(dict)  # result data

    # Error signal
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._server: Optional[BridgeServer] = None
        self._client: Optional[BridgeClient] = None
        self._role: Optional[NetworkRole] = None

        # Seat assignments
        self._my_seat: Optional[Seat] = None
        self._partner_seat: Optional[Seat] = None

        # Client role: "partner" (same team as host) or "opponent" (vs host)
        self._client_role = "partner"

        # Remote player's seats (the seats they control)
        self._remote_seats: List[Seat] = []

        # My name
        self._my_name = ""

        # Current board state (for server to track)
        self._current_board: Optional[BoardState] = None

    @property
    def is_active(self) -> bool:
        """Check if network game is active (server or client connected)."""
        if self._role == NetworkRole.SERVER:
            return self._server is not None and self._server.is_running
        elif self._role == NetworkRole.CLIENT:
            return self._client is not None and self._client.is_connected
        return False

    @property
    def is_server(self) -> bool:
        """Check if we are the server."""
        return self._role == NetworkRole.SERVER

    @property
    def is_client(self) -> bool:
        """Check if we are a client."""
        return self._role == NetworkRole.CLIENT

    @property
    def my_seat(self) -> Optional[Seat]:
        """Get my seat."""
        return self._my_seat

    @property
    def partner_seat(self) -> Optional[Seat]:
        """Get my partner's seat."""
        return self._partner_seat

    @property
    def client_role(self) -> str:
        """Get the client role ('partner' or 'opponent')."""
        return self._client_role

    @property
    def my_seats(self) -> List[Seat]:
        """Get list of seats I control.

        In partner mode: just my seat (partner is controlled by remote player)
        In opponent mode: my seat and my partner's seat (full partnership)
        """
        if self._my_seat is None:
            return []
        if self._client_role == "partner":
            # Partner mode: each player controls one seat
            return [self._my_seat]
        else:
            # Opponent mode: each player controls their partnership
            if self._partner_seat is not None:
                return [self._my_seat, self._partner_seat]
            return [self._my_seat]

    @property
    def remote_seats(self) -> List[Seat]:
        """Get list of seats controlled by the remote player."""
        return self._remote_seats

    @property
    def ai_seats(self) -> List[Seat]:
        """Get list of seats controlled by AI (neither me nor remote)."""
        all_seats = set(Seat)
        controlled = set(self.my_seats) | set(self._remote_seats)
        return list(all_seats - controlled)

    def is_my_seat(self, seat: Seat) -> bool:
        """Check if a seat is controlled by me (local player)."""
        result = seat in self.my_seats
        logger.debug(f"is_my_seat({seat}): _my_seat={self._my_seat}, _client_role={self._client_role}, my_seats={self.my_seats}, result={result}")
        return result

    def is_remote_seat(self, seat: Seat) -> bool:
        """Check if a seat is controlled by the remote player."""
        if not self.is_active:
            return False
        result = seat in self._remote_seats
        logger.debug(f"is_remote_seat({seat}): remote_seats={self._remote_seats}, result={result}")
        return result

    def is_ai_seat(self, seat: Seat) -> bool:
        """Check if a seat is controlled by AI."""
        if not self.is_active:
            return False
        return seat in self.ai_seats

    # Server mode

    def start_server(self, port: int, name: str, seat: Seat) -> bool:
        """
        Start a server to host a game.

        Args:
            port: Port to listen on
            name: Host player name
            seat: Host player's seat

        Returns:
            True if server started successfully
        """
        if self._server is not None or self._client is not None:
            self.disconnect()

        self._server = BridgeServer(self)
        self._server.client_connected.connect(self._on_client_connected)
        self._server.client_disconnected.connect(self._on_client_disconnected)
        self._server.message_received.connect(self._on_message_received)
        self._server.error_occurred.connect(self._on_error)
        self._server.server_started.connect(self._on_server_started)

        if self._server.start(port, name, seat):
            self._role = NetworkRole.SERVER
            self._my_seat = seat
            self._partner_seat = seat.partner()
            self._my_name = name
            return True

        self._server = None
        return False

    def _on_server_started(self, port: int):
        """Handle server start."""
        logger.info(f"Server started on port {port}")
        self.server_started.emit(port)

    def _on_client_connected(self, client_name: str, client_role: str):
        """Handle client connection."""
        logger.info(f"Client connected: {client_name} as {client_role}")
        self._client_role = client_role

        # Set remote seats based on client role
        # Partner mode: client controls one seat (server's partner), AI controls opponents
        # Opponent mode: client controls their partnership (2 seats)
        if client_role == "partner":
            client_seat = self._server._client_seat
            self._remote_seats = [client_seat]
        else:
            client_seat = self._server._client_seat
            client_partner = self._server._client_partner_seat
            self._remote_seats = [client_seat, client_partner]

        self.client_joined.emit(client_name, client_role)
        self.connection_established.emit(
            "server",
            self._my_seat.to_char(),
            self._partner_seat.to_char(),
            client_role
        )

    def _on_client_disconnected(self):
        """Handle client disconnection."""
        logger.info("Client disconnected")
        self.connection_lost.emit("Client disconnected")

    # Client mode

    def connect_to_server(self, host: str, port: int, name: str, role: str = "partner") -> bool:
        """
        Connect to a server.

        Args:
            host: Server hostname or IP
            port: Server port
            name: Client player name
            role: "partner" (same team as host) or "opponent" (vs host)

        Returns:
            True if connection attempt started
        """
        if self._server is not None or self._client is not None:
            self.disconnect()

        self._client = BridgeClient(self)
        self._client.connected.connect(self._on_connected_to_server)
        self._client.disconnected.connect(self._on_disconnected_from_server)
        self._client.connection_failed.connect(self._on_connection_failed)
        self._client.message_received.connect(self._on_message_received)

        self._my_name = name
        self._client_role = role
        return self._client.connect_to_server(host, port, name, role)

    def _on_connected_to_server(self, server_name: str, my_seat: str, partner_seat: str, role: str):
        """Handle successful connection to server."""
        logger.info(f"_on_connected_to_server: received my_seat={my_seat}, partner_seat={partner_seat}, role={role}")
        self._role = NetworkRole.CLIENT
        self._my_seat = Seat.from_char(my_seat)
        self._partner_seat = Seat.from_char(partner_seat)
        self._client_role = role
        logger.info(f"_on_connected_to_server: set _my_seat={self._my_seat}, _partner_seat={self._partner_seat}, _client_role={self._client_role}")

        # Set remote seats (what the server controls)
        # Partner mode: server controls their seat (our partner_seat), AI controls opponents
        # Opponent mode: server controls their partnership (opposite of ours)
        if role == "partner":
            self._remote_seats = [self._partner_seat]
        else:
            all_seats = set(Seat)
            our_seats = {self._my_seat, self._my_seat.partner()}
            self._remote_seats = list(all_seats - our_seats)
        logger.info(f"_on_connected_to_server: remote_seats={self._remote_seats}")

        logger.info(f"Connected to '{server_name}' as {my_seat}, partner {partner_seat}, role {role}")
        self.connection_established.emit("client", my_seat, partner_seat, role)

    def _on_disconnected_from_server(self):
        """Handle disconnection from server."""
        logger.info("Disconnected from server")
        self.connection_lost.emit("Disconnected from server")
        self._cleanup()

    def _on_connection_failed(self, reason: str):
        """Handle connection failure."""
        logger.warning(f"Connection failed: {reason}")
        self.error_occurred.emit(reason)
        self._cleanup()

    # Common methods

    def disconnect(self):
        """Disconnect from network game."""
        if self._server is not None:
            self._server.stop()
            self._server = None

        if self._client is not None:
            self._client.disconnect_from_server()
            self._client = None

        self._cleanup()

    def _cleanup(self):
        """Clean up state."""
        self._role = None
        self._my_seat = None
        self._partner_seat = None
        self._current_board = None
        self._client_role = "partner"
        self._remote_seats = []

    def _on_error(self, error: str):
        """Handle error."""
        logger.error(f"Network error: {error}")
        self.error_occurred.emit(error)

    def _on_message_received(self, message: NetworkMessage):
        """Handle received message."""
        logger.debug(f"Message received: {message.type.value}")

        if message.type == MessageType.DEAL_START:
            self._handle_deal_start(message)
        elif message.type == MessageType.BID_MADE:
            self._handle_bid_made(message)
        elif message.type == MessageType.CARD_PLAYED:
            self._handle_card_played(message)
        elif message.type == MessageType.TRICK_COMPLETE:
            self._handle_trick_complete(message)
        elif message.type == MessageType.TRICK_CLEAR:
            self._handle_trick_clear(message)
        elif message.type == MessageType.BOARD_COMPLETE:
            self._handle_board_complete(message)

    def _handle_deal_start(self, message: NetworkMessage):
        """Handle deal start message or dummy reveal."""
        payload = message.payload

        # Check if this is a dummy reveal message
        if payload.get("reveal_dummy"):
            dummy_seat = Seat.from_char(payload["dummy_seat"])
            dummy_hand = Hand.from_dict(payload["dummy_hand"])
            self.dummy_revealed.emit(dummy_seat, dummy_hand)
            return

        board = BoardState.from_dict(payload)
        self._current_board = board
        self.deal_received.emit(board)

    def _handle_bid_made(self, message: NetworkMessage):
        """Handle bid made message."""
        payload = message.payload
        bidder = payload.get("bidder")
        bid = Bid.from_dict(payload.get("bid", {}))
        self.remote_bid_received.emit(bidder, bid)

    def _handle_card_played(self, message: NetworkMessage):
        """Handle card played message."""
        payload = message.payload
        player = payload.get("player")
        card = Card.from_dict(payload.get("card", {}))
        self.remote_card_received.emit(player, card)

    def _handle_trick_complete(self, message: NetworkMessage):
        """Handle trick complete message."""
        payload = message.payload
        winner = payload.get("winner")
        declarer_tricks = payload.get("declarer_tricks", 0)
        defense_tricks = payload.get("defense_tricks", 0)
        self.trick_completed.emit(winner, declarer_tricks, defense_tricks)

    def _handle_board_complete(self, message: NetworkMessage):
        """Handle board complete message."""
        self.board_completed.emit(message.payload)

    def _handle_trick_clear(self, message: NetworkMessage):
        """Handle trick clear message (remote player clicked 'next card')."""
        logger.debug("Received trick clear from remote player")
        self.trick_clear_received.emit()

    # Broadcasting methods (for server/client to send state)

    def _send_message(self, message: NetworkMessage) -> bool:
        """Send a message to the peer."""
        if self._role == NetworkRole.SERVER and self._server:
            return self._server.send_message(message)
        elif self._role == NetworkRole.CLIENT and self._client:
            return self._client.send_message(message)
        return False

    def broadcast_deal(self, board: BoardState):
        """
        Broadcast a new deal to the remote player.

        Only the server should call this.
        """
        if self._role != NetworkRole.SERVER:
            logger.warning("Only server can broadcast deals")
            return

        self._current_board = board

        # Hide opponent hands from the client
        hidden_seats = self.my_seats  # Hide server's hands from client

        # Create deal message
        message = make_deal_start(
            board_number=board.board_number,
            dealer=board.dealer.to_char(),
            vulnerability=board.vulnerability.value,
            hands={
                seat.to_char(): board.hands[seat].to_dict(hidden=seat in hidden_seats)
                for seat in board.hands
            },
            sequence=self._server.get_next_sequence()
        )
        self._send_message(message)

    def broadcast_dummy_reveal(self, dummy_seat: Seat, dummy_hand: 'Hand'):
        """Broadcast dummy's hand when play starts."""
        from .protocol import NetworkMessage, MessageType
        message = NetworkMessage(
            type=MessageType.DEAL_START,  # Reuse deal message to send hand
            payload={
                "reveal_dummy": True,
                "dummy_seat": dummy_seat.to_char(),
                "dummy_hand": dummy_hand.to_dict(hidden=False),
            }
        )
        self._send_message(message)

    def broadcast_bid(self, seat: Seat, bid: Bid):
        """Broadcast a bid to the remote player."""
        message = make_bid_made(
            bidder=seat.to_char(),
            bid=bid.to_dict(),
        )
        self._send_message(message)

    def broadcast_card(self, seat: Seat, card: Card):
        """Broadcast a card play to the remote player."""
        message = make_card_played(
            player=seat.to_char(),
            card=card.to_dict(),
        )
        self._send_message(message)

    def broadcast_trick_complete(self, winner: Seat, declarer_tricks: int, defense_tricks: int):
        """Broadcast trick completion to the remote player."""
        message = make_trick_complete(
            winner=winner.to_char(),
            trick_cards=[],  # Could include trick cards if needed
            declarer_tricks=declarer_tricks,
            defense_tricks=defense_tricks,
        )
        self._send_message(message)

    def broadcast_board_complete(self, contract_dict: dict, declarer_tricks: int,
                                  ns_score: int, ew_score: int):
        """Broadcast board completion to the remote player."""
        message = make_board_complete(
            contract=contract_dict,
            declarer_tricks=declarer_tricks,
            ns_score=ns_score,
            ew_score=ew_score,
        )
        self._send_message(message)

    def broadcast_trick_clear(self):
        """Broadcast trick clear to the remote player (sync 'next card')."""
        message = make_trick_clear()
        self._send_message(message)

    def get_player_type_for_seat(self, seat: Seat) -> PlayerType:
        """
        Get the appropriate player type for a seat in network mode.

        Returns:
            HUMAN for local seats, EXTERNAL for remote player seats, COMPUTER for AI
        """
        if not self.is_active:
            return PlayerType.COMPUTER

        if self.is_my_seat(seat):
            return PlayerType.HUMAN
        elif self.is_remote_seat(seat):
            return PlayerType.EXTERNAL
        else:
            return PlayerType.COMPUTER

    def configure_players_for_network(self, players: dict) -> dict:
        """
        Configure player types for network play.

        Args:
            players: Dict[Seat, Player] - existing player configuration

        Returns:
            Modified player configuration with network-appropriate types
        """
        if not self.is_active:
            return players

        for seat, player in players.items():
            player.player_type = self.get_player_type_for_seat(seat)

        return players
