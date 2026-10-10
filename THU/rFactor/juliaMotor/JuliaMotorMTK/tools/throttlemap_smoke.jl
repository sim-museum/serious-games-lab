# CARPHYS-1 S8: the measured, progressive part-throttle map (powertrain.jl THROTTLE_KNOTS, tools/throttlefit_261009.py).
#   * closed and wide open are unchanged (the WOT pulls and coasts longval_261002 validates stay exact);
#   * 30 % pedal gives 21 % of the way from engine drag to WOT, 10 % gives 2 % (iRacing's Lotus 49), not the linear 30/10;
#   * the map rises monotonically, so more pedal is always more torque.
# CARPHYS-1 S9, the clutch (powertrain.jl CLUTCH_KNOTS, tools/clutchfit_261009.py): a bite point near 0.15 engagement,
# 71 / 202 / 407 N·m at 0.25 / 0.45 / 0.65 (the gold's standing starts), rising monotonically, above the engine's peak
# torque when fully in; the vehicle's clutch is the Clutch object.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 66), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
f = DriveRT3D.throttle_map
chk("closed and WOT unchanged: f(0) = 0, f(1) = 1", f(0.0) == 0.0 && isapprox(f(1.0), 1.0; atol = 1e-12))
chk("progressive: f(0.3) = 0.21, f(0.1) = 0.02 (gold), not linear", isapprox(f(0.3), 0.21; atol = 1e-9) && isapprox(f(0.1), 0.02; atol = 1e-9))
chk("ahead of linear near the top: f(0.8) = 0.84", isapprox(f(0.8), 0.84; atol = 1e-9))
xs = 0:0.01:1; chk("monotonic", all(diff([f(x) for x in xs]) .> 0))
r = 6000.0
chk("engine torque at WOT and closed is the measured curve / drag", isapprox(DriveRT3D.engine_torque(r, 1.0), DriveRT3D.wot_torque(r)*0.5*(1 - tanh((r - 9500)/200)); rtol = 1e-12) &&
    DriveRT3D.engine_torque(r, 0.0) < 0, "WOT $(round(DriveRT3D.engine_torque(r, 1.0), digits = 1)), closed $(round(DriveRT3D.engine_torque(r, 0.0), digits = 1)) N·m")
cc = DriveRT3D.clutch_capacity
chk("clutch: bite point (≤ 15 N·m up to 0.15 engagement)", cc(0.1) < 10 && cc(0.15) <= 15, "$(round(cc(0.1), digits = 1)) / $(round(cc(0.15), digits = 1)) N·m")
chk("clutch: the gold's 71 / 202 / 407 N·m at 0.25 / 0.45 / 0.65", isapprox(cc(0.25), 71; atol = 1e-6) && isapprox(cc(0.45), 202; atol = 1e-6) && isapprox(cc(0.65), 407; atol = 1e-6))
chk("clutch: monotonic, holds more than the engine's 312 N·m when fully in", all(diff([cc(x) for x in 0.0:0.01:1.0]) .> 0) && cc(1.0) > 2*312, "$(cc(1.0)) N·m")
src = read(joinpath(@__DIR__, "..", "src", "components", "vehicle_3d.jl"), String)
chk("the vehicle's clutch is the Clutch object", occursin("clu = Clutch(; name = :clu)", src) && occursin("Tcl   = clu.T", src))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
