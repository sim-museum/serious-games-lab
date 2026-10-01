# E91-S9: aero + rolling from the gold's CLUTCH-DISENGAGED coasts (iRacing Clutch 0 = disengaged).
# Segment bootstrap: points inside one coast are autocorrelated, so resample whole segments.
using Printf, Statistics, Random
const T = joinpath(@__DIR__, "..")
include(joinpath(T, "src", "ibt.jl")); using .IBT
include(joinpath(T, "src", "setup.jl")); using .Setup
const DT = 1/60; const G = 9.80665
ch(f,n) = try channel(f,n) catch; nothing end
const REF = get(ENV, "JM_REFDIR", "/home/admin/gold standard/julia racer")

fitAR(v, d) = (X = hcat(v.^2, ones(length(v))); X \ d)

function main()
    files = String[]
    for (r,_,fs) in walkdir(REF), fn in fs
        endswith(lowercase(fn), ".ibt") && push!(files, joinpath(r,fn))
    end
    segs = Vector{Vector{NTuple{2,Float64}}}()
    rho = Float64[]; mass = Float64[]
    nshift = Ref(0); ngear0 = Ref(0)
    for p in files
        f = ibt_open(p)
        try push!(mass, sum(values(Setup.setup_params(IBT.session_yaml(f)).corner_weight_N))/G) catch; end
        thr, brk, spd, gr, cl = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed"), ch(f,"Gear"), ch(f,"Clutch")
        lat, stw, yaw, alt, ad = ch(f,"LatAccel"), ch(f,"SteeringWheelAngle"), ch(f,"YawRate"), ch(f,"Alt"), ch(f,"AirDensity")
        ad !== nothing && append!(rho, ad[ad .> 0.5])
        n = minimum(length, (thr,brk,spd,gr,cl))
        cur = NTuple{2,Float64}[]; last = -10
        for k in 4:n-4
            ok = thr[k] <= 0.01 && brk[k] <= 0.01 && spd[k] >= 8 &&
                 abs(lat[k]) <= 2.0 && abs(stw[k]) <= 0.10 && abs(yaw[k]) <= 0.05
            # disengaged: clutch pedal fully in for the whole window, OR neutral
            dis = all(j -> cl[j] < 0.05, k-3:k+3) || all(j -> gr[j] == 0, k-3:k+3)
            ok && dis || continue
            if !all(j -> gr[j] == gr[k], k-30:k+30) ; nshift[] += 1; continue; end   # a shift transient
            gr[k] == 0 && (ngear0[] += 1)
            dec = -(spd[k+3]-spd[k-3])/(6*DT) - G*((alt[k+3]-alt[k-3])/(6*DT))/spd[k]
            abs(dec) > 15 && continue
            if k != last + 1 && !isempty(cur); push!(segs, cur); cur = NTuple{2,Float64}[]; end
            push!(cur, (spd[k], dec)); last = k
        end
        isempty(cur) || push!(segs, cur)
    end
    segs = filter(s -> length(s) >= 6, segs)
    v = [x[1] for s in segs for x in s]; d = [x[2] for s in segs for x in s]
    @printf("clean disengaged: %d points in %d segments (%d dropped as shift transients, %d in neutral); %.0f..%.0f km/h\n",
            length(v), length(segs), nshift[], ngear0[], 3.6minimum(v), 3.6maximum(v))
    A, R = fitAR(v, d)
    res = d .- (A .* v.^2 .+ R)
    rng = MersenneTwister(1); As = Float64[]; Rs = Float64[]
    for _ in 1:2000
        ss = segs[rand(rng, 1:length(segs), length(segs))]
        vv = [x[1] for s in ss for x in s]; dd = [x[2] for s in ss for x in s]
        a, r = fitAR(vv, dd); push!(As, a); push!(Rs, r)
    end
    q(x) = (quantile(x, 0.05), quantile(x, 0.95))
    m = median(mass); ρ = median(rho)
    @printf("fit: dec = %.3e v^2 + %.3f   resid sd %.3f   (m = %.0f kg, rho = %.3f)\n", A, R, std(res), m, ρ)
    @printf("  A 90%% CI %.3e .. %.3e   ->  CdA %.2f (%.2f .. %.2f) m^2\n", q(As)..., 2m*A/ρ, (2m .* q(As) ./ ρ)...)
    @printf("  R 90%% CI %.3f .. %.3f   ->  Crr %.4f (%.4f .. %.4f)\n", q(Rs)..., R/G, (q(Rs) ./ G)...)
    # model at fixed speeds with CI (A,R are anticorrelated; this is the honest band)
    for kmh in (80, 100, 120, 160, 200)
        u = kmh/3.6; pr = As .* u^2 .+ Rs
        @printf("  %3d km/h: ref %.3f (%.3f..%.3f)   sim(CdA .9, rho 1.10, Crr .02, m 617) %.3f\n",
                kmh, A*u^2+R, q(pr)..., 0.5*1.10*0.9*u^2/617 + 0.02*G)
    end
end
main()
