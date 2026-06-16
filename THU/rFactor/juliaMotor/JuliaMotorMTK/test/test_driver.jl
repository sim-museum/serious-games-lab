# Validate the closed-loop driver: the car must TRACK and HOLD a target speed and
# yaw rate (a steady corner), demonstrating the feedback that removes open-loop
# drift.   Run: julia --project=. test/test_driver.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D
for fnm in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","vehicle_driven.jl","driver.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

const UREF = 28.0
const RREF = 0.25     # target yaw rate [rad/s] → ~0.7 g, ~112 m radius
println("compiling the closed-loop driver + vehicle…")
function Maneuver(; name)
    @named drv = ClosedLoopVehicle()
    eqs = [drv.uref ~ UREF,
           drv.rref ~ RREF*clamp((t - 1.0)/2.0, 0.0, 1.0),   # ramp into a steady corner, then hold
           drv.gear_in ~ 1.32]
    System(eqs, t, Num[], []; systems = [drv], name)
end
sys = mtkcompile(Maneuver(name = :m))
println("  states: $(length(unknowns(sys)))")
prob = ODEProblem(sys, [sys.drv.car.u => UREF, sys.drv.car.ωf => 93.3, sys.drv.car.ωr => 84.8], (0.0, 18.0))
sol  = solve(prob, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sol.retcode) == :Success

# steady-state tracking over the last 4 s (corner fully held)
tail = findall(≥(14.0), sol.t)
uend = sol[sys.drv.car.u][end];  rend = sol[sys.drv.car.r][end]
uerr = maximum(abs.(sol[sys.drv.car.u][tail] .- UREF))
rerr = maximum(abs.(sol[sys.drv.car.r][tail] .- RREF))
thr  = sol[sys.drv.car.throttle][end];  st = sol[sys.drv.car.δ][end];  ay = sol[sys.drv.car.ay][end]

println("\n  reference: u_ref=$(UREF) m/s, r_ref=$(RREF) rad/s")
println("  tracking:  u=$(round(uend,digits=2)) m/s (err≤$(round(uerr,digits=2)))   r=$(round(rend,digits=3)) rad/s (err≤$(round(rerr,digits=3)))")
println("  driver outputs: throttle=$(round(thr,digits=2))  steer=$(round(st,digits=3)) rad   ay=$(round(ay/9.81,digits=2)) g")
println("  → closed loop holds the target speed AND yaw rate steadily (no open-loop drift)")

@test Symbol(sol.retcode) == :Success
@test uerr < 0.8                        # holds target SPEED (PI throttle/brake)
@test rerr < 0.03                       # holds target YAW RATE (steer FF + feedback)
@test 0.0 ≤ thr ≤ 1.0                    # sensible pedal
@test ay > 5.0                          # actually cornering (~0.7 g)
@test sol[sys.drv.car.r][end] > 0       # correct direction

println("\nALL TESTS PASSED ✓ — closed-loop driver tracks speed + yaw; the model drives itself.")
