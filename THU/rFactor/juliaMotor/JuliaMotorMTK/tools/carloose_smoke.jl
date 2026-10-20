# GATE: CARCOLLIDE-2 S4 -- an AI car the player hits hard comes loose: it takes the same impulse as the player (spin,
# launch) as a free Car3D, then rejoins its line.
#
# PO 2026-10-18: "In iracing, a collision involving contact with a spinning tire causes both cars to spin around ...
# Right now in Julia, two cars hitting is like two beanbags hitting." GPL's AI field answered a player contact only by
# easing away sideways (gplai.jl tick!). A real sim race at Monza: JM_RAM_AI puts the player 4.7 m behind AI 1, 0.8 m to
# its left, closing at 12 m/s, a few seconds after the start. Control: JM_AI_LOOSE=0 (the field's gentle answer only).
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 60), d))
function race(extra)
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_MODE" => "race", "JM_AI" => "3", "JM_LAPS" => "1",
                                "JM_RAM_AI" => "1:12:0.8:4", "JM_SMOKE_FRAMES" => "1500"), extra)
    log = tempname()
    run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
    read(log, String)
end
println("CARLOOSE gate: a hard-hit AI car comes loose")
t = race(Dict{String,String}())
check("the ram ran", occursin("[ram]", t))
m = match(r"\[loose\] t=[0-9.]+ AI 1 knocked loose: dv ([0-9.]+) m/s, yaw kick (-?[0-9.]+) rad/s, launch (-?[0-9.]+)", t)
check("AI 1 was knocked loose", m !== nothing)
m !== nothing && check("its yaw kick is a spin, not a nudge (>= 0.6 rad/s) or a speed change >= 4 m/s",
                       abs(parse(Float64, m[2])) >= 0.6 || parse(Float64, m[1]) >= 4.0, "dv $(m[1]) m/s, yaw $(m[2]) rad/s, launch $(m[3]) m/s")
check("it rejoined its line", occursin(r"\[loose\] t=[0-9.]+ AI 1 rejoins", t))
check("no error in the run", !occursin(r"ERROR|Stacktrace"i, t))
c = race(Dict("JM_AI_LOOSE" => "0"))
check("control (JM_AI_LOOSE=0): the ram ran", occursin("[ram]", c))
check("control: nothing comes loose", !occursin("[loose]", c))
println(fails[] == 0 ? "CARLOOSE: PASS" : "CARLOOSE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
