# IRGOLD-1: the sim's cornering drag vs lateral g (counterpart of 261011/tools/cornerdrag.py on the gold): steady circles
# at V on the session car (settle_vr!, free PI throttle), the pedal and rpm logged; the drag follows from the same engine
# tables in cornerdrag.py. JM_CD_IBT = the session file stem (default 15-24-06), JM_CD_V [m/s] (default 31).
using Printf
include(joinpath(@__DIR__, "irgold_replay.jl"))
fn = first(filter(f -> occursin(get(ENV, "JM_CD_IBT", "15-24-06"), f), readdir(DG; join = true)))
sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u)
V = parse(Float64, get(ENV, "JM_CD_V", "31.0"))
get_ = ModelingToolkit.getsym(car.sys, [car.sys.u, car.sys.v, car.sys.r, car.sys.ay, car.sys.rpm])
println("g_target dir ay_sim v_kmh pedal rpm gear beta_deg steer_deg ok")
for dir in (1.0, -1.0), g in 0.2:0.1:1.25
    R = dir*g*G/V
    gr = findfirst(i -> V/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 7500, 1:5)
    δ, ok = settle_vr!(car, sp, u0, V, R, gr; δcap = 0.3)
    for _ in 1:120                                   # hold 2 s more with the settled steer and the PI throttle
        q = LASTSETTLE[]
    end
    u, v, r, ay, rpm = get_(car.integ)
    @printf("%.2f %+.0f %.3f %.1f %.3f %.0f %d %.2f %.2f %s\n", g, dir, ay/G, 3.6u, LASTSETTLE[].thr, rpm, gr, rad2deg(atan(v, u)), rad2deg(δ), ok)
end
