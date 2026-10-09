# CARPHYS-1 (PO 2026-10-09: "for car physics modeling, use .ibt and julia equivalent of modelica objects. If the .ibt
# contains a rollbar, the julia model should contain a rollbar object"): the car's vertical load path as physical
# objects joined by connectors, as in Modelica's Translational library. `mtkcompile` flattens the assembly into the
# same equations the single block had, so the objects cost nothing at run time (tools/carphys_regress.jl checks it).
#
# Connector: a translational FLANGE, as Modelica.Mechanics.Translational.Interfaces.Flange, plus its velocity (the
# road's vertical velocity is fed forward by the adapter, not differentiated from a sampled height). Across a
# connection s and v are equal and the forces f sum to zero; f is the force the outside exerts ON the object at that
# flange, positive upward.
#
# Strut convention (every element between a body mount and a wheel, or a wheel and the road): flange `a` is the top,
# `b` the bottom, compression c = b.s − a.s (the bottom moving up), and a push-apart force F appears as a.f = −F,
# b.f = +F -- the body above is pushed up by F, the wheel below down by F.

using ModelingToolkit
const Logging = Base.CoreLogging   # the logger API in Base: no Logging dependency for the packages that include this file
using ModelingToolkit: t_nounits as t, D_nounits as D

@connector function Flange(; name)
    vars = @variables s(t) v(t) f(t) [connect = Flow]
    System(Equation[], t, vars, []; name)
end

# MTK's connector heuristic warns, once per flange at every compile, that a connector with two potentials (s, v) and
# one flow "could lead to imbalanced model"; v is s's rate, so the count is right (the compiled car is balanced and
# matches the single-block model, tools/carphys_regress.jl). The check runs as each flange is constructed (the
# @connector macro); drop exactly that message while the parts are built, and let every other log record through.
struct _FlangeCheckFilter <: Logging.AbstractLogger
    inner::Logging.AbstractLogger
end
Logging.min_enabled_level(l::_FlangeCheckFilter) = Logging.min_enabled_level(l.inner)
Logging.shouldlog(l::_FlangeCheckFilter, args...) = Logging.shouldlog(l.inner, args...)
Logging.catch_exceptions(l::_FlangeCheckFilter) = Logging.catch_exceptions(l.inner)
function Logging.handle_message(l::_FlangeCheckFilter, level, msg, args...; kw...)
    occursin("flow variables, yet", string(msg)) && return nothing
    Logging.handle_message(l.inner, level, msg, args...; kw...)
end
"""Run `f()` -- building a System that connects flanges, or compiling one -- without MTK's false connector-balance
warning (see above)."""
quiet_flanges(f) = Logging.with_logger(f, _FlangeCheckFilter(Logging.current_logger()))

"""Prescribed motion (as Modelica's Translational.Sources.Position): a flange that moves as told -- the sprung body's
point above a wheel, or the road under it. `s`, `v` are set by the owner; `f` is the force the parts exert on it (on the
body: the suspension force at that mount)."""
function PrescribedMotion(; name)
    @named fl = Flange()
    vars = @variables s(t) v(t) f(t)
    System([fl.s ~ s, fl.v ~ v, f ~ fl.f], t, vars, []; systems = [fl], name)
end

"""Unsprung mass (wheel, hub, upright, brake): heave only, under gravity and the forces at its flange."""
function WheelMass(; name, m_u, g = 9.80665)
    @named fl = Flange()
    ps = @parameters m_u=m_u g=g
    vars = @variables zu(t)=0.0 [state_priority = 10] vu(t)=0.0 [state_priority = 10]   # keep these names as the states
    System([fl.s ~ zu, fl.v ~ vu, D(zu) ~ vu, m_u*D(vu) ~ fl.f - m_u*g], t, vars, ps; systems = [fl], name)
end

"""Coil-over: the coil SPRING (rate `ks` at the wheel, static preload `P` = the corner's sprung weight) and the DAMPER
(bump `cb` / rebound `cr`, blended through zero velocity; one symmetric `cs` when cb/cr are NaN) on one strut.
The strut can only push: the SEAT clamps the sum smoothly at zero (rounding `ε` N). That clamp stands in for the
strut's travel limits (droop) until they are modelled from the ibt's ShockDeflection; `Fbar` is the anti-roll bar's
force at this wheel, which today acts through the same seat (as it did in the single block -- see AntiRollBar)."""
function CoilOver(; name, ks, P, cs, cb = NaN, cr = NaN, ε = 80.0)
    @named a = Flange(); @named b = Flange()
    ps = @parameters ks=ks P=P ε=ε
    asym = isfinite(cb) && isfinite(cr)
    append!(ps, asym ? @parameters(cb=cb, cr=cr) : @parameters(cs=cs))
    vars = @variables c(t) vrel(t) Fk(t) Fd(t) Fbar(t) F(t)
    cdmp = asym ? cr + (cb - cr)*0.5*(1 + tanh(vrel/0.01)) : cs
    eqs = [c ~ b.s - a.s, vrel ~ b.v - a.v,
           Fk ~ P + ks*c,                       # spring
           Fd ~ cdmp*vrel,                      # damper
           F ~ smoothpos(Fk + Fd + Fbar, ε),    # seat: the strut cannot pull
           a.f ~ -F, b.f ~ F]
    System(eqs, t, vars, ps; systems = [a, b], name)
end

"""Anti-roll bar of one axle: a torsion bar linking the left and right wheels, stiff in roll and free in heave and
pitch. It reads each side's suspension compression from the mount (`mL`, `mR`) and wheel (`wL`, `wR`) flanges and
pushes each wheel down (and its mount up) by k·(c_this − c_other): `k` is the bar's roll stiffness at the wheel [N/m].
Its forces reach the car through each corner's coil-over (`FL`, `FR` → CoilOver.Fbar), so its sensing flanges carry
no force of their own."""
function AntiRollBar(; name, k)
    @named mL = Flange(); @named wL = Flange(); @named mR = Flange(); @named wR = Flange()
    ps = @parameters k=k
    vars = @variables cL(t) cR(t) FL(t) FR(t)
    eqs = [cL ~ wL.s - mL.s, cR ~ wR.s - mR.s,
           FL ~ k*(cL - cR), FR ~ k*(cR - cL),
           mL.f ~ 0, wL.f ~ 0, mR.f ~ 0, wR.f ~ 0]
    System(eqs, t, vars, ps; systems = [mL, wL, mR, wR], name)
end

"""Tyre, vertical: the carcass as a spring `kt` and damper `ct` between the wheel (`a`) and the road (`b`), loaded to
`Fz_static` at rest. It can only push -- a wheel off the ground carries nothing (rounding `ε` N). `Fz` is the load
the tyre's force law (BrushTyre) works with."""
function TyreVertical(; name, kt, ct, Fz_static, ε = 80.0)
    @named a = Flange(); @named b = Flange()
    ps = @parameters kt=kt ct=ct Fz_static=Fz_static ε=ε
    vars = @variables Fz(t)
    eqs = [Fz ~ smoothpos(Fz_static + kt*(b.s - a.s) + ct*(b.v - a.v), ε), a.f ~ -Fz, b.f ~ Fz]
    System(eqs, t, vars, ps; systems = [a, b], name)
end
