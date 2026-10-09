# GUI-1 (PO 2026-10-06): the redesigned launcher must hand the sim exactly the environment the old one did, remember
# every choice, and keep the tabs a user needs. Headless (Qt offscreen); run by JuliaMotorMTK/tools/launcher_smoke.jl
# with a throw-away settings directory. QProcess.start is stubbed: nothing is launched.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess, QSettings
app = QApplication([])
import juliaRacer as jr
import tempfile
# launch() writes last_sim_run.log and DELETES last_race_result.txt in HERE: point it at a scratch directory so the test
# can never touch the real demo/native (a first version of this test clobbered the tracked log).
jr.HERE = tempfile.mkdtemp(prefix="jr_launcher_test_")
open(os.path.join(jr.HERE, "last_race_result.txt"), "w").write("sentinel")
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
check(env.value("JM_TIMING") == "1", "LOADHANG-1: the race logs its load stages (JM_TIMING=1)")
check(started[0][2][-1] == "drive_native_mtk.jl", "runs drive_native_mtk.jl")
d.proc = None; d.launch_b.setEnabled(True)
# a new launcher remembers all of it
w2 = jr.Main(); d2 = w2.drive
check((d2.track.currentIndex(), d2.mode.currentIndex(), d2.laps.value(), d2.ai.value(), d2.gearbox.currentIndex(),
       d2.carsetup.currentIndex()) == (3, 1, 7, 4, 1, 1), "session and car remembered")
check(d2.mute.isChecked() and not d2.replay.isChecked(), "preferences remembered")
real = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
check(os.path.realpath(started[0][0].workingDirectory()) == os.path.realpath(jr.HERE), "the sim's working dir is the scratch HERE")
check(not os.path.exists(os.path.join(jr.HERE, "last_race_result.txt")), "launch clears the (scratch) stale result")
# REPLAY-2 S1: the Replays tab lists every recording newest first, labels it, and pre-selects the session just finished
import time as _time
rd = tempfile.mkdtemp(prefix="jr_replays_"); now = _time.time()
for name, age in (("replay_watglen 5ai 2026-10-05 08-54-36.jmr", 3000), ("replay_zandvoort 0ai 2026-10-06 23-58-31.jmr", 10),
                  ("replay_monza 2ai 2026-10-06 12-00-00.jmr", 600)):
    fp = os.path.join(rd, name); open(fp, "w").write("x"); os.utime(fp, (now - age, now - age))
rt = w.replay; rt.dir = rd; files = rt.refresh()
check(files[0].startswith("replay_zandvoort") and files[-1].startswith("replay_watglen"), "replays newest first")
check(rt.combo.itemText(0) == "Zandvoort  ·  solo  ·  2026-10-06 23:58", f"readable label ({rt.combo.itemText(0)!r})")
check(rt.show_latest(since=now - 60) == files[0] and rt.combo.currentIndex() == 0, "the session just finished is selected")
check(rt.show_latest(since=now + 3600) is None, "an old recording is not claimed as this session's")
check(w.drive.on_session_end == rt.show_latest, "the Race tab hands the end of a session to the Replays tab")
started.clear(); rt.combo.setCurrentIndex(1); rt.watch()
env = started[0][0].processEnvironment()
check(env.value("JM_REPLAY").endswith("replay_monza 2ai 2026-10-06 12-00-00.jmr") and env.value("TRACK") == "monza"
      and env.value("JM_AI") == "2", "Watch plays the selected file with its track and field")
check(env.value("JM_TIMING") == "1", "LOADHANG-1: the replay logs its load stages too")
rt.proc = None
# DOC-RACE-1: Help > How to race opens the shipped guide
acts = [a.text() for m in w.menuBar().actions() for a in (m.menu().actions() if m.menu() else [])]
check("&How to race…" in acts, "Help menu has How to race")
g = jr.guide_dialog(w); txt = g.findChild(jr.QWidget, "guide").toPlainText()
check(os.path.exists(jr.GUIDE) and "Smoothness + balance = speed" in txt and "Shift + R" in txt, "the guide loads and renders")
# GUI-1 S2: the IQ-style theme loads, references only images that ship, and JR_THEME=classic opts out
import re as _re
jr.apply_theme(app); qss = app.styleSheet()
check(len(qss) > 1000 and "@UI@" not in qss, "theme applied")
imgs = _re.findall(r"url\(([^)]+)\)", qss)
check(imgs and all(os.path.exists(f) for f in imgs), f"theme images exist ({len(imgs)})")
check("QPushButton#primary" in qss and w.drive.launch_b.objectName() == "primary", "Start is the primary button")
app.setStyleSheet(""); os.environ["JR_THEME"] = "classic"; jr.apply_theme(app)
check(app.styleSheet() == "", "JR_THEME=classic keeps the platform look")
print("LAUNCHER:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
