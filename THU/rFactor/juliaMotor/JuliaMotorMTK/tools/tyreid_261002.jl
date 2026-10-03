# TYRE-1: identify the brush tyre (μ, Cα per axle, kμ) THROUGH THE PLAYER CAR, so lateral load
# transfer, load sensitivity, the suspension and the rear's drive force are all in the loop -- the
# same "fit in the sim's own frame" rule as E91-S10.
#
# Target: the gold's steady-state cornering curve -- median front and rear axle slip angle per 0.1 g
# lateral band (tools/tyrefit_261002.jl, Nordschleife + Centripetal Circuit; Charlotte's 24° banking
# is excluded because LatAccel/g there overstates grip use). Sim: constant speed (PI throttle), a slow
# steering ramp, the axle slip angles computed from u, v, r, δ with exactly the gold's formula.
#
#   julia --project=. tools/tyreid_261002.jl            (prints the gold target, current tyre, fit)
using Printf, Statistics
ENV["JM_NOTC"] = "1"                                         # raw car: no traction aid (iRacing had none)
include(joinpath(@__DIR__, "tyrefit_261002.jl"))             # loadtyre, REF, brush_tyre
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const setp = ModelingToolkit.setp

const BANDS = 0.1:0.1:1.2
function gold_target()
    P = filter(p -> !occursin("charlotte", p.file), loadtyre(REF))
    T = NamedTuple[]
    for g in BANDS
        ii = [p for p in P if g <= p.ay/G < g + 0.1]; length(ii) < 30 && continue
        push!(T, (g = mean(p.ay for p in ii)/G, af = rad2deg(median(p.αf for p in ii)),
                  ar = rad2deg(median(p.αr for p in ii)), n = length(ii)))
    end
    T
end

# the car on the skidpad session's setup (the session with the plateau data; asymmetric corners)
skid = first(filter(f -> occursin("skidpad 2026-10-02 23", f), readdir(REF; join = true)))
let p = setup_params(ibt_open(skid).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(skid))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(skid))
end
const V0 = 24.0                                               # 86 km/h: the skidpad's 1.0-1.2 g speed
const CAR = DriveRT3D.build_car3d(; v0 = V0)
const U0 = copy(CAR.integ.u)
const SYS = CAR.sys
const SETW = Dict((w, k) => setp(SYS, getproperty(getproperty(SYS, w), k)) for w in (:FL,:FR,:RL,:RR) for k in (:μ,:Cα,:kμ))
const GET = ModelingToolkit.getsym(SYS, [SYS.u, SYS.v, SYS.r, SYS.ay])
const A_CG = ModelingToolkit.getp(SYS, SYS.a)(CAR.integ)      # the sim's own CG geometry
const B_CG = ModelingToolkit.getp(SYS, SYS.b)(CAR.integ)

function settyre!(μf, μr, Cf, Cr, kμ)
    for w in (:FL, :FR); SETW[(w,:μ)](CAR.integ, μf); SETW[(w,:Cα)](CAR.integ, Cf); SETW[(w,:kμ)](CAR.integ, kμ); end
    for w in (:RL, :RR); SETW[(w,:μ)](CAR.integ, μr); SETW[(w,:Cα)](CAR.integ, Cr); SETW[(w,:kμ)](CAR.integ, kμ); end
end

# steering ramp 0 -> δmax over `tr` s at constant speed; returns per-band median axle slip (deg)
function sim_curve(; δmax = 0.14, tr = 24.0, dir = 1.0)
    reinit!(CAR.integ, copy(U0)); CAR.gear = 2; CAR.s_gr(CAR.integ, DriveRT3D.GEARS[2])
    CAR.s_we(CAR.integ, V0/DriveRT3D.RW_R*DriveRT3D.GEARS[2]*DriveRT3D.FINAL[])
    pts = NTuple{3,Float64}[]; ie = 0.0; ayprev = 0.0; maxay = 0.0
    for k in 1:round(Int, (tr + 1)*60)
        t = k/60; δ = dir*δmax*clamp((t - 1)/tr, 0, 1)
        thr = clamp(0.25 + 0.4*(V0 - CAR.v) + ie, 0, 1); ie = clamp(ie + 0.02*(V0 - CAR.v), -0.5, 0.8)
        DriveRT3D.step_car3d!(CAR, thr, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)   # input is normalised
        u, v, r, ay = GET(CAR.integ)
        (isfinite(u) && u > 5) || break
        abs(atan(v, u)) > deg2rad(15) && break                  # spun / sliding: past the steady limit
        t > 2 && abs(CAR.v - V0) < 1.5 || continue
        s = sign(ay); s == 0 && continue
        αf = δ - atan(v + A_CG*r, u); αr = -atan(v - B_CG*r, u)
        push!(pts, (s*ay/G, rad2deg(s*αf), rad2deg(s*αr))); maxay = max(maxay, s*ay/G)
    end
    out = Dict{Float64,Tuple{Float64,Float64}}()
    for g in BANDS
        ii = [p for p in pts if g <= p[1] < g + 0.1]; length(ii) < 10 && continue
        out[g] = (median(getindex.(ii, 2)), median(getindex.(ii, 3)))
    end
    out, maxay
end

function score(T, θ; verbose = false)
    μf, μr, Cf, Cr, kμ = θ
    (0.8 < μf < 1.8 && 0.8 < μr < 1.8 && 8 < Cf < 60 && 8 < Cr < 60 && 0 <= kμ < 0.4) || return 1e9
    settyre!(μf, μr, Cf, Cr, kμ)
    e = 0.0
    for dir in (1.0, -1.0)                                  # both directions: the skidpad car is asymmetric
        S, maxay = sim_curve(; dir)
        for tg in T
            g = floor(tg.g*10)/10; key = argmin(b -> abs(b - g), collect(BANDS))
            if haskey(S, key)
                sf, sr = S[key]; e += sqrt(tg.n)*((sf - tg.af)^2 + (sr - tg.ar)^2)
                verbose && @printf("   dir %+d  %.2f g | gold front %5.2f rear %5.2f | sim front %5.2f rear %5.2f\n", dir, tg.g, tg.af, tg.ar, sf, sr)
            else
                e += sqrt(tg.n)*25.0                         # band not reached: the car cannot hold that g
                verbose && @printf("   dir %+d  %.2f g | gold front %5.2f rear %5.2f | sim -- (max steady %.2f g)\n", dir, tg.g, tg.af, tg.ar, maxay)
            end
        end
    end
    e
end

function main()
    T = gold_target()
    println("gold target (Ring + Centripetal, steady):"); for t in T; @printf("   %.2f g  n %5d  front %5.2f°  rear %5.2f°\n", t.g, t.n, t.af, t.ar); end
    θ0 = [BRUSH_FRONT.μ, BRUSH_REAR.μ, BRUSH_FRONT.Cα, BRUSH_REAR.Cα, BRUSH_FRONT.kμ]
    @printf("\nCURRENT tyre %s  score %.1f\n", θ0, score(T, θ0; verbose = true))
    parse(Int, get(ENV, "JM_TYREID_ITERS", "150")) == 0 && return θ0
    θ, e = nelder_mead(θ -> score(T, θ), [1.15, 1.15, 24.0, 34.0, 0.08]; iters = parse(Int, get(ENV, "JM_TYREID_ITERS", "150")), step = 0.1)
    @printf("\nFITTED tyre  μf %.3f  μr %.3f  Cαf %.2f  Cαr %.2f  kμ %.3f   score %.1f\n", θ..., e)
    score(T, θ; verbose = true)
    θ
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
