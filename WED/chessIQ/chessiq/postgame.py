"""The Post-Game Analysis window, as Chessmaster shows after each game (EPIC CM, CM-20): the game's type and summary,
the rating change, a chart of the evaluation after every move (hover for values), and Play Suggested Opponent.
Below the chart, "Self-capture moments" (EPIC KS, KS-3): the moments where Kramnik rules mattered -- self-captures played,
strong ones missed, ordinary-chess moves that lose here, and the right move found -- from a second pass with
Fairy-Stockfish searching each position with self-capture on and off (chessiq/kansas.py). Clicking a moment shows
the position on the board. Non-modal: it never blocks the board; closing it cancels an analysis still running."""
from PyQt6.QtCore import QPointF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from . import analysis
from . import kansas as K

CLIP = 1000                         # the chart shows +-10 pawns; beyond that the game is decided


KANSAS_NODES = 30000                # per search in the self-capture pass (three or four searches a move)


class AnalysisThread(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(object)
    kprogress = pyqtSignal(int, int)
    kdone = pyqtSignal(object)

    def __init__(self, moves, parent=None):
        super().__init__(parent)
        self.moves, self.cancelled = moves, False

    def run(self):
        ev = analysis.evaluate_game(self.moves, progress=lambda i, n: self.progress.emit(i, n),
                                    cancel=lambda: self.cancelled)
        if self.cancelled:
            return
        self.done.emit(ev)
        rs = K.RuleSwitch(analysis.BINARY, analysis.VARIANTS, KANSAS_NODES)
        try:
            ms = K.moments(self.moves, rs, cancel=lambda: self.cancelled,
                           progress=lambda i, n: self.kprogress.emit(i, n))
        finally:
            rs.close()
        if not self.cancelled and ms is not None:
            self.kdone.emit(ms)


class Chart(QWidget):
    """Evaluation after each move: above the line is good for White, below for Black (as Chessmaster's Game Chart)."""

    def __init__(self, evals, sans, parent=None):
        super().__init__(parent)
        self.evals, self.sans, self.hover = evals, sans, None
        self.setMinimumSize(520, 200)
        self.setMouseTracking(True)
        self.readout = None

    def _pt(self, i, v):
        w, h, n = self.width() - 20, self.height() - 20, max(1, len(self.evals) - 1)
        v = max(-CLIP, min(CLIP, v))
        return QPointF(10 + w * i / n, 10 + h * (0.5 - v / (2 * CLIP)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#fbfbf8"))
        p.setPen(QPen(QColor("#999999"), 1, Qt.PenStyle.DashLine))
        p.drawLine(self._pt(0, 0), self._pt(len(self.evals) - 1, 0))
        p.setPen(QPen(QColor("#2f7de1"), 2))
        p.drawPolyline(QPolygonF([self._pt(i, v) for i, v in enumerate(self.evals)]))
        if self.hover is not None:
            p.setPen(QPen(QColor("#e06666"), 1))
            p.drawEllipse(self._pt(self.hover, self.evals[self.hover]), 4, 4)
        p.end()

    def mouseMoveEvent(self, e):
        n = max(1, len(self.evals) - 1)
        i = round((e.position().x() - 10) / max(1, self.width() - 20) * n)
        self.hover = max(0, min(len(self.evals) - 1, i))
        if self.readout is not None:
            self.readout.setText(self.describe(self.hover))
        self.update()

    def describe(self, i):
        v = self.evals[i]
        val = ("mate" if abs(v) >= analysis.MATE // 2 else "%+.2f" % (v / 100)) + (" (White)" if v > 0 else
                                                                               " (Black)" if v < 0 else "")
        if i == 0:
            return "Start: %s" % val
        return "After %d%s %s: %s" % ((i + 1) // 2, "." if i % 2 else "...", self.sans[i - 1], val)


class PostGameDialog(QDialog):
    def __init__(self, parent, moves, sans, result, white, black, people, current, my_rating, rating_line=""):
        super().__init__(parent)
        self.setWindowTitle("Post-Game Analysis")
        self.setModal(False)
        self.sans, self.result, self.white, self.black = sans, result, white, black
        self.people, self.current, self.my_rating = people, current, my_rating
        self.kind, self.text, self.suggested, self.evals, self.moments = None, "", None, None, None
        self.v = QVBoxLayout(self)
        self.head = QLabel("Analysing the game…")
        self.head.setWordWrap(True)
        self.v.addWidget(self.head)
        self.rating_line = rating_line
        row = QHBoxLayout()
        self.suggest_btn = QPushButton("Play suggested opponent")
        self.suggest_btn.setEnabled(False)
        self.suggest_btn.clicked.connect(self._play_suggested)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addStretch(1); row.addWidget(self.suggest_btn); row.addWidget(close)
        self.v.addLayout(row)
        self.thread = AnalysisThread(moves, self)
        self.thread.progress.connect(lambda i, n: self.head.setText("Analysing the game… move %d of %d" %
                                                                    ((i + 1) // 2, (n + 1) // 2)))
        self.thread.done.connect(self._show)
        self.kansas = QLabel("")
        self.kansas.setWordWrap(True)
        self.klist = QListWidget()
        self.klist.setMinimumHeight(90)
        self.klist.setMaximumHeight(180)
        self.klist.setWordWrap(True)
        self.klist.hide()
        self.klist.itemClicked.connect(self._go)
        self.practise_btn = QPushButton("Practise these positions")
        self.practise_btn.hide()
        self.practise_btn.clicked.connect(self._practise)
        self.practice = None
        self.thread.kprogress.connect(lambda i, n: self.kansas.setText(
            "<b>Self-capture moments</b> — looking for the moments where Kramnik rules mattered… move %d of %d"
            % ((i + 1) // 2, (n + 1) // 2)))
        self.thread.kdone.connect(self._show_kansas)
        self.thread.start()

    def _show(self, evals):
        if evals is None:
            return
        self.evals = evals
        self.kind, self.text = analysis.summary(evals, self.result, self.sans, self.white, self.black)
        self.suggested = analysis.suggest_opponent(self.people, self.current, self.my_rating, self._my_score())
        lines = [self.text]
        if self.rating_line:
            lines.append(self.rating_line)
        if self.suggested is not None:
            lines.append("Suggested opponent: %s (%d)." % (self.suggested.name, self.suggested.rating))
            self.suggest_btn.setText("Play %s" % self.suggested.name)
            self.suggest_btn.setEnabled(True)
        self.head.setText("<br>".join(lines))
        chart = Chart(evals, self.sans, self)
        readout = QLabel("Point at the chart for the evaluation after each move (+ is good for White).")
        chart.readout = readout
        self.v.insertWidget(1, chart)
        self.v.insertWidget(2, readout)
        self.v.insertWidget(3, self.kansas)
        self.v.insertWidget(4, self.klist)
        self.v.insertWidget(5, self.practise_btn)
        self.adjustSize()

    def _show_kansas(self, ms):
        self.moments = ms
        human = getattr(getattr(self.parent(), "game", None), "human", None)
        played = [m for m in ms if m["kind"] == "played"]
        counts = (len(played), sum(m["kind"] == "missed" for m in ms), sum(m["kind"] == "trap" for m in ms),
                  sum(m["kind"] == "spotted" for m in ms))
        if not ms:
            self.kansas.setText("<b>Self-capture moments</b> — nothing in this game depended on self-capture: it could have "
                                "been ordinary chess. Kramnik chess often looks like that, until it doesn't.")
            return
        self.kansas.setText("<b>Self-capture moments</b> — %d self-capture%s played, %d missed, %d ordinary-chess move%s that "
                            "lost here, %d found. Click one to see the position."
                            % (counts[0], "" if counts[0] == 1 else "s", counts[1], counts[2],
                               "" if counts[2] == 1 else "s", counts[3]))
        for m in ms:
            who = "You" if m["side"] == human else self.white if m["side"] == "w" else self.black
            it = QListWidgetItem("%s — %s" % (who, K.describe(m)))
            it.setData(Qt.ItemDataRole.UserRole, m["ply"])
            self.klist.addItem(it)
        self.klist.show()
        n = len(self._exercises())
        if n:
            self.practise_btn.setText("Practise %d position%s from this game" % (n, "" if n == 1 else "s"))
            self.practise_btn.show()
        self.adjustSize()

    def _exercises(self):
        from .academy import practice_exercises
        human = getattr(getattr(self.parent(), "game", None), "human", None)
        mode = getattr(getattr(self.parent(), "game", None), "mode", "ai")
        return practice_exercises(self.moments or [], human if mode in ("ai", "net") else None)

    def _practise(self):
        from .academy import PracticeDialog
        exs = self._exercises()
        if exs:
            self.practice = PracticeDialog(exs, self.parent())
            self.practice.show()

    def _go(self, item):
        p = self.parent()
        if p is not None and hasattr(p, "go_to"):
            p.go_to(item.data(Qt.ItemDataRole.UserRole))          # the position before the moment's move

    def _my_score(self):
        p = self.parent()
        human = getattr(getattr(p, "game", None), "human", "w")
        return self.result if human == "w" else 1.0 - self.result

    def _play_suggested(self):
        p = self.parent()
        if self.suggested is not None and p is not None:
            i = p.who.findData(self.suggested.name)
            if i >= 0:
                p.who.setCurrentIndex(i)
            self.close()
            p.new_game()

    def closeEvent(self, e):
        self.thread.cancelled = True
        self.thread.wait(10000)
        super().closeEvent(e)


class RatingChart(QWidget):
    """Your rating after each rated game (the first point is where you started); provisional games are hollow."""

    def __init__(self, points, provisional, parent=None):
        super().__init__(parent)
        self.points, self.provisional = points, provisional
        self.setMinimumSize(520, 200)

    def _pt(self, i, v):
        lo, hi = min(self.points) - 50, max(self.points) + 50
        w, h, n = self.width() - 60, self.height() - 30, max(1, len(self.points) - 1)
        return QPointF(50 + w * i / n, 15 + h * (1 - (v - lo) / max(1, hi - lo)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#fbfbf8"))
        if len(self.points) >= 2:
            p.setPen(QPen(QColor("#2f7de1"), 2))
            p.drawPolyline(QPolygonF([self._pt(i, v) for i, v in enumerate(self.points)]))
        for i, v in enumerate(self.points):
            hollow = 0 < i <= self.provisional
            p.setPen(QPen(QColor("#2f7de1"), 2))
            p.setBrush(QColor("#fbfbf8") if hollow else QColor("#2f7de1"))
            p.drawEllipse(self._pt(i, v), 3.5, 3.5)
        p.setPen(QColor("#555555"))
        for v in (min(self.points), max(self.points)):
            p.drawText(QPointF(4, self._pt(0, v).y() + 4), str(v))
        p.end()


class RatingHistoryDialog(QDialog):
    """Rating history (CM-23): the chart and your rated games, newest first."""

    def __init__(self, parent, profile, provisional_games):
        super().__init__(parent)
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
        import time as _t
        self.setWindowTitle("Rating history")
        self.resize(640, 520)
        v = QVBoxLayout(self)
        h = profile.history
        start = h[0]["before"] if h else profile.rating
        self.points = [start] + [e["after"] for e in h]
        v.addWidget(QLabel("<b>%s</b>: %d after %d rated game%s%s" % (
            profile.name, profile.rating, profile.games, "" if profile.games == 1 else "s",
            " (provisional)" if profile.provisional else "")))
        self.chart = RatingChart(self.points, provisional_games, self)
        v.addWidget(self.chart)
        self.table = QTableWidget(len(h), 5)
        self.table.setHorizontalHeaderLabels(["Date", "Opponent", "Colour", "Result", "Rating"])
        for i, e in enumerate(reversed(h)):
            res = {1.0: "won", 0.5: "drew", 0.0: "lost"}.get(e["result"], str(e["result"]))
            cells = [_t.strftime("%Y-%m-%d", _t.localtime(e["time"])), "%s (%d)" % (e["opponent"], e["opponent_rating"]),
                     {"w": "White", "b": "Black"}.get(e.get("colour"), ""), res,
                     "%d → %d (%+d)" % (e["before"], e["after"], e["after"] - e["before"])]
            for j, c in enumerate(cells):
                self.table.setItem(i, j, QTableWidgetItem(c))
        self.table.resizeColumnsToContents()
        v.addWidget(self.table)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        v.addWidget(close)
