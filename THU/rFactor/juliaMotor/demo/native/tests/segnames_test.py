# TRACKSEG-3 (PO 2026-10-06): the launcher's "Show track section names" switch -- default ON, OFF -> JM_SEGNAME_SECS=0,
# remembered, honoured by the replay path. Run headless by JuliaMotorMTK/tools/launcher_smoke.jl (own XDG config dir).
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcessEnvironment, QSettings
app = QApplication([])
import juliaRacer as jr
class J:            # stand-in for the joystick reader: DriveTab only stores it at construction
    def __getattr__(self, k): return lambda *a, **kw: None
t = jr.DriveTab(J(), on_result=lambda *a: None)
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)
check(t.gfx_segnames.isChecked(), "default ON")
e = QProcessEnvironment(); t._gfx_env(e)
check(not e.contains("JM_SEGNAME_SECS"), "ON -> no JM_SEGNAME_SECS (sim default 3 s)")
t.gfx_segnames.setChecked(False); e = QProcessEnvironment(); t._gfx_env(e)
check(e.value("JM_SEGNAME_SECS") == "0", "OFF -> JM_SEGNAME_SECS=0")
check(QSettings("juliaRacer", "launcher").value("hud/segnames") == "false", "OFF remembered")
t2 = jr.DriveTab(J(), on_result=lambda *a: None)
check(not t2.gfx_segnames.isChecked(), "a new launcher starts with it OFF")
e = QProcessEnvironment(); jr.segnames_env(e, QSettings("juliaRacer", "launcher").value("hud/segnames", "true") == "true")
check(e.value("JM_SEGNAME_SECS") == "0", "the replay path honours OFF")
print("TRACKSEG-3:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
