# gplwall.jl — GPLWALL-1: GPL's own walls, read from the .trk, as a hard boundary in TRACK coordinates.
#
# GPL does not collide a car with scenery meshes. Every .trk section carries a strip list across the
# track, left to right; each 32-byte record is
#     i32 lat_at_section_start, i32 lat_at_section_end   (TRK units, 19685.04 per metre; - = left)
#     i32 type                                           (low bits = surface; bit 0x800 = RAISED)
#     i32 flags, i32 height (TRK units), 3 x i32 unused here
# Bit 0x800 is GPLTrk's "or-in 2048 to give a wall a non-zero height": without it the height does not apply.
# So 0x80A is a raised wall, 0x804 a raised grass bank, and 0x8xx with height 0 is FLAT (Spa has 176, all
# zero thickness). A raised strip BLOCKS the car only when it is taller than the car can climb (`hmin`).
# GPL's track .3do carries no collision; it all comes from the .trk (GPL track-making notes).
# A strip runs from its own edge to the next record's edge. The first record's edge is the world's left
# edge and the last record (type 10, exactly one per section) is the right edge. Section record i32[11]
# is the strip count and i32[12] the index of its first strip (verified: cumulative, sums to the block).
# Decoded 2026-10-01 from Watkins Glen; wall heights read 0.76 m (armco), 0.91 m and 1.22 m.
#
# The car is contained by the walls: anything left of the leftmost free edge or right of the rightmost
# is OUT, so there is no wall thickness to tunnel through. That is the property this file exists for.
module GPLWall

export Strip, Walls, read_walls, free_interval

const TRK = 19685.03937
const WALLBIT = 0x800

struct Strip
    l0::Float64      # lateral edge at section start (m, + = right in GPL's frame)
    l1::Float64      # lateral edge at section end
    typ::Int         # raw type word
    wall::Bool       # raised (0x800)
    height::Float64  # m (raised strips only)
end

struct Walls
    secs::Vector{Vector{Strip}}
    seclen::Vector{Float64}          # m
    E::Vector{Matrix{Float64}}       # per section: edge lateral of record k at f = (j-1)/NF, j = 1..NF+1 (registrable)
end
const NF = 10

function read_walls(b::AbstractVector{UInt8})
    u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o))
    traces = Int(u32(12)); sections = Int(u32(16)); wallsize = Int(u32(20))
    wb = 28 + 64 + sections*4 + 32*traces*sections
    sb = wb + wallsize
    nrec = wallsize ÷ 32
    secs = Vector{Vector{Strip}}(undef, sections); seclen = zeros(sections)
    for s in 0:sections-1
        seclen[s+1] = i32(sb + s*52 + 8) / TRK
        cnt = Int(i32(sb + s*52 + 44)); first = Int(i32(sb + s*52 + 48))
        (first < 0 || first + cnt > nrec) && error("GPLWall: section $s strip range $first+$cnt outside $nrec records")
        v = Strip[]
        for k in first:first+cnt-1
            o = wb + 32k
            t = Int(i32(o + 8))
            push!(v, Strip(i32(o)/TRK, i32(o + 4)/TRK, t, (t & WALLBIT) != 0, i32(o + 16)/TRK))
        end
        secs[s+1] = v
    end
    E = [[st.l0 + (st.l1 - st.l0)*(j - 1)/NF for st in v, j in 1:NF+1] for v in secs]
    Walls(secs, seclen, E)
end

edge(st::Strip, f) = st.l0 + (st.l1 - st.l0)*f          # GPL's own (unregistered) edge
"edge lateral of record k in section sec at fraction f, from the (possibly registered) table"
@inline function edge(W::Walls, sec::Int, k::Int, f::Float64)
    E = W.E[sec]; t = clamp(f, 0.0, 1.0)*NF; j = min(floor(Int, t), NF - 1) + 1; u = t - (j - 1)
    E[k, j] + (E[k, j+1] - E[k, j])*u
end

"""    free_interval(W, sec, f, lat, prev) -> (lo, hi, hlo, hhi)

The open lateral interval the car may occupy in section `sec` (1-based) at fraction `f`: bounded by the
nearest wall strip or world edge on each side. `lo`/`hi` are the wall FACES (m, GPL lateral), `hlo`/`hhi`
their heights (Inf at a world edge). If `lat` lies inside a wall (the car has penetrated past its centre),
the free interval nearest `prev` (last frame's lateral) is returned, so a deep hit is pushed back out the
side it came from, never through."""
function free_interval(W::Walls, sec::Int, f::Float64, lat::Float64, prev::Float64; hmin::Float64 = 0.25)
    v = W.secs[sec]; n = length(v)
    best = (-Inf, Inf, Inf, Inf); bestd = Inf
    lo = edge(W, sec, 1, f); hlo = Inf            # left world edge
    k = 1
    while k <= n
        st = v[k]
        e0 = edge(W, sec, k, f)
        if (st.wall && st.height >= hmin) || k == n   # a blocking wall, or the right world edge (last record)
            hi = e0; hhi = (k == n) ? Inf : st.height
            if hi > lo
                d = lat < lo ? lo - lat : lat > hi ? lat - hi : 0.0
                if d == 0.0
                    return (lo, hi, hlo, hhi)
                end
                dp = prev < lo ? lo - prev : prev > hi ? prev - hi : 0.0
                if dp < bestd
                    bestd = dp; best = (lo, hi, hlo, hhi)
                end
            end
            k == n && break
            lo = edge(W, sec, k + 1, f); hlo = st.height  # the wall's far face starts the next free run
        end
        k += 1
    end
    best
end

end # module
