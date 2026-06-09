"""
    JuliaMotor

The engine: a Modelica-style vehicle dynamics model assembled from
rFactor's own data files (via RFactorData), built to reproduce isiMotor 2
behavior.  Phase 1: component library with bench validation — plain Julia
force functions first; ModelingToolkit wrapping comes with vehicle
assembly in Phase 2.

Implemented components:
  * `TBCTire` — tire force model with TBC slip-curve/peak-shift/load-
    sensitivity semantics (`lateral_force`, `longitudinal_force`,
    `tire_forces`)
"""
module JuliaMotor

using RFactorData
using RFactorData: SlipCurve, TBCFile, EngineFile, Vehicle, PMFile,
                   compound, slipcurve, param, section,
                   gear_ratios, final_drive_ratios, body, resolve, isequal_ci

export UniformSpline,
       TireCurve, LoadSens, PeakShift, TBCTire,
       reaction, loadmult, peakslip, combo,
       peak_mu_lat, peak_mu_long,
       lateral_force, longitudinal_force, tire_forces,
       EngineModel, engine_torque, full_torque, coast_torque, peak_power,
       Drivetrain, ngears, wheel_speed, engine_rpm, wheel_torque,
       Carrier, CarrierPose, solve_carrier, sweep, axle_sweep, corner_wheel,
       rotmat,
       VehicleModel, mass, effective_mass, longitudinal_accel, replay_speed,
       replay_yaw, drive_force_trace, replay_inputs, LATERAL_CAL,
       LOAD4_CAL, corner_loads,
       TrackSurface, HATResult, hat,
       TriangleHAT, hat3d, hat_meshes,
       SimSample, SimResult, simulate_lap, FrenetTrack, speed_profile, qss_speed_profile,
       CarState, DriveInput, DriveCar, spawn, step!, survey!

include("spline.jl")
include("tire.jl")
include("engine.jl")
include("drivetrain.jl")
include("suspension.jl")
include("vehicle.jl")
include("hat.jl")
include("trihat.jl")
include("sim.jl")
include("drive.jl")

end # module
