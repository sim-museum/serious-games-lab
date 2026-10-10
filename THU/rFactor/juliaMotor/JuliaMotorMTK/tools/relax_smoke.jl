# CARPHYS-1 S11: tyre relaxation (TyreRelaxation, chassis_parts.jl) -- σ·dα/ds = α_in − α, ds = V·dt.
#   * standalone: a 0.1 rad step in kinematic slip at 20 m/s reaches 1 − 1/e of it after rolling σ (0.4 m = 20 ms);
#   * in the car: a steering step at 30 m/s builds yaw rate later with a long σ than a short one (the lag is real);
#   * off by default (JM_RELAX unset): the car is built without it, the model of S10 and before.
haskey(ENV, "JM_RELAX") && delete!(ENV, "JM_RELAX")
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 70), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
chk("off by default", DriveRT3D.RELAX === nothing)
@named rx = DriveRT3D.TyreRelaxation(; σ = 0.4)
@named top = System([rx.α_in ~ 0.1, rx.V ~ 20.0], t; systems = [rx])
s = mtkcompile(top)
sol = solve(ODEProblem(s, [s.rx.α => 0.0], (0.0, 0.1)), Tsit5(); reltol = 1e-9, abstol = 1e-12)
a20 = sol(0.02; idxs = s.rx.α); a100 = sol(0.1; idxs = s.rx.α)
chk("standalone: 63.2 % of the step after rolling σ", isapprox(a20, 0.1*(1 - exp(-1)); rtol = 1e-4), "α(20 ms) $(round(a20, digits = 5))")
chk("standalone: settled after 5σ", isapprox(a100, 0.1; rtol = 1e-2), "α(100 ms) $(round(a100, digits = 5))")
ENV["JM_RELAX"] = "0.4,0.4"
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D   # rebuilt with relaxation on
chk("JM_RELAX=0.4,0.4 turns it on", DriveRT3D.RELAX == (0.4, 0.4))
car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u); sys = car.sys
function yaw50(σ)
    car.integ.u .= u0
    for x in (sys.rxFL.σ, sys.rxFR.σ, sys.rxRL.σ, sys.rxRR.σ); ModelingToolkit.setp(sys, x)(car.integ, σ); end
    for _ in 1:60; DriveRT3D.step_car3d!(car, 0.4, 0.0, 0.0, 1/60; clutch = 0.0, manual = true); end
    for _ in 1:3; DriveRT3D.step_car3d!(car, 0.4, 0.0, 0.15, 1/60; clutch = 0.0, manual = true); end
    rad2deg(ModelingToolkit.getsym(sys, sys.r)(car.integ))
end
y1 = yaw50(0.05); y2 = yaw50(2.0)
chk("car: steering step, yaw rate at 50 ms lower with σ 2 m than 0.05 m", y2 < 0.6*y1, "$(round(y1, digits = 2)) vs $(round(y2, digits = 2)) deg/s")
delete!(ENV, "JM_RELAX")
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
