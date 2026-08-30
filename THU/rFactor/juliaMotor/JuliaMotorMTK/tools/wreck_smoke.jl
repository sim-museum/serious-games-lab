# E96 / E99 SMOKE: the PO's collision rules, as assertions.
#
# WHY THIS EXISTS
#   Four rounds of E96 and two of E99 were verified by throwaway scripts that no longer exist. The
#   rules they established are the PO's own words, and nothing in the repo would notice them
#   regressing:
#     E96  "car should never bounce back, ever"                       (2026-08-30)
#     E99  "a graze at speed should scrub you but not end your race"  (2026-08-30)
#     E95  "you hit something hard, your race is over"                (2026-08-29)
#   contact_smoke.jl already covers wall-stops-car and hedge-buries-car. This covers the three that
#   are about IMPULSE rather than placement, and it uses the same closing-speed rule the sim does.
#
#   Note contact_smoke.jl itself once ASSERTED THE BUG -- it passed on "BOUNCED BACK ✓" while the PO
#   was reporting exactly that. So these assertions are written against the PO's sentences, not
#   against whatever the code currently happens to do.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl"))
using .DriveRT3D
using Printf
const dt = 1/60; const M = 617.0; const CARHALF = 2.0
const WRECK_CLOSE = parse(Float64, get(ENV, "JM_WRECK_CLOSE", "12.0"))   # must match the sim
const WRECK_MS    = 50.0/3.6
flat(x,z) = 0.0

"Drive at an obstacle with a lateral offset; return what the sim's own trigger would see."
function hit(v0, lateral; r = 3.0, wallx = 60.0, nsteps = 500)
    c = build_car3d(; x0 = wallx - 12.0, z0 = lateral, θ0 = 0.0, v0 = v0, y0 = 0.0)
    rr = r + CARHALF; wvx = 0.0; wvz = 0.0
    closing = 0.0; touched = false; eafter = -1.0; worst_back = 0.0
    e(cc) = (a = cc.getall(cc.integ); 0.5*M*(a[4]^2 + a[5]^2))
    epre = 0.5*M*v0*v0; xprev = c.x
    for i in 1:nsteps
        dx = c.x - wallx; dz = c.z - 0.0; d = hypot(dx, dz); Fx=Fy=Mz=0.0; inct=false
        if d < rr && d > 1e-3
            nx = dx/d; nz = dz/d; vn = wvx*nx + wvz*nz
            closing = max(closing, -vn)
            (Fx,Fy,Mz) = DriveRT3D.contact_force(rr-d, nx, nz, vn, c.θ; kind=:wall, dt=dt)
            touched = true; inct = true
        end
        extforce3d!(c; Fx=Fx, Fy=Fy, Mz=Mz)
        step_car3d!(c, 0.0, 0.0, 0.0, dt; groundz = flat)
        (wvx, wvz) = DriveRT3D.world_velocity(c)
        touched && (worst_back = max(worst_back, (xprev - c.x)/dt))   # world-frame retreat
        xprev = c.x
        touched && !inct && eafter < 0 && (eafter = e(c))
    end
    (touched=touched, closing=closing, kept=100*(eafter < 0 ? e(c) : eafter)/epre,
     wrecks=(closing > WRECK_CLOSE && v0 > WRECK_MS), retreat=worst_back)
end

fails = Ref(0)
chk(name, ok, detail) = (@printf("  %-46s %s   %s\n", name, ok ? "PASS" : "FAIL", detail); ok || (fails[] += 1))

println("\n  E96/E99 collision-rule smoke\n")

# E96: no rebound, at any speed, off any object. VN_OUT_MAX is 0.25 m/s; allow a little slack for
# the solver's own response, but nothing a driver could read as a bounce.
for v0 in (2.0, 15.0, 30.0, 55.6)
    r = hit(v0, 0.0)
    chk(@sprintf("E96 no bounce-back at %3.0f km/h", v0*3.6), r.retreat < 1.0,
        @sprintf("peak retreat %.2f m/s", r.retreat))
end

# E99: a graze at speed scrubs but does not end the race.
g = hit(30.0, 4.9)
chk("E99 graze at 108 km/h does NOT wreck", !g.wrecks, @sprintf("closing %.1f m/s, kept %.0f%%", g.closing, g.kept))
chk("E99 graze keeps most of its energy",   g.kept > 50.0, @sprintf("kept %.0f%%", g.kept))

# E95: a square hit at speed ends the race.
sq = hit(30.0, 0.0)
chk("E95 square hit at 108 km/h WRECKS", sq.wrecks, @sprintf("closing %.1f m/s", sq.closing))
sl = hit(4.0, 0.0)
chk("E95 slow square hit does NOT wreck", !sl.wrecks, @sprintf("closing %.1f m/s (below the speed gate)", sl.closing))

@printf("\n  RESULT: %s\n", fails[] == 0 ? "COLLISION RULES OK ✓" : "FAIL ✗")
exit(fails[] == 0 ? 0 : 1)
