"""Poker network client for LAN multiplayer.

Connects to a poker server and handles game communication.
"""

from typing import Optional, Dict, List
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QTcpSocket, QHostAddress, QAbstractSocket

from .protocol import (
    NetworkMessage, MessageType, DEFAULT_PORT, HEARTBEAT_INTERVAL_MS,
    make_connect_request, make_seat_request, make_player_action,
    make_heartbeat_ack, make_chat_message
)


class PokerClient(QObject):
    """TCP client for joining poker games.

    Signals:
        connected(server_name): Connected to server
        disconnected(): Disconnected from server
        connection_failed(reason): Connection failed
        seat_list_received(seats): Received seat list {index: player_name or None}
        seat_confirmed(seat_index): Seat assignment confirmed
        seat_rejected(reason): Seat request rejected
        hole_cards_received(cards): Received hole cards
        community_cards_received(cards, street): Received board cards
        action_requested(valid_actions, to_call, min_raise, max_raise, pot): Action needed
        action_broadcast(seat, player, action, amount, pot): Player action occurred
        hand_started(hand_num, button, blinds, stacks): New hand started
        hand_ended(winners, pot, shown_hands): Hand ended
        player_joined(name): Player joined table
        player_left(name): Player left table
        chat_received(sender, text): Chat message received
        error_occurred(message): Error occurred
    """

    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    connection_failed = pyqtSignal(str)
    seat_list_received = pyqtSignal(dict)
    seat_confirmed = pyqtSignal(int)
    seat_rejected = pyqtSignal(str)
    hole_cards_received = pyqtSignal(list)
    community_cards_received = pyqtSignal(list, str)
    action_requested = pyqtSignal(list, float, float, float, float)
    action_broadcast = pyqtSignal(int, str, str, float, float)
    hand_started = pyqtSignal(int, int, tuple, dict)
    hand_ended = pyqtSignal(list, float, dict, dict)  # winners, pot, shown_hands, hand_summary
    player_joined = pyqtSignal(str)
    player_left = pyqtSignal(str)
    active_player_changed = pyqtSignal(int)  # seat index of player whose turn it is
    feature_toggle_received = pyqtSignal(str, dict)  # player_name, features dict
    chat_received = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, player_name: str = "Player", parent=None):
        super().__init__(parent)
        self.player_name = player_name
        self.client_id: Optional[str] = None
        self.server_name: Optional[str] = None
        self.my_seat: Optional[int] = None
        self.seats: Dict[int, Optional[str]] = {}

        self._socket = QTcpSocket(self)
        self._buffer = b''
        self._connecting = False

        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_data_received)
        self._socket.errorOccurred.connect(self._on_error)

        # Connection timeout
        self._connect_timer = QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._on_connect_timeout)

    def connect_to_server(self, host: str, port: int = DEFAULT_PORT, timeout_ms: int = 10000):
        """Connect to a poker server.

        Args:
            host: Server hostname or IP address
            port: Server port
            timeout_ms: Connection timeout in milliseconds
        """
        if self._socket.state() != QTcpSocket.SocketState.UnconnectedState:
            self._socket.disconnectFromHost()

        self._connecting = True
        self._connect_timer.start(timeout_ms)
        self._socket.connectToHost(host, port)

    def disconnect_from_server(self):
        """Disconnect from the server."""
        if self._socket.state() == QTcpSocket.SocketState.ConnectedState:
            # Send disconnect message
            msg = NetworkMessage(type=MessageType.DISCONNECT, payload={})
            self._send(msg)
            self._socket.disconnectFromHost()

    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._socket.state() == QTcpSocket.SocketState.ConnectedState

    def request_seat(self, seat_index: int):
        """Request to sit in a specific seat."""
        msg = make_seat_request(seat_index)
        self._send(msg)

    def send_action(self, action: str, amount: float = 0):
        """Send a player action to the server.

        Args:
            action: Action type ('fold', 'check', 'call', 'bet', 'raise', 'all-in')
            amount: Amount for bet/raise actions
        """
        msg = make_player_action(action, amount)
        self._send(msg)

    def send_chat(self, text: str):
        """Send a chat message."""
        msg = make_chat_message(self.player_name, text)
        self._send(msg)

    def send_feature_toggle(self, features: dict):
        """Send feature toggle to server for broadcast."""
        msg = NetworkMessage(
            type=MessageType.FEATURE_TOGGLE,
            payload={'player_name': self.player_name, 'features': features}
        )
        self._send(msg)

    def _send(self, msg: NetworkMessage):
        """Send a message to the server."""
        if self._socket.state() == QTcpSocket.SocketState.ConnectedState:
            self._socket.write(msg.to_bytes())

    def _on_connected(self):
        """Handle successful connection."""
        self._connecting = False
        self._connect_timer.stop()

        # Send connect request
        msg = make_connect_request(self.player_name)
        self._send(msg)

    def _on_disconnected(self):
        """Handle disconnection."""
        self._connecting = False
        self._connect_timer.stop()
        self.client_id = None
        self.server_name = None
        self.my_seat = None
        self.seats.clear()
        self._buffer = b''
        self.disconnected.emit()

    def _on_connect_timeout(self):
        """Handle connection timeout."""
        if self._connecting:
            self._connecting = False
            self._socket.abort()
            self.connection_failed.emit("Connection timed out")

    def _on_error(self, error):
        """Handle socket error."""
        if self._connecting:
            self._connecting = False
            self._connect_timer.stop()
            self.connection_failed.emit(f"Connection error: {error}")
        else:
            self.error_occurred.emit(f"Socket error: {error}")

    def _on_data_received(self):
        """Handle data received from server."""
        self._buffer += bytes(self._socket.readAll())

        # Process complete messages
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                msg = NetworkMessage.from_json(line.decode('utf-8'))
                if msg:
                    self._handle_message(msg)
            except Exception as e:
                print(f"Error processing message: {e}")

    def _handle_message(self, msg: NetworkMessage):
        """Process a message from the server."""

        if msg.type == MessageType.CONNECT_ACCEPT:
            self.client_id = msg.payload.get('client_id')
            self.server_name = msg.payload.get('server_name', 'Poker Table')
            self.connected.emit(self.server_name)

        elif msg.type == MessageType.CONNECT_REJECT:
            reason = msg.payload.get('reason', 'Connection rejected')
            self._socket.disconnectFromHost()
            self.connection_failed.emit(reason)

        elif msg.type == MessageType.SEAT_LIST:
            # Convert string keys back to int
            seats_data = msg.payload.get('seats', {})
            self.seats = {int(k): v for k, v in seats_data.items()}
            self.seat_list_received.emit(self.seats)

        elif msg.type == MessageType.SEAT_CONFIRM:
            self.my_seat = msg.payload.get('seat_index')
            self.seat_confirmed.emit(self.my_seat)

        elif msg.type == MessageType.SEAT_TAKEN:
            reason = msg.payload.get('reason', 'Seat taken')
            self.seat_rejected.emit(reason)

        elif msg.type == MessageType.PLAYER_JOINED:
            name = msg.payload.get('player_name', 'Unknown')
            self.player_joined.emit(name)

        elif msg.type == MessageType.PLAYER_LEFT:
            name = msg.payload.get('player_name', 'Unknown')
            self.player_left.emit(name)

        elif msg.type == MessageType.HOLE_CARDS:
            cards = msg.payload.get('cards', [])
            self.hole_cards_received.emit(cards)

        elif msg.type == MessageType.COMMUNITY_CARDS:
            cards = msg.payload.get('cards', [])
            street = msg.payload.get('street', '')
            self.community_cards_received.emit(cards, street)

        elif msg.type == MessageType.ACTION_REQUEST:
            valid_actions = msg.payload.get('valid_actions', [])
            to_call = msg.payload.get('to_call', 0)
            min_raise = msg.payload.get('min_raise', 0)
            max_raise = msg.payload.get('max_raise', 0)
            pot = msg.payload.get('pot', 0)
            self.action_requested.emit(valid_actions, to_call, min_raise, max_raise, pot)

        elif msg.type == MessageType.ACTION_BROADCAST:
            seat = msg.payload.get('seat_index', -1)
            player = msg.payload.get('player_name', '')
            action = msg.payload.get('action', '')
            amount = msg.payload.get('amount', 0)
            pot = msg.payload.get('pot', 0)
            self.action_broadcast.emit(seat, player, action, amount, pot)

        elif msg.type == MessageType.HAND_START:
            hand_num = msg.payload.get('hand_number', 0)
            button = msg.payload.get('button_seat', 0)
            sb = msg.payload.get('small_blind', 0)
            bb = msg.payload.get('big_blind', 0)
            stacks = {int(k): v for k, v in msg.payload.get('stacks', {}).items()}
            self.hand_started.emit(hand_num, button, (sb, bb), stacks)

        elif msg.type == MessageType.HAND_END:
            winners = msg.payload.get('winners', [])
            pot = msg.payload.get('pot', 0)
            shown = {int(k): v for k, v in msg.payload.get('shown_hands', {}).items()}
            hand_summary = msg.payload.get('hand_summary', {})
            self.hand_ended.emit(winners, pot, shown, hand_summary)

        elif msg.type == MessageType.CHAT_MESSAGE:
            sender = msg.payload.get('sender', 'Unknown')
            text = msg.payload.get('text', '')
            self.chat_received.emit(sender, text)

        elif msg.type == MessageType.HEARTBEAT:
            # Respond to heartbeat
            self._send(make_heartbeat_ack())

        elif msg.type == MessageType.ACTIVE_PLAYER:
            seat = msg.payload.get('seat', -1)
            if seat >= 0:
                self.active_player_changed.emit(seat)

        elif msg.type == MessageType.FEATURE_TOGGLE:
            player_name = msg.payload.get('player_name', '')
            features = msg.payload.get('features', {})
            self.feature_toggle_received.emit(player_name, features)

        elif msg.type == MessageType.GAME_START:
            pass  # Handle as needed

        elif msg.type == MessageType.POT_UPDATE:
            pass  # Handle as needed

        elif msg.type == MessageType.STACK_UPDATE:
            pass  # Handle as needed
