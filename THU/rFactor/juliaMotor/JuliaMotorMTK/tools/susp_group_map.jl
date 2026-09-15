const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpl3do.jl")); using .GPL3DO
m = GPL3DO.parse_3do("/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do")
println("tris ", length(m.tris), "   groups field length ", length(m.groups))
using Printf
const EXCL = Set([6600,3560,27288,39792])
# for each rear-suspension texture, which positioner groups carry it, and are they all excluded?
want = ("lshok","lsusp2","lsusp3","lsusp4","lsusp5","lsusp6","lsusp7","axlelot","frontlot","lbrdisc")
tally = Dict{String,Dict{Int,Int}}()
for (i,t) in enumerate(m.tris)
    t.tex in want || continue
    g = i <= length(m.groups) ? m.groups[i] : -1
    d = get!(tally, t.tex, Dict{Int,Int}())
    d[g] = get(d, g, 0) + 1
end
@printf("%-10s %-46s %s\n", "texture", "groups (tris)", "verdict")
for k in want
    haskey(tally,k) || (@printf("%-10s %-46s %s\n", k, "(absent)", ""); continue)
    d = tally[k]
    gs = join(["$g:$(d[g])" for g in sort(collect(keys(d)))], " ")
    allexcl = all(g in EXCL for g in keys(d))
    anyexcl = any(g in EXCL for g in keys(d))
    @printf("%-10s %-46s %s\n", k, gs,
            allexcl ? "ALL in excluded groups -- not drawn at all" :
            anyexcl ? "partly excluded" : "drawn")
end
