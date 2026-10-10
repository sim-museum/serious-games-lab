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

# S2: the wizard is GPL's/iRacing's sweep. A synthetic TX and a synthetic Extreme 3D Pro go through it; each must come out
# behaving like its built-in profile (rest = nothing, floored = full, steering the same way), found by movement alone.
def feed(t, axes=None, buttons=None):
    if axes is not None:
        t.joy.axes = list(axes)
    if buttons is not None:
        t.joy.buttons = list(buttons)
    t.refresh()

def run_wizard(name, rest, sweep_moves, steer_left, wheel90, pedals, up_btn, dn_btn):
    j = Joy(); j.present = True; j.name = name; j.axes = list(rest); j.buttons = [0] * 12
    t = jr.CalibrateTab(j, lambda: None)
    t.start_wizard(); feed(t, rest); t.capture()                       # rest snapshot
    for ax in sweep_moves:
        feed(t, ax)
    feed(t, rest); t.capture()                                          # sweep done -> steer
    feed(t, rest); feed(t, steer_left)                                  # arm, then turn left
    if wheel90 is None:
        t.skip()
    else:
        feed(t, wheel90); t.capture()
    for ax in pedals:                                                   # throttle, brake, clutch: release, press
        feed(t, rest); feed(t, ax)
    feed(t, rest)
    b = [0] * 12; b[up_btn - 1] = 1; feed(t, buttons=[0] * 12); feed(t, buttons=b); feed(t, buttons=[0] * 12)
    b = [0] * 12; b[dn_btn - 1] = 1; feed(t, buttons=b); feed(t, buttons=[0] * 12)
    return t

def same_behaviour(m, ref, rest, floored, left):
    r1 = m.apply(rest, [0] * 12)[:4]; r2 = ref.apply(rest, [0] * 12)[:4]
    f1 = m.apply(floored, [0] * 12)[1:4]
    s1 = m.apply(left, [0] * 12)[0]; s2 = ref.apply(left, [0] * 12)[0]
    return all(abs(x) < 0.03 for x in r1[1:]) and all(x > 0.97 for x in f1) and s1 * s2 > 0, (r1, f1, s1, s2)

TXREST = [0.0, 1.0, 1.0, 1.0]
t = run_wizard(TX, TXREST,
               [[-1, 1, 1, 1], [1, 1, 1, 1], [0, -1, 1, 1], [0, 1, -1, 1], [0, 1, 1, 0.29814]],
               [-0.7, 1, 1, 1], [-0.2, 1, 1, 1],
               [[0, -1, 1, 1], [0, 1, 1, 0.29814], [0, 1, -1, 1]], 2, 1)
m = t.work; ref = jr.JoyMap.load(os.path.join(jr.BUILTIN_DIR, "thrustmaster_tx.conf"))
check(jr.STEPS[t.step][0] == "done", f"TX: the wizard reaches Done by movement alone (at {jr.STEPS[t.step][0]})")
check((m.steer.axis, m.throttle.axis, m.brake.axis, m.clutch.axis, m.up_btn, m.dn_btn) == (1, 2, 4, 3, 2, 1),
      f"TX: wheel 1, throttle 2, brake 4, clutch 3, up 2, down 1 ({t._summary()})")
okb, why = same_behaviour(m, ref, TXREST, [0, -1, -1, 0.29814], [-0.5, 1, 1, 1])
check(okb, f"TX: behaves like the built-in profile (rest 0, floored 1, steers the same way) {why}")
check(abs(m.wheel_half_deg - 450.0) < 1e-6, f"TX: the 90° step measures a 900° wheel ({2 * m.wheel_half_deg:.0f}°)")
check(abs(m.throttle.a - 0.96) < 1e-9 and abs(m.throttle.b + 0.96) < 1e-9, "TX: GPL's 2 % saturation at both pedal ends")
kinds = [t.sweep.kind(i) for i in range(4)]
check(kinds == ["centred", "pedal", "pedal", "pedal"], f"TX: GPL's rule classifies wheel/pedals {kinds}")
t.save()
check(abs(jr.JoyMap.load(jr.CONF).wheel_half_deg - 450.0) < 1e-6, "TX: the wheel range is saved")

X3D = "Logitech Logitech Extreme 3D pro"; XREST = [0.0, 0.0, 0.0, -1.0]
t = run_wizard(X3D, XREST,
               [[-1, 0, 0, -1], [1, 0, 0, -1], [0, -1, 0, -1], [0, 1, 0, -1], [0, 0, -1, -1], [0, 0, 1, -1], [0, 0, 0, 1]],
               [-0.8, 0, 0, -1], None,
               [[0, -1, 0, -1], [0, 1, 0, -1], [0, 0, 0, 1]], 1, 2)
m = t.work; ref = jr.JoyMap.load(os.path.join(jr.BUILTIN_DIR, "logitech_extreme_3d_pro.conf"))
check(jr.STEPS[t.step][0] == "done", f"X3D: reaches Done (at {jr.STEPS[t.step][0]})")
check((m.steer.axis, m.throttle.axis, m.brake.axis, m.clutch.axis, m.up_btn, m.dn_btn) == (1, 2, 2, 4, 1, 2),
      f"X3D: roll 1, push/pull 2 (one axis, two halves -- GPL's N</N>), slider 4 ({t._summary()})")
r = m.apply(XREST, [0] * 12); fw = m.apply([0, -1, 0, -1], [0] * 12); bk = m.apply([0, 1, 0, -1], [0] * 12)
check(r[1] == 0 and r[2] == 0 and r[3] < 0.03 and fw[1] > 0.97 and fw[2] == 0 and bk[2] > 0.97 and bk[1] == 0,
      f"X3D: centred = nothing; push = throttle only; pull = brake only ({r[:4]} {fw[:4]} {bk[:4]})")
check(m.apply([-0.5, 0, 0, -1], [0] * 12)[0] * ref.apply([-0.5, 0, 0, -1], [0] * 12)[0] > 0, "X3D: steers the same way as the profile")
check(m.wheel_half_deg == 0.0, "X3D: Skip = not a wheel (endpoint steering)")
# a pedal pressed before the previous one was released is not taken (iRacing/GPL: one control at a time)
j = Joy(); j.present = True; j.name = TX; j.axes = list(TXREST); j.buttons = [0] * 12
t = jr.CalibrateTab(j, lambda: None); t.start_wizard(); feed(t, TXREST); t.capture()
for ax in ([-1, 1, 1, 1], [1, 1, 1, 1], [0, -1, 1, 1], [0, 1, -1, 1], [0, 1, 1, 0.3]):
    feed(t, ax)
feed(t, TXREST); t.capture(); feed(t, [-0.7, 1, 1, 1])
check(jr.STEPS[t.step][0] == "steer", "NEGATIVE CONTROL: no assignment before the controls were seen at rest")
sys.exit(0 if ok else 1)
