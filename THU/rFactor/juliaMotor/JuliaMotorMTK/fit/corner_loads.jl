# Build + validate the per-corner load model from shock deflection, then use the
# MEASURED per-corner loads to identify tyre load sensitivity (pKy2) — which the
# forward-ay method (assumed load transfer) could not.
#
# Run:  julia --project=. fit/corner_loads.jl

include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "corner_loads.jl")); using .CornerLoads
include(joinpath(@__DIR__, "..", "src", "components", "tyre_law.jl"))
include(joinpath(@__DIR__, "fitutil.jl")); using .FitUtil

const G = 9.80665
const L = 2.41
const DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
files = filter(f -> startswith(f, "lotus49_nurburgring") && endswith(f, ".ibt"), readdir(DATA))

shchan = vcat([["$(c)shockDefl", "$(c)shockVel"] for c in ("LF","RF","LR","RR")]...)
chs = vcat(["Speed","VelocityX","VelocityY","YawRate","LatAccel","LongAccel","VertAccel",
            "SteeringWheelAngle","IsOnTrack"], shchan)
Dch = Dict(c => Float64[] for c in chs)
for fn in files
    f = IBT.ibt_open(joinpath(DATA, fn))
    cols = Dict(c => IBT.channel(f, c) for c in chs)
    for i in 2:f.nrows-1
        cols["IsOnTrack"][i] > 0.5 && cols["Speed"][i] > 10 &&
        cols["VelocityX"][i] > 5 && abs(cols["LatAccel"][i]) < 25 &&
        abs(cols["LongAccel"][i]) < 25 || continue
        for c in chs; push!(Dch[c], cols[c][i]); end
    end
end
N = length(Dch["Speed"]); println("clean samples: $N")

p = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(joinpath(DATA, files[1]))))
m = sum(values(p.corner_weight_N)) / G
front_fr = (p.corner_weight_N[:LF] + p.corner_weight_N[:RF]) / sum(values(p.corner_weight_N))
a = (1-front_fr)*L;  b = front_fr*L
ks = Dict(c => p.spring_rate_Npmm[c]*1000.0 for c in CORNERS)   # N/m
cw = Dict(c => p.corner_weight_N[c] for c in CORNERS)
shock    = Dict(c => Dch["$(c)shockDefl"] for c in CORNERS)
shockvel = Dict(c => Dch["$(c)shockVel"]  for c in CORNERS)
va = Dch["VertAccel"]
println("m=$(round(m,digits=1))kg  springs(N/mm) "*join(["$c=$(Int(p.spring_rate_Npmm[c]))" for c in CORNERS], " "))

# ---- calibrate the per-corner load model ------------------------------------
static = [i for i in 1:N if abs(va[i]-G)<0.4 && abs(Dch["LongAccel"][i])<0.8 && abs(Dch["LatAccel"][i])<0.8 && Dch["Speed"][i]>12]
good   = collect(1:N)
M = fit_corner_loads(shock, shockvel, va, m, ks, cw, good, static)
println("\n[CORNER LOAD MODEL]")
println("  motion ratio MR=$(round(M.MR,digits=3))   damper cd=$(round(M.cd,digits=1)) N/(m/s)")
println("  static refs(mm): "*join(["$c=$(round(M.ref[c]*1000,digits=1))" for c in CORNERS], " "))
println("  Σ corner loads vs measured m·VertAccel:  R²=$(round(M.r2,digits=3))  ($(length(static)) static-ref samples)")
for c in CORNERS
    fz = [corner_Fz(M, shock[c][i], shockvel[c][i], c) for i in 1:N]
    println("  Fz_$c: $(round(minimum(fz)))..$(round(maximum(fz))) N  (static $(Int(round(cw[c]))), mean $(round(sum(fz)/N)))")
end

# ---- lateral load-sensitivity fit using MEASURED per-corner loads -----------
front0 = TYRE_SKIDPAD_FRONT;  rear0 = TYRE_SKIDPAD_REAR
withp(base; pKy2, μs) = merge(base, (; pKy2 = pKy2, μy = base.μy*μs))
cidx = [i for i in 1:N if abs(Dch["LatAccel"][i])>3.0]
nc = length(cidx); println("\n[LATERAL load sensitivity]  cornering samples: $nc")

# precompute per-sample per-corner Fz, axle slip, measured ay
FZ = Dict(c => [corner_Fz(M, shock[c][i], shockvel[c][i], c) for i in cidx] for c in CORNERS)
αf = Float64[]; αr = Float64[]; aym = Float64[]; axm = Float64[]; vam = Float64[]
for i in cidx
    vx,vy,r = Dch["VelocityX"][i], Dch["VelocityY"][i], Dch["YawRate"][i]
    δ = Dch["SteeringWheelAngle"][i]/p.steering_ratio
    push!(αf, δ - atan(vy + a*r, vx)); push!(αr, -atan(vy - b*r, vx))
    push!(aym, Dch["LatAccel"][i]); push!(axm, Dch["LongAccel"][i]); push!(vam, va[i])
end
r2(pred,meas) = (ȳ=sum(meas)/length(meas); 1 - sum(abs2,pred.-meas)/sum(x->abs2(x-ȳ),meas))

# (a) measured per-corner loads
function ay_measload(θ)
    μs,pKy2 = θ
    pf=withp(front0;pKy2=pKy2,μs=μs); pr=withp(rear0;pKy2=pKy2,μs=μs)
    [ (tyre_fy(FZ[:LF][k],αf[k];p=pf)+tyre_fy(FZ[:RF][k],αf[k];p=pf)+
       tyre_fy(FZ[:LR][k],αr[k];p=pr)+tyre_fy(FZ[:RR][k],αr[k];p=pr))/m for k in 1:nc ]
end
# (b) assumed load transfer (the old method), same samples, for comparison
function ay_assumed(θ; h=0.30)
    μs,pKy2 = θ
    pf=withp(front0;pKy2=pKy2,μs=μs); pr=withp(rear0;pKy2=pKy2,μs=μs)
    out=zeros(nc)
    for k in 1:nc
        Fzt=m*max(vam[k],0.2G); Fzf=Fzt*(b/L)-m*axm[k]*h/L; Fzr=Fzt*(a/L)+m*axm[k]*h/L
        Fzf=clamp(Fzf/2,150,2e4); Fzr=clamp(Fzr/2,150,2e4)
        out[k]=(2tyre_fy(Fzf,αf[k];p=pf)+2tyre_fy(Fzr,αr[k];p=pr))/m
    end
    out
end
println("  baseline (skidpad params, pKy2=2.2):")
println("    assumed transfer : R²=$(round(r2(ay_assumed([1.0,2.2]),aym),digits=3))")
println("    MEASURED per-corner loads (shock): R²=$(round(r2(ay_measload([1.0,2.2]),aym),digits=3))")
θm,_ = nelder_mead(θ->( (θ[1]<0.7||θ[1]>1.5||θ[2]<1.0||θ[2]>6.0) ? 1e9 : sum(abs2,ay_measload(θ).-aym) ), [1.0,2.2]; iters=600)
println("  fitted (measured loads): μ_scale=$(round(θm[1],digits=3)) pKy2=$(round(θm[2],digits=2)) → R²=$(round(r2(ay_measload(θm),aym),digits=3))")
println("  → pKy2 now identifiable: real outer/inner loads from shock expose load sensitivity")
