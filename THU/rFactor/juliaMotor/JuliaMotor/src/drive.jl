# Real-time, human-drivable vehicle: a world-space (X, Z, heading) integrator
# driven by live driver inputs (throttle / brake / steer / shift) instead of
# the autonomous racing-line controller of `simulate_lap`.
#
# This is the Phase 4.3 "drivable standalone" path: a human supplies the
# control loop, so the limit-handling autonomous driver (the open research
# item) is not on the critical path.  The per-step dynamics are the *same*
# validated bicycle model as `replay_inputs` (the capstone integrated-physics
# test): longitudinal accel with load transfer feeding the lateral tire
# loads, combined-slip derate on the driven rear, the calibrated TBC tires.
# Two things are added for free human driving:
#
#   * world pose — `replay_inputs` integrates only body state (v, β, r); here
#     we also carry (X, Z, θ) so the car drives over the actual track.  The
#     velocity vector points along θ + β; θ̇ = r (yaw rate).
#   * a low-speed kinematic steering blend — the dynamic bicycle model divides
#     by speed and degenerates as v → 0 (the singularity that traps the
#     autonomous driver).  Below `v_couple` we blend the yaw rate toward the
#     kinematic value v·tan(δ)/L and damp sideslip, so the car is controllable
#     from a standing start and through slow hairpins.  Above it the validated
#     dynamic model is unchanged.

"""
Live state of a human-driven car in world coordinates.

`x, z` are the world-plane position (m); `θ` the heading of the forward axis
(rad, forward = (cos θ, sin θ) in X–Z); `v` forward speed (m/s); `β` sideslip
(rad); `r` yaw rate (rad/s).  `y`, `ontrack`, `lapdist` are filled from the
track surface each step (diagnostics / lap timing).
"""
mutable struct CarState
    x::Float64
    z::Float64
    θ::Float64
    v::Float64
    β::Float64
    r::Float64
    gear::Int
    fuel::Float64
    rpm::Float64
    along::Float64       # last longitudinal accel (m/s²), for a g-meter
    y::Float64           # surface height under the car (m)
    ontrack::Bool
    lateral::Float64     # signed offset from the racing line (m)
    lapdist::Float64     # distance into the lap (m)
    t::Float64           # elapsed sim time (s)
    laps::Int
    # per-wheel traction circle (FL, FR, RL, RR), each (longitudinal, lateral,
    # radius) on a common scale (static corner weight mg/4): + long =
    # drive/accel, + lat = turning left, radius = that wheel's current grip
    # limit.  A dot at its own rim (|long,lat| = radius) is the tyre at the
    # friction-circle limit; the radius shrinks as the wheel unloads.
    tc::NTuple{4,NTuple{3,Float64}}
end

"""Driver inputs for one step: pedals in [0,1], `steer` in [-1,1] (fraction of
the steering lock, + = left), and discrete shift requests."""
Base.@kwdef struct DriveInput
    throttle::Float64 = 0.0
    brake::Float64 = 0.0
    steer::Float64 = 0.0
    clutch::Float64 = 0.0          # 1 = disengaged (coast, no drive)
    shift_up::Bool = false
    shift_down::Bool = false
    autoshift::Bool = true
end

"""A car the human drives: the physics model plus its fixed setup constants
(steering lock, the track surfaces for height/grade and lap timing)."""
struct DriveCar
    model::VehicleModel
    ts::TrackSurface                       # AIW ribbon: on-track, lateral, lapdist
    terrain::Union{Nothing,TriangleHAT}    # collision mesh: height + grade
    max_steer::Float64                     # steering lock (rad)
    v_couple::Float64                      # low-speed kinematic-blend threshold (m/s)
end

function DriveCar(model::VehicleModel, aiw;
                  terrain::Union{Nothing,TriangleHAT}=nothing,
                  max_steer::Real=0.35, v_couple::Real=8.0)
    DriveCar(model, TrackSurface(aiw), terrain, Float64(max_steer),
             Float64(v_couple))
end

"""
    spawn(car; fuel=40.0, waypoint=1) -> CarState

Place the car at rest on the racing line at `waypoint`, heading along the
track tangent there.  Used at startup and on respawn after a crash/off.
"""
function spawn(car::DriveCar; fuel::Real=40.0, waypoint::Integer=1, v0::Real=0.0)
    ts = car.ts
    n = length(ts.pos)
    i = mod1(waypoint, n)
    j = mod1(i + 1, n)
    p = ts.pos[i]
    θ = atan(ts.pos[j][3] - p[3], ts.pos[j][1] - p[1])
    cs = CarState(p[1], p[3], θ, Float64(v0), 0.0, 0.0, 1, Float64(fuel),
                  0.0, 0.0, p[2], true, 0.0, ts.lapdist[i], 0.0, 0,
                  ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0),
                   (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)))
    survey!(cs, car)
    cs
end

# fill surface height / on-track / lateral / lapdist from the track surfaces
function survey!(cs::CarState, car::DriveCar)
    h = hat(car.ts, cs.x, cs.z)
    if h.found
        cs.ontrack = h.on_track
        cs.lateral = h.lateral
        cs.lapdist = h.lapdist
    end
    if car.terrain !== nothing
        y, _, found = hat3d(car.terrain, cs.x, cs.z; ref=cs.y + 2.0)
        found && (cs.y = y)
    elseif h.found
        cs.y = h.height
    end
    cs
end

# surface grade (rise/run) in the travel direction, from the collision mesh
function travel_grade(car::DriveCar, x, z, θ, yref)
    car.terrain === nothing && return 0.0
    tx, tz = cos(θ), sin(θ)
    h1, _, f1 = hat3d(car.terrain, x - 3tx, z - 3tz; ref=yref + 2.0)
    h2, _, f2 = hat3d(car.terrain, x + 3tx, z + 3tz; ref=yref + 2.0)
    (f1 && f2) ? (h2 - h1) / 6.0 : 0.0
end

"""
    drive_accel(m, v, gear, throttle, brake, fuel) -> (a, rpm)

Longitudinal accel for a *human* launch.  The validated `longitudinal_accel`
assumes a locked clutch (it derives RPM from wheel speed) — correct once
rolling, but it makes negative torque below idle, so the car cannot pull away
from rest (the engine table is −25 Nm at 0 RPM; idle is 1600).  Here, while
the wheel-geared RPM is below the throttle-demanded engine speed, the clutch
slips: the engine turns at `rpm_demand` (idle rising to ~4800 with throttle),
its inertia decoupled from the driveline.  Once the wheels catch up
(`geared ≥ rpm_demand`) the clutch locks and we hand back to the validated
model — continuous at the lock point (same RPM, same torque).
"""
function drive_accel(m::VehicleModel, v::Real, gear::Integer, throttle::Real,
                     brake::Real, clutch::Real, fuel::Real)
    (clutch > 0.5 || brake > throttle || gear < 1) &&
        return longitudinal_accel(m, v, gear, throttle, fuel; brake=brake, clutch=clutch)
    geared = engine_rpm(m.dt, gear, max(v, 0.0) / m.radius)
    rpm_demand = m.eng.idle_lo + clamp(throttle, 0.0, 1.0) * (4800.0 - m.eng.idle_lo)
    geared >= rpm_demand &&
        return longitudinal_accel(m, v, gear, throttle, fuel; brake=brake)
    # clutch slipping: engine held at rpm_demand, engine inertia decoupled
    mt = mass(m, fuel)
    resist = m.drag_k * v^2 + m.loss_const
    f = engine_torque(m.eng, rpm_demand, throttle) * m.dt.totals[gear] / m.radius
    effmass = mt + 4 * 1.25 / m.radius^2
    ((f - resist) / effmass, rpm_demand)
end

"""
    step!(cs, car, input; dt) -> cs

Advance the human-driven car by `dt` seconds under `input`, in place.  Uses
the validated bicycle dynamics with longitudinal load transfer, combined-slip
rear derate and the calibrated tires (identical to `replay_inputs`), plus
world-pose integration and the low-speed kinematic blend.  `dt` is sub-stepped
at ≤5 ms for stability when the caller's frame is long.
"""
function step!(cs::CarState, car::DriveCar, input::DriveInput; dt::Real)
    m = car.model
    L = m.wheelbase
    a = L * m.rear_frac          # CG → front axle
    b = L - a
    δ = clamp(input.throttle >= 0 ? input.steer : input.steer, -1.0, 1.0) * car.max_steer

    # gear: manual shift requests, or an automatic up/down on RPM band
    if input.shift_up && cs.gear < ngears(m.dt)
        cs.gear += 1
    elseif input.shift_down && cs.gear > 1
        cs.gear -= 1
    elseif input.autoshift
        if cs.rpm > 7400 && cs.gear < ngears(m.dt)
            cs.gear += 1
        elseif cs.rpm < 3500 && cs.gear > 1
            cs.gear -= 1
        end
    end

    nsub = max(1, ceil(Int, dt / 0.005))
    h = dt / nsub
    grade = travel_grade(car, cs.x, cs.z, cs.θ, cs.y)
    for _ in 1:nsub
        mt = mass(m, cs.fuel)
        along, rpm = drive_accel(m, cs.v, cs.gear, input.throttle,
                                 input.brake, input.clutch, cs.fuel)
        along -= 9.81 * grade                       # gravity along the slope
        cs.rpm = rpm

        # longitudinal load transfer onto the lateral tire loads (validated
        # bicycle core — unchanged)
        dW = mt * along * m.cg_h / L
        Fzf = max(mt * 9.81 * (1 - m.rear_frac) - dW, 0.0)
        Fzr = max(mt * 9.81 * m.rear_frac + dW, 0.0)
        vv = max(cs.v, 3.0)
        αf = δ - atan(cs.β + a * cs.r / vv)
        αr = -atan(cs.β - b * cs.r / vv)
        Fyf = lateral_force(m.tire_f, sin(αf), Fzf, vv)
        fx = max(along * mt, 0.0)
        capr = peak_mu_long(m.tire_r, Fzr / 2) * Fzr
        der = capr > 1 ?
            max(0.0, 1 - (min(fx, 0.92capr) / capr)^2)^LATERAL_CAL.slip_exponent : 1.0
        Fyr = der * lateral_force(m.tire_r, sin(αr), Fzr, vv)

        # ---- four-corner resolution (lateral transfer gains validated against
        # the measured per-corner Tire Load / Lat Force channels; see
        # LOAD4_CAL).  The validated axle loads Fzf/Fzr are split L/R by the
        # data-fitted lateral-transfer gains (kf/kr) — keeping fl+fr = Fzf so
        # the split stays consistent with the validated dynamics — and each
        # axle's lateral force is distributed L/R by the corner's grip capacity
        # μ_lat(Fz)·Fz (reproducing the measured 67/33 outer/inner split at
        # 0.4 g).  The axle force is limited to the sum of the two corners'
        # capacities: the inside-wheel-lift grip ceiling, which only binds when
        # a wheel unloads (a kerb, the grass, a lifted inside wheel) — beyond
        # the symmetric envelope the telemetry covers, so the validated
        # dynamics are untouched in normal driving.
        ay = (Fyf * cos(δ) + Fyr) / mt
        dFf = LOAD4_CAL.kf * mt * ay             # front L/R transfer (outer +)
        dFr = LOAD4_CAL.kr * mt * ay
        fl4 = max(Fzf / 2 - dFf / 2, 0.0); fr4 = max(Fzf / 2 + dFf / 2, 0.0)
        rl4 = max(Fzr / 2 - dFr / 2, 0.0); rr4 = max(Fzr / 2 + dFr / 2, 0.0)
        cFL = peak_mu_lat(m.tire_f, fl4) * fl4; cFR = peak_mu_lat(m.tire_f, fr4) * fr4
        cRL = peak_mu_lat(m.tire_r, rl4) * rl4; cRR = peak_mu_lat(m.tire_r, rr4) * rr4
        Fyf = clamp(Fyf, -(cFL + cFR), cFL + cFR)
        Fyr = clamp(Fyr, -(cRL + cRR), cRL + cRR)

        rdot = (a * Fyf * cos(δ) - b * Fyr) / m.iz
        βdot = (Fyf * cos(δ) + Fyr) / (mt * vv) - cs.r
        r_dyn = cs.r + h * rdot
        β_dyn = cs.β + h * βdot

        # low-speed kinematic blend: as v → 0 the dynamic model degenerates
        # (÷v).  Blend toward kinematic steering so the car stays controllable
        # from a standstill; weight → 0 above v_couple (dynamics untouched).
        w = clamp((car.v_couple - cs.v) / car.v_couple, 0.0, 1.0)
        r_kin = cs.v * tan(δ) / L
        β_kin = atan(b * tan(δ) / L)
        cs.r = (1 - w) * r_dyn + w * r_kin
        cs.β = clamp((1 - w) * β_dyn + w * β_kin, -1.5, 1.5)
        cs.v = max(cs.v + h * along, 0.0)
        cs.along = along

        # per-wheel traction-circle coordinates (for the cockpit instrument
        # panel).  The (capped) axle lateral force and the longitudinal force
        # are each distributed L/R by the corner's grip capacity, so the outer
        # loaded wheel genuinely carries more — FL ≠ FR, RL ≠ RR.  Longitudinal
        # is the drive force on the rear when accelerating (split by rear grip,
        # the loaded-wheel / diff effect), or the brake force split front/rear
        # by bias then L/R by grip when decelerating.  Each wheel reports
        # (long, lat, radius) on a COMMON scale (the static corner weight
        # mg/4), so the dots and the friction-circle radii are directly
        # comparable: the loaded outer wheel shows a larger circle AND a longer
        # vector; a lifted inner wheel shrinks to nothing.  A dot at its own
        # rim (|long,lat| = radius) is that tyre at the grip limit.
        sF = cFL + cFR + 1e-9; sR = cRL + cRR + 1e-9
        fyFL = Fyf * cFL / sF; fyFR = Fyf * cFR / sF
        fyRL = Fyr * cRL / sR; fyRR = Fyr * cRR / sR
        Flong = along * mt                       # total longitudinal force (N)
        if Flong >= 0                            # accel: drive on the rear
            fxFL = fxFR = 0.0
            fxRL = Flong * cRL / sR; fxRR = Flong * cRR / sR
        else                                     # braking: front/rear by bias
            biasF = m.brake_f / (m.brake_f + m.brake_r + 1e-9)
            FlF = Flong * biasF; FlR = Flong * (1 - biasF)
            fxFL = FlF * cFL / sF; fxFR = FlF * cFR / sF
            fxRL = FlR * cRL / sR; fxRR = FlR * cRR / sR
        end
        G0 = max(mt * 9.81 / 4, 1.0)             # common scale: static corner weight
        cs.tc = ((fxFL / G0, fyFL / G0, cFL / G0), (fxFR / G0, fyFR / G0, cFR / G0),
                 (fxRL / G0, fyRL / G0, cRL / G0), (fxRR / G0, fyRR / G0, cRR / G0))

        # world-pose kinematics: velocity points along θ + β, θ̇ = r
        course = cs.θ + cs.β
        cs.x += cs.v * cos(course) * h
        cs.z += cs.v * sin(course) * h
        cs.θ = atan(sin(cs.θ + cs.r * h), cos(cs.θ + cs.r * h))
    end
    cs.fuel = max(0.0, cs.fuel - 0.0)        # fuel burn negligible over a session
    cs.t += dt

    prev_ld = cs.lapdist
    survey!(cs, car)
    # lap counter: lapdist wraps from near the end back to near the start
    (prev_ld > 0.75 * car.ts.lap_length && cs.lapdist < 0.25 * car.ts.lap_length) &&
        (cs.laps += 1)
    cs
end
