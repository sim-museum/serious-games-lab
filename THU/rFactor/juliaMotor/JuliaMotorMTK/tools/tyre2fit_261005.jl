# TYRE-2: refit the brush tyre's lateral side THROUGH THE PLAYER CAR, now that the car carries camber (CAMBER-1) and its
# own diff, bars and toe (WWSETUP-1) -- with the stiffness LOAD EXPONENT ns (BrushTyre, CFα ∝ Fz^ns) free.
#
# Why: on the skidpad cells (tools/camberfit_261005.jl, three garage setups, both directions, each cell at its own speed,
# g and longitudinal acceleration) the sim slips ~20 % less than the gold at 0.8-0.95 g on both axles, and TYRE-1's
# target (the 261002 slip curve) was fitted on upright tyres. A brush that peaks lower (relative to where the car runs)
# slips more mid-range; a load-sensitive stiffness softens the loaded axle. Both are physical; the fit chooses.
#
# Score (degrees):  weighted RMS of the ABSOLUTE axle slips over every cell (both directions, so the skidpads'
#   152/207 kPa split averages out)  +  the camber A/B score (differences from the default, camberfit evaluate())
#   +  reach: the default car must hold 1.10 g both ways (the gold does: 1,032 samples)  +  10 × the stability penalty
#   (tools/stability_check.jl's step steers and WOT blips, on the default car).
# Bounds as TYRE-1: front μ ≤ rear μ ≤ the rear's braking μx; front Cα ≤ rear Cα (linear understeer); 0.3 ≤ ns ≤ 1.
#
#   julia --project=. tools/tyre2fit_261005.jl                    (score the current tyre, then Nelder-Mead)
#   JM_TYRE2_EVAL="μf,μr,Cf,Cr,ns"  julia ...                      (score one point, verbose)
#   JM_TYRE2_ITERS=40                                             (simplex iterations, default 40)
using Printf, Statistics
include(joinpath(@__DIR__, "camberfit_261005.jl"))           # cells, sim_cell, build_cars, set_camber!, DriveRT3D
include(joinpath(@__DIR__, "..", "fit", "fitutil.jl")); using .FitUtil: nelder_mead

function settyre2!(cars, θ)
    μf, μr, Cf, Cr, ns = θ
    for (_, c) in cars
        sys = c.car.sys
        for (w, μ, C) in ((:FL, μf, Cf), (:FR, μf, Cf), (:RL, μr, Cr), (:RR, μr, Cr))
            ty = getproperty(sys, w)
            setp(sys, ty.μ)(c.car.integ, μ); setp(sys, ty.Cα)(c.car.integ, C); setp(sys, ty.ns)(c.car.integ, ns)
        end
    end
end

# ---- stability (tools/tyreid_261002.jl's checks, on a given car) ----
function step_beta(c, V, thr, δd)
    car, sp = c.car, c.sp; sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v])
    reinit!(car.integ, copy(c.u0)); g = V > 30 ? 3 : 2; car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
    car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
    for k in 1:30; DriveRT3D.step_car3d!(car, thr, 0.0, 0.0, 1/60; clutch = 0.0, manual = true); end
    mb = 0.0
    for k in 1:240
        DriveRT3D.step_car3d!(car, thr, 0.0, deg2rad(δd)/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v = get(car.integ); mb = max(mb, abs(rad2deg(atan(v, max(u, 1.0))))); mb > 30 && break
    end
    mb
end
function wot_pulse(c, V)
    car, sp = c.car, c.sp; sys = car.sys
    get = ModelingToolkit.getsym(sys, sys.r)
    reinit!(car.integ, copy(c.u0)); g = 5; car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
    car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
    for k in 1:60; DriveRT3D.step_car3d!(car, 1.0, 0.0, 0.0, 1/60; clutch = 0.0, manual = true); end
    rs = Float64[]
    for k in 1:180
        DriveRT3D.step_car3d!(car, 1.0, 0.0, (k <= 12 ? deg2rad(0.5) : 0.0)/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        push!(rs, abs(get(car.integ)))
    end
    rs[end] / max(maximum(rs), 1e-6)
end
const STEPS = [(V, thr, δ) for V in (90/3.6, 125/3.6) for thr in (0.0, 0.45) for δ in (3.0, 5.0, 7.0)]
function stability(c; verbose = false)
    b = [step_beta(c, s...) for s in STEPS]; w = [wot_pulse(c, V) for V in (200/3.6, 240/3.6)]
    verbose && println("   step-steer max |β|: ", join([@sprintf("%.0f", x) for x in b], " "), "   WOT yaw left: ", join([@sprintf("%.2f", x) for x in w], " "))
    sum(max(0.0, x - 10.0)^2 for x in b) + sum(max(0.0, x - 0.10)^2 for x in w)*1e4
end

function score2(cars, C, θ; verbose = false)
    μf, μr, Cf, Cr, ns = θ
    (1.0 < μf < 1.8 && μf <= μr <= BRUSH_REAR.μx && 12 < Cf <= Cr < 60 && 0.3 <= ns <= 1.0) || return 1e3
    settyre2!(cars, θ)
    camb = (DriveRT3D.CAMBER_CG, DriveRT3D.CAMBER_KG, DriveRT3D.CAMBER_RC...)
    did = evaluate(cars, C, camb; verbose)                    # the A/B; also leaves every cell's sim result in LAST
    e = 0.0; w = 0.0
    for (key, sm) in LAST[]
        gd = C[key]; isfinite(sm.f) || (e += 25.0*sqrt(gd.n); w += sqrt(gd.n); continue)
        e += sqrt(gd.n)*((sm.f - gd.f)^2 + (sm.r - gd.r)^2); w += sqrt(gd.n)
    end
    absr = sqrt(e/w)
    d = cars[:def]; reach = 0.0
    for dir in (1, -1)
        r = sim_cell(d.car, d.sp, d.u0, 39.0, 1.10, dir; axt = 0.04*G)
        verbose && @printf("   reach 1.10 g dir %+d: sim %.2f g  front %.2f rear %.2f\n", dir, r.g, r.f, r.r)
        reach += isfinite(r.g) ? 20*max(0.0, 1.08 - r.g) : 1.0
    end
    st = stability(d; verbose)
    s = absr + did + reach + 10st
    verbose && @printf("   abs %.3f°  A/B %.3f°  reach %.3f  stability %.3f  => %.3f\n", absr, did, reach, st, s)
    @printf("   θ μf %.3f μr %.3f Cf %.2f Cr %.2f ns %.3f  score %.3f\n", θ..., s); flush(stdout)
    s
end

function main()
    C = gold_cells(); cars = build_cars()
    if haskey(ENV, "JM_TYRE2_EVAL")
        score2(cars, C, parse.(Float64, split(ENV["JM_TYRE2_EVAL"], ",")); verbose = true); return
    end
    T2 = DriveRT3D.TYRE2
    θ0 = [T2.μf, T2.μr, T2.Cαf, T2.Cαr, DriveRT3D.BRUSH_NS]
    println("CURRENT:"); score2(cars, C, θ0; verbose = true)
    θ, e = nelder_mead(θ -> score2(cars, C, θ), [θ0[1:4]..., 0.85]; iters = parse(Int, get(ENV, "JM_TYRE2_ITERS", "40")), step = 0.08)
    @printf("\nFITTED  μf %.3f μr %.3f Cf %.2f Cr %.2f ns %.3f  score %.3f\n", θ..., e)
    score2(cars, C, θ; verbose = true)
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
