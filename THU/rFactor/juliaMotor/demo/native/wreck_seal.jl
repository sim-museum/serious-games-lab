# wreck_seal.jl — E103: WHERE a last-resort containment seal puts the car.
#
# Extracted so the gate tests the SIM's rule rather than a reimplementation of it. This codebase has
# been bitten by the alternative: S371 found a gate carrying its own copy of the wreck rule, already
# drifted from the sim's — "a gate asserting its own reimplementation tests nothing about the sim".
#
# PO 2026-09-01: "when wheels come off during a collision, the car stops dead where the impact
# happened. It does not hyperspace back to the start line, which is the current behavior."
#
# The hyperspace was `contain3d!(c, LASTGX, LASTGZ)`, which does not push — it PLACES:
#     c.s_pos(c.integ, [xnew, znew]); c.x = xnew; c.z = znew
# and (LASTGX, LASTGZ) is the last ON-TRACK position, which stops updating the moment the car leaves
# the mesh. Both are initialised to the SPAWN point, so a car that wrecks before ever registering
# on-track is sealed to the start line — exactly the report.
module WreckSeal
export seal_target

"""    seal_target(wrecked, curx, curz, lastx, lastz; seal_back=false) -> (x, z)

A WRECK is sealed where it lies: the race is over, and moving it is the defect.
A DRIVEABLE car is sealed back to its last on-track point: that is a rescue, and the race continues.
`seal_back=true` (JM_WRECK_SEAL_BACK) restores the old behaviour for both.
"""
seal_target(wrecked::Bool, curx, curz, lastx, lastz; seal_back::Bool = false) =
    (wrecked && !seal_back) ? (curx, curz) : (lastx, lastz)

end # module
