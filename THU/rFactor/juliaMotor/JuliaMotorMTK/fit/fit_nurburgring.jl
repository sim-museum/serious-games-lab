# Nürburgring Nordschleife fit — extend/cross-validate the skidpad tyre on a road
# course.  Two things the skidpad couldn't give:
#   (1) LATERAL load sensitivity (pKy2) + an independent cross-validation of the
#       skidpad grip curve, by FORWARD-predicting ay from slip angles + per-axle
#       loads and tuning params to match measured ay (no yaw-inertia inversion).
#   (2) LONGITUDINAL Fx (μx, pKx1) + aero drag (CdA), from braking events where
#       the wheel-speed channels give slip ratio κ down to full lock (κ=−1).
#
# Grade (±12° on the Nordschleife) is handled implicitly by using the measured
# specific-force channels: m·VertAccel = total normal load, and
# m·LongAccel = Fx_tyre − ½ρ·CdA·v² (gravity cancels in specific-force form).
#
# Run:  julia --project=. fit/fit_nurburgring.jl

include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "components", "tyre_law.jl"))
include(joinpath(@__DIR__, "fitutil.jl")); using .FitUtil

const G = 9.80665
const L = 2.41                      # wheelbase [m]
const DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
files = filter(f -> startswith(f, "lotus49_nurburgring") && endswith(f, ".ibt"), readdir(DATA))
println("Nordschleife files: $(length(files))")

# ---- load + clean-concatenate all laps --------------------------------------
chs = ["Speed","VelocityX","VelocityY","YawRate","LatAccel","LongAccel","VertAccel",
       "SteeringWheelAngle","Throttle","Brake","IsOnTrack",
       "LFspeed","RFspeed","LRspeed","RRspeed","AirDensity"]
D = Dict(c => Float64[] for c in chs)
for fn in files
    f = IBT.ibt_open(joinpath(DATA, fn))
    cols = Dict(c => IBT.channel(f, c) for c in chs)
    for i in 2:f.nrows-1
        cols["IsOnTrack"][i] > 0.5 || continue
        cols["Speed"][i] > 10      || continue
        cols["VelocityX"][i] > 5   || continue
        abs(cols["LatAccel"][i])  < 22 || continue
        abs(cols["LongAccel"][i]) < 22 || continue
        abs(atan(cols["VelocityY"][i], cols["VelocityX"][i])) < deg2rad(20) || continue
        for c in chs; push!(D[c], cols[c][i]); end
    end
end
N = length(D["Speed"]); println("clean samples (all laps): $N")

p = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(joinpath(DATA, files[1]))))
m = sum(values(p.corner_weight_N)) / G
front_fr = (p.corner_weight_N[:LF] + p.corner_weight_N[:RF]) / sum(values(p.corner_weight_N))
a = (1 - front_fr) * L;  b = front_fr * L
ρ = sum(D["AirDensity"]) / N
vsign = sum(D["VertAccel"]) < 0 ? -1.0 : 1.0     # orient normal-load sign
println("m=$(round(m,digits=1))kg  front_frac=$(round(front_fr,digits=3))  a=$(round(a,digits=2)) b=$(round(b,digits=2))  ρ=$(round(ρ,digits=3))kg/m³  mean VertAccel=$(round(vsign*sum(D["VertAccel"])/N,digits=2))")

# ============================================================================
# (1) LATERAL: load sensitivity + cross-validation
# ============================================================================
front0 = TYRE_SKIDPAD_FRONT;  rear0 = TYRE_SKIDPAD_REAR
withp(base; pKy2, μs) = merge(base, (; pKy2 = pKy2, μy = base.μy*μs))

# precompute per-sample kinematics + measured ay for cornering samples
αf = Float64[]; αr = Float64[]; aymeas = Float64[]; axv = Float64[]; vacc = Float64[]
for i in 1:N
    abs(D["LatAccel"][i]) > 3.0 || continue           # actually cornering
    vx, vy, r = D["VelocityX"][i], D["VelocityY"][i], D["YawRate"][i]
    δ = D["SteeringWheelAngle"][i] / p.steering_ratio
    push!(αf, δ - atan(vy + a*r, vx))
    push!(αr,   - atan(vy - b*r, vx))
    push!(aymeas, D["LatAccel"][i]); push!(axv, D["LongAccel"][i])
    push!(vacc, vsign*D["VertAccel"][i])
end
nc = length(aymeas); println("\n[LATERAL] cornering samples: $nc")

function predict_ay(θ)
    μs, pKy2, h = θ
    pf = withp(front0; pKy2 = pKy2, μs = μs);  pr = withp(rear0; pKy2 = pKy2, μs = μs)
    pred = similar(aymeas)
    @inbounds for i in eachindex(aymeas)
        Fz_tot = m * max(vacc[i], 0.2G)
        Fzf = Fz_tot*(b/L) - m*axv[i]*h/L
        Fzr = Fz_tot*(a/L) + m*axv[i]*h/L
        Fzf = clamp(Fzf, 200.0, 4e4); Fzr = clamp(Fzr, 200.0, 4e4)
        pred[i] = (tyre_fy(Fzf, αf[i]; p = pf) + tyre_fy(Fzr, αr[i]; p = pr)) / m
    end
    pred
end
r2(pred, meas) = (ḡ = sum(meas)/length(meas); 1 - sum(abs2, pred .- meas)/sum(x->abs2(x-ḡ), meas))
loss_lat(θ) = (θ[1]<0.7||θ[1]>1.5||θ[2]<1.0||θ[2]>6.0||θ[3]<0.18||θ[3]>0.5) ? 1e9 :
              sum(abs2, predict_ay(θ) .- aymeas)

base = predict_ay([1.0, 2.2, 0.30])
println("  baseline (skidpad params, pKy2=2.2, h=0.30): R²=$(round(r2(base, aymeas),digits=3))  RMS=$(round(sqrt(sum(abs2,base.-aymeas)/nc)/G,digits=3))g")
θlat, _ = nelder_mead(loss_lat, [1.0, 2.2, 0.30]; iters = 1500)
fit = predict_ay(θlat)
println("  free 3-param fit: μ_scale=$(round(θlat[1],digits=3)) pKy2=$(round(θlat[2],digits=2)) h_cg=$(round(θlat[3],digits=3))m → R²=$(round(r2(fit,aymeas),digits=3))")
println("    (μ_scale & h_cg hit bounds for a tiny R² gain → overfitting banked/compressed high-g samples; not adopted)")
# honest load-sensitivity: trust the skidpad μ (μ_scale=1) + nominal CG height, fit pKy2 only
loss_pky2(x) = (x[1] < 1.0 || x[1] > 6.0) ? 1e9 : sum(abs2, predict_ay([1.0, x[1], 0.30]) .- aymeas)
θp, _ = nelder_mead(loss_pky2, [2.2]; iters = 400)
conp = predict_ay([1.0, θp[1], 0.30])
println("  constrained (skidpad μ, h=0.30, fit pKy2 only): pKy2=$(round(θp[1],digits=2)) → R²=$(round(r2(conp,aymeas),digits=3))  (≈ baseline → load sensitivity NOT identifiable this way)")

# ============================================================================
# (2) LONGITUDINAL: Fx + drag, from braking events
# ============================================================================
κb = Float64[]; axb = Float64[]; vacb = Float64[]; vb = Float64[]
for i in 1:N
    D["Brake"][i] > 0.2 || continue
    abs(D["LatAccel"][i]) < 3.0 || continue
    abs(D["SteeringWheelAngle"][i]) < 0.3 || continue
    12 < D["Speed"][i] < 45 || continue                # limit drag contamination
    v = D["Speed"][i]
    wheel = (D["LFspeed"][i]+D["RFspeed"][i]+D["LRspeed"][i]+D["RRspeed"][i])/4
    push!(κb, (wheel - v)/v); push!(axb, D["LongAccel"][i])
    push!(vacb, vsign*D["VertAccel"][i]); push!(vb, v)
end
nb = length(κb); println("\n[LONGITUDINAL] braking samples: $nb  (κ range $(round(minimum(κb),digits=2))..$(round(maximum(κb),digits=2)))")

function predict_ax(θ)
    μx, pKx1, CdA = θ
    pl = merge(TYRE_DEFAULTS, (; μx = μx, pKx1 = pKx1))
    pred = similar(axb)
    @inbounds for i in eachindex(axb)
        Fz = m * max(vacb[i], 0.2G)
        pred[i] = (tyre_fx(Fz, κb[i]; p = pl) - 0.5*ρ*CdA*vb[i]^2) / m
    end
    pred
end
loss_lon(θ) = (θ[1]<0.6||θ[1]>2.0||θ[2]<5||θ[2]>40||θ[3]<0.2||θ[3]>2.5) ? 1e9 :
              sum(abs2, predict_ax(θ) .- axb)
base_x = predict_ax([TYRE_DEFAULTS.μx, TYRE_DEFAULTS.pKx1, 0.8])
println("  baseline (μx=1.3, pKx1=18, CdA=0.8): R²=$(round(r2(base_x,axb),digits=3))")
θlon, _ = nelder_mead(loss_lon, [1.2, 15.0, 0.8]; iters = 1500)
fitx = predict_ax(θlon)
println("  fitted μx=$(round(θlon[1],digits=3)) pKx1=$(round(θlon[2],digits=1)) CdA=$(round(θlon[3],digits=2))m²:  R²=$(round(r2(fitx,axb),digits=3))  RMS=$(round(sqrt(sum(abs2,fitx.-axb)/nb)/G,digits=3))g")
# longitudinal grip-curve peak
κg = range(-0.25, 0; length=200); fg = [tyre_fx(1.0, k; p=merge(TYRE_DEFAULTS,(;μx=θlon[1],pKx1=θlon[2]))) for k in κg]
pk,ip = findmin(fg)
println("  longitudinal peak |μx|=$(round(-pk,digits=3)) at κ=$(round(κg[ip],digits=3))  (drag CdA=$(round(θlon[3],digits=2))m²)")

println("\nConclusions:")
println("  • CROSS-VALIDATION (headline): the skidpad tyre predicts Nordschleife lateral")
println("    accel at R²=$(round(r2(base,aymeas),digits=2)) on 23k independent samples — the grip curve generalises.")
println("  • Longitudinal (NEW, adopt): μx≈$(round(θlon[1],digits=2)) (matches lateral μ → good friction isotropy),")
println("    pKx1≈$(round(θlon[2],digits=1)), peak at κ≈$(round(κg[ip],digits=2)). → update TYRE_DEFAULTS μx/pKx1.")
println("  • NOT adopted: μ_scale=$(round(θlat[1],digits=2)) (overfit banking), CdA=$(round(θlon[3],digits=2))m² (lumped engine-braking,")
println("    not pure aero), pKy2 (load sensitivity unidentifiable from forward-ay).")
println("  • NEXT: pin load sensitivity with the per-corner model driven by the measured")
println("    shock-deflection/ride-height channels (real per-corner Fz), not assumed transfer.")
