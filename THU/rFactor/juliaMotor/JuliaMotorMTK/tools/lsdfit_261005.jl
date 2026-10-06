# WWSETUP-1: identify the rear LSD's friction constant LSD_K THROUGH THE PLAYER CAR, from both setups at once.
#
# Gold measure (no model in it): the rear wheel-speed split as a fraction of an open diff's,
#     ρ = (RRspeed − LRspeed) / (YawRate · track)
# 1 = open (each wheel follows its own path), 0 = locked (both turn together), < 0 = the inside wheel spinning up.
# The front axle, free-rolling, reads 0.95–1.07 by the same formula, so the measure is sound. The gold shows the two
# setups apart under power: the default's 75° drive ramp lets the inside wheel spin up (ρ −0.7…−2.7 above ~45 %
# throttle), WW103's 35° ramp holds it near 0 to full throttle. Both coast at ~0.4.
#
# The sim gives each rear wheel its own speed and a ramp-type LSD (vehicle_3d.jl). Its geometry comes from the
# garage (preload, ramps, plates); k does not. Binned by the diff INPUT torque Tin = engine_torque(rpm, throttle)
# × gear × final × η (the same function on both sides) at 0.8–1.2 g, 25–45 m/s; the sim holds a ~1 g circle, then
# squeezes the throttle to full over 5 s, at three speeds, each setup on its own ibt car.
#
#   julia --project=. tools/lsdfit_261005.jl            (gold table, then sim vs gold for a k sweep)
using Printf, Statistics
ENV["JM_NOTC"] = "1"                                         # raw car: iRacing ran no traction aid
include(joinpath(@__DIR__, "tyrefit_261002.jl"))             # IBT, Setup, ch, G
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const setp = ModelingToolkit.setp

const D4 = expanduser("~/gold standard/julia racer/261004")
const D5 = expanduser("~/gold standard/julia racer/261005")
const TBINS = [-100, 0, 150, 300, 450, 600, 800, 1000, 1300, 1700, 2500]   # Tin at the diff [N·m]
const ETA = 0.9

isww(sp) = sp.spring_rate_Npmm[:LF] < 24
binof(T) = (i = searchsortedlast(TBINS, T); 1 <= i < length(TBINS) ? i : 0)

function gold()
    B = Dict(s => [Float64[] for _ in 1:length(TBINS)-1] for s in (:def, :ww))
    for d in (D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        f = ibt_open(fn); sp = setup_params(f.yaml); s = isww(sp) ? :ww : :def
        c = Dict(n => ch(f, n) for n in ("Speed","YawRate","LatAccel","Throttle","Brake","LRspeed","RRspeed","IsOnTrack",
                                         "Gear","Clutch","RPM","VelocityX","VelocityY"))
        for k in 1:f.nrows
            c["IsOnTrack"][k] > 0.5 && 25 < c["Speed"][k] < 45 && c["Brake"][k] < 0.01 && c["Clutch"][k] > 0.95 || continue
            g = Int(c["Gear"][k]); 1 <= g <= 5 || continue
            0.8 <= abs(c["LatAccel"][k])/G < 1.2 && abs(c["YawRate"][k]) > 0.15 || continue
            abs(atan(c["VelocityY"][k], c["VelocityX"][k])) < deg2rad(10) || continue
            Tin = DriveRT3D.engine_torque(c["RPM"][k], c["Throttle"][k]) * sp.gear_ratios[g] * sp.final_drive * ETA
            b = binof(Tin); b == 0 && continue
            push!(B[s][b], (c["RRspeed"][k] - c["LRspeed"][k]) / (c["YawRate"][k]*1.5))
        end
    end
    B
end

"""Install one gold file's setup (gearbox, mass, springs, ride, chassis) -- the sim car for that side of the A/B."""
function install!(fn)
    sp = setup_params(ibt_open(fn).yaml)
    DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(fn))
    m, ff = DriveRT3D.mass_from_corner_weights(sp.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(fn))
    s = sp.spring_rate_Npmm
    DriveRT3D.set_suspension!(wheel_rate(s[:LF]), wheel_rate(s[:RF]), wheel_rate(s[:LR]; rear = true), wheel_rate(s[:RR]; rear = true); source = basename(fn))
    DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(sp; source = basename(fn)))
    sp
end

const RAMPS = Dict{Symbol,Any}()
"""Sim (Tin, ρ) samples: hold ~1 g at V, then squeeze to full throttle over 5 s, steer held."""
function sim_samples(car, sp, k)
    sys = car.sys
    setp(sys, sys.lsd_k)(car.integ, k)
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay, sys.ωRL, sys.ωRR, sys.rpm])
    u0 = get!(RAMPS, Symbol(objectid(car))) do; copy(car.integ.u) end
    out = Tuple{Float64,Float64}[]
    for V in (30.0, 36.0, 42.0), dir in (1.0, -1.0)
        reinit!(car.integ, copy(u0))
        g = findfirst(i -> V/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 8500, 1:5)
        car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
        ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
        ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
        car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
        δ = 0.0; ie = 0.0; thr = 0.3
        for n in 1:round(Int, 16*60)
            t = n/60
            u, v, r, ay = get(car.integ)
            if t < 9                                            # settle a ~1 g circle at V (PI throttle, I steer)
                δ = clamp(δ + 0.004*(0.98G - abs(ay))/G, 0.0, 0.25)
                thr = clamp(0.3 + 0.3*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.4, 0.7)
            else
                thr = min(1.0, thr + (1/60)/5)                  # squeeze to full over ~5 s
            end
            DriveRT3D.step_car3d!(car, thr, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            u, v, r, ay, ωL, ωR, rpm = get(car.integ)
            (isfinite(u) && u > 5) || break
            abs(atan(v, u)) > deg2rad(10) && break
            t > 6 && 0.8 <= abs(ay)/G < 1.2 && abs(r) > 0.15 || continue
            Tin = DriveRT3D.engine_torque(rpm, thr) * sp.gear_ratios[g] * sp.final_drive * ETA
            push!(out, (Tin, (ωR - ωL)*DriveRT3D.RW_R/(r*1.5)))
        end
    end
    out
end

function table(B, S)
    e = 0.0
    for s in (:def, :ww), b in 1:length(TBINS)-1
        gb = B[s][b]; length(gb) < 30 && continue
        sb = [p[2] for p in S[s] if binof(p[1]) == b]
        sm = length(sb) >= 10 ? median(sb) : NaN
        @printf("   %-3s  Tin %5d..%5d  gold n %5d ρ %6.2f   sim n %4d ρ %6.2f\n", s, TBINS[b], TBINS[b+1], length(gb), median(gb), length(sb), sm)
        isfinite(sm) && (e += sqrt(length(gb))*(clamp(sm, -3, 3) - clamp(median(gb), -3, 3))^2)
    end
    e
end

function main()
    B = gold()
    println("GOLD: rear split ρ by diff input torque (0.8–1.2 g, 25–45 m/s)")
    for s in (:def, :ww), b in 1:length(TBINS)-1
        length(B[s][b]) >= 30 && @printf("   %-3s  Tin %5d..%5d  n %5d  ρ med %6.2f (q25 %6.2f q75 %6.2f)\n", s, TBINS[b], TBINS[b+1],
                                         length(B[s][b]), median(B[s][b]), quantile(B[s][b], .25), quantile(B[s][b], .75))
    end
    files = Dict(:def => joinpath(D4, "lotus49_skidpad 2026-10-04 14-36-48.ibt"), :ww => joinpath(D5, "lotus49_skidpad 2026-10-06 00-21-30.ibt"))
    cars = Dict{Symbol,Any}(); sps = Dict{Symbol,Any}()
    for s in (:def, :ww)
        sps[s] = install!(files[s]); cars[s] = DriveRT3D.build_car3d(; v0 = 30.0)
    end
    ks = [parse(Float64, x) for x in split(get(ENV, "JM_LSD_KS", "0.03,0.06,0.1,0.15,0.22,0.3"), ',')]
    ws = [parse(Float64, x) for x in split(get(ENV, "JM_LSD_WEPS", string(DriveRT3D.LSD_WEPS)), ',')]
    best = (Inf, NaN, NaN, NaN)
    pres = [parse(Float64, x) for x in split(get(ENV, "JM_LSD_PRE", "1.0"), ',')]   # preload as a fraction of the garage's
    for w in ws, pf in pres, k in ks
        for s in (:def, :ww)
            setp(cars[s].sys, cars[s].sys.lsd_weps)(cars[s].integ, w)
            setp(cars[s].sys, cars[s].sys.lsd_pre)(cars[s].integ, pf*sps[s].diff_preload_Nm)
        end
        S = Dict(s => sim_samples(cars[s], sps[s], k) for s in (:def, :ww))
        println("\nk = $k   ωε = $w rad/s   preload x$pf")
        e = table(B, S); @printf("   score %.1f\n", e)
        e < best[1] && (best = (e, k, w, pf))
    end
    @printf("\nbest k %.3f ωε %.2f preload x%.2f (score %.1f)\n", best[2], best[3], best[4], best[1])
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
