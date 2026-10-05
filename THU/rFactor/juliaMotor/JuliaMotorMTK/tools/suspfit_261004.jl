# IRFIT-261004 (test 2): the Lotus 49's springs and dampers as iRacing has them, from the 360 Hz shock channels of the
# PO's 2026-10-04 Ring session (irsdkLog360Hz=1: LF/RF/LR/RR shockDefl + shockVel, VertAccel, 6 per 60 Hz row).
#
# Road-independent identity (the iRacing Ring is a modern laser scan, GPL's is 1967, so crest passes cannot be
# compared directly): the four suspension forces carry the sprung mass,
#     Σ F_i = M_s · a_z          (a_z = VertAccel, specific force, gravity included)
#     F_i   = K·d_i + C·v_i + P  (d, v = shock deflection / velocity; per axle, C split bump / rebound)
# so a linear regression of M_s·a_z on per-axle Σd, Σv⁺, Σv⁻ gives the per-shock-mm wheel force K and damping C.
# Check: K must equal the setup's spring rate x motion ratio (30 / 48 N/mm x MR) -- the sim's wheel rate is
# spring x MR² with MR² = 0.6083 (drive_rt3d.jl). Only straight, unaccelerated samples (|long| < 0.1 g, |lat| < 0.25 g)
# with all four shocks inside their travel (no bump-stop / droop) -- anti-dive/squat and jacking stay out.
#   julia --project=. tools/suspfit_261004.jl
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
const G = 9.80665
const D4 = get(ENV, "JM_SUSPDIR", expanduser("~/gold standard/julia racer/261004"))
const M_U = 20.0                                    # unsprung per corner, as DrivenVehicle3D
hs(f, n) = (M = hcat([channel(f, n; idx = j) for j in 1:6]...); vec(permutedims(M)))   # 360 Hz series
function collect_rows()
    X = Vector{Float64}[]; y = Float64[]; files = 0; grp = Int[]
    for fn in sort(readdir(D4; join = true))
        (occursin("nordschleife", fn) && endswith(fn, ".ibt")) || continue
        f = ibt_open(fn); haskey(f.vars, "LFshockDefl") && f.vars["LFshockDefl"].count == 6 || continue
        files += 1
        sp = setup_params(f.yaml); Ms = sum(values(sp.corner_weight_N))/9.81 - 4M_U
        az = hs(f, "VertAccel"); ax = hs(f, "LongAccel"); ay = hs(f, "LatAccel")
        d = [hs(f, c*"shockDefl") for c in ("LF","RF","LR","RR")]; v = [hs(f, c*"shockVel") for c in ("LF","RF","LR","RR")]
        on = channel(f, "IsOnTrack"); spd = channel(f, "Speed")
        for j in 1:length(az)
            r = div(j - 1, 6) + 1
            on[r] > 0.5 && spd[r] > 15 || continue
            abs(ax[j]) < 0.1G && abs(ay[j]) < 0.25G || continue
            all(i -> 0.010 < d[i][j] < (i <= 2 ? 0.095 : 0.103), 1:4) || continue
            df = d[1][j] + d[2][j]; dr = d[3][j] + d[4][j]
            vf = v[1][j] + v[2][j]; vr = v[3][j] + v[4][j]
            push!(X, [df, dr, max(vf, 0.0), min(vf, 0.0), max(vr, 0.0), min(vr, 0.0), 1.0]); push!(y, Ms*az[j]); push!(grp, files)
        end
    end
    reduce(hcat, X)', y, files, grp
end
# NOT fitted: a pitch-acceleration term (a VertAccel sensor away from the CG). Tried: it is collinear with the
# unknowns (pitch acceleration is CAUSED by the same suspension forces) and drove front K to 13.8 N/mm against
# the setup's 30 N/mm x MR 0.78 = 23.4 -- which the plain identity reproduces (22.9). The sensor is at the CG.
A, y, nf, grp = collect_rows()
θ = A \ y
r = y - A*θ
@printf("%d samples from %d files (360 Hz)   resid sd %.0f N  (y sd %.0f N, R² %.3f)\n", length(y), nf, std(r), std(y), 1 - var(r)/var(y))
@printf("K front %.1f N/mm  rear %.1f N/mm   (setup spring x MR 0.78: %.1f / %.1f)\n", θ[1]/1000, θ[2]/1000, 30*0.78, 48*0.78)
@printf("C front bump %.0f  rebound %.0f   rear bump %.0f  rebound %.0f  N·s/m  (per shock, at the wheel)\n", θ[3], θ[4], θ[5], θ[6])
mr = sqrt(0.6083)
@printf("as WHEEL rates (x MR %.3f): ks front %.0f rear %.0f N/m (sim 18250 / 29200);  cs front %.0f/%.0f rear %.0f/%.0f N·s/m (sim 2500 / 3000)\n",
        mr, θ[1]*mr, θ[2]*mr, θ[3]*mr, θ[4]*mr, θ[5]*mr, θ[6]*mr)
# bootstrap by 1-s blocks for a CI on the damping
using Random; rng = MersenneTwister(1); n = length(y); B = 360; nb = div(n, B); bs = Vector{Vector{Float64}}()
for _ in 1:300
    idx = vcat([((k-1)*B+1):(k*B) for k in rand(rng, 1:nb, nb)]...)
    push!(bs, A[idx, :] \ y[idx])
end
for (i, lab) in enumerate(("K front", "K rear", "C f bump", "C f reb", "C r bump", "C r reb"))
    @printf("   %-9s 90%% CI %.0f .. %.0f\n", lab, quantile(getindex.(bs, i), 0.05), quantile(getindex.(bs, i), 0.95))
end

# consistency: the same fit on odd and even files separately
for (lab, sel) in (("odd files ", isodd.(grp)), ("even files", iseven.(grp)))
    t = A[sel, :] \ y[sel]
    @printf("   %s n %6d  K %.1f / %.1f N/mm   C front %.0f/%.0f  rear %.0f/%.0f\n", lab, count(sel), t[1]/1000, t[2]/1000, t[3], t[4], t[5], t[6])
end
