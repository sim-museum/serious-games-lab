include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack; include("ai.jl"); using .RaceAI; include("gpl_lp.jl"); using .GPLLP
using Statistics
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
gpl = min.(lp_speed_mps(read_lp(joinpath(T, "race.lp"))) .* 1.016, 2.41*36)
function report(tag; amax, vmax)
    (fs, fv) = RaceAI.free_speed_profile(line; amax, vmax, ds = 3.0); n = min(length(fv), length(gpl))
    da = [abs(fv[i%n+1]-fv[i]) for i in 1:n]
    println("  ", rpad(tag, 34), "lap ", round(sum(3.0 ./ fv), digits=1), " s  mean|diff| ", round(mean(abs.(fv[1:n] .- gpl[1:n])), digits=2), "  min v ", round(minimum(fv), digits=1), "  |dv|>1/3m: ", count(>(1.0), da), "  corr ", round(cor(fv[1:n], gpl[1:n]), digits=3))
end
println("GPL lap ", round(sum(3.0 ./ gpl), digits=1), " s   (free-running single car, Monza)")
report("κ model, amax=8 (shipped)"; amax=8.0, vmax=74.0)
report("κ model, amax=14 vmax=86.8"; amax=14.0, vmax=86.8)
RaceAI.set_gpl_speeds!(gpl)
report("GPL race.lp speeds (JM_AI_GPLLINE)"; amax=14.0, vmax=86.8)
RaceAI.set_gpl_speeds!(nothing)
