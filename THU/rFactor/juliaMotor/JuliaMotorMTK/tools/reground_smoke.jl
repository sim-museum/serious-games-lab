# GATE: E104(a) -- an AI car must be drawn ON the road, not at the centreline's height.
#
# THE DEFECT THIS LOCKS DOWN. `RaceAI.pose_at` interpolates the centreline's (x, y, z) and then
# applies the car's lane offset to x AND z ONLY -- y is never re-sampled. So a car running `lane`
# metres to the side of the centreline is posed at the CENTRELINE's height, which on a cambered or
# cross-sloped road is wrong by lane x cross-slope. Every wheel inherits it, because wheels are
# drawn at <car origin> + [wx, r, wz].
#
# Measured in the sim before the fix (Watkins, 5 AI, JM_WHEELGAP): AI cars sat -0.192 .. +0.302 m
# off the terrain, median +0.093, with 13 of 45 samples at or above +0.20 m -- the PO's "every car
# floats 20-40 cm above the road". The player, whose height comes from the physics, measured 0.00.
#
# The road here is a straight along +x with a CONSTANT CROSS-SLOPE, so the correct height at any
# point is known in closed form and the error is exactly lane x slope. No terrain data, no sim.
#
# ⚠️ The first arm is a POSITIVE CONTROL and it must keep failing-by-construction: it asserts the
# RAW pose really is off by lane x slope. If someone fixes pose_at upstream, that arm goes red and
# says so, rather than this gate passing vacuously on a defect that no longer exists.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "ai.jl"))
using .RaceAI

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 52), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)

const SLOPE = 0.10          # 10 % cross-slope: 2.4 m of lane = 0.24 m of height
const LANE  = 2.4           # the sim's own grid lane (drive_native_mtk: c.lane = +-2.4)

# terrain: height rises with +z. Returns (y, ok) -- the form RaceAI.reground expects.
terrain(x, z) = (SLOPE * z, true)
offmap(x, z)  = (0.0, false)          # "off the terrain": no answer available

# a straight centreline along +x at height 0, heading 0 (so lane offset moves +z)
n = 21
line = RaceAI.AILine(collect(0.0:10.0:200.0), zeros(n), zeros(n), collect(0.0:10.0:200.0),
                     zeros(n), zeros(n), zeros(n), 200.0)

p_raw = RaceAI.pose_at(line, 100.0, LANE)
want_z = LANE                                   # heading 0 -> left is +z
chk("premise: lane offset moves z, not y", isapprox(p_raw[3], want_z; atol=1e-9), "z=$(round(p_raw[3],digits=3))")
chk("POSITIVE CONTROL: raw pose IS off by lane x slope",
    isapprox(p_raw[2] - SLOPE*want_z, -SLOPE*LANE; atol=1e-9),
    "raw y=$(round(p_raw[2],digits=3)) vs ground $(round(SLOPE*want_z,digits=3))")

p_fix = RaceAI.reground(p_raw, terrain)
chk("reground puts the car exactly on the ground",
    isapprox(p_fix[2], SLOPE*want_z; atol=1e-12), "y=$(round(p_fix[2],digits=4))")
chk("reground changes ONLY the height",
    p_fix[1] == p_raw[1] && p_fix[3] == p_raw[3] && p_fix[4] == p_raw[4], "x, z, heading untouched")

# 6-tuple (the draw path carries pitch/roll) -- both must survive
p6 = (p_raw[1], p_raw[2], p_raw[3], p_raw[4], 0.031, -0.017)
f6 = RaceAI.reground(p6, terrain)
chk("6-tuple: height corrected", isapprox(f6[2], SLOPE*want_z; atol=1e-12), "y=$(round(f6[2],digits=4))")
chk("6-tuple: pitch and roll preserved", f6[5] == p6[5] && f6[6] == p6[6], "$(f6[5]), $(f6[6])")

# off the terrain there is no better answer than the line's -- the pose must come back UNTOUCHED
chk("off the terrain the pose is returned unchanged", RaceAI.reground(p6, offmap) === p6, "identical")

# the correction must scale with the lane, and vanish at lane 0 (which is why E104-S3's
# centreline-only measurement read exactly 0.0 and wrongly refuted E104-S2)
p0 = RaceAI.pose_at(line, 100.0, 0.0)
chk("at lane 0 there is nothing to correct (why S3 read 0.0)",
    isapprox(RaceAI.reground(p0, terrain)[2], p0[2]; atol=1e-12), "unchanged on the centreline")
pn = RaceAI.pose_at(line, 100.0, -LANE)
chk("the other lane is corrected the other way",
    isapprox(RaceAI.reground(pn, terrain)[2], -SLOPE*LANE; atol=1e-9),
    "y=$(round(RaceAI.reground(pn, terrain)[2],digits=4))")

println(fails[] == 0 ? "\n  REGROUND GATE: PASS ✓" : "\n  REGROUND GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
