include("gpl3do.jl"); using .GPL3DO
m = GPL3DO.parse_3do("/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do")
# GPL frame here: x fwd, y lateral, z up (as parsed). Hub positions from the positioner dump.
hubs = Dict(3560 => (1.526, -0.762, 0.0), 6600 => (1.526, 0.762, 0.0), 27288 => (-0.893, -0.772, 0.01), 39792 => (-0.893, 0.772, 0.01))
# the 24 proper axis permutations as signed permutation matrices
perms = []
for p in ((1,2,3),(1,3,2),(2,1,3),(2,3,1),(3,1,2),(3,2,1)), sx in (1,-1), sy in (1,-1), sz in (1,-1)
    R = zeros(3,3); R[1,p[1]] = sx; R[2,p[2]] = sy; R[3,p[3]] = sz
    abs(R[1,1]*(R[2,2]*R[3,3]-R[2,3]*R[3,2]) - R[1,2]*(R[2,1]*R[3,3]-R[2,3]*R[3,1]) + R[1,3]*(R[2,1]*R[3,2]-R[2,2]*R[3,1]) - 1) < 1e-9 && push!(perms, (p, sx, sy, sz, R))
end
for g in (3560, 27288)
    h = hubs[g]; side = sign(h[2])
    V = [(Float64(v[1])-h[1], Float64(v[2])-h[2], Float64(v[3])-h[3]) for (k,t) in enumerate(m.tris) if m.groups[k]==g && t.tex in ("lsusp1","frontlot","axlelot","lshok","lsusp2","lsusp5","lsusp7","lbrdisc") for v in t.p]
    println("group $g: ", length(V), " suspension verts, hub-relative. Envelope: |x|<0.6 (near the axle), inboard 0..0.9 (toward the centreline), height -0.15..0.35")
    best = []
    for (p, sx, sy, sz, R) in perms
        n = 0
        for v in V
            w = (R[1,1]*v[1]+R[1,2]*v[2]+R[1,3]*v[3], R[2,1]*v[1]+R[2,2]*v[2]+R[2,3]*v[3], R[3,1]*v[1]+R[3,2]*v[2]+R[3,3]*v[3])
            inboard = -side*w[2]                       # toward the centreline from this hub
            (abs(w[1]) < 0.6 && -0.05 <= inboard <= 0.9 && -0.15 <= w[3] <= 0.35) && (n += 1)
        end
        push!(best, (n/length(V), p, sx, sy, sz))
    end
    sort!(best, rev=true)
    println("  identity fit: ", round(100*first(filter(b -> b[2]==(1,2,3) && b[3]==1 && b[4]==1 && b[5]==1, best))[1]), "%")
    for b in first(best, 4); println("  fit ", round(100*b[1]), "%  perm ", b[2], " signs ", (b[3],b[4],b[5])); end
end
