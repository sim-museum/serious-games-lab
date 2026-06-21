# Measure the car's PEAK lateral grip (g): hold speed, slowly ramp steering to the limit,
# track max |ay|. iRacing skidpad .ibt = 1.40 g. Tune tyre μ to match.
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt.jl"); using .DriveRT

function main()
    c = build_car(v0 = 0.0)
    for _ in 1:280; step_car!(c, 1.0, 0.0, 0.0, 1/60); end
    peak = 0.0; vpk = 0.0
    for k in 1:600
        st = min(0.30, k/600 * 0.30)
        step_car!(c, 0.42, 0.0, st, 1/60)
        ay = abs(telemetry(c).ay) / 9.80665
        if c.v > 8 && ay > peak; peak = ay; vpk = c.v; end
    end
    println("PEAK lateral grip = $(round(peak,digits=3)) g  (at $(round(vpk,digits=1)) m/s)   [iRacing: 1.40 g]")
end
main()
