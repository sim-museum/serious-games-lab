include(joinpath(@__DIR__,"gplmip.jl")); using .GPLMip
include(joinpath(@__DIR__,"gpldat.jl")); using .GPLDat
const ZD = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks","nurburg"))
const OUT = ARGS[1]
blobs = Dict{String,Vector{UInt8}}()
for f in readdir(ZD; join=true)
    lf = lowercase(f); endswith(lf, ".mip") && (blobs[lowercase(basename(f))] = read(f))
    endswith(lf, ".dat") && (try; for (k,v) in GPLDat.parse_dat(f); endswith(k, ".mip") && (blobs[k] = v); end; catch; end)
end
bytype = Dict{Int,Vector{Any}}()
for (k,b) in blobs
    length(b) < 40 && continue; mt = Int(b[25])
    r = try GPLMip.decode_mip_bytes(b) catch; nothing end; r === nothing && continue
    w,h,px = r; sr=sg=sb=na=0
    for i in 1:4:length(px)-3; if px[i+3]>=0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 end; end
    na==0 && continue; push!(get!(bytype, mt, []), (k, w, h, sr÷na, sg÷na, sb÷na, abs(sr-sb)÷na, px))
end
for mt in sort(collect(keys(bytype)))
    v = sort(bytype[mt], by = t -> -t[7]); println("type $mt (n=$(length(v))), most R/B-asymmetric:")
    for t in first(v, 5); println("    ", rpad(t[1],14), " rgb=(", t[4], ",", t[5], ",", t[6], ")"); end
end
dump(nm, t) = open(joinpath(OUT, nm * ".rgba"), "w") do io; write(io, Int32(t[2]), Int32(t[3]), t[8]); end
for mt in keys(bytype), t in bytype[mt]
    t[1] in ("bo_sign2.mip", "drygrass.mip", "hgbush.mip", "x-sign.mip") && dump("t$(mt)_" * replace(t[1], ".mip"=>""), t)
end
for t in first(sort(bytype[4], by = t -> -t[7]), 2); dump("t4_" * replace(t[1], ".mip"=>""), t); end
haskey(bytype, 5) && for t in first(sort(bytype[5], by = t -> -t[7]), 1); dump("t5_" * replace(t[1], ".mip"=>""), t); end
println("dumped")
