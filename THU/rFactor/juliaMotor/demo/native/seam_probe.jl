# SEAM-1 probe: measure the TRACK-FRAME seams that both PO symptoms share (AI sideways skitter +
# player bounce at the same places). No GL, no sim, no eye -- geometry only.
#
# Three candidate seam sources, measured separately:
#   A. the (lapdist, lateral) map: JuliaMotor.hat(TrackSurface) projects onto a 3 m POLYLINE, so the
#      track frame is only C0 (and DISCONTINUOUS on the inside of a corner, where the nearest
#      segment switches). The .trk height spline is smooth, but it is evaluated at these coordinates.
#   B. trk_height's LATERAL interpolation is linear between traces -> cross-slope steps at each trace.
#   C. RaceAI.project returns the nearest NODE's s (3 m quantisation) and a lateral in that node's
#      frame -> the AI controller's own inputs step every ~3 m of travel.
include("gpldat.jl"); using .GPLDat
include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using JuliaMotor, Statistics, Printf

const WP = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
name = get(ENV, "GPLNAME", "watglen")
T = get(ENV, "TRACK", joinpath(WP, name)); name = basename(T)
dat = first(filter(f -> lowercase(basename(f)) == lowercase(name)*".dat", joinpath.(T, readdir(T))))
d = GPLDat.parse_dat(dat)
key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
tmp = tempname()*".trk"; write(tmp, d[key])

ta  = GPLTrack.trk_altitude(tmp)
cl  = GPLTrack.trk_centreline(tmp)
line = RaceAI.build_line(cl, (x,z) -> 0.0)
n = length(line.x)
@printf("track=%s  nodes=%d  ribbon lap=%.1f m  .trk lap=%.1f m  traces=%d\n",
        name, n, line.s[end] + hypot(line.x[1]-line.x[end], line.z[1]-line.z[end]), ta.total, length(ta.lat))
@printf("trace offsets [m]: %s\n", join((@sprintf("%.2f", l) for l in ta.lat), " "))

# --- the surface the sim asks: a TrackSurface whose node heights come from the .trk spline, so the
# ONLY defect left in the height field is the coordinate map (A), not the mesh.
sv = zeros(n)
for i in 2:n; sv[i] = sv[i-1] + hypot(line.x[i]-line.x[i-1], line.z[i]-line.z[i-1]); end
pos = [(line.x[i], GPLTrack.trk_height(ta, sv[i], 0.0), line.z[i]) for i in 1:n]
ts  = JuliaMotor.TrackSurface(pos; halfwidth = 9.0, cell = 25.0)

pct(v, p) = isempty(v) ? NaN : (sort!(v); v[clamp(ceil(Int, p*length(v)), 1, length(v))])

# ---------------- A + C: drive a SMOOTH path and watch the queries ----------------
# The path is the Catmull-Rom centreline at a constant lateral offset -- by construction smooth, and
# on a smooth surface a car on it would feel nothing.
v = parse(Float64, get(ENV, "JM_SEAM_V", "25.0")); dt = 1/60; LAT = parse(Float64, get(ENV, "JM_SEAM_LAT", "2.0"))
nstep = round(Int, ta.total / (v*dt))
hq = Float64[]; hs = Float64[]; ldq = Float64[]; latq = Float64[]
sp = Float64[]; latp = Float64[]; strq = Float64[]
xs = Float64[]; zs = Float64[]
for k in 0:nstep
    st = mod(k*v*dt, line.total)
    p = RaceAI.pose_at(line, st, LAT)
    push!(xs, p[1]); push!(zs, p[3])
    r = JuliaMotor.hat(ts, p[1], p[3])
    push!(ldq, r.lapdist); push!(latq, r.lateral)
    push!(hq, GPLTrack.trk_height(ta, r.lapdist, r.lateral))    # what the sim's road height does
    push!(hs, GPLTrack.trk_height(ta, st, LAT))                 # the same spline at the TRUE arc length
    ps, pl = RaceAI.project(line, p[1], p[3])
    push!(sp, ps); push!(latp, pl)
    thr, brk, str = RaceAI.controller(line, ps, pl, 0.0, v, p[1], p[3], p[4], v, 0.0)
    push!(strq, str)
end
# vertical velocity and its frame-to-frame step (the bounce: a step in w is an impulse).
# The lap WRAP frame is excluded: mod(s, total) there is the probe's own discontinuity, not the map's.
function steps_excl_wrap(h, ld, dt)
    out = Float64[]; idx = Int[]
    w = [(h[i+1]-h[i])/dt for i in 1:length(h)-1]
    for i in 1:length(w)-1
        (abs(ld[i+1]-ld[i]) > 5.0 || abs(ld[i+2]-ld[i+1]) > 5.0) && continue
        push!(out, abs(w[i+1]-w[i])); push!(idx, i)
    end
    (out, idx)
end
let (jq, iq) = steps_excl_wrap(hq, ldq, dt), (js, is) = steps_excl_wrap(hs, ldq, dt)
    @printf("\n[A] road height along a SMOOTH path (v=%.0f m/s, lat=%+.1f m, %d frames, wrap excluded)\n", v, LAT, length(hq))
    @printf("    vertical-velocity STEP per frame |dw| [m/s]:  polyline frame  p50 %.4f p99 %.4f max %.4f\n",
            pct(copy(jq),0.5), pct(copy(jq),0.99), maximum(jq))
    @printf("                                                  true arc length p50 %.4f p99 %.4f max %.4f\n",
            pct(copy(js),0.5), pct(copy(js),0.99), maximum(js))
    kw = iq[argmax(jq)]
    @printf("    worst polyline-frame step: %.3f m/s at s=%.1f m (x=%.1f z=%.1f)\n",
            maximum(jq), mod(kw*v*dt, line.total), xs[kw], zs[kw])
    # where are the spikes? compare the local centreline curvature at the worst 5%% against the lap
    thr = pct(copy(jq), 0.95)
    hot = [iq[i] for i in eachindex(jq) if jq[i] >= thr]
    kap(fr) = line.κ[clamp(searchsortedlast(line.s, mod(fr*v*dt, line.total)), 1, length(line.κ))]
    hotk = [kap(f) for f in hot]; allk = [kap(f) for f in iq]
    @printf("    curvature at the worst 5%% of steps: median %.4f /m (R=%.0f m) vs lap median %.4f /m (R=%.0f m)\n",
            median(hotk), 1/max(median(hotk),1e-6), median(allk), 1/max(median(allk),1e-6))
    # sanity: a step in lapdist that is not v*dt is the seam showing up in the COORDINATE
    dld2 = [abs(ldq[i+1]-ldq[i] - v*dt) for i in 1:length(ldq)-1 if abs(ldq[i+1]-ldq[i]) < 5.0]
    @printf("    |lapdist step - v*dt| [m]: p50 %.4f p99 %.4f max %.4f  (a perfect frame gives 0)\n",
            pct(copy(dld2),0.5), pct(copy(dld2),0.99), maximum(dld2))
end
# residual diagnostic: is what is LEFT node-locked (a seam) or smooth (the surface itself)?
# A seam repeats every node, i.e. every spacing/(v*dt) frames; a surface feature does not.
let d2 = [abs(ldq[i+2] - 2ldq[i+1] + ldq[i]) for i in 1:length(ldq)-2 if abs(ldq[i+1]-ldq[i]) < 5.0 && abs(ldq[i+2]-ldq[i+1]) < 5.0],
    w  = [(hq[i+1]-hq[i])/dt for i in 1:length(hq)-1],
    j  = [(abs(w[i+1]-w[i]), i) for i in 1:length(w)-1 if abs(ldq[i+1]-ldq[i]) < 5.0 && abs(ldq[i+2]-ldq[i+1]) < 5.0]
    sort!(j, rev=true)
    top = [x[2] for x in j[1:min(60,length(j))]]
    gaps = sort([top[i+1]-top[i] for i in 1:length(top)-1])
    nodefr = 3.0/(v*dt)
    @printf("    [residual] d2(lapdist) p99 %.5f max %.5f m;  worst-60 step frames: median gap %.1f frames (one node = %.1f)\n",
            pct(copy(d2),0.99), maximum(d2), isempty(gaps) ? NaN : median(abs.(gaps)), nodefr)
end

# ---------------- B: the lateral interpolation across traces ----------------
@printf("\n[B] cross-slope steps in trk_height's lateral interpolation\n")
function bscan(ta)
    worst = 0.0; wat = (0.0, 0.0); steps = Float64[]
    for s in range(0, ta.total, length = 400)
        for l in range(ta.lat[1]+0.05, ta.lat[end]-0.05, length = 2000)
            dl = 0.02
            k1 = (GPLTrack.trk_height(ta, s, l+dl) - GPLTrack.trk_height(ta, s, l)) / dl
            k0 = (GPLTrack.trk_height(ta, s, l) - GPLTrack.trk_height(ta, s, l-dl)) / dl
            push!(steps, abs(k1-k0))
            abs(k1-k0) > worst && (worst = abs(k1-k0); wat = (s, l))
        end
    end
    (worst, wat, steps)
end
# inside the ROAD (|lat| <= 5.49 m, the innermost traces) vs anywhere on the traces
function broad(ta, latmax)
    worst = 0.0; wat = (0.0, 0.0)
    for s in range(0, ta.total, length = 400)
        for l in range(-latmax, latmax, length = 600)
            dl = 0.02
            k1 = (GPLTrack.trk_height(ta, s, l+dl) - GPLTrack.trk_height(ta, s, l)) / dl
            k0 = (GPLTrack.trk_height(ta, s, l) - GPLTrack.trk_height(ta, s, l-dl)) / dl
            abs(k1-k0) > worst && (worst = abs(k1-k0); wat = (s, l))
        end
    end
    (worst, wat)
end
let (worst, wat, steps) = bscan(ta), (wr, war) = broad(ta, 5.0)
    @printf("    all traces: |d(cross-slope)| per 2 cm: p99 %.4f max %.4f at s=%.0f lat=%+.2f\n",
            pct(copy(steps),0.99), worst, wat[1], wat[2])
    @printf("    inside the road (|lat|<=5 m): max %.5f at s=%.0f lat=%+.2f -> at 1 m/s lateral, a %.4f m/s vertical step\n",
            wr, war[1], war[2], wr)
end

# ---------------- C: the AI's own inputs ----------------
dsp = [sp[i+1]-sp[i] for i in 1:length(sp)-1]
zero_steps = count(==(0.0), dsp)
@printf("\n[C] AI projection + controller along the same smooth path\n")
@printf("    RaceAI.project s step per frame [m] (expect %.3f): p50 %.3f max %.3f;  frames with NO advance: %d (%.1f%%)\n",
        v*dt, pct(copy(dsp),0.5), maximum(dsp), zero_steps, 100*zero_steps/length(dsp))
dlp = [abs(latp[i+1]-latp[i]) for i in 1:length(latp)-1]
@printf("    projected |lateral| step per frame [m]: p50 %.4f p99 %.4f max %.4f\n",
        pct(copy(dlp),0.5), pct(copy(dlp),0.99), maximum(dlp))
# window the steer stats to a stretch of the lap when asked (JM_SEAM_S0/JM_SEAM_S1) -- the
# look-ahead distance is only curvature-limited in a TIGHT corner, so a lap-wide statistic cannot
# see a change that only applies there.
S0 = parse(Float64, get(ENV, "JM_SEAM_S0", "-1")); S1 = parse(Float64, get(ENV, "JM_SEAM_S1", "-1"))
inwin(i) = S0 < 0 || (S0 <= mod(i*v*dt, line.total) <= S1)
dst = [abs(strq[i+1]-strq[i]) for i in 1:length(strq)-1 if inwin(i)]
# JERK: a staircase shows up in the SECOND difference of the command, where smooth cornering does
# not. This is the number that separates "the wheel is moving" from "the wheel is chattering".
djk = [abs(strq[i+2] - 2strq[i+1] + strq[i]) for i in 1:length(strq)-2 if inwin(i)]
@printf("    steer JERK |d2(steer)| per frame: p50 %.5f p99 %.5f max %.5f  (n=%d%s)\n",
        pct(copy(djk),0.5), pct(copy(djk),0.99), maximum(djk), length(djk),
        S0 < 0 ? "" : @sprintf(", s=%.0f..%.0f", S0, S1))
@printf("    commanded STEER step per frame (-1..1 full lock): p50 %.4f p99 %.4f max %.4f\n",
        pct(copy(dst),0.5), pct(copy(dst),0.99), maximum(dst))
@printf("    steer reversals (sign flips of the per-frame change): %d of %d frames (%.1f%%)\n",
        count(i -> (strq[i+1]-strq[i])*(strq[i+2]-strq[i+1]) < 0, 1:length(strq)-2), length(strq), 100*count(i -> (strq[i+1]-strq[i])*(strq[i+2]-strq[i+1]) < 0, 1:length(strq)-2)/length(strq))
# The look-ahead DISTANCE is sized from the curvature: la = clamp(min(6+0.35v, 0.32/kappa), 4, 20).
# Read per-node (kappa[_locate]) that is a staircase, so la steps at every node crossing and the
# look-ahead point with it. Measured both ways here; the lap-wide steer statistic cannot see it
# because the corners tight enough to limit la are the ones where the steer is already at full lock.
let lan = Float64[], lai = Float64[]
    for k in 0:nstep
        st = mod(k*v*dt, line.total)
        la0 = clamp(6.0 + v*0.35, 6.0, 20.0)
        kn = max(line.κ[RaceAI._locate(line, st)[1]], line.κ[RaceAI._locate(line, st + 0.5*la0)[1]], 1e-4)
        ki = max(RaceAI.curv_at(line, st), RaceAI.curv_at(line, st + 0.5*la0), 1e-4)
        push!(lan, clamp(min(la0, 0.32/kn), 4.0, 20.0))
        push!(lai, clamp(min(la0, 0.32/ki), 4.0, 20.0))
    end
    dn = [abs(lan[i+1]-lan[i]) for i in 1:length(lan)-1]
    di = [abs(lai[i+1]-lai[i]) for i in 1:length(lai)-1]
    dsx = [(abs(strq[i+1]-strq[i]), i) for i in 1:length(strq)-1]
    sort!(dsx, rev=true)
    @printf("    worst 3 steer steps at s = %s\n", join((@sprintf("%.0f m (%.4f)", mod((i-1)*v*dt, line.total), d) for (d,i) in dsx[1:3]), ", "))
    @printf("    look-ahead distance step per frame [m]: per-node kappa p99 %.4f max %.4f | interpolated p99 %.4f max %.4f\n",
            pct(copy(dn),0.99), maximum(dn), pct(copy(di),0.99), maximum(di))
end

# ---------------- D: the KINEMATIC AI's drawn pose (the shipped default AI) ----------------
# A rail-following AI is drawn at pose_at(line, s, lane) = CR(centreline) + lane * left-normal(theta),
# where theta is the APPROXIMATING chord tangent (TRACKSMOOTH-1). That tangent is piecewise linear in
# the node parameter, so its normal has a KINK at every node -- and a kink in POSITION is a step in
# VELOCITY, scaled by `lane`. TRACKSMOOTH-2 fixed the centreline position term (chord lerp -> CR);
# this is the lane term, which no fix has touched. Metric: the frame-to-frame step in the car's
# LATERAL velocity (the component across its own heading) at a constant lane -- the PO's "jump
# sideways" in the units a viewer sees.
function lane_kick(line, lane, v, dt)
    nstep = round(Int, line.total / (v*dt))
    px = Float64[]; pz = Float64[]; ph = Float64[]
    for k in 0:nstep
        p = RaceAI.pose_at(line, mod(k*v*dt, line.total), lane)
        push!(px, p[1]); push!(pz, p[3]); push!(ph, p[4])
    end
    vlat = Float64[]
    for i in 1:length(px)-1
        vx = (px[i+1]-px[i])/dt; vz = (pz[i+1]-pz[i])/dt
        push!(vlat, -vx*sin(ph[i]) + vz*cos(ph[i]))        # across the car's own heading
    end
    [abs(vlat[i+1]-vlat[i]) for i in 1:length(vlat)-1]
end
@printf("\n[D] kinematic AI drawn pose: step in LATERAL velocity per frame [m/s] (v=%.0f m/s)\n", v)
for lane in (0.0, 1.5, 3.0)
    k = lane_kick(line, lane, v, dt)
    @printf("    lane %+.1f m: p50 %.4f p99 %.4f max %.4f\n", lane, pct(copy(k),0.5), pct(copy(k),0.99), maximum(k))
end

# where do the [D] steps sit? (a lane-independent, wrap-sized kick is not the lane term)
let lane = 3.0, nstep = round(Int, line.total/(v*dt))
    px = Float64[]; pz = Float64[]; ph = Float64[]; ss = Float64[]
    for k in 0:nstep
        st = mod(k*v*dt, line.total); p = RaceAI.pose_at(line, st, lane)
        push!(px, p[1]); push!(pz, p[3]); push!(ph, p[4]); push!(ss, st)
    end
    vl = [(-(px[i+1]-px[i])/dt*sin(ph[i]) + (pz[i+1]-pz[i])/dt*cos(ph[i])) for i in 1:length(px)-1]
    jj = [(abs(vl[i+1]-vl[i]), i) for i in 1:length(vl)-1]; sort!(jj, rev=true)
    @printf("    worst 8 lateral-velocity steps at s = %s\n",
            join((@sprintf("%.0f(%.2f)", ss[i], d) for (d,i) in jj[1:8]), " "))
    # node spacing of the line, and the spacing of the worst-step locations
    ds = [line.s[i+1]-line.s[i] for i in 1:length(line.s)-1]
    @printf("    node spacing: min %.3f max %.3f m; wrap segment %.3f m\n",
            minimum(ds), maximum(ds), line.total - line.s[end])
end

# ---------------- E: the SHIPPED AI -- the kinematic field, stepped exactly as the sim steps it ----
# AI_PHYSICS is opt-in (nothing in the launcher sets it), so what the PO watches is step_field!: each
# car integrates its own arc length and its LANE is moved by the racecraft rules. A sideways jump
# here is a jump in `lane` (or in the drawn pose that follows from it), so measure both: the per-frame
# lane step, and the step in the drawn car's lateral velocity.
using Random
const SCALE = parse(Float64, get(ENV, "JM_SEAM_SCALE", "1.0"))
let n = 5
    Random.seed!(20260926)
    cars = RaceAI.init_cars(line, n)
    RaceAI.aistat_reset!()
    prevlane = [c.lane for c in cars]; prevrate = zeros(n)
    lastp = [RaceAI.pose_at(line, c.s, c.lane) for c in cars]
    lastv = [(0.0, 0.0) for _ in 1:n]; lasth = [p[4] for p in lastp]; lasts = [c.s for c in cars]
    lastdvl = Union{Nothing,Float64}[nothing for _ in 1:n]; jlat = Float64[]
    draterr = Float64[]; dvvec = Float64[]; dhdg = Float64[]; dscar = Float64[]; dvlat2 = Float64[]; dvfwd = Float64[]
    big = Tuple{Float64,Int,Float64,Float64,Float64}[]     # (|dv|, frame, dlane, ds, dheading)
    for f in 1:5400                                   # 90 s at 60 Hz, as the AI self-test does
        # player = nothing, NOT the (-1e9, ...) sentinel the sim's own self-test passes: the yield rule
        # computes mod(c.s - player[1] + total/2, total), so -1e9 aliases onto a REAL lap position and
        # the field spends the run swerving and braking for a phantom car. That artifact produced the
        # first version of these numbers (0.1 m lane steps at the 6 m/s yield rate, v *= 0.9 speed hits).
        poses, _ = RaceAI.step_field!(cars, line, dt; scale = SCALE, player = nothing, rel = Inf)
        for (i, p) in enumerate(poses)
            # (a) the LANE term on its own: the step in the lane's own rate (what SEAM-1's accel limit bounds)
            dl = cars[i].lane - prevlane[i]; rate = dl / dt
            f > 2 && push!(draterr, abs(rate - prevrate[i]))
            prevrate[i] = rate; prevlane[i] = cars[i].lane
            # (b) the DRAWN motion: the step in the velocity VECTOR (frame-independent, no heading in it)
            vx = (p[1]-lastp[i][1])/dt; vz = (p[3]-lastp[i][3])/dt
            dv = hypot(vx - lastv[i][1], vz - lastv[i][2])
            # decompose the velocity step along / across the car's own heading: a sideways JUMP and a
            # longitudinal jolt are different defects with different causes, and (b) alone cannot tell
            # them apart -- half of it turned out to be the cars' own acceleration.
            dvl = abs(-(vx - lastv[i][1])*sin(p[4]) + (vz - lastv[i][2])*cos(p[4]))
            dvf = abs( (vx - lastv[i][1])*cos(p[4]) + (vz - lastv[i][2])*sin(p[4]))
            if f > 2
                push!(dvlat2, dvl); push!(dvfwd, dvf)
                # JERK across the heading: a large but STEADY lateral acceleration is a car cornering
                # hard (the kinematic AI is not grip-limited in its drawn path); a DISCONTINUITY shows
                # up in the second difference. This is the number that says "jump", not "corner".
                lastdvl[i] === nothing || push!(jlat, abs(dvl - lastdvl[i]))
                lastdvl[i] = dvl
            end
            ds = mod(cars[i].s - lasts[i] + line.total/2, line.total) - line.total/2
            dh = abs(atan(sin(p[4]-lasth[i]), cos(p[4]-lasth[i])))
            if f > 2
                push!(dvvec, dv); push!(dhdg, dh); push!(dscar, abs(ds - lastv[i][1]*0.0 - cars[i].v*dt))
                dv > 0.5 && push!(big, (dv, f, abs(dl), abs(ds - cars[i].v*dt), dh))
            end
            lastv[i] = (vx, vz); lastp[i] = p; lasth[i] = p[4]; lasts[i] = cars[i].s
        end
    end
    @printf("\n[E] shipped (kinematic) AI field, %d cars x 90 s  (JM_AI_LANE_ACCEL=%s, pace scale %.2f)\n", n, get(ENV,"JM_AI_LANE_ACCEL","default"), SCALE)
    @printf("    (a) lane RATE step per frame [m/s]:      p50 %.4f p99 %.4f max %.4f\n",
            pct(copy(draterr),0.5), pct(copy(draterr),0.99), maximum(draterr))
    @printf("    (b) drawn velocity-VECTOR step [m/s]:    p50 %.4f p99 %.4f max %.4f  (>0.5: %d of %d)\n",
            pct(copy(dvvec),0.5), pct(copy(dvvec),0.99), maximum(dvvec), count(>(0.5), dvvec), length(dvvec))
    @printf("    (b1) ... of it ACROSS the heading [m/s]:  p50 %.4f p99 %.4f max %.4f  (>0.5: %d)\n",
            pct(copy(dvlat2),0.5), pct(copy(dvlat2),0.99), maximum(dvlat2), count(>(0.5), dvlat2))
    @printf("    (b2) ... and ALONG the heading [m/s]:     p50 %.4f p99 %.4f max %.4f  (>0.5: %d)\n",
            pct(copy(dvfwd),0.5), pct(copy(dvfwd),0.99), maximum(dvfwd), count(>(0.5), dvfwd))
    @printf("    (b3) JERK across the heading [m/s/frame]: p50 %.4f p99 %.4f max %.4f\n",
            pct(copy(jlat),0.5), pct(copy(jlat),0.99), maximum(jlat))
    @printf("    (c) drawn heading step per frame [deg]:  p50 %.4f p99 %.4f max %.4f\n",
            rad2deg(pct(copy(dhdg),0.5)), rad2deg(pct(copy(dhdg),0.99)), rad2deg(maximum(dhdg)))
    @printf("    (d) arc-length step minus v*dt [m]:      p99 %.4f max %.4f  (a teleport shows here)\n",
            pct(copy(dscar),0.99), maximum(dscar))
    a = RaceAI.AISTAT
    @printf("    racecraft events: engage=%d release=%d match=%d qsnap=%d sidepush=%d mishap=%d hardyield=%d\n",
            a.engage, a.release, a.match, a.qsnap, a.sidepush, a.mishap, a.hardyield)
    sort!(big, rev=true)
    isempty(big) || @printf("    worst 5 velocity steps (|dv|, frame, dlane, ds-vdt, dheading deg): %s\n",
        join((@sprintf("(%.2f f%d dl=%.3f ds=%.3f dh=%.2f)", b[1], b[2], b[3], b[4], rad2deg(b[5])) for b in big[1:min(5,end)]), " "))
end
