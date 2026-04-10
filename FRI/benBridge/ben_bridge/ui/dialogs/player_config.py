"""
Player Configuration Dialog
Configure human/computer players and visibility settings.
Supports up to 4 human players with unique names.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QComboBox, QCheckBox, QPushButton, QRadioButton,
    QButtonGroup, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from ben_backend.models import Seat, PlayerType, Player
from typing import Dict

from .dialog_style import apply_dialog_style

SEAT_NAMES = {Seat.NORTH: "North", Seat.EAST: "East", Seat.SOUTH: "South", Seat.WEST: "West"}


class PlayerConfigDialog(QDialog):
    """
    Dialog for configuring players at each seat.
    Supports up to 4 human players with unique name enforcement.
    """

    def __init__(self, players: Dict[Seat, Player], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Player Configuration")
        self.setMinimumWidth(450)
        apply_dialog_style(self)

        self.players = {seat: Player(seat=seat,
                                     player_type=p.player_type,
                                     name=p.name,
                                     visible=p.visible)
                       for seat, p in players.items()}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Mode selection
        mode_group = QGroupBox("Game Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_buttons = QButtonGroup(self)

        self.four_player_radio = QRadioButton("4 Players (Human South, AI others)")
        self.four_player_radio.setChecked(True)
        self.mode_buttons.addButton(self.four_player_radio, 0)
        mode_layout.addWidget(self.four_player_radio)

        self.multi_human_radio = QRadioButton("Multi-Human (choose which seats are human)")
        self.mode_buttons.addButton(self.multi_human_radio, 1)
        mode_layout.addWidget(self.multi_human_radio)

        self.one_player_radio = QRadioButton("1 Player (Human South, hidden hands)")
        self.mode_buttons.addButton(self.one_player_radio, 2)
        mode_layout.addWidget(self.one_player_radio)

        self.all_computer_radio = QRadioButton("All Computer (Auto-play)")
        self.mode_buttons.addButton(self.all_computer_radio, 3)
        mode_layout.addWidget(self.all_computer_radio)

        layout.addWidget(mode_group)

        # Individual player settings
        players_group = QGroupBox("Player Settings")
        players_layout = QGridLayout(players_group)

        headers = ["Seat", "Type", "Name", "Visible"]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setStyleSheet("font-weight: bold;")
            players_layout.addWidget(lbl, 0, col)

        self.player_widgets = {}

        for row, seat in enumerate([Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST], 1):
            player = self.players[seat]

            # Seat label
            seat_lbl = QLabel(f"{seat.to_char()} ({SEAT_NAMES[seat]})")
            players_layout.addWidget(seat_lbl, row, 0)

            # Type combo
            type_combo = QComboBox()
            type_combo.addItems(["Human", "Computer", "External"])
            type_combo.setCurrentIndex(
                {"human": 0, "computer": 1, "external": 2}[player.player_type.value]
            )
            type_combo.currentIndexChanged.connect(
                lambda idx, s=seat: self._on_type_changed(s, idx)
            )
            players_layout.addWidget(type_combo, row, 1)

            # Editable name field
            name_edit = QLineEdit(player.name)
            name_edit.setPlaceholderText(f"Player name for {SEAT_NAMES[seat]}")
            name_edit.setEnabled(player.player_type == PlayerType.HUMAN)
            players_layout.addWidget(name_edit, row, 2)

            # Visible checkbox
            visible_check = QCheckBox()
            visible_check.setChecked(player.visible or player.player_type == PlayerType.HUMAN)
            visible_check.toggled.connect(
                lambda checked, s=seat: self._on_visible_changed(s, checked)
            )
            players_layout.addWidget(visible_check, row, 3)

            self.player_widgets[seat] = {
                'type': type_combo,
                'name': name_edit,
                'visible': visible_check
            }

        layout.addWidget(players_group)

        # Connect mode changes
        self.mode_buttons.idToggled.connect(self._on_mode_changed)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_mode_changed(self, id: int, checked: bool):
        if not checked:
            return

        if id == 0:  # 4 Players (Human South)
            for seat in Seat:
                widgets = self.player_widgets[seat]
                if seat == Seat.SOUTH:
                    widgets['type'].setCurrentIndex(0)  # Human
                    widgets['visible'].setChecked(True)
                else:
                    widgets['type'].setCurrentIndex(1)  # Computer
                    widgets['visible'].setChecked(True)

        elif id == 1:  # Multi-Human
            # Don't change types — let user choose which seats are human
            pass

        elif id == 2:  # 1 Player
            for seat in Seat:
                widgets = self.player_widgets[seat]
                if seat == Seat.SOUTH:
                    widgets['type'].setCurrentIndex(0)  # Human
                    widgets['visible'].setChecked(True)
                else:
                    widgets['type'].setCurrentIndex(1)  # Computer
                    widgets['visible'].setChecked(False)

        elif id == 3:  # All Computer
            for seat in Seat:
                widgets = self.player_widgets[seat]
                widgets['type'].setCurrentIndex(1)  # Computer
                widgets['visible'].setChecked(True)

    def _on_type_changed(self, seat: Seat, idx: int):
        player_type = [PlayerType.HUMAN, PlayerType.COMPUTER, PlayerType.EXTERNAL][idx]
        self.players[seat].player_type = player_type

        # Enable/disable name editing for human players
        widgets = self.player_widgets[seat]
        widgets['name'].setEnabled(player_type == PlayerType.HUMAN)

        # Auto-set visibility for human
        if player_type == PlayerType.HUMAN:
            widgets['visible'].setChecked(True)
            # Auto-switch to Multi-Human mode if >1 human
            human_count = sum(1 for s in Seat
                              if self.player_widgets[s]['type'].currentIndex() == 0)
            if human_count > 1:
                self.multi_human_radio.setChecked(True)

    def _on_visible_changed(self, seat: Seat, checked: bool):
        self.players[seat].visible = checked

    def _on_ok(self):
        """Validate unique names for human players before accepting."""
        human_names = {}
        for seat in Seat:
            widgets = self.player_widgets[seat]
            if widgets['type'].currentIndex() == 0:  # Human
                name = widgets['name'].text().strip()
                if not name:
                    QMessageBox.warning(self, "Name Required",
                                        f"{SEAT_NAMES[seat]} is set to Human but has no name.")
                    widgets['name'].setFocus()
                    return
                if name in human_names.values():
                    QMessageBox.warning(self, "Duplicate Name",
                                        f"Each human player must have a unique name.\n"
                                        f"'{name}' is used by more than one player.")
                    widgets['name'].setFocus()
                    return
                human_names[seat] = name

        self.accept()

    def get_players(self) -> Dict[Seat, Player]:
        """Return the configured players"""
        for seat in Seat:
            widgets = self.player_widgets[seat]
            idx = widgets['type'].currentIndex()
            self.players[seat].player_type = [
                PlayerType.HUMAN, PlayerType.COMPUTER, PlayerType.EXTERNAL
            ][idx]
            self.players[seat].name = widgets['name'].text().strip() or self.players[seat].name
            self.players[seat].visible = widgets['visible'].isChecked()

        return self.players
