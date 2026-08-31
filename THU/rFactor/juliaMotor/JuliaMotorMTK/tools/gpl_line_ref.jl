# GPL reference metrics for a track's AI line — the yardstick E89 measures our AI against.
#   julia --project=demo/native JuliaMotorMTK/tools/gpl_line_ref.jl [monza]
include(joinpath(@__DIR__, "..", "..", "demo", "native", "gpl_lp.jl")); using .GPLLP
track = length(ARGS) >= 1 ? ARGS[1] : "monza"
dir = "/home/admin/sgl/THU/WP/drive_c/Sierra/GPL/tracks/$track"
isdir(dir) || (println("no GPL track dir: $dir"); exit(2))
race  = read_lp(joinpath(dir, "race.lp")); p1 = read_lp(joinpath(dir, "pass1.lp")); p2 = read_lp(joinpath(dir, "pass2.lp"))
v = lp_speed_mps(race); n = length(v); ds = 3.0
dv = [abs(v[i % n + 1] - v[i]) for i in 1:n]
rail1 = Float64.(p1.dlat .- race.dlat); rail2 = Float64.(p2.dlat .- race.dlat)
using Statistics
println("GPL AI line reference — $track  ($n records, ~$(round(Int, n*ds)) m)")
println("  speed m/s: min ", round(minimum(v), digits=1), "  max ", round(maximum(v), digits=1), "  implied AI lap ", round(sum(ds ./ v), digits=1), " s")
println("  speed smoothness per 3 m: max |dv| ", round(maximum(dv), digits=2), " m/s;  p99 ", round(quantile(dv, 0.99), digits=2),
        ";  records with |dv|>1 m/s: ", count(>(1.0), dv), " of ", n)
println("  passing rails vs race line (m): pass1 median ", round(median(rail1), digits=2), " (min ", round(minimum(rail1), digits=2), ")",
        "   pass2 median ", round(median(rail2), digits=2), " (max ", round(maximum(rail2), digits=2), ")")
println("  race dlat range (m): ", round(minimum(race.dlat), digits=1), " .. ", round(maximum(race.dlat), digits=1))
