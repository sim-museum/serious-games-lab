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

    s = best; t = bestt; s2 = mod1(s + 1, n)
    a, b = ts.pos[s], ts.pos[s2]
    cy = a[2] + t * (b[2] - a[2])                       # centerline height
    pp = unit((ts.perp[s][1] + t * (ts.perp[s2][1] - ts.perp[s][1]),
               ts.perp[s][2] + t * (ts.perp[s2][2] - ts.perp[s][2]),
               ts.perp[s][3] + t * (ts.perp[s2][3] - ts.perp[s][3])))
    nn = unit((ts.normal[s][1] + t * (ts.normal[s2][1] - ts.normal[s][1]),
               ts.normal[s][2] + t * (ts.normal[s2][2] - ts.normal[s][2]),
               ts.normal[s][3] + t * (ts.normal[s2][3] - ts.normal[s][3])))
    # signed lateral offset of (x,z) from the centerline, along perp(x,z)
    cx0, cz0 = a[1] + t * (b[1] - a[1]), a[3] + t * (b[3] - a[3])
    lat = (x - cx0) * pp[1] + (z - cz0) * pp[3]
    # banking: moving `lat` along perp changes height by lat * perp.y
    height = cy + lat * pp[2]
    hwl = ts.halfwidth[s][1] + t * (ts.halfwidth[s2][1] - ts.halfwidth[s][1])
    hwr = ts.halfwidth[s][2] + t * (ts.halfwidth[s2][2] - ts.halfwidth[s][2])
    ontrack = -hwr <= lat <= hwl
    ld = ts.lapdist[s] + t * (ts.lapdist[s2] - ts.lapdist[s])
    HATResult(height, nn, ontrack, lat, ld, true, (pp[1], pp[3]))
end
