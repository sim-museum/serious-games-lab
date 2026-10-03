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
# TYRE-1 (2026-10-03): μ (lateral), Cα and kμ IDENTIFIED THROUGH THE PLAYER CAR against the 261002 gold's
# steady cornering curve -- median front/rear axle slip angle per 0.1 g, 0.15-1.14 g, Nordschleife +
# Centripetal (tools/tyreid_261002.jl; Charlotte excluded, its banking inflates LatAccel/g). Score 222 -> 9.8:
# both axles within ~0.2° everywhere, including the front's 6-8° plateau at 1.06-1.14 g, which is where
# "turn the wheel and scrub off speed" lives. The old μ 1.36/1.40 was set by judgement toward a raw peak, and
# the soft Cα 20.5/24 made the car run ~1.4x the gold's slip at mid g -- which happened to give iRacing's scrub
# only because it stood in for the ablation loss (C_ABL) the model lacked.  μx / Cκ: braking fit, unchanged.
const BRUSH_FRONT = (μ = 1.220*_GRIP, μx = 1.42*_GRIP, Cα = 28.97, Cκ = 28.0, kμ = 0.081, Fz0 = 1415.0)
const BRUSH_REAR  = (μ = 1.148*_GRIP, μx = 1.45*_GRIP, Cα = 29.57, Cκ = 28.0, kμ = 0.081, Fz0 = 1670.0)

"Pure-lateral brush force Fy(Fz, α) — for fitting/validation."
function brush_fy(Fz, α; p = BRUSH_FRONT)
    μ = brush_mu(Fz, p.μ, p.kμ, p.Fz0)
    ξ = p.Cα*abs(sin(α)) / (3.0*μ)
    sign(α) * μ*Fz * brush_sat(ξ)
end

"Pure-longitudinal brush force Fx(Fz, κ) — uses the LONGITUDINAL friction μx."
function brush_fx(Fz, κ; p = BRUSH_FRONT)
    μ = brush_mu(Fz, p.μx, p.kμ, p.Fz0)
    ξ = p.Cκ*abs(κ) / (3.0*μ)
    sign(κ) * μ*Fz * brush_sat(ξ)
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
    s  = brush_sat(ξ)                          # is finite at zero slip (sqrt(0)' = 0/0 = NaN otherwise)
    (μx*Fz*s*ξx/ξ, μy*Fz*s*ξy/ξ)              # along the deflection dir; magnitude on the friction ellipse
end
