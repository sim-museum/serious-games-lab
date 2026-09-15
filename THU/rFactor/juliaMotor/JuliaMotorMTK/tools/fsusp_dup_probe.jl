# E102 S17: is `fsusp:1` -- the 34-triangle stray REAR cluster of the "frontlot" part, the one that
# tints to exactly the two wedges the PO photographed -- a DUPLICATE of geometry the car already
# draws there, or the only copy?
#
# Duplicate  -> drop it; the car loses nothing and the wedges go.
# Only copy  -> it needs the REAR placement; dropping it would remove real bodywork.
#
# The test is geometric and needs no renderer: for each of the 34 triangles, find the nearest
# triangle ANYWHERE ELSE in lotus.3do by centroid, and report how close it is and whether its three
# vertices coincide. A duplicate has a twin at distance ~0 with matching vertices.
#
#   julia --project=demo/native JuliaMotorMTK/tools/fsusp_dup_probe.jl
const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpl3do.jl")); using .GPL3DO
const CAR = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
m = GPL3DO.parse_3do(CAR)
cen(t) = ntuple(i -> sum(p[i] for p in t.p)/length(t.p), 3)
# E102 S16: fsusp:1 is the "frontlot" triangles whose x lies in the stray rear cluster.
const XLO, XHI = -1.10, -0.90
target = [t for t in m.tris if t.tex == "frontlot" && XLO <= cen(t)[1] <= XHI]
others = [t for t in m.tris if !(t.tex == "frontlot" && XLO <= cen(t)[1] <= XHI)]
println("lotus.3do: ", length(m.tris), " triangles;  fsusp:1 candidate = ", length(target),
        " with tex=\"frontlot\" and centroid x in [", XLO, ", ", XHI, "]")
isempty(target) && (println("  nothing selected -- the split bounds are wrong for this mesh"); exit(2))
d2(a,b) = sqrt(sum((a[i]-b[i])^2 for i in 1:3))
vmatch(t,u) = length(t.p)==length(u.p) && all(any(d2(p,q) < 0.01 for q in u.p) for p in t.p)
near0 = 0; vdup = 0; dists = Float64[]
bytex = Dict{String,Int}()
for t in target
    local c, best, bd
    c = cen(t); best = nothing; bd = Inf
    for u in others
        dd = d2(c, cen(u))
        if dd < bd; bd = dd; best = u; end
    end
    push!(dists, bd)
    if bd < 0.05
        global near0 += 1
        bytex[best.tex] = get(bytex, best.tex, 0) + 1
        vmatch(t, best) && (global vdup += 1)
    end
end
sort!(dists)
println("  nearest OTHER triangle, centroid distance (m):")
println("    min ", round(dists[1], digits=4), "   median ", round(dists[(end+1)÷2], digits=4),
        "   max ", round(dists[end], digits=4))
println("  triangles with a neighbour closer than 5 cm: ", near0, " of ", length(target))
println("  of those, with all three vertices coincident (<1 cm): ", vdup)
if !isempty(bytex)
    println("  the close neighbours belong to: ", join(["$k x$v" for (k,v) in sort(collect(bytex), by=last, rev=true)], ", "))
end
println()
println(vdup == length(target) ? "VERDICT: every fsusp:1 triangle has an exact twin elsewhere -- DUPLICATE, safe to drop." :
        near0 == 0 ? "VERDICT: no fsusp:1 triangle has anything within 5 cm -- it is the ONLY copy; dropping it removes real bodywork." :
        "VERDICT: MIXED -- $near0 of $(length(target)) have a close neighbour and $vdup are exact twins. Not a clean drop; see the table above.")
