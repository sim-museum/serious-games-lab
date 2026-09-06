# CARGOLD-1 S1: where does each car's own .3do put its wheels, versus the hand table the sim uses?
# The body .3do references each wheel .3do by NAME through a 0x0E "named external sub-object"
# node whose positioner carries (dx,dy,dz) -- the same node kind trackside_objects() reads for a
# track. The sim instead places every car's wheels from one table (drive_native_mtk.jl WHEELS /
# aiwheels): front +1.05, rear -1.15 along, ±0.62 / ±0.66 lateral, all six chassis alike.
const BASE = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67"
cars = [("Lotus 49", "lotus",    "lotus.3do",    ("lotwlf","lotwrf","lotwlr","lotwrr")),
        ("Ferrari",  "ferrari",  "ferrari.3do",  ("f222lf","f222rf","f444lr","f444rr")),
        ("Brabham",  "brabham",  "brabham.3do",  ("brablf","brabrf","brablr","brabrr")),
        ("BRM",      "brm",      "brm.3do",      ("brm2lf","brm2rf","brm4lr","brm4rr")),
        ("Eagle",    "eagle",    "eagle.3do",    ("eotwlf","eotwrf","eotwlr","eotwrr")),
        ("Cooper",   "coventry", "coventry.3do", ("cooplf","cooprf","cooplr","cooprr"))]
table = Dict("lf" => (1.05, 0.62), "rf" => (1.05, -0.62), "lr" => (-1.15, 0.66), "rr" => (-1.15, -0.66))
function named_nodes(path)
    b = read(path)
    u32(o) = (o < 0 || o + 4 > length(b)) ? UInt32(0) : UInt32(b[o+1]) | (UInt32(b[o+2]) << 8) | (UInt32(b[o+3]) << 16) | (UInt32(b[o+4]) << 24)
    f32(o) = reinterpret(Float32, u32(o))
    strn = prim = 0; strnsz = 0; o = 12
    while o + 12 <= length(b)
        t = String(b[o+1:o+4]); sz = Int(u32(o+8)); data = o + 12
        t == "NRTS" && (strn = data; strnsz = sz); t == "MIRP" && (prim = data)
        o = data + sz; o += (4 - o % 4) % 4
    end
    off2name = Dict{Int,String}(); let cur = UInt8[], p = 0
        for i in strn:strn+strnsz-1
            c = b[i+1]; if c == 0xFF; break; elseif c == 0x00; off2name[p] = String(copy(cur)); p += length(cur) + 1; empty!(cur); else push!(cur, c); end
        end
    end
    out = Tuple{String,Float64,Float64,Float64,Float64,Float64}[]; k = 0; primlen = length(b) - prim
    while k + 44 <= primlen
        if u32(prim+k) == 14 && u32(prim+k+8) == 0 && u32(prim+k+12) == 19
            wn = Int(u32(prim+k+4))
            if haskey(off2name, wn)
                push!(out, (lowercase(off2name[wn]), f32(prim+k+16), f32(prim+k+20), f32(prim+k+24), f32(prim+k+28), f32(prim+k+40)))
            end
        end
        k += 4
    end
    out
end
println(rpad("car", 10), rpad("wheel", 8), rpad("node dx", 10), rpad("dy", 10), rpad("dz", 10), rpad("| table along", 14), "lateral")
for (nm, dir, body, wheels) in cars
    p = joinpath(BASE, dir, body); isfile(p) || (println(nm, ": no ", p); continue)
    nodes = named_nodes(p)
    for w in wheels
        hits = [n for n in nodes if n[1] == w]
        key = w[end-1:end]; (ta, tl) = table[key]
        if isempty(hits)
            println(rpad(nm, 10), rpad(w, 8), "(no 0x0E node named ", w, ")  | ", ta, "  ", tl)
        else
            for h in hits
                println(rpad(nm, 10), rpad(w, 8), rpad(round(h[2], digits=3), 10), rpad(round(h[3], digits=3), 10), rpad(round(h[4], digits=3), 10),
                        "| ", rpad(ta, 12), tl)
            end
        end
    end
    others = unique([n[1] for n in nodes if !(n[1] in wheels)])
    println("  other named nodes in ", body, ": ", length(nodes), " total, e.g. ", join(others[1:min(end, 8)], " "))
end
