# GATE: GROOVECULL-1 -- the racing groove (GPL's braking marks) is never drawn single-sided.
#
# PO 2026-10-18: "the braking marks, which reveal the line, are entirely missing from the tracks. Tracks are now a uniform
# grey color throughout." WGTD-1 (f) (2026-10-08) added the groove to `railfam` for its coplanar dedup; `railfam` also
# selected TRACK_RAILCULL, the parts drawn with back-face culling, and the groove's triangles face away under that rule:
# from 10-08 no track drew a mark (planted check: asphalt hidden, still no groove; JM_GROOVE_DEDUP=0 brought it back).
#
# Source-text gate (the sim needs a display): evaluates the TRACK_RAILCULL predicate as written in drive_native_mtk.jl on
# texture names -- the groove must not be culled, a guardrail still must (known positive), and the dedup keeps the groove.
const SRC = joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl")
src = read(SRC, String)
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 58), d))
println("GROOVECULL-1 gate: the groove is never culled single-sided")

m = match(r"railfam\(tx\) = (\(lt = lowercase\(tx\);.*?\))\n"s, src)
check("railfam is defined", m !== nothing)
mc = match(r"const TRACK_RAILCULL = Bool\[(.*?) for p in TRACK\]", src)
check("TRACK_RAILCULL is defined", mc !== nothing)
if m !== nothing && mc !== nothing
    GROOVE_DEDUP = true
    _cull_tex = Set{String}()   # JM_TRACK_CULL_TEX (MONZAWALL-1 A/B), unset
    railfam = eval(Meta.parse("tx -> " * m.captures[1]))
    cull = eval(Meta.parse("p -> " * mc.captures[1]))
    P(t) = (tex = t,)
    check("groove: not culled", !Base.invokelatest(cull, P("groove")), "")
    check("Groove (any case): not culled", !Base.invokelatest(cull, P("Groove1")), "")
    check("KNOWN POSITIVE: a guardrail (armco) is still culled", Base.invokelatest(cull, P("armco")), "")
    check("the groove keeps its coplanar dedup (railfam)", Base.invokelatest(railfam, "groove"), "")
end
println(fails[] == 0 ? "GROOVECULL: PASS" : "GROOVECULL: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
