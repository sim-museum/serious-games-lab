# CRASHBODY-1 (PO 2026-10-20): "The car should be treated as a rigid body with rotation, including rotation of each wheel,
# with moments of inertia. This levitation where the wheels stay level is non-physical."
#
# The driving model (JuliaMotorMTK DrivenVehicle3D) is a small-angle suspension model: heave, pitch and roll about the
# static pose, springs at the four corners, and contact forces that act only in the road plane. It is right for driving
# and wrong for a crash: at the PO's 162 km/h Monza wreck (2026-10-20 22:29) the right-front corner was torn off, the
# three remaining springs rolled the body to -85 deg and lifted it 2.4 m with nothing to stop them, and the drawn car
# showed none of it (its tilt is capped at ~6 deg and the wheels follow the road) -- a level car floating up.
#
# From the moment of a wreck the car is handed to this module instead: one rigid body in full 3-D (rotation matrix
# attitude, Euler's equations with the chassis inertias), touching the ground and the walls at the points of its real
# outline -- each wheel a sprung tyre that spins on its own axle with its own inertia, driven by tyre friction, and the
# tub, nose, gearbox, cockpit rim, roll hoop and helmet as hard points that scrape. It runs until the car is still and
# carried by the ground, then stops exactly where and how it lies.
#
# Frames: everything here is in RENDER coordinates, R = (X = game x, Y = up, Z = -game z), and the body frame is the car
# model's own (x forward, y up, z right) -- so the drawn matrix is the state itself, with no Euler-angle detour.
module WreckBody

using LinearAlgebra, StaticArrays

const V3 = SVector{3,Float64}
const M3 = SMatrix{3,3,Float64,9}
const G = 9.80665

"""Car geometry and the contact law. Body frame: x forward, y up, z right, origin at the CG."""
Base.@kwdef struct Geometry
    m::Float64 = 584.0
    I::V3 = V3(120.0, 890.0, 850.0)                 # about x (roll), y (yaw), z (pitch): the driving model's Ixx, Izz, Iyy
    hcg::Float64 = 0.30                             # CG above the ground at rest (the driving model's h)
    wheel_x::NTuple{4,Float64} = (1.314, 1.314, -1.096, -1.096)    # FL FR RL RR, forward of the CG
    wheel_z::NTuple{4,Float64} = (-0.75, 0.75, -0.75, 0.75)       # right of the CG (left = negative)
    wheel_r::NTuple{4,Float64} = (0.30, 0.30, 0.334, 0.334)
    wheel_w::Float64 = 0.12                         # half the tyre width: a wheel lying on its side touches at its face
    Iw::Float64 = 1.0                               # each wheel's spin inertia (the driving model's Iw)
    # the chassis outline (forward, up, right) from the CG -- a Lotus 49, tub floor ~8 cm off the road
    hull::Vector{V3} = V3[
        V3( 2.05, -0.14,  0.00),                                   # nose tip
        V3( 1.55, -0.20, -0.24), V3( 1.55, -0.20,  0.24),
        V3( 0.80, -0.22, -0.33), V3( 0.80, -0.22,  0.33),         # tub floor
        V3(-0.30, -0.22, -0.36), V3(-0.30, -0.22,  0.36),
        V3(-1.20, -0.18, -0.34), V3(-1.20, -0.18,  0.34),         # engine bay floor
        V3(-1.78, -0.08,  0.00),                                   # gearbox tail
        V3(-1.70,  0.05, -0.26), V3(-1.70,  0.05,  0.26),
        V3( 0.40,  0.22, -0.30), V3( 0.40,  0.22,  0.30),         # cockpit rim
        V3(-0.20,  0.33, -0.33), V3(-0.20,  0.33,  0.33),
        V3(-0.15,  0.62,  0.00),                                   # helmet
        V3(-0.38,  0.74,  0.00),                                   # roll hoop top
        V3(-1.00,  0.30, -0.30), V3(-1.00,  0.30,  0.30),         # engine top / exhausts
    ]
    k_tyre::Float64 = 40.0e3;  c_tyre::Float64 = 3.0e3            # wheel: suspension + tyre in series, per corner
    k_hull::Float64 = 300.0e3; c_hull::Float64 = 8.0e3            # chassis on the ground: hard, scraping
    k_wall::Float64 = 2.0e6;   c_wall::Float64 = 2.0e4
    k_hedge::Float64 = 6.0e4;  c_hedge::Float64 = 1.5e4; μ_hedge::Float64 = 1.2   # a hedge gives ~0.5 m and holds the car
    μ_tyre::Float64 = 1.1; μ_hull::Float64 = 0.6; μ_wall::Float64 = 0.5
    v_reg::Float64 = 0.3                            # m/s: friction regularisation (tanh) -- no stick-slip chatter
    Fcap::Float64 = 1.2e5                           # N: most any one contact point can push (a chassis crumples)
    Crr::Float64 = 0.02                             # tyre rolling resistance: a wreck on free wheels stops rolling
    bearing::Float64 = 0.5                          # N·m per rad/s of wheel spin
    Tbrake::NTuple{4,Float64} = (865.0, 865.0, 613.0, 613.0)  # N·m per wheel at full pedal (2956 total, 0.585 front)
    CdA::Float64 = 0.8
    hz::Float64 = 1200.0                            # integration rate
end

"""A ground patch: the plane Y = h0 + gx (X - X0) + gz (Z - Z0), refit every frame around the car."""
struct Plane
    X0::Float64; Z0::Float64; h0::Float64; gx::Float64; gz::Float64
end
Plane(h0::Real) = Plane(0.0, 0.0, Float64(h0), 0.0, 0.0)
plane_n(p::Plane) = normalize(V3(-p.gx, 1.0, -p.gz))
plane_y(p::Plane, X, Z) = p.h0 + p.gx*(X - p.X0) + p.gz*(Z - p.Z0)

"""The ground as the real terrain: `h(X, Z, yref)` = the surface height at or below `yref` (render frame; NaN off the
mesh), queried at each touching point -- a verge that rises against a wall, a kerb, a ditch are where they are. One fitted
plane cannot hold a verge: it tilted under the car and pushed the wall-side wheels up through it (the 2026-10-20 1.4 m hop
along Monza's wall). `plane` gives the contact direction and the fallback where the mesh has a hole."""
struct Terrain{F}
    h::F
    plane::Plane
end

"""Fit the ground plane from a height query `h(X, Z)` (render frame) sampled ±`d` m around (X, Z)."""
function fit_plane(h, X, Z; d = 1.5)
    y0 = h(X, Z); yx = h(X + d, Z) - h(X - d, Z); yz = h(X, Z + d) - h(X, Z - d)
    Plane(X, Z, y0, yx/(2d), yz/(2d))
end

"""A wall near the car this frame, as a plane: its surface passes through `p0` with `n` pointing out of it (render
frame, horizontal). `soft` = a hedge or hay bale: it gives and grips (the car buries itself) instead of bouncing."""
struct WallPlane
    p0::V3; n::V3; soft::Bool
end
WallPlane(p0::V3, n::V3) = WallPlane(p0, n, false)

mutable struct Body
    g::Geometry
    p::V3                   # CG position (render frame)
    v::V3
    R::M3                   # body -> render rotation
    ω::V3                   # angular velocity, body frame
    spin::MVector{4,Float64}       # wheel spin rate [rad/s], forward rolling positive
    angle::MVector{4,Float64}      # wheel rotation angle (for drawing)
    on::MVector{4,Bool}            # wheel still on the car
    dmu::MVector{4,Float64}        # per-corner grip factor (damage)
    still::Float64          # seconds spent still and carried
    rest::Bool
    t::Float64
    contacts::Int           # points touching on the last substep
    peak_h::Float64         # highest CG height above its ground (diagnostic)
    brake::Float64          # the driver's brake pedal, 0..1 (a wrecking driver stands on it)
    wall_peak::Float64      # the largest hard-wall push this frame [N] and that wall's normal: the game tears off the
    wall_n::V3              # wheels leading into a hard hit (as it does for the driving car)
end

Body(g::Geometry = Geometry()) =
    Body(g, V3(0, g.hcg, 0), V3(0, 0, 0), M3(I), V3(0, 0, 0), MVector(0.0, 0.0, 0.0, 0.0), MVector(0.0, 0.0, 0.0, 0.0),
         MVector(true, true, true, true), MVector(1.0, 1.0, 1.0, 1.0), 0.0, false, 0.0, 0, 0.0, 0.0, 0.0, V3(0, 0, 0))

roty(a) = (c = cos(a); s = sin(a); M3(c, 0, -s, 0, 1, 0, s, 0, c))
rotz(a) = (c = cos(a); s = sin(a); M3(c, s, 0, -s, c, 0, 0, 0, 1))
rotx(a) = (c = cos(a); s = sin(a); M3(1, 0, 0, 0, c, s, 0, -s, c))

"""Game pose -> body. x, z, ground_y: the game's planar position and the ground height under the car (render Y);
θ: heading (forward = (cos θ, sin θ) in game x, z); pitch: nose up +; roll: lean right + (the drawn car's own rotz / rotx
conventions). `v`: render-frame velocity; `ω_body` = (roll rate, yaw rate, pitch rate)."""
function start!(b::Body, x, z, ground_y, θ, pitch, roll, v::V3, ω_body::V3; spin = nothing,
                on = (true, true, true, true), dmu = (1.0, 1.0, 1.0, 1.0))
    b.R = roty(θ) * rotz(pitch) * rotx(roll)
    b.p = V3(x, ground_y, -z) + b.R * V3(0, b.g.hcg, 0)
    b.v = v; b.ω = ω_body
    for i in 1:4
        b.on[i] = on[i]; b.dmu[i] = dmu[i]; b.angle[i] = 0.0
        b.spin[i] = spin === nothing ? dot(v, b.R[:, 1]) / b.g.wheel_r[i] : spin[i]
    end
    b.still = 0.0; b.rest = false; b.t = 0.0; b.contacts = 0; b.peak_h = 0.0
    b
end

"""The drawn car's model matrix as 16 column-major values: the model's origin is the ground point under the CG."""
function model_matrix(b::Body)
    o = b.p - b.R * V3(0, b.g.hcg, 0); R = b.R
    (Float32(R[1,1]), Float32(R[2,1]), Float32(R[3,1]), 0f0,
     Float32(R[1,2]), Float32(R[2,2]), Float32(R[3,2]), 0f0,
     Float32(R[1,3]), Float32(R[2,3]), Float32(R[3,3]), 0f0,
     Float32(o[1]), Float32(o[2]), Float32(o[3]), 1f0)
end

"""(θ, pitch, roll) of the body in the drawn car's conventions -- for the camera, the HUD and the telemetry."""
function attitude(b::Body)
    f = b.R[:, 1]; u = b.R[:, 2]; r = b.R[:, 3]
    (atan(-f[3], f[1]), asin(clamp(f[2], -1.0, 1.0)), atan(-r[2], u[2]))
end

"""Game-frame position of the ground point under the CG (x, z) and the CG height."""
game_xz(b::Body) = (b.p[1], -b.p[3])

skew(w::V3) = M3(0, w[3], -w[2], -w[3], 0, w[1], w[2], -w[1], 0)

function orthonormalize(R::M3)
    x = normalize(R[:, 1]); y = normalize(R[:, 2] - dot(R[:, 2], x)*x); z = cross(x, y)
    M3(x[1], x[2], x[3], y[1], y[2], y[3], z[1], z[2], z[3])
end

"""Kinetic energy (translation + rotation + wheel spin) -- a crash may only lose it."""
energy(b::Body) = 0.5*b.g.m*dot(b.v, b.v) + 0.5*dot(b.ω, b.g.I .* b.ω) + 0.5*b.g.Iw*sum(abs2, b.spin)

"""A car that starts the frame INSIDE a wall -- the driving model hands over a car already up to ~0.4 m into the barrier
it hit -- is first moved out along the wall's normal and stripped of its speed into it, as a contact solver's position
correction would. Without this the stiff wall springs meet several deep points at once (~1 MN) and throw the car."""
function depenetrate!(b::Body, walls::Vector{WallPlane})
    g = b.g
    for w in walls
        w.soft && continue                          # a hedge is meant to be sunk into
        δ = 0.0
        for q in g.hull
            δ = max(δ, dot(w.p0 - (b.p + b.R*q), w.n))
        end
        for i in 1:4
            b.on[i] || continue
            δ = max(δ, dot(w.p0 - (b.p + b.R*V3(g.wheel_x[i], g.wheel_r[i] - g.hcg, g.wheel_z[i])), w.n) + g.wheel_r[i])
        end
        if δ > 0.05
            b.p += (δ - 0.02) * w.n
            vn = dot(b.v, w.n); vn < 0 && (b.v -= vn * w.n)
        end
    end
    b
end

"""An impulse from outside (another car hits the wreck): `dv` the render-frame velocity change, `dyaw` a yaw-rate change
about the world vertical. Wakes a body at rest (WRECKJIT-1 S2: a car hit went into the driving model, which is not
stepped in a wreck, so the wreck never felt it)."""
function kick!(b::Body, dv::V3, dyaw::Float64)
    b.v += dv; b.ω += b.R' * V3(0.0, dyaw, 0.0)
    b.rest = false; b.still = 0.0
    b
end

"""One frame of `dt` s on the ground `plane`, against this frame's `walls`."""
function step!(b::Body, dt::Float64, ground::Union{Plane,Terrain}; walls::Vector{WallPlane} = WallPlane[])
    b.rest && return b
    b.wall_peak = 0.0
    depenetrate!(b, walls)
    n = max(1, ceil(Int, dt * b.g.hz)); h = dt / n
    for _ in 1:n
        substep!(b, h, ground, walls)
    end
    b.t += dt
    plane = ground isa Plane ? ground : ground.plane
    b.peak_h = max(b.peak_h, b.p[2] - plane_y(plane, b.p[1], b.p[3]))
    # at rest = still AND carried by the ground (three or more points touching), for 0.6 s
    if norm(b.v) < 0.2 && norm(b.ω) < 0.2 && b.contacts >= 3
        b.still += dt
        b.still >= 0.6 && (b.rest = true; b.v = V3(0, 0, 0); b.ω = V3(0, 0, 0); b.spin .= 0.0)
    else
        b.still = 0.0
    end
    b
end

# a contact at lever r (render frame, from the CG): penalty spring-damper along `nrm`, regularised Coulomb friction across
@inline function _contact(b::Body, r::V3, δ, nrm::V3, k, c, μ)
    vp = b.v + cross(b.R * b.ω, r)
    vn = dot(vp, nrm)
    Fn = clamp(k*δ - c*vn, 0.0, b.g.Fcap)
    vt = vp - vn*nrm; s = norm(vt)
    Fn*nrm + (s > 1e-9 ? (-μ*Fn*tanh(s/b.g.v_reg)/s) * vt : V3(0, 0, 0))
end

@inline function _depth(ground::Plane, pw::V3, nrm::V3)
    (plane_y(ground, pw[1], pw[3]) - pw[2]) * nrm[2]
end
@inline function _depth(ground::Terrain, pw::V3, nrm::V3)
    yp = plane_y(ground.plane, pw[1], pw[3])
    pw[2] - yp > 1.5 && return -1.0                 # well above the ground: no query
    y = ground.h(pw[1], pw[3], pw[2] + 0.5)
    (isfinite(y) ? y - pw[2] : yp - pw[2]) * nrm[2]
end

function substep!(b::Body, h::Float64, ground::Union{Plane,Terrain}, walls::Vector{WallPlane})
    g = b.g
    plane = ground isa Plane ? ground : ground.plane
    nrm = plane_n(plane)
    F = V3(0, -g.m*G, 0)
    τ = V3(0, 0, 0)                      # torque about the CG, render frame
    contacts = 0
    sp = norm(b.v); sp > 0 && (F -= (0.5*1.2*g.CdA*sp) * b.v)
    depth(pw) = _depth(ground, pw, nrm)              # below the ground, along its normal
    # the chassis on the ground
    for q in g.hull
        r = b.R * q
        δ = depth(b.p + r)
        δ > 0 || continue
        f = _contact(b, r, δ, nrm, g.k_hull, g.c_hull, g.μ_hull)
        F += f; τ += cross(r, f); contacts += 1
    end
    # the wheels: a sprung tyre on the ground, spinning on its own axle
    a = b.R[:, 3]                                  # every axle is the body's right axis
    ŝ = -a                                         # forward rolling spins a wheel about the body's left
    for i in 1:4
        R_ = g.wheel_r[i]
        rh = b.R * V3(g.wheel_x[i], R_ - g.hcg, g.wheel_z[i]); hub = b.p + rh
        if !b.on[i]                                # the corner without its wheel: the upright scrapes like the hull
            r = rh - 0.12*b.R[:, 2]; δ = depth(b.p + r)
            δ > 0 || continue
            f = _contact(b, r, δ, nrm, g.k_hull, g.c_hull, g.μ_hull)
            F += f; τ += cross(r, f); contacts += 1
            continue
        end
        nd = nrm - dot(nrm, a)*a; ndn = norm(nd)  # the ground normal within the wheel's plane
        # the tyre's lowest point toward the ground (a cylinder's support point): the tread while it stands, the
        # sidewall edge as it leans, the face once it lies flat
        rc = rh - (ndn > 1e-6 ? R_*(nd/ndn) : V3(0, 0, 0)) - g.wheel_w*sign(dot(nrm, a))*a
        δ = depth(b.p + rc)
        δ > 0 || continue
        μ = g.μ_tyre * b.dmu[i]
        vp = b.v + cross(b.R * b.ω, rc)
        vn = dot(vp, nrm)
        Fn = clamp(g.k_tyre*δ - g.c_tyre*vn, 0.0, g.Fcap)
        vt = vp - vn*nrm
        ρ = cross(nrm, a); ρn = norm(ρ)
        if ρn > 0.3                               # rolling: the slip along the tread is against the wheel's own speed
            ρ /= ρn
            vρ = dot(vt, ρ); vλ = vt - vρ*ρ; sλ = norm(vλ)
            Ft = (-μ*Fn*tanh((vρ - b.spin[i]*R_)/g.v_reg) - g.Crr*Fn*tanh(vρ/0.1)) * ρ +
                 (sλ > 1e-9 ? (-μ*Fn*tanh(sλ/g.v_reg)/sλ) * vλ : V3(0, 0, 0))
            ft = norm(Ft); ft > μ*Fn && (Ft *= μ*Fn/ft)          # the friction circle
        else                                       # lying flat: it slides
            s = norm(vt)
            Ft = s > 1e-9 ? (-g.μ_hull*Fn*tanh(s/g.v_reg)/s) * vt : V3(0, 0, 0)
        end
        f = Fn*nrm + Ft
        # the force's moment about the axle spins the wheel; the bearing drags it and hands that back to the body
        Tspin = dot(cross(rc - rh, f), ŝ)
        Tbrg = g.bearing*b.spin[i] + b.brake*g.Tbrake[i]*tanh(b.spin[i]/0.5)   # bearing drag + the brake (locks it)
        b.spin[i] += h*(Tspin - Tbrg)/g.Iw
        F += f; τ += cross(rc, f) - (Tspin - Tbrg)*ŝ
        contacts += 1
    end
    # the walls: every hull point, and every wheel as a ball of its radius, against each plane
    for w in walls
        k, c, μ = w.soft ? (g.k_hedge, g.c_hedge, g.μ_hedge) : (g.k_wall, g.c_wall, g.μ_wall)
        wsum = 0.0
        for q in g.hull
            r = b.R * q
            δ = dot(w.p0 - (b.p + r), w.n)
            δ > 0 || continue
            f = _contact(b, r, δ, w.n, k, c, μ)
            F += f; τ += cross(r, f); wsum += dot(f, w.n)
        end
        for i in 1:4
            b.on[i] || continue
            rh = b.R * V3(g.wheel_x[i], g.wheel_r[i] - g.hcg, g.wheel_z[i])
            δ = dot(w.p0 - (b.p + rh), w.n) + g.wheel_r[i]
            δ > 0 || continue
            r = rh - g.wheel_r[i]*w.n
            f = _contact(b, r, δ, w.n, k, c, μ)
            F += f; τ += cross(r, f); wsum += dot(f, w.n)
        end
        (!w.soft && wsum > b.wall_peak) && (b.wall_peak = wsum; b.wall_n = w.n)
    end
    for i in 1:4
        b.angle[i] = mod(b.angle[i] + h*b.spin[i], 2π)
    end
    # semi-implicit Euler: velocities, then positions with the new velocities
    b.v += (h/g.m) * F
    ω = b.ω
    b.ω = ω + h * ((b.R' * τ - cross(ω, g.I .* ω)) ./ g.I)
    b.p += h * b.v
    b.R = orthonormalize(b.R + h * (b.R * skew(b.ω)))
    b.contacts = contacts
    b
end

end # module
