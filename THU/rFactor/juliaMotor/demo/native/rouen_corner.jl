include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Printf
wrapp(a)=atan(sin(a),cos(a))
name="rouen"; T="/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/"*name
dat=first(filter(f->lowercase(basename(f))==lowercase(name)*".dat", joinpath.(T,readdir(T))))
d=GPLDat.parse_dat(dat); key=first(filter(k->endswith(lowercase(k),".trk"), collect(keys(d))))
tmp=tempname()*".trk"; write(tmp,d[key])
line=RaceAI.build_line(GPLTrack.trk_centreline(tmp),(x,z)->0.0); n=length(line.x)
turn=[abs(wrapp(line.θ[i%n+1]-line.θ[i])) for i in 1:n]
# extent of the corner around node 610
function extent(turn, n, start)
    lo = start; while lo > 1 && rad2deg(turn[lo-1]) > 5; lo -= 1; end
    hi = start; while hi < n && rad2deg(turn[hi+1]) > 5; hi += 1; end
    (lo, hi)
end
lo, hi = extent(turn, n, 610)
tot=sum(turn[lo:hi]); arc=line.s[hi]-line.s[lo]
@printf("corner spans nodes %d..%d (%d nodes, %.1f m of arc)\n", lo,hi,hi-lo+1,arc)
@printf("total turn %.1f deg -> implied radius %.1f m\n", rad2deg(tot), arc/tot)
@printf("consistent 12.5 deg per 3.0 m segment = a genuine hairpin, not a data defect\n")
# how many nodes anywhere exceed 5 deg?
@printf("nodes >5 deg on the whole circuit: %d of %d (%.2f%%)\n", count(t->rad2deg(t)>5,turn), n, 100count(t->rad2deg(t)>5,turn)/n)
