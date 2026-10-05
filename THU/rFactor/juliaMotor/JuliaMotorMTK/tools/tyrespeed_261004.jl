# IRFIT-261004 (test 3) acceptance at SPEED: the player car's stable-branch slip curve at 130 km/h on the 261004 skidpad
# setup, against the 261004 gold's steady circles at 100-140 km/h (tools/tyrecmp_261004.jl). TYRE-1 was identified at
# 86 km/h only.   julia --project=. tools/tyrespeed_261004.jl
ENV["JM_TYREID_ITERS"] = "0"
include(joinpath(@__DIR__, "tyrecmp_261004.jl"))     # g4s (261004 skidpad gold), loadtyre, ...
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
skid4 = first(filter(f -> occursin("skidpad", f) && endswith(f, ".ibt"), readdir(D4; join = true)))
let p = setup_params(ibt_open(skid4).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(skid4))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(skid4))
end
const VS = 130/3.6
car = DriveRT3D.build_car3d(; v0 = VS)
sys = car.sys; getv = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay])
A = ModelingToolkit.getp(sys, sys.a)(car.integ); B = ModelingToolkit.getp(sys, sys.b)(car.integ)
function curve(dir)
    g = 3; car.gear = g; car.s_gr(car.integ, DriveRT3D.GEARS[g]); car.s_we(car.integ, VS/DriveRT3D.RW_R*DriveRT3D.GEARS[g]*DriveRT3D.FINAL[])
    pts = NTuple{3,Float64}[]; ie = 0.0; tr = 40.0
    for k in 1:round(Int, (tr + 1)*60)
        t = k/60; δ = dir*0.12*clamp((t - 1)/tr, 0, 1)
        thr = clamp(0.35 + 0.4*(VS - car.v) + ie, 0, 1); ie = clamp(ie + 0.02*(VS - car.v), -0.5, 0.8)
        DriveRT3D.step_car3d!(car, thr, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, r, ay = getv(car.integ); (isfinite(u) && u > 5) || break
        abs(atan(v, u)) > deg2rad(15) && break
        t > 2 && abs(car.v - VS) < 2.0 || continue
        s = sign(ay); s == 0 && continue
        push!(pts, (s*ay/G, rad2deg(s*(δ - atan(v + A*r, u))), rad2deg(s*(-atan(v - B*r, u)))))
    end
    isempty(pts) ? pts : pts[1:argmax(first.(pts))]
end
P = vcat(curve(1.0), curve(-1.0))
println("130 km/h, stable branch: median slip (deg) front/rear per g band -- gold 261004 skidpad 100-140 km/h vs sim")
for lo in 0.4:0.1:1.1
    Q = [p.tp for p in g4s if lo <= p.tp.ay/G < lo + 0.1 && 100 <= 3.6p.tp.v < 140]
    S = [p for p in P if lo <= p[1] < lo + 0.1]
    (length(Q) < 25 || length(S) < 5) && continue
    @printf("   %.1f-%.1f g | gold %5.2f %5.2f (n %4d) | sim %5.2f %5.2f\n", lo, lo + 0.1, rad2deg(median(q.αf for q in Q)), rad2deg(median(q.αr for q in Q)),
            length(Q), median(getindex.(S, 2)), median(getindex.(S, 3)))
end
@printf("   sim peak lateral at 130 km/h: %.3f g\n", maximum(first.(P)))
