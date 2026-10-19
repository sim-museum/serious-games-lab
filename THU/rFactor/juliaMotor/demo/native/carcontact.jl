# CARCOLLIDE-2 (PO 2026-10-18: "In iracing, a collision involving contact with a spinning tire causes both cars to spin
# around ... Right now in Julia, two cars hitting is like two beanbags hitting"). The car-to-car contact law, shared by
# the sim (drive_native_mtk.jl) and tools/carcollide_harness.jl.
#
# HANDLING-1 S3 (2026-10-09) made contact a rigid-body impulse between two equal masses -- physically right, and the
# 261018 iRacing races agree on a rear-end hit (dv ~10 m/s at ~20 m/s closing). But it found the contact point by
# clamping the other car's centre into a 4 x 1.8 m rectangle: alongside, the point sat at the car's MID-SIDE (no lever
# arm), so a side-swipe barely turned either car (harness: 0.0-1.1 rad/s). A Lotus 49 is an OPEN-WHEELER: its tyres are
# the widest part and stand ~1.2-1.3 m fore and aft of the CG, so cars touch tyre to tyre at the axles, rubber on rubber
# (μ ~1, not bodywork's 0.4) -- iRacing's side contacts are yaw-rate steps of 1.1-2.3 rad/s with a few km/h of speed lost
# (261018 races, CARCOLLIDE-2 S1). So (S2): each car is its narrow tub + four tyre rectangles in plan; the deepest
# overlapping pair (separating axes) gives the contact point and normal; the impulse there has both cars' rotation in
# its effective mass, and rubber friction when a tyre is in the pair. JM_CARCONTACT=old = HANDLING-1's law.

const CAR_M = 617.0; const CAR_IZZ = 890.0; const CAR_E = 0.12; const CAR_MU = 0.4
const TYRE_MU = parse(Float64, get(ENV, "JM_TYRE_CONTACT_MU", "1.0"))   # rubber on rubber / rubber on bodywork
const TYRE_E = parse(Float64, get(ENV, "JM_TYRE_CONTACT_E", "0.5"))     # a tyre bounces: restitution ~0.5 (bodywork 0.12)
const CARCONTACT_OLD = get(ENV, "JM_CARCONTACT", "") == "old"
# plan-view parts, car frame (x forward from the CG, y left): (cx, cy, half-length, half-width, is_tyre)
const CAR_PARTS = (
    (0.105, 0.0, 1.755, 0.35, false),                       # tub, nose cone (+1.86 m) to gearbox (-1.65 m)
    (1.314, 0.75, 0.300, 0.110, true), (1.314, -0.75, 0.300, 0.110, true),     # front tyres (R 0.30, 0.22 wide)
    (-1.096, 0.75, 0.334, 0.150, true), (-1.096, -0.75, 0.334, 0.150, true))   # rear tyres (R 0.334, 0.30 wide)
# broad phase: every part lies within 1.9 m of the CG (nose corner 1.89, front tyre corner 1.83), so two cars can touch
# only when their centres are closer than 3.8 m (the old 2.0 x 0.9 m ellipse missed the tyres' outer corners)
const CAR_BOUND_D = 3.8 + 0.8                                       # + the speculative margin (car_contact_impulse)
const CONTACT_DT = 1/60                                            # the sim step the speculative margin covers
car_near(dx, dz, d, θa, θb) = CARCONTACT_OLD ? d <= contact_d(dx, dz, d, θa, θb) : d <= CAR_BOUND_D

"Corners of a part of the car at (x, z) heading θ, world frame, grown by `m` on every side."
function _part_corners(x, z, θ, p, m = 0.0)
    c = cos(θ); s = sin(θ)
    px = x + p[1]*c - p[2]*s; pz = z + p[1]*s + p[2]*c
    ax = (c*(p[3] + m), s*(p[3] + m)); ay = (-s*(p[4] + m), c*(p[4] + m))
    ((px + ax[1] + ay[1], pz + ax[2] + ay[2]), (px + ax[1] - ay[1], pz + ax[2] - ay[2]),
     (px - ax[1] - ay[1], pz - ax[2] - ay[2]), (px - ax[1] + ay[1], pz - ax[2] + ay[2]))
end

"Separating-axis test of two oriented rectangles (corner tuples): nothing, or (depth, nx, nz) with n from P toward Q."
function _sat(P, Q)
    best = Inf; bn = (0.0, 0.0)
    for R in (P, Q), k in 1:2
        ex = R[k+1][1] - R[k][1]; ez = R[k+1][2] - R[k][2]; l = hypot(ex, ez); l < 1e-9 && continue
        nx = -ez/l; nz = ex/l
        pmin = Inf; pmax = -Inf; qmin = Inf; qmax = -Inf
        for v in P; d = v[1]*nx + v[2]*nz; pmin = min(pmin, d); pmax = max(pmax, d); end
        for v in Q; d = v[1]*nx + v[2]*nz; qmin = min(qmin, d); qmax = max(qmax, d); end
        o = min(pmax, qmax) - max(pmin, qmin)
        o <= 0.0 && return nothing
        if o < best
            best = o
            cp = (sum(v[1] for v in P) - sum(v[1] for v in Q))*nx + (sum(v[2] for v in P) - sum(v[2] for v in Q))*nz
            bn = cp > 0 ? (-nx, -nz) : (nx, nz)                     # point the normal from P toward Q
        end
    end
    (best, bn[1], bn[2])
end

"""Contact between car A at (ax, az, θa) and car B (bx, bz, θb): nothing, or (px, pz, nx, nz, depth, tyre) -- the contact
point, the normal from A toward B, the overlap and whether a tyre is in the touching pair (the deepest pair)."""
function car_contact_geom(ax, az, θa, bx, bz, θb; margin = 0.0)
    best = nothing
    for pa in CAR_PARTS
        P = _part_corners(ax, az, θa, pa, margin/2)
        for pb in CAR_PARTS
            Q = _part_corners(bx, bz, θb, pb, margin/2)
            r = _sat(P, Q); r === nothing && continue
            (best === nothing || r[1] > best[5]) || continue
            # the contact point: the mean of each rectangle's corners that lie inside the other (or the centres' midpoint)
            sx = 0.0; sz = 0.0; n = 0
            for (S, T) in ((P, Q), (Q, P)), v in S
                _inrect(v, T) && (sx += v[1]; sz += v[2]; n += 1)
            end
            if n == 0
                cpx = (sum(v[1] for v in P) + sum(v[1] for v in Q))/8; cpz = (sum(v[2] for v in P) + sum(v[2] for v in Q))/8
            else
                cpx = sx/n; cpz = sz/n
            end
            best = (cpx, cpz, r[2], r[3], r[1], pa[5] || pb[5])
        end
    end
    best
end
function _inrect(v, T)                                            # inside a convex quad, either winding
    pos = false; neg = false
    for k in 1:4
        a = T[k]; b = T[k % 4 + 1]
        c = (b[1] - a[1])*(v[2] - a[2]) - (b[2] - a[2])*(v[1] - a[1])
        c > 0 && (pos = true); c < 0 && (neg = true)
    end
    !(pos && neg)
end

"""Impulse on car A (at (px,pz) heading θ, world velocity (pvx,pvz), yaw rate r) from a contact with car B (centre
(qx,qz), velocity (avx,avz), heading θb, yaw rate rb). Returns (dvx, dvz, dr, jn) -- A's world velocity and yaw-rate
changes and the normal impulse [N·s] -- or nothing when the cars are apart or separating. B takes the opposite impulse at
the same point (car_contact_impulse with the cars swapped gives it). `b_fixed`: B cannot answer within this frame (a
REMOTE car, moved by the other machine after the network latency) -- A then takes the whole stop, as from a wall; with
equal masses A kept ~44 % of its closing speed for the latency's frames and ran 0.5 m into the other car
(netcollide_smoke, S2)."""
function car_contact_impulse(px, pz, θ, pvx, pvz, r, qx, qz, avx, avz; θb = θ, rb = 0.0, b_fixed = false)
    CARCONTACT_OLD && return _car_contact_impulse_old(px, pz, θ, pvx, pvz, r, qx, qz, avx, avz)
    # SPECULATIVE contact (netcollide_smoke, S2): at 25 m/s a frame closes 0.42 m, so testing the parts as they stand let
    # a car get deep before the first impulse, where the separating axis can pick a SIDEWAYS normal and the car slides
    # through. The parts are grown by the distance the cars close in one frame, so the impulse lands as they meet.
    margin = clamp(hypot(pvx - avx, pvz - avz)*CONTACT_DT, 0.02, 0.8)
    g = car_contact_geom(px, pz, θ, qx, qz, θb; margin)
    g === nothing && return nothing
    (cx, cz, nx, nz, ov, tyre) = g
    depth = ov - margin                                             # > 0: the parts overlap; < 0: the gap still left
    rx = cx - px; rz = cz - pz; sx = cx - qx; sz = cz - qz          # lever arms from each CG
    # velocity of A's contact point relative to B's (planar: ω × r with ω up = (-ω·rz, ω·rx))
    vcx = (pvx - r*rz) - (avx - rb*sz); vcz = (pvz + r*rx) - (avz + rb*sx)
    vn = vcx*nx + vcz*nz
    ra = rx*nz - rz*nx; rbn = sx*nz - sz*nx
    meff = b_fixed ? 1.0/(1.0/CAR_M + ra^2/CAR_IZZ) : 1.0/(2.0/CAR_M + ra^2/CAR_IZZ + rbn^2/CAR_IZZ)
    if depth > 0.02
        # already overlapping (a car pushed in under power, or a deep first frame): drive the parts apart at a speed
        # set by the overlap -- without this a 0.2 m/s creep under throttle went through the other car
        vsep = min(10.0*depth, 3.0)
        vn + vsep <= 0.0 && return nothing
        jn = (vn + vsep)*meff
    else
        vgap = max(-depth, 0.0)/CONTACT_DT                          # the closing speed the remaining gap allows this frame
        vn - vgap <= 0.2 && return nothing                          # separating, a resting touch, or not reaching it yet
        jn = (1 + (tyre ? TYRE_E : CAR_E))*(vn - vgap)*meff
    end
    tx = -nz; tz = nx; vt = vcx*tx + vcz*tz
    rat = rx*tz - rz*tx; rbt = sx*tz - sz*tx
    mt = b_fixed ? 1.0/(1.0/CAR_M + rat^2/CAR_IZZ) : 1.0/(2.0/CAR_M + rat^2/CAR_IZZ + rbt^2/CAR_IZZ)
    μ = tyre ? TYRE_MU : CAR_MU
    jt = -sign(vt)*min(μ*jn, abs(vt)*mt)                            # friction: never more than stops the slip
    jx = -jn*nx + jt*tx; jz = -jn*nz + jt*tz                        # impulse ON A (pushed away from B)
    (jx/CAR_M, jz/CAR_M, (rx*jz - rz*jx)/CAR_IZZ, jn)
end

# HANDLING-1 S3's law (JM_CARCONTACT=old): contact point = B's centre clamped into A's 4 x 1.8 m rectangle, B not rotating.
function _car_contact_impulse_old(px, pz, θ, pvx, pvz, r, qx, qz, avx, avz)
    dx = qx - px; dz = qz - pz; d = hypot(dx, dz); d < 1e-6 && return nothing
    nx = dx/d; nz = dz/d
    c = cos(θ); s_ = sin(θ)
    lx = clamp(dx*c + dz*s_, -2.0, 2.0); ly = clamp(-dx*s_ + dz*c, -0.9, 0.9)
    rx = lx*c - ly*s_; rz = lx*s_ + ly*c
    vcx = pvx - r*rz - avx; vcz = pvz + r*rx - avz
    vn = vcx*nx + vcz*nz
    vn <= 0.2 && return nothing
    rxn = rx*nz - rz*nx
    meff = 1.0/(2.0/CAR_M + rxn^2/CAR_IZZ)
    jn = (1 + CAR_E)*vn*meff
    tx = -nz; tz = nx; vt = vcx*tx + vcz*tz
    rxt = rx*tz - rz*tx
    mt = 1.0/(2.0/CAR_M + rxt^2/CAR_IZZ)
    jt = -sign(vt)*min(CAR_MU*jn, abs(vt)*mt)
    jx = -jn*nx + jt*tx; jz = -jn*nz + jt*tz
    (jx/CAR_M, jz/CAR_M, (rx*jz - rz*jx)/CAR_IZZ, jn)
end
