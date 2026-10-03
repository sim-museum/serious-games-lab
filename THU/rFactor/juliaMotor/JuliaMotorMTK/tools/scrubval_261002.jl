# TYRE-1 acceptance: CORNERING SCRUB, sim vs gold. "Turn the wheel and scrub off speed."
#
# Gold: zero-throttle CLUTCH-IN coasts, steady, extra speed loss over the straight-line road load
#       (tools/tyrefit_261002.jl, B), per 0.1 g lateral band, all three tracks.
# Sim:  the player car (DriveRT3D) coasting clutch-in while a steering controller holds a target
#       lateral g, from 45 m/s down; extra speed loss = its decel minus the same car's STRAIGHT coast
#       decel at the same speed (so the sim's own road load cancels exactly).
# Tyre parameters can be overridden for A/B: JM_TYRE="μf,μr,Cαf,Cαr,kμ".
#
#   julia --project=. tools/scrubval_261002.jl
using Printf, Statistics
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "tyrefit_261002.jl"))
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq

ring = first(filter(f -> occursin("nurburgring", f) && endswith(f, ".ibt"), sort(readdir(REF; join = true))))
let p = setup_params(ibt_open(ring).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(ring))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(ring))
end
const CAR = DriveRT3D.build_car3d(; v0 = 45.0)
const U0 = copy(CAR.integ.u); const SYS = CAR.sys
const GET = ModelingToolkit.getsym(SYS, [SYS.u, SYS.v, SYS.r, SYS.ay])
if haskey(ENV, "JM_TYRE")
    μf, μr, Cf, Cr, kμ = parse.(Float64, split(ENV["JM_TYRE"], ","))
    for (w, μ, C) in ((:FL, μf, Cf), (:FR, μf, Cf), (:RL, μr, Cr), (:RR, μr, Cr))
        tw = getproperty(SYS, w)
        ModelingToolkit.setp(SYS, tw.μ)(CAR.integ, μ); ModelingToolkit.setp(SYS, tw.Cα)(CAR.integ, C)
        ModelingToolkit.setp(SYS, tw.kμ)(CAR.integ, kμ)
    end
    U0 .= CAR.integ.u
    println("tyre override: ", ENV["JM_TYRE"])
end

# clutch-in coast from v0 holding |ay| = gt (gt = 0: straight); returns (v, ay/g, decel) samples
function coast(gt; v0 = 45.0)
    reinit!(CAR.integ, copy(U0)); CAR.gear = 5; CAR.s_gr(CAR.integ, DriveRT3D.GEARS[5])
    vs = Float64[]; gs = Float64[]; δ = 0.0
    for k in 1:60*150
        u, v, r, ay = GET(CAR.integ)
        k > 60 && gt > 0 && (δ = clamp(δ + 0.004*(gt*G - abs(ay))/G, 0.0, 0.30))   # integral steering on |ay| error
        DriveRT3D.step_car3d!(CAR, 0.0, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 1.0, manual = true)
        push!(vs, CAR.v); push!(gs, abs(ay)/G)
        (CAR.v < 14 || abs(atan(v, u)) > deg2rad(12)) && break
    end
    n = length(vs); out = NTuple{3,Float64}[]
    for k in 121:n-15
        d = -sum(j*vs[k+j] for j in -15:15)/((1/60)*15*16*31/3)
        push!(out, (vs[k], gs[k], d))
    end
    out
end

if haskey(ENV, "JM_CABL")
    ModelingToolkit.setp(SYS, SYS.c_abl)(CAR.integ, parse(Float64, ENV["JM_CABL"])); U0 .= CAR.integ.u
    println("c_abl override: ", ENV["JM_CABL"])
end
function main()
    straight = coast(0.0)
    sv = [p[1] for p in straight]; sd = [p[3] for p in straight]
    base(v) = (i = argmin(abs.(sv .- v)); sd[i])
    S = NTuple{3,Float64}[]
    for gt in 0.15:0.1:1.15
        for p in coast(gt); abs(p[2] - gt) < 0.05 && p[1] < 44 && push!(S, (p[1], p[2], p[3] - base(p[1]))); end
    end
    # Charlotte excluded: on 24° banking LatAccel/g overstates the tyre's share of the load (more Fz),
    # so its scrub at a given "g" is low -- the same reason the tyre fit leaves it out.
    P = [p for p in loadtyre(REF) if p.kind === :dis && !occursin("charlotte", p.file)]
    println("CORNERING SCRUB, clutch-in coast: extra decel over a straight coast (m/s^2)")
    println("   g band   | gold n  km/h  scrub | sim n  km/h  scrub | sim/gold")
    rs = Float64[]
    for g in 0.1:0.1:1.0
        gi = [p for p in P if g <= p.ay/G < g + 0.1]; si = [s for s in S if g <= s[2] < g + 0.1]
        (length(gi) < 30 || length(si) < 30) && continue
        gm = median(p.dec - (0.480*0.5p.rho*p.v^2 + 0.0139*p.m*G)/(p.m + M_W) for p in gi)
        sm = median(getindex.(si, 3))
        push!(rs, sm/gm)
        @printf("   %.1f-%.1f  | %5d  %4.0f  %.3f | %5d %4.0f  %.3f | %5.2f\n", g, g + 0.1, length(gi), 3.6mean(p.v for p in gi), gm,
                length(si), 3.6mean(getindex.(si, 1)), sm, sm/gm)
    end
    @printf("   median sim/gold %.2f over %d bands\n", median(rs), length(rs))
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
