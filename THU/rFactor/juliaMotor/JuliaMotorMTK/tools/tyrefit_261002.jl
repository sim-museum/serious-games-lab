# TYRE-1 (2026-10-03): the Lotus 49's tyre, identified from the 2026-10-02 iRacing session.
#
# Three measurements, all from the gold, none from the sim:
#   A. per-axle slip angle vs lateral grip (the cornering curve) -- αf, αr from the car-frame velocity,
#      yaw rate and steering (as fit/validate_brush.jl), normalised grip = |LatAccel|/g, which is each
#      axle's Fy / static axle load exactly in steady state (no yaw acceleration);
#   B. the SCRUB: extra speed loss while cornering, from zero-throttle coasts, after the straight-line
#      road load (and engine drag, in gear) fitted by tools/longfit_261002.jl is removed;
#   C. the test of the PO's "the tyre ablates" (Kaemmer): a brush-type tyre can only take energy out of
#      the car through its slip, so its scrub MUST equal Σ|Fy_i|·sin|α_i| / m_eff computed from the
#      gold's own slip angles. Measured scrub > that projection => iRacing's tyre dissipates more than
#      its lateral force accounts for, and the sim needs a slip-dependent loss term the brush lacks.
#
# Run:  julia --project=. tools/tyrefit_261002.jl
using Printf, Statistics
include(joinpath(@__DIR__, "longfit_261002.jl"))          # IBT, Setup, REF, constants, lslope, HW, G, DT
include(joinpath(@__DIR__, "..", "src", "components", "brush_tyre.jl"))

const LWB = 2.41                                           # wheelbase, as DrivenVehicle3D (a + b)
const CDA = 0.480; const CRR = 0.0139                      # E91-S10 (powertrain.jl)
efric(r) = (14.24 + 0.00389r) * 0.5*(1 + tanh((r - 2353)/351))

struct TP; v; ay; αf; αr; dec; kind; m; gr; rpm; rho; ff; file; end   # kind: :dis / :eng / :drive

function loadtyre(dir)
    out = TP[]
    for (r, _, fs) in walkdir(dir), fn in sort(fs)
        endswith(lowercase(fn), ".ibt") || continue
        f = ibt_open(joinpath(r, fn)); sp = setup_params(f.yaml)
        all(iszero, something(ch(f, "Voltage"), [0.0])) && continue
        cw = sp.corner_weight_N; m = sum(values(cw))/9.81
        ff = (cw[:LF] + cw[:RF]) / sum(values(cw)); a = (1 - ff)*LWB; b = ff*LWB
        sr = sp.steering_ratio; ratios = sp.gear_ratios .* sp.final_drive
        c = Dict(n => ch(f, n) for n in ("Speed","VelocityX","VelocityY","YawRate","LatAccel","LongAccel","SteeringWheelAngle",
                                         "Throttle","Brake","Clutch","Gear","RPM","Alt","AirDensity","IsOnTrack",
                                         "LFspeed","RFspeed","LRspeed","RRspeed"))
        spd, vx, vy, yr, lat = c["Speed"], c["VelocityX"], c["VelocityY"], c["YawRate"], c["LatAccel"]
        stw, thr, brk, cl, gr = c["SteeringWheelAngle"], c["Throttle"], c["Brake"], c["Clutch"], c["Gear"]
        tag = fn[9:min(end-4, 40)]
        for k in 1+2HW:f.nrows-2HW
            c["IsOnTrack"][k] > 0.5 && spd[k] > 8 && vx[k] > 5 || continue
            w = k-HW:k+HW
            # steady: yaw acceleration, steering rate and lateral jerk all small over the window
            abs(lslope(yr, k)) < 0.15 && abs(lslope(stw, k)) < 0.10 && abs(lslope(lat, k)) < 1.5 || continue
            maximum(j -> abs(lat[j]), w) < 1.35G || continue                 # slides/impacts out
            abs(atan(vy[k], vx[k])) < deg2rad(15) || continue
            δ = stw[k]/sr
            αf = δ - atan(vy[k] + a*yr[k], vx[k]); αr = -atan(vy[k] - b*yr[k], vx[k])
            s = sign(lat[k]); s == 0 && continue
            g = Int(gr[k])
            all(j -> gr[j] == g, k-2HW:k+2HW) || continue
            coast = all(j -> thr[j] < 0.01 && brk[j] < 0.01, w)
            kind = coast && (all(j -> cl[j] < 0.05, w) || g == 0) ? :dis :
                   coast && all(j -> cl[j] > 0.95, w) && g >= 1 ? :eng :
                   all(j -> brk[j] < 0.01 && cl[j] > 0.95, w) && abs(c["LongAccel"][k]) < 0.15G ? :drive : :none
            kind === :none && continue
            dec = -(lslope(spd, k) + G*lslope(c["Alt"], k)/spd[k])
            push!(out, TP(spd[k], s*lat[k], s*αf, s*αr, dec, kind, m, g >= 1 ? ratios[g] : 0.0, c["RPM"][k], c["AirDensity"][k], ff, tag))
        end
    end
    out
end

function main()
    P = loadtyre(REF)
    @printf("steady samples: %d  (clutch-in coast %d, in-gear coast %d, light-throttle %d)\n", length(P),
            count(p -> p.kind === :dis, P), count(p -> p.kind === :eng, P), count(p -> p.kind === :drive, P))
    # orientation sanity: slip must carry the sign of the lateral force
    @printf("orientation: front slip same sign as ay in %.1f %%, rear %.1f %% (|ay| > 3 m/s^2)\n",
            100mean(p.αf > 0 for p in P if p.ay > 3), 100mean(p.αr > 0 for p in P if p.ay > 3))

    # ---------- A. cornering curve per axle ----------
    println("\nA. CORNERING CURVE: median slip angle (deg) per lateral-g band, all steady samples")
    println("   g band    |    n  |  front α  rear α | brush now: front  rear")
    bands = 0.1:0.1:1.3
    for k in 1:length(bands)-1
        ii = [p for p in P if bands[k] <= p.ay/G < bands[k+1]]; length(ii) < 20 && continue
        gm = mean(p.ay for p in ii)/G
        ainv(par) = (μ = brush_mu(1.0, par.μ, 0.0, 1.0); x = gm/μ; x >= 1 ? NaN :
                    rad2deg(asin(clamp(3μ*(1 - cbrt(1 - x))/par.Cα, 0, 1))))
        @printf("   %.1f-%.1f   | %5d | %6.2f  %6.2f    |  %6.2f  %6.2f\n", bands[k], bands[k+1], length(ii),
                rad2deg(median(p.αf for p in ii)), rad2deg(median(p.αr for p in ii)), ainv(BRUSH_FRONT), ainv(BRUSH_REAR))
    end
    # brush fit per axle: grip(α) = μ·sat(Cα·sinα/(3μ)), least squares on α-binned medians
    function curve(αs, gs)
        e = range(0, deg2rad(12); length = 25); bx = Float64[]; by = Float64[]; bw = Float64[]
        for k in 1:24
            ii = findall(a -> e[k] <= a < e[k+1], αs); length(ii) < 20 && continue
            push!(bx, median(αs[ii])); push!(by, median(gs[ii])); push!(bw, sqrt(length(ii)))
        end
        bx, by, bw
    end
    fits = Dict{Symbol,Tuple{Float64,Float64,Float64}}()
    for (nm, αs) in ((:front, [p.αf for p in P]), (:rear, [p.αr for p in P]))
        gs = [p.ay/G for p in P]
        bx, by, bw = curve(αs, gs)
        best = (Inf, 0.0, 0.0)
        for μ in 1.00:0.005:1.60, Cα in 8.0:0.25:40.0
            e = sum(bw[i]*(μ*brush_sat(Cα*sin(bx[i])/(3μ)) - by[i])^2 for i in eachindex(bx))
            e < best[1] && (best = (e, μ, Cα))
        end
        fits[nm] = (best[2], best[3], sqrt(best[1]/sum(bw)))
        @printf("\n   %s axle brush fit: μ = %.3f  Cα = %.2f /rad   (bin RMS %.3f g, %d bins to %.1f°; data reach %.2f g)\n",
                uppercase(string(nm)), best[2], best[3], sqrt(best[1]/sum(bw)), length(bx), rad2deg(maximum(bx)), maximum(by))
        for i in eachindex(bx)
            @printf("      %5.2f°  gold %.3f g   fit %.3f   brush-now %.3f\n", rad2deg(bx[i]), by[i],
                    best[2]*brush_sat(best[3]*sin(bx[i])/(3best[2])), brush_fy(1.0, bx[i]; p = nm === :front ?
                    merge(BRUSH_FRONT, (kμ = 0.0, Fz0 = 1.0)) : merge(BRUSH_REAR, (kμ = 0.0, Fz0 = 1.0))))
        end
    end

    # ---------- B + C. scrub ----------
    println("\nB/C. SCRUB in zero-throttle coasts: measured extra decel vs the brush projection Σ|Fy|·sin|α|/m_eff (m/s^2)")
    println("   kind  g band   |    n  mean km/h | measured  projection  meas/proj")
    for kind in (:dis, :eng)
        for k in 1:length(bands)-1
            ii = [p for p in P if p.kind === kind && bands[k] <= p.ay/G < bands[k+1]]; length(ii) < 30 && continue
            meas = Float64[]; proj = Float64[]
            for p in ii
                me = kind === :dis ? p.m + M_W : p.m + M_W + IE*p.gr^2*ETA/RW_R^2
                road = CDA*0.5p.rho*p.v^2 + CRR*p.m*G + (kind === :eng ? efric(p.rpm)*p.gr*ETA/RW_R : 0.0)
                push!(meas, p.dec - road/me)
                # steady axle forces: Fyf = m·ay·b/L, Fyr = m·ay·a/L; b/L = front share ff
                push!(proj, p.m*p.ay*(p.ff*sin(abs(p.αf)) + (1 - p.ff)*sin(abs(p.αr))) / me)
            end
            @printf("   %-4s  %.1f-%.1f  | %5d   %5.0f   |  %6.3f    %6.3f     %5.2f\n", kind, bands[k], bands[k+1], length(ii),
                    3.6mean(p.v for p in ii), median(meas), median(proj), median(meas)/median(proj))
        end
    end
    fits
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
