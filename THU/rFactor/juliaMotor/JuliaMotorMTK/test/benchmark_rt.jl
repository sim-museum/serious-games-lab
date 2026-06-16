# Can the MTK vehicle step in REAL TIME for interactive driving?  Build the RT
# model, init an integrator, step at 60 Hz with live parameter updates, measure the
# real-time factor.   Run: julia --project=. test/benchmark_rt.jl
using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t, D_nounits as D
const setp = ModelingToolkit.setp
for fnm in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","vehicle_rt.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

println("compiling DrivenVehicleRT…")
sys = mtkcompile(DrivenVehicleRT(name = :rt))
println("  states: $(length(unknowns(sys)))")
u0 = 8.0
prob = ODEProblem(sys, [sys.u=>u0, sys.ωf=>u0/0.30, sys.ωr=>u0/0.33], (0.0, 1e6))

for (label, alg) in (("Rosenbrock23", Rosenbrock23()), ("FBDF", FBDF()), ("Rodas5P", Rodas5P()))
    integ = init(prob, alg; save_everystep=false, dense=false, abstol=1e-4, reltol=1e-4)
    sth = setp(sys, sys.throttle); sst = setp(sys, sys.δ); sbr = setp(sys, sys.brake)
    for _ in 1:20                                   # warmup (force compilation)
        sth(integ, 0.4); sst(integ, 0.02); step!(integ, 1/60, true)
    end
    dt = 1/60; nstep = 300
    t0 = time_ns()
    for i in 1:nstep
        sth(integ, 0.4); sst(integ, 0.03*sin(i/40)); sbr(integ, 0.0)
        step!(integ, dt, true)
    end
    wall = (time_ns() - t0)/1e9; sim = nstep*dt
    println("  $(rpad(label,12)) per-step $(round(wall/nstep*1000,digits=2)) ms  → real-time ×$(round(sim/wall,digits=1))  (need ≥1×, want ≥3× to leave room for rendering)")
end
println("\n  60 Hz frame budget = 16.7 ms.  If per-step ≪ that, interactive driving is feasible.")
