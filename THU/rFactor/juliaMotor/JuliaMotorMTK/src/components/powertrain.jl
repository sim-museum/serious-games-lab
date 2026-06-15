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

# Cosworth-DFV-like torque curve [N·m] (heuristic — fit to telemetry later via
# T_wheel = I·ω̇ + Fx·Rw from acceleration runs).  Smooth in rpm & throttle.
function engine_torque(rpm, throttle; Tpeak = 360.0, rpm_peak = 7500.0,
                       spread = 4500.0, redline = 9500.0, eb = 0.012, Tmin_frac = 0.2)
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
