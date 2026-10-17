# SETUPMODEL-1: the launcher's Garage tab -- iRacing's knobs, live derived numbers, JM_GARAGE only when modified.
# Headless (Qt offscreen), own config dir (never the PO's), QProcess.start stubbed. Run by tools/garage_smoke.jl.
import sys, os, tempfile
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="jr_garage_cfg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcess
app = QApplication([])
import juliaRacer as jr
jr.HERE = tempfile.mkdtemp(prefix="jr_garage_test_")
jr.JoyReader.start_reader = lambda self, *a, **k: None
jr.JoyReader.stop_reader = lambda self, *a, **k: None
started = []
QProcess.start = lambda self, prog, args=None: started.append((self, prog, args))
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

w = jr.Main(); d = w.drive; g = w.garage
check(not g.is_modified(), "a fresh garage is the session")
cw = [round(x) for x in g.D["cw"]]
check(cw == [1338, 1338, 1630, 1630] and round(g.D["cross"], 1) == 50.0, f"default session numbers shown exactly {cw}")
d.launch()
env = started[-1][0].processEnvironment()
check(not env.contains("JM_GARAGE"), "untouched garage: no JM_GARAGE (the sim races the session as is)")
d.proc = None; d.launch_b.setEnabled(True)
# iRacing 261017 snip 34: LF perch 165.1 -> 167.1 mm (5 clicks of 1/64") = 1326/1350/1640/1619 N, cross 50.4 %
sp = g.widgets[("perch", 0)]
for _ in range(5):
    sp.stepUp()
check(abs(g.K["perch"][0] - 167.084) < 0.01, f"5 clicks = 5/64 inch ({g.K['perch'][0]:.3f} mm)")
cw = [round(x) for x in g.D["cw"]]
check(all(abs(a - b) <= 3 for a, b in zip(cw, [1326, 1350, 1640, 1619])) and abs(g.D["cross"] - 50.4) <= 0.15,
      f"LF perch +2 mm moves the corner weights as iRacing's garage does: {cw} cross {g.D['cross']:.1f}")
check(g.is_modified() and "MODIFIED" in g.status.text(), "modified state shown")
d.launch()
env = started[-1][0].processEnvironment()
gf = env.value("JM_GARAGE")
check(bool(gf) and os.path.exists(gf), f"modified garage: JM_GARAGE handed to the sim ({os.path.basename(gf or '')})")
import garage as gm
base, K = gm.read_garage_file(gf)
check(base == "default" and abs(K["perch"][0] - 167.084) < 0.01, "the garage file carries the knob and its base")
d.proc = None; d.launch_b.setEnabled(True)
# camber shows iRacing's displayed value; a click moves it one step
c0 = g.D["camber"][1]
g.widgets[("camber", 1)].stepUp()
check(abs(g.D["camber"][1] - (c0 + 0.1)) < 0.02, f"RF camber click: {c0:.2f} -> {g.D['camber'][1]:.2f}")
# the garage persists per base; a new launcher resumes it
w2 = jr.Main()
check(w2.garage.is_modified() and abs(w2.garage.K["perch"][0] - 167.084) < 0.01, "the garage is remembered")
g.reset()
check(not g.is_modified(), "Reset = the session again")
d.launch()
check(not started[-1][0].processEnvironment().contains("JM_GARAGE"), "after Reset: no JM_GARAGE")
d.proc = None; d.launch_b.setEnabled(True)
# switching the base setup switches the garage
d.carsetup.setCurrentIndex(1)
cw = [round(x) for x in g.D["cw"]]
check(g.session_key == "ww103" and cw == [1351, 1324, 1641, 1619] and g.K["spring"][0] == 18.0,
      f"WW103 base: its own garage ({cw}, front springs {g.K['spring'][0]:.0f} N/mm)")
# 'use' off: a modified garage is not raced
g.widgets[("fuel", None)].setValue(100.0)
g.use.setChecked(False)
d.launch()
check(not started[-1][0].processEnvironment().contains("JM_GARAGE"), "'Use this garage' off: no JM_GARAGE")
print("GARAGE TAB:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
