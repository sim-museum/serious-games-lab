# offroad_smoke.jl — E104(b): driving off the edge of the terrain must not launch the car.
#
# PO 2026-08-31: "elastic collisions (if any) if a car goes off the road, leading to levitating and
# bouncing."
#
# THE MECHANISM, and why this gate is a physics test rather than a rendering one:
# drive_native_mtk's `groundz` reports "off the terrain mesh" as the sentinel **-999**, and several
# render-side callers test it as `gz > -900f0`. But drive_rt3d.jl:454 guards the height it receives
# with `isfinite(h) ? h : c.zref` -- and -999 IS FINITE. The sentinel sails through the guard, the
# wheel is told the ground is 999 m below, the suspension goes to full droop, and the next sample
# that IS on the mesh slams the car back. A levitate-and-bounce with no collision involved.
#
# So: feed the physics a ground function that goes off-mesh partway through, and compare the
# sentinel against a proper NaN. The sentinel arm is the negative control and MUST misbehave -- if
# both arms are quiet the guard is not the mechanism and this gate is testing nothing.
using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

fails = Ref(0)
chk(n, ok, d) = (@printf("  %-50s %s   %s\n", n, ok ? "PASS" : "FAIL", d); ok || (fails[] += 1))

"Drive straight at 30 m/s; past x = 40 m the ground query returns `offval` (off-mesh)."
function run_offroad(offval; secs = 6.0)
    c = DriveRT3D.build_car3d(; x0 = 0.0, v0 = 30.0); c.gear = 4
    c.s_gr(c.integ, DriveRT3D.GEARS[4])
    gz(x, z) = x > 40.0 ? offval : 0.0
    dt = 1/60
    ylo, yhi = Inf, -Inf
    for _ in 1:round(Int, secs/dt)
        DriveRT3D.step_car3d!(c, 0.25, 0.0, 0.0, dt; manual = true, groundz = gz)
        isfinite(c.y) || return (NaN, NaN, c)
        ylo = min(ylo, c.y); yhi = max(yhi, c.y)
    end
    (ylo, yhi, c)
end

println("\n  E104(b) — off the terrain mesh must not launch the car\n")

# NEGATIVE CONTROL FIRST: the -999 sentinel reaching the physics, as it did before this fix.
lo1, hi1, c1 = run_offroad(-999.0f0)
span1 = isfinite(hi1 - lo1) ? hi1 - lo1 : Inf
@printf("  sentinel -999 (the old path): y %.1f .. %.1f  (span %.1f m)\n", lo1, hi1, span1)
chk("control: the sentinel DOES misbehave", !(span1 < 5.0),
    span1 > 1e6 ? "diverged" : @sprintf("%.1f m of vertical travel", span1))

# TREATMENT: a proper "unknown", which the isfinite guard rejects as designed.
lo2, hi2, c2 = run_offroad(NaN32)
span2 = isfinite(hi2 - lo2) ? hi2 - lo2 : Inf
@printf("  NaN (off-mesh = unknown):     y %.1f .. %.1f  (span %.1f m)\n", lo2, hi2, span2)
chk("off-mesh with NaN keeps the car in place", span2 < 5.0, @sprintf("%.2f m of vertical travel", span2))
chk("and the car does not diverge", isfinite(c2.y) && isfinite(c2.v), @sprintf("y=%.2f v=%.1f", c2.y, c2.v))

println(fails[] == 0 ? "\n  OFF-ROAD GATE: PASS ✓" : "\n  OFF-ROAD GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
