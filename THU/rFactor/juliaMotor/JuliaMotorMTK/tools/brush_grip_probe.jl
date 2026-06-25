# brush_grip_probe.jl — validate the brush tyre WIRED INTO the car: build both the
# Magic-Formula car and the physics-brush car, ramp the steering at speed, and read
# the peak lateral grip.  Brush should cap at μ≈1.2 g (the measured friction); the
# fudged Magic Formula caps higher (~1.45 g).
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/brush_grip_probe.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT
const G = 9.80665

function peak_grip(brush)
    c = DriveRT.build_car(; v0 = 22.0, brush = brush)
    c.gear = 2; c.s_gr(c.integ, DriveRT.GEARS[2])
    maxg = 0.0; dt = 1/60
    for i in 1:300
        st = clamp((i*dt)/2.0, 0.0, 1.0)                 # ramp steer to full over 2 s
        DriveRT.step_car!(c, 0.25, 0.0, st, dt; manual = true, clutch = 0.0)
        tl = DriveRT.telemetry(c)
        c.v > 6.0 && (maxg = max(maxg, abs(tl.ay)/G))     # peak lateral grip once rolling
    end
    maxg
end

println("\n  ───── peak lateral grip: Magic Formula (fudged) vs physics brush ─────")
gm = peak_grip(false); @printf("    Magic Formula : %.2f g   (tyre μ 1.45 — fudged ×1.13)\n", gm)
gb = peak_grip(true);  @printf("    brush (physics): %.2f g   (tyre μ 1.21 — measured)\n", gb)
@printf("\n  grip ratio brush/Magic = %.2f   (μ ratio 1.21/1.45 = %.2f)\n", gb/gm, 1.21/1.45)
println(gb < gm && 0.78 < gb/gm < 0.90 ?
        "  ✓ the wired brush car is less grippy by exactly the PHYSICAL μ ratio — fudge removed." :
        "  (review: ratio off)")
