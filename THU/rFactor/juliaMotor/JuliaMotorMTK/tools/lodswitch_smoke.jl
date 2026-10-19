# GATE: MONZAGROUND-1 S3 -- GPL's lap-position switches (0x11, source 1) pick what GPL draws near the object.
#
# PO 2026-10-18: "Holes in the ground surface to right and left of track between start/finish line and curva grande at
# Monza -- looks like I am driving on a suspended ribbon of track". GPL's 0x11 node is a SWITCH (gpl.exe 0x4cf9b0): a
# value (source +4: 1 = the camera's lap position in TRK units, 1/500 inch), a compare op (+12: 1 <=, 2 >=, 3 ==) and the
# FIRST entry that holds is drawn. The parser always took the minimum-threshold child, so Monza's trees72 (4e7 stub |
# 0 geometry | -6000 stub, op >=) lost its armco, grass, wire fence and tree row at s 442 -- the open right-hand side.
# Now the richest child any camera within GPL's 914 m lap range gets.
#
# Parser-only gate (no display): monza.dat objects parsed at their own lap positions; JM_LOD_LAPPOS=0 is the control.
include(normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "gpl3do.jl")))
include(normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "gpldat.jl")))
using .GPL3DO, .GPLDat
const TRK = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 62), d))
println("LODSWITCH gate: GPL lap-position switches")

findci(dir, name) = (f = filter(x -> lowercase(x) == lowercase(name), readdir(dir)); isempty(f) ? "" : joinpath(dir, f[1]))
const TMP = mktempdir()
function parse_obj(dat, nm; s = NaN, lap = NaN)
    fn = joinpath(TMP, nm * ".3do"); write(fn, dat[nm * ".3do"])
    redirect_stdout(devnull) do
        GPL3DO.parse_3do(fn; lappos = s*500/0.0254, laplen = lap*500/0.0254)
    end
end
monza = GPLDat.parse_dat(findci(joinpath(TRK, "monza"), "monza.dat"))
m = parse_obj(monza, "trees72"; s = 442.0, lap = 5759.0)
check("trees72 @ s 442: the roadside geometry is drawn", length(m.tris) >= 28, "$(length(m.tris)) tris")
check("trees72: armco, grass and wire fence among its textures", all(t -> t in m.textures, ("armco_s", "grass", "wiref_s")), "$(m.textures)")
m = parse_obj(monza, "trees71"; s = 350.0, lap = 5759.0)
check("trees71 @ s 350: its grass and fence are drawn", "grass" in m.textures && "wiref_s" in m.textures, "$(m.textures)")
# the window never takes away what the static pick drew (Monza objects at their own lap positions)
for (nm, s) in (("trees40", 3951.0), ("trees48", 4977.0), ("front06", 5514.0), ("tunmid", 3311.0), ("treelod", 907.0))
    a = length(parse_obj(monza, nm).tris); b = length(parse_obj(monza, nm; s, lap = 5759.0).tris)
    check("$(nm) @ s $(round(Int, s)): no loss against the static pick", b >= a, "$(a) -> $(b) tris")
end
ring = GPLDat.parse_dat(findci(joinpath(TRK, "nurburg"), "nurburg.dat"))
for (nm, s, n) in (("ogrnd2", 467.0, 156), ("tower2", 1496.0, 22), ("wehr-l4", 8872.0, 82))
    b = length(parse_obj(ring, nm; s, lap = 22810.0).tris)
    check("Ring $(nm) @ s $(round(Int, s)): unchanged", b == n, "$(b) tris (want $(n))")
end
ENV["JM_LOD_LAPPOS"] = "0"
m = parse_obj(monza, "trees72"; s = 442.0, lap = 5759.0)
check("control (JM_LOD_LAPPOS=0): the old pick loses trees72", isempty(m.tris), "$(length(m.tris)) tris")
delete!(ENV, "JM_LOD_LAPPOS")
println(fails[] == 0 ? "LODSWITCH: PASS" : "LODSWITCH: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
