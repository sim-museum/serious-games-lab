# CARPHYS-1 S5: the steering column object and the force feedback it drives.
#   * SteeringColumn (chassis_parts.jl) is in the car: in a steady LEFT turn the rim torque is the front axle force on
#     the fitted 4.78 cm trail through the 10:1 rack, and it turns the rim back to centre (negative = to the right);
#   * at ~0.7 g it is in iRacing's range (the gold's SteeringWheelTorque runs about ±17 N·m at the 1st/99th percentile);
#   * the sim's FFB road term reads that torque by default, with the 15 ms smoothing the lag-free gold calls for;
#     JM_FFB_LEGACY keeps the old hand-trail model for A/B.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 66), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
c = DriveRT3D.build_car3d(; v0 = 25.0)
for _ in 1:300; DriveRT3D.step_car3d!(c, 0.40, 0.0, 0.08, 1/60); end
t = DriveRT3D.tyregrip3d(c); fy = (t[1][2] + t[2][2])*617*9.80665/4; τ = DriveRT3D.rimtorque3d(c); ay = DriveRT3D.telemetry3d(c).ay/9.80665
chk("left turn (control)", ay > 0.5, "ay $(round(ay, digits = 2)) g")
chk("rim torque = -ΣFy_front × 0.0478 m / 10", τ !== nothing && isapprox(τ, -0.0478*fy/10; rtol = 1e-6), "τ $(round(τ, digits = 2)) N·m, ΣFy $(round(fy)) N")
chk("it self-centres (opposes the turn)", τ < 0)
chk("magnitude at ~0.7 g within iRacing's range (5..17 N·m)", 5 <= abs(τ) <= 17, "$(round(abs(τ), digits = 1)) N·m at $(round(ay, digits = 2)) g")
src = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
chk("the FFB road term reads the column's torque by default", occursin("τrim = (FFB_PHYS && CAR3D) ? DriveRT3D.rimtorque3d(cs) : nothing", src) &&
    occursin("const FFB_PHYS    = !haskey(ENV, \"JM_FFB_LEGACY\")", src))
chk("15 ms smoothing (the gold has no measurable lag), legacy keeps 50 ms",
    occursin("haskey(ENV, \"JM_FFB_LEGACY\") ? \"0.05\" : \"0.015\"", src) && occursin("FFB_PHYS ? \"0.015\" : \"0.05\"", src))
# IRGOLD-1 S5: a SESSION car (the game's -- setup, camber, relaxation) carries the trail law: mechanical 4.50 cm +
# pneumatic 1.55 cm × (1 − ξ) on the kinematic-slip front force (fitted on the 261011 Monza + skidpad rim torque)
include(joinpath(@__DIR__, "..", "src", "setup.jl")); include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using ModelingToolkit
let fn = expanduser("~/gold standard/julia racer/lotus49_nurburgring nordschleife 2026-06-24 15-53-11.ibt")
    if isfile(fn)
        sp = Setup.setup_params(IBT.ibt_open(fn).yaml)
        DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(fn))
        DriveRT3D.set_corner_weights!(sp.corner_weight_N; source = basename(fn))
        DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(sp; source = basename(fn)))
        cs = DriveRT3D.build_car3d(; v0 = 25.0)
        for _ in 1:300; DriveRT3D.step_car3d!(cs, 0.40, 0.0, 0.08, 1/60; clutch = 0.0, manual = true); end
        sy = cs.sys
        fyk, xi, τs = ModelingToolkit.getsym(sy, [sy.FL.Fyk + sy.FR.Fyk, 0.5*(sy.FL.ξk + sy.FR.ξk), sy.col.τ])(cs.integ)
        law = -(DriveRT3D.COLUMN_TRAIL[1] + DriveRT3D.COLUMN_TRAIL[2]*(1 - min(xi, 1.0)))*fyk/10
        chk("session car: τ = -(4.50 cm + 1.55 cm·(1-ξ))·ΣFyk / 10", isapprox(τs, law; rtol = 1e-6), "τ $(round(τs, digits = 2)) N·m, ξ $(round(xi, digits = 2))")
        chk("session car: heavier than the constant 4.78 cm at moderate slip", abs(τs) > 0.0478*abs(fyk)/10, "")
    else
        println("  (no June Ring template on this machine: session-car checks skipped)")
    end
end
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
