# UNDERSTEER-1 / IRPLAN-3 D1: the PO's held power slides on the skidpad, from the gold alone.  Finds every >= 3 s stretch
# held on the throttle with the rear stepped out (sideslip |β| > 3°, steady ay within ±0.08 g, throttle > 0.3) and prints
# its medians: speed, ay, yaw rate, β, road steer, throttle, gear/rpm, the driven rears' slip ratio (outside/inside).
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/powerslide_261018.jl <file.ibt> ...
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics
sm(x, n) = (h = n ÷ 2; [mean(@view x[max(1, k-h):min(length(x), k+h)]) for k in eachindex(x)])
const RR = 0.3337            # rear rolling radius used by julia's .ibt export (DriveRT3D.RW_R)
for fn in ARGS
    f = IBT.ibt_open(fn); ch(n) = Float64.(IBT.channel(f, n))
    y = IBT.session_yaml(f); m = match(r"SteeringRatio: (\d+)", y); sr = parse(Float64, m.captures[1])
    setup = match(r"DriverSetupName: ([^\n]*)", y).captures[1]
    vx = ch("VelocityX"); vy = ch("VelocityY"); r = ch("YawRate"); ay = sm(ch("LatAccel"), 31) ./ 9.80665
    th = ch("Throttle"); st = ch("SteeringWheelAngle"); gr = ch("Gear"); rpm = ch("RPM")
    lr = ch("LRspeed"); rrs = ch("RRspeed"); v = ch("Speed")
    β = rad2deg.(atan.(vy, max.(vx, 1.0)))
    ok = (v .> 12) .& (abs.(sm(β, 31)) .> 3) .& (sm(th, 31) .> 0.3) .& (sign.(β) .== -sign.(ay))
    println("== ", basename(fn), "  (", setup, ")")
    @printf("  %6s %5s %6s %6s %6s %6s %5s %3s %5s %7s %7s\n", "t0", "dur", "km/h", "ay g", "β°", "δ°", "thr", "gr", "rpm", "sl_out", "sl_in")
    k = 1; n = length(v)
    while k <= n
        if ok[k]
            j = k; while j < n && ok[j+1]; j += 1; end
            if j - k >= 180
                s = k:j; a = mean(ay[s])
                if std(ay[s]) < 0.08
                    out, inn = a > 0 ? (rrs, lr) : (lr, rrs)       # +ay = turning left: outside = right
                    slo = median(out[s] ./ vx[s] .- 1); sli = median(inn[s] ./ vx[s] .- 1)
                    @printf("  %6.1f %5.1f %6.1f %6.2f %6.1f %6.2f %5.2f %3d %5.0f %7.3f %7.3f\n", (k-1)/60, (j-k)/60,
                            median(v[s])*3.6, a, median(β[s]), median(st[s])/sr*180/pi, median(th[s]), round(Int, median(gr[s])),
                            median(rpm[s]), slo, sli)
                end
            end
            k = j + 1
        else
            k += 1
        end
    end
end
