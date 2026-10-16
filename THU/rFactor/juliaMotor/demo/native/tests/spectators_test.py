# SPECTATORS-1 (2026-10-16): the launcher's "Spectators, where they stand well off the road" switch -- default OFF (the PO's
# 2026-08-27 order), ON -> JM_SAFE_SPECTATORS=1, remembered, honoured by the replay path. Own XDG config dir (never the PO's).
import sys, os
import tempfile as _tf
os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp(prefix="jr_test_cfg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QProcessEnvironment, QSettings
app = QApplication([])
import juliaRacer as jr
class J:
    def __getattr__(self, k): return lambda *a, **kw: None
t = jr.DriveTab(J(), on_result=lambda *a: None)
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)
check(not t.gfx_spect.isChecked(), "default OFF (the PO's order stands)")
e = QProcessEnvironment(); t._gfx_env(e)
check(not e.contains("JM_SAFE_SPECTATORS"), "OFF -> no JM_SAFE_SPECTATORS")
t.gfx_spect.setChecked(True); e = QProcessEnvironment(); t._gfx_env(e)
check(e.value("JM_SAFE_SPECTATORS") == "1", "ON -> JM_SAFE_SPECTATORS=1")
check(QSettings("juliaRacer", "launcher").value("scene/spectators") == "true", "ON remembered")
t2 = jr.DriveTab(J(), on_result=lambda *a: None)
check(t2.gfx_spect.isChecked(), "a new launcher starts with it ON")
e = QProcessEnvironment(); jr.spectators_env(e, QSettings("juliaRacer", "launcher").value("scene/spectators", "false") == "true")
check(e.value("JM_SAFE_SPECTATORS") == "1", "the replay path honours ON")
print("SPECTATORS-1:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
