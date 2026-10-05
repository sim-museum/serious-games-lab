# tools/gpl_segvis.jl (E81/GREY-1, 2026-10-05): GPL draws a track object only when the CAMERA is in a segment whose tree
# reaches it (nurburg.3do: root group -> group of 894 segment trees; each tree = group(8), slots 1..7 = BSP / cell
# copies, slot 8 = a 0x10 table of four lap positions in TRK units). Usage: WANT=<object> julia tools/gpl_segvis.jl
# Ancestry of named external objects in a GPL track .3do: which cells / LOD lists / segment slots reach them.
const F = expanduser("~/sgl/THU/WP/drive_c/Sierra/GPL/tracks/nurburg/nurburg.3do")
b = read(F)
u32(o) = (o < 0 || o+4 > length(b)) ? UInt32(0) : UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
i32(o) = reinterpret(Int32, u32(o)); f32(o) = reinterpret(Float32, u32(o))
tag(o) = String(b[o+1:o+4])
strn = prim = primsz = 0; strsz = 0; o = 12
while o + 12 <= length(b)
    t = tag(o); sz = Int(u32(o+8)); d = o + 12
    t == "NRTS" && (global strn = d; global strsz = sz); t == "MIRP" && (global prim = d; global primsz = sz)
    global o = d + sz; global o += (4 - o % 4) % 4
end
stroff = Dict{Int,String}(); let q = 0, cur = UInt8[]
    for i in strn:strn+strsz-1
        c = b[i+1]; c == 0xFF && break
        if c == 0x00; stroff[q] = String(copy(cur)); q += length(cur) + 1; empty!(cur) else push!(cur, c) end
    end
end
parents = Dict{Int,Vector{Tuple{Int,UInt32,Int}}}()   # child => [(parent, ptype, slot)]
ninfo = Dict{Int,String}()
seen = Set{Int}()
stack = [Int(u32(prim))]
edge(par, t, k, ch) = (ch >= 0 && ch < primsz) && (push!(get!(parents, ch, Tuple{Int,UInt32,Int}[]), (par, t, k)); push!(stack, ch))
unk = Dict{UInt32,Int}()
while !isempty(stack)
    off = pop!(stack); off in seen && continue; push!(seen, off)
    p = prim + off; t = u32(p)
    if t == 0x04
        n = Int(u32(p+4)); 0 < n < 5000 && for k in 1:n; edge(off, t, k, Int(i32(p+4+4k))); end
        ninfo[off] = "group($n)"
    elseif t == 0x05; edge(off, t, 1, Int(i32(p+4)))
    elseif t in 0x06:0x0B
        nc = t == 0x06 ? 1 : t in (0x07, 0x0B) ? 2 : t == 0x08 ? 4 : 3
        for k in 1:nc; edge(off, t, k, Int(i32(p+8+4(k-1)))); end
    elseif t in (0x0D, 0x13, 0x16); edge(off, t, 1, Int(i32(p+32)))
    elseif t == 0x19; edge(off, t, 1, Int(i32(p+36)))
    elseif t == 0x11
        n = Int(u32(p+16)); ds = Float32[]
        0 < n < 4096 && for k in 1:n; push!(ds, f32(p+20+8(k-1))); edge(off, t, k, Int(i32(p+24+8(k-1)))); end
        ninfo[off] = "LOD" * string(ds)
    elseif t == 0x0E
        ninfo[off] = "ext:" * get(stroff, Int(u32(p+4)), "?")
        u32(p+12) == 19 && edge(off, t, 1, Int(i32(p+12+32)))
    elseif t == 0x0F
        nd = Int(i32(p+36)); n = Int(u32(p+60))
        ninfo[off] = "cell(n=$n, nextdetail=$nd)"
        nd >= 0 && edge(off, t, 0, nd)
        0 < n < 4096 && for k in 1:n; edge(off, t, k, Int(i32(p+64+16(k-1)+12))); end
    elseif t == 0x10
        n = Int(u32(p+4)); ninfo[off] = "table(n=$n): " * string([f32(p+8+4k) for k in 0:min(n,6)-1]) * " / " * string([i32(p+8+4k) for k in 0:min(n,6)-1])
    else
        unk[t] = get(unk, t, 0) + 1
    end
end
println("nodes reached ", length(seen), "; unknown types (count): ", sort(collect(unk), by = x -> -x[2])[1:min(8, end)])
want = lowercase(get(ENV, "WANT", "wehr-r1b"))
targets = [k for (k, v) in ninfo if startswith(v, "ext:") && lowercase(v[5:end]) == want]
println("ext nodes named $want: ", targets)
# segment trees: children of the big group; their slot-8 table gives the segment's lap positions (TRK units)
const SEGROOT = parse(Int, get(ENV, "SEGROOT", "7364576"))
segs = Int[Int(i32(prim + SEGROOT + 4 + 4k)) for k in 1:Int(u32(prim + SEGROOT + 4))]
segs_s = Dict{Int,Float64}(); for (k, sg) in enumerate(segs)
    t8 = Int(i32(prim + sg + 4 + 32)); u32(prim + t8) == 0x10 && (segs_s[k] = i32(prim + t8 + 8) / 19685.03937)
end
segidx = Dict(sg => k for (k, sg) in enumerate(segs))
# which segments reach node n (memoised upward search)
memo = Dict{Int,Set{Int}}()
function reach(n, stackset = Set{Int}())
    haskey(memo, n) && return memo[n]
    n in stackset && return Set{Int}()
    push!(stackset, n)
    r = Set{Int}(); haskey(segidx, n) && push!(r, segidx[n])
    for (par, t, k) in get(parents, n, Tuple{Int,UInt32,Int}[]); union!(r, reach(par, stackset)); end
    delete!(stackset, n); memo[n] = r
end
for tg in targets
    r = sort(collect(reach(tg)))
    ss = sort([segs_s[k] for k in r if haskey(segs_s, k)])
    println("== ", ninfo[tg], " @", tg, ": reached from ", length(r), " of ", length(segs), " segment trees; camera s range: ",
            isempty(ss) ? "-" : string(round(ss[1]), " .. ", round(ss[end])), "   segments ", r[1:min(end,12)])
end
