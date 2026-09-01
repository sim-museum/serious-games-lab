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

println(fails[] == 0 ? "\n  SETUP TAB GATE: PASS ✓" : "\n  SETUP TAB GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
