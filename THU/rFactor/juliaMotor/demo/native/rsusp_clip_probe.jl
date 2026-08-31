include("render.jl"); using .Render
const LOT = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
for (tag, grp) in (("RSUSPP_A", 27288), ("RSUSPP_B", 39792))
    parts = Render.extract_gpl_car(LOT; include_groups=(grp,), exclude=("ltraymap","lshad"))
    tris = []
    for p in parts, i in 1:33:length(p.verts)-32
        push!(tris, [(p.verts[i+11j], p.verts[i+11j+1], p.verts[i+11j+2]) for j in 0:2])
    end
    el(t) = maximum(sqrt(sum((t[a][k]-t[b][k])^2 for k in 1:3)) for (a,b) in ((1,2),(2,3),(1,3)))
    println(tag, ": ", length(tris), " tris")
    # the rear assembly should live between the gearbox (x ~ -0.8) and just behind the axle (x ~ -1.8)
    for thr in (-1.6, -1.8, -2.0, -2.2)
        println("   keep tris with min x >= ", thr, " : ", count(t -> minimum(v[1] for v in t) >= thr, tris), " of ", length(tris))
    end
    far = [t for t in tris if minimum(v[1] for v in t) < -1.8 || maximum(abs(v[3]) for v in t) > 0.95]
    println("   outside the envelope (x < -1.8 or |z| > 0.95): ", length(far), " tris")
    if !isempty(far)
        xs=[v[1] for t in far for v in t]; zs=[v[3] for t in far for v in t]
        println("     extent x [", round(minimum(xs),digits=2), ",", round(maximum(xs),digits=2), "]  |z| max ", round(maximum(abs.(zs)),digits=2), "   max edges ", join(sort(round.([el(t) for t in far],digits=2), rev=true)[1:min(end,6)], " "))
    end
end
