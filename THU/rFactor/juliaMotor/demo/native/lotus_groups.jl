include("gpl3do.jl"); using .GPL3DO
m = GPL3DO.parse_3do(ARGS[1])
bygrp = Dict{Int,Dict{String,Int}}()
for (k,t) in enumerate(m.tris); d = get!(bygrp, m.groups[k], Dict{String,Int}()); d[t.tex] = get(d, t.tex, 0) + 1; end
for g in (27288, 39792); println("group $g: ", haskey(bygrp,g) ? join(["$k=$v" for (k,v) in sort(collect(bygrp[g]))], " ") : "(absent)"); end
println("groups containing axlelot:"); for (g,d) in bygrp; haskey(d,"axlelot") && println("  group $g: ", join(["$k=$v" for (k,v) in sort(collect(d))], " ")); end
# lateral extent of axlelot per group
for (g,d) in bygrp
    haskey(d,"axlelot") || continue
    ys = Float32[]; for (k,t) in enumerate(m.tris); (m.groups[k]==g && t.tex=="axlelot") && for v in t.p; push!(ys, v[2]); end; end
    println("  axlelot in group $g: |y| max ", round(maximum(abs.(ys)), digits=2), "  x range ", round(minimum(t.p[1][1] for (k,t) in enumerate(m.tris) if m.groups[k]==g && t.tex=="axlelot"), digits=2), "..", round(maximum(t.p[1][1] for (k,t) in enumerate(m.tris) if m.groups[k]==g && t.tex=="axlelot"), digits=2))
end
