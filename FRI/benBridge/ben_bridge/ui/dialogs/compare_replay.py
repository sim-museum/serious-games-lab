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

    # Trick area font: keep in sync with the hand-row font so the cards
    # in the centre read at the same weight as those in N/E/S/W.
    TRICK_FS = 22

    def __init__(self, run: BenBoardRun, title: str, parent=None):
        super().__init__(parent)
        self.run = run

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Title strip — distinguishes "open" vs "closed".
        title_lbl = QLabel(f'<span style="font-size:18px"><b>{title}</b></span>')
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
        # min-height bumped from 200 → 260 so all four cards of a
        # trick (4 lines @ ~30 px line-height + the "Trick N" header
        # + frame margins) fit without clipping. The Qt grid row
        # only grows to the tallest widget, so the trick frame
        # itself has to declare enough space for 4 rows or the
        # bottom card vanishes off the bottom edge.
        center.setStyleSheet(
            "QFrame { background-color: #e8ece8; border: 1px solid #c0c0c0;"
            " border-radius: 4px; min-width: 200px; min-height: 260px; }"
        )
        c_layout = QVBoxLayout(center)
        # 4 px top margin pulls "Trick N" hard against the top of
        # the grey frame so the previous wasted strip above it is
        # gone. AlignTop on the layout forces every widget to stack
        # from the top down — without it the QVBoxLayout default
        # vertically centres a short stack of widgets in a tall
        # frame, which was what put "Trick N" mid-frame and pushed
        # the 4th card off the bottom.
        c_layout.setContentsMargins(8, 4, 8, 8)
        c_layout.setSpacing(2)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        fs = self.TRICK_FS
        self.trick_label = QLabel(
            f'<span style="font-size:{fs}px"><b>Trick 1</b></span>'
        )
        self.trick_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        c_layout.addWidget(self.trick_label)
        self.trick_cards_label = QLabel("")
        self.trick_cards_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.trick_cards_label.setTextFormat(Qt.TextFormat.RichText)
        # WordWrap on so a long card label can't push the rest off
        # the bottom of the frame.
        self.trick_cards_label.setWordWrap(True)
        c_layout.addWidget(self.trick_cards_label)
        grid.addWidget(center, 1, 1)

        layout.addWidget(table_frame, stretch=1)

        # Tricks-won line.
        trick_line = QHBoxLayout()
        self.declarer_lbl = QLabel('<span style="font-size:16px">Declarer: 0</span>')
        trick_line.addWidget(self.declarer_lbl)
        trick_line.addStretch()
        self.defense_lbl = QLabel('<span style="font-size:16px">Defense: 0</span>')
        trick_line.addWidget(self.defense_lbl)
        layout.addLayout(trick_line)

    # ------------------------------------------------------------------
    # Position model
    #
    # Position 0 is "trick 1, no card yet". Each step adds one card to
    # the current trick; once 4 cards land we move on to trick N+1.
    # The auction is shown in its own dialog (see BiddingLogDialog),
    # so we don't intermix bids and cards in the navigation any more.
    # The panel freezes at its last card if the other side ran longer.
    # ------------------------------------------------------------------

    def total_steps(self) -> int:
        return sum(len(t.cards) for t in self.run.tricks)

    def set_position(self, step: int):
        """Render the panel at card-step `step` (0..total_steps())."""
        step = max(0, min(step, self.total_steps()))
        self._render_play(card_step=step)

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

        fs = self.TRICK_FS
        # Trick area
        if current_trick_idx < len(tricks):
            trick = tricks[current_trick_idx]
            self.trick_label.setText(
                f'<span style="font-size:{fs}px"><b>Trick {current_trick_idx + 1}</b></span>'
            )
            shown_cards = []
            for ci in range(cards_in_current):
                card = trick.cards[ci]
                seat = Seat((trick.leader.value + ci) % 4)
                shown_cards.append(
                    f'<span style="font-size:{fs}px">{seat.to_char()}: {self._fmt_card(card)}</span>'
                )
            self.trick_cards_label.setText(
                "<br>".join(shown_cards) if shown_cards else
                f'<span style="font-size:{fs}px">(lead)</span>'
            )
        else:
            self.trick_label.setText(
                f'<span style="font-size:{fs}px"><b>Complete</b></span>'
            )
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
            f'<span style="font-size:16px">Declarer: {decl_won}</span>'
        )
        self.defense_lbl.setText(
            f'<span style="font-size:16px">Defense: {def_won}</span>'
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


class _BiddingLogPanel(QWidget):
    """One side's auction rendered as a 4-column N/E/S/W grid."""

    HEADER_FS = 18
    CELL_FS = 18

    def __init__(self, run: BenBoardRun, title: str,
                 dealer_idx: int | None = None, parent=None):
        """If `dealer_idx` is supplied, use it instead of deriving from
        `run.board_number` — useful when one side is loaded from a
        source that doesn't carry a board number (Q-Plus QSS files
        leave board_number=0, which would otherwise mis-place the
        first bid at the wrong column).
        """
        super().__init__(parent)
        from ..styles import get_suit_color
        self._dealer_idx_override = dealer_idx
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title_lbl = QLabel(f'<span style="font-size:18px"><b>{title}</b></span>')
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        meta_bits = []
        if run.contract:
            decl = run.contract.declarer.to_char() if run.contract.declarer else "?"
            meta_bits.append(f"Final contract: {run.contract.to_str()} by {decl}")
        if run.contract:
            target = run.contract.target_tricks()
            diff = run.declarer_tricks - target
            res = "=" if diff == 0 else (f"+{diff}" if diff > 0 else str(diff))
            meta_bits.append(f"Result: {res}  (NS {run.ns_score:+d})")
        if meta_bits:
            meta_lbl = QLabel('<span style="font-size:14px">' + ' • '.join(meta_bits) + '</span>')
            meta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(meta_lbl)

        # Dealer / vulnerability / per-pair systems line — answers
        # the "why didn't both rooms bid the same?" question by
        # making the systems each side was actually playing visible
        # at a glance. Pulled from board_number for dealer/vul (the
        # canonical board → dealer/vul mapping) and from the run's
        # own ns_bidding_system / ew_bidding_system fields, which
        # are persisted per-deal so an old replay shows whatever
        # systems were configured when the deal was played.
        try:
            from ben_backend.models import BoardState
            dealer, vuln = BoardState._board_dealer_vuln(run.board_number)
            dealer_char = dealer.to_char()
            vul_map = {0: 'None', 1: 'NS', 2: 'EW', 3: 'Both'}
            vul_str = vul_map.get(getattr(vuln, 'value', 0), 'None')
        except Exception:
            dealer_char, vul_str = '?', '?'
        ns_sys = (getattr(run, 'ns_bidding_system', '') or '—')
        ew_sys = (getattr(run, 'ew_bidding_system', '') or '—')
        sys_lbl = QLabel(
            f'<span style="font-size:13px; color:#444">'
            f'Dealer: <b>{dealer_char}</b> • Vul: <b>{vul_str}</b>'
            f' • NS: <b>{ns_sys}</b> • EW: <b>{ew_sys}</b>'
            f'</span>'
        )
        sys_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sys_lbl)

        # The grid: header row N/E/S/W + one row per round of bidding.
        grid_frame = QFrame()
        grid_frame.setStyleSheet(
            "QFrame { background-color: #f8f8f8; border: 1px solid #a0a0a0;"
            " border-radius: 4px; padding: 8px; }"
        )
        grid = QGridLayout(grid_frame)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(2)
        for col, seat_char in enumerate(['N', 'E', 'S', 'W']):
            h = QLabel(
                f'<span style="font-size:{self.HEADER_FS}px"><b>{seat_char}</b></span>'
            )
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h.setStyleSheet(
                "QLabel { background-color: #d0d0d0; border: 1px solid #888;"
                " padding: 4px 12px; }"
            )
            grid.addWidget(h, 0, col)

        # Pad cells before the dealer's first bid with em dashes so each
        # column lines up with its seat.  Prefer the explicit override
        # passed by the parent dialog (which already worked out the
        # correct dealer from whichever run carries a real board
        # number); only fall back to deriving from `run.board_number`
        # when no override is supplied.
        from ben_backend.models import Seat as _Seat
        if self._dealer_idx_override is not None:
            dealer_idx = self._dealer_idx_override
        else:
            try:
                from ben_backend.models import BoardState
                dealer, _ = BoardState._board_dealer_vuln(run.board_number)
                dealer_idx = dealer.value
            except Exception:
                dealer_idx = 0

        suit_symbols = {0: '♠', 1: '♥', 2: '♦', 3: '♣'}
        suit_names = {0: 'spades', 1: 'hearts', 2: 'diamonds', 3: 'clubs'}

        col = 0
        row = 1
        # Pre-fill cells before dealer's first bid with em dashes.
        for _ in range(dealer_idx):
            cell = QLabel(
                f'<span style="font-size:{self.CELL_FS}px;color:#999">—</span>'
            )
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(cell, row, col)
            col += 1

        for bid in run.auction:
            if bid.is_pass:
                text = f'<span style="font-size:{self.CELL_FS}px;color:#666">Pass</span>'
            elif bid.is_double:
                text = f'<span style="font-size:{self.CELL_FS}px;color:blue"><b>X</b></span>'
            elif bid.is_redouble:
                text = f'<span style="font-size:{self.CELL_FS}px;color:#00008B"><b>XX</b></span>'
            else:
                if bid.suit is not None and bid.suit.value < 4:
                    color = get_suit_color(suit_names[bid.suit.value])
                    sym = suit_symbols[bid.suit.value]
                    text = (
                        f'<span style="font-size:{self.CELL_FS}px"><b>{bid.level}</b>'
                        f'<span style="color:{color}">{sym}</span></span>'
                    )
                else:
                    text = f'<span style="font-size:{self.CELL_FS}px"><b>{bid.level}NT</b></span>'
            cell = QLabel(text)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(cell, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        layout.addWidget(grid_frame)
        layout.addStretch(1)


class BiddingLogDialog(QDialog):
    """Independent top-level window with the two auctions side-by-side.

    Spawned by CompareReplayDialog when the user clicks "Bidding logs".
    Lives in its own window so it can be dragged to a second monitor;
    the main Compare window keeps the play replay.
    """

    def __init__(self, left: BenBoardRun, right: BenBoardRun,
                 left_label: str, right_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bidding logs: Board {left.board_number}")
        apply_dialog_style(self)
        from .dialog_style import make_detachable
        make_detachable(self)
        self.resize(900, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Both runs describe the same deal, so dealer must agree.  Use
        # whichever run carries a real (non-zero) board number to derive
        # it — Q-Plus QSS imports leave board_number=0 on the closed
        # side, which would otherwise mis-place the first bid one
        # column to the right.
        dealer_idx = self._derive_shared_dealer_idx(left, right)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(_BiddingLogPanel(left, left_label, dealer_idx=dealer_idx))
        splitter.addWidget(_BiddingLogPanel(right, right_label, dealer_idx=dealer_idx))
        splitter.setSizes([1, 1])
        layout.addWidget(splitter, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    @staticmethod
    def _derive_shared_dealer_idx(left: BenBoardRun, right: BenBoardRun) -> int:
        """Pick the seat index of the dealer using whichever run carries
        a real board number.  Returns 0 (North) if neither does."""
        from ben_backend.models import BoardState
        for run in (left, right):
            board_no = getattr(run, 'board_number', 0) or 0
            if board_no > 0:
                try:
                    dealer, _ = BoardState._board_dealer_vuln(board_no)
                    return dealer.value
                except Exception:
                    pass
        return 0


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
        self.bidding_btn = QPushButton("Bidding logs")
        self.bidding_btn.setToolTip(
            "Open both auction logs in a separate window so you can drag "
            "them to a second monitor while the play replay continues here."
        )
        self.bidding_btn.clicked.connect(self._on_show_bidding_logs)
        bottom.addWidget(self.bidding_btn)

        self.transcript_btn = QPushButton("Annotated transcript (Claude)")
        self.transcript_btn.setToolTip(
            "Send both BDLs (open + closed room) to Claude Opus 4.7 with "
            "extended thinking and get a side-by-side annotated transcript: "
            "bidding differences, card-play differences, what the human "
            "did well, and where they could improve."
        )
        self.transcript_btn.clicked.connect(self._on_annotated_transcript)
        bottom.addWidget(self.transcript_btn)

        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._left_label = left_label
        self._right_label = right_label
        self._bidding_dialog = None

        self._refresh()

    def _on_show_bidding_logs(self):
        """Pop the auctions into their own top-level window."""
        existing = self._bidding_dialog
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self._bidding_dialog = BiddingLogDialog(
            self.left_run, self.right_run,
            self._left_label, self._right_label, self,
        )
        self._bidding_dialog.show()
        self._bidding_dialog.raise_()

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
        # Position label: cards-played counter + a trick counter so
        # the user can see at a glance which trick the comparison is
        # parked on. Trick number = (step - 1) // 4 + 1 for steps
        # ≥ 1; at step 0 we're about to play the opening lead, so
        # show "Trick 1" pre-emptively (more useful than "Trick 0").
        trick_no = max(1, ((max(self._step, 1) - 1) // 4) + 1)
        max_tricks = max(1, (max_step + 3) // 4)
        self.position_lbl.setText(
            f"Card {self._step}/{max_step} • "
            f"Trick {trick_no}/{max_tricks}"
        )
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
        # Snap back to the start of the current trick, or one trick
        # earlier if we're already at the start. Both runs share the
        # same card-step grid (auction lives in its own dialog), so a
        # single calculation drives both panels.
        if self._step == 0:
            return
        within = (self._step - 1) % 4
        if within == 0:
            self._step = max(0, self._step - 4)
        else:
            self._step -= within
        self._refresh()

    def _on_next_trick(self):
        within = self._step % 4
        if within == 0:
            self._step = min(self._max_step(), self._step + 4)
        else:
            self._step = min(self._max_step(), self._step + (4 - within))
        self._refresh()

    # ------------------------------------------------------------------
    # Annotated transcript — Claude Opus 4.7 thinking comparison of both
    # rooms. Builds a BDL from each BenBoardRun, frames them as an
    # open-vs-closed comparison prompt, and routes through the host
    # MainWindow's _run_claude_with_dialog helper so we share the same
    # progress dialog / error handling as the Hint button.
    # ------------------------------------------------------------------

    def _run_to_bdl(self, run: BenBoardRun) -> str:
        """Build BDL text for a finished BenBoardRun by synthesising a
        BoardState and handing it to the existing build_bdl_snapshot
        formatter. viewer_seat=None so every hand is visible (this is a
        post-mortem with full information — both rooms are over)."""
        try:
            from ben_backend.models import BoardState
            from ..game_logger import build_bdl_snapshot
        except Exception:
            return ""
        try:
            dealer, vuln = BoardState._board_dealer_vuln(run.board_number)
        except Exception:
            dealer = run.original_hands and list(run.original_hands)[0]
            vuln = None
        state = BoardState(
            board_number=run.board_number,
            dealer=dealer,
            vulnerability=vuln,
            hands=dict(run.original_hands),
            auction=list(run.auction),
            contract=run.contract,
            tricks=list(run.tricks),
            declarer_tricks=run.declarer_tricks,
        )
        result_summary = ""
        if run.contract:
            target = run.contract.target_tricks()
            diff = run.declarer_tricks - target
            verdict = ("made exactly" if diff == 0
                       else f"made +{diff}" if diff > 0
                       else f"down {abs(diff)}")
            result_summary = (
                f"Result: declarer {verdict} "
                f"({run.declarer_tricks} tricks); "
                f"NS {run.ns_score:+d}, EW {run.ew_score:+d}."
            )
        else:
            result_summary = "Result: passed out (no play)."
        return build_bdl_snapshot(
            state,
            original_hands=run.original_hands,
            viewer_seat=None,  # full information for hindsight analysis
            phase='finished' if run.played else None,
            contract=run.contract,
            result_summary=result_summary,
            deal_id=run.pavlicek_id or "",
            include_footer=False,
        )

    def _build_transcript_prompt(self) -> str:
        """Assemble the side-by-side comparison prompt."""
        left_bdl = self._run_to_bdl(self.left_run) or "(no left BDL available)"
        right_bdl = self._run_to_bdl(self.right_run) or "(no right BDL available)"
        return (
            "You are reviewing the SAME bridge deal played at two different "
            "tables in a teams match. Compare the two rooms side by side and "
            "produce an annotated transcript that a human bridge player can "
            "study to improve their game.\n\n"
            "Use FULL hindsight (every hand is visible to you, both rooms "
            "are complete). Open room = the table where a human played at "
            "one or more seats. Closed room = the bot reference table "
            "(Q-Plus, BEN, etc.) for the same deal — it's the "
            "yardstick.\n\n"
            f"=== OPEN ROOM ({self._left_label}) ===\n"
            f"{left_bdl}\n\n"
            f"=== CLOSED ROOM ({self._right_label}) ===\n"
            f"{right_bdl}\n\n"
            "TASKS:\n"
            "1. Annotated bidding comparison. Walk through the auction "
            "round by round. For each call that DIFFERS between the two "
            "rooms, explain who was right and why (cite HCP, distribution, "
            "vulnerability, system: SAYC / 2-over-1 / Precision).\n\n"
            "2. Annotated card-play comparison. Walk through the play "
            "trick by trick. Note the opening lead, declarer's plan, key "
            "defensive plays, and signalling. When the two rooms diverge, "
            "explain the principle (suit-prefence, second-hand low, "
            "endplay, squeeze, count signals, etc.) that should have "
            "driven the choice.\n\n"
            "3. IMP swing. Compute the IMP difference if any and state "
            "which room came out ahead.\n\n"
            "4. WHAT THE HUMAN DID WELL — be specific. Name the seat, the "
            "round / trick, the action, and exactly why it was good "
            "(matched expert line, made the right inference, didn't fall "
            "for a trap, etc.). At least 2 items if there is anything to "
            "praise; if there's truly nothing, say so honestly.\n\n"
            "5. WHERE THE HUMAN COULD IMPROVE — concrete, actionable. "
            "Each item should name the spot (auction round or trick "
            "number), the actual choice, the better alternative, and a "
            "short principle so it transfers to similar future deals. "
            "Don't pad with generic advice; cite the specific cards.\n\n"
            "Format the output as Markdown with clear section headers. "
            "Use code blocks for short BDL fragments when quoting "
            "auction lines or trick cards verbatim. Keep the tone "
            "constructive and focused — the human is studying, not "
            "being scolded."
        )

    def _on_annotated_transcript(self):
        """Generate the side-by-side annotated transcript via Claude."""
        prompt = self._build_transcript_prompt()
        host = self._find_main_window()
        title = (f"Annotated transcript — Board {self.left_run.board_number}"
                 if self.left_run.board_number == self.right_run.board_number
                 else (f"Annotated transcript — "
                       f"{self.left_run.board_number} vs "
                       f"{self.right_run.board_number}"))
        if host is not None and hasattr(host, '_run_claude_with_dialog'):
            host._run_claude_with_dialog(
                prompt=prompt,
                title=title,
                wait_label="Claude Opus 4.7 is comparing the two rooms…",
                timeout_seconds=420,
            )
            return
        # Fallback path — no MainWindow reachable (unlikely): run claude
        # inline and pop a plain scrollable dialog. Keeps the feature
        # available if the dialog ever gets shown from a different host.
        self._run_claude_inline_fallback(prompt, title)

    def _find_main_window(self):
        """Walk up the parent chain looking for the MainWindow (or any
        object with the _run_claude_with_dialog helper)."""
        node = self.parent()
        while node is not None:
            if hasattr(node, '_run_claude_with_dialog'):
                return node
            try:
                node = node.parent()
            except Exception:
                return None
        return None

    def _run_claude_inline_fallback(self, prompt: str, title: str):
        """Last-resort claude invocation when no MainWindow is reachable.
        Keeps the dialog usable as a standalone widget."""
        import shutil
        import subprocess
        if not shutil.which('claude'):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, title,
                "Claude CLI is not installed on this machine — install "
                "it to enable annotated transcripts.")
            return
        try:
            r = subprocess.run(
                ['claude', '-p', '--model', 'claude-opus-4-7',
                 '--thinking', 'enabled', '--max-turns', '1', prompt],
                capture_output=True, text=True, timeout=420,
            )
            text = (r.stdout or '').strip()
        except Exception as ex:
            text = f"(claude call failed: {ex})"
        self._show_text_dialog(title, text)

    def _show_text_dialog(self, title: str, text: str):
        """Plain scrollable dialog for the fallback path."""
        from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 700)
        layout = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text or "(no response)")
        view.setFont(QFont("Courier", 11))
        layout.addWidget(view)
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)
        dlg.exec()

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
