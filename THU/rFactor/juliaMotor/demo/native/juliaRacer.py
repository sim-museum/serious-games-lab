#!/usr/bin/env python3
"""juliaMotor — PyQt6 front-end: launch the GPL Lotus 49 driving sim and calibrate
your controller.

Two devices are supported the same way: the Logitech Extreme 3D Pro joystick (as
before) and a Thrustmaster TX wheel with clutch/brake/accelerator pedals.  Both are
mapped by the same wizard — you hold each control and the GUI captures which axis (or
button) it is and its travel endpoints.

WHY A JULIA HELPER READS THE STICK: the game reads the controller through GLFW, and
`joystick.conf` records axis indices in GLFW's ordering.  Reading the device in Python
(pygame/evdev) would number the axes differently and produce a config that maps the
wrong axes in-game.  So this GUI streams the live state from `joyserver.jl` (GLFW) and
calibrates against exactly the indices the game uses.  The file it writes,
`joystick.conf`, is the same format `calibrate.jl`/`JoyCfg` already read.

Run:  python3 juliaRacer.py (from demo/native/, or anywhere — paths are resolved)
"""
import json
import os
import re
import shutil
import socket
import sys
import time

from PyQt6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "assets", "ui")    # the theme's glyphs ship with the module (fixed even if HERE is redirected)
CONF = os.path.join(HERE, "joystick.conf")
PROFILE_DIR = os.path.join(HERE, "joystick_profiles")

# TRACK env keys in the same order as the Track dropdown (Zandvoort, Skidpad, Nürburgring, …).
TRACK_KEYS = ["zandvoort", "skidpad", "nurburgring", "watglen", "monza", "spa"]
# A1/A3: GPLrank (1967) benchmark laptimes in seconds — MUST match REF_LAP in drive_native_mtk.jl.
# 100 % AI = the fastest car achieves this; the per-track preset = REF_LAP/human_best · 100.
REF_LAP = {"zandvoort": 86.848, "nurburgring": 501.931, "watglen": 66.912,
           "monza": 90.202, "spa": 200.342, "skidpad": 30.0}


def _read_track_times(fname):
    """Read a '<track>\\t<seconds>' file → {track: seconds}. Empty if absent."""
    out = {}
    try:
        with open(os.path.join(HERE, fname)) as f:
            for ln in f:
                sp = ln.strip().split("\t")
                if len(sp) == 2:
                    try:
                        out[sp[0]] = float(sp[1])
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def human_bests():
    """Per-track best lap (s) the sim banks whenever you improve."""
    return _read_track_times("human_best.txt")


def human_recents():
    """B (PO): per-track MOST-RECENT race AVERAGE lap (s) — the sim overwrites it each race."""
    return _read_track_times("human_recent.txt")


def preset_ai_pct(track_key):
    """B (PO): the AI-speed % that paces the fastest AI car at the driver's MOST RECENT race
    AVERAGE on this track (so the field matches how you actually race, not a one-off hot lap):
    % = GPLrank_ref / your_recent_average · 100.  Falls back to your best lap, then 50 % if
    you've never raced/lapped here.  Clamped to the spinbox range [30, 200].
    PO 2026-09-05 set the DEFAULT to 60% (was 85%). That default applies when there is no pace for
    the track; once you HAVE raced here the personalised value still wins, because that is what the
    preset was asked for in the first place."""
    ref = REF_LAP.get(track_key)
    # AISPEED-1 (PO 2026-09-05): "by default 60% AI speed, not 200%!"  The 200% was this function
    # faithfully computing REF_LAP/base*100 from a POISONED lap file -- watglen banked at 2.708 s,
    # nurburgring at 4.058 s, spa at 5.851 s -- so every track saturated the clamp. The sim now
    # refuses to bank an impossible lap, but this side must not trust the file either: a preset
    # that silently pins the field to maximum is the most expensive way to be wrong.
    def plausible(t):
        return t and t > 0 and (not ref or t >= 0.5 * ref)
    base = next((t for t in (human_recents().get(track_key), human_bests().get(track_key))
                 if plausible(t)), None)
    if not base or not ref:
        return 60          # PO 2026-09-05: 60% is the default when there is nothing to personalise
    return max(30, min(200, round(ref / base * 100)))


def find_julia():
    j = shutil.which("julia")
    if j:
        return j
    cand = os.path.expanduser("~/.juliaup/bin/julia")
    return cand if os.path.exists(cand) else "julia"


# ---------------------------------------------------------------------------
# JoyCfg model — mirrors joycfg.jl so the live preview matches the game exactly
# and the file we write is byte-compatible with what JoyCfg.loadmap expects.
# ---------------------------------------------------------------------------

CONTROLS = [
    ("Throttle / brake", "W / S  (or your pedals)"),
    ("Steer", "A / D  (or your wheel)"),
    ("Shift up / down", "E / Q  (or the paddles)"),
    ("Clutch", "C  (or the clutch pedal)"),
    ("Automatic / manual gearbox", "G"),
    ("Change view (cockpit, chase, ...)", "V"),
    ("Restart the race", "R"),
    ("Mute the engine", "M"),
    ("Leave the session", "Esc"),
]


def show_controls(parent):
    """GUI-1: the key list as a table in a dialog (it was a run-on sentence under the Launch button)."""
    d = QDialog(parent); d.setWindowTitle("Controls"); v = QVBoxLayout(d)
    g = QGridLayout(); v.addLayout(g)
    for i, (what, keys) in enumerate(CONTROLS):
        g.addWidget(QLabel(what), i, 0); g.addWidget(QLabel(f"<b>{keys}</b>"), i, 1)
    note = QLabel("A calibrated wheel and pedals work directly (Controller tab). The first start compiles and loads "
                  "the game: the window can take a few minutes to appear.")
    note.setWordWrap(True); note.setObjectName("hint"); v.addWidget(note)
    ok = QPushButton("Close"); ok.clicked.connect(d.accept); v.addWidget(ok, 0, Qt.AlignmentFlag.AlignRight)
    d.exec()


def segnames_env(qenv, on):
    """TRACKSEG-3: the track-section names are on by default; off = the sim's JM_SEGNAME_SECS=0."""
    if not on:
        qenv.insert("JM_SEGNAME_SECS", "0")

class Ctrl:
    def __init__(self, axis=0, a=0.0, b=1.0):
        self.axis, self.a, self.b = int(axis), float(a), float(b)

    def norm(self, axes):
        if self.axis < 1 or self.axis > len(axes):
            return 0.0
        d = self.b - self.a
        return 0.0 if abs(d) < 1e-6 else (axes[self.axis - 1] - self.a) / d


class JoyMap:
    def __init__(self):
        # default = historical hardcoded Logitech Extreme 3D Pro mapping
        self.steer = Ctrl(1, -1.0, 1.0)
        self.throttle = Ctrl(2, 0.0, -1.0)
        self.brake = Ctrl(2, 0.0, 1.0)
        self.clutch = Ctrl(0, 0.0, 1.0)
        self.up_btn, self.dn_btn, self.clutch_btn = 1, 2, 3
        self.deadzone = 0.06

    def apply(self, axes, btns):
        clamp = lambda v, lo, hi: max(lo, min(hi, v))
        s = clamp(1.0 - 2.0 * self.steer.norm(axes), -1.0, 1.0)
        if abs(s) < self.deadzone:
            s = 0.0
        thr = clamp(self.throttle.norm(axes), 0.0, 1.0)
        if thr < self.deadzone:
            thr = 0.0
        brk = clamp(self.brake.norm(axes), 0.0, 1.0)
        if brk < self.deadzone:
            brk = 0.0
        btn = lambda i: 1 <= i <= len(btns) and btns[i - 1] != 0
        if self.clutch.axis >= 1:
            clu = clamp(self.clutch.norm(axes), 0.0, 1.0)
        else:
            clu = 1.0 if btn(self.clutch_btn) else 0.0
        return s, thr, brk, clu, btn(self.up_btn), btn(self.dn_btn)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("# zand_racer joystick config — generated by juliaRacer.py\n")
            for nm, c in (("steer", self.steer), ("throttle", self.throttle),
                          ("brake", self.brake), ("clutch", self.clutch)):
                f.write(f"{nm}.axis {c.axis}\n{nm}.a {c.a}\n{nm}.b {c.b}\n")
            f.write(f"up_btn {self.up_btn}\ndn_btn {self.dn_btn}\n")
            f.write(f"clutch_btn {self.clutch_btn}\ndeadzone {self.deadzone}\n")

    @classmethod
    def load(cls, path):
        m = cls()
        if not os.path.isfile(path):
            return m
        d = {}
        for ln in open(path):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            p = ln.split()
            if len(p) >= 2:
                try:
                    d[p[0]] = float(p[1])
                except ValueError:
                    pass
        ctrl = lambda nm, df: Ctrl(round(d.get(nm + ".axis", df.axis)),
                                   d.get(nm + ".a", df.a), d.get(nm + ".b", df.b))
        m.steer = ctrl("steer", m.steer)
        m.throttle = ctrl("throttle", m.throttle)
        m.brake = ctrl("brake", m.brake)
        m.clutch = ctrl("clutch", m.clutch)
        m.up_btn = round(d.get("up_btn", m.up_btn))
        m.dn_btn = round(d.get("dn_btn", m.dn_btn))
        m.clutch_btn = round(d.get("clutch_btn", m.clutch_btn))
        m.deadzone = d.get("deadzone", m.deadzone)
        return m


def preset_x3d():
    """Logitech Extreme 3D Pro — the historical default; clutch on the throttle slider
    (axis 4), as drive_native_mtk.jl used to hardcode."""
    m = JoyMap()
    m.steer = Ctrl(1, -1.0, 1.0)
    m.throttle = Ctrl(2, 0.0, -1.0)
    m.brake = Ctrl(2, 0.0, 1.0)
    m.clutch = Ctrl(4, -1.0, 1.0)
    m.up_btn, m.dn_btn, m.clutch_btn = 1, 2, 3
    return m


def preset_tx():
    """Thrustmaster TX wheel + 3 pedals — a sensible STARTING point (it enumerates as a
    'Generic X-Box pad': steer on axis 1).  Pedals/buttons vary, so finish in the
    wizard: hold each pedal, press each paddle, then Save."""
    m = JoyMap()
    m.steer = Ctrl(1, -1.0, 1.0)
    m.throttle = Ctrl(0, 0.0, 1.0)   # capture in the wizard
    m.brake = Ctrl(0, 0.0, 1.0)
    m.clutch = Ctrl(0, 0.0, 1.0)
    m.up_btn, m.dn_btn, m.clutch_btn = 1, 2, 0
    return m


# ---------------------------------------------------------------------------
# Live joystick reader — drives joyserver.jl (GLFW) and parses its JSON lines.
# ---------------------------------------------------------------------------
class JoyReader(QProcess):
    updated = pyqtSignal()        # new axes/buttons available
    status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.present = False
        self.name = ""
        self.axes = []
        self.buttons = []
        self._buf = b""
        self.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.readyReadStandardOutput.connect(self._read)

    def start_reader(self, slot=1):
        if self.state() != QProcess.ProcessState.NotRunning:
            return
        self.setWorkingDirectory(HERE)
        self.start(find_julia(), ["--project=.", "joyserver.jl", str(slot)])
        self.status.emit("starting joystick reader (GLFW)… first start compiles, ~10–20 s")

    def stop_reader(self):
        if self.state() != QProcess.ProcessState.NotRunning:
            self.kill()
            self.waitForFinished(1500)

    def _read(self):
        self._buf += bytes(self.readAllStandardOutput())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"{"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.present = d.get("present", False)
            self.name = d.get("name", "")
            self.axes = [float(x) for x in d.get("axes", [])]
            self.buttons = [int(x) for x in d.get("buttons", [])]
            self.updated.emit()


# ---------------------------------------------------------------------------
# A signed [-1,1]-ish bar; autoscaling for axes that aren't normalized (the TX
# pedals report values well outside [-1,1]).
# ---------------------------------------------------------------------------
class Bar(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setRange(-1000, 1000)
        self.setValue(0)
        self.setTextVisible(True)
        self.setFormat("%v")
        self.setFixedHeight(18)

    def set_norm(self, frac, raw=None):
        self.setValue(int(max(-1.0, min(1.0, frac)) * 1000))
        self.setFormat(f"{raw:.2f}" if raw is not None else f"{frac:.2f}")


# ---------------------------------------------------------------------------
# Calibration wizard — a small state machine driven by live updates.
# ---------------------------------------------------------------------------
STEPS = [
    ("idle", ""),
    ("rest", "Step 1 — CENTER the wheel/stick and RELEASE every pedal, then click Capture."),
    ("steer_l", "Step 2 — Hold STEER fully LEFT, then click Capture."),
    ("steer_r", "Step 3 — Hold STEER fully RIGHT, then click Capture."),
    ("throttle", "Step 4 — Press the ACCELERATOR fully, then click Capture."),
    ("brake", "Step 5 — Press the BRAKE fully, then click Capture."),
    ("clutch", "Step 6 — Press the CLUTCH pedal fully and click 'Capture pedal' — "
               "or click 'Use button' / 'No clutch'."),
    ("clutch_btn", "Step 6b — Press the button you want to use as CLUTCH."),
    ("up", "Step 7 — Press the SHIFT-UP paddle/button."),
    ("dn", "Step 8 — Press the SHIFT-DOWN paddle/button."),
    ("done", "Done — review the live preview below, then Save."),
]


class CalibrateTab(QWidget):
    def __init__(self, joy: JoyReader, on_saved):
        super().__init__()
        self.joy = joy
        self.on_saved = on_saved
        self.map = JoyMap.load(CONF)
        self.work = JoyMap.load(CONF)   # map being edited by the wizard
        self.rest = []
        self.step = 0
        self._btn_armed = True
        self._sax = 0
        self.axis_bars = []
        self.btn_lamps = []
        self._build()
        self.joy.updated.connect(self.refresh)
        self.joy.status.connect(lambda s: self.statusl.setText(s))

    # ---- ui ----
    def _build(self):
        root = QVBoxLayout(self)

        self.devl = QLabel("No controller — plug it in (it must be the first joystick).")
        self.devl.setStyleSheet("font-weight:bold")
        root.addWidget(self.devl)
        self.statusl = QLabel("")
        self.statusl.setStyleSheet("color:#888")
        root.addWidget(self.statusl)

        # presets
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Preset:"))
        self.preset = QComboBox()
        self.preset.addItems(["Logitech Extreme 3D Pro", "Thrustmaster TX wheel + pedals"])
        prow.addWidget(self.preset)
        b = QPushButton("Load preset → editor")
        b.clicked.connect(self.load_preset)
        prow.addWidget(b)
        prow.addStretch(1)
        root.addLayout(prow)

        mid = QHBoxLayout()
        root.addLayout(mid, 1)

        # live axes + buttons
        live = QGroupBox("Live input  (raw values from GLFW)")
        self.live_v = QVBoxLayout(live)
        self.axes_box = QVBoxLayout()
        self.live_v.addLayout(self.axes_box)
        self.live_v.addWidget(QLabel("Buttons:"))
        self.btn_grid = QGridLayout()
        self.live_v.addLayout(self.btn_grid)
        self.live_v.addStretch(1)
        mid.addWidget(live, 1)

        # wizard
        wiz = QGroupBox("Calibration wizard")
        wv = QVBoxLayout(wiz)
        self.instr = QLabel("Click Start to map the controller now plugged in.")
        self.instr.setWordWrap(True)
        self.instr.setMinimumHeight(60)
        f = QFont(); f.setPointSize(11); self.instr.setFont(f)
        wv.addWidget(self.instr)

        brow = QHBoxLayout()
        self.start_b = QPushButton("Start")
        self.start_b.clicked.connect(self.start_wizard)
        self.cap_b = QPushButton("Capture")
        self.cap_b.clicked.connect(self.capture)
        self.cap_b.setEnabled(False)
        self.alt_b = QPushButton("Use button")
        self.alt_b.clicked.connect(self.clutch_use_button)
        self.alt_b.hide()
        self.skip_b = QPushButton("No clutch")
        self.skip_b.clicked.connect(self.clutch_skip)
        self.skip_b.hide()
        for x in (self.start_b, self.cap_b, self.alt_b, self.skip_b):
            brow.addWidget(x)
        brow.addStretch(1)
        wv.addLayout(brow)

        self.capl = QLabel("")
        self.capl.setStyleSheet("color:#2a7")
        self.capl.setWordWrap(True)
        wv.addWidget(self.capl)
        wv.addStretch(1)
        mid.addWidget(wiz, 1)

        # mapped preview
        prev = QGroupBox("Mapped output  (what the game will see)")
        pg = QGridLayout(prev)
        self.pv = {}
        for i, nm in enumerate(("steer", "throttle", "brake", "clutch")):
            pg.addWidget(QLabel(nm.capitalize()), i, 0)
            bar = Bar(); self.pv[nm] = bar; pg.addWidget(bar, i, 1)
        self.shiftl = QLabel("shift: · ·")
        pg.addWidget(self.shiftl, 4, 0, 1, 2)
        root.addWidget(prev)

        # save row
        srow = QHBoxLayout()
        self.save_b = QPushButton("Save → joystick.conf")
        self.save_b.clicked.connect(self.save)
        srow.addWidget(self.save_b)
        self.summl = QLabel(self._summary())
        self.summl.setStyleSheet("color:#888")
        srow.addWidget(self.summl, 1)
        root.addLayout(srow)

    # ---- live refresh ----
    def refresh(self):
        j = self.joy
        if not j.present:
            self.devl.setText("No controller detected on joystick #1 — plug it in.")
            return
        self.devl.setText(f"● {j.name}   ({len(j.axes)} axes, {len(j.buttons)} buttons)")
        # (re)build axis bars if the count changed
        if len(self.axis_bars) != len(j.axes):
            while self.axes_box.count():
                it = self.axes_box.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            self.axis_bars = []
            for i in range(len(j.axes)):
                row = QHBoxLayout()
                row.addWidget(QLabel(f"axis {i + 1}"))
                bar = Bar(); row.addWidget(bar, 1)
                self.axis_bars.append(bar)
                w = QWidget(); w.setLayout(row)
                self.axes_box.addWidget(w)
        if len(self.btn_lamps) != len(j.buttons):
            while self.btn_grid.count():
                it = self.btn_grid.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            self.btn_lamps = []
            for i in range(len(j.buttons)):
                lab = QLabel(str(i + 1))
                lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lab.setFixedSize(24, 20)
                lab.setFrameShape(QFrame.Shape.Box)
                self.btn_lamps.append(lab)
                self.btn_grid.addWidget(lab, i // 8, i % 8)
        for i, v in enumerate(j.axes):
            self.axis_bars[i].set_norm(v, v)
        for i, v in enumerate(j.buttons):
            self.btn_lamps[i].setStyleSheet(
                "background:#2a7;color:white" if v else "background:none")
        # mapped preview from the work map
        s, thr, brk, clu, up, dn = self.work.apply(j.axes, j.buttons)
        self.pv["steer"].set_norm(s, s)
        self.pv["throttle"].set_norm(thr, thr)
        self.pv["brake"].set_norm(brk, brk)
        self.pv["clutch"].set_norm(clu, clu)
        self.shiftl.setText(f"shift:  up {'▼' if up else '·'}   down {'▼' if dn else '·'}")
        # auto-capture for button steps
        if STEPS[self.step][0] in ("up", "dn", "clutch_btn"):
            self._auto_button()

    # ---- wizard flow ----
    def load_preset(self):
        self.work = preset_x3d() if self.preset.currentIndex() == 0 else preset_tx()
        self.capl.setText("Preset loaded into the editor — Save to use it, or run the "
                          "wizard to fine-tune pedals/buttons.")
        self.summl.setText(self._summary())

    def start_wizard(self):
        if not self.joy.present:
            QMessageBox.warning(self, "No controller",
                                "Plug in the controller (as joystick #1) and try again.")
            return
        self.work = JoyMap()
        self.step = 1
        self._show_step()

    def _show_step(self):
        key, txt = STEPS[self.step]
        self.instr.setText(txt)
        self.cap_b.setEnabled(key not in ("idle", "done", "up", "dn", "clutch_btn"))
        self.cap_b.setVisible(key not in ("up", "dn", "clutch_btn", "done", "idle"))
        self.alt_b.setVisible(key == "clutch")
        self.skip_b.setVisible(key == "clutch")
        self.start_b.setText("Restart" if key != "idle" else "Start")
        # a button step must first see all buttons released, so a button still held
        # from the previous step (e.g. the clutch button) isn't grabbed immediately.
        self._btn_armed = key not in ("up", "dn", "clutch_btn")
        if key == "done":
            self.cap_b.setEnabled(False)
            self.capl.setText("Calibration captured. Review the preview, then Save.")
        self.summl.setText(self._summary())

    def _advance(self):
        self.step += 1
        self._show_step()

    def capture(self):
        key = STEPS[self.step][0]
        ax = self.joy.axes
        if not ax:
            return
        if key == "rest":
            self.rest = list(ax)
            self.capl.setText("Rest captured.")
            self._advance()
        elif key == "steer_l":
            i = self._most_moved()
            self.work.steer.axis = i + 1
            self.work.steer.a = ax[i]
            self._sax = i
            self.capl.setText(f"Steer = axis {i + 1}, left @ {ax[i]:.2f}")
            self._advance()
        elif key == "steer_r":
            i = getattr(self, "_sax", self.work.steer.axis - 1)
            self.work.steer.b = ax[i]
            self.capl.setText(f"Steer right @ {ax[i]:.2f}")
            self._advance()
        elif key == "throttle":
            i = self._most_moved()
            self.work.throttle = Ctrl(i + 1, self.rest[i], ax[i])
            self.capl.setText(f"Throttle = axis {i + 1}: {self.rest[i]:.2f} → {ax[i]:.2f}")
            self._advance()
        elif key == "brake":
            i = self._most_moved()
            self.work.brake = Ctrl(i + 1, self.rest[i], ax[i])
            self.capl.setText(f"Brake = axis {i + 1}: {self.rest[i]:.2f} → {ax[i]:.2f}")
            self._advance()
        elif key == "clutch":
            i = self._most_moved()
            self.work.clutch = Ctrl(i + 1, self.rest[i], ax[i])
            self.work.clutch_btn = 0
            self.capl.setText(f"Clutch pedal = axis {i + 1}: {self.rest[i]:.2f} → {ax[i]:.2f}")
            self.step = 8   # → shift-up
            self._show_step()

    def clutch_use_button(self):
        self.work.clutch = Ctrl(0, 0.0, 1.0)
        self.step = 7  # clutch_btn
        self._show_step()

    def clutch_skip(self):
        self.work.clutch = Ctrl(0, 0.0, 1.0)
        self.work.clutch_btn = 0
        self.step = 8  # shift up
        self._show_step()

    def _auto_button(self):
        bs = self.joy.buttons
        if not self._btn_armed:                 # wait for a fully-released frame first
            if not any(bs):
                self._btn_armed = True
            return
        for i, v in enumerate(bs):
            if v:
                key = STEPS[self.step][0]
                if key == "clutch_btn":
                    self.work.clutch_btn = i + 1
                    self.capl.setText(f"Clutch button = {i + 1}")
                    self.step = 8
                elif key == "up":
                    self.work.up_btn = i + 1
                    self.capl.setText(f"Shift-up button = {i + 1}")
                    self.step = 9
                elif key == "dn":
                    self.work.dn_btn = i + 1
                    self.capl.setText(f"Shift-down button = {i + 1}")
                    self.step = 10
                self._show_step()
                return

    def _most_moved(self):
        ax = self.joy.axes
        if not self.rest or len(self.rest) != len(ax):
            self.rest = [0.0] * len(ax)
        devs = [abs(ax[i] - self.rest[i]) for i in range(len(ax))]
        return max(range(len(devs)), key=lambda i: devs[i]) if devs else 0

    def _summary(self):
        m = self.work
        c = (f"steer ax{m.steer.axis}  thr ax{m.throttle.axis}  brk ax{m.brake.axis}  "
             f"clutch {'ax'+str(m.clutch.axis) if m.clutch.axis else ('btn'+str(m.clutch_btn) if m.clutch_btn else 'none')}  "
             f"up b{m.up_btn} dn b{m.dn_btn}")
        return c

    def save(self):
        self.work.save(CONF)
        # also stash a per-device profile so swapping controllers is one click
        if self.joy.name:
            safe = "".join(ch if ch.isalnum() else "_" for ch in self.joy.name)
            self.work.save(os.path.join(PROFILE_DIR, safe + ".conf"))
        self.map = JoyMap.load(CONF)
        self.capl.setText(f"Saved → {CONF}")
        QMessageBox.information(self, "Saved",
                                f"Wrote {CONF}.\nThe game will use it on next launch.")
        self.on_saved()


# ---------------------------------------------------------------------------
# Launch tab
# ---------------------------------------------------------------------------
class DriveTab(QWidget):
    def __init__(self, joy: JoyReader, on_result=None):
        super().__init__()
        self.joy = joy
        self.proc = None
        self.on_result = on_result   # PO: callback(path) to show the result in a TAB (not a modal)
        root = QVBoxLayout(self)
        # GUI-1 S1 (PO 2026-10-06: "redesign the julia GUI for ease of use, following GUI best practices"). One screen
        # per task: this tab only sets up and starts a session; preferences that rarely change moved to the Settings
        # tab (settings_page()), the key list to Help > Controls. Widget names are unchanged, so launch(), the LAN
        # lobby and the tests read the same attributes. Every choice is remembered (QSettings juliaRacer/launcher).
        self._settings = QSettings("juliaRacer", "launcher")
        st = self._settings
        cols = QHBoxLayout(); root.addLayout(cols)

        # ---- Session: where, what kind, against whom ----
        sess = QGroupBox("Session"); form = QGridLayout(sess); cols.addWidget(sess, 3)
        form.addWidget(QLabel("Track:"), 0, 0)
        self.track = QComboBox()
        self.track.addItems(["Zandvoort", "Skidpad (test area)", "Nürburgring", "Watkins Glen", "Monza", "Spa"])
        self.track.setCurrentIndex(min(max(int(st.value("session/track", 0)), 0), 5))   # first run: Zandvoort
        form.addWidget(self.track, 0, 1, 1, 2)
        form.addWidget(QLabel("Session:"), 1, 0)
        self.mode = QComboBox()
        self.mode.addItems(["Practice", "Race"])   # Practice = lone car; Race = AI grid
        self.mode.setToolTip("Practice: you alone on the track. Race: a standing start against the AI field.")
        self.mode.setCurrentIndex(min(max(int(st.value("session/mode", 0)), 0), 1))
        form.addWidget(self.mode, 1, 1, 1, 2)
        # Race-only fields (Laps / AI cars / AI speed / qualifying) -- hidden in Practice (a lone car has none)
        self.laps_l = QLabel("Laps:")
        form.addWidget(self.laps_l, 2, 0)
        self.laps = QSpinBox(); self.laps.setRange(1, 99); self.laps.setValue(int(st.value("session/laps", 3)))
        form.addWidget(self.laps, 2, 1)
        self.ai_l = QLabel("Opponents:")
        form.addWidget(self.ai_l, 3, 0)
        self.ai = QSpinBox(); self.ai.setRange(0, 5); self.ai.setValue(int(st.value("session/ai", 5)))   # full grid (PO)
        self.ai.setToolTip("Number of AI cars on the grid (up to 5).")
        form.addWidget(self.ai, 3, 1)
        self.ai_pct_l = QLabel("Opponent pace:")
        form.addWidget(self.ai_pct_l, 4, 0)
        self.ai_pct = QSpinBox(); self.ai_pct.setRange(30, 200); self.ai_pct.setValue(60)   # PO 2026-09-05: 60% default
        self.ai_pct.setSuffix(" %")
        self.ai_pct.setToolTip("Field pace as a % of the track's GPLrank reference lap time: 100% = the "
                               "fastest AI car hits the GPLrank time for this circuit. Auto-preset when you "
                               "pick a track to GPLrank/your-best-lap·100 (so the fastest AI matches your "
                               "best lap); 50% if you've no recorded lap yet. Edit it freely.")
        form.addWidget(self.ai_pct, 4, 1)
        self.ai_pct_note = QLabel("")          # A3: shows how the preset was derived (your best vs GPLrank)
        self.ai_pct_note.setObjectName("hint")
        self.ai_pct_note.setWordWrap(True)
        form.addWidget(self.ai_pct_note, 5, 1, 1, 2)
        self.qual = QCheckBox("Qualifying session first (your hot lap sets the grid)")
        self.qual.setChecked(str(st.value("session/qual", "false")) == "true")   # default OFF: straight to the grid
        self.qual.setToolTip("Off (default): start on the grid, floor it to launch the field. On: a practice/qualifying session sets your grid slot first (press T to end it).")
        form.addWidget(self.qual, 6, 0, 1, 3)
        form.setColumnStretch(1, 1)
        form.setRowStretch(7, 1)

        # ---- Car: which setup, how you shift ----
        car = QGroupBox("Car — Lotus 49"); cform = QGridLayout(car); cols.addWidget(car, 2)
        # WWSETUP-1 (PO 2026-10-05): "The julia user can then choose which setup to use - default iracing, or ww".
        # Each choice is an iRacing session the car physics is locked to (JM_CARSETUP; see drive_native_mtk.jl).
        cform.addWidget(QLabel("Setup:"), 0, 0)
        self.carsetup = QComboBox()
        self.carsetup.addItems(["iRacing default", "WW103 fast loose (Wolfgang Wagner)"])
        self.carsetup.setToolTip("iRacing default: the Lotus 49 setup Julia has always raced.\n"
                                 "WW103 fast loose: Wolfgang Wagner's GPL Watkins Glen setup, driven in iRacing "
                                 "(session 261005) -- soft front springs, stiff rear bar, 35° drive ramp (the diff "
                                 "locks under power), front toe-out, long gearing. Loose on power, controllable at speed.")
        self.carsetup.setCurrentIndex(min(max(int(st.value("car/setup", 0)), 0), 1))
        self.carsetup.currentIndexChanged.connect(lambda i: QSettings("juliaRacer", "launcher").setValue("car/setup", i))
        cform.addWidget(self.carsetup, 0, 1)
        cform.addWidget(QLabel("Gearbox:"), 1, 0)
        self.gearbox = QComboBox()
        self.gearbox.addItems(["Automatic", "Manual (clutch + shift)"])
        self.gearbox.setToolTip("Automatic shifts up/down by speed and needs no clutch; Manual = work the clutch "
                                "(C) and shift (E/Q or the paddles). G toggles in-game.")
        self.gearbox.setCurrentIndex(min(max(int(st.value("car/gearbox", 0)), 0), 1))
        cform.addWidget(self.gearbox, 1, 1)
        cform.setColumnStretch(1, 1)
        cform.setRowStretch(2, 1)

        # Settings-tab widgets (built here so launch() keeps reading them; shown by settings_page())
        self.mute = QCheckBox("Mute the engine sound")
        self.mute.setToolTip("JM_NOSOUND")
        # 2026-10-03: an FFB on/off A/B for the PO's "side-to-side rocking that won't settle" -- the
        # sim car alone settles a steering pulse with no overshoot, so the open question is whether
        # the wheel's force feedback sustains the ~1 Hz shuttle. JM_NOFFB existed but was unreachable.
        self.noffb = QCheckBox("Turn force feedback off")
        self.noffb.setToolTip("JM_NOFFB")
        self.ibt = QCheckBox("Record iRacing-format telemetry (.ibt) to data/juliaracer/")
        self.replay = QCheckBox("Record a replay of every session (all cars) to data/juliaracer/")
        self.replay.setToolTip("Saves a .jmr recording of every car each session -- watch it from the Replays tab.")
        self.d2 = QCheckBox("Simplified 2-D physics (no jumps, lighter on slow PCs)")
        self.d2.setToolTip("JM_2D -- the full 3-D model is the default")
        for w, key, dflt in ((self.mute, "pref/mute", "false"), (self.noffb, "pref/noffb", "false"),
                             (self.ibt, "pref/ibt", "true"), (self.replay, "pref/replay", "true"),
                             (self.d2, "pref/d2", "false")):
            w.setChecked(str(st.value(key, dflt)) == "true")
            w.toggled.connect(lambda on, k=key: QSettings("juliaRacer", "launcher").setValue(k, "true" if on else "false"))
        self._gfx_group = self._build_gfx_group()

        root.addWidget(self._build_net_group())

        # a race needs opponents and can't run on the skidpad — keep the form coherent as the mode changes
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed(self.mode.currentIndex())
        # A3: when the track changes, pre-set the AI-speed % to match the human's best lap on that track
        self.track.currentIndexChanged.connect(self._track_changed)
        self._track_changed(self.track.currentIndex())

        # ---- the one primary action ----
        brow = QHBoxLayout()
        self.launch_b = QPushButton("Start")
        self.launch_b.setObjectName("primary")
        self.launch_b.setMinimumHeight(44); self.launch_b.setMinimumWidth(220)
        self.launch_b.setDefault(True)
        self.launch_b.clicked.connect(self.launch)
        self.stop_b = QPushButton("Stop")
        self.stop_b.setMinimumHeight(44)
        self.stop_b.setToolTip("End the session (Esc in the game window does the same)")
        self.stop_b.clicked.connect(self.stop)
        self.stop_b.setEnabled(False)
        self.keys_b = QPushButton("Controls…")
        self.keys_b.setToolTip("The keyboard and wheel controls")
        self.keys_b.clicked.connect(lambda: show_controls(self))
        self.log_b = QPushButton("Show log")
        self.log_b.setCheckable(True)
        self.log_b.toggled.connect(self._toggle_log)
        brow.addWidget(self.launch_b)
        brow.addWidget(self.stop_b)
        brow.addStretch(1)
        brow.addWidget(self.keys_b)
        brow.addWidget(self.log_b)
        root.addLayout(brow)
        self._mode_label()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(22)
        root.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log")
        self.log.setVisible(False)              # details on demand ("Show log"); shown by itself if the sim fails
        root.addWidget(self.log, 1)
        self._spacer = QWidget(); self._spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        root.addWidget(self._spacer, 1)

    def settings_page(self):
        """GUI-1: the rarely changed preferences, on their own tab (Main adds it)."""
        page = QWidget(); v = QVBoxLayout(page)
        v.addWidget(self._gfx_group)
        snd = QGroupBox("Sound and force feedback"); sv = QVBoxLayout(snd)
        sv.addWidget(self.mute); sv.addWidget(self.noffb); v.addWidget(snd)
        rec = QGroupBox("Recording"); rv = QVBoxLayout(rec)
        rv.addWidget(self.replay); rv.addWidget(self.ibt); v.addWidget(rec)
        adv = QGroupBox("Advanced"); av = QVBoxLayout(adv)
        av.addWidget(self.d2); v.addWidget(adv)
        v.addStretch(1)
        return page

    def _toggle_log(self, on):
        self.log.setVisible(on); self._spacer.setVisible(not on)
        self.log_b.setText("Hide log" if on else "Show log")

    def _mode_label(self):
        race = self.mode.currentIndex() == 1
        self.launch_b.setText("Start race" if race else "Start practice")

    def _status(self, msg):
        w = self.window()
        if isinstance(w, QMainWindow) and w.statusBar() is not None:
            w.statusBar().showMessage(msg)

    # PO 2026-09-03: "julia racer appImage needs some kind of graphical display showing that
    # it's compiling, and how long it will take. Users are used to compiled binaries."
    # Julia precompiles its packages on first use -- measured at over 25 minutes on the build
    # machine -- and until now that showed as an indeterminate "compiling…" bar, which is
    # indistinguishable from a hung application. Julia's non-TTY precompile output prints one
    # "<ms> ✓ <package>" line per finished package, so the count is observable even though the
    # per-round total is not announced until the round ends. Count them against a total measured
    # on the build machine and derive an ETA from the observed rate.
    # MEASURED, not estimated: a cold first run on the build box emitted 318 '✓' lines across
    # 14 precompile rounds (2026-09-03). An earlier guess of 216 was wrong by a third.
    PRECOMPILE_EXPECTED = 318
    # Package COUNT is not linear in TIME, and assuming it was would make the progress bar lie.
    # From the same reference run: at half the packages only 19% of the compile work is done --
    # the tail (ModelingToolkit 283 s, SymbolicUtils 161 s, Pkg 146 s) dominates. A count-linear
    # ETA says "5 min left" ten packages in and then runs for another hour, which is worse than
    # no estimate because the user concludes it has hung. This is the measured curve: fraction of
    # total work completed at each decile of package count.
    PRECOMPILE_CURVE = [0.011, 0.026, 0.053, 0.113, 0.192, 0.379, 0.660, 0.941, 0.954, 1.0]

    @classmethod
    def _precompile_work_fraction(cls, n):
        """Fraction of total compile WORK done after n packages (piecewise-linear on the curve)."""
        x = max(0.0, min(1.0, n / float(cls.PRECOMPILE_EXPECTED))) * 10.0
        i = int(x)
        if i >= 10:
            return 1.0
        lo = cls.PRECOMPILE_CURVE[i - 1] if i > 0 else 0.0
        return lo + (cls.PRECOMPILE_CURVE[i] - lo) * (x - i)

    # loading milestones the game flushes to stdout, in execution order → (substring, %, label)
    LOAD_STAGES = [
        ("loading GPL", 20, "loading track…"),
        ("extracting geometry", 45, "extracting geometry…"),
        ("loading textures", 62, "decoding textures…"),
        ("placed", 85, "placing scenery…"),
        ("Drive:", 100, "ready — window opening"),
    ]

    # -----------------------------------------------------------------------
    # MP-GUI-1 (PO 2026-10-01: "add multiplayer functionality to the julia pyQt GUI").
    # The sim has had LAN multiplayer since MP-3/MP-5 -- JM_NET=host|join, JM_NET_HOST, JM_NET_PORT,
    # host-authoritative AI -- but only from the command line. The sim has NO handshake: two PCs on
    # different tracks, or a client asking for fewer AI chassis than the host sends, connect and
    # silently disagree. So the launcher carries a tiny LOBBY on the next UDP port (game port + 1,
    # launcher-to-launcher only, the sim never sees it): while "Host" is selected this launcher
    # answers "JRLOBBY?" with its race settings as JSON, and the joining launcher's "Get host's
    # settings" applies them, so both sims start from the same track / mode / laps / AI count.
    # -----------------------------------------------------------------------
    NET_PORT_DEFAULT = 47700
    LOBBY_ASK = b"JRLOBBY?"

    # -----------------------------------------------------------------------
    # GFX-1 (PO 2026-10-01: "allow graphics options, including full-screen and resolution. Right now the graphics
    # always looks just one step up from 1024x768"). The sim rendered a fixed 1440x810 window; it now takes
    # JM_RES=<w>x<h>, JM_FULLSCREEN=1 (native mode unless a resolution is given) and JM_MSAA.
    # -----------------------------------------------------------------------
    def _build_gfx_group(self):
        if not hasattr(self, "_settings"):
            self._settings = QSettings("juliaRacer", "launcher")
        g = QGroupBox("Graphics")
        lay = QGridLayout(g)
        lay.addWidget(QLabel("Resolution:"), 0, 0)
        self.gfx_res = QComboBox()
        native = None
        scr = QApplication.primaryScreen()
        if scr is not None:
            sz = scr.size(); dpr = scr.devicePixelRatio()
            native = (int(round(sz.width() * dpr)), int(round(sz.height() * dpr)))
        self._res_values = []
        if native:
            self._res_values.append("native")         # the sim asks GLFW for the monitor's own mode
            self.gfx_res.addItem(f"Native ({native[0]} x {native[1]})")
        for w, h in ((3840, 2160), (2560, 1440), (1920, 1080), (1600, 900), (1440, 810)):
            if native and (w, h) == native:
                continue
            self._res_values.append(f"{w}x{h}")
            self.gfx_res.addItem(f"{w} x {h}" + ("  (old default)" if (w, h) == (1440, 810) else ""))
        saved = str(self._settings.value("gfx/res", self._res_values[0]))
        self.gfx_res.setCurrentIndex(self._res_values.index(saved) if saved in self._res_values else 0)
        lay.addWidget(self.gfx_res, 0, 1)
        self.gfx_full = QCheckBox("Full screen")
        self.gfx_full.setChecked(str(self._settings.value("gfx/full", "true")) == "true")
        self.gfx_full.setToolTip("Full screen on the primary monitor at the chosen resolution (Native = the monitor's own mode).")
        lay.addWidget(self.gfx_full, 0, 2)
        lay.addWidget(QLabel("Anti-aliasing:"), 1, 0)
        self.gfx_msaa = QComboBox(); self._msaa_values = ["8", "4", "2", "0"]
        self.gfx_msaa.addItems(["8x MSAA (smoothest)", "4x MSAA", "2x MSAA", "Off (fastest)"])
        sm = str(self._settings.value("gfx/msaa", "8"))
        self.gfx_msaa.setCurrentIndex(self._msaa_values.index(sm) if sm in self._msaa_values else 0)
        lay.addWidget(self.gfx_msaa, 1, 1)
        # TRACKSEG-3 (PO 2026-10-06): the section names ("Front Straight", "The Big Bend" at Watkins Glen) can be turned
        # off; ON is the default. Remembered like the graphics choices, and honoured by replays too (JM_SEGNAME_SECS=0).
        self.gfx_segnames = QCheckBox("Show track section names (e.g. \"Front Straight\")")
        self.gfx_segnames.setChecked(str(self._settings.value("hud/segnames", "true")) == "true")
        self.gfx_segnames.setToolTip("Shows each section's name above the 3-D view for a few seconds as you enter it.")
        lay.addWidget(self.gfx_segnames, 2, 0, 1, 3)
        return g

    def _gfx_env(self, qenv):
        res = self._res_values[self.gfx_res.currentIndex()]
        full = self.gfx_full.isChecked(); msaa = self._msaa_values[self.gfx_msaa.currentIndex()]
        self._settings.setValue("gfx/res", res); self._settings.setValue("gfx/full", "true" if full else "false")
        self._settings.setValue("gfx/msaa", msaa)
        qenv.insert("JM_RES", res); qenv.insert("JM_MSAA", msaa)
        if full:
            qenv.insert("JM_FULLSCREEN", "1")
        segnames = self.gfx_segnames.isChecked()
        self._settings.setValue("hud/segnames", "true" if segnames else "false")
        segnames_env(qenv, segnames)

    def _build_net_group(self):
        if not hasattr(self, "_settings"):
            self._settings = QSettings("juliaRacer", "launcher")
        g = QGroupBox("Multiplayer (LAN)")
        lay = QGridLayout(g)
        lay.addWidget(QLabel("Players:"), 0, 0)
        self.net_mode = QComboBox()
        self.net_mode.addItems(["Single player", "Host a LAN race", "Join a LAN race"])
        self.net_mode.setToolTip("Host: this PC runs the AI field and sends it to the other player.\n"
                                 "Join: connect to a host on your network; its AI cars are drawn here.")
        lay.addWidget(self.net_mode, 0, 1, 1, 2)
        self.net_host_l = QLabel("Host address:")
        lay.addWidget(self.net_host_l, 1, 0)
        self.net_host = QLineEdit(str(self._settings.value("net/host", "")))
        self.net_host.setPlaceholderText("e.g. 192.168.1.20 (shown on the host's launcher)")
        lay.addWidget(self.net_host, 1, 1)
        self.net_fetch = QPushButton("Get host's settings")
        self.net_fetch.setToolTip("Ask the host's launcher for its track, mode, laps and AI cars and use them here.")
        self.net_fetch.clicked.connect(self._lobby_fetch)
        lay.addWidget(self.net_fetch, 1, 2)
        self.net_port_l = QLabel("Port (UDP):")
        lay.addWidget(self.net_port_l, 2, 0)
        self.net_port = QSpinBox(); self.net_port.setRange(1024, 65534)
        self.net_port.setValue(int(self._settings.value("net/port", self.NET_PORT_DEFAULT)))
        self.net_port.setToolTip("The race uses this UDP port and the launcher lobby the next one; "
                                 "allow both through a firewall on the host.")
        lay.addWidget(self.net_port, 2, 1)
        self.net_info = QLabel("")
        self.net_info.setWordWrap(True)
        self.net_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.net_info, 3, 0, 1, 3)
        self._lobby_sock = None
        self._lobby_timer = QTimer(self)
        self._lobby_timer.timeout.connect(self._lobby_poll)
        self.net_mode.setCurrentIndex(int(self._settings.value("net/mode", 0)))
        self.net_mode.currentIndexChanged.connect(self._net_changed)
        self.net_port.valueChanged.connect(lambda _v: self._net_changed(self.net_mode.currentIndex()))
        self._net_changed(self.net_mode.currentIndex())
        return g

    @staticmethod
    def _lan_addresses():
        """This PC's LAN address(es) for the host to read out. A UDP connect sends nothing; it only
        asks the kernel which interface would route, which is the address a peer must use."""
        out = []
        for probe in ("192.168.255.255", "10.255.255.255", "172.31.255.255"):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as t:
                    t.connect((probe, 9)); a = t.getsockname()[0]
                if a and not a.startswith("127.") and a not in out:
                    out.append(a)
            except OSError:
                pass
        return out

    def _lobby_close(self):
        self._lobby_timer.stop()
        if self._lobby_sock is not None:
            self._lobby_sock.close(); self._lobby_sock = None

    def _net_changed(self, idx):
        join, host = idx == 2, idx == 1
        for w in (self.net_host_l, self.net_host, self.net_fetch):
            w.setVisible(join)
        for w in (self.net_port_l, self.net_port, self.net_info):   # GUI-1: LAN details only when playing over LAN
            w.setVisible(idx != 0)
        self._lobby_close()
        port = self.net_port.value()
        if host:
            ips = self._lan_addresses()
            txt = ("Tell the other player to choose <b>Join a LAN race</b> with address <b>"
                   + (" or ".join(ips) if ips else "this PC's LAN IP") + f"</b> and port <b>{port}</b>. ")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(("", port + 1)); s.setblocking(False)
                self._lobby_sock = s; self._lobby_timer.start(200)
                txt += "Their launcher can copy your track and race settings with <i>Get host's settings</i>."
            except OSError as e:
                txt += f"<span style='color:#c80'>(lobby port {port+1} unavailable: {e}; set the same track, mode, laps and AI cars on both PCs by hand)</span>"
            txt += " Launch first: the host's AI field starts with the host."
            self.net_info.setText(txt)
        elif join:
            self.net_info.setText("Use the <b>same track, mode, laps and AI cars</b> as the host "
                                  "(<i>Get host's settings</i> does that). The host steps the AI field; "
                                  "its cars are drawn here.")
        else:
            self.net_info.setText("")

    def _lobby_state(self):
        return {"jr": 1, "track": self.track.currentIndex(), "mode": self.mode.currentIndex(),
                "laps": self.laps.value(), "ai": self.ai.value(), "ai_pct": self.ai_pct.value(),
                "port": self.net_port.value()}

    def _lobby_poll(self):
        """Host side: answer every lobby query waiting on the socket (non-blocking, 5 Hz)."""
        s = self._lobby_sock
        while s is not None:
            try:
                data, addr = s.recvfrom(256)
            except (BlockingIOError, OSError):
                return
            if data.strip() == self.LOBBY_ASK:
                try:
                    s.sendto(json.dumps(self._lobby_state()).encode(), addr)
                    self.log.appendPlainText(f"[lobby] sent race settings to {addr[0]}")
                except OSError:
                    pass

    def _lobby_apply(self, st):
        """Join side: adopt the host's settings. Returns a one-line summary."""
        names = [self.track.itemText(i) for i in range(self.track.count())]
        self.mode.setCurrentIndex(int(st["mode"]))       # first: the mode handler may move the track
        self.track.setCurrentIndex(int(st["track"]))
        self.laps.setValue(int(st["laps"])); self.ai.setValue(int(st["ai"]))
        self.ai_pct.setValue(int(st["ai_pct"]))          # after the track: _track_changed presets it
        return (f"{names[int(st['track'])]}, {self.mode.itemText(int(st['mode']))}"
                + (f", {st['laps']} laps, {st['ai']} AI" if int(st["mode"]) == 1 else ""))

    def _lobby_fetch(self):
        host = self.net_host.text().strip()
        if not host:
            self.net_info.setText("<span style='color:#c80'>Enter the host's address first.</span>"); return
        port = self.net_port.value() + 1
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.6)
                for _ in range(3):                         # UDP: a lost datagram is retried, not fatal
                    try:
                        s.sendto(self.LOBBY_ASK, (host, port))
                        data, _a = s.recvfrom(1024)
                        st = json.loads(data.decode())
                        if st.get("jr") == 1:
                            break
                    except socket.timeout:
                        st = None
                else:
                    st = None
        except (OSError, ValueError) as e:
            self.net_info.setText(f"<span style='color:#c80'>Could not reach {host}: {e}</span>"); return
        if not st:
            self.net_info.setText(f"<span style='color:#c80'>No answer from {host}:{port}. Is its launcher "
                                  "open with <b>Host a LAN race</b> selected, and is the port allowed?</span>"); return
        if int(st.get("port", self.net_port.value())) != self.net_port.value():
            self.net_port.setValue(int(st["port"]))
        self.net_info.setText("Host's settings applied: <b>" + self._lobby_apply(st) + "</b>. Launch when ready.")

    def _net_env(self, qenv):
        """Set JM_NET* for the sim (launch() has already refused a Join with no address)."""
        idx = self.net_mode.currentIndex()
        self._settings.setValue("net/mode", idx)
        self._settings.setValue("net/port", self.net_port.value())
        self._settings.setValue("net/host", self.net_host.text().strip())
        if idx == 0:
            return
        qenv.insert("JM_NET_PORT", str(self.net_port.value()))
        if idx == 1:
            qenv.insert("JM_NET", "host")
        else:
            qenv.insert("JM_NET", "join")
            qenv.insert("JM_NET_HOST", self.net_host.text().strip())

    def _mode_changed(self, idx):
        """Race (idx 1) needs opponents and can't run on the skidpad; Practice is a lone car
        (no Laps / AI cars / AI speed — those rows are hidden)."""
        is_race = (idx == 1)
        for w in (self.laps_l, self.laps, self.ai_l, self.ai, self.ai_pct_l, self.ai_pct, self.ai_pct_note, self.qual):
            w.setVisible(is_race)                # race-only fields: hidden in Practice
        if hasattr(self, "launch_b"):
            self._mode_label()
        skid = self.track.model().item(1)        # "Skidpad" entry
        if skid is not None:
            skid.setEnabled(not is_race)         # grey it out for races (no race at the skidpad)
        if is_race:
            if self.track.currentIndex() == 1:   # currently on Skidpad → bump to Zandvoort
                self.track.setCurrentIndex(0)
            if self.ai.value() == 0:             # a race with 0 AI shows no field — default to a full grid
                self.ai.setValue(5)

    def _track_changed(self, idx):
        """B: pre-set AI-speed % to GPLrank / your-most-recent-race-average · 100 (best lap, then 50%, as fallback)."""
        key = TRACK_KEYS[idx] if 0 <= idx < len(TRACK_KEYS) else "zandvoort"
        self.ai_pct.setValue(preset_ai_pct(key))
        # AISPEED-1: show only a pace the preset would actually USE. Quoting "your best 2.708s"
        # under a 200% field is how the poisoned file looked reasonable for as long as it did.
        ref = REF_LAP.get(key)
        ok = lambda t: bool(t) and t > 0 and (not ref or t >= 0.5 * ref)
        recent = human_recents().get(key); recent = recent if ok(recent) else None
        best = human_bests().get(key);     best = best if ok(best) else None
        if recent:
            self.ai_pct_note.setText(f"≈ your recent avg {self._fmt(recent)} vs GPLrank {self._fmt(REF_LAP.get(key,0))}")
        elif best:
            self.ai_pct_note.setText(f"≈ your best {self._fmt(best)} vs GPLrank {self._fmt(REF_LAP.get(key,0))} (race for an avg)")
        else:
            self.ai_pct_note.setText("no recorded lap yet → 50%")

    @staticmethod
    def _fmt(sec):
        m, s = divmod(sec, 60)
        return f"{int(m)}:{s:06.3f}"

    def launch(self):
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            return
        if self.net_mode.currentIndex() == 2 and not self.net_host.text().strip():
            QMessageBox.warning(self, "Join a LAN race", "Enter the host's address (shown on the host's launcher).")
            return
        # GUI-1: remember the session so the next launch opens where this one left off
        st = self._settings
        st.setValue("session/track", self.track.currentIndex()); st.setValue("session/mode", self.mode.currentIndex())
        st.setValue("session/laps", self.laps.value()); st.setValue("session/ai", self.ai.value())
        st.setValue("session/qual", "true" if self.qual.isChecked() else "false")
        st.setValue("car/gearbox", self.gearbox.currentIndex())
        self._status(f"Starting {self.mode.currentText().lower()} at {self.track.currentText()}… "
                     "(the game window opens when loading finishes)")
        # free the device so the game's GLFW owns joystick #1 cleanly
        self.joy.stop_reader()
        qenv = QProcessEnvironment.systemEnvironment()
        qenv.insert("TRACK", ["zandvoort", "skidpad", "nurburgring",
                              "watglen", "monza", "spa"][self.track.currentIndex()])
        is_race = (self.mode.currentIndex() == 1)
        qenv.insert("JM_MODE", "race" if is_race else "practice")
        qenv.insert("JM_LAPS", str(self.laps.value()))
        qenv.insert("JM_AI", str(self.ai.value() if is_race else 0))   # Practice = lone car (no AI grid)
        qenv.insert("JM_AI_PCT", str(self.ai_pct.value()))
        qenv.insert("ZAND_SHIFT", "auto" if self.gearbox.currentIndex() == 0 else "manual")
        qenv.insert("JM_CARSETUP", ["default", "ww103"][self.carsetup.currentIndex()])
        if self.mute.isChecked():
            qenv.insert("JM_NOSOUND", "1")
        if self.noffb.isChecked():
            qenv.insert("JM_NOFFB", "1")
        if not self.ibt.isChecked():     # telemetry is on by default; this disables it
            qenv.insert("JM_NOIBT", "1")
        if not self.replay.isChecked():  # replay recording is on by default; this disables it
            qenv.insert("JM_NOREPLAY", "1")
        if self.qual.isChecked():        # opt in to a qualifying session (default: straight to the grid)
            qenv.insert("JM_QUAL", "1")
        if self.d2.isChecked():          # opt out of the default full-3D physics back to the planar model
            qenv.insert("JM_2D", "1")
        self._net_env(qenv)              # MP-GUI-1: host/join a LAN race
        self._gfx_env(qenv)              # GFX-1: resolution / full screen / anti-aliasing
        # E14: clear any stale race result so the post-race screen only shows THIS race
        self._result_path = os.path.join(HERE, "last_race_result.txt")
        try:
            os.remove(self._result_path)
        except OSError:
            pass
        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(qenv)
        self.proc.setWorkingDirectory(HERE)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._log)
        self.proc.finished.connect(self._done)
        # PO 2026-09-04: the sim exited mid-session and its Julia stacktrace existed ONLY in the
        # log pane above -- QProcess captures the child's output, so nothing reached a file and the
        # crash could not be diagnosed afterwards.  Mirror everything to a session log.
        try:
            self._sim_log = open(os.path.join(HERE, "last_sim_run.log"), "w",
                                 encoding="utf-8", errors="replace")
        except OSError:
            self._sim_log = None
        # use the prebuilt sysimage if present (skips ~40-80 s of physics/render JIT)
        jlargs = ["-t", "2", "--gcthreads=3,1", "--project=."]   # PERF-1: parallel GC mark + concurrent sweep (pauses 32-39 ms -> 16 ms)
        sysimg = os.path.join(HERE, "jlracer.so")
        fast = os.path.exists(sysimg)
        if fast:
            jlargs += ["-J", sysimg]
        jlargs.append("drive_native_mtk.jl")
        self.proc.start(find_julia(), jlargs)
        self.log.clear()
        self.log.appendPlainText(
            "launching drive_native_mtk.jl … " +
            ("(sysimage: faster start)\n" if fast else
             "(first load ~3–4 min — run build_sysimage.jl once to speed this up)\n"))
        self.launch_b.setEnabled(False)
        self.stop_b.setEnabled(True)
        self._stage = 0
        self.progress.setRange(0, 0)             # indeterminate "busy" during the Julia/MTK compile (no output yet)
        self.progress.setFormat("compiling…")
        self.progress.setVisible(True)

    def stop(self):
        if self.proc:
            self._stopping = True               # a requested stop is not a failure
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()

    def _log(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.log.appendPlainText(text.rstrip())
        f = getattr(self, "_sim_log", None)
        if f is not None:
            try: f.write(text); f.flush()   # flush: a crash must not lose the tail
            except (OSError, ValueError): pass

        # ---- precompilation phase: a REAL count and a time estimate, not a busy spinner ----
        done = len(re.findall(r"✓\s", text))
        if done or "Precompiling packages" in text:
            if getattr(self, "_pc_t0", None) is None:
                self._pc_t0 = time.monotonic()
                self._pc_n = 0
            self._pc_n += done
            n = self._pc_n
            total = max(self.PRECOMPILE_EXPECTED, n)
            frac = self._precompile_work_fraction(n)
            self.progress.setRange(0, 1000)
            self.progress.setValue(min(int(frac * 1000), 999))   # never 100% while work continues
            elapsed = time.monotonic() - self._pc_t0
            # ETA from the measured curve and the observed wall clock, so it self-corrects on a
            # slower or faster machine instead of trusting the build box's timings.
            if frac > 0.02 and elapsed > 20:
                remain = elapsed * (1.0 / frac - 1.0)
                mins = int(remain // 60)
                eta = f"about {mins} min left" if mins >= 1 else "under a minute left"
            else:
                eta = "estimating…"
            mm = int(elapsed // 60)
            self.progress.setFormat(
                f"compiling Julia packages — {n}/{total} — {mm} min elapsed, {eta}"
                f"   (one-off: later launches start immediately)")
            self.progress.setVisible(True)
            return                                          # don't let LOAD_STAGES fight for the bar

        if getattr(self, "_pc_t0", None) is not None and getattr(self, "_stage", 0) == 0:
            # first real game output after compiling: hand the bar over to the load milestones
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self._pc_t0 = None

        for marker, pct, label in self.LOAD_STAGES:        # advance the progress bar through load milestones
            if marker in text and pct > getattr(self, "_stage", 0):
                if self.progress.maximum() == 0:           # leave "busy" mode for a real percentage
                    self.progress.setRange(0, 100)
                self._stage = pct
                self.progress.setValue(pct)
                self.progress.setFormat(f"{label}  %p%")
                self._status("Loading: " + label)

    def _done(self):
        self.log.appendPlainText("\n— game exited —")
        # PO 2026-09-03: "when you type ESC in the 3D view, have it go back to the pyQt gui, not
        # just exit the app". The GUI never hid itself -- it simply lost focus to the game window,
        # so when the game quit the user was left looking at whatever was behind it, which reads as
        # the whole application having closed. Bring this window back to the front and give it
        # focus, so Esc returns you to the launcher.
        w = self.window()
        if w is not None:
            if w.isMinimized():
                w.showNormal()
            w.raise_()
            w.activateWindow()
        self.launch_b.setEnabled(True)
        self.stop_b.setEnabled(False)
        self.progress.setVisible(False)
        # GUI-1: say how it ended; a failure opens the log by itself (the stacktrace is the diagnosis)
        failed = (self.proc.exitStatus() != QProcess.ExitStatus.NormalExit or self.proc.exitCode() != 0) \
            and not getattr(self, "_stopping", False)
        self._stopping = False
        if failed:
            self.log_b.setChecked(True)
            self._status("The game stopped with an error -- the log below has the details (also last_sim_run.log).")
        else:
            self._status("Session ended. Ready.")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("")
        f = getattr(self, "_sim_log", None)
        if f is not None:
            try:
                f.write("\n[juliaRacer] sim exited: code=%r status=%r\n"
                        % (self.proc.exitCode(), self.proc.exitStatus()))
                f.close()
            except (OSError, ValueError, RuntimeError): pass
            self._sim_log = None
        # A fresh best/recent lap may have been recorded this race → refresh the AI-% preset.
        self._track_changed(self.track.currentIndex())
        # PO: show the result in a TAB, not a modal — robust even if the game crashed on exit (we just
        # read last_race_result.txt, which is written when the race finishes, before any exit crash).
        if self.on_result:
            self.on_result(getattr(self, "_result_path", os.path.join(HERE, "last_race_result.txt")))


class ResultTab(QWidget):
    """PO: the race result lives in a TAB (not a modal that duplicates 'choose track'). Two inner tabs —
    Classification (order + winner total / gap) and Your laps — populated from last_race_result.txt."""
    def __init__(self, on_again):
        super().__init__()
        self._on_again = on_again
        v = QVBoxLayout(self)
        self.head = QLabel("<i>No race yet — start one from the Race tab.</i>")
        self.head.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.head)
        self.tabs = QTabWidget()
        self.cls = QLabel(); self.cls.setTextFormat(Qt.TextFormat.RichText)
        cw = QWidget(); cv = QVBoxLayout(cw); cv.addWidget(self.cls); cv.addStretch(1)
        self.tabs.addTab(cw, "Classification")
        self.laps = QLabel(); self.laps.setTextFormat(Qt.TextFormat.RichText)
        lw = QWidget(); lv = QVBoxLayout(lw); lv.addWidget(self.laps); lv.addStretch(1)
        self.tabs.addTab(lw, "Your laps")
        v.addWidget(self.tabs)
        brow = QHBoxLayout()
        again = QPushButton("Race again")
        again.clicked.connect(lambda: self._on_again())
        brow.addWidget(again); brow.addStretch(1)
        v.addLayout(brow)

    def load(self, path):
        """Render last_race_result.txt into the tab. Returns True if a result was found."""
        if not os.path.exists(path):
            return False
        try:
            rows = [ln.rstrip("\n").split("\t") for ln in open(path) if ln.strip()]
        except OSError:
            return False
        d = {r[0]: r[1] for r in rows if len(r) >= 2 and not r[0].startswith("P")}
        grid = [(r[1], r[2] if len(r) >= 3 else "") for r in rows if r[0].startswith("P") and len(r) >= 2]
        best_any = next((r[1:] for r in rows if r[0] == "best_any"), ["-", "-"])
        your_laps = d.get("you_laps", "").split(",") if d.get("you_laps") else []
        self.head.setText(
            f"<b>{d.get('track','?').title()} — {d.get('laps','?')} laps</b><br>"
            f"You finished <b>P{d.get('you_pos','?')}</b> of {d.get('field','?')} "
            f"(started P{d.get('you_start','?')})")
        # Classification: P, car, winner-total / gap; You row a readable light highlight
        crows = ["<table cellspacing=0 cellpadding=4 width='100%'>",
                 "<tr style='color:#888'><th align=left>Pos</th><th align=left>Car</th>"
                 "<th align=right>Total&nbsp;/&nbsp;gap</th></tr>"]
        for i, (name, gap) in enumerate(grid, 1):
            you = (name == "You")
            sty = " style='background:#ffe98a;color:#000'" if you else ""
            nm = f"<b>{name}</b>" if you else name
            crows.append(f"<tr{sty}><td>P{i}</td><td>{nm}</td><td align=right>{gap}</td></tr>")
        crows.append("</table>")
        fast = (f"<br><b>Fastest lap:</b> {best_any[0]}"
                + (f" &nbsp;({best_any[1]})" if len(best_any) > 1 else ""))
        self.cls.setText("".join(crows) + fast)
        # Your laps: per-lap times, best flagged
        if your_laps:
            lrows = ["<table cellspacing=0 cellpadding=4 width='100%'>",
                     "<tr style='color:#888'><th align=left>Lap</th><th align=right>Time</th></tr>"]
            best_str = d.get("you_best", ""); seen_best = False
            for i, lt in enumerate(your_laps, 1):
                mark = ""
                if lt == best_str and not seen_best:
                    mark = " &nbsp;<span style='color:#6c6'>(best)</span>"; seen_best = True
                lrows.append(f"<tr><td>Lap {i}</td><td align=right>{lt}{mark}</td></tr>")
            lrows.append("</table>")
        else:
            lrows = ["<i>No completed laps recorded.</i>"]
        self.laps.setText("".join(lrows)
                          + f"<br><b>Your best:</b> {d.get('you_best','-')} &nbsp;·&nbsp; "
                            f"<b>Total:</b> {d.get('you_total','-')}")
        return True


class ReplayTab(QWidget):
    """E18: pick a saved .jmr race recording and watch it back (cockpit/chase + VCR keys)."""
    def __init__(self, joy):
        super().__init__()
        self.joy = joy
        self.proc = None
        self.dir = os.path.join(os.path.dirname(os.path.dirname(HERE)), "data", "juliaracer")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Pick a saved race recording (.jmr) and watch it back:"))
        self.combo = QComboBox()
        v.addWidget(self.combo)
        row = QHBoxLayout()
        self.refresh_b = QPushButton("Refresh")
        self.watch_b = QPushButton("Watch replay")
        self.stop_b = QPushButton("Stop")
        self.stop_b.setEnabled(False)
        row.addWidget(self.refresh_b)
        row.addWidget(self.watch_b)
        row.addWidget(self.stop_b)
        v.addLayout(row)
        v.addWidget(QLabel("In the replay:  SPACE play/pause · ←/→ scrub · ↑/↓ speed · Esc quit"))
        # REPLAYLOAD-1 (PO 2026-09-19): "the replay takes a very long time to load ... at minimum a
        # progress bar is needed ... it can seem hung". The Drive tab has had load milestones since
        # 2026-09-03; the replay had only "(loading)". Same bar, same milestones, plus the replay's own.
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(22)
        v.addWidget(self.progress)
        v.addWidget(QLabel("Cinematics:  V = switch ANGLE (cockpit · chase · TV/distant · F10 rear · nose · RR-suspension)   ·   C = switch CAR (cycle the field)"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        v.addWidget(self.log)
        self.refresh_b.clicked.connect(self.refresh)
        self.watch_b.clicked.connect(self.watch)
        self.stop_b.clicked.connect(self.stop)
        self.refresh()

    def refresh(self):
        self.combo.clear()
        try:
            files = sorted((f for f in os.listdir(self.dir) if f.endswith(".jmr")), reverse=True)
        except OSError:
            files = []
        self.combo.addItems(files)

    def watch(self):
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            return
        name = self.combo.currentText()
        if not name:
            return
        m = re.match(r"replay_(\w+) (\d+)ai", name)
        if not m:
            self.log.appendPlainText("could not read track / car count from the filename")
            return
        track, nai = m.group(1), m.group(2)
        self.joy.stop_reader()
        qenv = QProcessEnvironment.systemEnvironment()
        qenv.insert("TRACK", track)
        qenv.insert("JM_MODE", "race")
        qenv.insert("JM_AI", nai)
        qenv.insert("JM_REPLAY", os.path.join(self.dir, name))
        qenv.insert("JM_VIEW", "0")
        segnames_env(qenv, str(QSettings("juliaRacer", "launcher").value("hud/segnames", "true")) == "true")   # TRACKSEG-3
        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(qenv)
        self.proc.setWorkingDirectory(HERE)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._log)
        self.proc.finished.connect(self._done)
        self._stage = 0
        self._t0 = time.monotonic()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("starting Julia…  (a replay loads the whole track, like a race: 3–4 min)")
        self.progress.setVisible(True)
        jlargs = ["-t", "2", "--gcthreads=3,1", "--project=."]   # PERF-1: parallel GC mark + concurrent sweep (pauses 32-39 ms -> 16 ms)
        sysimg = os.path.join(HERE, "jlracer.so")
        if os.path.exists(sysimg):
            jlargs += ["-J", sysimg]
        jlargs.append("drive_native_mtk.jl")
        self.proc.start(find_julia(), jlargs)
        self.log.clear()
        self.log.appendPlainText(f"replaying {name} … (loading)")
        self.watch_b.setEnabled(False)
        self.stop_b.setEnabled(True)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()

    # REPLAYLOAD-1: the same load milestones as the Drive tab, so the bar moves on real events.
    LOAD_STAGES = [
        ("loading GPL", 15, "loading track…"),
        ("extracting geometry", 35, "extracting geometry…"),
        ("loading textures", 50, "decoding textures…"),
        ("placed", 70, "placing scenery…"),
        ("AI car models begin", 80, "loading the cars…"),
        ("physics build", 90, "building physics…"),
        ("REPLAY:", 100, "ready — replay window opening"),
    ]

    def _log(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.log.appendPlainText(text.rstrip())
        for marker, pct, label in self.LOAD_STAGES:
            if marker in text and pct > self._stage:
                self._stage = pct
                mm = int((time.monotonic() - self._t0) // 60)
                self.progress.setValue(pct)
                self.progress.setFormat(f"{label}  %p%   ({mm} min elapsed)")

    def _done(self):
        self.log.appendPlainText("\n— replay ended —")
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.watch_b.setEnabled(True)
        self.stop_b.setEnabled(False)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Julia Racer — Lotus 49")
        self.resize(980, 700)
        self.joy = JoyReader(self)
        tabs = QTabWidget()
        self.tabs = tabs
        self.cal = CalibrateTab(self.joy, self._reload)
        self.result = ResultTab(self._race_again)
        self.drive = DriveTab(self.joy, on_result=self._show_result_tab)
        self.replay = ReplayTab(self.joy)
        # GUI-1: tabs named for the task, in the order a session runs: set up and start, read the result,
        # watch it back; then the things changed once (Settings, Controller).
        tabs.addTab(self.drive, "Race")
        tabs.addTab(self.result, "Results")
        tabs.addTab(self.replay, "Replays")
        tabs.addTab(self.drive.settings_page(), "Settings")
        tabs.addTab(self.cal, "Controller")
        tabs.currentChanged.connect(self._tab)
        self.setCentralWidget(tabs)
        self._build_menus()
        self.statusBar().showMessage("Ready")
        self.joy.start_reader(1)

    def _build_menus(self):
        mb = self.menuBar()
        game = mb.addMenu("&Game")
        a = game.addAction("&Start"); a.setShortcut("Ctrl+Return"); a.triggered.connect(self._start)
        a = game.addAction("S&top"); a.triggered.connect(self.drive.stop)
        game.addSeparator()
        a = game.addAction("&Quit"); a.setShortcut("Ctrl+Q"); a.triggered.connect(self.close)
        hlp = mb.addMenu("&Help")
        a = hlp.addAction("&Controls…"); a.setShortcut("F1"); a.triggered.connect(lambda: show_controls(self))
        a = hlp.addAction("&About Julia Racer"); a.triggered.connect(self._about)

    def _start(self):
        self.tabs.setCurrentWidget(self.drive)
        self.drive.launch()

    def _about(self):
        QMessageBox.about(self, "About Julia Racer",
                          "<b>Julia Racer</b><br>The 1967 Lotus 49 on GPL's circuits, with physics fitted to iRacing "
                          "telemetry (ModelingToolkit) and an AI field that drives like GPL's.")

    def _show_result_tab(self, path):
        """PO: after a race, populate the Race Result tab and switch to it (no modal popup)."""
        if self.result.load(path):
            self.tabs.setCurrentWidget(self.result)

    def _race_again(self):
        self.tabs.setCurrentWidget(self.drive)
        self.drive.launch()

    def _tab(self, i):
        # keep the reader alive while calibrating; it's harmless during Drive too,
        # but DriveTab.launch()/ReplayTab.watch() stop it so the game owns the device cleanly.
        # 2026-10-03: match the WIDGET, not an index. This tested `i == 2` -- the Calibrate tab's index
        # before "Race Result" was inserted ahead of it -- so after any drive (which stops the reader)
        # the Calibrate tab never restarted it: frozen bars, dead buttons, a wizard that cannot advance.
        if self.tabs.widget(i) is self.cal and self.joy.state() == QProcess.ProcessState.NotRunning:
            self.joy.start_reader(1)

    def _reload(self):
        self.cal.map = JoyMap.load(CONF)

    def closeEvent(self, e):
        self.joy.stop_reader()
        if self.drive.proc:
            self.drive.stop()
        super().closeEvent(e)


# GUI-1 S2 (PO 2026-10-06: "restyle the GUI to be similar to the PyQt GUI's of pokerIQ and bridgeIQ"). Their shared look,
# taken from the running apps (offscreen grabs, 261006/gui/): a dark navy/charcoal background, flat slate buttons, ONE
# green primary action (bridgeIQ "First deal", pokerIQ "New Hand"), green-outlined panels, bold white Arial, and a
# near-black status strip with green text. JR_THEME=classic keeps the platform look (A/B).
THEME = """
QMainWindow, QDialog { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0e1a24, stop:1 #1a2834); }
QWidget { color: #e8eef3; font-family: Arial; font-size: 11pt; }
QTabWidget::pane { border: 1px solid #2c3e50; border-radius: 6px; background: rgba(10, 18, 26, 120); top: -1px; }
QTabBar::tab { background: #1b2733; color: #b9c7d3; padding: 8px 18px; border: 1px solid #2c3e50;
               border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
QTabBar::tab:selected { background: #24384a; color: #ffffff; font-weight: bold; border-bottom: 3px solid #3fa86a; }
QTabBar::tab:hover:!selected { background: #22313f; }
QGroupBox { background: rgba(255, 255, 255, 10); border: 1px solid #2f6f4f; border-radius: 6px;
            margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #7fd1ae; }
QLabel { background: transparent; }
QLabel#hint { color: #8aa0b2; font-size: 9pt; font-weight: normal; }
QPushButton { background: #2a3a4a; color: #dde6ee; border: 1px solid #3e5468; border-radius: 4px; padding: 6px 14px; }
QPushButton:hover { background: #34495c; }
QPushButton:pressed { background: #22303d; }
QPushButton:checked { background: #24384a; border-color: #3fa86a; }
QPushButton:disabled { background: #1c2731; color: #5f6f7e; border-color: #2a3742; }
QPushButton#primary { background: #2e7d4f; border: 1px solid #3fa86a; color: #ffffff; font-size: 13pt; font-weight: bold; }
QPushButton#primary:hover { background: #379160; }
QPushButton#primary:pressed { background: #276b43; }
QPushButton#primary:disabled { background: #1f3a2b; color: #6f8f7d; border-color: #2a4a38; }
QComboBox, QSpinBox, QLineEdit { background: #0f1922; color: #e8eef3; border: 1px solid #34495e; border-radius: 3px;
                                 padding: 4px 6px; selection-background-color: #2e7d4f; }
QComboBox:hover, QSpinBox:hover, QLineEdit:hover { border-color: #3fa86a; }
QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled { color: #5f6f7e; border-color: #26333f; }
QComboBox QAbstractItemView { background: #0f1922; color: #e8eef3; border: 1px solid #34495e;
                              selection-background-color: #2e7d4f; selection-color: #ffffff; }
QSpinBox { padding-right: 22px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 20px; background: #1f2c38;
                                             border-left: 1px solid #34495e; }
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 3px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 3px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #2e7d4f; }
QSpinBox::up-arrow { image: url(@UI@/arrow_up.png); width: 10px; height: 6px; }
QSpinBox::down-arrow { image: url(@UI@/arrow_down.png); width: 10px; height: 6px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #4a6276; border-radius: 3px; background: #0f1922; }
QCheckBox::indicator:checked { background: #2e7d4f; border-color: #3fa86a; image: url(@UI@/check.png); }
QCheckBox::indicator:hover { border-color: #3fa86a; }
QProgressBar { background: #0f1922; border: 1px solid #34495e; border-radius: 4px; color: #e8eef3; text-align: center; }
QProgressBar::chunk { background: #2e7d4f; border-radius: 3px; }
QPlainTextEdit, QTextEdit { background: #0b1218; color: #b8c7d3; border: 1px solid #2c3e50; border-radius: 4px;
                            font-family: monospace; font-size: 9pt; }
QMenuBar { background: #0b1218; color: #dde6ee; }
QMenuBar::item:selected { background: #24384a; }
QMenu { background: #16222d; color: #e8eef3; border: 1px solid #34495e; }
QMenu::item:selected { background: #2e7d4f; }
QStatusBar { background: #0b1218; color: #5fd38d; font-weight: bold; }
QToolTip { background: #16222d; color: #e8eef3; border: 1px solid #3fa86a; }
QScrollBar:vertical { background: #0f1922; width: 12px; }
QScrollBar::handle:vertical { background: #34495e; border-radius: 5px; min-height: 24px; }
"""


def apply_theme(app):
    if os.environ.get("JR_THEME", "") != "classic":
        app.setStyle("Fusion")             # the platform style ignores parts of a stylesheet; Fusion honours all of it
        app.setStyleSheet(THEME.replace("@UI@", UI_DIR.replace(os.sep, "/")))


def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
