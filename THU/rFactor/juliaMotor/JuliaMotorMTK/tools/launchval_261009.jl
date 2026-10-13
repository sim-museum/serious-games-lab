# CARPHYS-1 S9 acceptance: the gold's standing starts, re-driven by the sim car with the gold's own throttle and clutch.
# Each launch: from rest (gold speed < 0.5 m/s) in 1st with the clutch out, for 4 s of the gold's inputs (iRacing's
# Clutch channel, 1 = engaged -> the sim's pedal 1 − Clutch), on flat ground. Compared: the speed at 1, 2 and 3 s and
# the engine speed's lowest point (a launch the sim bogs or stalls shows there). Run with JM_CLUTCH_LINEAR=1 for the
# model before S9.
#   julia --project=. tools/launchval_261009.jl
using Printf, Statistics
include(joinpath(@__DIR__, "arbfit_261005.jl"))                 # install!, ibt_open, ch, D4, D5, DriveRT3D, ModelingToolkit
# IRGOLD-1 S15: the Clutch channel already holds iRacing's anti-stall; only the raw-pedal mode wants the sim's own
DriveRT3D.ANTISTALL[] = get(ENV, "JM_LAUNCH_RAW", "0") == "1"
const GOLDD = expanduser("~/gold standard/julia racer")

function launches(fn; maxn = 12)
    f = ibt_open(fn)
    v = ch(f, "Speed"); cl = ch(f, "Clutch"); g = ch(f, "Gear"); thr = ch(f, "Throttle"); rpm = ch(f, "RPM"); brk = ch(f, "Brake")
    out = Int[]; k = 2
    while k < f.nrows - 300 && length(out) < maxn
        # the clutch starts to come in from fully out, at rest, in 1st, off the brakes
        if v[k] < 0.5 && g[k] == 1 && cl[k-1] < 0.02 && cl[k] >= 0.02 && maximum(v[k:k+240]) > 3
            push!(out, k); k += 600
        else
            k += 1
        end
    end
    # IRGOLD-1 S15: JM_LAUNCH_RAW=1 drives the sim with the driver's PEDAL (ClutchRaw) instead of iRacing's resulting
    # engagement (Clutch) -- the test of an anti-stall clutch, which is what turns the one into the other
    raw = ch(f, "ClutchRaw")
    pedal = get(ENV, "JM_LAUNCH_RAW", "0") == "1" && raw !== nothing ? raw : cl
    (f = f, ks = out, v = v, cl = cl, pedal = pedal, thr = thr, rpm = rpm, brk = brk, lrs = ch(f, "LRspeed"), rrs = ch(f, "RRspeed"),
     ax = ch(f, "LongAccel"))
end

const AS = Ref{Any}(nothing)
const QUIET = Ref(false)
function main()
    files = [joinpath(GOLDD, "261004", "lotus49_skidpad 2026-10-04 14-36-48.ibt")]
    append!(files, filter(x -> endswith(x, ".ibt"), readdir(joinpath(GOLDD, "261004"); join = true))[1:min(end, 6)])
    # IRGOLD-1 S14: JM_LAUNCH_DIR=<dir> takes every .ibt there instead (261012: IRTEST test 2, fixed-pedal starts at Monza)
    haskey(ENV, "JM_LAUNCH_DIR") && (files = filter(x -> endswith(x, ".ibt"), readdir(ENV["JM_LAUNCH_DIR"]; join = true)))
    println("engine: ", DriveRT3D.ENGINE_LUMPED ? "lumped (Ie 0.18 at the crank, before S14)" : "split (S14: engine 0.052 + gearbox 0.128)")
    println("clutch model: ", DriveRT3D.CLUTCH_LINEAR ? "linear 500 N·m × engagement (before S9)" : "measured bite point (S9)")
    println("  file                 k      | gold v@1s v@2s v@3s  rpm min | sim v@1s v@2s v@3s  rpm min")
    errs = Float64[]; n = 0
    for fn in unique(files)
        L = launches(fn); isempty(L.ks) && continue
        install!(fn)
        for k in L.ks
            car = DriveRT3D.build_car3d(; v0 = 0.0)
            # IRGOLD-1: JM_LAUNCH_IE=<kg m²> tries another engine inertia (the gold's engine falls 8,900 -> 2,000 rpm in 0.4 s)
            haskey(ENV, "JM_LAUNCH_IE") && ModelingToolkit.setp(car.sys, car.sys.Ie)(car.integ, parse(Float64, ENV["JM_LAUNCH_IE"]))
            # IRGOLD-1 S15: AS[] = (as_r0, as_k, as_w) overrides the anti-stall law (tools/antistall_fit_261012.jl)
            AS[] === nothing || for (nm, x) in zip((:as_r0, :as_k, :as_w), AS[])
                ModelingToolkit.setp(car.sys, getproperty(car.sys, nm))(car.integ, x)
            end
            car.gear = 1; car.s_gr(car.integ, DriveRT3D.gearratio(1)); car.s_we(car.integ, L.rpm[k]*2π/60)
            sv = Float64[]; sr = Float64[]
            for j in 0:239
                kk = k + j
                DriveRT3D.step_car3d!(car, L.thr[kk], L.brk[kk], 0.0, 1/60; clutch = 1.0 - L.pedal[kk], manual = true)
                push!(sv, car.v); push!(sr, car.rpm)
                # IRGOLD-1 S14: JM_LAUNCH_TRACE=<k> prints that launch every 0.1 s, gold vs sim (speed, rear wheel speed, rpm)
                if get(ENV, "JM_LAUNCH_TRACE", "") == string(k) && j % 6 == 0
                    te = DriveRT3D.telemetry3d(car)
                    @printf("    %4.1fs thr %.2f clu %.2f | gold v %5.2f rear %5.2f rpm %5.0f ax %5.2f | sim v %5.2f rear %5.2f rpm %5.0f ax %5.2f\n",
                            j/60, L.thr[kk], L.cl[kk], L.v[kk], 0.5*(L.lrs[kk] + L.rrs[kk]), L.rpm[kk], L.ax[kk]/9.81,
                            car.v, te.ωr*DriveRT3D.RW_R, car.rpm, te.ax/9.81)
                end
            end
            gv = [L.v[k + 60s] for s in 1:3]; simv = [sv[60s] for s in 1:3]
            QUIET[] || @printf("  %-20s %6d | %5.1f %5.1f %5.1f  %6.0f | %5.1f %5.1f %5.1f  %6.0f\n", basename(fn)[max(1, end-22):end-4], k,
                    gv..., minimum(L.rpm[k:k+239]), simv..., minimum(sr))
            append!(errs, abs.(simv .- gv)); n += 1
        end
    end
    @printf("%d launches: mean |Δv| at 1/2/3 s %.2f m/s\n", n, mean(errs))
    mean(errs)
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
