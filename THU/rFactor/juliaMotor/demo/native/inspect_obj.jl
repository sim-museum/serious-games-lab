# inspect_obj.jl — dump the parts/groups + object-space bounding boxes of a GPL
# object .3do, so we can identify a specific sub-structure (e.g. one gantry leg) to
# exclude.   OBJ=startbox julia --project=. inspect_obj.jl
using JuliaMotor
include("render.jl"); using .Render
const GPLBASE = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks"
const TRACKSEL = lowercase(get(ENV,"TRACK","watglen"))
const GPLNAME  = get(Dict("nurburgring"=>"nurburg","zandvoort"=>"zandvort","watglen"=>"watglen","monza"=>"monza","spa"=>"spa67"), TRACKSEL, "zandvort")
const ZD = joinpath(GPLBASE, GPLNAME)
find_ci(dir,name)=(m=filter(f->lowercase(f)==lowercase(name),readdir(dir)); isempty(m) ? joinpath(dir,name) : joinpath(dir,m[1]))
const DAT=(p=find_ci(ZD,GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMP=mktempdir()
const OBJ = get(ENV,"OBJ","startbox")
p = find_ci(ZD, OBJ*".3do")
if !isfile(p); v=get(DAT, lowercase(OBJ*".3do"), nothing); v!==nothing && (p=joinpath(TMP,OBJ*".3do"); write(p,v)); end
println("object: ", OBJ, "  file: ", p, "  exists=", isfile(p))
parts = Render.extract_gpl_car(p; track=true, mirror=true)
println("parts: ", length(parts))
# each TrackPart: verts is flat [x,y,z, nx,ny,nz, r,g,b, u,v] × N (11 floats/vert)
for (k,pp) in enumerate(parts)
    n = length(pp.verts) ÷ 11
    xs = [pp.verts[(i-1)*11+1] for i in 1:n]; ys=[pp.verts[(i-1)*11+2] for i in 1:n]; zs=[pp.verts[(i-1)*11+3] for i in 1:n]
    println("  part ", lpad(k,2), "  tex=", rpad(pp.tex,10), " nverts=", lpad(n,4),
        "  x[", round(minimum(xs),digits=1), ",", round(maximum(xs),digits=1), "]",
        "  y[", round(minimum(ys),digits=1), ",", round(maximum(ys),digits=1), "]",
        "  z[", round(minimum(zs),digits=1), ",", round(maximum(zs),digits=1), "]")
end
