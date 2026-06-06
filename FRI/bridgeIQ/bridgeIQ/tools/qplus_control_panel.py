"""PyQt6 control panel for biq-vs-Q-Plus Closed-Room matches.

Replaces the 3 helper terminals (proxy, biq, autoclicker) with one
window: configure a run, start/stop it, watch live progress (Deal N/M,
process health, biq log tail), and aggregate the complete result from
Q-Plus's .qss export. The Q-Plus server window itself stays separate
(it's the opponent engine) — start it under wine-9.0 and Start the
bridge server on :5555 before using this panel.

Run:  python3 tools/qplus_control_panel.py
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QProcess, QTimer, Qt, QPoint
from PyQt6.QtGui import QFont, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
    QGridLayout, QMessageBox,
)

BIQ_ROOT = Path(__file__).resolve().parent.parent
# Q-Plus server Wine prefix (FRI/WP) — used to launch it and to
# `wineserver -k` it between unattended sessions.
WP_SERVER = BIQ_ROOT.parent.parent / "WP"
QSS_DIR = (BIQ_ROOT.parent.parent
           / "WP/drive_c/games/qbridge17/DATA/LOCAL-MATCHES")
PROXY_LOG = BIQ_ROOT / "tools/runs/qnet_session.log"
BIQ_LOG = BIQ_ROOT / "tools/runs/biq_session.log"
BIQ_N_LOG = BIQ_ROOT / "tools/runs/biq_N.log"
BIQ_S_LOG = BIQ_ROOT / "tools/runs/biq_S.log"
BIQ_E_LOG = BIQ_ROOT / "tools/runs/biq_E.log"   # double-pair Room 2 (biq E/W)
BIQ_W_LOG = BIQ_ROOT / "tools/runs/biq_W.log"
# Saved Room-1 / Room-2 logs for the double-pair board-a-match compare,
# plus the optional all-Q-Plus baseline .qss for the closed-room decomposition.
DP_ROOM1_LOG = BIQ_ROOT / "tools/runs/dp_room1_NS.log"
DP_ROOM2_LOG = BIQ_ROOT / "tools/runs/dp_room2_EW.log"
DP_BASELINE_QSS = BIQ_ROOT / "tools/runs/dp_baseline_allqp.qss"
SERVER_PORT, PROXY_PORT = 5555, 5556
SYSTEMS = ["SAYC", "TwoOverOne", "StandardAcol", "StandardFrench",
           "Precision90M"]
# Calibrated screen positions. closed_room -> our own file; the lower-left
# cycle button shares qplus_button_loop.py's file so the clicker reads it.
SERVER_BTN_FILE = Path.home() / ".qplus_server_buttons.json"
CYCLE_BTN_FILE = Path.home() / ".qplus_button_loop.json"
TRANSITION_FILE = Path.home() / ".qplus_transition.json"
SYS_CAL_FILE = Path.home() / ".qplus_mixed_corpus.json"
PANEL_LOG = BIQ_ROOT / "tools/runs/panel.log"   # persisted panel actions
AB_REF_FILE = BIQ_ROOT / "tools/runs/ab/ab_reference.json"  # Run-A deal id

# Bump this on any user-visible behaviour change. It's shown in the title
# bar AND logged on startup, so you can tell at a glance whether a freshly
# launched panel actually has the latest fix (no more "did it reload?").
PANEL_BUILD = "2026-06-06b · Match End dialog dismiss in .qss export + crash-watchdog"
# Fixed seed for 'reproducible random' systems — both A and B pass the same
# value so they draw identical per-deal systems on identical boards.
REPRO_SYS_SEED = 20260604

HELP_TEXT = """\
ONE-CLICK / LIFECYCLE (top row)
  Run full session (one click)  Launch Q-Plus (if needed) -> start the
        bridge server -> start biq -> deal board 1 -> run the autoclicker
        -> aggregate. Hands-off. Don't touch the mouse while it runs.
  Launch Q-Plus server          Just start Q-Plus under wine-9.0 and click
        Start on the bridge-server dialog so :5555 is listening.
  Exit Q-Plus (kill wine)       THE EXIT COMMAND. Force-quit Q-Plus + all
        wine; clears the :5555 socket and the 64-board scoring cap. Export
        the .qss FIRST if you want to keep the run (this discards Q-Plus's
        score table).

STARTUP PROCEDURE — STEP / AUTOPILOT (debugger for a balky Q-Plus)
  The startup is broken into discrete steps (each = one series of clicks):
    1 Launch Q-Plus + dismiss splash   2 Start bridge server (wait :5555)
    3 Minimise the server dialog       4 Start biq + wait for 'joined'
    5 Set bidding systems (deal 1)     6 Set East = Computer
    7 Deal board 1 (Closed Room)       8 Start the autoclicker
  Step >       Run the NEXT step, then stop and wait. Watch the log to see
        exactly what happened (e.g. an auto-dealt bidding box popping up
        before the server starts) and fix anything out of order by hand
        before continuing.
  Autopilot >  Run all remaining steps back-to-back. Toggle on at any point;
        toggle off to stop after the current step.
  Reset steps  Move the pointer back to step 1 (does NOT undo Q-Plus state).
  A step that fails stops autopilot and is RETRIED by the next 'Step >' — and
  a retry short-circuits if you fixed the blocker by hand (e.g. the server is
  now listening). 'Stop all' halts the stepper but keeps your place.

NUMBERED STEPS (manual alternative to one-click)
  1 > Start server+biq   Launch the two biq clients (needs :5555 already up).
  2 > Deal board 1       Click Q-Plus's 'Closed Room' to deal the first board.
  3 > Run autoclicker    Start the clicker that drives Q-Plus through the deals.
  Stop all               Terminate biq + the autoclicker (Q-Plus stays up).

UTILITIES (third row)
  New run (reset logs)   Clear the logs/result for a fresh run.
  Export .qss            Drive Q-Plus View > Scoring Table > Save and send >
        OK to write the score sheet, then aggregate from it. Do this before
        exiting if 'Exit automatically' is off.
  Aggregate (.qss)       Re-score from the newest .qss (no new export).
  Calibrate / edit captures...   Show + edit every click position the harness
        uses; Capture re-sets one via a 5s countdown (live mouse readout).

DOUBLE-PAIR VALIDATION (section 2b)  — the unbiased teams test
  Play the SAME deck twice with biq on opposite sides, so card luck cancels:
    Room 1 (biq side = N/S)  biq N/S vs Q-Plus E/W  → run, ‘Save run → Room 1’
    Room 2 (biq side = E/W)  Q-Plus N/S vs biq E/W  → run, ‘Save run → Room 2’
  Set Q-Plus’s Extern seats to match the room (Config ▸ Players); for Room 2
  that’s INVERTED (N/S=Computer, E/W=Extern — the auto East-reset is skipped).
  ‘Compare rooms → IMP’ scores board-a-match: IMP(Room1_NS − Room2_NS) per
  board; positive net = biq AHEAD. Acceptance bar: biq ahead in all 4 cases
  {both SAYC, both Precision} × {random, slam-eligible}. Needs biq+biq mode.
  Optional baseline (R3) for the closed-room split: ‘Run 4-comp autoclicker’
  drives an all-Q-Plus run on the SAME deck with NO network log (it clicks the
  cycle button whenever the screen settles — set Q-Plus to all-Computer, load
  the deck, calibrate the watch region first). Export its .qss, ‘Export .qss →
  baseline’, and Compare then ALSO prints the N/S-side vs E/W-side edges so you
  can see which pair carries biq’s advantage (the baseline cancels from the
  total, so it only splits it — never shifts the verdict).

OPTIONS
  biq+biq (N+S Extern)   Run biq as BOTH North and South (partnership test).
        Set Q-Plus to N=Extern, S=Extern, E/W=Computer.
  Auto-run               When biq joins, auto deal board 1 + start clicker.
  Exit automatically     OFF (default): the run ends with Q-Plus still
        running; you press 'Export .qss' then 'Exit Q-Plus' by hand. ON:
        fully hands-off -- auto-export, aggregate, then exit (kill wine).
  NS sys / EW sys        Bidding system per side, independent:
        auto   = leave Q-Plus's default (biq follows N/S)
        random = a fresh random system for that side each deal
        <name> = a fixed system (SAYC / 2-1 / Acol / French / Precision).
        e.g. NS=Precision90M + EW=random.

RUN CONFIGURATION (top fields)
  Deals          how many boards to play.
  biq seat       seat biq plays when NOT in biq+biq mode.
  MC samples     Monte-Carlo samples per cardplay decision (higher=stronger,
        slower).
  Idle backstop  seconds of silence before the clicker fires a fallback click.
  Reset every    >64-deal runs: full Network reset every N deals to clear
        Q-Plus's 64-board scoring cap (needs the reset clicks calibrated).
  Sessions       back-to-back self-contained runs (kills wine between each).

SCORING: teams IMP from the .qss. Same deal at both tables (biq's N/S vs
Q-Plus's N/S), identical cards -- so card luck cancels; it's pure skill.
Health dots: server (:5555), biq (clients up), clicker (running).
"""
_SYS_NAMES = ["SAYC", "TwoOverOne", "StandardAcol", "StandardFrench",
              "Precision90M"]


def _xdotool(*args):
    try:
        return subprocess.run(["xdotool", *args], capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None


def _mouse_xy():
    r = _xdotool("getmouselocation", "--shell")
    if not r or r.returncode != 0:
        return None
    env = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
    return int(env["X"]), int(env["Y"])


def _click_xy(x, y):
    _xdotool("mousemove", str(x), str(y))
    _xdotool("click", "1")


def _minimize_bridge_dialog():
    """Click the calibrated minimise (_) button of Q-Plus's 'Local bridge
    server' dialog so it stops covering the menu bar — while it's up the
    Configuration menu (bidding-system set + East-reset) is unreachable.
    xdotool CANNOT find Q-Plus's Wine windows by name (search returns
    nothing), so this is a position click, not windowminimize. The server
    keeps running and biq stays connected. Returns True if it clicked."""
    xy = _load_server_btn("bridge_min")
    if xy:
        _click_xy(*xy)
        return True
    return False


def _menu_pick(top, item, gap="0.3"):
    """Open a top-level menu and pick an item from its dropdown in ONE
    chained xdotool call — move→click→sleep→move→click with nothing in
    between, so the menu can't close before the item is clicked. `top`
    and `item` are (x, y); returns False if either is missing."""
    if not (top and item):
        return False
    _xdotool("mousemove", str(top[0]), str(top[1]), "click", "1",
             "sleep", gap,
             "mousemove", str(item[0]), str(item[1]), "click", "1")
    return True


def _load_server_btn(key):
    try:
        return tuple(json.loads(SERVER_BTN_FILE.read_text())[key])
    except Exception:
        return None


def _load_closed_room():
    return _load_server_btn("closed_room")


def _biq_proc_count() -> int:
    """Count running biq clients by process (not QProcess handle): the
    autoclicker relaunches biq detached during unattended resets, so our
    QProcess handles go stale but the clients are still up."""
    try:
        r = subprocess.run(["pgrep", "-c", "-f", "biq[_]qnet_client"],
                           capture_output=True, text=True, timeout=2)
        return int((r.stdout or "0").strip() or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def _qplus_running() -> bool:
    """True if a Q-Plus (QBRIDGE.EXE) process is up — so we don't launch a
    second instance when one is already loading behind the splash."""
    try:
        r = subprocess.run(["pgrep", "-f", "QBRIDG[E]"],
                           capture_output=True, text=True, timeout=2)
        return bool((r.stdout or "").strip())
    except (OSError, subprocess.SubprocessError):
        return False


def _dismiss_qplus_splash(blind: bool = False) -> bool:
    """Press Ok/Return on Q-Plus's launch splash ('The activation is
    already done!'). Found by the '… - Login' title or Q-Plus's WM_CLASS
    (title-independent). Normally only a window whose title contains
    'login' is touched, so Return never hits the bridge-server Start/Cancel;
    with blind=True (the first few seconds, when only the splash can exist)
    any Q-Plus window is dismissed in case wine's WM_NAME lacks 'login'."""
    for args in (("--name", "Q-plus Bridge - Login"),
                 ("--class", "qbridge")):
        r = _xdotool("search", *args)
        if not r or r.returncode != 0:
            continue
        for wid in (r.stdout or "").split():
            nm = _xdotool("getwindowname", wid)
            name = (nm.stdout if nm else "") or ""
            if blind or "login" in name.lower():
                _xdotool("windowactivate", wid)
                _xdotool("key", "--clearmodifiers", "Return")
                return True
    return False


def _server_listening() -> bool:
    """True if something holds a LISTEN socket on :5555. Uses `ss`, NOT
    an actual connect — a real connect that the server doesn't accept
    lingers in Q-Plus's accept backlog, and a 1.5s health poll would
    slowly fill it and lock out the real client."""
    try:
        r = subprocess.run(["ss", "-tln"], capture_output=True,
                           text=True, timeout=2)
        return bool(re.search(rf":{SERVER_PORT}(?:\s|$)", r.stdout))
    except (OSError, subprocess.SubprocessError):
        return False


class Dot(QLabel):
    """A small coloured status dot with a label."""
    def __init__(self, name):
        super().__init__(f"● {name}")
        self.name = name
        self.set_state(False)

    def set_state(self, up: bool):
        colour = "#2e7d32" if up else "#9e9e9e"
        self.setStyleSheet(f"color:{colour}; font-weight:bold;")


class CalibrateDialog(QDialog):
    """Capture screen positions of Q-Plus buttons by countdown: click
    Capture, then move the mouse over the button before it hits 0."""
    # (label, storage-kind). 'cycle' -> CYCLE_BTN_FILE (shared with
    # qplus_button_loop.py); everything else -> SERVER_BTN_FILE (merged).
    # The network_menu/stop_item/start_item are needed for unattended
    # >64-deal runs (the every-N-deals Network stop/start that frees
    # Q-Plus's 64-board scoring buffer).
    TARGETS = [("‘Closed Room’ button (deal board 1)", "closed_room"),
               ("Lower-left cycle button (Next deal / play)", "cycle"),
               ("‘Stop’ button on the Local-bridge-server dialog",
                "stop_item"),
               ("‘Start’ button on the Local-bridge-server dialog",
                "start_item"),
               ("‘Network’ top-level menu (to start the bridge server)",
                "network_menu"),
               ("‘Start bridge server on this PC’ item in the Network menu "
                "(optional — skip if Start appears directly)", "net_start_item"),
               ("‘Configuration’ top-level menu (for East=Computer)",
                "cfg_menu"),
               ("‘Players’ item in the Configuration menu", "players_item"),
               ("Set East = Computer (control in the Players dialog)",
                "east_computer"),
               ("‘OK’ on the Players dialog", "players_ok")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibrate Q-Plus server buttons")
        self.resize(440, 200)
        v = QVBoxLayout(self)
        intro = QLabel("For each button: press Capture, then move the "
                       "mouse over that Q-Plus button before the 3s "
                       "countdown ends.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        g = QGridLayout()
        self.status = {}
        for row, (label, key) in enumerate(self.TARGETS):
            g.addWidget(QLabel(label), row, 0)
            b = QPushButton("Capture (3s)")
            b.clicked.connect(lambda _=False, k=key: self._capture(k))
            g.addWidget(b, row, 1)
            st = QLabel(self._current(key))
            self.status[key] = st
            g.addWidget(st, row, 2)
        v.addLayout(g)
        close = QPushButton("Done")
        close.clicked.connect(self.accept)
        v.addWidget(close)

    def _current(self, key):
        try:
            if key == "cycle":
                xy = tuple(json.loads(CYCLE_BTN_FILE.read_text())["button"])
            else:
                xy = tuple(json.loads(SERVER_BTN_FILE.read_text())[key])
        except Exception:
            xy = None
        return f"= {xy}" if xy else "= (not set)"

    def _capture(self, key):
        st = self.status[key]
        self._count = 3

        def tick():
            if self._count > 0:
                st.setText(f"… {self._count}")
                self._count -= 1
                QTimer.singleShot(1000, tick)
                return
            xy = _mouse_xy()
            if not xy:
                st.setText("xdotool failed")
                return
            if key == "cycle":
                CYCLE_BTN_FILE.write_text(
                    json.dumps({"button": list(xy), "window": 0}, indent=2))
            else:
                # merge into the server-buttons file so closed_room and the
                # network targets coexist
                try:
                    d = json.loads(SERVER_BTN_FILE.read_text())
                except Exception:
                    d = {}
                d[key] = list(xy)
                d.setdefault("window", 0)
                SERVER_BTN_FILE.write_text(json.dumps(d, indent=2))
            st.setText(f"= {xy} ✓")
        tick()


class CalibrationManagerDialog(QDialog):
    """Show and EDIT every calibrated click position the panel can use,
    across all its JSON files — including captures saved by earlier
    versions / sibling tools (shown as ‘extra’). Capture re-sets a
    position via a 3-second countdown: press Capture, then hover the
    target Q-Plus control before it hits 0. Q-Plus must be on-screen
    with the relevant menu/dialog open."""

    # (file, section title, [(key, label), ...]) — keys the panel uses.
    REGISTRY = [
        (SERVER_BTN_FILE, "Server / table / menus (start, players, export)", [
            ("closed_room", "Closed Room (deal board 1)"),
            ("network_menu", "Network — top-level menu"),
            ("net_start_item", "Start bridge server — menu item"),
            ("start_item", "Start — bridge-server dialog button"),
            ("stop_item", "Stop — bridge-server dialog button"),
            ("bridge_min", "Minimise (_) button of the bridge-server dialog "
                           "— frees the Configuration menu"),
            ("cfg_menu", "Configuration — top-level menu"),
            ("players_item", "Players — Configuration item"),
            ("east_computer", "East = Computer — Players dialog"),
            ("players_ok", "OK — Players dialog"),
            ("view_menu", "View — top-level menu"),
            ("view_scoring_table", "View Scoring Table — View item"),
            ("match_end", "‘View the scoring table’ — Match End dialog (pops "
                          "up after the last board; dismisses it AND opens the "
                          "scoring table, so the export skips the View menu)"),
            ("save_and_send", "Save and send — scoring table"),
            ("save_ok", "OK — after Save and send"),
        ]),
        (CYCLE_BTN_FILE, "Lower-left cycle button", [
            ("button", "Next deal / play"),
        ]),
        (TRANSITION_FILE, "Match-Control transition (reset-every runs)", [
            ("deal_menu", "Deal — top-level menu"),
            ("match_control", "Match Control — item"),
            ("minor_field", "Board-number field"),
            ("ok_button", "OK — Match Control"),
            ("deal_button", "Deal button"),
        ]),
        (SYS_CAL_FILE, "Bidding-system dialog (random/fixed systems)", [
            ("config_menu", "Configuration menu"),
            ("bidding_system_item", "Bidding system — item"),
            ("radio_american", "Radio: American"),
            ("radio_british", "Radio: British"),
            ("radio_french", "Radio: French"),
            ("radio_precision", "Radio: Precision"),
            ("list_SAYC", "List: SAYC"),
            ("list_TwoOverOne", "List: TwoOverOne"),
            ("list_StandardAcol", "List: StandardAcol"),
            ("list_StandardFrench", "List: StandardFrench"),
            ("list_Precision90M", "List: Precision90M"),
            ("set_ns_btn", "Set N/S button"),
            ("set_ew_btn", "Set E/W button"),
            ("close_btn", "Close button"),
        ]),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration manager — all click captures")
        self.resize(700, 780)
        outer = QVBoxLayout(self)
        intro = QLabel(
            "Every click position the panel can use. Press Capture, then move "
            "the mouse over that Q-Plus control before the 3-second countdown "
            "ends. Q-Plus must be on-screen with the relevant menu/dialog open. "
            "Rows marked ‘extra’ were captured by an earlier version or a "
            "sibling tool.")
        intro.setWordWrap(True)
        outer.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        g = QGridLayout(inner)
        self._labels = {}            # (file_str, key) -> value QLabel
        row = 0
        seen = set()
        for path, title, items in self.REGISTRY:
            hdr = QLabel(f"▸ {title}")
            hdr.setStyleSheet("font-weight:bold; margin-top:10px;")
            g.addWidget(hdr, row, 0, 1, 3); row += 1
            fn = QLabel(str(path))
            fn.setStyleSheet("color:#888;")
            g.addWidget(fn, row, 0, 1, 3); row += 1
            data = self._read(path)
            for key, label in items:
                seen.add((str(path), key))
                row = self._add_row(g, row, path, key, label, data.get(key))
            for key, val in data.items():
                if (key == "window" or (str(path), key) in seen
                        or not (isinstance(val, list) and len(val) == 2)):
                    continue
                seen.add((str(path), key))
                row = self._add_row(g, row, path, key, f"{key}  (extra)", val)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        outer.addWidget(done)

    def _read(self, path):
        try:
            return json.loads(Path(path).read_text())
        except Exception:
            return {}

    def _fmt(self, val):
        if isinstance(val, list) and len(val) == 2:
            return f"= ({val[0]}, {val[1]})"
        return "(not set)"

    def _add_row(self, g, row, path, key, label, val):
        g.addWidget(QLabel(label), row, 0)
        vlab = QLabel(self._fmt(val))
        self._labels[(str(path), key)] = vlab
        g.addWidget(vlab, row, 1)
        b = QPushButton("Capture (5s)")
        b.clicked.connect(lambda _=False, p=path, k=key: self._capture(p, k))
        g.addWidget(b, row, 2)
        return row + 1

    def _expected_x_range(self):
        """The X span of already-calibrated server/transition points — the
        Q-Plus window. Used to flag a capture that lands far outside it (the
        classic 'I captured the calibration dialog, not the menu item')."""
        xs = []
        for path in (SERVER_BTN_FILE, TRANSITION_FILE):
            for k, v in self._read(path).items():
                if k != "window" and isinstance(v, list) and len(v) == 2:
                    xs.append(v[0])
        return (min(xs), max(xs)) if xs else None

    def _capture(self, path, key):
        vlab = self._labels[(str(path), key)]
        self._cd = 6            # menu/dialog items need time to open + hover

        def tick():
            if self._cd > 0:
                # Live read-out: show WHERE the mouse is each second so you
                # can confirm it's on the dropdown item / dialog button before
                # the capture fires. Captures wherever the mouse is at 0.
                here = _mouse_xy()
                vlab.setText(f"… {self._cd}  mouse at {here}")
                self._cd -= 1
                QTimer.singleShot(1000, tick)
                return
            xy = _mouse_xy()
            if not xy:
                vlab.setText("xdotool failed")
                return
            # Sanity warning: a point far off the Q-Plus window's X range is
            # almost always a miscapture (mouse left on the dialog).
            rng = self._expected_x_range()
            warn = ""
            if rng and (xy[0] < rng[0] - 300 or xy[0] > rng[1] + 300):
                warn = ("  ⚠ off Q-Plus window (X≈{}–{}) — likely the dialog, "
                        "not the target".format(rng[0], rng[1]))
            d = self._read(path)
            d[key] = [xy[0], xy[1]]
            d.setdefault("window", 0)
            try:
                Path(path).write_text(json.dumps(d, indent=2))
                vlab.setText(self._fmt([xy[0], xy[1]]) + " ✓" + warn)
            except OSError as e:
                vlab.setText(f"write failed: {e}")
        tick()


class CalibrationOverlay(QWidget):
    """A translucent full-screen overlay that draws a labeled crosshair at
    every calibrated click position in a group, so you can eyeball — against
    the live Q-Plus window showing through — whether any are off. Click or
    press any key to dismiss."""

    def __init__(self, title, points):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._title = title
        self._points = points       # [(label, x, y), …] in global coords
        geo = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 70))      # dim, see-through
        p.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        for label, gx, gy in self._points:
            pt = self.mapFromGlobal(QPoint(int(gx), int(gy)))
            x, y = pt.x(), pt.y()
            p.setPen(QPen(QColor(255, 70, 70), 2))
            p.setBrush(QColor(255, 70, 70, 110))
            p.drawEllipse(QPoint(x, y), 9, 9)
            p.drawLine(x - 18, y, x + 18, y)
            p.drawLine(x, y - 18, x, y + 18)
            p.setPen(QColor(255, 255, 0))
            p.drawText(x + 14, y - 6, f"{label}  ({gx},{gy})")
        p.setPen(QColor(255, 255, 255))
        p.setFont(QFont("sans-serif", 15, QFont.Weight.Bold))
        p.drawText(24, 36, f"{self._title}  —  {len(self._points)} points  "
                           "·  click or press any key to close")

    def mousePressEvent(self, _e):
        self.close()

    def keyPressEvent(self, _e):
        self.close()


class LiveMatchWidget(QWidget):
    """The end-to-end biq-vs-Q-Plus match panel, as a reusable widget so
    it can stand alone OR be folded in as a tab of the corpus GUI."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proxy = self.biq = self.biq2 = self.clicker = self._oneshot = None
        self.deals_total = 50
        self._match_started = False
        # session-loop state (for unattended back-to-back 64-deal runs)
        self._loop_active = False
        self._session_total = 1
        self._session_idx = 1
        self._session_logs = []
        self._session_qss = []
        self._await_session_end = False   # guards export-on-exit vs manual stop
        self._board1_dealt = True   # set False only by the auto flow (deal-1 gate)
        # startup stepper (debugger-style): run the procedure one discrete
        # step at a time, or hand control to autopilot. _step_idx = index of
        # the last step STARTED (-1 = none); _step_running while one is in
        # flight (incl. async waits); _autopilot auto-advances on completion.
        self._step_idx = -1
        self._step_running = False
        self._autopilot = False
        self._await_biq_join = False
        # True once the user drives the stepper (Step/Autopilot). It locks
        # OUT the legacy one-click auto-deal chain (_auto_deal_and_run), so a
        # second biq-client join can't kick off set-systems→East→deal→clicker
        # behind the stepper's back. Reset by the one-click / numbered paths.
        self._stepper_mode = False
        # Deal-set guard for the live A/B: (seed, start_board) of the current
        # run's FIRST deal, and the locked Run-A reference to check against.
        self._this_run = None
        self._this_run_seen = False
        self._ab_ref = self._load_ab_ref()
        self._ab_mode = None          # None | "A" | "B"
        self._build_ui()
        self._append(f"[panel] build {PANEL_BUILD}")
        self._append("[panel] Step runs ONE step then stops; the legacy "
                     "auto-deal chain is locked out once you start stepping.")
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_health)
        self._tick.start(1500)
        app = QApplication.instance()
        if app is not None:  # kill our subprocesses when the app quits
            app.aboutToQuit.connect(lambda: self.stop_all(silent=True))

    # ---------- UI ----------
    def _build_ui(self):
        # Two-panel landscape: controls (1·2·3·4) on the left, live deal
        # names + result + log on the right.
        outer = QHBoxLayout(self)
        root = QVBoxLayout()          # LEFT column — the controls
        rightcol = QVBoxLayout()      # RIGHT column — deals / result / log
        outer.addLayout(root)
        outer.addLayout(rightcol, 1)  # the output side takes the extra width
        self._build_config_dialog()

        # ===== 1 ▏ Bidding systems =====
        sys_box = QGroupBox("1 ▏ Bidding systems")
        sh = QHBoxLayout(sys_box)
        _SYS_OPTS = ["sequential", "random"] + _SYS_NAMES
        self.ns_sys = QComboBox(); self.ns_sys.addItems(_SYS_OPTS)
        self.ew_sys = QComboBox(); self.ew_sys.addItems(_SYS_OPTS)
        self.ns_sys.setCurrentText("SAYC")
        self.ew_sys.setCurrentText("SAYC")
        _systip = ("sequential = step the 5 systems by deal number "
                   "(1 2 3 4 5 1 2 3 4 5 …) — repeatable with NO seed, so the "
                   "SAME boards get the SAME systems every run (the clean A/B "
                   "basis). When BOTH sides are sequential the pair sweeps as "
                   "an odometer: N/S holds while E/W runs 1-5, then N/S steps "
                   "(all 25 pairings).  random = a fresh random system each "
                   "deal.  Or pick one fixed system for the whole run. N/S and "
                   "E/W independent. Frozen during an A/B so both runs match.")
        self.ns_sys.setToolTip(_systip)
        self.ew_sys.setToolTip(_systip)
        sh.addWidget(QLabel("N/S")); sh.addWidget(self.ns_sys)
        sh.addSpacing(18)
        sh.addWidget(QLabel("E/W")); sh.addWidget(self.ew_sys)
        sh.addStretch(1)
        self.repro_random = QCheckBox("🔒 reproducible random")
        self.repro_random.setToolTip(
            "Only affects the 'random' mode: seed the per-deal choice so Run "
            "A and Run B draw the SAME random systems on the same boards. "
            "'sequential' is already repeatable with no seed, so leave this "
            "unticked when using it.")
        sh.addWidget(self.repro_random)
        root.addWidget(sys_box)

        # ===== 2 ▏ A/B test =====
        ab_box = QGroupBox("2 ▏ A/B test  (swaps the bidder + guards the deals)")
        abv = QVBoxLayout(ab_box)
        abtop = QHBoxLayout()
        abtop.addWidget(QLabel("Mode:"))
        self.ab_combo = QComboBox()
        self.ab_combo.addItems(["Off (single run)",
                                "Run A — baseline (pre-fix)",
                                "Run B — candidate (with fixes)"])
        self.ab_combo.setToolTip(
            "Run A loads the baseline bidder and auto-locks this run's "
            "deal-set as the reference. Run B loads the candidate bidder and "
            "checks deal 1 against that reference — and if you didn't label "
            "the previous run 'Run A', it infers the reference from the last "
            "run's log automatically. Off = a normal single run. While A or B "
            "is selected the system dropdowns are frozen so both runs match.")
        abtop.addWidget(self.ab_combo, 1)
        self.lbl_bidder = QLabel("bidder: —")
        self.lbl_bidder.setStyleSheet("font-weight:bold;")
        abtop.addWidget(self.lbl_bidder)
        self.b_clearref = QPushButton("✕ clear ref")
        self.b_clearref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_clearref.setToolTip("Forget the locked Run-A reference.")
        abtop.addWidget(self.b_clearref)
        abv.addLayout(abtop)
        abrow = QHBoxLayout()
        self.lbl_thisrun = QLabel("This run: —")
        self.lbl_thisrun.setStyleSheet("font-weight:bold;")
        self.lbl_abref = QLabel()
        abrow.addWidget(self.lbl_thisrun)
        abrow.addSpacing(16)
        abrow.addWidget(self.lbl_abref)
        abrow.addStretch(1)
        abv.addLayout(abrow)
        root.addWidget(ab_box)

        # ===== 2b ▏ Double-pair validation (board-a-match) =====
        dp_box = QGroupBox("2b ▏ Double-pair validation  (biq vs Q-Plus, "
                           "cards swapped → board-a-match)")
        dpv = QVBoxLayout(dp_box)
        dptop = QHBoxLayout()
        dptop.addWidget(QLabel("biq side:"))
        self.dp_side = QComboBox()
        self.dp_side.addItems(["N/S  (Room 1)", "E/W  (Room 2)"])
        self.dp_side.setToolTip(
            "Which side biq sits for THIS run. Play the SAME deck twice:\n"
            "  Room 1 — biq N/S vs Q-Plus E/W   (Q-Plus: N/S=Extern, E/W=Computer)\n"
            "  Room 2 — biq E/W vs Q-Plus N/S   (Q-Plus: E/W=Extern, N/S=Computer)\n"
            "biq holds both pairs over the two rooms, so card luck cancels — "
            "the unbiased teams test. Requires biq+biq (pair) mode.")
        dptop.addWidget(self.dp_side, 1)
        self.b_dp_save = QPushButton("Save run → Room 1")
        self.b_dp_save.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_dp_save.setToolTip(
            "Copy this run's biq log to the Room-1/Room-2 slot for the "
            "board-a-match compare. Do it after each room's run finishes.")
        dptop.addWidget(self.b_dp_save)
        self.b_dp_cmp = QPushButton("Compare rooms → IMP")
        self.b_dp_cmp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_dp_cmp.setToolTip(
            "Board-a-match: IMP = imp(Room1_NS − Room2_NS) per board. "
            "Positive net = biq AHEAD. Run after both rooms are saved.")
        dptop.addWidget(self.b_dp_cmp)
        dpv.addLayout(dptop)
        # Baseline row — the all-Q-Plus run (R3) for the closed-room split.
        dpbot = QHBoxLayout()
        dpbot.addWidget(QLabel("Baseline (all-Q-Plus, R3):"))
        self.b_dp_4cc = QPushButton("Run 4-comp autoclicker")
        self.b_dp_4cc.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_dp_4cc.setToolTip(
            "Drive a 4-computer Q-Plus run with NO network log: clicks the "
            "cycle button whenever the screen settles (idle-detection). Set "
            "Q-Plus to all-Computer + load the SAME deck first; calibrate the "
            "watch region once (Calibrate ▸ region). This is the optional R3 "
            "baseline that splits the result into N/S-edge vs E/W-edge.")
        dpbot.addWidget(self.b_dp_4cc)
        self.b_dp_savebase = QPushButton("Export .qss → baseline")
        self.b_dp_savebase.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_dp_savebase.setToolTip(
            "After the 4-computer run, Export the .qss, then click this to "
            "stash it as the baseline. ‘Compare rooms’ then also prints the "
            "N/S-side and E/W-side decomposition.")
        dpbot.addWidget(self.b_dp_savebase)
        dpbot.addStretch(1)
        dpv.addLayout(dpbot)
        self.b_dp_4cc.clicked.connect(self._dp_run_4computer)
        self.b_dp_savebase.clicked.connect(self._dp_save_baseline)
        self.lbl_dp = QLabel(
            "Validate biq ahead in all 4 cases: {both SAYC, both Precision} × "
            "{random, slam-eligible}.  Set systems (1), pick a side, run the "
            "deck; repeat with the other side on the SAME deck; Compare.")
        self.lbl_dp.setWordWrap(True)
        self.lbl_dp.setStyleSheet("color:#555;")
        dpv.addWidget(self.lbl_dp)
        self.dp_side.currentIndexChanged.connect(self._on_dp_side_changed)
        self.b_dp_save.clicked.connect(self._dp_save_room)
        self.b_dp_cmp.clicked.connect(self._dp_compare)
        root.addWidget(dp_box)

        # ===== 3 ▏ Startup procedure (Step / Autopilot) =====
        steps_box = QGroupBox("3 ▏ Startup procedure — Step (one move) or "
                              "Autopilot")
        sbx = QVBoxLayout(steps_box)
        self.step_list = QListWidget()
        self.step_list.setFixedHeight(168)
        self.step_list.setFont(QFont("monospace"))
        self.step_list.setToolTip(
            "Each step = one series of clicks. Step runs the next and stops "
            "so you can watch the log and fix anything out of order; "
            "Autopilot runs the rest. A failed step is retried by the next "
            "Step. Reset moves the pointer back (doesn't undo Q-Plus state).")
        self._steps = self._build_steps()
        for i, (_key, label, _fn) in enumerate(self._steps):
            QListWidgetItem(f"  •  {i + 1}. {label}", self.step_list)
        sbx.addWidget(self.step_list)
        sbtn = QHBoxLayout()
        self.b_step = QPushButton("Step ▷")
        self.b_step.setStyleSheet("font-weight:bold; padding:4px 10px;")
        self.b_step.setToolTip("Run the next startup step, then stop and wait.")
        self.b_auto = QPushButton("Autopilot ▶")
        self.b_auto.setCheckable(True)
        self.b_auto.setToolTip("Run all remaining steps back-to-back "
                               "(asks first).")
        self.b_steps_reset = QPushButton("⏮ Reset steps")
        self.b_auto.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_steps_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for b in (self.b_step, self.b_auto, self.b_steps_reset):
            sbtn.addWidget(b)
        sbtn.addStretch(1)
        sbx.addLayout(sbtn)
        root.addWidget(steps_box)

        # ===== 4 ▏ Run / export / exit =====
        act_box = QGroupBox("4 ▏ Run / export / exit")
        actl = QHBoxLayout(act_box)
        self.b_full = QPushButton("▶ Run full session")
        self.b_full.setToolTip(
            "Launch Q-Plus, start biq, deal, run the autoclicker and "
            "aggregate — all hands-off (no stepping). Sessions>1 loops, "
            "killing wine between. Don't touch the mouse while it runs.")
        self.b_export = QPushButton("Export .qss")
        self.b_export.setToolTip(
            "View ▸ Scoring Table ▸ Save and send ▸ OK in Q-Plus, then "
            "aggregate from the new .qss.")
        self.b_killwine = QPushButton("⏻ Exit Q-Plus (kill wine)")
        self.b_killwine.setToolTip(
            "Force-quit Q-Plus + all wine; clears the :5555 socket and the "
            "64-board cap. Export the .qss FIRST.")
        self.b_stop = QPushButton("Stop all")
        self.b_stop.setToolTip("Stop biq + the autoclicker (Q-Plus stays up).")
        for b in (self.b_full, self.b_export, self.b_killwine, self.b_stop):
            actl.addWidget(b)
        actl.addStretch(1)
        self.b_stop.setEnabled(False)
        root.addWidget(act_box)

        # ===== status + hint + progress + result + log =====
        mid = QHBoxLayout()
        self.dots = {n: Dot(n) for n in ("server", "biq", "clicker")}
        for d in self.dots.values():
            mid.addWidget(d)
        mid.addStretch(1)
        root.addLayout(mid)

        self.hint = QLabel("Set systems (1), pick A/B mode (2), Step through "
                           "the startup (3), export when done (4). Config & "
                           "Calibrate are in the menu bar.")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#555;")
        root.addWidget(self.hint)

        self.bar = QProgressBar()
        self.bar.setRange(0, 50)
        self.bar.setFormat("Deal %v / %m")
        root.addWidget(self.bar)
        root.addStretch(1)            # keep the controls top-packed

        # ===== RIGHT column: live deal names + result + log =====
        dealsbox = QGroupBox("Deals dealt  (name · dealer/vul)")
        dv = QVBoxLayout(dealsbox)
        self.deals_list = QListWidget()
        self.deals_list.setFont(QFont("monospace"))
        self.deals_list.setToolTip(
            "Each deal's NAME as Q-Plus deals it. 'SLAM-001' etc. = your "
            "loaded Own-deals deck; '4210-NN' = Q-Plus's own seed. Lets you "
            "see at a glance which deal source is actually live.")
        dv.addWidget(self.deals_list)
        rightcol.addWidget(dealsbox, 2)

        res = QGroupBox("Result — teams IMP vs Q-Plus (live report_score)")
        rl = QVBoxLayout(res)
        self.result = QPlainTextEdit(); self.result.setReadOnly(True)
        self.result.setMaximumBlockCount(2000)
        self.result.setFont(QFont("monospace"))
        self.result.setFixedHeight(110)
        rl.addWidget(self.result)
        rightcol.addWidget(res)

        logbox = QGroupBox("Log (biq + autoclicker + panel)")
        ll = QVBoxLayout(logbox)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        self.log.setFont(QFont("monospace"))
        ll.addWidget(self.log)
        rightcol.addWidget(logbox, 3)

        # ----- connections (main-screen widgets) -----
        self.ab_combo.currentIndexChanged.connect(self._on_ab_mode_changed)
        self.b_clearref.clicked.connect(self._clear_ab_ref)
        self.b_step.clicked.connect(self._on_step_clicked)
        self.b_auto.toggled.connect(self._on_autopilot_toggled)
        self.b_steps_reset.clicked.connect(self._steps_reset)
        self.b_full.clicked.connect(self.run_full_session)
        self.b_export.clicked.connect(self._export_and_aggregate)
        self.b_killwine.clicked.connect(
            lambda: self.kill_all_wine(confirm=True))
        self.b_stop.clicked.connect(self.stop_all)
        self._update_bidder_indicator()
        self._refresh_ab_ref_label()

    def _build_config_dialog(self):
        """Run settings + options + advanced/manual controls, in a dialog
        opened from the Config menu. Widgets stay as attributes so the run
        code keeps reading self.deals.value(), self.pair.isChecked(), etc."""
        self.config_dialog = QDialog(self)
        self.config_dialog.setWindowTitle("Config — run settings & options")
        dl = QVBoxLayout(self.config_dialog)

        cfg = QGroupBox("Run configuration")
        g = QGridLayout(cfg)
        self.deals = QSpinBox(); self.deals.setRange(1, 1000)
        self.deals.setValue(64)
        self.seat = QComboBox(); self.seat.addItems(["S", "N", "E", "W"])
        self.samples = QSpinBox(); self.samples.setRange(5, 300)
        self.samples.setValue(50)    # 50 balances finesse accuracy vs the
        #                              libdds crash rate (120 caused ~45
        #                              crashes/64-board run → weak fallbacks)
        self.idle = QSpinBox(); self.idle.setRange(3, 60); self.idle.setValue(10)
        self.reset_every = QSpinBox(); self.reset_every.setRange(0, 64)
        self.reset_every.setValue(0)
        self.reset_every.setToolTip(
            "Unattended runs >64 deals: every N deals do a Network "
            "stop/start + biq relaunch + Match Control. 0 = single ≤64 "
            "session (no reset). Needs the Network + transition calibrated.")
        self.sessions = QSpinBox(); self.sessions.setRange(1, 50)
        self.sessions.setValue(1)
        self.sessions.setToolTip(
            "Back-to-back self-contained sessions for hands-off runs; kills "
            "wine between each. Use with ▶ Run full session.")
        for col, (lab, w) in enumerate([
                ("Deals", self.deals), ("biq seat", self.seat),
                ("MC samples", self.samples), ("Idle backstop (s)", self.idle),
                ("Reset every", self.reset_every),
                ("Sessions", self.sessions)]):
            g.addWidget(QLabel(lab), 0, col)
            g.addWidget(w, 1, col)
        dl.addWidget(cfg)

        opt = QGroupBox("Options")
        ov = QVBoxLayout(opt)
        self.pair = QCheckBox("biq+biq (N+S Extern)")
        self.pair.setChecked(True)
        self.pair.setToolTip(
            "Run two biq clients as partners (N+S). Set Q-Plus to N=Extern, "
            "S=Extern, E/W=Computer.")
        self.auto = QCheckBox("Auto-run (deal + click when biq joins)")
        self.auto.setChecked(True)
        self.exit_auto = QCheckBox(
            "Exit automatically (auto-export + kill wine at end)")
        self.exit_auto.setChecked(False)
        self.exit_auto.setToolTip(
            "OFF (default): the run ends with Q-Plus running; you Export then "
            "Exit by hand. ON: fully hands-off — auto-export, aggregate, then "
            "kill wine.")
        for w in (self.pair, self.auto, self.exit_auto):
            ov.addWidget(w)
        dl.addWidget(opt)
        self.pair.toggled.connect(lambda on: self.seat.setEnabled(not on))

        util = QGroupBox("Utilities")
        uv = QHBoxLayout(util)
        self.b_launch = QPushButton("Launch Q-Plus server")
        self.b_reset = QPushButton("New run (reset logs)")
        self.b_agg = QPushButton("Aggregate (.qss)")
        for b in (self.b_launch, self.b_reset, self.b_agg):
            uv.addWidget(b)
        uv.addStretch(1)
        dl.addWidget(util)

        adv = QGroupBox("Manual startup steps (advanced — the stepper does "
                        "these)")
        av = QHBoxLayout(adv)
        self.b_start = QPushButton("1 ▸ Start server+biq")
        self.b_deal = QPushButton("2 ▸ Deal board 1 (Closed Room)")
        self.b_run = QPushButton("3 ▸ Run autoclicker")
        for b in (self.b_start, self.b_deal, self.b_run):
            av.addWidget(b)
        self.b_deal.setEnabled(False)
        self.b_run.setEnabled(False)
        dl.addWidget(adv)

        row = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.config_dialog.hide)
        row.addStretch(1); row.addWidget(close)
        dl.addLayout(row)

        self.b_launch.clicked.connect(lambda: self.launch_qplus())
        self.b_reset.clicked.connect(self.new_run)
        self.b_agg.clicked.connect(self.aggregate_qss)
        self.b_start.clicked.connect(self.manual_start)
        self.b_deal.clicked.connect(self.deal_first_board)
        self.b_run.clicked.connect(self.start_clicker)

    def show_config_dialog(self):
        self.config_dialog.show()
        self.config_dialog.raise_()
        self.config_dialog.activateWindow()

    def show_deck_dialog(self):
        """Dialog to generate a curated BDE test deck (slam-eligible /
        definite-slam / grand-slam / random) into Q-Plus's OWN-DEALS dir."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Generate test deck (BDE)")
        v = QVBoxLayout(dlg)
        lab = QLabel(
            "Make a FIXED deck of curated deals for Q-Plus to play (File ▸ "
            "Open Own deals). Both Run A and Run B draw the same deals from "
            "the file — so you can A/B specifically on, e.g., slams.")
        lab.setWordWrap(True)
        v.addWidget(lab)
        row = QHBoxLayout()
        kind = QComboBox()
        kind.addItems(["slam-eligible", "definite-slam", "grand-slam",
                       "random"])
        cnt = QSpinBox(); cnt.setRange(1, 128); cnt.setValue(64)
        row.addWidget(QLabel("Kind:")); row.addWidget(kind, 1)
        row.addWidget(QLabel("Count:")); row.addWidget(cnt)
        v.addLayout(row)
        row2 = QHBoxLayout()
        gen = QPushButton("Generate")
        gen.setStyleSheet("font-weight:bold;")
        close = QPushButton("Close")
        row2.addStretch(1); row2.addWidget(gen); row2.addWidget(close)
        v.addLayout(row2)

        def do_gen():
            self._deck = self._mk_proc("deck")
            self._deck.setArguments(
                ["-u", "tools/gen_test_deck.py", "--kind", kind.currentText(),
                 "--count", str(cnt.value()), "--seed", "1"])
            self._deck.finished.connect(
                lambda *_a: self._append("[deck] done — load the .BDE in "
                                         "Q-Plus via File ▸ Open Own deals"))
            self._deck.start()
            self._append(f"[deck] generating {cnt.value()} "
                         f"{kind.currentText()} deals (DD-filtered, may take a "
                         "few seconds)…")
        gen.clicked.connect(do_gen)
        close.clicked.connect(dlg.hide)
        dlg.show()

    def _append(self, text):
        text = text.rstrip()
        self.log.appendPlainText(text)
        # Persist to a file so a run's actions can be examined afterwards
        # (the in-memory widget is lost when the panel closes).
        try:
            with open(PANEL_LOG, "a") as f:
                f.write(time.strftime("%H:%M:%S ") + text + "\n")
        except OSError:
            pass

    # ---------- deal-set guard (live A/B same-boards check) ----------
    def _load_ab_ref(self):
        try:
            d = json.loads(AB_REF_FILE.read_text())
            return (str(d["seed"]), int(d["start"]))
        except Exception:
            return None

    def _save_ab_ref(self, seed, start):
        try:
            AB_REF_FILE.parent.mkdir(parents=True, exist_ok=True)
            AB_REF_FILE.write_text(json.dumps({"seed": seed, "start": start}))
        except OSError:
            pass

    def _infer_ab_ref_from_last_run(self):
        """Recover the (seed, start_board) of the most recent run from its biq
        log, so Run B can lock onto the previous run even when it wasn't
        explicitly labelled 'Run A'. Checks the live biq logs, then the newest
        saved run log; returns the first that carries a new_deal, else None."""
        cands = [BIQ_N_LOG, BIQ_E_LOG, BIQ_LOG]
        try:
            cands += sorted((BIQ_ROOT / "tools/runs/ab").glob("run_*.log"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            pass
        for p in cands:
            try:
                txt = Path(p).read_text(errors="replace")
            except OSError:
                continue
            m = re.search(r'new_deal_pbn"?\s*\[[NESW]\s+(\d+)\s+(\d+)\]', txt)
            if m:
                return (str(m.group(2)), int(m.group(1)))
        return None

    def _refresh_ab_ref_label(self):
        if not hasattr(self, "lbl_abref"):
            return
        if self._ab_ref:
            self.lbl_abref.setText(
                f"Run-A ref: seed {self._ab_ref[0]} / start board "
                f"{self._ab_ref[1]}")
            self.lbl_abref.setStyleSheet("color:#06c;")
        else:
            self.lbl_abref.setText("Run-A ref: none yet "
                                   "(set on the first run, or inferred for B)")
            self.lbl_abref.setStyleSheet("color:#888;")

    def _clear_ab_ref(self):
        self._ab_ref = None
        try:
            AB_REF_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        self._refresh_ab_ref_label()
        self._append("[panel] cleared the Run-A reference")

    # ---------- A/B test selector (bidder swap + mode) ----------
    def _detect_bidder(self):
        """Ask ab_bidder.sh which version is in the working tree. Parse ONLY
        the 'now loaded :' line — the rest of the output names both words in
        its proof text, so a whole-output scan always false-matches."""
        try:
            out = subprocess.run(
                ["bash", str(BIQ_ROOT / "tools/ab_bidder.sh"), "status"],
                cwd=str(BIQ_ROOT), capture_output=True, text=True, timeout=15)
            for line in out.stdout.splitlines():
                if "now loaded" in line:
                    if "candidate" in line:
                        return "candidate"
                    if "baseline" in line:
                        return "baseline"
                    return "?"
        except Exception:
            pass
        return "?"

    def _update_bidder_indicator(self, loaded=None):
        if not hasattr(self, "lbl_bidder"):
            return
        if loaded is None:
            loaded = self._detect_bidder()
        if loaded == "baseline":              # A = blue
            self.lbl_bidder.setText("bidder: ●A baseline")
            self.lbl_bidder.setStyleSheet("font-weight:bold; color:#06c;")
        elif loaded == "candidate":           # B = orange
            self.lbl_bidder.setText("bidder: ●B candidate")
            self.lbl_bidder.setStyleSheet("font-weight:bold; color:#e60;")
        else:
            self.lbl_bidder.setText("bidder: ? (not baseline/candidate)")
            self.lbl_bidder.setStyleSheet("font-weight:bold; color:#888;")

    def _set_ab_bidder(self, which):
        """Swap the working-tree bidder via ab_bidder.sh (which ∈
        baseline|candidate). Returns the resulting loaded version."""
        try:
            out = subprocess.run(
                ["bash", str(BIQ_ROOT / "tools/ab_bidder.sh"), which],
                cwd=str(BIQ_ROOT), capture_output=True, text=True, timeout=20)
            first = (out.stdout.strip().splitlines() or ["(no output)"])[0]
            self._append(f"[ab] {first}")
        except Exception as e:
            self._append(f"[ab] bidder swap failed: {e}")
            QMessageBox.warning(self, "Bidder swap failed", str(e))
        return self._detect_bidder()

    def show_calibration_overlay(self, group):
        """Draw labeled crosshairs at every calibrated point in a group, over
        the live screen, so you can spot any that are off."""
        groups = {
            "server": (SERVER_BTN_FILE,
                       "Server buttons + Closed Room + bridge_min"),
            "systems": (Path.home() / ".qplus_mixed_corpus.json",
                        "Bidding-system dialog"),
            "transition": (Path.home() / ".qplus_transition.json",
                           "Match Control transition"),
        }
        path, title = groups[group]
        try:
            d = json.loads(Path(path).read_text())
        except Exception as e:
            QMessageBox.warning(self, "No calibration",
                                f"Couldn't read {path}:\n{e}")
            return
        pts = [(k, v[0], v[1]) for k, v in d.items()
               if isinstance(v, list) and len(v) == 2
               and all(isinstance(n, (int, float)) for n in v)]
        if not pts:
            QMessageBox.information(self, "No points",
                                    f"No calibrated click points in {path}.")
            return
        self._overlay = CalibrationOverlay(title, pts)
        self._overlay.show()
        self._append(f"[calib] overlay: {len(pts)} points from "
                     f"{Path(path).name} — click/key to close")

    def _sys_seed_args(self):
        """['--system-seed', N] when 'reproducible random' is ticked, else []."""
        if getattr(self, "repro_random", None) and self.repro_random.isChecked():
            return ["--system-seed", str(REPRO_SYS_SEED)]
        return []

    def _set_systems_locked(self, locked):
        """Freeze the bidding-system dropdowns during an A/B pair so both
        runs use identical systems (the SAYC/SAYC trap)."""
        for w in (self.ns_sys, self.ew_sys):
            w.setEnabled(not locked)
        tip = " (frozen during A/B — both runs must use the same systems)"
        self.ns_sys.setToolTip((self.ns_sys.toolTip().split(" (frozen")[0])
                               + (tip if locked else ""))

    def _on_ab_mode_changed(self, _idx):
        t = self.ab_combo.currentText()
        if t.startswith("Run A"):
            self._ab_mode = "A"
            self._update_bidder_indicator(self._set_ab_bidder("baseline"))
            self._set_systems_locked(True)
            self._append("[ab] Run A — baseline bidder; this run's deal-set "
                         "will be AUTO-LOCKED as the reference on deal 1.")
        elif t.startswith("Run B"):
            self._ab_mode = "B"
            self._update_bidder_indicator(self._set_ab_bidder("candidate"))
            self._set_systems_locked(True)
            # Smart: if no reference is set, recover it from the saved file,
            # else infer it from the last run's log — so you can run B without
            # having explicitly labelled the previous run 'Run A'.
            if self._ab_ref is None:
                ref = self._load_ab_ref() or self._infer_ab_ref_from_last_run()
                if ref:
                    self._ab_ref = ref
                    self._save_ab_ref(ref[0], ref[1])
                    self._refresh_ab_ref_label()
                    self._append(
                        f"[ab] Run B — inferred the reference from the last "
                        f"run: seed {ref[0]}, start board {ref[1]}. Set Q-Plus "
                        f"Match Control major={ref[0]}, minor={ref[1]} to "
                        f"replay the same deals.")
            if self._ab_ref is None:
                QMessageBox.information(
                    self, "No previous run to compare against",
                    "Run B replays the previous run's deals and diffs them — "
                    "but I couldn't find a previous run to lock onto (no saved "
                    "reference, and no readable last-run log).\n\n"
                    "Just play a deck once first: any completed run is captured "
                    "automatically as the reference — you don't have to label "
                    "it 'Run A'.")
            else:
                self._append(
                    f"[ab] Run B — candidate bidder; guard armed against "
                    f"seed {self._ab_ref[0]} / start board {self._ab_ref[1]}.")
        else:
            self._ab_mode = None
            self._set_systems_locked(False)
            self._append("[ab] A/B off — single run (bidder left as-is).")

    def _on_first_deal(self, seed, start):
        """First new_deal of a run. In Run-A mode auto-lock the reference; in
        Run-B mode check deal 1 against it and warn IMMEDIATELY on mismatch."""
        self._this_run = (str(seed), int(start))
        self.lbl_thisrun.setText(f"This run: seed {seed} / start board {start}")
        if self._ab_mode == "A":
            self._ab_ref = (str(seed), int(start))
            self._save_ab_ref(str(seed), int(start))
            self._refresh_ab_ref_label()
            self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#06c;")
            self._append(f"[ab] ●A Run-A reference auto-locked: seed {seed}, "
                         f"start board {start}. For Run B set Q-Plus Match "
                         f"Control major={seed}, minor(start board)={start}.")
            return
        if self._ab_mode == "B" and self._ab_ref is not None:
            ref_seed, ref_start = self._ab_ref
            if str(seed) == str(ref_seed) and int(start) == int(ref_start):
                self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#0a0;")
                self._append(f"[ab] ✓ Run B deals MATCH Run A (seed {seed}, "
                             f"board {start}) — A/B valid, play it out.")
            else:
                self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#c00;")
                self._append(f"[ab] ⚠ MISMATCH: Run B seed {seed}/board {start}"
                             f" vs Run A {ref_seed}/{ref_start}")
                QMessageBox.warning(
                    self, "⚠ Run B deals don't match Run A",
                    "Run B is dealing a DIFFERENT set / start board than Run "
                    "A — the A/B would be invalid.\n\n"
                    f"    Run A:    seed {ref_seed}, start board {ref_start}\n"
                    f"    Run B:    seed {seed}, start board {start}\n\n"
                    "Stop, then in Q-Plus ▸ Deal ▸ Match Control set "
                    f"major = {ref_seed} and minor (start board) = "
                    f"{ref_start}, and restart Run B. (Caught on deal 1.)")
            return
        # Off (or B with no ref) — just display.
        self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#333;")
        self._append(f"[panel] run deal-set: seed {seed}, start board {start}")

    # ---------- process orchestration ----------
    def _mk_proc(self, tag):
        p = QProcess(self)
        p.setProgram("bash" if tag == "proxy" else sys.executable)
        p.setWorkingDirectory(str(BIQ_ROOT))
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.readyReadStandardOutput.connect(
            lambda p=p, tag=tag: self._on_output(p, tag))
        return p

    def _arm_biq_watchdog(self, proc, args, slot):
        """Auto-restart a biq client that DIES mid-run, so a single crash
        (e.g. a libdds segfault the in-process fork-wrapper can't catch
        everywhere) doesn't wedge the whole match. `slot` ∈ {'biq','biq2'}."""
        proc._wd = {"args": list(args), "slot": slot, "n": 0,
                    "t0": time.time()}
        proc.finished.connect(
            lambda code, status, p=proc: self._on_biq_finished(p, code, status))

    def _on_biq_finished(self, proc, code, status):
        wd = getattr(proc, "_wd", None)
        if wd is None or not getattr(self, "_biq_should_run", False):
            return                                  # intentional stop
        crashed = (status == QProcess.ExitStatus.CrashExit) or code != 0
        if not crashed:
            return
        alive = time.time() - wd["t0"]
        if wd["n"] >= 6 or alive < 2.0:
            self._append(f"[watchdog] {wd['slot']} died (code {code}, alive "
                         f"{alive:.0f}s) and won't auto-restart — Stop all "
                         f"and re-run.")
            return
        wd["n"] += 1
        self._append(f"[watchdog] {wd['slot']} crashed (code {code}); "
                     f"restarting (attempt {wd['n']}) to keep the match alive.")
        QTimer.singleShot(1500, lambda: self._relaunch_biq(wd))

    def _relaunch_biq(self, wd):
        if not getattr(self, "_biq_should_run", False):
            return
        new = self._mk_proc(wd["slot"])
        new.setArguments(wd["args"])
        self._arm_biq_watchdog(new, wd["args"], wd["slot"])
        new._wd["n"] = wd["n"]               # carry the relaunch count forward
        setattr(self, wd["slot"], new)
        new.start()

    def _biq_args(self, seat, port, log_path):
        # biq always follows Q-Plus's N/S system: in 'auto' it matches
        # whatever Q-Plus is configured for; in sequential/random/fixed the
        # clicker sets Q-Plus's N/S and biq follows it. So --auto-system always.
        return ["tools/biq_qnet_client.py", "--host", "127.0.0.1",
                "--port", str(port), "--seat", seat,
                "--num-samples", str(self.samples.value()),
                "--log", str(log_path), "--auto-system"]

    def _pair_seats(self):
        """Which side biq sits on for a biq+biq run — the double-pair 'room'.
        Room 1 = biq N/S (default); Room 2 = biq E/W. Returns a dict the run
        plumbing reads instead of hardcoding N/S, so the SAME deck can be
        played from both sides for a board-a-match validation."""
        ew = (getattr(self, "dp_side", None) is not None
              and self.dp_side.currentText().startswith("E/W"))
        if ew:
            return {"s1": "E", "log1": BIQ_E_LOG, "s2": "W", "log2": BIQ_W_LOG,
                    "watch": BIQ_E_LOG, "our_seat": "W", "room": 2,
                    "extern": "E & W = Extern, N/S = Computer"}
        return {"s1": "N", "log1": BIQ_N_LOG, "s2": "S", "log2": BIQ_S_LOG,
                "watch": BIQ_N_LOG, "our_seat": "S", "room": 1,
                "extern": "N & S = Extern, E/W = Computer"}

    def _watch_log(self):
        """The biq log the autoclicker tails — side-aware for biq+biq."""
        return self._pair_seats()["watch"] if self.pair.isChecked() else BIQ_LOG

    def _our_seat(self):
        """biq's representative seat for score aggregation — side-aware."""
        return (self._pair_seats()["our_seat"] if self.pair.isChecked()
                else self.seat.currentText())

    # ---------- double-pair (board-a-match) validation ----------
    def _on_dp_side_changed(self, _idx):
        ps = self._pair_seats()
        self.b_dp_save.setText(f"Save run → Room {ps['room']}")
        if not self.pair.isChecked():
            self._append("[dp] Double-pair needs biq+biq (pair) mode — tick "
                         "‘biq+biq (N+S Extern)’ in Run configuration.")
        self._append(f"[dp] Room {ps['room']}: biq {ps['s1']}/{ps['s2']}. "
                     f"Set Q-Plus Config ▸ Players to {ps['extern']}, then run "
                     f"the SAME deck as the other room.")

    def _dp_save_room(self):
        """Copy the current side's biq log into the Room-1/Room-2 slot."""
        ps = self._pair_seats()
        src = self._watch_log()
        dst = DP_ROOM1_LOG if ps["room"] == 1 else DP_ROOM2_LOG
        if not src.exists() or src.stat().st_size == 0:
            QMessageBox.warning(self, "No run log",
                f"{src.name} is empty — run Room {ps['room']} (biq "
                f"{ps['s1']}/{ps['s2']}) first, then save.")
            return
        dst.write_bytes(src.read_bytes())
        self._append(f"[dp] saved Room {ps['room']} ({ps['s1']}/{ps['s2']}): "
                     f"{src.name} → {dst.name}")

    def _dp_run_4computer(self):
        """Launch the all-computer autoclicker for the R3 baseline run."""
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setWorkingDirectory(str(BIQ_ROOT))
        proc.setArguments(["tools/qplus_4computer_clicker.py",
                           "--deals", str(self.deals.value())])
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(
            lambda p=proc: self._append(
                bytes(p.readAllStandardOutput()).decode("utf-8", "replace").rstrip()))
        proc.start()
        self._biq_4cc = proc
        self._append("[dp] 4-computer autoclicker started (idle-driven). "
                     "Ensure Q-Plus is all-Computer with the deck loaded and "
                     "the watch region calibrated. Export the .qss when done.")

    def _dp_save_baseline(self):
        """Stash the newest exported .qss as the all-Q-Plus baseline."""
        qss = self._newest_qss()
        if not qss:
            QMessageBox.warning(self, "No .qss",
                "Export the .qss from the 4-computer run first "
                "(‘Export .qss’), then save it as the baseline.")
            return
        DP_BASELINE_QSS.write_bytes(Path(qss).read_bytes())
        self._append(f"[dp] saved baseline (all-Q-Plus): "
                     f"{Path(qss).name} → {DP_BASELINE_QSS.name}")

    def _dp_compare(self):
        """Board-a-match compare on the two saved room logs; if an all-Q-Plus
        baseline is saved, also print the N/S vs E/W closed-room split."""
        if not DP_ROOM1_LOG.exists() or not DP_ROOM2_LOG.exists():
            QMessageBox.information(self, "Need both rooms",
                "Save BOTH rooms first: run the deck with biq N/S (Room 1) "
                "and again with biq E/W (Room 2) on the SAME deck, clicking "
                "‘Save run → Room N’ after each.")
            return
        label = f"{self.ns_sys.currentText()} vs {self.ew_sys.currentText()}"
        cmd = [sys.executable, "tools/double_pair_compare.py",
               "--room1", str(DP_ROOM1_LOG), "--room2", str(DP_ROOM2_LOG),
               "--biq-prefix", "", "--label", label]
        if DP_BASELINE_QSS.exists():
            cmd += ["--baseline", str(DP_BASELINE_QSS)]
        try:
            out = subprocess.run(cmd, cwd=str(BIQ_ROOT),
                                 capture_output=True, text=True, timeout=60)
            text = out.stdout + (("\n" + out.stderr) if out.stderr else "")
        except Exception as e:                       # noqa: BLE001
            text = f"compare failed: {e}"
        self._append("[dp] board-a-match compare:\n" + text)
        verdict = next((ln for ln in text.splitlines()
                        if "Net teams IMP" in ln), text[:200])
        QMessageBox.information(self, "Double-pair result", verdict.strip())

    # ---------- Q-Plus lifecycle (replaces the terminal commands) ----------
    def launch_qplus(self, on_ready=None):
        """Launch Q-Plus under system wine-9.0 and click Start on the
        Local-bridge-server dialog until :5555 listens. Calls on_ready()
        once the server is up (immediately if it already was)."""
        if _server_listening():
            self._append("[panel] :5555 already listening — server up")
            if on_ready:
                on_ready()
            return
        env = dict(os.environ, WINE_BIN_SERVER="/usr/bin/wine")
        if _qplus_running():
            # already loading (e.g. stuck behind the splash) — don't spawn a
            # second instance; just resume the poll to clear it and Start.
            self._append("[panel] Q-Plus already running — resuming "
                         "(dismissing splash + clicking Start)…")
        else:
            try:
                subprocess.Popen(
                    ["bash", "tools/qplus_dual_instance.sh", "server"],
                    cwd=str(BIQ_ROOT), env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL, start_new_session=True)
            except OSError as e:
                QMessageBox.warning(self, "Launch failed", str(e))
                return
            self._append("[panel] launching Q-Plus server (wine-9.0)…")
        self.hint.setText("Launching Q-Plus… auto-clicking past the splash, "
                          "then Start, when it loads.")
        self._qp_wait = 0

        def poll():
            if _server_listening():
                self._append("[panel] :5555 listening — server ready")
                self.hint.setText("Q-Plus server up on :5555.")
                # The 'Local bridge server' dialog stays open over the menu
                # bar and BLOCKS the Configuration menu — so the bidding-system
                # set and the East-reset clicks miss (only buttons elsewhere,
                # like Closed Room, work). Minimise it so the menu is reachable;
                # the server keeps running and biq stays connected.
                if _minimize_bridge_dialog():
                    self._append("[panel] minimised the bridge-server dialog "
                                 "(frees the Configuration menu)")
                else:
                    self._append("[panel] ⚠ bridge-server dialog NOT minimised "
                                 "— calibrate 'bridge_min' (its minimise "
                                 "button); it blocks the Configuration menu so "
                                 "systems + East-reset will fail.")
                if on_ready:
                    on_ready()
                return
            self._qp_wait += 1
            # Every tick, clear the launch splash ('The activation is already
            # done!' → Ok). Blind for the first 8s (only the splash can exist
            # then), title-guarded after, so it never hits the bridge dialog.
            _dismiss_qplus_splash(blind=self._qp_wait <= 8)
            # ~12s load grace, then every 6s: open the Network menu and pick
            # ‘Start bridge server’, then click Start in the dialog. The menu
            # closes the instant the mouse pauses or clicks off it, so the
            # menu→item clicks must be TIGHT (0.25s) with nothing in between;
            # the dialog then needs ~1s to appear before the Start click.
            if self._qp_wait >= 12 and (self._qp_wait - 12) % 6 == 0:
                # Q-Plus may auto-deal a LOCAL board on launch (if a prior
                # broken state left East=Local) → a bidding box / 'No bid
                # entered' MODAL dialog that blocks the Network clicks and
                # the server never starts. Clear it first: Return = OK any
                # dialog, Escape = cancel the bidding box. Sent to the focused
                # window (xdotool can't find Wine windows to target).
                _xdotool("key", "Return")
                _xdotool("key", "Escape")
                time.sleep(0.3)
                nm = _load_server_btn("network_menu")
                nsi = _load_server_btn("net_start_item")
                xy = _load_server_btn("start_item")
                # Every retry, re-do BOTH clicks: Network → Start-server,
                # as one atomic chained action so the menu can't close in
                # between. (Just retrying the dialog ‘Start’ click is useless
                # if the dialog never opened.)
                if _menu_pick(nm, nsi):
                    self._append(f"[panel] Network {nm} → Start-server {nsi} "
                                 "(atomic)")
                    time.sleep(1.0)         # let the bridge-server dialog open
                elif nm:
                    _click_xy(*nm)
                    time.sleep(0.6)
                # Then click the dialog ‘Start’ — unless the server already
                # bound (some builds start straight from the menu item).
                if xy and not _server_listening():
                    _click_xy(*xy)
                    self._append(f"[panel] clicked dialog Start {xy}")
                elif not xy:
                    self.hint.setText(
                        "Q-Plus loading, but the ‘Start’ button isn't "
                        "calibrated — Calibrate / edit captures…")
            if self._qp_wait > 90:
                self.hint.setText(
                    "Q-Plus didn't reach :5555 in ~90s. Check the server "
                    "window and the Start-button calibration.")
                return
            QTimer.singleShot(1000, poll)
        QTimer.singleShot(1000, poll)

    def kill_all_wine(self, confirm=True):
        """Force-quit Q-Plus + all wine, clearing the :5555 listen socket
        and the 64-board scoring cap. confirm=False for the automated
        inter-session cleanup."""
        if confirm:
            mb = QMessageBox(self)
            mb.setWindowTitle("Exit Q-Plus")
            # No icon → the text spans the full width (no blank left column).
            mb.setIcon(QMessageBox.Icon.NoIcon)
            mb.setText(
                "Force-quit Q-Plus and all wine processes?\n\n"
                "This exits Q-Plus and clears the :5555 listen socket and the "
                "64-board scoring cap, so the next run starts clean.\n\n"
                "Make sure you've pressed ‘Export .qss’ first if you want to "
                "keep this run's score sheet — killing wine discards Q-Plus's "
                "in-memory score table.")
            mb.setStandardButtons(QMessageBox.StandardButton.Yes
                                  | QMessageBox.StandardButton.No)
            mb.setDefaultButton(QMessageBox.StandardButton.No)
            if mb.exec() != QMessageBox.StandardButton.Yes:
                return
        self.stop_all(silent=True)   # biq + clicker + pkill biq_qnet_client
        try:
            subprocess.run(["bash", "-c",
                            f'WINEPREFIX="{WP_SERVER}" wineserver -k'],
                           timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
        # bracketed patterns never match this python3 process
        for pat in ("win[e]", "syste[m]32", "deskto[p]",
                    "QBRIDG[E]", "Q-NE[T]"):
            subprocess.run(["pkill", "-9", "-f", pat])
        self._append("[panel] killed all wine — :5555 socket + cap cleared")

    # ==================== startup stepper ====================
    # The Q-Plus startup as an ordered list of discrete steps. Each step
    # does ONE series of clicks/launches and calls _step_done() when
    # finished (including async waits). ‘Step ▷’ runs one; ‘Autopilot’
    # runs them back-to-back. This lets you watch the order — e.g. catch
    # the auto-dealt bidding box that pops up before the server starts —
    # and fix things by hand between steps.
    def _build_steps(self):
        return [
            ("launch",   "Launch Q-Plus (wine-9.0) + dismiss splash",
             self._step_launch),
            ("server",   "Start bridge server (Network ▸ Start ▸ wait :5555)",
             self._step_start_server),
            ("minimize", "Minimise bridge-server dialog (frees Config menu)",
             self._step_minimize),
            ("biq",      "Start biq + connect to :5555 (wait for ‘joined’)",
             self._step_start_biq),
            ("systems",  "Set bidding systems for deal 1 (one-shot dialog)",
             self._step_set_systems),
            ("east",     "Set seats (East=Computer; biq+biq: verify N/S=Extern)",
             self._step_east),
            ("deal",     "Deal board 1 (Closed Room)",
             self._step_deal),
            ("clicker",  "Start autoclicker (run the match)",
             self._step_clicker),
        ]

    def _cur_step_key(self):
        if 0 <= self._step_idx < len(self._steps):
            return self._steps[self._step_idx][0]
        return None

    def _refresh_step_list(self):
        if not hasattr(self, "step_list"):
            return
        for i in range(self.step_list.count()):
            label = self._steps[i][1]
            if i == self._step_idx and self._step_running:
                mark = "▶"
            elif i <= self._step_idx:
                mark = "✓"
            else:
                mark = "•"
            self.step_list.item(i).setText(f"  {mark}  {i + 1}. {label}")
        row = self._step_idx if self._step_running else self._step_idx + 1
        self.step_list.setCurrentRow(
            max(0, min(row, self.step_list.count() - 1)))

    def _update_step_buttons(self):
        if not hasattr(self, "b_step"):
            return
        at_end = self._step_idx + 1 >= len(self._steps)
        # Keep Step ENABLED while a step runs (the _step_run_next re-entry
        # guard ignores extra presses) — disabling it would move keyboard
        # focus to Autopilot and let a stray keypress trigger it.
        self.b_step.setEnabled(not at_end)

    def _steps_reset(self):
        self._step_idx = -1
        self._step_running = False
        self._await_biq_join = False
        self._set_autopilot(False, run=False)
        self._refresh_step_list()
        self._update_step_buttons()
        self._append("[steps] reset to start")
        self.hint.setText(
            "Stepper reset. ‘Step ▷’ runs one step then stops; ‘Autopilot’ "
            "runs them all. (Reset only moves the pointer — it does not undo "
            "Q-Plus state.)")

    def _on_step_clicked(self):
        """The Step button is ALWAYS single-shot: run exactly the next step,
        then stop. If Autopilot was left on it would otherwise chain into the
        rest — so turn it off first. (Autopilot is the only thing that runs
        steps back-to-back; Step never does.)"""
        self._stepper_mode = True       # lock out the legacy auto-deal chain
        if self._autopilot:
            self._set_autopilot(False, run=False)
            self._append("[steps] Autopilot off — Step does ONE step at a "
                         "time now")
        self._step_run_next()

    def _step_run_next(self):
        if self._step_running:
            self._append("[steps] a step is still running — wait for it")
            return
        nxt = self._step_idx + 1
        if nxt >= len(self._steps):
            self._append("[steps] all steps complete")
            self._set_autopilot(False, run=False)
            self._update_step_buttons()
            return
        self._step_idx = nxt
        self._step_running = True
        _key, label, fn = self._steps[nxt]
        self._append(f"[steps] ▶ STEP {nxt + 1}/{len(self._steps)}: {label}")
        self.hint.setText(f"STEP {nxt + 1}: {label}…")
        self._refresh_step_list()
        self._update_step_buttons()
        try:
            fn()
        except Exception as e:               # never wedge the stepper
            self._step_done(False, f"exception: {e}")

    def _step_done(self, ok=True, note=""):
        if not self._step_running:
            return
        self._step_running = False
        mark = "✓" if ok else "✗"
        self._append(f"[steps] {mark} STEP {self._step_idx + 1} done"
                     + (f": {note}" if note else ""))
        if not ok:
            failed = self._step_idx
            # Step back so the next ‘Step ▷’/Autopilot RETRIES this step
            # (it short-circuits if you fixed the blocker by hand).
            self._step_idx -= 1
            self._set_autopilot(False, run=False)
            self._refresh_step_list()
            self._update_step_buttons()
            self.hint.setText(
                f"⚠ STEP {failed + 1} failed: {note}\nFix it by hand, then "
                "‘Step ▷’ to retry (it short-circuits if already done), or "
                "‘Autopilot’.")
            return
        self._refresh_step_list()
        self._update_step_buttons()
        nxt = self._step_idx + 1
        if nxt >= len(self._steps):
            self._set_autopilot(False, run=False)
            self.hint.setText("✓ All startup steps complete — match running.")
            return
        if self._autopilot:
            QTimer.singleShot(600, self._step_run_next)
        else:
            self.hint.setText(
                f"✓ STEP {self._step_idx + 1} done. Next: STEP {nxt + 1} — "
                f"{self._steps[nxt][1]}.   ‘Step ▷’ or ‘Autopilot’.")

    def _set_autopilot(self, on, run=True):
        self._autopilot = on
        if hasattr(self, "b_auto"):
            self.b_auto.blockSignals(True)
            self.b_auto.setChecked(on)
            self.b_auto.blockSignals(False)
            self.b_auto.setText("Autopilot ▶ (ON)" if on else "Autopilot ▶")
        if on and run and not self._step_running:
            self._step_run_next()

    def _on_autopilot_toggled(self, checked):
        if checked:
            # Autopilot runs ALL remaining steps and drives the mouse — so it
            # must NOT engage from a stray click while you're stepping by hand.
            # Confirm first; on No, revert the toggle and stay manual.
            ans = QMessageBox.question(
                self, "Start Autopilot?",
                "Autopilot will run ALL the remaining startup steps "
                "back-to-back, moving the mouse on its own — you won't be "
                "able to fix anything between steps.\n\n"
                "Start Autopilot now?\n\n"
                "(To keep going one step at a time, click No and use "
                "‘Step ▷’.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                self.b_auto.blockSignals(True)
                self.b_auto.setChecked(False)
                self.b_auto.blockSignals(False)
                self._append("[steps] autopilot cancelled — staying on "
                             "manual Step (one step per click)")
                return
            self._stepper_mode = True   # lock out the legacy auto-deal chain
        self._append(f"[steps] autopilot {'ON' if checked else 'OFF'}")
        self._set_autopilot(checked, run=True)

    # ---- the individual steps (each ends by calling _step_done) ----
    def _step_launch(self):
        if _server_listening():
            self._step_done(True, ":5555 already up — Q-Plus already launched")
            return
        env = dict(os.environ, WINE_BIN_SERVER="/usr/bin/wine")
        if _qplus_running():
            self._append("[step] Q-Plus already running — not spawning a 2nd")
        else:
            try:
                subprocess.Popen(
                    ["bash", "tools/qplus_dual_instance.sh", "server"],
                    cwd=str(BIQ_ROOT), env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL, start_new_session=True)
            except OSError as e:
                self._step_done(False, f"launch failed: {e}")
                return
            self._append("[step] launching Q-Plus server (wine-9.0)…")
        self._launch_wait = 0

        def poll():
            if not self._step_running or self._cur_step_key() != "launch":
                return                     # stepped away / stopped
            self._launch_wait += 1
            _dismiss_qplus_splash(blind=self._launch_wait <= 8)
            if _server_listening():
                self._step_done(True, "server already listening")
                return
            if _qplus_running() and self._launch_wait >= 4:
                self._step_done(
                    True, "Q-Plus window up (splash dismissed). If a bidding "
                    "box auto-popped, clear it before ‘Start server’.")
                return
            if self._launch_wait > 40:
                self._step_done(False, "Q-Plus didn't come up in ~40s")
                return
            QTimer.singleShot(1000, poll)
        QTimer.singleShot(1000, poll)

    def _step_start_server(self):
        if _server_listening():
            self._step_done(True, ":5555 already listening")
            return
        self._srv_wait = 0

        def poll():
            if not self._step_running or self._cur_step_key() != "server":
                return
            if _server_listening():
                self._step_done(True, ":5555 listening — server ready")
                return
            self._srv_wait += 1
            # Clear any auto-dealt bidding box / 'No bid entered' modal FIRST
            # (this is the out-of-order pop-up): Return = OK, Escape = cancel.
            _xdotool("key", "Return")
            _xdotool("key", "Escape")
            time.sleep(0.3)
            if self._srv_wait == 1 or self._srv_wait % 6 == 0:
                nm = _load_server_btn("network_menu")
                nsi = _load_server_btn("net_start_item")
                xy = _load_server_btn("start_item")
                if _menu_pick(nm, nsi):
                    self._append(f"[step] Network {nm} → Start-server {nsi} "
                                 "(atomic)")
                    time.sleep(1.0)
                elif nm:
                    _click_xy(*nm)
                    time.sleep(0.6)
                if xy and not _server_listening():
                    _click_xy(*xy)
                    self._append(f"[step] clicked dialog Start {xy}")
                elif not xy:
                    self._step_done(
                        False, "‘start_item’ not calibrated — Calibrate "
                        "server buttons…")
                    return
            if self._srv_wait > 60:
                self._step_done(False, "server didn't reach :5555 in ~60s")
                return
            QTimer.singleShot(1000, poll)
        QTimer.singleShot(200, poll)

    def _step_minimize(self):
        if _minimize_bridge_dialog():
            self._step_done(True, "minimised the bridge-server dialog")
        else:
            # not fatal, but the Configuration menu may be blocked
            self._step_done(
                True, "⚠ ‘bridge_min’ not calibrated — dialog NOT minimised; "
                "the Configuration menu may be blocked (systems + East-reset "
                "can fail). Calibrate ‘bridge_min’.")

    def _step_start_biq(self):
        if not _server_listening():
            self._step_done(
                False, "no :5555 server — run ‘Start bridge server’ first")
            return
        # Run context (mirrors start_proxy_biq): fresh logs, progress range.
        # halt_steps=False so this cleanup doesn't cancel the step we're in.
        self.stop_all(silent=True, halt_steps=False)
        self.b_stop.setEnabled(True)
        self.deals_total = self.deals.value()
        self.bar.setRange(0, self.deals_total)
        self.bar.setValue(0)
        for lg in (BIQ_N_LOG, BIQ_S_LOG, BIQ_E_LOG, BIQ_W_LOG, BIQ_LOG):
            try:
                lg.write_text("")
            except OSError:
                pass
        self._append(f"===== run start (stepper): {self.deals_total} deals "
                     f"=====")
        self._this_run_seen = False          # arm the deal-set guard
        self.lbl_thisrun.setText("This run: (waiting for deal 1…)")
        self.deals_list.clear()
        self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#333;")
        self._await_biq_join = True
        self._start_biq()

        def grace():
            if (self._step_running and self._cur_step_key() == "biq"
                    and self._await_biq_join):
                self._await_biq_join = False
                self._step_done(
                    True, "biq started (no ‘joined’ line in ~20s — check the "
                    "log and the server seat config: N/S=Extern, E/W=Computer)")
        QTimer.singleShot(20000, grace)

    def _step_set_systems(self):
        ns_mode = self.ns_sys.currentText()
        ew_mode = self.ew_sys.currentText()
        syscal = Path.home() / ".qplus_mixed_corpus.json"
        if self._system_calibration_missing(syscal):
            self._step_done(
                True, "systems not calibrated — skipped (deal 1 uses Q-Plus "
                "default). Calibrate on the corpus GUI's Bidding-system "
                "dialog.")
            return
        self._oneshot = self._mk_proc("clicker")
        self._oneshot.setArguments(
            ["-u", "tools/qplus_button_loop.py", "--set-systems-once",
             "--system-buttons", str(syscal),
             "--ns-system", ns_mode, "--ew-system", ew_mode]
            + self._sys_seed_args())

        def on_finish(*_a):
            if self._step_running and self._cur_step_key() == "systems":
                self._step_done(True, f"systems set NS={ns_mode} EW={ew_mode}")
        self._oneshot.finished.connect(on_finish)
        self._oneshot.start()
        self.hint.setText("Setting bidding systems for deal 1…")

    def _step_east(self):
        ps = self._pair_seats() if self.pair.isChecked() else None
        if ps and ps["room"] == 2:
            # Double-pair Room 2: biq sits E/W, so the Extern/Computer config
            # is INVERTED (N/S=Computer, E/W=Extern). The calibrated
            # East=Computer click is wrong here — set the four seats by hand.
            self._step_done(True,
                "Room 2 (biq E/W): SET BY HAND in Config ▸ Players — "
                "N=Computer, S=Computer, E=Extern, W=Extern — then Step to "
                "‘Deal board 1’. (The auto East-reset is N/S-room only.)")
            return
        self.set_east_computer()
        note = "East = Computer click sequence sent"
        if self.pair.isChecked():
            # biq+biq Room 1 needs N & S = Extern AND E & W = Computer. We only
            # auto-click East; if South isn't Extern, Q-Plus pops a SOUTH
            # bidding box and later stalls on the South dummy. With Step
            # now single-shot, PAUSE here and verify all four seats by hand
            # before dealing.
            note += (" — biq+biq Room 1: now VERIFY in Config ▸ Players that "
                     "N=Extern, S=Extern, E=Computer, W=Computer BEFORE you "
                     "Step to ‘Deal board 1’. A South bidding box / dummy "
                     "stall means South isn't Extern.")
        self._step_done(True, note)

    def _step_deal(self):
        xy = _load_closed_room()
        if not xy:
            self._step_done(
                False, "‘Closed Room’ not calibrated — calibrate it or click "
                "it on the Q-Plus server by hand")
            return
        _click_xy(*xy)
        self._append(f"[step] clicked Closed Room at {xy}")
        self.b_run.setEnabled(True)
        self._step_done(True, "board 1 dealt (Closed Room)")

    def _step_clicker(self):
        self.start_clicker()
        self._step_done(True, "autoclicker started — match running")

    # ---------- one-click / session loop ----------
    def run_full_session(self):
        """One click: (loop of) launch Q-Plus → biq → deal → click →
        aggregate, fully hands-off. Sessions>1 loops, killing wine between."""
        self._session_total = self.sessions.value()
        self._session_idx = 1
        self._loop_active = self._session_total > 1
        self._session_logs = []
        self._session_qss = []
        self._stepper_mode = False   # one-click uses the legacy auto chain
        self.auto.setChecked(True)   # so deal+click auto-fire when biq joins
        self._start_one_session()

    def _start_one_session(self):
        # Always allow stopping a run in progress.
        self.b_stop.setEnabled(True)
        self.hint.setText(
            f"Session {self._session_idx}/{self._session_total}: launching "
            "Q-Plus + biq (hands-off)…")
        self.launch_qplus(on_ready=self.start_proxy_biq)

    def manual_start(self):
        """The numbered ‘1 ▸ Start server+biq’ path: single session, no
        loop, and don't auto-launch Q-Plus (user manages the server)."""
        self._loop_active = False
        self._session_total = 1
        self._session_idx = 1
        self.start_proxy_biq()

    def start_proxy_biq(self):
        if not _server_listening():
            QMessageBox.warning(
                self, "No server",
                f"Nothing is listening on :{SERVER_PORT}.\n\nStart the "
                "Q-Plus server under wine-9.0 and Start the bridge server "
                "on 5555 first:\n\n  WINE_BIN=/usr/bin/wine "
                "tools/qplus_dual_instance.sh server")
            return
        self.stop_all(silent=True)
        self.deals_total = self.deals.value()
        self.bar.setRange(0, self.deals_total)
        self.bar.setValue(0)
        # Fresh biq logs so the run aggregates cleanly: biq connects DIRECT
        # (no proxy) and appends to its own log through the whole run incl.
        # the reset relaunches; the autoclicker watches that client log and
        # the aggregator scores from it. Direct = biq survives the Network
        # Stop/Start reset without the proxy-upstream zombie.
        for lg in (BIQ_N_LOG, BIQ_S_LOG, BIQ_E_LOG, BIQ_W_LOG, BIQ_LOG):
            try:
                lg.write_text("")
            except OSError:
                pass
        self._append(f"===== run start: {self.deals_total} deals, "
                     f"session {self._session_idx}/{self._session_total} =====")
        self._this_run_seen = False          # arm the deal-set guard
        self.lbl_thisrun.setText("This run: (waiting for deal 1…)")
        self.deals_list.clear()
        self.lbl_thisrun.setStyleSheet("font-weight:bold; color:#333;")
        self._start_biq()
        self.b_start.setEnabled(False)
        self.b_stop.setEnabled(True)
        self.hint.setText("Starting biq (direct, no proxy)…")

    def _start_biq(self):
        runs = BIQ_ROOT / "tools/runs"
        self._biq_should_run = True       # arm the crash-watchdog
        if self.pair.isChecked():
            # biq+biq partnership: BOTH clients connect DIRECT to :5555
            # (no proxy) so each sees the server Stop/Start and the reset
            # relaunch rejoins cleanly. The autoclicker watches the first
            # seat's log. Side (N/S Room 1 vs E/W Room 2) per _pair_seats().
            ps = self._pair_seats()
            a1 = self._biq_args(ps["s1"], SERVER_PORT, ps["log1"]) + ["--pair"]
            a2 = self._biq_args(ps["s2"], SERVER_PORT, ps["log2"]) + ["--pair"]
            self.biq = self._mk_proc("biq")
            self.biq.setArguments(a1)
            self._arm_biq_watchdog(self.biq, a1, "biq")
            self.biq.start()
            self.biq2 = self._mk_proc("biq")
            self.biq2.setArguments(a2)
            self._arm_biq_watchdog(self.biq2, a2, "biq2")
            self.biq2.start()
            who = f"biq+biq Room {ps['room']} ({ps['s1']}/{ps['s2']}, direct on :5555)"
            extra = f" — server needs {ps['extern']}"
        else:
            a1 = self._biq_args(self.seat.currentText(), SERVER_PORT, BIQ_LOG)
            self.biq = self._mk_proc("biq")
            self.biq.setArguments(a1)
            self._arm_biq_watchdog(self.biq, a1, "biq")
            self.biq.start()
            who = f"biq as {self.seat.currentText()}"
            extra = ""
        calibrated = _load_closed_room() is not None
        self.b_deal.setEnabled(calibrated)
        self.b_run.setEnabled(True)
        tail = ("press ‘2 ▸ Deal board 1’ then ‘3 ▸ Run autoclicker’ "
                "(or tick Auto-run)." if calibrated else
                "click Closed Room then ‘3 ▸ Run autoclicker’.")
        self.hint.setText(f"{who} connecting{extra}. When joined, {tail}")

    def open_calibrate(self):
        CalibrationManagerDialog(self).exec()
        running = bool(self.biq and
                       self.biq.state() != QProcess.ProcessState.NotRunning)
        self.b_deal.setEnabled(running and _load_closed_room() is not None)

    def deal_first_board(self):
        xy = _load_closed_room()
        if not xy:
            QMessageBox.information(
                self, "Not calibrated",
                "Calibrate the 'Closed Room' button first, or click it "
                "manually on the Q-Plus server.")
            return
        _click_xy(*xy)
        self._append(f"[panel] clicked Closed Room at {xy}")
        self.b_run.setEnabled(True)

    def _auto_deal_and_run(self):
        # Order: ONE-SHOT system-set (deal-1 systems) → East-reset → deal
        # board 1 → autoclicker. The system-set is a Q-Plus CONFIG change, so
        # it must come BEFORE the East-reset (a config change can drop East
        # off Computer). The one-shot drives the dialog as a SEPARATE process
        # with verified open+close, so it can't leave a modal dialog blocking
        # the East-reset / deal / network clicks. The autoclicker then handles
        # deal-2+ systems (re-rolling random sides at each score).
        self.b_stop.setEnabled(True)
        if not self._start_oneshot_systems():
            self._after_systems_set()

    def _start_oneshot_systems(self):
        ns_mode = self.ns_sys.currentText()
        ew_mode = self.ew_sys.currentText()
        if ns_mode == "auto" and ew_mode == "auto":
            return False
        syscal = Path.home() / ".qplus_mixed_corpus.json"
        if self._system_calibration_missing(syscal):
            self._append("[panel] systems not calibrated — skipping one-shot "
                         "set (deal 1 uses Q-Plus default).")
            return False
        self._oneshot = self._mk_proc("clicker")
        self._oneshot.setArguments(
            ["-u", "tools/qplus_button_loop.py", "--set-systems-once",
             "--system-buttons", str(syscal),
             "--ns-system", ns_mode, "--ew-system", ew_mode]
            + self._sys_seed_args())
        self._oneshot.finished.connect(
            lambda *_a: QTimer.singleShot(1200, self._after_systems_set))
        self._oneshot.start()
        self.hint.setText("Setting bidding systems for deal 1…")
        return True

    def _after_systems_set(self):
        # East-reset AFTER the system config change, then deal board 1, then
        # start the autoclicker (handles deal-2+ systems).
        self.set_east_computer()
        QTimer.singleShot(1500, self._deal_then_clicker)

    def _deal_then_clicker(self):
        self.deal_first_board()
        QTimer.singleShot(2500, self.start_clicker)

    def set_east_computer(self):
        """Configuration ▸ Players ▸ (East = Computer) ▸ OK — the 4-click
        sequence that keeps the East seat a Q-Plus bot. Skips (with a note)
        if the four positions aren't calibrated."""
        keys = ["cfg_menu", "players_item", "east_computer", "players_ok"]
        pts = [_load_server_btn(k) for k in keys]
        if not all(pts):
            miss = [k for k, p in zip(keys, pts) if not p]
            self._append("[panel] East=Computer skipped — not calibrated: "
                         + ", ".join(miss) + " (use ‘Calibrate server "
                         "buttons…’).")
            return
        self._append("[panel] resetting East = Computer "
                     "(Configuration ▸ Players ▸ OK)…")
        for p in pts:
            _click_xy(*p)
            time.sleep(0.6)

    def _reset_calibration_missing(self, trans_path):
        """Return a list of calibration targets still missing for an
        unattended reset-every run (empty list = ready)."""
        missing = []
        try:
            srv = json.loads(SERVER_BTN_FILE.read_text())
        except Exception:
            srv = {}
        for k in ("stop_item", "start_item"):
            if k not in srv:
                missing.append(f"Bridge-server button: {k}")
        try:
            tr = json.loads(Path(trans_path).read_text())
        except Exception:
            tr = {}
        for k in ("deal_menu", "match_control", "minor_field", "ok_button",
                  "deal_button"):
            if k not in tr:
                missing.append(f"Transition target: {k}")
        return missing

    def _system_calibration_missing(self, path):
        """Required keys in the corpus GUI's calibration for per-deal
        NS+EW system clicks (empty list = ready)."""
        req = ["config_menu", "bidding_system_item", "radio_american",
               "radio_british", "radio_french", "radio_precision",
               "list_SAYC", "list_TwoOverOne", "list_StandardAcol",
               "list_StandardFrench", "list_Precision90M",
               "set_ns_btn", "set_ew_btn", "close_btn"]
        try:
            d = json.loads(Path(path).read_text())
        except Exception:
            return req
        return [k for k in req if k not in d]

    def start_clicker(self):
        if not (self.biq and self.biq.state() != QProcess.ProcessState.NotRunning):
            QMessageBox.warning(self, "biq not running",
                                "Start server+biq first.")
            return
        watch_log = self._watch_log()
        # -u = unbuffered: deliver the autoclicker's progress + completion
        # lines (and EOF on exit) to us immediately. Without it, the final
        # "deals complete" can sit block-buffered in the pipe when the
        # clicker idles after the last deal, so NONE of our finish triggers
        # fire and the .qss export never runs.
        args = ["-u", "tools/qplus_button_loop.py",
                "--deals", str(self.deals_total),
                "--watch", str(watch_log), "--client-log",
                "--idle", str(self.idle.value())]
        n = self.reset_every.value()
        if n > 0:
            trans = Path.home() / ".qplus_transition.json"
            missing = self._reset_calibration_missing(trans)
            if missing:
                QMessageBox.warning(
                    self, "Reset not calibrated",
                    "Unattended ‘Reset every’ needs these calibrated first:"
                    "\n  • " + "\n  • ".join(missing) +
                    "\n\nNetwork buttons → ‘Calibrate server buttons…’.\n"
                    "Match-Control transition →\n  python3 "
                    "tools/qplus_button_loop.py --recalibrate-transition")
                return
            args += ["--clear-every", str(n), "--start-board", "1",
                     "--server-buttons", str(SERVER_BTN_FILE),
                     "--transition-calibration", str(trans)]
            self.hint.setText(
                f"Unattended: {self.deals_total} deals, full reset every {n} "
                "(Network stop/start + biq relaunch). Hands-off — don't "
                "touch the mouse/biq while it runs.")
        else:
            self.hint.setText("Autoclicker running — watch the deal counter.")
        ns_mode = self.ns_sys.currentText()
        ew_mode = self.ew_sys.currentText()
        if ns_mode != "auto" or ew_mode != "auto":   # at least one side driven
            syscal = Path.home() / ".qplus_mixed_corpus.json"
            miss = self._system_calibration_missing(syscal)
            if miss:
                QMessageBox.warning(
                    self, "Systems not calibrated",
                    "Driving Q-Plus systems needs the corpus GUI's "
                    "bidding-system dialog calibrated "
                    "(~/.qplus_mixed_corpus.json). Missing:\n  • "
                    + "\n  • ".join(miss[:10])
                    + ("\n  • …" if len(miss) > 10 else "")
                    + "\n\nCalibrate it on the Calibration tab of "
                    "tools/qplus_mixed_corpus.py.")
                return
            args += ["--system-buttons", str(syscal),
                     "--ns-system", ns_mode, "--ew-system", ew_mode]
            args += self._sys_seed_args()
        self.clicker = self._mk_proc("clicker")
        self.clicker.setArguments(args)
        # Robust completion: fire the end-of-session handler when the
        # clicker EXITS, not only on the "deals complete" string — the
        # autoclicker can mis-count the last deal (report_score gap) and
        # idle out without printing it, which previously left the run with
        # no .qss export. Guarded by _await_session_end so a manual Stop
        # (which clears it) doesn't trigger an export.
        self._await_session_end = True
        self.clicker.finished.connect(
            lambda *_a: QTimer.singleShot(1500, self._finish_session_once))
        self.clicker.start()
        self.b_run.setEnabled(False)

    def _finish_session_once(self):
        """Run the end-of-session export+aggregate exactly once per run,
        whether triggered by the ‘deals complete’ line or the clicker
        exiting. Skips if the run was stopped manually."""
        if not self._await_session_end:
            return
        self._await_session_end = False
        self.b_run.setEnabled(True)
        self._session_finished()

    def stop_all(self, silent=False, halt_steps=True):
        # a manual/forced stop must NOT trigger the auto export-on-exit
        self._await_session_end = False
        # tell the crash-watchdog this is intentional — don't auto-restart
        self._biq_should_run = False
        # A user/forced stop halts the stepper too: pending async polls check
        # _step_running and bail. (We don't reset the pointer, so you can
        # resume from where you were.) halt_steps=False is for the internal
        # process-cleanup inside _step_start_biq, which must NOT cancel the
        # very step it's part of.
        if halt_steps:
            self._step_running = False
            self._await_biq_join = False
            if self._autopilot:
                self._set_autopilot(False, run=False)
            if hasattr(self, "step_list"):
                self._refresh_step_list()
                self._update_step_buttons()
        for p in (self.clicker, self._oneshot, self.biq, self.biq2,
                  self.proxy):
            if p and p.state() != QProcess.ProcessState.NotRunning:
                p.terminate()
                if not p.waitForFinished(1500):
                    p.kill()
        # also kill any DETACHED biq the autoclicker relaunched during a
        # reset (bracketed pattern → never matches this process).
        subprocess.run(["pkill", "-f", "biq[_]qnet_client"])
        self.clicker = self._oneshot = self.biq = self.biq2 = self.proxy = None
        self._match_started = False
        self.b_start.setEnabled(True)
        self.b_run.setEnabled(False)
        self.b_stop.setEnabled(False)
        if not silent:
            self.hint.setText("Stopped.")

    def new_run(self):
        self.stop_all(silent=True)
        try:
            BIQ_LOG.write_text("")
        except OSError:
            pass
        self.bar.setValue(0)
        self.log.clear()
        self.result.setPlainText("")
        self.hint.setText(
            "Logs cleared. To start the score table fresh too, in Q-Plus "
            "open Match Control and begin a new match (don't 'Restore a "
            "score table'). Then ‘1 ▸ Start server+biq’.")

    # ---------- output parsing ----------
    def _on_output(self, proc, tag):
        data = bytes(proc.readAllStandardOutput()).decode(
            "utf-8", "replace")
        for line in data.splitlines():
            self._append(line)
            if tag == "biq" and "new_deal_pbn" in line:
                # First deal → deal-set guard. Every deal → name list.
                if not self._this_run_seen:
                    m = re.search(
                        r'new_deal_pbn"?\s*\[[NESW]\s+(\d+)\s+(\d+)\]', line)
                    if m:
                        self._this_run_seen = True
                        self._on_first_deal(seed=m.group(2),
                                            start=int(m.group(1)))
                nm = re.search(
                    r'new_deal_pbn"?\s*\[[^\]]*\]\s*\[[^\]]*\]\s*\[([^\]]*)\]'
                    r'\s*\[(\S+)\s+(\S+)', line)
                if nm:
                    label, dealer, vul = nm.group(1), nm.group(2), nm.group(3)
                    n = self.deals_list.count() + 1
                    QListWidgetItem(f"{n:>3}. {label:<11} {dealer} {vul}",
                                    self.deals_list)
                    self.deals_list.scrollToBottom()
            if tag == "biq" and "joined as" in line:
                self.hint.setText("biq " + line.split("]", 1)[-1].strip())
                if (self._await_biq_join and self._step_running
                        and self._cur_step_key() == "biq"):
                    # the stepper owns the biq step — complete it
                    self._await_biq_join = False
                    self._step_done(
                        True, "biq " + line.split("]", 1)[-1].strip())
                elif (not self._stepper_mode
                        and self.auto.isChecked() and _load_closed_room()
                        and not self._match_started):
                    # legacy one-click auto path — ONLY when NOT stepping, so
                    # the 2nd biq join (N+S both connect) can't chain the rest
                    # of the startup while the user is stepping by hand.
                    self._match_started = True
                    self.hint.setText("Auto-run: dealing board 1 + starting "
                                      "autoclicker…")
                    QTimer.singleShot(1500, self._auto_deal_and_run)
            if tag == "clicker":
                m = re.search(r"Deal (\d+)/(\d+)", line)
                if m:
                    n, tot = int(m.group(1)), int(m.group(2))
                    self.bar.setValue(n)
                    # Last deal done — finish even if the explicit "deals
                    # complete" line or the process exit never arrives (the
                    # autoclicker can idle/mis-count). Delay lets the final
                    # cardplay + score settle before the .qss export.
                    if n >= tot and self._await_session_end:
                        self.hint.setText("Last deal done — exporting score "
                                          "sheet…")
                        QTimer.singleShot(6000, self._finish_session_once)
                if "deals complete" in line:
                    self.hint.setText("Match finished — aggregating result…")
                    # small delay so biq flushes the final report_score first,
                    # then export+aggregate (+ loop). Once-guarded so the
                    # clicker-exit fallback doesn't double-fire.
                    QTimer.singleShot(2000, self._finish_session_once)

    def _refresh_health(self):
        def _up(p):
            return bool(p and p.state() != QProcess.ProcessState.NotRunning)
        self.dots["server"].set_state(_server_listening())
        self.dots["clicker"].set_state(_up(self.clicker))
        # Count actual biq processes — the autoclicker may relaunch biq
        # (detached) during an unattended reset, staling our QProcess.
        need = 2 if self.pair.isChecked() else 1
        self.dots["biq"].set_state(_biq_proc_count() >= need)

    # ---------- aggregation ----------
    def aggregate(self):
        # Score from biq's client log report_score (real teams IMP, no DD,
        # complete across the whole run — biq appends through the resets).
        # The .qss caps at 64 boards/session; the client log doesn't.
        watch_log = self._watch_log()
        if not watch_log.exists():
            self.result.setPlainText(
                f"No biq log at {watch_log} yet.\nStart a run "
                "(Start server+biq) so biq begins logging, then retry.")
            return
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setWorkingDirectory(str(BIQ_ROOT))
        seat = self._our_seat()
        proc.setArguments(["tools/qnet_score_aggregate.py", "--log",
                           str(watch_log), "--our-seat", seat])
        proc.start()
        proc.waitForFinished(15000)
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        self.result.setPlainText(f"[{watch_log.name}]\n{out}{err}")

    # ---------- .qss export + aggregation (authoritative score source) ----
    def export_score_sheet(self) -> bool:
        """View ▸ View Scoring Table ▸ Save and send ▸ OK — drives Q-Plus to
        write a fresh .qss. biq's client log under-counts report_score (the
        score message doesn't always reach the client), so the .qss is the
        authoritative source. Skips (with a note) if not calibrated."""
        ss, ok = _load_server_btn("save_and_send"), _load_server_btn("save_ok")
        me = _load_server_btn("match_end")
        if not (ss and ok):
            miss = [k for k, p in (("save_and_send", ss), ("save_ok", ok))
                    if not p]
            self._append("[panel] score-sheet export skipped — not "
                         "calibrated: " + ", ".join(miss)
                         + " (Calibrate / edit captures…).")
            return False
        # Preferred path: after the last board Q-Plus pops the modal "Match
        # End" dialog, which BLOCKS the View menu (so the old View ▸ Scoring
        # Table clicks miss). Its ‘View the scoring table’ button dismisses
        # the dialog AND opens the scoring table in one click — so when
        # match_end is calibrated we click it and SKIP the View-menu nav.
        if me is not None:
            self._append("[panel] dismissing Match End dialog via ‘View the "
                         "scoring table’ → scoring table opens…")
            _click_xy(*me)
            self._append(f"[panel]   Match End ▸ View scoring table {me}")
            time.sleep(2.0)
        else:
            vm, vst = (_load_server_btn(k) for k in
                       ("view_menu", "view_scoring_table"))
            if not (vm and vst):
                self._append("[panel] score-sheet export skipped — calibrate "
                             "‘match_end’ (preferred) OR view_menu + "
                             "view_scoring_table.")
                return False
            self._append("[panel] exporting score sheet (View ▸ Scoring "
                         "Table ▸ Save and send ▸ OK)…")
            _menu_pick(vm, vst)
            self._append(f"[panel]   View {vm} → Scoring Table {vst} (atomic)")
            time.sleep(2.0)
        _click_xy(*ss)
        self._append(f"[panel]   Save and send {ss}")
        time.sleep(1.5)          # save / confirm dialog
        _click_xy(*ok)
        self._append(f"[panel]   OK {ok}")
        time.sleep(0.8)
        return True

    def _export_and_aggregate(self):
        self.export_score_sheet()
        self.aggregate_qss()

    def _newest_qss(self):
        try:
            files = sorted(QSS_DIR.glob("*.qss"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            return files[0] if files else None
        except OSError:
            return None

    def aggregate_qss(self, qss=None):
        """Aggregate biq-vs-Q-Plus IMPs from a .qss score sheet (the full,
        authoritative result). Defaults to the newest .qss in QSS_DIR."""
        qss = qss or self._newest_qss()
        if qss is None:
            self.result.setPlainText(
                f"No .qss found in {QSS_DIR}.\nRun ‘Export score sheet’ (or "
                "View ▸ Scoring Table ▸ Save and send) in Q-Plus first, or "
                "calibrate the export clicks.")
            return
        seat = self._our_seat()
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setWorkingDirectory(str(BIQ_ROOT))
        proc.setArguments(["tools/qss_score_aggregate.py", "--qss",
                           str(qss), "--our-seat", seat])
        proc.start()
        proc.waitForFinished(20000)
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        self.result.setPlainText(f"[{qss.name}]\n{out}{err}")

    # ---------- session-loop continuation ----------
    def _archive_run_log(self):
        """Preserve this run's biq client log so a same-boards A/B isn't lost
        when the NEXT run clears biq_N.log. Saves to tools/runs/ab/ and, once
        there's a prior archive, prints the ready-to-run live A/B compare."""
        try:
            arch = BIQ_ROOT / "tools/runs/ab"
            arch.mkdir(parents=True, exist_ok=True)
            src = self._watch_log()
            dst = arch / f"run_{time.strftime('%y%m%d_%H%M%S')}.log"
            dst.write_text(src.read_text(errors="replace"))
        except OSError as e:
            self._append(f"[panel] could not archive run log: {e}")
            return
        prev = getattr(self, "_last_ab_archive", None)
        self._last_ab_archive = dst
        self._append(f"[panel] run log archived for A/B: {dst}")
        if prev is not None and Path(prev).exists():
            self._append(
                "[panel] live A/B (needs the SAME Q-Plus boards in both runs): "
                f"python3 tools/live_ab_compare.py {prev} {dst} "
                "--label-a A --label-b B")

    def _session_finished(self):
        """Called when the autoclicker reports all deals done.

        'Exit automatically' OFF (default): leave Q-Plus running and do
        NOTHING automatic — the user presses ‘Export .qss’ then ‘Exit
        Q-Plus’ by hand (so unverified export/exit clicks can't lose data).

        ON: full hands-off — auto Export .qss, aggregate, then Exit Q-Plus
        (kill wine). A multi-session loop always auto-exports + kills between
        sessions (it can't continue otherwise), regardless of the tick."""
        # Always preserve this run's log first — so a same-boards A/B works
        # even in manual mode (where we return early and the next run would
        # otherwise overwrite biq_N.log).
        self._archive_run_log()
        looping_more = (self._loop_active
                        and self._session_idx < self._session_total)
        if not self.exit_auto.isChecked() and not looping_more:
            self._append("[panel] run complete — manual mode (Exit "
                         "automatically off): press ‘Export .qss’ then "
                         "‘Exit Q-Plus’ when ready.")
            self.hint.setText(
                "Run complete — Q-Plus left running. Press ‘Export .qss’, "
                "then ‘Exit Q-Plus (kill wine)’, when you're ready.")
            return

        # Automatic (or mid-loop): export the authoritative score sheet,
        # aggregate from it, archive.
        self.export_score_sheet()
        qss = self._newest_qss()
        self.aggregate_qss(qss)
        try:
            arch = BIQ_ROOT / "tools/runs/loop_results"
            arch.mkdir(parents=True, exist_ok=True)
            src = self._watch_log()
            (arch / f"biq_session_{self._session_idx}.log").write_text(
                src.read_text(errors="replace"))
            if qss is not None:
                self._session_qss.append(qss)
        except OSError:
            pass
        if looping_more:
            self._session_idx += 1
            self.hint.setText(
                f"Session done — cleaning wine, starting "
                f"{self._session_idx}/{self._session_total}…")
            self.kill_all_wine(confirm=False)
            QTimer.singleShot(5000, self._start_one_session)
            return
        if self._loop_active:
            self._loop_active = False
            self._aggregate_combined()
        # Fully done + auto exit: kill wine (the .qss is already saved above).
        self.hint.setText("Run complete — result below; exiting Q-Plus.")
        self.kill_all_wine(confirm=False)

    def _aggregate_combined(self):
        """Aggregate across every session's exported .qss (de-duped by deal
        id by the aggregator), the authoritative combined result."""
        if not self._session_qss:
            return
        seat = self._our_seat()
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setWorkingDirectory(str(BIQ_ROOT))
        proc.setArguments(["tools/qss_score_aggregate.py", "--qss",
                           *[str(p) for p in self._session_qss],
                           "--our-seat", seat])
        proc.start()
        proc.waitForFinished(20000)
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        self.result.setPlainText(
            f"=== COMBINED over {len(self._session_qss)} sessions ===\n{out}")

class ControlPanel(QMainWindow):
    """Standalone window wrapping the live-match widget (live-only use;
    the unified GUI is tools/qplus_mixed_corpus.py, which embeds the same
    LiveMatchWidget as its front tab)."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"bridgeIQ test harness   —   build {PANEL_BUILD}")
        self.resize(1280, 720)
        self.live = LiveMatchWidget(self)
        self.setCentralWidget(self.live)
        self._build_menu()
        # Clean slate on startup: kill any leftover wine so the :5555 socket
        # and Q-Plus's 64-board scoring cap start fresh. Runs once after the
        # window is up (no confirm). Standalone-only — not the embedded tab.
        self.live.hint.setText("Cleaning up any leftover wine…")
        QTimer.singleShot(250, lambda: self.live.kill_all_wine(confirm=False))

    def _build_menu(self):
        mb = self.menuBar()
        cfg_menu = mb.addMenu("⚙ Config")
        cfg_menu.addAction("Run settings & options…").triggered.connect(
            self.live.show_config_dialog)
        cfg_menu.addAction("Generate test deck (BDE)…").triggered.connect(
            self.live.show_deck_dialog)
        cal_menu = mb.addMenu("🎯 Calibrate")
        cal_menu.addAction("Calibration manager…").triggered.connect(
            self.live.open_calibrate)
        cal_menu.addSeparator()
        cal_menu.addAction("Show points — Server buttons").triggered.connect(
            lambda: self.live.show_calibration_overlay("server"))
        cal_menu.addAction("Show points — System dialog").triggered.connect(
            lambda: self.live.show_calibration_overlay("systems"))
        cal_menu.addAction("Show points — Match Control").triggered.connect(
            lambda: self.live.show_calibration_overlay("transition"))
        help_menu = mb.addMenu("&Help")
        act = help_menu.addAction("Button &reference…")
        act.triggered.connect(self._show_help)

    def _show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("bridgeIQ test harness — button reference")
        dlg.resize(720, 640)
        v = QVBoxLayout(dlg)
        intro = QLabel(
            "What every control does. This harness plays biq (North+South) "
            "vs Q-Plus over the Q-NET socket and scores the result by teams "
            "IMP from Q-Plus's .qss score sheet.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setFont(QFont("monospace"))
        body.setPlainText(HELP_TEXT)
        v.addWidget(body, 1)
        b = QPushButton("Close")
        b.clicked.connect(dlg.accept)
        v.addWidget(b)
        dlg.exec()

    def closeEvent(self, e):
        self.live.stop_all(silent=True)
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("bridgeIQ-test-harness")
    app.setStyle("Fusion")
    try:
        sys.path.insert(0, str(BIQ_ROOT))
        from ui.styles import apply_global_style
        apply_global_style(app)
    except Exception:
        pass
    w = ControlPanel()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
