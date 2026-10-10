# TRACKSIGNS-1 (2026-10-10): GPL runs on Windows (case-blind file names); the PO's Ring "Traffic-signs" add-on ships its
# 140+ signs as UPPER-case loose .3do files placed under lower-case names. Checks: the object lookup is case-blind (the
# track folder indexed by lower-case name), and the add-on's km stones (0.45 m) pass the "under 1 m tall" rule.
# With the PO's GPL install present, also: every TS_/SI_/KM_ file the Ring places resolves through that index.
const D = joinpath(@__DIR__, "..", "..", "demo", "native")
src = read(joinpath(D, "drive_native_mtk.jl"), String)
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 66), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
chk("object files are looked up case-blind", occursin("const _ZD_LC = Dict(lowercase(f) => f", src) && occursin("objpath(nm) = (p=_zd_file(nm*\".3do\")", src))
chk("km stones pass the height rule", occursin("tallenough(nm) = (get(ymx,nm,0f0)-get(ymn,nm,0f0)) > 1.0f0 || startswith(lowercase(nm), \"km_\")", src) &&
    !occursin("(get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0", src))
ZD = expanduser("~/sgl/THU/WP/drive_c/Sierra/GPL/tracks/nurburg")
if isdir(ZD)
    lc = Dict(lowercase(f) => f for f in readdir(ZD))
    names = ["ts_hb", "si_or", "km_02_4", "ts_qh"]
    found = [haskey(lc, n * ".3do") for n in names]
    chk("the add-on's files resolve by lower-case name", all(found), join(("$n => $(get(lc, n * ".3do", "?"))" for n in names), ", "))
else
    println("  (no GPL install here: file check skipped)")
end
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
