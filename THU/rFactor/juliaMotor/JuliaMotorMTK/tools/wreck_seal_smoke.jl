# wreck_seal_smoke.jl — E103: a wreck stops where it happened; it does not go back to the start.
#
# Tests the SIM's own rule (demo/native/wreck_seal.jl), not a copy of it. S371 caught a gate here
# carrying its own drifted reimplementation of the wreck rule: "a gate asserting its own
# reimplementation tests nothing about the sim."
using Printf
include(joinpath(@__DIR__, "..", "..", "demo", "native", "wreck_seal.jl")); using .WreckSeal
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

fails = Ref(0)
chk(n, ok, d) = (@printf("  %-52s %s   %s\n", n, ok ? "PASS" : "FAIL", d); ok || (fails[] += 1))

println("\n  E103 — a wreck is sealed WHERE IT HAPPENED\n")

# The shape that produced the PO's report: the car wrecks 800 m down the lap, off the mesh, and the
# last ON-TRACK anchor is still the spawn point because it stopped updating when the car left.
START = (0.0, 0.0)            # LASTGX/LASTGZ initialise to the spawn = the start line
IMPACT = (812.5, -344.0)

(wx, wz) = seal_target(true, IMPACT..., START...)
chk("a WRECK seals at the impact site", (wx, wz) == IMPACT, @sprintf("(%.1f, %.1f)", wx, wz))
chk("a wreck is NOT sent to the start line", (wx, wz) != START,
    @sprintf("%.0f m away from spawn", hypot(wx - START[1], wz - START[2])))

# A driveable car is a different case: putting it back on track is a rescue, and the race continues.
(dx, dz) = seal_target(false, IMPACT..., START...)
chk("a DRIVEABLE car is still rescued to the last on-track point", (dx, dz) == START,
    @sprintf("(%.1f, %.1f)", dx, dz))

# The negative control: the old behaviour must still be reachable, and must still hyperspace.
(ox, oz) = seal_target(true, IMPACT..., START...; seal_back = true)
chk("control (JM_WRECK_SEAL_BACK) reproduces the hyperspace", (ox, oz) == START,
    @sprintf("back to (%.1f, %.1f) — the defect, on demand", ox, oz))

# And the primitive underneath really does TELEPORT, which is why WHERE it is pointed matters.
# If contain3d! merely pushed, the seal target would be a nudge and this whole item would be moot.
c = DriveRT3D.build_car3d(; x0 = 100.0, v0 = 20.0)
DriveRT3D.contain3d!(c, 7.0, -3.0; vdamp = 0.0, settle = true)
chk("contain3d! PLACES the car (it is a teleport, not a push)",
    isapprox(c.x, 7.0; atol=1e-6) && isapprox(c.z, -3.0; atol=1e-6),
    @sprintf("x %.1f -> %.1f", 100.0, c.x))

println(fails[] == 0 ? "\n  WRECK SEAL GATE: PASS ✓" : "\n  WRECK SEAL GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
