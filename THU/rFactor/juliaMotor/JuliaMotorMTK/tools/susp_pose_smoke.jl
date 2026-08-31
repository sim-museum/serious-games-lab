# GATE: E82 -- the rear suspension must be drawn where the car is, not under the road.
#
# PO: "the car external view still has no axles". The parts exist and are correctly posed by GPL's
# positioners; the shipped corrective fold moved them 1.2-1.9 m below the road surface. This applies
# the SAME rsfix the sim applies (SuspPose, shared) to the extracted rear halves and asserts every
# vertex stays above the road and within the car's footprint.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(D, "render.jl")); using .Render
include(joinpath(D, "susp_pose.jl")); using .SuspPose
const LOT = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
isfile(LOT) || (println("lotus.3do not found"); exit(2))
fails = Ref(0)
check(name, ok, msg) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 54), msg))
println("E82 rear-suspension pose gate   (JM_RS_ROLL = ", SuspPose.RS_ROLL_DEG, ")")
for (grp, side) in ((27288, 1), (39792, -1))
    parts = Render.extract_gpl_car(LOT; include_groups=(grp,), exclude=("ltraymap","lshad"))
    M = SuspPose.rsfix(side, Render.translate, Render.rotx, Render.scalexyz)
    ymin = Inf; ymax = -Inf; zmax = 0.0; n = 0
    for p in parts, i in 1:11:length(p.verts)-10
        v = Float32[p.verts[i], p.verts[i+1], p.verts[i+2], 1f0]; w = M * v
        ymin = min(ymin, w[2]); ymax = max(ymax, w[2]); zmax = max(zmax, abs(w[3])); n += 1
    end
    println("  group $grp (side $side): $n verts after rsfix -> y ", round(ymin, digits=2), "..", round(ymax, digits=2), "  |z| max ", round(zmax, digits=2))
    check("group $grp stays above the road (y > -0.35)", ymin > -0.35, string("lowest vertex y=", round(ymin, digits=2)))
    check("group $grp stays within the car's width (|z| < 1.2)", zmax < 1.2, string(round(zmax, digits=2)))
end
println(fails[] == 0 ? "SUSP POSE GATE: PASS" : "SUSP POSE GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
