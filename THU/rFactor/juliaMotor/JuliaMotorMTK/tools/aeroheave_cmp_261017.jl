# PHYSFID-1 S12: julia's car vs iRacing on the 261017 straights -- axle ride height against v² (aero lift + the drag/thrust
# pitch transfer together, which is what a regression on a straight sees). Gold: a + b·v² + c·ax on straight samples,
# read at ax = 0. Sim: the same session car held at constant speed on a flat straight, 30-75 m/s.
using Printf, Statistics
include(joinpath(@__DIR__, "replay_261005.jl"))
include(joinpath(@__DIR__, "irgold_params.jl"))
const DIR17 = expanduser("~/gold standard/julia racer/261017/telemetry")
function goldfit(fn)
    f = ibt_open(fn); v = ch(f, "Speed"); ax = ch(f, "LongAccel"); ay = ch(f, "LatAccel"); on = ch(f, "IsOnTrack")
    rf = (ch(f, "LFrideHeight") .+ ch(f, "RFrideHeight")) ./ 2; rr = (ch(f, "LRrideHeight") .+ ch(f, "RRrideHeight")) ./ 2
    idx = [i for i in eachindex(v) if on[i] > 0.5 && v[i] > 20 && abs(ay[i]) < 0.08G]
    X = hcat(ones(length(idx)), v[idx].^2, ax[idx])
    (X \ rf[idx], X \ rr[idx])
end
function simfit(fn)
    sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0)
    if !isempty(get(ENV, "JM_IRG_PARAMS", ""))         # A/B: irgold_params.jl names, e.g. "claf=0,clafrh=-4.4"
        Base.invokelatest(setparams!, car, Dict(String(strip(split(x, "=")[1])) => parse(Float64, split(x, "=")[2]) for x in split(ENV["JM_IRG_PARAMS"], ",")))
    end
    sys = car.sys; getu = ModelingToolkit.getsym(sys, sys.u)
    V2 = Float64[]; F = Float64[]; R = Float64[]
    for V in 30.0:5.0:75.0
        g = V < 35 ? 3 : V < 50 ? 4 : 5
        car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
        ie = 0.0; fs = Float64[]; rs = Float64[]
        for k in 1:8*60
            u = getu(car.integ)
            thr = clamp(0.4 + 0.5*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.5, 0.8)
            DriveRT3D.step_car3d!(car, thr, 0.0, 0.0, 1/60; clutch = 0.0, manual = true)
            if k > 6*60
                t = DriveRT3D.telemetry3d(car); push!(fs, (t.rh[1] + t.rh[2])/2); push!(rs, (t.rh[3] + t.rh[4])/2)
            end
        end
        push!(V2, getu(car.integ)^2); push!(F, mean(fs)); push!(R, mean(rs))
    end
    X = hcat(ones(length(V2)), V2)
    (X \ F, X \ R)
end
for run in split(get(ENV, "AH_RUNS", "11-58-11,12-13-04,12-18-53"), ",")
    fn = joinpath(DIR17, first(filter(x -> occursin(run, x), readdir(DIR17))))
    gf, gr = goldfit(fn); sf, sr = simfit(fn)
    sp = setup_params(ibt_open(fn).yaml)
    @printf("%s springs %2.0f/%2.0f | ride height change at 70 m/s, front: iRacing %+5.1f mm  julia %+5.1f mm | rear: iRacing %+5.1f  julia %+5.1f mm\n",
            run, sp.spring_rate_Npmm[:LF], sp.spring_rate_Npmm[:LR], 1000gf[2]*4900, 1000sf[2]*4900, 1000gr[2]*4900, 1000sr[2]*4900)
end
