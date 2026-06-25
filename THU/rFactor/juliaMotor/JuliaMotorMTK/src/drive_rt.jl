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

export Car, build_car, step_car!, respawn!, telemetry, contain!

const GEARS    = [2.23, 1.72, 1.32, 1.09, 0.916]   # Lotus 49 gearbox (gear 1..5)
gearratio(g::Int) = g <= 0 ? 0.0 : GEARS[g]        # g=0 ⇒ NEUTRAL (ratio 0 ⇒ clutch decoupled, engine idles free)
const FINAL    = 4.11
const MAXSTEER = 0.30                               # road-wheel angle at full lock [rad]
const RW_R     = 0.33

mutable struct Car
    sys; integ
    s_thr; s_brk; s_st; s_gr; s_clu                 # parameter setters
    s_we                                            # engine-speed STATE setter (for restart after a stall)
    s_pos; s_vel                                    # world-position (X,Y) + body-velocity (u,v) STATE setters (boundary)
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
function build_car(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0, brush = !haskey(ENV, "JM_MAGIC"))
    sys = mtkcompile(DrivenVehicleRT(name = :car, brush = brush))   # physics brush by DEFAULT; JM_MAGIC ⇒ old Magic-Formula tyre
    println(brush ? "  TYRE: physics-based brush model (default; μ≈1.2, no fudge) — set JM_MAGIC=1 for the old fudged tyre" :
                    "  TYRE: Magic-Formula tyre (JM_MAGIC)")
    prob = ODEProblem(sys, [sys.u => v0, sys.ωf => v0/0.30, sys.ωr => v0/RW_R,
                            sys.ωe => 209.4, sys.X => x0, sys.Y => z0, sys.ψ => θ0], (0.0, 1e7))
    # FIXED-STEP for hard real-time guarantees: an adaptive solver can subdivide into
    # thousands of tiny steps in a stiff transient and freeze the render loop.  A fixed
    # step (Rosenbrock23 is L-stable, so it stays stable for the stiff wheel-slip/clutch
    # modes even at this rate) does a bounded number of substeps per frame — never hangs.
    integ = init(prob, Rosenbrock23(); save_everystep = false, dense = false,
                 adaptive = false, dt = 1/300)
    # one batched getter for all per-frame reads (compiled once → sub-ms steady state)
    getall = ModelingToolkit.getsym(sys, [sys.X, sys.Y, sys.ψ, sys.u, sys.v, sys.rpm,
        sys.FL.tyre.Fx, sys.FR.tyre.Fx, sys.RL.tyre.Fx, sys.RR.tyre.Fx,
        sys.FL.tyre.Fy, sys.FR.tyre.Fy, sys.RL.tyre.Fy, sys.RR.tyre.Fy, sys.ωr])
    c = Car(sys, integ, setp(sys, sys.throttle), setp(sys, sys.brake), setp(sys, sys.δ),
            setp(sys, sys.gear), setp(sys, sys.clutch), ModelingToolkit.setu(sys, sys.ωe),
            ModelingToolkit.setu(sys, [sys.X, sys.Y]), ModelingToolkit.setu(sys, [sys.u, sys.v]), getall, 1,
            x0, 0.0, z0, θ0, v0, 0.0, 0.0, 1,
            ntuple(_ -> (0.0,0.0,0.0), 4), 0.0, 0, 0.0, 0.0, true)
    c.s_gr(c.integ, GEARS[c.gear]);  getall(integ)
    for _ in 1:3; step_car!(c, 0.3, 0.0, 0.0, 1/60); end                          # warm AUTO path
    for _ in 1:3; step_car!(c, 0.3, 0.0, 0.0, 1/60; clutch = 0.5, manual = true); end  # warm MANUAL path
    reinit!(c.integ); c.gear = 0; c.s_gr(c.integ, 0.0)                            # spawn in NEUTRAL (like GPL/rF/iRacing)
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
    held = abs(c.v) < 1.0 && throttle < 0.05         # auto-hold at a standstill (AUTO mode only)
    if manual                                        # driver clutch + manual gears — NO auto-clutch.
        c.s_clu(c.integ, clamp(clutch, 0, 1))        # clutch is 100% the driver's: you must slip it
        up && c.gear < 5 && (c.gear += 1; c.s_gr(c.integ, gearratio(c.gear)))   # N→1→…→5
        dn && c.gear > 0 && (c.gear -= 1; c.s_gr(c.integ, gearratio(c.gear)))   # …→1→N
    else                                             # auto-clutch (slip in/out on throttle+motion)
        c.gear == 0 && (c.gear = 1; c.s_gr(c.integ, GEARS[1]))   # AUTO auto-engages 1st out of neutral
        ae = held ? 0.0 : clamp((c.rpm - 1400.0)/1000.0, 0, 1) * clamp(max(2*throttle, c.v/2), 0, 1)
        c.s_clu(c.integ, clamp(1.0 - ae, 0, 1))
    end
    c.s_thr(c.integ, clamp(throttle, 0, 1))
    c.s_brk(c.integ, clamp(brake, 0, 1))
    c.s_st(c.integ, clamp(steer, -1, 1) * MAXSTEER)
    step!(c.integ, max(dt, 1e-3), true)
    a = c.getall(c.integ)                            # [X,Y,ψ,u,v,rpm, 4×Fx, 4×Fy, ωr]
    c.x = a[1];  c.z = a[2];  c.θ = a[3]
    c.v = sqrt(a[4]^2 + a[5]^2);  c.t = c.integ.t
    c.rpm = clamp(a[6], 0.0, 9700.0);  c.gear_n = c.gear   # floor 0 so a STALLED engine reads ~0, not 600
    # rF1-style restart: a stalled engine fires back to idle the instant you disengage the drivetrain
    # (clutch pedal in, or shift to neutral). Otherwise a stall stays a stall.
    if c.rpm < 350.0 && (clamp(clutch, 0, 1) > 0.5 || c.gear == 0)
        c.s_we(c.integ, 209.44); c.rpm = 2000.0           # 209.44 rad/s = 2000 rpm idle
    end
    c.y = groundz(c.x, c.z)
    mg4 = 617.0*9.80665/4
    c.tc = ntuple(i -> (a[6+i]/mg4, a[10+i]/mg4, hypot(a[6+i], a[10+i])/mg4), 4)
    (!isfinite(c.v) || abs(c.v) > 110) && return respawn!(c)   # safety net: recover from any divergence
    if !manual && c.gear >= 1                         # auto-shift on road-speed-implied rpm
        grpm = (a[4]/RW_R)*GEARS[c.gear]*FINAL*60/(2π)
        if grpm > 8500 && c.gear < 5;                       c.gear += 1; c.s_gr(c.integ, GEARS[c.gear])
        elseif grpm < 3400 && c.gear > 1 && throttle < 0.9; c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]); end
    end
    c
end

"Extra physics observables for telemetry export (.ibt), beyond the per-frame
render fields: body velocities u (fwd), v (lat), yaw rate r, long/lat accel, and
front/rear wheel speeds.  The getter is compiled once per system and cached, so
this stays cheap when polled every tick.  Returns a NamedTuple."
const _TELCACHE = IdDict{Any,Any}()
function telemetry(c::Car)
    g = get!(_TELCACHE, c.sys) do
        ModelingToolkit.getsym(c.sys, [c.sys.u, c.sys.v, c.sys.r, c.sys.ax, c.sys.ay, c.sys.ωf, c.sys.ωr])
    end
    a = g(c.integ)
    (u = a[1], v = a[2], r = a[3], ax = a[4], ay = a[5], ωf = a[6], ωr = a[7])
end

"Snap the car onto the track boundary (xnew, znew) and bleed its speed — a
fence/hedge collision that keeps the car inside the game world (E7)."
function contain!(c::Car, xnew, znew; vdamp = 0.45)
    a = c.getall(c.integ)
    c.s_pos(c.integ, [xnew, znew])
    c.s_vel(c.integ, [a[4]*vdamp, a[5]*vdamp])           # u,v body velocities (getall idx 4,5) — fence scrubs speed
    c.x = xnew; c.z = znew; c.v = sqrt((a[4]*vdamp)^2 + (a[5]*vdamp)^2)
    c
end

"Reset the car to its spawn position/state (R key)."
function respawn!(c::Car)
    reinit!(c.integ); c.gear = 1; c.s_gr(c.integ, GEARS[1])
    a = c.getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = a[4]; c.rpm = a[6]
    c
end

end # module
