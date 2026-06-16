# Validate the clutch-pack LSD: under power with a loaded outer / light inner rear
# (as in a corner), the LSD must limit inner wheelspin and recover traction vs an
# open diff.   Run: julia --project=. test/test_lsd.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D
for fnm in ("tyre.jl","powertrain.jl","lsd.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

# light inner (900 N) + loaded outer (2600 N) rear, 2nd gear, full throttle
build(lock; name) = mtkcompile(RearAxleLSD(name = name, Fz_RL = 900.0, Fz_RR = 2600.0,
                                           gear = 1.72, throttle = 1.0, lock_scale = lock))
function run(sys)
    sol = solve(ODEProblem(sys, [sys.u=>20.0, sys.ωRL=>60.6, sys.ωRR=>60.6], (0.0, 5.0)),
                FBDF(); reltol = 1e-7, abstol = 1e-7)
    (u = sol[sys.u][end], κRL = sol[sys.κRL][end], κRR = sol[sys.κRR][end],
     Fx = sol[sys.FxRL][end] + sol[sys.FxRR][end], Tlsd = sol[sys.Tlsd][end])
end
op = run(build(0.0, name = :op))         # open diff
ls = run(build(1.0, name = :ls))         # clutch-pack LSD

println("split grip (inner 900 N / outer 2600 N), 2nd gear WOT, after 5 s:")
println("  OPEN diff:  inner κRL=$(round(op.κRL,digits=3))  outer κRR=$(round(op.κRR,digits=3))  ΣFx=$(round(op.Fx)) N  u=$(round(op.u,digits=1)) m/s")
println("  LSD:        inner κRL=$(round(ls.κRL,digits=3))  outer κRR=$(round(ls.κRR,digits=3))  ΣFx=$(round(ls.Fx)) N  u=$(round(ls.u,digits=1)) m/s  (T_lsd=$(round(ls.Tlsd)) N·m)")
println("  → LSD transfers torque to the gripping outer wheel: less inner spin, more traction")

@test op.κRL > ls.κRL + 0.02            # LSD reduces inner (light-wheel) spin
@test abs(ls.Tlsd) > 50                  # the clutch pack is transferring torque
@test ls.Fx > op.Fx                      # more total drive force (better traction)
@test ls.u > op.u                        # so the car accelerates more
@test ls.κRR > op.κRR                     # outer wheel does more work under the LSD

println("\nALL TESTS PASSED ✓ — clutch-pack LSD: torque transfer fast→slow, traction recovered.")
