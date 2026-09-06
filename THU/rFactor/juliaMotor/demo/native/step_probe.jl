# TERRAIN-STEP probe (epic #2, decision deferred to Fable 5.1): the steepest GENUINE upward step of
# each circuit's physics surface, so a "reject implausible upward step" rule (WALL_CLIMB, today
# Monza-only) can be given a threshold that is measured, not guessed. Walks the aligned centreline
# at 0.5 m with lateral offsets -8..+8 m and reports, per track, the max upward height change per
# 0.5 m step, the 99.9th percentile, where the max is, and how many samples a given threshold
# would reject. Headless. Usage: julia --project=demo/native demo/native/step_probe.jl [thresh_m]
include(joinpath(@__DIR__,"gpldat.jl"));   using .GPLDat
include(joinpath(@__DIR__,"gpl3do.jl"));   using .GPL3DO
include(joinpath(@__DIR__,"gpltrack.jl")); using .GPLTrack
using JuliaMotor, Printf, Statistics
const G = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks"
const TRACKS = length(ARGS) >= 2 ? [(ARGS[2], ARGS[2] == "zandvoort" ? "zandvort" : ARGS[2] == "nurburgring" ? "nurburg" : ARGS[2])] :
    [("zandvoort","zandvort"), ("nurburgring","nurburg"), ("watglen","watglen"), ("monza","monza"), ("spa","spa")]
thresh = length(ARGS) >= 1 ? parse(Float64, ARGS[1]) : 3.0
function align(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return cl
    xs = Float64[]; zs = Float64[]
    for tr in hat.tris, p in (tr.a, tr.b, tr.c); push!(xs, p[1]); push!(zs, p[3]); end
    dx0 = (minimum(xs)+maximum(xs))/2 - (minimum(p[1] for p in cl)+maximum(p[1] for p in cl))/2
    dz0 = (minimum(zs)+maximum(zs))/2 - (minimum(p[2] for p in cl)+maximum(p[2] for p in cl))/2
    best = (cov(dx0, dz0), dx0, dz0)
    for dx in dx0-400:40:dx0+400, dz in dz0-400:40:dz0+400; c = cov(dx, dz); c > best[1] && (best = (c, dx, dz)); end
    for dx in best[2]-40:8:best[2]+40, dz in best[3]-40:8:best[3]+40; c = cov(dx, dz); c > best[1] && (best = (c, dx, dz)); end
    [(p[1]+best[2], p[2]+best[3]) for p in cl]
end
for (name, dir) in TRACKS
    dats = filter(f -> lowercase(f)[end-3:end] == ".dat", readdir(joinpath(G, dir)))   # monza's is monza10k.dat
    datf = isempty(dats) ? "" : joinpath(G, dir, first(sort(dats; by = f -> (lowercase(f) != dir*".dat", f))))
    isfile(datf) || (println(name, ": no .dat"); continue)
    dat = GPLDat.parse_dat(datf)
    k3 = first(filter(k -> endswith(lowercase(k), ".3do") && startswith(lowercase(k), lowercase(dir)), collect(keys(dat))))
    kt = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(dat))))
    m3 = tempname()*".3do"; write(m3, dat[k3]); mt = tempname()*".trk"; write(mt, dat[kt])
    hat = GPLTrack.build_hat(GPL3DO.parse_3do(m3); drop_overpass = (name == "monza"))
    cl = align(GPLTrack.trk_centreline(mt), hat)
    h(x,z) = (r = JuliaMotor.hat3d(hat, x, z; ref=Inf); r[3] ? Float64(r[1]) : NaN)
    n = length(cl); steps = Float64[]; where = (0.0,0.0,0.0); mx = -Inf; rej = 0; tot = 0
    for lat in -8.0:2.0:8.0
        prev = NaN
        for i in 1:n
            (x0,z0) = cl[i]; (x1,z1) = cl[mod1(i+1,n)]
            dx, dz = x1-x0, z1-z0; L = hypot(dx,dz); L < 1e-6 && continue
            px, pz = -dz/L, dx/L
            # sub-sample this centreline segment at 0.5 m
            for t in 0.0:0.5:L
                x = x0 + dx/L*t + px*lat; z = z0 + dz/L*t + pz*lat
                hh = h(x, z)
                if !isnan(hh) && !isnan(prev)
                    d = prev - hh   # GPL y is up in hat3d? keep sign-agnostic: use the raw height, up = larger
                    d = hh - prev
                    push!(steps, d); tot += 1
                    d > thresh && (rej += 1)
                    if d > mx; mx = d; where = (x, z, hh); end
                end
                prev = hh
            end
        end
    end
    isempty(steps) && (println(name, ": no samples"); continue)
    up = filter(x -> x > 0, steps)
    @printf("%-12s samples=%7d  max up-step per 0.5 m = %6.2f m at (%.1f, %.1f) h=%.1f   p99.9 up = %5.2f m   >%.1f m: %d (%.4f%%)\n",
            name, tot, mx, where[1], where[2], where[3], isempty(up) ? 0.0 : quantile(up, 0.999), thresh, rej, 100rej/max(tot,1))
    flush(stdout)
end
println("STEP PROBE DONE")
