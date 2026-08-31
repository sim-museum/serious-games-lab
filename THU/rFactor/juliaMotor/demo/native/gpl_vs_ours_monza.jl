# Headless: our kinematic AI's free-running speed profile on Monza vs GPL's own race.lp speed, per 3 m.
include("gpldat.jl"); using .GPLDat
include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
include("gpl_lp.jl"); using .GPLLP
using Statistics
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
cl = GPLTrack.trk_centreline(tmp)                      # Monza is NOT re-centred in the sim (E73-S5)
line = RaceAI.build_line(cl, (x,z) -> 0.0)             # elevation irrelevant to the speed model
amax = 8.0                                             # JM_AI_AMAX default in the sim
(fs, fv) = RaceAI.free_speed_profile(line; amax = amax, ds = 3.0)
gpl = lp_speed_mps(read_lp(joinpath(T, "race.lp"))) .* 1.016   # track.ini dlong_speed_adj_coeff
gpl = min.(gpl, 2.41*36)                               # dlong_speed_maximum
n = min(length(fv), length(gpl)); a = fv[1:n]; g = gpl[1:n]
println("Monza: ours ", length(fv), " samples vs GPL ", length(gpl), " records (compared ", n, ")")
println("  lap time  ours ", round(sum(3.0 ./ a), digits=1), " s   GPL ", round(sum(3.0 ./ g), digits=1), " s")
println("  speed     ours min/max ", round(minimum(a), digits=1), "/", round(maximum(a), digits=1), "   GPL ", round(minimum(g), digits=1), "/", round(maximum(g), digits=1))
println("  corr ", round(cor(a, g), digits=3), "   mean|diff| ", round(mean(abs.(a .- g)), digits=2), " m/s   ours slower on ", round(100*count(a .< g .- 2)/n), "% of records, faster on ", round(100*count(a .> g .+ 2)/n), "%")
da = [abs(a[i%n+1]-a[i]) for i in 1:n]; dg = [abs(g[i%n+1]-g[i]) for i in 1:n]
println("  smoothness per 3 m: ours max ", round(maximum(da), digits=2), " p99 ", round(quantile(da,.99), digits=2), " >1 m/s: ", count(>(1.0), da),
        "   GPL max ", round(maximum(dg), digits=2), " p99 ", round(quantile(dg,.99), digits=2), " >1 m/s: ", count(>(1.0), dg))
worst = sortperm(abs.(a .- g), rev=true)[1:8]
println("  largest divergences (s, ours, GPL):"); for i in worst; println("     s=", 3*(i-1), "  ours ", round(a[i], digits=1), "  GPL ", round(g[i], digits=1)); end
