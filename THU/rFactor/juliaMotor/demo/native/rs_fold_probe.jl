include("gpl3do.jl"); using .GPL3DO
m = GPL3DO.parse_3do("/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do")
# render frame per build_hat's comment: GPL (x,y,z) -> (x, z_up -> y, y -> z_lateral)
tor(v) = (Float64(v[1]), Float64(v[3]), Float64(v[2]))
# rsfix(+1) with shipped defaults: about hub line (y0=0.02, z0=0.772), rotx(-90deg); scale 1; no dx/dy
function rsfix(p; side=1, roll=deg2rad(90.0), y0=0.02, z0=0.772)
    x,y,z = p; y -= y0; z -= side*z0
    c, s = cos(-side*roll), sin(-side*roll)         # rotx: y' = c*y - s*z ; z' = s*y + c*z
    y2 = c*y - s*z; z2 = s*y + c*z
    (x, y2 + y0, z2 + side*z0)
end
for g in (27288,)
    acc = Dict{String,Any}()
    for (k,t) in enumerate(m.tris)
        m.groups[k] == g || continue
        a = get!(acc, t.tex, Any[fill(Inf,3), fill(-Inf,3), fill(Inf,3), fill(-Inf,3)])
        for v in t.p
            r = tor(v); f = rsfix(r)
            for i in 1:3; a[1][i]=min(a[1][i],r[i]); a[2][i]=max(a[2][i],r[i]); a[3][i]=min(a[3][i],f[i]); a[4][i]=max(a[4][i],f[i]); end
        end
    end
    println("group $g (render frame x fwd, y up, z lateral) -- RAW vs after rsfix(+1, 90deg about hub line z=0.772):")
    for tex in ("axlelot","lshok","lsusp2","lsusp5","lsusp7","lbrdisc","rear","top")
        haskey(acc,tex) || continue; a = acc[tex]
        r(v) = string("[", round(v[1],digits=2), ",", round(v[2],digits=2), "]")
        println("  ", rpad(tex,8), " RAW x", r((a[1][1],a[2][1])), " y", r((a[1][2],a[2][2])), " z", r((a[1][3],a[2][3])),
                "   FOLDED x", r((a[3][1],a[4][1])), " y", r((a[3][2],a[4][2])), " z", r((a[3][3],a[4][3])))
    end
end
println("reference: rear tyres at z=+-0.772 (hub line), ground y ~ -0.22 (lowest body), wheel radius 0.33")
