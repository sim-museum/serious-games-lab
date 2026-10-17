# SETUPMODEL-1 S4 (Part D3): how hard iRacing's Lotus 49 diff locks at drive ramp 35° vs 75°, from the PO's 261017 runs.
# In a corner the rear wheels must differ by yaw rate x rear track (the kinematic split); an open diff lets them, a locked
# one holds them together. Locking = 1 - (measured outer-inner rear speed) / (kinematic split), on samples under power
# (throttle > 0.6, in gear 2-4) in steady-ish corners (|yaw rate| > 0.15 rad/s, speed 15-60 m/s).
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/difframp_261017.jl
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
const DIR = get(ENV, "JM_DIFFDIR", expanduser("~/gold standard/julia racer/261017/telemetry"))
const TRACK_R = 1.53                                  # rear track [m] (garage fit: ~1.51-1.53)
for fn in sort(readdir(DIR; join = true))
    endswith(fn, ".ibt") || continue
    f = ibt_open(fn); sp = setup_params(f.yaml)
    yr = channel(f, "YawRate"); v = channel(f, "Speed"); thr = channel(f, "Throttle"); gear = channel(f, "Gear")
    lr = channel(f, "LRspeed"); rr = channel(f, "RRspeed"); on = channel(f, "IsOnTrack")
    lock = Float64[]; lockc = Float64[]
    for i in eachindex(v)
        on[i] > 0.5 && 15 < v[i] < 60 && abs(yr[i]) > 0.15 && 2 <= gear[i] <= 4 || continue
        kin = yr[i]*TRACK_R                            # left-hand turn (yaw > 0): right rear is outside, faster
        meas = rr[i] - lr[i]
        thr[i] > 0.6 && push!(lock, 1 - meas/kin)
        thr[i] < 0.05 && push!(lockc, 1 - meas/kin)
    end
    q(x) = isempty(x) ? "   -   " : @sprintf("%5.2f (n %4d, IQR %.2f-%.2f)", median(x), length(x), quantile(x, 0.25), quantile(x, 0.75))
    @printf("%-28s ramps %2.0f/%2.0f plates %d preload %3.0f | power: locking %s | coast: %s\n",
            basename(fn)[24:end], sp.diff_drive_ramp, sp.diff_coast_ramp, sp.diff_plates, sp.diff_preload_Nm, q(lock), q(lockc))
end
