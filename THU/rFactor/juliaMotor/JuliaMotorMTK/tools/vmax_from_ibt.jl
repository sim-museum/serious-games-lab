# AI-GOLD: derive the AI's top-speed anchor from the CAR, not from a fitted constant.
#
# Monza's residual is vmax-limited (102.68 s at 74 m/s vs 92.75 s at 120 m/s), and the current
# vmax = 74 m/s = 266 km/h is a hand-set number. The gold .ibt cannot supply it by observation --
# its only road lap is the Nordschleife, which tops out at 59 m/s because that track never asks for
# more. But the DRIVETRAIN can: v = RW_R * rpm * 2π/60 / (topGear * final).
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf
D = get(ENV, "JM_IBTDIR", "/home/admin/gold standard/julia racer")
files = sort(filter(f -> endswith(lowercase(f), ".ibt"), readdir(D; join=true)); by=filesize, rev=true)
pct(v,q) = (u=sort(v); u[clamp(ceil(Int,q*length(u)),1,length(u))])
GEARS = [2.23, 1.72, 1.32, 1.09, 0.916]; RW_R = parse(Float64, get(ENV,"JM_RW_R","0.33"))
for f in files
    r = try filter(isfinite, channel(ibt_open(f), "RPM")) catch; Float64[] end
    length(r) < 500 && continue
    s = try filter(isfinite, channel(ibt_open(f), "Speed")) catch; Float64[] end
    fin = parse(Float64, get(ENV, "JM_FINAL", "4.11"))
    for (lbl,q) in (("p99",0.99),("max",1.0))
        rp = q==1.0 ? maximum(r) : pct(r,q)
        v  = RW_R * rp * 2π/60 / (GEARS[end]*fin)
        @printf("  %-46s RPM %s=%6.0f -> vmax=%5.1f m/s (%3.0f km/h)   observed speed max=%.1f m/s\n",
                first(basename(f), 46), lbl, rp, v, 3.6v, isempty(s) ? NaN : maximum(s))
    end
end
