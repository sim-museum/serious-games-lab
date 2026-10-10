# TRACKS-TD-1 S2 (PO 2026-10-07: "long openings in the ground just after Stavelot showing another view through the
# ground"): the track mesh has a draw range, as in GPL (which draws its track over a segment range and leaves the
# distance to the horizon panels). Text checks on the sim and the shader:
#   * TRACK_MAXD defaults below the fog's end (2800 m), so the cut sits in the haze;
#   * the range is set for the track-mesh loop only and reset after it (objects, cars, sky are not cut);
#   * the shader discards beyond it, and the per-frame uniforms default it off.
const D = joinpath(@__DIR__, "..", "..", "demo", "native")
src = read(joinpath(D, "drive_native_mtk.jl"), String); rnd = read(joinpath(D, "render.jl"), String)
fails = Ref(0)
chk(name, ok) = (println("  ", rpad(name, 70), ok ? "PASS" : "FAIL"); ok || (fails[] += 1); ok)
m = match(r"const TRACK_MAXD = parse\(Float32, get\(ENV, \"JM_TRACK_MAXD\", \"(\d+)\"\)\)", src)
fog = match(r"fognear=400f0, fogfar=(\d+)f0", src)
chk("TRACK_MAXD defaults inside the fog's end", m !== nothing && fog !== nothing && parse(Int, m[1]) < parse(Int, fog[1]))
i = findfirst("glUniform1f(Render.uloc(prog,\"uMaxDist\"), TRACK_MAXD)", src); j = findfirst("glUniform1f(Render.uloc(prog,\"uMaxDist\"), 0f0)", src)
k = i === nothing ? nothing : findnext("for (ti, it) in enumerate(trackItems)", src, last(i))   # (the shadow pass's loop comes first)
chk("set just before the track-mesh loop, reset after it", i !== nothing && j !== nothing && k !== nothing && first(i) < first(k) < first(j))
chk("the shader discards beyond it", occursin("if(uMaxDist > 0.0 && length(vWorld-uCamPos) > uMaxDist) discard;", rnd))
chk("the frame's uniforms default it off", occursin("glUniform1f(uloc(prog,\"uMaxDist\"),0f0)", rnd))
# WGTD-1 (f): the racing groove (a ~22 % alpha overlay) joins the coplanar-duplicate dedup -- doubled strips blended
# twice drew dark blocks -- with 20 cm keys, its doubles lying a few cm apart
chk("the groove is deduplicated like the rails (20 cm keys)", occursin("(GROOVE_DEDUP && startswith(lt,\"groove\"))", src) &&
    occursin("q = startswith(lowercase(part.tex), \"groove\") ? (5, 10) : (50, 100)", src))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
