# Rear-suspension corrective transform, shared by the sim (drive_native_mtk.jl) and its gate
# (JuliaMotorMTK/tools/susp_pose_smoke.jl) so the two cannot drift apart.
#
# E82-S1 (2026-08-30): parse_3do applies the positioner chain, so RSUSPP_A/B (groups 27288/39792)
# arrive in car space already correctly posed -- a rotation search over all 24 axis permutations
# finds the identity fits 84% of the rear suspension vertices inside the hub-to-chassis envelope,
# and nothing fits better. The E64-S8 "authored flat, fold 90 degrees about the hub line" transform
# lands every rear part at y = -1.2..-1.9 m: under the road. That is the PO's "no axles".
module SuspPose
export rsfix, RS_ROLL_DEG

# Default roll of the corrective transform, degrees. 90 = the E64-S8 fold; 0 = identity, i.e. the
# positioner-placed geometry. Measured through the sim's own extraction (extract_gpl_car on groups
# 27288/39792, then rsfix): roll 90 puts every rear-suspension vertex at y = -1.87..-1.17 (the road
# is at about -0.22); roll 0 puts them at y = -0.15..0.25, hub height, |z| <= 1.16. DEFAULT 0.
# JM_RS_ROLL=90 restores the fold and is the gate's negative control.
const RS_ROLL_DEG = parse(Float32, get(ENV, "JM_RS_ROLL", "0"))

"4x4 corrective matrix for one rear half. `side` = +1 (z>0 half) / -1. Uses `T`(translate),
`RX`(rotx), `S`(scalexyz) supplied by the caller (Render's helpers), so this file needs no GL."
function rsfix(side, T, RX, S; roll = RS_ROLL_DEG)
    ax, ay = -1.05f0, 0.31f0
    sx = parse(Float32, get(ENV,"JM_RS_SX","1.0")); sy = parse(Float32, get(ENV,"JM_RS_SY","1.0")); sz = parse(Float32, get(ENV,"JM_RS_SZ","1.0"))
    dx, dy = parse(Float32, get(ENV,"JM_RS_DX","0.0")), parse(Float32, get(ENV,"JM_RS_DY","0.0"))
    y0, z0 = parse(Float32, get(ENV,"JM_RS_Y0","0.02")), parse(Float32, get(ENV,"JM_RS_Z0","0.772"))
    r = deg2rad(Float32(roll))
    T(Float32[dx, dy, 0]) * T(Float32[ax, ay, 0]) * S(sx, sy, sz) * T(Float32[-ax, -ay, 0]) *
        T(Float32[0, y0, side*z0]) * RX(Float32(-side*r)) * T(Float32[0, -y0, -side*z0])
end
end
