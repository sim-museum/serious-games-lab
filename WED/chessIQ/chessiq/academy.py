"""The Kramnik Academy window (EPIC KS, KS-4): lessons on what self-capture changes, with positions to solve on a
board, as Chessmaster's tutorials. Quizzes accept only the checked solution (tools/lesson_check.py); demonstrations
let you try and then show the idea. Each lesson ends with a game against the specialist in its motif. Finished
lessons are remembered in academy.json beside the rating profile."""
import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
                             QTextBrowser, QVBoxLayout, QWidget)

from . import engine as E
from . import kansas as K
from .lessons import LESSONS
from .rating import profile_path


def progress_path():
    return os.path.join(os.path.dirname(profile_path()), "academy.json")


def load_progress():
    try:
        with open(progress_path()) as f:
            return set(json.load(f).get("done", []))
    except (OSError, ValueError):
        return set()


def save_progress(done):
    path = progress_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"done": sorted(done)}, f)


class AcademyWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .app import BoardWidget          # imported here: app imports this module
        self.setWindowTitle("Kramnik Academy")
        self.setModal(False)
        self.resize(1000, 640)
        self.done = load_progress()
        self.lesson, self.index, self.solved = None, 0, False
        split = QSplitter(self)
        self.list = QListWidget()
        self.list.setMaximumWidth(360)
        self.list.setMinimumWidth(320)
        split.addWidget(self.list)
        right = QWidget()
        rv = QVBoxLayout(right)
        self.text = QTextBrowser()
        self.text.setMinimumHeight(150)
        rv.addWidget(self.text, 2)
        row = QHBoxLayout()
        self.board = BoardWidget()
        self.board.setMinimumSize(320, 320)
        self.board.clicked.connect(self.on_square)
        row.addWidget(self.board, 3)
        side = QVBoxLayout()
        self.counter = QLabel("")
        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        side.addWidget(self.counter)
        side.addWidget(self.prompt)
        side.addWidget(self.feedback, 1)
        nav = QHBoxLayout()
        self.prev_btn, self.show_btn, self.next_btn = QPushButton("◀ Previous"), QPushButton("Show"), QPushButton("Next ▶")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        self.show_btn.clicked.connect(self.reveal)
        for b in (self.prev_btn, self.show_btn, self.next_btn):
            nav.addWidget(b)
        side.addLayout(nav)
        self.play_btn = QPushButton("")
        self.play_btn.clicked.connect(self.play_opponent)
        side.addWidget(self.play_btn)
        row.addLayout(side, 2)
        rv.addLayout(row, 5)
        split.addWidget(right)
        v = QVBoxLayout(self)
        v.addWidget(split)
        self.refill()
        self.list.currentRowChanged.connect(self.open_lesson)
        self.list.setCurrentRow(0)

    # ---- lessons ----
    def refill(self):
        row = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for lesson in LESSONS:
            it = QListWidgetItem("%s %s — %s" % ("✓" if lesson.key in self.done else "  ", lesson.level, lesson.title))
            it.setData(Qt.ItemDataRole.UserRole, lesson.key)
            self.list.addItem(it)
        if row >= 0:
            self.list.setCurrentRow(row)           # signals still blocked: re-selecting must not restart the lesson
        self.list.blockSignals(False)

    def open_lesson(self, row):
        if not 0 <= row < len(LESSONS):
            return
        self.lesson = LESSONS[row]
        self.text.setHtml("<h2>%s</h2><p><i>%s</i></p>%s" % (self.lesson.title, self.lesson.level, self.lesson.text))
        opp = self.lesson.opponent
        self.play_btn.setText("Play %s, who specialises in this" % opp if opp else "")
        self.play_btn.setVisible(bool(opp))
        self.go(0)

    def go(self, i):
        exs = self.lesson.exercises
        if not exs:
            self.counter.setText("No positions in this lesson.")
            return
        self.index = max(0, min(len(exs) - 1, i))
        ex = exs[self.index]
        self.solved = False
        self.pos = K.from_fen(ex.fen)
        b, turn = self.pos[0], self.pos[1]
        self.board.board, self.board.orient = b, turn
        self.board.selected, self.board.targets, self.board.last, self.board.hints = None, [], None, []
        self.board.update()
        self.counter.setText("Position %d of %d · %s · %s to move" % (
            self.index + 1, len(exs), "Find the move" if ex.quiz else "Find the idea", "White" if turn == "w" else "Black"))
        self.prompt.setText("<b>%s</b>" % ex.prompt)
        self.feedback.setText("" if ex.quiz else "<i>A demonstration: try a move, then see the idea.</i>")
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(exs) - 1)

    # ---- moves on the board ----
    def on_square(self, i):
        if self.solved or self.lesson is None or not self.lesson.exercises:
            return
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        bw = self.board
        if bw.selected is not None:
            hits = [m for m in bw.targets if m.to == i]
            if hits:
                sols = self.lesson.exercises[self.index].solutions
                m = next((h for h in hits if K.uci_of(h) in sols), None) or next(
                    (h for h in hits if h.promo in (None, "q")), hits[0])
                self.attempt(m)
                return
        p = b[i]
        if p and p[0] == turn:
            bw.selected = i
            bw.targets = [m for m in E.legal_moves(b, turn, ep) if m.frm == i]
        else:
            bw.selected, bw.targets = None, []
        bw.update()

    def attempt(self, m):
        ex = self.lesson.exercises[self.index]
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        u, san = K.uci_of(m), E.san_of(b, m, ep)
        self.board.selected, self.board.targets = None, []
        if u in ex.solutions:
            self.finish(m, "<span style='color:#1a7f37'><b>%s — yes!</b></span> %s" % (san, ex.explain))
        elif ex.quiz:
            self.feedback.setText("<span style='color:#b35900'><b>%s</b> is not it.</span> Try again, or press Show."
                                  % san)
            self.board.update()
        else:
            best = E.san_of(b, K.find(b, turn, ep, ex.solutions[0]), ep)
            self.finish(K.find(b, turn, ep, ex.solutions[0]),
                        "<b>%s</b> is a move a strong player might consider. The idea here is <b>%s</b>: %s"
                        % (san, best, ex.explain))

    def reveal(self):
        if self.lesson is None or not self.lesson.exercises or self.solved:
            return
        ex = self.lesson.exercises[self.index]
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        m = K.find(b, turn, ep, ex.solutions[0])
        self.finish(m, "<b>%s.</b> %s" % (E.san_of(b, m, ep), ex.explain))

    def finish(self, m, html):
        self.solved = True
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        self.board.board, self.board.last = E.apply_move(b, m), m
        self.board.update()
        self.feedback.setText(html)
        if self.index == len(self.lesson.exercises) - 1 and self.lesson.key not in self.done:
            self.done.add(self.lesson.key)
            save_progress(self.done)
            self.refill()

    # ---- the specialist ----
    def play_opponent(self):
        p = self.parent()
        name = self.lesson.opponent if self.lesson else ""
        if p is None or not name or p.who.findData(name) < 0:
            return
        p.who.setCurrentIndex(p.who.findData(name))
        p.mode.setCurrentIndex(p.mode.findData("ai"))
        p.rated_box.setChecked(False)
        p.new_game()
        p.raise_()
