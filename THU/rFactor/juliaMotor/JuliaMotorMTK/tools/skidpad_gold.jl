# SKIDPAD-GOLD-1 S1 (2026-09-15): the steady-state cornering envelope of the REAL Lotus 49.
#
# ~/gold standard/julia racer/260626telemetry/ holds four .ibt captures, and ibt_provenance.jl
# reports all four as "iRacing-written, 0 JULIA-RACER-written" -- a pure reference. One of them is a
# SKIDPAD run (425 MB), which is the classic steady-state tyre oracle: constant-radius cornering
# gives lateral acceleration against speed directly, with no track, line or driver skill in the way.
#
# This prints the reference envelope. Our own sim already has a SKIDPAD mode
# (drive_native_mtk.jl: `inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer)`), so the same statistic can be
# taken from both sides and compared.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/skidpad_gold.jl [file.ibt]
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics

const DEFAULT = "/home/admin/gold standard/julia racer/260626telemetry/lotus49_skidpad 2026-06-26 12-16-59.ibt"
path = length(ARGS) >= 1 ? ARGS[1] : DEFAULT
f = ibt_open(path)
sp  = channel(f, "Speed")            # m/s
lat = channel(f, "LatAccel")         # m/s^2
lon = channel(f, "LongAccel")
sw  = channel(f, "SteeringWheelAngle")
yr  = channel(f, "YawRate")
n = min(length(sp), length(lat), length(sw), length(yr))
println("samples: ", n)

# steady state = actually cornering, not braking or changing line:
#   speed above 5 m/s, steering held (|dSW| small), longitudinal accel small
keep = Int[]
for i in 2:n
    (sp[i] > 5.0) || continue
    (abs(sw[i] - sw[i-1]) < 0.02) || continue
    (abs(lon[i]) < 2.0) || continue
    push!(keep, i)
end
@printf("steady-state samples: %d of %d (%.1f%%)\n", length(keep), n, 100*length(keep)/n)
isempty(keep) && exit(1)
g(x) = x / 9.80665
la = [abs(lat[i]) for i in keep]
sk = [sp[i] for i in keep]
@printf("  speed        %.1f .. %.1f m/s  (median %.1f)\n", minimum(sk), maximum(sk), median(sk))
@printf("  |LatAccel|   median %.2f m/s^2 (%.2f g)   p95 %.2f (%.2f g)   max %.2f (%.2f g)\n",
        median(la), g(median(la)), quantile(la, 0.95), g(quantile(la, 0.95)), maximum(la), g(maximum(la)))
@printf("  |steering|   median %.3f rad  max %.3f rad\n",
        median([abs(sw[i]) for i in keep]), maximum([abs(sw[i]) for i in keep]))
println()
println("lateral g by speed band (steady state):")
@printf("  %-14s %7s %9s %9s\n", "speed m/s", "n", "med g", "p95 g")
for lo in 5:5:45
    b = [la[k] for (k,i) in enumerate(keep) if lo <= sk[k] < lo+5]
    isempty(b) && continue
    @printf("  %5.0f .. %-5.0f %7d %9.2f %9.2f\n", lo, lo+5, length(b), g(median(b)), g(quantile(b, 0.95)))
end
