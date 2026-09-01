# setup_tab_smoke.jl — E105: the setup tab changes the car modestly, and RESET restores it exactly.
#
# The PO amended the "lock physics to .ibt" rule for setup values and attached one condition:
# "Make it easy to return to default." So the assertions that matter here are the RESET ones, and
# they are EXACT (===), not approximate. "Close to the session" is the failure this gate exists to
# catch: a car that has been reset must be indistinguishable from one never touched, or the tab
# quietly becomes a one-way door away from the reference.
using Printf
include(joinpath(@__DIR__, "..", "..", "demo", "native", "setup_tab.jl")); using .SetupTab

fails = Ref(0)
chk(n, ok, d) = (@printf("  %-52s %s   %s\n", n, ok ? "PASS" : "FAIL", d); ok || (fails[] += 1))

# The Nordschleife session's installed values (E100-S4/S5).
KS = (18249.0, 18249.0, 29198.0, 29198.0)
RH = (0.0829, 0.0829, 0.1052, 0.1052)
FD, MASS = 4.11, 616.9

println("\n  E105 setup tab — modest changes, exact reset\n")

s = session_setup(KS, RH, FD, MASS)
chk("a fresh setup IS the session", is_default(s), "nothing touched")

# 1. edits move the car
apply_delta(s, :springs, 10.0)
chk("springs +10% moves every corner", all(s.ks .> KS), string(round(Int, s.ks[1]), " from ", round(Int, KS[1])))
chk("the session values are NOT overwritten", s.ks_session == KS, "reset has something to restore")
chk("a modified setup reports itself modified", !is_default(s), "provenance can say so")

# 2. per-corner
s2 = session_setup(KS, RH, FD, MASS)
apply_delta(s2, :ride, -5.0; corner = 3)
chk("ride -5% on ONE corner touches only that corner",
    s2.rh[3] < RH[3] && s2.rh[1] == RH[1] && s2.rh[2] == RH[2] && s2.rh[4] == RH[4],
    string(round(1000*s2.rh[3], digits=1), " mm vs ", round(1000*RH[3], digits=1)))

# 3. the band is a CLAMP, not a suggestion — and repeated nudges must not walk past it, which is
# why deltas are percentages of the SESSION value rather than of the current one.
s3 = session_setup(KS, RH, FD, MASS)
for _ in 1:10; apply_delta(s3, :springs, 50.0); end
chk("a huge delta clamps to the modest band", all(s3.ks .<= KS .* (1 + SetupTab.BAND) .+ 1e-9),
    string(round(Int, s3.ks[1]), " <= ", round(Int, KS[1]*(1+SetupTab.BAND))))
chk("repeated nudges do not walk past the band", s3.ks[1] == KS[1]*(1+SetupTab.BAND),
    "10x +50% lands exactly on the cap")

# 4. RESET — both scopes the PO named, and both EXACT
s4 = session_setup(KS, RH, FD, MASS)
apply_delta(s4, :springs, 7.0); apply_delta(s4, :ride, 3.0)
apply_delta(s4, :final, -4.0); apply_delta(s4, :mass, 2.0)
reset_one!(s4, :springs)
chk("reset ONE value restores it exactly", s4.ks === KS, "springs back")
chk("reset ONE leaves the others alone", s4.rh !== RH && s4.final != FD, "ride/final still modified")
reset_all!(s4)
chk("reset ALL restores every value exactly", s4.ks === KS && s4.rh === RH && s4.final == FD && s4.mass == MASS, "===")
chk("a reset car reports itself UNCHANGED", is_default(s4), "indistinguishable from untouched")

# 5. a reset car must equal a never-touched one, field for field
fresh = session_setup(KS, RH, FD, MASS)
chk("reset car == never-touched car",
    s4.ks == fresh.ks && s4.rh == fresh.rh && s4.final == fresh.final && s4.mass == fresh.mass,
    "byte-identical, not merely close")

# 6. camber must NOT be offerable: E100-S6 established it is not modelled, and a control that moves
# nothing is worse than no control.
# In a FUNCTION, so `threw` is an ordinary local. At top level Julia's soft-scope rule makes the
# assignment inside `try` a new local and the check reads FAIL on working code -- which it did.
refuses(field) = (try; apply_delta(session_setup(KS, RH, FD, MASS), field, 1.0); false; catch; true; end)
chk("camber is refused (it is not modelled)", refuses(:camber), refuses(:camber) ? "threw" : "ACCEPTED IT")
chk("tyre pressure is refused (not on the live path)", refuses(:pressure), refuses(:pressure) ? "threw" : "ACCEPTED IT")

# 7. E105-S2 -- the TAB ITSELF. The menu lives in the module and takes its streams as parameters
# precisely so this can exist: driven from an IOBuffer, no terminal, no sim launch.
# What matters here is the PO's condition, so the reset arms use `===` like the rest of the gate.
function menu(script::String; s = session_setup(KS, RH, FD, MASS))
    out = IOBuffer()
    setup_menu!(s; input = IOBuffer(script), output = out)
    (s, String(take!(out)))
end

m1, _ = menu("1\n+5\n\n")
chk("menu applies a delta", m1.ks != KS && all(m1.ks[i] ≈ KS[i]*1.05 for i in 1:4), "springs +5%")
chk("menu leaves the SESSION values alone", m1.ks_session === KS, "session untouched")

m2, _ = menu("2\n-4\nr\n\n")                     # modify, then R = reset everything
chk("menu R resets EVERYTHING, exactly", m2.rh === RH && is_default(m2), "=== session")

m3, _ = menu("3\n+6\n1\n+5\n1\nr\n\n")         # per-value reset leaves the others modified
chk("menu r resets ONE value only", m3.ks === KS && m3.final != FD, "springs back, final still +6%")

m4, out4 = menu("9\nzzz\n\n")                     # junk must not crash or apply anything
chk("menu survives junk input", is_default(m4), "unchanged")
chk("menu says what junk means", occursin("?", out4), "prompts again")

# EOF at the next prompt must RETURN, not hang -- and the answer already given must still count.
# (The no-hang property is proved by this gate TERMINATING; the assertion below is about the value,
# because `x || !x` is true for every x and an arm that cannot fail is not an arm.)
m5, _ = menu("1\n+5")
chk("EOF returns, keeping the answer already given", all(m5.ks[i] ≈ KS[i]*1.05 for i in 1:4), "+5% survived EOF")

m6, out6 = menu("1\n+999\n\n")                    # the band still holds through the menu
chk("menu cannot exceed the ±15% band", all(m6.ks[i] ≈ KS[i]*1.15 for i in 1:4), "clamped")
chk("menu SAYS it clamped", occursin("clamped", out6), "told the driver")

_, out7 = menu("\n")
chk("the way back is on screen without asking", occursin("reset EVERYTHING", out7), "R offered at top level")

# 8. the env and the menu must share ONE parser, or they drift into meaning different things
se = session_setup(KS, RH, FD, MASS); apply_spec!(se, "springs=+5")
chk("apply_spec! agrees with the menu", se.ks == m1.ks, "same car from JM_SETUP and from the menu")
chk("apply_spec!(\"reset\") is a no-op, not an error", apply_spec!(session_setup(KS,RH,FD,MASS), "reset") == 0, "0 deltas")

println(fails[] == 0 ? "\n  SETUP TAB GATE: PASS ✓" : "\n  SETUP TAB GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
