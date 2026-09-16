# AI-GOLD: what speed anchor does a GPL-competitive Watkins Glen lap imply?
# Sweep vmax/amax against the gold 66.912 s. This asks a different question from the six skitter
# sprints: not "is the line good" but "is the pace model's ceiling anywhere near a real car".
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Printf
G = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks"
name = get(ENV, "TRK", "watglen"); T = joinpath(G, name)
GOLD = Dict("watglen"=>66.912, "monza"=>90.202)[name]
dat = first(filter(f -> lowercase(basename(f)) == name*".dat", joinpath.(T, readdir(T))))
d = GPLDat.parse_dat(dat)
key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
tmp = tempname()*".trk"; write(tmp, d[key])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
@printf("track=%s  lap length=%.0f m  gold=%.3f s  =>  gold mean speed=%.1f m/s (%.0f km/h)\n",
        name, line.total, GOLD, line.total/GOLD, 3.6*line.total/GOLD)
println("  vmax  amax |   lap s   delta vs gold")
function sweep(line, GOLD)
  best = (1e9, 0.0, 0.0)
  for vmax in (74.0, 85.0, 95.0, 105.0, 120.0), amax in (11.0, 14.0, 18.0, 24.0)
    t = RaceAI.natural_laptime(line; vmax=vmax, amax=amax)
    d_ = t - GOLD
    abs(d_) < abs(best[1]-GOLD) && (best = (t, vmax, amax))
    @printf("  %5.0f %5.0f | %7.2f  %+7.2f\n", vmax, amax, t, d_)
  end
  best
end
best = sweep(line, GOLD)
@printf("closest: lap=%.2f s at vmax=%.0f m/s (%.0f km/h) amax=%.0f m/s2 (%.2f g)\n",
        best[1], best[2], best[2]*3.6, best[3], best[3]/9.81)
