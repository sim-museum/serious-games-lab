# GATE: RESTARTGROUND-1 -- a restart re-anchors Monza's ground guard.
#
# PO 2026-10-18 (video 261018_monza_sink_jump.mp4, log monza 2026-10-18 21-49-15): after a wreck off the road (the
# guard's held height LASTZ -4.17 m) the PO pressed R; the restart never re-anchored the guard, so the new race ran
# under the mesh and was launched 12 m at s 460. restart_smoke checks the re-anchor line is in the source; this drives
# it: a Monza race with the held height forced to the PO's -4.17 m (JM_LASTZ_AT) on the frame of the restart, then
# JM_DRIVECHECK over the first ~280 m. Known positive (2026-10-22, the re-anchors removed): 1252 frames off the mesh,
# lowest ground -4.17, 6.5 m above the held height at s 442; with them: 0, -0.04, 0.06 m.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 64), d))
println("RESTARTGROUND gate: R after a wreck off the road re-anchors the ground (Monza)")
env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_MODE" => "race", "JM_AI" => "0", "JM_LAPS" => "3",
                            "JM_AUTODRIVE" => "1", "JM_AUTODRIVE_MANUAL" => "1", "ZAND_SHIFT" => "manual",
                            "JM_SMOKE" => "1", "JM_SMOKE_FRAMES" => "1050", "JM_FIXED_DT" => "0.016666666666666666",
                            "JM_NOREPLAY" => "1", "JM_NOIBT" => "1", "JM_NOSOUND" => "1", "JM_DRIVECHECK" => "1",
                            "JM_LASTZ_AT" => "2:-4.17", "JM_RESTART_AT" => "2"))
log = tempname()
run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
t = read(log, String); rm(log; force = true)
check("the stale height was forced", occursin("[test] LASTZ set to -4.17", t))
check("the race restarted", occursin("[restart] session reset on monza", t))
r = match(r"longest slow spell\s+: ([\d.]+) s at s=(-?[\d.]+)", t)   # (max s is no use: the grid is behind the line)
check("the car drove on after the restart (never 8 s slow)", r !== nothing && parse(Float64, r[1]) < 8, r === nothing ? "no report" : "$(r[1]) s at s $(r[2])")
o = match(r"frames OFF the mesh\s+: (\d+)", t)
check("never measured against the stale height (0 off-mesh frames)", o !== nothing && o[1] == "0", o === nothing ? "" : "$(o[1]) frames")
g = match(r"lowest groundz seen\s+: (-?[\d.]+)", t)
check("the ground never read the wreck's -4.17 m (lowest > -1 m)", g !== nothing && parse(Float64, g[1]) > -1, g === nothing ? "" : g[1])
a = match(r"max height above ground : (-?[\d.]+)", t)
check("no levitation (< 0.75 m above ground)", a !== nothing && parse(Float64, a[1]) < 0.75, a === nothing ? "" : "$(a[1]) m")
check("no error", !occursin(r"ERROR|Stacktrace"i, t))
println(fails[] == 0 ? "RESTARTGROUND: PASS" : "RESTARTGROUND: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
