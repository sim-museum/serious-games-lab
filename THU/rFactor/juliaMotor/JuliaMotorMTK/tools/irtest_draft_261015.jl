# CARINTERACT-1 (prepared 2026-10-16 for IRTEST-261015 test 5): iRacing's DRAFT, measured from the PO's .ibt files.
#
# Full-throttle samples on a straight (Throttle > 0.98, no brake, |LatAccel| < 0.12 g, gear steady) are split by the gap
# to the car ahead (CarDistAhead, metres). The lone acceleration a0(v) is fitted per gear on samples with no car within
# LONE_GAP; a sample in a tow then gains da = a - a0(v), which is drag removed: the drag cut = da x m / (0.5 rho v^2 CdA).
# Printed per gap bin, against julia's rule (DRAFT_DRAG_CUT 45 % right behind, tapering to 0 at DRAFT_LEN 26 m).
#
#   julia --project=. tools/irtest_draft_261015.jl <dir or .ibt files...>      (JM_DRAFT_MASS, default 650 kg incl. fuel)
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
const G = 9.80665
const RHO = 1.10; const CDA = 0.480                                    # powertrain.jl CDA_IBT, at the model's air density
const MASS = parse(Float64, get(ENV, "JM_DRAFT_MASS", "650"))
const LONE_GAP = 150.0
const BINS = ((0.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 50.0), (50.0, LONE_GAP))
julia_cut(gap) = gap < 2.0 ? 0.45 : gap > 26.0 ? 0.0 : 0.45*(1 - (gap - 2.0)/24.0)   # the shape, for comparison

files = String[]
for a in ARGS
    isdir(a) ? append!(files, filter(f -> endswith(lowercase(f), ".ibt"), readdir(a; join = true))) : push!(files, a)
end
isempty(files) && (println("usage: irtest_draft_261015.jl <dir or .ibt files>"); exit(2))

# samples: (gear, v, a, gap)
S = Tuple{Int,Float64,Float64,Float64}[]
SETUPS = String[]                                   # a gear key is setup*10 + gear (lone fits per setup)
for fn in files
    f = ibt_open(fn); c(n) = haskey(f.vars, n) ? channel(f, n) : nothing
    m = match(r"DriverSetupName: ([^\n]*)", f.yaml); su = m === nothing ? "?" : m.captures[1]
    su in SETUPS || push!(SETUPS, su); si = findfirst(==(su), SETUPS)
    v = c("Speed"); ax = c("LongAccel"); thr = c("Throttle"); brk = c("Brake"); ay = c("LatAccel"); gear = c("Gear"); gap = c("CarDistAhead")
    any(x -> x === nothing, (v, ax, thr, brk, ay, gear)) && (println("  skip ", basename(fn), ": missing channels"); continue)
    n = length(v); kept = 0
    # 2026-10-18 (IRPLAN-3 F): the PO's pedal topped out at 0.807 from 13:44 that day -- "full" is the file's own top
    full = 0.98*maximum(thr); full < 0.95 && @printf("  %s: the pedal tops out at %.3f -- full throttle taken as > %.3f\n", basename(fn), maximum(thr), full)
    for k in 31:n
        (thr[k] > full && brk[k] < 0.01 && abs(ay[k]) < 0.12G && v[k] > 25 && gear[k] >= 2) || continue
        all(j -> gear[j] == gear[k] && thr[j] > 0.92*full, k-30:k) || continue          # 0.5 s settled in this gear, on power
        g = gap === nothing ? Inf : (gap[k] > 0 ? Float64(gap[k]) : Inf)
        push!(S, (10si + Int(gear[k]), Float64(v[k]), Float64(ax[k]), g)); kept += 1
    end
    @printf("  %-60s %6d full-throttle straight samples\n", basename(fn)[1:min(end, 60)], kept)
end
isempty(S) && (println("no samples"); exit(1))

# lone fit per gear: a0(v) = c0 + c1 v + c2 v^2 (least squares)
fits = Dict{Int,Vector{Float64}}()
for g in sort(unique(first.(S)))
    L = [s for s in S if s[1] == g && s[4] >= LONE_GAP]
    length(L) < 60 && continue
    X = hcat(ones(length(L)), [s[2] for s in L], [s[2]^2 for s in L]); y = [s[3] for s in L]
    fits[g] = X \ y
    r = y - X*fits[g]
    @printf("  %s gear %d: lone fit on %d samples, residual %.3f m/s^2 RMS (v %.0f-%.0f km/h)\n", SETUPS[g ÷ 10], g % 10, length(L), sqrt(mean(abs2, r)),
            3.6minimum(s[2] for s in L), 3.6maximum(s[2] for s in L))
end
isempty(fits) && (println("no gear with enough lone samples (>= 60 with no car within $(LONE_GAP) m) -- record the lone runs (test 5a)"); exit(1))

println("\n  gap to the car ahead | samples | mean speed | extra accel | drag cut (iRacing) | julia's rule")
for (lo, hi) in BINS
    B = [s for s in S if haskey(fits, s[1]) && lo <= s[4] < hi]
    isempty(B) && (@printf("  %5.0f-%-5.0f m          |       0 |\n", lo, hi); continue)
    da = [s[3] - (fits[s[1]][1] + fits[s[1]][2]*s[2] + fits[s[1]][3]*s[2]^2) for s in B]
    cut = [da[i]*MASS / (0.5*RHO*B[i][2]^2*CDA) for i in eachindex(B)]
    @printf("  %5.0f-%-5.0f m          | %7d | %6.0f km/h | %+6.3f m/s^2 | %6.1f %% +- %4.1f    | %5.1f %%\n", lo, hi, length(B),
            3.6mean(s[2] for s in B), mean(da), 100mean(cut), 100std(cut)/sqrt(length(cut)), 100julia_cut((lo + hi)/2))
end
println("\n  (the cut assumes the extra acceleration is all drag removed; mass $(MASS) kg -- JM_DRAFT_MASS to change)")
