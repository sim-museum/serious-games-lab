# E91-S8: off-throttle decel split by clutch state, in BOTH the iRacing gold and the sim.
# engine braking = (in gear, clutch engaged) - (clutch disengaged), at matched speed and RPM.
using Printf, Statistics
const T = joinpath(@__DIR__, "..")
include(joinpath(T, "src", "ibt.jl"));      using .IBT
include(joinpath(T, "src", "drive_rt.jl")); using .DriveRT
using .DriveRT: FINAL, RW_R
const DT = 1/60; const G = 9.80665
ch(f,n) = try channel(f,n) catch; nothing end
const REF = get(ENV, "JM_REFDIR", "/home/admin/gold standard/julia racer")

function sim_coast(v0, ratio, clutch)
    c = DriveRT.build_car(; v0 = v0)
    c.gear = 3; c.s_gr(c.integ, ratio)
    c.s_we(c.integ, (v0/RW_R)*ratio*FINAL)
    for _ in 1:30; DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = clutch, manual = true); end
    a = c.getall(c.integ); u0 = a[4]; r0 = a[6]
    for _ in 1:30; DriveRT.step_car!(c, 0.0, 0.0, 0.0, DT; clutch = clutch, manual = true); end
    a = c.getall(c.integ)
    (u0 - a[4]) / (30*DT), r0
end

function main()
    files = String[]
    for (r,_,fs) in walkdir(REF), fn in fs
        endswith(lowercase(fn), ".ibt") && push!(files, joinpath(r,fn))
    end
    P = Dict{Tuple{Int,Symbol},Vector{NTuple{3,Float64}}}()   # (gear, :eng/:dis) => (v, dec, rpm)
    for p in files
        f = ibt_open(p)
        thr, brk, spd, gr, cl, rpm = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed"), ch(f,"Gear"), ch(f,"Clutch"), ch(f,"RPM")
        lat, stw, yaw, alt = ch(f,"LatAccel"), ch(f,"SteeringWheelAngle"), ch(f,"YawRate"), ch(f,"Alt")
        n = minimum(length, (thr,brk,spd,gr,cl,rpm))
        for k in 4:n-4
            (thr[k] > 0.01 || brk[k] > 0.01 || spd[k] < 8) && continue
            abs(lat[k]) > 2.0 && continue; abs(stw[k]) > 0.10 && continue; abs(yaw[k]) > 0.05 && continue
            g = Int(round(gr[k])); (g < 1 || g > 5) && continue
            all(j -> gr[j] == gr[k], k-3:k+3) || continue           # no shift inside the window
            st = all(j -> cl[j] > 0.95, k-3:k+3) ? :eng : all(j -> cl[j] < 0.05, k-3:k+3) ? :dis : :slip
            st === :slip && continue
            dec = -(spd[k+3]-spd[k-3])/(6*DT) - G*((alt[k+3]-alt[k-3])/(6*DT))/spd[k]
            (dec <= -1 || dec > 15) && continue
            push!(get!(P, (g,st), NTuple{3,Float64}[]), (spd[k], dec, rpm[k]))
        end
    end
    println(" gear km/h | ref: n_eng  eng   n_dis  dis   EB    rpm | sim: eng   dis   EB  | EB sim/ref  total sim/ref")
    out = []
    for g in 1:5, (lo,hi) in ((20.0,30.0),(30.0,40.0),(40.0,55.0))
        E = [x for x in get(P,(g,:eng),[]) if lo<=x[1]<hi]
        D = [x for x in get(P,(g,:dis),[]) if lo<=x[1]<hi]
        (length(E) < 15 || length(D) < 15) && continue
        e, d = median(getindex.(E,2)), median(getindex.(D,2))
        r = median(getindex.(E,3)); vmid = median(getindex.(E,1))
        ratio = r*2π/60 / (vmid/RW_R) / FINAL               # gear ratio implied by the gold's own RPM
        se, rs = sim_coast(vmid, ratio, 0.0)
        sd, _  = sim_coast(vmid, ratio, 1.0)
        @printf(" %d   %4.0f | %5d %6.3f %5d %6.3f %6.3f %5.0f | %6.3f %6.3f %6.3f | %6.2f  %6.2f\n",
                g, vmid*3.6, length(E), e, length(D), d, e-d, r, se, sd, se-sd, (se-sd)/(e-d), se/e)
        push!(out, (g, vmid, r, e-d, se-sd))
    end
    rr = [o[5]/o[4] for o in out]
    @printf("\nengine-braking sim/ref: median %.2f  range %.2f..%.2f over %d bands\n", median(rr), minimum(rr), maximum(rr), length(rr))
end
main()
