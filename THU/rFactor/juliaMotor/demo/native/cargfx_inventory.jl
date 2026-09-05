# AI-CARGFX sprint 1: per-chassis group inventory.
# The item's first move is "which of the five AI chassis show which deviations", BEFORE any mesh is
# touched. The player Lotus was fixed by suppressing mis-posed rear-half groups (E106-S7) and
# synthesizing straight shafts (S9); the AI cars load through another path and never got either.
# So: list every group in every chassis with its triangle count and LATERAL extent, and flag the
# ones that reach past the wheel plane -- those are the "rods" candidates, per chassis.
push!(LOAD_PATH, joinpath(@__DIR__))
include(joinpath(ENV["JM"], "demo", "native", "gpl3do.jl"))
using .GPL3DO
const BASE = normpath(joinpath(ENV["JM"],"..","..","WP","drive_c","Sierra","GPL","cars","cars67"))
SPECS = [("Lotus","lotus","lotus.3do", 0.62f0, 0.66f0),
         ("Ferrari","ferrari","ferrari.3do", 0.62f0, 0.66f0),
         ("Brabham","brabham","brabham.3do", 0.62f0, 0.66f0),
         ("BRM","brm","brm.3do", 0.62f0, 0.66f0),
         ("Eagle","eagle","eagle.3do", 0.62f0, 0.66f0),
         ("Cooper","coventry","coventry.3do", 0.62f0, 0.66f0)]
for (nm,dir,body,hf,hr) in SPECS
    p = joinpath(BASE,dir,body)
    if !isfile(p); println("$nm: MISSING $p"); continue; end
    m = GPL3DO.parse_3do(p)
    # per group: tri count, lateral (z) extent
    acc = Dict{Int,Vector{Float32}}()
    tex = Dict{Int,Dict{String,Int}}()
    for i in eachindex(m.tris)
        g = m.groups[i]; t = m.tris[i]
        e = get!(acc, g, Float32[Inf32,-Inf32,0f0])
        for v in t.p
            z = Float32(v[3])          # GPL native lateral axis
            e[1] = min(e[1], z); e[2] = max(e[2], z)
        end
        e[3] += 1f0
        d = get!(tex, g, Dict{String,Int}()); d[t.tex] = get(d, t.tex, 0) + 1
    end
    # half-track of the rear wheels, in the same native units, from the widest wheel-ish group
    println("\n=== $nm  ($(length(m.tris)) tris, $(length(acc)) groups)")
    rows = sort(collect(acc); by = kv -> -max(abs(kv[2][1]), abs(kv[2][2])))
    for (g,e) in rows[1:min(8,length(rows))]
        tn = sort(collect(tex[g]); by = kv -> -kv[2])
        @printf("   grp=%-8d tris=%-6d lat z = %8.3f .. %8.3f  halfwidth=%7.3f  tex=%s\n",
                g, Int(e[3]), e[1], e[2], max(abs(e[1]),abs(e[2])),
                join([first(x) for x in tn[1:min(3,length(tn))]], ","))
    end
end
