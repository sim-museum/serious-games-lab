# PO 2026-08-27: coast-down at LOW speed — "let off the throttle and it stops very quickly".
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","drive_rt.jl"))); using .DriveRT
function coast(label, clutch, target_kmh)
    c = build_car(v0 = 0.0)
    n=0
    while c.v*3.6 < target_kmh && n < 3000; step_car!(c, 1.0, 0.0, 0.0, 1/60; manual=false, clutch=0.0); n+=1; end
    print(rpad(label,12), " from ", round(c.v*3.6,digits=1), " km/h: ")
    for k in 1:1800
        step_car!(c, 0.0, 0.0, 0.0, 1/60; manual=false, clutch=clutch)
        k % 60 == 0 && print(round(c.v*3.6,digits=1), " ")
        if c.v*3.6 < 1.0; println("  → STOPPED after ", round(k/60,digits=1), " s"); return; end
    end
    println("  → still ", round(c.v*3.6,digits=1), " km/h after 30 s")
end
coast("from 100", 0.0, 100.0)
coast("from 60",  0.0,  60.0)
