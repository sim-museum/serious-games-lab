# GATE: the PO's standing CONTROL requirements, as assertions.
#
#   PO 2026-08-27: "I like the clutch attached to a slider - that way I can ride the clutch.
#                   The clutch should be an axis."
#
# A standing requirement that nothing tests drifts. This one is one line away from being lost at
# any time: joystick.conf overrides the built-in mapping, and JoyCfg.Ctrl(0, ...) means "no axis,
# fall back to clutch_btn" -- which is 0 (unused) in the shipped map. So a recalibration that
# writes clutch.axis 0 removes the ridable clutch entirely, silently.
#
# Headless: pure config, no window and no car.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "joycfg.jl")); using .JoyCfg

const CONF = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "joystick.conf"))
fails = Ref(0)
function check(name, cond, msg)
    cond || (fails[] += 1)
    println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 50), msg)
end

println("PO control-requirements gate")

# The live mapping the sim will actually use, resolved the same way drive_native_mtk.jl resolves it.
# (Headless: no device name, so this is joystick.conf if present, else the X3D default.)
live, src = JoyCfg.resolve(CONF, "")
check("clutch is on an AXIS, not a button", live.clutch.axis >= 1,
      string("clutch.axis=", live.clutch.axis, "  (", src, ")"))

# An axis you can RIDE needs a real travel range: a degenerate a==b would normalise to a constant
# and behave like an on/off switch while still reporting an axis number.
span = abs(live.clutch.b - live.clutch.a)
check("clutch axis has usable travel", span > 0.5, string("|b-a| = ", round(span, digits=3)))

# Steering, throttle and brake must be axes too -- the same Ctrl(0,...) trap applies to them.
for (nm, c) in (("steer", live.steer), ("throttle", live.throttle), ("brake", live.brake))
    check("$nm is on an axis", c.axis >= 1, string(nm, ".axis=", c.axis))
end

# NEGATIVE CONTROL: the gate must reject a config that demotes the clutch. Without this, the
# check above would pass on any map at all if the field were read wrongly.
bad = JoyCfg.JoyMap(live.steer, live.throttle, live.brake, JoyCfg.Ctrl(0, 0.0, 1.0),
                    live.up_btn, live.dn_btn, live.clutch_btn, live.deadzone)
check("a clutch.axis=0 map is REJECTED", !(bad.clutch.axis >= 1), "detected as button/unused")

# AUTODETECT (PO 2026-10-03). The TX pedals rest at +1.0. Read through the X3D map that is FULL BRAKE
# on a released throttle and the clutch held in -- what the PO drove on 2026-10-03 after an update
# deleted joystick.conf. The TX device name must select the TX profile, and at rest it must give no
# throttle, no brake and no clutch; full pedals must give full outputs.
for nm in ("Thrustmaster Thrustmaster TX Racing Wheel", "Thrustmaster TX Racing Wheel")
    pr = JoyCfg.profile_for(nm)
    check("\"$nm\" -> TX profile", pr !== nothing && pr[1] == "Thrustmaster TX", string(pr === nothing ? "none" : pr[1]))
end
check("Logitech Extreme 3D -> X3D profile", (p = JoyCfg.profile_for("Logitech Logitech Extreme 3D pro"); p !== nothing && p[1] == "Logitech Extreme 3D Pro"), "")
check("unknown device -> no profile (X3D fallback, warned)", JoyCfg.profile_for("Some Gamepad") === nothing, "")
rest = Float32[0.0, 1.0, 1.0, 1.0]; floor_ = Float32[0.0, -1.0, -1.0, 0.29814]   # TX axes: wheel, throttle, clutch, brake -- floored
_, thr, brk, clu, _, _ = JoyCfg.apply(JoyCfg.txmap(), rest, nothing)
check("TX at rest: throttle 0, brake 0, clutch 0", thr == 0 && brk == 0 && clu < 0.01, "thr=$thr brk=$brk clu=$(round(clu, digits=3))")
_, thr, brk, clu, _, _ = JoyCfg.apply(JoyCfg.txmap(), floor_, nothing)
check("TX pedals floored: throttle 1, brake 1, clutch 1", thr > 0.99 && brk > 0.99 && clu > 0.99, "thr=$thr brk=$brk clu=$(round(clu, digits=3))")
_, thr, brk, clu, _, _ = JoyCfg.apply(JoyCfg.x3dmap(), rest, nothing)
check("NEGATIVE CONTROL: X3D map on a resting TX = full brake", brk > 0.99 && clu > 0.99, "thr=$thr brk=$brk clu=$clu (the 2026-10-03 bug)")

# PHYSICAL STEERING (PO 2026-10-03 fishtailing): a wheel's road angle = wheel angle / steering ratio,
# INDEPENDENT of where the calibration's endpoints were captured. 900° TX, 10:1, sim lock 0.30 rad:
# full lock at 0.30·10 rad = 172° of wheel = raw 172/450 = 0.382; 10% of that raw gives 10% of lock.
gain = 450.0 / 10.0 / rad2deg(0.30)
for (lab, m) in (("TX profile (June endpoints ±1.0)", JoyCfg.txmap()),
                 ("PO's 2026-10-03 calibration (endpoints ±0.22)", JoyCfg.JoyMap(JoyCfg.Ctrl(1, -0.22307, 0.21367),
                  JoyCfg.txmap().throttle, JoyCfg.txmap().brake, JoyCfg.txmap().clutch, 2, 1, 0, 0.06)))
    c0 = 0.5*(m.steer.a + m.steer.b)
    full = JoyCfg.steer_physical(m, Float32[c0 - 0.382, 1, 1, 1], gain)
    tenth = JoyCfg.steer_physical(m, Float32[c0 - 0.0382, 1, 1, 1], gain)
    check("$lab: 172° left = full lock, 17° = 10 %", abs(full - 1.0) < 0.01 && abs(tenth - 0.1) < 0.005, "full=$(round(full, digits=3)) tenth=$(round(tenth, digits=3))")
end
check("wheel range: TX name -> 450° half range (sysfs or default)", JoyCfg.wheel_half_range_deg("Thrustmaster Thrustmaster TX Racing Wheel") == 450.0, "")
check("joystick -> no physical steering", JoyCfg.wheel_half_range_deg("Logitech Logitech Extreme 3D pro") == 0.0, "")

# MANUAL SHIFT GATE (PO 2026-10-03): blip, held clutch, and rev-matched clutchless shifts pass; a
# clutchless shift with the revs far off is refused (the realism the gate exists for).
check("clutch held (0.5) -> shift",                  JoyCfg.shift_ok(0.5, 99.0, 5000.0, 7000.0), "")
check("clutch blipped 0.2 s ago -> shift",           JoyCfg.shift_ok(0.0, 0.2, 5000.0, 7000.0), "")
check("blip 0.5 s ago, revs off -> REFUSED",         !JoyCfg.shift_ok(0.0, 0.5, 5000.0, 7000.0), "")
check("no clutch, revs matched (6500 vs 7000) -> shift", JoyCfg.shift_ok(0.0, 99.0, 6500.0, 7000.0), "")
check("no clutch, revs 30 % off -> REFUSED",         !JoyCfg.shift_ok(0.0, 99.0, 4900.0, 7000.0), "")
check("no clutch at a crawl (target < 1500) -> REFUSED", !JoyCfg.shift_ok(0.0, 99.0, 1200.0, 1100.0), "")

println(fails[] == 0 ? "CONTROLS GATE: PASS" : "CONTROLS GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
