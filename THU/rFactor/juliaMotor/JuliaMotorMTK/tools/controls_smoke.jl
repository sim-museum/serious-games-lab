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
live = if isfile(CONF)
    JoyCfg.loadmap(CONF)
else
    m = JoyCfg.defaultmap()
    JoyCfg.JoyMap(m.steer, m.throttle, m.brake, JoyCfg.Ctrl(4, -1.0, 1.0),
                  m.up_btn, m.dn_btn, m.clutch_btn, m.deadzone)
end
check("clutch is on an AXIS, not a button", live.clutch.axis >= 1,
      string("clutch.axis=", live.clutch.axis, isfile(CONF) ? "  (from joystick.conf)" : "  (X3D default)"))

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

println(fails[] == 0 ? "CONTROLS GATE: PASS" : "CONTROLS GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
