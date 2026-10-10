# CTRLCAL-1 (PO 2026-10-10): the Controller tab offers two ways -- Autodetect or a Saved profile (Thrustmaster TX,
# Logitech Extreme 3D Pro, and every calibration the wizard saved). Headless (Qt offscreen); run by launcher_smoke.jl.
# joystick.conf and joystick_profiles/ are pointed at a scratch directory: the PO's real calibration is never touched.
import sys, os, tempfile
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="jr_test_cfg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication, QMessageBox
app = QApplication([])
import juliaRacer as jr
scratch = tempfile.mkdtemp(prefix="jr_ctrlcal_test_")
jr.CONF = os.path.join(scratch, "joystick.conf")
jr.PROFILE_DIR = os.path.join(scratch, "joystick_profiles")
jr.JoyReader.start_reader = lambda self, *a, **k: None
jr.JoyReader.stop_reader = lambda self, *a, **k: None
QMessageBox.information = staticmethod(lambda *a, **k: None)
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

TX = "Thrustmaster Thrustmaster TX Racing Wheel"
class Joy(jr.JoyReader):
    pass
joy = Joy(); joy.present = True; joy.name = TX; joy.axes = [0.0, 1.0, 1.0, 1.0]; joy.buttons = [0] * 12
saved = []
t = jr.CalibrateTab(joy, lambda: saved.append(1))
check(t.auto_r.isChecked() and not t.profile.isEnabled(), "no conf: Autodetect is the default, the profile list is off")
check(not os.path.exists(jr.CONF), "opening the tab writes nothing")
labs = [t.profile.itemText(i) for i in range(t.profile.count())]
check(labs[:2] == ["Logitech Extreme 3D Pro  (built-in)", "Thrustmaster TX  (built-in)"], f"built-in profiles listed {labs}")
check("autodetected Thrustmaster TX" in t.usingl.text(), f"says what the game will use: {t.usingl.text()!r}")
_, thr, brk, clu, _, _ = t.work.apply(joy.axes, joy.buttons)
check(thr == 0 and brk == 0 and clu < 0.01, "the TX at rest previews no throttle, brake or clutch")

# Saved profile: pick the X3D profile and use it -- on a TX, because the driver chose it
t.prof_r.setChecked(True)
check(t.profile.isEnabled() and t.use_b.isEnabled(), "Saved profile enables the list")
t.profile.setCurrentIndex(0); t.use_b.click()
meta = jr.load_meta(jr.CONF)
check(meta.get("mode") == "profile" and meta.get("label") == "Logitech Extreme 3D Pro", f"conf records the profile {meta}")
m = jr.JoyMap.load(jr.CONF)
check(m.clutch.axis == 4 and m.throttle.axis == 2 and m.up_btn == 1, "conf holds the X3D map")
check('saved profile "Logitech Extreme 3D Pro"' in t.usingl.text() and saved, "the game will use the profile; the launcher is told")
t2 = jr.CalibrateTab(joy, lambda: None)
check(t2.prof_r.isChecked() and t2.profile.currentText().startswith("Logitech Extreme 3D Pro"), "a new launcher remembers the choice")

# back to Autodetect: the profile stops applying; the TX gets its built-in profile
t.auto_r.setChecked(True)
check(jr.load_meta(jr.CONF).get("mode") == "autodetect" and "autodetected Thrustmaster TX" in t.usingl.text(),
      f"Autodetect again: {t.usingl.text()!r}")

# the wizard's calibration belongs to its device and joins the profile list
t.work = jr.JoyMap.load(os.path.join(jr.BUILTIN_DIR, "thrustmaster_tx.conf")); t.work.brake = jr.Ctrl(4, 1.0, 0.86)
t.step = 10; t.save()
dev = jr.device_file(TX)
check(os.path.isfile(dev) and jr.load_meta(dev).get("device") == TX, "wizard save -> joystick_profiles/<device>.conf")
check(jr.load_meta(jr.CONF).get("mode") == "autodetect" and jr.load_meta(jr.CONF).get("device") == TX, "and the autodetect conf")
check(abs(jr.JoyMap.load(jr.CONF).brake.b - 0.86) < 1e-9, "with the captured values")
labs = [t.profile.itemText(i) for i in range(t.profile.count())]
check(any(l.endswith("(your calibration)") and TX in l for l in labs), f"listed as a saved profile {labs[2:]}")
check("autodetect: calibration of" in t.usingl.text(), f"the game will use it: {t.usingl.text()!r}")
# another device plugged in: its own built-in profile, not the TX calibration
joy.name = "Logitech Logitech Extreme 3D pro"; t.refresh()
check("autodetected Logitech Extreme 3D Pro" in t.usingl.text(), f"X3D plugged in: {t.usingl.text()!r}")
sys.exit(0 if ok else 1)
