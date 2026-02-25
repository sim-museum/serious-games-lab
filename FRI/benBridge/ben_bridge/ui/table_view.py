"""
TableView - Visual representation of the bridge table.
Optimized for 1920x1080 screens with large cards and easy-to-read layout.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QRect, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QBrush, QPen, QPolygon, QFontMetrics

from ben_backend.models import (
    BoardState, Card, Hand, Seat, Suit, Trick, Vulnerability, Contract, Rank
)
from typing import Optional, List, Dict


# BEN Bridge color scheme
COLORS = {
    'background': '#1a3a5c',
    'table_green': '#2d9c40',
    'panel_teal': '#4a7c8a',
    'card_back': '#1a2a4a',
    'card_border': '#c0a050',
    'card_face': '#ffffff',
    'text_white': '#ffffff',
    'text_black': '#000000',
    'vuln_red': '#cc0000',
    'highlight': '#ffff88',
    'button_bg': '#6090a0',
    'button_text': '#ffffff',
    'selectable_border': '#ff0000',
}

# Card dimensions - LARGE for 1080p
CARD_WIDTH = 120
CARD_HEIGHT = 170
CARD_OVERLAP = 55  # How much cards overlap (shows ~65px per card)
SUIT_GAP = 60  # Extra gap between suits in face-up hands - very visible separation


class CardWidget(QWidget):
    """Large playing card widget with proper face card graphics"""

    card_clicked = pyqtSignal(object)

    SUIT_SYMBOLS = {
        Suit.SPADES: '♠',
        Suit.HEARTS: '♥',
        Suit.DIAMONDS: '♦',
        Suit.CLUBS: '♣',
    }

    @staticmethod
    def get_suit_color(suit: Suit) -> str:
        """Get color for a suit using centralized color settings."""
        from .styles import get_suit_color
        suit_names = {
            Suit.SPADES: 'spades',
            Suit.HEARTS: 'hearts',
            Suit.DIAMONDS: 'diamonds',
            Suit.CLUBS: 'clubs',
        }
        return get_suit_color(suit_names.get(suit, 'spades'))

    def __init__(self, card: Card = None, face_up: bool = True, parent=None):
        super().__init__(parent)
        self.card = card
        self.face_up = face_up
        self.selectable = False
        self.highlighted = False
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        # Ensure widget receives mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

    def set_card(self, card: Card, face_up: bool = True):
        self.card = card
        self.face_up = face_up
        self.update()

    def set_selectable(self, selectable: bool):
        self.selectable = selectable
        self.setCursor(Qt.CursorShape.PointingHandCursor if selectable else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_highlighted(self, highlighted: bool):
        self.highlighted = highlighted
        self.update()

    def mousePressEvent(self, event):
        print(f"DEBUG CardWidget.mousePressEvent: card={self.card.to_str() if self.card else None}, selectable={self.selectable}", flush=True)
        if self.card and self.selectable and event.button() == Qt.MouseButton.LeftButton:
            print(f"DEBUG CardWidget.mousePressEvent: emitting card_clicked for {self.card.to_str()}", flush=True)
            self.card_clicked.emit(self.card)

    def enterEvent(self, event):
        """Highlight card when mouse enters if selectable"""
        if self.selectable:
            self.highlighted = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Remove highlight when mouse leaves"""
        if self.highlighted:
            self.highlighted = False
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if not self.card or not self.face_up:
            # Face down card with decorative back
            painter.setBrush(QBrush(QColor(COLORS['card_back'])))
            painter.setPen(QPen(QColor(COLORS['card_border']), 2))
            painter.drawRoundedRect(1, 1, w-2, h-2, 8, 8)
            # Decorative border
            painter.setPen(QPen(QColor('#4a5a7a'), 1))
            painter.drawRoundedRect(6, 6, w-12, h-12, 5, 5)
            # Cross-hatch pattern
            painter.setPen(QPen(QColor('#3a4a6a'), 1))
            for i in range(10, w-10, 12):
                for j in range(10, h-10, 12):
                    painter.drawLine(i, j, i+6, j+6)
                    painter.drawLine(i+6, j, i, j+6)
        else:
            # Face up card with proper borders
            color = QColor(self.get_suit_color(self.card.suit))
            bg = QColor(COLORS['highlight']) if self.highlighted else QColor(COLORS['card_face'])

            painter.setBrush(QBrush(bg))
            border_color = QColor(COLORS['selectable_border']) if self.selectable else QColor('#888888')
            painter.setPen(QPen(border_color, 3 if self.selectable else 1))
            painter.drawRoundedRect(1, 1, w-2, h-2, 8, 8)

            rank_char = self.card.rank.to_char()
            suit_sym = self.SUIT_SYMBOLS.get(self.card.suit, '?')

            # Top-left corner
            painter.setPen(color)
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.drawText(6, 26, rank_char)
            painter.setFont(QFont("Arial", 18))
            painter.drawText(6, 48, suit_sym)

            # Bottom-right corner (rotated)
            painter.save()
            painter.translate(w, h)
            painter.rotate(180)
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.drawText(6, 26, rank_char)
            painter.setFont(QFont("Arial", 18))
            painter.drawText(6, 48, suit_sym)
            painter.restore()

            # Center content
            cx, cy = w // 2, h // 2

            if self.card.rank in (Rank.KING, Rank.QUEEN, Rank.JACK):
                # Face card with decorative graphics
                self._draw_face_card(painter, cx, cy, color)
            elif self.card.rank == Rank.ACE:
                # Large center suit symbol
                painter.setFont(QFont("Arial", 60, QFont.Weight.Bold))
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(suit_sym)
                painter.drawText(cx - tw//2, cy + 22, suit_sym)
            else:
                # Number cards - draw pip pattern
                pip_count = 10 - self.card.rank.value
                painter.setFont(QFont("Arial", 28))
                self._draw_pips(painter, cx, cy, suit_sym, pip_count)

    def _draw_face_card(self, painter, cx, cy, color):
        """Draw decorative face card"""
        rank = self.card.rank
        suit_sym = self.SUIT_SYMBOLS.get(self.card.suit, '?')

        # Draw decorative frame
        painter.setPen(QPen(color, 2))
        frame_w, frame_h = 60, 85
        painter.drawRect(cx - frame_w//2, cy - frame_h//2, frame_w, frame_h)

        # Crown/tiara above letter
        if rank == Rank.KING:
            painter.setFont(QFont("Arial", 28))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance("♔")
            painter.drawText(cx - tw//2, cy - 18, "♔")
        elif rank == Rank.QUEEN:
            painter.setFont(QFont("Arial", 28))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance("♕")
            painter.drawText(cx - tw//2, cy - 18, "♕")
        elif rank == Rank.JACK:
            painter.setFont(QFont("Arial", 22))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(suit_sym)
            painter.drawText(cx - tw//2, cy - 20, suit_sym)

        # Letter in center
        painter.setFont(QFont("Arial", 44, QFont.Weight.Bold))
        letter = {Rank.KING: 'K', Rank.QUEEN: 'Q', Rank.JACK: 'J'}[rank]
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(letter)
        painter.drawText(cx - tw//2, cy + 18, letter)

        # Suit symbol below letter
        painter.setFont(QFont("Arial", 20))
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(suit_sym)
        painter.drawText(cx - tw//2, cy + 38, suit_sym)

    def _draw_pips(self, painter, cx, cy, sym, count):
        # Pip positions for cards
        positions = {
            2: [(0, -30), (0, 30)],
            3: [(0, -35), (0, 0), (0, 35)],
            4: [(-18, -28), (18, -28), (-18, 28), (18, 28)],
            5: [(-18, -28), (18, -28), (0, 0), (-18, 28), (18, 28)],
            6: [(-18, -35), (18, -35), (-18, 0), (18, 0), (-18, 35), (18, 35)],
            7: [(-18, -35), (18, -35), (0, -14), (-18, 0), (18, 0), (-18, 35), (18, 35)],
            8: [(-18, -35), (18, -35), (0, -18), (-18, 0), (18, 0), (0, 18), (-18, 35), (18, 35)],
            9: [(-18, -38), (18, -38), (-18, -14), (18, -14), (0, 0), (-18, 14), (18, 14), (-18, 38), (18, 38)],
            10: [(-18, -40), (18, -40), (0, -26), (-18, -10), (18, -10), (-18, 10), (18, 10), (0, 26), (-18, 40), (18, 40)],
        }
        for dx, dy in positions.get(count, []):
            painter.drawText(cx + dx - 10, cy + dy + 10, sym)


class FannedHandWidget(QWidget):
    """Widget showing a fanned hand of cards with overlap"""

    card_selected = pyqtSignal(object, object)

    def __init__(self, seat: Seat, horizontal: bool = True, parent=None):
        super().__init__(parent)
        self.seat = seat
        self.logical_seat = seat
        self.hand: Optional[Hand] = None
        self.face_up = True
        self.selectable = False
        self.horizontal = horizontal
        self.card_widgets: List[CardWidget] = []
        self.is_dummy = False
        self.is_declarer = False
        self.is_human = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        # Label - smaller font
        self.label = QLabel()
        self.label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_label()
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Cards container - use absolute positioning for overlap
        self.cards_container = QWidget()
        # Allow mouse events to pass through to children
        self.cards_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        # Set minimum size for 13 cards
        if self.horizontal:
            # Fan width: first card full + 12 cards with overlap + 3 suit gaps
            fan_width = CARD_WIDTH + (12 * (CARD_WIDTH - CARD_OVERLAP)) + (3 * SUIT_GAP)
            self.cards_container.setMinimumSize(fan_width, CARD_HEIGHT + 10)
        layout.addWidget(self.cards_container)

    def _update_label(self):
        if self.is_dummy:
            text = f"{self.seat.to_char()} / Dummy"
            style = "background-color: #ff6688; color: black; padding: 3px 10px; border-radius: 4px;"
        elif self.is_declarer:
            text = f"{self.seat.to_char()} / Declarer"
            style = "background-color: #ff6688; color: black; padding: 3px 10px; border-radius: 4px;"
        elif self.is_human:
            # Show HUMAN label for human player
            text = f"{self.seat.to_char()}: HUMAN"
            style = "background-color: #88ccff; color: black; padding: 3px 10px; border-radius: 4px;"
        else:
            text = f"{self.seat.to_char()}: BEN"
            style = "background-color: #d0d0e0; color: black; padding: 3px 10px; border-radius: 4px;"
        self.label.setText(text)
        self.label.setStyleSheet(f"QLabel {{ {style} }}")

    def set_player_info(self, is_human: bool = False, is_dummy: bool = False, is_declarer: bool = False):
        self.is_human = is_human
        self.is_dummy = is_dummy
        self.is_declarer = is_declarer
        self._update_label()

    def set_hand(self, hand: Hand, face_up: bool = True):
        self.hand = hand
        self.face_up = face_up
        self._rebuild_cards()

    def set_selectable(self, selectable: bool):
        self.selectable = selectable
        for cw in self.card_widgets:
            cw.set_selectable(selectable and self.face_up)

    def clear(self):
        for cw in self.card_widgets:
            cw.deleteLater()
        self.card_widgets.clear()

    def _rebuild_cards(self):
        self.clear()
        if not self.hand:
            return

        sorted_cards = sorted(self.hand.cards, key=lambda c: (c.suit, c.rank))

        # Fan cards horizontally with overlap, adding gaps between suits
        step = CARD_WIDTH - CARD_OVERLAP
        x_pos = 0
        prev_suit = None

        for card in sorted_cards:
            # Add extra gap when suit changes (only for face-up hands)
            if self.face_up and prev_suit is not None and card.suit != prev_suit:
                x_pos += SUIT_GAP

            cw = CardWidget(card, self.face_up, self.cards_container)
            cw.set_selectable(self.selectable and self.face_up)
            cw.card_clicked.connect(lambda c, s=self.logical_seat: self.card_selected.emit(s, c))
            cw.move(int(x_pos), 0)
            cw.show()
            cw.raise_()  # Ensure this card is on top of previous ones
            self.card_widgets.append(cw)

            x_pos += step
            prev_suit = card.suit

    def remove_card(self, card: Card):
        if self.hand:
            self.hand.remove_card(card)
            self._rebuild_cards()

    def highlight_legal(self, lead_suit: Optional[Suit]):
        if not self.hand:
            return
        # Note: use 'is not None' because Suit.SPADES has value 0 which is falsy
        has_suit = lead_suit is not None and any(c.suit == lead_suit for c in self.hand.cards)
        for cw in self.card_widgets:
            if lead_suit is None:
                cw.set_selectable(self.selectable)
            elif has_suit:
                cw.set_selectable(self.selectable and cw.card.suit == lead_suit)
            else:
                cw.set_selectable(self.selectable)


class TrickAreaWidget(QFrame):
    """Green table center with played cards at fixed compass positions"""

    # Trick area size - increased height to fit all cards
    AREA_WIDTH = 340
    AREA_HEIGHT = 420

    # Use smaller cards in trick area to fit
    TRICK_CARD_WIDTH = 80
    TRICK_CARD_HEIGHT = 115

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.AREA_WIDTH, self.AREA_HEIGHT)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['table_green']};
                border: 4px solid #1a5c30;
                border-radius: 12px;
            }}
        """)
        self.played_cards: Dict[Seat, Card] = {}
        self.winner: Optional[Seat] = None
        self.card_widgets: Dict[Seat, CardWidget] = {}
        self.show_bidding = False
        self.auction = []
        self.dealer = Seat.NORTH
        self.bidding_status = ""

        self._setup_ui()

    def _setup_ui(self):
        # Use absolute positioning for fixed card placements
        w, h = self.AREA_WIDTH, self.AREA_HEIGHT
        tcw, tch = self.TRICK_CARD_WIDTH, self.TRICK_CARD_HEIGHT

        # Card positions - arranged around center with spacing
        center_x, center_y = w // 2, h // 2
        gap = 5  # Gap between cards

        positions = {
            Seat.NORTH: (center_x - tcw // 2, center_y - tch - gap),
            Seat.SOUTH: (center_x - tcw // 2, center_y + gap),
            Seat.WEST: (center_x - tcw - gap, center_y - tch // 2),
            Seat.EAST: (center_x + gap, center_y - tch // 2),
        }

        # Create card widgets with fixed positions (smaller size for trick area)
        for seat in Seat:
            cw_widget = CardWidget(parent=self)
            cw_widget.setFixedSize(tcw, tch)  # Use smaller size
            cw_widget.setVisible(False)
            cw_widget.move(positions[seat][0], positions[seat][1])
            self.card_widgets[seat] = cw_widget

        # Direction arrows at edges
        arrow_positions = {
            'N': (center_x - 17, 8),
            'S': (center_x - 17, h - 43),
            'W': (8, center_y - 17),
            'E': (w - 43, center_y - 17),
        }
        for d, pos in arrow_positions.items():
            arrow = DirectionArrow(d, self)
            arrow.move(pos[0], pos[1])

        # Bidding table overlay in center
        self.bidding_widget = BiddingTableWidget(self)
        bw, bh = 260, 200
        self.bidding_widget.move((w - bw) // 2, (h - bh) // 2)
        self.bidding_widget.setFixedSize(bw, bh)

    def set_show_bidding(self, show: bool):
        self.show_bidding = show
        self.bidding_widget.setVisible(show)
        if show:
            for cw in self.card_widgets.values():
                cw.setVisible(False)

    def set_auction(self, auction, dealer: Seat):
        self.auction = auction
        self.dealer = dealer
        self.bidding_widget.set_auction(auction, dealer)

    def set_bidding_status(self, status: str):
        self.bidding_status = status
        self.bidding_widget.set_status(status)

    def play_card(self, seat: Seat, card: Card, is_winner: bool = False):
        self.played_cards[seat] = card
        cw = self.card_widgets[seat]
        cw.set_card(card, True)
        cw.set_highlighted(is_winner)
        cw.setVisible(True)

    def set_winner(self, seat: Seat):
        self.winner = seat
        for s, cw in self.card_widgets.items():
            cw.set_highlighted(s == seat)

    def clear_trick(self):
        print(f"DEBUG TrickAreaWidget.clear_trick: hiding {len(self.played_cards)} cards", flush=True)
        self.played_cards.clear()
        self.winner = None
        for cw in self.card_widgets.values():
            cw.setVisible(False)
            cw.set_highlighted(False)
        self.update()  # Force repaint


class DirectionArrow(QWidget):
    def __init__(self, direction: str, parent=None):
        super().__init__(parent)
        self.direction = direction
        self.setFixedSize(35, 35)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#d0d0d0'), 2))
        painter.setBrush(QBrush(QColor('#d0d0d0')))

        w, h = self.width(), self.height()
        pts = {
            'N': [QPoint(w//2, 3), QPoint(w-3, h-3), QPoint(3, h-3)],
            'S': [QPoint(w//2, h-3), QPoint(3, 3), QPoint(w-3, 3)],
            'E': [QPoint(w-3, h//2), QPoint(3, 3), QPoint(3, h-3)],
            'W': [QPoint(3, h//2), QPoint(w-3, 3), QPoint(w-3, h-3)],
        }
        painter.drawPolygon(QPolygon(pts.get(self.direction, [])))

        painter.setPen(QColor('#ffffff'))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.direction)


class BiddingTableWidget(QFrame):
    """Bidding table overlay in center"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background-color: #e8e8e8; border: 1px solid #888; border-radius: 5px; }")
        self.setMinimumSize(200, 150)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Header - moderate font size for green area
        header = QHBoxLayout()
        for d in ['N', 'E', 'S', 'W']:
            lbl = QLabel(d)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            lbl.setFixedWidth(55)
            lbl.setStyleSheet("background-color: #c0c0c0; border: 1px solid #888;")
            header.addWidget(lbl)
        layout.addLayout(header)

        self.bids_widget = QWidget()
        self.bids_layout = QVBoxLayout(self.bids_widget)
        self.bids_layout.setContentsMargins(0, 0, 0, 0)
        self.bids_layout.setSpacing(1)
        layout.addWidget(self.bids_widget)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.status_label)

    def set_auction(self, auction, dealer: Seat):
        while self.bids_layout.count():
            item = self.bids_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not auction:
            return

        dealer_idx = dealer.value
        col = 0
        current_row = None

        for i in range(dealer_idx):
            if col == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(0)
            lbl = QLabel("-")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(55)
            lbl.setFont(QFont("Arial", 13))
            lbl.setStyleSheet("border: 1px solid #ccc;")
            current_row.addWidget(lbl)
            col += 1

        for bid in auction:
            if col == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(0)

            text = bid.symbol() if hasattr(bid, 'symbol') else str(bid)
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(55)
            lbl.setFont(QFont("Arial", 13))

            if hasattr(bid, 'is_pass') and bid.is_pass:
                lbl.setStyleSheet("border: 1px solid #ccc; color: #666;")
            elif hasattr(bid, 'is_double') and bid.is_double:
                lbl.setStyleSheet("border: 1px solid #ccc; color: blue; font-weight: bold;")
            elif hasattr(bid, 'is_redouble') and bid.is_redouble:
                lbl.setStyleSheet("border: 1px solid #ccc; color: #00008B; font-weight: bold;")
            elif hasattr(bid, 'suit') and bid.suit is not None:
                # Use centralized suit colors (respects 4-color mode)
                from .styles import get_suit_color
                suit_names = {Suit.SPADES: 'spades', Suit.HEARTS: 'hearts',
                             Suit.DIAMONDS: 'diamonds', Suit.CLUBS: 'clubs'}
                color = get_suit_color(suit_names.get(bid.suit, 'spades'))
                lbl.setStyleSheet(f"border: 1px solid #ccc; color: {color}; font-weight: bold;")
            else:
                lbl.setStyleSheet("border: 1px solid #ccc; color: black; font-weight: bold;")

            current_row.addWidget(lbl)
            col += 1
            if col >= 4:
                self.bids_layout.addLayout(current_row)
                current_row = None
                col = 0

        if current_row and col > 0:
            while col < 4:
                lbl = QLabel("?")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFixedWidth(55)
                lbl.setFont(QFont("Arial", 13))
                lbl.setStyleSheet("border: 1px solid #ccc; color: #888;")
                current_row.addWidget(lbl)
                col += 1
            self.bids_layout.addLayout(current_row)

    def set_status(self, text: str):
        self.status_label.setText(text)


class InfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['panel_teal']}; border: 1px solid #2a5c6a; border-radius: 4px; }}
            QLabel {{ color: {COLORS['text_white']}; }}
        """)


class TableView(QWidget):
    """Main table view for 1920x1080"""

    card_played = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board: Optional[BoardState] = None
        self.declarer: Optional[Seat] = None
        self.dummy: Optional[Seat] = None
        self.human_controls_declarer = False
        self.swapped_positions = False
        self.is_play_phase = False

        self.setStyleSheet(f"background-color: {COLORS['background']};")
        self.setMinimumHeight(850)  # Ensure enough height for trick area
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 5, 10, 5)

        # Top bar
        top_bar = QHBoxLayout()

        top_bar.addStretch()

        self.info_panel = InfoPanel()
        il = QVBoxLayout(self.info_panel)
        il.setContentsMargins(10, 5, 10, 5)
        self.dealer_label = QLabel("Dealer:")
        self.dealer_label.setFont(QFont("Arial", 12))
        il.addWidget(self.dealer_label)
        self.vuln_label = QLabel("Vul.:")
        self.vuln_label.setFont(QFont("Arial", 12))
        il.addWidget(self.vuln_label)
        top_bar.addWidget(self.info_panel)

        layout.addLayout(top_bar)

        # Create all hand widgets first
        self.hand_widgets = {}
        for seat in Seat:
            self.hand_widgets[seat] = FannedHandWidget(seat, horizontal=True)
            self.hand_widgets[seat].label.setVisible(False)  # We use our own labels

        # North label (always visible during bidding, changes during play)
        self.north_label = QLabel("N: BEN")
        self.north_label.setFont(QFont("Arial", 10))
        self.north_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
        self.north_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.north_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # North hand area (hidden during bidding, shown during play when N is dummy)
        self.hand_widgets[Seat.NORTH].set_player_info(is_human=False)
        north_hand_layout = QHBoxLayout()
        north_hand_layout.addStretch()
        north_hand_layout.addWidget(self.hand_widgets[Seat.NORTH])
        north_hand_layout.addStretch()
        self.hand_widgets[Seat.NORTH].setVisible(False)  # Hidden during bidding
        layout.addLayout(north_hand_layout)

        # Middle section with E/W areas and trick area
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)

        # West side - label and hand widget (vertical stack)
        west_vbox = QVBoxLayout()
        self.west_label = QLabel("W: BEN")
        self.west_label.setFont(QFont("Arial", 10))
        self.west_label.setFixedWidth(70)
        self.west_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
        self.west_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        west_vbox.addStretch()
        west_vbox.addWidget(self.west_label, alignment=Qt.AlignmentFlag.AlignCenter)
        west_vbox.addWidget(self.hand_widgets[Seat.WEST])
        self.hand_widgets[Seat.WEST].setVisible(False)  # Hidden by default
        west_vbox.addStretch()
        middle_layout.addLayout(west_vbox, stretch=1)

        # Trick area in center - wrap in layouts to ensure proper centering
        trick_container = QVBoxLayout()
        trick_container.addStretch()
        # Horizontal wrapper to ensure horizontal centering
        trick_h_wrapper = QHBoxLayout()
        trick_h_wrapper.addStretch()
        self.trick_area = TrickAreaWidget()
        trick_h_wrapper.addWidget(self.trick_area)
        trick_h_wrapper.addStretch()
        trick_container.addLayout(trick_h_wrapper)
        trick_container.addStretch()
        # Use stretch=1 so the center column gets equal space distribution
        middle_layout.addLayout(trick_container, stretch=1)

        # East side - label and hand widget (vertical stack)
        east_vbox = QVBoxLayout()
        self.east_label = QLabel("E: BEN")
        self.east_label.setFont(QFont("Arial", 10))
        self.east_label.setFixedWidth(70)
        self.east_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
        self.east_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        east_vbox.addStretch()
        east_vbox.addWidget(self.east_label, alignment=Qt.AlignmentFlag.AlignCenter)
        east_vbox.addWidget(self.hand_widgets[Seat.EAST])
        self.hand_widgets[Seat.EAST].setVisible(False)  # Hidden by default
        east_vbox.addStretch()
        middle_layout.addLayout(east_vbox, stretch=1)

        layout.addLayout(middle_layout, stretch=1)

        # Add spacing before south label to ensure it's outside the trick area
        layout.addSpacing(10)

        # South label (small, just the text) - above the cards
        self.south_label = QLabel("S: HUMAN")
        self.south_label.setFont(QFont("Arial", 10))
        self.south_label.setStyleSheet("QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }")
        self.south_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.south_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # South hand (fanned out)
        self.hand_widgets[Seat.SOUTH].set_player_info(is_human=True)
        south_layout = QHBoxLayout()
        south_layout.addStretch()
        south_layout.addWidget(self.hand_widgets[Seat.SOUTH])
        south_layout.addStretch()
        layout.addLayout(south_layout)

        # Bottom bar with contract and tricks
        bottom_bar = QHBoxLayout()

        self.contract_panel = InfoPanel()
        cl = QVBoxLayout(self.contract_panel)
        cl.setContentsMargins(10, 5, 10, 5)
        self.contract_title = QLabel("Contract:")
        self.contract_title.setFont(QFont("Arial", 12))
        cl.addWidget(self.contract_title)
        self.contract_label = QLabel("")
        self.contract_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        cl.addWidget(self.contract_label)
        bottom_bar.addWidget(self.contract_panel)

        bottom_bar.addStretch()

        self.tricks_panel = InfoPanel()
        tl = QVBoxLayout(self.tricks_panel)
        tl.setContentsMargins(10, 5, 10, 5)
        self.tricks_title = QLabel("Tricks:")
        self.tricks_title.setFont(QFont("Arial", 12))
        tl.addWidget(self.tricks_title)
        self.tricks_label = QLabel("0 : 0")
        self.tricks_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        tl.addWidget(self.tricks_label)
        bottom_bar.addWidget(self.tricks_panel)

        layout.addLayout(bottom_bar)

        # Connect signals
        for seat, hw in self.hand_widgets.items():
            hw.card_selected.connect(self._on_card_selected)

        # Hide tricks panel during bidding
        self.tricks_panel.setVisible(False)

    def _on_card_selected(self, seat: Seat, card: Card):
        print(f"DEBUG TableView._on_card_selected: seat={seat}, card={card.to_str()}", flush=True)
        self.card_played.emit(seat, card)

    def set_board(self, board: BoardState):
        self.board = board
        self.declarer = None
        self.dummy = None
        self.swapped_positions = False
        self.is_play_phase = False

        self.dealer_label.setText(f"Dealer: {board.dealer.to_char()}")
        vuln_map = {Vulnerability.NONE: 'None', Vulnerability.NS: 'N-S', Vulnerability.EW: 'E-W', Vulnerability.BOTH: 'Both'}
        self.vuln_label.setText(f"Vul.: {vuln_map[board.vulnerability]}")

        # Update player labels
        self.north_label.setText("N: BEN")
        self.north_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
        self.east_label.setText("E: BEN")
        self.west_label.setText("W: BEN")
        self.south_label.setText("S: HUMAN")
        self.south_label.setStyleSheet("QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }")

        # Hide North's hand during bidding (will show during play if dummy)
        self.hand_widgets[Seat.NORTH].setVisible(False)

        # Only show South's hand (face up) during bidding
        for seat in Seat:
            self.hand_widgets[seat].logical_seat = seat
            self.hand_widgets[seat].set_player_info(is_human=(seat == Seat.SOUTH))
            if seat == Seat.SOUTH and seat in board.hands:
                self.hand_widgets[seat].setVisible(True)
                self.hand_widgets[seat].set_hand(board.hands[seat], face_up=True)
            else:
                self.hand_widgets[seat].setVisible(False)
                self.hand_widgets[seat].clear()

        self.trick_area.clear_trick()
        self.trick_area.set_show_bidding(True)
        self.trick_area.set_auction([], board.dealer)
        self.tricks_label.setText("0 : 0")
        self.contract_label.setText("")

        # Hide tricks during bidding
        self.tricks_panel.setVisible(False)

    def update_auction(self, auction, dealer: Seat):
        self.trick_area.set_auction(auction, dealer)

    def set_auction_complete(self, msg: str = "bidding finished"):
        self.trick_area.set_bidding_status(msg)

    def setup_declarer_play(self, contract: Contract):
        self.declarer = contract.declarer
        self.dummy = contract.declarer.partner()
        self.is_play_phase = True

        # Update labels for declarer/dummy
        for seat in Seat:
            is_dec = (seat == self.declarer)
            is_dum = (seat == self.dummy)
            is_hum = seat in (Seat.SOUTH, Seat.NORTH) and (self.declarer in (Seat.NORTH, Seat.SOUTH))
            self.hand_widgets[seat].set_player_info(is_human=is_hum, is_dummy=is_dum, is_declarer=is_dec)

        # Handle position swapping if North is declarer
        if self.declarer == Seat.NORTH:
            self._swap_ns()

        # Show South's hand (always visible - the human player)
        self.hand_widgets[Seat.SOUTH].setVisible(True)

        # ALWAYS show dummy's hand face-up (bridge rules)
        # Show dummy in the North widget position (top of screen)
        if self.dummy == Seat.NORTH:
            # North is dummy
            self.north_label.setText("N: Dummy")
            self.north_label.setStyleSheet("QLabel { background-color: #ff6688; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.south_label.setText("S: Declarer" if self.declarer == Seat.SOUTH else "S: HUMAN")
            style = "QLabel { background-color: #88ff88; color: black; padding: 3px 8px; border-radius: 3px; }" if self.declarer == Seat.SOUTH else "QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }"
            self.south_label.setStyleSheet(style)
            if Seat.NORTH in self.board.hands:
                self.hand_widgets[Seat.NORTH].set_hand(self.board.hands[Seat.NORTH], face_up=True)
                self.hand_widgets[Seat.NORTH].setVisible(True)
        elif self.dummy == Seat.SOUTH:
            # South is dummy (North is declarer) - positions swapped by _swap_ns()
            # After swap: top shows South's cards (dummy), bottom shows North's cards (declarer)
            self.north_label.setText("S: Dummy")  # Top label - showing South's cards
            self.north_label.setStyleSheet("QLabel { background-color: #ff6688; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.south_label.setText("N: Declarer")  # Bottom label - showing North's cards
            self.south_label.setStyleSheet("QLabel { background-color: #88ff88; color: black; padding: 3px 8px; border-radius: 3px; }")
            # _swap_ns() already set up the hands, but ensure dummy is visible
            self.hand_widgets[Seat.NORTH].setVisible(True)
        elif self.dummy == Seat.EAST:
            # East is dummy (West is declarer) - show East's cards at RIGHT (natural position)
            self.north_label.setText("N: BEN")
            self.north_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.east_label.setText("E: Dummy")
            self.east_label.setStyleSheet("QLabel { background-color: #ff6688; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.west_label.setText("W: Declarer")
            self.west_label.setStyleSheet("QLabel { background-color: #88ff88; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.south_label.setText("S: HUMAN")
            self.south_label.setStyleSheet("QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }")
            if Seat.EAST in self.board.hands:
                self.hand_widgets[Seat.EAST].set_hand(self.board.hands[Seat.EAST], face_up=True)
                self.hand_widgets[Seat.EAST].logical_seat = Seat.EAST
                self.hand_widgets[Seat.EAST].setVisible(True)
        elif self.dummy == Seat.WEST:
            # West is dummy (East is declarer) - show West's cards at LEFT (natural position)
            self.north_label.setText("N: BEN")
            self.north_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.west_label.setText("W: Dummy")
            self.west_label.setStyleSheet("QLabel { background-color: #ff6688; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.east_label.setText("E: Declarer")
            self.east_label.setStyleSheet("QLabel { background-color: #88ff88; color: black; padding: 3px 8px; border-radius: 3px; }")
            self.south_label.setText("S: HUMAN")
            self.south_label.setStyleSheet("QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }")
            if Seat.WEST in self.board.hands:
                self.hand_widgets[Seat.WEST].set_hand(self.board.hands[Seat.WEST], face_up=True)
                self.hand_widgets[Seat.WEST].logical_seat = Seat.WEST
                self.hand_widgets[Seat.WEST].setVisible(True)

        self.contract_label.setText(f"{contract.declarer.to_char()} {contract.to_str()}")
        self.trick_area.set_show_bidding(False)
        self.tricks_panel.setVisible(True)

    def _swap_ns(self):
        """Swap N/S and E/W positions when North is declarer.
        This rotates the view 180 degrees so declarer (N) is at the bottom."""
        self.swapped_positions = True

        # Swap N/S hands
        n_hand = self.board.hands.get(Seat.NORTH)
        s_hand = self.board.hands.get(Seat.SOUTH)
        self.hand_widgets[Seat.NORTH].logical_seat = Seat.SOUTH
        self.hand_widgets[Seat.SOUTH].logical_seat = Seat.NORTH
        if s_hand:
            self.hand_widgets[Seat.NORTH].set_hand(s_hand, face_up=True)
        if n_hand:
            self.hand_widgets[Seat.SOUTH].set_hand(n_hand, face_up=True)

        # Swap E/W hands
        e_hand = self.board.hands.get(Seat.EAST)
        w_hand = self.board.hands.get(Seat.WEST)
        self.hand_widgets[Seat.EAST].logical_seat = Seat.WEST
        self.hand_widgets[Seat.WEST].logical_seat = Seat.EAST
        if w_hand:
            self.hand_widgets[Seat.EAST].set_hand(w_hand, face_up=False)  # W's cards at E position
        if e_hand:
            self.hand_widgets[Seat.WEST].set_hand(e_hand, face_up=False)  # E's cards at W position

        # Swap E/W labels
        self.east_label.setText("W: BEN")
        self.west_label.setText("E: BEN")

    def set_hand_visible(self, seat: Seat, visible: bool):
        if self.board and seat in self.board.hands:
            ds = seat
            if self.swapped_positions:
                if seat == Seat.NORTH:
                    ds = Seat.SOUTH
                elif seat == Seat.SOUTH:
                    ds = Seat.NORTH
                elif seat == Seat.EAST:
                    ds = Seat.WEST
                elif seat == Seat.WEST:
                    ds = Seat.EAST
            # Make the widget visible and set the hand
            self.hand_widgets[ds].setVisible(visible)
            if visible:
                self.hand_widgets[ds].set_hand(self.board.hands[seat], face_up=True)

    def set_hand_selectable(self, seat: Seat, selectable: bool, lead_suit: Optional[Suit] = None):
        ds = seat
        if self.swapped_positions:
            if seat == Seat.NORTH:
                ds = Seat.SOUTH
            elif seat == Seat.SOUTH:
                ds = Seat.NORTH
            elif seat == Seat.EAST:
                ds = Seat.WEST
            elif seat == Seat.WEST:
                ds = Seat.EAST
        if selectable:
            print(f"DEBUG set_hand_selectable: seat={seat}, ds={ds}, swapped={self.swapped_positions}, lead_suit={lead_suit}", flush=True)
        self.hand_widgets[ds].set_selectable(selectable)
        if selectable:
            self.hand_widgets[ds].highlight_legal(lead_suit)

    def play_card_to_trick(self, seat: Seat, card: Card, is_winner: bool = False):
        ds = seat  # Display seat (which widget to remove card from)
        trick_seat = seat  # Position in trick area
        if self.swapped_positions:
            # When N is declarer, all positions are rotated 180 degrees
            if seat == Seat.NORTH:
                ds = Seat.SOUTH
                trick_seat = Seat.SOUTH
            elif seat == Seat.SOUTH:
                ds = Seat.NORTH
                trick_seat = Seat.NORTH
            elif seat == Seat.EAST:
                ds = Seat.WEST
                trick_seat = Seat.WEST
            elif seat == Seat.WEST:
                ds = Seat.EAST
                trick_seat = Seat.EAST
        print(f"DEBUG play_card_to_trick: seat={seat}, trick_seat={trick_seat}, ds={ds}, swapped={self.swapped_positions}", flush=True)
        self.trick_area.play_card(trick_seat, card, is_winner)
        self.hand_widgets[ds].remove_card(card)

    def show_trick_winner(self, winner: Seat):
        display_winner = winner
        if self.swapped_positions:
            # Rotate 180 degrees
            if winner == Seat.NORTH:
                display_winner = Seat.SOUTH
            elif winner == Seat.SOUTH:
                display_winner = Seat.NORTH
            elif winner == Seat.EAST:
                display_winner = Seat.WEST
            elif winner == Seat.WEST:
                display_winner = Seat.EAST
        self.trick_area.set_winner(display_winner)

    def clear_trick(self):
        print(f"DEBUG TableView.clear_trick: clearing trick display", flush=True)
        self.trick_area.clear_trick()

    def update_tricks(self, dec_tricks: int, def_tricks: int):
        self.tricks_label.setText(f"{dec_tricks} : {def_tricks}")

    def set_contract(self, contract_str: str, declarer: str):
        self.contract_label.setText(f"{declarer} {contract_str}")
