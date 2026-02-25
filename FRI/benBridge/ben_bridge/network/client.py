"""
Bridge network client using Qt TCP.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QTcpSocket, QAbstractSocket

from .protocol import (
    NetworkMessage, MessageType,
    make_connect_request, make_disconnect,
    make_heartbeat, make_heartbeat_ack,
    DEFAULT_PORT, CONNECTION_TIMEOUT_MS, HEARTBEAT_INTERVAL_MS, HEARTBEAT_TIMEOUT_MS,
)
from ben_backend.models import Seat

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BridgeClient(QObject):
    """
    TCP client for joining a LAN bridge game.

    Connects to a server and receives seat assignment.
    """

    # Signals
    connected = pyqtSignal(str, str, str, str)  # server_name, my_seat, partner_seat, role
    disconnected = pyqtSignal()
    connection_failed = pyqtSignal(str)  # reason
    message_received = pyqtSignal(object)  # NetworkMessage
    connecting = pyqtSignal()  # Emitted when connection attempt starts

    def __init__(self, parent=None):
        super().__init__(parent)

        self._socket: Optional[QTcpSocket] = None
        self._buffer = b""

        # Client configuration
        self._client_name = "Guest"
        self._role = "partner"  # "partner" or "opponent"
        self._my_seat: Optional[Seat] = None
        self._partner_seat: Optional[Seat] = None
        self._server_name = ""

        # Connection state
        self._connection_pending = False

        # Timers
        self._connection_timer = QTimer(self)
        self._connection_timer.setSingleShot(True)
        self._connection_timer.timeout.connect(self._on_connection_timeout)

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._last_heartbeat_received = 0
        self._heartbeat_check_timer = QTimer(self)
        self._heartbeat_check_timer.timeout.connect(self._check_heartbeat_timeout)

        # Sequence tracking
        self._last_sequence = 0

    @property
    def is_connected(self) -> bool:
        """Check if connected to server."""
        return (self._socket is not None and
                self._socket.state() == QTcpSocket.SocketState.ConnectedState and
                not self._connection_pending)

    @property
    def my_seat(self) -> Optional[Seat]:
        """Get my assigned seat."""
        return self._my_seat

    @property
    def partner_seat(self) -> Optional[Seat]:
        """Get my partner's seat."""
        return self._partner_seat

    @property
    def server_name(self) -> str:
        """Get server player name."""
        return self._server_name

    @property
    def client_name(self) -> str:
        """Get client player name."""
        return self._client_name

    def connect_to_server(self, host: str, port: int = DEFAULT_PORT,
                          name: str = "Guest", role: str = "partner") -> bool:
        """
        Connect to a bridge server.

        Args:
            host: Server hostname or IP address
            port: Server port
            name: Client player name
            role: "partner" (play with host) or "opponent" (play against host)

        Returns:
            True if connection attempt started (not yet complete)
        """
        if self._socket is not None:
            self.disconnect_from_server()

        self._client_name = name
        self._role = role
        self._connection_pending = True

        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self._on_socket_connected)
        self._socket.disconnected.connect(self._on_socket_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.errorOccurred.connect(self._on_socket_error)

        logger.info(f"Connecting to {host}:{port} as '{name}' (role: {role})")
        self.connecting.emit()

        self._socket.connectToHost(host, port)
        self._connection_timer.start(CONNECTION_TIMEOUT_MS)

        return True

    def disconnect_from_server(self):
        """Disconnect from the server."""
        self._heartbeat_timer.stop()
        self._heartbeat_check_timer.stop()
        self._connection_timer.stop()

        if self._socket is not None:
            if self._socket.state() == QTcpSocket.SocketState.ConnectedState:
                self.send_message(make_disconnect("Client disconnecting"))
                self._socket.disconnectFromHost()
            self._socket.deleteLater()
            self._socket = None

        self._cleanup()

    def send_message(self, message: NetworkMessage) -> bool:
        """
        Send a message to the server.

        Args:
            message: Message to send

        Returns:
            True if message was sent successfully
        """
        if not self.is_connected:
            return False

        data = message.to_bytes()
        bytes_written = self._socket.write(data)

        if bytes_written == -1:
            logger.error(f"Failed to send message: {self._socket.errorString()}")
            return False

        return True

    def _on_socket_connected(self):
        """Handle successful socket connection."""
        logger.info(f"Socket connected, sending connect request (role: {self._role})")
        self._connection_timer.stop()

        # Send connection request with role
        request = make_connect_request(self._client_name, self._role)
        data = request.to_bytes()
        self._socket.write(data)

        # Restart timer for handshake completion
        self._connection_timer.start(CONNECTION_TIMEOUT_MS)

    def _on_socket_disconnected(self):
        """Handle socket disconnection."""
        logger.info("Socket disconnected")
        self._cleanup()
        self.disconnected.emit()

    def _on_socket_error(self, error):
        """Handle socket error."""
        if self._socket:
            error_str = self._socket.errorString()
            logger.error(f"Socket error: {error_str}")

            if self._connection_pending:
                self._connection_timer.stop()
                self._cleanup()
                self.connection_failed.emit(error_str)

    def _on_connection_timeout(self):
        """Handle connection timeout."""
        logger.warning("Connection timeout")
        if self._connection_pending:
            self._cleanup()
            self.connection_failed.emit("Connection timed out")

    def _on_ready_read(self):
        """Handle incoming data from server."""
        if self._socket is None:
            return

        self._buffer += bytes(self._socket.readAll())

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
        logger.debug(f"Client received: {message.type.value}")

        # Track sequence for sync detection
        if message.sequence > 0:
            if message.sequence > self._last_sequence + 1:
                logger.warning(f"Sequence gap detected: expected {self._last_sequence + 1}, got {message.sequence}")
                # Could request resync here
            self._last_sequence = message.sequence

        if message.type == MessageType.CONNECT_ACCEPT:
            self._handle_connect_accept(message)
        elif message.type == MessageType.CONNECT_REJECT:
            self._handle_connect_reject(message)
        elif message.type == MessageType.DISCONNECT:
            self._handle_disconnect(message)
        elif message.type == MessageType.HEARTBEAT:
            self.send_message(make_heartbeat_ack())
        elif message.type == MessageType.HEARTBEAT_ACK:
            self._last_heartbeat_received = self._get_timestamp()
        else:
            # Forward other messages to the application
            self.message_received.emit(message)

    def _handle_connect_accept(self, message: NetworkMessage):
        """Handle connection acceptance from server."""
        self._connection_timer.stop()
        self._connection_pending = False

        payload = message.payload
        self._server_name = payload.get("server_name", "Host")
        self._my_seat = Seat.from_char(payload.get("client_seat", "N"))
        self._partner_seat = Seat.from_char(payload.get("client_partner_seat", "S"))
        self._role = payload.get("role", "partner")

        # Start heartbeat
        self._last_heartbeat_received = self._get_timestamp()
        self._heartbeat_timer.start(HEARTBEAT_INTERVAL_MS)
        self._heartbeat_check_timer.start(HEARTBEAT_INTERVAL_MS)

        logger.info(f"Connected to '{self._server_name}' as {self._my_seat.to_char()} (role: {self._role})")
        self.connected.emit(
            self._server_name,
            self._my_seat.to_char(),
            self._partner_seat.to_char(),
            self._role
        )

    def _handle_connect_reject(self, message: NetworkMessage):
        """Handle connection rejection from server."""
        self._connection_timer.stop()
        reason = message.payload.get("reason", "Connection rejected")
        logger.warning(f"Connection rejected: {reason}")
        self._cleanup()
        self.connection_failed.emit(reason)

    def _handle_disconnect(self, message: NetworkMessage):
        """Handle disconnect message from server."""
        reason = message.payload.get("reason", "")
        logger.info(f"Server disconnected: {reason}")
        self._cleanup()
        self.disconnected.emit()

    def _cleanup(self):
        """Clean up connection state."""
        self._connection_pending = False
        self._heartbeat_timer.stop()
        self._heartbeat_check_timer.stop()
        self._connection_timer.stop()
        self._buffer = b""
        self._my_seat = None
        self._partner_seat = None
        self._server_name = ""
        self._last_sequence = 0

        if self._socket is not None:
            self._socket.deleteLater()
            self._socket = None

    def _send_heartbeat(self):
        """Send heartbeat to server."""
        if self.is_connected:
            self.send_message(make_heartbeat())

    def _check_heartbeat_timeout(self):
        """Check if heartbeat has timed out."""
        if not self.is_connected:
            return

        elapsed = self._get_timestamp() - self._last_heartbeat_received
        if elapsed > HEARTBEAT_TIMEOUT_MS:
            logger.warning("Server heartbeat timeout")
            self._cleanup()
            self.disconnected.emit()

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        from PyQt6.QtCore import QDateTime
        return QDateTime.currentMSecsSinceEpoch()
