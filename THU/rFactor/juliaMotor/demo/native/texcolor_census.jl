# E83: headless census of decoded texture colours for a GPL track dir -- which textures decode to
# a hue no vegetation has (cyan / turquoise) or to near-white? Those are decode suspects, and the
# PO's "neon" trees are exactly such sprites.   julia --project=. texcolor_census.jl nurburg
include(joinpath(@__DIR__,"render.jl")); using .Render
const GPLBASE = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks"))
const ZD = joinpath(GPLBASE, length(ARGS)>=1 ? ARGS[1] : "nurburg")
idx = Render.gpl_texture_index(ZD)
names = sort(unique(vcat(collect(keys(idx.paths)), [splitext(k)[1] for k in keys(idx.dat)])))
println("track: ", ZD, "  textures: ", length(names))
rows = Tuple{String,Int,Int,Int,Int,Float64}[]
for n in names
    r = Render.tex_rgba(idx, n); r === nothing && continue
    w,h,px = r; sr=0; sg=0; sb=0; na=0; nt=0
    for i in 1:4:length(px)-3
        if px[i+3] >= 0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 else nt+=1 end
    end
    na == 0 && continue
    push!(rows, (n, sr÷na, sg÷na, sb÷na, w*h, nt/(na+nt)))
end
cyan = filter(t -> t[4] > t[2]+40 && t[3] > t[2]+30, rows)          # B >> R and G >> R: turquoise
pale = filter(t -> t[2] > 190 && t[3] > 190 && t[4] > 170 && t[6] > 0.2, rows)   # near-white cutout sprites
println("CYAN/TURQUOISE decodes (", length(cyan), "):"); for t in cyan; println("  ", rpad(t[1],14), " rgb=(", t[2], ",", t[3], ",", t[4], ") ", t[5], "px transparent ", round(100t[6]), "%"); end
println("PALE cutouts (", length(pale), "):"); for t in pale; println("  ", rpad(t[1],14), " rgb=(", t[2], ",", t[3], ",", t[4], ") ", t[5], "px transparent ", round(100t[6]), "%"); end
gr = filter(t -> t[3] > t[2]+20 && t[3] > t[4]+20 && t[6] > 0.2, rows)
println("green cutouts (", length(gr), ") -- sample: ", join([string(t[1],"(",t[2],",",t[3],",",t[4],")") for t in first(gr, 8)], " "))
