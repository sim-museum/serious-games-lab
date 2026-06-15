# Validate the four-corner chassis: a constant-speed step-steer must reach a
# steady cornering state with consistent yaw rate / lateral accel and load
# transferred to the OUTER wheels.   Run: julia --project=. test/test_vehicle.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "corner.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "corner_assembly.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "vehicle.jl"))

const U0 = 25.0          # constant speed [m/s] (90 km/h)
const DMAX = 0.04        # front road-steer angle [rad] (~2.3°)

function StepSteer(; name)
    @named car = Vehicle()
    eqs = [car.u ~ U0, car.δ ~ DMAX*clamp((t - 0.5)/0.5, 0.0, 1.0)]
    System(eqs, t, Num[], []; systems = [car], name)
end

println("compiling the 4-corner vehicle…")
sys = mtkcompile(StepSteer(name = :ss))
println("  states: $(length(unknowns(sys)))")
prob = ODEProblem(sys, [], (0.0, 6.0))
sol  = solve(prob, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sol.retcode) == :Success

# steady-state values (end of run)
r   = sol[sys.car.r][end]
ay  = sol[sys.car.ay][end]
β   = sol[sys.car.β][end]
FzFL = sol[sys.car.FL.corner.Fz][end];  FzFR = sol[sys.car.FR.corner.Fz][end]
FzRL = sol[sys.car.RL.corner.Fz][end];  FzRR = sol[sys.car.RR.corner.Fz][end]
R = U0 / r

println("\n  STEADY STATE (δ=$(DMAX) rad, u=$(U0) m/s):")
println("    yaw rate r   = $(round(r,digits=4)) rad/s   → radius R = $(round(R,digits=1)) m")
println("    lateral accel ay = $(round(ay,digits=3)) m/s² ($(round(ay/9.81,digits=2)) g)")
println("    consistency  u·r = $(round(U0*r,digits=3)) m/s²  (should ≈ ay)")
println("    body slip β  = $(round(rad2deg(β),digits=2))°")
println("    corner loads N:  FL=$(round(FzFL)) FR=$(round(FzFR)) | RL=$(round(FzRL)) RR=$(round(FzRR))")
println("    front lat transfer = $(round(FzFR-FzFL)) N,  rear = $(round(FzRR-FzRL)) N")
println("    understeer check: neutral δ=L/R=$(round(2.41/R,digits=4)) vs actual $(DMAX) rad (actual>neutral ⇒ understeer)")

@test r > 0                                   # δ>0 → left turn → r>0
@test isapprox(ay, U0*r; rtol = 0.02)         # steady-state kinematic consistency
@test 3.0 < ay < 14.0                         # a sane mid-corner (0.3–1.4 g)
@test FzFR > FzFL && FzRR > FzRL              # outer (right) wheels loaded in a left turn
@test (FzFL+FzFR+FzRL+FzRR) > 5500 && (FzFL+FzFR+FzRL+FzRR) < 6600  # ≈ m·g, vert load conserved
@test abs(rad2deg(β)) < 12                    # body slip sane

println("\nALL TESTS PASSED ✓ — four-corner chassis closes (load transfer → grip → yaw/accel).")
