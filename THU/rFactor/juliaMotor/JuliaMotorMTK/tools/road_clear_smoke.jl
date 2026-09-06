# GATE: ROAD-1 -- Spa and the Ring drivable all the way through: NO object standing on the road.
#
# PO 2026-09-06: "spa and the ring drivable all the way through - no collisions so long as you
# stay on the road." Two censuses, both the sim's own (drive_native_mtk.jl hooks that exit before
# the window):
#   SPA   JM_ROADSWEEP=2  every centreline station x every 0.5 m of lateral where the point AND the
#         car's two flanks are over road-textured tarmac inside the 9 m corridor, tested against
#         every solid with the sim's contact model (solid_gap). PASS = `inside=0`: no solid holds
#         the car's centre point (thin edge barriers and the 1.4 m brush zone are reported, not
#         counted -- scraping the armco at the road edge is GPL, an object across the road is not).
#         The census's own control (a probe at a solid's centre reads as a hit) must be "ok".
#   RING  the Ring places no object solids at all (its buildings are track mesh), so its collision
#         census is the terrain sweep JM_SWEEP=4: PASS = 0 anomaly points (no HAT hole, wall/cliff,
#         false grass or on-road mesh over 22.8 km).
# Slow (two sim loads, ~5-10 min each, ~4 GB). JM_ROAD_TRACKS=spa for a single-track check.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
tracks = split(get(ENV, "JM_ROAD_TRACKS", "spa,nurburgring"), ",")
fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 60), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)
runsim(env) = (cmd = `env $(env) julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`;
               try read(pipeline(cmd; stderr = devnull), String) catch e; sprint(showerror, e) end)
for t in tracks
    println("ROAD-1 census: ", t)
    if t == "nurburgring"
        out = runsim(["TRACK=$t", "JM_SWEEP=4"])
        m = match(r"(\d+) anomaly point\(s\), (\d+) clean", out)
        m === nothing && (chk("$t: terrain sweep ran to its result line", false, "no anomaly line (load failed?)"); continue)
        chk("$t: terrain sweep covers the lap", parse(Int, m.captures[2]) > 5000, "$(m.captures[2]) clean points")
        chk("$t: zero terrain anomalies on the road", m.captures[1] == "0", "$(m.captures[1]) anomaly point(s)")
        m.captures[1] == "0" || for l in split(out, '\n'); startswith(l, "  s=") && println("      ", strip(l)); end
    else
        out = runsim(["TRACK=$t", "JM_ROADSWEEP=2"])
        m = match(r"ROADSWEEP_RESULT track=(\S+) solids_on_road=(\d+) inside=(\d+) edge_barriers=(\d+) verge_only=(\d+) tarmac_pred=(\w+) control=(\w+)", out)
        m === nothing && (chk("$t: census ran to its result line", false, "no ROADSWEEP_RESULT (load failed?)"); continue)
        chk("$t: control probe at a solid centre is a hit", m.captures[7] == "ok", "control=$(m.captures[7])")
        chk("$t: tarmac predicate is the road-only HAT", m.captures[6] == "roadhat", "tarmac_pred=$(m.captures[6])")
        chk("$t: zero objects standing on the road", m.captures[3] == "0",
            "inside=$(m.captures[3])  (brush zone $(m.captures[2]), edge barriers $(m.captures[4]), verge $(m.captures[5]))")
        m.captures[3] == "0" || for l in split(out, '\n'); occursin("hits=", l) && occursin("worst gap= -", l) && println("      ", strip(l)); end
    end
end
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
