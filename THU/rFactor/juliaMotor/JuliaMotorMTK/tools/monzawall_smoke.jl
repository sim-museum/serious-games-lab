# GATE: MONZAWALL-1 -- a track wall's vertex normals face the way the wall does.
#
# PO 2026-10-21: "side wall on left before lesmos flickers" (video 261021_monza_1.mp4). Monza's brush_s wall before Lesmo
# is several layers in one plane: GPL's near/mid/far versions of the wall (all walked), each a front and a back with
# opposite windings and different triangulations. The track mesh averaged every normal at a shared corner, so +n and -n
# cancelled and the leftover (the grass on top) pointed the wall's normals UP: lit as a floor in patches, a different patch
# per layer -- the depth fight between the layers then showed as light and dark panels jumping across the wall. Track
# meshes now average only the normals within 60 deg (JM_TRACK_CREASE); the layers light alike and the fight is invisible.
# Here JM_TRIDUMP_AT dumps the wall's triangles at that spot: every vertex normal within 25 deg of its face; the control
# (JM_TRACK_CREASE=180, the old average) must show the up-normals, so the probe is known to see them.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 64), d))
function dump(extra)
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_TRIDUMP_AT" => "brush_s,-1004,-122,12"), extra)
    log = tempname()
    run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
    t = read(log, String); rm(log; force = true); t
end
num(s) = parse.(Float64, split(replace(s, "f0" => ""), ","))
# the smallest cos(vertex normal, face normal) over the dumped triangles (first vertex of each)
function worst(t)
    c = [(n = num(m[1]); v = num(m[2]); sum(n .* v) / sqrt(sum(abs2, v))) for m in eachmatch(r"\[tri\] part \d+ #\d+ n \(([^)]*)\).* vn \(([^)]*)\)", t)]
    (length(c), isempty(c) ? NaN : minimum(c))
end
println("MONZAWALL gate: the wall before Lesmo is lit as a wall")
c = dump(Dict("JM_TRACK_CREASE" => "180"))
nc, wc = worst(c)
check("control (old average): the probe dumped the wall", nc >= 16, "$nc triangles")
check("control: some wall normal points away from its face (> 60 deg)", wc < 0.5, "worst cos $(round(wc, digits = 2))")
t = dump(Dict{String,String}())
nt, wt = worst(t)
check("the probe dumped the wall", nt >= 16, "$nt triangles")
check("every wall normal within 25 deg of its face", wt > cosd(25), "worst cos $(round(wt, digits = 2))")
check("no error", !occursin(r"ERROR|Stacktrace"i, t))
println(fails[] == 0 ? "MONZAWALL: PASS" : "MONZAWALL: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
