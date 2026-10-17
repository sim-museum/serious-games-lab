# SETUPMODEL-1 S4 (Part D3): does julia's LSD lock like iRacing's at drive ramp 35° and let go at 75°?
# The gold's corner exits on power (261017: 12-29-07 at 35°, 12-33-46 + 11-58-11 at 75°) replayed through that session's
# own sim car (replay_261005.jl: settled on the gold's circle in the gold's gear, then the gold's throttle and steering
# changes). Scored on locking = 1 - (outer - inner rear speed)/(yaw rate x 1.53 m), samples on power (thr > 0.6,
# |r| > 0.15 rad/s): 1 = spool, 0 = open diff, > 1 = the inner wheel spinning up.
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/difframp_replay_261017.jl
using Printf, Statistics
include(joinpath(@__DIR__, "replay_261005.jl"))
const DIR17 = expanduser("~/gold standard/julia racer/261017/telemetry")
const RUNS = ["12-29-07", "12-33-46", "11-58-11"]

"""Corner exits: a circle (|ay| > 0.3 g, circle kinematics within 25 %), gear 2-4, throttle < 0.5 now and > 0.7 within
2 s; one per 3 s."""
function exits(fn)
    f = ibt_open(fn)
    ay = ch(f, "LatAccel"); r = ch(f, "YawRate"); v = ch(f, "Speed"); g = ch(f, "Gear"); thr = ch(f, "Throttle"); on = ch(f, "IsOnTrack")
    ks = Int[]; last = -10^6
    for k in 61:length(v) - 300
        on[k] > 0.5 && 2 <= g[k] <= 4 && abs(ay[k]) > 0.3G && thr[k] < 0.5 || continue
        abs(abs(r[k])*v[k] - abs(ay[k])) < 0.25abs(ay[k]) || continue
        maximum(thr[k:k+120]) > 0.7 || continue
        k - last > 180 || continue
        push!(ks, k); last = k
    end
    ks
end
lockv(rr, lr, yaw) = 1 - (rr - lr)/(yaw*1.53)
for run in RUNS
    fn = joinpath(DIR17, first(filter(x -> occursin(run, x), readdir(DIR17))))
    sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u)
    f = ibt_open(fn); LR = ch(f, "LRspeed"); RR = ch(f, "RRspeed"); YR = ch(f, "YawRate"); TH = ch(f, "Throttle")
    getw = ModelingToolkit.getsym(car.sys, [car.sys.r, car.sys.ωRL, car.sys.ωRR])
    gl = Float64[]; sl = Float64[]
    ev = exits(fn)
    for k0 in ev
        gt = goldtrace(fn, k0, 150)
        δ0 = settle!(car, sp, u0, gt)
        for k in 1:min(150, length(gt.thr) - 1)
            DriveRT3D.step_car3d!(car, gt.thr[k], 0.0, (δ0 + gt.δ[k] - gt.δ[1])/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            r, wl, wr = getw(car.integ)
            j = k0 + k - 1
            if TH[j] > 0.6 && abs(YR[j]) > 0.15
                push!(gl, lockv(RR[j], LR[j], YR[j]))
                abs(r) > 0.15 && push!(sl, lockv(wr*DriveRT3D.RW_R, wl*DriveRT3D.RW_R, r))
            end
        end
    end
    q(x) = isempty(x) ? "-" : @sprintf("%.2f (IQR %.2f-%.2f, n %d)", median(x), quantile(x, 0.25), quantile(x, 0.75), length(x))
    @printf("%s  drive ramp %2.0f°  %d exits | iRacing locking %s | julia %s\n", run, sp.diff_drive_ramp, length(ev), q(gl), q(sl))
end
