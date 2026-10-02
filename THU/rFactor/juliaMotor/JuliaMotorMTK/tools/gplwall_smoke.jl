# gplwall_smoke.jl — GPLWALL-1 gate (PO 2026-10-01: "using GPL's methods where possible, ensure that the user's car
# will never go through any object on any track as if it wasn't there, consistent with the GPL behavior upon collision")
#
# Three parts, each able to fail:
#  1. the .trk wall decoder reads Watkins Glen's known structure (section count, strip records, raised walls, heights,
#     and the free interval at the start line);
#  2. TREATMENT: the real sim drives the player car into both boundaries every 300 m at 45 deg / 55 m/s (JM_CRASH);
#     no scenario may end THROUGH a wall, and no penetration of a GPL wall or a drawn hard face may exceed the 0.3 m
#     design limit + 5 cm (wall and obstacle contacts at once: each clamp can nudge the car into the other's face);
#  3. POSITIVE CONTROL: the same sweep with the collision physics off (JM_GPLWALL=0) MUST report cars going through.
#     A detector that cannot see a failure proves nothing (on 2026-10-01 the old system let 16 of 50 through here).
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS", normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl")); using .GPLDat
include(joinpath(D, "gplwall.jl")); using .GPLWall

fails = Ref(0)
check(name, cond, msg) = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 58), msg))

println("GPLWALL-1 gate: GPL's .trk walls + every drawn obstacle stop the player car")
dir = joinpath(G, "watglen")
f = filter(x -> lowercase(x) == "watglen.trk", readdir(dir))
b = isempty(f) ? GPLDat.parse_dat(joinpath(dir, filter(x -> lowercase(x) == "watglen.dat", readdir(dir))[1]))["watglen.trk"] :
                 read(joinpath(dir, f[1]))
W = read_walls(b)
nrec = sum(length, W.secs); walls = [s for v in W.secs for s in v if s.wall]
check("decoder: 47 sections, 591 strip records", length(W.secs) == 47 && nrec == 591, "$(length(W.secs)) / $nrec")
check("decoder: 107 raised strips, heights 0.76/0.91/1.22 m", length(walls) == 107 &&
      sort(unique(round.([s.height for s in walls], digits = 2))) == [0.76, 0.91, 1.22],
      "$(length(walls)) raised")
(lo, hi) = free_interval(W, 1, 0.0, 0.0, 0.0)
check("decoder: start-line free interval = (-13.41, 40.84) m", abs(lo + 13.41) < 0.01 && abs(hi - 40.84) < 0.01,
      "($(round(lo, digits = 2)), $(round(hi, digits = 2)))")
check("decoder: every section ends with exactly one type-10 record", all(v -> count(s -> s.typ == 10, v) == 1 && v[end].typ == 10, W.secs), "")

function sweep(extra::Dict)
    env = merge(Dict(ENV), Dict("TRACK" => "watglen", "JM_MODE" => "practice", "JM_CRASH" => "auto:300", "JM_SMOKE" => "1"), extra)
    log = tempname()
    cmd = setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)
    run(pipeline(ignorestatus(cmd); stdout = log, stderr = log))
    txt = read(log, String)
    m = match(r"SUMMARY watglen: (\d+) scenarios, THROUGH (\d+), deepest GPL-wall penetration ([0-9.]+) m, deepest drawn-face penetration ([0-9.]+) m", txt)
    m === nothing && (println(last(txt, 1500)); return nothing)
    (n = parse(Int, m[1]), thru = parse(Int, m[2]), wall = parse(Float64, m[3]), drawn = parse(Float64, m[4]))
end
r = sweep(Dict{String,String}())
check("treatment: the sweep ran", r !== nothing && r.n >= 20, r === nothing ? "no SUMMARY line" : "$(r.n) scenarios")
if r !== nothing
    check("treatment: no car ends THROUGH a wall", r.thru == 0, "$(r.thru) of $(r.n)")
    check("treatment: GPL-wall penetration <= 0.35 m", r.wall <= 0.35, "$(r.wall) m")
    check("treatment: drawn hard-face penetration <= 0.35 m", r.drawn <= 0.35, "$(r.drawn) m")
end
c = sweep(Dict("JM_GPLWALL" => "0"))
check("control (physics off): the detector SEES cars go through", c !== nothing && c.thru >= 1,
      c === nothing ? "no SUMMARY line" : "$(c.thru) of $(c.n) through, deepest wall $(c.wall) m")
println()
println(fails[] == 0 ? "✓ OK" : "✗ $(fails[]) FAILED")
exit(fails[] == 0 ? 0 : 1)
