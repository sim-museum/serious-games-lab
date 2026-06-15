# Validate the Corner→Tyre coupling (tyre.Fz ~ corner.Fz): a road bump and a
# load-transfer Fext must flow through the suspension into the tyre's vertical
# load, and hence its grip.   Run:  julia --project=. test/test_corner_assembly.jl
using ModelingToolkit, OrdinaryDiffEq, Test, Statistics
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "corner.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "corner_assembly.jl"))

# front corner: cw 1376 N + ~20 kg unsprung; wheel-rate = MR²·k_spring ≈ 0.78²·30 N/mm
const CORNER_KW = (Fz_static = 1376.0 + 20.0*9.81, ks = 18_000.0, cs = 2_500.0,
                   m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 300.0)
const Fz_stat = CORNER_KW.Fz_static
const α0 = deg2rad(4.0)

println("="^70); println("1) static hold: corner load → tyre Fy matches the pure law"); println("="^70)
function RigStatic(; name)
    @named ca = CornerAssembly(corner = CORNER_KW, tyre = TYRE_SKIDPAD_FRONT)
    eqs = [ca.corner.zr ~ 0.0, ca.corner.Fext ~ 0.0, ca.tyre.α ~ α0, ca.tyre.κ ~ 0.0]
    System(eqs, t, Num[], []; systems = [ca], name)
end
s1 = mtkcompile(RigStatic(name = :s1))
sol1 = solve(ODEProblem(s1, [], (0.0, 2.0)), Rodas5P(); reltol = 1e-8, abstol = 1e-8)
Fz1 = sol1[s1.ca.corner.Fz][end];  Fy1 = sol1[s1.ca.tyre.Fy][end]
Fy_expect = tyre_fy(Fz_stat, α0; p = TYRE_SKIDPAD_FRONT)
println("  Fz=$(round(Fz1,digits=1)) N (static $(round(Fz_stat,digits=1)))   Fy=$(round(Fy1,digits=1)) N   pure law=$(round(Fy_expect,digits=1)) N")
@test isapprox(Fz1, Fz_stat; atol = 1.0)
@test isapprox(Fy1, Fy_expect; rtol = 1e-4)

println("\n", "="^70); println("2) road bump: tyre load and grip rise together"); println("="^70)
function RigBump(; name)
    @named ca = CornerAssembly(corner = CORNER_KW, tyre = TYRE_SKIDPAD_FRONT)
    ps = @parameters A=0.03 t0b=0.4 tau=0.02
    eqs = [ca.corner.zr ~ A*(1 + tanh((t - t0b)/tau))/2, ca.corner.Fext ~ 0.0,
           ca.tyre.α ~ α0, ca.tyre.κ ~ 0.0]
    System(eqs, t, Num[], ps; systems = [ca], name)
end
s2 = mtkcompile(RigBump(name = :s2))
sol2 = solve(ODEProblem(s2, [], (0.0, 2.0)), Rodas5P(); reltol = 1e-8, abstol = 1e-8)
Fz2 = sol2[s2.ca.corner.Fz];  Fy2 = sol2[s2.ca.tyre.Fy]
ρ = cor(Fz2, Fy2)
println("  Fz range $(round(minimum(Fz2)))..$(round(maximum(Fz2))) N   Fy range $(round(minimum(Fy2)))..$(round(maximum(Fy2))) N")
println("  corr(Fz, Fy) over the transient = $(round(ρ, digits=4))   (load flows to grip;")
println("    <1 because Fy(Fz) is sublinear over the 4× load swing — load sensitivity pKy2)")
@test maximum(Fz2) > Fz_stat + 200       # the bump loads the tyre
@test ρ > 0.9                             # Fy strongly tracks Fz at fixed slip

println("\n", "="^70); println("3) load transfer (Fext): more load → more grip, with load sensitivity"); println("="^70)
function RigFext(; name)
    @named ca = CornerAssembly(corner = CORNER_KW, tyre = TYRE_SKIDPAD_FRONT)
    ps = @parameters dF=-3000.0 tr=1.0   # ramp to −3000 N (downward = outer wheel)
    eqs = [ca.corner.zr ~ 0.0, ca.corner.Fext ~ dF*clamp((t - 0.3)/tr, 0.0, 1.0),
           ca.tyre.α ~ α0, ca.tyre.κ ~ 0.0]
    System(eqs, t, Num[], ps; systems = [ca], name)
end
s3 = mtkcompile(RigFext(name = :s3))
sol3 = solve(ODEProblem(s3, [], (0.0, 2.5)), Rodas5P(); reltol = 1e-8, abstol = 1e-8)
Fz3 = sol3[s3.ca.corner.Fz];  Fy3 = sol3[s3.ca.tyre.Fy]
glo, ghi = Fy3[1]/Fz3[1], Fy3[end]/Fz3[end]
println("  low load:  Fz=$(round(Fz3[1])) N  Fy=$(round(Fy3[1])) N  Fy/Fz=$(round(glo,digits=3))")
println("  high load: Fz=$(round(Fz3[end])) N  Fy=$(round(Fy3[end])) N  Fy/Fz=$(round(ghi,digits=3))")
println("  → Fz≈Fz_static−Fext ($(round(Fz3[end])) vs $(round(Fz_stat+3000))); Fy up, but Fy/Fz down (load sensitivity, pKy2=$(TYRE_SKIDPAD_FRONT.pKy2))")
@test isapprox(Fz3[end], Fz_stat + 3000.0; atol = 30.0)   # Fz = Fz_static − Fext
@test Fy3[end] > Fy3[1]                                     # more load → more force
@test ghi < glo                                            # but normalised grip falls (load sensitivity)

println("\nALL TESTS PASSED ✓ — Corner.Fz → Tyre.Fz coupling closed.")
