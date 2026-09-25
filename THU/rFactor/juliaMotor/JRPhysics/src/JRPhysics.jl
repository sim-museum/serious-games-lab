# PHYSPRE-1 (PO 2026-09-25: "pre-compile what speeds things up, but not what has minimal speed impact").
# Measured (JM_TIMING, Watkins Glen, 5-AI race launch): 209 s with the full 1.19 GB sysimage, 243 s without
# -- the sysimage buys 35 s, and the biggest phase, the physics build (mtkcompile of the car), is 87 s WITH it
# and 93 s without, although E80-S3 proved it ~100 % compilation (a second build takes 0.1 s). Why: the sim
# `include`d drive_rt*.jl as loose files, so every launch made a NEW module and nothing compiled for the car
# model -- by the sysimage trace or anyone else -- could ever be reused.
# This package owns those two modules, so Julia's package image caches the compiled car. The workload below
# builds and steps exactly what the sim uses (the 3-D player car and the shared-system AI field).
# The modules' ENV-read constants (traction aid, contact caps) are fixed at precompile time to their
# defaults; neither the launcher nor the sim sets them. JM_PHYS_INCLUDE=1 in the sim loads the loose files
# instead, with those knobs live, for A/B work.
module JRPhysics
# The engine audio's SampledSignals (via PortAudio) adds methods that INVALIDATE the cached symbolic/car code
# when it is loaded after this package: the player build went 5 s -> 96-99 s in the bisect (audio.jl alone).
# Loading it HERE, before the workload, compiles the cache in a world that already has those methods.
using SampledSignals
const MTKSRC = normpath(joinpath(@__DIR__, "..", "..", "JuliaMotorMTK", "src"))
include(joinpath(MTKSRC, "drive_rt.jl"))      # module DriveRT   (2-D)
include(joinpath(MTKSRC, "drive_rt3d.jl"))    # module DriveRT3D (the default player + AI physics)
export DriveRT, DriveRT3D

using PrecompileTools
@setup_workload begin
    flat(x, z) = 0.0
    @compile_workload begin
        c = DriveRT3D.build_car3d(x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0, y0 = 0.0)
        for i in 1:30; DriveRT3D.step_car3d!(c, 0.6, 0.0, 0.05, 1/60; manual = false, groundz = flat); end
        DriveRT3D.telemetry3d(c)
        field = DriveRT3D.build_cars3d([(0.0, 10.0, 0.0, 0.0), (0.0, 20.0, 0.0, 0.0)])
        for f in field, i in 1:10; DriveRT3D.step_car3d!(f, 0.5, 0.0, 0.0, 1/60; manual = false, groundz = flat); end
        DriveRT3D.damage_reset!()
    end
end
end # module
