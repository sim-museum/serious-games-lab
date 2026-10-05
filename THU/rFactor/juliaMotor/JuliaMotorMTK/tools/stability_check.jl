# Stability suite for ANY tyre/brake change (TYRE-1-R/R2, BRAKE-1 lessons): constant-input step steers at
# 90/125 km/h (max sideslip must stay < 10°), the WOT 0.5° blip at 200/240 km/h (yaw must decay), a straight
# WOT pull to top speed (heading must hold) and trail braking from 250 km/h. Uses tyreid_261002.jl's car and checks.
#   julia --project=. tools/stability_check.jl
ENV["JM_TYREID_ITERS"] = "0"
include(joinpath(@__DIR__, "tyreid_261002.jl"))
using Printf
println("step steers (V km/h, throttle, steer deg -> max |β| deg) and WOT blips:")
st = stability(; verbose = true)
@printf("stability penalty %.3f (0 = every check passes)\n", st)

# straight WOT pull from 150 km/h in 5th for 30 s: heading drift and max |β|
function straight_pull()
    reinit!(CAR.integ, copy(U0)); CAR.gear = 5; CAR.s_gr(CAR.integ, DriveRT3D.GEARS[5])
    V = 150/3.6; ModelingToolkit.setu(SYS, [SYS.u, SYS.v])(CAR.integ, [V, 0.0])
    CAR.s_we(CAR.integ, V/DriveRT3D.RW_R*DriveRT3D.GEARS[5]*DriveRT3D.FINAL[])
    psi = ModelingToolkit.getsym(SYS, SYS.ψ); mb = 0.0
    for k in 1:60*30
        DriveRT3D.step_car3d!(CAR, 1.0, 0.0, 0.0, 1/60; clutch = 0.0, manual = true)
        u, v, r, ay = GET(CAR.integ); mb = max(mb, abs(rad2deg(atan(v, max(u, 1.0)))))
    end
    @printf("straight WOT pull 30 s: v %.0f km/h, heading %.4f rad, max |β| %.2f°\n", 3.6CAR.v, psi(CAR.integ), mb)
end
straight_pull()

# trail braking from 250 km/h: 2.5° turn-in held, pedal p for 3 s; max |β|
function trail(p)
    reinit!(CAR.integ, copy(U0)); CAR.gear = 5; CAR.s_gr(CAR.integ, DriveRT3D.GEARS[5])
    V = 250/3.6; ModelingToolkit.setu(SYS, [SYS.u, SYS.v])(CAR.integ, [V, 0.0])
    CAR.s_we(CAR.integ, V/DriveRT3D.RW_R*DriveRT3D.GEARS[5]*DriveRT3D.FINAL[])
    mb = 0.0
    for k in 1:180
        DriveRT3D.step_car3d!(CAR, 0.0, p*clamp(k/6, 0, 1), deg2rad(2.5)*clamp(k/12, 0, 1)/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, r, ay = GET(CAR.integ); mb = max(mb, abs(rad2deg(atan(v, max(u, 1.0))))); (u < 5 || mb > 30) && break
    end
    mb
end
println("trail braking from 250 km/h, 2.5° turn-in, max |β| by pedal: ",
        join([@sprintf("%.1f: %.1f°", p, trail(p)) for p in (0.4, 0.6, 0.8, 1.0)], "  "))
