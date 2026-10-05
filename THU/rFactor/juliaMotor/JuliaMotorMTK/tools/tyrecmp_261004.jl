# IRFIT-261004 (test 3): is the tyre the same across SPEED and SETUP? The TYRE-1 fit used the 261002 gold (skidpad on
# the lopsided oval setup, ~86 km/h, plus Ring driving). 261004 adds steady circles on the symmetric Ring setup
# (152 L / 207 R kPa, the oval's pressure floor) at ~45-160 km/h in both directions. Median axle slip per g band,
# split by session, speed and turn direction (+ = left turn: LatAccel > 0).
#   julia --project=. tools/tyrecmp_261004.jl
using Printf, Statistics
include(joinpath(@__DIR__, "tyrefit_261002.jl"))
const D4 = expanduser("~/gold standard/julia racer/261004")
struct TPD; tp::TP; dir::Int; end
function loaddir(dir, pred)
    out = TPD[]
    for (r, _, fs) in walkdir(dir), fn in sort(fs)
        (endswith(lowercase(fn), ".ibt") && pred(fn)) || continue
        f = ibt_open(joinpath(r, fn)); lat = channel(f, "LatAccel")
        tmp = mktempdir(); cp(joinpath(r, fn), joinpath(tmp, fn))
        for p in loadtyre(tmp); push!(out, TPD(p, 0)); end
        rm(tmp; recursive = true)
    end
    out
end
g2 = loaddir(REF, fn -> !occursin("charlotte", fn))
g4s = loaddir(D4, fn -> occursin("skidpad", fn))
g4r = loaddir(D4, fn -> occursin("nordschleife", fn))
row(P, lo, hi, vlo, vhi) = (Q = [p.tp for p in P if lo <= p.tp.ay/G < hi && vlo <= 3.6p.tp.v < vhi];
    length(Q) < 25 ? "      --       " : @sprintf("%5.2f %5.2f %4d", rad2deg(median(q.αf for q in Q)), rad2deg(median(q.αr for q in Q)), length(Q)))
for (lab, vlo, vhi) in (("< 100 km/h", 0, 100), ("100-140 km/h", 100, 140), ("> 140 km/h", 140, 400))
    println("\n", lab, ":  front/rear median slip (deg) and n per lateral-g band")
    println("   g band   | 261002 skid+Ring  | 261004 skidpad    | 261004 Ring")
    for lo in 0.1:0.1:1.2
        @printf("   %.1f-%.1f  | %s | %s | %s\n", lo, lo + 0.1, row(g2, lo, lo + 0.1, vlo, vhi), row(g4s, lo, lo + 0.1, vlo, vhi), row(g4r, lo, lo + 0.1, vlo, vhi))
    end
end
