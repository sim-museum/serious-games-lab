# HANDLING-1: the PO's own slide, replayed. The 2026-10-08 21:55 WG race (WW103), run 2 lap 2: the car stepped out after
# the Speed Trap lift (s ≈ 2700) and slid sideways at 40–50° for ~4 s holding only 0.80–0.85 g. Here the sim car starts in
# that run's state at frame JM_POSLIDE_K0 and is driven with the PO's recorded throttle, brake, clutch and road steer
# angle, on flat ground, for JM_POSLIDE_SECS. Run it twice to compare models:
#   julia --project=. tools/poslide_261009.jl                          # today's car
#   JM_TC=1 JM_POSLIDE_RSY=0.629 julia --project=. tools/poslide_261009.jl   # before CARPHYS-1 S3/S4
using Printf
include(joinpath(@__DIR__, "wwab_261005.jl"))                # setup_params, ibt_open, ch, D5
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D   # (no JM_NOTC here: JM_TC=1 can bring the aid back)
using ModelingToolkit, OrdinaryDiffEq

"""The session car of an ibt (as arbfit_261005.jl's install!, which forces the traction aid off)."""
function install!(fn)
    sp = setup_params(ibt_open(fn).yaml)
    DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(fn))
    m, ff = DriveRT3D.mass_from_corner_weights(sp.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(fn))
    s = sp.spring_rate_Npmm; wr = DriveRT3D.wheel_rate
    DriveRT3D.set_suspension!(wr(s[:LF]), wr(s[:RF]), wr(s[:LR]; rear = true), wr(s[:RR]; rear = true); source = basename(fn))
    DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(sp; source = basename(fn)))
    sp
end
const WW103 = joinpath(D5, "lotus49_skidpad 2026-10-06 00-21-30.ibt")   # the PO raced WW103 (template of 261005)
# the car: WW103 (the WG race) unless JM_POSLIDE_SETUP names another session ibt (the Ring race ran the default setup:
# ~/gold standard/julia racer/261004/lotus49_nurburgring nordschleifetourist 2026-10-04 13-34-46.ibt)
const SETUP = get(ENV, "JM_POSLIDE_SETUP", WW103)

const IBT = get(ENV, "JM_POSLIDE_IBT", joinpath(@__DIR__, "..", "..", "data", "juliaracer", "lotus49_watglen 2026-10-08 21-55-45.ibt"))
const K0 = parse(Int, get(ENV, "JM_POSLIDE_K0", "22025"))
const SECS = parse(Float64, get(ENV, "JM_POSLIDE_SECS", "6"))

function main()
    f = ibt_open(IBT)
    c = Dict(x => ch(f, x) for x in ("VelocityX","VelocityY","YawRate","Throttle","Brake","Clutch","SteeringWheelAngle",
                                     "Gear","RPM","LFspeed","LRspeed","RRspeed","LatAccel","LongAccel","Speed"))
    sp = install!(SETUP); car = DriveRT3D.build_car3d(; v0 = 30.0); sys = car.sys
    rsy = get(ENV, "JM_POSLIDE_RSY", "")
    isempty(rsy) || for ty in (:FL, :FR, :RL, :RR)
        ModelingToolkit.setp(sys, getproperty(getproperty(sys, ty), :rsy))(car.integ, parse(Float64, rsy))
    end
    k = K0; g = Int(c["Gear"][k])
    car.gear = g; car.s_gr(car.integ, DriveRT3D.GEARS[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v, sys.r])(car.integ, [c["VelocityX"][k], c["VelocityY"][k], c["YawRate"][k]])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [c["LFspeed"][k]/0.30, c["LRspeed"][k]/DriveRT3D.RW_R, c["RRspeed"][k]/DriveRT3D.RW_R])
    car.s_we(car.integ, c["RPM"][k]*2π/60)
    obs = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ax, sys.ay])
    @printf("model: TC %s, rsy %s   from frame %d (%.0f km/h, gear %d)\n", DriveRT3D.TC_ON ? "ON" : "off",
            isempty(rsy) ? "default" : rsy, K0, 3.6c["Speed"][k], g)
    println("   t   |  PO's race: km/h    β°     |a| g |  sim: km/h    β°     |a| g    r")
    βmax = 0.0; slide = 0.0
    for j in 0:round(Int, SECS*60) - 1
        kk = K0 + j
        DriveRT3D.step_car3d!(car, c["Throttle"][kk], c["Brake"][kk], c["SteeringWheelAngle"][kk]/DriveRT3D.MAXSTEER, 1/60;
                              clutch = 1.0 - c["Clutch"][kk], manual = true)
        u, v, r, ax, ay = obs(car.integ)
        β = rad2deg(atan(v, max(abs(u), 1.0))); βmax = max(βmax, abs(β)); abs(β) > 20 && (slide += 1/60)
        if j % 30 == 0
            βg = rad2deg(atan(c["VelocityY"][kk], max(abs(c["VelocityX"][kk]), 1.0)))
            @printf("  %4.1f |  %6.1f  %6.1f  %5.2f   |  %6.1f  %6.1f  %5.2f  %5.2f\n", j/60, 3.6c["Speed"][kk], βg,
                    hypot(c["LatAccel"][kk], c["LongAccel"][kk])/9.80665, 3.6hypot(u, v), β, hypot(ax, ay)/9.80665, r)
        end
    end
    @printf("sim: max |β| %.1f°, time beyond 20° %.2f s\n", βmax, slide)
end
main()
