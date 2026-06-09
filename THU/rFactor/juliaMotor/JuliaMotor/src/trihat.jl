# TriangleHAT — track surface from the actual collision-mesh triangles.
#
# The AIW-ribbon `TrackSurface` is fast and carries lap distance / lateral,
# but its 2D nearest-segment projection mis-snaps where track sections run
# parallel or stack (Zandvoort's main straight vs return road: p90 ~5 m).
# This builds the surface from the GMT triangles the SCN flags
# `HATTarget=True` and answers height/normal by exact point-in-triangle —
# p90 ~0.13 m against the AIW racing line, no ambiguity tail.  A uniform
# X–Z grid keeps queries O(triangles-per-cell) for real-time use.

struct Tri
    a::NTuple{3,Float64}
    b::NTuple{3,Float64}
    c::NTuple{3,Float64}
end

struct TriangleHAT
    tris::Vector{Tri}
    cell::Float64
    x0::Float64
    z0::Float64
    nx::Int
    nz::Int
    buckets::Vector{Vector{Int}}
end

Base.show(io::IO, t::TriangleHAT) =
    print(io, "TriangleHAT(", length(t.tris), " triangles, grid ",
          t.nx, "×", t.nz, ")")

"""
    hat_meshes(scn_dir) -> Vector{String}

Mesh filenames flagged `HATTarget=True` in the track's `.scn` (the
collision/drivable surfaces).
"""
function hat_meshes(scn_dir::AbstractString)
    scn_path = only(filter(p -> endswith(lowercase(p), ".scn"),
                           readdir(scn_dir; join=true)))
    scn = read_gen(scn_path)
    names = String[]
    for st in gen_statements(scn, "MeshFile")
        pairs = Dict(lowercase(k) => v for (k, v) in st.pairs)
        get(pairs, "hattarget", "") == "True" &&
            push!(names, lowercase(string(RFactorData.value(st))))
    end
    names
end

"""
    TriangleHAT(track_dir; cell=15.0) -> TriangleHAT

Build the collision surface for a track: read its `.scn` for the
`HATTarget` meshes, extract their triangles from the directory's `.mas`
archives into world space, and index them on a uniform X–Z grid.
"""
function TriangleHAT(track_dir::AbstractString; cell::Real=15.0)
    want = Set(hat_meshes(track_dir))
    tris = Tri[]
    for maspath in filter(p -> endswith(lowercase(p), ".mas"),
                          readdir(track_dir; join=true))
        m = read_mas(maspath)
        for e in m.entries
            lowercase(e.name) in want || continue
            g = parse_gmt(extract(m, e))
            P = g.positions
            for t in g.triangles
                push!(tris, Tri(Float64.(P[t[1]+1]), Float64.(P[t[2]+1]),
                                Float64.(P[t[3]+1])))
            end
        end
    end
    isempty(tris) && throw(ArgumentError("no HAT triangles found in $track_dir"))

    xs = Float64[]; zs = Float64[]
    for t in tris, v in (t.a, t.b, t.c)
        push!(xs, v[1]); push!(zs, v[3])
    end
    x0, z0 = minimum(xs) - cell, minimum(zs) - cell
    nx = ceil(Int, (maximum(xs) + cell - x0) / cell)
    nz = ceil(Int, (maximum(zs) + cell - z0) / cell)
    buckets = [Int[] for _ in 1:nx*nz]
    cidx(x, z) = (clamp(floor(Int, (x - x0) / cell), 0, nx - 1),
                  clamp(floor(Int, (z - z0) / cell), 0, nz - 1))
    for (i, t) in enumerate(tris)
        txmin = min(t.a[1], t.b[1], t.c[1]); txmax = max(t.a[1], t.b[1], t.c[1])
        tzmin = min(t.a[3], t.b[3], t.c[3]); tzmax = max(t.a[3], t.b[3], t.c[3])
        (cxlo, czlo) = cidx(txmin, tzmin); (cxhi, czhi) = cidx(txmax, tzmax)
        for cx in cxlo:cxhi, cz in czlo:czhi
            push!(buckets[cz*nx + cx + 1], i)
        end
    end
    TriangleHAT(tris, Float64(cell), x0, z0, nx, nz, buckets)
end

# barycentric point-in-triangle (X–Z plane) + interpolated height
@inline function tri_height(t::Tri, px, pz)
    ax, az = t.a[1], t.a[3]; bx, bz = t.b[1], t.b[3]; cx, cz = t.c[1], t.c[3]
    d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
    abs(d) < 1e-9 && return (false, 0.0)
    l1 = ((bz - cz) * (px - cx) + (cx - bx) * (pz - cz)) / d
    l2 = ((cz - az) * (px - cx) + (ax - cx) * (pz - cz)) / d
    l3 = 1.0 - l1 - l2
    inside = l1 >= -1e-4 && l2 >= -1e-4 && l3 >= -1e-4
    (inside, l1 * t.a[2] + l2 * t.b[2] + l3 * t.c[2])
end

@inline function tri_normal(t::Tri)
    ux, uy, uz = t.b[1]-t.a[1], t.b[2]-t.a[2], t.b[3]-t.a[3]
    vx, vy, vz = t.c[1]-t.a[1], t.c[2]-t.a[2], t.c[3]-t.a[3]
    nx, ny, nz = uy*vz - uz*vy, uz*vx - ux*vz, ux*vy - uy*vx
    n = sqrt(nx^2 + ny^2 + nz^2)
    n < 1e-12 ? (0.0, 1.0, 0.0) : (ny < 0 ? (-nx/n, -ny/n, -nz/n) : (nx/n, ny/n, nz/n))
end

"""
    hat3d(th, x, z; ref=Inf) -> (height, normal, found)

Surface height and upward normal under world (x, z) from the collision
triangles.  When several surfaces overlap (track over terrain, bridges),
returns the topmost triangle at or below `ref` (default: the very top),
so a car queries the surface it is on.
"""
function hat3d(th::TriangleHAT, x::Real, z::Real; ref::Real=Inf)
    cx = clamp(floor(Int, (x - th.x0) / th.cell), 0, th.nx - 1)
    cz = clamp(floor(Int, (z - th.z0) / th.cell), 0, th.nz - 1)
    besth = -Inf; bestt = 0
    for i in th.buckets[cz*th.nx + cx + 1]
        inside, h = tri_height(th.tris[i], x, z)
        (inside && h <= ref + 0.5 && h > besth) && ((besth, bestt) = (h, i))
    end
    bestt == 0 && return (0.0, (0.0, 1.0, 0.0), false)
    (besth, tri_normal(th.tris[bestt]), true)
end
