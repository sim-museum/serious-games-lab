# E91-S10: refit the Lotus 49's longitudinal model from the 2026-10-02 iRacing test session -- the
# straight-line clutch-in + in-gear coast-downs E91-S3/S7/S9 asked the PO for, plus full-throttle pulls.
#
# Everything is solved IN THE SIM'S OWN EQUATION OF MOTION (DrivenVehicle3D, clutch locked, no slip):
#
#   T·gr·η/Rw_r = (m + m_w + m_e(gr))·u̇ + ½·ρ·CdA·u² + Crr·m·g + m·g·sinθ
#   m_w = 2Iw/Rw_f² + 2Iw/Rw_r²     (wheels, both directions)
#   m_e = Ie·gr²·η/Rw_r²             (engine, only with the clutch engaged)
#
# so the fitted numbers reproduce the gold when they are put back into that model, rather than
# being "true" numbers that a model with different inertias would then miss.
#   1. clutch DISENGAGED coasts  (T = 0, m_e = 0)  -> CdA, Crr          (linear least squares)
#   2. in-gear zero-throttle coasts                 -> engine drag torque vs rpm
#   3. full-throttle pulls, no wheelspin            -> WOT torque vs rpm
# iRacing Clutch: 1 = ENGAGED (E91-S8). Per-file mass (CornerWeights), per-sample AirDensity,
# per-file gearing. Points inside one coast are autocorrelated, so the CI bootstraps SEGMENTS.
#
# Run:  JM_REFDIR=".../gold standard/julia racer/261002" julia --project=. tools/longfit_261002.jl
using Printf, Statistics, Random
const T = joinpath(@__DIR__, "..")
include(joinpath(T, "src", "ibt.jl"));   using .IBT
include(joinpath(T, "src", "setup.jl")); using .Setup
include(joinpath(T, "fit", "fitutil.jl")); using .FitUtil

const G = 9.80665; const DT = 1/60
const REF = get(ENV, "JM_REFDIR", expanduser("~/gold standard/julia racer/261002"))
# WOT pulls: every iRacing capture in the store (older sessions reach higher rpm in lower gears);
# road load and engine drag come from REF alone -- the designed straight-line coast-down test.
const WOTREF = get(ENV, "JM_WOTDIR", dirname(REF))
# the sim's constants (DrivenVehicle3D defaults) -- the frame the fit is expressed in
const RW_F = 0.30; const RW_R = parse(Float64, get(ENV, "JM_FIT_RWR", "0.33"))
const IW = 1.0; const IE = 0.18; const ETA = 0.9
const M_W = 2IW/RW_F^2 + 2IW/RW_R^2
const HW = 15                                     # half-window for derivatives: ±0.25 s

ch(f, n) = try channel(f, n) catch; nothing end

# least-squares slope of y over the window k-HW..k+HW (per second)
function lslope(y, k)
    s = 0.0; for j in -HW:HW; s += j*y[k+j]; end
    s / (DT * HW*(HW+1)*(2HW+1)/3)
end

struct Pt; v::Float64; dec::Float64; rho::Float64; m::Float64; gr::Float64; rpm::Float64; gear::Int; seg::Int; file::String; end

function load(dir)
    files = String[]
    for (r,_,fs) in walkdir(dir), fn in fs
        endswith(lowercase(fn), ".ibt") && push!(files, joinpath(r, fn))
    end
    dis = Pt[]; eng = Pt[]; wot = Pt[]; seg = 0
    for p in sort(files)
        f = ibt_open(p); sp = setup_params(f.yaml)
        all(iszero, something(ch(f, "Voltage"), [0.0])) && (println("  SKIP (not iRacing-written): ", basename(p)); continue)
        m = sum(values(sp.corner_weight_N)) / 9.81          # same conversion as mass_from_corner_weights
        ratios = sp.gear_ratios .* sp.final_drive
        thr, brk, spd, gr, cl, rpm = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed"), ch(f,"Gear"), ch(f,"Clutch"), ch(f,"RPM")
        lat, alt, ad, on = ch(f,"LatAccel"), ch(f,"Alt"), ch(f,"AirDensity"), ch(f,"IsOnTrack")
        lrs, rrs, lfs, rfs = ch(f,"LRspeed"), ch(f,"RRspeed"), ch(f,"LFspeed"), ch(f,"RFspeed")
        n = f.nrows; last = (-10, :x); tag = basename(p)[9:min(end-4, 40)]
        for k in 1+2HW:n-2HW
            on[k] > 0.5 && spd[k] >= 8 || continue
            # whole window clean: steady gear, no big lateral load, no impact (|lat| spike)
            w = k-HW:k+HW
            all(j -> gr[j] == gr[k], k-2HW:k+2HW) || continue             # ±0.5 s from any shift
            latmax = maximum(j -> abs(lat[j]), w)
            latmax < 0.30G || continue
            u̇ = lslope(spd, k); ż = lslope(alt, k)
            a = u̇ + G*ż/spd[k]                     # gravity removed: m·a = ΣF_long excluding slope
            g = Int(gr[k])
            coast = all(j -> thr[j] < 0.01 && brk[j] < 0.01, w)
            if coast && latmax >= 0.10G
                continue                                                   # coasts: straight road only
            elseif coast && (all(j -> cl[j] < 0.05, w) || g == 0)
                cls = :dis
            elseif coast && all(j -> cl[j] > 0.95, w) && 1 <= g <= 5
                cls = :eng
            elseif all(j -> thr[j] > 0.98 && brk[j] < 0.01 && cl[j] > 0.95, w) && 1 <= g <= 5
                # no wheelspin: driven wheels within 5 % of the fronts over the window
                all(j -> (lrs[j]+rrs[j]) / max(lfs[j]+rfs[j], 1.0) < 1.05, w) || continue
                cls = :wot
            else
                continue
            end
            abs(a) < 12 || continue
            if last != (k-1, cls); seg += 1; end; last = (k, cls)
            grk = g >= 1 ? ratios[g] : 0.0
            pt = Pt(spd[k], -a, ad[k], m, grk, rpm[k], g, seg, tag)
            push!(cls === :dis ? dis : cls === :eng ? eng : wot, pt)
        end
    end
    dis, eng, wot
end

segs(P) = unique(p.seg for p in P)
minseg(P, nmin) = (c = Dict{Int,Int}(); for p in P; c[p.seg] = get(c, p.seg, 0) + 1; end; filter(p -> c[p.seg] >= nmin, P))

# (m+m_w)·dec = CdA·(½ρv²) + Crr·(m g)
function fit_roadload(P)
    X = hcat([0.5p.rho*p.v^2 for p in P], [p.m*G for p in P]); y = [(p.m + M_W)*p.dec for p in P]
    X \ y
end

function main()
    println("REF = ", REF, "   (sim frame: Rw_r=$RW_R Iw=$IW Ie=$IE eta=$ETA, m_w=$(round(M_W,digits=1)) kg)")
    dis, eng, _ = load(REF); _, _, wot = load(WOTREF)
    println("WOT from ", WOTREF)
    dis = minseg(dis, 60); eng = minseg(eng, 30); wot = minseg(wot, 20)   # ≥ 1 s / 0.5 s / 0.33 s runs
    @printf("points: disengaged %d (%d segs)  in-gear coast %d (%d segs)  WOT %d (%d segs)\n",
            length(dis), length(segs(dis)), length(eng), length(segs(eng)), length(wot), length(segs(wot)))

    # ---------------- 1. road load ----------------
    CdA, Crr = fit_roadload(dis)
    res = [(p.m+M_W)*p.dec - CdA*0.5p.rho*p.v^2 - Crr*p.m*G for p in dis] ./ [p.m+M_W for p in dis]
    rng = MersenneTwister(1); S = segs(dis); bs = Tuple{Float64,Float64}[]
    for _ in 1:2000
        cnt = Dict{Int,Int}(); for s in rand(rng, S, length(S)); cnt[s] = get(cnt, s, 0) + 1; end
        PP = Pt[]; for p in dis, _ in 1:get(cnt, p.seg, 0); push!(PP, p); end
        c, r = fit_roadload(PP); push!(bs, (c, r))
    end
    q(x) = (quantile(x, 0.05), quantile(x, 0.95))
    @printf("\n1. ROAD LOAD (clutch disengaged, %d pts, %.0f-%.0f km/h): CdA = %.4f m^2 (90%% CI %.4f..%.4f)   Crr = %.4f (%.4f..%.4f)   resid sd %.3f m/s^2\n",
            length(dis), 3.6minimum(p.v for p in dis), 3.6maximum(p.v for p in dis),
            CdA, q(first.(bs))..., Crr, q(last.(bs))..., std(res))
    println("   per-file residual mean (m/s^2) -- a hill/fuel/density error would show here:")
    for fn in unique(p.file for p in dis)
        ii = findall(p -> p.file == fn, dis)
        @printf("     %-34s n=%5d  mean %+.3f   v %.0f-%.0f km/h\n", fn, length(ii), mean(res[ii]),
                3.6minimum(dis[i].v for i in ii), 3.6maximum(dis[i].v for i in ii))
    end
    println("   by speed band: gold decel vs fit (m = 605, rho = 1.10):")
    for (lo, hi) in ((10,20),(20,30),(30,40),(40,50),(50,60),(60,70))
        ii = findall(p -> lo <= p.v < hi, dis); isempty(ii) && continue
        vm = mean(dis[i].v for i in ii)
        @printf("     %3.0f-%3.0f km/h  n=%5d  gold %.3f  fit %.3f\n", 3.6lo, 3.6hi, length(ii),
                mean(dis[i].dec for i in ii), mean((CdA*0.5dis[i].rho*dis[i].v^2 + Crr*dis[i].m*G)/(dis[i].m+M_W) for i in ii))
    end
    roadF(p) = CdA*0.5p.rho*p.v^2 + Crr*p.m*G

    # ---------------- 2. engine drag (in-gear coast) ----------------
    Tf(p) = RW_R/(p.gr*ETA) * ((p.m + M_W + IE*p.gr^2*ETA/RW_R^2)*p.dec - roadF(p))
    println("\n2. ENGINE DRAG TORQUE at the crank, in-gear zero-throttle coast (N·m, + = braking):")
    println("    rpm band  |  all: n  median   |  per gear median (n)")
    edges = 1000:500:9500; eb_x = Float64[]; eb_y = Float64[]; eb_w = Float64[]
    for k in 1:length(edges)-1
        ii = findall(p -> edges[k] <= p.rpm < edges[k+1], eng); length(ii) < 10 && continue
        t = [Tf(eng[i]) for i in ii]
        pg = join([(jj = filter(i -> eng[i].gear == g, ii); length(jj) >= 10 ?
                    @sprintf("g%d %.1f (%d)", g, median(Tf(eng[i]) for i in jj), length(jj)) : "") for g in 1:5], "  ")
        @printf("   %4d-%4d  | %5d  %6.1f   | %s\n", edges[k], edges[k+1], length(ii), median(t), strip(pg))
        push!(eb_x, mean(eng[i].rpm for i in ii)); push!(eb_y, median(t)); push!(eb_w, sqrt(length(ii)))
    end
    # forms: code's eb·rpm, and the standard friction-MEP form T0 + k·rpm, over rpm >= 2500 (above idle)
    sel = findall(x -> x >= 2500, eb_x)
    xw = eb_x[sel]; yw = eb_y[sel]; ww = eb_w[sel]
    k1 = sum(ww .* xw .* yw) / sum(ww .* xw.^2)
    A2 = hcat(ones(length(xw)), xw) .* ww; b2 = (A2 \ (yw .* ww))
    r1 = sqrt(sum(ww .* (yw .- k1 .* xw).^2)/sum(ww)); r2 = sqrt(sum(ww .* (yw .- b2[1] .- b2[2] .* xw).^2)/sum(ww))
    @printf("   fit eb·rpm:        eb = %.5f            bin RMS %.1f N·m   (code ENGBRAKE = 0.012)\n", k1, r1)
    @printf("   fit T0 + k·rpm:    T0 = %.2f, k = %.6f   bin RMS %.1f N·m\n", b2[1], b2[2], r2)
    # near idle the gold's drag FADES to ~0 (the idle governor fuels the engine, in gear too): fit the
    # whole curve from 1500 rpm as (T0 + k·rpm)·½(1 + tanh((rpm − r0)/w)), r0/w free, T0/k free.
    fade(r, θ) = (θ[1] + θ[2]*r) * 0.5*(1 + tanh((r - θ[3])/θ[4]))
    # finer bins where the fade lives (100 rpm, 1500-3500), the 500-rpm bins above
    eb_x = Float64[]; eb_y = Float64[]; eb_w = Float64[]
    for (lo, hi) in vcat([(r, r+100) for r in 1500:100:3400], [(r, r+500) for r in 3500:500:6000])
        ii = findall(p -> lo <= p.rpm < hi, eng); length(ii) < 10 && continue
        push!(eb_x, mean(eng[i].rpm for i in ii)); push!(eb_y, median(Tf(eng[i]) for i in ii)); push!(eb_w, sqrt(length(ii)))
    end
    lf(θ) = (θ[4] < 50 || θ[4] > 2000) ? 1e12 : sum(eb_w[i]*(fade(eb_x[i], θ) - eb_y[i])^2 for i in eachindex(eb_x))
    θf, _ = nelder_mead(lf, [b2[1], b2[2], 2200.0, 300.0]; iters = 6000)
    @printf("   fit with idle fade (all bins >= 1500 rpm): T0 = %.2f, k = %.6f, r0 = %.0f rpm, w = %.0f rpm   bin RMS %.1f N·m\n",
            θf..., sqrt(lf(θf)/sum(eb_w)))
    for i in eachindex(eb_x); @printf("      %5.0f rpm  gold %6.1f   fade-fit %6.1f   line %6.1f\n", eb_x[i], eb_y[i], fade(eb_x[i], θf), b2[1]+b2[2]*eb_x[i]); end

    # ---------------- 3. WOT torque ----------------
    Tw(p) = RW_R/(p.gr*ETA) * ((p.m + M_W + IE*p.gr^2*ETA/RW_R^2)*(-p.dec) + roadF(p))
    println("\n3. WOT NET TORQUE at the crank (N·m):  rpm band | n | median | per gear")
    bx = Float64[]; by = Float64[]; bw = Float64[]
    for k in 1:length(edges)-1
        ii = findall(p -> edges[k] <= p.rpm < edges[k+1], wot); length(ii) < 8 && continue
        t = [Tw(wot[i]) for i in ii]
        pg = join([(jj = filter(i -> wot[i].gear == g, ii); length(jj) >= 8 ?
                    @sprintf("g%d %.0f (%d)", g, median(Tw(wot[i]) for i in jj), length(jj)) : "") for g in 1:5], "  ")
        @printf("   %4d-%4d | %4d | %5.1f | %s\n", edges[k], edges[k+1], length(ii), median(t), strip(pg))
        push!(bx, mean(wot[i].rpm for i in ii)); push!(by, median(t)); push!(bw, sqrt(length(ii)))
    end
    shape(r, Tp, rp, sp) = Tp*max(0.2, 1 - ((r - rp)/sp)^2)
    loss(θ) = (θ[1] < 100 || θ[1] > 600 || θ[2] < 6000 || θ[2] > 9500 || θ[3] < 2000 || θ[3] > 12000) ? 1e12 :
              sum(bw[k]*(shape(bx[k], θ...) - by[k])^2 for k in eachindex(bx))
    θ, _ = nelder_mead(loss, [300.0, 8000.0, 6000.0]; iters = 4000)
    rmsw = sqrt(loss(θ)/sum(bw))
    @printf("   fit Tpeak*max(0.2,1-((rpm-rpm_peak)/spread)^2): Tpeak=%.1f rpm_peak=%.0f spread=%.0f  bin RMS %.1f N·m\n", θ..., rmsw)
    @printf("   (code: Tpeak=409 rpm_peak=8211 spread=6000 -> %.0f N·m at 6000 rpm vs fit %.0f)\n",
            shape(6000.0, 409.0, 8211.0, 6000.0), shape(6000.0, θ...))
    @printf("   data reach: %.0f-%.0f rpm; peak power of the fit %.0f kW (%.0f hp) at %.0f rpm\n", minimum(bx), maximum(bx),
            maximum(shape(r, θ...)*r*2π/60 for r in 3000:50:9500)/1e3, maximum(shape(r, θ...)*r*2π/60 for r in 3000:50:9500)/745.7,
            argmax(r -> shape(r, θ...)*r*2π/60, 3000:50:9500))
    # ---- top speed this implies (5th, Ring gearing 0.846*4.22) ----
    for (lab, gr5, ρ, m) in (("Ring 5th 0.846x4.22", 0.846*4.22, 1.099, 605.1), ("Charlotte 5th 0.916x4.11", 0.916*4.11, 1.148, 628.8))
        vt = 0.0
        for v in 30:0.05:110
            r = v/RW_R*gr5*60/(2π)
            r > 9500 && break
            F = shape(r, θ...)*gr5*ETA/RW_R - CdA*0.5ρ*v^2 - Crr*m*G
            F > 0 && (vt = v)
        end
        @printf("   top speed %-26s %.1f km/h (%.1f mph)%s\n", lab, 3.6vt, 2.23694vt, vt/RW_R*gr5*60/(2π) > 9450 ? "  -- rev-limited" : "")
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
