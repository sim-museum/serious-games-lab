# Validate the thermal / pressure / camber extension (structural physics — the
# .ibt can't fit these; see tyre_thermal.jl).   Run: julia --project=. test/test_tyre_thermal.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D
include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "tyre_thermal.jl"))

println("="^70); println("1) grip multipliers: temperature & pressure curves"); println("="^70)
println("  μ_temp: 50°C=$(round(mu_temp(50),digits=3))  90°C(opt)=$(round(mu_temp(90),digits=3))  140°C=$(round(mu_temp(140),digits=3))")
println("  μ_press: 120kPa=$(round(mu_press(120),digits=3))  152kPa(opt)=$(round(mu_press(152),digits=3))  190kPa=$(round(mu_press(190),digits=3))")
@test mu_temp(90) > mu_temp(50)  && mu_temp(90) > mu_temp(140)   # peaks at optimal temp
@test mu_press(152) > mu_press(120) && mu_press(152) > mu_press(190)  # peaks at ref pressure
@test mu_temp(90) ≈ 1.0 && mu_press(152) ≈ 1.0

println("\n", "="^70); println("2) camber adds lateral thrust at fixed slip"); println("="^70)
function gripAt(; γ, T0=90.0, pk=152.0, name)
    @named ty = ThermalTyre(; γ=γ, pk=pk, T0=T0)
    vars = @variables d(t)=0.0
    eqs = [D(d)~1, ty.Fz~2000.0, ty.α~deg2rad(3.0), ty.κ~0.0, ty.v~30.0]
    System(eqs, t, vars, []; systems=[ty], name)
end
s0 = mtkcompile(gripAt(γ=0.0,  name=:g0))
sγ = mtkcompile(gripAt(γ=deg2rad(2.0), name=:gc))
Fy0 = solve(ODEProblem(s0, [], (0.0,0.1)), Tsit5())[s0.ty.Fy][1]
Fyγ = solve(ODEProblem(sγ, [], (0.0,0.1)), Tsit5())[sγ.ty.Fy][1]
println("  Fy at 3° slip:  no camber=$(round(Fy0)) N   +2° camber=$(round(Fyγ)) N   (Δ=$(round(Fyγ-Fy0)) N thrust)")
@test Fyγ > Fy0 + 20                                  # camber thrust adds lateral force

println("\n", "="^70); println("3) warmup: cold tyre heats under slip → grip rises toward optimal"); println("="^70)
function Warmup(; name)                                # sustained hard slip from cold
    @named ty = ThermalTyre(; T0=50.0)
    vars = @variables dum(t)=0.0
    eqs = [D(dum)~1, ty.Fz~2000.0, ty.α~deg2rad(7.0), ty.κ~0.0, ty.v~35.0]
    System(eqs, t, vars, []; systems=[ty], name)
end
w = mtkcompile(Warmup(name=:w))
sw = solve(ODEProblem(w, [], (0.0, 40.0)), Tsit5(); saveat=2.0)
T = sw[w.ty.T]; Fy = sw[w.ty.Fy]; gT = sw[w.ty.gT]
println("  T: $(round(T[1]))°C → $(round(T[end]))°C   grip factor gT: $(round(gT[1],digits=3)) → $(round(gT[end],digits=3))")
println("  Fy: $(round(Fy[1])) N → $(round(Fy[end])) N  (warming toward optimal raises grip)")
@test T[end] > T[1] + 20                               # it heats up from slip energy
@test 70 < T[end] < 130                                 # into the observed operating range
@test Fy[end] > Fy[1]                                   # grip rises as it warms toward Topt
@test gT[end] > gT[1]

println("\nALL TESTS PASSED ✓ — thermal (T state, grip vs temp), pressure, camber added to the tyre.")
