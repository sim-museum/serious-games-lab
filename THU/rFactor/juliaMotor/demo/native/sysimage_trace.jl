# Precompile-trace workload for the jlracer sysimage build (PackageCompiler runs this
# to capture method instances to bake).  Headless — exercises the EXPENSIVE compile
# paths (mtkcompile, the Rosenbrock solve loop, GPL track parse, geometry/texture
# decode) WITHOUT opening a GLFW window, so it traces safely with no display.
const HERE = @__DIR__
using GLFW, ModernGL, LinearAlgebra, Dates           # bake package loads
using JuliaMotor, RFactorData

include(joinpath(HERE, "..", "..", "JuliaMotorMTK", "src", "drive_rt.jl"));   using .DriveRT
include(joinpath(HERE, "..", "..", "JuliaMotorMTK", "src", "drive_rt3d.jl")); using .DriveRT3D
include(joinpath(HERE, "..", "..", "JuliaMotorMTK", "src", "ibt.jl"));        using .IBT
include(joinpath(HERE, "gpltrack.jl")); using .GPLTrack
include(joinpath(HERE, "render.jl"));   using .Render      # bakes the CPU geometry/texture decode

println("[trace] mtkcompile + solve loop (planar brush) …")
car = DriveRT.build_car(x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0)
for i in 1:50
    DriveRT.step_car!(car, 0.6, 0.0, 0.1, 1/300)
end
DriveRT.telemetry(car); DriveRT.respawn!(car); DriveRT.contain!(car, 1.0, 1.0)

# the Magic-Formula path too (JM_MAGIC), so switching tyre models is also baked
let c2 = DriveRT.build_car(brush = false)
    for i in 1:5; DriveRT.step_car!(c2, 0.5, 0.0, 0.0, 1/300); end
end

println("[trace] 3-D contact solve …")
try
    c3 = DriveRT3D.build_car3d(x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0)
    for i in 1:20; DriveRT3D.step_car3d!(c3, 0.6, 0.0, 0.1, 1/300); end
    DriveRT3D.telemetry3d(c3)
catch e
    @info "3-D trace skipped" e
end

println("[trace] done.")
