# E104-S3: the FLOAT, measured in the RENDERER'S OWN SPACE.
#
# E104-S2 derived an excess of 0.23-0.26 m by comparing a part bbox with a wheel radius and then
# warned, in its own words, that "the axis mapping has to be pinned before any number replaces 0.30,
# and reasoning across two coordinate conventions is how E102 lost two sprints". This probe pins it
# and takes both heights in one frame of reference.
#
# THE TWO CONVENTIONS, read out of the code rather than assumed:
#   * a .3do vertex is (x = fore/aft, y = LATERAL, z = UP). Render.mesh_wheel_hubs uses p[2] for the
#     side and the SIDE half-track, and takes the wheel radius off the p[3] extent -- so p[3] is up.
#   * render.jl uploads each vertex as (p[1], p[3], p[2]) (render.jl:1544, :1603), i.e. render space
#     is (fore/aft, UP, lateral). So BODY_OFF = [-0.55, 0.30, 0.0] is [fore/aft, UP, lateral], and
#     BODY_OFF[2] is a 0.30 m vertical lift of the body ONLY.
#   * the drawn wheels are placed by drive_native_mtk.jl's
#         wheelmat(wx,wz,steer,r) = carModel * Render.translate([wx, r, wz])
#     so a drawn hub sits at render-up = r above the car origin, and the car origin is the contact
#     plane (the tyre of radius r just touches it).
#
# Therefore, in ONE space (render up, car frame):
#     drawn wheel hub   = r                        (0.31 front / 0.34 rear, WHEELS_TABLE)
#     drawn body hub    = <body mesh's own hub z> + BODY_OFF[2]
# and the difference is the float, measured where it is drawn.
#
#   julia --project=demo/native JuliaMotorMTK/tools/body_float_probe.jl
const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpl3do.jl")); using .GPL3DO
const BASE = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67"
const BODY_OFF_UP = 0.30                      # BODY_OFF[2], drive_native_mtk.jl:2754
const R_F, R_R = 0.31, 0.34                   # WHEELS_TABLE radii

# the wheel-group detector, copied from Render.mesh_wheel_hubs so this measures what the sim uses
function hubs_of(m)
    acc = Dict{Tuple{String,Int},Vector{NTuple{3,Float32}}}()
    for t in m.tris, p in t.p
        push!(get!(acc, (t.tex, p[2] >= 0 ? 1 : -1), NTuple{3,Float32}[]), p)
    end
    out = NTuple{5,Float64}[]                 # (x, up, radius, weight, side)
    for ((tex, side), ps) in acc
        length(ps) < 30 && continue
        xl, xh = extrema(p[1] for p in ps); zl, zh = extrema(p[3] for p in ps); yl, yh = extrema(p[2] for p in ps)
        ez = zh - zl; ey = yh - yl; cy = sum(p[2] for p in ps)/length(ps)
        (0.5 <= ez <= 0.8 && ey <= 0.45 && abs(cy) >= 0.45) || continue
        cx = sum(p[1] for p in ps)/length(ps)
        groups = (xh - xl) <= 0.8 ? [ps] : [[p for p in ps if p[1] >= cx], [p for p in ps if p[1] < cx]]
        for q in groups
            length(q) < 15 && continue
            qxl, qxh = extrema(p[1] for p in q); (qxh - qxl) <= 0.8 || continue
            qzl, qzh = extrema(p[3] for p in q)
            push!(out, (sum(p[1] for p in q)/length(q), sum(p[3] for p in q)/length(q), (qzh - qzl)/2, length(q), side))
        end
    end
    out
end

cars = [("Lotus 49","lotus","lotus.3do"), ("Ferrari","ferrari","ferrari.3do"), ("Brabham","brabham","brabham.3do"),
        ("BRM","brm","brm.3do"), ("Eagle","eagle","eagle.3do"), ("Cooper","coventry","coventry.3do")]
println("E104-S3 -- drawn hub height vs drawn body-hub height, render space (up), car frame")
println("  BODY_OFF[2] = ", BODY_OFF_UP, " m applied to the BODY only; wheels drawn at up = r\n")
for (nm, dir, body) in cars
    path = joinpath(BASE, dir, body)
    isfile(path) || (println(rpad(nm,10), "  no ", path); continue)
    m = GPL3DO.parse_3do(path)
    hs = hubs_of(m)
    if length(hs) < 4
        println(rpad(nm,10), "  only ", length(hs), " wheel groups found -- skipped")
        continue
    end
    xm = sum(h[1]*h[4] for h in hs)/sum(h[4] for h in hs)
    front = [h for h in hs if h[1] >= xm]; rear = [h for h in hs if h[1] < xm]
    wmean(v,i) = sum(h[i]*h[4] for h in v)/sum(h[4] for h in v)
    fup, rup = wmean(front,2), wmean(rear,2)          # the body mesh's OWN hub height
    fr,  rr  = wmean(front,3), wmean(rear,3)          # the body mesh's own tyre radius
    # the whole body's vertical extent, for "where does the drawn body bottom out"
    zs = [p[3] for t in m.tris for p in t.p]
    bmin, bmax = minimum(zs), maximum(zs)
    println("== ", nm, "  (", length(m.tris), " tris, ", length(hs), " wheel groups)")
    println("   body mesh, own frame (up):  hubs front ", round(fup,digits=3), "  rear ", round(rup,digits=3),
            "   own tyre radius ", round(fr,digits=3), "/", round(rr,digits=3), "   bbox ", round(bmin,digits=3), " .. ", round(bmax,digits=3))
    println("   DRAWN wheel hub (up):       front ", round(R_F,digits=3), "   rear ", round(R_R,digits=3))
    println("   DRAWN body  hub (up):       front ", round(fup+BODY_OFF_UP,digits=3), "   rear ", round(rup+BODY_OFF_UP,digits=3),
            "      (mesh hub + BODY_OFF[2])")
    println("   FLOAT (body hub - wheel hub): front ", round(fup+BODY_OFF_UP-R_F,digits=3), " m   rear ",
            round(rup+BODY_OFF_UP-R_R,digits=3), " m")
    println("   BODY_OFF[2] that would align them: front ", round(R_F-fup,digits=3), "   rear ", round(R_R-rup,digits=3),
            "   (mean ", round(((R_F-fup)+(R_R-rup))/2, digits=3), ")")
    println("   drawn body underside (up):  ", round(bmin+BODY_OFF_UP,digits=3), " m above the contact plane")
    println()
end
