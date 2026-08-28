# Powertrain + brakes: the longitudinal driveline that GENERATES slip ratio κ
# from throttle/brake, instead of prescribing it.  Engine torque curve → rigid
# driveline (gear × final drive) → rear wheels (RWD); brakes split front/rear by
# bias act on all wheels.  Wheel-spin states ωf/ωr give κ = (ω·Rw − u)/u, the
# tyre returns Fx, and the body longitudinal speed u integrates ΣFx − drag.
#
# Rigid driveline (clutch locked, in gear): engine speed is kinematically tied to
# the rear wheel, ω_eng = ωr·gear·final, so the engine adds a reflected inertia
# Ieng·(gear·final)² rather than a separate stiff clutch state.  Front/rear wheels
# are lumped (L/R share speed — exact in a straight line).
#
# Requires the tyre law (tyre_law.jl) for tyre_fx.

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

# Cosworth-DFV torque curve [N·m], FIT to telemetry (fit/fit_engine.jl): peak
# 409 N·m at ~8200 rpm, matching WOT straight-line accel across 4400–7100 rpm
# (rpm_peak pinned to the DFV-realistic range since clean accel data only reveals
# the rising part).  Smooth in rpm & throttle.  ±~20% absolute (CdA/η/Rw/inertia).
# PO 2026-08-27, after driving Monza: "I never needed to use the brakes ever, which is not right",
# and "if I put the clutch in I should be coasting, but in fact I'm decelerating a lot".
#
# ⚠️ A DEFAULT CHANGE WAS PREPARED HERE AND REVERTED. The first pass measured the PO's coast-downs
# WITHOUT separating clutch-in from clutch-out, attributed the whole deceleration to the engine,
# and concluded eb was ~1.5x too high. Splitting by the clutch column — which the telemetry has
# had all along — says otherwise:
#
#   clutch IN  (engage=0, Tcl=0, so NO engine braking)   130 km/h  1.24 m/s^2   (model: 1.30)
#                                                          96 km/h  1.06 m/s^2   (model: 0.83)
#   clutch OUT (in gear)                          5th, 161 km/h  2.56  -> engine ~0.7
#                                                 4th, 126 km/h  2.86  -> engine ~1.6
#
# So engine braking is 0.7-1.6 m/s^2 (0.07-0.16 g), which is normal, and what actually dominates a
# clutch-in coast is AERO DRAG. That is calibrated, not arbitrary: CdA=0.9 needs ~420 hp to hold
# 300 km/h, which is a DFV at 1967 Monza. Lowering eb would have made the car wrong in order to
# make one complaint go away.
# PO 2026-08-27: "the car physics should be determined entirely by the iracing ibt data, there
# should be no modifiable parameters." JM_ENGBRAKE is REMOVED for that reason. The value must come
# from the reference, not from a knob — JuliaMotorMTK/tools/engbrake_probe.jl exists to measure
# exactly this against a real iRacing coast-down.
const ENGBRAKE = 0.012

function engine_torque(rpm, throttle; Tpeak = 409.0, rpm_peak = 8211.0,
                       spread = 6000.0, redline = 9500.0, eb = ENGBRAKE, Tmin_frac = 0.2)
    wot = Tpeak * max(Tmin_frac, 1 - ((rpm - rpm_peak)/spread)^2)   # WOT torque
    cut = 0.5*(1 - tanh((rpm - redline)/200.0))                     # smooth redline fuel cut
    throttle*wot*cut - (1 - throttle)*eb*rpm                        # blend WOT ↔ engine braking
end

# Straight-line longitudinal vehicle: states u (speed), ωf, ωr (axle wheel speeds).
# throttle, brake, gear are constant parameters per run.
function LongitudinalVehicle(; name,
        m = 617.0, Rw_f = 0.30, Rw_r = 0.33, Iw = 1.0, Ieng = 0.10, η = 0.9,
        gear = 1.72, final = 4.11, bias = 0.535, Tbrake_max = 3000.0,
        CdA = 0.9, ρair = 1.10, Fzf = 2752.0, Fzr = 3300.0,
        throttle = 1.0, brake = 0.0,
        tyre_f = TYRE_SKIDPAD_FRONT, tyre_r = TYRE_SKIDPAD_REAR)
    ps = @parameters m=m Rw_f=Rw_f Rw_r=Rw_r Iw=Iw Ieng=Ieng η=η gear=gear final=final bias=bias Tbrake_max=Tbrake_max CdA=CdA ρair=ρair Fzf=Fzf Fzr=Fzr throttle=throttle brake=brake
    vars = @variables u(t)=15.0 ωf(t)=50.0 ωr(t)=45.0 rpm(t) κf(t) κr(t) Fxf(t) Fxr(t) ax(t)
    gr = gear*final
    eqs = [
        rpm ~ ωr*gr*60/(2π),
        κf  ~ (ωf*Rw_f - u)/(u + 0.5),                 # slip ratios (guard u→0)
        κr  ~ (ωr*Rw_r - u)/(u + 0.5),
        Fxf ~ 2*tyre_fx(Fzf/2, κf; p = tyre_f),        # two front wheels at half axle load
        Fxr ~ 2*tyre_fx(Fzr/2, κr; p = tyre_r),        # two rear wheels (driven)
        # wheel rotational dynamics (brake opposes spin; tyre reaction −Fx·Rw)
        2*Iw*D(ωf) ~ -brake*Tbrake_max*bias*tanh(ωf) - Fxf*Rw_f,
        (2*Iw + Ieng*gr^2)*D(ωr) ~ engine_torque(rpm, throttle)*gr*η
                                   - brake*Tbrake_max*(1 - bias)*tanh(ωr) - Fxr*Rw_r,
        # body longitudinal
        ax ~ (Fxf + Fxr - 0.5*ρair*CdA*u^2)/m,
        D(u) ~ ax,
    ]
    System(eqs, t, vars, ps; name)
end
