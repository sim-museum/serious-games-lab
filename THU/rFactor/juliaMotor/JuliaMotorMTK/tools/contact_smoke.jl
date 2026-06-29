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
    for i in 1:round(Int, secs/dt)
        # contact from the CURRENT state, fed before the step (zero latency)
        dx = c.x - ox; dz = c.z - 0.0; d = hypot(dx, dz)
        Fx = Fy = Mz = 0.0
        if 1e-3 < d < rr
            nx = dx/d; nz = dz/d
            vn = c.v*cos(c.θ)*nx + c.v*sin(c.θ)*nz          # car vel along the outward normal
            δ  = rr - d
            (Fx, Fy, Mz) = DriveRT3D.contact_force(δ, nx, nz, vn, c.θ; kind=kind, dt=dt)
            maxpen = max(maxpen, δ)
        end
        DriveRT3D.extforce3d!(c; Fx=Fx, Fy=Fy, Mz=Mz)
        DriveRT3D.step_car3d!(c, 0.0, 0.0, 0.0, dt; manual=true, groundz=flat)
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
@printf("  WALL  (k stiff, elastic):  final x=%+.1f m  v=%.1f m/s  maxpen=%.2f m  → %s\n",
        xw, vw, penw, rebw ? "BOUNCED BACK ✓" : (xw < -1.0 ? "stopped/back ✓" : "FAIL (passed through)"))
wall_ok = isfinite(xw) && xw < 0.5 && vw < 8.0 && penw < 2.6   # didn't pass through, didn't blow up

xh, vh, penh, stuckh, rebh = run_into(:soft, 0.0, 2.2)
@printf("  HEDGE (k weak, viscous):   final x=%+.1f m  v=%.1f m/s  maxpen=%.2f m  → %s\n",
        xh, vh, penh, (abs(xh) < 3.6 && vh < 3.0) ? "BURIED & STUCK ✓" : "FAIL")
hedge_ok = isfinite(xh) && abs(xh) < 4.0 && vh < 3.0 && penh > 0.8   # drove IN and stopped, no pass-through

allok = wall_ok && hedge_ok
@printf("\n  RESULT: %s\n", allok ? "CONTACT LAW OK ✓ (wall bounces · hedge sticks · no divergence)" : "FAIL ✗")
exit(allok ? 0 : 1)
