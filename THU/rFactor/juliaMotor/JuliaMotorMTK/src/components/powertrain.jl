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

# E91-S10 (2026-10-03): the LONGITUDINAL model, refit from the PO's 2026-10-02 iRacing test session
# (`gold standard/julia racer/261002`: straight-line clutch-in AND in-gear coast-downs to 221 km/h on
# the Döttinger Höhe and Charlotte, plus full-throttle pulls). tools/longfit_261002.jl solves every
# number below IN THIS MODEL'S OWN EQUATION OF MOTION (m + wheel + engine inertia, η, Rw_r = 0.334),
# so putting them back in reproduces the gold; tools/longval_261002.jl is the acceptance test.
#
# PO 2026-08-27: "the car physics should be determined entirely by the iracing ibt data, there should
# be no modifiable parameters." These replace ENGBRAKE = 0.012, CdA = 0.9, Crr = 0.026 and a
# 409 N·m torque curve, none of which were from an ibt -- and which were coupled: the old torque
# was fitted ASSUMING CdA 0.9, so too much drag was hidden by too much torque (E91-S9). Before this
# refit the car decelerated 1.87x the gold off-throttle (clutch in) and 1.86x in gear (the PO's
# "Tesla brakes", E91).
#
#   road load   (9399 pts, 26 clutch-in coasts, 29-221 km/h)  CdA 0.480 m² (90% CI 0.472-0.484),
#               Crr 0.0139 (0.0132-0.0156), residual sd 0.035 m/s², no per-track bias
#   engine drag (13993 pts, 39 in-gear coasts, gears 1-5)     T = (14.24 + 0.00389·rpm)·fade N·m,
#               fade = ½(1 + tanh((rpm − 2353)/351)), bin RMS 2.2 N·m over 1800-6200 rpm. Gears 1, 2, 4
#               and 5 agree within ~2 N·m, which also corroborates Ie = 0.18. The FADE is measured, not
#               shaped: approaching the 2000 rpm idle the gold's drag falls to ~0 (its idle governor
#               fuels the engine in gear too) -- without it a 5th-gear coast below 90 km/h ran
#               1.3-2.3x too hard. (Gold dips to −5 N·m below idle, i.e. the governor drives; not modelled.)
#   WOT torque  (1830 pts, 4th + 5th, 4300-7775 rpm)          Tpeak 310 N·m @ 7727 rpm, spread 6742,
#               bin RMS 3.2 N·m; 4th and 5th agree within ~1 %. ABOVE 7775 rpm IS EXTRAPOLATED
#               (no gold yet) -- the fit gives ~287 kW (385 hp) at 9500 and a rev-limited 335 km/h
#               in 5th on Ring gearing, which the PO's analysis predicted (~206 mph).
const CDA_IBT = 0.480                 # m², at the model's ρair 1.10 (the Ring session's AirDensity 1.099)
const CRR_IBT = 0.0139
const EFRIC_T0 = 14.24                # N·m   engine drag at zero throttle: (T0 + k·rpm) (friction-MEP form) ...
const EFRIC_K  = 0.00389              # N·m/rpm
const EFRIC_R0 = 2353.0               # rpm   ... × ½(1 + tanh((rpm − R0)/W)), the fade toward idle
const EFRIC_W  = 351.0                # rpm

function engine_torque(rpm, throttle; Tpeak = 310.0, rpm_peak = 7727.0,
                       spread = 6742.0, redline = 9500.0, T0 = EFRIC_T0, k = EFRIC_K,
                       r0 = EFRIC_R0, w = EFRIC_W, Tmin_frac = 0.2)
    wot = Tpeak * max(Tmin_frac, 1 - ((rpm - rpm_peak)/spread)^2)   # WOT (net) torque
    cut = 0.5*(1 - tanh((rpm - redline)/200.0))                     # smooth redline fuel cut
    fric = (T0 + k*rpm) * 0.5*(1 + tanh((rpm - r0)/w))              # zero-throttle drag, fading at idle
    throttle*wot*cut - (1 - throttle)*fric                          # blend WOT ↔ engine drag
end

# Straight-line longitudinal vehicle: states u (speed), ωf, ωr (axle wheel speeds).
# throttle, brake, gear are constant parameters per run.
function LongitudinalVehicle(; name,
        m = 617.0, Rw_f = 0.30, Rw_r = 0.334, Iw = 1.0, Ieng = 0.10, η = 0.9,
        gear = 1.72, final = 4.11, bias = 0.535, Tbrake_max = 3000.0,
        CdA = CDA_IBT, ρair = 1.10, Fzf = 2752.0, Fzr = 3300.0,
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
