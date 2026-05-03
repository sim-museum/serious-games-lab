"""
Connect to Server Dialog for LAN play.

Two-phase flow modelled on pokerIQ's seat picker:
1. Connection form — enter host/port/name.
2. Lobby view — graphical 4-seat board with live occupancy. The guest
   picks an empty seat (server confirms) and waits there until the host
   broadcasts GAME_START.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QStackedWidget,
    QLabel, QLineEdit, QSpinBox, QPushButton, QProgressBar, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ben_backend.models import Seat
from .dialog_style import apply_dialog_style
from .seat_board_widget import SeatBoardWidget


class ConnectServerDialog(QDialog):
    """Dialog that walks a guest through connecting and seat selection."""

    # Emitted when the guest clicks Connect with an attempted seat
    # (host, port, name, seat_char). If the seat is rejected, the dialog
    # surfaces the error inline and lets the user pick a different seat.
    connect_requested = pyqtSignal(str, int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Network Game")
        self.setMinimumWidth(520)
        apply_dialog_style(self)

        self._connecting = False
        self._selected_seat: Seat = Seat.SOUTH
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_form_page())
        self._stack.addWidget(self._build_lobby_page())
        layout.addWidget(self._stack)

    # ------------------------------------------------------------------ #
    # Phase 1: connection form (host/port/name + seat board)
    # ------------------------------------------------------------------ #
    def _build_form_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        settings_group = QGroupBox("Connection Settings")
        settings_layout = QGridLayout(settings_group)

        settings_layout.addWidget(QLabel("Server address:"), 0, 0)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("IP address or hostname")
        settings_layout.addWidget(self.host_edit, 0, 1)

        settings_layout.addWidget(QLabel("Port:"), 1, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(7777)
        settings_layout.addWidget(self.port_spin, 1, 1)

        settings_layout.addWidget(QLabel("Your name:"), 2, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setText("Guest")
        settings_layout.addWidget(self.name_edit, 2, 1)
        layout.addWidget(settings_group)

        # Pre-connection seat board. Without a server yet there is no live
        # state to render — the guest just clicks the seat they would like.
        # If it turns out to be taken the server replies with the free list
        # and the lobby phase shows live updates.
        self._form_board = SeatBoardWidget(allow_click=True)
        self._form_board.set_seats({}, host_seat="")
        self._form_board.seat_clicked.connect(self._on_seat_clicked_form)
        layout.addWidget(self._form_board)

        self._form_seat_status = QLabel(f"Seat selected: {self._selected_seat.to_char()}")
        self._form_seat_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._form_seat_status)

        # Status (shown during the connection attempt).
        self.status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout(self.status_group)
        self.status_label = QLabel("Not connected")
        status_layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        self.status_group.setVisible(False)
        layout.addWidget(self.status_group)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c00; font-weight: bold;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        button_layout.addWidget(self.connect_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        return page

    # ------------------------------------------------------------------ #
    # Phase 2: lobby — visible after the connection succeeds
    # ------------------------------------------------------------------ #
    def _build_lobby_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.lobby_status = QLabel("Waiting for the host to start the game…")
        self.lobby_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lobby_status)

        self._lobby_board = SeatBoardWidget(allow_click=False)
        layout.addWidget(self._lobby_board)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.leave_btn = QPushButton("Leave Table")
        self.leave_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.leave_btn)
        layout.addLayout(button_layout)
        return page

    # ------------------------------------------------------------------ #
    # External API used by main_window
    # ------------------------------------------------------------------ #
    def update_seat_map(self, seats: dict, host_seat: str = "",
                        my_seat: Seat = None):
        """Apply a fresh seat list. Routed from NetworkGameController."""
        self._form_board.set_seats(seats, host_seat=host_seat, my_seat=my_seat)
        self._lobby_board.set_seats(seats, host_seat=host_seat, my_seat=my_seat)

    def enter_lobby(self, my_seat: Seat):
        """Switch the dialog to the lobby (post-connection) view."""
        self._selected_seat = my_seat or self._selected_seat
        self._lobby_board.set_my_seat(self._selected_seat)
        self._stack.setCurrentIndex(1)
        self.setWindowTitle(
            f"Network Game Lobby — seated at {self._selected_seat.to_char()}"
        )

    def show_lobby_status(self, message: str):
        self.lobby_status.setText(message)

    # ------------------------------------------------------------------ #
    # Internal handlers
    # ------------------------------------------------------------------ #
    def _on_seat_clicked_form(self, seat: Seat):
        self._selected_seat = seat
        self._form_seat_status.setText(f"Seat selected: {seat.to_char()}")
        self._form_board.set_my_seat(seat)

    def _on_connect_clicked(self):
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        name = self.name_edit.text().strip() or "Guest"
        seat_char = self._selected_seat.to_char()

        if not host:
            self.show_error("Please enter a server address")
            return

        self.set_connecting(True)
        self.connect_requested.emit(host, port, name, seat_char)

    def set_connecting(self, connecting: bool):
        self._connecting = connecting
        self.status_group.setVisible(connecting)
        self.progress_bar.setVisible(connecting)
        self.connect_btn.setEnabled(not connecting)
        self.host_edit.setEnabled(not connecting)
        self.port_spin.setEnabled(not connecting)
        self.name_edit.setEnabled(not connecting)
        self.error_label.setVisible(False)
        self.status_label.setText("Connecting…" if connecting else "Not connected")

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.set_connecting(False)
        # Stay on the form page so the user can re-pick a seat / retry.
        self._stack.setCurrentIndex(0)
