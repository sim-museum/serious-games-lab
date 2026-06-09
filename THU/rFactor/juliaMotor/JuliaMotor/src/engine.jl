# Engine torque model from the rFactor engine INI.
#
# The torque map is the RPMTorque table: (rpm, coast torque, full torque)
# rows.  isiMotor blends coast and full torque linearly with throttle;
# rows are interpolated linearly in RPM (the tables are dense — 250 RPM
# spacing — so spline vs linear is immaterial here).

struct EngineModel
    rpm::Vector{Float64}
    coast::Vector{Float64}
    full::Vector{Float64}
    inertia::Float64       # EngineInertia (kg m^2)
    rev_limit::Float64
    idle_lo::Float64       # IdleRPMLogic
    idle_hi::Float64
end

"""
    EngineModel(e::RFactorData.EngineFile; rev_limit=Inf)

`rev_limit` comes from the chassis (HDV `[ENGINE] RevLimitRange` +
setting), not the engine file, so it is passed in.
"""
function EngineModel(e::EngineFile; rev_limit::Real=Inf)
    issorted(e.rpm) || throw(ArgumentError("$(e.path): RPMTorque table not sorted"))
    idle = param(e, "IdleRPMLogic", [0.0, 0.0])
    EngineModel(e.rpm, e.coast, e.torque,
                Float64(param(e, "EngineInertia", 0.0)), Float64(rev_limit),
                Float64(idle[1]), Float64(idle[2]))
end

Base.show(io::IO, m::EngineModel) =
    print(io, "EngineModel(", length(m.rpm), " samples, ",
          round(Int, m.rpm[end]), " rpm max, rev limit ",
          isfinite(m.rev_limit) ? round(Int, m.rev_limit) : "none", ")")

function interp(xs::Vector{Float64}, ys::Vector{Float64}, x::Real)
    x <= xs[1] && return ys[1]
    x >= xs[end] && return ys[end]
    i = searchsortedlast(xs, x)
    t = (x - xs[i]) / (xs[i+1] - xs[i])
    ys[i] + t * (ys[i+1] - ys[i])
end

"""Full-throttle torque (Nm) at `rpm`."""
full_torque(m::EngineModel, rpm::Real) = interp(m.rpm, m.full, rpm)

"""Closed-throttle (engine braking) torque (Nm) at `rpm`; negative."""
coast_torque(m::EngineModel, rpm::Real) = interp(m.rpm, m.coast, rpm)

"""
    engine_torque(m, rpm, throttle) -> Nm

Linear coast/full blend by throttle; zero beyond the rev limit (the
limiter cuts).
"""
function engine_torque(m::EngineModel, rpm::Real, throttle::Real)
    rpm >= m.rev_limit && return min(coast_torque(m, rpm), 0.0)
    c = coast_torque(m, rpm)
    c + clamp(throttle, 0.0, 1.0) * (full_torque(m, rpm) - c)
end

"""Peak full-throttle power (W) and the RPM where it occurs."""
function peak_power(m::EngineModel)
    best, bestrpm = -Inf, 0.0
    for r in m.rpm[1]:50.0:m.rpm[end]
        p = full_torque(m, r) * r * 2π / 60
        p > best && ((best, bestrpm) = (p, r))
    end
    best, bestrpm
end
