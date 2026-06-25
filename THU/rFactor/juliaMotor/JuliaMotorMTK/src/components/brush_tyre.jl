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

"Load-sensitive friction coefficient μ(Fz)."
brush_mu(Fz, μ, kμ, Fz0) = μ * (1.0 - kμ * (Fz/Fz0 - 1.0))

# physical tyre parameter sets (front/rear), IDENTIFIED from the iRacing Lotus 49
# skidpad grip curve by fit/validate_brush.jl (2-param fit, RMS 0.02/0.04 g):
#   μ  = the measured PEAK grip (1.19/1.21 g — the real friction, NOT the fudged 1.40+)
#   Cα = the measured low-slip cornering stiffness (20.5/24.0 /rad)
# This is a period bias-ply: low stiffness, grip peaks ~9-10° slip, plateaus at μ.
# NO ×1.13 grip fudge and NO Magic-Formula Cy/Ey shape knobs.
#   Cκ (longitudinal stiffness) is a physical estimate pending a braking-data fit;
#   kμ (friction load-sensitivity) pending a multi-load (Nürburgring) fit.
const BRUSH_FRONT = (μ = 1.19, μx = 1.42, Cα = 20.5, Cκ = 28.0, kμ = 0.08, Fz0 = 1415.0)
const BRUSH_REAR  = (μ = 1.21, μx = 1.42, Cα = 24.0, Cκ = 28.0, kμ = 0.08, Fz0 = 1670.0)

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
    ξ  = sqrt(ξx^2 + ξy^2)
    s  = brush_sat(ξ)                          # utilization in [0,1]
    ξg = sqrt(ξx^2 + ξy^2) + 1e-9              # direction floor (force = 0 at exactly zero slip)
    (μx*Fz*s*ξx/ξg, μy*Fz*s*ξy/ξg)            # along the deflection dir; magnitude on the friction ellipse
end
