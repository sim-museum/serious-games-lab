# Real-time driving adapter for the MTK vehicle — drives DrivenVehicleRT with live
# inputs and tracks world position, exposing a CarState-like object the native
# renderer can place on a track.  Steps in <0.1 ms (see test/benchmark_rt.jl), so
# it runs far inside a 60 Hz frame.
#
# DrivenVehicleRT now has a slipping-clutch + idle engine model, so it launches
# from a true standing start (engine idles with the clutch open; throttle revs it
# and the clutch progressively engages).  Low-speed slip is regularised.

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
const FINAL    = 4.11
const MAXSTEER = 0.30                               # road-wheel angle at full lock [rad]
const RW_R     = 0.33

mutable struct Car
    sys; integ
    s_thr; s_brk; s_st; s_gr; s_clu                 # parameter setters
    getall                                          # batched observed getter (compiled once)
    gear::Int
    # CarState-like render fields
    x::Float64; y::Float64; z::Float64; θ::Float64
    v::Float64; t::Float64; rpm::Float64; gear_n::Int
    tc::NTuple{4,NTuple{3,Float64}}
    lapdist::Float64; laps::Int; lateral::Float64; along::Float64; ontrack::Bool
end

"Build the real-time car, spawned at world (x0,z0) heading θ0.  v0=0 ⇒ standing
start (engine idling, clutch open; throttle revs + engages it to launch)."
function build_car(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0)
    sys = mtkcompile(DrivenVehicleRT(name = :car))
    prob = ODEProblem(sys, [sys.u => v0, sys.ωf => v0/0.30, sys.ωr => v0/RW_R,
                            sys.ωe => 209.4, sys.X => x0, sys.Y => z0, sys.ψ => θ0], (0.0, 1e7))
    # CAPPED for real-time: dtmin + force_dtmin guarantee step!(dt) returns in bounded
    # time even in a stiff transient (it takes the floor step and advances rather than
    # subdividing forever → never freezes the render loop).  Looser tol = faster + robust.
    integ = init(prob, Rosenbrock23(); save_everystep = false, dense = false,
                 abstol = 1e-3, reltol = 1e-3, dtmin = 2e-5, force_dtmin = true, maxiters = 50_000)
    # one batched getter for all per-frame reads (compiled once → sub-ms steady state)
    getall = ModelingToolkit.getsym(sys, [sys.X, sys.Y, sys.ψ, sys.u, sys.v, sys.rpm,
        sys.FL.tyre.Fx, sys.FR.tyre.Fx, sys.RL.tyre.Fx, sys.RR.tyre.Fx,
        sys.FL.tyre.Fy, sys.FR.tyre.Fy, sys.RL.tyre.Fy, sys.RR.tyre.Fy, sys.ωr])
    c = Car(sys, integ, setp(sys, sys.throttle), setp(sys, sys.brake), setp(sys, sys.δ),
            setp(sys, sys.gear), setp(sys, sys.clutch), getall, 1,
            x0, 0.0, z0, θ0, v0, 0.0, 0.0, 1,
            ntuple(_ -> (0.0,0.0,0.0), 4), 0.0, 0, 0.0, 0.0, true)
    c.s_gr(c.integ, GEARS[c.gear]);  getall(integ)
    for _ in 1:3; step_car!(c, 0.3, 0.0, 0.0, 1/60); end                          # warm AUTO path
    for _ in 1:3; step_car!(c, 0.3, 0.0, 0.0, 1/60; clutch = 0.5, manual = true); end  # warm MANUAL path
    reinit!(c.integ); c.gear = 1; c.s_gr(c.integ, GEARS[1])                       # reset to spawn
    a = getall(c.integ)                                                           # refresh struct fields
    c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = sqrt(a[4]^2 + a[5]^2); c.rpm = a[6]  # (else stale warmup v
    c                                                                             #  spuriously engages the auto-clutch)
end

"Advance the car by dt.  throttle/brake/steer ∈ [0,1]/[0,1]/[-1,1]; `clutch` ∈ [0,1]
(0 engaged, 1 pressed); `up`/`dn` are one-frame shift events; `manual=true` ⇒ the
driver works the clutch + gears, else the adapter auto-clutches and auto-shifts."
function step_car!(c::Car, throttle, brake, steer, dt;
                   clutch = 0.0, up = false, dn = false, manual = false,
                   groundz = (x,z)->0.0)
    if manual                                        # driver clutch + manual gears
        c.s_clu(c.integ, clamp(clutch, 0, 1))
        up && c.gear < 5 && (c.gear += 1; c.s_gr(c.integ, GEARS[c.gear]))
        dn && c.gear > 1 && (c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]))
    else                                             # auto-clutch (slip in/out on throttle+motion)
        ae = clamp((c.rpm - 1400.0)/1000.0, 0, 1) * clamp(max(2*throttle, c.v/2), 0, 1)
        c.s_clu(c.integ, clamp(1.0 - ae, 0, 1))
    end
    c.s_thr(c.integ, clamp(throttle, 0, 1))
    c.s_brk(c.integ, clamp(brake, 0, 1))
    c.s_st(c.integ, clamp(steer, -1, 1) * MAXSTEER)
    step!(c.integ, max(dt, 1e-3), true)
    a = c.getall(c.integ)                            # [X,Y,ψ,u,v,rpm, 4×Fx, 4×Fy, ωr]
    c.x = a[1];  c.z = a[2];  c.θ = a[3]
    c.v = sqrt(a[4]^2 + a[5]^2);  c.t = c.integ.t
    c.rpm = clamp(a[6], 600.0, 9700.0);  c.gear_n = c.gear
    c.y = groundz(c.x, c.z)
    mg4 = 617.0*9.80665/4
    c.tc = ntuple(i -> (a[6+i]/mg4, a[10+i]/mg4, hypot(a[6+i], a[10+i])/mg4), 4)
    if !manual                                       # auto-shift on road-speed-implied rpm
        grpm = (a[4]/RW_R)*GEARS[c.gear]*FINAL*60/(2π)
        if grpm > 8500 && c.gear < 5;                       c.gear += 1; c.s_gr(c.integ, GEARS[c.gear])
        elseif grpm < 3400 && c.gear > 1 && throttle < 0.9; c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]); end
    end
    c
end

"Reset the car to its spawn position/state (R key)."
function respawn!(c::Car)
    reinit!(c.integ); c.gear = 1; c.s_gr(c.integ, GEARS[1])
    a = c.getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = a[4]; c.rpm = a[6]
    c
end

end # module
