# Validate combined-slip coupling (friction ellipse): sliding (κ) while cornering
# (α) trades lateral for longitudinal grip, resultant capped at μ·Fz; pure slip
# untouched.   Run:  julia --project=. test/test_combined_slip.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
const P  = TYRE_SKIDPAD_FRONT
const Fz = 2000.0
const μ  = P.μy            # μx == μy for this preset → ellipse is a circle of radius μ·Fz

println("="^70); println("1) friction ellipse: more κ steals Fy, resultant ≤ μ·Fz"); println("="^70)
α = deg2rad(8.0)                                   # near peak lateral
Fy_pure = tyre_fy(Fz, α; p = P)
println("   κ      Fx(N)    Fy(N)   |F|(N)   |F|/μFz   (Fy_pure=$(round(Fy_pure)) N)")
for κ in (0.0, 0.05, 0.10, 0.20, 0.30)
    Fx, Fy = tyre_forces(Fz, α, κ; p = P)
    res = hypot(Fx, Fy)
    println("  $(rpad(κ,5)) $(lpad(round(Fx),7)) $(lpad(round(Fy),7)) $(lpad(round(res),7))   $(round(res/(μ*Fz),digits=3))")
    @test res ≤ μ*Fz*1.01                          # never outside the ellipse
    @test Fy ≤ Fy_pure + 1e-6                       # combined lateral never exceeds pure
end
# note: Fy dips then recovers as κ grows past the longitudinal peak (Fx falls,
# freeing lateral grip) — correct combined-slip physics, not monotonic.
@test isapprox(tyre_forces(Fz, α, 0.0; p = P)[2], Fy_pure; rtol = 1e-9)   # κ=0 ⇒ pure Fy
@test tyre_forces(Fz, α, 0.05; p = P)[2] < Fy_pure                        # adding slip does steal grip

println("\n", "="^70); println("2) pure slip is untouched (one slip at a time ⇒ scale=1)"); println("="^70)
Fx_only = tyre_forces(Fz, 0.0, 0.15; p = P)[1]
Fy_only = tyre_forces(Fz, deg2rad(6), 0.0; p = P)[2]
println("  pure long Fx(κ=.15,α=0) = $(round(Fx_only)) N  vs tyre_fx = $(round(tyre_fx(Fz,0.15;p=P))) N")
println("  pure lat  Fy(α=6°,κ=0)  = $(round(Fy_only)) N  vs tyre_fy = $(round(tyre_fy(Fz,deg2rad(6);p=P))) N")
@test isapprox(Fx_only, tyre_fx(Fz, 0.15; p = P); rtol = 1e-9)
@test isapprox(Fy_only, tyre_fy(Fz, deg2rad(6); p = P); rtol = 1e-9)

println("\n", "="^70); println("3) MTK Tyre applies the same coupling"); println("="^70)
function Combo(; name)
    @named tyre = Tyre(; P...)
    vars = @variables d(t)=0.0
    eqs = [D(d) ~ 1.0, tyre.Fz ~ Fz, tyre.α ~ deg2rad(8.0), tyre.κ ~ 0.15]
    System(eqs, t, vars, []; systems = [tyre], name)
end
sys = mtkcompile(Combo(name = :c))
sol = solve(ODEProblem(sys, [], (0.0, 1.0)), Tsit5())
FxM = sol[sys.tyre.Fx][end]; FyM = sol[sys.tyre.Fy][end]; gcM = sol[sys.tyre.gc][end]
FxP, FyP = tyre_forces(Fz, deg2rad(8.0), 0.15; p = P)
println("  MTK  Fx=$(round(FxM)) Fy=$(round(FyM))  gc=$(round(gcM,digits=3))")
println("  pure Fx=$(round(FxP)) Fy=$(round(FyP))   (ellipse active: gc<1 = $(gcM<1))")
@test isapprox(FxM, FxP; rtol = 1e-5) && isapprox(FyM, FyP; rtol = 1e-5)
@test gcM < 1.0                                    # combined slip is actually biting here

println("\nALL TESTS PASSED ✓ — combined-slip friction ellipse coupled in tyre + MTK Tyre.")
