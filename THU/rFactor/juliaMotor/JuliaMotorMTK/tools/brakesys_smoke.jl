# CARPHYS-1 S6: the BrakeSystem object (master cylinder, bias valve, calipers), against what the gold records.
#   * full pedal makes iRacing's line pressures: front 65.4 bar at 53.5 % bias, 66.0 at 54 % (122.2 bar × bias);
#   * at the reference 53.5 % the axle torques are exactly the BRAKE-2 fit (2956 N·m, 0.585 front);
#   * a different garage bias moves the pressures, and through the fixed calipers the split and the total;
#   * the sim's .ibt carries the four brakeLinePress channels.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 66), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
function axle(bias_p)
    DriveRT3D.set_chassis!(DriveRT3D.Chassis(; bias_p, bias = DriveRT3D.bias_torque(100bias_p)))
    c = DriveRT3D.build_car3d(; v0 = 30.0)
    c.s_brk(c.integ, 1.0)
    p = DriveRT3D.brakepress3d(c); T = ModelingToolkit.getsym(c.sys, [c.sys.brk.TF, c.sys.brk.TR])(c.integ)
    p, T
end
(p0, T0) = axle(0.535); (p1, T1) = axle(0.54); (p2, T2) = axle(0.58)
DriveRT3D.set_chassis!(DriveRT3D.Chassis())
chk("53.5 %: front line 65.4 bar at full pedal (gold 65.4)", isapprox(p0[1], 65.4; atol = 0.05), "$(round(p0[1], digits = 2)) / $(round(p0[2], digits = 2)) bar")
chk("54 %: front line 66.0 bar at full pedal (gold 66.0)", isapprox(p1[1], 66.0; atol = 0.05), "$(round(p1[1], digits = 2)) / $(round(p1[2], digits = 2)) bar")
chk("53.5 %: axle torques are the BRAKE-2 fit (2956 N·m, 0.585 front)", isapprox(T0[1] + T0[2], 2956.0; atol = 0.01) &&
    isapprox(T0[1]/(T0[1] + T0[2]), 0.585; atol = 1e-6), "$(round(T0[1], digits = 1)) + $(round(T0[2], digits = 1)) N·m")
chk("58 %: more front torque, total moves with the calipers", T2[1]/(T2[1]+T2[2]) > T0[1]/(T0[1]+T0[2]) + 0.04 && T2[1] + T2[2] > T0[1] + T0[2],
    "split $(round(T2[1]/(T2[1]+T2[2]), digits = 3)), total $(round(T2[1] + T2[2], digits = 1)) N·m")
src = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
chk("the sim's .ibt writes LF/RF/LR/RR brakeLinePress", all(occursin("row[\"$(w)brakeLinePress\"]", src) for w in ("LF", "RF", "LR", "RR")))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
