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
import sys

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QPlainTextEdit, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

HERE = os.path.dirname(os.path.abspath(__file__))
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
    you've never raced/lapped here.  Clamped to the spinbox range [30, 200]."""
    base = human_recents().get(track_key) or human_bests().get(track_key)
    ref = REF_LAP.get(track_key)
    if not base or not ref:
        return 50
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

        form = QGridLayout()
        form.addWidget(QLabel("Track:"), 0, 0)
        self.track = QComboBox()
        self.track.addItems(["Zandvoort", "Skidpad", "Nürburgring", "Watkins Glen", "Monza", "Spa"])
        self.track.setCurrentIndex(1)        # Skidpad default
        form.addWidget(self.track, 0, 1)
        form.addWidget(QLabel("Mode:"), 1, 0)
        self.mode = QComboBox()
        self.mode.addItems(["Practice", "Race"])   # Practice = lone car; Race = AI grid
        form.addWidget(self.mode, 1, 1)
        # Race-only fields (Laps / AI cars / AI speed) — hidden in Practice (a lone car has none)
        self.laps_l = QLabel("Laps (race):")
        form.addWidget(self.laps_l, 2, 0)
        self.laps = QSpinBox(); self.laps.setRange(1, 99); self.laps.setValue(3)
        form.addWidget(self.laps, 2, 1)
        self.ai_l = QLabel("AI cars:")
        form.addWidget(self.ai_l, 3, 0)
        self.ai = QSpinBox(); self.ai.setRange(0, 5); self.ai.setValue(5)   # default to a full grid (PO)
        form.addWidget(self.ai, 3, 1)
        self.ai_pct_l = QLabel("AI speed %:")
        form.addWidget(self.ai_pct_l, 4, 0)
        self.ai_pct = QSpinBox(); self.ai_pct.setRange(30, 200); self.ai_pct.setValue(100)
        self.ai_pct.setToolTip("Field pace as a % of the track's GPLrank reference lap time: 100% = the "
                               "fastest AI car hits the GPLrank time for this circuit. Auto-preset when you "
                               "pick a track to GPLrank/your-best-lap·100 (so the fastest AI matches your "
                               "best lap); 50% if you've no recorded lap yet. Edit it freely.")
        form.addWidget(self.ai_pct, 4, 1)
        self.ai_pct_note = QLabel("")          # A3: shows how the preset was derived (your best vs GPLrank)
        self.ai_pct_note.setStyleSheet("color:#888;font-size:10px")
        form.addWidget(self.ai_pct_note, 4, 2)
        form.addWidget(QLabel("Gearbox:"), 5, 0)
        self.gearbox = QComboBox()
        self.gearbox.addItems(["Automatic (auto-clutch + auto-shift)", "Manual (clutch C + shift E/Q)"])
        self.gearbox.setToolTip("Automatic shifts up/down by speed and needs no clutch; Manual = work the clutch (G also toggles in-game).")
        form.addWidget(self.gearbox, 5, 1)
        self.mute = QCheckBox("Mute engine audio (JM_NOSOUND)")
        form.addWidget(self.mute, 6, 1)
        self.ibt = QCheckBox("Record iRacing .ibt telemetry → data/juliaracer/")
        self.ibt.setChecked(True)        # on by default
        form.addWidget(self.ibt, 7, 1)
        self.replay = QCheckBox("Record race replay (all cars) → data/juliaracer/")
        self.replay.setChecked(True)     # on by default (PO); untick to skip recording
        self.replay.setToolTip("Saves a .jmr recording of every car each race — replay it from the Replay tab.")
        form.addWidget(self.replay, 8, 1)
        self.qual = QCheckBox("Qualifying session first (your hot lap sets the grid)")
        self.qual.setChecked(False)      # default OFF: Race goes straight to the grid with the AI visible
        self.qual.setToolTip("Off (default): start on the grid, floor it to launch the field. On: a practice/qualifying session sets your grid slot first (press T to end it).")
        form.addWidget(self.qual, 9, 1)
        self.d2 = QCheckBox("Simplified 2-D physics (no jumps, lighter; JM_2D)")
        form.addWidget(self.d2, 10, 1)   # 3-D is the default; tick this only to fall back to planar
        root.addLayout(form)

        # a race needs opponents and can't run on the skidpad — keep the form coherent as the mode changes
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed(self.mode.currentIndex())
        # A3: when the track changes, pre-set the AI-speed % to match the human's best lap on that track
        self.track.currentIndexChanged.connect(self._track_changed)
        self._track_changed(self.track.currentIndex())

        brow = QHBoxLayout()
        self.launch_b = QPushButton("Launch")
        self.launch_b.clicked.connect(self.launch)
        self.stop_b = QPushButton("Stop")
        self.stop_b.clicked.connect(self.stop)
        self.stop_b.setEnabled(False)
        brow.addWidget(self.launch_b)
        brow.addWidget(self.stop_b)
        brow.addStretch(1)
        root.addLayout(brow)

        note = QLabel("First launch compiles & loads assets — the window can take "
                      "~3–4 min to appear. Controls: W/S gas·brake, A/D steer, E/Q shift, "
                      "C clutch, G auto⇄manual, V view, R respawn, M mute, Esc quit. "
                      "Your calibrated wheel/pedals work natively.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#888")
        root.addWidget(note)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setMinimumHeight(22)
        root.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family:monospace;font-size:11px")
        root.addWidget(self.log, 1)

    # loading milestones the game flushes to stdout, in execution order → (substring, %, label)
    LOAD_STAGES = [
        ("loading GPL", 20, "loading track…"),
        ("extracting geometry", 45, "extracting geometry…"),
        ("loading textures", 62, "decoding textures…"),
        ("placed", 85, "placing scenery…"),
        ("Drive:", 100, "ready — window opening"),
    ]

    def _mode_changed(self, idx):
        """Race (idx 1) needs opponents and can't run on the skidpad; Practice is a lone car
        (no Laps / AI cars / AI speed — those rows are hidden)."""
        is_race = (idx == 1)
        for w in (self.laps_l, self.laps, self.ai_l, self.ai, self.ai_pct_l, self.ai_pct):
            w.setVisible(is_race)                # race-only fields: hidden in Practice
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
        recent = human_recents().get(key)
        best = human_bests().get(key)
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
        if self.mute.isChecked():
            qenv.insert("JM_NOSOUND", "1")
        if not self.ibt.isChecked():     # telemetry is on by default; this disables it
            qenv.insert("JM_NOIBT", "1")
        if not self.replay.isChecked():  # replay recording is on by default; this disables it
            qenv.insert("JM_NOREPLAY", "1")
        if self.qual.isChecked():        # opt in to a qualifying session (default: straight to the grid)
            qenv.insert("JM_QUAL", "1")
        if self.d2.isChecked():          # opt out of the default full-3D physics back to the planar model
            qenv.insert("JM_2D", "1")
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
        # use the prebuilt sysimage if present (skips ~40-80 s of physics/render JIT)
        jlargs = ["-t", "2", "--project=."]
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
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()

    def _log(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.log.appendPlainText(text.rstrip())
        for marker, pct, label in self.LOAD_STAGES:        # advance the progress bar through load milestones
            if marker in text and pct > getattr(self, "_stage", 0):
                if self.progress.maximum() == 0:           # leave "busy" mode for a real percentage
                    self.progress.setRange(0, 100)
                self._stage = pct
                self.progress.setValue(pct)
                self.progress.setFormat(f"{label}  %p%")

    def _done(self):
        self.log.appendPlainText("\n— game exited —")
        self.launch_b.setEnabled(True)
        self.stop_b.setEnabled(False)
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("")
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
        self.head = QLabel("<i>No race yet — start one from the Drive tab.</i>")
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
        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(qenv)
        self.proc.setWorkingDirectory(HERE)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.log.appendPlainText(
                bytes(self.proc.readAllStandardOutput()).decode(errors="replace").rstrip()))
        self.proc.finished.connect(self._done)
        jlargs = ["-t", "2", "--project=."]
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

    def _done(self):
        self.log.appendPlainText("\n— replay ended —")
        self.watch_b.setEnabled(True)
        self.stop_b.setEnabled(False)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("juliaMotor — Lotus 49")
        self.resize(900, 640)
        self.joy = JoyReader(self)
        tabs = QTabWidget()
        self.tabs = tabs
        self.cal = CalibrateTab(self.joy, self._reload)
        self.result = ResultTab(self._race_again)
        self.drive = DriveTab(self.joy, on_result=self._show_result_tab)
        self.replay = ReplayTab(self.joy)
        tabs.addTab(self.drive, "Drive")
        tabs.addTab(self.result, "Race Result")
        tabs.addTab(self.replay, "Replay")
        tabs.addTab(self.cal, "Calibrate controller")
        tabs.currentChanged.connect(self._tab)
        self.setCentralWidget(tabs)
        self.joy.start_reader(1)

    def _show_result_tab(self, path):
        """PO: after a race, populate the Race Result tab and switch to it (no modal popup)."""
        if self.result.load(path):
            self.tabs.setCurrentWidget(self.result)

    def _race_again(self):
        self.tabs.setCurrentWidget(self.drive)
        self.drive.launch()

    def _tab(self, i):
        # keep the reader alive while calibrating (tab 2); it's harmless during Drive too,
        # but DriveTab.launch()/ReplayTab.watch() stop it so the game owns the device cleanly.
        if i == 2 and self.joy.state() == QProcess.ProcessState.NotRunning:
            self.joy.start_reader(1)

    def _reload(self):
        self.cal.map = JoyMap.load(CONF)

    def closeEvent(self, e):
        self.joy.stop_reader()
        if self.drive.proc:
            self.drive.stop()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
