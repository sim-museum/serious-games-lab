# landing_convergence.jl — is the landing-g SPIKE physical or a numerical artifact?
# Launch the 3-D car straight up, land it on flat ground, and measure the peak
# VertAccel at progressively FINER solver substeps.  If the peak shrinks as dt→0
# it was a fixed-step/contact numerical overshoot (not a real force); if it
# CONVERGES, that value is the model's true physical prediction for these params.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/landing_convergence.jl

using Printf
using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t, D_nounits as D, setp, setu, getsym
const HERE = joinpath(@__DIR__, "..", "src", "components")
include(joinpath(HERE, "tyre.jl")); include(joinpath(HERE, "powertrain.jl")); include(joinpath(HERE, "vehicle_3d.jl"))
const G = 9.80665
sys = mtkcompile(DrivenVehicle3D(name = :car))

"Drop the car (whole-car up-velocity w0) onto flat ground; return peak VertAccel,
peak tyre load, and the work done by suspension dampers vs tyre dampers."
function landing(; w0 = 4.0, solver_dt = 1/300, frame = 1/600)
    prob = ODEProblem(sys, [sys.w => w0, sys.vuFL => w0, sys.vuFR => w0, sys.vuRL => w0, sys.vuRR => w0], (0.0, 1e6))
    integ = init(prob, Rosenbrock23(); save_everystep=false, dense=false, adaptive=false, dt=solver_dt)
    get = getsym(sys, [sys.az, sys.z, sys.FzFL, sys.FzFR, sys.FzRL, sys.FzRR])
    maxaz = 0.0; maxfz = 0.0
    for i in 1:round(Int, 1.5/frame)
        step!(integ, frame, true)
        a = get(integ)
        maxaz = max(maxaz, a[1]/G); maxfz = max(maxfz, a[3]+a[4]+a[5]+a[6])
    end
    (peakg = maxaz, peakFz = maxfz)
end

println("\n  Hard flat landing (launch 4 m/s up, land on flat ground)")
println("  solver dt    frame dt   peak VertAccel   peak ΣFz")
for sdt in (1/300, 1/600, 1/1200, 1/2400, 1/4800)
    r = landing(; w0 = 4.0, solver_dt = sdt, frame = sdt)
    @printf("  1/%-7d   1/%-6d   %7.2f g       %7.0f N\n", round(Int,1/sdt), round(Int,1/sdt), r.peakg, r.peakFz)
end
println("\n  → if peak g shrinks with finer dt = numerical overshoot at contact;")
println("    if it converges = the model's true physical landing for these stiffness/damping params.")
