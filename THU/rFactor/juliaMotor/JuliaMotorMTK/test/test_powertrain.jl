# Validate the powertrain + brakes: throttle/brake must GENERATE slip ratio κ and
# drive the body speed.   Run:  julia --project=. test/test_powertrain.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre_law.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "powertrain.jl"))

g = 9.80665
println("="^70); println("1) full-throttle acceleration in 2nd gear"); println("="^70)
acc = mtkcompile(LongitudinalVehicle(name = :acc, gear = 1.72, throttle = 1.0, brake = 0.0))
pa  = ODEProblem(acc, [acc.u => 20.0, acc.ωf => 66.7, acc.ωr => 60.6], (0.0, 8.0))
sa  = solve(pa, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sa.retcode) == :Success
u0, uf = sa[acc.u][1], sa[acc.u][end]
κr = sa[acc.κr];  rpm = sa[acc.rpm];  ax = sa[acc.ax]
println("  u: $(round(u0,digits=1)) → $(round(uf,digits=1)) m/s ($(round(uf*3.6)) km/h)   mean ax=$(round(sum(ax)/length(ax)/g,digits=2)) g")
println("  rpm: $(round(minimum(rpm)))..$(round(maximum(rpm)))   rear slip κr: $(round(minimum(κr),digits=3))..$(round(maximum(κr),digits=3))")
println("  → 2nd-gear WOT: drive torque > rear grip ⇒ traction-limited wheelspin (κr≈0.5), physical for a ~400 hp Lotus 49")
@test uf > u0 + 5                              # it accelerates
@test all(κr .> -1e-3)                          # driven wheel slips POSITIVE (traction = forward slip)
@test maximum(κr) < 0.9                          # bounded — wheelspin, not numerical runaway
@test maximum(rpm) < 9800                        # redline fuel-cut respected
@test sum(ax)/length(ax) > 0                     # net positive acceleration

println("\n", "="^70); println("2) hard braking (70%) from 45 m/s"); println("="^70)
brk = mtkcompile(LongitudinalVehicle(name = :brk, gear = 1.32, throttle = 0.0, brake = 0.7))
pb  = ODEProblem(brk, [brk.u => 45.0, brk.ωf => 150.0, brk.ωr => 136.0], (0.0, 3.0))
sb  = solve(pb, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sb.retcode) == :Success
ub0, ubf = sb[brk.u][1], sb[brk.u][end]
κfb = sb[brk.κf];  κrb = sb[brk.κr];  axb = sb[brk.ax]
amin = minimum(axb)
println("  u: $(round(ub0,digits=1)) → $(round(ubf,digits=1)) m/s   peak decel=$(round(amin/g,digits=2)) g")
println("  front slip κf: $(round(minimum(κfb),digits=3))..$(round(maximum(κfb),digits=3))   rear κr: $(round(minimum(κrb),digits=3))..$(round(maximum(κrb),digits=3))")
@test ubf < ub0 - 10                            # it decelerates
@test minimum(κfb) < -0.02 && minimum(κrb) < -0.02   # braking ⇒ negative slip
@test amin < -0.5g                              # meaningful deceleration
@test amin > -1.5g                              # but physical (≤ tyre μ)
@test minimum(κfb) > -1.01                       # wheels not spinning backwards

println("\nALL TESTS PASSED ✓ — powertrain + brakes generate κ and drive body speed.")
