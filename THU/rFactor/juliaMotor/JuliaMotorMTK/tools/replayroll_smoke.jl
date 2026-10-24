# replayroll_smoke.jl -- REPLAYROLL-1 gate (2026-10-23). PO: in the Monza race the car rolled over and lay upside down
# (cockpit and outside view), but "the replay shows the car levitating after hitting the hedge, and coming to a stop in
# midair 1-2 m above the ground": the replay recorded x, y, z, heading only, so a wreck played back upright at its CG's
# height. A wreck's pose is now its rigid body's, with pitch / roll / body channels (each AI car's pitch / roll too).
#   1. RECORD: a Monza race whose wreck starts rolling (JM_WRECK_ROLL, smoke-only): the live body passes upside down,
#      and the recording carries the body channels with that roll;
#   2. PLAY BACK: the drawn car (JM_REPLAY_BODYDIAG: its model matrix's up axis) goes upside down too;
#   3. CONTROL (the known positive): JM_REPLAY_ROLL=0 (played as before) draws it upright throughout.
using Serialization
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 62), detail); ok || (fails[] += 1); ok)
const BASE = Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_NOSOUND" => "1", "JM_NOIBT" => "1", "JM_FIXED_DT" => "0.016666666666666666")
function sim(extra)
    log = tempname()
    p = run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, merge(Dict(ENV), BASE, extra); dir = D));
                     stdout = log, stderr = log))
    L = readlines(log); rm(log; force = true)
    foreach(l -> println("    ", l), first(filter(l -> occursin("ERROR", l), L), 3))
    (p.exitcode, L)
end
println("REPLAYROLL-1 gate: a wreck replays as it lay (rolled, upside down), not upright in the air")
rec = mktempdir()
(rc, L) = sim(Dict("JM_MODE" => "race", "JM_AI" => "1", "JM_LAPS" => "1", "JM_AUTODRIVE" => "1", "JM_WRECK_AT" => "10",
                   "JM_WRECK_ROLL" => "8", "JM_CRASHBODY_DIAG" => "1", "JM_REPLAY_REC" => "1", "JM_IBT_DIR" => rec,
                   "JM_SMOKE_FRAMES" => "1300"))
chk("the recorded race exits cleanly", rc == 0 && any(==("bye"), strip.(L)), "exit $rc")
rolls = [abs(parse(Float64, m[1])) for m in (match(r"\[crashbody\] t .* roll (-?[0-9.]+) ", l) for l in L) if m !== nothing]
chk("live: the wreck rolls past 120 deg (the known positive)", !isempty(rolls) && maximum(rolls) > 120,
    isempty(rolls) ? "no [crashbody] lines" : "max |roll| $(maximum(rolls)) deg")
jmr = filter(f -> endswith(f, ".jmr"), readdir(rec; join = true))
chk("a replay was written", length(jmr) == 1, "$(length(jmr)) .jmr")
if length(jmr) == 1
    r = deserialize(jmr[1]); nt = length(r.tele_p) + length(r.tele_ai)*(r.ncar - 1)
    kp = findfirst(==("roll"), r.tele_p); kb = findfirst(==("body"), r.tele_p)
    ok = kp !== nothing && kb !== nothing && "roll" in r.tele_ai
    rr = ok ? [abs(rad2deg(r.tele[f*nt+kp])) for f in 0:r.nframes-1 if r.tele[f*nt+kb] > 0.5] : Float64[]
    chk("the recording carries the body's roll past 120 deg", !isempty(rr) && maximum(rr) > 120,
        ok ? "$(length(rr)) body frames, max |roll| $(isempty(rr) ? 0 : round(maximum(rr), digits = 1)) deg" : "no pitch/roll/body channels")
    ups = Dict{String,Vector{Float64}}()
    @sync for c in ("1", "0")
        @async begin
            (rc2, L2) = sim(Dict("JM_REPLAY" => jmr[1], "JM_REPLAY_ROLL" => c, "JM_REPLAY_BODYDIAG" => "1", "JM_SMOKE_FRAMES" => "840"))
            ups[c] = [parse(Float64, m[1]) for m in (match(r"\[replaybody\] frame \d+ up_y (-?[0-9.]+)", l) for l in L2) if m !== nothing]
            chk("playback (JM_REPLAY_ROLL=$c) exits cleanly", rc2 == 0 && any(==("bye"), strip.(L2)), "exit $rc2")
        end
    end
    u1 = get(ups, "1", Float64[]); u0 = get(ups, "0", Float64[])
    chk("replay: the drawn wreck goes upside down (up axis < -0.5)", !isempty(u1) && minimum(u1) < -0.5,
        isempty(u1) ? "no [replaybody] lines" : "min up_y $(minimum(u1))")
    chk("control (JM_REPLAY_ROLL=0): drawn upright throughout (the old replay)", !isempty(u0) && minimum(u0) > 0.9,
        isempty(u0) ? "no [replaybody] lines" : "min up_y $(minimum(u0))")
end
rm(rec; recursive = true, force = true)
println(fails[] == 0 ? "\n  REPLAYROLL GATE: PASS" : "\n  REPLAYROLL GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
