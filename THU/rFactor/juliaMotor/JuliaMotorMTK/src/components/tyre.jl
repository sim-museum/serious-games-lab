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
include("brush_tyre.jl") # PHYSICS-BASED brush: brush_forces + BRUSH_FRONT/REAR presets

# ----- the PHYSICS-BASED brush tyre as an MTK component -----------------------
# Same Fz/α/κ → Fx/Fy/Mz interface as `Tyre`, but the force is the contact-patch
# brush law F = μ·Fz·(1−(1−ξ)³) (smooth/branchless via min for the symbolic graph),
# with PHYSICAL parameters (μ, Cα, Cκ, kμ) — no Magic-Formula Cy/Ey, no grip fudge.
function BrushTyre(; name, μ = BRUSH_FRONT.μ, μx = BRUSH_FRONT.μx, Cα = BRUSH_FRONT.Cα,
                   Cκ = BRUSH_FRONT.Cκ, kμ = BRUSH_FRONT.kμ, Fz0 = BRUSH_FRONT.Fz0, t0 = 0.035, μscale = 1.0)
    # E56: μscale is a per-wheel SURFACE friction multiplier (1 = tarmac; <1 = grass/verge).  Driving it
    # from the game makes "off the racing line" a REAL per-tyre grip loss the model integrates — a wheel
    # dropping onto the grass loses grip and pulls the car — not a bumpX! drag/yaw state hack.
    ps = @parameters μ=μ μx=μx Cα=Cα Cκ=Cκ kμ=kμ Fz0=Fz0 t0=t0 μscale=μscale
    vars = @variables Fz(t) α(t) κ(t) Fy(t) Fx(t) Mz(t) μye(t) μxe(t) ξx(t) ξy(t) ξ(t) sat(t)
    eqs = [
        μye  ~ μscale * μ  * clamp(1.0 - kμ*(Fz/Fz0 - 1.0), 0.4, 1.6),  # lateral friction (load-sensitive, clamped >0)
        μxe  ~ μscale * μx * clamp(1.0 - kμ*(Fz/Fz0 - 1.0), 0.4, 1.6),  # longitudinal friction (anisotropic, clamped >0)
        ξx   ~ Cκ*κ      / (3.0*μxe),                  # per-axis NORMALIZED slip (1 = friction limit)
        ξy   ~ Cα*sin(α) / (3.0*μye),                  # — the ellipse lives here, no 1/0 at zero slip
        ξ    ~ sqrt(ξx^2 + ξy^2 + 1e-9),               # floor INSIDE the sqrt → autodiff Jacobian finite at
        sat  ~ 1.0 - (1.0 - min(ξ, 1.0))^3,            #   zero slip (sqrt(0)' = 0/0 = NaN breaks the solver)
        Fx   ~ μxe*Fz * sat * ξx/ξ,                    # along the deflection dir; magnitude on the ellipse
        Fy   ~ μye*Fz * sat * ξy/ξ,
        Mz   ~ -t0 * (1.0 - min(ξ, 1.0)) * Fy,         # pneumatic trail collapses as the patch slides
    ]
    System(eqs, t, vars, ps; name)
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
    vars = @variables Fz(t) α(t) κ(t) Fy(t) Fx(t) Mz(t) Ky(t) σ(t) Fmag(t)
    #            Fz: vertical load [N] (in)   α: slip angle [rad] (in)   κ: slip ratio (in)
    #            Fy/Fx: lateral/longitudinal force [N] (out, combined)   Mz: aligning moment [N·m]
    #            σ: combined slip magnitude   Fmag: friction-circle force magnitude
    # PHYSICS-BASED combined slip (energy-conserving — no empirical coupling): the friction
    # force has magnitude μ·Fz·MF(σ), where σ combines longitudinal (κ) and lateral (sin α)
    # slip, and is DIRECTED ALONG THE SLIP VECTOR (κ, sin α) — i.e. opposite the contact-patch
    # slip velocity.  This dissipates energy at ANY heading (no spurious speed-up in a spin)
    # AND gives power-on snap oversteer for free: when the rear spins up (κ large) the slip
    # vector points longitudinally, so the force is mostly longitudinal and almost no lateral
    # grip is left → the rear lets go.  Pure lateral (κ=0) ⇒ the fitted Fy0(α); pure
    # longitudinal (α=0) ⇒ Fx at the fitted peak μ·Fz.
    eqs = [
        # σ in the slip-DIRECTION (κ/σ, sinα/σ) carries a small floor (0.02) so the unit
        # direction stays well-conditioned near zero slip; the force MAGNITUDE Fmag uses the
        # true slip (1e-9 floor) so peak grip is unaffected.  The direction floor only rounds
        # the split at near-zero slip, where the force → 0 anyway (κ,sinα → 0).
        Ky   ~ mf_stiffness(Fz, Fz0, pKy1, pKy2),
        σ    ~ sqrt(κ^2 + sin(α)^2 + 0.02^2),
        Fmag ~ μy*Fz * mf_branch(Ky/(Cy*μy*Fz + 1e-6) * sqrt(κ^2 + sin(α)^2 + 1e-9), Cy, Ey),
        Fx   ~ Fmag * κ / σ,
        Fy   ~ Fmag * sin(α) / σ,
        Mz   ~ -(t0 / (1 + (Bt*α)^2)) * Fy,
    ]
    System(eqs, t, vars, ps; name)
end
