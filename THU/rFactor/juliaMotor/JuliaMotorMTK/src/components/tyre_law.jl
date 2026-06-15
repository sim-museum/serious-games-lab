# Isothermal tyre force law (pure functions — NO ModelingToolkit dependency).
# Single source of truth: `tyre.jl` inlines these into the symbolic MTK `Tyre`,
# and the fit scripts (fit/*.jl) call them directly without loading MTK.
#
# Pacejka-style Magic Formula, pure-slip Fx/Fy, isothermal (constant μ).  Slip
# angle α [rad], slip ratio κ [-], load Fz [N]; forces in N.

"Sine Magic-Formula branch: sin(C·atan(x − E·(x − atan x)))."
mf_branch(x, C, E) = sin(C * atan(x - E * (x - atan(x))))

"Load-dependent slip stiffness K(Fz) = p1·Fz0·sin(2·atan(Fz/(p2·Fz0))) — rises
then saturates with load, the standard MF shape (N/rad for α, N for κ)."
mf_stiffness(Fz, Fz0, p1, p2) = p1 * Fz0 * sin(2 * atan(Fz / (p2 * Fz0)))

"Default isothermal tyre parameters (placeholders — fitted to .ibt later)."
const TYRE_DEFAULTS = (
    Fz0 = 3000.0,    # nominal vertical load [N]
    μy  = 1.30,      # lateral peak friction
    μx  = 1.30,      # longitudinal peak friction
    Cy  = 1.40,      # lateral shape
    Cx  = 1.60,      # longitudinal shape
    Ey  = -0.5,      # lateral curvature
    Ex  = -0.5,      # longitudinal curvature
    pKy1 = 14.0,     # peak cornering stiffness factor (Kα ≈ pKy1·Fz near Fz0)
    pKy2 = 1.71,     # load (×Fz0) at which cornering stiffness peaks (per-corner load fit)
    pKx1 = 16.6,     # longitudinal slip-stiffness factor (Nürburgring braking fit)
    t0   = 0.035,    # peak pneumatic trail [m]
    Bt   = 8.0,      # pneumatic-trail decay with slip
)

# Fitted to the iRacing Lotus 49 skidpad (fit/fit_skidpad.jl): normalised lateral
# grip curve per axle, isothermal.  μ ~1.2 front / 1.3 rear, rear tyre stiffer
# (bigger rear tyre); peak grip reached by ~7.6°/8.7° slip; loop-closure R²
# 0.90/0.81 vs measured ay.  Fz0 = per-corner static axle load (2830/2, 3339/2).
# CROSS-VALIDATED on the Nürburgring Nordschleife: predicts lateral accel at
# R²=0.86 (axle-effective) / R²≈0.96 with measured per-corner loads, on 23k
# independent samples.  Longitudinal pKx1=16.6 from braking (κ to −1); μx≈μy
# (friction isotropy).  pKy2=1.71 (load sensitivity) IDENTIFIED via the per-corner
# load model driven by the shock-deflection channels (corner_loads.jl) — real
# outer/inner loads expose it; μy unchanged (skidpad μ is the controlled measure;
# the per-corner fit's μ_scale was a mild 1.08, within uncertainty).
# Splat into the Tyre constructor: `Tyre(; name=:t, TYRE_SKIDPAD_FRONT...)`.
const TYRE_SKIDPAD_FRONT = (
    Fz0 = 1415.0, μy = 1.213, μx = 1.213, Cy = 1.345, Cx = 1.6,
    Ey = 0.40, Ex = -0.5, pKy1 = 25.7, pKy2 = 1.71, pKx1 = 16.6, t0 = 0.035, Bt = 8.0)
const TYRE_SKIDPAD_REAR = (
    Fz0 = 1670.0, μy = 1.304, μx = 1.304, Cy = 1.000, Cx = 1.6,
    Ey = 0.329, Ex = -0.5, pKy1 = 33.8, pKy2 = 1.71, pKx1 = 16.6, t0 = 0.035, Bt = 8.0)

"Pure-Julia lateral force Fy(Fz, α) — mirror of the symbolic `Tyre.Fy` eq."
function tyre_fy(Fz, α; p = TYRE_DEFAULTS)
    Ky = mf_stiffness(Fz, p.Fz0, p.pKy1, p.pKy2)
    By = Ky / (p.Cy * p.μy * Fz + 1e-6)
    p.μy * Fz * mf_branch(By * α, p.Cy, p.Ey)
end

"Pure-Julia longitudinal force Fx(Fz, κ)."
function tyre_fx(Fz, κ; p = TYRE_DEFAULTS)
    Kx = p.pKx1 * Fz
    Bx = Kx / (p.Cx * p.μx * Fz + 1e-6)
    p.μx * Fz * mf_branch(Bx * κ, p.Cx, p.Ex)
end
