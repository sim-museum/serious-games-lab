# GUI-1 (PO 2026-10-06): the redesigned launcher must hand the sim exactly the environment the old one did, remember
# every choice, and keep the tabs a user needs. Headless (Qt offscreen); run by JuliaMotorMTK/tools/launcher_smoke.jl
# with a throw-away settings directory. QProcess.start is stubbed: nothing is launched.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess, QSettings
app = QApplication([])
import juliaRacer as jr
jr.JoyReader.start_reader = lambda self, *a, **k: None
jr.JoyReader.stop_reader = lambda self, *a, **k: None
started = []
QProcess.start = lambda self, prog, args=None: started.append((self, prog, args))
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

w = jr.Main(); d = w.drive
names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
check(names == ["Race", "Results", "Replays", "Settings", "Controller"], f"tabs {names}")
check(d.track.currentText() == "Zandvoort" and d.mode.currentText() == "Practice", "first run: Zandvoort practice")
check(d.launch_b.text() == "Start practice" and not d.laps.isVisibleTo(d), "practice: no race-only rows, 'Start practice'")
d.mode.setCurrentIndex(1)
check(d.launch_b.text() == "Start race" and d.laps.isVisibleTo(d) and d.qual.isVisibleTo(d), "race: race rows shown, 'Start race'")
check(d.ibt.isChecked() and d.replay.isChecked() and not d.mute.isChecked() and not d.d2.isChecked(), "default prefs")
check(not d.log.isVisibleTo(d), "log hidden until asked for")
check(not d.net_port.isVisibleTo(d), "LAN details hidden in single player")
# a race at Watkins Glen, 7 laps, 4 opponents, manual, WW103, muted, no replay
d.track.setCurrentIndex(3); d.laps.setValue(7); d.ai.setValue(4); d.gearbox.setCurrentIndex(1)
d.carsetup.setCurrentIndex(1); d.mute.setChecked(True); d.replay.setChecked(False)
d.launch()
check(len(started) == 1, "launch starts one process")
env = started[0][0].processEnvironment()
want = {"TRACK": "watglen", "JM_MODE": "race", "JM_LAPS": "7", "JM_AI": "4", "ZAND_SHIFT": "manual",
        "JM_CARSETUP": "ww103", "JM_NOSOUND": "1", "JM_NOREPLAY": "1"}
for k, v in want.items():
    check(env.value(k) == v, f"env {k}={env.value(k)!r} (want {v!r})")
for k in ("JM_NOFFB", "JM_NOIBT", "JM_2D", "JM_QUAL", "JM_NET", "JM_SEGNAME_SECS"):
    check(not env.contains(k), f"env has no {k}")
check(started[0][2][-1] == "drive_native_mtk.jl", "runs drive_native_mtk.jl")
d.proc = None; d.launch_b.setEnabled(True)
# a new launcher remembers all of it
w2 = jr.Main(); d2 = w2.drive
check((d2.track.currentIndex(), d2.mode.currentIndex(), d2.laps.value(), d2.ai.value(), d2.gearbox.currentIndex(),
       d2.carsetup.currentIndex()) == (3, 1, 7, 4, 1, 1), "session and car remembered")
check(d2.mute.isChecked() and not d2.replay.isChecked(), "preferences remembered")
print("LAUNCHER:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
