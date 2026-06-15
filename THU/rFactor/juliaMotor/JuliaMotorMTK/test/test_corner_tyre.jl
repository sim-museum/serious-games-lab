# Standalone validation of the first two components: Tyre (isothermal MF) and
# Corner (quarter-car ride).  Run:  julia --project=. test/test_corner_tyre.jl
using ModelingToolkit, OrdinaryDiffEq, Test
using ModelingToolkit: t_nounits as t, D_nounits as D

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "corner.jl"))

println("="^70)
println("1) Pure-Julia tyre lateral curve Fy(α) — saturation & load dependence")
println("="^70)
for Fz in (1500.0, 3000.0, 4500.0)
    αs = range(0, deg2rad(20); length = 400)
    fy = [tyre_fy(Fz, α) for α in αs]
    pk, i = findmax(fy)
    @test pk ≤ TYRE_DEFAULTS.μy * Fz * 1.001          # never exceeds μ·Fz
    @test pk ≥ TYRE_DEFAULTS.μy * Fz * 0.9            # but reaches near it
    @test fy[2] > fy[1]                                # rises from 0
    println("  Fz=$(Int(Fz)) N: peak Fy=$(round(pk)) N at α=$(round(rad2deg(αs[i]),digits=1))°  "*
            "(μ·Fz=$(round(TYRE_DEFAULTS.μy*Fz)) N, util=$(round(100*pk/(TYRE_DEFAULTS.μy*Fz)))%)")
end

println("\n", "="^70)
println("2) MTK Tyre component compiles and matches the pure law")
println("="^70)
function TyreSweep(; name, rate = deg2rad(3.0), Fzc = 3000.0)
    @named tyre = Tyre()
    ps = @parameters rate=rate Fzc=Fzc
    vars = @variables α(t)=0.0
    eqs = [D(α) ~ rate, tyre.Fz ~ Fzc, tyre.α ~ α, tyre.κ ~ 0.0]
    System(eqs, t, vars, ps; systems = [tyre], name)
end
sweep = mtkcompile(TyreSweep(name = :sweep))
prob  = ODEProblem(sweep, [], (0.0, 6.0))
sol   = solve(prob, Tsit5(); reltol = 1e-8, abstol = 1e-8)
maxerr = 0.0
for tt in range(0.5, 5.5; length = 11)
    αv  = sol(tt; idxs = sweep.α)
    fyM = sol(tt; idxs = sweep.tyre.Fy)
    fyP = tyre_fy(3000.0, αv)
    global maxerr = max(maxerr, abs(fyM - fyP))
end
println("  max |Fy_MTK − Fy_pure| over the sweep = $(round(maxerr, sigdigits = 3)) N")
@test maxerr < 1e-6
peakMz = maximum(abs, sol[sweep.tyre.Mz])
println("  peak |Mz| = $(round(peakMz, digits = 1)) N·m  (aligning moment from trail)")
@test peakMz > 0

println("\n", "="^70)
println("3) Corner quarter-car — 2 cm road step, settle to static load")
println("="^70)
function RideTest(; name, A = 0.02, t0b = 0.3, tau = 0.01)
    @named cor = Corner()
    ps = @parameters A=A t0b=t0b tau=tau
    eqs = [cor.zr ~ A*(1 + tanh((t - t0b)/tau))/2, cor.Fext ~ 0.0]
    System(eqs, t, Num[], ps; systems = [cor], name)
end
ride = mtkcompile(RideTest(name = :ride))
Fz0  = 1547.0 + 20.0*9.81
prob2 = ODEProblem(ride, [], (0.0, 3.0))
sol2  = solve(prob2, Rodas5P(); reltol = 1e-8, abstol = 1e-8)
Fz = sol2[ride.cor.Fz]
println("  static Fz (t=0)    = $(round(Fz[1], digits = 1)) N   (expect $(round(Fz0, digits = 1)) N)")
println("  peak Fz (transient)= $(round(maximum(Fz), digits = 1)) N")
println("  settled Fz (t=3s)  = $(round(Fz[end], digits = 1)) N")
@test isapprox(Fz[1],   Fz0; atol = 1.0)
@test isapprox(Fz[end], Fz0; atol = 5.0)
@test maximum(Fz) > Fz0 + 50          # the road step does load the tyre

# mode-frequency sanity (analytic)
ks, kt, m_s, m_u = 26_000.0, 180_000.0, 157.0, 20.0
f_body = sqrt(ks/m_s)/2π
f_hop  = sqrt((ks + kt)/m_u)/2π
println("  body ride mode ≈ $(round(f_body, digits = 2)) Hz, wheel-hop ≈ $(round(f_hop, digits = 1)) Hz")
@test 1.0 < f_body < 3.0
@test 10.0 < f_hop < 20.0

println("\nALL TESTS PASSED ✓")
