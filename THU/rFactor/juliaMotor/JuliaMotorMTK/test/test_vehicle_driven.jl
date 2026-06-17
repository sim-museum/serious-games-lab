# Validate the full closed car: powertrain integrated, κ generated, combined slip
# engaging mid-corner.   Run: julia --project=. test/test_vehicle_driven.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

for f in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","vehicle_driven.jl")
    include(joinpath(@__DIR__, "..", "src", "components", f))
end

println("compiling the full driven vehicle…")
function TrailBrake(; name)         # hard braking into a hard corner → front tyres at the limit
    @named car = DrivenVehicle()
    eqs = [car.δ        ~ 0.060*clamp((t-0.3)/0.5, 0.0, 1.0),
           car.throttle ~ 0.0,
           car.brake    ~ 0.40*clamp((t-0.3)/0.5, 0.0, 1.0),
           car.gear     ~ 1.32]
    System(eqs, t, Num[], []; systems = [car], name)
end
sys = mtkcompile(TrailBrake(name = :tb))
println("  states: $(length(unknowns(sys)))")
prob = ODEProblem(sys, [sys.car.u => 42.0, sys.car.ωf => 140.0, sys.car.ωr => 127.3], (0.0, 2.0))
sol  = solve(prob, FBDF(); reltol = 1e-6, abstol = 1e-6)
@test Symbol(sol.retcode) == :Success

# combined-slip activation: with both κ and α present, the force vector tilts off the pure-
# lateral axis, so the lateral-force fraction sinα/σ drops below 1 (longitudinal slip steals
# lateral grip).  Scan the trajectory for the strongest coupling (min lateral fraction).
corners = (sys.car.FL, sys.car.FR, sys.car.RL, sys.car.RR)
latfracmin = minimum(minimum(abs.(sin.(sol[c.tyre.α])) ./ sol[c.tyre.σ]) for c in corners)
tt = 1.5
u  = sol(tt; idxs = sys.car.u);  ay = sol(tt; idxs = sys.car.ay);  ax = sol(tt; idxs = sys.car.ax);  r = sol(tt; idxs = sys.car.r)
κFL = sol(tt; idxs = sys.car.FL.tyre.κ);  αFL = sol(tt; idxs = sys.car.FL.tyre.α)
latfrac = [abs(sin(sol(tt; idxs = c.tyre.α))) / sol(tt; idxs = c.tyre.σ) for c in corners]
FzFL = sol(tt; idxs = sys.car.FL.corner.Fz); FzFR = sol(tt; idxs = sys.car.FR.corner.Fz)
FzRL = sol(tt; idxs = sys.car.RL.corner.Fz); FzRR = sol(tt; idxs = sys.car.RR.corner.Fz)

println("\n  STATE at t=$(tt)s (trail-braking: brake 0.40 + δ 0.06 rad):")
println("    u=$(round(u,digits=1)) m/s   ax=$(round(ax/9.80665,digits=2)) g   ay=$(round(ay/9.80665,digits=2)) g   |a|=$(round(hypot(ax,ay)/9.80665,digits=2)) g")
println("    front tyre: slip ratio κ=$(round(κFL,digits=3)) (braking)  slip angle α=$(round(rad2deg(αFL),digits=2))°  ⇒ BOTH nonzero")
println("    lateral-force fraction sinα/σ: FL=$(round(latfrac[1],digits=3)) FR=$(round(latfrac[2],digits=3)) RL=$(round(latfrac[3],digits=3)) RR=$(round(latfrac[4],digits=3))   min over run=$(round(latfracmin,digits=3))")
println("    corner loads N: FL=$(round(FzFL)) FR=$(round(FzFR)) | RL=$(round(FzRL)) RR=$(round(FzRR))  (front loaded by braking)")

@test r > 0 && ay > 0                                  # it corners
@test ax < -0.4*9.80665                                # and brakes
@test κFL < -0.01                                       # front braking slip (negative κ)
@test abs(rad2deg(αFL)) > 0.3                           # and a slip angle (cornering)
@test latfracmin < 0.99                                 # COMBINED SLIP engages (longitudinal slip steals lateral grip)
@test FzFL+FzFR > FzRL+FzRR                             # braking loads the front axle
@test 5000 < FzFL+FzFR+FzRL+FzRR < 7600                # vertical load ≈ m·g (+ longitudinal transfer)

println("\nALL TESTS PASSED ✓ — full driven car: brake→κ, steer→α, combined slip engages in trail-braking.")
