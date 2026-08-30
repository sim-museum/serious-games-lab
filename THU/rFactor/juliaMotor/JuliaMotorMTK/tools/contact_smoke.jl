# contact_smoke.jl — E56.4: drive a Car3D into a synthetic obstacle using the all-Modelica
# spring-damper CONTACT kernel (contact_force → extforce3d! → step), and confirm the two
# distinct GPL behaviours: a WALL bounces the car back; a HEDGE buries it and it gets stuck.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/contact_smoke.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

flat(x, z) = 0.0
const CARHALF = 1.4

# one obstacle at (ox,0), collision radius r; drive the car straight at it from x=-40, v0=30
function run_into(kind, ox, r; v0 = 30.0, secs = 6.0)
    c = DriveRT3D.build_car3d(; x0 = -40.0, v0 = v0); c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])
    dt = 1/60; rr = r + CARHALF
    maxpen = 0.0; vmin = v0; bounced = false; stuck = false
    prvx = NaN; prvz = NaN; wvx = 0.0; wvz = 0.0            # E96-S2: world velocity, by position delta
    for i in 1:round(Int, secs/dt)
        # contact from the CURRENT state, fed before the step (zero latency)
        dx = c.x - ox; dz = c.z - 0.0; d = hypot(dx, dz)
        Fx = Fy = Mz = 0.0
        if 1e-3 < d < rr
            nx = dx/d; nz = dz/d
            # E96-S2: the TRUE world velocity, from the position delta. This test used
            # `c.v*cos(θ)*nx + c.v*sin(θ)*nz`, and c.v is an UNSIGNED SPEED -- so a car being
            # pushed backwards off the obstacle still read as driving INTO it, which turns the
            # contact clamp into an accelerator. The sim was fixed in E96-S2; the test kept the
            # old convention and so was still measuring the bug.
            vn = wvx*nx + wvz*nz                             # car vel along the outward normal
            δ  = rr - d
            (Fx, Fy, Mz) = DriveRT3D.contact_force(δ, nx, nz, vn, c.θ; kind=kind, dt=dt)
            maxpen = max(maxpen, δ)
        end
        DriveRT3D.extforce3d!(c; Fx=Fx, Fy=Fy, Mz=Mz)
        DriveRT3D.step_car3d!(c, 0.0, 0.0, 0.0, dt; manual=true, groundz=flat)
        wvx = isfinite(prvx) ? (c.x - prvx)/dt : 0.0
        wvz = isfinite(prvz) ? (c.z - prvz)/dt : 0.0
        prvx = c.x; prvz = c.z
        # signed forward speed (car heading ·world vel): negative ⇒ moving backwards = bounced
        fwd = c.v * sign(cos(c.θ)*cos(c.θ) + 1)             # |v| (heading ~0 here)
        vmin = min(vmin, c.x)                                # track furthest progress (min x is start)
        if c.x < ox - rr - 0.5 && i > 30; bounced = true; end   # ended up well back from the obstacle
    end
    # final state
    dfin = c.x - ox
    isfinite(c.x) || return (:DIVERGED, NaN, NaN, NaN)
    sticky = abs(dfin) < rr + 0.6 && c.v < 2.0              # came to rest inside/at the obstacle
    rebounded = c.x < ox - rr + 0.3 && c.v < 6.0            # pushed back out in front of it, slow
    (c.x, c.v, maxpen, sticky, rebounded)
end

println("\n  E56.4 all-Modelica spring-damper CONTACT smoke\n")

xw, vw, penw, stuckw, rebw = run_into(:wall, 0.0, 1.2)
# E96 (PO 2026-08-30: "car should never bounce back, ever") -- this line used to PASS on
# `BOUNCED BACK ✓`, i.e. it asserted the very behaviour the PO rejected. A wall must now STOP the
# car near the obstacle, not return it. Passing straight through is still a failure.
@printf("  WALL  (inelastic, no rebound): final x=%+.1f m  v=%.1f m/s  maxpen=%.2f m  → %s\n",
        xw, vw, penw, (xw < -1.0 && abs(xw) < 6.0 && vw < 3.0) ? "STOPPED AT THE WALL ✓" :
                      (xw >= -1.0 ? "FAIL (passed through)" : "FAIL (thrown back to $(round(xw,digits=1)) m)"))
# E96: no rebound at any speed. `xw < 0.5` alone accepted a car thrown 78 m back down the road,
# which is how this test passed while the PO was complaining about exactly that. Bound BOTH sides:
# it must stop NEAR the obstacle, not pass through it and not be returned down the road.
wall_ok = isfinite(xw) && xw < -1.0 && abs(xw) < 6.0 && vw < 3.0 && penw < 2.6

xh, vh, penh, stuckh, rebh = run_into(:soft, 0.0, 2.2)
@printf("  HEDGE (k weak, viscous):   final x=%+.1f m  v=%.1f m/s  maxpen=%.2f m  → %s\n",
        xh, vh, penh, (abs(xh) < 3.6 && vh < 3.0) ? "BURIED & STUCK ✓" : "FAIL")
hedge_ok = isfinite(xh) && abs(xh) < 4.0 && vh < 3.0 && penh > 0.8   # drove IN and stopped, no pass-through

allok = wall_ok && hedge_ok
@printf("\n  RESULT: %s\n", allok ? "CONTACT LAW OK ✓ (wall STOPS the car · hedge sticks · no divergence)" : "FAIL ✗")
exit(allok ? 0 : 1)
