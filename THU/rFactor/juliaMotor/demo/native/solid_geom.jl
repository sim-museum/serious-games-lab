# SOLID-BOX: collision geometry for trackside solids. Pure, so the gate can prove it.
# A DISC is (centre, r). A BOX is an oriented rectangle: centre (ox, oz), half-extents (hx, hz)
# along axes rotated by φ in the physics frame. Both answer the same question: the signed GAP
# from a point to the object's boundary (negative = inside) and the outward unit normal there.
module SolidGeom
export disc_gap, box_gap

function disc_gap(px, pz, ox, oz, r)
    dx = px - ox; dz = pz - oz; d = hypot(dx, dz)
    d < 1e-6 && return (-r, 1.0, 0.0)
    (d - r, dx/d, dz/d)
end

function box_gap(px, pz, ox, oz, hx, hz, φ)
    c = cos(φ); s = sin(φ)
    dx = px - ox; dz = pz - oz
    lx =  c*dx + s*dz                                   # into the box frame
    lz = -s*dx + c*dz
    qx = abs(lx) - hx; qz = abs(lz) - hz
    if qx > 0.0 || qz > 0.0                             # outside: distance to the nearest edge/corner
        ex = max(qx, 0.0); ez = max(qz, 0.0); g = hypot(ex, ez)
        nlx = qx > 0.0 ? copysign(ex/g, lx) : 0.0
        nlz = qz > 0.0 ? copysign(ez/g, lz) : 0.0
    else                                                # inside: push out through the nearest face
        g = max(qx, qz)
        if qx >= qz; nlx = copysign(1.0, lx); nlz = 0.0 else nlx = 0.0; nlz = copysign(1.0, lz) end
    end
    (g, c*nlx - s*nlz, s*nlx + c*nlz)                   # normal back to the world frame
end
end
