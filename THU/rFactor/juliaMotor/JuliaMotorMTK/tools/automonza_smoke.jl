# automonza_smoke.jl -- AUTODRIVE-MONZA-1 gate (2026-10-23). The autodriver (JM_AUTODRIVE, the actor of every integration
# race and several gates) follows CLINE, the centreline re-centred on the visible road -- and at Monza's pit exit
# (s 345-440) CLINE runs down the walled pit-exit channel beside GPL's road, which closes at s 440: the autodriver hit its
# walls at s 409 and 437 on every run, alone or in a race (no gate drove that far: restartground_smoke stops near 280 m).
# Where CLINE leaves GPL's road (the free interval holding GPL's own race.lp line) the autodriver now steers along its own
# line (autodrive_offsets / autodrive_line in main_loop.jl).
#   1. TREATMENT: Monza practice, autodriver alone, 40 s: the line is shifted at the fork, no wall contact before s 700,
#      the car passes s 600, the run exits cleanly;
#   2. CONTROL (the known positive): JM_AUTODRIVE_ROAD=0 (CLINE as is), 20 s: it must hit the walls before s 450.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 62), detail); ok || (fails[] += 1); ok)
function drive(extra, frames)
    log = tempname()
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_NOSOUND" => "1", "JM_NOIBT" => "1", "JM_NOREPLAY" => "1",
                                "JM_FIXED_DT" => "0.016666666666666666", "JM_AUTODRIVE" => "1", "JM_AUTODRIVE_DIAG" => "60",
                                "JM_STUCK_SECS" => "0", "JM_SMOKE_FRAMES" => string(frames)), extra)
    p = run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env; dir = D)); stdout = log, stderr = log))
    L = readlines(log); rm(log; force = true)
    hits = Float64[parse(Float64, m[1]) for m in (match(r"\[jolt\] t=[0-9.]+ s=([0-9.]+) .*wall hits \+[1-9]", l) for l in L) if m !== nothing]
    smax = maximum((parse(Float64, m[1]) for m in (match(r"\[auto\] t=.* s=([0-9.]+) ", l) for l in L) if m !== nothing); init = 0.0)
    sh = match(r"\[autodrive\] line kept on GPL's road: (\d+) m shifted", join(L, "\n"))
    (p.exitcode, L, hits, smax, sh === nothing ? -1 : parse(Int, sh[1]))
end
println("AUTODRIVE-MONZA-1 gate: the autodriver passes Monza's pit exit on GPL's road")
(rc, L, hits, smax, shifted) = drive(Dict{String,String}(), 2400)
foreach(l -> println("    ", l), first(filter(l -> occursin("ERROR", l), L), 3))
chk("the run exits cleanly", rc == 0 && any(==("bye"), strip.(L)), "exit $rc")
chk("the line is shifted onto GPL's road at the fork (> 200 m)", shifted > 200, "$shifted m")
early = filter(s -> s < 700, hits)
chk("no wall contact before s 700", isempty(early), isempty(early) ? "" : "at s $(round.(early[1:min(3, end)], digits = 1))")
chk("the car passes s 600 (past the pit exit's end at 440)", smax > 600, "max s $(round(smax, digits = 1))")
(rc2, L2, hits2, smax2, _) = drive(Dict("JM_AUTODRIVE_ROAD" => "0"), 1200)
c = filter(s -> s < 450, hits2)
chk("control (JM_AUTODRIVE_ROAD=0): CLINE hits the pit-exit walls before s 450", !isempty(c),
    isempty(c) ? "no contact (max s $(round(smax2, digits = 1)))" : "first at s $(round(c[1], digits = 1))")
println(fails[] == 0 ? "\n  AUTOMONZA GATE: PASS" : "\n  AUTOMONZA GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
