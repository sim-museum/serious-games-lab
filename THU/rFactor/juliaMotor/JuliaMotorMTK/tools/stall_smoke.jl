# GATE: E98 -- "if the user stalls out in manual mode, switch to auto mode immediately" (PO 2026-08-30).
#
# Headless: the rule is a pure function (DriveRT3D.stall_step), so this needs no window, no
# track and no GL. Every condition in the rule gets a control arm -- the treatment shows the
# switch fires, the controls show it does NOT fire when it must not, which is the half that
# actually protects the PO's other requests (revving with the clutch down, and wrecks).
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl"))
using .DriveRT3D
const D = DriveRT3D

const DT = 1/60
fails = Ref(0)
function arm(name, expect; auto=false, wrecked=false, rpm=100.0, clutch=0.0, secs=0.5, hold=1.0, speed=0.0, vmax=Inf)
    t = 0.0; fired = false; n = 0
    while n * DT < hold
        t, f = D.stall_step(t, DT; auto=auto, wrecked=wrecked, rpm=rpm, clutch=clutch, secs=secs, speed=speed, vmax=vmax)
        if f; fired = true; break; end
        n += 1
    end
    ok = (fired == expect)
    if !ok; fails[] += 1; end
    println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 52),
            "fired=", fired, " expected=", expect,
            fired ? string("  after ", round(n*DT, digits=3), "s") : "")
    ok
end

println("E98 stall -> auto gate")
# Treatment: manual, engine dead, clutch engaged, not wrecked.
arm("manual + dead engine + clutch engaged -> SWITCHES", true)
# Controls, one per condition. Each must NOT fire.
arm("already in AUTO -> no switch",                       false; auto=true)
# PO 2026-10-03: AUTO is for a stall at the START LINE, not at speed (rears locked under braking with the
# clutch out, or a tall gear held into a corner). With the caller's speed gate the rule must not fire.
arm("stall at 30 m/s (braking lock-up) -> NO switch",      false; speed=30.0, vmax=5.0)
arm("stall at 2 m/s (start line) -> switch",               true;  speed=2.0,  vmax=5.0)
arm("WRECKED (engine decoupled deliberately) -> no switch", false; wrecked=true)
arm("clutch OUT, low rpm (the PO's revving case) -> none", false; clutch=1.0)
arm("engine running (rpm above floor) -> no switch",       false; rpm=2500.0)
# Sustain: a brief dip must not trigger. 0.3s of stall against a 0.5s threshold.
arm("brief dip shorter than the threshold -> no switch",   false; hold=0.3)
# And the timer must RESET, not accumulate across a recovery: two 0.3s dips separated by a
# recovery frame add to 0.6s > 0.5s, and would fire if the reset were missing.
let t = 0.0, fired = false
    for _ in 1:18; t, f = D.stall_step(t, DT; auto=false, wrecked=false, rpm=100.0, clutch=0.0); f && (fired = true); end
    t, _ = D.stall_step(t, DT; auto=false, wrecked=false, rpm=2500.0, clutch=0.0)   # recovers
    for _ in 1:18; t, f = D.stall_step(t, DT; auto=false, wrecked=false, rpm=100.0, clutch=0.0); f && (fired = true); end
    ok = !fired
    if !ok; fails[] += 1; end
    println("  ", ok ? "PASS" : "FAIL", "  ", rpad("two short dips must NOT accumulate", 52),
            "fired=", fired, " expected=false")
end

println(fails[] == 0 ? "E98 GATE: PASS" : "E98 GATE: FAIL ($(fails[]) arm(s))")
exit(fails[] == 0 ? 0 : 1)
