# Isothermal tyre — Pacejka-style Magic Formula, pure-slip Fx/Fy + aligning
# moment Mz.  No thermal/pressure coupling yet (v1): peak friction μ is constant.
#
# The force law lives in plain functions in `tyre_law.jl` (the single source of
# truth, no MTK dep) and is *inlined* symbolically into the `Tyre` System below —
# Symbolics traces straight through `mf_branch`/`mf_stiffness` (no value-dependent
# control flow).  Slip angle α / slip ratio κ in SI; forces N, Mz N·m.

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

include("tyre_law.jl")   # mf_branch, mf_stiffness, TYRE_DEFAULTS, presets, tyre_fy/fx

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
    vars = @variables Fz(t) α(t) κ(t) Fy(t) Fx(t) Mz(t) Ky(t) Fy0(t) Fx0(t) gc(t)
    #            Fz: vertical load [N] (in)   α: slip angle [rad] (in)   κ: slip ratio (in)
    #            Fy/Fx: lateral/longitudinal force [N] (out, combined)   Mz: aligning moment [N·m]
    #            Fy0/Fx0: pure-slip forces   gc: friction-ellipse combined-slip scale
    eqs = [
        Ky  ~ mf_stiffness(Fz, Fz0, pKy1, pKy2),
        Fy0 ~ μy*Fz * mf_branch(Ky/(Cy*μy*Fz + 1e-6) * α, Cy, Ey),
        Fx0 ~ μx*Fz * mf_branch((pKx1*Fz)/(Cx*μx*Fz + 1e-6) * κ, Cx, Ex),
        # friction ellipse: cap the resultant of (Fx0, Fy0) at the μ·Fz ellipse
        gc  ~ min(1.0, 1.0 / sqrt((Fx0/(μx*Fz + 1e-6))^2 + (Fy0/(μy*Fz + 1e-6))^2 + 1e-9)),
        Fx  ~ gc * Fx0,
        # Gyκ: lateral grip collapses with longitudinal slip (wheelspin/lock) → snap oversteer;
        # ≈1 for κ<0.1, falls past κ≈0.25.  κ=0 ⇒ 1 (fitted pure-slip curve untouched).
        Fy  ~ gc * Fy0 / (1.0 + (κ / 0.25)^4),
        Mz  ~ -(t0 / (1 + (Bt*α)^2)) * Fy,
    ]
    System(eqs, t, vars, ps; name)
end
