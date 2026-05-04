"""Side-by-side replay dialog comparing two BenBoardRuns of the same deal.

The classic single-side replay (`ReplayViewDialog`) drives one mini table
through bidding/play. CompareReplayDialog hosts two of those tables and a
single navigation bar; each step advances both panels in lockstep so the
user can compare an open-room human play against a Q-Plus closed-room.
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QWidget, QSplitter, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .dialog_style import apply_dialog_style
from .replay_view import MiniHandWidget
from ben_backend.models import (
    BenBoardRun, Seat, Suit, Card, Trick
)


class _ReplayPanel(QWidget):
    """One side of the comparison view — header, four hand widgets, trick
    area, and tricks-won line. Driven externally by `set_position`.
    """

    def __init__(self, run: BenBoardRun, title: str, parent=None):
        super().__init__(parent)
        self.run = run

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Title strip — distinguishes "open" vs "closed".
        title_lbl = QLabel(f'<span style="font-size:14px"><b>{title}</b></span>')
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        # Header (contract / result)
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #e0e8f0; border: 1px solid #a0a0a0;"
            " border-radius: 4px; padding: 6px; }"
        )
        h_layout = QHBoxLayout(header)
        from ..styles import get_suit_color
        if run.contract:
            c = run.contract
            sym = ['♠', '♥', '♦', '♣', 'NT'][c.suit.value]
            names = ['spades', 'hearts', 'diamonds', 'clubs', 'spades']
            if c.suit.value < 4:
                color = get_suit_color(names[c.suit.value])
                contract_html = f'{c.level}<span style="color:{color}">{sym}</span>'
            else:
                contract_html = f"{c.level}NT"
            if c.redoubled:
                contract_html += "XX"
            elif c.doubled:
                contract_html += "X"
            contract_html += f" by {c.declarer.to_char()}"
        else:
            contract_html = "Passed Out"
        contract_lbl = QLabel(f'<span style="font-size:16px"><b>{contract_html}</b></span>')
        h_layout.addWidget(contract_lbl)
        h_layout.addStretch()

        if run.contract:
            target = run.contract.target_tricks()
            diff = run.declarer_tricks - target
            res = "Made" if diff == 0 else (f"+{diff}" if diff > 0 else str(diff))
            score_str = f"{run.ns_score:+d}"
        else:
            res, score_str = "—", "0"
        result_lbl = QLabel(f'<span style="font-size:14px">{res} ({score_str})</span>')
        h_layout.addWidget(result_lbl)
        layout.addWidget(header)

        # Mini table — 4 hands in N/E/S/W with center trick area.
        table_frame = QFrame()
        table_frame.setStyleSheet(
            "QFrame { background-color: #f8f8f8; border: 1px solid #a0a0a0;"
            " border-radius: 4px; }"
        )
        grid = QGridLayout(table_frame)
        grid.setSpacing(8)

        self.north = MiniHandWidget(Seat.NORTH)
        grid.addWidget(self.north, 0, 1)
        self.west = MiniHandWidget(Seat.WEST)
        grid.addWidget(self.west, 1, 0)
        self.east = MiniHandWidget(Seat.EAST)
        grid.addWidget(self.east, 1, 2)
        self.south = MiniHandWidget(Seat.SOUTH)
        grid.addWidget(self.south, 2, 1)

        center = QFrame()
        center.setStyleSheet(
            "QFrame { background-color: #e8ece8; border: 1px solid #c0c0c0;"
            " border-radius: 4px; min-width: 110px; min-height: 70px; }"
        )
        c_layout = QVBoxLayout(center)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.trick_label = QLabel('<span style="font-size:13px"><b>Auction</b></span>')
        self.trick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.trick_label)
        self.trick_cards_label = QLabel("")
        self.trick_cards_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.trick_cards_label)
        grid.addWidget(center, 1, 1)

        layout.addWidget(table_frame, stretch=1)

        # Tricks-won line.
        trick_line = QHBoxLayout()
        self.declarer_lbl = QLabel('<span style="font-size:13px">Declarer: 0</span>')
        trick_line.addWidget(self.declarer_lbl)
        trick_line.addStretch()
        self.defense_lbl = QLabel('<span style="font-size:13px">Defense: 0</span>')
        trick_line.addWidget(self.defense_lbl)
        layout.addLayout(trick_line)

    # ------------------------------------------------------------------
    # Position model
    #
    # Positions are flat: the auction occupies indices [0, len(auction)],
    # play occupies [len(auction)+1 .. len(auction)+1+sum(len(t.cards))].
    # A panel "freezes" once its own length is exceeded — useful when the
    # two runs disagree in auction or trick count.
    # ------------------------------------------------------------------

    def total_steps(self) -> int:
        play_steps = sum(len(t.cards) for t in self.run.tricks)
        return len(self.run.auction) + play_steps

    def set_position(self, step: int):
        """Render the panel at the global step index (0..total_steps).

        Step 0 is "no bids yet"; bumping the step shows one more bid until
        all bids are visible, then one more card per step. Excess steps
        are clamped so this panel just shows its final state.
        """
        step = max(0, min(step, self.total_steps()))
        auction_len = len(self.run.auction)

        if step <= auction_len:
            self._render_auction(bids_shown=step)
        else:
            self._render_play(card_step=step - auction_len)

    def _render_auction(self, bids_shown: int):
        # During bidding all four hands are visible (post-mortem); no cards
        # have been played yet.
        played_cards = {s: [] for s in Seat}
        self._update_hands(played_cards)
        if bids_shown == 0:
            self.trick_label.setText('<span style="font-size:13px"><b>Auction (start)</b></span>')
        else:
            self.trick_label.setText(
                f'<span style="font-size:13px"><b>Auction: {bids_shown}/{len(self.run.auction)}</b></span>'
            )
        # Show the auction so far as a compact strip.
        if self.run.auction:
            shown = self.run.auction[:bids_shown]
            self.trick_cards_label.setText(
                "<span style='font-size:13px'>" + " ".join(b.symbol() for b in shown) + "</span>"
            )
        else:
            self.trick_cards_label.setText("")
        self.declarer_lbl.setText('<span style="font-size:13px">Declarer: 0</span>')
        self.defense_lbl.setText('<span style="font-size:13px">Defense: 0</span>')

    def _render_play(self, card_step: int):
        tricks = self.run.tricks
        played_cards = {s: [] for s in Seat}

        cards_left = card_step
        current_trick_idx = 0
        cards_in_current = 0
        for ti, t in enumerate(tricks):
            n = len(t.cards)
            if cards_left >= n:
                # All four cards of this trick already played
                for ci, card in enumerate(t.cards):
                    played_cards[Seat((t.leader.value + ci) % 4)].append(card)
                cards_left -= n
                if cards_left == 0:
                    current_trick_idx = ti
                    cards_in_current = n
                    break
                current_trick_idx = ti + 1
            else:
                for ci in range(cards_left):
                    card = t.cards[ci]
                    played_cards[Seat((t.leader.value + ci) % 4)].append(card)
                current_trick_idx = ti
                cards_in_current = cards_left
                cards_left = 0
                break

        self._update_hands(played_cards)

        # Trick area
        if current_trick_idx < len(tricks):
            trick = tricks[current_trick_idx]
            self.trick_label.setText(
                f'<span style="font-size:13px"><b>Trick {current_trick_idx + 1}</b></span>'
            )
            shown_cards = []
            for ci in range(cards_in_current):
                card = trick.cards[ci]
                seat = Seat((trick.leader.value + ci) % 4)
                shown_cards.append(
                    f'<span style="font-size:13px">{seat.to_char()}: {self._fmt_card(card)}</span>'
                )
            self.trick_cards_label.setText(
                "<br>".join(shown_cards) if shown_cards else
                '<span style="font-size:13px">(lead)</span>'
            )
        else:
            self.trick_label.setText('<span style="font-size:13px"><b>Complete</b></span>')
            self.trick_cards_label.setText("")

        # Tricks-won
        decl_won = 0
        def_won = 0
        if self.run.contract:
            decl_ns = self.run.contract.declarer.is_ns()
            for ti in range(min(current_trick_idx, len(tricks))):
                t = tricks[ti]
                if t.winner is not None:
                    if t.winner.is_ns() == decl_ns:
                        decl_won += 1
                    else:
                        def_won += 1
        # Include current trick if all four cards landed and it's done.
        if (current_trick_idx < len(tricks)
                and cards_in_current == 4
                and tricks[current_trick_idx].winner is not None):
            if self.run.contract:
                decl_ns = self.run.contract.declarer.is_ns()
                if tricks[current_trick_idx].winner.is_ns() == decl_ns:
                    decl_won += 1
                else:
                    def_won += 1
        self.declarer_lbl.setText(
            f'<span style="font-size:13px">Declarer: {decl_won}</span>'
        )
        self.defense_lbl.setText(
            f'<span style="font-size:13px">Defense: {def_won}</span>'
        )

    def _update_hands(self, played):
        for seat, w in [(Seat.NORTH, self.north), (Seat.EAST, self.east),
                        (Seat.SOUTH, self.south), (Seat.WEST, self.west)]:
            hand = self.run.original_hands.get(seat)
            if hand:
                w.set_hand(hand, played[seat])

    def _fmt_card(self, card: Card) -> str:
        from ..styles import get_suit_color
        sym = {Suit.SPADES: '♠', Suit.HEARTS: '♥',
               Suit.DIAMONDS: '♦', Suit.CLUBS: '♣'}[card.suit]
        names = {Suit.SPADES: 'spades', Suit.HEARTS: 'hearts',
                 Suit.DIAMONDS: 'diamonds', Suit.CLUBS: 'clubs'}
        color = get_suit_color(names[card.suit])
        return f'<span style="color:{color}">{sym}</span>{card.rank.to_char()}'


class CompareReplayDialog(QDialog):
    """Side-by-side replay of two BenBoardRuns sharing one nav bar.

    Both runs should describe the same deal (same `pavlicek_id` or
    `board_number`); we don't enforce it because users may want to
    compare two different sessions.
    """

    def __init__(self, left: BenBoardRun, right: BenBoardRun,
                 left_label: str = "Open (this table)",
                 right_label: str = "Closed (Q-Plus)",
                 parent=None):
        super().__init__(parent)
        self.left_run = left
        self.right_run = right

        self.setWindowTitle(
            f"Compare: Board {left.board_number}"
            if left.board_number == right.board_number
            else f"Compare: {left.board_number} vs {right.board_number}"
        )

        screen = QApplication.primaryScreen().geometry()
        self.resize(int(screen.width() * 0.85), int(screen.height() * 0.9))
        apply_dialog_style(self)

        self._step = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Two panels in a horizontal splitter so the user can resize.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = _ReplayPanel(left, left_label)
        self.right_panel = _ReplayPanel(right, right_label)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([1, 1])
        layout.addWidget(splitter, stretch=1)

        # Navigation bar.
        nav = QFrame()
        nav.setStyleSheet(
            "QFrame { background-color: #f0f0f0; border: 1px solid #c0c0c0;"
            " border-radius: 4px; padding: 6px; }"
        )
        nav_layout = QHBoxLayout(nav)

        self.start_btn = QPushButton("|<")
        self.start_btn.setToolTip("Jump to start (Home)")
        self.start_btn.clicked.connect(self._on_start)
        nav_layout.addWidget(self.start_btn)

        self.prev_trick_btn = QPushButton("<< Prev Trick")
        self.prev_trick_btn.clicked.connect(self._on_prev_trick)
        nav_layout.addWidget(self.prev_trick_btn)

        self.prev_btn = QPushButton("< Prev")
        self.prev_btn.clicked.connect(self._on_prev)
        nav_layout.addWidget(self.prev_btn)

        nav_layout.addStretch()
        self.position_lbl = QLabel("0")
        self.position_lbl.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        nav_layout.addWidget(self.position_lbl)
        nav_layout.addStretch()

        self.next_btn = QPushButton("Next >")
        self.next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self.next_btn)

        self.next_trick_btn = QPushButton("Next Trick >>")
        self.next_trick_btn.clicked.connect(self._on_next_trick)
        nav_layout.addWidget(self.next_trick_btn)

        self.end_btn = QPushButton(">|")
        self.end_btn.setToolTip("Jump to end (End)")
        self.end_btn.clicked.connect(self._on_end)
        nav_layout.addWidget(self.end_btn)

        layout.addWidget(nav)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._refresh()

    # ------------------------------------------------------------------
    # Navigation
    #
    # Step counts always come from the *longer* run so the user can scrub
    # through the entire wider game; the shorter side just freezes at the
    # last frame it has data for.
    # ------------------------------------------------------------------

    def _max_step(self) -> int:
        return max(self.left_panel.total_steps(),
                   self.right_panel.total_steps())

    def _refresh(self):
        max_step = self._max_step()
        self._step = max(0, min(self._step, max_step))
        self.left_panel.set_position(self._step)
        self.right_panel.set_position(self._step)
        self.position_lbl.setText(f"{self._step}/{max_step}")
        self.start_btn.setEnabled(self._step > 0)
        self.prev_btn.setEnabled(self._step > 0)
        self.prev_trick_btn.setEnabled(self._step > 0)
        self.next_btn.setEnabled(self._step < max_step)
        self.next_trick_btn.setEnabled(self._step < max_step)
        self.end_btn.setEnabled(self._step < max_step)

    def _on_start(self):
        self._step = 0
        self._refresh()

    def _on_end(self):
        self._step = self._max_step()
        self._refresh()

    def _on_prev(self):
        self._step = max(0, self._step - 1)
        self._refresh()

    def _on_next(self):
        self._step = min(self._max_step(), self._step + 1)
        self._refresh()

    def _on_prev_trick(self):
        # Step back to the previous trick boundary on the longer run. We
        # use the same trick-grid for both panels — auction first, then 4
        # cards per trick — so this lines up with the panels naturally.
        max_left = max(self.left_run.auction.__len__(), self.right_run.auction.__len__())
        if self._step <= max_left:
            self._step = 0
        else:
            offset = self._step - max_left  # 1..N within play
            # Snap to current trick start, or to previous trick if already at start.
            within = (offset - 1) % 4
            if within == 0:
                # Currently on first card of a trick; move back one full trick.
                self._step = max(max_left, self._step - 4)
            else:
                self._step -= within
        self._refresh()

    def _on_next_trick(self):
        max_left = max(self.left_run.auction.__len__(), self.right_run.auction.__len__())
        if self._step < max_left:
            # Skip the rest of bidding in one go.
            self._step = max_left
        else:
            offset = self._step - max_left
            within = offset % 4
            if within == 0:
                self._step = min(self._max_step(), self._step + 4)
            else:
                self._step = min(self._max_step(), self._step + (4 - within))
        self._refresh()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Right:
            self._on_next()
        elif key == Qt.Key.Key_Left:
            self._on_prev()
        elif key == Qt.Key.Key_PageDown or key == Qt.Key.Key_Down:
            self._on_next_trick()
        elif key == Qt.Key.Key_PageUp or key == Qt.Key.Key_Up:
            self._on_prev_trick()
        elif key == Qt.Key.Key_Home:
            self._on_start()
        elif key == Qt.Key.Key_End:
            self._on_end()
        elif key == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
