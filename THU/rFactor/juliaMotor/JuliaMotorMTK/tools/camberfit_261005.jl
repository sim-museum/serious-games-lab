# CAMBER-1: the camber law (brush_tyre.jl CAMBER_*), identified THROUGH THE PLAYER CAR against the gold's steady cornering.
#
# The gold has three camber configurations on the skidpad, each driven both ways round:
#   default (261004, 00-38-20)   −0.5/−0.4/−0.4/−0.5   nearly symmetric
#   WW103   (261005)             −0.4/ 0.0/−0.4/+0.2   right side leans out
#   oval    (261002)             +0.4/−0.5/+0.3/−0.5   both sides lean left (left turns only below the limit)
# Every skidpad session ALSO runs 152 kPa left / 207 kPa right, which the model does not have, so the targets are
# DIFFERENCES from the default car at the same direction and g: [gold(cfg) − gold(default)] against
# [sim(cfg) − sim(default)], per axle. The pressure split and any common tyre-fit offset cancel; what remains is
# what the setups change -- camber, and the springs/bars/weights/diff the model already has from each session.
#
# A cell = (configuration, direction, g band): the gold's median front/rear axle slip (the TYRE-1 extractor,
# wwab_261005.jl steady(), samples > 15 m/s and front slip < 12° -- the limit-ploughing excluded) and its median
# SPEED. The sim car of that session is settled on that circle at that speed and g (PI throttle on speed, I steer
# on lateral g) and its axle slips read the same way. Cells are run at their own speed because the A/B is
# confounded by it: WW103's right-hand runs were at 40 m/s and its left-hand ones at 24, and the faster circle
# carries more drive force on the rear.
#
#   julia --project=. tools/camberfit_261005.jl                     (upright tyres, then the grid)
#   JM_CAMB_EVAL="Cg,kg,rcf,rcr"  julia ... tools/camberfit_261005.jl   (score one point)
#   JM_CAMB_GRID="1;5,8,12;0.75,1;0.25,0.5,0.75"                      (a different grid)
#   JM_CAMB_MU="μf,μr"                                                 (the upright μ the joint fit gave for that kγ)
using Printf, Statistics
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "arbfit_261005.jl"))              # install!, steady(), D4/D5, DriveRT3D, setp
const D2 = expanduser("~/gold standard/julia racer/261002")
const CFILES = Dict(:def  => joinpath(D4, "lotus49_skidpad 2026-10-04 14-36-48.ibt"),
                    :ww   => joinpath(D5, "lotus49_skidpad 2026-10-06 00-21-30.ibt"),
                    :oval => joinpath(D2, "lotus49_skidpad 2026-10-02 23-16-16.ibt"))
const GC = (0.65, 0.80, 0.95)                                 # g band centres, ±0.075
cfgof(sp) = sp.camber_deg[:LF] > 0 ? :oval : sp.spring_rate_Npmm[:LF] < 24 ? :ww : :def

function gold_cells()
    S = Dict{Tuple{Symbol,Int},Vector{NamedTuple}}()
    for d in (D2, D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        c = cfgof(setup_params(ibt_open(fn).yaml))
        for q in steady(fn)
            q.v > 15 && abs(q.αf) < deg2rad(12) && append!(get!(S, (c, q.dir), NamedTuple[]), [q])
        end
    end
    C = Dict{Tuple{Symbol,Int,Float64},NamedTuple}()
    for ((c, dir), P) in S, g in GC
        ii = [q for q in P if g - 0.075 <= q.g < g + 0.075]
        length(ii) >= 40 || continue
        ρs = [q.ρ for q in ii if isfinite(q.ρ)]
        C[(c, dir, g)] = (n = length(ii), f = rad2deg(median(q.αf for q in ii)), r = rad2deg(median(q.αr for q in ii)),
                          v = median(q.v for q in ii), ax = median(q.ax for q in ii), thr = median(q.thr for q in ii),
                          ρ = isempty(ρs) ? NaN : median(ρs))
    end
    C
end

"""Set the camber law on a built car (live MTK parameters: no rebuild)."""
function set_camber!(car, Cg, kg, rcf, rcr)
    sys = car.sys
    for w in (sys.FL, sys.FR, sys.RL, sys.RR)
        setp(sys, getproperty(w, :Cγ))(car.integ, Cg); setp(sys, getproperty(w, :kγ))(car.integ, kg)
    end
    setp(sys, sys.rc_f)(car.integ, rcf); setp(sys, sys.rc_r)(car.integ, rcr)
end

"""Settle on a circle at lateral g `gt` in direction `dir`, then hold the gold cell's longitudinal acceleration `axt`
(CAMBER-1 S2: the gold's 0.65 g WW cells were COASTING, which a constant-speed sim cell is not); the speed passes V at
the middle of the measurement. Means over the last 1.5 s: axle slips (deg), lateral g, rear split ρ, throttle."""
function sim_cell(car, sp, u0, V, gt, dir; axt = 0.0)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay, sys.δ, sys.ax, sys.ωRL, sys.ωRR])
    a = ModelingToolkit.getp(sys, sys.a)(car.integ); b = ModelingToolkit.getp(sys, sys.b)(car.integ)
    reinit!(car.integ, copy(u0))
    Vs = V - axt*2.25                                        # 9 s at Vs, then 3 s at axt: V at 11.25 s
    g = findfirst(i -> max(V, Vs)/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 8200, 1:5)
    car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [Vs, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [Vs/0.30, Vs/DriveRT3D.RW_R, Vs/DriveRT3D.RW_R])
    car.s_we(car.integ, Vs/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
    δ = 0.6*gt*G*(a + b)/Vs^2 + 0.02*gt; ie = 0.0; thr = 0.3
    F = Float64[]; R = Float64[]; Gs = Float64[]; P = Float64[]; Th = Float64[]
    for n in 1:12*60
        u, v, r, ay, _, ax = get(car.integ)
        δ = clamp(δ + 0.006*(gt*G - abs(ay))/G, 0.0, 0.30)
        if n <= 9*60
            thr = clamp(0.3 + 0.3*(Vs - u) + ie, 0, 1); ie = clamp(ie + 0.01*(Vs - u), -0.4, 0.8)
        else
            thr = clamp(thr + 0.02*(axt - ax), 0, 1)        # integral on the longitudinal acceleration
        end
        DriveRT3D.step_car3d!(car, thr, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, r, ay, δr, ax, wl, wr = get(car.integ)
        (isfinite(u) && u > 5 && abs(atan(v, u)) < deg2rad(20)) || return (f = NaN, r = NaN, g = NaN, ρ = NaN, thr = NaN)
        if n > 10.5*60
            push!(F, rad2deg(dir*(δr - atan(v + a*r, u)))); push!(R, rad2deg(dir*(-atan(v - b*r, u)))); push!(Gs, abs(ay)/G)
            abs(r) > 0.1 && push!(P, (wr - wl)*DriveRT3D.RW_R/(r*1.5)); push!(Th, thr)
        end
    end
    (f = mean(F), r = mean(R), g = mean(Gs), ρ = isempty(P) ? NaN : mean(P), thr = mean(Th))
end

function build_cars()
    cars = Dict{Symbol,Any}()
    for (k, fn) in CFILES
        sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0)
        if haskey(ENV, "JM_CAMB_MU")                         # the upright μ front/rear from the joint fit (tyreid JM_CAMB_TRY)
            μf, μr = parse.(Float64, split(ENV["JM_CAMB_MU"], ","))
            for w in (:FL, :FR); setp(car.sys, getproperty(getproperty(car.sys, w), :μ))(car.integ, μf); end
            for w in (:RL, :RR); setp(car.sys, getproperty(getproperty(car.sys, w), :μ))(car.integ, μr); end
        end
        cars[k] = (car = car, sp = sp, u0 = copy(car.integ.u), desc = DriveRT3D.describe_chassis())
    end
    cars
end

"""Sim slips for every gold cell, then the score: Σ over non-default cells of the squared error of the
difference from the default's cell (same direction, same g), front and rear, weighted by √n of the smaller."""
function evaluate(cars, C, θ; verbose = false)
    S = Dict{Any,NamedTuple}()
    for (k, c) in cars
        set_camber!(c.car, θ...)
    end
    for key in sort(collect(keys(C)); by = string)
        (c, dir, g) = key
        S[key] = sim_cell(cars[c].car, cars[c].sp, cars[c].u0, C[key].v, g, dir; axt = C[key].ax)
    end
    err = 0.0; wsum = 0.0
    verbose && println("   cfg   dir  g    | gold  front  rear (n, v)  ax g thr ρ | sim  front  rear  g    thr  ρ   | Δdef gold f  r | Δdef sim f  r")
    for key in sort(collect(keys(C)); by = string)
        (c, dir, g) = key; gd = C[key]; sm = S[key]
        dk = (:def, dir, g)
        if verbose
            @printf("   %-5s %+d  %.2f | %5.2f %5.2f (%4d, %4.1f) %+.2f %.2f %5.2f | %5.2f %5.2f %.2f %.2f %5.2f", c, dir, g, gd.f, gd.r,
                    gd.n, gd.v, gd.ax/G, gd.thr, gd.ρ, sm.f, sm.r, sm.g, sm.thr, sm.ρ)
        end
        if c !== :def && haskey(C, dk)
            Gf = gd.f - C[dk].f; Gr = gd.r - C[dk].r; Sf = sm.f - S[dk].f; Sr = sm.r - S[dk].r
            w = sqrt(min(gd.n, C[dk].n))
            err += w*((Sf - Gf)^2 + (Sr - Gr)^2); wsum += w
            verbose && @printf(" | %+5.2f %+5.2f | %+5.2f %+5.2f", Gf, Gr, Sf, Sr)
        end
        verbose && println()
    end
    isfinite(err) ? sqrt(err/wsum) : Inf
end

function main()
    C = gold_cells()
    cars = build_cars()
    for k in (:def, :ww, :oval); println("$k: ", cars[k].desc); end
    if haskey(ENV, "JM_CAMB_EVAL")
        θ = Tuple(parse.(Float64, split(ENV["JM_CAMB_EVAL"], ",")))
        @printf("\nθ = Cγ %.2f  kγ %.2f  rc %.2f/%.2f\n", θ...)
        @printf("score %.3f°\n", evaluate(cars, C, θ; verbose = true)); return
    end
    @printf("\nUPRIGHT-EQUIVALENT (Cγ 0, kγ 0): score %.3f°\n", evaluate(cars, C, (0.0, 0.0, 0.0, 0.0); verbose = true))
    best = (Inf, ())
    # JM_CAMB_GRID="Cγs;kγs;rc_fs;rc_rs" (comma lists) overrides the coarse grid
    gl = haskey(ENV, "JM_CAMB_GRID") ? [parse.(Float64, split(x, ",")) for x in split(ENV["JM_CAMB_GRID"], ";")] :
         [[0.0, 1.0, 2.5], [0.0, 2.0, 5.0], [0.0, 0.5, 1.0], [0.5, 1.0]]
    for Cg in gl[1], kg in gl[2], rcf in gl[3], rcr in gl[4]
        s = evaluate(cars, C, (Cg, kg, rcf, rcr))
        @printf("   Cγ %.1f kγ %.1f rc %.1f/%.1f  score %.3f°\n", Cg, kg, rcf, rcr, s); flush(stdout)
        s < best[1] && (best = (s, (Cg, kg, rcf, rcr)))
    end
    @printf("\nBEST: Cγ %.1f kγ %.1f rc %.1f/%.1f  score %.3f°\n", best[2]..., best[1])
    evaluate(cars, C, best[2]; verbose = true)
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
