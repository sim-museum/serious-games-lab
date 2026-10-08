"""chessIQ main window: Kramnik chess (no castling, capture anything) against the computer, hotseat, computer vs
computer, or another player over the network -- found through the Serious Games Week matchmaker."""
import os
import random
import threading
import time
import sys

from PyQt6.QtCore import QRectF, QSettings, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
                             QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTextBrowser,
                             QVBoxLayout, QWidget)

from . import VERSION
from . import engine as E
from . import serious_games_week
from .game import AI_NAME, MAX_DEPTH, THINK_S, Game, load_pgn
from . import academy, analysis, clock as clocks, cmbook, personalities, postgame, rating, tourney_ui, uci_engine
from .net import DEFAULT_PORT, Link

LIGHT, DARK = QColor("#f0d9b5"), QColor("#b58863")
LAST, SEL = QColor(246, 246, 105, 150), QColor(90, 160, 255, 140)
MOVE_DOT, ENEMY_RING, SELF_RING, BOOK = QColor(20, 20, 20, 90), QColor("#d04040"), QColor("#9b4dca"), QColor("#2f7de1")


def player_name():
    return (os.environ.get("SGW_NAME") or os.environ.get("USER") or "Player")[:24]


class BoardWidget(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self.board = E.init_board()
        self.orient = "w"
        self.last = None
        self.selected = None
        self.targets = []           # legal moves of the selected piece
        self.hints = []             # book moves
        self.font_family = "DejaVu Sans"

    def geometry_(self):
        side = min(self.width(), self.height())
        sq = side / 8.0
        return (self.width() - side) / 2, (self.height() - side) / 2, sq

    def square_at(self, x, y):
        ox, oy, sq = self.geometry_()
        dc, dr = int((x - ox) // sq), int((y - oy) // sq)
        if not (0 <= dc < 8 and 0 <= dr < 8):
            return None
        r, c = (dr, dc) if self.orient == "w" else (7 - dr, 7 - dc)
        return r * 8 + c

    def mousePressEvent(self, ev):
        i = self.square_at(ev.position().x(), ev.position().y())
        if i is not None:
            self.clicked.emit(i)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ox, oy, sq = self.geometry_()
        hint_from = {m.frm for m in self.hints}
        hint_to = {m.to for m in self.hints}
        targets = {}
        for m in self.targets:
            targets.setdefault(m.to, m.kind)
        coord_font = QFont(self.font_family, max(7, int(sq * 0.14)))
        piece_font = QFont(self.font_family, max(10, int(sq * 0.62)))
        for dr in range(8):
            for dc in range(8):
                r, c = (dr, dc) if self.orient == "w" else (7 - dr, 7 - dc)
                i = r * 8 + c
                rect = QRectF(ox + dc * sq, oy + dr * sq, sq, sq)
                p.fillRect(rect, LIGHT if (r + c) % 2 == 0 else DARK)
                if self.last and i in (self.last.frm, self.last.to):
                    p.fillRect(rect, LAST)
                if i == self.selected:
                    p.fillRect(rect, SEL)
                if i in hint_from:
                    p.setPen(QPen(BOOK, max(2, sq * 0.06)))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(rect.adjusted(sq * 0.04, sq * 0.04, -sq * 0.04, -sq * 0.04))
                piece = self.board[i]
                if piece:
                    # the font rasterizer draws the glyphs (filling them as QPainterPaths inverted the kings at
                    # some sizes): black = the solid glyph in black; white = the solid glyph in white as a body,
                    # then the outline glyph in black over it
                    p.setFont(piece_font)
                    flags = Qt.AlignmentFlag.AlignCenter
                    if piece[0] == "w":
                        p.setPen(QColor("#fdfdfd"))
                        p.drawText(rect, flags, E.GLYPH["b"][piece[1]])
                        p.setPen(QColor("#111"))
                        p.drawText(rect, flags, E.GLYPH["w"][piece[1]])
                    else:
                        p.setPen(QColor("#111"))
                        p.drawText(rect, flags, E.GLYPH["b"][piece[1]])
                if i in hint_to:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(BOOK)
                    p.drawEllipse(rect.center(), sq * 0.09, sq * 0.09)
                kind = targets.get(i)
                if kind == "move":
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(MOVE_DOT)
                    p.drawEllipse(rect.center(), sq * 0.15, sq * 0.15)
                elif kind:
                    p.setPen(QPen(SELF_RING if kind == "self" else ENEMY_RING, max(2, sq * 0.07)))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(rect.center(), sq * 0.42, sq * 0.42)
                p.setFont(coord_font)
                p.setPen(DARK if (r + c) % 2 == 0 else LIGHT)
                if dc == 0:
                    p.drawText(rect.adjusted(3, 2, 0, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                               str(8 - r))
                if dr == 7:
                    p.drawText(rect.adjusted(0, 0, -3, -2), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                               "abcdefgh"[c])
        p.end()


def think_time(clk, turn, ply, u):
    """Seconds a personality spends on a move (CM-15). Strength is set by search nodes, so this is only the pause a
    player would take: on a clock, its remaining time over the moves it still expects (50 at the start, never fewer than
    30, so a long game keeps a reserve) plus 60% of the increment, varied by u in [0, 1) between 0.4x and 1.6x, and
    never more than 8% of what is left; untimed, 0.8-3 s. At 10+3: about 13 s a move early, ~2.4 min left at move 60."""
    if not clk:
        return 0.8 + 2.2 * u
    rem = clk["wtime" if turn == "w" else "btime"] / 1000.0
    inc = clk["winc" if turn == "w" else "binc"] / 1000.0
    to_go = max(30, 50 - ply // 4)
    return max(0.4, min((rem / to_go + 0.6 * inc) * (0.4 + 1.2 * u), 0.08 * rem))


ENGINE_FAILED = object()            # the opponent's engine process died or stopped answering mid-search


class ThinkThread(QThread):
    """The search, off the UI thread (the GIL is shared, but Python switches often enough to keep the board live)."""
    done = pyqtSignal(int, object)

    def __init__(self, token, think, parent=None):
        super().__init__(parent)
        self.token, self.think = token, think

    def run(self):
        self.done.emit(self.token, self.think())


class OpponentDialog(QDialog):
    """Choose the computer opponent, as Chessmaster's opponent list does: filter by type and rating, search by name or
    style, and read the biography (CM-12)."""

    def __init__(self, people, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose your opponent")
        self.resize(760, 520)
        self.people = people
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        self.kind = QComboBox()
        for label, key in (("All opponents", ""), ("Chessmaster personalities", "Chessmaster"),
                           ("chessIQ's own", "chessIQ"), ("Self-capture specialists", "kansas"),
                           ("Neural networks (Leela, Maia)", "leela")):
            self.kind.addItem(label, key)
        self.lo, self.hi = QSpinBox(), QSpinBox()
        for sb, val in ((self.lo, 0), (self.hi, 3000)):
            sb.setRange(0, 3000); sb.setSingleStep(100); sb.setValue(val)
        self.search = QLineEdit()
        self.search.setPlaceholderText("name or style, e.g. attacker")
        for w in (QLabel("Show"), self.kind, QLabel("rated"), self.lo, QLabel("to"), self.hi, self.search):
            row.addWidget(w)
        v.addLayout(row)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.bio = QTextBrowser()
        body.addWidget(self.list, 3)
        body.addWidget(self.bio, 4)
        v.addLayout(body)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        for w in (self.kind, self.lo, self.hi):
            (w.currentIndexChanged if w is self.kind else w.valueChanged).connect(self.refill)
        self.search.textChanged.connect(self.refill)
        self.list.currentItemChanged.connect(self.show_bio)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept())
        self.refill(select=current)

    def matches(self, p):
        k = self.kind.currentData()
        if k == "leela" and p.engine != "leela":
            return False
        if k == "kansas" and not getattr(p, "kansas", 0):
            return False
        if k in ("Chessmaster", "chessIQ") and (p.source != k or p.engine == "leela"):
            return False
        if not self.lo.value() <= p.rating <= self.hi.value():
            return False
        q = self.search.text().strip().lower()
        return not q or q in p.name.lower() or q in (p.style or "").lower()

    def refill(self, *_, select=None):
        keep = select or self.chosen()
        self.list.clear()
        for p in self.people:
            if self.matches(p):
                it = QListWidgetItem("%-24s %4d   %s" % (p.name, p.rating, p.style[:40]))
                it.setData(Qt.ItemDataRole.UserRole, p.name)
                self.list.addItem(it)
                if p.name == keep:
                    self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def chosen(self):
        it = self.list.currentItem() if hasattr(self, "list") else None
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def show_bio(self, *_):
        p = next((p for p in self.people if p.name == self.chosen()), None)
        if p is None:
            self.bio.setHtml("")
            return
        kind = ("a neural network" if p.engine == "leela" else
                "a Chessmaster personality (from your installation)" if p.source == "Chessmaster" else
                "a self-capture specialist (chessIQ's own)" if getattr(p, "kansas", 0) else "chessIQ's own")
        from .lessons import LESSONS
        learn = [lesson.title for lesson in LESSONS if lesson.opponent == p.name]
        self.bio.setHtml("<h3>%s</h3><p><b>Rated %d</b> &middot; %s</p><p><i>%s</i></p><p>%s</p>%s"
                         % (p.name, p.rating, kind, p.style or "", (p.bio or "").replace("\n", "<br>"),
                            "<p>Learn the idea first: Academy &rarr; %s.</p>" % " and ".join(learn) if learn else ""))


class HostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host a network game")
        f = QFormLayout(self)
        self.name = QLineEdit(player_name())
        self.name.setMaxLength(24)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(DEFAULT_PORT)
        self.colour = QComboBox()
        self.colour.addItems(["White", "Black", "Random"])
        f.addRow("Your name:", self.name)
        f.addRow("Port (TCP):", self.port)
        f.addRow("You play:", self.colour)
        note = QLabel("Your game is listed on Serious Games Week while you wait." if serious_games_week.configured() else
                      "No Serious Games Week matchmaker is set up (sgw url ...): give your opponent this computer's address.")
        note.setWordWrap(True)
        f.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


class JoinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join a network game")
        v = QVBoxLayout(self)
        if serious_games_week.configured():
            g = QGroupBox("Games on Serious Games Week")
            gl = QVBoxLayout(g)
            self.games = QListWidget()
            self.games.currentItemChanged.connect(self._pick)
            self.games.itemDoubleClicked.connect(lambda _i: self.accept())
            gl.addWidget(self.games)
            b = QPushButton("Refresh")
            b.clicked.connect(self.refresh)
            gl.addWidget(b)
            v.addWidget(g)
        f = QFormLayout()
        self.name = QLineEdit(player_name())
        self.name.setMaxLength(24)
        self.host = QLineEdit("127.0.0.1")
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(DEFAULT_PORT)
        f.addRow("Your name:", self.name)
        f.addRow("Host address:", self.host)
        f.addRow("Port (TCP):", self.port)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        if serious_games_week.configured():
            QTimer.singleShot(0, self.refresh)

    def refresh(self):
        self.games.clear()
        found = serious_games_week.list_tables()
        for t in found:
            it = QListWidgetItem("%s  —  %s:%d" % (t.get("title") or "chessIQ game", t["host"], t["port"]))
            it.setData(Qt.ItemDataRole.UserRole, (t["host"], int(t["port"])))
            self.games.addItem(it)
        if not found:
            self.games.addItem("(no open games on Serious Games Week right now)")
        else:
            self.games.setCurrentRow(0)

    def _pick(self, item, _prev=None):
        hp = item.data(Qt.ItemDataRole.UserRole) if item else None
        if hp:
            self.host.setText(hp[0])
            self.port.setValue(hp[1])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("chessIQ — Kramnik chess")
        self.game = Game("ai", "w")
        self.orient = "w"
        self.review = None              # None = live; else showing the position after this many plies
        self.token = 0                  # bumps cancel any thinking or pending book move
        self.threads = []
        self._restarts = 0              # engine restarts in this game (one is allowed; never a stand-in engine)
        self._postgame_done, self.postgame = False, None   # the Post-Game Analysis window (CM-20)
        self.tourney, self.tourney_game = None, None      # the tournament window, and your game in it (CM-22)
        self.engine = None                  # the chosen personality's engine process (EPIC CM)
        self.profile = rating.Profile.load()  # your rating (CM-4); None until your first rated game
        self.rated = None                   # the rated game in progress: {opponent, rating, colour, recorded}
        self.clock = clocks.Clock()         # CM-5: the game's chess clock (untimed by default)
        self.note = ""
        self.link = None
        self.announcer = None
        self.my_name = player_name()
        self._build()
        self.new_game()

    # ---------------- layout ----------------
    def _build(self):
        central = QWidget()
        h = QHBoxLayout(central)
        self.boardw = BoardWidget()
        self.boardw.clicked.connect(self.on_square)
        h.addWidget(self.boardw, 3)
        side = QVBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setMinimumHeight(64)
        side.addWidget(self.status)
        grid = QGridLayout()
        self.mode = QComboBox()
        self.mode.addItem("Vs Computer", "ai")
        self.mode.addItem("Two Players (hotseat)", "human")
        self.mode.addItem("Computer vs Computer (watch)", "self")
        self.side = QComboBox()
        self.side.addItem("White", "w")
        self.side.addItem("Black", "b")
        grid.addWidget(QLabel("Opponent"), 0, 0)
        grid.addWidget(self.mode, 0, 1)
        grid.addWidget(QLabel("Play as"), 1, 0)
        grid.addWidget(self.side, 1, 1)
        side.addLayout(grid)
        # EPIC CM: choose the computer opponent -- a rating and a playing style (Chessmaster's personalities when
        # Chessmaster is installed, chessIQ's own otherwise). Without the engine build, chessIQ's own engine plays.
        self.who = QComboBox()
        self.people = sorted((p for p in personalities.roster()             # an opponent is offered only if its engine
                              if p.engine != "leela" or uci_engine.leela_available(p.net)),   # can run: never a
                             key=lambda p: p.rating) if uci_engine.available() else []        # stand-in under its name
        for p in self.people:
            self.who.addItem("%s (%d)%s" % (p.name, p.rating, " — " + p.style if p.style else ""), p.name)
        if not self.people:
            self.who.addItem("chessIQ classic (engine not built)", None)
        self.who.setCurrentIndex(self._default_opponent())
        grid.addWidget(QLabel("Computer"), 2, 0)
        pick = QHBoxLayout()
        pick.addWidget(self.who, 1)
        choose = QPushButton("Choose…")
        choose.setEnabled(bool(self.people))
        choose.clicked.connect(self.choose_opponent)
        pick.addWidget(choose)
        grid.addLayout(pick, 2, 1)
        self.rated_box = QCheckBox("Rated game (no take-backs; your rating changes)")
        self.rated_box.setChecked(QSettings("sim-museum", "chessIQ").value("rated", "false") == "true")
        self.rated_box.toggled.connect(lambda on: (QSettings("sim-museum", "chessIQ").setValue("rated", "true" if on else "false"),
                                                   self._show_opponent()))
        grid.addWidget(self.rated_box, 3, 0, 1, 2)
        self.tc = QComboBox()
        for label, kind, args in clocks.PRESETS:
            self.tc.addItem(label, (kind, args))
        self.tc.setCurrentIndex(int(QSettings("sim-museum", "chessIQ").value("timecontrol", 0)))
        self.tc.currentIndexChanged.connect(lambda i: QSettings("sim-museum", "chessIQ").setValue("timecontrol", i))
        grid.addWidget(QLabel("Time"), 4, 0)
        grid.addWidget(self.tc, 4, 1)
        # KS-6: the coach -- self-capture chances and traps on your turn, in unrated games against the computer
        self.coach_box = QCheckBox("Coach: point out self-capture chances and traps")
        self.coach_box.setToolTip("On your turn in an unrated game, a quick search with self-capture on and off. "
                                  "Off in rated games, which allow no advice.")
        self.coach_box.setChecked(QSettings("sim-museum", "chessIQ").value("coach", "true") == "true")
        self.coach_box.toggled.connect(lambda on: (QSettings("sim-museum", "chessIQ").setValue(
            "coach", "true" if on else "false"), self.maybe_coach()))
        grid.addWidget(self.coach_box, 5, 0, 1, 2)
        self.coach_label = QLabel("")
        self.coach_label.setWordWrap(True)
        self.coach_rs, self.coach_thread, self.coach_lock = None, None, threading.Lock()
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("font-family: monospace; font-size: 13pt")
        side.addWidget(self.clock_label)
        side.addWidget(self.coach_label)
        # CM-6: the opening helper -- what the grandmasters played in this position (also in rated games, as in
        # Chessmaster, whose coach may show opening moves during ranked play)
        self.openings = QLabel()
        self.openings.setWordWrap(True)
        self.openings.setTextFormat(Qt.TextFormat.RichText)
        self.openings.setStyleSheet("font-size: 9pt")
        side.addWidget(self.openings)
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._on_tick)
        self.tick.start(200)
        self.blurb = QLabel()
        self.blurb.setWordWrap(True)
        self.blurb.setStyleSheet("color: gray; font-size: 9pt")
        side.addWidget(self.blurb)
        self.who.currentIndexChanged.connect(self._show_opponent)
        self._show_opponent()
        self.new_btn = QPushButton("New Game")
        self.new_btn.clicked.connect(self.new_game)
        side.addWidget(self.new_btn)
        row = QHBoxLayout()
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo)
        flip = QPushButton("Flip")
        flip.clicked.connect(self.flip)
        self.offer_btn = QPushButton("Offer draw")
        self.offer_btn.clicked.connect(self.offer_draw)
        self.resign_btn = QPushButton("Resign")
        self.resign_btn.clicked.connect(self.resign)
        for b in (self.undo_btn, flip, self.offer_btn, self.resign_btn):
            row.addWidget(b)
        side.addLayout(row)
        row = QHBoxLayout()
        save = QPushButton("Save PGN")
        save.clicked.connect(self.save_pgn)
        load = QPushButton("Load PGN")
        load.clicked.connect(self.load_pgn_file)
        row.addWidget(save)
        row.addWidget(load)
        side.addLayout(row)
        row = QHBoxLayout()
        for label, fn in (("⏮", lambda: self.go_to(0)), ("◀", lambda: self.nav(-1)),
                          ("▶", lambda: self.nav(1)), ("⏭", lambda: self.go_to(len(self.game.history)))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        side.addLayout(row)
        self.offer_bar = QFrame()
        ob = QHBoxLayout(self.offer_bar)
        self.offer_label = QLabel("Your opponent offers a draw.")
        acc = QPushButton("Accept")
        acc.clicked.connect(self.accept_draw)
        dec = QPushButton("Decline")
        dec.clicked.connect(self.decline_draw)
        ob.addWidget(self.offer_label, 1)
        ob.addWidget(acc)
        ob.addWidget(dec)
        self.offer_bar.setStyleSheet("QFrame { background: #fff3c4; border-radius: 4px; }")
        self.offer_bar.hide()
        side.addWidget(self.offer_bar)
        legend = QLabel("<span style='color:#555'>●</span> legal move &nbsp; "
                        "<span style='color:#d04040'>◯</span> capture enemy<br>"
                        "<span style='color:#9b4dca'>◯</span> capture your own piece (legal here!)<br>"
                        "<span style='color:#2f7de1'>●</span> book move — what the grandmasters played here")
        legend.setStyleSheet("font-size: 9pt")
        side.addWidget(legend)
        self.moves = QTextBrowser()
        self.moves.setOpenLinks(False)
        self.moves.anchorClicked.connect(lambda url: self.go_to(int(url.toString().lstrip("#"))))
        side.addWidget(self.moves, 1)
        self.chat_box = QGroupBox("Chat")
        cl = QVBoxLayout(self.chat_box)
        self.chat_log = QPlainTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setMaximumHeight(110)
        self.chat_in = QLineEdit()
        self.chat_in.setPlaceholderText("Say something to your opponent, then Enter")
        self.chat_in.returnPressed.connect(self.send_chat)
        cl.addWidget(self.chat_log)
        cl.addWidget(self.chat_in)
        self.chat_box.hide()
        side.addWidget(self.chat_box)
        sw = QWidget()
        sw.setLayout(side)
        sw.setMaximumWidth(380)
        h.addWidget(sw, 2)
        self.setCentralWidget(central)
        net = self.menuBar().addMenu("&Network")
        self.host_act = QAction("&Host a network game...", self)
        self.host_act.triggered.connect(self.host_dialog)
        self.join_act = QAction("&Join a network game...", self)
        self.join_act.triggered.connect(self.join_dialog)
        self.leave_act = QAction("&Leave the network game", self)
        self.leave_act.triggered.connect(self.leave_network)
        self.leave_act.setEnabled(False)
        for a in (self.host_act, self.join_act, self.leave_act):
            net.addAction(a)
        rm = self.menuBar().addMenu("&Rating")
        hist = QAction("Rating &history...", self)
        hist.triggered.connect(self.rating_history)
        rm.addAction(hist)
        tm = self.menuBar().addMenu("&Tournament")
        for label, fn in (("&New tournament...", self.tournament_new), ("&Resume the saved tournament",
                                                                          self.tournament_resume),
                          ("&Show the tournament window", self.tournament_show)):
            act = QAction(label, self)
            act.triggered.connect(fn)
            tm.addAction(act)
        am = self.menuBar().addMenu("&Academy")
        tour = QAction("Kansas &tour for first-time players...", self)
        tour.triggered.connect(self.tour_open)
        am.addAction(tour)
        acad = QAction("Kramnik &Academy: lessons on self-capture...", self)
        acad.triggered.connect(self.academy_open)
        am.addAction(acad)
        puz = QAction("Kansas &puzzles...", self)
        puz.triggered.connect(self.puzzles_open)
        am.addAction(puz)
        self.academy, self.puzzles, self.tour = None, None, None
        self.resize(1000, 680)

    def welcome(self):
        """A new player's first look (KS-8, KS-13): the game looks ordinary, so open the Kansas tour."""
        if self.profile is None and not academy.load_state():
            self.note = ("New to Kramnik chess? It looks like ordinary chess, but it isn't. The Kansas tour "
                         "(Academy menu) shows the difference in five minutes.")
            self.render()
            if os.environ.get("CHESSIQ_TOUR", "1") != "0":
                self.tour_open()

    def tour_open(self):
        """The Kansas tour (KS-13): the rules, four boards, then a first game against Hal."""
        if self.tour is None:
            self.tour = academy.TourWindow(self)
        self.tour.show(); self.tour.raise_()

    def academy_open(self):
        """The Kramnik Academy (KS-4): lessons and positions on what self-capture changes."""
        if self.academy is None:
            self.academy = academy.AcademyWindow(self)
        self.academy.show(); self.academy.raise_()

    def puzzles_open(self):
        """Kansas puzzles (KS-5): one at a time near your puzzle rating."""
        if self.puzzles is None:
            self.puzzles = academy.PuzzleWindow(self)
        self.puzzles.show(); self.puzzles.raise_()

    # ---------------- game flow ----------------
    def choose_opponent(self):
        d = OpponentDialog(self.people, self.who.currentData(), self)
        if d.exec() and d.chosen():
            self.who.setCurrentIndex(self.who.findData(d.chosen()))

    def _default_opponent(self):
        """The opponent nearest 1500, the first time; afterwards the last one chosen."""
        last = QSettings("sim-museum", "chessIQ").value("opponent", "")
        names = [p.name for p in self.people]
        if last in names:
            return names.index(last)
        return min(range(len(self.people)), key=lambda i: abs(self.people[i].rating - 1500)) if self.people else 0

    def _opp_name(self):
        """The name of the opponent actually playing this game (the picker may already show the next one)."""
        return self.engine.p.name if self.engine is not None else "The computer"

    def _opponent(self):
        name = self.who.currentData()
        return next((p for p in self.people if p.name == name), None)

    def _show_opponent(self):
        p = self._opponent()
        if p is None:
            self.blurb.setText("chessIQ's own engine at full strength. Build the personality engine "
                               "(engine/build_engine.sh) to choose opponents by rating and style.")
            return
        text = "%s, rated %d. %s" % (p.name, p.rating, p.style + "." if p.style else "")
        if getattr(self, "rated_box", None) is not None and self.rated_box.isChecked():
            if self.profile is None:
                text += "<br>Your first rated game: you will be asked about your experience for a starting rating."
            else:
                loss, draw, win = self.profile.preview(p.rating)
                text += ("<br>Your rating %d%s. This game: loss %+d, draw %+d, win %+d."
                         % (self.profile.rating, " (provisional, %d of %d games)" % (self.profile.games, rating.PROVISIONAL)
                            if self.profile.provisional else "", loss, draw, win))
        self.blurb.setText(text)
        self.who.setToolTip(p.bio or p.style)
        QSettings("sim-museum", "chessIQ").setValue("opponent", p.name)

    def _start_engine(self):
        p = self._opponent()
        if self.engine is not None and (p is None or self.engine.p is not p):
            self.engine.stop()
            self.engine.close()
            self.engine = None
        if p is not None and self.engine is None:
            try:
                self.engine = (uci_engine.LeelaEngine(p) if p.engine == "leela" else uci_engine.PersonalityEngine(p))
            except OSError:
                self.engine = None
        elif self.engine is not None:
            try:
                self.engine.stop()
                self.engine.new_game()
            except (OSError, RuntimeError, ValueError):     # it died between games: start a fresh one
                try:
                    self.engine.close()
                except Exception:
                    pass
                self.engine = None
                self._start_engine()

    def _on_tick(self):
        g, c = self.game, self.clock
        if not c.timed:
            self.clock_label.setText("")
            return
        f = c.check_flag()
        if f and not g.over:
            winner = E.opp(f)
            if self._cannot_mate(winner):
                g.over = {"type": "draw", "reason": "flag fall, but the other side cannot mate"}
            else:
                g.over = {"type": "time", "winner": winner}
            c.stop()
            self.token += 1                            # stop any thinking
            if self.engine is not None:
                self.engine.stop()
            self.render()
        mark = lambda col: "▶" if c.running == col and not g.over else " "
        self.clock_label.setText("%s White %s   %s Black %s" % (mark("w"), clocks.fmt(c.remaining("w")),
                                                                  mark("b"), clocks.fmt(c.remaining("b"))))

    def _cannot_mate(self, colour):
        """FIDE: a player whose flag falls draws if the opponent cannot mate by any series of legal moves.
        Approximated as the side having only its king, or king and one minor piece."""
        pieces = [p[1] for p in self.game.board if p and p[0] == colour and p[1] != "k"]
        return not pieces or (len(pieces) == 1 and pieces[0] in "nb")

    def _opponent_book(self):
        """The chosen Chessmaster personality's own opening book, cut at castling (cached), or None."""
        p = self._opponent()
        if p is None or p.source != "Chessmaster" or not p.book:
            return None
        cache = self.__dict__.setdefault("_books", {})
        if p.book not in cache:
            path = cmbook.find_book(personalities.chessmaster_dir() or "", p.book)
            try:
                cache[p.book] = cmbook.read_obk(path) if path else None
            except (OSError, ValueError):
                cache[p.book] = None
        return cache[p.book]

    def _advice_off(self):
        """Chessmaster's Ranked Play: "no advice tools are available" -- from the first position until the game ends."""
        r = self.rated
        return r is not None and not r["recorded"] and not self.game.over

    def _rated_in_progress(self):
        r = self.rated
        return r is not None and not r["recorded"] and not self.game.over and self.game.history

    def _record_rated(self, score, why=""):
        r = self.rated
        if r is None or r["recorded"] or self.profile is None:
            return
        r["recorded"] = True
        me, them = player_name(), "%s (%d)" % (r["opponent"], r["rating"])
        pgn = self.game.pgn(*((me, them) if r["colour"] == "w" else (them, me)))
        d = self.profile.record(r["opponent"], r["rating"], score, r["colour"], len(self.game.history), pgn)
        self.note = "Rated%s: your rating %+d → %d." % (" (" + why + ")" if why else "", d, self.profile.rating)
        r["line"] = "Your rating: %+d → %d." % (d, self.profile.rating)
        self._show_opponent()

    def _ensure_profile(self):
        if self.profile is not None:
            return True
        labels = [l for l, _ in rating.LEVELS]
        choice, ok = QInputDialog.getItem(self, "Your first rated game",
                                          "Chessmaster-style ratings start from an estimate. How much chess do you play?",
                                          labels, 2, False)
        if not ok:
            return False
        self.profile = rating.Profile(player_name(), dict(rating.LEVELS)[choice])
        self.profile.save()
        return True

    def _adjourn(self):
        """Save the rated game in progress to finish later (CM-11): moves, clocks, stakes."""
        r, g, c = self.rated, self.game, self.clock
        c.stop()
        rating.save_adjourned({"opponent": r["opponent"], "rating": r["rating"], "colour": r["colour"],
                               "sans": [h["san"] for h in g.history],
                               "clock": {"kind": c.kind, "args": list(c.args), "left": c.left, "moves": c.moves}})
        r["recorded"] = True                     # nothing to record now; the result comes when it is finished

    def _resume_adjourned(self, state):
        """Recreate an adjourned rated game: the same opponent, moves, clocks and stakes."""
        i = next((i for i in range(self.who.count()) if self.who.itemData(i) == state["opponent"]), -1)
        if i < 0:
            QMessageBox.information(self, "Adjourned game", "%s is no longer available; the game cannot be resumed."
                                    % state["opponent"])
            rating.clear_adjourned()
            return False
        self.who.setCurrentIndex(i)
        self.mode.setCurrentIndex(self.mode.findData("ai"))
        self.side.setCurrentIndex(self.side.findData(state["colour"]))
        self._start_engine()
        self.game = Game("ai", state["colour"])
        self.game.opp_book = self._opponent_book()
        for san in state["sans"]:
            m = self.game.move_from_san(san)
            if m is None:
                break
            self.game.do_move(m)
        ck = state["clock"]
        self.clock = clocks.Clock(ck["kind"], ck["args"])
        self.clock.left, self.clock.moves = {k: float(v) for k, v in ck["left"].items()}, dict(ck["moves"])
        self.clock.start(self.game.turn)
        self.rated = {"opponent": state["opponent"], "rating": state["rating"], "colour": state["colour"],
                      "recorded": False}
        rating.clear_adjourned()
        return True

    def new_game(self):
        if self._rated_in_progress():
            box = QMessageBox(self)
            box.setWindowTitle("The rated game is not finished")
            box.setText("Adjourn it to finish later, or resign it (a loss)?")
            adj = box.addButton("Adjourn", QMessageBox.ButtonRole.AcceptRole)
            res = box.addButton("Resign", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is adj:
                self._adjourn()
            elif box.clickedButton() is res:
                self._record_rated(0, "resigned")
            else:
                return
        if self.link is None and self.rated_box.isChecked() and self.mode.currentData() == "ai":
            st = rating.load_adjourned()
            if st and QMessageBox.question(self, "Adjourned game",
                                           "Resume your adjourned rated game against %s (after %d moves)?"
                                           % (st["opponent"], len(st["sans"]))) == QMessageBox.StandardButton.Yes:
                self.token += 1
                self.review = None
                if self._resume_adjourned(st):
                    self.orient = self.game.human
                    self.boardw.selected, self.boardw.targets = None, []
                    self.note = "Resumed: rated game against %s." % st["opponent"]
                    self.offer_bar.hide()
                    self.render()
                    self.maybe_ai()
                    return
        if self.link is not None:
            if not self.link.is_host or self.link.sock is None:
                return                      # in a network game only the host starts games, once a guest is here
            colour = "w" if self.game.human == "b" else "b"     # swap colours each new game
            self.link.start_game(E.opp(colour))
            self._start_net_game(colour)
            return
        self.token += 1
        self.review = None
        self._restarts = 0
        self._postgame_done = False
        self.tourney_game = None                    # a tournament game is linked after it starts (play_mine)
        self._start_engine()
        self.game = Game(self.mode.currentData(), self.side.currentData())
        self.game.opp_book = self._opponent_book()
        self.rated = None
        p = self._opponent()
        if self.rated_box.isChecked() and self.game.mode == "ai" and p is not None and self._ensure_profile():
            self.rated = {"opponent": p.name, "rating": p.rating, "colour": self.game.human, "recorded": False}
            self._show_opponent()
        kind, args = self.tc.currentData()
        if self.rated is not None and kind == "untimed":
            kind, args = "fischer", (10, 3)            # Chessmaster's ranked play has no infinite time
            self._pending_note = "Rated games are timed: Fischer 10+3."
        self.clock = clocks.Clock(kind, args)
        self.clock.start("w")
        self.orient = "w" if self.game.mode == "self" else self.game.human
        self.boardw.selected, self.boardw.targets = None, []
        self.note, self._pending_note = getattr(self, "_pending_note", ""), ""
        self.offer_bar.hide()
        self.render()
        self.maybe_ai()

    def do_move(self, m, remote=False):
        self.offer_bar.hide()
        self.note = ""
        mover = self.game.turn
        said = self._self_capture_words(m) if m.kind == "self" and not self.rated else ""
        san = self.game.do_move(m)
        if said:
            self.note = "%s %s: %s." % (san, said[0], said[1])
        if self.game.over:
            self.clock.stop()
        elif self.clock.moved(mover):
            self._on_tick()                            # moved after the flag fell
        self.boardw.selected, self.boardw.targets = None, []
        if self.link is not None and not remote:
            self.link.send(t="move", ply=len(self.game.history) - 1, san=san)
        self.render()
        self.maybe_ai()
        self.maybe_coach()

    def _self_capture_words(self, m):
        """Who self-captured and what it does, for the status line (KS: the moment shows as it happens). Unrated only,
        like all commentary during play."""
        from . import kansas as K
        g = self.game
        who = ("you" if g.mode == "ai" and g.turn == g.human else self._opp_name() if g.mode == "ai" else
               "White" if g.turn == "w" else "Black")
        return "by " + who, K.phrase(K.motif(g.board, g.turn, g.ep, m), g.board[m.frm][1], g.board[m.to][1])

    # ---------------- the coach (KS-6) ----------------
    def maybe_coach(self):
        """Start the coach's look at the position if it is the local player's turn in an unrated computer game."""
        g = self.game
        self.coach_label.setText("")
        if (not self.coach_box.isChecked() or self.rated or g.mode != "ai" or g.over or not g.local_to_move()
                or self.review is not None or not analysis.available()):
            return
        from . import kansas as K
        fen, ply = K.to_fen(g.board, g.turn, g.ep, g.half, len(g.history) // 2 + 1), len(g.history)

        def look():
            with self.coach_lock:
                if self.coach_rs is None:
                    self.coach_rs = K.RuleSwitch(analysis.BINARY, analysis.VARIANTS, 30000)
                try:
                    return K.coach(fen, self.coach_rs)
                except (OSError, RuntimeError, ValueError):
                    return None
        th = ThinkThread(ply, look)
        th.done.connect(self._coached)
        th.finished.connect(lambda: self.threads.remove(th) if th in self.threads else None)
        self.threads.append(th)
        th.start()

    def _coached(self, ply, word):
        g = self.game
        if word is None or ply != len(g.history) or g.over or not g.local_to_move() or self.rated:
            return
        colour = "#1a7f37" if word[0] == "chance" else "#b35900"
        self.coach_label.setText("<span style='color:%s'><b>Coach:</b> %s</span>" % (colour, word[1]))

    def on_square(self, i):
        g = self.game
        if self.review is not None or not g.local_to_move():
            return
        if self.link is not None and self.link.sock is None:
            return
        bw = self.boardw
        if bw.selected is not None:
            hits = [m for m in bw.targets if m.to == i]
            if hits:
                if len(hits) > 1 and hits[0].promo:
                    m = self.ask_promo(hits)
                    if m is None:
                        return
                    self.do_move(m)
                else:
                    self.do_move(hits[0])
                return
        p = g.board[i]
        if p and p[0] == g.turn:
            bw.selected = i
            bw.targets = [m for m in g.legal() if m.frm == i]
        else:
            bw.selected, bw.targets = None, []
        self.render()

    def ask_promo(self, hits):
        d = QDialog(self)
        d.setWindowTitle("Promote to")
        row = QHBoxLayout(d)
        chosen = []
        for t in "qrbn":
            b = QPushButton(E.GLYPH[self.game.turn][t])
            b.setFont(QFont("DejaVu Sans", 28))
            b.clicked.connect(lambda _c=False, t=t: (chosen.append(t), d.accept()))
            row.addWidget(b)
        d.exec()
        return next((m for m in hits if chosen and m.promo == chosen[0]), None)

    def maybe_ai(self):
        g = self.game
        if self.review is not None or not g.computer_to_move():
            return
        self.render(thinking=True)
        tok, turn = self.token, g.turn
        bm = g.book_move()                  # the GM no-castling book first
        if bm is not None:
            declines = g.p_offer["pending"]  # still in book = far too early to agree a draw
            g.p_offer["pending"] = False

            def play():
                if tok != self.token or g is not self.game or g.over or g.turn != turn:
                    return
                self.do_move(bm)
                if declines:
                    self.note = "%s declines your draw offer — far too early." % self._opp_name()
                    self.render()
            QTimer.singleShot(300 + int(random.random() * 400), play)
            return
        if self.engine is not None:
            clk = self.clock.uci() if self.clock.timed else None
            moves, eng, legal = [E.sqname(h["m"].frm) + E.sqname(h["m"].to) + (h["m"].promo or "") for h in g.history], \
                self.engine, g.legal()

            target = think_time(clk, turn, len(moves), random.random())

            def think():                    # the chosen personality (EPIC CM)
                t0 = time.monotonic()
                try:
                    u = eng.choose(moves, clock=clk) if clk else eng.choose(moves, movetime_ms=int(THINK_S * 1000))
                except (OSError, RuntimeError, ValueError):
                    return ENGINE_FAILED
                if u is None and legal:     # closed under us, or died: not "no legal move"
                    return ENGINE_FAILED
                while time.monotonic() - t0 < target and self.token == tok:   # CM-15: think like a player
                    time.sleep(0.05)
                return next((m for m in legal if E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "") == u), None)
        else:
            board, turn_, ep, banned = g.board[:], g.turn, g.ep, g.banned_keys()

            def think():                    # chessIQ's own engine (no personality engine built)
                return E.best_move(board, turn_, ep, t=THINK_S, d=MAX_DEPTH, banned=banned,
                                   cancel=lambda: self.token != tok)
        th = ThinkThread(tok, think)
        th.done.connect(self._thought)
        th.finished.connect(lambda: self.threads.remove(th) if th in self.threads else None)
        self.threads.append(th)
        th.start()

    def _thought(self, tok, m):
        g = self.game
        if tok != self.token or g.over:
            return
        if m is ENGINE_FAILED:
            if self._restarts < 1:          # restart the same opponent once and carry on
                self._restarts += 1
                name = self._opp_name()
                try:
                    self.engine.close()
                except Exception:
                    pass
                self.engine = None
                self._start_engine()
                self.note = "%s's engine stopped and was restarted." % name
                self.maybe_ai()
            else:
                self.note = "The opponent's engine failed again. Save the game (Save PGN) and start a new one."
                self.render()
            return
        if m is None:
            g.check_end()
            self.render()
            return
        if g.p_offer["pending"]:
            g.p_offer["pending"] = False
            if g.ai_accepts_draw(m):
                g.over = {"type": "draw", "reason": "by agreement"}
                self.render()
                return
            self.do_move(m)
            if not g.over:
                self.note = "%s declines your draw offer — play on." % self._opp_name()
                self.render()
            return
        offer = g.ai_offers_draw(m)
        self.do_move(m)
        if offer and not g.over:
            g.offers = {"count": g.offers["count"] + 1, "last_ply": len(g.history)}
            self.offer_label.setText("%s offers a draw." % self._opp_name())
            self.offer_bar.show()

    def undo(self):
        if self.link is not None or not self.game.history:
            return
        if self._rated_in_progress():
            self.note = "No take-backs in a rated game."
            self.render()
            return
        self.token += 1
        self.review = None
        self.game.undo()
        self.boardw.selected, self.boardw.targets = None, []
        self.offer_bar.hide()
        if self.game.mode == "self":
            self.note = "Self-play paused — press ⏭ to resume."
        self.render()

    def flip(self):
        self.orient = E.opp(self.orient)
        self.render()

    def go_to(self, ply):
        self.review = None if ply >= len(self.game.history) else max(0, ply)
        self.boardw.selected, self.boardw.targets = None, []
        self.render()
        if self.review is None:
            self.maybe_ai()

    def nav(self, delta):
        n = len(self.game.history)
        self.go_to(max(0, (n if self.review is None else self.review) + delta))

    # ---------------- draws and resignation ----------------
    def offer_draw(self):
        g = self.game
        if g.over or self.review is not None:
            return
        if g.mode == "self":
            self.note = "You are only watching — they decide."
        elif g.mode == "human":
            self.offer_label.setText("%s offers a draw." % ("White" if g.turn == "w" else "Black"))
            self.offer_bar.show()
        elif g.mode == "net":
            if self.link and self.link.sock is not None:
                self.link.send(t="draw_offer")
                self.note = "Draw offered — waiting for %s." % self.link.peer_name
        elif g.turn != g.human or g.p_offer["pending"]:
            return
        elif len(g.history) - g.p_offer["last_ply"] < 12:
            self.note = "Too soon to offer again."
        else:
            g.p_offer = {"pending": True, "last_ply": len(g.history)}
            self.note = "Draw offered — make your move; %s will answer with theirs." % self._opp_name()
        self.render()

    def accept_draw(self):
        if self.game.over or not self.offer_bar.isVisible():
            return
        self.token += 1
        if self.game.mode == "net" and self.link:
            self.link.send(t="draw_accept")
        self.game.over = {"type": "draw", "reason": "by agreement"}
        self.offer_bar.hide()
        self.render()

    def decline_draw(self):
        if self.game.mode == "net" and self.link:
            self.link.send(t="draw_decline")
        self.offer_bar.hide()

    def resign(self, confirm=True):
        g = self.game
        if g.over or self.review is not None:
            return
        if g.mode == "self":
            self.note = "You are only watching — they decide."
            self.render()
            return
        loser = g.turn if g.mode == "human" else g.human
        if confirm and QMessageBox.question(self, "Resign", "%s resigns — are you sure?" %
                                            ("White" if loser == "w" else "Black")) != QMessageBox.StandardButton.Yes:
            return
        self.token += 1
        if g.mode == "net" and self.link:
            self.link.send(t="resign")
        g.over = {"type": "resign", "winner": E.opp(loser)}
        g.p_offer["pending"] = False
        self.offer_bar.hide()
        self.render()

    # ---------------- PGN ----------------
    def _pgn_dir(self):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "savedGames")
        return d if os.path.isdir(d) else os.path.expanduser("~")

    def save_pgn(self):
        import time
        name = "chessiq_%s.pgn" % time.strftime("%Y%m%d_%H%M")
        path, _ = QFileDialog.getSaveFileName(self, "Save PGN", os.path.join(self._pgn_dir(), name),
                                              "PGN (*.pgn)")
        if path:
            peer = self.link.peer_name if self.link else "Opponent"
            with open(path, "w") as f:
                f.write(self.game.pgn(*self.game.names(self.my_name, peer)))

    def load_pgn_file(self):
        if self.link is not None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load PGN", self._pgn_dir(), "PGN (*.pgn *.txt)")
        if path:
            with open(path, errors="replace") as f:
                self.load_pgn_text(f.read())

    def load_pgn_text(self, text):
        self.token += 1
        g, bad = load_pgn(text)
        self.game = g
        self.mode.setCurrentIndex(max(0, self.mode.findData(g.mode)))
        self.side.setCurrentIndex(max(0, self.side.findData(g.human)))
        self.orient = "w" if g.mode == "self" else g.human
        self.review = None
        self.offer_bar.hide()
        self.render()
        if bad:
            QMessageBox.warning(self, "Load PGN", "Loaded %d move(s); could not interpret \"%s\". The rest was "
                                "skipped." % (len(g.history), bad))
        self.maybe_ai()                 # unfinished game and it's the computer's move: it plays on

    # ---------------- network ----------------
    def host_dialog(self):
        d = HostDialog(self)
        if d.exec():
            colour = {0: "w", 1: "b"}.get(d.colour.currentIndex(), random.choice("wb"))
            self.start_hosting(d.name.text().strip() or "Host", d.port.value(), colour)

    def join_dialog(self):
        d = JoinDialog(self)
        if d.exec():
            self.start_joining(d.name.text().strip() or "Guest", d.host.text().strip(), d.port.value())

    def _net_ui(self, on):
        for w in (self.mode, self.side, self.undo_btn):
            w.setEnabled(not on)
        self.host_act.setEnabled(not on)
        self.join_act.setEnabled(not on)
        self.leave_act.setEnabled(on)
        self.chat_box.setVisible(on)

    def start_hosting(self, name, port, colour):
        self.my_name = name
        link = Link(name, self)
        if not link.host(port):
            QMessageBox.warning(self, "Host", "Could not listen on TCP port %d." % port)
            return False
        self.link, self.host_colour = link, colour
        link.connected.connect(self._guest_arrived)
        self._wire(link)
        self._net_ui(True)
        self.token += 1
        self.game = Game("net", colour)
        self.clock = clocks.Clock()                    # network games are untimed (a shared clock is later work)
        self.rated = None
        self.orient = colour
        self._announce()
        self.note = "Hosting on TCP %d — waiting for an opponent%s." % (
            link.port, " (listed on Serious Games Week)" if self.announcer and self.announcer.proc else "")
        self.render()
        return True

    def _announce(self):
        if self.announcer is None:
            self.announcer = serious_games_week.Announcer()
        self.announcer.start(self.link.port, "%s's chessIQ game" % self.my_name, name=self.my_name, max_players=2,
                             version=VERSION)

    def _guest_arrived(self, peer):
        if self.announcer:
            self.announcer.stop()       # a two-player game is full: off the list
        self.chat_log.appendPlainText("%s joined." % peer)
        self.link.start_game(E.opp(self.host_colour))
        self._start_net_game(self.host_colour)

    def start_joining(self, name, host, port):
        self.my_name = name
        link = Link(name, self)
        self.link = link
        link.started.connect(self._start_net_game)
        link.connected.connect(lambda peer: self.chat_log.appendPlainText("Playing %s." % peer))
        self._wire(link)
        self._net_ui(True)
        self.token += 1
        self.note = "Connecting to %s:%d ..." % (host, port)
        self.render()
        link.join(host, port)

    def _wire(self, link):
        link.moved.connect(self._remote_move)
        link.draw_offered.connect(self._remote_offer)
        link.draw_answered.connect(self._remote_answer)
        link.resigned.connect(self._remote_resign)
        link.chat.connect(lambda text: self.chat_log.appendPlainText("%s: %s" % (link.peer_name, text)))
        link.closed.connect(self._peer_gone)

    def _start_net_game(self, colour):
        self.token += 1
        self.review = None
        self.game = Game("net", colour)
        self.clock = clocks.Clock()                    # network games are untimed (a shared clock is later work)
        self.rated = None
        self.orient = colour
        self.boardw.selected, self.boardw.targets = None, []
        self.offer_bar.hide()
        self.note = "New game against %s — you play %s." % (self.link.peer_name,
                                                                 "White" if colour == "w" else "Black")
        self.new_btn.setEnabled(self.link.is_host)
        self.render()

    def _remote_move(self, ply, san):
        g = self.game
        m = g.move_from_san(san) if (ply == len(g.history) and not g.over and g.turn != g.human) else None
        if m is None:
            why = "%s sent a move this board cannot play (%s at ply %d); the connection was closed." % (
                self.link.peer_name, san, ply)
            self.chat_log.appendPlainText(why)
            self.link.close()
            self.note = why
            self.render()
            return
        self.review = None
        self.do_move(m, remote=True)

    def _remote_offer(self):
        if not self.game.over:
            self.offer_label.setText("%s offers a draw." % self.link.peer_name)
            self.offer_bar.show()

    def _remote_answer(self, accepted):
        if accepted and not self.game.over:
            self.game.over = {"type": "draw", "reason": "by agreement"}
        self.note = "" if accepted else "%s declines the draw — play on." % self.link.peer_name
        self.render()

    def _remote_resign(self):
        if not self.game.over:
            self.game.over = {"type": "resign", "winner": self.game.human}
            self.render()

    def _peer_gone(self, why):
        self.chat_log.appendPlainText(why)
        if self.link and self.link.is_host:
            self.note = "%s — waiting for another opponent." % why
            self.new_btn.setEnabled(False)
            self._announce()            # back on the list
        else:
            self.note = why
        self.render()

    def send_chat(self):
        text = self.chat_in.text().strip()
        if text and self.link and self.link.sock is not None:
            self.link.send(t="chat", text=text[:300])
            self.chat_log.appendPlainText("%s: %s" % (self.my_name, text))
        self.chat_in.clear()

    def leave_network(self):
        if self.announcer:
            self.announcer.stop()
        if self.link:
            self.link.close()
            self.link.deleteLater()
        self.link = None
        self._net_ui(False)
        self.new_btn.setEnabled(True)
        self.new_game()

    def closeEvent(self, ev):
        self.token += 1
        if self.postgame is not None:
            self.postgame.close()
        if self.tourney is not None:
            self.tourney.close()
        if self.announcer:
            self.announcer.stop()
        if self.link:
            self.link.close()
        if self._rated_in_progress():
            self._adjourn()                         # as Chessmaster does: closing adjourns the rated game
        if self.engine is not None:
            self.engine.stop()
        for th in list(self.threads):
            th.wait(3000)
        if self.engine is not None:
            self.engine.close()
        if self.coach_rs is not None:
            self.coach_rs.close()
        for w in (self.academy, self.puzzles, self.tour):
            if w is not None:
                w.close()
        super().closeEvent(ev)

    # ---------------- drawing ----------------
    def render(self, thinking=False):
        g = self.game
        live = self.review is None
        ply = len(g.history) if live else self.review
        bw = self.boardw
        bw.board = g.board if live else g.board_at(ply)
        bw.orient = self.orient
        bw.last = g.history[ply - 1]["m"] if ply > 0 else None
        bw.hints = g.book_hints() if (live and g.local_to_move() and g.mode != "net" and not self._advice_off()) else []
        if not live:
            bw.selected, bw.targets = None, []
        bw.update()
        self.status.setText(self._status_html(thinking))
        self._render_moves(ply)
        stats = g.book_stats(ply)
        if self._advice_off():
            self.openings.setText("<span style='color:gray'>No advice during a rated game.</span>")
        elif stats:
            total = sum(n for _, n, _ in stats)
            top = [x for x in stats if x[2] >= 1.0][:6] or stats[:3]
            shown = " · ".join("<b>%s</b> %.0f%%" % (m, pct) for m, _, pct in top)
            more = " · %d rarer" % (len(stats) - len(top)) if len(stats) > len(top) else ""
            self.openings.setText("Grandmasters here (%d game%s): %s%s" % (total, "s" if total != 1 else "", shown, more))
        else:
            self.openings.setText("<span style='color:gray'>Out of the grandmaster book.</span>" if ply else "")
        self.offer_btn.setEnabled(not g.over)
        self.resign_btn.setEnabled(not g.over)
        if g.over and self.rated is not None and not self.rated["recorded"]:
            w = g.over.get("winner")
            self._record_rated(0.5 if w is None else 1.0 if w == self.rated["colour"] else 0.0)
            self.status.setText(self._status_html(thinking))
        self.undo_btn.setEnabled(not self._rated_in_progress())
        if g.over and self.tourney_game is not None and self.tourney is not None:
            w = g.over.get("winner")
            self.tourney.game_over(0.5 if w is None else 1.0 if w == "w" else 0.0)
        if g.over and g.mode == "ai" and not self._postgame_done and g.history:
            self._postgame_done = True
            self._show_postgame()

    def rating_history(self):
        """Your rating game by game, and your rated games (CM-23)."""
        if self.profile is None:
            self.note = "No rated games yet: tick \"Rated game\" to start a rating."
            self.render()
            return
        self.history_dlg = postgame.RatingHistoryDialog(self, self.profile, rating.PROVISIONAL)
        self.history_dlg.show()

    def tournament_new(self):
        if not self.people:
            return
        w = tourney_ui.new_tournament(self)
        if w is not None:
            if self.tourney is not None:
                self.tourney.close()
            self.tourney = w
            w.show()

    def tournament_resume(self):
        w = tourney_ui.resume(self)
        if w is None:
            self.note = "No saved tournament."
            self.render()
            return
        if self.tourney is not None:
            self.tourney.close()
        self.tourney = w
        w.show()

    def tournament_show(self):
        if self.tourney is not None:
            self.tourney.show(); self.tourney.raise_()

    def _show_postgame(self):
        """Chessmaster's Post-Game Analysis after a game against the computer (CM-20); CHESSIQ_POSTGAME=0 turns it off."""
        if not analysis.available() or os.environ.get("CHESSIQ_POSTGAME", "1") == "0":
            return
        g = self.game
        w = g.over.get("winner")
        result = 0.5 if w is None else 1.0 if w == "w" else 0.0
        opp = self._opp_name()
        white, black = (player_name(), opp) if g.human == "w" else (opp, player_name())
        moves = [E.sqname(h["m"].frm) + E.sqname(h["m"].to) + (h["m"].promo or "") for h in g.history]
        sans = [h["san"] for h in g.history]
        mine = self.profile.rating if self.profile is not None else (self._opponent().rating if self._opponent() else 1400)
        line = self.rated.get("line", "") if self.rated else ""
        if self.postgame is not None:
            self.postgame.close()
        self.postgame = postgame.PostGameDialog(self, moves, sans, result, white, black, self.people, opp, mine, line)
        self.postgame.show()

    def _status_html(self, thinking):
        g = self.game
        if self.review is not None:
            return ("<span style='color:#2f7de1'>Reviewing</span> — after %d of %d plies<br><small>◀ ▶ "
                    "to step, click a move, ⏭ returns to the game</small>" % (self.review, len(g.history)))
        note = "<br><small style='color:#2f7de1'>%s</small>" % self.note if self.note else ""
        if g.over:
            o = g.over
            won = "White" if o.get("winner") == "w" else "Black"
            lost = "Black" if o.get("winner") == "w" else "White"
            text = {"mate": "Checkmate — <b>%s wins!</b>" % won,
                    "time": "%s ran out of time — <b>%s wins!</b>" % (lost, won),
                    "resign": "%s resigns — <b>%s wins!</b>" % (lost, won),
                    "stalemate": "Stalemate — <b>draw.</b>"}.get(o["type"], "Draw — <b>%s.</b>" % o.get("reason"))
            return text + note
        side = "White" if g.turn == "w" else "Black"
        chk = " <span style='color:#e06666'>(in check)</span>" if g.in_check() else ""
        who = ""
        if g.mode == "ai":
            who = " — your move" if g.turn == g.human else (" — thinking…" if thinking else " — %s to move" % self._opp_name())
        elif g.mode == "self":
            who = " — thinking…" if thinking else ""
        elif g.mode == "net" and self.link is not None:
            who = " — your move" if g.turn == g.human else " — %s to move" % (self.link.peer_name or "opponent")
        return ("<span style='color:#2f7de1'>%s to move</span>%s%s%s<br><small>No castling · capturing your "
                "own pieces is allowed</small>" % (side, chk, who, note))

    def _render_moves(self, cur):
        parts = []
        for i, h in enumerate(self.game.history):
            if i % 2 == 0:
                parts.append("<span style='color:gray'>%d.</span>" % (i // 2 + 1))
            style = "color:#9b4dca;" if h["self"] else "color:inherit;"
            if i + 1 == cur:
                style += "background:#ffe58a;"
            parts.append("<a href='#%d' style='text-decoration:none;%s'>%s%s</a>" % (
                i + 1, style, h["san"], "<small>(self)</small>" if h["self"] else ""))
        self.moves.setHtml(" ".join(parts) or "<span style='color:gray'>No moves yet.</span>")


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("chessIQ")
    w = MainWindow()
    w.show()
    w.welcome()
    return app.exec()
