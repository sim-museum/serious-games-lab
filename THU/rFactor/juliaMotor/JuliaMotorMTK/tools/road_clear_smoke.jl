# GATE: ROAD-1 -- Spa and the Ring drivable all the way through: NO solid reachable from the road.
#
# PO 2026-09-06: "spa and the ring drivable all the way through - no collisions so long as you
# stay on the road." This runs the sim's own census (JM_ROADSWEEP, drive_native_mtk.jl): every
# centreline station, every 0.5 m of lateral that the sim's TrackSurface calls on_track, tested
# against every solid with the sim's own contact model (solid_gap: disc or oriented box, in the
# loader's frame). The gate PASSES only when both tracks report zero solids reachable from the
# road AND the census's own control (a probe at a solid's centre reads as a hit) is "ok" -- a
# blind instrument reporting zero must fail here, not pass.
#
# Slow (two full sim loads, ~4-8 min each); memory ~4 GB per run. JM_ROAD_TRACKS overrides the
# track list (comma-separated) for a quick single-track check.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
tracks = split(get(ENV, "JM_ROAD_TRACKS", "spa,nurburg"), ",")
fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)
for t in tracks
    println("ROAD-1 census: ", t)
    cmd = `env TRACK=$t JM_ROADSWEEP=2 JM_HEADLESS=1 julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`
    out = try read(pipeline(cmd; stderr = devnull), String) catch e; sprint(showerror, e) end
    m = match(r"ROADSWEEP_RESULT track=(\S+) solids_on_road=(\d+) control=(\w+)", out)
    if m === nothing
        chk("$t: census ran to its result line", false, "no ROADSWEEP_RESULT (load failed?)"); continue
    end
    n = parse(Int, m.captures[2]); ctrl = m.captures[3]
    chk("$t: control probe at a solid centre is a hit", ctrl == "ok", "control=$ctrl")
    chk("$t: zero solids reachable from the road", n == 0, "solids_on_road=$n")
    n == 0 || for l in split(out, '\n'); occursin("hits=", l) && println("      ", strip(l)); end
end
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
