# Validate the LSD integrated into the full vehicle: in a power-on corner the
# unloaded inner-rear wheel spins under an open diff; the clutch-pack LSD reins it
# in.   Run: julia --project=. test/test_vehicle_lsd.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D
for fnm in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","lsd.jl","vehicle_lsd.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

println("compiling the LSD vehicle…")
function PowerCorner(; name)            # power-on LEFT corner (inner rear = left = RL)
    @named car = DrivenVehicleLSD()
    eqs = [car.δ ~ 0.035*clamp((t-0.5)/0.5, 0.0, 1.0),
           car.throttle ~ 0.6*clamp((t-0.5)/0.5, 0.0, 1.0),
           car.brake ~ 0.0, car.gear ~ 1.72]
    System(eqs, t, Num[], []; systems = [car], name)
end
sys = mtkcompile(PowerCorner(name = :pc))
println("  states: $(length(unknowns(sys)))  (rear axle unlumped: ωRL, ωRR)")
u0 = [sys.car.u => 28.0, sys.car.ωf => 93.3, sys.car.ωRL => 84.8, sys.car.ωRR => 84.8]

# compile once, solve open (lock_scale=0) vs LSD (lock_scale=1) via the parameter
function run(lock)
    sol = solve(ODEProblem(sys, merge(Dict(u0), Dict(sys.car.lock_scale => lock)), (0.0, 4.0)),
                FBDF(); reltol = 1e-6, abstol = 1e-6)
    (κRL = sol[sys.car.RL.tyre.κ][end], κRR = sol[sys.car.RR.tyre.κ][end],
     ωRL = sol[sys.car.ωRL][end], ωRR = sol[sys.car.ωRR][end],
     Tlsd = sol[sys.car.Tlsd][end], ax = sol[sys.car.ax][end],
     ay = sol[sys.car.ay][end], r = sol[sys.car.r][end])
end
op = run(0.0)    # open diff
ls = run(1.0)    # clutch-pack LSD

println("\n  power-on left corner, after 4 s:")
println("  OPEN diff:  inner κRL=$(round(op.κRL,digits=3))  outer κRR=$(round(op.κRR,digits=3))  Δω=$(round(op.ωRL-op.ωRR,digits=2))  ax=$(round(op.ax/9.81,digits=2))g")
println("  LSD:        inner κRL=$(round(ls.κRL,digits=3))  outer κRR=$(round(ls.κRR,digits=3))  Δω=$(round(ls.ωRL-ls.ωRR,digits=2))  ax=$(round(ls.ax/9.81,digits=2))g  (T_lsd=$(round(ls.Tlsd)) N·m)")
println("  → LSD ties the rear wheels together; the loaded outer then puts power down → more traction")

@test op.r > 0 && op.ay > 0                          # cornering (left)
@test op.κRL > op.κRR                                 # open: inner (lighter) rear free-spins, outer grips
@test abs(ls.ωRL - ls.ωRR) < 0.3*abs(op.ωRL - op.ωRR)  # LSD ties the rear wheel speeds together
@test ls.ax > op.ax + 0.5                             # better corner-exit traction (more longitudinal accel)
@test abs(ls.Tlsd) > 30                               # the clutch pack is transferring torque

println("\nALL TESTS PASSED ✓ — LSD integrated into the vehicle: rear unlumped, torque transfer in-corner.")
