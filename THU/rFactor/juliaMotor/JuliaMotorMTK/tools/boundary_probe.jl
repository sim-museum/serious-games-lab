# boundary_probe.jl — verify E7: the track boundary keeps the car in the world.
# Build a straight TrackSurface, drive a car forward then steer HARD off to one
# side, applying the same fence logic the game uses, and confirm the lateral
# offset never runs past the fence (the car collides + is held, not sailing off).
#
#   julia --project=demo/native JuliaMotorMTK/tools/boundary_probe.jl

using Printf
using JuliaMotor: TrackSurface, hat
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT

const FENCE = 13.0
# straight centreline along +x at z=0 (200 m), 9 m half-width road
ts = TrackSurface([(Float64(x), 0.0, 0.0) for x in 0:4:400]; halfwidth = 9.0)

c = DriveRT.build_car(; x0 = 5.0, z0 = 0.0, θ0 = 0.0, v0 = 25.0)
c.gear = 3; c.s_gr(c.integ, DriveRT.GEARS[3])

maxlat = 0.0; contained = 0
println("  drive forward, then steer hard off-track — does the fence hold?")
println("   t(s)   x(m)   lateral(m)   km/h   note")
dt = 1/60; tt = 0.0
for i in 1:600
    global tt += dt
    steer = tt > 1.0 ? 1.0 : 0.0                 # after 1 s, full steer to leave the track sideways
    DriveRT.step_car!(c, 0.6, 0.0, steer, dt; manual = true, clutch = 0.0)
    hr = hat(ts, c.x, c.z)
    if hr.found
        over = hr.lateral - clamp(hr.lateral, -FENCE, FENCE)
        if abs(over) > 0.01
            DriveRT.contain!(c, c.x - over*hr.perp[1], c.z - over*hr.perp[2]; vdamp = 0.5)
            global contained += 1
        end
        hr2 = hat(ts, c.x, c.z)
        global maxlat = max(maxlat, abs(hr2.lateral))
        if i % 40 == 0 || (abs(hr.lateral) > FENCE && i % 10 == 0)
            @printf("  %5.2f  %5.1f   %+8.2f   %4.0f   %s\n", tt, c.x, hr2.lateral, c.v*3.6,
                    abs(over) > 0.01 ? "← FENCE (contained)" : "")
        end
    end
    c.x > 390 && break
end
@printf("\n  max |lateral| reached = %.2f m   (fence at %.1f m)   contained %d frames\n", maxlat, FENCE, contained)
println(maxlat <= FENCE + 0.6 ? "  ✓ PASS — the car cannot leave the world (held at the fence)." :
                                 "  ✗ FAIL — the car got past the fence.")
