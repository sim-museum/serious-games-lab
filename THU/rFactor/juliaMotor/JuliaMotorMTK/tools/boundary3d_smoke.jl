# boundary3d_smoke.jl — E56.6: the world edge is a PHYSICAL WALL (contact_force(:wall) fed through
# extforce3d!), not a position snap-back.  Replicates the game's boundary logic against a Car3D:
# a virtual world is x ≤ 0; drive the car from x=-40 straight at +x past the edge and confirm the
# stiff inward wall force CONTAINS it (never escapes far / falls) and the integrator stays finite.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/boundary3d_smoke.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
flat(x, z) = 0.0
const FENCE_GRACE = 2.5; const FENCE_FAR = 16.0

function run_boundary(v0)
    c = DriveRT3D.build_car3d(; x0 = -40.0, v0 = v0); c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])
    dt = 1/60; lastgx = -40.0; lastgz = 0.0
    bfx = bfy = bmz = 0.0                                  # boundary force, applied with 1-frame latency
    maxover = 0.0; failsafe = 0
    for _ in 1:round(Int, 7.0/dt)
        DriveRT3D.extforce3d!(c; Fx = bfx, Fy = bfy, Mz = bmz)   # last frame's wall force
        DriveRT3D.step_car3d!(c, 0.5, 0.0, 0.0, dt; manual = true, groundz = flat)
        isfinite(c.x) || return (:DIVERGED, NaN, failsafe)
        if c.x <= 0.0                                      # inside the world
            lastgx = c.x; lastgz = c.z; bfx = bfy = bmz = 0.0
        else                                               # off the world edge → physical wall
            nwx = lastgx - c.x; nwz = lastgz - c.z; nl = hypot(nwx, nwz)
            nl < 1e-3 && (nwx = -1.0; nwz = 0.0; nl = 1.0); nwx /= nl; nwz /= nl
            maxover = max(maxover, c.x)
            if nl > FENCE_GRACE
                vn = c.v*cos(c.θ)*nwx + c.v*sin(c.θ)*nwz
                (bfx, bfy, bmz) = DriveRT3D.contact_force(nl - FENCE_GRACE, nwx, nwz, vn, c.θ; kind=:wall, dt=dt)
                if nl > FENCE_GRACE + FENCE_FAR; failsafe += 1; end   # would hard-seal in game (escape attempt)
            else
                bfx = bfy = bmz = 0.0
            end
        end
    end
    (c.x, maxover, failsafe)
end

println("\n  E56.6 physical-wall WORLD EDGE smoke (no teleport)\n")
ok = true
for v0 in (20.0, 40.0, 60.0)
    (xf, over, fs) = run_boundary(v0)
    held = isfinite(xf) && over < FENCE_GRACE + FENCE_FAR && fs == 0
    @printf("  approach %2.0f m/s: max penetration past edge = %.2f m   final x=%+.1f   failsafe hits=%d   → %s\n",
            v0, isnan(over) ? -1 : over, isnan(xf) ? NaN : xf, fs,
            held ? "WALL CONTAINS ✓" : "FAIL")
    global ok &= held
end
@printf("\n  RESULT: %s\n", ok ? "WORLD-EDGE WALL OK ✓ (physical bounce, no escape, no divergence)" : "FAIL ✗")
exit(ok ? 0 : 1)
