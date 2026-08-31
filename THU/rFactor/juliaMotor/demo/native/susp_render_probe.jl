# E82-S2: WHICH parts produce the chrome legs the PO sees? Report, for every group the chase view
# draws, the extent in car space AFTER the corrective transform the sim applies -- so a part that
# reaches far forward/outward can be named rather than guessed at from a screenshot.
include("render.jl"); using .Render
include("susp_pose.jl"); using .SuspPose
const LOT = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus/lotus.3do"
function extent(parts, M)
    lo = fill(Inf,3); hi = fill(-Inf,3); n = 0
    for p in parts, i in 1:11:length(p.verts)-10
        v = Float32[p.verts[i], p.verts[i+1], p.verts[i+2], 1f0]; w = M === nothing ? v : M*v
        for k in 1:3; lo[k] = min(lo[k], w[k]); hi[k] = max(hi[k], w[k]); end
        n += 1
    end
    (n, lo, hi)
end
r(v) = string("[", round(v[1],digits=2), ",", round(v[2],digits=2), "]")
function show1(tag, parts, M)
    (n, lo, hi) = extent(parts, M)
    println("  ", rpad(tag,26), rpad(string(n," v"),8), "x", rpad(r((lo[1],hi[1])),16), "y", rpad(r((lo[2],hi[2])),16), "z", r((lo[3],hi[3])))
end
println("car space: x fwd, y up, z lateral. Wheels: front axle x=+1.31, rear x=-1.10, hubs z=±0.75, tyre r=0.33")
MA = SuspPose.rsfix(1, Render.translate, Render.rotx, Render.scalexyz)
MB = SuspPose.rsfix(-1, Render.translate, Render.rotx, Render.scalexyz)
show1("FSUSPP (lsusp1+frontlot)", Render.extract_gpl_car(LOT; only=("lsusp1","frontlot"), maxlat=1.3f0, maxedge=1.5f0), nothing)
show1("RSUSPP_A raw", Render.extract_gpl_car(LOT; include_groups=(27288,), exclude=("ltraymap","lshad")), nothing)
show1("RSUSPP_A after rsfix(+1)", Render.extract_gpl_car(LOT; include_groups=(27288,), exclude=("ltraymap","lshad")), MA)
show1("RSUSPP_B after rsfix(-1)", Render.extract_gpl_car(LOT; include_groups=(39792,), exclude=("ltraymap","lshad")), MB)
show1("RSUSPP2 (lshok/lsusp5/7)", Render.extract_gpl_car(LOT; only=("lshok","lsusp5","lsusp7","lbrdisc"), maxlat=1.3f0, maxedge=1.5f0), nothing)
println("JM_RS_ROLL currently ", SuspPose.RS_ROLL_DEG)
