# obj_locate.jl — FAST (no-physics) trackside-object locator.  Lists GPL object
# placements near the racing line: name, lateral offset from the .trk centreline,
# and distance along the lap — to identify which object protrudes into the road.
#   TRACK=watglen JM_NEAR=25 julia --project=. obj_locate.jl
using JuliaMotor
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack

const TRACKSEL = lowercase(get(ENV,"TRACK","watglen"))
const GPLBASE  = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks"
const GPLNAME  = get(Dict("nurburgring"=>"nurburg","zandvoort"=>"zandvort","watglen"=>"watglen","monza"=>"monza","spa"=>"spa67"), TRACKSEL, "zandvort")
const ZD = joinpath(GPLBASE, GPLNAME)
find_ci(dir,name)=(m=filter(f->lowercase(f)==lowercase(name),readdir(dir)); isempty(m) ? joinpath(dir,name) : joinpath(dir,m[1]))
const DAT=(p=find_ci(ZD,GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMP=mktempdir()
function tf(base,ext); p=find_ci(ZD,base*ext); isfile(p)&&return p; v=get(DAT,lowercase(base*ext),nothing); v===nothing&&return p; q=joinpath(TMP,base*ext); write(q,v); q; end
const ZTRK=tf(GPLNAME,".3do")
objnames=Set{String}()
for f in readdir(ZD); endswith(lowercase(f),".3do") && push!(objnames, lowercase(replace(f,r"\.3do$"i=>""))); end
for k in keys(DAT); endswith(k,".3do") && push!(objnames, replace(k,r"\.3do$"=>"")); end
insts = GPLTrack.trackside_objects(ZTRK; objnames=objnames)
CL = GPLTrack.trk_centreline(tf(GPLNAME,".trk"))
# arc length
seg=[hypot(CL[i%length(CL)+1][1]-CL[i][1], CL[i%length(CL)+1][2]-CL[i][2]) for i in 1:length(CL)]
arc=cumsum(seg)
function project(x,y)   # nearest centreline vertex → (lateral signed, lapdist)
    bd=Inf; bj=1
    for (j,p) in enumerate(CL); d=(p[1]-x)^2+(p[2]-y)^2; d<bd && (bd=d; bj=j); end
    p=CL[bj]; q=CL[bj%length(CL)+1]
    tx=q[1]-p[1]; ty=q[2]-p[2]; tl=hypot(tx,ty); tl<1e-6 && (tl=1.0)
    tx/=tl; ty/=tl; nx=-ty; ny=tx      # left normal
    lat=(x-p[1])*nx + (y-p[2])*ny
    (lat, arc[bj])
end
const NEAR = parse(Float64, get(ENV,"JM_NEAR","25"))
const SMIN = parse(Float64, get(ENV,"JM_SMIN","-1"))
const SMAX = parse(Float64, get(ENV,"JM_SMAX","1e9"))
rows=[]
for i in insts
    lat,s = project(i.x, i.y)
    abs(lat) <= NEAR || continue
    (s>=SMIN && s<=SMAX) || continue
    push!(rows,(round(lat,digits=1), round(Int,s), i.name, round(Int,i.x), round(Int,i.y)))
end
sort!(rows, by=r->(r[2], abs(r[1])))
println("track=$TRACKSEL  objects with |lateral| ≤ $NEAR m of the racing line", SMIN>0 ? "  (s∈[$SMIN,$SMAX])" : "")
println(rpad("lat[m]",8), rpad("s[m]",7), rpad("name",16), "x     y")
for (lat,s,nm,x,y) in rows; println(rpad(lat,8), rpad(s,7), rpad(nm,16), rpad(x,6), y); end
println("(", length(rows), " near-road placements; lateral <0 = right of travel, >0 = left)")
