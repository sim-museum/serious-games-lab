# IRFIT-261004 (torque): WOT torque to the 9,500 rpm limiter from the PO's 2026-10-04 3rd/4th-gear pulls
# (test 4, `gold standard/julia racer/261004/... 14-04-29.ibt`), plus every earlier capture in the store.
#
# longfit_261002.jl rejected any WOT sample with > 5 % rear wheelspin, so its torque stopped at 7,775 rpm.
# The 261004 pulls run 4-13 % rear slip the whole way (3rd gear, 6000-9350 rpm). Wheelspin does not break
# the force balance; it only breaks the assumption that the rotating parts accelerate with the BODY. Here the
# engine and rear wheels accelerate at the MEASURED rpm slope, so a slipping sample is as good as a gripping one:
#
#   T = Ie·ω̇e + [ 2Iw·ω̇e/gr + Rw_r·( (m + 2Iw/Rw_f²)·a + ½ρ·CdA·v² + Crr·m·g ) ] / (gr·η)
#
# (crank torque, sim frame: Iw 1.0, Ie 0.18, η 0.9, Rw_r 0.334; a has gravity removed via Alt.)
# CdA / Crr are the shipped E91-S10 values (powertrain.jl), not refitted here.
#
# Run:  julia --project=. tools/torquefit_261004.jl
using Printf, Statistics
const T = joinpath(@__DIR__, "..")
include(joinpath(T, "src", "ibt.jl"));   using .IBT
include(joinpath(T, "src", "setup.jl")); using .Setup
include(joinpath(T, "fit", "fitutil.jl")); using .FitUtil

const G = 9.80665; const DT = 1/60
const STORE = get(ENV, "JM_WOTDIR", expanduser("~/gold standard/julia racer"))
const RW_F = 0.30; const RW_R = 0.334; const IW = 1.0; const IE = 0.18; const ETA = 0.9
const CDA = 0.480; const CRR = 0.0139                       # powertrain.jl CDA_IBT / CRR_IBT
const HW = 15
ch(f, n) = try channel(f, n) catch; nothing end
lslope(y, k) = (s = 0.0; for j in -HW:HW; s += j*y[k+j]; end; s / (DT * HW*(HW+1)*(2HW+1)/3))

struct W; rpm::Float64; T::Float64; Tbody::Float64; gear::Int; spin::Float64; file::String; end

function load(dir)
    files = String[]
    for (r,_,fs) in walkdir(dir), fn in fs
        endswith(lowercase(fn), ".ibt") && push!(files, joinpath(r, fn))
    end
    out = W[]
    for p in sort(files)
        f = ibt_open(p); sp = setup_params(f.yaml)
        all(iszero, something(ch(f, "Voltage"), [0.0])) && continue      # not iRacing-written (our own export)
        m = sum(values(sp.corner_weight_N)) / 9.81
        ratios = sp.gear_ratios .* sp.final_drive
        thr, brk, spd, gr, cl, rpm = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed"), ch(f,"Gear"), ch(f,"Clutch"), ch(f,"RPM")
        lat, alt, ad, on = ch(f,"LatAccel"), ch(f,"Alt"), ch(f,"AirDensity"), ch(f,"IsOnTrack")
        lrs, rrs, lfs, rfs = ch(f,"LRspeed"), ch(f,"RRspeed"), ch(f,"LFspeed"), ch(f,"RFspeed")
        tag = basename(p)[9:min(end-4, 52)]
        for k in 1+2HW:f.nrows-2HW
            on[k] > 0.5 && spd[k] >= 15 || continue
            w = k-HW:k+HW
            all(j -> gr[j] == gr[k], k-2HW:k+2HW) || continue
            g = Int(gr[k]); 3 <= g <= 5 || continue
            maximum(j -> abs(lat[j]), w) < 0.30G || continue
            all(j -> thr[j] > 0.98 && brk[j] < 0.01 && cl[j] > 0.95, w) || continue
            rpm[k] < 9400 || continue                                     # off the limiter's fuel cut
            spin = (lrs[k]+rrs[k]) / max(lfs[k]+rfs[k], 1.0)
            spin < 1.20 || continue                                       # a burnout, not a pull
            a = lslope(spd, k) + G*lslope(alt, k)/spd[k]
            ωė = lslope(rpm, k) * 2π/60
            grk = ratios[g]
            road = 0.5*ad[k]*CDA*spd[k]^2 + CRR*m*G
            Tq = IE*ωė + (2IW*ωė/grk + RW_R*((m + 2IW/RW_F^2)*a + road)) / (grk*ETA)
            # the longfit_261002 form (rotating parts follow the body) -- shows what the slip costs
            Tb = RW_R/(grk*ETA) * ((m + 2IW/RW_F^2 + 2IW/RW_R^2 + IE*grk^2*ETA/RW_R^2)*a + road)
            abs(a) < 12 && push!(out, W(rpm[k], Tq, Tb, g, spin, tag))
        end
    end
    out
end

shape(r, Tp, rp, sp) = Tp*max(0.2, 1 - ((r - rp)/sp)^2)

function main()
    P = load(STORE)
    @printf("WOT samples, gears 3-5, all iRacing captures under %s: %d\n", STORE, length(P))
    edges = 3500:250:9500; bx = Float64[]; by = Float64[]; bw = Float64[]
    println("   rpm band   |   n  | T median (sd) | per gear median (n)                  | old form | rear spin")
    for k in 1:length(edges)-1
        ii = findall(p -> edges[k] <= p.rpm < edges[k+1], P); length(ii) < 8 && continue
        t = [P[i].T for i in ii]
        pg = join([(jj = filter(i -> P[i].gear == g, ii); length(jj) >= 8 ?
                    @sprintf("g%d %.0f (%d)", g, median(P[i].T for i in jj), length(jj)) : "") for g in 3:5], "  ")
        @printf("   %4d-%4d  | %4d | %5.1f (%4.1f)  | %-36s | %6.1f   | %.3f\n", edges[k], edges[k+1], length(ii),
                median(t), std(t), strip(pg), median(P[i].Tbody for i in ii), median(P[i].spin for i in ii))
        push!(bx, mean(P[i].rpm for i in ii)); push!(by, median(t)); push!(bw, sqrt(length(ii)))
    end
    loss(θ) = (θ[1] < 100 || θ[1] > 600 || θ[2] < 6000 || θ[2] > 12000 || θ[3] < 2000 || θ[3] > 15000) ? 1e12 :
              sum(bw[k]*(shape(bx[k], θ...) - by[k])^2 for k in eachindex(bx))
    θ, _ = nelder_mead(loss, [310.0, 8000.0, 7000.0]; iters = 6000)
    @printf("\nfit Tpeak·max(0.2, 1-((rpm-rpm_peak)/spread)^2): Tpeak %.1f  rpm_peak %.0f  spread %.0f   bin RMS %.1f N·m\n",
            θ..., sqrt(loss(θ)/sum(bw)))
    @printf("   shipped (E91-S10) Tpeak 310 @ 7727, spread 6742:  at 9000 rpm %.0f N·m vs fit %.0f;  at 9400 %.0f vs %.0f\n",
            shape(9000.0, 310.0, 7727.0, 6742.0), shape(9000.0, θ...), shape(9400.0, 310.0, 7727.0, 6742.0), shape(9400.0, θ...))
    @printf("   data reach %.0f-%.0f rpm; fit peak power %.0f kW (%.0f hp) at %.0f rpm\n", minimum(bx), maximum(bx),
            maximum(shape(r, θ...)*r*2π/60 for r in 3000:50:9500)/1e3, maximum(shape(r, θ...)*r*2π/60 for r in 3000:50:9500)/745.7,
            argmax(r -> shape(r, θ...)*r*2π/60, 3000:50:9500))
    println("   residual by band (gold - fit):")
    for k in eachindex(bx); @printf("      %5.0f rpm  gold %6.1f  fit %6.1f  %+5.1f\n", bx[k], by[k], shape(bx[k], θ...), by[k] - shape(bx[k], θ...)); end
    θ
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
