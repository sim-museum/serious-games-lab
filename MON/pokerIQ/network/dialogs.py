"""Network dialogs for hosting and joining poker games."""

from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QGroupBox, QRadioButton, QButtonGroup,
    QMessageBox, QFrame, QGridLayout, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from .protocol import DEFAULT_PORT
from .server import PokerServer
from .client import PokerClient


class HostGameDialog(QDialog):
    """Dialog for hosting a poker game."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host Poker Game")
        self.setMinimumWidth(350)

        self.server: Optional[PokerServer] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Server settings
        settings_group = QGroupBox("Server Settings")
        settings_layout = QGridLayout()

        settings_layout.addWidget(QLabel("Table Name:"), 0, 0)
        self.name_edit = QLineEdit("Poker Table")
        settings_layout.addWidget(self.name_edit, 0, 1)

        settings_layout.addWidget(QLabel("Port:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        settings_layout.addWidget(self.port_spin, 1, 1)

        settings_layout.addWidget(QLabel("Seats:"), 2, 0)
        self.seats_spin = QSpinBox()
        self.seats_spin.setRange(2, 10)
        self.seats_spin.setValue(6)
        settings_layout.addWidget(self.seats_spin, 2, 1)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.start_btn.clicked.connect(self._start_server)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _start_server(self):
        """Start the poker server."""
        name = self.name_edit.text() or "Poker Table"
        port = self.port_spin.value()
        num_seats = self.seats_spin.value()

        self.server = PokerServer(server_name=name, num_seats=num_seats,
                                   host_seat=0, host_name="Hero (Server)")

        if self.server.start(port):
            self.status_label.setText(f"Server running on port {port}")
            self.status_label.setStyleSheet("color: green;")
            self.start_btn.setEnabled(False)
            self.accept()
        else:
            self.status_label.setText("Failed to start server")
            self.status_label.setStyleSheet("color: red;")
            self.server = None

    def get_server(self) -> Optional[PokerServer]:
        """Get the created server instance."""
        return self.server


class JoinGameDialog(QDialog):
    """Dialog for joining a poker game."""

    def __init__(self, player_name: str = "Player", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join Poker Game")
        self.setMinimumWidth(350)

        self.player_name = player_name
        self.client: Optional[PokerClient] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Connection settings
        conn_group = QGroupBox("Connection")
        conn_layout = QGridLayout()

        conn_layout.addWidget(QLabel("Your Name:"), 0, 0)
        self.name_edit = QLineEdit(self.player_name)
        conn_layout.addWidget(self.name_edit, 0, 1)

        conn_layout.addWidget(QLabel("Server IP:"), 1, 0)
        self.host_edit = QLineEdit("localhost")
        conn_layout.addWidget(self.host_edit, 1, 1)

        conn_layout.addWidget(QLabel("Port:"), 2, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        conn_layout.addWidget(self.port_spin, 2, 1)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _connect(self):
        """Connect to the poker server."""
        name = self.name_edit.text() or "Player"
        host = self.host_edit.text() or "localhost"
        port = self.port_spin.value()

        self.client = PokerClient(player_name=name)
        self.client.connected.connect(self._on_connected)
        self.client.connection_failed.connect(self._on_connection_failed)

        self.status_label.setText("Connecting...")
        self.status_label.setStyleSheet("color: blue;")
        self.connect_btn.setEnabled(False)

        self.client.connect_to_server(host, port)

    def _on_connected(self, server_name: str):
        """Handle successful connection."""
        self.status_label.setText(f"Connected to {server_name}")
        self.status_label.setStyleSheet("color: green;")
        self.accept()

    def _on_connection_failed(self, reason: str):
        """Handle connection failure."""
        self.status_label.setText(f"Failed: {reason}")
        self.status_label.setStyleSheet("color: red;")
        self.connect_btn.setEnabled(True)
        self.client = None

    def _cancel(self):
        """Cancel and clean up."""
        if self.client:
            self.client.disconnect_from_server()
            self.client = None
        self.reject()

    def get_client(self) -> Optional[PokerClient]:
        """Get the created client instance."""
        return self.client


class SeatSelectionDialog(QDialog):
    """Dialog for selecting a seat at the poker table."""

    seat_selected = pyqtSignal(int)

    def __init__(self, client: PokerClient, num_seats: int = 6, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Your Seat")
        self.setMinimumSize(500, 400)

        self.client = client
        self.num_seats = num_seats
        self.seat_buttons: Dict[int, QPushButton] = {}

        self._setup_ui()
        self._connect_signals()

        # Request initial seat list
        if client.seats:
            self._update_seats(client.seats)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Select Your Seat")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Seat grid (arranged to match game table layout)
        seat_widget = QWidget()
        seat_layout = QGridLayout(seat_widget)
        seat_layout.setSpacing(15)

        # Match game table layout (clockwise: 0,1,2,3,4,5):
        # Top: seats 5 (left), 0 (right) — above table
        # Right: seats 1, 2 — right of table
        # Left: seats 4, 3 — left of table
        positions = [
            (0, 2),  # Seat 0: top right (Hero/Server)
            (1, 3),  # Seat 1: right upper
            (2, 3),  # Seat 2: right lower
            (2, 0),  # Seat 3: left lower
            (1, 0),  # Seat 4: left upper
            (0, 1),  # Seat 5: top left
        ]

        for i in range(min(self.num_seats, len(positions))):
            btn = QPushButton(f"Seat {i + 1}\n(Empty)")
            btn.setMinimumSize(100, 60)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, seat=i: self._on_seat_clicked(seat))
            self.seat_buttons[i] = btn

            row, col = positions[i]
            seat_layout.addWidget(btn, row, col)

        # Add table center label
        table_label = QLabel("TABLE")
        table_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_label.setStyleSheet("""
            background-color: #228B22;
            color: white;
            border-radius: 10px;
            padding: 20px;
            font-weight: bold;
        """)
        seat_layout.addWidget(table_label, 1, 1, 2, 2)

        layout.addWidget(seat_widget)

        # Status
        self.status_label = QLabel("Select an available seat")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.sit_btn = QPushButton("Sit Down")
        self.sit_btn.setEnabled(False)
        self.sit_btn.clicked.connect(self._request_seat)
        self.leave_btn = QPushButton("Leave Table")
        self.leave_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.sit_btn)
        btn_layout.addWidget(self.leave_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        """Connect client signals."""
        self.client.seat_list_received.connect(self._update_seats)
        self.client.seat_confirmed.connect(self._on_seat_confirmed)
        self.client.seat_rejected.connect(self._on_seat_rejected)
        self.client.player_joined.connect(self._on_player_joined)
        self.client.player_left.connect(self._on_player_left)

    def _update_seats(self, seats: Dict[int, Optional[str]]):
        """Update seat display."""
        for i, btn in self.seat_buttons.items():
            player_name = seats.get(i)
            if player_name:
                btn.setText(f"Seat {i + 1}\n{player_name}")
                btn.setEnabled(False)
                btn.setStyleSheet("background-color: #FFB6C1;")  # Light pink - taken
            else:
                btn.setText(f"Seat {i + 1}\n(Empty)")
                btn.setEnabled(True)
                btn.setStyleSheet("background-color: #90EE90;")  # Light green - available

    def _on_seat_clicked(self, seat_index: int):
        """Handle seat button click."""
        # Uncheck other buttons
        for i, btn in self.seat_buttons.items():
            if i != seat_index:
                btn.setChecked(False)

        self.selected_seat = seat_index
        self.sit_btn.setEnabled(True)

    def _request_seat(self):
        """Request the selected seat."""
        if hasattr(self, 'selected_seat'):
            self.status_label.setText("Requesting seat...")
            self.client.request_seat(self.selected_seat)

    def _on_seat_confirmed(self, seat_index: int):
        """Handle seat confirmation."""
        self.status_label.setText(f"You are now in seat {seat_index + 1}")
        self.seat_selected.emit(seat_index)
        QTimer.singleShot(500, self.accept)

    def _on_seat_rejected(self, reason: str):
        """Handle seat rejection."""
        self.status_label.setText(f"Cannot take seat: {reason}")
        self.status_label.setStyleSheet("color: red;")

    def _on_player_joined(self, name: str):
        """Handle player join notification."""
        self.status_label.setText(f"{name} joined the table")

    def _on_player_left(self, name: str):
        """Handle player left notification."""
        self.status_label.setText(f"{name} left the table")


class NetworkModeDialog(QDialog):
    """Dialog for choosing network mode (host or join)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Play")
        self.setMinimumWidth(300)

        self.mode: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Choose Network Mode")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        # Host button
        host_btn = QPushButton("Host Game")
        host_btn.setMinimumHeight(50)
        host_btn.setToolTip("Start a server for others to join")
        host_btn.clicked.connect(self._select_host)
        layout.addWidget(host_btn)

        # Join button
        join_btn = QPushButton("Join Game")
        join_btn.setMinimumHeight(50)
        join_btn.setToolTip("Connect to an existing server")
        join_btn.clicked.connect(self._select_join)
        layout.addWidget(join_btn)

        layout.addSpacing(10)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select_host(self):
        self.mode = "host"
        self.accept()

    def _select_join(self):
        self.mode = "join"
        self.accept()

    def get_mode(self) -> Optional[str]:
        return self.mode
