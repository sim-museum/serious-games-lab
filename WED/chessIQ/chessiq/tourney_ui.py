"""The tournament windows (EPIC CM, CM-22), as Chessmaster's Play/Tournaments: create a round robin or Swiss event
against personalities around your level, play your games on the main board, get quick results for the computer
games, and follow the standings and crosstable. The event in progress is saved after every result."""
import json
import os
import random

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from . import clock as clocks, rating, tournament as T, uci_engine


def save_path():
    return os.path.join(os.path.dirname(rating.profile_path()), "tournament.json")


class NewTournamentDialog(QDialog):
    """Type, field size, rating range, time control, rated."""

    def __init__(self, parent, my_rating):
        super().__init__(parent)
        self.setWindowTitle("New tournament")
        f = QFormLayout(self)
        self.kind = QComboBox()
        for label, data in (("Round robin", "rr"), ("Double round robin", "rr2"), ("Swiss", "swiss")):
            self.kind.addItem(label, data)
        self.size = QSpinBox(); self.size.setRange(3, 11); self.size.setValue(5)
        self.rounds = QSpinBox(); self.rounds.setRange(3, 9); self.rounds.setValue(5)
        self.lo = QSpinBox(); self.lo.setRange(0, 3000); self.lo.setSingleStep(50); self.lo.setValue(max(0, my_rating - 200))
        self.hi = QSpinBox(); self.hi.setRange(0, 3300); self.hi.setSingleStep(50); self.hi.setValue(my_rating + 200)
        self.tc = QComboBox()
        for label, kind, args in clocks.PRESETS:
            self.tc.addItem(label, (kind, args))
        self.tc.setCurrentIndex(1)
        self.rated = QCheckBox("Rated (your games change your rating)")
        f.addRow("Type", self.kind)
        f.addRow("Opponents", self.size)
        f.addRow("Swiss rounds", self.rounds)
        f.addRow("Lowest rating", self.lo)
        f.addRow("Highest rating", self.hi)
        f.addRow("Your games", self.tc)
        f.addRow("", self.rated)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)


def pick_field(people, n, lo, hi, seed=None):
    """n opponents with ratings in [lo, hi], spread across the range; widened if too few qualify."""
    pool = [p for p in people if lo <= p.rating <= hi]
    while len(pool) < n and (lo > 0 or hi < 3300):
        lo, hi = max(0, lo - 100), hi + 100
        pool = [p for p in people if lo <= p.rating <= hi]
    rnd = random.Random(seed)
    return sorted(rnd.sample(pool, min(n, len(pool))), key=lambda p: -p.rating)


class QuickThread(QThread):
    """Plays out the round's computer-vs-computer games with their engines."""
    one = pyqtSignal(str, str, float)

    def __init__(self, games, people, parent=None):
        super().__init__(parent)
        self.games, self.people, self.cancelled = games, people, False

    def _engine(self, p):
        return uci_engine.LeelaEngine(p) if p.engine == "leela" else uci_engine.PersonalityEngine(p)

    def run(self):
        for w, b in self.games:
            if self.cancelled:
                return
            ew, eb = self._engine(self.people[w]), self._engine(self.people[b])
            try:
                s = T.play_out(ew, eb)
            finally:
                ew.close(); eb.close()
            self.one.emit(w, b, s)


class TournamentWindow(QDialog):
    def __init__(self, main, t, extra):
        super().__init__(main)
        self.setWindowTitle("Tournament")
        self.setModal(False)
        self.resize(720, 520)
        self.main, self.t, self.extra = main, t, extra
        self.people = {p.name: p for p in main.people}
        self.quick = None
        v = QVBoxLayout(self)
        self.title = QLabel()
        v.addWidget(self.title)
        self.games = QTableWidget(0, 3)
        self.games.setHorizontalHeaderLabels(["White", "Black", "Result"])
        self.games.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.games)
        row = QHBoxLayout()
        self.play_btn = QPushButton("Play my game")
        self.play_btn.clicked.connect(self.play_mine)
        self.quick_btn = QPushButton("Quick results")
        self.quick_btn.clicked.connect(self.quick_results)
        self.next_btn = QPushButton("Next round")
        self.next_btn.clicked.connect(self.next_round)
        for b in (self.play_btn, self.quick_btn, self.next_btn):
            row.addWidget(b)
        v.addLayout(row)
        v.addWidget(QLabel("Standings"))
        self.table = QTableWidget(0, 0)
        v.addWidget(self.table)
        self.refresh()

    # ---- state ---------------------------------------------------------------------------------------------------
    def save(self):
        try:
            os.makedirs(os.path.dirname(save_path()), exist_ok=True)
            with open(save_path() + ".tmp", "w") as f:
                json.dump(T.to_dict(self.t, self.extra), f)
            os.replace(save_path() + ".tmp", save_path())
        except OSError:
            pass

    def my_game(self):
        if not self.t.rounds:
            return None
        return next(((w, b) for w, b in self.t.pending() if self.t.human in (w, b)), None)

    def record(self, w, b, score):
        self.t.record(len(self.t.rounds) - 1, w, b, score)
        self.save()
        self.refresh()

    # ---- actions -------------------------------------------------------------------------------------------------
    def play_mine(self):
        g = self.my_game()
        if g is None:
            return
        w, b = g
        opp = b if w == self.t.human else w
        m = self.main
        m.mode.setCurrentIndex(m.mode.findData("ai"))
        m.side.setCurrentIndex(m.side.findData("w" if w == self.t.human else "b"))
        m.who.setCurrentIndex(m.who.findData(opp))
        m.tc.setCurrentIndex(self.extra.get("tc", 1))
        m.rated_box.setChecked(bool(self.t.rated))
        m.new_game()
        m.tourney_game = (w, b)                    # linked after the start: a manual New Game unlinks it

    def game_over(self, score_for_white):
        """Called by the main window when your tournament game ends."""
        g = self.main.tourney_game
        self.main.tourney_game = None
        if g is not None and g in self.t.pending():
            self.record(g[0], g[1], score_for_white)

    def quick_results(self):
        games = [(w, b) for w, b in self.t.pending() if self.t.human not in (w, b)]
        if not games or (self.quick is not None and self.quick.isRunning()):
            return
        self.quick_btn.setEnabled(False)
        self.quick_btn.setText("Playing %d game%s…" % (len(games), "s" if len(games) > 1 else ""))
        self.quick = QuickThread(games, self.people, self)
        self.quick.one.connect(self.record)
        self.quick.finished.connect(self.refresh)
        self.quick.start()

    def next_round(self):
        if not self.t.pending() and len(self.t.rounds) < self.t.n_rounds:
            self.t.pair_next()
            self.save()
        self.refresh()

    # ---- display -------------------------------------------------------------------------------------------------
    def refresh(self):
        t = self.t
        r = len(t.rounds)
        kind = {"rr": "Double round robin" if t.double else "Round robin", "swiss": "Swiss"}[t.kind]
        state = "finished" if t.finished() else "round %d of %d" % (r, t.n_rounds)
        self.title.setText("<b>%s</b>, %d players%s — %s" % (kind, len(t.players), ", rated" if t.rated else "", state))
        pairs = t.rounds[-1] if t.rounds else []
        self.games.setRowCount(len(pairs))
        for i, (w, b) in enumerate(pairs):
            res = t.results.get((r - 1, w, b))
            txt = "bye" if b is T.BYE else "—" if res is None else {1.0: "1–0", 0.5: "½–½", 0.0: "0–1"}[res]
            for j, x in enumerate((w, b or "", txt)):
                self.games.setItem(i, j, QTableWidgetItem(x))
        busy = self.quick is not None and self.quick.isRunning()
        others = [g for g in t.pending() if t.human not in g]
        self.play_btn.setEnabled(self.my_game() is not None)
        self.quick_btn.setEnabled(bool(others) and not busy)
        if not busy:
            self.quick_btn.setText("Quick results")
        self.next_btn.setEnabled(not t.pending() and r < t.n_rounds)
        st = t.standings()
        names = [p for p, _, _ in st]
        cross = t.crosstable()
        cols = ["Player", "Rating", "Points", "Tie-break"] + [str(i + 1) for i in range(len(names))]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(st))
        for i, (p, pts, tb) in enumerate(st):
            cells = ["%d. %s" % (i + 1, p), str(t.rating[p]), ("%g" % pts), ("%g" % tb)]
            for o in names:
                s = cross[p].get(o)
                cells.append("×" if o == p else "" if s is None else " ".join({1.0: "1", 0.5: "½", 0.0: "0"}[x] for x in s))
            for j, c in enumerate(cells):
                item = QTableWidgetItem(c)
                if p == t.human:
                    item.setBackground(Qt.GlobalColor.yellow)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

    def closeEvent(self, e):
        if self.quick is not None:
            self.quick.cancelled = True
            self.quick.wait(120000)
        super().closeEvent(e)


def new_tournament(main):
    my = main.profile.rating if main.profile is not None else 1400
    d = NewTournamentDialog(main, my)
    if not d.exec():
        return None
    return start(main, d.kind.currentData(), d.size.value(), d.rounds.value(), d.lo.value(), d.hi.value(),
                 d.tc.currentIndex(), d.rated.isChecked())


def start(main, kind, n, rounds, lo, hi, tc_index, rated, seed=None):
    from .app import player_name
    me = player_name()
    my = main.profile.rating if main.profile is not None else 1400
    field = pick_field(main.people, n, lo, hi, seed)
    players = [(me, my)] + [(p.name, p.rating) for p in field]
    t = T.Tournament(players, "swiss" if kind == "swiss" else "rr", rounds=rounds, double=(kind == "rr2"),
                     rated=rated, seed=seed, human=me)
    t.pair_next()
    w = TournamentWindow(main, t, {"tc": tc_index})
    w.save()
    return w


def resume(main):
    try:
        with open(save_path()) as f:
            t, extra = T.from_dict(json.load(f))
    except (OSError, ValueError, KeyError):
        return None
    return TournamentWindow(main, t, extra)
