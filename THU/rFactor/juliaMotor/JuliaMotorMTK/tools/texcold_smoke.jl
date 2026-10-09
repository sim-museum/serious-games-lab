# GATE: LOADHANG-1 -- a COLD texture (decoded-texture cache empty) must cost milliseconds, with unchanged pixels.
#
# PO 2026-10-07: the AppImage's first Spa launch "hung" for 13 minutes: 1,921 textures through the cache-miss path at
# 125 ms each. The decode was 0.7 ms; the rest was the alpha-bleed pass inline in `tex_rgba`, whose closure captured a
# reassigned `w` (boxed -> a dynamic call per texel). Fixed by `_alpha_bleed!` (S3). Asserted: 120 Spa textures through
# `tex_rgba` with an empty cache at under 10 ms each (fixed: 1.7-3.4; the pre-fix code: 29 here, 125 in a quieter benchmark), and the pixels hash to the value both
# the broken and the fixed code produced, so a faster pass that changed the output fails too.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "render.jl")); using .Render
const SPA = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks", "spa67"))
isdir(SPA) || (println("GPL spa67 track not found: $SPA"); exit(2))
ENV["JM_TEXCACHE_DIR"] = mktempdir()
idx = Render.gpl_texture_index(SPA)
names = sort(collect(union(keys(idx.paths), [splitext(k)[1] for k in keys(idx.dat)])))[1:120]
Render.tex_rgba(Render.gpl_texture_index(SPA), names[1])                 # compile (and cache names[1])
ENV["JM_TEXCACHE_DIR"] = mktempdir(); idx = Render.gpl_texture_index(SPA) # a fresh, empty cache
redirect_stdout(devnull) do; global t = @elapsed (global rs = [Render.tex_rgba(idx, k) for k in names]); end
h = foldl((h, (k, r)) -> r === nothing ? h : hash((k, r[1], r[2], r[3]), h), zip(names, rs); init = UInt64(0))
ms = 1000t / length(names)
ok_t = ms < 10; ok_h = string(h, base = 16) == "51ed1bb0441d0a89"
println("  cold tex_rgba: ", round(ms, digits = 1), " ms per texture (limit 10)  ", ok_t ? "ok" : "TOO SLOW")
println("  pixel hash   : ", string(h, base = 16), ok_h ? "  (unchanged)" : "  CHANGED (want 51ed1bb0441d0a89)")
println(ok_t && ok_h ? "TEXCOLD: PASS" : "TEXCOLD: FAIL")
exit(ok_t && ok_h ? 0 : 1)
