# TRACKBAND-1 probe (2026-10-21): which PRIM leaf nodes each segment-tree band reaches (near slots 1-4, mid 5-6, far 7).
# julia gpl_bandreach.jl monza
const NAT = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(NAT, "gpldat.jl")); using .GPLDat
name = ARGS[1]
base = normpath(joinpath(NAT, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks", name))
dat = first(filter(f -> lowercase(f) == name * ".dat", readdir(base)))
D = GPLDat.parse_dat(joinpath(base, dat))
b = D[first(filter(k -> endswith(k, ".3do") && startswith(k, name), collect(keys(D))))]
u32(o) = (o < 0 || o+4 > length(b)) ? UInt32(0) : UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
i32(o) = reinterpret(Int32, u32(o))
prim = 0; primsz = 0; o = 12
while o + 12 <= length(b)
    t = String(b[o+1:o+4]); sz = Int(u32(o+8)); d = o + 12
    t == "MIRP" && (global prim = d; global primsz = sz)
    global o = d + sz; global o += (4 - o % 4) % 4
end
isseg(g) = u32(prim+g) == 0x04 && u32(prim+g+4) == 8 && u32(prim + Int(i32(prim+g+36))) == 0x10
function children(off)
    p = prim + off; t = u32(p); out = Int[]
    if t == 0x04
        n = Int(u32(p+4)); 0 < n < 5000 && for k in 1:n; push!(out, Int(i32(p+4+4k))); end
    elseif t == 0x05; push!(out, Int(i32(p+4)))
    elseif 0x06 <= t <= 0x0B
        for k in 1:(t == 0x06 ? 1 : t in (0x07, 0x0B) ? 2 : t == 0x08 ? 4 : 3); push!(out, Int(i32(p+8+4(k-1)))); end
    elseif t in (0x0D, 0x13, 0x16); push!(out, Int(i32(p+32)))
    elseif t == 0x19; push!(out, Int(i32(p+36)))
    elseif t == 0x11
        n = Int(u32(p+16)); 0 < n < 4096 && for k in 1:n; push!(out, Int(i32(p+24+8(k-1)))); end
    elseif t == 0x0F
        nd = Int(i32(p+40)); nd >= 0 && push!(out, nd)
        n = Int(u32(p+60)); 0 < n < 4096 && for k in 1:n; push!(out, Int(i32(p+64+16(k-1)+12))); end
    end
    filter(c -> 0 <= c < primsz, out)
end
STRUCT = Set{UInt32}([0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0D,0x0F,0x10,0x11,0x13,0x16,0x19])
function leaves(roots)
    seen = Set{Int}(); st = copy(roots); L = Set{Int}()
    while !isempty(st)
        off = pop!(st); off in seen && continue; push!(seen, off)
        t = u32(prim+off)
        t == 0x0E && continue                 # external object: placed separately
        t == 0x01 && continue
        if t in STRUCT; append!(st, children(off)); else; push!(L, off); end
    end
    L
end
root = Int(u32(prim))
segroot = -1
for k in 1:Int(u32(prim+root+4))
    c = Int(i32(prim+root+4+4k)); (c >= 0 && u32(prim+c) == 0x04) || continue
    n = Int(u32(prim+c+4)); n > 16 || continue
    count(j -> (g = Int(i32(prim+c+4+4j)); g >= 0 && isseg(g)), 1:min(n, 64)) >= 32 && (global segroot = c; break)
end
segs = [Int(i32(prim+segroot+4+4k)) for k in 1:Int(u32(prim+segroot+4))]
slot(g, s) = Int(i32(prim+g+4+4s))
near = leaves([slot(g, s) for g in segs if isseg(g) for s in 1:4 if slot(g, s) >= 0])
mid  = leaves([slot(g, s) for g in segs if isseg(g) for s in 5:6 if slot(g, s) >= 0])
far  = leaves([slot(g, s) for g in segs if isseg(g) for s in 7:7 if slot(g, s) >= 0])
allL = leaves([root])
nonseg = setdiff(allL, union(near, mid, far))
ty(S) = (d = Dict{String,Int}(); for x in S; k = "0x" * string(u32(prim+x), base = 16); d[k] = get(d, k, 0) + 1; end; d)
println(name, ": ", length(segs), " segment trees; leaves all ", length(allL), " | near ", length(near), " mid ", length(mid), " far ", length(far))
println("  near∩mid ", length(intersect(near, mid)), "  near∩far ", length(intersect(near, far)), "  mid∩far ", length(intersect(mid, far)))
println("  ONLY near ", length(setdiff(near, mid, far)), "  ONLY mid ", length(setdiff(mid, near, far)), "  ONLY far ", length(setdiff(far, near, mid)), "  in no segment tree ", length(nonseg))
println("  only-far leaf types ", ty(setdiff(far, near, mid)))
