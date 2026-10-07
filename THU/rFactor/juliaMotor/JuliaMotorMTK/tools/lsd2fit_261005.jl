# LSD-2: the rear diff's preload and friction constant fitted on BOTH regimes the gold shows.
#   (a) POWER breakaway (tools/lsdfit_261005.jl): the rear split ρ by diff input torque while the throttle is squeezed to
#       full on a ~1 g circle -- the default's 75° ramp lets the inside wheel spin up above ~450 N·m, WW's 35° holds.
#   (b) STEADY cells (tools/camberfit_261005.jl): ρ at 0.65/0.8/0.95 g at each cell's own speed and longitudinal
#       acceleration -- the gold's diff is about HALF OPEN under light power (default ~0.5) and on the coast, where the
#       sim's (preload 41 N·m, k 0.20) is LOCKED (CAMBER-1 S2).
# Free: the preload as a fraction of the garage's (iRacing's "Preload" need not be the clutch packs' static breakaway in
# this model's sense) and LSD_K. Scores are reported separately; (b) uses direction-averaged gold where both directions
# exist (the skidpads' 152/207 kPa split makes the two directions differ in the gold, which the model has no input for).
#
#   julia --project=. tools/lsd2fit_261005.jl                 JM_LSD2_PRE="0.25,0.5,0.75,1" JM_LSD2_K="0.15,0.2,0.25"
using Printf, Statistics
include(joinpath(@__DIR__, "camberfit_261005.jl"))           # cells, sim_cell, build_cars, D4/D5, ch, setp, DriveRT3D
const TBINS = [-100, 0, 150, 300, 450, 600, 800, 1000, 1300, 1700, 2500]
const ETA = 0.9
binof(T) = (i = searchsortedlast(TBINS, T); 1 <= i < length(TBINS) ? i : 0)
isww(sp) = sp.spring_rate_Npmm[:LF] < 24

function gold_power()
    B = Dict(s => [Float64[] for _ in 1:length(TBINS)-1] for s in (:def, :ww))
    for d in (D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        f = ibt_open(fn); sp = setup_params(f.yaml); s = isww(sp) ? :ww : :def
        c = Dict(n => ch(f, n) for n in ("Speed","YawRate","LatAccel","Throttle","Brake","LRspeed","RRspeed","IsOnTrack","Gear","Clutch","RPM"))
        for k in 1:f.nrows
            c["IsOnTrack"][k] > 0.5 && 25 < c["Speed"][k] < 45 && c["Brake"][k] < 0.01 && c["Clutch"][k] > 0.95 || continue
            g = Int(c["Gear"][k]); 1 <= g <= 5 || continue
            0.8 <= abs(c["LatAccel"][k])/G < 1.2 && abs(c["YawRate"][k]) > 0.15 || continue
            Tin = DriveRT3D.engine_torque(c["RPM"][k], c["Throttle"][k]) * sp.gear_ratios[g] * sp.final_drive * ETA
            b = binof(Tin); b > 0 && push!(B[s][b], (c["RRspeed"][k] - c["LRspeed"][k])/(c["YawRate"][k]*1.5))
        end
    end
    B
end

"""Sim (Tin, ρ): settle a ~1 g circle at V (rate-limited steer -- TYRE-2 S1), then squeeze to full throttle over 5 s."""
function sim_power(c)
    car, sp, u0 = c.car, c.sp, c.u0; sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay, sys.ωRL, sys.ωRR, sys.rpm])
    out = Tuple{Float64,Float64}[]
    for V in (30.0, 36.0, 42.0), dir in (1.0, -1.0)
        reinit!(car.integ, copy(u0))
        g = findfirst(i -> V/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 8500, 1:5)
        car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
        ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
        ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
        car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
        δ = 0.02; ie = 0.0; thr = 0.3
        for n in 1:16*60
            t = n/60; u, v, r, ay = get(car.integ)
            if t < 9
                δ = clamp(δ + clamp(0.004*(25/max(V, 25))^2*(0.98G - abs(ay))/G, -0.0005, 0.0005), 0.0, 0.25)
                thr = clamp(0.3 + 0.3*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.4, 0.7)
            else
                thr = min(1.0, thr + (1/60)/5)
            end
            DriveRT3D.step_car3d!(car, thr, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            u, v, r, ay, ωL, ωR, rpm = get(car.integ)
            (isfinite(u) && u > 5 && abs(atan(v, u)) < deg2rad(10)) || break
            t > 6 && 0.8 <= abs(ay)/G < 1.2 && abs(r) > 0.15 || continue
            push!(out, (DriveRT3D.engine_torque(rpm, thr) * sp.gear_ratios[g] * sp.final_drive * ETA, (ωR - ωL)*DriveRT3D.RW_R/(r*1.5)))
        end
    end
    out
end

function score_power(B, S; verbose = false)
    e = 0.0
    for s in (:def, :ww), b in 1:length(TBINS)-1
        gb = B[s][b]; length(gb) < 30 && continue
        sb = [p[2] for p in S[s] if binof(p[1]) == b]; sm = length(sb) >= 10 ? median(sb) : NaN
        verbose && @printf("     power %-3s Tin %5d..%5d  gold %6.2f  sim %6.2f\n", s, TBINS[b], TBINS[b+1], median(gb), sm)
        isfinite(sm) && (e += sqrt(length(gb))*(clamp(sm, -3, 3) - clamp(median(gb), -3, 3))^2)
    end
    e
end

function score_cells(C, cars; verbose = false)
    # gold target per (cfg, g): direction-averaged where both directions exist
    tg = Dict{Tuple{Symbol,Float64},Float64}(); nn = Dict{Tuple{Symbol,Float64},Int}()
    for ((c, d, g), x) in C
        isfinite(x.ρ) || continue
        k = (c, g); tg[k] = get(tg, k, 0.0) + x.ρ; nn[k] = get(nn, k, 0) + 1
    end
    e = 0.0; w = 0.0; sims = Dict{Tuple{Symbol,Float64},Vector{Float64}}()
    for ((c, d, g), x) in C
        isfinite(x.ρ) || continue
        r = sim_cell(cars[c].car, cars[c].sp, cars[c].u0, x.v, g, d; axt = x.ax)
        push!(get!(sims, (c, g), Float64[]), r.ρ)
    end
    for (k, v) in sims
        gm = tg[k]/nn[k]; fv = filter(isfinite, v); sm = isempty(fv) ? NaN : mean(fv)
        verbose && @printf("     cell %-4s %.2f g  gold %5.2f  sim %5.2f\n", k[1], k[2], gm, sm)
        isfinite(sm) && (e += (clamp(sm, -2, 2) - gm)^2; w += 1)
    end
    sqrt(e/max(w, 1))
end

function main()
    B = gold_power(); C = gold_cells(); cars = build_cars()
    pres = parse.(Float64, split(get(ENV, "JM_LSD2_PRE", "0.25,0.5,0.75,1.0"), ","))
    ks = parse.(Float64, split(get(ENV, "JM_LSD2_K", "0.15,0.2,0.25"), ","))
    verbose = haskey(ENV, "JM_LSD2_VERBOSE")
    for pf in pres, k in ks
        for (name, c) in cars
            setp(c.car.sys, c.car.sys.lsd_pre)(c.car.integ, pf*c.sp.diff_preload_Nm)
            setp(c.car.sys, c.car.sys.lsd_k)(c.car.integ, k)
        end
        S = Dict(:def => sim_power(cars[:def]), :ww => sim_power(cars[:ww]))
        ep = score_power(B, S; verbose); ec = score_cells(C, cars; verbose)
        @printf("preload x%.2f  k %.2f  | power %7.1f  | cells ρ rms %.3f\n", pf, k, ep, ec); flush(stdout)
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
