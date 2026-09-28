# E107-S3 groundwork: GPL ships the CORRIDOR too. minrace.lp / maxrace.lp should bound the racing
# line, and our LANE_MAX = 3.8 m is a guess that cannot represent Monza's line at all (S2 measured
# race.lp running 4.5-13.4 m off the .trk centreline for ~1400 m across the start/finish line).
#
# This reads all six line files per track and asks: what band does GPL itself describe, does race.lp
# sit inside it, and how does that compare with our +-3.8 m?
#
# It also settles the question S2 left open -- whether Monza's 13 m is real or an index-origin
# artifact -- WITHOUT the leaky road-texture filter: if minrace/maxrace bracket race.lp at those same
# stations, then all six files agree the line is out there and it is real data, not a phase error.
const ND = "/home/g/sgl-jr/THU/rFactor/juliaMotor/demo/native"
include(joinpath(ND, "gpldat.jl")); using .GPLDat
include(joinpath(ND, "gpl_lp.jl")); using .GPLLP
using Printf
const BASE = normpath(joinpath(ND, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
pct(v, p) = isempty(v) ? NaN : (u = sort(copy(v)); u[clamp(ceil(Int, p*length(u)), 1, length(u))])

function lines(dir, nm)
    zd = joinpath(BASE, dir)
    ci(n) = (m = filter(f -> lowercase(f) == lowercase(n), readdir(zd)); isempty(m) ? "" : joinpath(zd, m[1]))
    dat = (p = ci(nm*".dat"); p == "" ? Dict{String,Vector{UInt8}}() : GPLDat.parse_dat(p))
    function getf(n)
        p = ci(n); p != "" && return p
        v = get(dat, lowercase(n), nothing); v === nothing && return ""
        q = tempname()*"_"*n; write(q, v); q
    end
    out = Dict{String,Any}()
    for n in ("race.lp", "pass1.lp", "pass2.lp", "minrace.lp", "maxrace.lp", "pit.lp")
        p = getf(n); p == "" && continue
        try; out[n] = GPLLP.read_lp(p); catch e; println("   ", n, ": ", sprint(showerror, e)); end
    end
    out
end

function track(dir, nm)
    L = lines(dir, nm)
    haskey(L, "race.lp") || (println("== ", dir, ": no race.lp"); return)
    r = Float64.(L["race.lp"].dlat); n = length(r)
    @printf("\n== %s: %d records (~%.0f m lap)   files: %s\n", dir, n, 3.0n,
            join(sort(collect(keys(L))), " "))
    for k in sort(collect(keys(L)))
        v = Float64.(L[k].dlat)
        @printf("   %-12s %5d rec  dlat p05 %+7.2f p50 %+7.2f p95 %+7.2f  min %+7.2f max %+7.2f m\n",
                k, length(v), pct(v,0.05), pct(v,0.5), pct(v,0.95), minimum(v), maximum(v))
    end
    if haskey(L, "minrace.lp") && haskey(L, "maxrace.lp")
        lo = Float64.(L["minrace.lp"].dlat); hi = Float64.(L["maxrace.lp"].dlat)
        m = min(n, length(lo), length(hi))
        # which of the pair is actually the lower bound? do not assume the filenames
        swapped = sum(lo[1:m]) > sum(hi[1:m])
        a = swapped ? hi : lo; b = swapped ? lo : hi
        w = [b[i] - a[i] for i in 1:m]
        inside = count(i -> a[i] - 1e-6 <= r[i] <= b[i] + 1e-6, 1:m)
        @printf("   corridor (%s): width p05 %.2f p50 %.2f p95 %.2f max %.2f m;  race.lp inside it at %d of %d (%.1f %%)\n",
                swapped ? "maxrace is the LOWER bound -- filenames are reversed" : "minrace low, maxrace high",
                pct(w,0.05), pct(w,0.5), pct(w,0.95), maximum(w), inside, m, 100inside/m)
        @printf("   our band is a fixed +-3.8 m, i.e. 7.6 m wide; GPL's is %.2f m at its narrowest and %.2f m at its widest\n",
                minimum(w), maximum(w))
        # the stations S2 flagged at Monza: does the corridor bracket race.lp there too?
        big = [i for i in 1:m if abs(r[i]) > 4.5]
        if !isempty(big)
            ok = count(i -> a[i] - 1e-6 <= r[i] <= b[i] + 1e-6, big)
            @printf("   at the %d records where |race dlat| > 4.5 m: corridor brackets race.lp at %d (%.1f %%), corridor spans %+.1f..%+.1f m\n",
                    length(big), ok, 100ok/length(big),
                    minimum(a[big]), maximum(b[big]))
        end
    end
end

function main()
    for (d, n) in (("zandvort","zandvort"), ("watglen","watglen"), ("monza","monza"),
                   ("spa67","spa67"), ("nurburg","nurburg"))
        try; track(d, n); catch e; println(d, ": ", sprint(showerror, e)); end
    end
end
main()
