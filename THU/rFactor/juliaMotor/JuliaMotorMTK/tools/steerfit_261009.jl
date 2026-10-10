# CARPHYS-1 S5: the steering column's torque, fitted to iRacing's SteeringWheelTorque (the force feedback a real
# Lotus 49 sends to the rim; 60 Hz on disk, 360 Hz in its _ST array, in every gold .ibt).
#
# Measured first, on the gold alone (all 261004/261005 files): the torque per newton of front-axle force falls by
# 25–30 % from 0.6–0.9 g to 1.1–1.4 g -- the pneumatic trail collapsing as the front tyres saturate. So the model
# to fit is the steering system's physics, not a fixed trail: the rim torque is the front tyres' own aligning torque
# Mz (BrushTyre: pneumatic trail t0, collapsing with the slip) plus their lateral force on the mechanical trail
# (caster), plus a centring term on the wheel angle (kingpin jacking), all through the rack ratio:
#     τ_rim = p·ΣMz_front + q·ΣFy_front + c·δ_wheel
# Model A (fixed trail: τ = a·ΣFy + c·δ) is fitted beside it for comparison.
#
# Method: every gold skidpad event (gold_events: power-on and lift-off, both setups, spinning or not), replayed through
# its session car from the settled circle with the gold's own throttle, brake and steering changes (as replay_261005 /
# slidefit_261009), for JM_STEER_SECS (2) s -- before a spin can carry the sim away from the gold. Per 60 Hz frame:
# the sim's front ΣMz, ΣFy and wheel angle, and the gold's torque at the same moment. Least squares, fitted on one
# setup's events and tested on the other's, then on all.
#
#   julia --project=. tools/steerfit_261009.jl
using Printf, Statistics, LinearAlgebra
include(joinpath(@__DIR__, "replay_261005.jl"))               # goldtrace, settle!, gold_events, install!, FILES, D4, D5, ibt_open, ch

function samples(car, sp, u0, gt, fn, k0, n)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.FL.Mz, sys.FR.Mz, sys.FL.Fy, sys.FR.Fy, sys.u, sys.v])
    f = ibt_open(fn); T = ch(f, "SteeringWheelTorque"); A = ch(f, "SteeringWheelAngle")
    δ0 = settle!(car, sp, u0, gt)
    out = NamedTuple[]
    for k in 1:min(n, length(gt.thr))
        δk = δ0 + (gt.δ[k] - gt.δ[1])
        DriveRT3D.step_car3d!(car, gt.thr[k], gt.brk[k], δk/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        mzl, mzr, fyl, fyr, u, v = get(car.integ)
        hypot(u, v) < 10 && break
        kk = k0 + k - 1                                       # the disk .ibt rows are 60 Hz, as the sim's steps
        kk > length(T) && break
        push!(out, (mz = mzl + mzr, fy = fyl + fyr, δw = δk*sp.steering_ratio, τ = T[kk], δgold = A[kk], side = 0))
    end
    out
end

function fit(S, cols)
    X = hcat((getfield.(S, c) for c in cols)...); y = getfield.(S, :τ)
    β = X \ y
    β, X, y
end
r2(β, X, y) = 1 - sum(abs2, y - X*β)/sum(abs2, y .- mean(y))
rmse(β, X, y) = sqrt(mean(abs2, y - X*β))

function main()
    E = gold_events()
    secs = parse(Float64, get(ENV, "JM_STEER_SECS", "2")); n = round(Int, secs*60)
    println("gold events: ", length(E))
    cars = Dict{Symbol,Any}()
    for k in (:default, :ww)
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0); cars[k] = (car, sp, copy(car.integ.u))
    end
    S = Dict(:default => NamedTuple[], :ww => NamedTuple[])
    for e in E
        d = joinpath(e.side === :default ? D4 : D5, e.file)
        isfile(d) || (d = joinpath(D5, e.file)); isfile(d) || (d = joinpath(D4, e.file))
        gt = goldtrace(d, round(Int, e.t*60), n)
        car, sp, u0 = cars[e.side]
        append!(S[e.side], samples(car, sp, u0, gt, d, round(Int, e.t*60), n))
    end
    for (name, cols) in (("A fixed trail      τ = a·ΣFy + c·δw", (:fy, :δw)),
                         ("B steering physics τ = p·ΣMz + q·ΣFy + c·δw", (:mz, :fy, :δw)))
        println(name)
        for (tr, te) in ((:default, :ww), (:ww, :default))
            β, _, _ = fit(S[tr], cols); _, Xt, yt = fit(S[te], cols)
            @printf("   fit on %-7s test on %-7s  R² %.3f  RMSE %.2f N·m   coeffs %s\n", tr, te, r2(β, Xt, yt), rmse(β, Xt, yt),
                    join((@sprintf("%.5f", b) for b in β), ", "))
        end
        all = vcat(S[:default], S[:ww]); β, X, y = fit(all, cols)
        @printf("   all (%d frames)                 R² %.3f  RMSE %.2f N·m   coeffs %s\n", length(y), r2(β, X, y), rmse(β, X, y),
                join((@sprintf("%.5f", b) for b in β), ", "))
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
