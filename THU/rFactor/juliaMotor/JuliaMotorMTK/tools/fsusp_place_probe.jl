# E102 S18: WHERE is the wedge cluster drawn, against the hub it should reach?
#
# S17 closed the "drop it" branch -- fsusp:1 is the only copy of that geometry, not a duplicate --
# so the remaining question is placement. The gold (260802_monza_nintendo.mp4) shows GPL running the
# driveshaft HORIZONTALLY at hub height, out to the wheel; ours puts a bar higher, at chassis
# height, that stops short. This prints both ends of that comparison as numbers, in the CAR frame
# the renderer actually draws in.
#
# Frames, read out of the code rather than assumed (see body_float_probe.jl for the derivation):
#   .3do vertex   = (x fore/aft, y LATERAL, z UP)
#   render space  = (fore/aft, UP, lateral)          -- render.jl uploads (p[1], p[3], p[2])
#   body drawn at <car origin> * translate(BODY_OFF), BODY_OFF = [-0.55, 0.30, 0.0]
#   wheel drawn at <car origin> * translate([wx, r, wz])
# so in the car frame, with the contact plane at up = 0:
#   a body vertex is   (p[1] + BODY_OFF[1],  p[3] + BODY_OFF[2],  p[2] + BODY_OFF[3])
#   the rear hub is    (hubs.rx + BODY_OFF[1],  r_rear,  ±hubs.ry + BODY_OFF[3])
#
#   julia --project=demo/native JuliaMotorMTK/tools/fsusp_place_probe.jl
const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpl3do.jl")); using .GPL3DO
const CAR = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
const BODY_OFF = (-0.55, 0.30, 0.0)
const R_REAR = 0.34
m = GPL3DO.parse_3do(CAR)
cen(t) = ntuple(i -> sum(p[i] for p in t.p)/length(t.p), 3)

# the rear hubs, by the same detector Render.mesh_wheel_hubs uses
acc = Dict{Tuple{String,Int},Vector{NTuple{3,Float32}}}()
for t in m.tris, p in t.p
    push!(get!(acc, (t.tex, p[2] >= 0 ? 1 : -1), NTuple{3,Float32}[]), p)
end
hubs = NTuple{4,Float64}[]          # (x, |lat|, up, weight)
for ((tex, side), ps) in acc
    length(ps) < 30 && continue
    xl, xh = extrema(p[1] for p in ps); zl, zh = extrema(p[3] for p in ps); yl, yh = extrema(p[2] for p in ps)
    (0.5 <= zh-zl <= 0.8 && yh-yl <= 0.45 && abs(sum(p[2] for p in ps)/length(ps)) >= 0.45) || continue
    push!(hubs, (sum(p[1] for p in ps)/length(ps), abs(sum(p[2] for p in ps)/length(ps)),
                 sum(p[3] for p in ps)/length(ps), length(ps)))
end
xm = sum(h[1]*h[4] for h in hubs)/sum(h[4] for h in hubs)
rear = [h for h in hubs if h[1] < xm]
wmean(v,i) = sum(h[i]*h[4] for h in v)/sum(h[4] for h in v)
rx, rlat = wmean(rear,1), wmean(rear,2)
hub = (rx + BODY_OFF[1], R_REAR, rlat + BODY_OFF[3])
println("DRAWN REAR HUB (car frame, metres):  fore/aft ", round(hub[1],digits=3),
        "   up ", round(hub[2],digits=3), "   lateral ±", round(hub[3],digits=3))

# the wedge cluster, drawn
target = [t for t in m.tris if t.tex == "frontlot" && -1.10 <= cen(t)[1] <= -0.90]
vs = [(p[1]+BODY_OFF[1], p[3]+BODY_OFF[2], p[2]+BODY_OFF[3]) for t in target for p in t.p]
lo(i) = minimum(v[i] for v in vs); hi(i) = maximum(v[i] for v in vs)
println("DRAWN fsusp:1 cluster (", length(target), " tris, ", length(vs), " verts):")
println("   fore/aft ", round(lo(1),digits=3), " .. ", round(hi(1),digits=3))
println("   up       ", round(lo(2),digits=3), " .. ", round(hi(2),digits=3))
println("   lateral  ", round(lo(3),digits=3), " .. ", round(hi(3),digits=3))
println()
println("the hub is at up ", round(hub[2],digits=3), "; the cluster spans up ",
        round(lo(2),digits=3), "..", round(hi(2),digits=3),
        "  -> its CENTRE is ", round((lo(2)+hi(2))/2 - hub[2], digits=3), " m above the hub")
outer = maximum(abs(v[3]) for v in vs)
println("the hub is ±", round(hub[3],digits=3), " m out; the cluster reaches ", round(outer,digits=3),
        " m  -> it stops ", round(hub[3]-outer, digits=3), " m short of the hub laterally")
