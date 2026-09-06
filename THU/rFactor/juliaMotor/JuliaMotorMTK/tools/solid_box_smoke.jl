# SOLID-BOX gate: oriented-box collision geometry for buildings (pure), and the sim wiring.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "solid_geom.jl")); using .SolidGeom
using Printf
fails = 0
pass(ok, msg, val) = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(msg, 54), val); ok || (global fails += 1))
≈(a, b; tol = 1e-9) = abs(a - b) <= tol
# an axis-aligned 10 x 4 box at the origin
g, nx, nz = box_gap(8.0, 0.0, 0.0, 0.0, 5.0, 2.0, 0.0);  pass(g ≈ 3.0 && nx ≈ 1.0 && nz ≈ 0.0, "outside the long face: gap 3, normal +x", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
g, nx, nz = box_gap(0.0, -5.0, 0.0, 0.0, 5.0, 2.0, 0.0); pass(g ≈ 3.0 && nx ≈ 0.0 && nz ≈ -1.0, "outside the short face: gap 3, normal -z", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
g, nx, nz = box_gap(8.0, 6.0, 0.0, 0.0, 5.0, 2.0, 0.0);  pass(g ≈ 5.0 && nx ≈ 0.6 && nz ≈ 0.8, "outside a corner: Euclidean gap 5, diagonal normal", @sprintf("%.2f (%.2f,%.2f)", g, nx, nz))
g, nx, nz = box_gap(4.5, 0.0, 0.0, 0.0, 5.0, 2.0, 0.0);  pass(g ≈ -0.5 && nx ≈ 1.0, "inside near the +x face: gap -0.5, pushes +x", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
g, nx, nz = box_gap(0.0, 1.5, 0.0, 0.0, 5.0, 2.0, 0.0);  pass(g ≈ -0.5 && nz ≈ 1.0, "inside near the +z face: gap -0.5, pushes +z", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
# the same box rotated 90°: the long axis now lies along z
g, nx, nz = box_gap(0.0, 8.0, 0.0, 0.0, 5.0, 2.0, pi/2); pass(g ≈ 3.0 && abs(nx) < 1e-9 && nz ≈ 1.0, "rotated 90°: long face now faces +z", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
g, nx, nz = box_gap(5.0, 0.0, 0.0, 0.0, 5.0, 2.0, pi/2); pass(g ≈ 3.0 && nx ≈ 1.0, "rotated 90°: short face at 2 m along x", @sprintf("%.2f (%.1f,%.1f)", g, nx, nz))
# a disc is a box's limit: disc gap sanity
g, nx, nz = disc_gap(8.0, 0.0, 0.0, 0.0, 5.0); pass(g ≈ 3.0 && nx ≈ 1.0, "disc gap 3 at 8 m from a 5 m disc", @sprintf("%.2f", g))
# the DEFECT this replaces, measured: a 5 m disc vs house28's 11.7 x 8.8 footprint
hx, hz = 11.7/2, 8.8/2
gb, _, _ = box_gap(0.0, 5.0, 0.0, 0.0, hx, hz, 0.0); gd, _, _ = disc_gap(0.0, 5.0, 0.0, 0.0, 5.0)
pass(gb ≈ 0.6 && gd ≈ 0.0, "house28 short side: disc touches 0.6 m before the wall (air-hit)", @sprintf("box %.1f disc %.1f", gb, gd))
gb, _, _ = box_gap(5.5, 0.0, 0.0, 0.0, hx, hz, 0.0); gd, _, _ = disc_gap(5.5, 0.0, 0.0, 0.0, 5.0)
pass(gb < 0 && gd > 0, "house28 long side: at 5.5 m the disc is clear, the box is hit", @sprintf("box %.1f disc %.1f", gb, gd))
# the sim wiring
SRC = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
pass(count(x -> true, eachmatch(r"solid_gap\((x|wx), (z|wz), k\)", SRC)) == 3, "all three SOLIDS consumers go through solid_gap", "source check")
pass(occursin("push!(SOLIDBOX, if r >= 5.0", SRC), "buildings get a mesh-footprint box", "source check")
println(fails == 0 ? "SOLID-BOX GATE: PASS" : "SOLID-BOX GATE: FAIL ($fails)")
exit(fails == 0 ? 0 : 1)
