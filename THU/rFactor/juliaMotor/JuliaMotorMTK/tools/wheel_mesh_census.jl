# CARGOLD-1 S1: each car's .3do CONTAINS its tyres; their centroids are where GPL puts the hubs.
# Detect tyre groups by shape (x- and z-extent both 0.5..0.8 m, centroid ≥ 0.45 m off centre) and
# print the four hub centroids per car, mesh frame (x along, y lateral, z up).
const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpl3do.jl")); using .GPL3DO
const BASE = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67"
cars = [("Lotus 49","lotus","lotus.3do"), ("Ferrari","ferrari","ferrari.3do"), ("Brabham","brabham","brabham.3do"),
        ("BRM","brm","brm.3do"), ("Eagle","eagle","eagle.3do"), ("Cooper","coventry","coventry.3do")]
for (nm, dir, body) in cars
    m = GPL3DO.parse_3do(joinpath(BASE, dir, body))
    # split every texture group by lateral SIDE so a texture shared by both wheels gives two hubs
    acc = Dict{Tuple{String,Int},Vector{NTuple{3,Float32}}}()
    for t in m.tris, p in t.p
        side = p[2] >= 0 ? 1 : -1
        push!(get!(acc, (t.tex, side), NTuple{3,Float32}[]), p)
    end
    hubs = Tuple{String,Int,Float64,Float64,Float64,Float64,Float64}[]
    for ((tex, side), ps) in acc
        length(ps) < 30 && continue
        xl, xh = extrema(p[1] for p in ps); zl, zh = extrema(p[3] for p in ps); yl, yh = extrema(p[2] for p in ps)
        ex = xh - xl; ez = zh - zl; ey = yh - yl
        cx = sum(p[1] for p in ps)/length(ps); cy = sum(p[2] for p in ps)/length(ps); cz = sum(p[3] for p in ps)/length(ps)
        # a tyre: round in x-z (0.5..0.8 m), narrow in y (≤ 0.45), sitting at |y| ≥ 0.45 — but a texture
        # may cover BOTH front and rear tyres on one side (x-extent then ~3 m): split by x sign too
        if 0.5 <= ez <= 0.8 && ey <= 0.45 && abs(cy) >= 0.45
            if ex <= 0.8
                push!(hubs, (tex, side, cx, cy, cz, ex, ez))
            else
                for sgn in (1, -1)
                    q = [p for p in ps if sign(p[1] - cx) == sgn || (sgn == 1 && p[1] == cx)]
                    length(q) < 15 && continue
                    qx = sum(p[1] for p in q)/length(q); qy = sum(p[2] for p in q)/length(q); qz = sum(p[3] for p in q)/length(q)
                    qxl, qxh = extrema(p[1] for p in q)
                    (qxh - qxl) <= 0.8 && push!(hubs, (tex, side, qx, qy, qz, qxh - qxl, ez))
                end
            end
        end
    end
    sort!(hubs; by = h -> (-h[3], -h[4]))
    println("== ", nm, " (", length(m.tris), " tris)")
    for h in hubs
        println("  ", rpad(h[1], 10), h[2] > 0 ? "L " : "R ", "hub (", round(h[3], digits=2), ", ", round(h[4], digits=2), ", ", round(h[5], digits=2), ")  extent x ", round(h[6], digits=2), " z ", round(h[7], digits=2))
    end
end
