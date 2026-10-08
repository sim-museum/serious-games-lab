"""The Kramnik Academy (EPIC KS): lessons on what self-capture changes (KS-4) and Kansas puzzles (KS-5), solved on a
board, as Chessmaster's tutorials and puzzles.

Lessons: quizzes accept only the checked solution (tools/lesson_check.py); demonstrations let you try and then show
the idea; each lesson ends with a game against the specialist in its motif. Puzzles (chessiq/puzzles.json, mined
and checked by tools/mine_puzzles.py) come one at a time near your puzzle rating, which moves like an Elo rating
with each first attempt. Progress is kept in academy.json beside the rating profile.

A puzzle's own rating moves the other way with each first attempt on this machine (puzzle_ratings.json beside the
profile, shared by everyone who plays here), so the engines' estimate gives way to how people actually do;
tools/puzzle_feedback.py folds the files from several machines back into chessiq/puzzles.json."""
import json
import os
import random

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
                             QTextBrowser, QVBoxLayout, QWidget)

from . import engine as E
from . import kansas as K
from .lessons import LESSONS, Exercise
from .rating import Profile, profile_path

HERE = os.path.dirname(os.path.abspath(__file__))
PUZZLES = os.path.join(HERE, "puzzles.json")


def progress_path():
    return os.path.join(os.path.dirname(profile_path()), "academy.json")


def load_state():
    try:
        with open(progress_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    path = progress_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(st, f)


def load_progress():
    return set(load_state().get("done", []))


def ratings_path():
    return os.path.join(os.path.dirname(profile_path()), "puzzle_ratings.json")


def load_ratings():
    """{puzzle id (str): {"r": rating now, "n": first attempts, "base": the shipped rating it started from}}"""
    try:
        with open(ratings_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _record(p, adj):
    """This machine's record for puzzle p, or None. A record made against an older shipped rating or position is
    ignored (the feedback it carried is already folded in)."""
    a = adj.get(str(p["id"]))
    return a if a and a.get("base") == p["rating"] and a.get("fen") == p["fen"] else None


def puzzle_rating(p, adj):
    """The rating a puzzle plays at here: the shipped one, moved by this machine's first attempts."""
    a = _record(p, adj)
    return a["r"] if a else p["rating"]


def puzzle_k(n):
    """How far one first attempt moves a puzzle's rating: 40 for its first, falling to 8 as attempts pile up."""
    return max(8, round(40 / (1 + n / 10)))


def load_puzzles():
    try:
        with open(PUZZLES) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


class ExerciseView(QWidget):
    """A board with one exercise: click a piece, then its target. Emits finished(first_try_correct)."""
    finished = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        from .app import BoardWidget          # imported here: app imports this module
        row = QHBoxLayout(self)
        self.board = BoardWidget()
        self.board.setMinimumSize(320, 320)
        self.board.clicked.connect(self.on_square)
        row.addWidget(self.board, 3)
        self.side = QVBoxLayout()
        self.counter = QLabel("")
        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        for w in (self.counter, self.prompt):
            self.side.addWidget(w)
        self.side.addWidget(self.feedback, 1)
        row.addLayout(self.side, 2)
        self.ex, self.pos, self.solved, self.tries = None, None, False, 0

    def load(self, ex, counter=""):
        self.ex, self.solved, self.tries = ex, False, 0
        self.pos = K.from_fen(ex.fen)
        b, turn = self.pos[0], self.pos[1]
        self.board.board, self.board.orient = b, turn
        self.board.selected, self.board.targets, self.board.last, self.board.hints = None, [], None, []
        self.board.update()
        self.counter.setText("%s%s · %s to move" % (counter, "Find the move" if ex.quiz else "Find the idea",
                                                    "White" if turn == "w" else "Black"))
        self.prompt.setText("<b>%s</b>" % ex.prompt)
        self.feedback.setText("" if ex.quiz else "<i>A demonstration: try a move, then see the idea.</i>")

    def on_square(self, i):
        if self.solved or self.ex is None:
            return
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        bw = self.board
        if bw.selected is not None:
            hits = [m for m in bw.targets if m.to == i]
            if hits:
                m = next((h for h in hits if K.uci_of(h) in self.ex.solutions), None) or next(
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
        ex = self.ex
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        u, san = K.uci_of(m), E.san_of(b, m, ep)
        self.board.selected, self.board.targets = None, []
        self.tries += 1
        if u in ex.solutions:
            self.finish(m, "<span style='color:#1a7f37'><b>%s — yes!</b></span> %s" % (san, ex.explain), self.tries == 1)
        elif ex.quiz:
            self.feedback.setText("<span style='color:#b35900'><b>%s</b> is not it.</span> Try again, or press Show."
                                  % san)
            self.board.update()
        else:
            best = K.find(b, turn, ep, ex.solutions[0])
            self.finish(best, "<b>%s</b> is a move a strong player might consider. The idea here is <b>%s</b>: %s"
                        % (san, E.san_of(b, best, ep), ex.explain), True)

    def reveal(self):
        if self.ex is None or self.solved:
            return
        b, turn, ep = self.pos[0], self.pos[1], self.pos[2]
        m = K.find(b, turn, ep, self.ex.solutions[0])
        self.tries += 1
        self.finish(m, "<b>%s.</b> %s" % (E.san_of(b, m, ep), self.ex.explain), False)

    def finish(self, m, html, first_try):
        self.solved = True
        self.board.board, self.board.last = E.apply_move(self.pos[0], m), m
        self.board.update()
        self.feedback.setText(html)
        self.finished.emit(first_try)


def play_against(main, name):
    """Start an unrated game against the named opponent in the main window."""
    if main is None or not name or main.who.findData(name) < 0:
        return
    main.who.setCurrentIndex(main.who.findData(name))
    main.mode.setCurrentIndex(main.mode.findData("ai"))
    main.rated_box.setChecked(False)
    main.new_game()
    main.raise_()


class AcademyWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kramnik Academy")
        self.setModal(False)
        self.resize(1000, 640)
        self.done = load_progress()
        self.lesson, self.index = None, 0
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
        self.view = ExerciseView()
        self.view.finished.connect(self.on_finished)
        nav = QHBoxLayout()
        self.prev_btn, self.show_btn, self.next_btn = QPushButton("◀ Previous"), QPushButton("Show"), QPushButton("Next ▶")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        self.show_btn.clicked.connect(self.view.reveal)
        for b in (self.prev_btn, self.show_btn, self.next_btn):
            nav.addWidget(b)
        self.view.side.addLayout(nav)
        self.play_btn = QPushButton("")
        self.play_btn.clicked.connect(self.play_opponent)
        self.view.side.addWidget(self.play_btn)
        rv.addWidget(self.view, 5)
        split.addWidget(right)
        v = QVBoxLayout(self)
        v.addWidget(split)
        self.refill()
        self.list.currentRowChanged.connect(self.open_lesson)
        self.list.setCurrentRow(0)

    @property
    def solved(self):
        return self.view.solved

    @property
    def feedback(self):
        return self.view.feedback

    def on_square(self, i):
        self.view.on_square(i)

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
        self.index = max(0, min(len(exs) - 1, i))
        self.view.load(exs[self.index], "Position %d of %d · " % (self.index + 1, len(exs)))
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(exs) - 1)

    def on_finished(self, _first_try):
        if self.index == len(self.lesson.exercises) - 1 and self.lesson.key not in self.done:
            self.done.add(self.lesson.key)
            st = load_state()
            st["done"] = sorted(self.done)
            save_state(st)
            self.refill()

    def play_opponent(self):
        play_against(self.parent(), self.lesson.opponent if self.lesson else "")


PUZZLE_K = 32                   # rating points per puzzle at most, as a club Elo
PUZZLE_TEXT = {"self-capture": "Find the self-capture.",
               "quiet": "The natural move of ordinary chess is a mistake here. Find the best move.",
               "mate": "Mate in one. In Kramnik chess you may take your own pieces.",
               "escape": "You are in check. Only one move saves you, and in ordinary chess it would be illegal."}
SPECIALIST_FOR = {"promotion": "Ada", "escape": "Mirela", "king-walk": "Ada", "king-other": "Mirela",
                  "check": "Corin", "attack": "Rosa", "activation": "Felix", "reposition": "Ada"}


class PuzzleWindow(QDialog):
    """Kansas puzzles, one at a time near your puzzle rating (KS-5)."""

    def __init__(self, parent=None, seed=None):
        super().__init__(parent)
        self.setWindowTitle("Kansas puzzles")
        self.setModal(False)
        self.resize(880, 560)
        self.rand = random.Random(seed)
        self.puzzles = load_puzzles()
        st = load_state()
        prof = Profile.load()
        self.rating = st.get("puzzle_rating", prof.rating if prof else 1200)
        self.seen = set(st.get("puzzles_seen", []))
        self.solved_ids = set(st.get("puzzles_solved", []))
        self.adj = load_ratings()
        v = QVBoxLayout(self)
        self.head = QLabel("")
        v.addWidget(self.head)
        self.view = ExerciseView()
        self.view.finished.connect(self.on_finished)
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.show_btn, self.next_btn = QPushButton("Show"), QPushButton("Next puzzle ▶")
        self.show_btn.clicked.connect(self.view.reveal)
        self.next_btn.clicked.connect(self.next_puzzle)
        for b in (self.show_btn, self.next_btn):
            row.addWidget(b)
        self.view.side.addLayout(row)
        self.play_btn = QPushButton("")
        self.play_btn.clicked.connect(lambda: play_against(self.parent(), self.specialist))
        self.view.side.addWidget(self.play_btn)
        self.current, self.specialist = None, ""
        self.next_puzzle()

    def pick(self):
        """An unseen puzzle among the five rated nearest yours (all puzzles again once every one has been seen)."""
        pool = [p for p in self.puzzles if p["id"] not in self.seen] or list(self.puzzles)
        if not pool:
            return None
        pool.sort(key=lambda p: abs(puzzle_rating(p, self.adj) - self.rating))
        return self.rand.choice(pool[:5])

    def next_puzzle(self):
        self.current = self.pick()
        if self.current is None:
            self.head.setText("No puzzles are installed (chessiq/puzzles.json).")
            return
        p = self.current
        ex = Exercise(p["fen"], PUZZLE_TEXT[p["kind"]], p["solution"], p["explain"])
        self.view.load(ex, "Puzzle %d · rated %d · " % (p["id"], puzzle_rating(p, self.adj)))
        self.specialist = "Hal" if p["kind"] in ("mate", "escape") else SPECIALIST_FOR.get(p.get("motif", ""), "Selim")
        self.play_btn.setText("Play %s, who plays for this" % self.specialist)
        self._head()

    def _head(self):
        self.head.setText("<b>Your puzzle rating: %d</b> · solved at the first try: %d of %d · %d puzzles in all"
                          % (self.rating, len(self.solved_ids), len(self.seen), len(self.puzzles)))

    def on_finished(self, first_try):
        p = self.current
        if p["id"] not in self.seen:                     # only a first attempt counts
            self.adj = load_ratings()                     # another window or profile may have written since
            pr = puzzle_rating(p, self.adj)
            expected = 1 / (1 + 10 ** ((pr - self.rating) / 400))
            score = 1.0 if first_try else 0.0
            self.rating = round(self.rating + PUZZLE_K * (score - expected))
            a = _record(p, self.adj)
            n = a["n"] if a else 0
            self.adj[str(p["id"])] = dict(r=round(pr - puzzle_k(n) * (score - expected)), n=n + 1, base=p["rating"],
                                          fen=p["fen"])
            path = ratings_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.adj, f)
            self.seen.add(p["id"])
            if first_try:
                self.solved_ids.add(p["id"])
            st = load_state()
            st.update(puzzle_rating=self.rating, puzzles_seen=sorted(self.seen), puzzles_solved=sorted(self.solved_ids))
            save_state(st)
        self._head()


class PracticeDialog(QDialog):
    """Your own game's Kansas moments -- the strong self-captures missed and the ordinary-chess moves that lost -- as
    positions to solve (KS-3 + KS-4): the lesson you learn best is from your own game."""

    def __init__(self, exercises, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Practise your game's Kansas moments")
        self.setModal(False)
        self.resize(820, 520)
        self.exs, self.index = exercises, 0
        v = QVBoxLayout(self)
        self.view = ExerciseView()
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.show_btn, self.next_btn = QPushButton("Show"), QPushButton("Next ▶")
        self.show_btn.clicked.connect(self.view.reveal)
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        for b in (self.show_btn, self.next_btn):
            row.addWidget(b)
        self.view.side.addLayout(row)
        self.go(0)

    def go(self, i):
        self.index = max(0, min(len(self.exs) - 1, i))
        self.view.load(self.exs[self.index], "Position %d of %d · " % (self.index + 1, len(self.exs)))
        self.next_btn.setEnabled(self.index < len(self.exs) - 1)


def practice_exercises(moments, side=None):
    """Exercises from Kansas moments (chessiq.kansas.moments): each missed self-capture and each ordinary-chess trap
    by `side` (both sides if None), to be found again."""
    out = []
    for m in moments:
        if m["kind"] not in ("missed", "trap") or (side is not None and m["side"] != side):
            continue
        num = "%d%s" % (m["ply"] // 2 + 1, "." if m["side"] == "w" else "...")
        if m["kind"] == "missed":
            prompt = "In the game, %s%s was played here. A self-capture was much stronger. Find it." % (num, m["san"])
        else:
            prompt = ("In the game, %s%s was played here: the best move in ordinary chess, but not in Kramnik chess. "
                      "Find the better move." % (num, m["san"]))
        out.append(Exercise(m["fen"], prompt, [m["best_uci"]], K.describe(m)))
    return out

