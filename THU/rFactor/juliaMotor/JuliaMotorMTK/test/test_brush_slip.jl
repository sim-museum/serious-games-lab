# Validate the PHYSICS-BASED brush tyre's combined slip (the friction ELLIPSE).
# The Magic Formula had a known combined-slip bug (it used the lateral curve for the
# longitudinal force too — see the test_combined_slip:34 open item); the brush fixes
# it structurally by carrying a separate stiffness AND friction per axis.   Run:
#   julia --project=. test/test_brush_slip.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))   # brings in brush_tyre.jl + BrushTyre
const P  = BRUSH_REAR
const Fz = 2000.0

println("="^70); println("1) friction ELLIPSE: (Fx/μxFz)² + (Fy/μyFz)² ≤ 1 (anisotropic μx≠μy)"); println("="^70)
α = deg2rad(8.0); Fy_pure = brush_fy(Fz, α; p = P)
println("   κ      Fx(N)    Fy(N)   ellipse-norm   (Fy_pure=$(round(Fy_pure)) N)")
for κ in (0.0, 0.05, 0.10, 0.20, 0.40)
    Fx, Fy = brush_forces(Fz, α, κ; p = P)
    enorm = (Fx/(P.μx*Fz))^2 + (Fy/(P.μ*Fz))^2
    println("  $(rpad(κ,5)) $(lpad(round(Fx),7)) $(lpad(round(Fy),7))   $(round(enorm,digits=3))")
    @test enorm ≤ 1.02                                 # never outside the friction ellipse
    @test Fy ≤ Fy_pure + 1e-6                           # combined lateral never exceeds pure
end
@test brush_forces(Fz, α, 0.10; p = P)[2] < Fy_pure    # adding longitudinal slip steals lateral grip

println("\n", "="^70); println("2) per-axis CONSISTENCY (the bug the Magic Formula fails)"); println("="^70)
Fx_only = brush_forces(Fz, 0.0, 0.15; p = P)[1]
Fy_only = brush_forces(Fz, deg2rad(6), 0.0; p = P)[2]
println("  pure long Fx(κ=.15,α=0) = $(round(Fx_only)) N  vs brush_fx = $(round(brush_fx(Fz,0.15;p=P))) N")
println("  pure lat  Fy(α=6°,κ=0)  = $(round(Fy_only)) N  vs brush_fy = $(round(brush_fy(Fz,deg2rad(6);p=P))) N")
@test isapprox(Fx_only, brush_fx(Fz, 0.15; p = P);        rtol = 1e-4)   # longitudinal uses μx/Cκ, NOT borrowed
@test isapprox(Fy_only, brush_fy(Fz, deg2rad(6); p = P);  rtol = 1e-4)   # lateral uses μy/Cα

println("\n", "="^70); println("3) the MTK BrushTyre component matches the pure law"); println("="^70)
function Combo(; name)
    @named tyre = BrushTyre(; P...)
    vars = @variables d(t)=0.0
    eqs = [D(d) ~ 1.0, tyre.Fz ~ Fz, tyre.α ~ deg2rad(8.0), tyre.κ ~ 0.15]
    System(eqs, t, vars, []; systems = [tyre], name)
end
sys = mtkcompile(Combo(name = :c))
sol = solve(ODEProblem(sys, [], (0.0, 1.0)), Tsit5())
FxM = sol[sys.tyre.Fx][end]; FyM = sol[sys.tyre.Fy][end]
FxP, FyP = brush_forces(Fz, deg2rad(8.0), 0.15; p = P)
println("  MTK  Fx=$(round(FxM)) Fy=$(round(FyM))    pure Fx=$(round(FxP)) Fy=$(round(FyP))")
@test isapprox(FxM, FxP; rtol = 1e-4) && isapprox(FyM, FyP; rtol = 1e-4)

println("\nALL TESTS PASSED ✓ — brush combined slip: friction ellipse + per-axis consistency (fixes the Magic-Formula coupling bug).")
