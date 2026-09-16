include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Printf
G = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks"
for (name, gold) in (("watglen", 66.912), ("monza", 90.202))
    T = joinpath(G, name)
    dat = first(filter(f -> lowercase(basename(f)) == name*".dat", joinpath.(T, readdir(T))))
    d = GPLDat.parse_dat(dat)
    key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
    tmp = tempname()*".trk"; write(tmp, d[key])
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
    for (label, amax) in (("shipped 11.0", 11.0), ("ibt p95 11.8", 11.8), ("ibt p99 13.67", 13.67))
        t = RaceAI.natural_laptime(line; amax=amax, vmax=74.0)
        @printf("  %-8s %-14s lap=%7.2f s  gold=%.3f  delta=%+6.2f\n", name, label, t, gold, t-gold)
    end
end
