"""Poker network server for LAN multiplayer.

Hosts a poker game and manages connected clients.
"""

import uuid
from typing import Dict, Optional, List
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

from .protocol import (
    NetworkMessage, MessageType, DEFAULT_PORT, HEARTBEAT_INTERVAL_MS,
    make_connect_accept, make_connect_reject, make_seat_list,
    make_seat_confirm, make_heartbeat
)


class ClientConnection:
    """Represents a connected client."""

    def __init__(self, socket: QTcpSocket, client_id: str):
        self.socket = socket
        self.client_id = client_id
        self.player_name: Optional[str] = None
        self.seat_index: Optional[int] = None
        self.buffer = b''
        self.missed_heartbeats = 0


class PokerServer(QObject):
    """TCP server for hosting poker games.

    Signals:
        client_connected(client_id, player_name): New client connected
        client_disconnected(client_id): Client disconnected
        seat_assigned(client_id, seat_index): Client took a seat
        action_received(client_id, action, amount): Player action received
        chat_received(client_id, text): Chat message received
        error_occurred(message): Error occurred
    """

    client_connected = pyqtSignal(str, str)
    client_disconnected = pyqtSignal(str)
    seat_assigned = pyqtSignal(str, int)
    action_received = pyqtSignal(str, str, float)
    feature_toggled = pyqtSignal(str, dict)  # player_name, features dict
    chat_received = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, server_name: str = "Poker Table", num_seats: int = 6,
                 host_seat: int = 0, host_name: str = "Hero (Server)", parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.num_seats = num_seats
        self.host_seat = host_seat
        self.host_name = host_name

        self._server = QTcpServer(self)
        self._clients: Dict[str, ClientConnection] = {}
        self._seats: Dict[int, Optional[str]] = {i: None for i in range(num_seats)}  # seat -> client_id
        # Reserve the host's seat with a special marker
        self._seats[host_seat] = "__HOST__"

        self._server.newConnection.connect(self._on_new_connection)

        # Heartbeat timer
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeats)

    def start(self, port: int = DEFAULT_PORT) -> bool:
        """Start the server on the specified port.

        Returns:
            True if server started successfully
        """
        if not self._server.listen(QHostAddress.SpecialAddress.Any, port):
            self.error_occurred.emit(f"Failed to start server: {self._server.errorString()}")
            return False

        self._heartbeat_timer.start(HEARTBEAT_INTERVAL_MS)
        print(f"Poker server started on port {port}")
        return True

    def stop(self):
        """Stop the server and disconnect all clients."""
        self._heartbeat_timer.stop()

        # Disconnect all clients
        for client in list(self._clients.values()):
            client.socket.disconnectFromHost()

        self._clients.clear()
        self._server.close()
        print("Poker server stopped")

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server.isListening()

    def get_server_address(self) -> str:
        """Get the server's listening address."""
        return f"{self._server.serverAddress().toString()}:{self._server.serverPort()}"

    def get_seats(self) -> Dict[int, Optional[str]]:
        """Get current seat assignments.

        Returns:
            Dict mapping seat index to player name (None if empty)
        """
        result = {}
        for seat, client_id in self._seats.items():
            if client_id == "__HOST__":
                result[seat] = self.host_name
            elif client_id and client_id in self._clients:
                result[seat] = self._clients[client_id].player_name
            else:
                result[seat] = None
        return result

    def get_connected_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)

    def get_seated_count(self) -> int:
        """Get number of clients with seats."""
        return sum(1 for cid in self._seats.values() if cid is not None)

    def _on_new_connection(self):
        """Handle new client connection."""
        socket = self._server.nextPendingConnection()
        if not socket:
            return

        client_id = str(uuid.uuid4())[:8]
        client = ClientConnection(socket, client_id)
        self._clients[client_id] = client

        socket.readyRead.connect(lambda: self._on_data_received(client_id))
        socket.disconnected.connect(lambda: self._on_client_disconnected(client_id))
        socket.errorOccurred.connect(lambda err: self._on_socket_error(client_id, err))

        print(f"New connection from {socket.peerAddress().toString()}, assigned ID: {client_id}")

    def _on_data_received(self, client_id: str):
        """Handle data received from a client."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        client.buffer += bytes(client.socket.readAll())

        # Process complete messages (newline-delimited)
        while b'\n' in client.buffer:
            line, client.buffer = client.buffer.split(b'\n', 1)
            try:
                msg = NetworkMessage.from_json(line.decode('utf-8'))
                if msg:
                    self._handle_message(client_id, msg)
            except Exception as e:
                print(f"Error processing message from {client_id}: {e}")

    def _handle_message(self, client_id: str, msg: NetworkMessage):
        """Process a message from a client."""
        client = self._clients.get(client_id)
        if not client:
            return

        if msg.type == MessageType.CONNECT_REQUEST:
            player_name = msg.payload.get('player_name', f'Player_{client_id}')
            client.player_name = player_name

            # Accept connection and send seat list
            accept_msg = make_connect_accept(client_id, self.server_name)
            self._send_to_client(client_id, accept_msg)

            seat_list = make_seat_list(self.get_seats())
            self._send_to_client(client_id, seat_list)

            self.client_connected.emit(client_id, player_name)
            print(f"Player {player_name} connected")

        elif msg.type == MessageType.SEAT_REQUEST:
            seat_index = msg.payload.get('seat_index')
            if seat_index is not None:
                self._handle_seat_request(client_id, seat_index)

        elif msg.type == MessageType.PLAYER_ACTION:
            action = msg.payload.get('action', '')
            amount = msg.payload.get('amount', 0)
            self.action_received.emit(client_id, action, amount)

        elif msg.type == MessageType.CHAT_MESSAGE:
            text = msg.payload.get('text', '')
            self.chat_received.emit(client_id, text)

        elif msg.type == MessageType.FEATURE_TOGGLE:
            player_name = msg.payload.get('player_name', client.player_name)
            features = msg.payload.get('features', {})
            # Notify host app
            self.feature_toggled.emit(player_name, features)
            # Re-broadcast to all clients so everyone sees it
            self.broadcast_feature_toggle(player_name, features)

        elif msg.type == MessageType.HEARTBEAT_ACK:
            client.missed_heartbeats = 0

        elif msg.type == MessageType.DISCONNECT:
            self._on_client_disconnected(client_id)

    def _handle_seat_request(self, client_id: str, seat_index: int):
        """Handle a client's request to sit in a seat."""
        client = self._clients.get(client_id)
        if not client:
            return

        # Validate seat index
        if seat_index < 0 or seat_index >= self.num_seats:
            reject = NetworkMessage(
                type=MessageType.SEAT_TAKEN,
                payload={'seat_index': seat_index, 'reason': 'Invalid seat'}
            )
            self._send_to_client(client_id, reject)
            return

        # Check if seat is taken
        if self._seats[seat_index] is not None:
            reject = NetworkMessage(
                type=MessageType.SEAT_TAKEN,
                payload={'seat_index': seat_index, 'reason': 'Seat already taken'}
            )
            self._send_to_client(client_id, reject)
            return

        # Remove from old seat if any
        if client.seat_index is not None:
            self._seats[client.seat_index] = None

        # Assign new seat
        self._seats[seat_index] = client_id
        client.seat_index = seat_index

        # Confirm to the client
        confirm = make_seat_confirm(seat_index)
        self._send_to_client(client_id, confirm)

        # Broadcast updated seat list to all
        self._broadcast_seat_list()

        self.seat_assigned.emit(client_id, seat_index)
        print(f"Player {client.player_name} took seat {seat_index}")

    def _broadcast_seat_list(self):
        """Send updated seat list to all clients."""
        msg = make_seat_list(self.get_seats())
        self._broadcast(msg)

    def _on_client_disconnected(self, client_id: str):
        """Handle client disconnection."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        player_name = client.player_name or client_id

        # Clear seat
        if client.seat_index is not None:
            self._seats[client.seat_index] = None

        # Clean up
        del self._clients[client_id]

        # Broadcast updated seats
        self._broadcast_seat_list()

        # Broadcast player left
        left_msg = NetworkMessage(
            type=MessageType.PLAYER_LEFT,
            payload={'player_name': player_name}
        )
        self._broadcast(left_msg)

        self.client_disconnected.emit(client_id)
        print(f"Player {player_name} disconnected")

    def _on_socket_error(self, client_id: str, error):
        """Handle socket error."""
        if client_id in self._clients:
            client = self._clients[client_id]
            self.error_occurred.emit(f"Socket error for {client.player_name}: {error}")

    def _send_to_client(self, client_id: str, msg: NetworkMessage):
        """Send a message to a specific client."""
        if client_id not in self._clients:
            return

        client = self._clients[client_id]
        if client.socket.state() == QTcpSocket.SocketState.ConnectedState:
            client.socket.write(msg.to_bytes())

    def _broadcast(self, msg: NetworkMessage, exclude: Optional[str] = None):
        """Send a message to all connected clients."""
        for client_id in self._clients:
            if client_id != exclude:
                self._send_to_client(client_id, msg)

    def _send_heartbeats(self):
        """Send heartbeat to all clients and check for timeouts."""
        heartbeat = make_heartbeat()
        disconnected = []

        for client_id, client in self._clients.items():
            client.missed_heartbeats += 1
            if client.missed_heartbeats > 6:
                # Client missed 6+ heartbeats (30+ seconds)
                disconnected.append(client_id)
            else:
                self._send_to_client(client_id, heartbeat)

        # Disconnect unresponsive clients
        for client_id in disconnected:
            print(f"Client {client_id} timed out")
            self._on_client_disconnected(client_id)

    # Game control methods

    def send_hole_cards(self, client_id: str, cards: list):
        """Send private hole cards to a player."""
        msg = NetworkMessage(
            type=MessageType.HOLE_CARDS,
            payload={'cards': [str(c) for c in cards]}
        )
        self._send_to_client(client_id, msg)

    def broadcast_community_cards(self, cards: list, street: str):
        """Broadcast community cards to all players."""
        msg = NetworkMessage(
            type=MessageType.COMMUNITY_CARDS,
            payload={'cards': [str(c) for c in cards], 'street': street}
        )
        self._broadcast(msg)

    def request_action(self, client_id: str, valid_actions: list,
                       to_call: float, min_raise: float, max_raise: float, pot: float):
        """Request action from a player."""
        from .protocol import make_action_request
        client = self._clients.get(client_id)
        if not client or client.seat_index is None:
            return

        msg = make_action_request(
            client.seat_index, valid_actions, to_call, min_raise, max_raise, pot
        )
        self._send_to_client(client_id, msg)

    def broadcast_action(self, seat_index: int, player_name: str,
                         action: str, amount: float, pot: float):
        """Broadcast a player's action to all clients."""
        from .protocol import make_action_broadcast
        msg = make_action_broadcast(seat_index, player_name, action, amount, pot)
        self._broadcast(msg)

    def broadcast_active_player(self, seat_index: int):
        """Broadcast whose turn it is to all clients."""
        from .protocol import NetworkMessage, MessageType
        msg = NetworkMessage(
            type=MessageType.ACTIVE_PLAYER,
            payload={'seat': seat_index}
        )
        self._broadcast(msg)

    def broadcast_hand_start(self, hand_number: int, button_seat: int,
                             blinds: tuple, stacks: Dict[int, float]):
        """Broadcast start of a new hand."""
        from .protocol import make_hand_start
        msg = make_hand_start(hand_number, button_seat, blinds, stacks)
        self._broadcast(msg)

    def broadcast_hand_end(self, winners: list, pot: float, shown_hands: Dict[int, list],
                           hand_summary: Dict = None):
        """Broadcast end of hand with results."""
        from .protocol import make_hand_end
        # Convert card objects to strings
        shown_str = {seat: [str(c) for c in cards] for seat, cards in shown_hands.items()}
        msg = make_hand_end(winners, pot, shown_str, hand_summary)
        self._broadcast(msg)

    def get_client_for_seat(self, seat_index: int) -> Optional[str]:
        """Get the client ID for a seat (None for host seat or empty seats)."""
        client_id = self._seats.get(seat_index)
        if client_id == "__HOST__":
            return None
        return client_id

    def is_seat_human(self, seat_index: int) -> bool:
        """Check if a seat has a human player (client or host)."""
        return self._seats.get(seat_index) is not None

    def broadcast_feature_toggle(self, player_name: str, features: dict):
        """Broadcast feature activation to all clients."""
        from .protocol import NetworkMessage, MessageType
        msg = NetworkMessage(
            type=MessageType.FEATURE_TOGGLE,
            payload={'player_name': player_name, 'features': features}
        )
        self._broadcast(msg)
