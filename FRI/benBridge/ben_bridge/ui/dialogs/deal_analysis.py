"""Deal Analysis + Evaluation of Actions — Q-Plus `.analys-ctl`
and `.analys-show`.

Two modals that wrap up the post-mortem analysis flow:

  DealAnalysisDialog — auction/card-play checkboxes + N/E/S/W seat
      radios + Start/Stop buttons. Picks WHAT to analyse and FOR
      WHOM. On Start the analyser walks each chosen action and
      compares the human's move with the engine's recommendation,
      then opens an EvaluationOfActionsDialog with the results.

  EvaluationOfActionsDialog — flat list of every analysed action.
      Each row carries an evaluation marker (green dot = matches
      engine recommendation, red dot = differs) plus the action
      text. Selecting a row could be wired to jump the underlying
      review dialog to that action; for the MVP the list is
      informational.

Neither dialog touches the engine directly when the caller passes
``engine=None`` (e.g. unit-test path): the list still renders with
neutral grey markers.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QRadioButton, QPushButton, QLabel, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from .dialog_style import apply_dialog_style


class DealAnalysisDialog(QDialog):
    """Pick which actions to analyse, then launch the action list."""

    def __init__(self, parent=None, board=None, auction=None,
                 tricks=None, engine=None):
        super().__init__(parent)
        self.board = board
        self.auction = auction or []
        self.tricks = tricks or []
        self.engine = engine
        self.setWindowTitle("Deal Analysis")
        apply_dialog_style(self)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # "analyse:" — auction vs card play checkboxes.
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("analyse:"))
        self.auction_cb = QCheckBox("auction")
        self.cards_cb = QCheckBox("card play")
        self.cards_cb.setChecked(True)
        row1.addWidget(self.auction_cb)
        row1.addWidget(self.cards_cb)
        row1.addStretch()
        root.addLayout(row1)

        # "of:" — seat selection (single-pick; Q-Plus actually uses
        # checkboxes here but we keep it simple with radios since
        # the analyser walks one seat at a time anyway).
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("of:"))
        self._seat_group = QButtonGroup(self)
        self.seat_radios = {}
        for sc in ('N', 'E', 'S', 'W'):
            rb = QRadioButton(
                {'N': 'North', 'E': 'East',
                 'S': 'South', 'W': 'West'}[sc])
            self._seat_group.addButton(rb)
            self.seat_radios[sc] = rb
            row2.addWidget(rb)
        # Default: South — matches Q-Plus's default seat.
        self.seat_radios['S'].setChecked(True)
        row2.addStretch()
        root.addLayout(row2)

        # "progress:" — informational, mirrors the Q-Plus label.
        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("progress:"))
        self.progress_label = QLabel("finished")
        self.progress_label.setStyleSheet(
            "QLabel { background: white; padding: 2px 6px;"
            " border: 1px solid #aaa; min-width: 120px; }")
        progress_row.addWidget(self.progress_label)
        progress_row.addStretch()
        root.addLayout(progress_row)

        # Buttons.
        btns = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._on_start)
        btns.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        btns.addWidget(self.stop_btn)
        btns.addStretch()
        help_btn = QPushButton("Help")
        help_btn.clicked.connect(self._on_help)
        btns.addWidget(help_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btns.addWidget(close_btn)
        root.addLayout(btns)

    def _selected_seat(self) -> str:
        for sc, rb in self.seat_radios.items():
            if rb.isChecked():
                return sc
        return 'S'

    def _on_start(self):
        from ben_backend.models import Seat
        seat_char = self._selected_seat()
        seat = Seat.from_char(seat_char)
        evaluations: List[tuple] = []  # (label, status, detail)
        # Auction actions for the chosen seat — every bid in the
        # auction made by them. Status currently always 'neutral'
        # because a real bid evaluator wants the rule-based bidder
        # walked over the partial auction, which adds latency; the
        # MVP shows the list and leaves room to wire that in later.
        if self.auction_cb.isChecked() and self.auction and self.board:
            dealer = self.board.dealer
            seat_chars = ['N', 'E', 'S', 'W']
            for i, bid in enumerate(self.auction):
                bidder = seat_chars[(dealer.value + i) % 4]
                if bidder != seat_char:
                    continue
                evaluations.append((
                    f"#{(i + 1):02d}  bid  {self._fmt_bid(bid)}",
                    'neutral',
                    "(bidding evaluation not wired)"))
        # Card-play actions: every card the chosen seat played, with
        # a green/red marker for engine agreement when an engine is
        # available.
        if self.cards_cb.isChecked() and self.tricks:
            for ti, t in enumerate(self.tricks, start=1):
                leader = t.leader if hasattr(t, 'leader') else None
                if leader is None:
                    continue
                for ci, card in enumerate(t.cards or []):
                    player_idx = (leader.value + ci) % 4
                    player_char = ['N', 'E', 'S', 'W'][player_idx]
                    if player_char != seat_char:
                        continue
                    status, detail = self._evaluate_card_play(
                        t, ci, seat)
                    evaluations.append((
                        f"#{ti:02d}  {self._fmt_card(card)}",
                        status, detail))
        # Open the result window.
        result = EvaluationOfActionsDialog(self, evaluations)
        result.exec()

    def _evaluate_card_play(self, trick, card_idx, seat) -> tuple:
        """Return (status, detail) for a single card-play action.

        status is 'good' / 'bad' / 'neutral'. Without the engine
        every card is neutral. With the engine we ask BEN for what
        it would play in the same position and mark agreement.
        """
        if self.engine is None or self.board is None:
            return ('neutral',
                    "(no engine — evaluation skipped)")
        try:
            played = trick.cards[card_idx]
            partial = trick.cards[:card_idx]
            resp = self.engine.get_card_play(
                self.board, seat, partial)
            if resp is None or resp.action is None:
                return ('neutral', "(engine declined)")
            if (resp.action.suit == played.suit
                    and resp.action.rank == played.rank):
                return ('good',
                        f"agrees with engine pick {resp.action.to_str()}")
            return ('bad',
                    f"engine prefers {resp.action.to_str()}")
        except Exception as ex:
            return ('neutral', f"engine error: {ex!r}")

    @staticmethod
    def _fmt_bid(bid) -> str:
        try:
            return bid.symbol()
        except Exception:
            return str(bid)

    @staticmethod
    def _fmt_card(card) -> str:
        try:
            sym = {0: '♠', 1: '♥', 2: '♦', 3: '♣'}[card.suit.value]
            return f"{sym} {card.rank.to_char()}"
        except Exception:
            return str(card)

    def _on_help(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Deal Analysis",
            "Pick which actions to analyse (auction, card play, or "
            "both) and for whom. Click Start to walk the chosen "
            "actions and compare each one against the engine's "
            "recommendation — agreement shows green, disagreement "
            "red.")


class EvaluationOfActionsDialog(QDialog):
    """Q-Plus `.analys-show` — list view of evaluated actions.

    Two columns: Action (formatted label) and Evaluation (coloured
    marker + brief detail). Selecting a row could be wired to
    re-position the underlying review walker; the MVP leaves that
    hook open.
    """

    def __init__(self, parent=None, evaluations: Optional[List[tuple]] = None):
        super().__init__(parent)
        self.evaluations = evaluations or []
        self.setWindowTitle("Evaluation of actions")
        self.resize(420, 560)
        apply_dialog_style(self)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        self.table = QTableWidget(len(self.evaluations), 2, self)
        self.table.setHorizontalHeaderLabels(
            ["Action", "Evaluation"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        for row, (label, status, detail) in enumerate(self.evaluations):
            self.table.setItem(row, 0, QTableWidgetItem(label))
            # Marker glyph: ● in green / red / grey.
            marker = "●"
            colors = {
                'good': QColor(0, 160, 50),
                'bad': QColor(192, 0, 0),
                'neutral': QColor(140, 140, 140),
            }
            item = QTableWidgetItem(f"{marker}  {detail}")
            item.setForeground(colors.get(status, QColor(128, 128, 128)))
            item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            self.table.setItem(row, 1, item)
        root.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btns.addWidget(close_btn)
        root.addLayout(btns)
