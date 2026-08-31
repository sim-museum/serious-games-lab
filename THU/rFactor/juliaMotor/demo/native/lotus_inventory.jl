include("gpl3do.jl"); using .GPL3DO
const LOT = ARGS[1]
m = GPL3DO.parse_3do(LOT)
println("lotus.3do: ", length(m.tris), " tris, ", length(m.textures), " textures")
acc = Dict{String,Any}()
for (k,t) in enumerate(m.tris)
    a = get!(acc, t.tex, Any[0, fill(Inf32,3), fill(-Inf32,3), Set{Int}()])
    a[1] += 1; push!(a[4], m.groups[k])
    for v in t.p, i in 1:3; a[2][i] = min(a[2][i], v[i]); a[3][i] = max(a[3][i], v[i]); end
end
println(rpad("texture",12), rpad("tris",6), rpad("x[min,max]",22), rpad("y[min,max]",22), rpad("z[min,max]",22), "groups")
for (tex,a) in sort(collect(acc), by = p -> p[1])
    f(v) = string("[", round(v[1],digits=2), ",", round(v[2],digits=2), "]")
    println(rpad(tex == "" ? "(untex)" : tex,12), rpad(a[1],6), rpad(f((a[2][1],a[3][1])),22), rpad(f((a[2][2],a[3][2])),22), rpad(f((a[2][3],a[3][3])),22), length(a[4]))
end
