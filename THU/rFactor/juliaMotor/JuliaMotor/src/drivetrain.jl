# Gearbox + final drive from the HDV [DRIVELINE] and its gear file.
#
# `Gear<N>Setting` / `FinalDriveSetting` / `ReverseSetting` are 0-based
# indices into the gear file's ratio lists — indexed in DESCENDING ratio
# order, not file order.  Verified against the 2026-06-05 telemetry: the
# 1958 gear file has a misplaced entry ((36,22)=0.611 sitting between
# 1.667 and 1.611); with a stable descending sort, all three observed
# gears match the logged RPM/wheel-speed ratios to 4 significant figures
# (file order would put gear 3 at 4.789 instead of the observed 4.694).
# For the corpus' already-sorted files the sort is a no-op.

struct Drivetrain
    totals::Vector{Float64}   # engine->wheel ratio per forward gear (incl. final)
    final::Float64
    reverse_total::Float64
    wheeldrive::Symbol        # :rear, :front, :four
end

"""
    Drivetrain(v::RFactorData.Vehicle) -> Drivetrain

Built from the vehicle's HDV `[DRIVELINE]` settings and its gear file.
Garage setups (.svm) can override the settings; pass `overrides` as a
Dict mapping setting names to values when replaying a non-default setup.
"""
function Drivetrain(v::Vehicle; overrides::AbstractDict{String,<:Integer}=Dict{String,Int}())
    dl = section(v.hdv, "DRIVELINE")
    dl === nothing && throw(ArgumentError("$(v.hdv.path): no [DRIVELINE]"))
    setting(name) = get(overrides, name, get(dl, name, 0))

    ratios = sort(gear_ratios(v.gears); rev=true)
    finals = sort(final_drive_ratios(v.gears); rev=true)
    isempty(ratios) && throw(ArgumentError("no [GEAR_RATIOS] in gear file"))
    fd = isempty(finals) ? 1.0 : finals[setting("FinalDriveSetting") + 1]

    n = get(dl, "ForwardGears", 0)
    totals = [ratios[setting("Gear$(g)Setting") + 1] * fd for g in 1:n]
    rev = ratios[setting("ReverseSetting") + 1] * fd

    wd = lowercase(string(get(dl, "WheelDrive", "REAR")))
    Drivetrain(totals, fd, rev, Symbol(wd))
end

ngears(d::Drivetrain) = length(d.totals)

Base.show(io::IO, d::Drivetrain) =
    print(io, "Drivetrain(", ngears(d), " gears, totals ",
          round.(d.totals; digits=3), ", final ", round(d.final; digits=3), ")")

"""Driven-wheel angular velocity (rad/s) for an engine speed in a gear."""
wheel_speed(d::Drivetrain, gear::Integer, engine_rpm::Real) =
    engine_rpm * 2π / 60 / d.totals[gear]

"""Engine RPM for a driven-wheel angular velocity (rad/s) in a gear."""
engine_rpm(d::Drivetrain, gear::Integer, wheel_omega::Real) =
    wheel_omega * d.totals[gear] * 60 / 2π

"""Torque multiplication engine→wheels in a gear (loss-free; isiMotor's
HDV exposes no driveline efficiency parameter)."""
wheel_torque(d::Drivetrain, gear::Integer, engine_torque::Real) =
    engine_torque * d.totals[gear]
