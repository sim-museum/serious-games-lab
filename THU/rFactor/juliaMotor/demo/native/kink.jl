include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Printf
wrapp(a) = atan(sin(a), cos(a))
name="watglen"; T="/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/"*name
dat=first(filter(f->lowercase(basename(f))==lowercase(name)*".dat", joinpath.(T,readdir(T))))
d=GPLDat.parse_dat(dat); key=first(filter(k->endswith(lowercase(k),".trk"), collect(keys(d))))
tmp=tempname()*".trk"; write(tmp,d[key])
for sd in (5,60)
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp; subdiv=sd), (x,z)->0.0)
    n=length(line.x)
    turn=[abs(wrapp(line.θ[i%n+1]-line.θ[i])) for i in 1:n]
    ord=sortperm(turn; rev=true)
    @printf("subdiv=%d n=%d  worst nodes (index/n, deg):\n", sd, n)
    for k in 1:6
        i=ord[k]; @printf("    node %5d / %5d  (%.1f%% round)  turn=%6.2f deg  s=%.1f m\n",
                          i, n, 100i/n, rad2deg(turn[i]), line.s[i])
    end
end
