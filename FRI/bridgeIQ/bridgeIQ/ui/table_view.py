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
    QPixmap, QImage, QRadialGradient
)
import os

from backend.models import (
    BoardState, Card, Hand, Seat, Suit, Trick, Vulnerability, Contract, Rank,
    PlayerType
)
from typing import Optional, List, Dict


# BridgeIQ color scheme — matched to pokerIQ for a consistent look across the
# two games: near-black background, muted dark-green felt with a brown rail,
# gold accents, light "ink" text. (pokerIQ palette: bg #0c1117, felt #15543a,
# gold #d9b25b, ink #eef3f7, card-red #d23b3b, accent #58a6ff.)
COLORS = {
    'background': '#0c1117',     # pokerIQ --bg (near-black)
    'table_green': '#15543a',    # pokerIQ --felt (muted dark green)
    'felt_hi': '#1d7a52',        # brighter felt centre (radial-gradient glow)
    'felt_rail': '#4a3420',      # pokerIQ --rail (warm brown table edge)
    'panel_teal': '#0d141c',     # pokerIQ panel background
    'card_back': '#5e1414',      # pokerIQ card-back red
    'card_border': '#d9b25b',    # pokerIQ --gold
    'card_face': '#f6f7f9',      # pokerIQ card face
    'text_white': '#eef3f7',     # pokerIQ --ink
    'text_muted': '#9aa7b4',     # pokerIQ --muted
    'text_black': '#1a1f29',     # pokerIQ --card-dark (text on light)
    'gold': '#d9b25b',           # pokerIQ --gold accent
    'accent': '#58a6ff',         # pokerIQ --accent (hero/turn blue)
    'pos': '#3fb950',            # pokerIQ --pos
    'vuln_red': '#f85149',       # pokerIQ --neg
    'highlight': '#d9b25b',      # pokerIQ gold (turn glow)
    'button_bg': '#2b3a4d',      # pokerIQ summary-button
    'button_text': '#eef3f7',
    'selectable_border': '#d9b25b',  # gold = your turn (pokerIQ feel)
    'line': '#2c4a3a',           # subtle warm green-grey panel border
}

# Card dimensions - sized to fill 1920x1080 screen.
# Bumped from 140×198 → 160×224 so the south human hand reads more
# easily and the dummy 4-row layout has bigger pip / rank text.
CARD_WIDTH = 160
CARD_HEIGHT = 224
CARD_OVERLAP = 84  # How much cards overlap (shows ~76px per card — proportional to 75/140 before)
# Inter-suit gap. We earlier had to dial this down to 55 because the
# south row also carried a 140-px right spacer which pushed the fan
# off-screen at SUIT_GAP=100. The spacer is now gone (south_row uses
# stretches on both sides), so we can restore a visibly clearer gap.
# 105 lands the 13-card fan at ~1402 px which fits comfortably with
# the south label (140) on a 1920-wide window.
SUIT_GAP = 105  # Extra gap between suits — creates clear visible gap


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
            # The deck images live alongside the UI module — moved
            # here from the deleted FRI/benBridge/ben/src/tmcgui/
            # tree during the rename to bridgeIQ.
            here = os.path.dirname(os.path.abspath(__file__))
            candidate = os.path.join(here, 'assets', 'deck',
                                     'width 100')
            cls._images_dir = os.path.normpath(candidate)
        return cls._images_dir

    @classmethod
    def _get_card_pixmap(cls, card: 'Card') -> Optional[QPixmap]:
        """Load and cache a card image.

        The bundled deck (deckofcards, 4-color) already has diamonds in
        blue and clubs in green, so no runtime recoloring is needed. The
        ``legacy_colors`` preference still recolors blue→red diamonds /
        green→black clubs on the fly for users who want a traditional
        2-color look.
        """
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

            # Optional: legacy 2-color override.  The bundled images are
            # already 4-color, so when the user asks for legacy we have
            # to invert the recolor (blue→red diamonds, green→black
            # clubs).  Defaults to 4-color (no recolor pass).
            from backend.config import get_config_manager
            try:
                legacy = get_config_manager().config.preferences.legacy_colors
            except Exception:
                legacy = False
            if legacy:
                if card.suit == Suit.DIAMONDS:
                    cls._recolor_blue_to_red(img)
                elif card.suit == Suit.CLUBS:
                    cls._recolor_green_to_black(img)

            cls._image_cache[key] = QPixmap.fromImage(img)

        return cls._image_cache.get(key)

    @classmethod
    def _get_back_pixmap(cls) -> QPixmap:
        if cls._back_pixmap is None:
            # The bundled deck ships its back image as back.png.  Older
            # forks of this code looked for blue_back.png; we still fall
            # back to that name so a custom replacement deck can use
            # either filename.
            for filename in ('back.png', 'blue_back.png'):
                path = os.path.join(cls._get_images_dir(), filename)
                if os.path.exists(path):
                    img = QImage(path).scaled(
                        CARD_WIDTH, CARD_HEIGHT,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    cls._back_pixmap = QPixmap.fromImage(img)
                    break
            else:
                cls._back_pixmap = QPixmap(CARD_WIDTH, CARD_HEIGHT)
                cls._back_pixmap.fill(QColor('#1a3a8c'))
        return cls._back_pixmap

    @staticmethod
    def _recolor_blue_to_red(img: QImage):
        """Re-tint blue diamond pips/text → red, for legacy 2-color mode.

        The bundled deck has diamonds drawn in vivid blue (~#0000cc).
        Anything noticeably more blue than red/green that isn't pure
        background gets shifted to red while preserving brightness.
        """
        for y in range(img.height()):
            for x in range(img.width()):
                px = img.pixelColor(x, y)
                r, g, b, a = px.red(), px.green(), px.blue(), px.alpha()
                if a < 10:
                    continue
                if b > 40 and b > r * 1.3 and b > g * 1.3 and r + g + b < 650:
                    lum = (r + g + b) / 3.0
                    f = (255 - lum) / 255.0
                    nr = int(220 * f + lum * (1 - f))
                    ng = int(20 * f + lum * (1 - f))
                    nb = int(20 * f + lum * (1 - f))
                    img.setPixelColor(x, y, QColor(nr, ng, nb, a))

    @staticmethod
    def _recolor_green_to_black(img: QImage):
        """Re-tint green club pips/text → black, for legacy 2-color mode."""
        for y in range(img.height()):
            for x in range(img.width()):
                px = img.pixelColor(x, y)
                r, g, b, a = px.red(), px.green(), px.blue(), px.alpha()
                if a < 10:
                    continue
                if g > 40 and g > r * 1.3 and g > b * 1.3 and r + g + b < 650:
                    img.setPixelColor(x, y, QColor(0, 0, 0, a))

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
        # Q-Plus-style "won a trick" badge — drawn as a red outline
        # in paintEvent. Set after play completes so the user can see
        # at a glance which 13 cards picked up the 13 tricks.
        self.is_trick_winner = False
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

    def set_trick_winner(self, is_winner: bool):
        """Mark / unmark this card as a trick winner. The red outline
        is drawn in paintEvent so it sits on top of the card image."""
        if self.is_trick_winner == is_winner:
            return
        self.is_trick_winner = is_winner
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

            # Q-Plus-style trick-winner outline. Drawn LAST so it
            # sits on top of selectable/hover overlays — at end of
            # hand the user wants to see which cards took tricks at
            # a glance, regardless of any other state.
            if self.is_trick_winner:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(220, 30, 30), 3))
                painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)


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
        # When true, lay out the hand as 4 vertical columns of cards
        # (one per suit, sorted high-to-low). Used for the opposing-side
        # dummy so the human-as-defender can read it like a real table
        # dummy. Set via set_four_column_layout(); ignored unless face_up.
        self.four_column_layout = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Label — bumped to 18pt and widened so the longer role badges
        # ("S / Declarer", "N / Dummy") never get clipped to "Dumr" /
        # "Declar". The label sizes itself to its content; we just stop
        # the parent layout from squeezing it below the natural width.
        self.label = QLabel()
        self.label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 200 px easily fits "S / Declarer" + the 10-px horizontal padding.
        self.label.setMinimumWidth(200)
        # Don't elide; if the label is forced narrower it will overflow
        # rather than display "...".
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
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
            # Also propagate the fan width up to the outer widget. With
            # absolute-positioned card children, Qt can't infer a
            # sizeHint for cards_container, so the parent layout would
            # happily allocate it less than fan_width — which clipped
            # the rightmost card on a typical 1920-wide window. Setting
            # the outer widget's minimum width explicitly forces the
            # parent layout to honour the full fan.
            self.setMinimumWidth(fan_width)
        layout.addWidget(self.cards_container)

    def _update_label(self):
        if self.is_dummy:
            text = f"{self.seat.to_char()} / Dummy"
            style = "background-color: #14202c; color: #3fb950; padding: 3px 10px; border-radius: 4px;"
        elif self.is_declarer:
            text = f"{self.seat.to_char()} / Declarer"
            style = "background-color: #14202c; color: #d9b25b; padding: 3px 10px; border-radius: 4px;"
        elif self.is_human:
            # Show HUMAN label for human player
            text = f"{self.seat.to_char()}: HUMAN"
            style = "background-color: #14202c; color: #58a6ff; padding: 3px 10px; border-radius: 4px;"
        else:
            text = f"{self.seat.to_char()}: biq"
            style = "background-color: #14202c; color: #eef3f7; padding: 3px 10px; border-radius: 4px;"
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

    def set_trick_winners(self, winning_cards):
        """Mark the cards in ``winning_cards`` (any iterable of Card
        instances) with a Q-Plus-style red trick-winner outline.
        Cards not in the set get the flag cleared, so calling this
        with an empty set is a clean reset.
        """
        # Build a tiny (suit, rank) lookup so equality works regardless
        # of whether the caller passed Card instances from a different
        # Hand snapshot.
        keys = set()
        for c in (winning_cards or []):
            try:
                keys.add((c.suit, c.rank))
            except AttributeError:
                pass
        for cw in self.card_widgets:
            try:
                k = (cw.card.suit, cw.card.rank) if cw.card else None
            except AttributeError:
                k = None
            cw.set_trick_winner(k is not None and k in keys)

    def clear_trick_winners(self):
        """Strip every trick-winner highlight from this hand."""
        for cw in self.card_widgets:
            cw.set_trick_winner(False)

    def set_four_column_layout(self, enabled: bool):
        """Switch between horizontal-fan and 4-column dummy display."""
        if self.four_column_layout == enabled:
            return
        self.four_column_layout = enabled
        if self.hand:
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

        if self.four_column_layout and self.face_up:
            self._rebuild_cards_four_columns()
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

    def _rebuild_cards_four_columns(self):
        """4-row dummy layout: one horizontal row per suit, sorted high-to-low.

        Mirrors how a real-table dummy is laid down: cards in each suit
        spread horizontally with mild overlap, suits stacked vertically.
        Each row above the bottom one is partially occluded by the row
        below, but the rank+suit corner of every card always shows. The
        method name kept "four_columns" for backwards compatibility with
        callers that flip the layout flag.
        """
        # Horizontal step inside a row — borrowed from the regular fan
        # so the look is familiar.
        h_step = CARD_WIDTH - CARD_OVERLAP  # 65 px
        # Vertical step between rows — exposes the top corner of each
        # row above the bottom one. 60 keeps the rank+suit visible
        # without burying the next row's index too far down.
        row_v_step = 60

        # Group cards by suit; sort each suit high-to-low (Rank is an
        # IntEnum where ACE=0 < TWO=12 — smaller value = higher rank).
        by_suit: Dict[Suit, List[Card]] = {s: [] for s in
                                           (Suit.SPADES, Suit.HEARTS,
                                            Suit.DIAMONDS, Suit.CLUBS)}
        for c in self.hand.cards:
            if c.suit in by_suit:
                by_suit[c.suit].append(c)
        for s in by_suit:
            by_suit[s].sort(key=lambda c: c.rank)

        suits_order = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]

        # Lay out the rows: row 0 (spades) sits at y=0 and is partly
        # covered by row 1, etc. The last row is fully visible.
        max_cards_in_row = max((len(by_suit[s]) for s in suits_order),
                               default=0)
        for row_idx, suit in enumerate(suits_order):
            cards = by_suit[suit]
            y = row_idx * row_v_step
            x = 0
            for card in cards:
                cw = CardWidget(card, True, self.cards_container)
                cw.set_selectable(self.selectable)
                cw.card_clicked.connect(
                    lambda c, s=self.logical_seat: self.card_selected.emit(s, c)
                )
                cw.move(int(x), int(y))
                cw.show()
                cw.raise_()
                self.card_widgets.append(cw)
                x += h_step

        # Container size: max row width + total stacked height.
        total_w = (CARD_WIDTH + max(0, max_cards_in_row - 1) * h_step
                   if max_cards_in_row > 0 else CARD_WIDTH)
        total_h = (len(suits_order) - 1) * row_v_step + CARD_HEIGHT
        self.cards_container.setMinimumSize(total_w, total_h + 10)
        self.cards_container.resize(total_w, total_h + 10)

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
    """Green table center with played cards at compass positions.

    The whole thing — green box, played cards, arrows — SCALES to the
    size the layout gives the widget, so on a tall window the cards are
    large and on a cramped 1080 they shrink to fit instead of being
    clipped. Geometry is recomputed in resizeEvent against a fixed
    DESIGN size (the look at scale 1.0); a min-scale floor keeps the
    bidding overlay readable and stops it collapsing to nothing.
    """

    # Design (scale = 1.0) geometry. The widget covers the OUTER rect
    # (green + arrow band); the green rounded rect is painted inset so
    # the band stays transparent and the arrows sit outside the green.
    DESIGN_BAND   = 44        # arrow band around the green box
    DESIGN_GREEN_W = 460
    DESIGN_GREEN_H = 360
    DESIGN_CARD_W = 130
    DESIGN_CARD_H = 182
    DESIGN_CARD_INSET = 18    # gap between a played card and the green border
    DESIGN_CHEVRON = 40
    DESIGN_ARROW_GAP = 4
    AREA_WIDTH  = DESIGN_GREEN_W + 2 * DESIGN_BAND
    AREA_HEIGHT = DESIGN_GREEN_H + 2 * DESIGN_BAND
    MIN_SCALE = 0.74         # floor — keeps the green ≥ the bidding overlay
    MAX_SCALE = 1.0          # never grow the cards past the design size
    BID_W, BID_H = 320, 260  # bidding overlay (fixed; centred in the green)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(round(self.AREA_WIDTH * self.MIN_SCALE),
                            round(self.AREA_HEIGHT * self.MIN_SCALE))
        # Take the vertical space the layout offers (so a taller window
        # gives bigger cards); keep a preferred width so the side columns
        # aren't squeezed.
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Expanding)
        # Transparent background — the green box is rendered in
        # paintEvent inside an inset rect so the outer band where
        # the compass arrows live shows the page colour behind it.
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.played_cards: Dict[Seat, Card] = {}
        self.winner: Optional[Seat] = None
        self.card_widgets: Dict[Seat, CardWidget] = {}
        self.show_bidding = False
        self.auction = []
        self.dealer = Seat.NORTH
        self.bidding_status = ""
        self._green_rect = QRect(self.DESIGN_BAND, self.DESIGN_BAND,
                                 self.DESIGN_GREEN_W, self.DESIGN_GREEN_H)
        self._setup_ui()

    def sizeHint(self) -> QSize:
        return QSize(self.AREA_WIDTH, self.AREA_HEIGHT)

    def _scale(self) -> float:
        s = min(self.width() / self.AREA_WIDTH,
                self.height() / self.AREA_HEIGHT)
        return max(self.MIN_SCALE, min(self.MAX_SCALE, s))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        """Recompute the green box + every child's geometry for the
        current widget size."""
        s = self._scale()
        band = self.DESIGN_BAND * s
        gw, gh = self.DESIGN_GREEN_W * s, self.DESIGN_GREEN_H * s
        area_w, area_h = gw + 2 * band, gh + 2 * band
        ox = (self.width() - area_w) / 2.0
        oy = (self.height() - area_h) / 2.0
        green = QRect(round(ox + band), round(oy + band), round(gw), round(gh))
        self._green_rect = green
        cx, cy = green.center().x(), green.center().y()
        cw, ch = self.DESIGN_CARD_W * s, self.DESIGN_CARD_H * s
        inset = self.DESIGN_CARD_INSET * s

        card_geom = {
            Seat.NORTH: (cx - cw / 2, green.top() + inset),
            Seat.SOUTH: (cx - cw / 2, green.bottom() - inset - ch),
            Seat.WEST:  (green.left() + inset, cy - ch / 2),
            Seat.EAST:  (green.right() - inset - cw, cy - ch / 2),
        }
        for seat, (x, y) in card_geom.items():
            w = self.card_widgets.get(seat)
            if w is not None:
                w.setFixedSize(round(cw), round(ch))
                w.move(round(x), round(y))

        chev = self.DESIGN_CHEVRON * s
        gap = self.DESIGN_ARROW_GAP * s
        arrow_geom = {
            'N': (cx - chev / 2, green.top() - gap - chev),
            'S': (cx - chev / 2, green.bottom() + gap),
            'W': (green.left() - gap - chev, cy - chev / 2),
            'E': (green.right() + gap, cy - chev / 2),
        }
        for d, (x, y) in arrow_geom.items():
            a = getattr(self, "arrows", {}).get(d)
            if a is not None:
                a.setFixedSize(round(chev), round(chev))
                a.move(round(x), round(y))

        if getattr(self, "bidding_widget", None) is not None:
            self.bidding_widget.move(cx - self.BID_W // 2, cy - self.BID_H // 2)

    def paintEvent(self, event):
        """Paint the green box as an inset rounded rectangle, sized and
        centred for the current scale (computed in _relayout)."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Brown rail + a radial-gradient felt (brighter at centre) for the
        # warm pokerIQ table glow instead of a flat green.
        g = self._green_rect
        grad = QRadialGradient(float(g.center().x()), float(g.center().y()),
                               float(max(g.width(), g.height())) / 1.4)
        grad.setColorAt(0.0, QColor(COLORS['felt_hi']))
        grad.setColorAt(1.0, QColor(COLORS['table_green']))
        painter.setPen(QPen(QColor(COLORS['felt_rail']), 7))   # brown rail (pokerIQ)
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(g, 14, 14)

    def _setup_ui(self):
        # Create the child widgets; their geometry is set by _relayout
        # (called on every resize), so positions here are placeholders.
        for seat in Seat:
            cw_widget = CardWidget(parent=self)
            cw_widget.setVisible(False)
            self.card_widgets[seat] = cw_widget

        # Keep references keyed by direction so set_vulnerability can
        # repaint the matching pair (NS or EW) pink.
        self.arrows: Dict[str, DirectionArrow] = {}
        for d in ('N', 'S', 'W', 'E'):
            self.arrows[d] = DirectionArrow(d, self)

        # Bidding table overlay — fixed size, centred on the green box.
        self.bidding_widget = BiddingTableWidget(self)
        self.bidding_widget.setFixedSize(self.BID_W, self.BID_H)

        self._relayout()

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

    def set_vulnerability(self, vuln: 'Vulnerability'):
        """Paint each compass arrow pink for the vulnerable pair(s).

        NS vulnerable → N + S triangles pink.
        EW vulnerable → E + W triangles pink.
        Both vulnerable → all four pink.
        None → all four grey.
        """
        ns_vul = vuln in (Vulnerability.NS, Vulnerability.BOTH)
        ew_vul = vuln in (Vulnerability.EW, Vulnerability.BOTH)
        vul_by_dir = {'N': ns_vul, 'S': ns_vul, 'E': ew_vul, 'W': ew_vul}
        for d, arrow in self.arrows.items():
            arrow.set_vulnerable(vul_by_dir.get(d, False))


class DirectionArrow(QWidget):
    def __init__(self, direction: str, parent=None):
        super().__init__(parent)
        self.direction = direction
        # Default size — callers (TrickAreaWidget) override via setFixedSize
        # if they want bigger chevrons.
        self.setFixedSize(40, 40)
        # Vulnerability flag — when True the triangle paints pink
        # instead of grey, matching the Q-Plus reference where the
        # compass marker for a vulnerable seat is highlighted.
        self._vulnerable = False

    def set_vulnerable(self, vulnerable: bool):
        if self._vulnerable != bool(vulnerable):
            self._vulnerable = bool(vulnerable)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Grey when not vulnerable; pink when this seat is vulnerable.
        # Letters stay dark for contrast against either body colour.
        if self._vulnerable:
            TRI_COLOR = QColor('#ff9aa8')   # soft pink (Q-Plus reference)
        else:
            TRI_COLOR = QColor('#9a9a9a')
        LETTER_COLOR = QColor('#202020')
        painter.setPen(QPen(TRI_COLOR, 2))
        painter.setBrush(QBrush(TRI_COLOR))

        w, h = self.width(), self.height()
        pts = {
            'N': [QPoint(w//2, 3), QPoint(w-3, h-3), QPoint(3, h-3)],
            'S': [QPoint(w//2, h-3), QPoint(3, 3), QPoint(w-3, 3)],
            'E': [QPoint(w-3, h//2), QPoint(3, 3), QPoint(3, h-3)],
            'W': [QPoint(3, h//2), QPoint(w-3, 3), QPoint(w-3, h-3)],
        }
        painter.drawPolygon(QPolygon(pts.get(self.direction, [])))

        # N/E/S/W letter centred on the triangle's CENTROID, not on
        # the widget rect. Each triangle has its apex at one edge of
        # the rect and its base at the opposite edge — so the
        # triangle's visual mass is offset from the rect's geometric
        # centre, and AlignCenter drew the letter against the flat
        # side instead of in the middle of the triangle. The centroid
        # of a triangle is the average of its three vertices.
        painter.setPen(LETTER_COLOR)
        font_pt = max(10, int(min(w, h) * 0.36))
        painter.setFont(QFont("Arial", font_pt, QFont.Weight.Bold))
        verts = pts.get(self.direction, [])
        if verts:
            cx = sum(p.x() for p in verts) // 3
            cy = sum(p.y() for p in verts) // 3
            # drawText at a point uses the BASELINE — shift up by ~0.3 of
            # the font size so the glyph looks centred on (cx, cy).
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.direction)
            th = fm.ascent()
            painter.drawText(cx - tw // 2, cy + th // 2 - 1, self.direction)


class BiddingTableWidget(QFrame):
    """Bidding table overlay in center — Q-Plus style.

    Columns are reordered so the DEALER's column is on the left, and
    bidding fills in left-to-right one row at a time. The seat that
    is on the spot to bid next gets a "?" cell. This is the format
    Q-Plus Bridge uses (and is much easier to read than the fixed
    N/E/S/W version we started with).
    """

    # Cell sizing kept here so set_auction can reproduce it without
    # the magic numbers drifting between the header row and the body.
    _CELL_W = 70
    _CELL_H = 40
    _HEADER_FS = 18
    _CELL_FS = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #f0f0f0; border: 1px solid #555;"
            " border-radius: 6px; }"
        )
        self.setMinimumSize(260, 180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header row — populated lazily in set_auction so the column
        # order can rotate to put the dealer first.
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(2)
        layout.addLayout(self.header_layout)

        # Body grid (one HBoxLayout per row of 4 cells).
        self.bids_widget = QWidget()
        self.bids_layout = QVBoxLayout(self.bids_widget)
        self.bids_layout.setContentsMargins(0, 0, 0, 0)
        self.bids_layout.setSpacing(2)
        layout.addWidget(self.bids_widget)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.status_label)

        # Render an empty header so the widget looks right pre-deal.
        self._render_header(Seat.NORTH)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_header(self, dealer: Seat):
        """Render the column header N/E/S/W rotated so that `dealer`
        is the first column (Q-Plus convention)."""
        self._clear_layout(self.header_layout)
        seat_chars = ['N', 'E', 'S', 'W']
        for offset in range(4):
            seat_char = seat_chars[(dealer.value + offset) % 4]
            lbl = QLabel(seat_char)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Arial", self._HEADER_FS, QFont.Weight.Bold))
            lbl.setFixedSize(self._CELL_W, self._CELL_H - 6)
            lbl.setStyleSheet(
                "background-color: #d8d8d8; color: #000;"
                " border: 1px solid #888; border-radius: 3px;"
            )
            self.header_layout.addWidget(lbl)

    def _make_cell(self, text: str, *, kind: str = 'bid',
                   suit=None) -> QLabel:
        """Build one bid cell with the right colour for its bid type."""
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Arial", self._CELL_FS,
                          QFont.Weight.Bold if kind != 'pad' else QFont.Weight.Normal))
        lbl.setFixedSize(self._CELL_W, self._CELL_H)
        if kind == 'pass':
            style = "color: #006400;"
        elif kind == 'double':
            style = "color: blue; font-weight: bold;"
        elif kind == 'redouble':
            style = "color: #00008B; font-weight: bold;"
        elif kind == 'suit' and suit is not None:
            from .styles import get_suit_color
            suit_names = {Suit.SPADES: 'spades', Suit.HEARTS: 'hearts',
                          Suit.DIAMONDS: 'diamonds', Suit.CLUBS: 'clubs'}
            color = get_suit_color(suit_names.get(suit, 'spades'))
            style = f"color: {color}; font-weight: bold;"
        elif kind == 'next':
            style = "color: #777; font-weight: bold;"
        elif kind == 'pad':
            style = "color: #888;"
        else:
            style = "color: #111;"
        lbl.setStyleSheet(
            "QLabel { background-color: #ffffff; border: 1px solid #bbb;"
            f" border-radius: 3px; padding: 2px; {style} }}"
        )
        return lbl

    def set_auction(self, auction, dealer: Seat):
        # Header rotates to put dealer first.
        self._render_header(dealer)

        # Clear body.
        self._clear_layout(self.bids_layout)

        # Build rows of four cells. Position 0 in each row is dealer's
        # seat — bids feed in dealer-first order.
        col = 0
        current_row = None

        def _new_row():
            nonlocal current_row
            current_row = QHBoxLayout()
            current_row.setSpacing(2)

        for bid in auction:
            if col == 0:
                _new_row()
            if getattr(bid, 'is_pass', False):
                cell = self._make_cell("Pass", kind='pass')
            elif getattr(bid, 'is_double', False):
                cell = self._make_cell("X", kind='double')
            elif getattr(bid, 'is_redouble', False):
                cell = self._make_cell("XX", kind='redouble')
            elif getattr(bid, 'suit', None) is not None:
                text = bid.symbol() if hasattr(bid, 'symbol') else str(bid)
                cell = self._make_cell(text, kind='suit', suit=bid.suit)
            else:
                text = bid.symbol() if hasattr(bid, 'symbol') else str(bid)
                cell = self._make_cell(text, kind='bid')
            current_row.addWidget(cell)
            col += 1
            if col >= 4:
                self.bids_layout.addLayout(current_row)
                current_row = None
                col = 0

        # Mark the next bidder with a "?" placeholder cell, then pad
        # any remaining cells in the row with empty placeholders so
        # the grid stays rectangular.
        if not auction and col == 0:
            _new_row()
        if col == 0 and auction:
            # New row will only be created if we still want to show "?"
            _new_row()
        # We still want to show "?" cell for the seat that's about to act.
        if current_row is not None or not auction:
            if current_row is None:
                _new_row()
            current_row.addWidget(self._make_cell("?", kind='next'))
            col += 1
            while col < 4:
                current_row.addWidget(self._make_cell("", kind='pad'))
                col += 1
            self.bids_layout.addLayout(current_row)

    def set_status(self, text: str):
        self.status_label.setText(text)


class InfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['panel_teal']}; border: 1px solid #243447; border-radius: 4px; }}
            QLabel {{ color: {COLORS['text_white']}; }}
        """)


class SeatInferenceBox(QFrame):
    """Wbridge5-style per-seat inference box.

    Shows the seat name, HCP range, and per-suit length range
    (e.g. ♠ 0..2, ♥ 0..7 …). Tooltips on hover display the
    natural-language reasoning that produced each constraint.

    Wired from MainWindow with a backend.auction_inference
    SeatConstraints object (or None to clear).
    """

    _SUIT_GLYPH = {0: "♠", 1: "♥", 2: "♦", 3: "♣"}
    _SUIT_COLOR = {0: "#101010", 1: "#c01010",
                   2: "#c01010", 3: "#101010"}

    def __init__(self, seat, label_text: str, parent=None):
        super().__init__(parent)
        self.seat = seat
        self.setStyleSheet("""
            QFrame {
                background-color: #f4f4ee;
                border: 1px solid #8a8a82;
                border-radius: 3px;
            }
            QLabel { color: #111; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)
        # Header
        self.name_label = QLabel(label_text)
        self.name_label.setFont(QFont("Sans Serif", 10,
                                      QFont.Weight.Bold))
        layout.addWidget(self.name_label)
        # HCP line
        self.hcp_label = QLabel("Points: —")
        self.hcp_label.setFont(QFont("Sans Serif", 9))
        layout.addWidget(self.hcp_label)
        # 4 suit lines
        self.suit_labels = {}
        for suit_val in (0, 1, 2, 3):
            lbl = QLabel(f"{self._SUIT_GLYPH[suit_val]} —")
            lbl.setFont(QFont("Sans Serif", 9))
            lbl.setStyleSheet(
                f"QLabel {{ color: {self._SUIT_COLOR[suit_val]}; }}")
            self.suit_labels[suit_val] = lbl
            layout.addWidget(lbl)
        self.setMinimumWidth(110)
        self.setMaximumWidth(140)

    _RANK_CHAR = "AKQJT98765432"  # rank.value → char (A=0)

    def update_from(self, constraints, known_hand=None,
                    played_cards=None):
        """Populate from a SeatConstraints (auction-inferred ranges)
        and optionally a known hand (for own / dummy displays).

        If `known_hand` is provided, the box shows exact HCP and
        suit lengths, plus the honors (A/K/Q/J) STILL in the hand
        (wbridge5-style: '♠ 4..4 AKJ').

        `played_cards`, when provided, is the set of cards already
        played by this seat — used to omit honors that have been
        played already.

        constraints == None clears everything to "—".
        """
        # Card isn't hashable as a dataclass; key by (suit_val, rank_val).
        played = {(c.suit.value, c.rank.value)
                  for c in (played_cards or [])}
        if known_hand is not None:
            # Exact data — own hand or dummy.
            hcp = 0
            length = {0: 0, 1: 0, 2: 0, 3: 0}
            honors = {0: [], 1: [], 2: [], 3: []}
            for c in known_hand.cards:
                if (c.suit.value, c.rank.value) in played:
                    continue  # already gone
                length[c.suit.value] += 1
                if c.rank.value <= 3:
                    hcp += (4, 3, 2, 1)[c.rank.value]
                    honors[c.suit.value].append(c.rank.value)
            self.hcp_label.setText(f"Points: {hcp}")
            for suit_val in (0, 1, 2, 3):
                glyph = self._SUIT_GLYPH[suit_val]
                # Sort honors high to low (rank.value 0 = ace).
                honor_chars = "".join(
                    self._RANK_CHAR[r]
                    for r in sorted(honors[suit_val]))
                if honor_chars:
                    self.suit_labels[suit_val].setText(
                        f"{glyph} {length[suit_val]}  {honor_chars}")
                else:
                    self.suit_labels[suit_val].setText(
                        f"{glyph} {length[suit_val]}")
            self.setToolTip("Known exact hand (honors after length)")
            return
        if constraints is None:
            self.hcp_label.setText("Points: —")
            for suit_val in (0, 1, 2, 3):
                self.suit_labels[suit_val].setText(
                    f"{self._SUIT_GLYPH[suit_val]} —")
            self.setToolTip("")
            return
        # Auction-inferred ranges.
        lo, hi = constraints.hcp_min, constraints.hcp_max
        if (lo, hi) == (0, 37):
            self.hcp_label.setText("Points: —")
        elif lo == hi:
            self.hcp_label.setText(f"Points: {lo}")
        else:
            self.hcp_label.setText(f"Points: {lo}..{hi}")
        for suit_val in (0, 1, 2, 3):
            lo_s, hi_s = constraints.suit_len.get(suit_val, (0, 13))
            if (lo_s, hi_s) == (0, 13):
                txt = f"{self._SUIT_GLYPH[suit_val]} —"
            elif lo_s == hi_s:
                txt = f"{self._SUIT_GLYPH[suit_val]} {lo_s}"
            else:
                txt = f"{self._SUIT_GLYPH[suit_val]} {lo_s}..{hi_s}"
            self.suit_labels[suit_val].setText(txt)
        # Tooltip lists the reasoning chain — one bullet per
        # inference rule that fired for this seat.
        if constraints.reasons:
            tooltip = "Why:\n" + "\n".join(
                f"• {r}" for r in constraints.reasons)
            self.setToolTip(tooltip)
        else:
            self.setToolTip("")


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
        # Per-seat player type, so the seat labels can show a Q-Plus-style
        # icon (👤 local human / 🖥 local Computer / 🖧 networked Extern).
        # main_window pushes the real map via set_seat_types() whenever the
        # network player config changes; default is single-player (South
        # human, rest Computer).
        self._seat_types: Dict[Seat, PlayerType] = {
            s: (PlayerType.HUMAN if s == Seat.SOUTH else PlayerType.COMPUTER)
            for s in Seat
        }
        self._rotation_quarters: int = 0  # number of 90° steps applied
        self.is_play_phase = False
        # True once dummy is visible. setup_declarer_play() flips this
        # off when the opposing side declared so dummy stays hidden
        # until the human-side opening lead lands; main_window calls
        # reveal_dummy() after the opening lead is played.
        self.dummy_revealed = True

        # Warm radial-gradient backdrop (pokerIQ felt glow) instead of a flat
        # near-black fill, for a consistent look with pokerIQ.
        self.setStyleSheet(
            "TableView { background: qradialgradient(cx:0.5, cy:0.32,"
            " radius:1.1, fx:0.5, fy:0.32, stop:0 #16242e,"
            f" stop:0.75 {COLORS['background']}); }}")
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
        self.north_label = QLabel("N: biq")
        self.north_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.north_label.setStyleSheet("QLabel { background-color: #14202c; color: #eef3f7; padding: 2px 8px; border:1px solid #3fb950; border-radius: 4px; }")
        self.north_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.north_label.setFixedWidth(140)

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

        # Q-Plus visual: the N label sits centered directly above the
        # green table, not in the screen's top-left corner. Use an
        # invisible placeholder on the left matching the info panel's
        # width so the label centres over the trick area below.
        from PyQt6.QtWidgets import QSizePolicy
        # Pin the info_panel width so we can mirror it on the left.
        self.info_panel.setMinimumWidth(140)
        self.info_panel.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Preferred)
        north_spacer_left = QWidget()
        north_spacer_left.setFixedWidth(140)
        north_row.addWidget(north_spacer_left, alignment=Qt.AlignmentFlag.AlignTop)
        north_row.addStretch()
        # Stack N label above the N hand fan so the label appears
        # next to the top edge of the green table (where Q-Plus puts
        # the "N: Q-plus" tab).
        north_combo = QVBoxLayout()
        north_combo.setContentsMargins(0, 0, 0, 0)
        north_combo.setSpacing(2)
        north_combo.addWidget(self.north_label,
                              alignment=Qt.AlignmentFlag.AlignHCenter)
        north_combo.addWidget(self.hand_widgets[Seat.NORTH])
        north_row.addLayout(north_combo)
        north_row.addStretch()
        north_row.addWidget(self.info_panel, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(north_row)

        # Middle section with E/W areas and trick area.
        # Side columns are wrapped in QWidgets (not bare layouts) so we
        # can pin both to the same minimum width via _balance_side_columns
        # — without that, an empty W column + a wide 4-row dummy on E
        # pulled the trick area off-centre and the green felt landed in
        # the upper-left of the screen instead of the middle.
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        # Kept so the bid-info panel overlay can shift JUST this row (W/felt/E)
        # right of itself, without moving the bottom hand (which would push the
        # rightmost suit off-screen). See set_left_inset.
        self._middle_layout = middle_layout

        # West column
        self.west_column = QWidget()
        west_vbox = QVBoxLayout(self.west_column)
        west_vbox.setContentsMargins(0, 0, 0, 0)
        self.west_label = QLabel("W: biq")
        self.west_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        # 160 px easily fits "W: Declarer" / "E: Dummy" with the 8-px
        # horizontal padding. Was 70, which clipped both Declarer and
        # Dummy down to "D".
        self.west_label.setMinimumWidth(160)
        self.west_label.setStyleSheet("QLabel { background-color: #14202c; color: #eef3f7; padding: 3px 8px; border:1px solid #3fb950; border-radius: 4px; }")
        self.west_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        west_vbox.addStretch()
        # Q-Plus visual: W label floats next to the LEFT edge of the
        # green table. Put it in a horizontal sub-row beside the hand
        # widget rather than stacked above it — when W is dummy and
        # the hand widget gets allocated big vertical space (4-column
        # mode), the previous stacked layout squeezed the label to
        # zero height and "W: Dummy" disappeared.
        west_hbox = QHBoxLayout()
        west_hbox.setContentsMargins(0, 0, 0, 0)
        west_hbox.setSpacing(6)
        west_hbox.addStretch()
        west_hbox.addWidget(self.hand_widgets[Seat.WEST])
        west_hbox.addWidget(self.west_label,
                            alignment=Qt.AlignmentFlag.AlignVCenter)
        west_vbox.addLayout(west_hbox)
        self.hand_widgets[Seat.WEST].setVisible(False)  # Hidden by default
        # Per-seat inference box, placed UNDER the W label area —
        # shown during cardplay when W is opponent (hand hidden).
        # Mirrors wbridge5's per-seat info box positioning.
        self.west_inference_box = SeatInferenceBox(Seat.WEST, "West")
        self.west_inference_box.setVisible(False)
        west_inf_row = QHBoxLayout()
        west_inf_row.setContentsMargins(0, 0, 0, 0)
        west_inf_row.addStretch()
        west_inf_row.addWidget(self.west_inference_box)
        west_inf_row.addStretch()
        west_vbox.addLayout(west_inf_row)
        west_vbox.addStretch()
        middle_layout.addWidget(self.west_column, stretch=1)

        # Trick area in center - wrap in layouts to ensure proper centering.
        # The center column has stretch=0 so it stays at the trick area's
        # natural width and doesn't stretch asymmetrically; the side
        # columns absorb extra horizontal space equally (stretch=1 each).
        trick_container_widget = QWidget()
        # Expand vertically so the extra height a tall window gives the
        # middle row reaches the (Expanding) trick area inside.
        trick_container_widget.setSizePolicy(QSizePolicy.Policy.Preferred,
                                             QSizePolicy.Policy.Expanding)
        trick_container = QVBoxLayout(trick_container_widget)
        trick_container.setContentsMargins(0, 0, 0, 0)
        # Asymmetric stretches so the felt floats UP within
        # middle_layout — leaves a clear gap below the felt before
        # the S label/cards, keeping the bottom of the green table
        # from being visually crowded by the S fan.
        # The trick area now scales to the height it's given, so let it
        # FILL the middle column vertically (no centering stretches) and
        # just centre it horizontally. A taller window → a taller middle
        # → bigger cards; a cramped one → the felt shrinks to fit.
        trick_h_wrapper = QHBoxLayout()
        trick_h_wrapper.addStretch()
        self.trick_area = TrickAreaWidget()
        trick_h_wrapper.addWidget(self.trick_area)
        trick_h_wrapper.addStretch()
        trick_container.addLayout(trick_h_wrapper, stretch=1)
        middle_layout.addWidget(trick_container_widget, stretch=0)

        # East column
        self.east_column = QWidget()
        east_vbox = QVBoxLayout(self.east_column)
        east_vbox.setContentsMargins(0, 0, 0, 0)
        self.east_label = QLabel("E: biq")
        self.east_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        # See west_label note — 160 fits "Declarer" / "Dummy" cleanly.
        self.east_label.setMinimumWidth(160)
        self.east_label.setStyleSheet("QLabel { background-color: #14202c; color: #eef3f7; padding: 3px 8px; border:1px solid #3fb950; border-radius: 4px; }")
        self.east_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        east_vbox.addStretch()
        # Mirror of the W layout — label inside a horizontal sub-row,
        # placed to the LEFT of the hand widget so it sits next to
        # the green box even when E is dummy with a big 4-column fan.
        east_hbox = QHBoxLayout()
        east_hbox.setContentsMargins(0, 0, 0, 0)
        east_hbox.setSpacing(6)
        east_hbox.addWidget(self.east_label,
                            alignment=Qt.AlignmentFlag.AlignVCenter)
        east_hbox.addWidget(self.hand_widgets[Seat.EAST])
        east_hbox.addStretch()
        east_vbox.addLayout(east_hbox)
        self.hand_widgets[Seat.EAST].setVisible(False)  # Hidden by default
        # Per-seat inference box, mirror of the W placement.
        self.east_inference_box = SeatInferenceBox(Seat.EAST, "East")
        self.east_inference_box.setVisible(False)
        east_inf_row = QHBoxLayout()
        east_inf_row.setContentsMargins(0, 0, 0, 0)
        east_inf_row.addStretch()
        east_inf_row.addWidget(self.east_inference_box)
        east_inf_row.addStretch()
        east_vbox.addLayout(east_inf_row)
        east_vbox.addStretch()
        middle_layout.addWidget(self.east_column, stretch=1)

        layout.addLayout(middle_layout, stretch=1)

        # No fixed spacer here — the trick_container's add-stretch above
        # and below the green area already gives it natural breathing
        # room. A 100-px spacer here forced middle_layout to give back
        # 100 px on a 1080-tall window, which was enough to clip the
        # green area's bottom edge (and the S chevron with it). Letting
        # middle_layout claim that space restores the full trick area
        # and the south hand sits as low as the layout permits.

        # South area — two stacked rows:
        #   1. Label row: "S: HUMAN" centered on screen.
        #   2. Hand row: the 13-card fan, centered horizontally and
        #      pushed lower in the available vertical space via a
        #      stretch above it.

        self.south_label = QLabel("S: HUMAN")
        self.south_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.south_label.setStyleSheet("QLabel { background-color: #14202c; color: #58a6ff; padding: 2px 8px; border:1px solid #58a6ff; border-radius: 4px; }")
        self.south_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.south_label.setFixedWidth(140)

        self.hand_widgets[Seat.SOUTH].set_player_info(is_human=True)

        # Label row — symmetrically padded so the label is centered
        # on screen, not biased toward one side by the N/info_panel
        # block on the opposite row.
        south_label_row = QHBoxLayout()
        south_label_row.setContentsMargins(0, 0, 0, 0)
        south_label_row.addStretch()
        south_label_row.addWidget(self.south_label,
                                  alignment=Qt.AlignmentFlag.AlignHCenter)
        south_label_row.addStretch()
        layout.addLayout(south_label_row)

        # A small fixed gap below the label. The trick area (middle row)
        # is now the only EXPANDING region, so it claims all spare height
        # and scales up on a taller window; an expanding stretch here
        # would instead swallow that height and starve the felt.
        layout.addSpacing(16)

        # Hand row — the 13-card fan, centered.
        south_row = QHBoxLayout()
        south_row.setSpacing(0)
        south_row.setContentsMargins(0, 0, 0, 0)
        south_row.addStretch()
        south_row.addWidget(self.hand_widgets[Seat.SOUTH])
        south_row.addStretch()
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

    # Icon + display name + background per player type, Q-Plus style. The
    # local human's own seat reads "You"; networked seats get the 🖧 glyph
    # and a distinct tint so it's obvious at a glance who is remote.
    _TYPE_ICON = {
        PlayerType.HUMAN: "👤",
        PlayerType.COMPUTER: "🖥",
        PlayerType.EXTERNAL: "🖧",
    }
    # Seat-label TEXT colours on a dark chip (pokerIQ tones).
    _TYPE_BG = {
        PlayerType.HUMAN: "#58a6ff",     # local user — accent blue
        PlayerType.COMPUTER: "#eef3f7",  # local AI — ink
        PlayerType.EXTERNAL: "#3fb950",  # networked — green
    }

    def set_left_inset(self, px: int):
        """Shift ONLY the middle play row (W | felt | E) right by `px`, used
        while the bid-info panel overlay covers the top-left so the West label
        isn't clipped. The bottom hand row is untouched (insetting the whole
        table pushed the rightmost suit off-screen)."""
        lay = getattr(self, '_middle_layout', None)
        if lay is None:
            return
        m = lay.contentsMargins()
        lay.setContentsMargins(max(0, int(px)), m.top(), m.right(), m.bottom())

    def set_seat_types(self, mapping: Dict[Seat, PlayerType]):
        """Push the real per-seat player types (from the game controller /
        network controller). Repaints the seat labels with the right icons."""
        for s in Seat:
            if s in mapping and mapping[s] is not None:
                self._seat_types[s] = mapping[s]
        self._refresh_seat_labels()

    def _seat_label_markup(self, logical: Seat):
        """(text, stylesheet) for a seat label: '<char>: <icon> <who>'."""
        char = {Seat.NORTH: 'N', Seat.EAST: 'E',
                Seat.SOUTH: 'S', Seat.WEST: 'W'}[logical]
        ptype = self._seat_types.get(logical, PlayerType.COMPUTER)
        icon = self._TYPE_ICON.get(ptype, "🖥")
        if logical == self._local_seat and ptype == PlayerType.HUMAN:
            who = "You"
        else:
            who = {PlayerType.HUMAN: "Human",
                   PlayerType.COMPUTER: "Computer",
                   PlayerType.EXTERNAL: "Network"}.get(ptype, "Computer")
        fg = self._TYPE_BG.get(ptype, "#eef3f7")
        style = (f"QLabel {{ background-color: #14202c; color: {fg}; "
                 f"padding: 2px 8px; border-radius: 3px; }}")
        return f"{char}: {icon} {who}", style

    def _refresh_seat_labels(self):
        """Set the four position labels to identify the logical seat (and its
        player type) in each physical position. Called whenever rotation or
        the player-type map changes; downstream helpers (setup_declarer_play,
        set_board) are free to overwrite with role info afterwards."""
        labels = {
            Seat.NORTH: self.north_label,
            Seat.EAST: self.east_label,
            Seat.SOUTH: self.south_label,
            Seat.WEST: self.west_label,
        }
        for physical_seat, label in labels.items():
            logical = self._logical_seat(physical_seat)
            text, style = self._seat_label_markup(logical)
            label.setText(text)
            label.setStyleSheet(style)

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
        # Repaint the compass arrows: pink for whichever pair is
        # vulnerable on this board, grey otherwise.
        try:
            self.trick_area.set_vulnerability(board.vulnerability)
        except Exception:
            # The trick area is always set up before set_board, but
            # guard against a partial init during very early calls.
            pass

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
        # Clear any leftover "bidding finished" status from the previous
        # deal — otherwise the next board opens with the auction-complete
        # message showing before a single bid has been made.
        self.trick_area.set_bidding_status("")
        self.tricks_label.setText("0 : 0")
        self.contract_label.setText("")

        # Hide tricks during bidding
        self.tricks_panel.setVisible(False)

        # Centre the trick area between the side columns from the start
        # of the bidding phase, before any dummy widget changes its
        # natural width.
        self._balance_side_columns()

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

        # Dummy reveal: bridge rule says dummy is laid down AFTER the
        # opening lead has been played. We honour that strictly when
        # the opposing side declared (local user is on defense and
        # dummy is also opposing). When the local user's side declares
        # — including when the user IS dummy — dummy goes up at once,
        # since the user already needs the cards visible to plan declarer
        # play. main_window flips dummy_revealed back on via
        # reveal_dummy() once the opening lead lands.
        dummy_widget = self.hand_widgets[self._display_seat(self.dummy)]
        opposing_side_declared = (
            self.dummy != local and self.dummy != local.partner()
        )
        # Reset the layout flag on every (non-dummy) widget so a previous
        # deal where the dummy was at, say, East doesn't leave East stuck
        # in 4-column mode when the next deal puts dummy elsewhere.
        for hw in self.hand_widgets.values():
            if hw is not dummy_widget:
                hw.set_four_column_layout(False)
        dummy_widget.set_four_column_layout(opposing_side_declared)

        self.dummy_revealed = not opposing_side_declared
        if self.dummy_revealed and self.dummy in self.board.hands:
            dummy_widget.set_hand(self.board.hands[self.dummy], face_up=True)
            dummy_widget.setVisible(True)
        else:
            # Keep dummy hidden until the opening lead lands.
            dummy_widget.setVisible(False)
            dummy_widget.clear()

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
            'declarer': "QLabel { background-color: #14202c; color: #d9b25b; padding: 3px 8px; border-radius: 3px; }",
            'dummy':    "QLabel { background-color: #14202c; color: #3fb950; padding: 3px 8px; border-radius: 3px; }",
            'human':    "QLabel { background-color: #14202c; color: #58a6ff; padding: 2px 8px; border-radius: 3px; }",
            'ai':       "QLabel { background-color: #14202c; color: #eef3f7; padding: 3px 8px; border-radius: 3px; }",
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
                label.setText(f"{char}: biq")
                label.setStyleSheet(styles['ai'])

        self.contract_label.setText(f"{contract.declarer.to_char()} {contract.to_str()}")
        self.trick_area.set_show_bidding(False)
        self.tricks_panel.setVisible(True)

        # Side columns may have been resized by the dummy widget
        # switching into 4-column mode (or back). Sync them so the
        # trick area lands roughly in the centre of the window.
        self._balance_side_columns()

    def _balance_side_columns(self):
        """Pin the W and E columns to the same minimum width so the
        trick area stays roughly in the middle of the screen.

        Without this, an empty west column (declarer hidden) plus a
        wide 4-row dummy on east shoves the entire green-felt block
        into the upper-left of the window. We compute each column's
        natural sizeHint, pick the larger, and set both column
        widgets to that minimum. The trick area still has its own
        fixed width and gets centered between the two side columns
        by the existing addStretch wrappers.
        """
        try:
            w_hint = self.west_column.sizeHint().width()
            e_hint = self.east_column.sizeHint().width()
            target = max(w_hint, e_hint, 90)
            self.west_column.setMinimumWidth(target)
            self.east_column.setMinimumWidth(target)
        except Exception:
            pass

    def reveal_dummy(self):
        """Flip dummy face-up after the opening lead.

        No-op if dummy was already up (single-player hands where the
        user's side declared) or if the contract data isn't loaded yet.
        """
        if self.dummy_revealed or self.dummy is None or self.board is None:
            return
        self.dummy_revealed = True
        if self.dummy in self.board.hands:
            dummy_widget = self.hand_widgets[self._display_seat(self.dummy)]
            dummy_widget.set_hand(self.board.hands[self.dummy], face_up=True)
            dummy_widget.setVisible(True)
        # Re-balance side columns now that the dummy widget is sized.
        self._balance_side_columns()

    def face_up_seats(self) -> set:
        """Logical seats whose hand is currently shown face-up.

        Used by the instrumented (teaching) view to decide which hands
        it may render as exact cards vs. inference only. Reads the live
        widget state so it tracks dummy reveal, Show All, the local
        seat, and network reveals without separate bookkeeping.
        """
        out = set()
        for logical in Seat:
            try:
                w = self.hand_widgets[self._display_seat(logical)]
                # `not isHidden()` (the widget's own flag), NOT isVisible():
                # when the instrumented view is shown the table_view page is
                # hidden, which would make isVisible() False for every hand.
                if (not w.isHidden()) and getattr(w, "face_up", False):
                    out.add(logical)
            except (KeyError, AttributeError):
                continue
        return out

    def set_hand_visible(self, seat: Seat, visible: bool):
        # Re-balance side columns when an E or W hand toggles, so
        # showing the dummy doesn't shove the trick area off-centre.
        if self.board and seat in self.board.hands:
            ds = self._display_seat(seat)
            self.hand_widgets[ds].setVisible(visible)
            if ds in (Seat.EAST, Seat.WEST):
                self._balance_side_columns()
            if visible:
                self.hand_widgets[ds].set_hand(self.board.hands[seat], face_up=True)
                # Showing dummy via the network reveal path also flips
                # the deferred-reveal flag so subsequent reveal_dummy()
                # calls become no-ops.
                if seat == self.dummy:
                    self.dummy_revealed = True

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

    def show_end_of_hand_view(self, original_hands, tricks):
        """Q-Plus-style end-of-hand display: re-populate every hand
        with its original 13 cards face-up and outline the cards that
        won a trick in red. ``tricks`` is the list of completed Trick
        objects from BoardState. Idempotent — calling again with a
        different trick list just re-paints.

        Each Trick's ``winner`` seat is consulted; the winning card
        for the trick is the card the winning seat played in it,
        which is at index ``(winner.value - trick.leader.value) % 4``
        in ``trick.cards``.
        """
        if not original_hands:
            return
        # 1) Re-spread every seat's original 13-card hand face up so
        #    the user can see all of them at once. Both opponents'
        #    panels are unhidden — by design, end-of-hand shows the
        #    whole table.
        for physical_seat, widget in self.hand_widgets.items():
            try:
                widget.setVisible(True)
            except Exception:
                pass
            logical = self._logical_seat(physical_seat)
            hand = original_hands.get(logical)
            if hand is None:
                continue
            widget.set_hand(hand, face_up=True)
            widget.set_selectable(False)

        # 2) Compute the winning card per trick and apply the flag.
        winners_by_seat = {seat: [] for seat in self.hand_widgets}
        for tr in tricks or []:
            if (tr.winner is None or tr.leader is None
                    or not tr.cards):
                continue
            try:
                idx = (tr.winner.value - tr.leader.value) % 4
                if 0 <= idx < len(tr.cards):
                    winning_card = tr.cards[idx]
                    physical = self._display_seat(tr.winner)
                    if physical in winners_by_seat:
                        winners_by_seat[physical].append(winning_card)
            except Exception:
                continue

        for physical_seat, winning_cards in winners_by_seat.items():
            widget = self.hand_widgets.get(physical_seat)
            if widget is not None:
                widget.set_trick_winners(winning_cards)

        # 3) Clear the centre trick area so the table reads as a
        #    static post-mortem rather than the last live trick.
        try:
            self.trick_area.clear_trick()
        except Exception:
            pass

    def clear_end_of_hand_view(self):
        """Strip the post-play winner outlines. Called when a new
        hand is dealt so the next hand starts fresh."""
        for widget in self.hand_widgets.values():
            try:
                widget.clear_trick_winners()
            except Exception:
                pass

    def show_review_position(self, original_hands, tricks, cards_played: int):
        """Animate the table to the n-th card of the review.

        ``original_hands`` is the {Seat: Hand} snapshot from the start
        of play (MainWindow caches this as ``self.original_hands`` in
        ``_on_new_deal``). ``tricks`` is the list of completed Trick
        objects from the BoardState. ``cards_played`` is the linear
        index 0..52 into the play stream — 0 = start of play, 4 = end
        of trick 1, etc.

        Each invocation re-renders:
          * Every hand widget with its remaining cards at this point.
          * The centre trick area with whichever 0-3 cards are sitting
            on the table for the in-progress trick.
          * Winning-card outlines for tricks that have completed at or
            before this point (carry-over from end-of-hand view).
        """
        if not original_hands or not tricks:
            return
        cards_played = max(0, int(cards_played))

        # 1) Build "remaining cards" per logical seat by walking the
        #    trick history and removing each played card from the
        #    original 13-card lists. Stop after `cards_played` cards.
        remaining = {seat: list(h.cards) for seat, h in original_hands.items()}
        played_so_far = 0
        current_trick = None              # in-progress trick, if any
        completed_tricks = []
        winner_cards = {seat: [] for seat in original_hands}
        for tr in tricks:
            if played_so_far >= cards_played:
                break
            cards_list = list(getattr(tr, 'cards', []) or [])
            leader = getattr(tr, 'leader', None)
            if leader is None or not cards_list:
                continue
            leader_idx = int(leader.value) if hasattr(leader, 'value') else 0
            in_this_trick = []
            for j, c in enumerate(cards_list):
                if played_so_far + j >= cards_played:
                    break
                seat_val = (leader_idx + j) % 4
                seat = Seat(seat_val)
                hand_cards = remaining.get(seat, [])
                try:
                    hand_cards.remove(c)
                except ValueError:
                    pass
                in_this_trick.append((seat, c))
            consumed = len(in_this_trick)
            if consumed == len(cards_list):
                # Whole trick consumed — count the winner.
                winner = getattr(tr, 'winner', None)
                if (winner is not None and hasattr(winner, 'value')
                        and len(cards_list) == 4):
                    win_idx = (int(winner.value) - leader_idx) % 4
                    if 0 <= win_idx < len(cards_list):
                        winner_cards.setdefault(winner, []).append(
                            cards_list[win_idx])
                completed_tricks.append(tr)
                current_trick = None
            else:
                current_trick = in_this_trick
            played_so_far += consumed

        # 2) Render the hands. We need the widget at each *physical*
        #    seat to show the logical seat's remaining cards. All four
        #    panels are unhidden because review shows the whole table.
        from backend.models import Hand
        for physical_seat, widget in self.hand_widgets.items():
            try:
                widget.setVisible(True)
            except Exception:
                pass
            logical = self._logical_seat(physical_seat)
            cards = remaining.get(logical, [])
            widget.set_hand(Hand(cards=cards), face_up=True)
            widget.set_selectable(False)
            wins = winner_cards.get(logical, [])
            try:
                if wins:
                    widget.set_trick_winners(wins)
                else:
                    widget.clear_trick_winners()
            except Exception:
                pass

        # 3) Centre trick area: show whatever's been played in the
        #    in-progress trick (0-3 cards). If we landed exactly on a
        #    trick boundary, clear it so the table reads cleanly.
        try:
            self.trick_area.clear_trick()
            if current_trick:
                for seat, card in current_trick:
                    self.trick_area.play_card(self._display_seat(seat), card,
                                              is_winner=False)
        except Exception:
            pass

    def set_contract(self, contract_str: str, declarer: str):
        self.contract_label.setText(f"{declarer} {contract_str}")
