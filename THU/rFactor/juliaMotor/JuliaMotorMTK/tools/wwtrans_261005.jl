# WWSETUP-1: the TRANSIENT A/B of the two setups, gold vs sim -- the PO's "loose on power", and the lift-off.
#
#   B3 power-on: on a ~1 g circle the throttle is squeezed to full. Measured: the throttle at which the rear lets go
#      (sideslip |β| passes 6°) and whether it then spins (|β| > 20°). The gold driver catches some slides with
#      countersteer, so only the let-go point is compared, not what follows.
#   B4 lift-off: the throttle snapped shut at 1.0-1.2 g, wheel held. Measured over 2.5 s: the peak yaw rate over the
#      path rate (r·u/ay; 1 = the car just follows its path, > 1 tucks in), the peak |β| and the speed lost.
# Gold events are found from the channels (no hand list); each is replayed by its own setup's sim car (the same
# install as tools/arbfit_261005.jl) at the event's speed and lateral g, settled first with the same controller.
#
#   julia --project=. tools/wwtrans_261005.jl
using Printf, Statistics
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "arbfit_261005.jl"))              # install!, FILES, gold helpers, DriveRT3D

function gold_events()
    E = NamedTuple[]
    for d in (D4, D5), fn in sort(readdir(d; join = true))
        (occursin("skidpad", fn) && endswith(fn, ".ibt")) || continue
        f = ibt_open(fn); side = setupof(f)
        c = Dict(n => ch(f, n) for n in ("Speed","VelocityX","VelocityY","YawRate","LatAccel","Throttle","Brake","IsOnTrack"))
        v, vx, vy, r, ay, thr = c["Speed"], c["VelocityX"], c["VelocityY"], c["YawRate"], c["LatAccel"], c["Throttle"]
        β(k) = rad2deg(abs(atan(vy[k], max(vx[k], 1.0))))
        k = 61; n = f.nrows
        while k < n - 200
            steady = c["IsOnTrack"][k] > 0.5 && v[k] > 33 && abs(ay[k]) > 0.85G && β(k) < 4 && c["Brake"][k] < 0.01
            if steady && thr[k] < 0.65 && any(j -> thr[j] > 0.95, k:k+360)           # B3: a squeeze within 6 s
                j0 = k; jf = findfirst(j -> thr[j] > 0.95, k:k+360) + k - 1
                rise = thr[jf] - thr[j0]
                if rise > 0.3 && all(j -> thr[j+1] >= thr[j] - 0.05, j0:jf-1)
                    jl = findfirst(j -> β(j) > 6, j0:min(n, jf + 180))
                    jl = jl === nothing ? nothing : jl + j0 - 1
                    push!(E, (kind = :power, side, file = basename(fn), t = k/60, v = v[k], g = abs(ay[k])/G,
                              thr0 = thr[j0], ramp = (jf - j0)/60, letgo = jl === nothing ? NaN : thr[jl],
                              spin = any(j -> β(j) > 20, j0:min(n, jf + 180))))
                    k = jf + 180; continue
                end
            end
            if steady && thr[k] > 0.3 && v[k] > 38 && abs(ay[k]) > 0.95G && thr[k+18] < 0.05   # B4: shut within 0.3 s
                w = k:min(n, k + 150)
                pr = [abs(r[j])*v[j]/max(abs(ay[j]), 1.0) for j in w]
                push!(E, (kind = :lift, side, file = basename(fn), t = k/60, v = v[k], g = abs(ay[k])/G,
                          yawratio = maximum(pr), βmax = maximum(β(j) for j in w), dv = 3.6*(v[k] - v[last(w)]),
                          spin = maximum(β(j) for j in w) > 20))
                k += 180; continue
            end
            k += 1
        end
    end
    E
end

"""Settle the sim car on a circle at speed V and lateral g, then run `action` (:power ramp seconds / :lift)."""
function sim_event(car, sp, u0, V, gt, dir; kind, thr0 = 0.4, ramp = 3.0)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay])
    reinit!(car.integ, copy(u0))
    g = findfirst(i -> V/DriveRT3D.RW_R*sp.gear_ratios[i]*sp.final_drive*60/2π < 8200, 1:5)
    car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
    car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
    δ = 0.0; ie = 0.0; thr = 0.3
    for n in 1:9*60                                              # settle: PI throttle on speed, I steer on lateral g
        u, v, r, ay = get(car.integ)
        δ = clamp(δ + 0.004*(gt*G - abs(ay))/G, 0.0, 0.25)
        thr = clamp(0.3 + 0.3*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.4, 0.7)
        DriveRT3D.step_car3d!(car, thr, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
    end
    u, v, r, ay = get(car.integ); v0 = u
    if kind === :power
        letgo = NaN; spin = false; th = min(thr, thr0)
        for n in 1:round(Int, (ramp + 3)*60)
            th = min(1.0, th + (1 - thr0)/(ramp*60))
            DriveRT3D.step_car3d!(car, th, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            u, v, r, ay = get(car.integ); b = rad2deg(abs(atan(v, max(u, 1.0))))
            isnan(letgo) && b > 6 && (letgo = th); b > 20 && (spin = true; break)
        end
        (letgo = letgo, spin = spin)
    else
        yr = 0.0; bm = 0.0
        for n in 1:150
            DriveRT3D.step_car3d!(car, 0.0, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
            u, v, r, ay = get(car.integ)
            yr = max(yr, abs(r)*u/max(abs(ay), 1.0)); bm = max(bm, rad2deg(abs(atan(v, max(u, 1.0)))))
            bm > 30 && break
        end
        (yawratio = yr, βmax = bm, dv = 3.6*(v0 - get(car.integ)[1]), spin = bm > 20)
    end
end

function main()
    E = gold_events()
    cars = Dict{Symbol,Any}()
    for k in (:default, :ww)
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0)
        cars[k] = (car, sp, copy(car.integ.u), DriveRT3D.describe_chassis())
    end
    for k in (:default, :ww); println("$k: ", cars[k][4]); end
    println("\nB3 POWER-ON (squeeze to full on a ~1 g circle): throttle at let-go (|β| > 6°), spin (|β| > 20°)")
    println("   side     file                                    t s   km/h   g    | gold: from  ramp s  let-go  spin | sim: let-go  spin")
    for e in E
        e.kind === :power || continue
        car, sp, u0, _ = cars[e.side]
        s = sim_event(car, sp, u0, e.v, min(e.g, 1.15), 1.0; kind = :power, thr0 = e.thr0, ramp = max(e.ramp, 0.5))
        @printf("   %-8s %-40s %5.1f  %4.0f  %.2f  |       %.2f   %4.1f    %4.2f   %-5s|       %4.2f  %s\n", e.side, e.file, e.t,
                3.6e.v, e.g, e.thr0, e.ramp, e.letgo, e.spin, s.letgo, s.spin)
    end
    println("\nB4 LIFT-OFF (snap shut at 1.0-1.2 g, wheel held 2.5 s): peak yaw/path rate, peak |β|, speed lost")
    println("   side     file                                    t s   km/h   g    | gold: yaw/path  β°   -km/h spin | sim: yaw/path  β°   -km/h spin")
    for e in E
        e.kind === :lift || continue
        car, sp, u0, _ = cars[e.side]
        s = sim_event(car, sp, u0, e.v, min(e.g, 1.15), 1.0; kind = :lift)
        @printf("   %-8s %-40s %5.1f  %4.0f  %.2f  |       %4.2f   %5.1f  %4.0f  %-5s|       %4.2f   %5.1f  %4.0f  %s\n", e.side, e.file, e.t,
                3.6e.v, e.g, e.yawratio, e.βmax, e.dv, e.spin, s.yawratio, s.βmax, s.dv, s.spin)
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
