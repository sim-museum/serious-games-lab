include("gpl3do.jl"); using .GPL3DO
m = GPL3DO.parse_3do("/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do")
tor(v) = (Float64(v[1]), Float64(v[3]), Float64(v[2]))
acc = Dict{String,Any}()
for (k,t) in enumerate(m.tris)
    a = get!(acc, t.tex, Any[0, fill(Inf,3), fill(-Inf,3)])
    a[1] += 1; for v in t.p; r = tor(v); for i in 1:3; a[2][i]=min(a[2][i],r[i]); a[3][i]=max(a[3][i],r[i]); end; end
end
println("parts whose lateral extent exceeds 0.8 m (car space z), i.e. at or beyond the wheels:")
for (tex,a) in sort(collect(acc), by=p->-max(abs(p[2][2][3]), abs(p[2][3][3])))
    zmax = max(abs(a[2][3]), abs(a[3][3])); zmax > 0.8 || continue
    println("  ", rpad(tex == "" ? "(untex)" : tex, 11), rpad(a[1],5), " x[", round(a[2][1],digits=2), ",", round(a[3][1],digits=2), "]  z max ", round(zmax,digits=2))
end
