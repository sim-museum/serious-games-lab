# SETUPMODEL-1: iRacing's GARAGE for the Lotus 49, as connected physical objects.
#
# iRacing's setup page has KNOBS (perch offsets, spring rates, packers, bars, fuel, camber, toe, pressures, gearing,
# diff, dampers, bias) and DERIVED numbers it solves from them (corner weights, ride heights, shock deflections,
# cross weight, the static camber, gear top speeds). This module is that solve: the car is a rigid sprung body on four
# corners, each corner a coil spring on a perch acting on the shock through a motion ratio, a bump rubber behind the
# packer, a tyre with a vertical rate; an anti-roll bar couples the two corners of an axle; a fuel tank moves mass and
# CG. Its constants are identified from the PO's 261017 garage sweeps + every CarSetup in the gold .ibt store
# (tools/garage_fit_261017.jl), so turning one knob moves the derived numbers the way iRacing's garage does.
#
# The constants and iRacing's knob list live in garage_lotus49.toml, shared with the launcher's Garage tab
# (demo/native/garage.py); tools/garage_smoke.jl keeps the two solvers in agreement.
#
# Conventions (iRacing's, measured):
#   * spring compression [mm] = shock deflection - perch offset + L_axle  (a bigger perch offset = LESS preload: the
#     corner sinks and sheds weight; 261017 D2: 18/30/35 N/mm at a fixed load pin L). A perch far enough up leaves the
#     spring LOOSE and the corner sits on its bump rubber (261017 snip 14: LF perch 305.6 mm) -- iRacing allows it.
#   * the displayed corner weight includes the anti-roll bar's share
#   * shock deflection is measured from full extension; "of max" = max - packer
#   * ride height = chassis height at the corner over the ground; one rigid chassis plane through all four
#   * perch/packer step 1/64 inch (0.396875 mm): every value seen is a whole number of 64ths
module Garage

using TOML, Printf

export GarageParams, Knobs, Derived, PARAMS, solve_static, knobs_from_setup, base_knobs, KNOB_SPECS,
       arb_rate, gear_speeds_kmh, describe_derived, apply_garage, carsetup_yaml, read_garage_file, write_garage_file, GARAGE_TOML

const G = 9.80665
const CORNERS = (:LF, :RF, :LR, :RR)
const INCH64 = 25.4/64

# ── the identified constants ────────────────────────────────────────────────────────────────────────────────────────
Base.@kwdef struct GarageParams
    # per axle (front, rear)
    L::NTuple{2,Float64}      = (149.6, 120.0)   # spring length constant [mm]: compression = shock - perch + L
    MR::NTuple{2,Float64}     = (0.83, 0.80)     # shock travel per wheel travel at the reference shock deflection
    MRq::NTuple{2,Float64}    = (0.0, 0.0)       # d(MR)/d(shock) [1/mm]: progressive linkage
    MRk::NTuple{2,Float64}    = (0.83, 0.80)     # SPRING travel per wheel travel (a rocker can drive spring and shock differently)
    bar_shown::Float64        = 1.0              # fraction of the bar's force the displayed corner weight includes
    rh_mix::NTuple{2,Float64} = (0.0, 0.0)       # the ride-height point sits this fraction of the wheelbase toward the other axle
    s0::NTuple{2,Float64}     = (61.7, 58.7)     # shock deflection at zero wheel travel (the reference) [mm]
    R0::NTuple{2,Float64}     = (90.0, 110.0)    # ride height at zero wheel travel and an unloaded tyre [mm]
    unsprung::NTuple{2,Float64} = (190.0, 260.0) # unsprung weight per corner [N]
    kt::NTuple{2,Float64}     = (300.0, 300.0)   # tyre vertical rate at 152 kPa [N/mm]
    kt_p::Float64             = 0.0              # d(kt)/d(pressure) per kPa, relative
    rp::NTuple{2,Float64}     = (0.0, 0.0)       # unloaded tyre radius growth per kPa above 152 [mm/kPa]
    karb::NTuple{2,Float64}   = (10.0, 10.0)     # bar rate at the wheel, reference dia + arm [N/mm of wheel-travel difference]
    arm_beta::NTuple{2,Float64} = (0.08, 0.08)   # arm length change per hole, relative (soft = hole 1 .. firm = hole 7)
    kbump::NTuple{2,Float64}  = (200.0, 200.0)   # bump rubber rate at the shock [N/mm]
    bump_gap::NTuple{2,Float64} = (5.0, 5.0)     # bump rubber engages this far before (max - packer) [mm]
    trackratio::Float64       = 1.0              # rear track / front track (roll plane)
    track_f::Float64          = 1530.0           # front track at the reference [mm]
    scrub::NTuple{2,Float64}  = (0.0, 0.0)       # half-track growth per mm of wheel travel (contact patch migration)
    cam_patch::Float64        = 0.0              # contact patch moves outward this far per degree of camber [mm/deg]
    cam_ref::NTuple{2,Float64} = (-0.4, -0.5)    # the base car's static camber (where cam_patch is zero)
    # mass
    W0::Float64               = 5936.0 - 43.2*0.75*G   # weight with an empty tank [N]
    front0::Float64           = 0.448            # front share of W0
    fuel_kgL::Float64         = 0.75
    fuel_front::Float64       = 0.66             # front share of the fuel's weight
    # static camber/toe kinematics (displayed = knob + gain * wheel travel + roll)
    cam_gain::NTuple{2,Float64} = (0.027, 0.02)  # deg per mm of wheel travel (compression = more negative)
    cam_roll::NTuple{2,Float64} = (0.0, 0.0)     # deg per deg of chassis roll
    toe_gain::Float64         = 0.016            # front toe-in mm per mm of front wheel travel (summed; droop = toe-out)
    # gearing: iRacing's gear km/h = (rev limit x rolling radius) / overall ratio
    rpm_r::Float64            = 3145.2           # rev-limit rpm x tyre rolling radius [rpm*m]
end

# ── the knobs, as iRacing names them ────────────────────────────────────────────────────────────────────────────────
Base.@kwdef mutable struct Knobs
    perch::NTuple{4,Float64}   = (165.1, 165.1, 103.6, 103.6)   # mm, LF RF LR RR
    spring::NTuple{4,Float64}  = (30.0, 30.0, 48.0, 48.0)       # N/mm
    packer::NTuple{4,Float64}  = (0.0, 0.0, 0.0, 0.0)           # mm
    camber::NTuple{4,Float64}  = (-0.4, -0.4, -0.5, -0.5)       # deg, the DISPLAYED static camber at the reference car
    pressure::NTuple{4,Float64} = (152.0, 152.0, 152.0, 152.0)  # kPa cold
    bump::NTuple{4,Int}        = (4, 4, 4, 4)                   # clicks
    rebound::NTuple{4,Int}     = (8, 8, 7, 7)                   # clicks
    toe_front::Float64         = -1.0                           # mm (toe-in; negative = out), at the reference car
    toe_rear::Float64          = 1.0
    farb_dia::Float64          = 0.375                          # inch; 0 = disconnected
    farb_arm::String           = "2"
    rarb_dia::Float64          = 0.6875
    rarb_arm::String           = "5"
    fuel::Float64              = 43.2                           # L
    brake_bias::Float64        = 53.5                           # % front
    steering_ratio::Float64    = 10.0
    final_drive::Float64       = 4.22
    gears::Vector{Float64}     = [2.23, 1.72, 1.32, 1.04, 0.846]
    diff_plates::Int           = 4
    diff_preload::Float64      = 41.0                           # Nm
    diff_drive::Float64        = 75.0                           # deg
    diff_coast::Float64        = 60.0                           # deg
end
base_knobs() = Knobs()

struct Derived
    cw::NTuple{4,Float64}       # corner weight N
    rh::NTuple{4,Float64}       # ride height mm
    shock::NTuple{4,Float64}    # shock deflection mm
    shock_max::NTuple{4,Float64}
    camber::NTuple{4,Float64}   # deg
    cross::Float64              # % (RF+LR)/total
    toe_front::Float64          # mm
    z::NTuple{4,Float64}        # wheel travel from the reference mm (internal)
    roll_deg::Float64
    ok::Bool                    # Newton converged
end

# Hole index of an arm setting: soft = 1, "2".."6", firm = 7.
armhole(a::AbstractString) = (s = lowercase(strip(a)); s == "soft" ? 1 : s == "firm" ? 7 : parse(Int, s))
const ARB_REF = ((0.375, 2), (0.6875, 5))     # the base car's front and rear bar (the rate karb refers to)

"""    arb_rate(P, axle, dia, arm) -> N/mm at the wheel

A torsion bar: rate ∝ diameter⁴ / lever², 1/lever growing by `arm_beta` (relative) per hole toward firm."""
function arb_rate(P::GarageParams, axle::Int, dia::Float64, arm::AbstractString)
    dia <= 0 && return 0.0
    dref, href = ARB_REF[axle]
    h = armhole(arm)
    # the lever shortens toward "firm": 1/lever grows by arm_beta per hole (a gentle, positive law at both ends)
    P.karb[axle] * (dia/dref)^4 * max(0.05, 1 + P.arm_beta[axle]*(h - href))^2
end

axle(i) = i <= 2 ? 1 : 2
side(i) = isodd(i) ? 1.0 : -1.0          # left +1

# Per-corner suspension: wheel load from wheel travel z (mm, + = compression from the reference).
function corner_force(P::GarageParams, K::Knobs, i::Int, z::Float64)
    a = axle(i)
    # shock deflection: progressive linkage, s = s0 + MR z + MRq/2 * MR^2 z^2  (MR grows by MRq per mm of shock)
    s = P.s0[a] + P.MR[a]*z + 0.5*P.MRq[a]*(P.MR[a]*z)^2
    mr = P.MR[a] + P.MRq[a]*P.MR[a]^2*z               # ds/dz: the force ratio (virtual work)
    # spring compression: L - perch at the reference, then the spring's own ratio (= the shock's on a coil-over)
    x = (P.s0[a] - K.perch[i] + P.L[a]) + P.MRk[a]*z
    Fs = K.spring[i] * max(x, 0.0)
    smax = (a == 1 ? 104.6 : 113.0) - K.packer[i]
    e = s - (smax - P.bump_gap[a])
    Fb = e > 0 ? P.kbump[a]*e^2/(2*P.bump_gap[a]) : 0.0   # rubber: rate grows from 0 to kbump over the gap
    (; W = P.unsprung[a] + P.MRk[a]*Fs + mr*Fb, s, smax)
end

tyre_rate(P::GarageParams, a::Int, p::Float64) = P.kt[a] * (1 + P.kt_p*(p - 152.0))

"""    solve_static(K, P; warp = 0) -> Derived

Place the car on its springs: find the chassis plane (heave, pitch, roll) and the four wheel loads such that every
corner's spring + bar + bump force carries its load through its tyre, and the loads balance the weight and its CG.
`warp` [mm] lifts the LF/RR ground and drops RF/LR (a garage floor that is not flat; the skidpad's is)."""
function solve_static(K::Knobs, P::GarageParams = PARAMS[]; warp::Float64 = 0.0)
    Wt = P.W0 + K.fuel*P.fuel_kgL*G
    Wf = P.W0*P.front0 + K.fuel*P.fuel_kgL*G*P.fuel_front    # front axle weight (statically determinate)
    Wr = Wt - Wf
    kbar = (arb_rate(P, 1, K.farb_dia, K.farb_arm), arb_rate(P, 2, K.rarb_dia, K.rarb_arm))
    tr = (1.0, P.trackratio)
    gnd = (warp/2, -warp/2, -warp/2, warp/2)
    # unknowns: v = (hf, hr, roll, z1..z4): front/rear chassis heights at the axle centre, roll [mm per front track]
    function resid(v)
        hf, hr, ro = v[1], v[2], v[3]
        z = (v[4], v[5], v[6], v[7])
        r = zeros(eltype(v), 7)
        W = ntuple(4) do i
            a = axle(i)
            F = corner_force(P, K, i, z[i]).W
            o = isodd(i) ? i+1 : i-1                                   # the other corner on the axle
            F + kbar[a]*(z[i] - z[o])
        end
        for i in 1:4
            a = axle(i)
            rh = (a == 1 ? hf : hr) + side(i)*ro*tr[a]/2 - gnd[i]          # chassis over the contact patch
            r[i] = rh - (P.R0[a] + P.rp[a]*(K.pressure[i] - 152.0) - z[i] - W[i]/tyre_rate(P, a, K.pressure[i]))   # tyre + travel close the loop
        end
        r[5] = (W[1] + W[2]) - Wf                                     # pitch balance
        r[6] = (W[3] + W[4]) - Wr
        # roll balance (CG on the centreline): each load acts at its contact patch, which migrates with travel and camber
        rdeg = ro/1500*180/pi
        cam = ntuple(i -> K.camber[i] - P.cam_gain[axle(i)]*z[i] + side(i)*P.cam_roll[axle(i)]*rdeg, 4)
        r[7] = sum(W[i]*side(i)*(P.track_f*tr[axle(i)]/2 + P.scrub[axle(i)]*z[i] +
                                 P.cam_patch*(cam[i] - P.cam_ref[axle(i)])) for i in 1:4)
        r
    end
    v = [P.R0[1] - 20.0, P.R0[2] - 20.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ok = false
    for it in 1:60
        r = resid(v)
        J = zeros(7, 7); h = 1e-6
        for j in 1:7
            vp = copy(v); vp[j] += h
            J[:, j] = (resid(vp) .- r) ./ h
        end
        dv = try J \ r catch; fill(NaN, 7) end
        all(isfinite, dv) || break
        v .-= dv
        if maximum(abs, dv) < 1e-9
            ok = true; break
        end
    end
    hf, hr, ro = v[1], v[2], v[3]
    z = (v[4], v[5], v[6], v[7])
    cf = ntuple(i -> corner_force(P, K, i, z[i]), 4)
    W = ntuple(4) do i
        o = isodd(i) ? i+1 : i-1
        cf[i].W + kbar[axle(i)]*(z[i] - z[o])
    end
    # displayed ride height: at iRacing's measuring point, rh_mix of the way toward the other axle
    hfm = (1 - P.rh_mix[1])*hf + P.rh_mix[1]*hr
    hrm = (1 - P.rh_mix[2])*hr + P.rh_mix[2]*hf
    rh = ntuple(i -> (axle(i) == 1 ? hfm : hrm) + side(i)*ro*(axle(i) == 1 ? 1.0 : P.trackratio)/2 - gnd[i], 4)
    rolldeg = ro/1500*180/pi                  # roll [deg] over a ~1.5 m front track (the same as in the balance)
    # camber: the knob is the displayed value of the reference car (z = 0, no roll); travel and roll move it
    cam = ntuple(i -> K.camber[i] - P.cam_gain[axle(i)]*z[i] + side(i)*P.cam_roll[axle(i)]*rolldeg, 4)
    toe = K.toe_front + P.toe_gain*(z[1] + z[2])
    Wshown = ntuple(4) do i
        o = isodd(i) ? i+1 : i-1
        W[i] - (1 - P.bar_shown)*kbar[axle(i)]*(z[i] - z[o])
    end
    Derived(Wshown, rh, ntuple(i -> cf[i].s, 4), ntuple(i -> cf[i].smax, 4), cam,
            100*(Wshown[2] + Wshown[3])/sum(Wshown), toe, z, rolldeg, ok)
end

"""Gear top speeds [km/h] as the garage shows them (rev limit x rolling radius / overall ratio)."""
gear_speeds_kmh(K::Knobs, P::GarageParams = PARAMS[]) =
    [P.rpm_r * 2π / 60 / (g*K.final_drive) * 3.6 for g in K.gears]

const GARAGE_TOML = joinpath(@__DIR__, "garage_lotus49.toml")

"""GarageParams from the shared constants file (the fit's output; see the header of garage_lotus49.toml)."""
function params_from_toml(fn::AbstractString = GARAGE_TOML)
    d = TOML.parsefile(fn)["params"]
    kw = Dict{Symbol,Any}()
    for f in fieldnames(GarageParams)
        haskey(d, String(f)) || continue
        v = d[String(f)]
        kw[f] = v isa AbstractVector ? Tuple(Float64.(v)) : Float64(v)
    end
    GarageParams(; kw...)
end
const PARAMS = Ref(params_from_toml())

# ── knob specs: iRacing's names, units, limits and steps ("known = false": provisional, see the TOML) ─────────────────
const KNOB_SPECS = TOML.parsefile(GARAGE_TOML)["knob"]

"""Knobs from a parsed .ibt CarSetup (Setup.setup_params), so a session's setup is the garage's starting point."""
function knobs_from_setup(sp)
    c4(d) = (d[:LF], d[:RF], d[:LR], d[:RR])
    dia(s) = (m = match(r"(\d*\.\d+|\d+)", s); occursin("isc", s) || m === nothing ? 0.0 : parse(Float64, m.captures[1]))
    fa = split(sp.arb_front); ra = split(sp.arb_rear)
    Knobs(; perch = haskey(sp, :perch_mm) ? c4(sp.perch_mm) : Knobs().perch,
          spring = Float64.(c4(sp.spring_rate_Npmm)), packer = Float64.(c4(sp.packer_mm)),
          camber = Float64.(c4(sp.camber_deg)), pressure = Float64.(c4(sp.cold_pressure_kPa)),
          bump = Int.(round.(c4(sp.bump_clicks))), rebound = Int.(round.(c4(sp.rebound_clicks))),
          toe_front = sp.toe_front_mm, toe_rear = sp.toe_rear_mm,
          farb_dia = dia(sp.arb_front), farb_arm = String(fa[end]), rarb_dia = dia(sp.arb_rear), rarb_arm = String(ra[end]),
          fuel = sp.fuel_L, brake_bias = sp.brake_bias_pct, steering_ratio = sp.steering_ratio,
          final_drive = sp.final_drive, gears = collect(Float64, sp.gear_ratios), diff_plates = Int(sp.diff_plates),
          diff_preload = sp.diff_preload_Nm, diff_drive = sp.diff_drive_ramp, diff_coast = sp.diff_coast_ramp)
end

"""    calibrate_session(sp) -> Knobs

The session's knobs, with the camber and front-toe knobs set so the model DISPLAYS the session's own static camber and
toe (the garage shows the result of a knob, not the knob)."""
function calibrate_session(sp, P::GarageParams = PARAMS[])
    K = knobs_from_setup(sp)
    want_c = K.camber; want_t = K.toe_front
    for _ in 1:3
        D = solve_static(K, P)
        K.camber = ntuple(i -> K.camber[i] + (want_c[i] - D.camber[i]), 4)
        K.toe_front += want_t - D.toe_front
    end
    K
end

"""    apply_garage(sp, K; Ks = calibrate_session(sp)) -> sp′

The session setup `sp` (Setup.setup_params) with the garage knobs `K` applied. Knob values are taken as set; the
DERIVED numbers are the session's own (iRacing's, exact) plus the model's change from the session's knobs `Ks` to `K`
-- so an untouched garage is the session to the digit, and the model's residual error cancels near it."""
function apply_garage(sp, K::Knobs; Ks::Knobs = calibrate_session(sp), P::GarageParams = PARAMS[])
    D = solve_static(K, P); Ds = solve_static(Ks, P)
    c4(d) = (d[:LF], d[:RF], d[:LR], d[:RR])
    d4(t) = Dict(:LF => t[1], :RF => t[2], :LR => t[3], :RR => t[4])
    cw = c4(sp.corner_weight_N) .+ (D.cw .- Ds.cw)
    rh = c4(sp.ride_height_mm) .+ (D.rh .- Ds.rh)
    sh = ntuple(i -> (c4(sp.shock_defl_mm)[i][1] + D.shock[i] - Ds.shock[i], D.shock_max[i]), 4)
    ca = c4(sp.camber_deg) .+ (D.camber .- Ds.camber)
    armstr(dia, arm) = (dia <= 0 ? "Disconnected" : string(dia) * "\"") * " " * arm
    gears = collect(Float64, K.gears)
    merge(sp, (; corner_weight_N = d4(cw), ride_height_mm = d4(rh), shock_defl_mm = d4(sh), camber_deg = d4(ca),
               cross_weight_pct = 100*(cw[2] + cw[3])/sum(cw),
               spring_rate_Npmm = d4(K.spring), perch_mm = d4(K.perch), packer_mm = d4(K.packer),
               cold_pressure_kPa = d4(K.pressure), bump_clicks = d4(Float64.(K.bump)), rebound_clicks = d4(Float64.(K.rebound)),
               toe_front_mm = sp.toe_front_mm + (D.toe_front - Ds.toe_front),
               toe_rear_mm = K.toe_rear,
               arb_front = armstr(K.farb_dia, K.farb_arm), arb_rear = armstr(K.rarb_dia, K.rarb_arm),
               fuel_L = K.fuel, brake_bias_pct = K.brake_bias, steering_ratio = K.steering_ratio,
               final_drive = K.final_drive, gear_ratios = gears,
               diff_plates = Float64(K.diff_plates), diff_preload_Nm = K.diff_preload,
               diff_drive_ramp = K.diff_drive, diff_coast_ramp = K.diff_coast))
end

# ── the garage file the launcher writes (TOML; one table of knobs, iRacing's names) ──────────────────────────────────
const KNOB_FIELDS = (:perch, :spring, :packer, :camber, :pressure, :bump, :rebound, :toe_front, :toe_rear, :farb_dia,
                     :farb_arm, :rarb_dia, :rarb_arm, :fuel, :brake_bias, :steering_ratio, :final_drive, :gears,
                     :diff_plates, :diff_preload, :diff_drive, :diff_coast)

function write_garage_file(fn::AbstractString, K::Knobs; base::AbstractString = "default")
    d = Dict{String,Any}("base" => base)
    k = Dict{String,Any}()
    for f in KNOB_FIELDS
        v = getfield(K, f)
        k[String(f)] = v isa Tuple ? collect(v) : v
    end
    d["knobs"] = k
    open(io -> TOML.print(io, d), fn, "w")
    fn
end

"""Names of the knobs that differ between two garages (what the sim reports as "changed from the session")."""
function knob_diff(K::Knobs, Kref::Knobs)
    same(a, b) = a isa AbstractString || b isa AbstractString ? string(a) == string(b) :
                 length(a) == length(b) && all(isapprox.(collect(a), collect(b); atol = 1e-6))
    [String(f) for f in KNOB_FIELDS if !same(getfield(K, f), getfield(Kref, f))]
end

"""    read_garage_file(fn, Kbase) -> (base, Knobs)

Knobs from a garage file; any knob the file does not name keeps its value in `Kbase` (the session's)."""
function read_garage_file(fn::AbstractString, Kbase::Knobs)
    d = TOML.parsefile(fn)
    K = deepcopy(Kbase)
    k = get(d, "knobs", Dict{String,Any}())
    for f in KNOB_FIELDS
        haskey(k, String(f)) || continue
        v = k[String(f)]; T = fieldtype(Knobs, f)
        setfield!(K, f, T <: Tuple ? T(Tuple(v)) : T <: AbstractString ? String(v) : T <: AbstractVector ? Float64.(v) : T(v))
    end
    (get(d, "base", "default"), K)
end

"""One line of a setup's derived numbers (a Setup.setup_params NamedTuple, e.g. apply_garage's result)."""
function describe_derived_pp(sp)
    c4(d) = (d[:LF], d[:RF], d[:LR], d[:RR])
    f1(x) = string(round(x, digits = 1))
    "cw " * join((string(round(Int, w)) for w in c4(sp.corner_weight_N)), "/") * " N  rh " * join(f1.(c4(sp.ride_height_mm)), "/") *
    " mm  springs " * join((string(round(Int, k)) for k in c4(sp.spring_rate_Npmm)), "/") * " N/mm  cross " * f1(sp.cross_weight_pct) *
    "%  fuel " * f1(sp.fuel_L) * " L  final " * string(sp.final_drive)
end

function describe_derived(D::Derived)
    f1(x) = string(round(x, digits = 1))
    "cw " * join((string(round(Int, w)) for w in D.cw), "/") * " N  rh " * join(f1.(D.rh), "/") *
    " mm  shock " * join(f1.(D.shock), "/") * " mm  camber " * join(f1.(D.camber), "/") *
    "  cross " * f1(D.cross) * "%  toeF " * string(round(Int, D.toe_front))
end

# ── the exported .ibt: its CarSetup block says the car the garage built (SETUPMODEL-1 S3) ─────────────────────────────
"""A ratio as iRacing prints it: two decimals at 1 and above ("1.40"), three below ("0.846")."""
ratio_str(r) = r >= 1 ? @sprintf("%.2f", r) : @sprintf("%.3f", r)

"""    carsetup_yaml(yaml, sp; maxlen) -> String

The session YAML with its CarSetup block rewritten from a setup NamedTuple (apply_garage's), in iRacing's own value
formats, so an exported lap says which car drove it. Lines the garage does not own are left as they are -- except that a
result longer than `maxlen` (the .ibt's reserved space) drops the template's tyre-wear lines (LastHotPressure,
LastTemps*, TreadRemaining: the template session's tyres, not julia's) until it fits."""
function carsetup_yaml(yaml::AbstractString, sp; maxlen::Int = typemax(Int))
    corner = Dict("LeftFront" => :LF, "RightFront" => :RF, "LeftRear" => :LR, "RightRear" => :RR)
    f1(x) = string(round(x, digits = 1)); f0(x) = string(round(Int, x)); sg(x) = (x >= 0 ? "+" : "") * f0(x)
    f1s(x) = (r = round(x, digits = 1); (r == 0 && signbit(r) ? "-" : r >= 0 ? "+" : "") * string(abs(r) == 0 ? 0.0 : r))
    function val(sec, sub, key)
        c = get(corner, sub, nothing)
        if sec == "Chassis" && c !== nothing
            key == "CornerWeight"      && return f0(sp.corner_weight_N[c]) * " N"
            key == "RideHeight"        && return f1(sp.ride_height_mm[c]) * " mm"
            key == "ShockDeflection"   && return f1(sp.shock_defl_mm[c][1]) * " mm " * f1(sp.shock_defl_mm[c][2]) * " mm"
            key == "SpringPerchOffset" && return f1(sp.perch_mm[c]) * " mm"
            key == "SpringRate"        && return f0(sp.spring_rate_Npmm[c]) * " N/mm"
            key == "Packer"            && return f1(sp.packer_mm[c]) * " mm"
            key == "BumpStiffness"     && return sg(sp.bump_clicks[c]) * " clicks"
            key == "ReboundStiffness"  && return sg(sp.rebound_clicks[c]) * " clicks"
            key == "Camber"            && return f1s(sp.camber_deg[c]) * " deg"
        elseif sec == "Tires" && c !== nothing && key == "ColdPressure"
            return f0(sp.cold_pressure_kPa[c]) * " kPa"
        elseif sec == "Chassis" && sub == "Front"
            key == "ArbArms"     && return String(last(split(sp.arb_front)))
            key == "ArbDiameter" && return String(first(split(sp.arb_front)))
            key == "BrakeBias"   && return @sprintf("%.2f%%", sp.brake_bias_pct)
            key == "ToeIn"       && return sg(sp.toe_front_mm) * " mm"
            key == "CrossWeight" && return f1(sp.cross_weight_pct) * "%"
        elseif sec == "Chassis" && sub == "Rear"
            key == "FuelLevel"   && return f1(sp.fuel_L) * " L"
            key == "ArbArms"     && return String(last(split(sp.arb_rear)))
            key == "ArbDiameter" && return String(first(split(sp.arb_rear)))
            key == "ToeIn"       && return sg(sp.toe_rear_mm) * " mm"
        elseif sec == "Drivetrain" && sub == "Transmission"
            key == "FinalDrive" && return ratio_str(sp.final_drive)
            gi = findfirst(==(key), ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear"))
            if gi !== nothing && gi <= length(sp.gear_ratios)
                K = Knobs(; final_drive = sp.final_drive, gears = collect(Float64, sp.gear_ratios))
                return ratio_str(sp.gear_ratios[gi]) * ", " * f1(gear_speeds_kmh(K)[gi]) * " Km/h"
            end
        elseif sec == "Drivetrain" && sub == "Differential"
            key == "ClutchPlates"   && return f0(sp.diff_plates)
            key == "Preload"        && return f0(sp.diff_preload_Nm) * " Nm"
            key == "DriveRampAngle" && return f0(sp.diff_drive_ramp) * " deg"
            key == "CoastRampAngle" && return f0(sp.diff_coast_ramp) * " deg"
        end
        nothing
    end
    lines = split(yaml, '\n'; keepempty = true)
    out = String[]; inblk = false; path = String[]
    for l in lines
        if startswith(l, "CarSetup:")
            inblk = true; push!(out, l); continue
        end
        ind = length(l) - length(lstrip(l, ' '))
        if inblk && !isempty(strip(l)) && ind == 0
            inblk = false
        end
        if inblk && !isempty(strip(l))
            k, v = split(strip(l), ':'; limit = 2)
            depth = ind                       # CarSetup is indented one space per level
            resize!(path, max(depth - 1, 0)); push!(path, String(k))
            if !isempty(strip(v)) && length(path) == 3
                nv = val(path[1], path[2], path[3])
                nv === nothing || (push!(out, l[1:ind] * k * ": " * nv); continue)
            end
        end
        push!(out, String(l))
    end
    y = join(out, '\n')
    if length(y) > maxlen
        wear = r"^\s+(LastHotPressure|LastTemps\w*|TreadRemaining):"
        out = [l for l in out if !occursin(wear, l)]
        y = join(out, '\n')
    end
    y
end

end # module
