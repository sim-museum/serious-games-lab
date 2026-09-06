# GATE: car-to-car contact must be detected NOSE-TO-TAIL, not just alongside.
#
#   PO 2026-09-04 (Monza, then again at Watkins Glen): "the user car seems to drive right through
#   AI cars as if they aren't there, though AI cars seem to react (by making evasive maneuvers)".
#
# WHY THIS EXISTS. The contact test was a CIRCLE of radius CONTACT_D = 2.1 m between car CENTRES.
# A Lotus 49 is about 4 m long and 1.8 m wide:
#   * alongside, the centres are ~1.8 m apart  -> inside 2.1  -> detected (so it LOOKED like it worked)
#   * nose-to-tail at real contact they are ~4 m apart -> OUTSIDE 2.1 -> nothing detected at all.
# So rear-ending an AI -- the commonest way to hit one -- passed straight through it. The AI still
# swerved, because evasion is a separate path that gets the player's position whether or not any
# contact is found; that asymmetry is exactly what the PO reported.
#
# The existing contact_smoke passed both BEFORE and AFTER the fix, so it never covered this. That
# is the point of this gate: it FAILS against the old circular rule (the control below) and passes
# against the oriented one, which is the only way it can be evidence of anything.
#
# Headless: pure geometry, no window and no car.

const SRC = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"))

# Load the REAL definitions out of the sim source rather than restating them here -- a gate that
# reimplements the rule tests its own copy (S371 learned this the hard way on `wrecks`).
src = read(SRC, String)
i = findfirst("const CAR_HALF_L", src)
j = findfirst("carrad(θa, dx/d, dz/d) + carrad(θb, dx/d, dz/d))", src)
(i === nothing || j === nothing) && error("cannot find the contact definitions in $SRC -- has the oriented test been removed?")
block = replace(src[first(i):last(j)], "haskey(ENV, \"JM_CONTACT_D\")" => "false")
eval(Meta.parse("begin\nconst CONTACT_D = 2.1\n" * block * "\nend"))

fails = Ref(0)
check(name, cond, msg) = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 48), msg))

println("Car-to-car contact geometry gate (PO: driving through AI cars)")

alongside = contact_d(0.0, 1.8, 1.8, 0.0, 0.0)          # both heading +x, offset across
nose2tail = contact_d(4.0, 0.0, 4.0, 0.0, 0.0)          # both heading +x, offset along
tbone     = contact_d(3.0, 0.0, 3.0, 0.0, pi/2)

check("nose-to-tail contact is detected at 4 m", 4.0 <= nose2tail + 1e-9,
      "threshold $(round(nose2tail, digits=2)) m")
check("alongside contact still detected at 1.8 m", 1.8 <= alongside + 1e-9,
      "threshold $(round(alongside, digits=2)) m")
check("nose-to-tail threshold exceeds alongside", nose2tail > alongside * 1.5,
      "$(round(nose2tail, digits=2)) m vs $(round(alongside, digits=2)) m -- the test is ORIENTED, not a circle")
check("t-bone lands between the two", alongside < tbone < nose2tail,
      "$(round(tbone, digits=2)) m")

# NEGATIVE CONTROL: the rule as it shipped. It must MISS the nose-to-tail case, or this gate is
# testing a defect that could no longer occur and proves nothing about the fix.
old_circular(d) = d <= 2.1
check("control: the old circular rule MISSES nose-to-tail", !old_circular(4.0),
      "2.1 m circle vs 4 m separation -- the bug the PO drove through")
check("control: the old circular rule caught alongside", old_circular(1.8),
      "which is why side contact worked and hid this")

println()
println(fails[] == 0 ? "  CONTACT GEOMETRY GATE: PASS ✓" : "  CONTACT GEOMETRY GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
