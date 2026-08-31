# E84: the lateral frame shift between GPL's .lp dlat (raw .trk centreline) and our aligned line, Monza.
using JuliaMotor
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack; include("gpldat.jl"); using .GPLDat; include("ai.jl"); using .RaceAI; include("gpl_lp.jl"); using .GPLLP
using Statistics
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
ztrk = haskey(d, "monza.3do") ? (p = tempname()*".3do"; write(p, d["monza.3do"]); p) : joinpath(T, "monza.3do")
println("mesh: ", ztrk); mesh = Render.GPL3DO.parse_3do(ztrk); println("  ", length(mesh.tris), " tris")
road_pred = lt -> occursin("asp", lt) || startswith(lt,"groove") || startswith(lt,"kerb")
hat = GPLTrack.build_hat(mesh; drop_overpass=true, road_pred=road_pred)
cl0 = GPLTrack.trk_centreline(tmp)
# replicate align_centreline (a pure 2-D translation maximising road coverage)
function align_shift(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return (0.0, 0.0, cov(0.0,0.0))
    xs = Float64[]; zs = Float64[]; for tr in hat.tris, p in (tr.a, tr.b, tr.c); push!(xs, p[1]); push!(zs, p[3]); end
    dx0 = (minimum(xs)+maximum(xs))/2 - (minimum(p[1] for p in cl)+maximum(p[1] for p in cl))/2
    dz0 = (minimum(zs)+maximum(zs))/2 - (minimum(p[2] for p in cl)+maximum(p[2] for p in cl))/2
    best = (cov(dx0, dz0), dx0, dz0)
    for dx in dx0-400:40:dx0+400, dz in dz0-400:40:dz0+400; c = cov(dx, dz); c > best[1] && (best = (c, dx, dz)); end
    for dx in best[2]-40:8:best[2]+40, dz in best[3]-40:8:best[3]+40; c = cov(dx, dz); c > best[1] && (best = (c, dx, dz)); end
    (best[2], best[3], best[1])
end
(dx, dz, cv) = align_shift(cl0, hat)
println("align shift: dx=", round(dx,digits=2), " dz=", round(dz,digits=2), "  coverage ", round(cv,digits=3))
line = RaceAI.build_line([(p[1]+dx, p[2]+dz) for p in cl0], (x,z) -> 0.0)
race = read_lp(joinpath(T, "race.lp")); n = min(length(line.rl), length(race.dlat))
# GPL dlat is measured from the RAW centreline; ours from the SHIFTED one. In our frame a GPL point
# is at raw_centre + dlat*n; its offset from our centre = dlat - (shift . n) with n our left-normal.
nx = [-sin(line.θ[i]) for i in 1:n]; nz = [cos(line.θ[i]) for i in 1:n]
gpl_ours = [Float64(race.dlat[i]) - (dx*nx[i] + dz*nz[i]) for i in 1:n]
ours = line.rl[1:n]; raw = Float64.(race.dlat[1:n])
println("ours vs GPL dlat RAW:        mean|Δ| ", round(mean(abs.(ours .- raw)),digits=2), "  corr ", round(cor(ours, raw),digits=3))
println("ours vs GPL dlat in OUR frame: mean|Δ| ", round(mean(abs.(ours .- gpl_ours)),digits=2), "  corr ", round(cor(ours, gpl_ours),digits=3), "  GPL range ", round(minimum(gpl_ours),digits=2), "..", round(maximum(gpl_ours),digits=2))
println("(GPL's line beyond our |rl| band ±3.8 on ", round(100*count(abs.(gpl_ours) .> 3.8)/n), "% of records -- room GPL uses that our band forbids)")
