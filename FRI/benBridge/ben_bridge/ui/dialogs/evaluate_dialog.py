"""
Evaluate dialog - asks which player to query about which hand.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from .dialog_style import apply_dialog_style


class EvaluateDialog(QDialog):
    """Dialog to select who to ask and about whom to evaluate."""

    def __init__(self, parent=None, current_seat=None):
        super().__init__(parent)
        self.setWindowTitle("Evaluate")
        self.setMinimumWidth(400)
        apply_dialog_style(self)

        self.current_seat = current_seat
        self.ask_who = None
        self.about_whom = None
        self.own_hand = False

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

    def _on_ok(self):
        if self._get_selected():
            self.own_hand = False
            self.accept()

    def _on_own_hand(self):
        self.own_hand = True
        self.accept()


# Import QWidget for container
from PyQt6.QtWidgets import QWidget
