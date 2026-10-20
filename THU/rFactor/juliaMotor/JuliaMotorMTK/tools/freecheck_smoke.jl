# freecheck_smoke.jl -- LOOPSPLIT-1 gate (2026-10-20). Moving a block of main()'s frame loop into a function in main_loop.jl
# leaves an UndefVarError behind for every main() local it uses but was not passed -- and that error fires only when its
# branch runs, which the other gates may never do (crash_step! needed the place_at_s! closure; autodrive_step!'s
# DRIVECHECK branch needed ONTRACK -- both found by this check, neither by 68 gates). JM_FREECHECK=1 lowers every function
# in main_loop.jl / main_diag.jl at main() entry and lists the globals it names that do not exist.
#   1. TREATMENT: the shipped code -- no undefined names;
#   2. CONTROL: JM_FREECHECK_CONTROL=1 adds a function filed under main_loop.jl that names an undefined global -- it must
#      be reported (a checker that reports nothing is worthless until it has caught something it must catch).
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 60), detail); ok || (fails[] += 1); ok)
function runcheck(extra)
    log = tempname()
    env = merge(Dict(ENV), Dict("TRACK" => "zandvoort", "JM_SMOKE" => "1", "JM_FREECHECK" => "1"), extra)
    p = run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env; dir = D)); stdout = log, stderr = log))
    (p.exitcode, filter(l -> occursin("[freecheck]", l), readlines(log)))
end
println("LOOPSPLIT-1 free-name gate: every function moved out of main() names only globals that exist")
(rc, lines) = runcheck(Dict{String,String}())
foreach(l -> println("    ", l), lines)
chk("treatment: no moved function names an undefined global", rc == 0 && any(l -> occursin("OK:", l), lines), "exit $rc")
(rc2, lines2) = runcheck(Dict("JM_FREECHECK_CONTROL" => "1"))
chk("control: a planted undefined name is reported", rc2 != 0 && any(l -> occursin("_freecheck_no_such_name", l), lines2),
    join(lines2, " | "))
println(fails[] == 0 ? "\n  FREECHECK GATE: PASS" : "\n  FREECHECK GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
