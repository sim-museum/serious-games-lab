"""
Bridge network server using Qt TCP.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

from .protocol import (
    NetworkMessage, MessageType,
    make_connect_accept, make_connect_reject, make_disconnect,
    make_heartbeat, make_heartbeat_ack,
    DEFAULT_PORT, HEARTBEAT_INTERVAL_MS, HEARTBEAT_TIMEOUT_MS,
)
from ben_backend.models import Seat

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BridgeServer(QObject):
    """
    TCP server for hosting a LAN bridge game.

    Supports a single client connection. The client can choose to be:
    - Partner: plays on the same team as the host
    - Opponent: plays against the host
    """

    # Signals
    client_connected = pyqtSignal(str, str)  # client_name, role
    client_disconnected = pyqtSignal()
    message_received = pyqtSignal(object)  # NetworkMessage
    error_occurred = pyqtSignal(str)  # error message
    server_started = pyqtSignal(int)  # port number
    server_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._server: Optional[QTcpServer] = None
        self._client_socket: Optional[QTcpSocket] = None
        self._buffer = b""

        # Server configuration
        self._server_name = "Host"
        self._server_seat: Optional[Seat] = None
        self._client_name = ""
        self._client_seat: Optional[Seat] = None
        self._client_partner_seat: Optional[Seat] = None
        self._client_role = "partner"

        # Heartbeat
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._last_heartbeat_received = 0
        self._heartbeat_check_timer = QTimer(self)
        self._heartbeat_check_timer.timeout.connect(self._check_heartbeat_timeout)

        # Message sequence number
        self._sequence = 0

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None and self._server.isListening()

    @property
    def is_client_connected(self) -> bool:
        """Check if a client is connected."""
        return (self._client_socket is not None and
                self._client_socket.state() == QTcpSocket.SocketState.ConnectedState)

    @property
    def server_seat(self) -> Optional[Seat]:
        """Get the server player's seat."""
        return self._server_seat

    @property
    def client_seat(self) -> Optional[Seat]:
        """Get the client player's primary seat."""
        return self._client_seat

    @property
    def client_partner_seat(self) -> Optional[Seat]:
        """Get the client player's partner seat."""
        return self._client_partner_seat

    @property
    def client_role(self) -> str:
        """Get the client's role ('partner' or 'opponent')."""
        return self._client_role

    @property
    def server_name(self) -> str:
        """Get server player name."""
        return self._server_name

    @property
    def client_name(self) -> str:
        """Get client player name."""
        return self._client_name

    def start(self, port: int = DEFAULT_PORT, name: str = "Host", seat: Seat = Seat.SOUTH) -> bool:
        """
        Start the server listening on the specified port.

        Args:
            port: Port to listen on
            name: Server player name
            seat: Server player's seat

        Returns:
            True if server started successfully
        """
        if self._server is not None:
            self.stop()

        self._server_name = name
        self._server_seat = seat
        # Client seat will be assigned when they connect and choose their role

        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)

        if not self._server.listen(QHostAddress.SpecialAddress.Any, port):
            error = self._server.errorString()
            logger.error(f"Failed to start server: {error}")
            self.error_occurred.emit(f"Failed to start server: {error}")
            self._server = None
            return False

        logger.info(f"Server started on port {port}, seat: {seat.to_char()}")
        self.server_started.emit(port)
        return True

    def stop(self):
        """Stop the server and disconnect any client."""
        # Stop heartbeat
        self._heartbeat_timer.stop()
        self._heartbeat_check_timer.stop()

        # Disconnect client
        if self._client_socket is not None:
            if self._client_socket.state() == QTcpSocket.SocketState.ConnectedState:
                self.send_message(make_disconnect("Server shutting down"))
                self._client_socket.disconnectFromHost()
            self._client_socket.deleteLater()
            self._client_socket = None

        # Stop server
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None

        self._buffer = b""
        self._sequence = 0
        logger.info("Server stopped")
        self.server_stopped.emit()

    def send_message(self, message: NetworkMessage) -> bool:
        """
        Send a message to the connected client.

        Args:
            message: Message to send

        Returns:
            True if message was sent successfully
        """
        if not self.is_client_connected:
            return False

        # Update sequence number for game messages
        if message.type not in (MessageType.HEARTBEAT, MessageType.HEARTBEAT_ACK):
            self._sequence += 1
            message.sequence = self._sequence

        data = message.to_bytes()
        bytes_written = self._client_socket.write(data)

        if bytes_written == -1:
            logger.error(f"Failed to send message: {self._client_socket.errorString()}")
            return False

        return True

    def get_next_sequence(self) -> int:
        """Get the next sequence number."""
        return self._sequence + 1

    def _on_new_connection(self):
        """Handle new incoming connection."""
        pending_socket = self._server.nextPendingConnection()

        if self._client_socket is not None:
            # Already have a client - reject
            reject_msg = make_connect_reject("Server already has a player connected")
            pending_socket.write(reject_msg.to_bytes())
            pending_socket.disconnectFromHost()
            pending_socket.deleteLater()
            logger.info("Rejected connection - already have a client")
            return

        self._client_socket = pending_socket
        self._client_socket.readyRead.connect(self._on_ready_read)
        self._client_socket.disconnected.connect(self._on_client_disconnected)
        self._client_socket.errorOccurred.connect(self._on_socket_error)

        logger.info(f"Client connecting from {self._client_socket.peerAddress().toString()}")

    def _on_ready_read(self):
        """Handle incoming data from client."""
        if self._client_socket is None:
            return

        self._buffer += bytes(self._client_socket.readAll())

        # Process complete messages (newline-delimited)
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            if line:
                try:
                    message = NetworkMessage.from_bytes(line)
                    self._handle_message(message)
                except Exception as e:
                    logger.error(f"Failed to parse message: {e}")

    def _handle_message(self, message: NetworkMessage):
        """Handle a received message."""
        logger.debug(f"Server received: {message.type.value}")

        if message.type == MessageType.CONNECT_REQUEST:
            self._handle_connect_request(message)
        elif message.type == MessageType.DISCONNECT:
            self._handle_disconnect(message)
        elif message.type == MessageType.HEARTBEAT:
            self.send_message(make_heartbeat_ack())
        elif message.type == MessageType.HEARTBEAT_ACK:
            self._last_heartbeat_received = self._get_timestamp()
        else:
            # Forward other messages to the application
            self.message_received.emit(message)

    def _handle_connect_request(self, message: NetworkMessage):
        """Handle a client connection request."""
        self._client_name = message.payload.get("player_name", "Guest")
        self._client_role = message.payload.get("role", "partner")

        # Assign client seat based on role
        if self._client_role == "partner":
            # Client plays as host's partner (same team)
            self._client_seat = self._server_seat.partner()
            self._client_partner_seat = self._server_seat  # Host is client's partner
        else:
            # Client plays as opponent (opposite team)
            # Client gets one of the opponent seats (the one after host's seat)
            self._client_seat = self._server_seat.next()  # E.g., if host is S, client gets W
            self._client_partner_seat = self._client_seat.partner()  # Client's partner

        # Send acceptance with seat assignments
        accept_msg = make_connect_accept(
            server_name=self._server_name,
            server_seat=self._server_seat.to_char(),
            client_seat=self._client_seat.to_char(),
            client_partner_seat=self._client_partner_seat.to_char(),
            role=self._client_role,
        )
        self.send_message(accept_msg)

        # Start heartbeat
        self._last_heartbeat_received = self._get_timestamp()
        self._heartbeat_timer.start(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_check_timer.start(HEARTBEAT_INTERVAL_MS)

        logger.info(f"Client '{self._client_name}' connected as {self._client_seat.to_char()} (role: {self._client_role})")
        self.client_connected.emit(self._client_name, self._client_role)

    def _handle_disconnect(self, message: NetworkMessage):
        """Handle client disconnect message."""
        reason = message.payload.get("reason", "")
        logger.info(f"Client disconnected: {reason}")
        self._cleanup_client()

    def _on_client_disconnected(self):
        """Handle client socket disconnection."""
        logger.info("Client socket disconnected")
        self._cleanup_client()

    def _on_socket_error(self, error):
        """Handle socket error."""
        if self._client_socket:
            error_str = self._client_socket.errorString()
            logger.error(f"Socket error: {error_str}")
            self.error_occurred.emit(f"Connection error: {error_str}")

    def _cleanup_client(self):
        """Clean up client connection state."""
        self._heartbeat_timer.stop()
        self._heartbeat_check_timer.stop()

        if self._client_socket is not None:
            self._client_socket.deleteLater()
            self._client_socket = None

        self._buffer = b""
        self._client_name = ""
        self.client_disconnected.emit()

    def _send_heartbeat(self):
        """Send heartbeat to client."""
        if self.is_client_connected:
            self.send_message(make_heartbeat())

    def _check_heartbeat_timeout(self):
        """Check if heartbeat has timed out."""
        if not self.is_client_connected:
            return

        elapsed = self._get_timestamp() - self._last_heartbeat_received
        if elapsed > HEARTBEAT_TIMEOUT_MS:
            logger.warning("Client heartbeat timeout")
            self.error_occurred.emit("Connection lost: heartbeat timeout")
            self._cleanup_client()

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        from PyQt6.QtCore import QDateTime
        return QDateTime.currentMSecsSinceEpoch()
