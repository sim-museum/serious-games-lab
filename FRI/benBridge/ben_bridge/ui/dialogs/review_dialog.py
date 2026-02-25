"""
Review Dialog - step through a completed hand to review bidding and play.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGroupBox, QGridLayout,
    QSplitter, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from .dialog_style import apply_dialog_style


class ReviewDialog(QDialog):
    """Dialog for reviewing a completed deal."""

    SUIT_SYMBOLS = {
        'S': '\u2660', 'H': '\u2665', 'D': '\u2666', 'C': '\u2663',
        'SPADES': '\u2660', 'HEARTS': '\u2665', 'DIAMONDS': '\u2666', 'CLUBS': '\u2663'
    }
    SUIT_COLORS = {
        'S': '#000000', 'H': '#cc0000', 'D': '#cc0000', 'C': '#000000',
        'SPADES': '#000000', 'HEARTS': '#cc0000', 'DIAMONDS': '#cc0000', 'CLUBS': '#000000'
    }

    def __init__(self, parent=None, board=None, auction=None, tricks=None, contract=None):
        super().__init__(parent)
        self.setWindowTitle("Review")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        apply_dialog_style(self)

        self.board = board
        self.auction = auction or []
        self.tricks = tricks or []
        self.contract = contract
        self.current_position = 0
        self.max_position = len(self.auction) + len(self.tricks) * 4

        self._setup_ui()
        self._update_display()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Navigation controls
        nav_frame = QFrame()
        nav_frame.setStyleSheet("""
            QFrame {
                background-color: #e8e8e8;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        nav_layout = QHBoxLayout(nav_frame)

        self.first_btn = QPushButton("|<")
        self.first_btn.setMaximumWidth(40)
        self.first_btn.clicked.connect(self._go_first)
        nav_layout.addWidget(self.first_btn)

        self.prev_btn = QPushButton("<")
        self.prev_btn.setMaximumWidth(40)
        self.prev_btn.clicked.connect(self._go_prev)
        nav_layout.addWidget(self.prev_btn)

        self.position_label = QLabel("Position: 0 / 0")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setMinimumWidth(150)
        nav_layout.addWidget(self.position_label)

        self.next_btn = QPushButton(">")
        self.next_btn.setMaximumWidth(40)
        self.next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self.next_btn)

        self.last_btn = QPushButton(">|")
        self.last_btn.setMaximumWidth(40)
        self.last_btn.clicked.connect(self._go_last)
        nav_layout.addWidget(self.last_btn)

        nav_layout.addStretch()

        self.analysis_btn = QPushButton("Analysis")
        self.analysis_btn.clicked.connect(self._on_analysis)
        nav_layout.addWidget(self.analysis_btn)

        self.actions_btn = QPushButton("Actions")
        self.actions_btn.clicked.connect(self._on_actions)
        nav_layout.addWidget(self.actions_btn)

        layout.addWidget(nav_frame)

        # Main content area
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Auction display
        auction_group = QGroupBox("Auction")
        auction_layout = QVBoxLayout(auction_group)
        self.auction_display = QLabel()
        self.auction_display.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.auction_display.setWordWrap(True)
        self.auction_display.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                padding: 10px;
                font-family: monospace;
            }
        """)
        auction_layout.addWidget(self.auction_display)
        content_splitter.addWidget(auction_group)

        # Play display
        play_group = QGroupBox("Play")
        play_layout = QVBoxLayout(play_group)
        self.play_display = QLabel()
        self.play_display.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.play_display.setWordWrap(True)
        self.play_display.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                padding: 10px;
                font-family: monospace;
            }
        """)
        play_layout.addWidget(self.play_display)
        content_splitter.addWidget(play_group)

        layout.addWidget(content_splitter)

        # Current action display
        action_frame = QFrame()
        action_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        action_layout = QHBoxLayout(action_frame)
        action_layout.addWidget(QLabel("Current action:"))
        self.action_label = QLabel("<i>Start of deal</i>")
        self.action_label.setStyleSheet("font-weight: bold;")
        action_layout.addWidget(self.action_label)
        action_layout.addStretch()
        layout.addWidget(action_frame)

        # Result display
        if self.contract:
            result_text = f"Contract: {self.contract}"
            result_label = QLabel(f"<b>{result_text}</b>")
            result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(result_label)

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

    def _update_display(self):
        """Update the display for current position."""
        self.position_label.setText(f"Position: {self.current_position} / {self.max_position}")

        # Update navigation buttons
        self.first_btn.setEnabled(self.current_position > 0)
        self.prev_btn.setEnabled(self.current_position > 0)
        self.next_btn.setEnabled(self.current_position < self.max_position)
        self.last_btn.setEnabled(self.current_position < self.max_position)

        # Update auction display
        auction_html = self._format_auction()
        self.auction_display.setText(auction_html)

        # Update play display
        play_html = self._format_play()
        self.play_display.setText(play_html)

        # Update current action
        self._update_action_label()

    def _format_auction(self):
        """Format the auction for display."""
        if not self.auction:
            return "<i>No auction</i>"

        # Determine dealer
        dealer_offset = 0
        if self.board and hasattr(self.board, 'dealer'):
            dealer_offset = self.board.dealer.value

        html = "<table style='border-collapse: collapse;'>"
        html += "<tr><th>N</th><th>E</th><th>S</th><th>W</th></tr>"

        # Add dashes for positions before dealer
        html += "<tr>"
        for i in range(4):
            if i < dealer_offset:
                html += "<td style='padding: 2px 8px; text-align: center;'>-</td>"
            else:
                break

        # Add bids
        bids_shown = 0
        for i, bid in enumerate(self.auction):
            pos_in_row = (dealer_offset + i) % 4
            if pos_in_row == 0 and i > 0:
                html += "</tr><tr>"

            # Highlight current bid
            bid_num = i + 1
            style = "padding: 2px 8px; text-align: center;"
            if bid_num <= self.current_position:
                bid_str = self._format_bid(bid)
            else:
                bid_str = "?"
                style += " color: #808080;"

            html += f"<td style='{style}'>{bid_str}</td>"

        html += "</tr></table>"
        return html

    def _format_bid(self, bid):
        """Format a single bid."""
        if hasattr(bid, 'is_pass') and bid.is_pass:
            return "Pass"
        elif hasattr(bid, 'is_double') and bid.is_double:
            return "X"
        elif hasattr(bid, 'is_redouble') and bid.is_redouble:
            return "XX"
        elif hasattr(bid, 'level') and hasattr(bid, 'suit'):
            level = bid.level
            if bid.suit:
                suit_name = bid.suit.name.upper()
                symbol = self.SUIT_SYMBOLS.get(suit_name, suit_name[0])
                color = self.SUIT_COLORS.get(suit_name, '#000000')
                return f"{level}<span style='color:{color}'>{symbol}</span>"
            return f"{level}NT"
        return str(bid)

    def _format_play(self):
        """Format the play for display."""
        if not self.tricks:
            return "<i>No play</i>"

        html = "<table style='border-collapse: collapse;'>"
        html += "<tr><th>#</th><th>N</th><th>E</th><th>S</th><th>W</th></tr>"

        cards_in_auction = len(self.auction)
        cards_shown = max(0, self.current_position - cards_in_auction)

        card_count = 0
        for trick_num, trick in enumerate(self.tricks):
            html += f"<tr><td style='padding: 2px 4px;'><b>{trick_num + 1}</b></td>"

            cards = trick.get('cards', {})
            for seat in ['N', 'E', 'S', 'W']:
                card = cards.get(seat, '')
                style = "padding: 2px 8px; text-align: center;"

                if card_count < cards_shown:
                    card_str = self._format_card(card) if card else "-"
                    # Highlight winner
                    winner = trick.get('winner', '')
                    if seat == winner:
                        style += " font-weight: bold; background-color: #e8e8ff;"
                else:
                    card_str = "?"
                    style += " color: #808080;"

                html += f"<td style='{style}'>{card_str}</td>"
                if card:
                    card_count += 1

            html += "</tr>"

        html += "</table>"
        return html

    def _format_card(self, card):
        """Format a single card."""
        if hasattr(card, 'suit') and hasattr(card, 'rank'):
            suit_name = card.suit.name.upper()
            symbol = self.SUIT_SYMBOLS.get(suit_name, suit_name[0])
            color = self.SUIT_COLORS.get(suit_name, '#000000')
            rank_char = self._rank_to_char(card.rank)
            return f"<span style='color:{color}'>{symbol}</span>{rank_char}"
        return str(card) if card else "-"

    def _rank_to_char(self, rank):
        """Convert rank to display character."""
        if hasattr(rank, 'value'):
            rank_val = rank.value
        else:
            rank_val = rank
        rank_chars = {12: 'A', 11: 'K', 10: 'Q', 9: 'J', 8: 'T'}
        return rank_chars.get(rank_val, str(rank_val + 2))

    def _update_action_label(self):
        """Update the current action label."""
        if self.current_position == 0:
            self.action_label.setText("<i>Start of deal</i>")
        elif self.current_position <= len(self.auction):
            bid_idx = self.current_position - 1
            if bid_idx < len(self.auction):
                bid = self.auction[bid_idx]
                bid_str = self._format_bid(bid)
                self.action_label.setText(f"Bid: {bid_str}")
        else:
            card_pos = self.current_position - len(self.auction) - 1
            trick_num = card_pos // 4
            card_in_trick = card_pos % 4
            self.action_label.setText(f"Trick {trick_num + 1}, card {card_in_trick + 1}")

    def _go_first(self):
        self.current_position = 0
        self._update_display()

    def _go_prev(self):
        if self.current_position > 0:
            self.current_position -= 1
            self._update_display()

    def _go_next(self):
        if self.current_position < self.max_position:
            self.current_position += 1
            self._update_display()

    def _go_last(self):
        self.current_position = self.max_position
        self._update_display()

    def _on_analysis(self):
        """Start post-mortem analysis."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Analysis",
            "Post-mortem analysis would evaluate all human player actions.\n"
            "This feature is not yet fully implemented."
        )

    def _on_actions(self):
        """Show/edit prepared actions."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Actions",
            "Prepared actions allow you to specify correct bids/plays.\n"
            "This feature is not yet fully implemented."
        )
