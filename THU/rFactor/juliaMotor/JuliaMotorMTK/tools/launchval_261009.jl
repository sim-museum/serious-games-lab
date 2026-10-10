# CARPHYS-1 S9 acceptance: the gold's standing starts, re-driven by the sim car with the gold's own throttle and clutch.
# Each launch: from rest (gold speed < 0.5 m/s) in 1st with the clutch out, for 4 s of the gold's inputs (iRacing's
# Clutch channel, 1 = engaged -> the sim's pedal 1 − Clutch), on flat ground. Compared: the speed at 1, 2 and 3 s and
# the engine speed's lowest point (a launch the sim bogs or stalls shows there). Run with JM_CLUTCH_LINEAR=1 for the
# model before S9.
#   julia --project=. tools/launchval_261009.jl
using Printf, Statistics
include(joinpath(@__DIR__, "arbfit_261005.jl"))                 # install!, ibt_open, ch, D4, D5, DriveRT3D, ModelingToolkit
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
    (f = f, ks = out, v = v, cl = cl, thr = thr, rpm = rpm, brk = brk)
end

function main()
    files = [joinpath(GOLDD, "261004", "lotus49_skidpad 2026-10-04 14-36-48.ibt")]
    append!(files, filter(x -> endswith(x, ".ibt"), readdir(joinpath(GOLDD, "261004"); join = true))[1:min(end, 6)])
    println("clutch model: ", DriveRT3D.CLUTCH_LINEAR ? "linear 500 N·m × engagement (before S9)" : "measured bite point (S9)")
    println("  file                 k      | gold v@1s v@2s v@3s  rpm min | sim v@1s v@2s v@3s  rpm min")
    errs = Float64[]; n = 0
    for fn in unique(files)
        L = launches(fn); isempty(L.ks) && continue
        install!(fn)
        for k in L.ks
            car = DriveRT3D.build_car3d(; v0 = 0.0)
            car.gear = 1; car.s_gr(car.integ, DriveRT3D.gearratio(1)); car.s_we(car.integ, L.rpm[k]*2π/60)
            sv = Float64[]; sr = Float64[]
            for j in 0:239
                kk = k + j
                DriveRT3D.step_car3d!(car, L.thr[kk], L.brk[kk], 0.0, 1/60; clutch = 1.0 - L.cl[kk], manual = true)
                push!(sv, car.v); push!(sr, car.rpm)
            end
            gv = [L.v[k + 60s] for s in 1:3]; simv = [sv[60s] for s in 1:3]
            @printf("  %-20s %6d | %5.1f %5.1f %5.1f  %6.0f | %5.1f %5.1f %5.1f  %6.0f\n", basename(fn)[max(1, end-22):end-4], k,
                    gv..., minimum(L.rpm[k:k+239]), simv..., minimum(sr))
            append!(errs, abs.(simv .- gv)); n += 1
        end
    end
    @printf("%d launches: mean |Δv| at 1/2/3 s %.2f m/s\n", n, mean(errs))
end
main()
