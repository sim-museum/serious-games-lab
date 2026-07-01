"""
Evaluate dialog - asks which player to query about which hand.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt
from .dialog_style import apply_dialog_style


class EvaluateDialog(QDialog):
    """Dialog to select who to ask and about whom to evaluate."""

    def __init__(self, parent=None, current_seat=None):
        super().__init__(parent)
        self.setWindowTitle("Evaluate")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        self.resize(600, 400)
        apply_dialog_style(self)
        self.setStyleSheet(self.styleSheet() + """
            QLabel { font-size: 15px; }
            QPushButton { font-size: 14px; padding: 8px 14px; }
            QRadioButton { font-size: 14px; }
        """)

        self.current_seat = current_seat
        self.ask_who = None
        self.about_whom = None
        self.own_hand = False
        # Q-Plus result-type options (card play).
        self.want_conventional = False
        self.want_tricks_hidden = False
        self.want_tricks_open = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Create the grid for seat selection
        grid_frame = QFrame()
        grid_frame.setStyleSheet("""
            QFrame {
                background-color: #e8e8e8;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setSpacing(8)
        grid_layout.setContentsMargins(10, 10, 10, 10)

        # Headers
        seats = ['North', 'East', 'South', 'West']
        grid_layout.addWidget(QLabel("ask who:"), 0, 0)

        for col, seat in enumerate(seats):
            lbl = QLabel(f"<b>{seat}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid_layout.addWidget(lbl, 0, col + 1)

        # "about:" row with radio buttons
        grid_layout.addWidget(QLabel("about:"), 1, 0)

        # Create button groups for each column
        self.ask_groups = []
        self.about_groups = {}

        for col, seat in enumerate(seats):
            group = QButtonGroup(self)
            self.ask_groups.append(group)

            vbox = QVBoxLayout()
            for row_seat in seats:
                radio = QRadioButton(row_seat)
                radio.setProperty("ask_seat", seat)
                radio.setProperty("about_seat", row_seat)
                group.addButton(radio)
                vbox.addWidget(radio)

            container = QWidget()
            container.setLayout(vbox)
            grid_layout.addWidget(container, 1, col + 1)

            # Store mapping
            self.about_groups[seat] = group

        layout.addWidget(grid_frame)

        # Q-Plus result-type options (used during card play). Leaving all
        # unchecked falls back to biq's hand point-count evaluation.
        result_group = QGroupBox("During play, show (instead of point count)")
        result_layout = QVBoxLayout(result_group)
        self.chk_conventional = QCheckBox("Conventional meaning of cards")
        self.chk_tricks_hidden = QCheckBox(
            "Expected tricks (hidden hands — legal knowledge)")
        self.chk_tricks_open = QCheckBox(
            "Expected tricks (open hands — double dummy)")
        for c in (self.chk_conventional, self.chk_tricks_hidden,
                  self.chk_tricks_open):
            result_layout.addWidget(c)
        layout.addWidget(result_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.ok_btn = QPushButton("Ok")
        self.ok_btn.clicked.connect(self._on_ok)
        self.ok_btn.setMinimumWidth(80)
        button_layout.addWidget(self.ok_btn)

        self.own_hand_btn = QPushButton("Own Hand")
        self.own_hand_btn.clicked.connect(self._on_own_hand)
        self.own_hand_btn.setMinimumWidth(80)
        button_layout.addWidget(self.own_hand_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(80)
        button_layout.addWidget(self.cancel_btn)

        self.help_btn = QPushButton("Help")
        self.help_btn.setMinimumWidth(80)
        button_layout.addWidget(self.help_btn)

        layout.addLayout(button_layout)

    def _get_selected(self):
        """Get the selected ask_who and about_whom."""
        for seat, group in self.about_groups.items():
            checked = group.checkedButton()
            if checked:
                self.ask_who = checked.property("ask_seat")
                self.about_whom = checked.property("about_seat")
                return True
        return False

    def _capture_result_modes(self):
        self.want_conventional = self.chk_conventional.isChecked()
        self.want_tricks_hidden = self.chk_tricks_hidden.isChecked()
        self.want_tricks_open = self.chk_tricks_open.isChecked()

    def _any_result_mode(self):
        return (self.chk_conventional.isChecked()
                or self.chk_tricks_hidden.isChecked()
                or self.chk_tricks_open.isChecked())

    def _on_ok(self):
        self._capture_result_modes()
        # A result-mode checkbox alone (no seat picked) is a valid request.
        if self._get_selected() or self._any_result_mode():
            self.own_hand = False
            self.accept()

    def _on_own_hand(self):
        self._capture_result_modes()
        self.own_hand = True
        self.accept()


# Import QWidget for container
from PyQt6.QtWidgets import QWidget
