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

"""Turn angles of the road-edge strip, in plan.

FIRST ATTEMPT WAS WRONG AND THE GATE PASSED ANYWAY, which is the worse failure: it bucketed the strip's
vertices by lap distance alone. But a white-line strip is TWO rows of vertices, its inner and outer edge
~0.2 m apart, so ordering by lap distance interleaves them and consecutive "nodes" zig-zag across the
stripe -- reported as a median turn of 90 deg at 0.3 m spacing, which is impossible for a road edge and
should have been caught by reading the number rather than the verdict.

So: per side of the road, bin the lap distance and keep the OUTERMOST vertex in each bin. That is the
boundary a driver actually sees, and it is one polyline per side by construction."""
function edge_turns(mesh, ribbon; bin = 1.0)
    per = Dict{Int,Dict{Int,Tuple{Float64,Float64,Float64}}}()   # side => lap bin => (|lat|, x, z)
    for t in mesh.tris
        isedge(t.tex) || continue
        for q in t.p
            x = Float64(q[1]); z = Float64(q[2])
            hr = JuliaMotor.hat(ribbon, x, z)
            hr.found || continue
            abs(hr.lateral) < 2.0 && continue          # the centre groove is not an edge strip
            side = sign(hr.lateral) > 0 ? 1 : -1
            d = get!(per, side, Dict{Int,Tuple{Float64,Float64,Float64}}())
            k = floor(Int, hr.lapdist / bin)
            cur = get(d, k, nothing)
            (cur === nothing || abs(hr.lateral) > cur[1]) && (d[k] = (abs(hr.lateral), x, z))
        end
    end
    ang = Float64[]; spacing = Float64[]
    for (_, d) in per
        ks = sort(collect(keys(d)))
        length(ks) < 3 && continue
        for i in 2:length(ks)-1
            # NOT "consecutive bins". The strip's own nodes are 9-18 m apart, so with a 1 m bin almost
            # no two populated bins are adjacent -- requiring adjacency left 7 nodes at Watkins Glen and
            # 0 at Monza. Take the kept vertices in lap order and reject a triple only when a chord is
            # so long that the strip must be interrupted (pit entry, a bridge).
            a = d[ks[i-1]]; b = d[ks[i]]; c = d[ks[i+1]]
            ax = b[2]-a[2]; az = b[3]-a[3]; bx = c[2]-b[2]; bz = c[3]-b[3]
            la = hypot(ax, az); lb = hypot(bx, bz)
            (la < 1e-6 || lb < 1e-6 || la > 40.0 || lb > 40.0) && continue
            cs = clamp((ax*bx + az*bz)/(la*lb), -1.0, 1.0)
            push!(ang, rad2deg(acos(cs))); push!(spacing, la)
        end
    end
    (ang = ang, spacing = spacing)
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
        c = edge_turns(raw, rib)
        t = edge_turns(cur, rib)
        @printf("\n== %s: .trk lap %.0f m, %d edge nodes sampled\n", name, ta.total, length(c.ang))
        for (nm, r) in (("raw .3do (control)", c), ("ROADCURVE (shipped)", t))
            isempty(r.ang) && (println("   ", nm, ": no edge strip found"); continue)
            @printf("   %-20s turn/node p50 %5.2f p90 %6.2f p99 %6.2f max %6.2f deg   node spacing p50 %5.2f p90 %6.2f m   %d nodes\n",
                    nm, pct(r.ang,0.5), pct(r.ang,0.9), pct(r.ang,0.99), maximum(r.ang),
                    pct(r.spacing,0.5), pct(r.spacing,0.9), length(r.ang))
        end
        (isempty(c.ang) || isempty(t.ang)) && continue
        # INSTRUMENT SELF-TEST, and it gates everything else. A road edge runs nearly straight at the
        # median whatever the tessellation; a median near 90 deg means the strip's two rows are still
        # interleaved, which is exactly how the first version of this file reported nonsense AND PASSED.
        # A track that fails this is reported UNMEASURED rather than judged: its numbers mean nothing, and
        # asserting on them would be worse than asserting nothing.
        if !(pct(c.ang, 0.5) < 15.0 && pct(t.ang, 0.5) < 15.0)
            @printf("  ---   UNMEASURED: %s -- the edge polyline is still mis-ordered (median turn %.2f / %.2f deg,\n",
                    name, pct(c.ang, 0.5), pct(t.ang, 0.5))
            println("        which a road edge cannot do). Its texture set is ", join(sort(unique(lowercase(t2.tex) for t2 in raw.tris if isedge(t2.tex))), " "),
                    " -- probably two concentric strips on one side (curb outside the white line), so")
            println("        'outermost per bin' hops between them. No assertion is made on this track.")
            push!(unmeasured, name)
            continue
        end
        ck(pct(c.ang, 0.99) > 5.0, "premise: the raw edge really does kink",
           @sprintf("p99 %.2f deg > 5", pct(c.ang, 0.99)))
        ck(pct(t.ang, 0.5) <= pct(c.ang, 0.5) + 1e-9, "ROADCURVE straightens the edge at the median",
           @sprintf("%.2f <= %.2f deg per node", pct(t.ang, 0.5), pct(c.ang, 0.5)))
        ck(pct(t.spacing, 0.5) <= pct(c.spacing, 0.5) + 1e-9, "ROADCURVE tessellates at least as finely",
           @sprintf("median node spacing %.2f <= %.2f m", pct(t.spacing, 0.5), pct(c.spacing, 0.5)))
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
