# E80-S10 (2026-10-15): the render/track modules load from the JRRender PACKAGE (cached compiled code: Spa launch
# 199 → 177 s). Checks: the sim takes them from the package by default with the loose-file fallback kept; the package
# includes the very files the sim's fallback does; its workload is there; it loads in this project and its modules
# are the ones the sim names; the AppImage refreshes and cache-checks it.
const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
src = read(joinpath(ROOT, "demo", "native", "drive_native_mtk.jl"), String)
pkg = read(joinpath(ROOT, "JRRender", "src", "JRRender.jl"), String)
app = read(joinpath(ROOT, "tools", "appimage", "build_julia.sh"), String)
fails = Ref(0)
chk(name, ok) = (println("  ", rpad(name, 74), ok ? "PASS" : "FAIL"); ok || (fails[] += 1); ok)
println("JRRender gate")
chk("the sim loads JRRender unless JM_RENDER_INCLUDE is set",
    occursin("if get(ENV, \"JM_RENDER_INCLUDE\", \"0\") != \"0\"", src) && occursin("using JRRender: Render, GPLTrack, GPLWall, RoadCurve", src))
for f in ("render.jl", "gpltrack.jl", "gplwall.jl", "roadcurve.jl")
    chk("package and fallback include the same $f", occursin("include(joinpath(NAT, \"$f\"))", pkg) && occursin(f, src))
end
wl = joinpath(ROOT, "JRRender", "src", "workload.jl")
chk("the workload holds the launch signatures (>= 200)", isfile(wl) && count(startswith("precompile("), eachline(wl)) >= 200)
chk("the AppImage refreshes and cache-checks JRRender",
    occursin("JRPhysics JRRender; do", app) && occursin("using JRPhysics, JRRender, JuliaMotor, RFactorData", app))
ok = try
    @eval using JRRender
    isdefined(JRRender.Render.GPL3DO, :parse_3do) && isdefined(JRRender.GPLTrack, :trk_centreline) &&
        isdefined(JRRender.RoadCurve, :curve_mesh) && parentmodule(JRRender.RoadCurve) === JRRender
catch e
    println("    load error: ", sprint(showerror, e)); false
end
chk("JRRender loads in demo/native's project, its modules in place", ok)
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
