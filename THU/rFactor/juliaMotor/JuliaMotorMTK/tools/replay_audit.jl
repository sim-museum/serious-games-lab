# REPLAY-AUDIT: scan the PO's .jmr replays for the event classes that turned out to be defects
# (SPA-BARRIER, the Ring plateau) and emit, per event, the exact JM_HATPROBE / JM_SOLIDNEAR strings
# that localise it headlessly in the sim's own frame. Usage:
#   julia replay_audit.jl [dir-or-file ...]      (default: demo/native/data/juliaracer)
using Serialization, Printf
paths = isempty(ARGS) ? [joinpath(@__DIR__, "..", "..", "data", "juliaracer")] : ARGS
files = String[]
for p in paths
    isdir(p) ? append!(files, filter(f -> endswith(f, ".jmr"), readdir(p; join = true))) : push!(files, p)
end
sort!(files)
function audit(path)
    r = deserialize(path); st = 1 + 4*r.ncar; nf = r.nframes
    t  = [Float64(r.data[(i-1)*st+1]) for i in 1:nf]
    xs = [Float64(r.data[(i-1)*st+2]) for i in 1:nf]; ys = [Float64(r.data[(i-1)*st+3]) for i in 1:nf]; zs = [Float64(r.data[(i-1)*st+4]) for i in 1:nf]
    v  = [i == 1 ? 0.0 : hypot(xs[i]-xs[i-1], zs[i]-zs[i-1])/max(t[i]-t[i-1], 1e-3) for i in 1:nf]
    dy = [i == 1 ? 0.0 : ys[i]-ys[i-1] for i in 1:nf]
    tele  = [i for i in 2:nf if hypot(xs[i]-xs[i-1], zs[i]-zs[i-1]) > 100]                 # respawn / teleport
    vjump = [i for i in 2:nf if abs(dy[i]) > 1.0 && !(i in tele)]                          # terrain step / plateau edge
    # throw-back: the car's direction of travel reverses within 0.5 s while still fast
    back = Int[]
    for i in 6:nf-1
        (i in tele) && continue
        ux = xs[i]-xs[i-5]; uz = zs[i]-zs[i-5]; wx = xs[i+1]-xs[i]; wz = zs[i+1]-zs[i]
        (hypot(ux, uz) > 5.0 && hypot(wx, wz) > 1.0 && ux*wx + uz*wz < -0.5*hypot(ux,uz)*hypot(wx,wz)) && push!(back, i)
    end
    # a WALL-STEEP climb: > 2 m gained at a grade above 30 % over the last 2 s (real roads stay
    # under ~15 %; the Ring plateau ramp was ~90 %). Not a teleport.
    climb = Int[]
    for i in 31:nf
        any(k -> i-30 <= k <= i, tele) && continue
        dyy = ys[i]-ys[i-30]; dyy > 2.0 || continue
        path = sum(hypot(xs[k]-xs[k-1], zs[k]-zs[k-1]) for k in i-29:i)
        dyy/max(path, 1e-3) > 0.30 && push!(climb, i)
    end
    (r = r, t = t, xs = xs, ys = ys, zs = zs, v = v, dy = dy, tele = tele, vjump = vjump, back = back, climb = climb, nf = nf)
end
function probe_strings(a, i)
    lo = max(1, i-8); hi = min(a.nf, i+4)
    pts = join([@sprintf("%.1f,%.1f", a.xs[k], a.zs[k]) for k in lo:2:hi], ";")
    @sprintf("      TRACK=%s JM_SMOKE=1 JM_NOREPLAY=1 JM_HATPROBE=\"%s\" JM_SOLIDNEAR=\"%.1f,%.1f,40\"", a.r.track, pts, a.xs[i], a.zs[i])
end
println("REPLAY AUDIT -- ", length(files), " replays")
for f in files
    a = audit(f)
    @printf("\n%s\n   track=%s ncar=%d dur=%.0f s  teleports=%d  |dy|>1m=%d  throw-backs=%d  climbs>3m=%d\n",
            basename(f), a.r.track, a.r.ncar, a.t[end]-a.t[1], length(a.tele), length(a.vjump), length(a.back), length(a.climb))
    shown = 0
    for (tag, idxs) in (("THROW-BACK", a.back), ("VERTICAL JUMP", a.vjump), ("CLIMB", a.climb), ("TELEPORT", a.tele))
        last = -100
        for i in idxs
            i - last < 30 && continue; last = i; shown += 1; shown > 6 && break
            @printf("   %-13s t=%7.2f at (%.1f, %.1f) y=%.2f v=%.1f m/s dy=%+.2f\n", tag, a.t[i], a.xs[i], a.zs[i], a.ys[i], a.v[i], a.dy[i])
            tag == "TELEPORT" || println(probe_strings(a, i))
        end
    end
end
