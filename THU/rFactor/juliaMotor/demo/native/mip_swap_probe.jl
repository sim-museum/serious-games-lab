include(joinpath(@__DIR__,"gplmip.jl")); using .GPLMip
include(joinpath(@__DIR__,"gpldat.jl")); using .GPLDat
const ZD = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks","nurburg"))
const OUT = ARGS[1]
blobs = Dict{String,Vector{UInt8}}()
for f in readdir(ZD; join=true)
    lf = lowercase(f); endswith(lf, ".mip") && (blobs[lowercase(basename(f))] = read(f))
    endswith(lf, ".dat") && (try; for (k,v) in GPLDat.parse_dat(f); endswith(k, ".mip") && (blobs[k] = v); end; catch; end)
end
rows = []
for (k,b) in blobs
    length(b) < 40 && continue; mt = Int(b[25]); mt in (0,1,2) || continue
    r = try GPLMip.decode_mip_bytes(b) catch; nothing end; r === nothing && continue
    w,h,px = r; sr=sg=sb=na=0
    for i in 1:4:length(px)-3; if px[i+3]>=0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 end; end
    na==0 && continue; push!(rows, (k, mt, w, h, sr÷na, sg÷na, sb÷na, abs(sr-sb)÷na, px))
end
sort!(rows, by = t -> -t[8])
println("palettised textures with the strongest R/B asymmetry (current decode = R,G,B order):")
for t in first(rows, 14); println("  ", rpad(t[1],16), " type ", t[2], " ", t[3], "x", t[4], "  rgb=(", t[5], ",", t[6], ",", t[7], ")   if BGRA -> (", t[7], ",", t[6], ",", t[5], ")"); end
# dump the top 4 as PNG (current decode) so the eye can judge which order is right
try
    using FileIO, ImageCore
    for t in first(rows, 4)
        w,h,px = t[3], t[4], t[9]
        img = [RGBA{N0f8}(px[4*((y-1)*w+(x-1))+1]/255, px[4*((y-1)*w+(x-1))+2]/255, px[4*((y-1)*w+(x-1))+3]/255, px[4*((y-1)*w+(x-1))+4]/255) for y in 1:h, x in 1:w]
        save(joinpath(OUT, "cur_" * replace(t[1], ".mip"=>"") * ".png"), img)
    end
    println("PNGs written")
catch e; println("PNG export unavailable: ", sprint(showerror, e)); end
