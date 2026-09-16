# AI-GOLD: the rolling radius, measured, so the vmax chain has no hand-set term left.
# r = v / ω on the REAR wheels. Restricted to steady high-speed samples: at low speed and under
# power/braking the wheels slip and v/ω is not a radius. Median, not mean -- one slip episode
# would drag a mean anywhere.
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics
D = get(ENV, "JM_IBTDIR", "/home/admin/gold standard/julia racer")
for f in sort(filter(x -> endswith(lowercase(x), ".ibt"), readdir(D; join=true)); by=filesize, rev=true)
    v  = try filter(isfinite, channel(ibt_open(f), "Speed"))   catch; Float64[] end
    wl = try filter(isfinite, channel(ibt_open(f), "LRspeed")) catch; Float64[] end
    wr = try filter(isfinite, channel(ibt_open(f), "RRspeed")) catch; Float64[] end
    n = min(length(v), length(wl), length(wr)); n < 500 && continue
    rs = Float64[]
    for i in 1:n
        ω = 0.5*(wl[i] + wr[i])
        v[i] > 25.0 && ω > 5.0 || continue          # rolling fast, not stationary
        push!(rs, v[i]/ω)
    end
    isempty(rs) && continue
    @printf("  %-46s r median=%.4f m  p25=%.4f p75=%.4f  n=%d\n",
            first(basename(f), 46), median(rs), quantile(rs,0.25), quantile(rs,0.75), length(rs))
end
