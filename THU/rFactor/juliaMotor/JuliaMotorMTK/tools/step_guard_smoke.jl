# GATE: TERRAIN-STEP -- the physics must reject a building-sized upward step and accept every real crest.
# Thresholds come from step_probe.jl on the actual circuits (2026-09-05): steepest genuine up-step per
# 0.5 m -- zandvoort 1.05, nurburgring 1.19, watglen 0.17, spa 1.58 m; the defect to catch is the
# Ring's 8.4 m building plateau (E106-S18). Both arms: the guard must FIRE on the plateau and must
# NOT fire on any measured real step, or the number is wrong.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "step_guard.jl")); using .StepGuard
fails = Ref(0)
chk(n, ok, d) = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(n, 52), d); ok || (fails[] += 1))
T = 3.0
println("TERRAIN-STEP guard gate (threshold $(T) m)")
# real crests, from the probe -- every one must pass
for (track, step) in (("zandvoort",1.05), ("nurburgring",1.19), ("watglen",0.17), ("spa",1.58))
    ok, g = step_guard(100.0 + step, 100.0, T)
    chk("$track steepest real step ($(step) m) accepted", ok && g == 100.0 + step, "")
end
# the defect -- must be held
ok, g = step_guard(619.8 + 8.4, 619.8, T)
chk("Ring 8.4 m building plateau rejected", !ok && g == 619.8, "held at 619.8")
# descents of any size are never rejected (a cliff down is real ground)
ok, g = step_guard(100.0 - 20.0, 100.0, T)
chk("a 20 m drop is accepted", ok, "")
# first sample after a respawn (no history) is always accepted
ok, g = step_guard(700.0, NaN, T)
chk("first sample after respawn accepted", ok && g == 700.0, "")
# the margin: the worst real step is well inside the threshold
chk("margin: threshold >= 1.5x steepest real step", T >= 1.5 * 1.58, "$(T) vs $(round(1.5*1.58, digits=2))")
println(fails[] == 0 ? "STEP GUARD GATE: PASS" : "STEP GUARD GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
