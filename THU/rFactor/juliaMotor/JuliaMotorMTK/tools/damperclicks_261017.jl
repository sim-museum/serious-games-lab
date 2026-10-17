# SETUPMODEL-1 S3: iRacing's damper CLICKS, from the PO's 261017 Part D1 (all dampers at 0 clicks, then at 12) and the
# base-damper runs of the same day (front +4/+8, rear +4/+7). Per file, the road-independent identity of
# suspfit_261004.jl: the four suspension forces carry the sprung mass,
#     M_s a_z = Σ_axle K·Σd + C_bump·Σv⁺ + C_reb·Σv⁻ + P
# on straight, unaccelerated 360 Hz samples with every shock inside its travel. C is per shock, at the shock.
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/damperclicks_261017.jl
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
const G = 9.80665
const DIR = get(ENV, "JM_DAMPDIR", expanduser("~/gold standard/julia racer/261017/telemetry"))
const M_U = 23.0                                    # unsprung per corner (garage fit: 226 N)
hs(f, n) = (M = hcat([channel(f, n; idx = j) for j in 1:6]...); vec(permutedims(M)))
function fitfile(fn)
    f = ibt_open(fn); sp = setup_params(f.yaml)
    Ms = sum(values(sp.corner_weight_N))/G - 4M_U
    az = hs(f, "VertAccel"); ax = hs(f, "LongAccel"); ay = hs(f, "LatAccel")
    d = [hs(f, c*"shockDefl") for c in ("LF","RF","LR","RR")]; v = [hs(f, c*"shockVel") for c in ("LF","RF","LR","RR")]
    on = channel(f, "IsOnTrack"); spd = channel(f, "Speed")
    X = Vector{Float64}[]; y = Float64[]
    for j in 1:length(az)
        r = div(j - 1, 6) + 1
        on[r] > 0.5 && spd[r] > 15 || continue
        abs(ax[j]) < 0.1G && abs(ay[j]) < 0.25G || continue
        all(i -> 0.010 < d[i][j] < (i <= 2 ? 0.095 : 0.103), 1:4) || continue
        vf = v[1][j] + v[2][j]; vr = v[3][j] + v[4][j]
        push!(X, [d[1][j] + d[2][j], d[3][j] + d[4][j], max(vf, 0.0), min(vf, 0.0), max(vr, 0.0), min(vr, 0.0), 1.0])
        push!(y, Ms*az[j])
    end
    A = reduce(hcat, X)'; θ = A \ y; r = y - A*θ
    # 1-s block bootstrap for the damping's spread
    n = length(y); B = 360; nb = div(n, B); bs = Vector{Float64}[]
    rng = Random.MersenneTwister(1)
    for _ in 1:200
        idx = vcat([((k-1)*B+1):(k*B) for k in rand(rng, 1:nb, nb)]...)
        push!(bs, A[idx, :] \ y[idx])
    end
    sd = [std(b[k] for b in bs) for k in 1:6]
    clk = (sp.bump_clicks[:LF], sp.rebound_clicks[:LF], sp.bump_clicks[:LR], sp.rebound_clicks[:LR])
    (; fn = basename(fn), clk, spring = (sp.spring_rate_Npmm[:LF], sp.spring_rate_Npmm[:LR]), n, θ, sd, r2 = 1 - var(r)/var(y))
end
using Random
rows = [fitfile(fn) for fn in sort(readdir(DIR; join = true)) if endswith(fn, ".ibt")]
println("clicks bump/reb F | R        springs   samples   K f/r N/mm      C front bump/reb      C rear bump/reb   N·s/m per shock (±1 sd)   R²")
for r in rows
    @printf("%-28s %2d/%2d | %2d/%2d  %2d/%2d  %7d   %5.1f / %5.1f   %5.0f±%-4.0f %5.0f±%-4.0f   %5.0f±%-4.0f %5.0f±%-4.0f  %.3f\n",
            first(r.fn[24:end], 28), r.clk..., r.spring..., r.n, r.θ[1]/1000, r.θ[2]/1000,
            r.θ[3], r.sd[3], r.θ[4], r.sd[4], r.θ[5], r.sd[5], r.θ[6], r.sd[6], r.r2)
end
