# flugplatz_real_bench.jl — benchmark the JM full-3D jump on the REAL iRacing
# Flugplatz crest profile (not a GPL crest).  Reconstructs the road elevation
# profile from an iRacing Flugplatz .ibt (Alt follows the road while on the ground;
# the airborne gap is bridged by interpolation), then drives the JM 3-D Lotus 49
# straight over that exact crest at the iRacing approach speed and compares.
#
#   julia -t1 --project=. flugplatz_real_bench.jl
#   IR_FILE="…/lotus49_nurburgring … .ibt"  to pick a different iRacing run.

using Printf, Dates
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/ibt.jl"); using .IBT
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt3d.jl"); using .DriveRT3D
const G = 9.80665

IRF = get(ENV, "IR_FILE",
    "/home/g/sgl/THU/rFactor/juliaMotor/data/iracing/2026-06-24/lotus49_nurburgring nordschleife 2026-06-24 15-59-43.ibt")
ir = ibt_open(IRF)
dt_ir = 1.0/ir.tickRate
spd = channel(ir, "Speed"); alt = channel(ir, "Alt"); vacc = channel(ir, "VertAccel")
n = length(spd)
fin(x) = isfinite(x)

# --- find the jump: longest airborne run (VertAccel well below 1 g) ---
air = [fin(vacc[i]) && vacc[i] < 5.0 for i in 1:n]
best=(0,0,0); i=1
while i<=n
    if air[i]; j=i; while j<=n && air[j]; j+=1; end; (j-i>best[1]) && (global best=(j-i,i,j-1)); global i=j
    else; global i+=1; end
end
(jair, j0, j1) = best
@printf("\n  iRacing %s\n  jump airborne %.2f s @ t=%.1f–%.1f s\n",
        basename(IRF), jair*dt_ir, j0*dt_ir, j1*dt_ir)

# --- window around the jump; reconstruct road elevation vs distance ---
w0 = max(1, j0 - round(Int, 2.0/dt_ir)); w1 = min(n, j1 + round(Int, 2.5/dt_ir))
s = zeros(n); for i in 2:n; s[i] = s[i-1] + (fin(spd[i]) ? spd[i] : 0.0)*dt_ir; end   # distance travelled
# road knots = ON-GROUND samples (Alt ≈ road); the airborne gap is bridged by the
# linear interp between the last pre-jump and first post-jump knot.
knot_s = Float64[]; knot_z = Float64[]; z0ref = alt[w0]
for i in w0:w1
    (fin(alt[i]) && !air[i]) || continue
    push!(knot_s, s[i] - s[w0]); push!(knot_z, alt[i] - z0ref)
end
smax = knot_s[end]
# linear interp of the sparse on-ground knots (this bridges the airborne gap by a chord)
function rawinterp(ds)
    ds <= knot_s[1] && return knot_z[1]; ds >= smax && return knot_z[end]
    k = clamp(searchsortedlast(knot_s, ds), 1, length(knot_s)-1)
    f = (ds - knot_s[k]) / (knot_s[k+1] - knot_s[k] + 1e-9)
    knot_z[k]*(1-f) + knot_z[k+1]*f
end
# dense grid + heavy low-pass: real roads are SMOOTH, but sparse on-ground knots plus the
# linear gap-fill leave a sharp corner at the brow that would kick the car off unphysically.
# A ~16 m moving average rounds the crest to a realistic radius.
grid = collect(0.0:0.5:smax); dz = rawinterp.(grid)
half = round(Int, parse(Float64, get(ENV, "CREST_SMOOTH", "8.0")) / 0.5)   # ± metres of moving average
zsm = [sum(@view dz[max(1,k-half):min(length(dz),k+half)]) / length(max(1,k-half):min(length(dz),k+half))
       for k in eachindex(dz)]
function profile(ds)
    ds <= 0 && return zsm[1]; ds >= smax && return zsm[end]
    k = clamp(Int(floor(ds/0.5))+1, 1, length(zsm)-1)
    zsm[k]*(1 - (ds-grid[k])/0.5) + zsm[k+1]*((ds-grid[k])/0.5)
end
# crest = peak road elevation just before takeoff; report its drop to the landing zone
s_take = s[j0]-s[w0]; s_land = s[j1]-s[w0]
z_take = profile(s_take); z_land = profile(s_land)
@printf("  reconstructed crest: takeoff @ %.0f m (elev %+.1f m) → landing @ %.0f m (elev %+.1f m), Δ %.1f m over %.0f m\n",
        s_take, z_take, s_land, z_land, z_take-z_land, s_land-s_take)
@printf("  iRacing takeoff speed %.0f km/h\n", spd[j0]*3.6)

# --- drive the JM 3-D car straight over the reconstructed real crest ---
groundz(x, z) = profile(Float64(x))                     # straight run along +x: distance = x
spawn_s = max(0.0, s_take - 130.0)                      # ~130 m before the brow
V0 = spd[max(1, j0 - round(Int,2.2/dt_ir))] |> x->fin(x) ? x : 60.0   # iRacing speed ~2.2 s before takeoff
c = DriveRT3D.build_car3d(; x0=spawn_s, z0=0.0, θ0=0.0, v0=V0, y0=profile(spawn_s))
c.gear = 5; c.s_gr(c.integ, DriveRT3D.GEARS[5]); c.s_we(c.integ, (V0/0.33)*DriveRT3D.GEARS[5]*DriveRT3D.FINAL)

dt = 1/60; tt=0.0; air_t=0.0; a0=0.0; a1=0.0; maxaz=0.0; minaz=9.9; vtake=0.0; seen=false; lastair=false
samples = Dict{String,Float64}[]
println("\n  JM 3-D over the real crest:  t(s)  km/h  VertAccel  note")
for i in 1:600
    global tt += dt
    s_now = DriveRT3D.step_car3d!(c, 1.0, 0.0, 0.0, dt; manual=true, groundz=groundz)
    az = s_now.vacc/G
    global maxaz=max(maxaz,az); global minaz=min(minaz,az)
    a = az < 0.5
    if a && !lastair && !seen; global a0=tt; global vtake=s_now.v; global seen=true; end
    if !a && lastair && seen && a1==0.0 && tt>a0+0.05; global a1=tt; end
    a && (global air_t += dt)
    tl = DriveRT3D.telemetry3d(c)
    push!(samples, Dict{String,Float64}("SessionTime"=>tt,"SessionTick"=>Float64(i),"IsOnTrack"=>1.0,
        "Speed"=>s_now.v,"RPM"=>s_now.rpm,"Gear"=>5.0,"Throttle"=>1.0,"Brake"=>0.0,"Clutch"=>1.0,
        "SteeringWheelAngle"=>0.0,"Yaw"=>s_now.θ,"YawRate"=>tl.r,"VelocityX"=>tl.u,"VelocityY"=>tl.v,"VelocityZ"=>0.0,
        "LongAccel"=>tl.ax,"LatAccel"=>tl.ay,"VertAccel"=>s_now.vacc,
        "LFrideHeight"=>s_now.rh[1],"RFrideHeight"=>s_now.rh[2],"LRrideHeight"=>s_now.rh[3],"RRrideHeight"=>s_now.rh[4],
        "Pitch"=>s_now.pitch,"Roll"=>s_now.roll,"Alt"=>s_now.y,
        "LFspeed"=>tl.ωf*0.30,"RFspeed"=>tl.ωf*0.30,"LRspeed"=>tl.ωr*0.33,"RRspeed"=>tl.ωr*0.33))
    if a || az>1.4 || i%45==0
        @printf("                               %4.2f  %4.0f   %+5.2f g   %s\n",
                tt, s_now.v*3.6, az, a ? "AIRBORNE" : (az>1.4 ? "LANDING" : ""))
    end
    global lastair = a
    c.x > spawn_s + smax - 5 && break
end
airtime = a1>a0 ? a1-a0 : air_t
li = clamp(round(Int,(a1>0 ? a1 : a0)*60)+1, 1, length(samples))
ai = clamp(round(Int,((a1>0 ? a1 : a0)+1.5)*60)+1, 1, length(samples))

# --- iRacing ground truth for the same crest ---
ir_land = maximum(vacc[j1:min(n,j1+round(Int,1.0/dt_ir))])/G
ir_after = spd[min(n, j1+round(Int,1.5/dt_ir))]
println("\n  ─────────────── Flugplatz on the REAL iRacing crest ───────────────")
@printf("  %-10s  airtime   takeoff    crest_g   landing_g   scrub(km/h/1.5s)\n", "")
@printf("  %-10s  %.2f s    %3.0f km/h   %+.2f g    %+.2f g      %.0f\n",
        "iRacing", jair*dt_ir, spd[j0]*3.6, minimum(vacc[j0:j1])/G, ir_land, spd[j1]*3.6 - ir_after*3.6)
@printf("  %-10s  %.2f s    %3.0f km/h   %+.2f g    %+.2f g      %.0f\n",
        "JM 3-D", airtime, vtake*3.6, minaz, maxaz, samples[li]["Speed"]*3.6 - samples[ai]["Speed"]*3.6)

try
    tmpl = ibt_open("/home/g/sgl/THU/rFactor/juliaMotor/data/iracing/lotus49_nurburgring nordschleife 2026-06-14 11-11-37.ibt")
    ts = Dates.format(Dates.now(), "yyyy-mm-dd HH-MM-SS")
    out = "/home/g/sgl/THU/rFactor/juliaMotor/data/juliaracer/lotus49_nurburgring nordschleife $(ts).ibt"
    write_ibt(out, tmpl, samples); println("\n  wrote JM .ibt: ", basename(out), "  (", length(samples), " ticks)")
catch e; println("\n  .ibt write failed: ", e); end
