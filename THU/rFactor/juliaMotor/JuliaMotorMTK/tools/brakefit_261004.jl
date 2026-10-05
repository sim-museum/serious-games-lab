# IRFIT-261004 BRAKE-2: identify the brakes and the tyre's LONGITUDINAL side through the player car, from the
# PO's 2026-10-04 steady-pedal stops and deliberate lock-ups at the Döttinger Höhe (test 1; files 12-00 to
# 14-08 and 15-52 in `gold standard/julia racer/261004`, all on the symmetric 261004_nurburgring setup).
#
# Gold (wheel-speed channels read 1.000 x Speed when free-rolling, so κ = wheel/Speed − 1 directly):
#   * steady straight braking, pedal sd < 0.03 over ±0.15 s, |lat| < 0.15 g, no wheel past κ −0.3:
#     deceleration (slope-corrected) and front/rear axle κ per 0.1-pedal x speed band, in gear;
#   * LOCKED slides (all four wheels κ < −0.8, pedal > 0.8): deceleration per speed band.
# iRacing: line pressure is linear in pedal (65.4 / 56.9 bar at full pedal = the 53.5 % bias), the car holds
# ~1.4 g at κ −0.15..−0.22 at full pedal, and once locked it STAYS locked at ~1.0 g until the pedal comes up.
#
# Sim: constant-pedal straight stops of DriveRT3D in the gold bin's own gear (engine braking included,
# clutch in below 2300 rpm as the PO did), plus a forced lock (wheel speeds zeroed at full pedal) that must
# stay locked. Fitted: Tbrake_max, torque split, Cκ front/rear, μx front/rear, sliding fraction rs.
#
#   julia --project=. tools/brakefit_261004.jl         (JM_BRAKEFIT_ITERS=0: report the current model only)
using Printf, Statistics
ENV["JM_NOTC"] = "1"
const TT = joinpath(@__DIR__, "..")
include(joinpath(TT, "src", "ibt.jl"));   using .IBT
include(joinpath(TT, "src", "setup.jl")); using .Setup
include(joinpath(TT, "fit", "fitutil.jl")); using .FitUtil
include(joinpath(TT, "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const setp = ModelingToolkit.setp
const G = 9.80665; const DT = 1/60; const HW = 9
const DIR = get(ENV, "JM_BRAKEDIR", expanduser("~/gold standard/julia racer/261004"))
lslope(y, k, hw = HW) = (s = 0.0; for j in -hw:hw; s += j*y[k+j]; end; s / (DT * hw*(hw+1)*(2hw+1)/3))

const RING = filter(f -> occursin("nordschleife", f) && endswith(f, ".ibt"), readdir(DIR; join = true))

function gold()
    P = NamedTuple[]; L = NamedTuple[]
    for fn in RING
        f = ibt_open(fn); ch(n) = channel(f, n)
        thr, brk, spd, lfs, rfs, lrs, rrs, lat, cl, gr, alt, on = ch.(["Throttle","Brake","Speed","LFspeed","RFspeed",
            "LRspeed","RRspeed","LatAccel","Clutch","Gear","Alt","IsOnTrack"])
        for k in 1+2HW:f.nrows-2HW
            on[k] > 0.5 && spd[k] > 14 && brk[k] > 0.08 && thr[k] < 0.02 || continue
            w = k-HW:k+HW
            maximum(j -> abs(lat[j]), w) < 0.15G || continue
            κ = (lfs[k], rfs[k], lrs[k], rrs[k]) ./ spd[k] .- 1
            dec = -(lslope(spd, k) + G*lslope(alt, k)/spd[k])/G
            if all(<(-0.8), κ) && brk[k] > 0.8
                push!(L, (v = spd[k], dec = dec))
                continue
            end
            all(j -> thr[j] < 0.02, w) && std(brk[w]) < 0.03 || continue
            minimum(κ) > -0.3 && cl[k] > 0.95 && gr[k] >= 2 || continue      # unlocked, in gear
            push!(P, (v = spd[k], pedal = brk[k], dec = dec, κf = (κ[1]+κ[2])/2, κr = (κ[3]+κ[4])/2, gear = Int(gr[k])))
        end
    end
    B = NamedTuple[]
    for lo in 0.1:0.1:0.9, (vlo, vhi) in ((14, 28), (28, 42), (42, 56), (56, 80))
        Q = [p for p in P if lo <= p.pedal < lo + 0.1 + (lo > 0.85 ? 0.05 : 0) && vlo <= p.v < vhi]
        length(Q) < 10 && continue
        gs = [p.gear for p in Q]; g = argmax(x -> count(==(x), gs), unique(gs))
        push!(B, (pedal = median(p.pedal for p in Q), vlo = vlo, vhi = vhi, n = length(Q), gear = g,
                  dec = median(p.dec for p in Q), κf = median(p.κf for p in Q), κr = median(p.κr for p in Q)))
    end
    LB = NamedTuple[]
    for (vlo, vhi) in ((5, 14), (14, 28), (28, 42), (42, 60))
        Q = [p for p in L if vlo <= p.v < vhi]; length(Q) < 20 && continue
        push!(LB, (vlo = vlo, vhi = vhi, n = length(Q), dec = median(p.dec for p in Q)))
    end
    B, LB
end

# the car on the 261004 Ring setup (gearbox, corner weights)
let p = setup_params(ibt_open(RING[1]).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(RING[1]))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(RING[1]))
end
const CAR = DriveRT3D.build_car3d(; v0 = 40.0)
const U0 = copy(CAR.integ.u)
const SYS = CAR.sys
const SETB = (setp(SYS, SYS.Tbrake_max), setp(SYS, SYS.bias))
const SETW = Dict((w, k) => setp(SYS, getproperty(getproperty(SYS, w), k)) for w in (:FL,:FR,:RL,:RR) for k in (:μx,:Cκ,:rs,:ws))
const GET = ModelingToolkit.getsym(SYS, [SYS.u, SYS.v, SYS.ωf, SYS.ωr])
const SETWHEEL = ModelingToolkit.setu(SYS, [SYS.ωf, SYS.ωr])

function setmodel!(θ)
    Tb, bias, Cf, Cr, μf, μr, rs = θ
    SETB[1](CAR.integ, Tb); SETB[2](CAR.integ, bias)
    for w in (:FL, :FR); SETW[(w,:Cκ)](CAR.integ, Cf); SETW[(w,:μx)](CAR.integ, μf); SETW[(w,:rs)](CAR.integ, rs); end
    for w in (:RL, :RR); SETW[(w,:Cκ)](CAR.integ, Cr); SETW[(w,:μx)](CAR.integ, μr); SETW[(w,:rs)](CAR.integ, rs); end
end

# constant-pedal straight stop in `gear` from v0; returns (v, dec g, κf, κr) at 60 Hz. `lock`: zero the wheels at t=0.3 s.
function stop(pedal, v0, gear; lock = false, vend = 6.0)
    reinit!(CAR.integ, copy(U0)); CAR.gear = gear; CAR.s_gr(CAR.integ, DriveRT3D.gearratio(gear))
    ModelingToolkit.setu(SYS, [SYS.u, SYS.v])(CAR.integ, [v0, 0.0])
    SETWHEEL(CAR.integ, [v0/0.30, v0/DriveRT3D.RW_R])
    CAR.s_we(CAR.integ, v0/DriveRT3D.RW_R*DriveRT3D.GEARS[gear]*DriveRT3D.FINAL[])
    for k in 1:20; DriveRT3D.step_car3d!(CAR, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true); end
    vs = Float64[]; kf = Float64[]; kr = Float64[]; clu = 0.0
    for k in 1:60*20
        lock && k == 18 && SETWHEEL(CAR.integ, [0.0, 0.0])
        CAR.rpm < 2300 && (clu = 1.0)
        DriveRT3D.step_car3d!(CAR, 0.0, pedal*clamp(k/6, 0, 1), 0.0, DT; clutch = clu, manual = true)
        u, v, ωf, ωr = GET(CAR.integ)
        (isfinite(u) && u > vend) || break
        push!(vs, u); push!(kf, (ωf*0.30 - u)/u); push!(kr, (ωr*DriveRT3D.RW_R - u)/u)
    end
    out = NTuple{4,Float64}[]
    for k in 12+HW:length(vs)-HW                      # after the 0.1 s pedal ramp
        push!(out, (vs[k], -lslope(vs, k)/G, kf[k], kr[k]))
    end
    out
end

function score(B, LB, θ; verbose = false)
    Tb, bias, Cf, Cr, μf, μr, rs = θ
    (1000 < Tb < 6000 && 0.4 < bias < 0.8 && 8 < Cf < 60 && 8 < Cr < 60 && 0.9 < μf < 2.0 && 0.9 < μr < 2.0 && 0.4 < rs <= 1.0) || return 1e9
    setmodel!(θ); e = 0.0
    verbose && println("   pedal  km/h     gear  n   | gold dec  κf      κr     | sim dec  κf      κr")
    for b in B
        S = [s for s in stop(b.pedal, b.vhi + 3.0, b.gear) if b.vlo <= s[1] < b.vhi]
        if isempty(S) || minimum(s -> min(s[3], s[4]), S) < -0.5
            e += sqrt(b.n)*400.0                          # locked where the gold held the wheels turning
            verbose && @printf("   %.2f  %3.0f-%3.0f  %d %4d   | %.3f  %+.4f %+.4f | LOCKED / none\n", b.pedal, 3.6b.vlo, 3.6b.vhi, b.gear, b.n, b.dec, b.κf, b.κr)
            continue
        end
        d = median(getindex.(S, 2)); f = median(getindex.(S, 3)); r = median(getindex.(S, 4))
        e += sqrt(b.n)*(((d - b.dec)/0.03)^2 + ((f - b.κf)/0.01)^2 + ((r - b.κr)/0.01)^2)
        verbose && @printf("   %.2f  %3.0f-%3.0f  %d %4d   | %.3f  %+.4f %+.4f | %.3f  %+.4f %+.4f\n", b.pedal, 3.6b.vlo, 3.6b.vhi, b.gear, b.n, b.dec, b.κf, b.κr, d, f, r)
    end
    S = stop(1.0, 60.0, 5; lock = true)
    held = isempty(S) ? 0.0 : mean(s -> max(s[3], s[4]) < -0.8, S)
    e += 300.0*(1 - held)^2*length(LB)
    for b in LB
        Q = [s for s in S if b.vlo <= s[1] < b.vhi && max(s[3], s[4]) < -0.8]
        isempty(Q) && (e += sqrt(b.n)*100.0; continue)
        d = median(getindex.(Q, 2)); e += sqrt(b.n)*((d - b.dec)/0.03)^2
        verbose && @printf("   LOCKED  %3.0f-%3.0f km/h  n %4d | gold dec %.3f | sim %.3f\n", 3.6b.vlo, 3.6b.vhi, b.n, b.dec, d)
    end
    verbose && @printf("   forced lock at full pedal from 216 km/h: wheels stayed locked for %.0f %% of the stop\n", 100held)
    e
end

function main()
    B, LB = gold()
    println("gold: ", length(B), " steady pedal x speed bins, ", length(LB), " locked-slide bands")
    θ0 = [DriveRT3D_TB(), DriveRT3D_BIAS(), DriveRT3D.BRUSH_FRONT.Cκ, DriveRT3D.BRUSH_REAR.Cκ, DriveRT3D.BRUSH_FRONT.μx, DriveRT3D.BRUSH_REAR.μx, DriveRT3D.BRUSH_FRONT.rs]
    @printf("\nCURRENT  Tb %.0f split %.3f Cκ %.1f/%.1f μx %.3f/%.3f rs %.2f\n", θ0...)
    @printf("   score %.1f\n", score(B, LB, θ0; verbose = true))
    it = parse(Int, get(ENV, "JM_BRAKEFIT_ITERS", "250")); it == 0 && return θ0
    start = [3000.0, 0.62, 22.0, 22.0, 1.40, 1.40, 0.72]
    θ, e = nelder_mead(θ -> score(B, LB, θ), start; iters = it, step = 0.1)
    @printf("\nFITTED   Tb %.0f split %.3f Cκ %.1f/%.1f μx %.3f/%.3f rs %.3f   score %.1f\n", θ..., e)
    score(B, LB, θ; verbose = true)
    θ
end
DriveRT3D_TB() = ModelingToolkit.getp(SYS, SYS.Tbrake_max)(CAR.integ)
DriveRT3D_BIAS() = ModelingToolkit.getp(SYS, SYS.bias)(CAR.integ)
abspath(PROGRAM_FILE) == (@__FILE__) && main()
