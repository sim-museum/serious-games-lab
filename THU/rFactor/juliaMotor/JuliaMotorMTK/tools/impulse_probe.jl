# impulse_probe.jl — E99-S4. DOES THE BODY RECEIVE THE IMPULSE THE CAPS ASSUME?
#
# E99-S3 measured the exit-bleed branch applying ~39 kN into the obstacle for 28 consecutive frames
# while the car's separation speed barely moved. Its cap — and the VN_OUT_MAX outcome cap, and the
# CONTACT_DVMAX clamp — are all sized as `F = m·Δv/dt`, i.e. they assume one step of that force
# changes the velocity by exactly Δv. This measures that assumption directly: apply a known force
# through the SAME path a contact uses (`extforce3d!` then `step_car3d!`) and compare the velocity
# change with F·dt/m.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/impulse_probe.jl

include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using Printf

const dt = 1/60; const M = 617.0
flat(x, z) = 0.0

"Apply (Fx,Fy) in the body frame for one step from a straight-line state at v0; return Δ(u,v)."
function one_step(v0, Fx, Fy)
    c = build_car3d(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = v0, y0 = 0.0)
    for _ in 1:30                                   # settle, no forces
        extforce3d!(c; Fx = 0.0, Fy = 0.0, Mz = 0.0)
        step_car3d!(c, 0.0, 0.0, 0.0, dt; groundz = flat)
    end
    a0 = c.getall(c.integ); u0 = a0[4]; v0b = a0[5]
    extforce3d!(c; Fx = Fx, Fy = Fy, Mz = 0.0)
    step_car3d!(c, 0.0, 0.0, 0.0, dt; groundz = flat)
    a1 = c.getall(c.integ)
    # the same step with NO force, to subtract drag/rolling/tyre effects
    c2 = build_car3d(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = v0, y0 = 0.0)
    for _ in 1:30
        extforce3d!(c2; Fx = 0.0, Fy = 0.0, Mz = 0.0)
        step_car3d!(c2, 0.0, 0.0, 0.0, dt; groundz = flat)
    end
    extforce3d!(c2; Fx = 0.0, Fy = 0.0, Mz = 0.0)
    step_car3d!(c2, 0.0, 0.0, 0.0, dt; groundz = flat)
    b1 = c2.getall(c2.integ)
    (du = (a1[4] - u0) - (b1[4] - u0), dv = (a1[5] - v0b) - (b1[5] - v0b))
end

@printf("\nE99-S4: Δv from ONE extforce3d! + step_car3d!, against the F·dt/m the caps assume\n\n")
@printf("%-10s %-12s %-12s %-12s %-12s %-8s\n", "v0 km/h", "F (kN)", "expect du", "measured du", "measured dv", "ratio")
for v0 in (5.0, 30.0)
    for F in (5.0e3, 3.9e4, 2.96e5)
        r = one_step(v0, -F, 0.0)                    # straight back along the body x axis
        expect = -F*dt/M
        @printf("%-10.0f %-12.1f %-12.4f %-12.4f %-12.4f %-8.3f\n",
                v0*3.6, F/1000, expect, r.du, r.dv, r.du/expect)
    end
end
println("\n  ratio 1.0 = the body receives exactly F·dt/m. Anything else means every force-level cap",
        "\n  in contact_force is sized against a Δv that does not arrive.\n")
