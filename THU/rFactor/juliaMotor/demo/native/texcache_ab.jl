# Deferred E67-S1 A/B, run headless: does the decoded-texture disk cache actually pay?
include(joinpath(@__DIR__,"render.jl")); using .Render
const GPLBASE = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks"))
const ZD = joinpath(GPLBASE, get(ENV,"GPLNAME","spa67"))
idx = Render.gpl_texture_index(ZD)
names = sort(unique(vcat(collect(keys(idx.paths)),
                         [splitext(k)[1] for k in keys(idx.dat)])))
println("track dir: ", ZD)
println("cache dir: ", idx.cachedir == "" ? "(OFF)" : idx.cachedir)
println("textures to resolve: ", length(names))
# Ref accumulators: a bare `ok += 1` in a top-level loop is a soft-scope local, not the global.
const OK = Ref(0); const BYTES = Ref(0)
# Content hash, not just a byte count: a cache that returns the WRONG pixels has the right
# size. Cold and warm must agree on this number or the cache is not safe to default on.
const H = Ref(UInt(0))
t = @elapsed for n in names
    r = Render.tex_rgba(idx, n)
    if r !== nothing
        OK[] += 1; BYTES[] += length(r[3])
        H[] = hash((n, r[1], r[2], r[3]), H[])
    end
end
println("RESULT resolved=", OK[], "/", length(names), "  bytes=", BYTES[],
        "  seconds=", round(t, digits=2), "  content=", string(H[], base=16))
