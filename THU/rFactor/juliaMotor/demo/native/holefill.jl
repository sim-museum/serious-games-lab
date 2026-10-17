# TD261016-1 (s4) (PO 2026-10-16, Spa: "The two large rectangular holes in the ground rendering on the left after Stavelot
# are still there"; first reported 2026-10-07 as TRACKS-TD-1 (b)). GPL's own spa67.3do has NO ground there: at s 8480-8560
# a strip 3-7 m wide between the tarmac edge and the guardrail line (x -1517..-1524, z -3270..-3310) is covered by no
# triangle at all (column probe of the raw mesh), and through it our renderer shows the horizon ring's lower art (hedges,
# straw). The gold shows grass. A census of the raw mesh finds such uncovered ground within 8 m of the tarmac at 66 places
# of 40 m2 or more round Spa.
#
# This fills them: every 2 m cell within FILL_NEAR of a road triangle that no non-vertical drawn triangle covers (in plan)
# gets a ground quad, at the height of the covered ground round it (median of the neighbours' heights, so a guardrail top
# or a roof does not lift it) and 5 cm under it (so where a cell overlaps real ground at its edge, the real ground wins the
# depth test). It takes the texture, part colour and vertex colour of the most common neighbouring ground part. Nothing
# that GPL draws is moved or removed. JM_HOLEFILL=0 = off.
module HoleFill
using ..Render
export holefill_parts

const STRIDE = 11                    # floats per vertex: position(3) normal(3) colour(3) uv(2)

# plan-view bucket index over the drawn triangles (render coords: x, up, z)
struct TriIndex
    cell::Float64
    tris::Vector{NTuple{9,Float32}}  # (x1,y1,z1, x2,y2,z2, x3,y3,z3)
    part::Vector{Int}
    b::Dict{Tuple{Int,Int},Vector{Int}}
end

function TriIndex(parts, keep; cell = 6.0)
    tris = NTuple{9,Float32}[]; part = Int[]; b = Dict{Tuple{Int,Int},Vector{Int}}()
    for (pi, p) in enumerate(parts)
        keep(p) || continue
        v = p.verts
        for k in 1:3STRIDE:length(v)-3STRIDE+1
            t = (v[k], v[k+1], v[k+2], v[k+STRIDE], v[k+STRIDE+1], v[k+STRIDE+2], v[k+2STRIDE], v[k+2STRIDE+1], v[k+2STRIDE+2])
            # non-vertical only: a fence or a wall does not cover the ground in plan
            ax, ay, az = t[4]-t[1], t[5]-t[2], t[6]-t[3]; bx, by, bz = t[7]-t[1], t[8]-t[2], t[9]-t[3]
            nx = ay*bz - az*by; ny = az*bx - ax*bz; nz = ax*by - ay*bx; nn = sqrt(nx^2 + ny^2 + nz^2)
            (nn > 1e-9 && abs(ny)/nn > 0.3) || continue
            push!(tris, t); push!(part, pi); i = length(tris)
            xs = (t[1], t[4], t[7]); zs = (t[3], t[6], t[9])
            for cx in floor(Int, minimum(xs)/cell):floor(Int, maximum(xs)/cell), cz in floor(Int, minimum(zs)/cell):floor(Int, maximum(zs)/cell)
                push!(get!(b, (cx, cz), Int[]), i)
            end
        end
    end
    TriIndex(cell, tris, part, b)
end

# every drawn surface over (x, z): (height, part index)
function column(ix::TriIndex, x, z)
    out = Tuple{Float64,Int}[]
    for i in get(ix.b, (floor(Int, x/ix.cell), floor(Int, z/ix.cell)), Int[])
        t = ix.tris[i]
        den = (t[6]-t[9])*(t[1]-t[7]) + (t[7]-t[4])*(t[3]-t[9]); abs(den) < 1e-12 && continue
        l1 = ((t[6]-t[9])*(x-t[7]) + (t[7]-t[4])*(z-t[9]))/den; l2 = ((t[9]-t[3])*(x-t[7]) + (t[1]-t[7])*(z-t[9]))/den
        (l1 >= -1e-4 && l2 >= -1e-4 && l1 + l2 <= 1 + 1e-4) || continue
        push!(out, (l1*t[2] + l2*t[5] + (1 - l1 - l2)*t[8], ix.part[i]))
    end
    out
end

"""
    holefill_parts(parts, isroad, isground; near = 10.0, step = 2.0, reach = 6.0, sink = 0.05) -> (Vector{TrackPart}, quads)

Ground quads for the uncovered cells within `near` m of a road triangle. `isroad(tex)` picks the tarmac, `isground(tex)`
the parts a filler may copy its look and height from.
"""
function holefill_parts(parts, isroad, isground; near = 10.0, step = 2.0, reach = 6.0, sink = 0.05)
    ix = TriIndex(parts, p -> true)
    # candidate cells: round every road vertex, out to `near`
    nr = ceil(Int, near/step); cand = Set{Tuple{Int,Int}}()
    for p in parts
        isroad(lowercase(p.tex)) || continue
        v = p.verts
        for k in 1:STRIDE:length(v)-STRIDE+1, dx in -nr:nr, dz in -nr:nr
            push!(cand, (round(Int, v[k]/step) + dx, round(Int, v[k+2]/step) + dz))
        end
    end
    holes0 = [c for c in cand if isempty(column(ix, step*c[1], step*c[2]))]
    isempty(holes0) && return Render.TrackPart[], 0
    holeset = Set(holes0)                    # the uncovered cell CENTRES: excluded from the height sampling
    # the hole's edge runs between cell centres, so a ring of covered cells round it still has an uncovered sliver: fill
    # those cells too (their corners on real ground sit `sink` under it, so where it exists the real ground wins)
    # -- but never a cell on the tarmac: one straddling the road edge would slope from the road up to the verge over the road
    onroad(c) = any(hp -> isroad(lowercase(parts[hp[2]].tex)), column(ix, step*c[1], step*c[2]))
    # cells centred on the tarmac lie FLAT at the road (under it): hidden by it, ground only in the sliver beside it
    ring = Set((c[1] + dx, c[2] + dz) for c in holes0 for dx in -1:1 for dz in -1:1)
    roadcells = Set(q for q in ring if !(q in holeset) && onroad(q))
    holes = collect(ring)
    # ground under a covered point near (x, z): the LOWEST ground-part surface there (a roof/rail sits above the ground)
    function ground_at(x, z)
        best = nothing
        for (h, pi) in column(ix, x, z)
            isground(lowercase(parts[pi].tex)) || continue
            (best === nothing || h < best[1]) && (best = (h, pi))
        end
        best
    end
    # corner heights: median of the ground round the corner within `reach`, among cells that are NOT holes
    rr = ceil(Int, reach/step); cornerh = Dict{Tuple{Int,Int},Float64}(); cornerp = Dict{Tuple{Int,Int},Int}()
    function corner(ci, cj)                     # corner (ci, cj) sits at ((ci - 0.5) step, (cj - 0.5) step)
        haskey(cornerh, (ci, cj)) && return cornerh[(ci, cj)]
        # a corner ON drawn ground (the tarmac edge, the verge) meets it: the lowest surface there, so the filler joins the
        # real ground instead of standing above the road beside it
        col0 = column(ix, step*(ci - 0.5), step*(cj - 0.5))
        if !isempty(col0)
            g = ground_at(step*(ci - 0.5), step*(cj - 0.5))
            g === nothing || (cornerp[(ci, cj)] = g[2])
            return cornerh[(ci, cj)] = minimum(first.(col0))
        end
        hs = Float64[]; votes = Dict{Int,Int}()
        for d in 1:rr                            # nearest ring first; stop at the first ring that has ground
            for dx in -d:d, dz in -d:d
                max(abs(dx), abs(dz)) == d || continue
                q = (ci + dx, cj + dz); q in holeset && continue
                g = ground_at(step*(q[1] - 0.5), step*(q[2] - 0.5)); g === nothing && continue
                push!(hs, g[1]); votes[g[2]] = get(votes, g[2], 0) + 1
            end
            length(hs) >= 3 && break
        end
        h = isempty(hs) ? NaN : sort(hs)[cld(length(hs), 2)]
        cornerh[(ci, cj)] = h
        isempty(votes) || (cornerp[(ci, cj)] = first(sort(collect(votes), by = x -> -x[2]))[1])
        h
    end
    byp = Dict{Int,Vector{Float32}}(); nq = 0
    for (ci, cj) in holes
        cs = ((ci, cj), (ci + 1, cj), (ci + 1, cj + 1), (ci, cj + 1))
        hs = if (ci, cj) in roadcells          # each corner follows the road under it (a 6 % grade is 6 cm per metre)
            h0 = minimum(first.(column(ix, step*ci, step*cj)))
            [(cc = column(ix, step*(c[1] - 0.5), step*(c[2] - 0.5)); isempty(cc) ? h0 : minimum(first.(cc))) for c in cs]
        else
            [corner(c...) for c in cs]
        end
        any(isnan, hs) && continue
        pv = Dict{Int,Int}(); for c in cs; haskey(cornerp, c) && (pv[cornerp[c]] = get(pv, cornerp[c], 0) + 1); end
        isempty(pv) && continue
        pi = first(sort(collect(pv), by = x -> -x[2]))[1]; src = parts[pi]
        col = (src.verts[7], src.verts[8], src.verts[9])
        # the source part's UV density: its first triangle's UV span per metre
        v = src.verts; L = hypot(v[1+STRIDE]-v[1], v[3+STRIDE]-v[3]); U = hypot(v[10+STRIDE]-v[10], v[11+STRIDE]-v[11])
        tile = (L > 1e-3 && U > 1e-4) ? L/U : 8.0
        out = get!(byp, pi, Float32[])
        pts = [(step*(c[1] - 0.5), h - sink, step*(c[2] - 0.5)) for (c, h) in zip(cs, hs)]
        for (a, b, d) in ((1, 3, 2), (1, 4, 3))      # counter-clockwise seen from above: the face normal points up
            for k in (a, b, d)
                (x, y, z) = pts[k]
                append!(out, Float32[x, y, z, 0, 1, 0, col[1], col[2], col[3], x/tile, z/tile])
            end
        end
        nq += 1
    end
    [Render.TrackPart(v, parts[pi].tex, parts[pi].col) for (pi, v) in byp], nq
end

end # module
