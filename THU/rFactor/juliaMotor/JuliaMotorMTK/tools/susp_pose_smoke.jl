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
# E82-S2: extract exactly as the sim does -- clipped at the wheel face (0.85). Without the clip these
# assemblies reach |z| = 1.12-1.16, spearing through the rear tyres: the PO's "chrome spider-legs".
const RSUSP_MAXLAT = parse(Float32, get(ENV, "JM_RSUSP_MAXLAT", "0.85"))
# E82-S3: the gate MUST extract the way the sim does. It did not: it called extract_gpl_car without
# `trim`, so after the sim started trimming, the gate went on measuring the DROP behaviour and kept
# printing the old |z| max 0.61 -- a green gate reporting a number the shipped build no longer
# produces. Mirror the sim's JM_SUSP_TRIM default here.
const TRIM = get(ENV,"JM_SUSP_TRIM","1") != "0"
fails = Ref(0)
check(name, ok, msg) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 54), msg))
println("E82 rear-suspension pose gate   (JM_RS_ROLL = ", SuspPose.RS_ROLL_DEG, ", maxlat = ", RSUSP_MAXLAT, ")")
# The FRONT carries the same defect: 4 of its 98 triangles are 1.3 m strips reaching x=2.73 (past the
# nose) at z=+-1.12. Assert the clipped front stays inside the car too.
let fp = Render.extract_gpl_car(LOT; only=("lsusp1","frontlot"), maxlat=parse(Float32, get(ENV,"JM_FSUSP_MAXLAT","0.85")), maxedge=1.5f0)   # front DROPS (no trim) -- see drive_native_mtk.jl
    xmax = -Inf; zmax = 0.0
    for p in fp, i in 1:11:length(p.verts)-10
        xmax = max(xmax, p.verts[i]); zmax = max(zmax, abs(p.verts[i+2]))
    end
    println("  front assembly: x max ", round(xmax, digits=2), "  |z| max ", round(zmax, digits=2))
    check("front stays behind the nose (x < 2.0)", xmax < 2.0, string(round(xmax, digits=2)))
    check("front stays inside the tyres (|z| < 0.95)", zmax < 0.95, string(round(zmax, digits=2)))
end
for (grp, side) in ((27288, 1), (39792, -1))
    parts = Render.extract_gpl_car(LOT; include_groups=(grp,), exclude=("ltraymap","lshad"), maxlat=RSUSP_MAXLAT, trim=TRIM)
    M = SuspPose.rsfix(side, Render.translate, Render.rotx, Render.scalexyz)
    ymin = Inf; ymax = -Inf; zmax = 0.0; n = 0
    for p in parts, i in 1:11:length(p.verts)-10
        v = Float32[p.verts[i], p.verts[i+1], p.verts[i+2], 1f0]; w = M * v
        ymin = min(ymin, w[2]); ymax = max(ymax, w[2]); zmax = max(zmax, abs(w[3])); n += 1
    end
    println("  group $grp (side $side): $n verts after rsfix -> y ", round(ymin, digits=2), "..", round(ymax, digits=2), "  |z| max ", round(zmax, digits=2))
    check("group $grp stays above the road (y > -0.35)", ymin > -0.35, string("lowest vertex y=", round(ymin, digits=2)))
    # The wheel FACE is 0.85 (CARP_MAXLAT). Geometry beyond it is inside/through the tyre, which is
    # what the PO photographed. 0.95 leaves a little room for the tyre's own width, and still fails
    # hard on the 1.12-1.16 overhang.
    check("group $grp stays inside the tyres (|z| < 0.95)", zmax < 0.95, string(round(zmax, digits=2)))
    # E82-S3: and it must REACH. Dropping whole triangles left the driveshafts ending at 0.61,
    # short of the hub at 0.772 -- stubs where gold shows shafts running to the wheel. That was
    # invisible to a gate that only checked an upper bound, so check the lower one too.
    # Deliberately NOT guarded on TRIM. Guarding it made JM_SUSP_TRIM=0 -- the knob that puts the
    # stubs back -- report PASS, i.e. the gate went green on the defect it exists to catch. The
    # check states the requirement (the shafts reach the hub); the knob is then a real negative
    # control that goes red, which is the only kind worth having.
    check("group $grp reaches the hub (|z| >= 0.772)", zmax >= 0.772, string(round(zmax, digits=3)))
end
println(fails[] == 0 ? "SUSP POSE GATE: PASS" : "SUSP POSE GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
