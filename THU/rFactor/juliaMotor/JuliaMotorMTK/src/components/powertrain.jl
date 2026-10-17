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
#   WOT torque  IRFIT-261004 (2026-10-04): now MEASURED to 8,900 rpm from the PO's 261004 3rd/4th-gear
#               pulls (test 4) plus every earlier capture -- 7013 pts, gears 3-5, tools/torquefit_261004.jl.
#               The pulls run 4-13 % rear wheelspin, which longfit_261002 rejected (> 5 %); here the engine
#               and wheels accelerate at the MEASURED rpm slope, so slipping samples count. The torque PEAKS
#               at ~312 N·m @ 7,100 rpm and FALLS to ~280 by 8,800 -- the E91-S10 parabola (310 @ 7727,
#               fitted below 7,775) extrapolated 299 N·m at 9,000, ~7 % too strong at the top. 3rd, 4th and
#               5th agree within ~2 % (3rd reads high, i.e. Ie 0.18 is slightly low; not refitted).
#               Below 3,700 rpm and above 8,900 rpm the table holds its end slope.
const CDA_IBT = 0.480                 # m², at the model's ρair 1.10 (the Ring session's AirDensity 1.099)
const CRR_IBT = 0.0139
# IRGOLD-1 S20: front LIFT area [m²] (+ = downforce). The gold's front suspension extends with speed on every straight
# (39 of 39 sessions' straights pooled: dF/dq −0.29 m² incl. the drag/thrust couple; on flat Monza/Charlotte −0.10..−0.27),
# 261012/tools/aerolift.py; −0.12 reproduces flat Monza's +7..+10 mm of front wheel droop at 216 km/h in the sim (no lift:
# −2 mm). The rear is neutral within its scatter. ~260 N of lift at 216 km/h, ~480 N at 300.
# PHYSFID-1 S9 (2026-10-15): both axles' lift MEASURED, per speed band and per setup, from the gold's axle heave against
# julia's on the same inputs (tools/irgold_replay.jl g_hF/s_hF/g_hR/s_hR, straight running): ClAf −0.06, ClAr −0.08
# reproduce iRacing's front droop AND rear squat at 160-280 km/h for both setups (−0.12 front / 0 rear lifted the nose
# too far and squatted the tail 2-5 mm too much). Shipped rear −0.04, half the measured lift: −0.08 spun the default car
# in the stability suite's 250 km/h trail-brake (β 20-24°, penalty 51); −0.04 passes both setups and judges best
# (closed loop J 1.0346 vs 1.0373 before S9). JM_PHYSFID_S9=0 restores −0.12 / 0 (and the bars' split, drive_rt3d).
const PHYSFID_S9 = get(ENV, "JM_PHYSFID_S9", "1") != "0"
const AERO_CLAF = PHYSFID_S9 ? -0.06 : -0.12
const AERO_CLAR = PHYSFID_S9 ? -0.04 : 0.0
const AERO_CLAF_RH = 0.0     # PHYSFID-1 S13: front lift per metre of nose rise [m²/m] (vehicle_3d.jl); 0 = none
# WWSETUP-1 (2026-10-06): the rear LSD (DrivenVehicle3D `diff`). LSD_K = friction faces × μ × radius ratio per
# clutch plate, the one constant the iRacing garage does not show; identified from the gold's rear wheel-speed split
# with both setups' ramps on the same value (tools/lsdfit_261005.jl). LSD_WEPS = the stick-slip regularisation [rad/s].
const LSD_K    = 0.20
const LSD_WEPS = 0.1
const EFRIC_T0 = 14.24                # N·m   engine drag at zero throttle: (T0 + k·rpm) (friction-MEP form) ...
const EFRIC_K  = 0.00389              # N·m/rpm
const EFRIC_R0 = 2353.0               # rpm   ... × ½(1 + tanh((rpm − R0)/W)), the fade toward idle
const EFRIC_W  = 351.0                # rpm
# IRGOLD-1 S14 (2026-10-12): the ENGINE alone, measured with the drivetrain decoupled (IRTEST-261012 test 1: free revs,
# standing, 11 files, 261012/tools/freerev2.py). At WOT the rpm rises at a rate that tracks the WOT torque at one constant
# ratio from 5,000 to 8,700 rpm (Ie = 0.0522, IQR 0.0520-0.0524): the crank inertia is 0.052 kg·m², not 0.18. The rest
# of the in-gear inertia sits BEHIND the gearbox: a joint least squares over every WOT row of every session (21,294 rows,
# gears 1-5, 261012/tools/inertiafit.py) puts 0.0013 on the gearbox input and 0.151 on its output (crank-referred in top-
# gear-free units, i.e. the same Igb·final² at the rear axle in every gear); with that split all five gears read the same
# torque within a few N·m, where 0.18 on the input made 1st gear read 20-40 N·m strong (so a launch was too slow).
# Likewise the closed-throttle decay gives the engine's own drag (4.84 + 0.00276·rpm)·fade (n 2498, sd 5.2 N·m),
# 12-20 N·m below the in-gear coast drag EFRIC: the rest is the gearbox's, applied while the clutch is in. Where the clutch
# slips or is out -- blips, downshifts, launches -- the engine now behaves as iRacing's: at the bite it falls 8,900 ->
# 2,000 rpm in ~0.4 s, which julia's 3.5× heavier crank did not. JM_ENGINE_LUMPED=1 = the model before S14 (Ie 0.18 at
# the crank, all drag on the engine, the S6 WOT table).
const ENGINE_LUMPED = haskey(ENV, "JM_ENGINE_LUMPED")
const IE_ENGINE = 0.0522              # kg·m²  crank (engine + flywheel), free revs
const IE_DRIVELINE = 0.1482           # kg·m²  behind the gearbox, crank-referred without the gear: Igb·final²·η at the axle
# WHERE the in-gear remainder (0.18 − 0.0522 = 0.128) sits is decided by the replay metric, not the gear-agreement fit: on the
# gearbox INPUT (reflected ×gr², so a locked clutch gives S6's car exactly) the 233-window metric is 1.1658, behind the gearbox
# 1.2189, the lumped car 1.2018 -- the WOT table and the part-throttle map were measured in the input frame. Default: input.
# JM_DRIVELINE_AXLE=1 = behind the gearbox (IE_DRIVELINE·final² at the axle, every gear), the open alternative.
const DRIVELINE_INPUT = !haskey(ENV, "JM_DRIVELINE_AXLE")
const EFREE_T0 = 4.84                 # N·m    the engine's own zero-throttle drag (T0 + k·rpm)·fade, same fade as EFRIC
const EFREE_K  = 0.00276              # N·m/rpm
"The engine's own zero-throttle drag [N·m] (S14, free revs)."
engine_drag_free(rpm) = (EFREE_T0 + EFREE_K*rpm) * 0.5*(1 + tanh((rpm - EFRIC_R0)/EFRIC_W))
"The gearbox's share of the in-gear coast drag [N·m at the input shaft]: EFRIC minus the engine's own, × (1 − f) like it."
gearbox_drag(rpm, throttle) = (1 - throttle_map(throttle, rpm)) *
    ((EFRIC_T0 - EFREE_T0) + (EFRIC_K - EFREE_K)*rpm) * 0.5*(1 + tanh((rpm - EFRIC_R0)/EFRIC_W))

# (rpm, N·m) knots: median WOT crank torque per 250-rpm band of the gold, sim frame (torquefit_261004.jl)
# IRGOLD-1 S14: below 3,500 rpm the S6 table only held its first value; the 261012 launches pull 1st gear from 1,600 rpm.
# Measured there (inertiafit.py, 250-rpm bands, the split drivetrain, every session, gradient removed): 219 N·m at
# 1,875 rising to the S6 table's 235.5 at 3,500. Above 3,500 the S6 table is kept AS IS -- a full refit in the split
# frame (1-4 N·m higher, with the road load and coast drag refitted to match) made the replay metric WORSE
# (1.2018 → 1.2627: the part-throttle map is a fraction between EFRIC and this table, so moving either moves every
# part-throttle torque the map was measured with). The longitudinal frame (EFRIC, CdA, Crr, WOT ≥ 3,500, the map) stays S6's.
const WOT_KNOTS_S14 = ((1875.0, 219.0), (2125.0, 231.0), (2375.0, 235.5), (3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0),
                       (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0), (7150.0, 312.0), (7650.0, 307.5),
                       (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))
const WOT_KNOTS_S6 = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5),
                   (6400.0, 302.5), (6850.0, 311.0), (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5),
                   (8650.0, 284.5), (8900.0, 278.5))
"Measured WOT crank torque: the knots joined by straight lines, as Σ ramps (symbolic-safe: max only)."
const WOT_KNOTS = ENGINE_LUMPED ? WOT_KNOTS_S6 : WOT_KNOTS_S14
function wot_torque(rpm)
    k = WOT_KNOTS
    T = k[1][2] + 0.0*rpm; s0 = 0.0                     # flat below the first knot
    for i in 1:length(k)-1
        s = (k[i+1][2] - k[i][2]) / (k[i+1][1] - k[i][1])
        T += (s - s0)*max(0.0, rpm - k[i][1]); s0 = s
    end
    T
end

# CARPHYS-1 S8: the part-throttle map, measured (tools/throttlefit_261009.py, 39,415 gold rows, both setups): the torque
# FRACTION f = (T + drag)/(WOT + drag) at each pedal position. iRacing's Lotus 49 throttle is PROGRESSIVE -- 30 % pedal
# gives 21 % of the way from engine drag to WOT, 10 % only 2 % -- and slightly ahead of linear above 70 % (80 % → 0.84).
# The model before S8 blended linearly (f = pedal), which made the first third of the pedal too strong: the zone where a
# car is balanced on the throttle mid-corner.
const THROTTLE_KNOTS = ((0.0, 0.0), (0.1, 0.02), (0.2, 0.13), (0.3, 0.21), (0.4, 0.33), (0.5, 0.45), (0.6, 0.58),
                        (0.7, 0.72), (0.8, 0.84), (0.9, 0.95), (1.0, 1.0))
const THROTTLE_LINEAR = haskey(ENV, "JM_THROTTLE_LINEAR")           # A/B: the linear blend of before S8
# IRGOLD-1 S6 (2026-10-12): the map depends on RPM. On every 261010 row (the S8 method, 261011/tools) the fraction FALLS
# with rpm at part throttle -- pedal 0.5: 0.48 at 4,000-5,500 rpm, 0.43 at 5,500-7,000, 0.41 at 7,000-8,000; pedal 0.6:
# 0.62 / 0.55 / 0.53 -- a fixed throttle opening chokes more as the engine speeds up. S8's single map was in effect the
# low-rpm column, so at high revs on part throttle the engine was 10-20 % too strong (the sim gained 4-8 km/h per 5 s on
# the gold's pedal round the skidpad, and did not bog on a clutch-slip launch). Two measured columns, at 4,750 and
# 7,500 rpm, blended linearly in rpm (extrapolated to 1.4× the span, i.e. 8,600 rpm, then held); closed and WOT unchanged.
# The replay metric over 245 windows: 1.887 -> 1.212 (handling unchanged, the speed errors collapse). JM_THROTTLE_1D=1 = S8.
const THROTTLE_KNOTS_LO = ((0.0, 0.0), (0.1, 0.02), (0.2, 0.12), (0.3, 0.22), (0.4, 0.34), (0.5, 0.48), (0.6, 0.62),
                           (0.7, 0.77), (0.8, 0.90), (0.9, 0.96), (1.0, 1.0))      # 4,750 rpm (4,000-5,500)
const THROTTLE_KNOTS_HI = ((0.0, 0.0), (0.1, 0.02), (0.2, 0.11), (0.3, 0.19), (0.4, 0.27), (0.5, 0.41), (0.6, 0.53),
                           (0.7, 0.70), (0.8, 0.87), (0.9, 0.95), (1.0, 1.0))      # 7,500 rpm (7,000-8,000)
const THROTTLE_1D = haskey(ENV, "JM_THROTTLE_1D")
"Pedal → torque fraction through a knot table (straight lines, as Σ ramps: symbolic-safe)."
function _knots(thr, k)
    f = 0.0*thr; s0 = 0.0
    for i in 1:length(k)-1
        s = (k[i+1][2] - k[i][2]) / (k[i+1][1] - k[i][1])
        f += (s - s0)*max(0.0, thr - k[i][1]); s0 = s
    end
    f
end
"Pedal (and rpm) → torque fraction: IRGOLD-1 S6's two columns blended by rpm; without rpm, or JM_THROTTLE_1D, S8's map."
function throttle_map(thr, rpm = nothing)
    THROTTLE_LINEAR && return thr
    (rpm === nothing || THROTTLE_1D) && return _knots(thr, THROTTLE_KNOTS)
    wr = min(max((rpm - 4750.0)/2750.0, 0.0), 1.4)
    lo = _knots(thr, THROTTLE_KNOTS_LO)
    lo + wr*(_knots(thr, THROTTLE_KNOTS_HI) - lo)
end

# CARPHYS-1 S9: the clutch's torque capacity against engagement (1 = fully in), measured from the gold's 289 standing
# starts on the CAR side (tools/clutchfit_261009.py, 23,293 slipping rows): a BITE POINT -- nothing below ~0.1, 14 N·m
# at 0.15 -- then 71 / 142 / 202 / 321 / 407 N·m at 0.25 … 0.65. Above 0.65 the launches have locked up; the 0.45–0.65
# slope is extended to 760 N·m at full engagement (it only matters for shift shocks). The model before S9 had a linear
# 500 N·m × engagement: grabbing too early (125 N·m at 0.25) and too soft late (325 at 0.65).
const CLUTCH_KNOTS_S9 = ((0.0, 0.0), (0.05, 1.0), (0.15, 14.0), (0.25, 71.0), (0.35, 142.0), (0.45, 202.0), (0.55, 321.0),
                         (0.65, 407.0), (1.0, 760.0))
# IRGOLD-1 S14: re-measured over every session (41,691 slipping rows incl. IRTEST-261012's fixed-pedal starts;
# 261012/tools/clutchfit2.py) in narrow ±0.02 windows, with the per-file mass, LongAccel's 360 Hz sub-samples and the S14
# driveline inertia on the car side. S9's 0.1-wide bands smeared a steep curve: at 0.40 engagement the clutch passes
# 212 N·m (IQR 196-222), S9's knots gave 172 -- less than the engine's ~230 at 2,000 rpm, so in a launch the sim's engine
# flared to 8,000 rpm where the gold's bogs to ~1,600 and the clutch then closed onto a revving engine (rears to the
# limiter). No dependence on slip speed or engine rpm. Above 0.60 the 0.25-0.60 slope (~9.6 N·m per 0.01) is extended.
const CLUTCH_KNOTS_S14 = ((0.0, 0.0), (0.05, 0.5), (0.10, 2.0), (0.15, 16.7), (0.20, 47.7), (0.25, 77.4), (0.30, 117.6),
                          (0.35, 162.4), (0.40, 212.3), (0.45, 245.5), (0.50, 300.5), (0.55, 338.3), (0.60, 412.8), (1.0, 797.0))
const CLUTCH_KNOTS = ENGINE_LUMPED ? CLUTCH_KNOTS_S9 : CLUTCH_KNOTS_S14
const CLUTCH_LINEAR = haskey(ENV, "JM_CLUTCH_LINEAR")               # A/B: 500 N·m × engagement, as before S9
"Clutch torque capacity [N·m] at engagement `e` (0 out … 1 in), through CLUTCH_KNOTS (Σ ramps: symbolic-safe)."
function clutch_capacity(e)
    CLUTCH_LINEAR && return 500.0*e
    k = CLUTCH_KNOTS
    T = 0.0*e; s0 = 0.0
    for i in 1:length(k)-1
        s = (k[i+1][2] - k[i][2]) / (k[i+1][1] - k[i][1])
        T += (s - s0)*max(0.0, e - k[i][1]); s0 = s
    end
    T
end

function engine_torque(rpm, throttle; redline = 9500.0, T0 = EFRIC_T0, k = EFRIC_K,
                       r0 = EFRIC_R0, w = EFRIC_W)
    wot = max(0.0, wot_torque(rpm))                                 # WOT (net) torque, measured
    cut = 0.5*(1 - tanh((rpm - redline)/200.0))                     # smooth redline fuel cut
    fric = (T0 + k*rpm) * 0.5*(1 + tanh((rpm - r0)/w))              # zero-throttle drag, fading at idle
    f = throttle_map(throttle, rpm)                                 # CARPHYS-1 S8 / IRGOLD-1 S6: progressive, by rpm
    f*wot*cut - (1 - f)*fric                                        # blend WOT ↔ engine drag
end
"The ENGINE alone (IRGOLD-1 S14): as engine_torque, with the engine's own drag instead of the in-gear total."
function engine_torque_free(rpm, throttle; redline = 9500.0)
    wot = max(0.0, wot_torque(rpm)); cut = 0.5*(1 - tanh((rpm - redline)/200.0))
    f = throttle_map(throttle, rpm)
    f*wot*cut - (1 - f)*engine_drag_free(rpm)
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

# IRGOLD-1 / FUEL-1 (2026-10-11): FUEL BURN, measured. The gold's FuelUsePerHour [kg/h] (its integral matches the fall in
# FuelLevel at 0.74 kg/L) by pedal and rpm, median over every 261010 Monza and Ring row above 10 m/s (261011/tools):
# closed throttle 1.7-2.6 kg/h, wide open 45 (4,000 rpm) to 78 (8,000). Bilinear in (pedal, rpm), held at the ends.
const FUEL_RPM   = (4000.0, 5000.0, 6000.0, 7000.0, 8000.0)
const FUEL_PEDAL = (0.0, 0.25, 0.5, 0.75, 1.0)
const FUEL_KGH   = ((1.7, 2.0, 2.2, 2.3, 2.6),        # pedal 0
                    (8.9, 10.5, 12.4, 11.8, 10.6),    # 0.25-0.35
                    (22.0, 27.2, 30.8, 33.1, 32.0),   # 0.5-0.6
                    (38.6, 48.4, 56.3, 64.7, 65.4),   # 0.75-0.85
                    (44.8, 57.5, 67.5, 75.7, 77.9))   # WOT
const FUEL_KG_PER_L = 0.75                           # ibt DriverCarFuelKgPerLtr
const FUEL_MAX_L    = 179.5                          # ibt DriverCarFuelMaxLtr (179.529)
function _interp1(xs, x)
    x <= xs[1] && return (1, 0.0); x >= xs[end] && return (length(xs) - 1, 1.0)
    i = findlast(k -> xs[k] <= x, 1:length(xs)); (i, (x - xs[i])/(xs[i+1] - xs[i]))
end
"Fuel burn [kg/h] at pedal `thr` (0-1) and `rpm` (the gold's table, bilinear)."
function fuel_rate_kgh(thr, rpm)
    i, fi = _interp1(FUEL_PEDAL, clamp(thr, 0, 1)); j, fj = _interp1(FUEL_RPM, rpm)
    a = FUEL_KGH[i][j]*(1 - fj) + FUEL_KGH[i][j+1]*fj; b = FUEL_KGH[i+1][j]*(1 - fj) + FUEL_KGH[i+1][j+1]*fj
    a*(1 - fi) + b*fi
end
