# ROADCURVE-1 (PO 2026-09-25, Watkins Glen: "the curves going into and out of the carousel/sweeper are
# piecewise linear rather than smooth curves as in the gold standard - make them smooth curves").
#
# The track .3do IS polygonal there: through the Loop (s~1600-1900) the asphalt/edge/curb/groove rows
# sit 8.5-9 m apart and the inner curb's chords run to ~20 m, a 10-15 deg kink at every row. GPL's own
# renderer shows round arcs (gold 260802_watkinsGlen_nintendo.mp4 t=47-59 s). So we round them here.
#
# Method -- a warp into the track's own curved frame, crack-free by construction:
#   * the curve C(u) is a periodic Catmull-Rom through the racing ribbon's nodes (u = node index), N(u)
#     its left normal; F(u, lat) = C(u) + lat*N(u) maps "developed" track coordinates to the ground plane.
#   * every mesh vertex within MAXLAT of the ribbon is projected to (u, lat) by Gauss-Newton on C, so
#     F(u, lat) gives the vertex back EXACTLY: original vertices never move.
#   * an edge A-B is split at F(mean u, mean lat) -- where the straight developed segment lands on the
#     curved road -- when that point is more than TOL off the chord. A cross-track edge (same u) stays
#     straight; a longitudinal edge becomes an arc; a diagonal becomes the right spiral.
#   * the split decision and the new vertex depend ONLY on the edge's two endpoints (canonically
#     ordered), so the two triangles sharing an edge always split it identically: no T-junctions, and
#     coplanar overlays (groove, lines, curbs over asphalt) follow the same field.
#   * height, UV and normal of a new vertex are the edge averages (the road's own linear profile).
module RoadCurve
using ..Render.GPL3DO: Tri, Mesh3DO

const MAXNODE_LAT = Ref(-1.0)
@inline function maxnode_lat()
    MAXNODE_LAT[] < 0.0 && (MAXNODE_LAT[] = something(tryparse(Float64, get(ENV, "JM_ROADCURVE_MAXNODE_LAT", "12.0")), 12.0))
    MAXNODE_LAT[]
end
const MAXNODE = Ref(-1.0)
@inline function maxnode()
    MAXNODE[] < 0.0 && (MAXNODE[] = something(tryparse(Float64, get(ENV, "JM_ROADCURVE_MAXNODE", "25")), 25.0))
    MAXNODE[]
end

struct Curve
    P::Vector{NTuple{2,Float64}}   # closed loop, no repeated end node
    sgn::Float64                   # +1 if N = left normal agrees with the ribbon's perp
end

@inline _wrap(c::Curve, i) = mod1(i, length(c.P))
function cpoint(c::Curve, u)
    i = floor(Int, u); f = u - i
    p0 = c.P[_wrap(c, i)]; p1 = c.P[_wrap(c, i+1)]; p2 = c.P[_wrap(c, i+2)]; p3 = c.P[_wrap(c, i+3)]
    f2 = f*f; f3 = f2*f
    x = 0.5*(2p1[1] + (-p0[1]+p2[1])*f + (2p0[1]-5p1[1]+4p2[1]-p3[1])*f2 + (-p0[1]+3p1[1]-3p2[1]+p3[1])*f3)
    y = 0.5*(2p1[2] + (-p0[2]+p2[2])*f + (2p0[2]-5p1[2]+4p2[2]-p3[2])*f2 + (-p0[2]+3p1[2]-3p2[2]+p3[2])*f3)
    dx = 0.5*((-p0[1]+p2[1]) + 2(2p0[1]-5p1[1]+4p2[1]-p3[1])*f + 3(-p0[1]+3p1[1]-3p2[1]+p3[1])*f2)
    dy = 0.5*((-p0[2]+p2[2]) + 2(2p0[2]-5p1[2]+4p2[2]-p3[2])*f + 3(-p0[2]+3p1[2]-3p2[2]+p3[2])*f2)
    (x, y, dx, dy)
end
# (u is 1-based: u = k means node k, matching c.P[k])
F(c::Curve, u, lat) = (q = cpoint(c, u - 1); t = hypot(q[3], q[4]); (q[1] - c.sgn*lat*q[4]/t, q[2] + c.sgn*lat*q[3]/t))

"""Project (x, y) onto the curve: (u, lat, ok)."""
function project(c::Curve, x, y, maxlat)
    n = length(c.P); best = 0; bd = Inf
    @inbounds for k in 1:n
        d = (c.P[k][1]-x)^2 + (c.P[k][2]-y)^2
        d < bd && (bd = d; best = k)
    end
    sqrt(bd) > maxlat + 20 && return (0.0, 0.0, false)
    u = Float64(best)
    for _ in 1:12
        q = cpoint(c, u - 1)
        tt = q[3]^2 + q[4]^2
        du = ((x - q[1])*q[3] + (y - q[2])*q[4]) / tt
        du = clamp(du, -1.0, 1.0); u += du
        abs(du) < 1e-9 && break
    end
    q = cpoint(c, u - 1); t = hypot(q[3], q[4])
    lat = c.sgn * ((y - q[2])*q[3] - (x - q[1])*q[4]) / t
    along = ((x - q[1])*q[3] + (y - q[2])*q[4]) / t
    (abs(lat) <= maxlat && abs(along) < 0.05) ? (mod(u - 1, n) + 1, lat, true) : (0.0, 0.0, false)
end

struct V
    p::NTuple{3,Float32}; n::NTuple{3,Float32}; uv::NTuple{2,Float32}
    u::Float64; lat::Float64; ok::Bool
end

avg3(a, b) = ((a[1]+b[1])/2, (a[2]+b[2])/2, (a[3]+b[3])/2)
function nrm3(a)
    l = sqrt(a[1]^2 + a[2]^2 + a[3]^2); l > 0 ? (a[1]/l, a[2]/l, a[3]/l) : a
end

"""Curved midpoint of edge (a, b), or nothing when the chord is already within tol."""
function edge_mid(c::Curve, a::V, b::V, tol)
    (a.ok && b.ok) || return nothing
    # canonical order: the same edge seen from either triangle gives bit-identical arithmetic
    if (a.p[1], a.p[2], a.p[3]) > (b.p[1], b.p[2], b.p[3]); a, b = b, a; end
    L = hypot(Float64(b.p[1]-a.p[1]), Float64(b.p[2]-a.p[2]))
    L < 0.5 && return nothing
    n = length(c.P); du = b.u - a.u
    du > n/2 && (du -= n); du < -n/2 && (du += n)
    # E108-S3: this guard, not JM_ROADCURVE_TOL, is what leaves the worst road-edge chords straight.
    # Measured (gplplan_smoke's sagitta, the gap between the drawn chord and the curve it should follow):
    # the six worst chords at Watkins Glen and at Monza all PROJECT correctly but span 13.1-17.6 curve
    # nodes, so a cap of 12 refused every one of them -- which is why the `max` sagitta was identical with
    # ROADCURVE on and off (1.559 m at WG, 1.065 m at Monza). At ~3 m per ribbon node a cap of 12 stops
    # splitting at ~36 m, and these are 31-55 m chords on gentle curves: plausible geometry, not the
    # mapping failure the guard was written to catch. The guard's real job is to reject an edge whose two
    # endpoints land at opposite ends of the lap, so the cap only has to stay far below that.
    # The cap is raised only out to MAXNODE_LAT laterally, because the extra triangles should go where the
    # defect is. Measured, sagitta p99 of the drawn road edge against triangle count in the SIM:
    #   lateral gate   WG p99   Monza p99   WG tris            Spa tris
    #   (shipped, 12)  0.452 m   0.305 m    67 234             225 549
    #   8 m            0.452 m   0.305 m    79 313             281 145
    #   12 m           0.214 m   0.186 m    81 803  (+21.7 %)  300 069  (+33.0 %)
    #   25 m           0.196 m   0.184 m    93 187             --
    # 12 m takes nearly all the gain; the chords still left straight sit at lateral 12-25 m, out on the
    # aprons, where a kink in a white line is far less visible. The cost matters because the PO has an open
    # frame-rate item (PERF-3) -- and note Spa, the track with that problem, takes the SMALLER relative
    # hit, because its mesh is already dense so fewer of its chords reach the cap at all.
    # This stays CRACK-FREE, which is the module's central invariant: the test reads only the edge's own
    # two endpoints (their laterals), so the two triangles sharing an edge always decide it identically.
    # Gating on TEXTURE instead would break that -- texture is per triangle, not per edge - and would
    # open T-junctions along the road edge, exactly where they would be most visible.
    # JM_ROADCURVE_MAXNODE / JM_ROADCURVE_MAXNODE_LAT override.
    abs(du) > (max(abs(a.lat), abs(b.lat)) <= maxnode_lat() ? maxnode() : 12.0) && return nothing
    # E108-S11 (PO 2026-10-02, Watkins Glen: "coming out of the sweeper the white line on the road is also curved the
    # wrong way"): at the s~1761 hairpin GPL draws a junction line that CUTS ACROSS the road edge (JM_ROADCURVE=0 shows
    # it straight). Rounding interpolates in the curve's (along, lateral) frame, which bends any edge that is not
    # parallel to the road -- the diagonal came out curved along the corner. Only road-parallel edges are rounded now:
    # an edge more than JM_ROADCURVE_OBLIQUE degrees (default 25) off the road direction is never split, so it stays
    # straight as GPL drew it. The decision is per EDGE, so the two triangles sharing it always agree (no cracks).
    let i0 = clamp(floor(Int, a.u), 1, n), j0 = mod1(i0 + 1, n)
        ds = max(hypot(c.P[j0][1] - c.P[i0][1], c.P[j0][2] - c.P[i0][2]), 1e-3)
        abs(b.lat - a.lat) > OBLIQUE_TAN[] * abs(du) * ds && return nothing
    end
    um = mod(a.u + du/2 - 1, n) + 1; lm = (a.lat + b.lat)/2
    m = F(c, um, lm)
    cx = (Float64(a.p[1]) + b.p[1])/2; cy = (Float64(a.p[2]) + b.p[2])/2
    dev = hypot(m[1] - cx, m[2] - cy)
    (dev < tol || dev > 0.2L) && return nothing          # already straight enough / a mapping failure
    V((Float32(m[1]), Float32(m[2]), Float32((Float64(a.p[3]) + b.p[3])/2)),
      Float32.(nrm3(avg3(a.n, b.n))), (Float32((a.uv[1]+b.uv[1])/2), Float32((a.uv[2]+b.uv[2])/2)),
      um, lm, true)
end

const OBLIQUE_TAN = Ref(tan(deg2rad(clamp(parse(Float64, get(ENV, "JM_ROADCURVE_OBLIQUE", "25")), 1.0, 89.9))))
function subdiv!(out, c, a::V, b::V, d::V, tex, col, flat, ptype, tol, depth)
    mab = depth > 0 ? edge_mid(c, a, b, tol) : nothing
    mbd = depth > 0 ? edge_mid(c, b, d, tol) : nothing
    mda = depth > 0 ? edge_mid(c, d, a, tol) : nothing
    k = (mab !== nothing) + (mbd !== nothing) + (mda !== nothing)
    if k == 0
        push!(out, Tri((a.p, b.p, d.p), (a.n, b.n, d.n), (a.uv, b.uv, d.uv), tex, col, flat, ptype)); return
    end
    r(x, y, z) = subdiv!(out, c, x, y, z, tex, col, flat, ptype, tol, depth - 1)
    if k == 3
        r(a, mab, mda); r(mab, b, mbd); r(mda, mbd, d); r(mab, mbd, mda)
    elseif k == 1
        mab !== nothing ? (r(a, mab, d); r(mab, b, d)) :
        mbd !== nothing ? (r(b, mbd, a); r(mbd, d, a)) :
                          (r(d, mda, b); r(mda, a, b))
    else   # two split edges -> three triangles (fan from the vertex shared by the two split edges)
        if mab === nothing      # split bd, da: shared vertex d
            r(d, mda, mbd); r(mda, a, b); r(mda, b, mbd)
        elseif mbd === nothing  # split ab, da: shared vertex a
            r(a, mab, mda); r(mab, b, d); r(mab, d, mda)
        else                    # split ab, bd: shared vertex b
            r(b, mbd, mab); r(mab, mbd, d); r(mab, d, a)
        end
    end
end

"""Gaussian low-pass of a closed polyline (sigma in nodes). The ribbon is re-centred on the drawn road
node by node, which leaves cm-scale lateral wiggle; used raw as the curve it reads as curvature on the
straights and splits the whole lap. The warp needs the road's SHAPE, not its exact centre -- vertices are
mapped exactly onto whatever curve is used -- so a smoothed curve loses nothing."""
function smooth_loop(P::Vector{NTuple{2,Float64}}, sig)
    sig <= 0 && return P
    n = length(P); k = ceil(Int, 3sig); w = [exp(-0.5*(j/sig)^2) for j in -k:k]; w ./= sum(w)
    [(sum(w[j+k+1]*P[mod1(i+j, n)][1] for j in -k:k), sum(w[j+k+1]*P[mod1(i+j, n)][2] for j in -k:k)) for i in 1:n]
end

"""Round the mesh's road-area polygons onto the curve through `P0` (closed ribbon nodes, x/y ground
plane, low-passed by `sig` nodes), with `perp1` the ribbon's lateral direction at node 1 (lateral sign)."""
function curve_mesh(m::Mesh3DO, P0::Vector{NTuple{2,Float64}}, perp1::NTuple{2,Float64}; tol=0.05, maxlat=25.0, maxdepth=5, sig=2.0,
                    heights::Vector{Float64}=Float64[], overhead=4.0, overlat=12.0)
    P = smooth_loop(P0, sig)
    c0 = Curve(P, 1.0); q = cpoint(c0, 0.0); t = hypot(q[3], q[4])
    sgn = ((-q[4]/t)*perp1[1] + (q[3]/t)*perp1[2]) >= 0 ? 1.0 : -1.0
    c = Curve(P, sgn)
    cache = Dict{NTuple{3,Float32},Tuple{Float64,Float64,Bool}}()
    # Structures OVER the road (bridge decks, Monza's banking overpass) must not be bent to follow the road
    # beneath them: a vertex within `overlat` of the centreline and more than `overhead` above the ribbon
    # stays out of the warp (its edges stay straight).
    nover = Ref(0)
    function proj_ok(p)
        pr = project(c, Float64(p[1]), Float64(p[2]), maxlat)
        if pr[3] && !isempty(heights) && abs(pr[2]) < overlat
            nh = length(heights); u = pr[1]; i = floor(Int, u); f = u - i
            h = heights[mod1(i, nh)]*(1-f) + heights[mod1(i+1, nh)]*f
            Float64(p[3]) - h > overhead && (nover[] += 1; return (0.0, 0.0, false))
        end
        pr
    end
    mk(p, n, uv) = (pr = get!(() -> proj_ok(p), cache, p); V(p, n, uv, pr[1], pr[2], pr[3]))
    out = Tri[]; groups = Int[]; nsplit = 0
    DIAG = get(ENV, "JM_ROADCURVE_DIAG", "0") != "0"; hist = Dict{Int,Int}(); hadd = Dict{Int,Int}(); tx = Dict{String,Int}()
    for (t, g) in zip(m.tris, m.groups)
        a = mk(t.p[1], t.n[1], t.uv[1]); b = mk(t.p[2], t.n[2], t.uv[2]); d = mk(t.p[3], t.n[3], t.uv[3])
        n0 = length(out)
        subdiv!(out, c, a, b, d, t.tex, t.col, t.flat, t.ptype, tol, maxdepth)
        if length(out) - n0 > 1
            nsplit += 1
            DIAG && (b_ = a.ok ? a.u : b.ok ? b.u : d.u; k_ = floor(Int, b_/25); hist[k_] = get(hist, k_, 0) + 1;
                     hadd[k_] = get(hadd, k_, 0) + length(out) - n0 - 1; tx[t.tex] = get(tx, t.tex, 0) + length(out) - n0 - 1)
        end
        for _ in n0+1:length(out); push!(groups, g); end
    end
    nok = count(v -> v[3], values(cache))
    if DIAG
        println("  [roadcurve] per 25-node (~100 m) bin: rounded polys / added tris")
        for k in sort(collect(keys(hist))); println("     node ", 25k, "..", 25k+24, ": ", hist[k], " / ", hadd[k]); end
        println("  [roadcurve] added tris by texture: ", join(["$k=$v" for (k, v) in sort(collect(tx), by = x -> -x[2])], " "))
    end
    (Mesh3DO(out, m.textures, groups), (tris_in = length(m.tris), tris_out = length(out), curved = nsplit,
                                        verts = length(cache), mapped = nok, overhead = nover[]))
end

end # module
