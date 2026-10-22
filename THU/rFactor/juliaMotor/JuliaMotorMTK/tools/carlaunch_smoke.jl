# GATE: CARLAUNCH-1 -- a car launched by a wheel-on-wheel hit flies as a rigid body: it pitches and rolls with the hit,
# lands, and drives on.
#
# PO 2026-10-21: "after a collision, the player's car lacks rotational degrees of freedom. In the monza collision from last
# night, the player car collided with an AI car, with point of contact the front left wheel of the player car. The player
# car should have pitched up and rolled right". The PO's hit (Monza 2026-10-20 22:29, t 230.71): 225 km/h, closing
# 5.1 m/s, the left-front ride height 0.08 -> 0.56 m in one frame. Here JM_RAM_AI puts the player 3.3 m behind AI 1 with
# its left-front wheel behind the AI's right-rear (1.53 m to the right), closing at 5.1 m/s.
# Control: JM_AIRBODY=0 (the small-angle driving model throughout, drawn tilt capped at ~6 deg) must not launch.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 64), d))
function race(extra)
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_MODE" => "race", "JM_AI" => "3", "JM_LAPS" => "1",
                                "JM_RAM_AI" => "1:5.1:-1.53:6:-3.3", "JM_SMOKE_FRAMES" => "900",
                                "JM_FIXED_DT" => string(1/60)), extra)
    log = tempname()
    run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
    read(log, String)
end
println("CARLAUNCH gate: a wheel-on-wheel launch flies as a rigid body and lands")
t = race(Dict{String,String}())
check("the ram ran", occursin("[ram]", t))
m = match(r"\[airbody\] launched at [0-9.]+ km/h: ride heights (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)", t)
check("the hit launched the car", m !== nothing)
m !== nothing && check("at its left-front wheel (the highest corner)", parse(Float64, m[1]) == maximum(parse.(Float64, m.captures)),
                       "ride heights $(join(m.captures, " ")) m")
l = match(r"\[airbody\] landed after ([0-9.]+) s \(highest CG ([0-9.]+) m, roll to (-?[0-9.]+) deg, pitch to (-?[0-9.]+) deg\)", t)
check("it landed on its wheels and drives on", l !== nothing && !occursin("[WRECK] hard impact", t))
if l !== nothing
    r = parse(Float64, l[3]); p = parse(Float64, l[4])
    check("it rolled RIGHT with the hit (left side up, > 15 deg)", r > 15.0, "roll to $r deg")
    check("and pitched nose UP", p > 2.0, "pitch to $p deg")
end
# nothing compiles in the air: the launch and the landing were each a ~40 ms stall (log lines)
st = [(parse(Float64, s[1]), parse(Float64, s[2])) for s in eachmatch(r"\[stall\] frame \d+ t=([0-9.]+)s\s+[0-9.]+ ms \(compile ([0-9.]+)", t)]
cc = sum((c for (tt, c) in st if tt > 6.0); init = 0.0)
check("compiling in stalls from the hit on <= 30 ms", cc <= 30.0, "$(cc) ms")
check("no error in the run", !occursin(r"ERROR|Stacktrace"i, t))
# CARLAUNCH-2 (PO 2026-10-21: "Make the struck AI car roll too"): an AI car whose wheel climbs another car's is thrown up
# and flies as a free rigid body too (it was the small-angle loose-car model: a few degrees of roll at most), then comes back
# onto its driving model -- landed, or set back on its wheels after lying off them -- with nothing compiled in the race.
# The field meets a stopped car 6 m ahead of AI 1 at 154 km/h (JM_RAM_AI 5th field > 0).
a = race(Dict("JM_RAM_AI" => "1:12:1.53:6:6", "JM_SMOKE_FRAMES" => "1200"))
check("AI: a car hit the stopped car", occursin(r"\[loose\] t=[0-9.]+ AI \d knocked loose", a))
check("AI: it was thrown up and flies as a free rigid body", occursin(r"\[airbody\] AI \d thrown up", a))
al = match(r"\[airbody\] AI \d (landed on its wheels|lay off its wheels and was set back on them) after ([0-9.]+) s \(highest CG ([0-9.]+) m, roll to (-?[0-9.]+) deg, pitch to (-?[0-9.]+) deg\)", a)
check("AI: it came back onto its driving model", al !== nothing, al === nothing ? "" : al.match)
al !== nothing && check("AI: it rolled (> 15 deg)", abs(parse(Float64, al[4])) > 15.0, "roll to $(al[4]) deg")
sta = [(parse(Float64, s[1]), parse(Float64, s[2])) for s in eachmatch(r"\[stall\] frame \d+ t=([0-9.]+)s\s+[0-9.]+ ms \(compile ([0-9.]+)", a)]
cca = sum((c for (tt, c) in sta if tt > 6.0); init = 0.0)
check("AI: compiling in stalls from the hit on <= 30 ms", cca <= 30.0, "$(cca) ms")
check("AI: no error in the run", !occursin(r"ERROR|Stacktrace"i, a))
c = race(Dict("JM_AIRBODY" => "0"))
check("control (JM_AIRBODY=0): the ram ran", occursin("[ram]", c))
check("control: no launch (player or AI)", !occursin("[airbody]", c))
println(fails[] == 0 ? "CARLAUNCH: PASS" : "CARLAUNCH: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
