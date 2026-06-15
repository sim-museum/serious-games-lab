# Isothermal tyre — Pacejka-style Magic Formula, pure-slip Fx/Fy + aligning
# moment Mz.  No thermal/pressure coupling yet (v1): peak friction μ is constant.
#
# The force law lives in plain functions (the single source of truth) and is
# *inlined* symbolically inside the `Tyre` @mtkmodel — Symbolics traces straight
# through `mf_branch`/`mf_stiffness` since they have no value-dependent control
# flow.  Slip angle α and slip ratio κ in SI (rad / unitless); forces in N, Mz N·m.
#
# Validation path: the .ibt logs no per-tyre force, so a tyre is checked
# indirectly — summed Fy across the four corners must equal m·LatAccel on the
# skidpad (steady ~1.5 g circles).  These functions give that Fy(α, Fz).

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

"Sine Magic-Formula branch: sin(C·atan(x − E·(x − atan x)))."
mf_branch(x, C, E) = sin(C * atan(x - E * (x - atan(x))))

"Load-dependent slip stiffness K(Fz) = p1·Fz0·sin(2·atan(Fz/(p2·Fz0))) — rises
then saturates with load, the standard MF shape (units: N/rad for α, N for κ)."
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
    pKy2 = 2.2,      # load (×Fz0) at which cornering stiffness peaks
    pKx1 = 18.0,     # longitudinal slip-stiffness factor
    t0   = 0.035,    # peak pneumatic trail [m]
    Bt   = 8.0,      # pneumatic-trail decay with slip
)

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

# ----- the acausal component --------------------------------------------------
# Fz, α, κ are inputs (driven by the suspension + chassis kinematics in the full
# vehicle, or by sources in a test rig); Fy, Fx, Mz are outputs.  Compile a model
# that *drives* the inputs — `Tyre` alone is underdetermined by design.
# Built with the functional `System` API (MTK v11; the @mtkmodel DSL split out
# into the un-bundled SciCompDSL, so we use the stable lower-level constructor).
function Tyre(; name,
        Fz0 = TYRE_DEFAULTS.Fz0, μy = TYRE_DEFAULTS.μy, μx = TYRE_DEFAULTS.μx,
        Cy = TYRE_DEFAULTS.Cy, Cx = TYRE_DEFAULTS.Cx, Ey = TYRE_DEFAULTS.Ey,
        Ex = TYRE_DEFAULTS.Ex, pKy1 = TYRE_DEFAULTS.pKy1, pKy2 = TYRE_DEFAULTS.pKy2,
        pKx1 = TYRE_DEFAULTS.pKx1, t0 = TYRE_DEFAULTS.t0, Bt = TYRE_DEFAULTS.Bt)
    ps = @parameters Fz0=Fz0 μy=μy μx=μx Cy=Cy Cx=Cx Ey=Ey Ex=Ex pKy1=pKy1 pKy2=pKy2 pKx1=pKx1 t0=t0 Bt=Bt
    vars = @variables Fz(t) α(t) κ(t) Fy(t) Fx(t) Mz(t) Ky(t)
    #            Fz: vertical load [N] (in)   α: slip angle [rad] (in)   κ: slip ratio (in)
    #            Fy/Fx: lateral/longitudinal force [N] (out)   Mz: aligning moment [N·m] (out)
    eqs = [
        Ky ~ mf_stiffness(Fz, Fz0, pKy1, pKy2),
        Fy ~ μy*Fz * mf_branch(Ky/(Cy*μy*Fz + 1e-6) * α, Cy, Ey),
        Fx ~ μx*Fz * mf_branch((pKx1*Fz)/(Cx*μx*Fz + 1e-6) * κ, Cx, Ex),
        Mz ~ -(t0 / (1 + (Bt*α)^2)) * Fy,
    ]
    System(eqs, t, vars, ps; name)
end
