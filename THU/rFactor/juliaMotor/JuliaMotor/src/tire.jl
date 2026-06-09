# TBC tire force model — isiMotor 2 semantics reconstructed from the TBC
# in-file spec (slip-curve header), ISI stock-tire inline comments, and
# the 2026-06-05 Vanwall/Monaco telemetry session.
#
# Documented anchors (treated as fixed):
#   * slip curves: samples at uniform Step, cubic spline, normalized peak=1
#   * peak shift: combo = load + speed * SpeedEffects[2];
#     LatPeak/LongPeak=(min, max, scale) — "slip range where peak force
#     occurs depending on load"; min at combo=0, max at combo=scale
#   * DropoffFunction d: how the post-peak curve reshapes when the peak
#     moves (-1 faster dropoff for larger peak, 0 fixed shape, 1 stretched
#     with the curve)
#   * LoadSensLat/Long=(initial slope, final grip multiplier, final load):
#     grip multiplier starts at 1 with the given slope at zero load and
#     reaches the final multiplier at the final load, constant beyond
#
# Calibration knobs (interpolation shapes the files do not pin down; the
# nominal choices below reproduce the telemetry's measured peak grip to
# ~3 % — Phase 3 fits the residuals):
#   * load-sensitivity transition: quadratic Hermite between the anchors
#   * dropoff remap for fractional d: geometric blend stretch^d
#   * combined slip: friction-ellipse scaling
#   * SpeedEffects[1] and thermal/pressure/wear/camber effects: not yet
#     modeled (bench assumes optimal-condition tires)

"""One slip curve, normalized to peak 1.0, with its nominal peak slip and
`DropoffFunction`.  `prepeak_tau > 0` switches the pre-peak segment to the
calibrated exponential shape (see `reaction`)."""
struct TireCurve
    spline::UniformSpline
    peak_slip0::Float64
    dropoff::Float64
    prepeak_tau::Float64
end

function TireCurve(c::SlipCurve; prepeak_tau::Real=0.0)
    peakval, ipeak = findmax(c.data)
    TireCurve(UniformSpline(c.data ./ peakval, c.step),
              (ipeak - 1) * c.step, c.dropoff, Float64(prepeak_tau))
end

"""
    reaction(tc, slip, peak) -> normalized force reaction in [0, ~1]

Evaluate the curve with its peak relocated from `peak_slip0` to `peak`.

Pre-peak: the literal whole-curve-stretch reading of the TBC spec
(`prepeak_tau == 0`) rises far too slowly — the 2026-06-05 Slide-Pct
measurement (11k cornering samples) shows isiMotor's effective curve is
exponential-saturating in normalized slip u = s/peak:

    F(u) = (1 - exp(-u/τ)) / (1 - exp(-1/τ)),   τ ≈ 0.0905 (R² 0.95)

That calibrated shape is used when `prepeak_tau > 0`; both forms reach
exactly 1.0 at the peak, so peak-grip behavior (validated at the limit)
is identical.

Post-peak: the local slip maps through `stretch^dropoff` (dropoff=1 →
whole-curve stretch, 0 → dropoff shape fixed, -1 → faster dropoff as the
peak grows).
"""
function reaction(tc::TireCurve, slip::Real, peak::Real)
    s = abs(slip)
    if s <= peak
        if tc.prepeak_tau > 0
            u = s / peak
            return (1 - exp(-u / tc.prepeak_tau)) / (1 - exp(-1 / tc.prepeak_tau))
        end
        return tc.spline(s * tc.peak_slip0 / peak)
    end
    stretch = peak / tc.peak_slip0
    tc.spline(tc.peak_slip0 + (s - peak) / stretch^tc.dropoff)
end

"""`LoadSens*=(slope, finalmult, finalload)`: quadratic Hermite from
(0, 1) with initial `slope` to (`finalload`, `finalmult`), clamped after."""
struct LoadSens
    slope::Float64
    finalmult::Float64
    finalload::Float64
    quad::Float64
end

LoadSens(slope::Real, finalmult::Real, finalload::Real) =
    LoadSens(slope, finalmult, finalload,
             (finalmult - 1.0 - slope * finalload) / finalload^2)
LoadSens(v::AbstractVector) = LoadSens(v[1], v[2], v[3])

loadmult(ls::LoadSens, load::Real) =
    load >= ls.finalload ? ls.finalmult :
    load <= 0 ? 1.0 : 1.0 + ls.slope * load + ls.quad * load^2

"""`LatPeak`/`LongPeak=(min, max, scale)`: peak slip vs load/speed combo."""
struct PeakShift
    smin::Float64
    smax::Float64
    scale::Float64
end
PeakShift(v::AbstractVector) = PeakShift(v[1], v[2], v[3])

peakslip(p::PeakShift, combo::Real) =
    p.smin + (p.smax - p.smin) * clamp(combo / p.scale, 0.0, 1.0)

"""
All force-model parameters for one axle's tire of one compound, built
straight from a parsed `TBCFile`.
"""
struct TBCTire
    name::String
    lat::TireCurve
    braking::TireCurve
    traction::TireCurve
    mu_lat::Float64          # DryLatLong[1]
    mu_long::Float64         # DryLatLong[2]
    ls_lat::LoadSens
    ls_long::LoadSens
    pk_lat::PeakShift
    pk_long::PeakShift
    equivalency::Float64     # SpeedEffects[2]
    radius::Float64
    lat_peak_scale::Float64  # calibration knob: scales the lateral peak slip
end

"""
    TBCTire(tbc, axle; compound_index=0, prepeak_tau=0.0905)

`prepeak_tau` is the calibrated pre-peak shape (fitted to the lateral
curve on the free-rolling front axle; the driven rear fitted the same τ
within 8 %).  It is applied to all three curves — the longitudinal shapes
are unmeasured (provisional), but every validated longitudinal result is
torque- or engine-limited below the peak where the shape doesn't bind.
Pass `prepeak_tau=0` for the literal whole-curve-stretch spec reading.

`lat_peak_scale` widens the lateral peak slip; the yaw-dynamics
calibration (see `VehicleModel`) identified that only the product
`lat_peak_scale × prepeak_tau` is observable in the driving envelope —
the canonical calibrated point uses `lat_peak_scale=2.5`.
"""
function TBCTire(tbc::TBCFile, axle::Symbol; compound_index::Integer=0,
                 prepeak_tau::Real=0.0905, lat_peak_scale::Real=1.0)
    c = compound(tbc, compound_index)
    p(key) = c[key, axle]
    curve(key) = begin
        sc = slipcurve(tbc, p(key))
        sc === nothing && error("$(tbc.path): compound '$(c.name)' references " *
                                "missing slip curve '$(p(key))'")
        TireCurve(sc; prepeak_tau)
    end
    dry = p("DryLatLong")
    TBCTire(c.name,
            curve("LatCurve"), curve("BrakingCurve"), curve("TractiveCurve"),
            dry[1], dry[2],
            LoadSens(p("LoadSensLat")), LoadSens(p("LoadSensLong")),
            PeakShift(p("LatPeak")), PeakShift(p("LongPeak")),
            p("SpeedEffects")[2], p("Radius"), Float64(lat_peak_scale))
end

Base.show(io::IO, t::TBCTire) =
    print(io, "TBCTire(\"", t.name, "\", μlat=", t.mu_lat, ", μlong=", t.mu_long, ")")

combo(load::Real, speed::Real, equivalency::Real) = load + speed * equivalency

"""Peak lateral grip coefficient at a given load (optimal conditions)."""
peak_mu_lat(t::TBCTire, load::Real) = t.mu_lat * loadmult(t.ls_lat, load)
peak_mu_long(t::TBCTire, load::Real) = t.mu_long * loadmult(t.ls_long, load)

"""
    lateral_force(t, slip, load, speed) -> Fy (N)

`slip` is the normalized lateral slip (sin of the slip angle, per the TBC
spec); sign convention: force opposes slip direction of the contact patch,
returned with the sign of `slip`.
"""
function lateral_force(t::TBCTire, slip::Real, load::Real, speed::Real)
    load <= 0 && return 0.0
    pk = t.lat_peak_scale * peakslip(t.pk_lat, combo(load, speed, t.equivalency))
    sign(slip) * peak_mu_lat(t, load) * load * reaction(t.lat, slip, pk)
end

"""
    longitudinal_force(t, ratio, load, speed) -> Fx (N)

`ratio` is the SAE-style slip ratio: positive driving (traction curve),
negative braking (braking curve).
"""
function longitudinal_force(t::TBCTire, ratio::Real, load::Real, speed::Real)
    load <= 0 && return 0.0
    pk = peakslip(t.pk_long, combo(load, speed, t.equivalency))
    c = ratio >= 0 ? t.traction : t.braking
    sign(ratio) * peak_mu_long(t, load) * load * reaction(c, ratio, pk)
end

"""
    tire_forces(t, slip, ratio, load, speed) -> (Fx, Fy)

Combined slip via friction-ellipse scaling of the pure-slip forces
(calibration knob: isiMotor's true combining method is undocumented).
"""
function tire_forces(t::TBCTire, slip::Real, ratio::Real, load::Real, speed::Real)
    fx = longitudinal_force(t, ratio, load, speed)
    fy = lateral_force(t, slip, load, speed)
    (fx == 0.0 || fy == 0.0) && return (fx, fy)
    fxmax = peak_mu_long(t, load) * load
    fymax = peak_mu_lat(t, load) * load
    u = hypot(fx / fxmax, fy / fymax)
    u <= 1.0 ? (fx, fy) : (fx / u, fy / u)
end
