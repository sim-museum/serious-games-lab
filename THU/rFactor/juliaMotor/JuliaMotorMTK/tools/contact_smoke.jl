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
    # E96-S3: acceptance 1 is "no impact at ANY speed returns the car in the direction it came
    # from". The car approaches along +x, so any sustained negative world-x velocity after first
    # contact is a bounce-back. Record the worst one and how far back the car was carried.
    # A single-step negative velocity is NOT a bounce: a stiff spring unloading the car out of its
    # own penetration reads as one or two frames of backward motion and moves it nowhere. Measure
    # how LONG the reversal is sustained as well as how fast, and the net backward travel.
    touched = false; worstback = 0.0; xback = Inf; runlen = 0; maxrun = 0; xcontact = NaN
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
        if 1e-3 < hypot(c.x - ox, c.z) < rr && !touched; touched = true; xcontact = c.x; end
        if touched
            worstback = min(worstback, wvx)   # most negative = fastest travel back down the road
            xback     = min(xback, c.x)       # furthest point back reached after contact
            if wvx < -1.0; runlen += 1; maxrun = max(maxrun, runlen) else; runlen = 0; end
        end
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
    (c.x, c.v, maxpen, sticky, rebounded, worstback, xback, maxrun*dt, xcontact)
end

println("\n  E56.4 all-Modelica spring-damper CONTACT smoke\n")

xw, vw, penw, stuckw, rebw, bkw, xbw, rvw, xcw = run_into(:wall, 0.0, 1.2)
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

xh, vh, penh, stuckh, rebh, bkh, xbh, rvh, xch = run_into(:soft, 0.0, 2.2)
@printf("  HEDGE (k weak, viscous):   final x=%+.1f m  v=%.1f m/s  maxpen=%.2f m  → %s\n",
        xh, vh, penh, (abs(xh) < 3.6 && vh < 3.0) ? "BURIED & STUCK ✓" : "FAIL")
hedge_ok = isfinite(xh) && abs(xh) < 4.0 && vh < 3.0 && penh > 0.8   # drove IN and stopped, no pass-through

# E96-S3: the PO's first acceptance is an ABSOLUTE -- "no impact AT ANY SPEED returns the car in
# the direction it came from" -- and this gate tested exactly one speed (30 m/s). One speed cannot
# support an "any speed" claim, and the interesting failures in a spring-damper contact live at the
# ENDS: too slow and the spring wins, too fast and the penetration does. Sweep it.
println("\n  E96 acceptance 1 -- no bounce-back at ANY approach speed (wall):\n")
sweep_ok = true
for v0 in (5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 80.0)
    x, v, pen, st, rb, bk, xb, rvt, xc = run_into(:wall, 0.0, 1.2; v0 = v0, secs = 8.0)
    # THREE ways a wall hit can be wrong, and they are alternatives, not a conjunction:
    #   sustained reversal  -- backwards for >0.15 s (one stiff step is the spring unloading the
    #                          car out of its own penetration; it moves the car nowhere)
    #   carried back        -- ends up >3 m behind where it FIRST TOUCHED, i.e. returned down the road
    #   passed through      -- ends up beyond the obstacle
    # The first cut required reversal AND displacement together, and used `x - xb`, which for a
    # car that went THROUGH the wall reports a huge positive "carried back". The control arm
    # (JM_VN_OUT_MAX=8) then reversed for 0.70 s at 10 m/s and passed clean through at 60 and
    # 80 m/s, and this gate still printed "no bounce-back". A gate that cannot fail its own
    # control is not evidence; measure each failure separately.
    carried = isfinite(xc) ? (xc - x) : 0.0          # positive = ended up behind first contact
    through = x > 0.0 + 1.2 + CARHALF          # past the obstacle (ox + r + car half-length)
    bad  = !isfinite(x) || rvt > 0.15 || carried > 3.0 || through
    global sweep_ok = sweep_ok && !bad
    @printf("    v0=%4.0f m/s  final x=%+7.1f  v=%5.1f  maxpen=%.2f  peak rev=%+6.1f m/s  reversing %.2f s  carried back=%5.1f m  %s\n",
            v0, x, v, pen, bk, rvt, carried,
            !isfinite(x) ? "FAIL <- diverged" : through ? "FAIL <- PASSED THROUGH" :
            rvt > 0.15 ? "FAIL <- SUSTAINED REVERSAL" : carried > 3.0 ? "FAIL <- RETURNED" : "ok")
end
println(sweep_ok ? "\n    no approach speed produced a bounce-back \u2713" :
                   "\n    BOUNCE-BACK AT ONE OR MORE SPEEDS \u2717")

allok = wall_ok && hedge_ok && sweep_ok
@printf("\n  RESULT: %s\n", allok ? "CONTACT LAW OK ✓ (wall STOPS the car · hedge sticks · no divergence)" : "FAIL ✗")
exit(allok ? 0 : 1)
