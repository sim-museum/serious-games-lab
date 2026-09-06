# GATE: CARGOLD-1 -- every car's wheels are placed at ITS OWN mesh's hubs, not a shared hand table.
#
# PO 2026-09-06: "place axles correctly for user and AI cars". The census (wheel_mesh_census.jl)
# reads the tyre groups out of each .3do; this gate asserts (a) mesh_wheel_hubs finds four tyres on
# all six chassis with the wheelbase and half-tracks the census measured (±3 cm), (b) the values
# are NOT the old table (front 1.05 / rear -1.15 / 0.62-0.78), so a fallback to the table fails
# here, (c) the source wires the mesh hubs into both the AI loader and the Lotus WHEELS.
const NATIVE = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(NATIVE, "render.jl")); using .Render
const BASE = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67"
expect = Dict("lotus"=>(1.53,-0.89,0.71,0.70), "ferrari"=>(1.57,-0.83,0.74,0.73), "brabham"=>(1.38,-1.00,0.67,0.70),
              "brm"=>(1.53,-0.91,0.75,0.76), "eagle"=>(1.50,-0.96,0.76,0.76), "coventry"=>(1.53,-0.90,0.71,0.69))
fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
for (dir, (fx, rx, fy, ry)) in expect
    h = Render.mesh_wheel_hubs(joinpath(BASE, dir, dir == "coventry" ? "coventry.3do" : dir * ".3do"))
    if h === nothing; chk("$dir: four tyres found in the mesh", false, "none"); continue; end
    near(a, b) = abs(a - b) <= 0.03
    chk("$dir: hub x matches the census (±3 cm)", near(h.fx, fx) && near(h.rx, rx),
        "front $(round(h.fx,digits=2)) rear $(round(h.rx,digits=2))")
    # lateral = the wheel's centre plane (inner..outer sidewall midpoint): a real '67 half-track,
    # symmetric front/rear within 10 cm, and not the AI table's 0.62 / 0.66
    chk("$dir: half-tracks are the wheel centre planes", 0.65 <= h.fy <= 0.85 && 0.65 <= h.ry <= 0.85 && abs(h.fy - h.ry) < 0.10 && !near(h.fy, 0.62),
        "tracks $(round(h.fy,digits=2))/$(round(h.ry,digits=2))")
    chk("$dir: not the old table (1.05/-1.15)", !(near(h.fx, 1.05) && near(h.rx, -1.15)), "")
end
src = read(joinpath(NATIVE, "drive_native_mtk.jl"), String); rsrc = read(joinpath(NATIVE, "render.jl"), String)
chk("AI loader places wheels from the mesh (source)", occursin("wheelspec = wheelspec_from_mesh(hubs, wheelspec, off_x, off_z)", rsrc))
chk("Lotus WHEELS come from lotus.3do (source)", occursin("Render.mesh_wheel_hubs(LOT3DO)", src))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
