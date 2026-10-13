# IRGOLD-1 S15: fit the anti-stall clutch law (vehicle_3d.jl as_r0, as_k, as_w) on the IRTEST-261012 launches driven by the
# driver's RAW pedal (ClutchRaw): emax = clamp((rpm − (as_r0 − as_k·throttle))/as_w). Coordinate search on mean |Δv|.
#   JM_LAUNCH_DIR=".../261012" julia --project=. tools/antistall_fit_261012.jl
ENV["JM_LAUNCH_RAW"] = "1"
include(joinpath(@__DIR__, "launchval_261009.jl"))
QUIET[] = true
score(x) = (AS[] = Tuple(x); s = main(); println("  AS ", round.(x), " -> ", round(s, digits = 3)); flush(stdout); s)
function search(p, h)                              # a function: top-level loops would make `best` local (soft scope)
    best = score(p)
    for it in 1:3, i in 1:3
        for sgn in (-1, 1)
            q = copy(p); q[i] += sgn*h[i]; q[3] = max(q[3], 50.0)
            sq = score(q)
            sq < best && (best = sq; p = q; break)
        end
        it == 3 || (h[i] *= 0.6)
    end
    p, best
end
p, best = search([1957.0, 623.0, 400.0], [150.0, 200.0, 150.0])
println("BEST AS ", p, "  mean |Δv| ", round(best, digits = 3))
