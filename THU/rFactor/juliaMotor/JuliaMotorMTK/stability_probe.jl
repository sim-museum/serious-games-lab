# Verify the traction aid: full-throttle release at 48 m/s must now DAMP (not spin).
include(joinpath(@__DIR__, "src", "drive_rt.jl")); using .DriveRT

function rel(; v0=48.0, throttle=1.0, bs=0.12, bt=45, ticks=300, dt=1/300, label="")
    c = DriveRT.build_car(x0=0.0, z0=0.0, θ0=0.0, v0=v0)
    println("\n=== $label  v0=$v0 thr=$throttle  TC_ON=$(DriveRT.TC_ON) ===")
    maxr_after = 0.0; rrel=0.0
    for k in 1:ticks
        st = k <= bt ? bs : 0.0
        DriveRT.step_car!(c, throttle, 0.0, st, dt)
        tl = DriveRT.telemetry(c)
        k == bt && (rrel = abs(tl.r))
        k > bt && (maxr_after = max(maxr_after, abs(tl.r)))
        if k % 30 == 0 || k == bt
            println("  t=$(rpad(round(k*dt,digits=2),5)) u=$(rpad(round(tl.u,digits=1),5)) v=$(rpad(round(tl.v,digits=1),6)) r=$(round(tl.r,digits=3))")
        end
    end
    verdict = maxr_after <= rrel*1.1 ? "STABLE (damps)" : "DIVERGES"
    println("  → yaw at release $(round(rrel,digits=3)); max after $(round(maxr_after,digits=3)) ⇒ $verdict")
end

rel(throttle=1.0, label="full throttle (was the SPIN)")
rel(throttle=1.0, v0=35.0, label="full throttle 35 m/s")
