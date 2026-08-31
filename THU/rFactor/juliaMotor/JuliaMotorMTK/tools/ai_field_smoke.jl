# GATE: E89 -- AI cars must not "dart around like june bugs, lunge ahead, then fall back".
#
# Headless: 4 kinematic AI on Monza for 270 s (after a 30 s warm-up), measured against a lone car's
# free-running speed at the same place. A LUNGE-FALL CYCLE is the deficit going >5 m/s and back <2.
# Rail switches are engage+release of a passing rail. Queue-snaps are the trailing car being
# teleported back a car length -- the visible jump.
#
# Both arms run. The CONTROL (κ speed model, no gap control -- what shipped before S2) must show the
# defect, or the treatment's clean numbers mean nothing; the TREATMENT (GPL race.lp speeds + gap
# control, the defaults) must be clean. Numbers from S2: control 1.83 cycles / 739 snaps per run;
# treatment 0.46 cycles / 0 snaps / 0.5 switches per car-lap.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
run_arm(env) = begin
    cmd = `env $(env) julia --project=$(D) $(joinpath(D, "e89_field_probe.jl"))`
    out = read(cmd, String)
    cyc = match(r"= ([0-9.]+) per car-lap;  worst", out); sw = match(r"release=\d+ = ([0-9.]+) per car-lap", out)
    qs  = match(r"queue-snaps (\d+)", out)
    (cycles = parse(Float64, cyc[1]), switches = parse(Float64, sw[1]), snaps = parse(Int, qs[1]), raw = out)
end
fails = Ref(0)
check(name, ok, msg) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 52), msg))
println("E89 AI field gate (Monza, headless, two arms)")
c = run_arm(["JM_AI_GPLLINE=0", "JM_AI_GAPCTL=0"])
println("  control:   cycles/car-lap ", c.cycles, "  switches/car-lap ", c.switches, "  queue-snaps ", c.snaps)
check("control shows lunge-fall cycles (premise)",  c.cycles > 1.0,  string(c.cycles))
check("control shows queue-snap teleports (premise)", c.snaps > 100, string(c.snaps))
t = run_arm(["JM_AI_GPLLINE=1", "JM_AI_GAPCTL=1"])
println("  treatment: cycles/car-lap ", t.cycles, "  switches/car-lap ", t.switches, "  queue-snaps ", t.snaps)
check("treatment: lunge-fall cycles < 1.0 per car-lap", t.cycles < 1.0, string(t.cycles))
check("treatment: no queue-snap teleports",             t.snaps == 0,   string(t.snaps))
check("treatment: rail switches < 2 per car-lap",       t.switches < 2.0, string(t.switches))
check("treatment beats control on cycles by 2x",       t.cycles * 2 < c.cycles, string(t.cycles, " vs ", c.cycles))
println(fails[] == 0 ? "AI FIELD GATE: PASS" : "AI FIELD GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
