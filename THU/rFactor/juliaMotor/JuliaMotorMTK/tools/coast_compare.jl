# coast_compare.jl — E91-S4. The comparison that needs NO decomposition.
#
# WHY THIS AND NOT ANOTHER FIT
#   E91-S1..S3 tried to DERIVE the engine-braking constant by subtracting aero and rolling from a
#   coast-down. That failed on its own terms: after removing the slope term the derived engine
#   torque had R^2 = 0.064 against rpm (and -0.091 for the code's own one-term form), i.e. no engine
#   signal survives subtracting two much larger quantities. Three sprints of fitting produced an
#   estimate that moved 2.5x on one modelling correction.
#
#   But the PO's complaint is not about a constant. It is: "lifting completely off the throttle
#   decelerates the car like ABS". That is a statement about TOTAL off-throttle deceleration, which
#   is DIRECTLY OBSERVABLE in both the sim and the reference. Compare those two numbers at matched
#   speed and gear and no decomposition is needed at all -- no aero fit, no rolling term, no slope
#   correction, nothing to get wrong.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/coast_compare.jl

using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl"));      using .IBT
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT
using .DriveRT: GEARS, FINAL, RW_R

const DT = 1/60
const G  = 9.80665

ch(f,n) = try channel(f,n) catch; nothing end

"Sim: coast at v0 (m/s) in `gear`, clutch OUT, zero throttle/brake. Return decel in m/s^2."
function sim_coast(v0, gear)
    c = DriveRT.build_car(; v0 = v0)
    c.gear = gear; c.s_gr(c.integ, GEARS[gear])
    c.s_we(c.integ, (v0/RW_R)*GEARS[gear]*FINAL)
    for _ in 1:30                                     # settle
        DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true)
    end
    a = c.getall(c.integ); u0 = a[4]
    for _ in 1:30                                     # 0.5 s of coast
        DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = 0.0, manual = true)
    end
    a = c.getall(c.integ); u1 = a[4]
    (u0 - u1) / (30*DT), u0
end

# ---- reference: telemetry off-throttle decel, straight-line only, slope removed --------------
dir = joinpath(@__DIR__, "..", "..", "data", "juliaracer")
files = sort(filter(p -> endswith(p,".ibt"), readdir(dir; join=true)))
ref = Dict{Int,Vector{Tuple{Float64,Float64}}}()      # gear => [(v, decel)]
for p in files
    f = try ibt_open(p) catch; continue end
    thr, brk, spd = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed")
    gr, cl        = ch(f,"Gear"), ch(f,"Clutch")
    lat, stw, yaw = ch(f,"LatAccel"), ch(f,"SteeringWheelAngle"), ch(f,"YawRate")
    alt           = ch(f,"Alt")
    any(isnothing,(thr,brk,spd,gr)) && continue
    n = min(length(thr),length(brk),length(spd),length(gr))
    for k in 4:(n-4)
        (thr[k] > 0.01 || brk[k] > 0.01 || spd[k] < 8) && continue
        cl !== nothing && cl[k] > 0.5 && continue                    # clutch OUT only
        lat !== nothing && abs(lat[k]) > 2.0 && continue
        stw !== nothing && abs(stw[k]) > 0.10 && continue
        yaw !== nothing && abs(yaw[k]) > 0.05 && continue
        g = Int(round(gr[k])); (g < 1 || g > 5) && continue
        dec = -(spd[k+3]-spd[k-3])/(6*DT)
        alt !== nothing && spd[k] > 1 && (dec -= G*((alt[k+3]-alt[k-3])/(6*DT))/spd[k])
        (dec <= 0 || dec > 15) && continue
        push!(get!(ref, g, Tuple{Float64,Float64}[]), (spd[k], dec))
    end
end

println("E91-S4: TOTAL off-throttle deceleration, sim vs iRacing reference")
println("        (clutch out, no brake, straight line; no decomposition anywhere)\n")
@printf("  %-5s %-9s %-8s %-12s %-12s %-8s\n", "gear","km/h","n(ref)","ref m/s^2","sim m/s^2","sim/ref")
rows = Tuple{Int,Float64,Int,Float64,Float64}[]
for g in sort(collect(keys(ref)))
    pts = ref[g]
    length(pts) < 25 && continue
    for (lo,hi) in ((20.0,30.0),(30.0,40.0),(40.0,55.0))
        band = [d for (v,d) in pts if lo <= v < hi]
        length(band) < 15 && continue
        vmid = (lo+hi)/2
        r = median(band)
        s, u0 = sim_coast(vmid, g)
        @printf("  %-5d %-9.0f %-8d %-12.3f %-12.3f %-8.2f\n", g, vmid*3.6, length(band), r, s, s/r)
        push!(rows, (g, vmid, length(band), r, s))
    end
end
if !isempty(rows)
    ratios = [x[5]/x[4] for x in rows]
    @printf("\n  median sim/ref ratio across %d matched bands: %.2f\n", length(rows), median(ratios))
    m = median(ratios)
    println(m > 1.25 ? "  => the SIM decelerates MORE off-throttle than the reference: the PO's complaint is confirmed." :
            m < 0.80 ? "  => the sim decelerates LESS than the reference." :
                       "  => sim and reference agree within 25%: the complaint is NOT reproduced by this measure.")
end
