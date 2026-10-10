# CARPHYS-1 S7: the shock travel limits (TravelStops, chassis_parts.jl) from the setup's ShockDeflection and Packer.
#   * the 261004 default's 61.8 of 104.6 mm (front) and 58.1 of 113.0 (rear) give wheel travel +55/−79 and +85/−90 mm;
#   * the setup parser reads ShockDeflection (static, max) and Packer per corner;
#   * a wheel in the air hangs near full droop instead of falling away (before S7: 150–210 mm over Flugplatz);
#   * parked, the stops carry nothing: the static state is the same as without them.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 66), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
tr = DriveRT3D.travel_from_setup(DriveRT3D.TRAVEL_REF...)
chk("261004 default: front +55/−79 mm, rear +85/−90 mm", isapprox(1000tr[1][1], 54.9; atol = 0.2) && isapprox(1000tr[1][2], -79.2; atol = 0.2) &&
    isapprox(1000tr[3][1], 84.7; atol = 0.2) && isapprox(1000tr[3][2], -89.7; atol = 0.2), join((string(round(Int, 1000t[1]), "/", round(Int, 1000t[2])) for t in tr), " "))
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
const DEF = joinpath(expanduser("~/gold standard/julia racer"), "261004", "lotus49_skidpad 2026-10-04 14-36-48.ibt")
if isfile(DEF)
    sp = setup_params(ibt_open(DEF).yaml)
    chk("the gold setup's ShockDeflection (static, max) and Packer are read", sp.shock_defl_mm[:LF] == (61.8, 104.6) &&
        sp.shock_defl_mm[:RR] == (59.2, 113.0) && sp.packer_mm[:LF] == 0.0, "LF $(sp.shock_defl_mm[:LF]), packer $(sp.packer_mm[:LF])")
    ch = DriveRT3D.chassis_from_setup(sp; source = "261004")
    chk("the session chassis carries that travel", ch.travel !== nothing && all(isapprox.(ch.travel[1], tr[1]; atol = 1e-9)))
else
    println("  (no gold setup here: parser check skipped)")
end
function parked(travel; drop = 0.0)
    DriveRT3D.set_chassis!(DriveRT3D.Chassis(; travel))
    c = DriveRT3D.build_car3d(; v0 = 0.0)
    for k in 1:180; DriveRT3D.step_car3d!(c, 0.0, 0.0, 0.0, 1/60); end
    if drop != 0                                   # the road falls away under the left front: that wheel hangs
        c.s_zr[1](c.integ, drop); for _ in 1:600; DriveRT3D.OrdinaryDiffEq.step!(c.integ, 1/300, true); end
    end
    ModelingToolkit.getsym(c.sys, [c.sys.sFL.c, c.sys.sRL.c])(c.integ)
end
a = parked(nothing); b = parked(tr)
chk("parked: the stops carry nothing (same static compression)", isapprox(a, b; atol = 1e-9), "F $(round(1000b[1], digits = 2)) R $(round(1000b[2], digits = 2)) mm")
h0 = parked(nothing; drop = -0.4); h1 = parked(tr; drop = -0.4)
chk("road 0.4 m away: without stops the wheel falls away", h0[1] < -0.2, "$(round(1000h0[1])) mm")
chk("with stops it hangs within 25 mm of full droop (−79 mm)", -0.104 < h1[1] < -0.07, "$(round(1000h1[1])) mm")
DriveRT3D.set_chassis!(DriveRT3D.Chassis())
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
