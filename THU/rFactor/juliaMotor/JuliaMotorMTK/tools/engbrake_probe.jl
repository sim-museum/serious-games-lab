# engbrake_probe.jl — headless test of JuliaMotor's ENGINE-BRAKING downshift
# physics, the centripetal-circuit benchmark test: get up to speed in 5th, lift
# off the throttle, and shift down through the gears — each downshift should drag
# the engine up to the lower gear's speed (an RPM spike).  We compare the JM spike
# magnitude per downshift to the iRacing gold standard (~+1000..+1700 rpm/shift).
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/engbrake_probe.jl
#
# No human / no GL — it scripts the coast-down directly through DriveRT.step_car!.

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT
using .DriveRT: GEARS, FINAL, RW_R

const DT = 1/60

# rpm the rigid driveline implies at road speed v (m/s) in gear g
gear_rpm(v, g) = (v/RW_R) * GEARS[g] * FINAL * 60/(2π)

"Build a car already rolling at v0 (m/s) in `gear`, clutch engaged."
function rolling_car(v0, gear)
    c = DriveRT.build_car(; v0 = v0)
    c.gear = gear; c.s_gr(c.integ, GEARS[gear])
    # set engine state to match the rigid driveline at this speed/gear
    c.s_we(c.integ, (v0/RW_R)*GEARS[gear]*FINAL)
    DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true)  # settle one tick, clutch engaged
    c
end

function coastdown(; v0 = 44.0)
    c = rolling_car(v0, 5)
    println("\n  JM engine-braking coast-down  (start ", round(v0*3.6), " km/h, 5th gear)")
    println("  ", rpad("t",6), rpad("gear",5), rpad("km/h",7), rpad("rpm",8), "event")
    rows = NamedTuple[]
    t = 0.0
    # schedule: coast in 5th, then downshift one gear every ~1.0 s while throttle=0
    shifts = Dict(1.0=>true, 2.0=>true, 3.0=>true, 4.0=>true)   # times (s) to press downshift
    spikes = NamedTuple[]
    nextshift = sort(collect(keys(shifts)))
    si = 1
    while t < 6.0
        dn = false
        if si <= length(nextshift) && t >= nextshift[si]
            dn = true; si += 1
        end
        gbefore = c.gear; rb = c.rpm
        DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true, dn = dn)
        t += DT
        if dn
            # peak rpm in the 0.5 s after the shift
            rp = c.rpm
            for _ in 1:30
                DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true)
                t += DT; rp = max(rp, c.rpm)
            end
            push!(spikes, (from=gbefore, to=c.gear, rb=rb, rp=rp, d=rp-rb, v=c.v))
            @printf("  %-5.1f %-4d %-6.0f %-7.0f  DOWNSHIFT %d->%d  spike +%.0f rpm (peak %.0f)\n",
                    t, c.gear, c.v*3.6, c.rpm, gbefore, c.gear, rp-rb, rp)
        elseif abs(t - round(t)) < DT/2
            @printf("  %-5.1f %-4d %-6.0f %-7.0f\n", t, c.gear, c.v*3.6, c.rpm)
        end
    end
    println("\n  ── summary: RPM spike per coasting downshift ──")
    for s in spikes
        @printf("    %d->%d  rpm %5.0f -> %5.0f  (+%4.0f)   [rigid-driveline expected +%.0f]\n",
                s.from, s.to, s.rb, s.rp, s.d, s.rp - gear_rpm(s.v, s.from))
    end
    println("\n  iRacing gold (centripetal coast-down): each downshift +1000..+1700 rpm,",
            "\n  peaks ~6000-7300 rpm; speed bleeds 5->1 over ~7 s.\n")
    spikes
end

coastdown()
