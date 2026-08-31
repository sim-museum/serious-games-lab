include(joinpath(@__DIR__,"gplmip.jl")); using .GPLMip
include(joinpath(@__DIR__,"gpldat.jl")); using .GPLDat
const ZD = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks", length(ARGS)>=1 ? ARGS[1] : "nurburg"))
blobs = Dict{String,Vector{UInt8}}()
for f in readdir(ZD; join=true)
    lf = lowercase(f)
    endswith(lf, ".mip") && (blobs[lowercase(basename(f))] = read(f))
    endswith(lf, ".dat") && (try; for (k,v) in GPLDat.parse_dat(f); endswith(k, ".mip") && (blobs[k] = v); end; catch; end)
end
u32(b,o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
bytype = Dict{Int,Vector{Tuple{String,Int,Int,Int,Float64}}}()
for (k,b) in blobs
    length(b) < 40 && continue
    mt = Int(b[25])
    r = try GPLMip.decode_mip_bytes(b) catch; nothing end; r === nothing && continue
    w,h,px = r; sr=sg=sb=na=nt=0
    for i in 1:4:length(px)-3; if px[i+3]>=0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 else nt+=1 end; end
    na==0 && continue
    push!(get!(bytype, mt, []), (k, sr÷na, sg÷na, sb÷na, nt/(na+nt)))
end
println("textures: ", length(blobs))
for mt in sort(collect(keys(bytype)))
    v = bytype[mt]; greenish = filter(t -> t[3] > t[2] && t[3] > t[4], v)
    bgtr = count(t -> t[4] > t[2], greenish)
    println("type $mt: n=", length(v), "  green-dominant: ", length(greenish), "  of which B>R (teal): ", bgtr,
            "  cutouts(>20% transparent): ", count(t -> t[5] > 0.2, v))
    for t in first(sort(greenish, by = t -> -(t[4]-t[2])), 5); println("     ", rpad(t[1],16), " rgb=(", t[2], ",", t[3], ",", t[4], ")  transp ", round(100t[5]), "%"); end
end
