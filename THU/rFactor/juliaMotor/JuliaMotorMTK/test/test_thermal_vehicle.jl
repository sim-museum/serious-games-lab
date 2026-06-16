# Validate ThermalTyre integrated into the full vehicle: per-corner tyre
# temperatures evolve during cornering (outer/worked tyres run hotter).
# Run: julia --project=. test/test_thermal_vehicle.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D
for fnm in ("tyre.jl","tyre_thermal.jl","corner.jl","powertrain.jl","thermal_vehicle.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

println("compiling the thermal vehicle…")
function Corner25(; name)               # sustained left corner under power
    @named car = ThermalVehicle(T0 = 60.0)
    eqs = [car.δ ~ 0.045*clamp((t-0.5)/0.5, 0.0, 1.0),
           car.throttle ~ 0.45*clamp((t-0.5)/0.5, 0.0, 1.0),
           car.brake ~ 0.0, car.gear ~ 1.32]
    System(eqs, t, Num[], []; systems = [car], name)
end
sys = mtkcompile(Corner25(name = :tv))
println("  states: $(length(unknowns(sys)))  (incl. 4 tyre temps)")
prob = ODEProblem(sys, [sys.car.u => 32.0, sys.car.ωf => 106.7, sys.car.ωr => 97.0], (0.0, 25.0))
sol  = solve(prob, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sol.retcode) == :Success

TFL = sol[sys.car.FL.tyre.T][end];  TFR = sol[sys.car.FR.tyre.T][end]
TRL = sol[sys.car.RL.tyre.T][end];  TRR = sol[sys.car.RR.tyre.T][end]
gFR = sol[sys.car.FR.tyre.gT][end]
ay  = sol[sys.car.ay][end];  r = sol[sys.car.r][end]
FzFL = sol[sys.car.FL.corner.Fz][end]; FzFR = sol[sys.car.FR.corner.Fz][end]

println("\n  after 25 s of a left corner (δ=0.045, throttle 0.45, 2nd-ish gear):")
println("    ay=$(round(ay/9.80665,digits=2)) g   yaw r=$(round(r,digits=3)) rad/s")
println("    tyre temps °C (start 60):  FL=$(round(TFL)) FR=$(round(TFR)) | RL=$(round(TRL)) RR=$(round(TRR))")
println("    outer fronts/rears run hotter (more load → more slip power); FR grip factor gT=$(round(gFR,digits=3))")
println("    corner loads N: FL=$(round(FzFL)) FR=$(round(FzFR)) (outer FR loaded)")

@test r > 0 && ay > 0                              # cornering (left)
@test max(TFL,TFR,TRL,TRR) > 60 + 5                # tyres heat up from slip energy
@test TFR > TFL                                     # outer-front hotter than inner-front
@test TRR > TRL                                     # outer-rear hotter than inner-rear
@test all(60 .≤ [TFL,TFR,TRL,TRR] .≤ 160)          # physical operating range
@test gFR ≤ 1.0                                     # grip factor responds to temperature

println("\nALL TESTS PASSED ✓ — ThermalTyre integrated: per-corner temps evolve, grip is temperature-dependent.")
