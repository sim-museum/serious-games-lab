# IRPLAN-3 E4: braking from ~250 km/h, straight and trail-braked, from the gold alone.  Each braking event (Brake > 0.15
# starting above 200 km/h) -> entry speed, peak/median pedal, pedal still applied while steering, peak |β| during the
# event (and while braking with steer), peak |yaw rate|, whether it spun (|β| > 30°).
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/trailbrake_261018.jl <file.ibt> ...
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics
for fn in ARGS
    f = IBT.ibt_open(fn); ch(n) = Float64.(IBT.channel(f, n)); y = IBT.session_yaml(f)
    setup = match(r"DriverSetupName: ([^\n]*)", y).captures[1]; sr = parse(Float64, match(r"SteeringRatio: (\d+)", y).captures[1])
    v = ch("Speed") .* 3.6; br = ch("Brake"); st = ch("SteeringWheelAngle") ./ sr .* (180 / pi)
    β = rad2deg.(atan.(ch("VelocityY"), max.(ch("VelocityX"), 1.0))); r = rad2deg.(ch("YawRate")); ax = ch("LongAccel") ./ 9.80665
    println("== ", basename(fn)[9:end], "  (", setup, ")")
    @printf("  %6s %6s %5s %5s %6s %7s %7s %7s %6s\n", "t", "v0", "pk", "med", "trail", "β_max", "β_trl", "r_max", "ax_pk")
    k = 2; n = length(v)
    while k <= n
        if br[k] > 0.15 && br[k-1] <= 0.15 && v[k] > 200
            j = k; while j < n && br[j+1] > 0.05; j += 1; end
            s = k:min(n, j + 60)                               # the event + 1 s after release
            tr = [i for i in k:j if abs(st[i]) > 0.4 && br[i] > 0.1]
            @printf("  %6.1f %6.0f %5.2f %5.2f %5.1fs %7.1f %7.1f %7.1f %6.2f%s\n", (k-1)/60, v[k], maximum(br[k:j]), median(br[k:j]),
                    length(tr)/60, maximum(abs.(β[s])), isempty(tr) ? 0.0 : maximum(abs.(β[tr])), maximum(abs.(r[s])),
                    -minimum(ax[k:j]), maximum(abs.(β[s])) > 30 ? "  SPIN" : "")
            k = j + 1
        else
            k += 1
        end
    end
end
