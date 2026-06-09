# GMT meshes (gMotor2 / rFactor 1) — geometry for rendering and for the
# track collision surface (HAT).
#
# Format recovered empirically from this install (2026-06-06); see
# DOC/gmtFormat.md for the full annotated layout.  Confirmed so far:
#
#   0x00  u32   per-file signature (varies; obfuscated)
#   0x04  u32   0x04000020 version/flags (constant across the corpus)
#   0x08  float[3]×8   axis-aligned bounding box, 8 corners (meters,
#                      ISI frame: +x left, +y up, +z rearward)
#   0x180 u32[]  section header: [0x190] is the byte offset of the
#                vertex array; other slots hold counts/pointers that
#                differ between trivial and multi-group meshes
#   0x194 char[] object name (NUL-terminated)
#
#   vertex (32 bytes): pad(4) | position float3 | normal float3 | color u32
#                      (UVs live in a separate, non-interleaved array)
#   index  : u16 triangle list (3 per triangle)
#   materials: "<name>" then LOD texture slots "L0DIFFUSET0"… and the
#              referenced ".dds" texture names
#
# This loader decodes the validated single-group case end-to-end (the
# track surface pieces we need first).  Multi-group / multi-LOD vehicle
# meshes expose more groups off the header table — see `gmt_header`.

struct GMTMesh
    name::String
    bbox_min::Vector{Float64}
    bbox_max::Vector{Float64}
    positions::Vector{NTuple{3,Float32}}
    normals::Vector{NTuple{3,Float32}}
    triangles::Vector{NTuple{3,Int}}     # 0-based vertex indices
end

Base.show(io::IO, m::GMTMesh) =
    print(io, "GMTMesh(\"", m.name, "\", ", length(m.positions), " verts, ",
          length(m.triangles), " tris)")

const GMT_VERSION = 0x04000020

f32(b, o) = reinterpret(Float32, view(b, o+1:o+4))[1]
u32(b, o) = reinterpret(UInt32, view(b, o+1:o+4))[1]
u16(b, o) = reinterpret(UInt16, view(b, o+1:o+2))[1]

"""Bounding box (min, max) from the 8-corner block at 0x08."""
function gmt_bbox(b::Vector{UInt8})
    pts = [(f32(b, 8 + 12k), f32(b, 12 + 12k), f32(b, 16 + 12k)) for k in 0:7]
    mn = [minimum(p[j] for p in pts) for j in 1:3]
    mx = [maximum(p[j] for p in pts) for j in 1:3]
    Float64.(mn), Float64.(mx)
end

"""Object name at 0x194 (NUL-terminated)."""
function gmt_name(b::Vector{UInt8})
    stop = findfirst(==(0x00), view(b, 0x195:min(0x195 + 64, length(b))))
    String(b[0x195:(stop === nothing ? 0x195 + 64 : 0x193 + stop)])
end

"""Whether point `p` fits the bbox axis ranges under *some* axis permutation.
The bbox corner block stores axes as (x, z, height) while vertices are
(x, height, z); a permutation-tolerant test makes the in-box check (used as
the vertex-array cutoff) order-independent, while still excluding the UV
array that follows the vertices."""
function inbox_perm(p, mn, mx; pad=1.0)
    perms = ((1,2,3),(1,3,2),(2,1,3),(2,3,1),(3,1,2),(3,2,1))
    for q in perms
        all(mn[q[j]] - pad <= p[j] <= mx[q[j]] + pad for j in 1:3) && return true
    end
    false
end

"""
    gmt_header(b) -> NamedTuple

The section table at 0x180 (eight u32 slots).  `vptr` (= slot 0x190) is
the validated vertex-array byte offset; the remaining slots are surfaced
raw for the multi-group work.
"""
function gmt_header(b::Vector{UInt8})
    slots = [Int(u32(b, 0x180 + 4k)) for k in 0:7]
    (slots=slots, vptr=slots[5])
end

"""
    parse_gmt(bytes) -> GMTMesh

Decode the geometry of a single-group GMT.  Vertex count and the index
array are located from the layout: vertices run from `vptr` until the UV
array, and the u16 index list follows the UV/material padding.  Verified
against `GROUNDPLANE.GMT` (Zandvoort): 6 verts, 2 triangles, normals up.
"""
function parse_gmt(b::Vector{UInt8})
    u32(b, 4) == GMT_VERSION ||
        @warn "unexpected GMT version $(string(u32(b,4); base=16))"
    bmin, bmax = gmt_bbox(b)
    vptr = gmt_header(b).vptr

    # The vertex count is NOT bounded by the in-box positions — the per-vertex
    # attribute arrays that follow (normals/UVs, small near-origin values) are
    # also "in box".  Instead derive it from the index array: find the u16
    # triangle-list run after the vertices and take nverts = max index + 1.
    tris, nverts = find_index_run(b, vptr)

    positions = Vector{NTuple{3,Float32}}(undef, nverts)
    normals = Vector{NTuple{3,Float32}}(undef, nverts)
    for k in 0:nverts-1
        o = vptr + 32k
        positions[k+1] = (f32(b, o + 4), f32(b, o + 8), f32(b, o + 12))
        normals[k+1] = (f32(b, o + 16), f32(b, o + 20), f32(b, o + 24))
    end
    GMTMesh(gmt_name(b), bmin, bmax, positions, normals, tris)
end

"""
Locate the u16 triangle-list index run and the implied vertex count.

These meshes store geometry as a **sequential** triangle soup: the index
array is exactly `0,1,2,…,3·ntri-1` (each vertex used once, in draw
order).  So the array is the longest run of u16 with `index[k] == k`,
starting at 0, whose implied vertex block (`len·32` bytes from `vptr`)
fits before it.  Detecting the strict sequence is unambiguous — it can't
be faked by coincidental attribute bytes the way a "longest valid run"
heuristic can.  Returns `(triangles, nverts)`.
"""
function find_index_run(b::Vector{UInt8}, vptr::Int)
    N = length(b)
    best_o = 0; best_len = 0
    o = vptr
    while o + 2 <= N
        if u16(b, o) == 0                  # a sequence can only start at 0
            len = 0
            while o + 2 * len + 2 <= N && Int(u16(b, o + 2 * len)) == len
                len += 1
            end
            len -= len % 3                 # whole triangles only
            if len >= 3 && vptr + len * 32 <= o && len > best_len
                best_len = len; best_o = o
            end
            o += 2 * max(len, 1)
        else
            o += 2
        end
    end
    best_len == 0 && return NTuple{3,Int}[], 0
    ntri = best_len ÷ 3
    tris = [(3t, 3t + 1, 3t + 2) for t in 0:ntri-1]   # sequential by construction
    tris, best_len
end

"""
    read_gmt_from_mas(mas, name) -> GMTMesh

Extract and decode a mesh directly from a MAS archive.
"""
read_gmt_from_mas(m::MASFile, name::AbstractString) = parse_gmt(extract(m, name))

"""
    parse_gmt_uv(bytes) -> (positions, normals, uvs, triangles, texture)

Decode a sequential-soup GMT *with* its diffuse texture coordinates and the
diffuse texture filename — the data the renderer needs for texturing.

UVs live in a separate per-vertex attribute array immediately after the vertex
block (`vptr + nverts*32`); its stride is material-dependent (16 B plain, ~56 B
with bump/spec maps), and the **diffuse `(u,v)` is the first two floats** of each
attribute record.  The stride is recovered exactly as
`(index_offset − attr_start) / nverts`.  `texture` is the first `*.dds`
filename in the material section after the indices (the L0 diffuse slot);
`""` if none.  UVs are `(0,0)` if the attribute array is too thin to hold them.
"""
function parse_gmt_uv(b::Vector{UInt8})
    N = length(b)
    vptr = gmt_header(b).vptr
    # strict-sequential index run → (offset, length)
    io = 0; ilen = 0; o = vptr
    while o + 2 <= N
        if u16(b, o) == 0
            len = 0
            while o + 2len + 2 <= N && Int(u16(b, o + 2len)) == len; len += 1; end
            len -= len % 3
            if len >= 3 && vptr + len*32 <= o && len > ilen; ilen = len; io = o; end
            o += 2*max(len, 1)
        else
            o += 2
        end
    end
    nv = ilen
    nv == 0 && return (NTuple{3,Float32}[], NTuple{3,Float32}[], NTuple{2,Float32}[], NTuple{3,Int}[], "")
    pos = Vector{NTuple{3,Float32}}(undef, nv); nrm = Vector{NTuple{3,Float32}}(undef, nv)
    for k in 0:nv-1
        p = vptr + 32k
        pos[k+1] = (f32(b, p+4), f32(b, p+8), f32(b, p+12))
        nrm[k+1] = (f32(b, p+16), f32(b, p+20), f32(b, p+24))
    end
    attr = vptr + 32nv
    stride = nv > 0 ? (io - attr) ÷ nv : 0
    uvs = Vector{NTuple{2,Float32}}(undef, nv)
    for k in 0:nv-1
        uvs[k+1] = stride >= 8 ? (f32(b, attr + stride*k), f32(b, attr + stride*k + 4)) : (0.0f0, 0.0f0)
    end
    tris = [(3t, 3t+1, 3t+2) for t in 0:(ilen÷3)-1]
    # diffuse texture: first *.dds string in the material section after indices
    tex = ""
    s = io + 2*ilen
    run = IOBuffer()
    while s < N
        c = b[s+1]
        if 0x20 <= c <= 0x7e
            write(run, Char(c))
        else
            str = String(take!(run))
            if endswith(lowercase(str), ".dds"); tex = str; break; end
        end
        s += 1
    end
    (pos, nrm, uvs, tris, tex)
end

"""
    parse_gmt_indexed(bytes) -> GMTMesh

Decode a **multi-group / indexed** GMT — the richer layout used by car body /
cockpit meshes, which `parse_gmt` (sequential triangle-soup only) cannot read.

Layout (reverse-engineered 2026-06-08 against `Vanwall_body.gmt`):
  * vertex count from the header word at `0x17c`;
  * vertices stride-32, position at `+4`, normal (unit) at `+16` (as `parse_gmt`);
  * after the vertex block come non-interleaved attribute arrays (UVs, …) and
    then one or more u16 **index** runs (the mesh is genuinely indexed —
    vertices shared — so the index list is NOT the sequential `0,1,2,…`).

The index runs are found as long stretches of u16 all `< nverts` that are NOT
float-attribute noise: UV floats put ~half their u16 halves in the float
exponent band `[16000,16500]`, real indices spread uniformly, so a low
band-fraction discriminates them.  Verified: the body decodes to ~24 k
triangles forming the recognisable Vanwall shape (nose, cockpit, wheel arches).
Degenerate triangles (repeated index) are dropped.
"""
function parse_gmt_indexed(b::Vector{UInt8})
    N = length(b)
    bmin, bmax = gmt_bbox(b)
    vptr = Int(u32(b, 0x190))
    nv = Int(u32(b, 0x17c))
    (nv <= 0 || vptr + 32nv > N) && return GMTMesh(gmt_name(b), bmin, bmax,
        NTuple{3,Float32}[], NTuple{3,Float32}[], NTuple{3,Int}[])
    positions = Vector{NTuple{3,Float32}}(undef, nv)
    normals = Vector{NTuple{3,Float32}}(undef, nv)
    for k in 0:nv-1
        o = vptr + 32k
        positions[k+1] = (f32(b, o + 4), f32(b, o + 8), f32(b, o + 12))
        normals[k+1] = (f32(b, o + 16), f32(b, o + 20), f32(b, o + 24))
    end
    band(o, w=96) = o + 2w > N ? 1.0 :
        count(j -> 16000 <= Int(u16(b, o + 2j)) <= 16500, 0:w-1) / w
    tris = NTuple{3,Int}[]
    o = vptr + 32nv
    while o + 2 <= N
        if Int(u16(b, o)) < nv && band(o) < 0.03
            s = o; len = 0
            while o + 2 <= N && Int(u16(b, o)) < nv && band(o) < 0.10
                len += 1; o += 2
            end
            if len >= 600                      # a real index block (≥ 200 tris)
                for t in 0:(len ÷ 3)-1
                    a = Int(u16(b, s + 6t)); c = Int(u16(b, s + 6t + 2)); d = Int(u16(b, s + 6t + 4))
                    (a != c && c != d && a != d) && push!(tris, (a, c, d))
                end
            end
        else
            o += 2
        end
    end
    GMTMesh(gmt_name(b), bmin, bmax, positions, normals, tris)
end
