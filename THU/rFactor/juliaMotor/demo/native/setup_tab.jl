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

export Setup4, session_setup, apply_delta, reset_one!, reset_all!, is_default, describe,
       apply_spec!, setup_menu!, FIELDS

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
                                "  -> MODIFIED by the player.  R here, or JM_SETUP=reset, restores the session.")
    String(take!(io))
end

# ── E105-S2: the TAB ────────────────────────────────────────────────────────────────────────────
# S1 built the values and left the shell "the PO's call". The PO asked for a setup TAB, and the
# only front end this sim has is `choose_track()`, a readline menu on stdin -- so the tab is a step
# in that menu. That is the routine reading of the request; an in-window screen would be a bigger
# guess, not a smaller one.
#
# Two things decide the shape, and both come from the PO's own condition -- "make it easy to return
# to default":
#   * the way back is on screen at ALL TIMES (`R) reset EVERYTHING`), not hidden behind a submenu,
#     and every value's own prompt offers `r` for just that one -- the two scopes S1 gated;
#   * `describe` is reprinted before every prompt, so the session value sits beside the current one
#     while you decide. "What was it?" is never answered from memory.
#
# It lives HERE, in the module, and takes its streams as parameters -- not inline in
# drive_native_mtk.jl. That file cannot be loaded by a test (it launches the sim), so a menu written
# inside it could never be gated, and E103-S2 is the standing reminder of what ships when nothing
# loads the file. With `input`/`output` parameters the gate drives it from an IOBuffer.

const FIELDS = (:springs, :ride, :final, :mass)

"""    apply_spec!(s, "springs=+5,ride=-3") -> number of deltas applied

The ONE parser for a setup spec. `JM_SETUP` and any future front end go through it, so the env and
the menu cannot drift into meaning different things. Unknown or unmodellable fields warn and are
skipped rather than aborting -- a typo in one term should not silently discard the others.
"""
function apply_spec!(s::Setup4, spec::AbstractString)
    n = 0
    (isempty(strip(spec)) || lowercase(strip(spec)) == "reset") && return n
    for part in split(spec, ',')
        kv = split(strip(part), '='); length(kv) == 2 || continue
        fld = Symbol(lowercase(strip(kv[1]))); pct = tryparse(Float64, strip(kv[2]))
        pct === nothing && continue
        try
            apply_delta(s, fld, pct); n += 1
        catch
            @warn "setup: ignoring unknown or unmodellable field" field=fld
        end
    end
    n
end

"""    setup_menu!(s; input, output) -> s

Interactive tab. Returns when the driver presses Enter, and ALSO on EOF at either prompt -- a menu
that loops forever on a closed stdin would hang every non-interactive launch that reached it.
"""
function setup_menu!(s::Setup4; input::IO = stdin, output::IO = stdout)
    while true
        println(output, """

      ╔════════════════════════════════════════════════╗
      ║          juliaMotor — car setup                 ║
      ╚════════════════════════════════════════════════╝""")
        print(output, describe(s))
        println(output, "\n   1) springs     2) ride height     3) final drive     4) mass")
        println(output, "   R) reset EVERYTHING to the ibt session          Enter) drive")
        print(output, "\n  setup> "); flush(output)
        eof(input) && return s
        line = lowercase(strip(readline(input)))
        isempty(line) && return s
        if line == "r"
            reset_all!(s); println(output, "  -> reset: the car is the ibt session's again.")
            continue
        end
        idx = tryparse(Int, line)
        if idx === nothing || !(1 <= idx <= length(FIELDS))
            println(output, "  ?  1-$(length(FIELDS)), R to reset everything, Enter to drive.")
            continue
        end
        fld = FIELDS[idx]
        print(output, "  $(fld): percent of the session value (",
              "-", round(Int,100BAND), " .. +", round(Int,100BAND),
              "), or r to reset just this one: "); flush(output)
        eof(input) && return s
        a = lowercase(strip(readline(input)))
        if a == "r"
            reset_one!(s, fld); println(output, "  -> $(fld) is the session's again.")
        else
            pct = tryparse(Float64, a)
            if pct === nothing
                println(output, "  ?  a number, or r.")
            else
                apply_delta(s, fld, pct)
                println(output, "  -> $(fld) set to $(pct >= 0 ? "+" : "")$(pct)% of the session",
                        abs(pct) > 100BAND ? "  (clamped to the ±$(round(Int,100BAND))% band)" : "")
            end
        end
    end
end

end # module
