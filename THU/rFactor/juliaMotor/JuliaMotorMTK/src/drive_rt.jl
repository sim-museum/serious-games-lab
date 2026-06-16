# Real-time driving adapter for the MTK vehicle — drives DrivenVehicleRT with live
# inputs and tracks world position, exposing a CarState-like object the native
# renderer can place on a track.  Steps in <0.1 ms (see test/benchmark_rt.jl), so
# it runs far inside a 60 Hz frame.
#
# Note: DrivenVehicleRT is a handling model — it can't launch cleanly from a dead
# stop (slip-angle atan singularity at u=0), so spawn at a small rolling speed.

module DriveRT

using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t, D_nounits as D
const setp = ModelingToolkit.setp

const HERE = @__DIR__
for f in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","vehicle_rt.jl")
    include(joinpath(HERE, "components", f))
end

export Car, build_car, step_car!, respawn!

const GEARS    = [2.23, 1.72, 1.32, 1.09, 0.916]   # Lotus 49 gearbox
const MAXSTEER = 0.30                               # road-wheel angle at full lock [rad]
const RW_R     = 0.33

mutable struct Car
    sys; integ
    s_thr; s_brk; s_st; s_gr                        # parameter setters
    getall                                          # batched observed getter (compiled once)
    gear::Int
    # CarState-like render fields
    x::Float64; y::Float64; z::Float64; θ::Float64
    v::Float64; t::Float64; rpm::Float64; gear_n::Int
    tc::NTuple{4,NTuple{3,Float64}}
    lapdist::Float64; laps::Int; lateral::Float64; along::Float64; ontrack::Bool
end

"Build the real-time car, spawned at world (x0,z0) heading θ0, rolling at v0."
function build_car(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 8.0)
    sys = mtkcompile(DrivenVehicleRT(name = :car))
    prob = ODEProblem(sys, [sys.u => v0, sys.ωf => v0/0.30, sys.ωr => v0/RW_R,
                            sys.X => x0, sys.Y => z0, sys.ψ => θ0], (0.0, 1e7))
    integ = init(prob, Rosenbrock23(); save_everystep = false, dense = false,
                 abstol = 1e-4, reltol = 1e-4)
    # one batched getter for all per-frame reads (compiled once → sub-ms steady state)
    getall = ModelingToolkit.getsym(sys, [sys.X, sys.Y, sys.ψ, sys.u, sys.v, sys.rpm,
        sys.FL.tyre.Fx, sys.FR.tyre.Fx, sys.RL.tyre.Fx, sys.RR.tyre.Fx,
        sys.FL.tyre.Fy, sys.FR.tyre.Fy, sys.RL.tyre.Fy, sys.RR.tyre.Fy])
    c = Car(sys, integ, setp(sys, sys.throttle), setp(sys, sys.brake), setp(sys, sys.δ),
            setp(sys, sys.gear), getall, 2,
            x0, 0.0, z0, θ0, v0, 0.0, 0.0, 2,
            ntuple(_ -> (0.0,0.0,0.0), 4), 0.0, 0, 0.0, 0.0, true)
    c.s_gr(c.integ, GEARS[c.gear])
    for _ in 1:5; step!(integ, 1/60, true); end     # warm up step! + getter (compile at load)
    getall(integ);  reinit!(integ)                  # then reset to the spawn state
    c
end

"Advance the car by dt with driver inputs (throttle, brake, steer ∈ [-1,1]).
`groundz(x,z)` returns track-surface elevation for rendering (default flat)."
function step_car!(c::Car, throttle, brake, steer, dt; groundz = (x,z)->0.0)
    s = c.sys
    # auto-shift on engine rpm
    if c.rpm > 8800 && c.gear < 5;     c.gear += 1; c.s_gr(c.integ, GEARS[c.gear]); end
    if c.rpm < 3600 && c.gear > 1 && throttle < 0.9; c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]); end
    c.s_thr(c.integ, clamp(throttle, 0, 1))
    c.s_brk(c.integ, clamp(brake, 0, 1))
    c.s_st(c.integ, clamp(steer, -1, 1) * MAXSTEER)
    step!(c.integ, max(dt, 1e-3), true)
    a = c.getall(c.integ)                            # [X,Y,ψ,u,v,rpm, 4×Fx, 4×Fy]
    c.x = a[1];  c.z = a[2];  c.θ = a[3]
    c.v = sqrt(a[4]^2 + a[5]^2);  c.t = c.integ.t
    c.rpm = clamp(a[6], 600.0, 9700.0);  c.gear_n = c.gear
    c.y = groundz(c.x, c.z)
    # traction circles: per-corner (long, lat, |F|) normalised to mg/4
    mg4 = 617.0*9.80665/4
    c.tc = ntuple(i -> (a[6+i]/mg4, a[10+i]/mg4, hypot(a[6+i], a[10+i])/mg4), 4)
    c
end

"Reset the car to its spawn position/state (R key)."
function respawn!(c::Car)
    reinit!(c.integ); c.gear = 2; c.s_gr(c.integ, GEARS[2])
    a = c.getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = a[4]; c.rpm = a[6]
    c
end

end # module
