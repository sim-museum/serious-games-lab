# Physics-based BRUSH tyre — force from contact-patch mechanics, no Magic-Formula
# shape knobs and no fudge factors.
#
# Model: the tread is a row of elastic bristles.  As the patch rolls through slip,
# each bristle deflects; in the ADHESION zone (leading edge) the deflection grows
# linearly with slip, until the elastic shear exceeds what friction can hold
# (μ·local pressure), past which the bristle SLIDES at μ·pressure.  Integrating the
# adhesion + sliding contributions over a parabolic pressure patch gives the closed
# form (Pacejka, "Tyre and Vehicle Dynamics", the physical brush model):
#
#     F = μ·Fz·(3ξ − 3ξ² + ξ³) = μ·Fz·(1 − (1−ξ)³)   for ξ ≤ 1   (partial sliding)
#     F = μ·Fz                                         for ξ > 1   (full sliding)
#
# with the normalized slip  ξ = (stiffness·slip)/(3·μ).  Everything is PHYSICAL:
#   μ    LATERAL friction (μy)                     → peak cornering grip = μ·Fz
#   μx   LONGITUDINAL friction                      → peak brake/drive grip = μx·Fz
#   Cα   cornering-stiffness coefficient [1/rad]   → CFα = Cα·Fz (lateral slope)
#   Cκ   longitudinal slip-stiffness coefficient   → CFκ = Cκ·Fz (brake/drive slope)
#   kμ   friction load-sensitivity [-]             → μ(Fz) = μ·(1 − kμ·(Fz/Fz0 − 1))
# The friction LIMIT is an ELLIPSE (μx ≠ μy — a real, measured anisotropy: the iRacing
# Lotus brakes at ~1.42 g but corners at ~1.2 g).  CFα ∝ Fz is the brush result for a
# load-independent tread stiffness; kμ adds the measured drop in grip at high load.
# All physical — no Magic-Formula shape knobs, no grip fudge.

"Brush saturation 1−(1−ξ)³ — the adhesion→sliding force fraction (parabolic pressure)."
brush_sat(ξ) = ξ < 1.0 ? ξ*(3.0 - ξ*(3.0 - ξ)) : 1.0

"""IRFIT-261004 BRAKE-2: SLIDING friction below static. Once the whole patch slides (ξ > 1) the friction
falls from the peak toward `rs`·peak as the slide deepens: rs + (1 − rs)·exp(−((ξ − 1)₊/ws)²). Exactly 1
up to ξ = 1 and flat just past it (Gaussian onset), so the adhesion curve and the peak are unchanged;
a LOCKED wheel (κ = −1, ξ ≈ Cκ/3μ ≈ 5) gets rs. Without it the brush held its peak at any slip, so the
car braked at ~1.45 g and never locked, where the gold locks at full pedal and then slides at ~1.0 g."""
brush_slide(ξ, rs, ws) = rs + (1.0 - rs)*exp(-(max(ξ - 1.0, 0.0)/ws)^2)

"Load-sensitive friction coefficient μ(Fz).  The load factor is CLAMPED to [0.4,1.6]:
friction varies with load but can never reach 0 or go negative (which would make the
brush's μ-division blow up on a load transient) — physical AND numerically safe."
brush_mu(Fz, μ, kμ, Fz0) = μ * clamp(1.0 - kμ * (Fz/Fz0 - 1.0), 0.4, 1.6)

# physical tyre parameter sets (front/rear), IDENTIFIED from the iRacing Lotus 49:
#   Cα = the measured low-slip cornering stiffness (20.5/24.0 /rad)  [validate_brush.jl]
#   μx = the measured straight-line BRAKE grip (1.42/1.45 g)         [fit_brush_long.jl]
#   Cκ (longitudinal stiffness) is a physical estimate pending a braking-data fit;
#   kμ (friction load-sensitivity) pending a multi-load (Nürburgring) fit.
# This is a period bias-ply: low stiffness, grip peaks ~9-10° slip, plateaus at μ.
# NO Magic-Formula Cy/Ey shape knobs — the curve SHAPE is pure brush mechanics.
#   μy: the binned-MEDIAN skidpad curve peaks at ~1.2 g, but that median under-states
#   the achievable peak — iRacing's raw peak lateral is ~1.4-1.58 g and the driver
#   corners at ~1.4 g.  μy is set toward that achievable peak so the car grips like the
#   real one (the measured low-slip cornering stiffness Cα is preserved); JM_GRIP scales it.
const _GRIP = parse(Float64, get(ENV, "JM_GRIP", "1.0"))   # global grip trim (feel)
# TYRE-1: ABLATION -- cornering energy loss beyond the brush's slip projection, as a fraction of Σ|Fy·sinα|
# (vehicle_3d.jl `abl`). Identified in the sim's own frame: with the tyre above fixed by the slip-angle fit,
# 0.40 makes the player car's clutch-in cornering scrub match the gold's (tools/scrubval_261002.jl, median
# 1.00 over 0.1-0.7 g; 0.30 -> 0.93, 0.50 -> 1.06). The gold-frame kinematic estimate is lower, 0.11 (90 % CI
# 0.02-0.24): the gold's COASTING samples run ~10-15 % more slip at 0.3-0.5 g than the combined curve the tyre
# is fitted to, so part of their scrub is slip the fitted tyre does not have, and c_abl carries it.
const C_ABL = 0.40
# TYRE-1 (2026-10-03, REVISED same day after the PO's Watkins race: "if I push at all, the car starts
# fishtailing"). μ (lateral), Cα and kμ identified THROUGH THE PLAYER CAR (tools/tyreid_261002.jl) against
# the 261002 gold's steady slip-angle curve (median front/rear axle slip per 0.1 g, Nordschleife +
# Centripetal; Charlotte's banking excluded), SUBJECT TO what the gold also shows:
#   * the car HOLDS the limit -- steady 1.1-1.19 g windows on half throttle, Ring sideslip max 3.7-11°:
#     constant-input step steers at 90/125 km/h must stay below 10° of sideslip;
#   * rear μ is only bounded BELOW by the slip curve (the gold rear never passes ~6° of slip): it is kept
#     between the front's μ and the rear's measured braking grip μx 1.45;
#   * LINEAR understeer (gold front slip 1.7-2x the rear's at low g): rear Cα >= front Cα. Without it
#     the fit took rear 27.0 < front 30.2 and the car could not hold a straight line above ~300 km/h.
#   * HIGH-SPEED POWER STABILITY (PO, Watkins: "rocking at high speed" with FFB, "wandering in 4th and 5th"
#     without; and coming out of the esses the 3rd->4th upshift no longer straightens the oversteer). On full
#     throttle each rear tyre carries ~0.87x its load in drive force (gold WOT pulls; Cκ ~29 measured = the
#     model's 28) and the brush's combined slip costs the rear ~25 % of its cornering stiffness. With rear Cα =
#     front, a 0.5° blip at 240 km/h WOT diverged and a 0.6 g WOT exit SPUN after the upshift. The gold holds
#     WOT straights > 180 km/h (wheel sd 0.7-1.6°, yaw sd 1.0-2.2°/s; sim was 2.9° / 4.2°/s). Rear Cα 34.0:
#     the blip dies (0.19°/s at 2 s), the exit straightens within 1 s of the shift; slip-curve 446 -> 509.
# The first, unconstrained fit (μ 1.22/1.148, Cα 28.97/29.57) matched the slip curve best (score 18) but
# SPUN at 125 km/h on a constant 3° steer at zero throttle -- that was shipped in 261003/261003b.
# Rear Cα 30.21 (= front) shipped briefly (261003 drives 14:35-15:xx). This set: slip-curve score 509 (low g within ~0.15°; at 1.06-1.14 g the front slides deeper and the
# rear less than the gold, i.e. a safer limit), all step steers held, straight at 321 km/h, max steady
# lateral 1.187 g (gold 1.185). μx / Cκ: braking fit, unchanged. The old μ 1.36/1.40 was set by judgement.
# IRFIT-261004 BRAKE-2 (2026-10-04): μx, Cκ and the sliding fraction rs identified through the player car against the
# PO's 261004 steady-pedal stops and lock-ups at the Döttinger Höhe (tools/brakefit_261004.jl): 20 pedal x speed
# bins (deceleration + front/rear κ) and the locked slide (gold 0.957/1.001/1.046 g at 50-216 km/h, sim
# 0.969/1.003/1.050; a lock now STAYS locked at full pedal, 96 % of the stop, as iRacing's does). Was μx 1.42/1.45,
# Cκ 28/28 (not fitted to braking), no sliding drop -- the car braked at ~1.45 g and never locked.
const BRUSH_FRONT = (μ = 1.277*_GRIP, μx = 1.438*_GRIP, Cα = 30.21, Cκ = 23.7, kμ = 0.082, Fz0 = 1415.0, rs = 0.629, ws = 1.5)
const BRUSH_REAR  = (μ = 1.446*_GRIP, μx = 1.498*_GRIP, Cα = 34.0, Cκ = 23.2, kμ = 0.082, Fz0 = 1670.0, rs = 0.629, ws = 1.5)

# CAMBER-1 (2026-10-06): the wheel's inclination γ to the road (BrushTyre `camber = true`). Two physical effects:
#   * camber THRUST -- a leaning tread is pushed sideways as it rolls through the patch, a lateral deflection
#     Cγ·sinγ added to the slip's Cα·sinα. It saturates with the slip (a sliding patch carries μ·Fz whatever
#     the lean), so camber thrust is a LOW-slip effect;
#   * the PEAK lateral friction rises when the tyre leans INTO its slip force and falls when it leans away (the
#     patch pressure moves to one shoulder): μy·(1 + kγ·sinγ·sign(α)), clamped to ±30 %.
# γ itself is the garage's static camber plus the suspension's roll camber (vehicle_3d.jl `rc_f`/`rc_r`).
# Values identified THROUGH THE PLAYER CAR on two independent gold sets, jointly with the upright μ (2026-10-06):
#   * the camber A/B (tools/camberfit_261005.jl): three garage camber sets on the skidpad (default, WW103, the oval
#     set), both directions, each cell at its own speed, scored as differences from the default car so the
#     skidpads' 152/207 kPa pressure split cancels. Upright 0.582°; kγ 6 0.530°, kγ 7 0.515° (μ 1.36).
#   * the TYRE-1 slip curve + stability suite (tools/tyreid_261002.jl, JM_STAB_IBT = the 261004 default car,
#     JM_CAMB_TRY): with μ re-fitted per kγ, kγ 0: 814 (μf 1.277), 3: 515, 5: 470 (1.33), 6: 443 (1.36),
#     7: 444 (1.40), 8: 754 (1.43, holds only 1.10 g). Every point passes the stability checks.
#   kγ 6 is taken: both sets prefer 6-7 over upright, and 6 is the smaller shift. It is LARGE -- ~10 % peak lateral
#   grip per degree of lean -- and that is what the gold says: the tread temperatures show the same thing (WW103's
#   +0.2° right rear runs its outer edge 15-19 °C hotter than the default's -0.5° in left turns).
#   Cγ is NOT identified: 0 to 2.5 /rad moves the A/B by < 0.003°, so it keeps a physical bias-ply 1.0.
#   Roll camber: the A/B wants the front wheel to lean fully with the body (rc_f 1.0, the edge of the physical
#   range; 0.75 is worse); the rear is flat 0.25-1.0, set 0.8 (the rear tread temperatures show it leaning).
# μ: with the lean modelled, the tyre's lateral μ is its UPRIGHT peak. The front's TYRE-1 1.277 was fitted on
# upright tyres and so already carried the roll-camber loss; the camber tyre takes CAMBER_MU instead. Cars built
# without camber (the 2-D model, a car with no setup) keep BRUSH_FRONT/REAR unchanged.
const CAMBER_CG = 1.0          # [1/rad] camber thrust coefficient (thrust/Fz per rad at low slip): physical, not identified
const CAMBER_KG = 6.0          # [1/rad] peak lateral friction gain when leaning into the slip force
const CAMBER_RC = (1.0, 0.8)   # roll camber (front, rear): road inclination change per rad of suspension roll
const CAMBER_MU = (1.36, 1.446) # CAMBER-1 S1's upright μ; superseded by TYRE2 below (kept for the record and the tools)

# TYRE-2 S1 (2026-10-06): the camber tyre's lateral side refitted THROUGH THE PLAYER CAR on the skidpad cells
# (tools/tyre2fit_261005.jl: three garage setups, both directions, each cell at its own speed, g and longitudinal
# acceleration; absolute slips + the camber A/B + holding 1.10 g + the stability suite). From CAMBER-1 S1's tyre
# (μ 1.36/1.446, Cα 30.21/34.0): absolute slip error 0.696 -> 0.320°, A/B 0.526 -> 0.538°, 1.10 g held both ways,
# stability penalty 0. The gold's ~20 % more mid-range slip is LOWER CORNERING STIFFNESS, not load sensitivity: the
# stiffness load exponent (BRUSH_NS) went free and came back 0.989, so it stays 1. Rear μ sits on its bound, the rear's
# braking μx. Rear Cα 27.8 is below TYRE-1's 34, which was raised for full-throttle stability above 200 km/h; with
# the LSD and camber now in the car, that check still passes (yaw left at 3 s after a 0.5° blip at 240 km/h: 0.06,
# limit 0.10) -- see the stability suite (tools/stability_check.jl, JM_STAB_IBT) for both setups.
const TYRE2 = (μf = 1.347, μr = 1.494, Cαf = 26.17, Cαr = 27.77)

# TYRE-2 (2026-10-06): the slip stiffnesses' load exponent (BrushTyre `ns`): CFα, CFκ ∝ Fz^ns. 1 = the plain brush.
const BRUSH_NS = 1.0

"Pure-lateral brush force Fy(Fz, α) — for fitting/validation."
function brush_fy(Fz, α; p = BRUSH_FRONT)
    μ = brush_mu(Fz, p.μ, p.kμ, p.Fz0)
    ξ = p.Cα*abs(sin(α)) / (3.0*μ)
    sign(α) * μ*Fz * brush_sat(ξ) * brush_slide(ξ, p.rs, p.ws)
end

"Pure-longitudinal brush force Fx(Fz, κ) — uses the LONGITUDINAL friction μx."
function brush_fx(Fz, κ; p = BRUSH_FRONT)
    μ = brush_mu(Fz, p.μx, p.kμ, p.Fz0)
    ξ = p.Cκ*abs(κ) / (3.0*μ)
    sign(κ) * μ*Fz * brush_sat(ξ) * brush_slide(ξ, p.rs, p.ws)
end

"""Combined brush force (Fx, Fy).  The deflection vector is (Cκ·κ, Cα·sinα); the
friction LIMIT is an ellipse (μx longitudinal, μy lateral), so the directional
friction is μ_dir = 1/√((cosψ/μx)² + (sinψ/μy)²) along the deflection direction ψ.
Magnitude = μ_dir·Fz·brush_sat(ξ).  Pure lateral ⇒ μy·Fz; pure longitudinal ⇒ μx·Fz;
the friction ellipse + the per-direction stiffness emerge from the physics."""
function brush_forces(Fz, α, κ; p = BRUSH_FRONT)
    μy = brush_mu(Fz, p.μ,  p.kμ, p.Fz0)
    μx = brush_mu(Fz, p.μx, p.kμ, p.Fz0)
    # per-axis NORMALIZED slip (1 = that axis's friction limit) — the ellipse lives here,
    # and this form has NO 1/0 at zero slip (the force → 0 there, cleanly).
    ξx = p.Cκ*κ / (3.0*μx);  ξy = p.Cα*sin(α) / (3.0*μy)
    ξ  = sqrt(ξx^2 + ξy^2 + 1e-9)              # floor INSIDE the sqrt → the autodiff Jacobian
    s  = brush_sat(ξ) * brush_slide(ξ, p.rs, p.ws)   # is finite at zero slip (sqrt(0)' = 0/0 = NaN otherwise)
    (μx*Fz*s*ξx/ξ, μy*Fz*s*ξy/ξ)              # along the deflection dir; magnitude on the friction ellipse
end
