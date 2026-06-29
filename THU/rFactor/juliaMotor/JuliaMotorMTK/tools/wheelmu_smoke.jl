# wheelmu_smoke.jl — E56.5: verify per-wheel tyre μscale (grass grip) drives the brush model.
# A steady-state cornering test: same steer, lower μ → less lateral grip → lower lateral accel.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/wheelmu_smoke.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
flat(x, z) = 0.0

function corner_ay(μ; secs = 3.0, v0 = 30.0, steer = 0.5)
    c = DriveRT3D.build_car3d(; v0 = v0); c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])
    dt = 1/300; aypk = 0.0
    for _ in 1:round(Int, secs/dt)
        DriveRT3D.wheelmu3d!(c, μ, μ, μ, μ)
        DriveRT3D.step_car3d!(c, 0.25, 0.0, steer, dt; manual = true, groundz = flat)
        aypk = max(aypk, abs(DriveRT3D.telemetry3d(c).ay))
    end
    aypk
end

println("\n  E56.5 per-wheel tyre μscale (grass grip) smoke\n")
ay_tar = corner_ay(1.0)
ay_grs = corner_ay(0.5)
@printf("  steady corner  μ=1.0 (tarmac): peak |ay| = %.2f m/s²\n", ay_tar)
@printf("  steady corner  μ=0.5 (grass) : peak |ay| = %.2f m/s²\n", ay_grs)
ok = isfinite(ay_tar) && isfinite(ay_grs) && ay_grs < ay_tar - 1.0 && ay_grs > 0.5
@printf("\n  RESULT: %s\n", ok ? "μscale LIVE ✓ (grass cuts grip)" : "FAIL ✗")
exit(ok ? 0 : 1)
