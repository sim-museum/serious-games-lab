# WWSETUP-1 C2: straight-line braking of the WW103 car (54 % pressure bias -> torque split, soft front springs), gold vs sim.
#
# Gold: the 261005 Döttinger Höhe file (00-49-20). Every window of >= 0.5 s with the pedal steady (range < 0.1), the
# wheel straight (|steer| < 5°) and speed > 15 m/s gives (pedal, speed, deceleration g). Sim: the WW103 car (the same
# file's setup, every chassis input) braked from that speed at that pedal for the same time, straight, clutch in.
#   julia --project=. tools/brakeval_261005.jl
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const G = 9.80665
const FN = get(ENV, "JM_BRAKE_IBT", expanduser("~/gold standard/julia racer/261005/lotus49_nurburgring nordschleifetourist 2026-10-06 00-49-20.ibt"))

function windows(f)
    c = Dict(n => channel(f, n) for n in ("Speed","LongAccel","Brake","SteeringWheelAngle","IsOnTrack"))
    v, ax, b, sw = c["Speed"], c["LongAccel"], c["Brake"], c["SteeringWheelAngle"]
    W = NamedTuple[]; k = 1
    while k < f.nrows - 30
        if b[k] > 0.15 && v[k] > 15 && c["IsOnTrack"][k] > 0.5
            j = k
            while j < f.nrows && abs(b[j+1] - b[k]) < 0.1 && v[j+1] > 12 && abs(sw[j+1]) < deg2rad(5)*10; j += 1; end
            if j - k >= 30
                push!(W, (pedal = mean(b[k:j]), v0 = v[k], v1 = v[j], dur = (j - k)/60, g = -mean(ax[k:j])/G))
            end
            k = j + 1
        else
            k += 1
        end
    end
    W
end

function main()
    f = ibt_open(FN); sp = setup_params(f.yaml)
    DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(FN))
    m, ff = DriveRT3D.mass_from_corner_weights(sp.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(FN))
    s = sp.spring_rate_Npmm
    DriveRT3D.set_suspension!(wheel_rate(s[:LF]), wheel_rate(s[:RF]), wheel_rate(s[:LR]; rear = true), wheel_rate(s[:RR]; rear = true); source = basename(FN))
    get(ENV, "JM_BRAKE_CHASSIS", "1") == "1" && DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(sp; source = basename(FN)))
    println("car: ", DriveRT3D.describe_chassis())
    car = DriveRT3D.build_car3d(; v0 = 40.0); u0 = copy(car.integ.u); sys = car.sys
    gs = ModelingToolkit.getsym(sys, [sys.u, sys.ax])
    println("   pedal  v0 km/h  dur s | gold g | sim g")
    for w in windows(f)
        reinit!(car.integ, copy(u0)); car.gear = 0; car.s_gr(car.integ, 0.0)
        ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [w.v0, 0.0])
        DriveRT3D.CHASSIS[].diff === nothing ? ModelingToolkit.setu(sys, [sys.ωf, sys.ωr])(car.integ, [w.v0/0.30, w.v0/DriveRT3D.RW_R]) :
            ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [w.v0/0.30, w.v0/DriveRT3D.RW_R, w.v0/DriveRT3D.RW_R])
        axs = Float64[]
        for n in 1:round(Int, w.dur*60)
            DriveRT3D.step_car3d!(car, 0.0, w.pedal, 0.0, 1/60; clutch = 1.0, manual = true)
            u, ax = gs(car.integ); push!(axs, ax); u < 12 && break
        end
        @printf("   %.2f   %5.0f   %4.1f  | %5.2f  | %5.2f\n", w.pedal, 3.6w.v0, w.dur, w.g, -mean(axs)/G)
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
