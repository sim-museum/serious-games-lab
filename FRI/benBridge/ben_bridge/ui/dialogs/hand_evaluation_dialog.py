"""
Hand Evaluation Dialog - shows detailed hand evaluation including point counts,
suit lengths, controls, and stoppers.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QCheckBox, QComboBox, QGroupBox,
    QFrame, QTextEdit, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from .dialog_style import apply_dialog_style


class HandEvaluationDialog(QDialog):
    """Dialog showing detailed evaluation of a hand."""

    SUIT_SYMBOLS = {'S': '\u2660', 'H': '\u2665', 'D': '\u2666', 'C': '\u2663'}
    SUIT_COLORS = {'S': '#000000', 'H': '#cc0000', 'D': '#cc0000', 'C': '#000000'}

    def __init__(self, parent=None, seat=None, hand=None, bid_round=1, board=None):
        super().__init__(parent)
        self.seat = seat
        self.hand = hand
        self.bid_round = bid_round
        self.board = board

        seat_name = seat.name.capitalize() if seat else "Player"
        self.setWindowTitle(f"Bidround {bid_round}: {seat_name}'s evaluation of {seat_name}'s hand")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        apply_dialog_style(self)

        self._setup_ui()
        self._populate_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Top row: bid, artificial, forcing, name
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("bid:"))
        self.bid_edit = QLineEdit()
        self.bid_edit.setMaximumWidth(80)
        self.bid_edit.setReadOnly(True)
        top_row.addWidget(self.bid_edit)

        self.artificial_cb = QCheckBox("artif.")
        self.artificial_cb.setEnabled(False)
        top_row.addWidget(self.artificial_cb)

        self.forcing_cb = QCheckBox("forc.")
        self.forcing_cb.setEnabled(False)
        top_row.addWidget(self.forcing_cb)

        top_row.addWidget(QLabel("name:"))
        self.name_combo = QComboBox()
        self.name_combo.setMinimumWidth(150)
        self.name_combo.setEnabled(False)
        top_row.addWidget(self.name_combo)
        top_row.addStretch()

        layout.addLayout(top_row)

        # Points section
        points_frame = QFrame()
        points_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
            }
        """)
        points_layout = QGridLayout(points_frame)
        points_layout.setSpacing(6)

        # Trump selector
        points_layout.addWidget(QLabel("trump"), 0, 0)
        self.trump_combo = QComboBox()
        self.trump_combo.addItems(['NT', 'S', 'H', 'D', 'C'])
        self.trump_combo.setMaximumWidth(60)
        points_layout.addWidget(self.trump_combo, 1, 0)

        # HP, LP, TP rows
        headers = ['', 'min', 'exp.', 'max']
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            points_layout.addWidget(lbl, 0, col + 1)

        point_types = [
            ('HP [0.0 - 40.0]:', 'hp'),
            ('LP [0.0 - 40.0]:', 'lp'),
            ('TP [0.0 - 40.0]:', 'tp'),
        ]

        self.point_edits = {}
        for row, (label, key) in enumerate(point_types, 1):
            points_layout.addWidget(QLabel(label), row, 1)
            for col, field in enumerate(['min', 'exp', 'max'], 2):
                edit = QLineEdit()
                edit.setMaximumWidth(50)
                edit.setReadOnly(True)
                edit.setAlignment(Qt.AlignmentFlag.AlignRight)
                self.point_edits[f"{key}_{field}"] = edit
                points_layout.addWidget(edit, row, col)

        # Aces and Kings row
        row = 4
        points_layout.addWidget(QLabel("# aces +"), row, 1)
        self.aces_plus = QLineEdit()
        self.aces_plus.setMaximumWidth(40)
        self.aces_plus.setReadOnly(True)
        points_layout.addWidget(self.aces_plus, row, 2)
        points_layout.addWidget(QLabel("-"), row, 3)
        self.aces_minus = QLineEdit()
        self.aces_minus.setMaximumWidth(40)
        self.aces_minus.setReadOnly(True)
        points_layout.addWidget(self.aces_minus, row, 4)
        points_layout.addWidget(QLabel("="), row, 5)
        self.aces_result = QLineEdit()
        self.aces_result.setMaximumWidth(40)
        self.aces_result.setReadOnly(True)
        points_layout.addWidget(self.aces_result, row, 6)
        points_layout.addWidget(QLabel("| exp. [0.0 - 4.0]:"), row, 7)
        self.aces_exp = QLineEdit()
        self.aces_exp.setMaximumWidth(40)
        self.aces_exp.setReadOnly(True)
        points_layout.addWidget(self.aces_exp, row, 8)

        row = 5
        points_layout.addWidget(QLabel("# kings +"), row, 1)
        self.kings_plus = QLineEdit()
        self.kings_plus.setMaximumWidth(40)
        self.kings_plus.setReadOnly(True)
        points_layout.addWidget(self.kings_plus, row, 2)
        points_layout.addWidget(QLabel("-"), row, 3)
        self.kings_minus = QLineEdit()
        self.kings_minus.setMaximumWidth(40)
        self.kings_minus.setReadOnly(True)
        points_layout.addWidget(self.kings_minus, row, 4)
        points_layout.addWidget(QLabel("="), row, 5)
        self.kings_result = QLineEdit()
        self.kings_result.setMaximumWidth(40)
        self.kings_result.setReadOnly(True)
        points_layout.addWidget(self.kings_result, row, 6)
        points_layout.addWidget(QLabel("| exp. [0.0 - 4.0]:"), row, 7)
        self.kings_exp = QLineEdit()
        self.kings_exp.setMaximumWidth(40)
        self.kings_exp.setReadOnly(True)
        points_layout.addWidget(self.kings_exp, row, 8)

        row = 6
        points_layout.addWidget(QLabel("aces[2] + kings[1] = [0 - 12]"), row, 1, 1, 4)
        self.controls_total = QLineEdit()
        self.controls_total.setMaximumWidth(40)
        self.controls_total.setReadOnly(True)
        points_layout.addWidget(self.controls_total, row, 5)
        self.any_void_cb = QCheckBox("any void")
        self.any_void_cb.setEnabled(False)
        points_layout.addWidget(self.any_void_cb, row, 6)
        self.any_single_cb = QCheckBox("any single")
        self.any_single_cb.setEnabled(False)
        points_layout.addWidget(self.any_single_cb, row, 7)

        layout.addWidget(points_frame)

        # Suit rows
        suits_frame = QFrame()
        suits_frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
            }
        """)
        suits_layout = QVBoxLayout(suits_frame)

        self.suit_widgets = {}
        for suit in ['S', 'H', 'D', 'C']:
            suit_row = self._create_suit_row(suit)
            suits_layout.addLayout(suit_row)

        layout.addWidget(suits_frame)

        # Dependencies text area
        dep_layout = QHBoxLayout()
        dep_layout.addWidget(QLabel("dependencies"))
        self.dependencies_edit = QTextEdit()
        self.dependencies_edit.setMaximumHeight(80)
        self.dependencies_edit.setReadOnly(True)
        dep_layout.addWidget(self.dependencies_edit)
        layout.addLayout(dep_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setMinimumWidth(80)
        button_layout.addWidget(self.close_btn)

        button_layout.addStretch()

        self.help_btn = QPushButton("Help")
        self.help_btn.setMinimumWidth(80)
        button_layout.addWidget(self.help_btn)

        layout.addLayout(button_layout)

    def _create_suit_row(self, suit):
        """Create a row for suit evaluation."""
        row_layout = QHBoxLayout()

        # Suit symbol
        symbol = self.SUIT_SYMBOLS[suit]
        color = self.SUIT_COLORS[suit]
        suit_label = QLabel(f'<span style="color:{color}; font-size:16px;">{symbol}</span>')
        suit_label.setMinimumWidth(20)
        row_layout.addWidget(suit_label)

        widgets = {}

        # Length fields
        row_layout.addWidget(QLabel("length [0.0 - 13.0]: min"))
        widgets['len_min'] = QLineEdit()
        widgets['len_min'].setMaximumWidth(40)
        widgets['len_min'].setReadOnly(True)
        row_layout.addWidget(widgets['len_min'])

        row_layout.addWidget(QLabel("exp."))
        widgets['len_exp'] = QLineEdit()
        widgets['len_exp'].setMaximumWidth(40)
        widgets['len_exp'].setReadOnly(True)
        row_layout.addWidget(widgets['len_exp'])

        row_layout.addWidget(QLabel("max"))
        widgets['len_max'] = QLineEdit()
        widgets['len_max'].setMaximumWidth(40)
        widgets['len_max'].setReadOnly(True)
        row_layout.addWidget(widgets['len_max'])

        row_layout.addWidget(QLabel("exp. HP [0.0 - 10.0]:"))
        widgets['hp_exp'] = QLineEdit()
        widgets['hp_exp'].setMaximumWidth(40)
        widgets['hp_exp'].setReadOnly(True)
        row_layout.addWidget(widgets['hp_exp'])

        # Second line info (percentages)
        row_layout.addWidget(QLabel("% [0-100]: A"))
        widgets['pct_a'] = QLineEdit()
        widgets['pct_a'].setMaximumWidth(35)
        widgets['pct_a'].setReadOnly(True)
        row_layout.addWidget(widgets['pct_a'])

        row_layout.addWidget(QLabel("K"))
        widgets['pct_k'] = QLineEdit()
        widgets['pct_k'].setMaximumWidth(35)
        widgets['pct_k'].setReadOnly(True)
        row_layout.addWidget(widgets['pct_k'])

        row_layout.addWidget(QLabel("Q"))
        widgets['pct_q'] = QLineEdit()
        widgets['pct_q'].setMaximumWidth(35)
        widgets['pct_q'].setReadOnly(True)
        row_layout.addWidget(widgets['pct_q'])

        # Control dropdown
        row_layout.addWidget(QLabel("control"))
        widgets['control'] = QComboBox()
        widgets['control'].addItems(['--', '1st', '2nd'])
        widgets['control'].setMaximumWidth(60)
        widgets['control'].setEnabled(False)
        row_layout.addWidget(widgets['control'])

        # Stopper dropdown
        row_layout.addWidget(QLabel("stopper"))
        widgets['stopper'] = QComboBox()
        widgets['stopper'].addItems(['--', 'yes', 'no', 'half'])
        widgets['stopper'].setMaximumWidth(60)
        widgets['stopper'].setEnabled(False)
        row_layout.addWidget(widgets['stopper'])

        row_layout.addStretch()

        self.suit_widgets[suit] = widgets
        return row_layout

    def _populate_values(self):
        """Populate fields with actual hand evaluation."""
        if not self.hand:
            return

        # Calculate HCP
        hcp = self.hand.hcp()
        self.point_edits['hp_exp'].setText(f"{hcp:.1f}")
        self.point_edits['hp_min'].setText("")
        self.point_edits['hp_max'].setText("")

        # Count aces and kings
        aces = sum(1 for c in self.hand.cards if c.rank.value == 12)  # Ace
        kings = sum(1 for c in self.hand.cards if c.rank.value == 11)  # King

        self.aces_exp.setText(str(aces))
        self.aces_result.setText(str(aces))
        self.kings_exp.setText(str(kings))
        self.kings_result.setText(str(kings))
        self.controls_total.setText(str(aces * 2 + kings))

        # Check for voids and singletons
        has_void = False
        has_singleton = False

        from ben_backend.models import Suit
        for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]:
            suit_cards = self.hand.get_suit_cards(suit)
            length = len(suit_cards) if suit_cards else 0

            if length == 0:
                has_void = True
            elif length == 1:
                has_singleton = True

            # Get suit key
            suit_key = suit.name[0]  # S, H, D, C
            widgets = self.suit_widgets.get(suit_key)
            if widgets:
                widgets['len_exp'].setText(str(length))

                # Calculate suit HCP
                suit_hcp = sum(max(0, c.rank.value - 9) for c in (suit_cards or []))
                widgets['hp_exp'].setText(f"{suit_hcp:.1f}")

                # Check for honors
                has_ace = any(c.rank.value == 12 for c in (suit_cards or []))
                has_king = any(c.rank.value == 11 for c in (suit_cards or []))
                has_queen = any(c.rank.value == 10 for c in (suit_cards or []))

                widgets['pct_a'].setText("100" if has_ace else "0")
                widgets['pct_k'].setText("100" if has_king else "0")
                widgets['pct_q'].setText("100" if has_queen else "0")

                # Set control
                if has_ace:
                    widgets['control'].setCurrentText('1st')
                elif has_king:
                    widgets['control'].setCurrentText('2nd')
                else:
                    widgets['control'].setCurrentText('--')

                # Set stopper (simplified)
                if has_ace or (has_king and length >= 2) or (has_queen and length >= 3):
                    widgets['stopper'].setCurrentText('yes')
                elif has_king or (has_queen and length >= 2):
                    widgets['stopper'].setCurrentText('half')
                else:
                    widgets['stopper'].setCurrentText('no')

        self.any_void_cb.setChecked(has_void)
        self.any_single_cb.setChecked(has_singleton)
