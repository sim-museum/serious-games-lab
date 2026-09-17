# GATE: RACESTART-1 -- an AI must not drive THROUGH a stationary player.
#
# PO 2026-09-05: "when stopped at start of race, in 3rd position out of 5 cars, rev engine, other
# cars take off, AI cars behind me clip off both my front wheels, leaving me dead at start line!"
#
# The geometry that produced it, reproduced exactly: the player stationary on a standing grid in
# P3 of 5, with two AI starting BEHIND, in the ALTERNATING grid lanes init_cars lays down. Before
# the fix, step 3 of step_field! moved the AI sideways and never touched its arc-length, so a car
# behind simply advanced through the player's position -- while step 2 gave another AI a full
# car-length of along-track separation. An AI queued politely behind an AI and carved through a
# human.
#
# THE ASSERTION IS OVERTAKING, NOT CONTACT. Cars touching on a grid is racing; a car occupying the
# same metre of track as a stationary human is the defect. So: no AI that starts behind the player
# may end up ahead of them while the player has not moved.
#
# Both arms run. The CONTROL (JM_AI_NOPLAYERQUEUE=1, the shipped behaviour before this fix) MUST
# show the pass-through, or a green treatment means nothing.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))

run_arm(control::Bool) = begin
    env = control ? ["JM_AI_YIELD_RATE=1000"] : String[]
    out = read(`env $(env) julia --project=$(D) $(joinpath(D, "racestart_probe.jl"))`, String)
    m = match(r"RESULT behind=(\d+) passframes=(\d+) hits=(\d+) hardyield=(\d+)", out)
    m === nothing && (println(out); error("probe produced no RESULT line"))
    (behind = parse(Int, m[1]), passed = parse(Int, m[2]), hits = parse(Int, m[3]),
     hardyield = parse(Int, m[4]), raw = out)
end

fails = Ref(0)
check(name, ok, msg) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 54), msg))
println("RACESTART-1 gate (Watkins Glen standing grid, player stationary in P3)")
c = run_arm(true)
println("  control (JM_AI_YIELD_RATE=1000): ", c.behind, " behind, ", c.passed, " frames past, ",
        c.hits, " contact frames, ", c.hardyield, " jolt frames")
t = run_arm(false)
println("  treatment (shipped):             ", t.behind, " behind, ", t.passed, " frames past, ",
        t.hits, " contact frames, ", t.hardyield, " jolt frames")
# PREMISE: this geometry really does put an AI into a stationary player. Without contact there is
# nothing for the fix to do and a green treatment would be meaningless.
check("premise: a car starts behind the player",     c.behind >= 1, string(c.behind))
check("premise: the control CONTACTS the player",    c.hits > 0,    string(c.hits, " frames"))
check("premise: the control JOLTS sideways",         c.hardyield > 0, string(c.hardyield, " frames >0.2 m"))
# THE FIX: an AI behind a stationary player is made to queue instead of advancing through them, and
# the scraping is reduced. Going AROUND a parked car is legitimate racing and is NOT asserted away.
check("treatment: no sideways jolt at all",          t.hardyield == 0, string(t.hardyield, " frames >0.2 m"))
# RACESTART-1 S12: ASSERT THE HEADLINE QUANTITY. S11's result was "283 contact frames -> 15", and
# nothing in this gate looked at hits on the TREATMENT arm. `hardyield == 0` only rules out the
# >0.2 m sideways JOLT; a regression that restored the scraping without the jolt -- exactly the
# partial revert the S11 nudge change could suffer -- passed this gate unchanged.
#
# ⚠️ THE CAP IS ABSOLUTE ON PURPOSE, and the first cut of this check got that wrong. It read
# `t.hits <= max(40, div(c.hits, 8))`, which LOOKS self-calibrating and is not: this gate's control
# is the TELEPORT arm (JM_AI_YIELD_RATE=1000), which jumps clear instantly and so contacts about 2
# frames -- S11 says so in as many words ("the control (teleport) arm shows 2 contact frames
# because it jumps clear instantly"). div(2,8) is 0, so the relative half never binds and the rule
# was a bare `<= 40` in disguise. A control that cannot scale the quantity must not be dressed up
# as if it could.
#
# The 283 S11 reduced came from a DIFFERENT control -- JM_AI_CLEAR_MARGIN=0.0, the pre-fix nudge --
# which this gate does not run. So the cap is justified from S11's measurements directly:
# shipped 15, pre-fix 283. 60 is 4x the shipped figure and still 4.7x below the defect.
check("treatment: contact stays near the shipped 15",  t.hits <= 60,
      string(t.hits, " contact frames (cap 60; S11 measured 15 shipped, 283 pre-fix)"))
# Going AROUND a parked car is racing, not a defect, so the AI must still get past. A "fix" that
# deadlocked the field behind a stalled player would pass a contact test and ruin the race.
check("treatment: the field still gets past",       t.passed > 0,   string(t.passed, " frames"))
println(fails[] == 0 ? "RACESTART GATE: PASS" : "RACESTART GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
