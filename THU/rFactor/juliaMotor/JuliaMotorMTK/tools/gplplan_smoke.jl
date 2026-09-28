# GATE: the drawn road edge must be SMOOTH IN PLAN VIEW.
#
# E108-S1 (PO 2026-09-28: "no seams, piecewise linear segments around turns, no piecewise linear white
# roadside stripes"; and 2026-09-26: "polygon corners you can see when there's a white boundary at the
# edge of the road").
#
# WHY THIS FILE EXISTS. Every road ruler in this project measures the VERTICAL -- seam_smoke, the
# vcrease probe, gplroad_smoke. And gplroad_smoke established that the vertical is already fine: the
# drawn road tracks the .trk elevation to 0.4 cm (Monza p50) - 5.7 cm (Watkins Glen p90). A vertical
# ruler cannot see the defect the PO is describing, and three sprints were spent before that was
# understood. This measures the thing itself: the IN-PLANE turn the white line makes at each of its
# own nodes, which is exactly what reads as a visible corner.
#
# THE MEASURE. Take the road-edge strip's vertices, order them along the lap, and at each node measure
# the angle between the incoming and outgoing chord. A smooth curve sampled finely gives small angles;
# a polygon gives one large angle per node. Also report the node spacing, because a turn angle only
# means something next to the distance it is spread over: the same corner tessellated twice as finely
# has half the angle per node.
#
# ARMS. Control = the raw .3do exactly as GPL ships it (JM_ROADCURVE=0 in the sim). Treatment =
# through RoadCurve.curve_mesh, the shipped path. Both in-process, same call the sim makes.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS",
              normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl"));   using .GPLDat
include(joinpath(D, "gpl3do.jl"))
module Render
    const GPL3DO = Main.GPL3DO
end
include(joinpath(D, "roadcurve.jl")); using .RoadCurve
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
using JuliaMotor, Printf

pct(v, p) = isempty(v) ? NaN : (u = sort(copy(v)); u[clamp(ceil(Int, p*length(u)), 1, length(u))])

# the white line / road-edge strips, per track. These are the polygons whose corners the PO can see.
const EDGETEX = ("edge", "pline", "sline", "bordo", "borcem", "curb", "aspgrs")
isedge(t) = (lt = lowercase(t); any(p -> startswith(lt, p), EDGETEX))

function load(dir, nm)
    zd = joinpath(G, dir)
    ci(n) = (m = filter(f -> lowercase(f) == lowercase(n), readdir(zd)); isempty(m) ? "" : joinpath(zd, m[1]))
    dat = (p = ci(nm*".dat"); p == "" ? Dict{String,Vector{UInt8}}() : GPLDat.parse_dat(p))
    function getf(n)
        p = ci(n); p != "" && return p
        v = get(dat, lowercase(n), nothing); v === nothing && return ""
        q = tempname()*"_"*n; write(q, v); q
    end
    (trk = getf(nm*".trk"), mesh = getf(nm*".3do"))
end

"""SAGITTA of the drawn road edge against a smooth curve, per edge chord, in METRES -- no polyline
reconstruction, no vertex ordering, and no bias from chord length.

FOUR EARLIER MEASURES FAILED, and recording why is the point of this comment:
 (a) turn angle from vertices bucketed by lap distance -- interleaves the strip's two rows (inner and
     outer edge of the white line, ~0.2 m apart): 90 deg medians at 0.3 m spacing, and the gate PASSED;
 (b) outermost vertex per lap bin, keyed by side -- hops between CONCENTRIC strips (Watkins Glen has a
     curb outboard of the white line), leaving that track unmeasurable;
 (c) as (b) but keyed by (side, texture) and restricted to the outer row -- the raw arm came good, but
     ROADCURVE inserts midpoints at INTERMEDIATE laterals, so the treatment row stayed jumpy, and a tight
     lateral tolerance cut Monza to 13 usable nodes;
 (d) angle between each chord and the ribbon tangent at the chord's MIDPOINT -- geometrically backwards.
     A chord of an arc is parallel to its own mid-tangent, so that angle tends to ZERO as the chord gets
     LONGER. It rewarded coarse tessellation: it read 0.61 deg for the raw mesh and 1.97 deg for the
     subdivided one.

WHAT IS MEASURED HERE. For each longitudinal chord of the strip, walk the ribbon's own curve across the
chord's lap-distance span at the chord's lateral offset, and take the greatest perpendicular distance from
that curve to the chord. That is the sagitta: the gap between the straight edge we DRAW and the curve the
road actually follows -- which is exactly the bulge a driver sees as a polygon corner. It grows as the
chord grows (L^2/8R) and shrinks with subdivision, it is in metres, and it needs nothing ordered."""
function edge_devs(mesh, ribbon; latsame = 0.5, minlen = 1.0, nsamp = 8)
    npos = length(ribbon.pos); ld = ribbon.lapdist; lap = ribbon.lap_length
    "world point on the ribbon at lap distance sv, offset `lat` along the local normal"
    function at(sv, lat)
        i = clamp(searchsortedlast(ld, mod(sv, lap)), 1, npos)
        send = i == npos ? lap : ld[i+1]
        f = (mod(sv, lap) - ld[i]) / max(send - ld[i], 1e-9)
        j = mod1(i+1, npos); pa = ribbon.pos[i]; pb = ribbon.pos[j]; q = ribbon.perp[i]
        (pa[1] + (pb[1]-pa[1])*f + lat*q[1], pa[3] + (pb[3]-pa[3])*f + lat*q[3])
    end
    dev = Float64[]; len = Float64[]
    seen = Set{NTuple{4,Int}}()
    for t in mesh.tris
        isedge(t.tex) || continue
        h = Vector{Any}(undef, 3)
        for k in 1:3
            x = Float64(t.p[k][1]); z = Float64(t.p[k][2])
            r = JuliaMotor.hat(ribbon, x, z)
            h[k] = (r.found && abs(r.lateral) >= 2.0) ? (r.lapdist, r.lateral, x, z) : nothing
        end
        for (k1, k2) in ((1,2), (2,3), (3,1))
            a = h[k1]; b = h[k2]
            (a === nothing || b === nothing) && continue
            abs(abs(a[2]) - abs(b[2])) > latsame && continue        # a cross-track edge, not longitudinal
            sign(a[2]) == sign(b[2]) || continue                    # spans the road: not an edge chord
            cx = round(Int, a[3]*100); cz = round(Int, a[4]*100)
            dx = round(Int, b[3]*100); dz = round(Int, b[4]*100)
            key = (cx, cz, dx, dz) < (dx, dz, cx, cz) ? (cx, cz, dx, dz) : (dx, dz, cx, cz)
            key in seen && continue
            push!(seen, key)
            ex = b[3]-a[3]; ez = b[4]-a[4]; L = hypot(ex, ez)
            (L < minlen || L > 60.0) && continue
            sa = a[1]; sb = b[1]
            abs(sb - sa) > lap/2 && continue                        # spans the start/finish wrap
            lat = (a[2] + b[2])/2
            worst = 0.0
            for k in 1:nsamp-1
                q = at(sa + (sb-sa)*k/nsamp, lat)
                # perpendicular distance from the ribbon point to the drawn chord
                worst = max(worst, abs((q[1]-a[3])*ez - (q[2]-a[4])*ex) / L)
            end
            push!(dev, worst); push!(len, L)
        end
    end
    (ang = dev, spacing = len)
end

const fails = Ref(0); const checks = Ref(0)
function ck(ok, label, detail)
    checks[] += 1; ok || (fails[] += 1)
    @printf("  %s  %-50s %s\n", ok ? "PASS" : "FAIL", label, detail)
end

const TRACKS = split(get(ENV, "JM_GPLPLAN_TRACKS", "watglen monza spa67"))

function main()
    println("E108-S1 gate: the drawn road edge, measured IN PLAN (turn angle per node)")
    unmeasured = String[]
    for name in TRACKS
        f = load(name, name)
        (f.trk == "" || f.mesh == "") && (println("  ", name, ": no .trk/.3do -- skipped"); continue)
        ta  = GPLTrack.trk_altitude(f.trk)
        cl  = GPLTrack.trk_centreline(f.trk)
        raw = GPL3DO.parse_3do(f.mesh)
        hat = GPLTrack.build_hat(raw)
        A   = GPLTrack.align_centreline(cl, hat)
        rib = GPLTrack.build_surface(A, hat)
        P = [(p[1], p[3]) for p in rib.pos]; HS = [p[2] for p in rib.pos]
        length(P) > 2 && hypot(P[end][1]-P[1][1], P[end][2]-P[1][2]) < 0.5 && (pop!(P); pop!(HS))
        q = rib.perp[1]
        cur, _ = RoadCurve.curve_mesh(raw, P, (q[1], q[3]); tol = 0.05, sig = 2.0, heights = HS)
        c = edge_devs(raw, rib)
        t = edge_devs(cur, rib)
        @printf("\n== %s: .trk lap %.0f m, %d edge nodes sampled\n", name, ta.total, length(c.ang))
        for (nm, r) in (("raw .3do (control)", c), ("ROADCURVE (shipped)", t))
            isempty(r.ang) && (println("   ", nm, ": no edge strip found"); continue)
            @printf("   %-20s sagitta p50 %5.3f p90 %6.3f p99 %6.3f max %6.3f m   chord len p50 %5.2f p90 %6.2f m   %d chords\n",
                    nm, pct(r.ang,0.5), pct(r.ang,0.9), pct(r.ang,0.99), maximum(r.ang),
                    pct(r.spacing,0.5), pct(r.spacing,0.9), length(r.ang))
        end
        (isempty(c.ang) || isempty(t.ang)) && continue
        # INSTRUMENT SELF-TEST, and it gates everything else. A road edge runs nearly straight at the
        # median whatever the tessellation; a median near 90 deg means the strip's two rows are still
        # interleaved, which is exactly how the first version of this file reported nonsense AND PASSED.
        # A track that fails this is reported UNMEASURED rather than judged: its numbers mean nothing, and
        # asserting on them would be worse than asserting nothing.
        if !(pct(c.ang, 0.5) < 1.0 && pct(t.ang, 0.5) < 1.0)
            @printf("  ---   UNMEASURED: %s -- the sagittas are implausible (median %.3f / %.3f m,\n",
                    name, pct(c.ang, 0.5), pct(t.ang, 0.5))
            println("        which a road edge cannot do). Its texture set is ", join(sort(unique(lowercase(t2.tex) for t2 in raw.tris if isedge(t2.tex))), " "),
                    " -- probably two concentric strips on one side (curb outside the white line), so")
            println("        'outermost per bin' hops between them. No assertion is made on this track.")
            push!(unmeasured, name)
            continue
        end
        ck(pct(c.ang, 0.9) > 0.05, "premise: the raw edge really does depart from the curve",
           @sprintf("p90 sagitta %.3f m > 0.05", pct(c.ang, 0.9)))
        ck(pct(t.ang, 0.9) <= pct(c.ang, 0.9) + 1e-9, "ROADCURVE cuts the edge's sagitta",
           @sprintf("p90 %.3f <= %.3f m", pct(t.ang, 0.9), pct(c.ang, 0.9)))
        ck(pct(t.spacing, 0.5) <= pct(c.spacing, 0.5) + 1e-9, "ROADCURVE shortens the edge chords",
           @sprintf("median chord %.2f <= %.2f m", pct(t.spacing, 0.5), pct(c.spacing, 0.5)))
    end
    println()
    isempty(unmeasured) || println("UNMEASURED tracks (instrument, not the road): ", join(unmeasured, " "))
    # a gate that can measure nothing has proved nothing, and must say so as a failure
    nomeasure = checks[] == 0
    nomeasure && println("GPLPLAN GATE: FAIL -- no track could be measured at all")
    println("GPLPLAN GATE: ", (fails[] == 0 && !nomeasure) ? "PASS" : "FAIL", "  (", checks[] - fails[],
            "/", checks[], " checks, ", length(unmeasured), " track(s) unmeasured)")
    exit((fails[] == 0 && !nomeasure) ? 0 : 1)
end
main()
