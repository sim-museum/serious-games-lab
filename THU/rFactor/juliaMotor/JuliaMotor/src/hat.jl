# HAT — "Height Above Terrain" track surface queries.
#
# The standalone physics needs, under each tire contact patch at ~400 Hz:
# ground height, surface normal, and whether the point is on the drivable
# road.  rFactor builds this by ray-casting collision GMT meshes; we build
# it from the AIW track ribbon — the waypoint chain that already carries,
# per point (validated, fully populated for all 68 tracks):
#
#   pos     world position of the racing-line point (x, y=up, z)
#   perp    lateral unit vector (3D — its y-component is the cross-slope)
#   normal  surface normal
#   width   (left, right, far-left, far-right) half-widths, meters
#   lapdist distance into the lap (→ lap timing)
#
# A query projects onto the nearest ribbon segment, interpolates along it,
# and offsets laterally.  This is the road surface; full off-track terrain
# (grass/sand/gravel elevation) is a later refinement from the GMT meshes.
# Surface height across the road accounts for banking via perp.y.

using RFactorData: AIWFile, AIWWaypoint, mainpath

"""
Drivable track surface built from an AIW ribbon, with a uniform-grid
spatial index over the segments for O(1) point queries.
"""
struct TrackSurface
    pos::Vector{NTuple{3,Float64}}
    perp::Vector{NTuple{3,Float64}}
    normal::Vector{NTuple{3,Float64}}
    halfwidth::Vector{NTuple{2,Float64}}   # (left, right) along +perp / -perp
    lapdist::Vector{Float64}
    seg::Vector{Int}                       # waypoint index i; segment i→i+1
    # spatial grid (horizontal x–z plane)
    cell::Float64
    x0::Float64
    z0::Float64
    nx::Int
    nz::Int
    buckets::Vector{Vector{Int}}           # cell → segment indices
    lap_length::Float64
end

Base.show(io::IO, t::TrackSurface) =
    print(io, "TrackSurface(", length(t.seg), " segments, lap ",
          round(t.lap_length; digits=1), " m, grid ", t.nx, "×", t.nz, ")")

unit(v) = (n = sqrt(v[1]^2 + v[2]^2 + v[3]^2); n > 0 ? v ./ n : v)

"""
    TrackSurface(aiw::AIWFile; cell=20.0) -> TrackSurface

Build the surface from an AIW's main-path ribbon.  `cell` is the spatial
grid resolution in meters.
"""
function TrackSurface(aiw::AIWFile; cell::Real=20.0)
    wp = mainpath(aiw)
    n = length(wp)
    n >= 2 || throw(ArgumentError("AIW has too few main-path waypoints"))

    pos = [ntuple(j -> Float64(w.pos[j]), 3) for w in wp]
    perp = [unit(ntuple(j -> Float64(get(w.perp, j, 0.0)), 3)) for w in wp]
    nrm = [unit(ntuple(j -> Float64(get(w.normal, j, j == 2 ? 1.0 : 0.0)), 3)) for w in wp]
    hw = [(Float64(get(w.width, 1, 5.0)), Float64(get(w.width, 2, 5.0))) for w in wp]
    ld = [Float64(w.lapdist) for w in wp]

    # segment i connects waypoint i and i+1 (wrapping the closed lap)
    segs = collect(1:n)

    xs = [p[1] for p in pos]; zs = [p[3] for p in pos]
    x0, z0 = minimum(xs) - cell, minimum(zs) - cell
    nx = ceil(Int, (maximum(xs) + cell - x0) / cell)
    nz = ceil(Int, (maximum(zs) + cell - z0) / cell)
    buckets = [Int[] for _ in 1:nx*nz]
    cellof(x, z) = (clamp(floor(Int, (x - x0) / cell), 0, nx - 1),
                    clamp(floor(Int, (z - z0) / cell), 0, nz - 1))
    for s in segs
        a = pos[s]; b = pos[mod1(s + 1, n)]
        (ax, az), (bx, bz) = cellof(a[1], a[3]), cellof(b[1], b[3])
        for cx in min(ax, bx):max(ax, bx), cz in min(az, bz):max(az, bz)
            push!(buckets[cz*nx + cx + 1], s)
        end
    end

    TrackSurface(pos, perp, nrm, hw, ld, segs, Float64(cell), x0, z0, nx, nz,
                 buckets, aiw.lap_length)
end

"""
    TrackSurface(pts::Vector{NTuple{3,Float64}}; halfwidth=8.0, cell=20.0)

Build the ribbon from a raw ordered centreline (closed loop) — for non-rFactor
tracks (GPL .trk).  `pts` are (x, y, z) with y the surface height.  perp = left
of the horizontal tangent, normal = up, lapdist = cumulative horizontal distance.
"""
function TrackSurface(pts::Vector{NTuple{3,Float64}}; halfwidth::Real=8.0, cell::Real=20.0)
    n = length(pts); n >= 2 || throw(ArgumentError("need ≥2 centreline points"))
    pos = pts
    perp = NTuple{3,Float64}[]; nrm = NTuple{3,Float64}[]
    hw = NTuple{2,Float64}[]; ld = Float64[]; d = 0.0
    for i in 1:n
        a = pos[i]; bn = pos[mod1(i+1, n)]
        tx = bn[1]-a[1]; tz = bn[3]-a[3]; tl = hypot(tx, tz); tl < 1e-6 && (tl = 1.0)
        push!(perp, (-tz/tl, 0.0, tx/tl)); push!(nrm, (0.0,1.0,0.0))
        push!(hw, (Float64(halfwidth), Float64(halfwidth))); push!(ld, d)
        d += hypot(bn[1]-a[1], bn[3]-a[3])
    end
    segs = collect(1:n)
    xs = [p[1] for p in pos]; zs = [p[3] for p in pos]
    x0, z0 = minimum(xs)-cell, minimum(zs)-cell
    nx = ceil(Int, (maximum(xs)+cell-x0)/cell); nz = ceil(Int, (maximum(zs)+cell-z0)/cell)
    buckets = [Int[] for _ in 1:nx*nz]
    cellof(x,z) = (clamp(floor(Int,(x-x0)/cell),0,nx-1), clamp(floor(Int,(z-z0)/cell),0,nz-1))
    for s in segs
        a = pos[s]; b = pos[mod1(s+1,n)]; (ax,az),(bx,bz) = cellof(a[1],a[3]), cellof(b[1],b[3])
        for cx in min(ax,bx):max(ax,bx), cz in min(az,bz):max(az,bz)
            push!(buckets[cz*nx + cx + 1], s)
        end
    end
    TrackSurface(pos, perp, nrm, hw, ld, segs, Float64(cell), x0, z0, nx, nz, buckets, d)
end

"""Result of a HAT query at a world (x, z)."""
struct HATResult
    height::Float64
    normal::NTuple{3,Float64}
    on_track::Bool
    lateral::Float64      # signed offset from centerline (m, + along perp)
    lapdist::Float64      # distance into lap at the projection (m)
    found::Bool           # false if no ribbon segment is near (x, z)
    perp::NTuple{2,Float64}  # horizontal lateral unit vector (x, z) — for boundary correction
end

"""
    hat(ts, x, z) -> HATResult

Surface height, normal, on-track flag, lateral offset and lap distance at
world position (x, z).  Searches the query cell and its 8 neighbours.
"""
# E92 (from E80): count and time hat() so per-query cost is MEASURED, not divided out.
# E80-S4 attributed the trackside block's 1.34x super-linearity to "HAT-cell density", but the
# structures say the opposite: Watkins is 450 segments over 1813 cells (0.248/cell) while Spa is
# 1180 over 28880 (0.041/cell) -- Spa is 6x SPARSER, and its TriangleHAT is finer too (1.83 vs
# 4.41 tris/cell). Density predicts Spa should be FASTER per query. So the standing explanation is
# probably wrong, and dividing a phase time by an instance count cannot tell the difference --
# the same mistake that made the billboard estimate 20x too high in E80-S4.
# JM_HAT_COUNT=1 counts calls; JM_HAT_TIME=1 also accumulates nanoseconds (adds overhead, so it is
# separate). Report with JuliaMotor.hat_stats().
const HAT_CALLS = Ref(0)
const HAT_NS    = Ref(0)
const HAT_COUNT_ON = Ref(false)
const HAT_TIME_ON  = Ref(false)
function hat_stats()
    c = HAT_CALLS[]; ns = HAT_NS[]
    (calls = c, total_s = ns/1e9, per_call_us = c == 0 ? 0.0 : ns/1e3/c)
end
hat_reset!() = (HAT_CALLS[] = 0; HAT_NS[] = 0; nothing)

# ---------------------------------------------------------------------------------------------
# SEAM-1 (PO 2026-09-26: "AI cars skitter (jump sideways) ... often at corners ... the places where
# they do this often coincide with locations where the user's car jolts or bounces ... seams in the
# road surface, where the track is piecewise linear rather than smooth").
#
# The ribbon's (lapdist, lateral) pair is the TRACK FRAME: every surface query the sim makes on the
# tarmac -- the .trk altitude spline for the player's ground, the AI's road height -- is evaluated at
# these two coordinates. Projecting onto the 3 m POLYLINE makes that frame only C0, and the clamp
# t in [0,1] makes it WORSE than C0 near a node: on the inside of a corner the nearest segment
# switches (a seam), and on the outside both segments clamp to the node (a fan where lapdist
# stalls). A perfectly smooth height spline read at a kinked coordinate is a kinked surface.
#
# MEASURED before the fix (demo/native/seam_probe.jl, Watkins Glen, a car on a smooth path at
# 25 m/s, vertical-velocity step per 1/60 s frame, p99 / max):
#   lateral +0 m: 0.045 / 0.140 m/s      the same spline at the TRUE arc length: 0.011 / 0.017
#   lateral +2 m: 0.198 / 0.531 m/s                                              0.010 / 0.016
#   lateral +4 m: 0.383 / 0.953 m/s                                              0.011 / 0.015
# The step scales with the LATERAL OFFSET (0.045 -> 0.198 -> 0.383) and vanishes when the same
# spline is read at the true arc length, which is the signature of the frame and not of the surface;
# the worst 5 % of steps sit at curvature 0.0055-0.0087 /m (R = 115-180 m) against a lap median of
# 0.0011 /m (R = 918 m), i.e. IN THE CORNERS. 0.95 m/s in one frame is a 58 m/s^2 impulse.
#
# THE FIX: project onto the Catmull-Rom curve through the same nodes instead. It is the curve the AI
# rail already uses for its poses (RaceAI.pose_at), it passes through every node so no geometry
# moves, and it is C1 -- so the foot point, and with it lapdist and lateral, vary smoothly as the
# car drives, INCLUDING across a node. Newton on g(u) = |C(u) - q|^2 from the polyline's own answer:
# two or three steps, and because both neighbouring segments converge to the same foot point the
# segment the search happened to pick no longer shows up in the answer. JM_HAT_POLYLINE=1 restores
# the polyline projection exactly, as the A/B control.
@inline _cr(p0, p1, p2, p3, t) =
    0.5 * (2p1 + (-p0 + p2)*t + (2p0 - 5p1 + 4p2 - p3)*t^2 + (-p0 + 3p1 - 3p2 + p3)*t^3)
@inline _crd(p0, p1, p2, p3, t) =
    0.5 * ((-p0 + p2) + 2t*(2p0 - 5p1 + 4p2 - p3) + 3t*t*(-p0 + 3p1 - 3p2 + p3))
@inline _crdd(p0, p1, p2, p3, t) =
    0.5 * (2*(2p0 - 5p1 + 4p2 - p3) + 6t*(-p0 + 3p1 - 3p2 + p3))

# ⚠ READ AT RUNTIME, NOT AT PRECOMPILE. `Ref(get(ENV, ...))` at module scope is evaluated when the
# package is PRECOMPILED and baked into the cache, so the control arm silently ran the treatment:
# JM_HAT_POLYLINE=1 reproduced the treatment's numbers to five decimals, which reads as "the fix
# does nothing" rather than "the switch is dead". (This project has booked that class of instrument
# fault three times -- see the AI-skittering sprints.) First call resolves it; hat_polyline!() sets it.
const HAT_POLYLINE = Ref(false)
const HAT_POLY_SEEN = Ref(false)
@inline function hat_polyline()
    if !HAT_POLY_SEEN[]
        HAT_POLYLINE[] = get(ENV, "JM_HAT_POLYLINE", "0") != "0"
        HAT_POLY_SEEN[] = true
    end
    HAT_POLYLINE[]
end
"""Project onto the polyline instead of the C1 curve (SEAM-1 A/B control)."""
hat_polyline!(on::Bool) = (HAT_POLYLINE[] = on; HAT_POLY_SEEN[] = true; on)

"""Foot point of (x,z) on the Catmull-Rom ribbon curve, refined from segment `seg`, parameter `t`.
Returns `(seg, t)` with t in [0,1]; the search MIGRATES across nodes so it follows one foot point
rather than one segment (that migration is what makes the frame continuous at a node)."""
@inline function _ribbon_foot(ts::TrackSurface, seg::Int, t::Float64, x::Float64, z::Float64)
    n = length(ts.pos)
    n < 4 && return (seg, clamp(t, 0.0, 1.0))
    @inbounds for _ in 1:3
        i = seg; h = mod1(i-1, n); j = mod1(i+1, n); k = mod1(i+2, n)
        ax, bx, cx2, dx2 = ts.pos[h][1], ts.pos[i][1], ts.pos[j][1], ts.pos[k][1]
        az, bz, cz2, dz2 = ts.pos[h][3], ts.pos[i][3], ts.pos[j][3], ts.pos[k][3]
        ex = _cr(ax, bx, cx2, dx2, t) - x;  ez = _cr(az, bz, cz2, dz2, t) - z
        d1x = _crd(ax, bx, cx2, dx2, t);    d1z = _crd(az, bz, cz2, dz2, t)
        d2x = _crdd(ax, bx, cx2, dx2, t);   d2z = _crdd(az, bz, cz2, dz2, t)
        g1 = ex*d1x + ez*d1z                       # d/dt of |C-q|^2 / 2
        g2 = d1x*d1x + d1z*d1z + ex*d2x + ez*d2z   # its derivative
        # g2 <= 0 means this stationary point is a MAXIMUM of the distance, not a minimum (a query far
        # off the ribbon, or inside the curve's centre of curvature): Newton would step AWAY from the
        # foot. Keep the chord's answer there instead -- exactly what the polyline did.
        g2 <= 1e-9 && break
        step = clamp(-g1/g2, -0.5, 0.5)            # a node is one unit of t: never leap more than half
        t += step
        if t < 0.0                                 # walked off the near end -> the previous segment
            seg = mod1(seg - 1, n); t += 1.0
        elseif t > 1.0                              # ... or the far end -> the next one
            seg = mod1(seg + 1, n); t -= 1.0
        end
        abs(step) < 1e-6 && break
    end
    (seg, clamp(t, 0.0, 1.0))
end

function hat(ts::TrackSurface, x::Real, z::Real)
    if HAT_COUNT_ON[]
        HAT_CALLS[] += 1
        if HAT_TIME_ON[]
            t0 = time_ns()
            r = _hat_impl(ts, x, z)
            HAT_NS[] += Int(time_ns() - t0)
            return r
        end
    end
    return _hat_impl(ts, x, z)
end

function _hat_impl(ts::TrackSurface, x::Real, z::Real)
    cx = clamp(floor(Int, (x - ts.x0) / ts.cell), 0, ts.nx - 1)
    cz = clamp(floor(Int, (z - ts.z0) / ts.cell), 0, ts.nz - 1)
    n = length(ts.pos)
    best = 0; bestd = Inf; bestt = 0.0
    for dz in -1:1, dx in -1:1
        gx, gz = cx + dx, cz + dz
        (0 <= gx < ts.nx && 0 <= gz < ts.nz) || continue
        for s in ts.buckets[gz*ts.nx + gx + 1]
            a = ts.pos[s]; b = ts.pos[mod1(s + 1, n)]
            abx, abz = b[1] - a[1], b[3] - a[3]
            len2 = abx^2 + abz^2
            len2 < 1e-9 && continue
            t = clamp(((x - a[1]) * abx + (z - a[3]) * abz) / len2, 0.0, 1.0)
            px, pz = a[1] + t * abx, a[3] + t * abz
            d = (x - px)^2 + (z - pz)^2
            if d < bestd
                bestd = d; best = s; bestt = t
            end
        end
    end
    best == 0 && return HATResult(0.0, (0.0, 1.0, 0.0), false, 0.0, 0.0, false, (1.0, 0.0))

    # SEAM-1: refine the polyline's answer to the foot point on the C1 curve through the same nodes.
    poly = hat_polyline()
    s, t = poly ? (best, bestt) : _ribbon_foot(ts, best, bestt, Float64(x), Float64(z))
    s2 = mod1(s + 1, n)
    a, b = ts.pos[s], ts.pos[s2]
    pp = unit((ts.perp[s][1] + t * (ts.perp[s2][1] - ts.perp[s][1]),
               ts.perp[s][2] + t * (ts.perp[s2][2] - ts.perp[s][2]),
               ts.perp[s][3] + t * (ts.perp[s2][3] - ts.perp[s][3])))
    nn = unit((ts.normal[s][1] + t * (ts.normal[s2][1] - ts.normal[s][1]),
               ts.normal[s][2] + t * (ts.normal[s2][2] - ts.normal[s][2]),
               ts.normal[s][3] + t * (ts.normal[s2][3] - ts.normal[s][3])))
    # centreline point, height and lateral direction ON THE CURVE (the polyline arm keeps the chord)
    local cx0, cz0, cy, ppx, ppz
    if poly
        cx0 = a[1] + t * (b[1] - a[1]); cz0 = a[3] + t * (b[3] - a[3])
        cy  = a[2] + t * (b[2] - a[2])
        ppx = pp[1]; ppz = pp[3]
    else
        h4 = mod1(s - 1, n); k4 = mod1(s + 2, n)
        p0, p1, p2, p3 = ts.pos[h4], ts.pos[s], ts.pos[s2], ts.pos[k4]
        cx0 = _cr(p0[1], p1[1], p2[1], p3[1], t); cz0 = _cr(p0[3], p1[3], p2[3], p3[3], t)
        cy  = _cr(p0[2], p1[2], p2[2], p3[2], t)      # centreline height is C1 too, not a chord
        tx  = _crd(p0[1], p1[1], p2[1], p3[1], t); tz = _crd(p0[3], p1[3], p2[3], p3[3], t)
        tl  = hypot(tx, tz)
        # left normal of the CURVE tangent (the same convention the node perps are built with)
        ppx, ppz = tl < 1e-9 ? (pp[1], pp[3]) : (-tz/tl, tx/tl)
    end
    # signed lateral offset of (x,z) from the centreline, along perp(x,z)
    lat = (x - cx0) * ppx + (z - cz0) * ppz
    # banking: moving `lat` along perp changes height by lat * perp.y
    height = cy + lat * pp[2]
    hwl = ts.halfwidth[s][1] + t * (ts.halfwidth[s2][1] - ts.halfwidth[s][1])
    hwr = ts.halfwidth[s][2] + t * (ts.halfwidth[s2][2] - ts.halfwidth[s][2])
    ontrack = -hwr <= lat <= hwl
    # TRACKSMOOTH-3 (2026-09-19): on the WRAP segment (last node -> node 1) lapdist[s2] is 0, so the
    # lerp ran 3769 -> 0 and a point 0.6 m from the line read as lapdist 2287 -- and any consumer of
    # lapdist near the start/finish (the .trk surface, lap fractions) got a mid-lap answer. The far end
    # of the wrap segment is the lap length, not 0.
    ld2 = s2 == 1 ? ts.lap_length : ts.lapdist[s2]
    # SEAM-1 note: lapdist stays LINEAR in the segment parameter. Making it arc-length-exact along
    # the curve (two-point Gauss on |C'|, normalised per segment) was tried and measured: Watkins
    # Glen, 4 m off the centreline, p99 vertical-velocity step 0.0241 -> 0.0241 m/s and max 0.0613 ->
    # 0.0616. It buys nothing, so the flops are not spent in the sim's hottest query.
    ld = ts.lapdist[s] + t * (ld2 - ts.lapdist[s])
    ld >= ts.lap_length && (ld -= ts.lap_length)
    HATResult(height, nn, ontrack, lat, ld, true, (ppx, ppz))
end
