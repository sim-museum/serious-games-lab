# E84: how far is OUR synthesised racing line (rl, left +) from GPL's race.lp dlat, and how do GPL's
# passing rails relate? Same .trk frame on Monza (not re-centred), 3.0 m records.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack; include("ai.jl"); using .RaceAI; include("gpl_lp.jl"); using .GPLLP
using Statistics
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
race = read_lp(joinpath(T, "race.lp")); p1 = read_lp(joinpath(T, "pass1.lp")); p2 = read_lp(joinpath(T, "pass2.lp"))
n = min(length(line.rl), length(race.dlat))
ours = line.rl[1:n]; gpl = Float64.(race.dlat[1:n])
println("Monza racing line lateral offset (m, left +): ours vs GPL race.lp, ", n, " records")
println("  ours  range ", round(minimum(ours),digits=2), "..", round(maximum(ours),digits=2), "   GPL range ", round(minimum(gpl),digits=2), "..", round(maximum(gpl),digits=2))
println("  mean|Δ| ", round(mean(abs.(ours .- gpl)), digits=2), " m   p90 ", round(quantile(abs.(ours .- gpl), .9), digits=2), "   corr ", round(cor(ours, gpl), digits=3))
# is there a constant lateral offset between the frames? (GPL dlat may be measured from a shifted reference)
println("  median(GPL - ours) ", round(median(gpl .- ours), digits=2), " m  (a constant here = a frame offset, not a line difference)")
big = sortperm(abs.(ours .- gpl), rev=true)[1:6]
println("  largest differences (s, ours, GPL):"); for i in big; println("     s=", 3*(i-1), "  ours ", round(ours[i],digits=2), "  GPL ", round(gpl[i],digits=2)); end
# GPL rails relative to GPL race line: room to the left / right at each record
rl_ = Float64.(p1.dlat[1:n] .- race.dlat[1:n]); rr_ = Float64.(p2.dlat[1:n] .- race.dlat[1:n])
println("  GPL rails vs race: left(pass1) median ", round(median(rl_),digits=2), "  right(pass2) median ", round(median(rr_),digits=2), "   our RAIL = +/-2.4")
