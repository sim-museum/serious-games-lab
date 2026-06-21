# Why does the car hold a constant low velocity after a spin instead of stopping?
# Test BOTH clutch states over a long coast to separate idle-creep from a rolling-resistance
# low-speed deadzone (tanh(u/0.4) → 0 as u→0 leaves the last bit of speed undamped).
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt.jl"); using .DriveRT

function trial(label, clutch)
    c = build_car(v0 = 0.0)
    for _ in 1:240; step_car!(c, 1.0, 0.0, 0.0, 1/60; manual=true, clutch=0.0); end
    for _ in 1:75;  step_car!(c, 0.6, 0.0, 0.7, 1/60; manual=true, clutch=0.0); end
    print("$label (clutch=$(clutch)): v after spin=$(round(c.v,digits=1)) → ")
    for k in 1:1800   # 30 s coast
        step_car!(c, 0.0, 0.0, 0.0, 1/60; manual=true, clutch=clutch)
        if k % 300 == 0; print("$(round(c.v,digits=2)) "); end
    end
    println(c.v < 0.2 ? " ✅stops" : " ⚠holds $(round(c.v,digits=2)) m/s")
end

trial("CLUTCH IN ", 1.0)   # disengaged — pure coast (rolling resistance only)
trial("CLUTCH OUT", 0.0)   # engaged — engine idle can creep
