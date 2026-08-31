include("render.jl"); using .Render
const LOT = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
# per-triangle forward extent of what FSUSPP draws
parts = Render.extract_gpl_car(LOT; only=("lsusp1","frontlot"), maxlat=1.3f0, maxedge=1.5f0)
tris = []
for p in parts
    for i in 1:33:length(p.verts)-32
        v = [(p.verts[i+11j], p.verts[i+11j+1], p.verts[i+11j+2]) for j in 0:2]
        push!(tris, v)
    end
end
println("FSUSPP triangles: ", length(tris))
for thr in (1.4, 1.6, 1.8, 2.0, 2.4)
    keep = count(t -> maximum(v[1] for v in t) <= thr, tris)
    println("  keep tris with max x <= ", thr, " m : ", keep, " of ", length(tris), "   (front axle x=1.31)")
end
far = [t for t in tris if maximum(v[1] for v in t) > 1.8]
println("far-forward tris: ", length(far))
if !isempty(far)
    xs = [v[1] for t in far for v in t]; zs = [v[3] for t in far for v in t]; ys = [v[2] for t in far for v in t]
    println("  their extent: x [", round(minimum(xs),digits=2), ",", round(maximum(xs),digits=2), "]  y [", round(minimum(ys),digits=2), ",", round(maximum(ys),digits=2), "]  z [", round(minimum(zs),digits=2), ",", round(maximum(zs),digits=2), "]")
    el(t) = maximum(sqrt(sum((t[a][k]-t[b][k])^2 for k in 1:3)) for (a,b) in ((1,2),(2,3),(1,3)))
    println("  their max edge lengths: ", join(sort(round.([el(t) for t in far], digits=2), rev=true)[1:min(end,8)], " "))
end
near = [t for t in tris if maximum(v[1] for v in t) <= 1.8]
if !isempty(near)
    xs = [v[1] for t in near for v in t]; zs = [v[3] for t in near for v in t]
    println("near tris extent: x [", round(minimum(xs),digits=2), ",", round(maximum(xs),digits=2), "]  z [", round(minimum(zs),digits=2), ",", round(maximum(zs),digits=2), "]")
end
