# AI-CARGFX S5 gate: the parked rear-suspension groups that render as flat blades beside the AI
# cars' wheels (Eagle 29108/39200, BRM 26116/35320 -- S447's map, confirmed by A/B capture) are
# dropped at parse time for those chassis and nothing else changes. JM_AI_PARKED_SUSP=1 shows them.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "gpl3do.jl")); using .GPL3DO
using Printf
const AIBASE = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "cars", "cars67"))
fails = 0
pass(ok, msg, val) = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(msg, 56), val); ok || (global fails += 1))
for (chassis, file, ids) in (("eagle", "eagle/eagle.3do", Set([29108, 39200])), ("brabham", "brabham/brabham.3do", Set([32916, 48284])), ("cooper", "coventry/coventry.3do", Set([30048, 41624])))
    path = joinpath(AIBASE, file)
    isfile(path) || (pass(false, "$chassis .3do present", path); continue)
    GPL3DO.HIDE_GROUPS[] = Set{Int}()
    m0 = GPL3DO.parse_3do(path)
    n_in = count(g -> g in ids, m0.groups)
    pass(n_in > 0, "premise: $chassis carries tris in the parked groups", "$n_in tris")
    GPL3DO.HIDE_GROUPS[] = ids
    m1 = GPL3DO.parse_3do(path)
    GPL3DO.HIDE_GROUPS[] = Set{Int}()
    pass(count(g -> g in ids, m1.groups) == 0, "treatment: $chassis emits none of them", "$(count(g -> g in ids, m1.groups)) tris")
    pass(length(m1.tris) == length(m0.tris) - n_in, "treatment: only those tris are gone", @sprintf("%d -> %d", length(m0.tris), length(m1.tris)))
    others0 = count(g -> !(g in ids), m0.groups); others1 = length(m1.tris)
    pass(others0 == others1, "every other group untouched", "$others1 tris")
end
SRC = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
pass(occursin("AI_PARKED_SUSP_GROUPS = Dict(\"eagle\" => Set([29108, 39200]), \"brabham\" => Set([32916, 48284]), \"cooper\" => Set([30048, 41624]))", SRC), "loader hides Eagle/Brabham/Cooper blade groups (BRM/Ferrari untouched)", "source check")
pass(occursin("Render.GPL3DO.HIDE_GROUPS[] = get(ENV, \"JM_AI_PARKED_SUSP\", \"0\") != \"0\" ? Set{Int}()", SRC), "JM_AI_PARKED_SUSP=1 restores the groups", "source check")
pass(occursin("Render.GPL3DO.HIDE_GROUPS[] = Set{Int}()   # never leak", SRC), "the hide set is reset after the AI loop", "source check")
println(fails == 0 ? "AI-PARKED-SUSP GATE: PASS" : "AI-PARKED-SUSP GATE: FAIL ($fails)")
exit(fails == 0 ? 0 : 1)
