# WWSETUP-1: the anti-roll bars' effect, identified THROUGH THE PLAYER CAR from the A/B of the two setups.
#
# The garage gives the bars as a diameter and an arm position, which are settings, not rates -- so their effect is
# identified, like the tyre (TYRE-1), against the gold's own steady-state cornering (tools/wwab_261005.jl):
#   * per-axle slip angle per 0.1 g band (the BALANCE), the TYRE-1 extractor on both sides;
#   * the ROLL GRADIENT, from the suspension travel (gold: shock deflections / motion ratio; sim: wheel vs body).
# Each setup is its own ibt car (springs, gearbox, mass, LSD, toe, dampers from that session); the free parameters
# are the extra roll-only stiffness per axle (DrivenVehicle3D karb_f / karb_r, live MTK parameters).
#
#   julia --project=. tools/arbfit_261005.jl            (default car at 0/0, then a grid for WW103)
#   JM_ARB_EVAL="kf,kr" JM_ARB_SIDE=ww                  (score one point)
using Printf, Statistics
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "wwab_261005.jl"))                # gold steady(), setupof, D4/D5, LWB
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const setp = ModelingToolkit.setp

const BANDS2 = 0.5:0.1:1.0
const FILES = Dict(:default => joinpath(D4, "lotus49_skidpad 2026-10-04 14-36-48.ibt"),
                   :ww      => joinpath(D5, "lotus49_skidpad 2026-10-06 00-21-30.ibt"))

function gold_targets()
    S = Dict(:default => NamedTuple[], :ww => NamedTuple[])
    for d in (D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        append!(S[setupof(ibt_open(fn))], steady(fn))
    end
    T = Dict{Symbol,Any}()
    for k in keys(S)
        P = S[k]
        bands = Dict(g => (rad2deg(median(p.αf for p in P if g <= p.g < g + 0.1)),
                           rad2deg(median(p.αr for p in P if g <= p.g < g + 0.1)),
                           count(p -> g <= p.g < g + 0.1, P)) for g in BANDS2)
        Q = [p for p in P if p.g > 0.3]; X = hcat([p.ay/G for p in Q], ones(length(Q)))
        roll = 0.5*abs((X \ [rad2deg(p.φf) for p in Q])[1] + (X \ [rad2deg(p.φr) for p in Q])[1])
        T[k] = (bands = bands, roll = roll)
    end
    T
end

function install!(fn)
    sp = setup_params(ibt_open(fn).yaml)
    DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(fn))
    m, ff = DriveRT3D.mass_from_corner_weights(sp.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(fn))
    s = sp.spring_rate_Npmm
    DriveRT3D.set_suspension!(wheel_rate(s[:LF]), wheel_rate(s[:RF]), wheel_rate(s[:LR]; rear = true), wheel_rate(s[:RR]; rear = true); source = basename(fn))
    DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(sp; source = basename(fn)))
    sp
end

"""Constant-speed steering ramp both ways: per-band median axle slip (deg) and the roll gradient (deg/g)."""
function sim_curve(car, sp, u0; V0 = 33.0, δmax = 0.22, tr = 30.0)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay, sys.δ, sys.z, sys.th, sys.ph,
                                       sys.wFL.zu, sys.wFR.zu, sys.wRL.zu, sys.wRR.zu])
    a = ModelingToolkit.getp(sys, sys.a)(car.integ); b = ModelingToolkit.getp(sys, sys.b)(car.integ)
    pts = NTuple{5,Float64}[]
    for dir in (1.0, -1.0)
        reinit!(car.integ, copy(u0))
        g = findfirst(i -> V0/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 8000, 1:5)
        car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
        ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V0, 0.0])
        ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V0/0.30, V0/DriveRT3D.RW_R, V0/DriveRT3D.RW_R])
        car.s_we(car.integ, V0/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
        ie = 0.0; seg = NTuple{5,Float64}[]
        for k in 1:round(Int, (tr + 1)*60)
            t = k/60; δ = dir*δmax*clamp((t - 1)/tr, 0, 1)
            u = car.v
            thr = clamp(0.25 + 0.4*(V0 - u) + ie, 0, 1); ie = clamp(ie + 0.02*(V0 - u), -0.5, 0.8)
            DriveRT3D.step_car3d!(car, thr, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            u, v, r, ay, δr, z, th, ph, zfl, zfr, zrl, zrr = get(car.integ)
            (isfinite(u) && u > 5) || break
            abs(atan(v, u)) > deg2rad(15) && break
            t > 2 && abs(u - V0) < 1.5 || continue
            s = sign(ay); s == 0 && continue
            αf = δr - atan(v + a*r, u); αr = -atan(v - b*r, u)
            # suspension compression per corner (wheel up relative to its body mount), as vehicle_3d's `comp`
            cmp(zu, xi, yi) = zu - (z + xi*th + yi*ph)
            φf = (cmp(zfl, a, 0.75) - cmp(zfr, a, -0.75))/1.5
            φr = (cmp(zrl, -b, 0.75) - cmp(zrr, -b, -0.75))/1.5
            push!(seg, (s*ay/G, rad2deg(s*αf), rad2deg(s*αr), ay/G, rad2deg(0.5*(φf + φr))))
        end
        isempty(seg) || append!(pts, seg[1:argmax(first.(seg))])      # the stable branch, as tyreid
    end
    bands = Dict(g => (median(p[2] for p in pts if g <= p[1] < g + 0.1), median(p[3] for p in pts if g <= p[1] < g + 0.1),
                       count(p -> g <= p[1] < g + 0.1, pts)) for g in BANDS2 if count(p -> g <= p[1] < g + 0.1, pts) >= 10)
    Q = [p for p in pts if p[1] > 0.3]
    roll = isempty(Q) ? NaN : abs((hcat(getindex.(Q, 4), ones(length(Q))) \ getindex.(Q, 5))[1])
    (bands = bands, roll = roll, gmax = isempty(pts) ? 0.0 : maximum(first.(pts)))
end

function score(T, S; verbose = false, tag = "")
    e = 0.0
    for g in BANDS2
        tg = T.bands[g]; haskey(S.bands, g) || (e += 25.0; continue)
        sf, sr, _ = S.bands[g]
        e += (sf - tg[1])^2 + (sr - tg[2])^2
        verbose && @printf("   %s %.1f g | gold front %5.2f rear %5.2f (n %5d) | sim front %5.2f rear %5.2f\n", tag, g, tg[1], tg[2], tg[3], sf, sr)
    end
    e += 10*(S.roll - T.roll)^2
    verbose && @printf("   %s roll gradient gold %.3f  sim %.3f deg/g    sim max %.2f g    score %.2f\n", tag, T.roll, S.roll, S.gmax, e)
    e
end

function main()
    T = gold_targets()
    side = Symbol(get(ENV, "JM_ARB_SIDE", "both"))
    for k in (side === :both ? (:default, :ww) : (side,))
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u)
        println("\n== $k   ", DriveRT3D.describe_chassis())
        setkf = setp(car.sys, car.sys.karb_f); setkr = setp(car.sys, car.sys.karb_r)
        pts = haskey(ENV, "JM_ARB_EVAL") ? [Tuple(parse.(Float64, split(ENV["JM_ARB_EVAL"], ',')))] :
              k === :default ? [(0.0, 0.0), (0.0, 5000.0), (5000.0, 0.0), (5000.0, 5000.0)] :
              [(kf, kr) for kf in (0.0, 5000.0, 10000.0, 15000.0) for kr in (0.0, 5000.0, 10000.0)]
        best = (Inf, (NaN, NaN))
        for (kf, kr) in pts
            setkf(car.integ, kf); setkr(car.integ, kr); u0 = copy(car.integ.u)
            S = sim_curve(car, sp, u0)
            println(" karb_f $kf  karb_r $kr")
            e = score(T[k], S; verbose = true, tag = string(k))
            e < best[1] && (best = (e, (kf, kr)))
        end
        @printf("best for %s: karb_f %.0f karb_r %.0f  score %.2f\n", k, best[2]..., best[1])
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
