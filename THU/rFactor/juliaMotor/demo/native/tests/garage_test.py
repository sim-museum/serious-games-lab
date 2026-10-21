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
# GPLSETUP-1: import a GPL Lotus setup (a synthetic .kj1 with WW103's values -- no GPL install needed)
import struct
b = bytearray(0x104)
b[0:4] = b"PGTS"
struct.pack_into("<9f", b, 0x0C, -3.0, 0.0, 2.2857, 1.7059, 1.4737, 1.2857, 1.16, 1.0, 3.1)
struct.pack_into("<2f", b, 0x54, 30.0, 85.0); struct.pack_into("<4f", b, 0x5C, 19.0, 20.0, 20.0, 20.0)
struct.pack_into("<4f", b, 0x6C, 50.0, 50.0, 120.0, 120.0); struct.pack_into("<4i", b, 0x7C, 3, 3, 4, 4)
struct.pack_into("<4i", b, 0x8C, 4, 4, 5, 5); struct.pack_into("<4f", b, 0x9C, -0.75, 0.0, -0.5, 0.25)
struct.pack_into("<2f", b, 0xDC, -0.5, 0.125); struct.pack_into("<2f", b, 0xE4, 200.0, 200.0)
struct.pack_into("<2f", b, 0xEC, 2.5, 2.5); struct.pack_into("<i", b, 0xF4, 4); struct.pack_into("<f", b, 0xF8, 4.0)
struct.pack_into("<f", b, 0xFC, 16.0); struct.pack_into("<i", b, 0x100, 54)
kj1 = os.path.join(tempfile.mkdtemp(prefix="jr_kj1_"), "ww103.kj1"); open(kj1, "wb").write(bytes(b))
d.carsetup.setCurrentIndex(0); g.use.setChecked(True)
notes = g.import_gpl_file(kj1)
check(g.K["spring"][:2] == [18.0, 18.0] and g.K["bump"] == [6, 6, 9, 9] and g.K["rebound"] == [9, 9, 12, 12] and
      (g.K["diff_drive"], g.K["diff_coast"]) == (35.0, 85.0) and g.K["final_drive"] == 3.78 and
      g.K["gears"] == [2.23, 1.40, 1.21, 1.04, 0.958] and abs(g.K["toe_rear"] - 3.0) < 0.01,
      f"GPL WW103 imports as its iRacing translation (springs {g.K['spring']}, dampers {g.K['bump']}/{g.K['rebound']}, final {g.K['final_drive']})")
check(all(abs(g.D["rh"][i] - [83.1, 83.1, 105.1, 105.1][i]) < 1.0 for i in range(4)),
      f"the import keeps the base car's ride heights by its perches ({[round(x, 1) for x in g.D['rh']]})")
check(any("outside iRacing's range" in n for n in notes) and any("bar" in n for n in notes), "the import reports what iRacing's ranges cut")
# SETUPLIST-1 (PO 2026-10-20: an imported fs_monza_lot was not in the Setup list): an import is a setup you can choose
items = [d.carsetup.itemText(i) for i in range(d.carsetup.count())]
check(d.carsetup.currentData() == "saved:ww103" and any(t.startswith("ww103") and "iRacing default" in t for t in items),
      f"the import is listed and chosen on the Race tab ({items}, chosen {d.carsetup.currentText()!r})")
d.proc = None; d.launch_b.setEnabled(True); d.launch()
env = started[-1][0].processEnvironment()
_, Kl = gm.read_garage_file(env.value("JM_GARAGE"))
check(env.value("JM_CARSETUP") == "default" and Kl["spring"][:2] == [18.0, 18.0] and Kl["final_drive"] == 3.78,
      "racing the imported setup: its base session + its knobs")
d.carsetup.setCurrentIndex(d.carsetup.findData("default"))
check(not g.is_modified() and g.K["final_drive"] != 3.78, "choosing the base again gives the base, not the import")
# a setup saved earlier (the PO's case: fs_monza_lot.toml, Save as on the WW103 base) is listed at the next start
w3 = jr.Main()
gm.write_garage_file(os.path.join(os.environ["XDG_CONFIG_HOME"], "juliaRacer", "garage", "fs_monza_lot.toml"),
                     dict(w3.garage.session["knobs"], fuel=33.0), base="ww103")
w4 = jr.Main(); d4 = w4.drive
k = d4.carsetup.findData("saved:fs_monza_lot")
check(k >= 0 and "WW103" in d4.carsetup.itemText(k), f"a saved setup is listed at start ({d4.carsetup.itemText(k) if k >= 0 else 'missing'})")
d4.carsetup.setCurrentIndex(k)
check(w4.garage.session_key == "ww103" and w4.garage.K["fuel"] == 33.0 and "fs_monza_lot" in w4.garage.base_lbl.text(),
      "choosing it loads its knobs on its own base")
w5 = jr.Main()
check(w5.drive.carsetup.currentData() == "saved:fs_monza_lot", "the choice is remembered")
print("GARAGE TAB:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
