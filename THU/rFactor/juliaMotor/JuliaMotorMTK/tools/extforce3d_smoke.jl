# extforce3d_smoke.jl — E56.2: verify the body-frame external force/moment + drag-scale PORTS
# (Fx_ext, Fy_ext, Mz_ext, CdA_scale) actually drive the Car3D ODE via extforce3d!.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/extforce3d_smoke.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

flat(x, z) = 0.0
runsecs(c, secs; thr=0.0, brk=0.0, st=0.0, pre=()->nothing) = begin
    dt = 1/300
    for _ in 1:round(Int, secs/dt)
        pre()
        DriveRT3D.step_car3d!(c, thr, brk, st, dt; manual=true, groundz=flat)
    end
end

println("\n  E56.2 external-force PORT smoke (extforce3d!)\n")

# --- 1. Fy_ext → lateral acceleration / sideways drift ---------------------------------
c = DriveRT3D.build_car3d(; v0 = 40.0); c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])
runsecs(c, 0.5; thr=0.2)                                   # settle straight-line
z0 = c.z
runsecs(c, 1.0; thr=0.2, pre=()->DriveRT3D.extforce3d!(c; Fy = 4000.0))   # +Y body = left push
tel = DriveRT3D.telemetry3d(c)
@printf("  Fy_ext=+4000 N for 1 s:  lateral v = %+.2f m/s   Δz(world) = %+.2f m   %s\n",
        tel.v, c.z - z0, abs(tel.v) > 0.5 ? "OK (drifts sideways)" : "FAIL")
fy_ok = abs(tel.v) > 0.5

# Release the port → drift decays (no permanent force) ----------------------------------
runsecs(c, 1.5; thr=0.2, pre=()->DriveRT3D.extforce3d!(c))
tel2 = DriveRT3D.telemetry3d(c)
@printf("  released (extforce3d!(c)):  lateral v = %+.2f m/s   %s\n",
        tel2.v, abs(tel2.v) < abs(tel.v) ? "OK (decays)" : "FAIL")
rel_ok = abs(tel2.v) < abs(tel.v)

# --- 2. CdA_scale < 1 → less drag → higher coast/terminal speed (the DRAFT tow) --------
function topspeed(scale)
    c = DriveRT3D.build_car3d(; v0 = 50.0); c.gear = 5; c.s_gr(c.integ, DriveRT3D.GEARS[5])
    runsecs(c, 20.0; thr=1.0, pre=()->DriveRT3D.extforce3d!(c; CdA_scale = scale))
    c.v
end
v_full = topspeed(1.0); v_draft = topspeed(0.6)
@printf("  top speed  CdA_scale=1.0: %.1f km/h   CdA_scale=0.6: %.1f km/h   %s\n",
        v_full*3.6, v_draft*3.6, v_draft > v_full + 0.3 ? "OK (draft tows)" : "FAIL")
cda_ok = v_draft > v_full + 0.3

# --- 3. Mz_ext → yaw rate --------------------------------------------------------------
c = DriveRT3D.build_car3d(; v0 = 30.0); c.gear = 4; c.s_gr(c.integ, DriveRT3D.GEARS[4])
runsecs(c, 0.5; thr=0.2)
r0 = DriveRT3D.telemetry3d(c).r
runsecs(c, 0.5; thr=0.2, pre=()->DriveRT3D.extforce3d!(c; Mz = 3000.0))
r1 = DriveRT3D.telemetry3d(c).r
@printf("  Mz_ext=+3000 N·m for 0.5 s:  yaw rate %+.3f → %+.3f rad/s   %s\n",
        r0, r1, r1 > r0 + 0.05 ? "OK (yaws)" : "FAIL")
mz_ok = r1 > r0 + 0.05

allok = fy_ok && rel_ok && cda_ok && mz_ok
@printf("\n  RESULT: %s\n", allok ? "ALL PORTS LIVE ✓" : "PORT FAILURE ✗")
exit(allok ? 0 : 1)
