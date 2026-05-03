"""
TableView - Visual representation of the bridge table.
Optimized for 1920x1080 screens with large cards and easy-to-read layout.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QRect, QPoint
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPainter, QBrush, QPen, QPolygon, QFontMetrics,
    QPixmap, QImage
)
import os

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

# Card dimensions - sized to fill 1920x1080 screen
CARD_WIDTH = 140
CARD_HEIGHT = 198
CARD_OVERLAP = 75  # How much cards overlap (shows ~65px per card)
SUIT_GAP = 90  # Extra gap between suits — creates clear visible gap


class CardWidget(QWidget):
    """Playing card widget using traditional card images from tmcgui deck."""

    card_clicked = pyqtSignal(object)

    SUIT_SYMBOLS = {
        Suit.SPADES: '♠',
        Suit.HEARTS: '♥',
        Suit.DIAMONDS: '♦',
        Suit.CLUBS: '♣',
    }

    # Cache for loaded and processed card images
    _image_cache: Dict[str, QPixmap] = {}
    _back_pixmap: Optional[QPixmap] = None
    _images_dir: Optional[str] = None

    @classmethod
    def _get_images_dir(cls) -> str:
        if cls._images_dir is None:
            # Find the card images relative to this file
            here = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.join(here, '..', '..', 'ben', 'src', 'tmcgui',
                                     'images', 'deck', 'width 100')
            cls._images_dir = os.path.normpath(candidate)
        return cls._images_dir

    @classmethod
    def _get_card_pixmap(cls, card: 'Card') -> Optional[QPixmap]:
        """Load and cache a card image, recoloring for 4-color mode."""
        suit_char = {Suit.SPADES: 'S', Suit.HEARTS: 'H',
                     Suit.DIAMONDS: 'D', Suit.CLUBS: 'C'}[card.suit]
        # Image naming: rank 2-10=2-10, J=11, Q=12, K=13, A=14
        rank_num = 14 - card.rank.value  # ACE=0→14, KING=1→13, ..., TWO=12→2
        key = f"{suit_char}{rank_num}"

        if key not in cls._image_cache:
            path = os.path.join(cls._get_images_dir(), f"{key}.png")
            if not os.path.exists(path):
                return None

            img = QImage(path)
            # Scale to card size
            img = img.scaled(CARD_WIDTH, CARD_HEIGHT,
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

            # Apply 4-color tinting for diamonds (→blue) and clubs (→green)
            from ben_backend.config import get_config_manager
            try:
                legacy = get_config_manager().config.preferences.legacy_colors
            except Exception:
                legacy = False

            if not legacy:
                if card.suit == Suit.DIAMONDS:
                    cls._recolor_image(img, Suit.DIAMONDS, QColor(0, 0, 204))
                elif card.suit == Suit.CLUBS:
                    cls._recolor_image(img, Suit.CLUBS, QColor(0, 100, 0))

            cls._image_cache[key] = QPixmap.fromImage(img)

        return cls._image_cache.get(key)

    @classmethod
    def _get_back_pixmap(cls) -> QPixmap:
        if cls._back_pixmap is None:
            path = os.path.join(cls._get_images_dir(), 'blue_back.png')
            if os.path.exists(path):
                img = QImage(path)
                img = img.scaled(CARD_WIDTH, CARD_HEIGHT,
                                 Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                cls._back_pixmap = QPixmap.fromImage(img)
            else:
                cls._back_pixmap = QPixmap(CARD_WIDTH, CARD_HEIGHT)
                cls._back_pixmap.fill(QColor('#1a3a8c'))
        return cls._back_pixmap

    @staticmethod
    def _recolor_image(img: QImage, suit: 'Suit', to_color: QColor):
        """Recolor card image suit symbols and rank text for 4-color mode.

        For diamonds: any reddish pixel (r > g*1.3 and r > b*1.3) → blue
        For clubs: any dark/gray pixel (max channel < 160, not white bg) → green
        Preserves brightness while shifting the hue.
        """
        tr, tg, tb = to_color.red(), to_color.green(), to_color.blue()

        for y in range(img.height()):
            for x in range(img.width()):
                px = img.pixelColor(x, y)
                r, g, b, a = px.red(), px.green(), px.blue(), px.alpha()
                if a < 10:
                    continue

                is_match = False
                if suit == Suit.DIAMONDS:
                    # Match any reddish pixel including anti-aliased pink edges
                    # Red channel dominates AND pixel is not background-white
                    is_match = (r > 40 and r > g * 1.3 and r > b * 1.3
                                and r + g + b < 650)
                elif suit == Suit.CLUBS:
                    # Match any dark/gray pixel (club symbols, rank text, edges)
                    # Skip white/light background (r+g+b > 500) and colored pixels
                    mx = max(r, g, b)
                    is_match = (mx < 170 and r + g + b < 450
                                and abs(r - g) < 40 and abs(r - b) < 40)

                if is_match:
                    # Map pixel brightness to target color, with minimum brightness
                    # so dark source pixels become visible in the target color
                    lum = (r + g + b) / 3.0
                    target_lum = (tr + tg + tb) / 3.0
                    # Use brightness ratio but ensure dark pixels stay visible
                    if lum < 40:
                        # Dark pixel: use target color at full/near-full intensity
                        scale = max(0.7, lum / max(1.0, target_lum))
                    else:
                        scale = lum / max(1.0, target_lum)
                    nr = min(255, int(tr * scale))
                    ng = min(255, int(tg * scale))
                    nb = min(255, int(tb * scale))
                    img.setPixelColor(x, y, QColor(nr, ng, nb, a))

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

    @classmethod
    def clear_image_cache(cls):
        """Clear cached images (call after changing color settings)."""
        cls._image_cache.clear()
        cls._back_pixmap = None

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
        if self.card and self.selectable and event.button() == Qt.MouseButton.LeftButton:
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
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        if not self.card or not self.face_up:
            # Face-down card
            back = self._get_back_pixmap()
            painter.drawPixmap(0, 0, w, h, back)
        else:
            # Face-up card — use traditional card images
            pixmap = self._get_card_pixmap(self.card)
            if pixmap:
                painter.drawPixmap(0, 0, w, h, pixmap)
            else:
                # Fallback: plain white card with rank/suit text
                painter.setBrush(QBrush(QColor('#fffff8')))
                painter.setPen(QPen(QColor('#000000'), 1))
                painter.drawRoundedRect(1, 1, w-2, h-2, 6, 6)
                color = QColor(self.get_suit_color(self.card.suit))
                painter.setPen(color)
                rank_char = self.card.rank.to_char()
                suit_sym = self.SUIT_SYMBOLS.get(self.card.suit, '?')
                painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
                painter.drawText(8, 28, rank_char)
                painter.setFont(QFont("Arial", 20))
                painter.drawText(8, 50, suit_sym)

            # Draw selection/highlight overlay
            if self.selectable:
                painter.setPen(QPen(QColor(COLORS['selectable_border']), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(1, 1, w-2, h-2, 6, 6)

            if self.highlighted:
                painter.setBrush(QBrush(QColor(255, 255, 200, 60)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(1, 1, w-2, h-2, 6, 6)


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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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

    # Trick area — fits between N and S hands
    AREA_WIDTH = 460
    AREA_HEIGHT = 400

    # Trick cards — large and readable
    TRICK_CARD_WIDTH = 110
    TRICK_CARD_HEIGHT = 155

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
        # _local_seat is the seat the local human is playing. The view is
        # rotated so this seat sits at the bottom physical position. Defaults
        # to South for single-player; main_window calls set_local_seat() in
        # network mode so a guest at East/N/W sees their own hand at the
        # bottom of the screen.
        self._local_seat: Seat = Seat.SOUTH
        self._rotation_quarters: int = 0  # number of 90° steps applied
        self.is_play_phase = False

        self.setStyleSheet(f"background-color: {COLORS['background']};")
        self._setup_ui()

    def _display_seat(self, logical_seat: Seat) -> Seat:
        """Map a logical seat (player identity) to the physical widget that
        currently displays its hand."""
        return Seat((logical_seat.value + self._rotation_quarters) % 4)

    def _logical_seat(self, physical_seat: Seat) -> Seat:
        """Inverse of _display_seat — given a physical widget position, the
        logical seat whose cards it is showing."""
        return Seat((physical_seat.value - self._rotation_quarters) % 4)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(5, 0, 5, 0)

        # Create all hand widgets first
        self.hand_widgets = {}
        for seat in Seat:
            self.hand_widgets[seat] = FannedHandWidget(seat, horizontal=True)
            self.hand_widgets[seat].label.setVisible(False)

        # North row: label + hand + info panel all on one line
        north_row = QHBoxLayout()
        north_row.setSpacing(0)
        north_row.setContentsMargins(0, 0, 0, 0)

        # North label
        self.north_label = QLabel("N: BEN")
        self.north_label.setFont(QFont("Arial", 10))
        self.north_label.setStyleSheet("QLabel { background-color: #d0d0e0; color: black; padding: 2px 8px; border-radius: 3px; }")
        self.north_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.north_label.setFixedWidth(90)

        # North hand
        self.hand_widgets[Seat.NORTH].set_player_info(is_human=False)
        self.hand_widgets[Seat.NORTH].setVisible(False)

        # Info panel (dealer/vuln) — floated to right of north row
        self.info_panel = InfoPanel()
        il = QVBoxLayout(self.info_panel)
        il.setContentsMargins(8, 2, 8, 2)
        self.dealer_label = QLabel("Dealer:")
        self.dealer_label.setFont(QFont("Arial", 11))
        il.addWidget(self.dealer_label)
        self.vuln_label = QLabel("Vul.:")
        self.vuln_label.setFont(QFont("Arial", 11))
        il.addWidget(self.vuln_label)

        north_row.addWidget(self.north_label, alignment=Qt.AlignmentFlag.AlignTop)
        north_row.addStretch()
        north_row.addWidget(self.hand_widgets[Seat.NORTH])
        north_row.addStretch()
        north_row.addWidget(self.info_panel, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(north_row)

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

        # South row: label + hand on one line
        south_row = QHBoxLayout()
        south_row.setSpacing(0)
        south_row.setContentsMargins(0, 0, 0, 0)

        self.south_label = QLabel("S: HUMAN")
        self.south_label.setFont(QFont("Arial", 10))
        self.south_label.setStyleSheet("QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }")
        self.south_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.south_label.setFixedWidth(90)

        self.hand_widgets[Seat.SOUTH].set_player_info(is_human=True)

        south_row.addWidget(self.south_label, alignment=Qt.AlignmentFlag.AlignBottom)
        south_row.addStretch()
        south_row.addWidget(self.hand_widgets[Seat.SOUTH])
        south_row.addStretch()
        # Spacer to balance info panel on north side
        spacer = QWidget()
        spacer.setFixedWidth(90)
        south_row.addWidget(spacer, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(south_row)

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

    def set_local_seat(self, seat: Seat):
        """Rotate the table so the given seat is at the bottom (South widget).

        Called from the network connection handler in main_window so a guest
        at East/N/W sees their own hand at the bottom. Single-player keeps
        the default (South).
        """
        if seat is None:
            seat = Seat.SOUTH
        self._local_seat = seat
        self._rotation_quarters = (Seat.SOUTH.value - seat.value) % 4
        # Re-key each widget's logical_seat. We only re-render the hands if
        # a board is already loaded; otherwise set_board() will do it.
        for physical_seat in Seat:
            self.hand_widgets[physical_seat].logical_seat = self._logical_seat(physical_seat)
        if self.board is not None:
            self._reapply_orientation()

    def _reapply_orientation(self):
        """Refresh hand contents and labels for the current rotation."""
        if self.board is None:
            return
        for physical_seat in Seat:
            logical = self._logical_seat(physical_seat)
            widget = self.hand_widgets[physical_seat]
            widget.logical_seat = logical
            hand = self.board.hands.get(logical)
            face_up = (logical == self._local_seat) or widget.isVisible()
            if hand is not None and widget.isVisible():
                widget.set_hand(hand, face_up=face_up)
        # Refresh seat-name labels (per-seat role labels are owned by
        # setup_declarer_play and set_board so we don't override them here).
        self._refresh_seat_labels()

    def _refresh_seat_labels(self):
        """Set the four position labels to identify the logical seat in each
        physical position. Called whenever rotation changes; downstream
        helpers (setup_declarer_play, set_board) are free to overwrite with
        role info ("Dummy", "Declarer", etc.) afterwards."""
        char_names = {Seat.NORTH: 'N', Seat.EAST: 'E',
                      Seat.SOUTH: 'S', Seat.WEST: 'W'}
        labels = {
            Seat.NORTH: self.north_label,
            Seat.EAST: self.east_label,
            Seat.SOUTH: self.south_label,
            Seat.WEST: self.west_label,
        }
        for physical_seat, label in labels.items():
            logical = self._logical_seat(physical_seat)
            if logical == self._local_seat:
                label.setText(f"{char_names[logical]}: HUMAN")
                label.setStyleSheet(
                    "QLabel { background-color: #88ccff; color: black; "
                    "padding: 2px 8px; border-radius: 3px; }"
                )
            else:
                label.setText(f"{char_names[logical]}: BEN")
                label.setStyleSheet(
                    "QLabel { background-color: #d0d0e0; color: black; "
                    "padding: 2px 8px; border-radius: 3px; }"
                )

    def _on_card_selected(self, seat: Seat, card: Card):
        self.card_played.emit(seat, card)

    def set_board(self, board: BoardState):
        self.board = board
        self.declarer = None
        self.dummy = None
        # Rotation is owned by _local_seat and persists across deals.
        self.is_play_phase = False

        self.dealer_label.setText(f"Dealer: {board.dealer.to_char()}")
        vuln_map = {Vulnerability.NONE: 'None', Vulnerability.NS: 'N-S', Vulnerability.EW: 'E-W', Vulnerability.BOTH: 'Both'}
        self.vuln_label.setText(f"Vul.: {vuln_map[board.vulnerability]}")

        # Repaint the per-position labels based on _local_seat. Keeps
        # "<seat char>: HUMAN" on the local user's seat regardless of which
        # physical position they sit in after rotation.
        self._refresh_seat_labels()

        # During bidding only the local user's hand is shown face up. Each
        # physical widget displays the logical seat dictated by rotation.
        local_physical = self._display_seat(self._local_seat)
        for physical_seat in Seat:
            logical = self._logical_seat(physical_seat)
            widget = self.hand_widgets[physical_seat]
            widget.logical_seat = logical
            widget.set_player_info(is_human=(logical == self._local_seat))
            if physical_seat == local_physical and logical in board.hands:
                widget.setVisible(True)
                widget.set_hand(board.hands[logical], face_up=True)
            else:
                widget.setVisible(False)
                widget.clear()

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

        local = self._local_seat
        char_names = {Seat.NORTH: 'N', Seat.EAST: 'E',
                      Seat.SOUTH: 'S', Seat.WEST: 'W'}

        # Per-widget role flags. is_human marks the *local* user's seat
        # only — defenders' AI hands keep BEN labels regardless of which
        # team won the contract. This is the fix for the East-guest bug
        # where the old NS-only `is_hum` ignored the local seat entirely.
        for physical_seat in Seat:
            logical = self._logical_seat(physical_seat)
            self.hand_widgets[physical_seat].logical_seat = logical
            self.hand_widgets[physical_seat].set_player_info(
                is_human=(logical == local),
                is_dummy=(logical == self.dummy),
                is_declarer=(logical == self.declarer),
            )

        # Always show the local user's hand at the bottom, face up.
        local_widget = self.hand_widgets[self._display_seat(local)]
        local_widget.setVisible(True)
        if local in self.board.hands:
            local_widget.set_hand(self.board.hands[local], face_up=True)

        # ALWAYS reveal dummy face up (bridge rule).
        dummy_widget = self.hand_widgets[self._display_seat(self.dummy)]
        if self.dummy in self.board.hands:
            dummy_widget.set_hand(self.board.hands[self.dummy], face_up=True)
            dummy_widget.setVisible(True)

        # When the local player controls the declarer side (single-player
        # partnership control, or any seat where they ARE declarer/dummy),
        # show declarer face up too. Network defenders never see declarer
        # face up. main_window flips human_controls_declarer before calling
        # us so we can read it without knowing about player types.
        if self.human_controls_declarer and self.declarer in self.board.hands:
            dec_widget = self.hand_widgets[self._display_seat(self.declarer)]
            dec_widget.set_hand(self.board.hands[self.declarer], face_up=True)
            dec_widget.setVisible(True)

        # Per-position labels — derive from the LOGICAL seat at each
        # physical position so a guest at East sees their own seat at the
        # bottom labelled with the correct role (Declarer / HUMAN / etc.).
        labels = {
            Seat.NORTH: self.north_label,
            Seat.EAST: self.east_label,
            Seat.SOUTH: self.south_label,
            Seat.WEST: self.west_label,
        }
        styles = {
            'declarer': "QLabel { background-color: #88ff88; color: black; padding: 3px 8px; border-radius: 3px; }",
            'dummy':    "QLabel { background-color: #ff6688; color: black; padding: 3px 8px; border-radius: 3px; }",
            'human':    "QLabel { background-color: #88ccff; color: black; padding: 2px 8px; border-radius: 3px; }",
            'ai':       "QLabel { background-color: #d0d0e0; color: black; padding: 3px 8px; border-radius: 3px; }",
        }
        for physical_seat, label in labels.items():
            logical = self._logical_seat(physical_seat)
            char = char_names[logical]
            if logical == self.declarer and logical == local:
                label.setText(f"{char}: Declarer (you)")
                label.setStyleSheet(styles['declarer'])
            elif logical == self.declarer:
                label.setText(f"{char}: Declarer")
                label.setStyleSheet(styles['declarer'])
            elif logical == self.dummy and logical == local:
                label.setText(f"{char}: Dummy (you)")
                label.setStyleSheet(styles['dummy'])
            elif logical == self.dummy:
                label.setText(f"{char}: Dummy")
                label.setStyleSheet(styles['dummy'])
            elif logical == local:
                label.setText(f"{char}: HUMAN")
                label.setStyleSheet(styles['human'])
            else:
                label.setText(f"{char}: BEN")
                label.setStyleSheet(styles['ai'])

        self.contract_label.setText(f"{contract.declarer.to_char()} {contract.to_str()}")
        self.trick_area.set_show_bidding(False)
        self.tricks_panel.setVisible(True)

    def set_hand_visible(self, seat: Seat, visible: bool):
        if self.board and seat in self.board.hands:
            ds = self._display_seat(seat)
            self.hand_widgets[ds].setVisible(visible)
            if visible:
                self.hand_widgets[ds].set_hand(self.board.hands[seat], face_up=True)

    def set_hand_selectable(self, seat: Seat, selectable: bool, lead_suit: Optional[Suit] = None):
        ds = self._display_seat(seat)
        self.hand_widgets[ds].set_selectable(selectable)
        if selectable:
            self.hand_widgets[ds].highlight_legal(lead_suit)

    def play_card_to_trick(self, seat: Seat, card: Card, is_winner: bool = False):
        ds = self._display_seat(seat)
        self.trick_area.play_card(ds, card, is_winner)
        self.hand_widgets[ds].remove_card(card)

    def show_trick_winner(self, winner: Seat):
        self.trick_area.set_winner(self._display_seat(winner))

    def clear_trick(self):
        self.trick_area.clear_trick()

    def update_tricks(self, dec_tricks: int, def_tricks: int):
        self.tricks_label.setText(f"{dec_tricks} : {def_tricks}")

    def set_contract(self, contract_str: str, declarer: str):
        self.contract_label.setText(f"{declarer} {contract_str}")
