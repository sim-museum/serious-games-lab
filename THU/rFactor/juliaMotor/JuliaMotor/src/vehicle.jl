# Whole-vehicle assembly (Phase 2 start): every parameter comes from the
# parsed rFactor files, plus the two empirically pinned constants from the
# Phase 1 benches (drag convention, constant loss term).

"""
Longitudinal vehicle model assembled from a `RFactorData.Vehicle`.

Calibration state (see project README):
  * `drag_k` — aero drag F = drag_k·v²; from the validated CdA convention
    0.5·ρ·BodyDragBase (Zandvoort bench: fitted 0.168 vs nominal 0.196)
  * `loss_const` — constant resistive force (N); fitted 764 N across two
    tracks, attribution open (Phase 3)
"""
struct VehicleModel
    mass0::Float64            # HDV Mass (includes driver, excludes fuel)
    fuel_density::Float64     # kg/L; 0.74 validated by static tire loads
    tire_f::TBCTire
    tire_r::TBCTire
    eng::EngineModel
    dt::Drivetrain
    radius::Float64
    drag_k::Float64
    loss_const::Float64
    brake_f::Float64          # max brake torque per front wheel (Nm), bias applied
    brake_r::Float64
    brake_eff::Float64        # calibration knob: brake-temperature effectiveness
    rear_frac::Float64        # static weight fraction on the rear axle
    cg_h::Float64             # CGHeight
    wheelbase::Float64        # from the PM wheel centers
    iz::Float64               # yaw inertia, HDV Inertia[2] (+y up), excl. fuel
end

"""
Lateral calibration (Phase 3, fitted on the 2026-06-05 direct-steering
session).  Only the products `scale×τ` are identified by the yaw data
(0.488 front / 0.657 rear) — `scale` and `τ` trade off freely along that
invariant, but `scale` alone sets where the tyre reaches peak grip (the
peak-slip angle), which the yaw RMS barely sees.

Originally `scale` was left at 2.5, which put peak grip at ~18–27° of slip —
unrealistic, and it drove like ice with a vague, wandering front (the tyre
only bites at huge slip).  **Recalibrated 2026-06-08 to `scale = 1.0`** (the
honest no-stretch value: trust the TBC file's own peak-slip location, shape
only the pre-peak rise via τ), with τ raised to hold each axle's `scale×τ`:

    τ_front = 0.488, τ_rear = 0.657, lat_peak_scale = 1.0 (both axles),
    combined-slip exponent = 0.434

This moves the front peak to a realistic ~11° slip (sharp, faithful crossply
feel) AND improves the predictive capstone (inputs-alone) yaw RMS from 0.174
to 0.066 rad/s — `scale = 2.5` was overfit to the measured-load `replay_yaw`
harness and hurt the drivable model.  Peak grip is unchanged (μ_lat ≈ 1.0,
period-correct); `replay_yaw` (measured loads) stays 0.067 (was 0.059).
"""
const LATERAL_CAL = (tau_f=0.488, tau_r=0.657, peak_scale=1.0, slip_exponent=0.434)

"""
Four-corner load-transfer calibration (2026-06-08), fitted by least squares
against the *measured* per-corner `Tire Load - FL/FR/RL/RR` channels of the
2026-06-05 direct-steering session (29 354 usable samples):

    rear_frac = 0.528, h_eff = 0.50 m, kf = 0.2527, kr = 0.2144

`rear_frac` is the measured static split (the axle totals at zero g; the load
cells read it heavier-rear than the HDV's CGRear = 0.441).  `h_eff` is the
effective longitudinal CG height — the pitch transfer behaves like 0.50 m,
not the file's CGHeight 0.27 (suspension geometry / anti effects fold in).
`kf`/`kr` are the per-axle lateral-transfer gains: ΔFz across the axle =
k · m · a_lat, with the front carrying 54 % of roll.  The full model
reproduces the measured per-corner loads to 198 N RMS (~9.5 % of a ~2.1 kN
corner), and the grip-capacity force split it feeds (`peak_mu_lat·Fz` share)
reproduces the measured per-corner `Lat Force` channels unbiased at 7 % (front)
/ 12 % (rear) RMS — the measured outer front tyre carries 67 % of the axle's
cornering force at 0.4 g, which the split captures.

This drives the cockpit traction circles and the inside-wheel-lift grip
limit; the *body* dynamics stay the validated 2-axle model (a full
four-corner dynamic replacement over-fits — better fit, worse holdout — so
the data does not support it; see the capstone test).
"""
const LOAD4_CAL = (rear_frac=0.528, h_eff=0.50, kf=0.2527, kr=0.2144)

"""
    corner_loads(mt, along, ay, L) -> (FL, FR, RL, RR)

Per-corner vertical loads (N) from body mass `mt` (kg), longitudinal accel
`along` and lateral accel `ay` (m/s²) and wheelbase `L`, using `LOAD4_CAL`:
static split + longitudinal pitch transfer + lateral roll transfer.
`+along` (forward accel) loads the rear; `+ay` (left turn) loads the right
(outer) wheels.  Loads clamp at 0 (a lifted wheel).
"""
function corner_loads(mt::Real, along::Real, ay::Real, L::Real)
    c = LOAD4_CAL
    ftot = mt * 9.81 * (1 - c.rear_frac) - mt * along * c.h_eff / L
    rtot = mt * 9.81 * c.rear_frac       + mt * along * c.h_eff / L
    dF = c.kf * mt * ay
    dR = c.kr * mt * ay
    (max(ftot / 2 - dF / 2, 0.0), max(ftot / 2 + dF / 2, 0.0),
     max(rtot / 2 - dR / 2, 0.0), max(rtot / 2 + dR / 2, 0.0))
end

function VehicleModel(v::Vehicle; loss_const::Real=764.0, rho::Real=1.225,
                      brake_eff::Real=0.87, lateral_cal::Bool=true)
    g = section(v.hdv, "GENERAL")
    e = section(v.hdv, "ENGINE")
    # rev limit lives in the engine INI (HDV [ENGINE] can override)
    rl = get(e, "RevLimitRange", param(v.engine, "RevLimitRange", [1e5, 0.0, 0.0]))
    rl isa Number && (rl = [rl, 0.0])
    rls = get(e, "RevLimitSetting", param(v.engine, "RevLimitSetting", 0))
    revlimit = rl[1] + rls * rl[2]
    aero = section(v.hdv, "BODYAERO")
    base = get(aero, "BodyDragBase", 0.0)
    tf = lateral_cal ?
         TBCTire(v.tbc, :front; prepeak_tau=LATERAL_CAL.tau_f,
                 lat_peak_scale=LATERAL_CAL.peak_scale) :
         TBCTire(v.tbc, :front)
    tr = lateral_cal ?
         TBCTire(v.tbc, :rear; prepeak_tau=LATERAL_CAL.tau_r,
                 lat_peak_scale=LATERAL_CAL.peak_scale) :
         TBCTire(v.tbc, :rear)

    # brakes: per-wheel torque = corner BrakeTorque × axle bias × pressure
    # × brake_eff.  The bias convention (plain fraction, NOT renormalized
    # ×2, which would double the force) was pinned by the 2026-06-05 50 Hz
    # session.  brake_eff is the measured cold-drum effectiveness: 0.857 at
    # 100-250 °C rising to 0.911 at 250-400 °C (BrakeResponseCurve-style
    # temperature response, full curve = Phase 3 knob).
    ctrl = section(v.hdv, "CONTROLS")
    rear = setting_value(ctrl, "RearBrake", 0.5)
    press = min(1.0, setting_value(ctrl, "BrakePressure", 1.0))
    btf = get(section(v.hdv, "FRONTLEFT"), "BrakeTorque", 0.0)
    btr = get(section(v.hdv, "REARLEFT"), "BrakeTorque", 0.0)

    rear_frac = setting_value(g, "CGRear", 0.5)
    hubs = [body(v.pm, corner_wheel(v.pm, c)).pos[3] for c in (:fl, :rl)]
    VehicleModel(Float64(g["Mass"]), 0.74,
                 tf, tr,
                 EngineModel(v.engine; rev_limit=revlimit),
                 Drivetrain(v), tf.radius,
                 0.5 * rho * Float64(base), Float64(loss_const),
                 btf * (1 - rear) * press, btr * rear * press, Float64(brake_eff),
                 Float64(rear_frac), Float64(get(g, "CGHeight", 0.3)),
                 abs(hubs[2] - hubs[1]),
                 Float64(get(g, "Inertia", [0.0, 0.0, 0.0])[2]))
end

"""Resolve an HDV `<name>Range`/`<name>Setting` pair to its value.
Range semantics are `(start, step, count)` with valid settings 0..count-1;
out-of-range settings clamp (verified: the Vanwall ships SteerLockSetting=6
against a count of 6, and the in-game garage shows the clamped setting 5)."""
function setting_value(sec, name::AbstractString, default)
    rng = get(sec, name * "Range", nothing)
    rng === nothing && return default
    rng isa Number && (rng = [rng, 0.0, 1.0])
    setting = get(sec, name * "Setting", 0)
    count = length(rng) >= 3 && rng[3] isa Number ? Int(rng[3]) : 0
    count >= 1 && (setting = clamp(setting, 0, count - 1))
    rng[1] + setting * rng[2]
end

Base.show(io::IO, m::VehicleModel) =
    print(io, "VehicleModel(", m.mass0, " kg + fuel, ", ngears(m.dt), " gears, ",
          round(peak_power(m.eng)[1] / 745.7; digits=0), " hp)")

mass(m::VehicleModel, fuel_l::Real) = m.mass0 + fuel_l * m.fuel_density

"""Effective inertial mass in a gear: vehicle + rotating parts referred to
the contact patch (engine through the squared total ratio, 4 wheels)."""
function effective_mass(m::VehicleModel, fuel_l::Real, gear::Integer)
    mr = (m.eng.inertia * m.dt.totals[gear]^2 + 4 * 1.25) / m.radius^2
    mass(m, fuel_l) + mr
end

"""
    longitudinal_accel(m, v, gear, throttle, fuel_l; brake=0.0) -> (a, rpm)

Forward longitudinal model on a flat road, clutch engaged: speed determines
RPM through the gearing; engine torque from the logged throttle; brake force
torque-limited per the validated bias convention (this car never reaches
the tire's braking grip); resistances from the calibrated terms.
`gear == 0` (neutral / mid-shift) coasts.
"""
function longitudinal_accel(m::VehicleModel, v::Real, gear::Integer,
                            throttle::Real, fuel_l::Real; brake::Real=0.0,
                            clutch::Real=0.0)
    mt = mass(m, fuel_l)
    resist = m.drag_k * v^2 + m.loss_const
    engaged = gear != 0 && clutch < 0.5

    # brake force per axle: torque-limited, capped by the tire's braking
    # grip at the load-transferred axle loads (fixed-point on the transfer;
    # lockup at an unloading axle is what limits this car's late braking)
    fbrake = 0.0
    if brake > 0 && v > 0.5
        ped = clamp(brake, 0, 1) * m.brake_eff
        a = -7.0   # transfer iteration seed
        for _ in 1:3
            dW = mt * a * m.cg_h / m.wheelbase     # a<0: load to the front
            fzf = mt * 9.81 * (1 - m.rear_frac) - dW
            fzr = mt * 9.81 * m.rear_frac + dW
            ff = min(2 * m.brake_f * ped / m.radius, peak_mu_long(m.tire_f, fzf / 2) * fzf)
            fr = min(2 * m.brake_r * ped / m.radius, peak_mu_long(m.tire_r, fzr / 2) * fzr)
            fbrake = ff + fr
            a = -(fbrake + resist) / mt
        end
    end

    engaged || return ((-resist - fbrake) / mt, 0.0)
    rpm = engine_rpm(m.dt, gear, v / m.radius)
    f = engine_torque(m.eng, rpm, throttle) * m.dt.totals[gear] / m.radius
    ((f - resist - fbrake) / effective_mass(m, fuel_l, gear), rpm)
end

"""
    replay_yaw(m, t, steer, v, loads, fuel; yaw0, drive=…) -> Vector{Float64}

Phase 2 lateral machinery: forward 2-DOF (sideslip, yaw-rate) replay
driven by logged front-wheel steer angle (rad), speed (m/s), per-corner
tire loads `(fl, fr, rl, rr)` and fuel.  `drive` (driven-axle longitudinal
force per sample, N) feeds the continuous combined-slip derate of the
rear; build it with `drive_force_trace`.  Anchor at a straight so
`beta0 = 0` holds.  States are clamped to physical bounds so divergent
excursions (spins, airborne wheels) cannot produce NaNs.

Status (2026-06-06, first protocol session with direct steering): with
file-derived parameters, re-anchored 10 s windows give median yaw-rate
correlation ≈ 0.74-0.79 and median RMS ≈ 0.08-0.09 rad/s against a
0.31 rad/s signal, with a systematic yaw-gain deficit (pred ≈ 0.7-0.8 ×
measured) — the open Phase 3 calibration target (front/rear pre-peak
shape balance and peak-slip scale move it; see project README).
"""
function replay_yaw(m::VehicleModel, t::AbstractVector, steer::AbstractVector,
                    v::AbstractVector, loads::NTuple{4,<:AbstractVector},
                    fuel::AbstractVector;
                    yaw0::Real=0.0, beta0::Real=0.0,
                    drive::AbstractVector=zeros(length(t)),
                    tire_f::TBCTire=m.tire_f, tire_r::TBCTire=m.tire_r,
                    slip_exponent::Real=LATERAL_CAL.slip_exponent,
                    nsub::Integer=4)
    fzfl, fzfr, fzrl, fzrr = loads
    L = m.wheelbase
    a = L * m.rear_frac          # CG to front axle (static balance)
    b = L - a
    ψ = Float64(yaw0); β = Float64(beta0)
    out = Float64[ψ]
    for i in 1:length(t)-1
        h = (t[i+1] - t[i]) / nsub
        vv = max(v[i], 5.0)
        δ = steer[i]
        mt = mass(m, fuel[i])
        fx = drive[i] / 2                       # per rear wheel
        for _ in 1:nsub
            αf = δ - β - a * ψ / vv
            αr = -β + b * ψ / vv
            Ff = lateral_force(tire_f, sin(αf), fzfl[i], vv) +
                 lateral_force(tire_f, sin(αf), fzfr[i], vv)
            Fr = 0.0
            for ld in (fzrl[i], fzrr[i])
                cap = peak_mu_long(tire_r, ld) * ld
                derate = cap > 1 ?
                    max(0.0, 1 - (min(fx, 0.92 * cap) / cap)^2)^slip_exponent : 1.0
                Fr += derate * lateral_force(tire_r, sin(αr), ld, vv)
            end
            β = clamp(β + h * ((Ff * cos(δ) + Fr) / (mt * vv) - ψ), -1.5, 1.5)
            ψ = clamp(ψ + h * (a * Ff * cos(δ) - b * Fr) / m.iz, -3.0, 3.0)
        end
        push!(out, ψ)
    end
    out
end

"""Driven-axle longitudinal force trace from logged throttle/gear/clutch
(engine-limited; ≥ 0), for `replay_yaw`'s combined-slip derate."""
function drive_force_trace(m::VehicleModel, v::AbstractVector,
                           throttle::AbstractVector, gear::AbstractVector,
                           clutch::AbstractVector)
    map(eachindex(v)) do i
        g = isfinite(gear[i]) ? Int(gear[i]) : 0
        (g >= 1 && clutch[i] < 0.5) || return 0.0
        rpm = engine_rpm(m.dt, g, max(v[i], 1.0) / m.radius)
        max(0.0, engine_torque(m.eng, rpm, throttle[i]) * m.dt.totals[g] / m.radius)
    end
end

"""
    replay_inputs(m, t, steer, throttle, brake, gear, fuel; v0, beta0, yaw0)
        -> (speed, yawrate)

Full coupled forward replay from logged driver inputs: integrates the
complete bicycle state (forward speed, sideslip, yaw rate) with
longitudinal load transfer feeding the lateral tire loads and drive force
derating the rear (combined slip).  Unlike `replay_speed`/`replay_yaw`
(each takes the other channel from telemetry), this drives the *whole*
engine from inputs alone — the capstone integrated-physics test.  Returns
predicted speed (m/s) and yaw rate (rad/s) at each timestamp to compare
against the logged trajectories.  `steer` is the road-wheel angle (rad).
"""
function replay_inputs(m::VehicleModel, t::AbstractVector, steer::AbstractVector,
                       throttle::AbstractVector, brake::AbstractVector,
                       gear::AbstractVector, fuel::AbstractVector;
                       v0::Real, beta0::Real=0.0, yaw0::Real=0.0, nsub::Integer=4)
    L = m.wheelbase
    a = L * m.rear_frac
    b = L - a
    v = Float64(v0); β = Float64(beta0); r = Float64(yaw0)
    vs = Float64[v]; rs = Float64[r]
    for i in 1:length(t)-1
        h = (t[i+1] - t[i]) / nsub
        g = isfinite(gear[i]) ? Int(gear[i]) : 0
        δ = steer[i]
        mt = mass(m, fuel[i])
        for _ in 1:nsub
            along, _ = longitudinal_accel(m, v, g, throttle[i], fuel[i]; brake=brake[i])
            # longitudinal load transfer onto the lateral tire loads
            dW = mt * along * m.cg_h / L
            Fzf = max(mt * 9.81 * (1 - m.rear_frac) - dW, 0.0)
            Fzr = max(mt * 9.81 * m.rear_frac + dW, 0.0)
            vv = max(v, 3.0)
            αf = δ - atan(β + a * r / vv)
            αr = -atan(β - b * r / vv)
            Fyf = lateral_force(m.tire_f, sin(αf), Fzf, vv)
            fx = max(along * mt, 0.0)
            capr = peak_mu_long(m.tire_r, Fzr / 2) * Fzr
            der = capr > 1 ?
                max(0.0, 1 - (min(fx, 0.92capr) / capr)^2)^LATERAL_CAL.slip_exponent : 1.0
            Fyr = der * lateral_force(m.tire_r, sin(αr), Fzr, vv)
            r = clamp(r + h * (a * Fyf * cos(δ) - b * Fyr) / m.iz, -3.0, 3.0)
            β = clamp(β + h * ((Fyf * cos(δ) + Fyr) / (mt * vv) - r), -1.5, 1.5)
            v = max(v + h * along, 2.0)
        end
        push!(vs, v); push!(rs, r)
    end
    vs, rs
end

"""
    replay_speed(m, t, throttle, gear, fuel; v0, brake=…, clutch=…) -> Vector{Float64}

Integrate the longitudinal model over a telemetry segment, driving it with
the logged throttle/gear/brake/clutch traces (zero-order hold, RK2
substeps).  Returns the predicted speed at each telemetry timestamp.
"""
function replay_speed(m::VehicleModel, t::AbstractVector, throttle::AbstractVector,
                      gear::AbstractVector, fuel::AbstractVector; v0::Real,
                      brake::AbstractVector=zeros(length(t)),
                      clutch::AbstractVector=zeros(length(t)))
    v = Float64(v0)
    out = Float64[v]
    for i in 1:length(t)-1
        dt_full = t[i+1] - t[i]
        nsub = max(1, ceil(Int, dt_full / 0.01))
        h = dt_full / nsub
        for _ in 1:nsub
            a1, _ = longitudinal_accel(m, v, Int(gear[i]), throttle[i], fuel[i];
                                       brake=brake[i], clutch=clutch[i])
            a2, _ = longitudinal_accel(m, v + h * a1, Int(gear[i]), throttle[i],
                                       fuel[i]; brake=brake[i], clutch=clutch[i])
            v = max(0.0, v + h * (a1 + a2) / 2)
        end
        push!(out, v)
    end
    out
end
