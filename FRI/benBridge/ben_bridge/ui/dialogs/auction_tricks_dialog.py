"""
Auction and Played Tricks Dialog - shows the complete auction record
and all played tricks.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from .dialog_style import apply_dialog_style
from ..styles import get_suit_color


class AuctionTricksDialog(QDialog):
    """Dialog showing complete auction and played tricks record."""

    SUIT_SYMBOLS = {
        'S': '\u2660', 'H': '\u2665', 'D': '\u2666', 'C': '\u2663',
        'SPADES': '\u2660', 'HEARTS': '\u2665', 'DIAMONDS': '\u2666', 'CLUBS': '\u2663',
        'NT': 'NT', 'NOTRUMP': 'NT'
    }

    # Font size for suit symbols (larger for visibility)
    SYMBOL_FONT_SIZE = 24

    def _get_suit_color(self, suit_key: str) -> str:
        """Get suit color based on current preference (4-color or legacy)."""
        suit_map = {
            'S': 'spades', 'H': 'hearts', 'D': 'diamonds', 'C': 'clubs',
            'SPADES': 'spades', 'HEARTS': 'hearts', 'DIAMONDS': 'diamonds', 'CLUBS': 'clubs',
            'NT': 'spades', 'NOTRUMP': 'spades'  # NT uses black
        }
        suit_name = suit_map.get(suit_key.upper(), 'spades')
        return get_suit_color(suit_name)

    def __init__(self, parent=None, board=None, tricks=None):
        super().__init__(parent)
        self.setWindowTitle("Record (current)")
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)
        self.resize(700, 650)
        apply_dialog_style(self)

        # Detach from the parent window: Qt.Dialog is a "tool" window
        # that some window managers (Mutter / KWin) keep glued to the
        # parent's screen, so it can't be dragged onto a second monitor.
        # Promote to a real top-level Qt.Window with min/max/close
        # buttons; the caller is expected to use show() instead of
        # exec() so the user can interact with the main window in
        # parallel. Qt.WA_DeleteOnClose makes sure each open/close
        # cycle still cleans up properly.
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.board = board
        self.tricks = tricks or []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Auction table
        auction_frame = QFrame()
        auction_frame.setStyleSheet("""
            QFrame {
                background-color: #e8e8f0;
                border: 1px solid #a0a0a0;
                border-radius: 4px;
            }
        """)
        auction_layout = QVBoxLayout(auction_frame)

        # Header row
        header_layout = QHBoxLayout()
        fs = self.SYMBOL_FONT_SIZE
        for seat in ['N', 'E', 'S', 'W']:
            lbl = QLabel(f'<b style="font-size:{fs}px">{seat}</b>')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumWidth(70)
            header_layout.addWidget(lbl)
        auction_layout.addLayout(header_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #808080;")
        auction_layout.addWidget(sep)

        # Auction bids
        self.auction_area = QWidget()
        self.auction_grid = QGridLayout(self.auction_area)
        self.auction_grid.setSpacing(4)
        self._populate_auction()
        auction_layout.addWidget(self.auction_area)

        layout.addWidget(auction_frame)

        # Tricks section (if any tricks played)
        if self.tricks:
            tricks_frame = QFrame()
            tricks_frame.setStyleSheet("""
                QFrame {
                    background-color: #f0f0e8;
                    border: 1px solid #a0a0a0;
                    border-radius: 4px;
                }
            """)
            tricks_layout = QVBoxLayout(tricks_frame)

            # Tricks header
            tricks_header = QHBoxLayout()
            tricks_header.addWidget(QLabel(""))  # Leader column
            for seat in ['N', 'E', 'S', 'W']:
                lbl = QLabel(f'<b style="font-size:{self.SYMBOL_FONT_SIZE}px">{seat}</b>')
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setMinimumWidth(60)
                tricks_header.addWidget(lbl)
            tricks_layout.addLayout(tricks_header)

            # Tricks grid
            self.tricks_area = QWidget()
            self.tricks_grid = QGridLayout(self.tricks_area)
            self.tricks_grid.setSpacing(4)
            self._populate_tricks()
            tricks_layout.addWidget(self.tricks_area)

            layout.addWidget(tricks_frame)

        # Outstanding cards by suit — useful for spotting "I hold all
        # the remaining diamonds" situations at a glance.
        if self.board is not None:
            remaining_frame = self._build_remaining_frame()
            if remaining_frame is not None:
                layout.addWidget(remaining_frame)

        layout.addStretch()

    def _build_remaining_frame(self):
        """Build the 'Cards still out' frame, one row per suit listing
        ranks not yet played (in any completed trick or the current trick).
        Returns None if the board can't supply the data.
        """
        try:
            remaining = self.board.remaining_cards_by_suit()
        except AttributeError:
            return None
        except Exception:
            return None
        if not remaining:
            return None

        from ben_backend.models import Suit
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #f0e8e8; border: 1px solid #a0a0a0;"
            " border-radius: 4px; }"
        )
        v = QVBoxLayout(frame)
        fs = self.SYMBOL_FONT_SIZE
        title = QLabel(
            f'<b style="font-size:{fs}px">Cards still out</b>'
        )
        v.addWidget(title)

        suit_order = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
        suit_names_full = {
            Suit.SPADES: 'SPADES', Suit.HEARTS: 'HEARTS',
            Suit.DIAMONDS: 'DIAMONDS', Suit.CLUBS: 'CLUBS',
        }
        for suit in suit_order:
            ranks = remaining.get(suit, [])
            symbol = self.SUIT_SYMBOLS.get(suit_names_full[suit], '?')
            color = self._get_suit_color(suit_names_full[suit])
            # Rank.to_char() already produces 'A','K','Q','J','T','9'…'2'
            # in declaration order, so the joined string reads high → low.
            rank_chars = ' '.join(r.to_char() for r in ranks) if ranks else '—'
            row = QLabel(
                f'<span style="color:{color};font-size:{fs}px">{symbol}</span>'
                f'<span style="font-size:{fs}px">  {rank_chars}'
                f'   <span style="color:#666">({len(ranks)})</span></span>'
            )
            v.addWidget(row)
        return frame

    def _populate_auction(self):
        """Fill in the auction bids."""
        if not self.board or not self.board.auction:
            return

        # Determine dealer position
        dealer = self.board.dealer
        dealer_offset = dealer.value  # N=0, E=1, S=2, W=3

        # Fill in the auction
        row = 0
        col = dealer_offset

        for bid in self.board.auction:
            bid_text = self._format_bid(bid)
            lbl = QLabel(bid_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.auction_grid.addWidget(lbl, row, col)

            col += 1
            if col >= 4:
                col = 0
                row += 1

        # Add dashes for positions before dealer in first row
        fs = self.SYMBOL_FONT_SIZE
        for i in range(dealer_offset):
            lbl = QLabel(f'<span style="font-size:{fs}px">-</span>')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.auction_grid.addWidget(lbl, 0, i)

        # Add "?" for current bidder if auction not complete
        if not self._is_auction_complete():
            lbl = QLabel(f'<span style="font-size:{fs}px">?</span>')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.auction_grid.addWidget(lbl, row, col)

    def _format_bid(self, bid):
        """Format a bid for display with colored suit symbol."""
        fs = self.SYMBOL_FONT_SIZE
        if bid.is_pass:
            return f'<span style="font-size:{fs}px">-</span>'
        elif bid.is_double:
            return f'<span style="font-size:{fs}px">X</span>'
        elif bid.is_redouble:
            return f'<span style="font-size:{fs}px">XX</span>'
        else:
            level = bid.level
            suit = bid.suit
            if suit:
                suit_name = suit.name.upper()
                symbol = self.SUIT_SYMBOLS.get(suit_name, suit_name[0])
                color = self._get_suit_color(suit_name)
                return f'<span style="font-size:{fs}px">{level}</span><span style="color:{color};font-size:{fs}px">{symbol}</span>'
            else:
                return f'<span style="font-size:{fs}px">{level}NT</span>'

    def _is_auction_complete(self):
        """Check if the auction is complete (3 consecutive passes after a bid)."""
        if not self.board or not self.board.auction:
            return False

        auction = self.board.auction
        if len(auction) < 4:
            return False

        # Check for 3 consecutive passes at end
        pass_count = 0
        has_bid = False
        for bid in auction:
            if not bid.is_pass:
                has_bid = True
                pass_count = 0
            else:
                pass_count += 1

        return has_bid and pass_count >= 3

    def _populate_tricks(self):
        """Fill in the played tricks."""
        if not self.tricks:
            return

        fs = self.SYMBOL_FONT_SIZE
        for trick_num, trick in enumerate(self.tricks):
            # Leader indicator
            leader = trick.get('leader', '')
            leader_lbl = QLabel(f'<b style="font-size:{fs}px">{leader}</b>')
            self.tricks_grid.addWidget(leader_lbl, trick_num, 0)

            # Cards played (in order N, E, S, W)
            cards = trick.get('cards', {})
            for col, seat in enumerate(['N', 'E', 'S', 'W']):
                card = cards.get(seat, '')
                if card:
                    card_text = self._format_card(card)
                    # Highlight winning card
                    winner = trick.get('winner', '')
                    if seat == winner:
                        card_text = f"<b>{card_text}</b>"
                else:
                    card_text = f'<span style="font-size:{fs}px">?</span>'
                lbl = QLabel(card_text)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tricks_grid.addWidget(lbl, trick_num, col + 1)

    def _format_card(self, card):
        """Format a card for display."""
        fs = self.SYMBOL_FONT_SIZE
        if hasattr(card, 'suit') and hasattr(card, 'rank'):
            suit = card.suit
            rank = card.rank

            suit_name = suit.name.upper()
            symbol = self.SUIT_SYMBOLS.get(suit_name, suit_name[0])
            color = self._get_suit_color(suit_name)

            rank_char = self._rank_to_char(rank)
            return f'<span style="color:{color};font-size:{fs}px">{symbol}</span><span style="font-size:{fs}px">{rank_char}</span>'
        elif isinstance(card, str):
            # String format like "SA" or "H10"
            if len(card) >= 2:
                suit = card[0].upper()
                rank = card[1:]
                symbol = self.SUIT_SYMBOLS.get(suit, suit)
                color = self._get_suit_color(suit)
                return f'<span style="color:{color};font-size:{fs}px">{symbol}</span><span style="font-size:{fs}px">{rank}</span>'
        return f'<span style="font-size:{fs}px">{str(card)}</span>'

    def _rank_to_char(self, rank):
        """Convert rank to display character.

        The model's Rank IntEnum is ace-high-low (ACE=0, KING=1, …,
        TWO=12) so its value is NOT the printed rank. Earlier this
        method assumed the opposite mapping (12=A) which made every
        card render with the wrong rank: an Ace came out as "2", a
        Five came out as "J", and the Cards-still-out list ended up
        inconsistent with the played-tricks display. Just delegate
        to Rank.to_char() which already uses the canonical
        'AKQJT98765432' table.
        """
        if hasattr(rank, 'to_char'):
            try:
                return rank.to_char()
            except Exception:
                pass
        # Fall-through for plain ints / strings — try the model's
        # Rank class so the same canonical table is used.
        try:
            from ben_backend.models import Rank
            return Rank(int(rank)).to_char()
        except Exception:
            return str(rank)
