# WWSETUP-1: the gold's A/B between the iRacing default setup and WW103 "fast loose" (PO session 2026-10-05).
#
# GOLD ONLY -- nothing here touches the sim. Every Centripetal file of 261004 and 261005 is classified by the
# setup embedded in it (front spring 30 N/mm = default `261004_skidpad`, 18 N/mm = `261005_jr_ww103`), so the
# 261005 default run (00-38-20, the B4 A/B half) lands on the default side automatically.
#
#   A. BALANCE (B1): median front and rear axle slip per 0.1 g band on the steady samples, exactly the TYRE-1
#      extractor (tyrefit_261002.jl): a loose car carries more rear slip at the same g.
#   B. ROLL (B1): roll angle per axle from the shock deflections -- (d_L - d_R)/MR/track -- regressed on
#      lateral g. Both axles of a stiff chassis roll alike; the GRADIENT says how stiff the car is in roll.
#      Pressure asymmetry (152 L / 207 R at Centripetal) is the same in both setups, so it cancels in the A/B.
#
#   julia --project=. tools/wwab_261005.jl
using Printf, Statistics
include(joinpath(@__DIR__, "tyrefit_261002.jl"))             # IBT, Setup, ch, lslope, HW, G, LWB

const D4 = expanduser("~/gold standard/julia racer/261004")
const D5 = expanduser("~/gold standard/julia racer/261005")
const MRF = 0.78; const MRR = 0.648                           # shock/wheel motion ratios (IRFIT-261004 SUSP-1)
const TRK = 1.50                                              # track, as DrivenVehicle3D

setupof(f) = (sp = setup_params(f.yaml); sp.spring_rate_Npmm[:LF] < 24 ? :ww : :default)

"""Steady samples of one file: (v, ay_signed_abs, αf, αr, φf, φr, thr) with the TYRE-1 filter (any power state)."""
function steady(fn)
    f = ibt_open(fn); sp = setup_params(f.yaml)
    cw = sp.corner_weight_N; ff = (cw[:LF] + cw[:RF]) / sum(values(cw)); a = (1 - ff)*LWB; b = ff*LWB
    sr = sp.steering_ratio
    c = Dict(n => ch(f, n) for n in ("Speed","VelocityX","VelocityY","YawRate","LatAccel","LongAccel","SteeringWheelAngle",
                                     "Throttle","Brake","IsOnTrack","LFshockDefl","RFshockDefl","LRshockDefl","RRshockDefl"))
    spd, vx, vy, yr, lat = c["Speed"], c["VelocityX"], c["VelocityY"], c["YawRate"], c["LatAccel"]
    stw, thr, brk = c["SteeringWheelAngle"], c["Throttle"], c["Brake"]
    out = NamedTuple[]
    for k in 1+2HW:f.nrows-2HW
        c["IsOnTrack"][k] > 0.5 && spd[k] > 8 && vx[k] > 5 || continue
        w = k-HW:k+HW
        abs(lslope(yr, k)) < 0.15 && abs(lslope(stw, k)) < 0.10 && abs(lslope(lat, k)) < 1.5 || continue
        maximum(j -> abs(lat[j]), w) < 1.35G || continue
        abs(atan(vy[k], vx[k])) < deg2rad(15) || continue
        all(j -> brk[j] < 0.01, w) && abs(c["LongAccel"][k]) < 0.15G || continue
        δ = stw[k]/sr
        αf = δ - atan(vy[k] + a*yr[k], vx[k]); αr = -atan(vy[k] - b*yr[k], vx[k])
        s = sign(lat[k]); s == 0 && continue
        φf = (c["LFshockDefl"][k] - c["RFshockDefl"][k]) / MRF / TRK
        φr = (c["LRshockDefl"][k] - c["RRshockDefl"][k]) / MRR / TRK
        push!(out, (v = spd[k], ay = lat[k], g = s*lat[k]/G, αf = s*αf, αr = s*αr, φf = φf, φr = φr,
                    thr = thr[k], dir = Int(s)))
    end
    out
end

function main()
    S = Dict(:default => NamedTuple[], :ww => NamedTuple[])
    for d in (D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        f = ibt_open(fn); k = setupof(f); P = steady(fn)
        @printf("  %-8s %-46s %6d steady\n", k, basename(fn), length(P))
        append!(S[k], P)
    end
    println("\nA. BALANCE: median axle slip (deg) per lateral-g band, steady samples, both directions")
    println("   g band  |  default n  front  rear  f-r | WW n   front  rear  f-r | Δrear (WW-def)")
    for g0 in 0.3:0.1:1.1
        r = Dict(k => [p for p in S[k] if g0 <= p.g < g0 + 0.1] for k in keys(S))
        (length(r[:default]) >= 30 && length(r[:ww]) >= 30) || continue
        m(k, f) = rad2deg(median(getproperty(p, f) for p in r[k]))
        @printf("   %.1f-%.1f | %6d %6.2f %5.2f %5.2f | %5d %6.2f %5.2f %5.2f | %+5.2f\n", g0, g0 + 0.1,
                length(r[:default]), m(:default,:αf), m(:default,:αr), m(:default,:αf) - m(:default,:αr),
                length(r[:ww]), m(:ww,:αf), m(:ww,:αr), m(:ww,:αf) - m(:ww,:αr), m(:ww,:αr) - m(:default,:αr))
    end
    println("\n   by direction (lateral g sign), 0.7-1.1 g:")
    for k in (:default, :ww), dir in (1, -1)
        ii = [p for p in S[k] if p.dir == dir && 0.7 <= p.g < 1.1]; length(ii) < 20 && continue
        @printf("   %-8s dir %+d  n %5d  g %.2f  front %.2f  rear %.2f  f-r %.2f\n", k, dir, length(ii), mean(p.g for p in ii),
                rad2deg(median(p.αf for p in ii)), rad2deg(median(p.αr for p in ii)),
                rad2deg(median(p.αf - p.αr for p in ii)))
    end
    println("\nB. ROLL: axle roll angle (deg) per g from the shock deflections, slope of φ on ay/g (with intercept)")
    for k in (:default, :ww)
        P = [p for p in S[k] if p.g > 0.3]
        X = hcat([p.ay/G for p in P], ones(length(P)))
        bf = X \ [rad2deg(p.φf) for p in P]; br = X \ [rad2deg(p.φr) for p in P]
        @printf("   %-8s n %6d   front %.3f deg/g   rear %.3f deg/g   (front/rear %.2f)\n", k, length(P), bf[1], br[1], bf[1]/br[1])
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
