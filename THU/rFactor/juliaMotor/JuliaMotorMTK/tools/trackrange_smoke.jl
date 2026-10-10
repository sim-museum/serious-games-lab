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
# BLINDTURN-1 S5: GPL draws the track over a LAP window (914 m ahead/behind along the road), not by eye distance --
# the Ring's Karussell plateau (1380 m ahead by road, 560 m away) hung in the sky from s 12500. The window functions are
# lifted from the sim and run on a synthetic 22.8 km lap of 100 m bins holding one triangle each.
fl = match(r"\nlapwin_in\(s, c\) = [^\n]*", src); fr = match(r"\nfunction lapranges\(off, c\)\n.*?\nend\n"s, src)
chk("the lap-window functions are in the sim", fl !== nothing && fr !== nothing)
if fl !== nothing && fr !== nothing
    M = Module(:LW)
    Core.eval(M, :(const LAPWIN = 914.0; const LAPBIN = 100.0; const _LW = (L = 22800.0,); const LAPNB = 228))
    Base.include_string(M, fl.match * fr.match)
    off = Int32[3k for k in 0:228]
    chk("the Karussell (1380 m ahead by road) is outside the window", !M.lapwin_in(13880.0, 12500.0))
    chk("800 m ahead and 800 m behind are inside", M.lapwin_in(13300.0, 12500.0) && M.lapwin_in(11700.0, 12500.0))
    chk("the window wraps across the line", M.lapwin_in(100.0, 22700.0) && M.lapwin_in(22700.0, 100.0))
    chk("mid-lap: one range of bins 40..59", M.lapranges(off, 5000.0) == ((120, 60), (0, 0)))
    chk("across the line: bins 221..227 and 0..12", M.lapranges(off, 300.0) == ((663, 21), (0, 39)))
    chk("an unknown eye position draws the whole part", M.lapranges(off, NaN) == ((0, 684), (0, 0)))
end
chk("the track loop draws the window's ranges; draw takes a range", occursin("for (f0, n0) in lapranges(TRACKLAPOFF[ti], _clap)", src) &&
    occursin("glDrawArrays(GL_TRIANGLES, first, count < 0 ? item.n : count)", rnd))
chk("objects get the same window (backdrops exempt)", occursin("!lapwin_in(OBJLAP[oi], _olap)) && continue", src) &&
    occursin("isbackdrop(lowercase(String(o[5]))) ? NaN", src))
chk("on by default at the Ring (914 m, GPL's 18,000,000 TRK)", occursin("get(ENV, \"JM_LAPWIN\", NURB ? \"914\" : \"0\")", src))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
