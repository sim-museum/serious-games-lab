# GATE: TARMACMU-1 -- a wheel on the DRAWN tarmac keeps tarmac grip, wherever the centreline is.
#
# PO 2026-10-18 (Monza): "twice while shifting into 5th gear the car started moving exactly sideways(!) Nothing like this
# happens in iracing". Both times at s 5424-5486, the pit straight, where the re-centred line jogs 11.6 m toward the
# banking's merge (s 5450-5510, back at 5690-5730). wheel_mu called a wheel grass at |lateral| > ROAD_HALFW (9 m) from
# that line; the car, straight on the tarmac 10-21 m off it, got GRASS_MU on the rears, spun them up in 5th at 215 km/h
# and slid sideways. The poses below are the PO's own (replay_monza 5ai 2026-10-18 21-20-56 / 21-35-55 .jrt, x/z).
#
#  1. KNOWN POSITIVE: Monza's road-only HAT (built as drive_native_mtk builds ROADHAT) has tarmac under every one of the
#     PO's off-line poses -- the ones the 9 m rule called grass (ontrack 0 in the replay).
#  2. KNOWN NEGATIVE: walking sideways from each pose, the tarmac ENDS within 40 m on both sides (the HAT is not just
#     answering "road" everywhere, which would make test 1 worthless).
#  3. wheel_mu consults ROADHAT before returning GRASS_MU (source text: the sim itself cannot run headless here).
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS",
              normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl"));   using .GPLDat
include(joinpath(D, "gpl3do.jl"));   using .GPL3DO
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
using JuliaMotor, Printf

fails = Ref(0)
chk(n, ok, d) = (@printf("  %-62s %s   %s\n", n, ok ? "PASS" : "FAIL", d); ok || (fails[] += 1))

dir = joinpath(G, "monza")
ci(n) = (m = filter(f -> lowercase(f) == lowercase(n), readdir(dir)); joinpath(dir, m[1]))
dat = GPLDat.parse_dat(ci("monza.dat"))
m3do = tempname() * ".3do"; write(m3do, dat["monza.3do"])
mesh = GPL3DO.parse_3do(m3do)
# drive_native_mtk.jl: ROAD_TEX, ROAD_PRED (Monza), HAT_EXCLUDE, drop_overpass = MONZA
road_tex = lt -> occursin("asp", lt) || startswith(lt, "groove") || startswith(lt, "curb") || startswith(lt, "kerb") ||
                 lt in ("sline", "sgrid", "start") || startswith(lt, "atog") || startswith(lt, "a_l_g") || lt == "concrete"
road_pred = lt -> occursin("asp", lt) || startswith(lt, "groove") || startswith(lt, "kerb")
RH = GPLTrack.build_hat(mesh; exclude = Set(["br_under", "villone"]), exclude_pred = (lt -> !road_tex(lt)),
                        drop_overpass = true, road_pred = road_pred)
road(x, z) = JuliaMotor.hat3d(RH, x, z; ref = Inf)[3]

println("TARMACMU-1 gate (Monza pit straight, the PO's 2026-10-18 spins)")
# (x, z, lateral from the line in the replay) -- every one had ontrack 0, i.e. grass grip under the 9 m rule
PO = [(592.5, -515.3, 9.68), (578.6, -515.6, 12.42), (563.5, -516.0, 17.01), (548.3, -516.2, 20.85),
      (534.0, -516.3, 21.69), (506.3, -516.0, 20.94), (479.0, -514.7, 19.70), (452.5, -512.7, 17.69),
      (555.0, -508.0, 11.28), (543.5, -508.2, 13.66), (518.6, -508.6, 13.56), (492.2, -508.8, 13.76),
      (467.4, -508.2, 13.20)]
n_on = count(p -> road(p[1], p[2]), PO)
chk("1. tarmac under the PO's off-line poses (9 m rule: grass)", n_on == length(PO), "$n_on / $(length(PO))")
edge(x, z, dir) = (for d in 0.5:0.5:40.0; road(x, z + dir*d) || return d; end; Inf)
ends = [(edge(p[1], p[2], +1.0), edge(p[1], p[2], -1.0)) for p in PO]
chk("2. the tarmac ends within 40 m on both sides of every pose", all(e -> isfinite(e[1]) && isfinite(e[2]), ends),
    "widest " * string(round(maximum(e[1] + e[2] for e in ends), digits = 1)) * " m")
src = read(joinpath(D, "drive_native_mtk.jl"), String)
m = match(r"function wheel_mu\(.*?\nend"s, src)
chk("3. wheel_mu consults ROADHAT before GRASS_MU", m !== nothing && occursin("hat3d(ROADHAT", m.match) &&
    occursin("GRASS_MU", m.match), m === nothing ? "wheel_mu not found" : "")
println(fails[] == 0 ? "TARMACMU: PASS" : "TARMACMU: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
