"""chessIQ main window: Kramnik chess (no castling, capture anything) against the computer, hotseat, computer vs
computer, or another player over the network -- found through the Serious Games Week matchmaker."""
import os
import random
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
from . import clock as clocks, personalities, rating, uci_engine
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


class ThinkThread(QThread):
    """The search, off the UI thread (the GIL is shared, but Python switches often enough to keep the board live)."""
    done = pyqtSignal(int, object)

    def __init__(self, token, think, parent=None):
        super().__init__(parent)
        self.token, self.think = token, think

    def run(self):
        self.done.emit(self.token, self.think())


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
        self.people = sorted(personalities.roster(), key=lambda p: p.rating) if uci_engine.available() else []
        for p in self.people:
            self.who.addItem("%s (%d)%s" % (p.name, p.rating, " — " + p.style if p.style else ""), p.name)
        if not self.people:
            self.who.addItem("chessIQ classic (engine not built)", None)
        self.who.setCurrentIndex(self._default_opponent())
        grid.addWidget(QLabel("Computer"), 2, 0)
        grid.addWidget(self.who, 2, 1)
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
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("font-family: monospace; font-size: 13pt")
        side.addWidget(self.clock_label)
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
        self.offer_label = QLabel("He offers a draw.")
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
        self.resize(1000, 680)

    # ---------------- game flow ----------------
    def _default_opponent(self):
        """The opponent nearest 1500, the first time; afterwards the last one chosen."""
        last = QSettings("sim-museum", "chessIQ").value("opponent", "")
        names = [p.name for p in self.people]
        if last in names:
            return names.index(last)
        return min(range(len(self.people)), key=lambda i: abs(self.people[i].rating - 1500)) if self.people else 0

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
            self.engine.stop()
            self.engine.new_game()

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

    def _rated_in_progress(self):
        r = self.rated
        return r is not None and not r["recorded"] and not self.game.over and self.game.history

    def _record_rated(self, score, why=""):
        r = self.rated
        if r is None or r["recorded"] or self.profile is None:
            return
        r["recorded"] = True
        d = self.profile.record(r["opponent"], r["rating"], score, r["colour"], len(self.game.history))
        self.note = "Rated%s: your rating %+d → %d." % (" (" + why + ")" if why else "", d, self.profile.rating)
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

    def new_game(self):
        if self._rated_in_progress():
            if QMessageBox.question(self, "Abandon the rated game?",
                                    "Starting a new game now counts as a loss in the rated game.") \
                    != QMessageBox.StandardButton.Yes:
                return
            self._record_rated(0, "abandoned")
        if self.link is not None:
            if not self.link.is_host or self.link.sock is None:
                return                      # in a network game only the host starts games, once a guest is here
            colour = "w" if self.game.human == "b" else "b"     # swap colours each new game
            self.link.start_game(E.opp(colour))
            self._start_net_game(colour)
            return
        self.token += 1
        self.review = None
        self._start_engine()
        self.game = Game(self.mode.currentData(), self.side.currentData())
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
        san = self.game.do_move(m)
        if self.game.over:
            self.clock.stop()
        elif self.clock.moved(mover):
            self._on_tick()                            # moved after the flag fell
        self.boardw.selected, self.boardw.targets = None, []
        if self.link is not None and not remote:
            self.link.send(t="move", ply=len(self.game.history) - 1, san=san)
        self.render()
        self.maybe_ai()

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
                    self.note = "He declines your draw offer — far too early."
                    self.render()
            QTimer.singleShot(300 + int(random.random() * 400), play)
            return
        if self.engine is not None:
            clk = self.clock.uci() if self.clock.timed else None
            moves, eng, legal = [E.sqname(h["m"].frm) + E.sqname(h["m"].to) + (h["m"].promo or "") for h in g.history], \
                self.engine, g.legal()

            def think():                    # the chosen personality (EPIC CM)
                u = eng.choose(moves, clock=clk) if clk else eng.choose(moves, movetime_ms=int(THINK_S * 1000))
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
                self.note = "He declines your draw offer — play on."
                self.render()
            return
        offer = g.ai_offers_draw(m)
        self.do_move(m)
        if offer and not g.over:
            g.offers = {"count": g.offers["count"] + 1, "last_ply": len(g.history)}
            self.offer_label.setText("He offers a draw.")
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
            self.note = "Draw offered — make your move; he will answer with his."
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
        self.maybe_ai()                 # unfinished game and it's his move: he plays on

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
        if self.announcer:
            self.announcer.stop()
        if self.link:
            self.link.close()
        if self._rated_in_progress():
            self._record_rated(0, "abandoned")      # Chessmaster adjourns; chessIQ does not, so leaving is a loss
        if self.engine is not None:
            self.engine.stop()
        for th in list(self.threads):
            th.wait(3000)
        if self.engine is not None:
            self.engine.close()
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
        bw.hints = g.book_hints() if (live and g.local_to_move() and g.mode != "net") else []
        if not live:
            bw.selected, bw.targets = None, []
        bw.update()
        self.status.setText(self._status_html(thinking))
        self._render_moves(ply)
        stats = g.book_stats(ply)
        if stats:
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
            who = " — your move" if g.turn == g.human else (" — thinking…" if thinking else " — his move")
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
    return app.exec()
