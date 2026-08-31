include("gplmip.jl"); using .GPLMip; include("gpldat.jl"); using .GPLDat
ZD = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/nurburg"
blobs = Dict{String,Vector{UInt8}}()
for f in readdir(ZD; join=true); lf = lowercase(f); endswith(lf, ".mip") && (blobs[lowercase(basename(f))] = read(f)); endswith(lf, ".dat") && (try; for (k,v) in GPLDat.parse_dat(f); endswith(k, ".mip") && (blobs[k] = v); end; catch; end); end
for (k,b) in sort(collect(blobs))
    occursin(r"tree|baum|fich|tann|conif|pine|wald|busch|bush|strauch|hedge|heck", k) || continue
    r = try GPLMip.decode_mip_bytes(b) catch; continue end; w,h,px = r; sr=sg=sb=na=nt=0
    for i in 1:4:length(px)-3; if px[i+3]>=0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 else nt+=1 end; end
    na == 0 && continue
    println("  ", rpad(k,14), " type ", Int(b[25]), " ", w, "x", h, "  opaque mean (", sr÷na, ",", sg÷na, ",", sb÷na, ")  transparent ", round(100nt/(na+nt)), "%")
end
