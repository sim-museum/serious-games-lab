"""
Connect to Server Dialog for LAN play.
Allows a player to connect to a hosted bridge game.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton, QProgressBar,
    QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from ben_backend.models import Seat
from .dialog_style import apply_dialog_style


class ConnectServerDialog(QDialog):
    """
    Dialog for connecting to a LAN server.

    The guest enters host/port/name and picks ANY of the four seats. The
    server tells the client which seats are already taken; if the guest's
    choice collides with the host (or another guest who connected first)
    the dialog re-opens listing which seats are still free.
    """

    # Emitted when user clicks Connect: host, port, name, seat_char
    connect_requested = pyqtSignal(str, int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Network Game")
        self.setMinimumWidth(450)
        apply_dialog_style(self)

        self._connecting = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Connection settings group
        settings_group = QGroupBox("Connection Settings")
        settings_layout = QGridLayout(settings_group)

        # Host
        settings_layout.addWidget(QLabel("Server address:"), 0, 0)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("IP address or hostname")
        settings_layout.addWidget(self.host_edit, 0, 1)

        # Port
        settings_layout.addWidget(QLabel("Port:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(7777)
        settings_layout.addWidget(self.port_spin, 1, 1)

        # Player name
        settings_layout.addWidget(QLabel("Your name:"), 2, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setText("Guest")
        settings_layout.addWidget(self.name_edit, 2, 1)

        # Seat selection - guest picks any seat; server validates it is free
        settings_layout.addWidget(QLabel("Your seat:"), 3, 0)
        self.seat_combo = QComboBox()
        self.seat_combo.addItem("North (N)", Seat.NORTH)
        self.seat_combo.addItem("East (E)",  Seat.EAST)
        self.seat_combo.addItem("South (S)", Seat.SOUTH)
        self.seat_combo.addItem("West (W)",  Seat.WEST)
        settings_layout.addWidget(self.seat_combo, 3, 1)

        settings_hint = QLabel(
            "If the seat is already taken, the server will tell you which\n"
            "seats are still free."
        )
        settings_hint.setWordWrap(True)
        settings_hint.setStyleSheet("color: #555; font-size: 11px;")
        settings_layout.addWidget(settings_hint, 4, 0, 1, 2)

        layout.addWidget(settings_group)

        # Status group (shown during connection)
        self.status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout(self.status_group)

        self.status_label = QLabel("Not connected")
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        self.status_group.setVisible(False)
        layout.addWidget(self.status_group)

        # Error display
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c00; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        button_layout.addWidget(self.connect_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_connect_clicked(self):
        """Handle Connect button click."""
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        name = self.name_edit.text().strip() or "Guest"
        seat = self.seat_combo.currentData()
        seat_char = seat.to_char() if seat is not None else "S"

        if not host:
            self.show_error("Please enter a server address")
            return

        self.set_connecting(True)
        self.connect_requested.emit(host, port, name, seat_char)

    def set_connecting(self, connecting: bool):
        """Set the connecting state (shows progress indicator)."""
        self._connecting = connecting
        self.status_group.setVisible(connecting)
        self.progress_bar.setVisible(connecting)
        self.connect_btn.setEnabled(not connecting)
        self.host_edit.setEnabled(not connecting)
        self.port_spin.setEnabled(not connecting)
        self.name_edit.setEnabled(not connecting)
        self.seat_combo.setEnabled(not connecting)
        self.error_label.setVisible(False)

        if connecting:
            self.status_label.setText("Connecting...")
        else:
            self.status_label.setText("Not connected")

    def show_error(self, message: str):
        """Show an error message."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.set_connecting(False)

    def show_status(self, message: str):
        """Show a status message."""
        self.status_label.setText(message)
        self.status_group.setVisible(True)

    def get_settings(self) -> dict:
        """
        Get the configured connection settings.

        Returns:
            Dict with 'host', 'port', 'name', and 'seat' (seat char N/E/S/W)
        """
        seat = self.seat_combo.currentData()
        return {
            'host': self.host_edit.text().strip(),
            'port': self.port_spin.value(),
            'name': self.name_edit.text().strip() or "Guest",
            'seat': seat.to_char() if seat is not None else "S",
        }
