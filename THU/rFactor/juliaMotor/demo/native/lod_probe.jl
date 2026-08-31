include("gpl3do.jl"); using .GPL3DO
m = GPL3DO.parse_3do("/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do")
tor(v) = (Float64(v[1]), Float64(v[3]), Float64(v[2]))
acc = Dict{Tuple{String,Int},Any}()
for (k,t) in enumerate(m.tris)
    t.tex in ("lsusp1","frontlot","lshok","axlelot","lsusp5","lsusp7") || continue
    a = get!(acc, (t.tex, m.groups[k]), Any[0, fill(Inf,3), fill(-Inf,3), 0.0])
    a[1] += 1; for v in t.p; r = tor(v); for i in 1:3; a[2][i]=min(a[2][i],r[i]); a[3][i]=max(a[3][i],r[i]); end; end
    e(a,b) = sqrt(sum((a[i]-b[i])^2 for i in 1:3)); a[4] = max(a[4], e(t.p[1],t.p[2]), e(t.p[2],t.p[3]), e(t.p[1],t.p[3]))
end
println("LOD_ALL=", GPL3DO.LOD_ALL, "  total tris ", length(m.tris))
for ((tex,g),a) in sort(collect(acc), by = p -> (p[1][1], p[1][2]))
    r(v) = string("[", round(v[1],digits=2), ",", round(v[2],digits=2), "]")
    println("  ", rpad(tex,9), rpad(g,8), rpad(a[1],5), "x", rpad(r((a[2][1],a[3][1])),15), "y", rpad(r((a[2][2],a[3][2])),15), "z", rpad(r((a[2][3],a[3][3])),15), "max edge ", round(a[4],digits=2))
end
