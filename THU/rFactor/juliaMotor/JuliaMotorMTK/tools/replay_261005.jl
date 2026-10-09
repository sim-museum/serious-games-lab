# TYRE-2 S2: replay the gold's power-on and lift-off events through the sim car WITH THE GOLD'S OWN INPUTS.
#
# tools/wwtrans_261005.jl abstracts each event (a 6 s throttle ramp, the lowest gear under 8,200 rpm), and that is not
# what the driver did: the default's let-go at 789.9 s is 4th gear at ~4,500 rpm, the throttle SNAPPED 0.3 -> 1.0 in
# half a second, rear wheel slip 3 % -> 27 % in a second, the inside rear spinning up (ρ -13), then the spin.
# Here: the event's own session car (springs, gearbox, mass, chassis), settled on the event's circle at its speed and
# lateral g IN THE GOLD'S GEAR (rate-limited settle), then for up to 6 s the gold's throttle and the gold's steering
# CHANGES (δ_sim = δ_settled + δ_gold(t) − δ_gold(t0)), gear held, for JM_REPLAY_SECS (9). Compared, gold vs sim, every 0.25 s: lateral g,
# sideslip β, rear slip angle, rear wheel slip κ (mean rear wheel speed / ground speed − 1), the diff split ρ.
#
#   julia --project=. tools/replay_261005.jl                 (every B3/B4 event wwtrans finds)
#   JM_REPLAY_ONLY="14-36-48:789.9"                          (one event: file stem fragment and t)
using Printf, Statistics
include(joinpath(@__DIR__, "wwtrans_261005.jl"))             # gold_events, install!, FILES, ch, DriveRT3D

function goldtrace(fn, k0, n)
    f = ibt_open(fn); sp = setup_params(f.yaml)
    c = Dict(x => ch(f, x) for x in ("Speed","VelocityX","VelocityY","YawRate","LatAccel","LongAccel","Throttle","Brake",
                                     "SteeringWheelAngle","LRspeed","RRspeed","Gear","RPM"))
    b = (setup_params(f.yaml).corner_weight_N |> cw -> (cw[:LF] + cw[:RF])/sum(values(cw)))*LWB
    ks = k0:min(f.nrows, k0 + n)
    (sp = sp, thr = c["Throttle"][ks], brk = c["Brake"][ks], δ = c["SteeringWheelAngle"][ks] ./ sp.steering_ratio, gear = Int(c["Gear"][k0]),
     amag = [hypot(c["LatAccel"][k], c["LongAccel"][k])/G for k in ks], spd = c["Speed"][ks],
     v = c["Speed"][k0], g = abs(c["LatAccel"][k0])/G, dir = sign(c["LatAccel"][k0]),
     β = [rad2deg(atan(c["VelocityY"][k], c["VelocityX"][k])) for k in ks],
     ay = c["LatAccel"][ks] ./ G,
     αr = [rad2deg(-atan(c["VelocityY"][k] - b*c["YawRate"][k], c["VelocityX"][k])) for k in ks],
     κ = [((c["LRspeed"][k] + c["RRspeed"][k])/2)/max(c["Speed"][k], 1) - 1 for k in ks],
     ρ = [abs(c["YawRate"][k]) > 0.1 ? (c["RRspeed"][k] - c["LRspeed"][k])/(c["YawRate"][k]*1.5) : NaN for k in ks])
end

"""Put the session car on the event's circle at its speed and lateral g in the gold's gear; returns the settled road
steer angle (sign: the event's direction). Rate-limited I steer on g, PI throttle on speed, 10 s."""
function settle!(car, sp, u0, gt)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay])
    V = gt.v; g = max(gt.gear, 1)
    reinit!(car.integ, copy(u0)); car.gear = g; car.s_gr(car.integ, sp.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
    car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[g]*sp.final_drive)
    δ = 0.02; ie = 0.0; dir = gt.dir; gtar = min(gt.g, 1.15)
    for k in 1:10*60                                          # settle: rate-limited I steer on g, PI throttle on speed
        u, v, r, ay = get(car.integ)
        δ = clamp(δ + clamp(0.004*(25/max(V, 25))^2*(gtar*G - abs(ay))/G, -0.0005, 0.0005), 0.0, 0.25)
        thr = clamp(0.3 + 0.3*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.4, 0.8)
        DriveRT3D.step_car3d!(car, thr, 0.0, dir*δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
    end
    dir*δ
end

function simreplay(car, sp, u0, gt, n)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r, sys.ay, sys.ωRL, sys.ωRR])
    b = ModelingToolkit.getp(sys, sys.b)(car.integ)
    δ0 = settle!(car, sp, u0, gt)
    out = NamedTuple[]
    for k in 1:n+1
        δk = δ0 + (gt.δ[k] - gt.δ[1])
        DriveRT3D.step_car3d!(car, gt.thr[k], 0.0, δk/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, r, ay, wl, wr = get(car.integ)
        push!(out, (β = rad2deg(atan(v, max(u, 1.0))), ay = ay/G, αr = rad2deg(-atan(v - b*r, max(u, 1.0))),
                    κ = (wl + wr)/2*DriveRT3D.RW_R/max(u, 1.0) - 1, ρ = abs(r) > 0.1 ? (wr - wl)*DriveRT3D.RW_R/(r*1.5) : NaN))
        abs(out[end].β) > 40 && break
    end
    out
end

function main()
    E = gold_events()
    only = get(ENV, "JM_REPLAY_ONLY", "")
    cars = Dict{Symbol,Any}()
    for k in (:default, :ww)
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0); cars[k] = (car, sp, copy(car.integ.u))
    end
    for e in E
        tag = "$(e.file[17:end-4]):$(round(e.t, digits = 1))"
        isempty(only) || occursin(split(only, ":")[1], e.file) && abs(e.t - parse(Float64, split(only, ":")[2])) < 0.2 || continue
        d = e.side === :default ? joinpath(D4, e.file) : joinpath(D5, e.file)
        isfile(d) || (d = joinpath(D5, e.file)); isfile(d) || (d = joinpath(D4, e.file))
        n = parse(Int, get(ENV, "JM_REPLAY_SECS", "9"))*60
        gt = goldtrace(d, round(Int, e.t*60), n)
        car, sp, u0 = cars[e.side]
        s = simreplay(car, sp, u0, gt, min(n, length(gt.thr) - 1))
        @printf("\n%s %-8s %s  gear %d  %.0f km/h  %.2f g  dir %+.0f\n", e.kind, e.side, tag, gt.gear, 3.6gt.v, gt.g, gt.dir)
        println("    t   thr  |  gold: g     β     αr    κ      ρ    |  sim: g     β     αr    κ      ρ")
        for k in 1:15:min(length(s), length(gt.thr))
            @printf("  %4.2f  %.2f | %6.2f %6.1f %6.1f %+.3f %6.2f | %6.2f %6.1f %6.1f %+.3f %6.2f\n", (k - 1)/60, gt.thr[k],
                    gt.dir*gt.ay[k], gt.dir*gt.β[k], gt.dir*gt.αr[k], gt.κ[k], gt.ρ[k], gt.dir*s[k].ay, gt.dir*s[k].β, gt.dir*s[k].αr, s[k].κ, s[k].ρ)
        end
        fg = findfirst(x -> abs(x) > 6, gt.β); fs = findfirst(x -> abs(x.β) > 6, s)
        @printf("  |β| > 6° at: gold %s s, sim %s s\n", fg === nothing ? "never" : @sprintf("%.2f", (fg-1)/60),
                fs === nothing ? "never" : @sprintf("%.2f", (fs-1)/60))
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
