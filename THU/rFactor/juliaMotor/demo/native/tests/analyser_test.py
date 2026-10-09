# REPLAY-2 S2: the analyser against a synthetic .jrt whose answers are known exactly -- a 1000 m circular lap driven at
# a constant 50 m/s by the player (20 s laps) and 40 m/s by one AI car (25 s laps). Checks the reader, lap detection
# with the line-crossing interpolation, the split times, the time difference, and that the window opens.
# REPLAY-3: lap 1 of a race is timed from the green flag; a practice out-lap and laps cut short (a crash, the end of the
# recording) are listed as untimed, never counted in a statistic, and a crash's reset is not distance driven.
# Run by JuliaMotorMTK/tools/launcher_smoke.jl (Qt offscreen).
import sys, os, json, math, struct, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import analyser as A

ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

L = 1000.0; R = L / (2 * math.pi); FPS = 15
TP = ["lap", "lapdist", "speed", "throttle", "brake", "steer", "clutch", "gear", "rpm", "lateral", "ontrack", "race"]
TA = ["s", "speed", "lap", "lane"]
speeds = [50.0, 40.0]; start = [7.0, 3.0]   # crossings fall BETWEEN frames, so the interpolation is exercised
n = 70 * FPS + 1
hdr = {"format": "jrt", "version": 1, "track": "synthetic", "laplen": L, "line_total": L, "fps": FPS, "ncar": 2,
       "nframes": n, "names": ["You", "Clark (Lotus)"], "pose": ["t", "x", "y", "z", "heading"],
       "tele_player": TP, "tele_ai": TA, "final": True,
       "refline": [[round(R * math.cos(2 * math.pi * k / 200), 2), round(R * math.sin(2 * math.pi * k / 200), 2)] for k in range(200)]}
def make(race=1, crash=None):
    """crash = (metres, seconds): the player stops dead there, and the last frame is reset to the line (as a sim exit)."""
    fd, path = tempfile.mkstemp(suffix=".jrt"); os.close(fd)
    with open(path, "wb") as f:
        f.write((json.dumps(hdr) + "\n").encode())
        for k in range(n):
            t = k / FPS; row = [t]; tele = []
            for c, v in enumerate(speeds):
                d = start[c] + v * t
                if c == 0 and crash is not None:
                    d = min(d, crash[0]); v = 0.0 if d >= crash[0] else v
                    if k == n - 1:
                        d = L - 0.01            # the reset jump: no car drives 400 m in a frame
                lap, dist = divmod(d, L); a = 2 * math.pi * dist / L
                row += [R * math.cos(a), 0.0, R * math.sin(a), a + math.pi / 2]
                tele += ([lap, dist, v, 1.0, 0.0, 0.1, 0.0, 4, 7000, 0.0, 1, race] if c == 0 else [dist, v, lap, 0.5])
            f.write(struct.pack("<%df" % (len(row) + len(tele)), *(row + tele)))
    return path

path = make()

rep = A.Replay(path)
check(rep.n == n and rep.ncar == 2 and rep.names[1] == "Clark (Lotus)", "reads the header and every frame")
pl = [lp for lp in rep.laps if lp.car == 0]; ai = [lp for lp in rep.laps if lp.car == 1]
check(rep.race and len(pl) == 3 and len(ai) == 2, f"a race: lap 1 timed from the green, then line to line: player {len(pl)}, AI {len(ai)}")
check(abs(pl[0].time - (L - 7.0) / 50) < 0.02 and pl[0].start and abs(ai[0].time - (L - 3.0) / 40) < 0.02,
      f"lap 1 from the start ({pl[0].time:.3f} s, {ai[0].time:.3f} s)")
check(all(abs(lp.time - 20.0) < 0.02 for lp in pl[1:]) and abs(ai[1].time - 25.0) < 0.02,
      f"lap times by line-crossing interpolation ({[round(lp.time, 3) for lp in rep.laps]})")
uf = sorted(rep.unfinished, key=lambda lp: lp.car)
check(len(uf) == 2 and all(lp.time is None for lp in uf) and abs(uf[0].reached - (7 + 50 * 70 - 3 * L)) < 8
      and abs(uf[1].reached - (3 + 40 * 70 - 2 * L)) < 8, f"the laps the recording ends in: unfinished "
      f"({[round(lp.reached) for lp in uf]} m), plotted only as far as they got ({[lp.dist[-1] for lp in uf]})")
check(all(abs(a - b) < 0.02 for a, b in zip(pl[1].splits, (5.0, 10.0, 15.0))), f"25/50/75 % splits ({[round(s, 3) for s in pl[1].splits]})")
secs = A.sector_times(pl[1], L)
check(all(abs(s - 5.0) < 0.03 for s in secs), "four equal sectors")
dl = A.delta(pl[1], ai[1]); k = int(500 / A.GRID_M)
check(abs(dl[k] - (500 / 40 - 500 / 50)) < 0.03, f"time difference at 500 m = 2.5 s ({dl[k]:.3f})")
check(abs(max(pl[1].ch["kmh"]) - 180.0) < 0.5 and abs(pl[1].ch["glat"][k] - 50 * 50 / R / 9.81) < 0.05,
      f"speed and lateral g on the grid (glat {pl[1].ch['glat'][k]:.3f} vs {50*50/R/9.81:.3f})")
# S3 reports
import re as _re
summ = A.race_summary(rep); plain = _re.sub("<[^>]+>", " ", summ)
check(plain.index("You") < plain.index("Clark (Lotus)") and "+" in plain, "summary: You P1, Clark behind with a gap")
check("No changes of position" in A.lap_by_lap(rep), "lap by lap: the faster car started ahead, so no passes")
sp = _re.sub("<[^>]+>", " ", A.speed_report(rep))
check(" 180 " in sp and " 144 " in sp, "speed report: top speeds 180 and 144 km/h")
lc = _re.sub("<[^>]+>", " ", A.lap_chart(rep))
check("Lap 1" in lc and "Lap 2" in lc, "lap chart lists the completed laps")
check([lp.num for lp in pl] == [1, 2, 3], f"laps numbered as racing does ({[lp.num for lp in pl]})")
w = A.AnalyserWindow(path); w.show(); app.processEvents()
for i in range(w.rep_combo.count()):
    w.rep_combo.setCurrentIndex(i); app.processEvents()
    check("could not be computed" not in w.report.toPlainText(), f"report '{w.rep_combo.currentText()}' renders")
check(len(w.selected()) == 2, "the window opens on a two-lap comparison")
check(w.times.rowCount() == len(rep.laps) + 2, "split-time table: every lap + each driver's best sectors")
check(w.table.rowCount() == len(rep.laps) + len(rep.unfinished), "the lap list shows the unfinished laps too")
# WGTD-1: AI laps hidden by default when the human has laps; the window compares the human's own two best laps
hid_ai = all(w.table.isRowHidden(r) == (lp.car != 0) for r, lp in enumerate(w.rows))
check(hid_ai and all(lp.car == 0 for lp in w.selected()) and len(w.selected()) == 2,
      f"lap filter: AI laps hidden, comparing your own laps ({[lp.label() for lp in w.selected()]})")
w.show_ai.setChecked(True); app.processEvents()
check(not any(w.table.isRowHidden(r) for r in range(len(w.rows))), "Show AI laps brings them back")
w.grab()                                            # paints every widget once (an exception would fail the test)
os.remove(path)

# REPLAY-3/4: a race started on a grid BEHIND the line (a restart puts every car there): the run to the line is not lap 1
start_saved = list(start); start[0] = L - 40.0; start[1] = L - 60.0
p4 = make(); r4 = A.Replay(p4); os.remove(p4); start[:] = start_saved
pl4 = [lp for lp in r4.laps if lp.car == 0]
check(len(pl4) >= 1 and pl4[0].num == 1 and abs(pl4[0].time - (L + 40.0) / 50) < 0.05,
      f"grid behind the line: lap 1 = run to the line + one lap ({[round(lp.time, 2) for lp in pl4]})")
# REPLAY-3: practice -- the first lap is an out-lap from the pits: listed, untimed
p2 = make(race=0); r2 = A.Replay(p2); os.remove(p2)
pl2 = [lp for lp in r2.laps if lp.car == 0]; out = [lp for lp in r2.unfinished if lp.car == 0 and lp.start]
check(not r2.race and len(pl2) == 2 and len(out) == 1 and out[0].full and A._untimed(out[0]) == "untimed",
      f"practice: the out-lap is listed untimed, two timed laps ({len(pl2)})")
# REPLAY-3: the PO's Ring race -- a crash in lap 1, no lap completed; the exit's reset to the line is not distance driven
p3 = make(crash=(600.0, 20.0)); r3 = A.Replay(p3)
mine = [lp for lp in r3.laps + r3.unfinished if lp.car == 0]
check(len(mine) == 1 and mine[0].time is None and abs(mine[0].reached - 600.0) < 8 and not mine[0].full,
      f"a crash in lap 1: one unfinished lap of {mine[0].reached:.0f} m, the reset ignored" if mine else "a crash in lap 1: listed")
w3 = A.AnalyserWindow(p3); w3.show(); app.processEvents()
sel = w3.selected()
check(len(sel) == 2 and sel[0].label() == mine[0].label(),
      f"no lap completed: the window opens on the player's attempt ({[lp.label() for lp in sel]})")
w3.speed_cb.setChecked(True); w3.tabs.setCurrentIndex(1); app.processEvents()
w3.grab()                                           # the speed-difference map with a short lap must not throw
import coach
check("completed no timed lap" in coach.build_summary(r3), "coach: says no lap was completed, sends no unfinished lap")
os.remove(p3)
print("ANALYSER:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
