# Skidpad peel-out: corner hard at low speed in 1st gear, then FLOOR it. With the TC
# gate OFF at low speed, flooring should overwhelm the rear (1st-gear torque ≫ grip)
# and break it loose (yaw spikes / spins). Compare TC default vs forced-off (JM_NOTC).
include(joinpath(@__DIR__, "src", "drive_rt.jl")); using .DriveRT

function skid(; v0=14.0, steer=0.7, ticks=240, dt=1/300, label="")
    c = DriveRT.build_car(x0=0.0, z0=0.0, θ0=0.0, v0=v0)
    c.gear = 1; c.s_gr(c.integ, DriveRT.GEARS[1])         # force 1st gear (peel-out gear)
    println("\n=== $label  v0=$v0  steer=$steer  gate@v0=$(round(clamp((v0-DriveRT.TC_VLO)/(DriveRT.TC_VHI-DriveRT.TC_VLO),0,1),digits=2)) ===")
    println("   t     u     r(yaw)   ay")
    for k in 1:ticks
        DriveRT.step_car!(c, 1.0, 0.0, steer, dt)         # full throttle, hard steer
        if k % 30 == 0
            tl = DriveRT.telemetry(c)
            note = abs(tl.r) > 1.0 ? "  <-- SPINNING" : ""
            println("  $(rpad(round(k*dt,digits=2),5)) $(rpad(round(tl.u,digits=1),5)) $(rpad(round(tl.r,digits=3),7)) $(round(tl.ay,digits=2))$note")
        end
    end
end

skid(label="skidpad peel-out, 1st gear (TC speed-gated, default)")
