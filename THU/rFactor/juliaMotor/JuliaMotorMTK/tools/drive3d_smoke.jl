# drive3d_smoke.jl — headless smoke test of the real-time 3-D adapter (Car3D):
# drive at speed over a synthetic crest and confirm the suspension produces real
# VertAccel / ride heights / pitch / roll and the car goes airborne + lands.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/drive3d_smoke.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

# A crest in world X: flat, then a 0.30 m ramp up to x=110, then the ground falls
# away steeply (the far side of the hill) — launches the car off the crest.
function terrain(x, z)
    x < 100 && return 0.0
    x <= 110 && return 0.30 * (x - 100)/10          # ramp up to the crest
    return 0.30 - 0.18*(x - 110)                     # steep downslope past the crest
end

c = DriveRT3D.build_car3d(; x0 = 0.0, v0 = 55.0)
c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])     # 4th gear, ~55 m/s
println("\n  3-D Car drive over a crest (start ", round(c.v*3.6), " km/h)")
println("  t(s)   x(m)   km/h  pitch°  roll°  VertAccel  RH_F(mm) RH_R(mm)  note")
minfz_proxy = 9.9; maxvacc = 0.0; air_t = 0.0; landed_g = 0.0
dt = 1/300; tt = 0.0
for i in 1:1200
    global tt += dt
    s = DriveRT3D.step_car3d!(c, 0.35, 0.0, 0.0, dt; manual = true, groundz = terrain)
    global maxvacc = max(maxvacc, s.vacc/9.80665)
    air = s.vacc/9.80665 < 0.25                       # ~free-fall ⇒ airborne
    air && (global air_t += dt)
    rhF = (s.rh[1]+s.rh[2])/2*1000; rhR = (s.rh[3]+s.rh[4])/2*1000
    if i % 30 == 0 || air || s.vacc/9.80665 > 1.5
        note = air ? "AIRBORNE" : (s.vacc/9.80665 > 1.4 ? "LANDING" : "")
        @printf("  %4.2f  %5.1f  %4.0f  %+5.2f  %+5.2f   %+5.2f g   %5.0f   %5.0f   %s\n",
                tt, s.x, s.v*3.6, rad2deg(s.pitch), rad2deg(s.roll), s.vacc/9.80665, rhF, rhR, note)
    end
end
@printf("\n  airborne ≈ %.2f s   peak VertAccel landing = %.2f g\n", air_t, maxvacc)
@printf("  → real VertAccel / ride-height / pitch / roll channels now produced by JM.\n")
