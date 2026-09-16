include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Printf
G = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks"
for (name, gold) in (("monza", 90.202), ("watglen", 66.912))
    T = joinpath(G, name)
    dat = first(filter(f -> lowercase(basename(f)) == name*".dat", joinpath.(T, readdir(T))))
    d = GPLDat.parse_dat(dat)
    key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
    tmp = tempname()*".trk"; write(tmp, d[key]); line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z)->0.0)
    for (lbl, vm) in (("shipped 74", 74.0), ("ibt-rev 84.4", 84.4), ("ibt-rev 87.8", 87.8))
        t = RaceAI.natural_laptime(line; vmax=vm, amax=13.04)
        @printf("  %-8s %-13s lap=%7.2f  gold=%.3f  delta=%+6.2f\n", name, lbl, t, gold, t-gold)
    end
end
