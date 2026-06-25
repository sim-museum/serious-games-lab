# flugplatz_bench.jl — drive the full-3D Lotus 49 (JM_3D physics) over the real GPL
# Nürburgring Flugplatz crest, headless, and benchmark the jump vs the iRacing gold.
#
# Loads the real nurburg road terrain (HAT) + .trk centreline, finds the steepest
# jump crest, spawns the 3-D car on the racing line ~250 m before it at the iRacing
# approach speed, drives it through with a pure-pursuit centreline follower at full
# throttle, captures iRacing-format telemetry → writes an .ibt and prints the
# airborne signature (airtime, crest/landing VertAccel, ride-height droop, scrub).
#
#   julia -t1 --project=. flugplatz_bench.jl            # auto-picks the steepest crest
#   FLUG_CREST=2 julia … flugplatz_bench.jl             # pick the Nth crest candidate
#   FLUG_V=60 …                                          # approach speed [m/s]

using Printf, Dates, LinearAlgebra
using JuliaMotor
include("gpl3do.jl");  using .GPL3DO
include("gpltrack.jl"); using .GPLTrack
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt3d.jl"); using .DriveRT3D
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/ibt.jl"); using .IBT

const ZD = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks/nurburg"
const G = 9.80665

# --- align the .trk centreline onto the road HAT (same logic as the app) ---
function align_centreline(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return cl
    xs = Float64[]; zs = Float64[]
    for tr in hat.tris, p in (tr.a, tr.b, tr.c); push!(xs, p[1]); push!(zs, p[3]); end
    dx0 = (minimum(xs)+maximum(xs))/2 - (minimum(p[1] for p in cl)+maximum(p[1] for p in cl))/2
    dz0 = (minimum(zs)+maximum(zs))/2 - (minimum(p[2] for p in cl)+maximum(p[2] for p in cl))/2
    best = (cov(dx0, dz0), dx0, dz0)
    for dx in dx0-400:40:dx0+400, dz in dz0-400:40:dz0+400
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    for dx in best[2]-40:8:best[2]+40, dz in best[3]-40:8:best[3]+40
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    [(p[1]+best[2], p[2]+best[3]) for p in cl]
end

print("loading nurburg road terrain + centreline… "); flush(stdout)
mesh    = GPL3DO.parse_3do(joinpath(ZD, "nurburg.3do"))
TERRAIN = GPLTrack.build_hat(mesh)
cl0     = GPLTrack.trk_centreline(joinpath(ZD, "nurburg.trk"))
CL      = align_centreline(cl0, TERRAIN)
println(length(CL), " centreline pts")
groundz(x, z) = (h = JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(z); ref=Inf); h[3] ? Float64(h[1]) : NaN)

# --- elevation profile + cumulative distance along the racing line ---
N = length(CL)
elev = [groundz(p...) for p in CL]
dist = zeros(N); for i in 2:N; dist[i] = dist[i-1] + hypot(CL[i][1]-CL[i-1][1], CL[i][2]-CL[i-1][2]); end
ok(i) = isfinite(elev[i])

# crest = local elevation peak with a steep drop over the next ~50 m; score by drop·steepness
ahead(i, d) = (j=i; while j<N && dist[j]-dist[i]<d; j+=1; end; j)
cands = NamedTuple[]
for i in 8:N-8
    ok(i) || continue
    j = ahead(i, 55.0); (ok(j) && dist[j]-dist[i] > 30) || continue
    drop = elev[i] - minimum(elev[k] for k in i:j if ok(k); init=elev[i])
    rise = elev[i] - minimum(elev[k] for k in max(1,i-8):i if ok(k); init=elev[i])
    drop > 2.0 && rise >= -0.3 && push!(cands, (i=i, s=dist[i], drop=drop, slope=drop/(dist[j]-dist[i])))
end
# keep the most prominent, well-separated crests
sort!(cands, by=c->-c.drop*c.slope)
sel = NamedTuple[]; for c in cands; all(abs(c.s-s.s)>300 for s in sel) && push!(sel, c); length(sel)>=6 && break; end
println("\n  top jump-crest candidates (GPL Nordschleife road profile):")
for (k,c) in enumerate(sel)
    @printf("   [%d] lapdist %5.0f m  drop %4.1f m over 55 m  (slope %.1f%%)\n", k, c.s, c.drop, 100*c.slope)
end
# pure-pursuit centreline follower (keeps the car on the racing line)
nearest(x,z) = argmin([hypot(x-CL[i][1], z-CL[i][2]) for i in 1:N])
wrapπ(a) = a > π ? a-2π : a < -π ? a+2π : a
function steer_to(x, z, θ)
    i0 = nearest(x, z); look = ahead(i0, 22.0)
    des = atan(CL[look][2]-z, CL[look][1]-x)
    clamp(wrapπ(des - θ) / 0.30 * 1.2, -1, 1)
end

V0 = parse(Float64, get(ENV, "FLUG_V", "60.0"))           # approach speed [m/s] (~216 km/h)

"Drive the 3-D car flat-out over one crest; return jump metrics + telemetry samples."
function drive_crest(crest; verbose=false)
    sp = something(findlast(i -> dist[i] <= crest.s - 250, 1:crest.i), 2)
    θ0 = atan(CL[sp+1][2]-CL[sp][2], CL[sp+1][1]-CL[sp][1])
    c = DriveRT3D.build_car3d(; x0=CL[sp][1], z0=CL[sp][2], θ0=θ0, v0=V0, y0=groundz(CL[sp]...))
    c.gear = 5; c.s_gr(c.integ, DriveRT3D.GEARS[5]); c.s_we(c.integ, (V0/0.33)*DriveRT3D.GEARS[5]*DriveRT3D.FINAL)
    samples = Dict{String,Float64}[]
    dt = 1/60; tt = 0.0; air_t=0.0; air0=0.0; air1=0.0; maxaz=0.0; minaz=9.9
    v_take=0.0; rhmax=0.0; lastair=false; airborne_seen=false
    verbose && println("  t(s)  km/h  VertAccel  pitch°  RH_F(mm)  note")
    for i in 1:540
        tt += dt
        s = DriveRT3D.step_car3d!(c, 1.0, 0.0, steer_to(c.x,c.z,c.θ), dt; manual=true, groundz=groundz)
        az = s.vacc/G; rhF = (s.rh[1]+s.rh[2])/2*1000
        maxaz=max(maxaz,az); minaz=min(minaz,az); rhmax=max(rhmax,rhF)
        air = az < 0.5
        if air && !lastair && !airborne_seen; air0=tt; v_take=s.v; airborne_seen=true; end
        if !air && lastair && airborne_seen && air1==0.0 && tt>air0+0.05; air1=tt; end
        air && (air_t += dt)
        tl = DriveRT3D.telemetry3d(c)
        push!(samples, Dict{String,Float64}(
            "SessionTime"=>tt, "SessionTick"=>Float64(i), "IsOnTrack"=>1.0,
            "Speed"=>s.v, "RPM"=>s.rpm, "Gear"=>Float64(s.gear),
            "Throttle"=>1.0, "Brake"=>0.0, "Clutch"=>1.0, "SteeringWheelAngle"=>steer_to(c.x,c.z,c.θ)*0.30,
            "Yaw"=>s.θ, "YawRate"=>tl.r, "VelocityX"=>tl.u, "VelocityY"=>tl.v, "VelocityZ"=>0.0,
            "LongAccel"=>tl.ax, "LatAccel"=>tl.ay, "VertAccel"=>s.vacc,
            "LFrideHeight"=>s.rh[1], "RFrideHeight"=>s.rh[2], "LRrideHeight"=>s.rh[3], "RRrideHeight"=>s.rh[4],
            "Pitch"=>s.pitch, "Roll"=>s.roll, "Alt"=>s.y,
            "LFspeed"=>tl.ωf*0.30, "RFspeed"=>tl.ωf*0.30, "LRspeed"=>tl.ωr*0.33, "RRspeed"=>tl.ωr*0.33))
        if verbose && (air || az>1.4 || i%30==0)
            @printf("  %4.2f  %4.0f   %+5.2f g   %+5.1f   %5.0f   %s\n", tt, s.v*3.6, az, rad2deg(s.pitch), rhF,
                    air ? "AIRBORNE" : (az>1.4 ? "LANDING" : ""))
        end
        lastair = air
    end
    airtime = air1>air0 ? air1-air0 : air_t
    li = clamp(round(Int, (air1>0 ? air1 : air0)*60)+1, 1, length(samples))
    ai = clamp(round(Int, ((air1>0 ? air1 : air0)+1.5)*60)+1, 1, length(samples))
    (airtime=airtime, v_take=v_take, minaz=minaz, maxaz=maxaz, rhmax=rhmax,
     v_land=samples[li]["Speed"], v_after=samples[ai]["Speed"], samples=samples)
end

# --- sweep the candidate crests; find the one matching the iRacing Flugplatz (~0.5 s air) ---
println("\n  sweeping ", length(sel), " crests (flat-out @ ", round(V0*3.6), " km/h, full-3D)…")
println("  crest  lapdist  drop   airtime  takeoff  crest_g  land_g  scrub(km/h/1.5s)")
results = []
for (k,cr) in enumerate(sel)
    r = drive_crest(cr)
    push!(results, (k=k, cr=cr, r=r))
    @printf("   [%d]   %5.0f m  %4.1fm  %5.2f s   %3.0f     %+.2f g  %+.2f g   %.0f→%.0f (%.0f)\n",
            k, cr.s, cr.drop, r.airtime, r.v_take*3.6, r.minaz, r.maxaz, r.v_land*3.6, r.v_after*3.6,
            r.v_land*3.6-r.v_after*3.6)
end
# pick the crest whose airtime is closest to the iRacing Flugplatz (~0.48 s)
best = argmin([abs(x.r.airtime - 0.48) for x in results])
B = results[best]
println("\n  ───── JM Flugplatz benchmark — best match = crest [", B.k, "] @ lapdist ",
        round(Int,B.cr.s), " m ─────")
@printf("  airtime %.2f s   takeoff %.0f km/h   crest VertAccel %.2f g → landing %.2f g   scrub %.0f km/h/1.5s\n",
        B.r.airtime, B.r.v_take*3.6, B.r.minaz, B.r.maxaz, (B.r.v_land-B.r.v_after)*3.6)
println("  iRacing gold:  0.42–0.53 s   213–221 km/h        −0.10 g       +1.8 g       ~42 km/h/1.5s")

# --- write the best run's .ibt (iRacing nurburgring template) ---
try
    tmpl = ibt_open("/home/g/sgl/THU/rFactor/juliaMotor/data/iracing/lotus49_nurburgring nordschleife 2026-06-14 11-11-37.ibt")
    ts = Dates.format(Dates.now(), "yyyy-mm-dd HH-MM-SS")
    out = "/home/g/sgl/THU/rFactor/juliaMotor/data/juliaracer/lotus49_nurburgring nordschleife $(ts).ibt"
    write_ibt(out, tmpl, B.r.samples)
    println("\n  wrote best-run .ibt: ", basename(out), "  (", length(B.r.samples), " ticks)")
catch e; println("\n  .ibt write failed: ", e); end
