# setup_tab.jl — E105: modest chassis-setup changes, with an obvious way back to the session.
#
# 🔒 THE RULE THIS IMPLEMENTS (amended by the PO, 2026-08-31):
#     "yes, this is a modification of the original 'lock physics to .ibt' rule.
#      Make it easy to return to default."
# so:
#     the ibt session is the SOURCE and the DEFAULT for car physics; the player may make modest
#     setup changes from it, and returning to the session's values must be EASY and OBVIOUS.
#
# What that means in code, and why the shape is what it is:
#   * the SESSION values are held separately from the CURRENT ones and are never overwritten, so
#     "reset" is a copy, not a re-read — a reset cannot fail because a file moved;
#   * every value is a DELTA in percent from the session, clamped to a modest band, so the tab
#     cannot express a car the session could not plausibly have been set up as;
#   * reset works at BOTH scopes the PO named: one value, or everything;
#   * `is_default` answers "has anything been touched?" so the provenance line can distinguish
#     "from the ibt" from "modified by the player" — a silent divergence from the reference is the
#     exact failure E100 exists to prevent.
#
# Only the four values E100 wired have setters, validation and provenance: spring rates, static
# ride height, gearbox ratios and mass. Camber is deliberately ABSENT — E100-S6 established it is
# not modelled at all, so a slider for it would move nothing, which is worse than no slider.
module SetupTab

export Setup4, session_setup, apply_delta, reset_one!, reset_all!, is_default, describe

const BAND = 0.15          # +-15%: "modest". A setup tab is not a physics editor.

"""Current-vs-session state for the values the physics model can actually take."""
mutable struct Setup4
    ks_session::NTuple{4,Float64}      # wheel rates N/m, FL FR RL RR
    ks::NTuple{4,Float64}
    rh_session::NTuple{4,Float64}      # static ride height m
    rh::NTuple{4,Float64}
    final_session::Float64             # final drive
    final::Float64
    mass_session::Float64              # kg
    mass::Float64
end

"""Build from the installed session values. Session and current start identical, by construction."""
session_setup(ks, rh, final, mass) =
    Setup4(NTuple{4,Float64}(ks), NTuple{4,Float64}(ks),
           NTuple{4,Float64}(rh), NTuple{4,Float64}(rh),
           Float64(final), Float64(final), Float64(mass), Float64(mass))

_clamp(base, v) = clamp(v, base*(1-BAND), base*(1+BAND))

"""    apply_delta(s, field, pct; corner)

`pct` is a percentage of the SESSION value, not of the current one — so repeated nudges cannot
drift past the band, and "+5%" always means the same car whatever was applied before.
`field` ∈ :springs, :ride, :final, :mass. `corner` selects FL/FR/RL/RR (0 = all four).
"""
function apply_delta(s::Setup4, field::Symbol, pct::Real; corner::Int = 0)
    f = 1 + pct/100
    if field === :springs
        s.ks = ntuple(i -> (corner == 0 || corner == i) ? _clamp(s.ks_session[i], s.ks_session[i]*f) : s.ks[i], 4)
    elseif field === :ride
        s.rh = ntuple(i -> (corner == 0 || corner == i) ? _clamp(s.rh_session[i], s.rh_session[i]*f) : s.rh[i], 4)
    elseif field === :final
        s.final = _clamp(s.final_session, s.final_session*f)
    elseif field === :mass
        s.mass = _clamp(s.mass_session, s.mass_session*f)
    else
        error("apply_delta: unknown field $field")
    end
    s
end

"""Reset ONE value to the session's. The PO asked for this scope explicitly."""
function reset_one!(s::Setup4, field::Symbol)
    field === :springs ? (s.ks = s.ks_session) :
    field === :ride    ? (s.rh = s.rh_session) :
    field === :final   ? (s.final = s.final_session) :
    field === :mass    ? (s.mass = s.mass_session) :
    error("reset_one!: unknown field $field")
    s
end

"""Reset EVERYTHING to the session, in one action. The other scope the PO asked for."""
function reset_all!(s::Setup4)
    s.ks = s.ks_session; s.rh = s.rh_session
    s.final = s.final_session; s.mass = s.mass_session
    s
end

"""True when the car is exactly the session's. Must be EXACT, not approximate: a car that has been
reset has to be indistinguishable from one never touched, which is what the gate asserts."""
is_default(s::Setup4) = s.ks == s.ks_session && s.rh == s.rh_session &&
                        s.final == s.final_session && s.mass == s.mass_session

"""One line per value, session value always shown beside the current one — so "what was it?" never
has to be answered from memory."""
function describe(s::Setup4)
    io = IOBuffer()
    println(io, "  springs N/m  ", join((round(Int,k) for k in s.ks), " / "),
                "      session ", join((round(Int,k) for k in s.ks_session), " / "))
    println(io, "  ride ht mm   ", join((round(1000*h, digits=1) for h in s.rh), " / "),
                "   session ", join((round(1000*h, digits=1) for h in s.rh_session), " / "))
    println(io, "  final drive  ", round(s.final, digits=3), "                    session ", round(s.final_session, digits=3))
    println(io, "  mass kg      ", round(s.mass, digits=1), "                    session ", round(s.mass_session, digits=1))
    # Name the ACTUAL way back. An instruction that does not work ("press R" when there is no such
    # key) is worse than none: it makes "return to default" look available when it is not, which is
    # the one thing the PO asked to be easy.
    println(io, is_default(s) ? "  -> UNCHANGED from the ibt session" :
                                "  -> MODIFIED by the player.  JM_SETUP=reset (or unset) restores the session.")
    String(take!(io))
end

end # module
