# GATE: a respawn must not credit lap progress.
#
#   PO 2026-09-04 (Watkins Glen): "my first lap was listed at 1.19 seconds, maybe because I hit r
#   to get back on the road at one point(?) ... no indication that race is over".
#
# WHY THIS EXISTS. Lap counting accumulates arc-length along the centreline and unwraps the step,
# on the assumption that every frame is a small FORWARD move. R (respawn at the start) and SHIFT+R
# (recover) TELEPORT the car BACKWARD. From past half-distance the backward jump is more negative
# than -total/2, so the unwrap adds a whole lap to it and it emerges as a large FORWARD step --
# up to 40% of a lap credited in ONE FRAME. That banks a near-instant lap (the PO's 1.19 s) and
# corrupts the lap COUNT, which feeds `cs.laps >= RACE_LAPS`: the race-over announcement and the
# replay written at exit both hang off that number.
#
# The rule lives in `prog_delta` so this gate can drive the REAL function, loaded out of the sim
# source. A gate that restates the rule tests its own copy (S371).
#
# Headless: pure arithmetic.

const SRC = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"))
src = read(SRC, String)
i = findfirst("function prog_delta(", src)
i === nothing && error("prog_delta not found in $SRC -- has the teleport guard been removed?")
j = findnext("end\n", src, last(i))
eval(Meta.parse(src[first(i):last(j)]))

const L = 4000.0            # lap length, m
fails = Ref(0)
check(name, cond, msg) = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 50), msg))

println("Lap-progress teleport gate (PO: 1.19 s lap after pressing R)")

# Normal driving still accumulates.
check("normal forward step accumulates", prog_delta(1010.0, 1000.0, L) ≈ 10.0,
      "$(round(prog_delta(1010.0, 1000.0, L), digits=2)) m")
# A genuine finish-line wrap still counts.
check("finish-line wrap still counts", prog_delta(5.0, L-5.0, L) ≈ 10.0,
      "$(round(prog_delta(5.0, L-5.0, L), digits=2)) m")

# THE BUG: respawn from the last part of a lap back to the start line.
# The exact window matters and is worth stating: for a respawn from fraction f of a lap the unwrap
# yields (1-f)*L, which the 0.4*L jump guard ACCEPTS when f > 0.6. So the last 40% of a lap is the
# danger zone, and f = 0.6 itself sits exactly on the boundary and is rejected -- picking that as
# the control was my own error, and it made the control look like it could not reproduce the bug.
back = prog_delta(0.0, 0.70*L, L; teleport = true)
check("respawn credits NOTHING", back == 0.0, "$(round(back, digits=1)) m")

# NEGATIVE CONTROL: the same jump WITHOUT the teleport flag is what the code used to do. It must
# come out as a large FORWARD credit, or the defect can no longer occur and this gate proves nothing.
bug = prog_delta(0.0, 0.70*L, L)
check("control: untagged, the same jump credits a FORWARD step", bug > 0.25*L,
      "+$(round(bug, digits=1)) m of a $(round(Int,L)) m lap -- $(round(100*bug/L, digits=0))% of a lap in one frame")
check("control: that is enough to bank a phantom lap", bug > 0.0,
      "accumulating this repeatedly crosses the next integer lap")

println()
println(fails[] == 0 ? "  LAP-PROGRESS GATE: PASS ✓" : "  LAP-PROGRESS GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
