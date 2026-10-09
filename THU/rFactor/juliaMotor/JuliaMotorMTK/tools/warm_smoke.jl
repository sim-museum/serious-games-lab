# PERF-4 gate (PO 2026-10-08: "a lag between control inputs and car response, especially noticable at the start of a
# race"). Measured cause: methods compiled the first time they ran, mid-race -- the first contact with another car in the
# crowded start froze the game ~145 ms, a crash ~250 ms. The sim now compiles those during loading (warm_statements.jl).
# This drives the PO's kind of race start headlessly -- Watkins Glen, 5 AI, MANUAL gearbox with clutch launches and
# shifts (JM_AUTODRIVE_MANUAL) -- and reads the sim's own [stall] lines (each slow frame with the compile time inside it):
#   * the warm-up ran and most of the list still matches the code (a stale list shows up as many skipped);
#   * after the first second (frame 40+: the smoke run's one-off screenshot sits at frame 38), at most WARM_BUDGET_MS of
#     compiling happens inside stalls over the 60 s.
# Known positive: with JM_WARM=0 the same run compiles ~145 ms at the first contact and this gate FAILS.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const BUDGET = parse(Float64, get(ENV, "WARM_BUDGET_MS", "60"))
fails = Ref(0)
chk(name, ok, detail) = (println(rpad("  " * name, 64), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1))
println("\n  PERF-4 — no compile stalls at the race start (Watkins Glen, 5 AI, manual gearbox)\n")
log = tempname()
env = Dict("TRACK" => "watglen", "JM_MODE" => "race", "JM_AI" => "5", "JM_LAPS" => "3", "JM_AUTODRIVE" => "1",
           "JM_AUTODRIVE_MANUAL" => "1", "ZAND_SHIFT" => "manual", "JM_SMOKE" => "1", "JM_SMOKE_FRAMES" => "3600",
           "JM_NOREPLAY" => "1", "JM_NOIBT" => "1", "JM_NOSOUND" => "1")
open(log, "w") do io
    run(pipeline(setenv(`julia -t 2 --gcthreads=3,1 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, merge(copy(ENV), env));
                 stdout = io, stderr = io); wait = true)
end
txt = read(log, String)
w = match(r"\[warm\] (\d+) in-race methods compiled ahead \((\d+) skipped\)", txt)
nok = w === nothing ? 0 : parse(Int, w[1]); nbad = w === nothing ? 0 : parse(Int, w[2])
chk("the warm-up ran", w !== nothing && nok > 0, w === nothing ? "no [warm] line" : "$nok compiled, $nbad skipped")
chk("the warm list matches the code (<= 25 % skipped)", nok > 0 && nbad <= 0.25 * (nok + nbad),
    "regenerate with tools/warmgen.py if this fails")
stalls = [(parse(Int, m[1]), parse(Float64, m[2]), parse(Float64, m[3])) for m in
          eachmatch(r"\[stall\] frame (\d+) t=[0-9.]+s\s+([0-9.]+) ms \(compile ([0-9.]+)", txt)]
late = [s for s in stalls if s[1] >= 40]
comp = sum((s[3] for s in late); init = 0.0)
for s in late; s[3] > 0 && println("    stall at frame ", s[1], ": ", s[2], " ms, compile ", s[3], " ms"); end
chk("compiling inside race stalls <= $(BUDGET) ms", comp <= BUDGET, "$(round(comp, digits = 1)) ms in $(length(late)) stall(s)")
chk("the race ran (window revealed)", occursin("window revealed", txt), "")
println(fails[] == 0 ? "\n  WARM GATE: PASS ✓" : "\n  WARM GATE: FAIL ✗")
exit(fails[] == 0 ? 0 : 1)
