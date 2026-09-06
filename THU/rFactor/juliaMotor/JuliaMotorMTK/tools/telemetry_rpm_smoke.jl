# GATE: RPM-1 -- the engine speed the gauge, the sound and the telemetry read must MOVE.
#
# PO 2026-09-06: "RPM gauge doesn't move at spa, missing entirely at the ring ... no sound of
# revving, no change in RPM digital readout ... If you stop, you can't get started again."
# Telemetry from that run: RPM = 1999.62 for all 13,161 samples while speed reached 50 m/s. Cause:
# LAPTIME-1 (e88250c, 2026-09-05) inserted a comment MID-LINE in drive_rt3d.jl's step and swallowed
# `c.rpm = clamp(a[6], ...)`, so every image since 09-05 evening shipped a frozen engine.
# Stated before the run: from rest, full throttle for 4 s (auto gearbox), the car's rpm must
# leave the 2000 floor (max - min > 1500) and end above 3000; speed must rise (the car drove
# before the fix too, so speed alone is NOT the assertion -- the frozen rpm still made torque).
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
c = DriveRT3D.build_car3d(x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0)
rpms = Float64[]; vs = Float64[]
for i in 1:1200
    DriveRT3D.step_car3d!(c, 1.0, 0.0, 0.0, 1/300)
    push!(rpms, c.rpm); push!(vs, c.v)
end
chk("rpm leaves the 2000 floor (max - min > 1500)", maximum(rpms) - minimum(rpms) > 1500, "min=$(round(minimum(rpms))) max=$(round(maximum(rpms)))")
chk("rpm ends above 3000 under full throttle", rpms[end] > 3000, "end=$(round(rpms[end]))")
chk("rpm is not the constant 2000 of the frozen build", count(r -> abs(r - 2000.0) > 1.0, rpms) > 600, "$(count(r -> abs(r - 2000.0) > 1.0, rpms)) of 1200 samples off 2000")
chk("speed rises (control: the car drives)", vs[end] > 5.0, "v=$(round(vs[end], digits=1)) m/s")
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
