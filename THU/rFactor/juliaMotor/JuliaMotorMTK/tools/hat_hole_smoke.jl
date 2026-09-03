# E106-S13 gate: the OFF-MESH SENTINEL MUST NOT REACH THE PHYSICS.
#
# E104(b) established the contract that "off the terrain mesh" reaches drive_rt3d as NaN
# ("unknown"), and offroad_smoke gates the physics side of it. But the PLAYER's groundz closure
# still returned the -999 SENTINEL and was wired straight into step_car3d!. drive_rt3d guards only
# `isfinite`, and -999 is finite -- so a wheel sampling a hole in the mesh was told the ground lay
# 999 m below. The car sank toward it and the correction on re-acquiring real terrain launched it.
# The PO hit exactly this at the Nurburgring: measured on the replay, the car sank 1.4 m, rose 7 m
# over 0.8 s above ground that is FLAT at 620.1-620.4, then fell 6.65 m in one frame.
#
# offroad_smoke proves the PHYSICS handles NaN. This gate proves the APP actually sends it -- the
# half that was missing, and the half that let the bug ship.
const SRC0 = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)

fails = 0

# 1. every physics CALL SITE must be handed the CONVERTING closure, never the raw one.
#    (`respawnX!(c; groundz=nothing) = ... respawn3d!(c; groundz=groundz)` is a wrapper forwarding
#     its OWN keyword -- correct, and not a call site, so it is excluded by name.)
lines = split(SRC0, "\n")
raw = [l for l in lines if occursin(r"groundz\s*=\s*groundz\s*\)", l) &&
                           !occursin("respawnX!(c; groundz=nothing)", l)]
if isempty(raw)
    println("  every physics call uses the converting closure       PASS")
else
    println("  every physics call uses the converting closure       FAIL  (", length(raw), " raw site(s))")
    fails += 1
end

# 2. the converting closure must exist and map the sentinel to NaN.
if occursin(r"groundz_phys\(x,y\)\s*=\s*\(g\s*=\s*groundz\(x,y\);\s*g\s*>\s*-900f0\s*\?\s*g\s*:\s*NaN32\)", SRC0)
    println("  the boundary closure maps the sentinel to NaN        PASS")
else
    println("  the boundary closure maps the sentinel to NaN        FAIL")
    fails += 1
end

# 3. the conversion itself, exercised rather than asserted by eye.
gp(g) = g > -900f0 ? g : NaN32
if isnan(gp(-999f0)) && gp(620.2f0) == 620.2f0 && !isnan(gp(0f0))
    println("  sentinel -> NaN, real heights pass through unchanged PASS")
else
    println("  sentinel -> NaN, real heights pass through unchanged FAIL")
    fails += 1
end

if fails > 0
    println("\n  HAT-HOLE GATE: FAIL (", fails, ")")
    exit(1)
end
println("\n  HAT-HOLE GATE: PASS ✓")
