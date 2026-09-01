# RaceAI — GPL-style multi-rail opponents for the race mode.  Each AI tracks the
# centreline at a curvature-limited speed (slows for corners, runs out the straights)
# and — like GPL's AI — moves between three rails (race line / inside / outside) to
# PASS slower cars and EVADE both the other AI and the human's car, matching speed when
# it can't get by yet (so it never rams).  This is a kinematic gameplay AI (not the full
# physics model); see RACE_AI_NOTES.md for the physics/hybrid path.
module RaceAI

struct AILine
    x::Vector{Float64}; z::Vector{Float64}; y::Vector{Float64}
    s::Vector{Float64}                 # cumulative arc length [m] (along the CENTRELINE)
    θ::Vector{Float64}                 # centreline tangent heading [rad] (defines the lateral frame)
    κ::Vector{Float64}                 # curvature of the RACING LINE [1/m] (drives the corner-speed model)
    rl::Vector{Float64}                # racing-line lateral offset from the centreline [m] (out-in-out apexes)
    total::Float64                     # lap length [m]
end

wrapπ(a) = a > π ? a - 2π : a < -π ? a + 2π : a

"Build an AI racing line from centreline points `pts` (each (x,z) in physics frame)
and a `groundz(x,z)->y` elevation function.  Resamples to ~`spacing` m so tight corners are
well-represented (a coarse line is a polygon that the AI chord across = corner-cutting) and
the per-point curvature is accurate."
function build_line(pts, groundz; spacing = 3.0, halfwidth = 3.0)   # E16: racing-line band kept off the edges (apex ≥ ~a car-width inside the 5.5 m road)
    # arc-length resample the closed input polyline to ~`spacing` metres
    m = length(pts)
    cum = zeros(m+1); for i in 1:m; cum[i+1] = cum[i] + hypot(pts[i%m+1][1]-pts[i][1], pts[i%m+1][2]-pts[i][2]); end
    total = cum[m+1]; nfine = max(m, round(Int, total/spacing))
    fine = Vector{Tuple{Float64,Float64}}(undef, nfine)
    for k in 1:nfine
        d = (k-1)/nfine * total
        j = clamp(searchsortedlast(cum, d), 1, m); f = (d - cum[j]) / max(cum[j+1]-cum[j], 1e-9)
        a = pts[j]; b = pts[j%m+1]; fine[k] = (a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f)
    end
    pts = fine
    n = length(pts)
    x = Float64[p[1] for p in pts]; z = Float64[p[2] for p in pts]
    s = zeros(n); for i in 2:n; s[i] = s[i-1] + hypot(x[i]-x[i-1], z[i]-z[i-1]); end
    θ = [atan(z[i%n+1]-z[i], x[i%n+1]-x[i]) for i in 1:n]
    κ0 = zeros(n)
    for i in 1:n
        j = i % n + 1; ds = max(j == 1 ? (s[end]-s[i]) : (s[j]-s[i]), 0.5)
        κ0[i] = abs(wrapπ(θ[j]-θ[i])) / ds
    end
    # ---- RACING LINE: out-in-out apexes via curvature-minimising relaxation, kept within the
    # track band (±halfwidth of the centreline).  Pulling the line taut (Laplacian smoothing,
    # clamped to the band) makes it run wide into a corner, clip the inside at the apex and track
    # back out — the geometric "the line" of "Anatomy of a Corner" — instead of sitting on the
    # centreline (so the AI no longer apex-cut into the grass or sit on the outer edge mid-corner).
    rx = copy(x); rz = copy(z)
    nx = Float64[-sin(θ[i]) for i in 1:n]; nz = Float64[cos(θ[i]) for i in 1:n]   # left-normal
    # TAPER the apex band by curvature: at a TIGHT corner (hairpin, high κ) the inside edge is close,
    # so the full ±halfwidth apex offset reaches the inside GRASS (the Zandvoort T1/Tarzan apex-on-grass).
    # Shrink the band toward halfwidth/2 as the corner tightens (κ ≥ ~1/22 m ⇒ a real hairpin); fast
    # corners (low κ) keep the full band.  Smoothed so the line stays continuous.
    hwκ = [halfwidth * (1.0 - 0.5*clamp((κ0[i]-0.018)/0.045, 0.0, 1.0)) for i in 1:n]
    hw  = similar(hwκ); for i in 1:n; a=0.0; for d in -3:3; a += hwκ[mod(i-1+d,n)+1]; end; hw[i]=a/7; end
    for _ in 1:600
        for i in 1:n
            p = mod(i-2, n)+1; q = i % n + 1
            mx = 0.5*(rx[p]+rx[q]); mz = 0.5*(rz[p]+rz[q])
            rx[i] += 0.25*(mx-rx[i]); rz[i] += 0.25*(mz-rz[i])
            off = clamp((rx[i]-x[i])*nx[i] + (rz[i]-z[i])*nz[i], -hw[i], hw[i])   # stay on the road (curvature-tapered band)
            rx[i] = x[i] + off*nx[i]; rz[i] = z[i] + off*nz[i]
        end
    end
    rlg = Float64[(rx[i]-x[i])*nx[i] + (rz[i]-z[i])*nz[i] for i in 1:n]   # geometric (out-in-out) offset
    # APEX TYPE by corner: a bend that OPENS onto a faster section (slow-in/fast-out) wants a LATE
    # apex — sacrifice entry to get on the power early for the straight; a bend leading into a SLOWER
    # section (fast-in/slow-out) wants an EARLY apex.  Detect the speed trend through each corner and
    # shift its apex along the track (sample the offset from earlier s ⇒ the apex lands later).
    κg = zeros(n)                                          # geometric-line curvature (for the trend)
    for i in 1:n; j=i%n+1; ds=max(hypot(rx[j]-rx[i], rz[j]-rz[i]),0.5); κg[i]=abs(wrapπ(atan(rz[j]-rz[i],rx[j]-rx[i]) - atan(rz[i]-rz[mod(i-2,n)+1], rx[i]-rx[mod(i-2,n)+1])))/ds; end
    vp = [sqrt(8.0/max(κg[i], 1e-3)) for i in 1:n]         # corner-speed proxy
    W  = max(1, round(Int, 22/spacing))                   # ±22 m trend baseline
    sh = zeros(n)
    for i in 1:n
        κg[i] > 1/130 || continue                         # only in genuine corners
        trend = vp[mod(i-1+W,n)+1] - vp[mod(i-1-W,n)+1]   # faster ahead (+) ⇒ late, slower ahead (−) ⇒ early
        sh[i] = clamp(trend*0.18, -2.5, 2.5)              # apex shift in metres
    end
    shs = zeros(n)                                        # smooth the shift so the line stays continuous
    for i in 1:n; a=0.0; for d in -W:W; a += sh[mod(i-1+d,n)+1]; end; shs[i]=a/(2W+1); end
    di(arr, p) = (p=mod(p-1,n)+1; lo=floor(Int,p); f=p-lo; lo=mod(lo-1,n)+1; hi=mod(lo,n)+1; arr[lo]*(1-f)+arr[hi]*f)  # circular lerp
    rl = Float64[di(rlg, i - shs[i]/spacing) for i in 1:n]   # late: sample from earlier index ⇒ apex lands later
    rx = Float64[x[i] + rl[i]*nx[i] for i in 1:n]; rz = Float64[z[i] + rl[i]*nz[i] for i in 1:n]
    # curvature of the FINAL RACING LINE (smoother than the centreline → higher, more realistic corner
    # speeds where the line straightens the bend), smoothed over a ~9 m window
    θr = [atan(rz[i%n+1]-rz[i], rx[i%n+1]-rx[i]) for i in 1:n]
    κr = zeros(n)
    for i in 1:n
        j = i % n + 1; ds = max(hypot(rx[j]-rx[i], rz[j]-rz[i]), 0.5)
        κr[i] = abs(wrapπ(θr[j]-θr[i])) / ds
    end
    κ = zeros(n)
    for i in 1:n
        a = 0.0; for d in -2:2; a += κr[mod(i-1+d, n)+1]; end; κ[i] = a/5
    end
    y = Float64[(h = groundz(x[i], z[i]); isfinite(h) ? h : 0.0) for i in 1:n]
    AILine(x, z, y, s, θ, κ, rl, s[end])
end

"Racing-line lateral offset (m, left +) at arc-length `s`."
function racelane(line::AILine, s)
    i, f = _locate(line, s); j = i % length(line.rl) + 1
    line.rl[i]*(1-f) + line.rl[j]*f
end

mutable struct AICar; s::Float64; v::Float64; lap::Int; lane::Float64; tlane::Float64; spin::Float64; follow::Float64
    pace::Float64        # per-car PHYSICS pace factor (power/weight) — the Eagle out-paces the BRM (the field spreads)
    mishap::Float64      # remaining time (s) of a current off/spin mishap — drops the car right back, GPL-style
end
AICar(s, v, lap, lane) = AICar(s, v, lap, lane, lane, 0.0, 0.0, 1.0, 0.0)   # tlane=current lane; spin=collision yaw; follow=tailgate timer (s)

const RAIL     = 2.4    # pass-deviation offset to either side of the racing line (m)
const LANE_MAX = 3.8    # E16 (PO): never get within ~a car-width of either edge — road half-width 5.5 − car 1.7 = 3.8
# E12/G2 physics-AI anti-spin band (yaw rate rad/s): below SPIN_LO = normal cornering (controller
# unchanged); SPIN_LO→SPIN_HI ramps the slide-catch (ease line-chase, add counter-yaw, lift throttle).
const SPIN_LO  = parse(Float64, get(ENV, "JM_AI_SPIN_LO", "1.0"))
const SPIN_HI  = parse(Float64, get(ENV, "JM_AI_SPIN_HI", "3.0"))
const CAR_LEN  = 4.2    # car length (m) — single-file spacing + collision longitudinal extent
const CAR_WID  = 1.7    # car width (m) — collision lateral extent
# PO: the AI clumped because every car aimed for the SAME racing line (the same point in space) and so
# kept colliding.  Give each car a small PERSISTENT lane bias (its own slightly-offset preferred line),
# distinct per car, so the field naturally fans across the road instead of stacking on one groove.
const LANE_BIAS = parse(Float64, get(ENV, "JM_AI_LANE_BIAS", "0.7"))
lanebias(i, n) = n <= 1 ? 0.0 : LANE_BIAS * (2.0*((0.41*i) % 1.0) - 1.0)   # pseudo-random distinct offset per car

# Longitudinal physics so the AI ACCELERATE like cars (not slot cars): traction-limited
# off the line, power-limited + aero drag at speed → a natural build-up and top speed.
# E89-S2: GPL-style following. gpl_ai.ini [follow_line]: desired_dlong_sep = 14.0 m (13.5 in
# corners), avoidance keyed to time-to-collision, a pass initiated at straightaway_pass_dlong_sep =
# 10 m while closing at only 0.022 m/tick (0.8 m/s), and min_cornering_outside_pass_radius = 400 m.
# Our follower had NO gap control until it committed to a rail at gap < v+14 (80 m at 70 m/s) --
# it closed at full speed and then either speed-matched hard or was queued back a car length: the
# PO's "lunge ahead, then fall back". A/B switch only; the constants are GPL's, not tunables.
# DEFAULT ON (S2, 2026-08-30), JM_AI_GAPCTL=0 reverts. Measured headlessly on Monza, 4 cars, 270 s,
# with the GPL speed table: without it 505 queue-snaps (the trailing car teleported back a car
# length -- a visible jump); with it 0, rail switches 0.5 per car-lap, lunge-fall cycles 0.46.
const GAPCTL        = get(ENV, "JM_AI_GAPCTL", "1") != "0"
const GPL_DESIRED_SEP = 14.0      # m, desired_dlong_sep
# Time over which the excess gap is closed. Swept 1.5 / 3 / 5 / 8 s: 1.5 OSCILLATED (1.29 lunge-fall
# cycles per car-lap -- an underdamped follower hunting round the desired gap), 3 and 5 gave 0.46,
# 8 crept back up to 0.92 (too slow to close, the leader's braking zones catch it out). 4.0 sits in
# the flat part of that curve. A constant, not a knob: the sweep is recorded here so it need not be redone.
const GPL_CLOSE_TAU   = 4.0
const AI_MASS = 560.0; const AI_PMAX = 300_000.0   # ~Lotus 49: 560 kg, ~400 bhp
const AI_FMAX = 6800.0; const AI_DRAG = 0.42; const AI_BRAKE = 16.0   # traction N, ½ρ·CdA, brake m/s²
function advance_speed(v, vtarget, dt)
    if v < vtarget
        Fdrive = min(AI_FMAX, AI_PMAX / max(v, 8.0))       # power = force×speed → force falls off at speed
        a = (Fdrive - AI_DRAG*v*v) / AI_MASS               # minus aero drag
        min(v + a*dt, vtarget)
    else
        max(v - AI_BRAKE*dt, vtarget)                      # decel-limited braking
    end
end

"Grid of `n` AI cars staggered ~9 m apart behind arc-length `start_s`, alternating lanes."
init_cars(line::AILine, n; start_s = 0.0) =
    [AICar(mod(start_s - 9.0*i, line.total), 25.0, 0, iseven(i) ? 2.4 : -2.4, 0.0, 0.0, 0.0, 1.0, 0.0) for i in 1:n]  # tlane=0 = on the racing line; pace set by the app from car physics

function _locate(line::AILine, sq)
    sq = mod(sq, line.total)
    i = clamp(searchsortedlast(line.s, sq), 1, length(line.s)-1)
    f = (sq - line.s[i]) / max(line.s[i+1]-line.s[i], 1e-6)
    i, f
end

"World pose (x, y, z, heading) at arc-length `s` with lateral `lane` (left +)."
function pose_at(line::AILine, s, lane)
    i, f = _locate(line, s); j = i % length(line.x) + 1
    x = line.x[i]*(1-f) + line.x[j]*f
    z = line.z[i]*(1-f) + line.z[j]*f
    y = line.y[i]*(1-f) + line.y[j]*f
    θ = line.θ[i] + f*wrapπ(line.θ[j]-line.θ[i])
    # ⚠️ E104(a): `y` is the CENTRELINE's height and the lane offset moves only x and z. A car
    # running `lane` metres to the side is therefore posed at the centreline's height, which is
    # wrong by lane x cross-slope wherever the road is cambered. Callers that DRAW the pose must
    # put it back on the ground with `reground` below; callers that PLACE a car on the rail
    # (re-anchoring a stuck AI) deliberately want the line's own y.
    (x + lane*(-sin(θ)), y, z + lane*cos(θ), θ)             # lane offset (left = (-sinθ, cosθ))
end

"""    reground(p, height) -> pose

Return pose `p` with its height taken from the terrain AT THE POSE'S OWN (x, z), rather than from
the racing line's centreline. `height(x, z)` must return `(y, ok)`; when `ok` is false the pose is
returned UNCHANGED, because off the terrain there is no better answer than the line's.

This exists because `pose_at` offsets a car laterally without re-sampling the ground under it
(E104(a): AI cars measured up to 0.30 m off the terrain, median 0.09 m, while the player measured
0.00 m — the PO's "every car floats 20–40 cm above the road"). Every wheel inherits the error,
since wheels are drawn at `<car origin> + [wx, r, wz]`.

It lives HERE, in the module, rather than inline in `drive_native_mtk.jl`, so it can be tested:
that file launches the sim and cannot be loaded by a gate (E103-S2).
Accepts a 4-tuple or a 6-tuple (the draw path carries pitch/roll too).
"""
function reground(p, height)
    h = height(p[1], p[3])
    h[2] || return p
    length(p) >= 6 ? (p[1], h[1], p[3], p[4], p[5], p[6]) : (p[1], h[1], p[3], p[4])
end

"Project a world point onto the line → (arc-length s, signed lateral offset, left +)."
function project(line::AILine, x, z)
    bi = 1; bd = Inf
    @inbounds for i in 1:length(line.x)
        d = (line.x[i]-x)^2 + (line.z[i]-z)^2
        d < bd && (bd = d; bi = i)
    end
    lat = (x-line.x[bi])*(-sin(line.θ[bi])) + (z-line.z[bi])*cos(line.θ[bi])
    (line.s[bi], lat)
end

"Curvature-limited target speed at arc-length `s`, moving at `v` (m/s).  Scans a BRAKING
HORIZON ahead (∝ speed) for the tightest corner, so the car slows BEFORE a tight bend
instead of arriving too hot and washing out."
# E84/E89 (2026-08-30): GPL's OWN speed profile as the target, when the track supplies one.
# race.lp records sit at exactly 3.0 m dlong from the .trk start, index-aligned with this line on
# tracks that are not re-centred. Measured on Monza against it: the κ model's free lap is 122.9 s
# to GPL's 89.6, slower on 85% of the lap, with 147 speed steps >1 m/s per 3 m to GPL's 13 -- and
# inside the constant R=304 m Curva Grande our racing-line κ swings R=153..745, collapsing vtarget
# to 35 m/s where GPL carries 66. A lone car braking hard mid-corner and recovering IS "lunge
# ahead, then fall back". The GPL table has no such noise. Set by the app (JM_AI_GPLLINE);
# nothing = the κ model as before.
const GPLV = Ref{Union{Nothing,Vector{Float64}}}(nothing)
set_gpl_speeds!(v) = (GPLV[] = v === nothing ? nothing : Float64.(v); nothing)

# E84-S8: GPL's LATERAL tables too -- race.lp dlat as the racing line, pass1/pass2 dlat as the two
# rails (per record, asymmetric: on Monza the left rail is median +1.1 m from the line, the right
# -3.4 m). Same 3.0 m indexing as the speed table. Valid where align/recentre leave the .trk frame
# alone (Monza: align shift measured 0.0). Where set, the +/-LANE_MAX clamp is lifted for the
# line itself: GPL's dlat is on the road by construction, and our clamp forbade 30% of GPL's line.
const GPLLAT = Ref{Union{Nothing,NTuple{3,Vector{Float64}}}}(nothing)
set_gpl_lateral!(race, p1, p2) = (GPLLAT[] = race === nothing ? nothing : (Float64.(race), Float64.(p1), Float64.(p2)); nothing)
@inline _gidx(line::AILine, s, n) = mod(floor(Int, mod(s, line.total) / 3.0), n) + 1
"GPL race-line lateral at s, or `nothing` when no table is loaded."
gpl_racelane(line::AILine, s) = (g = GPLLAT[]; g === nothing ? nothing : g[1][_gidx(line, s, length(g[1]))])
"GPL rail offset from the race line at s for side +1 (left, pass1) / -1 (right, pass2); nothing without a table."
gpl_rail(line::AILine, s, side) = (g = GPLLAT[]; g === nothing ? nothing :
    (i = _gidx(line, s, length(g[1])); (side > 0 ? g[2][i] : g[3][i]) - g[1][i]))

function _vtarget(line::AILine, s, v; amax, vmax, vmin, scale)
    g = GPLV[]
    if g !== nothing
        n = length(g); i0 = mod(floor(Int, mod(s, line.total) / 3.0), n) + 1
        vt = g[i0]
        horizon = max(v*2.2, 30.0); off = 3.0             # same look-ahead shape: brake for what is coming
        while off <= horizon
            vt = min(vt, g[mod(i0 - 1 + round(Int, off/3.0), n) + 1]); off += 3.0
        end
        return clamp(vt*scale, vmin, vmax*scale)
    end
    κ = max(line.κ[_locate(line, s)[1]], 1e-4)
    horizon = max(v*2.2, 30.0)                              # metres to look ahead (longer the faster you go)
    off = 5.0
    while off <= horizon
        κ = max(κ, line.κ[_locate(line, s + off)[1]]); off += 6.0
    end
    clamp(sqrt(amax/κ)*scale, vmin, vmax*scale)
end

"Advance one AI car by `dt` on the race line; returns its world pose.  `scale` paces it
(see `natural_laptime`).  Single-car (no racecraft) — used for pace calibration."
function step!(car::AICar, line::AILine, dt; amax = 11.0, vmax = 74.0, vmin = 12.0, scale = 1.0)
    vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale)
    car.v += clamp(vt - car.v, -30.0*dt, 9.0*dt)            # brake harder than it accelerates
    prev = mod(car.s, line.total); car.s += car.v*dt
    mod(car.s, line.total) < prev && (car.lap += 1)         # crossed start/finish
    pose_at(line, car.s, car.lane)
end

"""Advance the AI field with GPL-style racecraft + simple collision physics.  Returns
`(poses, player_hit)`: each car's world pose (heading carries a collision yaw `spin`), and
whether an AI made contact with the human (so the app can give the player a bump).  `rel`
caps every AI to `rel × player_speed` so the field never runs away from the human."""
# E89 instrument: count the racecraft events that a spectator reads as "lunge ahead, then fall back".
# Plain counters, reset by the harness; step_field! only increments them.
mutable struct AIStat; engage::Int; release::Int; match::Int; qsnap::Int; sidepush::Int; mishap::Int; end
const AISTAT = AIStat(0, 0, 0, 0, 0, 0)
aistat_reset!() = (AISTAT.engage = AISTAT.release = AISTAT.match = AISTAT.qsnap = AISTAT.sidepush = AISTAT.mishap = 0; nothing)

"""Free-running speed profile: one car alone on the line for a lap, sampled every `ds` metres.
Returns (s_samples, v_samples). This is what a car does with nobody ahead -- the baseline any
'fall back' must be measured against, because a car braking for Ascari is not falling back."""
function free_speed_profile(line::AILine; scale = 1.0, dt = 1/60, ds = 5.0, amax = 11.0, vmax = 74.0, vmin = 12.0)
    car = AICar(0.0, 25.0, 0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    n = max(2, round(Int, line.total / ds)); vs = fill(NaN, n)
    for _ in 1:2                                     # two laps: the second overwrites the standing-start first
        while car.lap < 1
            step!(car, line, dt; amax, vmax, vmin, scale)
            k = clamp(floor(Int, mod(car.s, line.total) / ds) + 1, 1, n); vs[k] = car.v
        end
        car.lap = 0
    end
    for k in 1:n; isnan(vs[k]) && (vs[k] = vs[k == 1 ? n : k-1]); end   # fill any gap from the neighbour
    ((0:n-1) .* ds, vs)
end

function step_field!(cars::Vector{AICar}, line::AILine, dt;
                     scale = 1.0, player = nothing, rel = Inf,
                     amax = 11.0, vmax = 74.0, vmin = 12.0)
    total = line.total
    blocker(s_i, skip) = begin                              # nearest object ahead → (gap, lane, v) or nothing
        bg = Inf; res = nothing
        for (k,c) in enumerate(cars)
            k == skip && continue
            g = mod(c.s - s_i, total); (0.0 < g < bg) && (bg = g; res = (g, c.lane, c.v))
        end
        if player !== nothing
            g = mod(player[1] - s_i, total); (0.0 < g < bg) && (bg = g; res = (g, player[2], player[3]))
        end
        res
    end
    # 1) decide a line + speed, then advance with the longitudinal PHYSICS model
    for (i, car) in enumerate(cars)
        vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale) * car.pace   # per-car PHYSICS pace → the field spreads (Eagle out-runs the BRM)
        if car.mishap > 0.0                                    # GPL-style MISHAP in progress: ran wide / spun → crawl, drop right back
            car.mishap -= dt; vt *= 0.22
        elseif rand() < 8.0e-6                                 # rare: a fresh mishap (~1-2 across the field per race)
            car.mishap = 2.4; AISTAT.mishap += 1
        end
        b = blocker(car.s, i)                                # nearest ahead in ANY lane: drives the pass hysteresis
        gap   = b === nothing ? Inf : b[1]
        blane = b === nothing ? 0.0 : b[2]
        bv    = b === nothing ? Inf : b[3]
        if GAPCTL
            # SPEED is governed by the nearest car IN OUR PATH (lateral overlap within a car width plus
            # margin), which is not the same car as the hysteresis blocker: with alternating grid lanes
            # the nearest car is beside us in the other rail while the one we are closing on sits two
            # places ahead in ours (measured: 650 queue-snaps per 120 s with the wrong car governing).
            # It must NOT also drive engage/release: S2 tried that and the in-path car changes the
            # moment we pull out, so release fired at once and engage/release flapped 925 times.
            bg = Inf; bp = nothing
            for (k, c) in enumerate(cars)
                k == i && continue
                g = mod(c.s - car.s, total)
                (0.0 < g < bg && abs(c.lane - car.lane) < CAR_WID + 0.6) && (bg = g; bp = (g, c.lane, c.v))
            end
            if player !== nothing
                g = mod(player[1] - car.s, total)
                (0.0 < g < bg && abs(player[2] - car.lane) < CAR_WID + 0.6) && (bg = g; bp = (g, player[2], player[3]))
            end
            if bp !== nothing
                # PROPORTIONAL gap control (GPL): target = leader's speed + the excess gap closed over
                # GPL_CLOSE_TAU -- free speed far back, the leader's speed at the desired gap, LESS inside
                # it, so the follower settles instead of slamming and rebounding.
                vt = max(min(vt, bp[3] + (bp[1] - GPL_DESIRED_SEP) / GPL_CLOSE_TAU), 0.0)
            end
        end
        if false
        end
        # HYSTERESIS so the AI commit to a pass instead of skittering between rails like a
        # water-insect: ENGAGE a move only when genuinely catching a car ahead in our lane;
        # once committed to a rail, HOLD it until well clear (a much larger release gap).
        # (S2 measured a GPL-style "settled + pace + straight" ENGAGE rule here and it FLAPPED: with GPL
        #  speeds every car has near-equal free speed, so "we are quicker" flickered and engage/release
        #  ran 133/133 in 270 s -- 24.6 rail switches per car-lap against the baseline's 1.3. The
        #  original hysteresis stays; gap control changes only WHOM we follow and HOW we close.)
        if car.tlane == 0.0
            if gap < car.v*1.0 + 14.0 && abs(car.lane - blane) < 2.2
                car.tlane = blane >= 0.0 ? -RAIL : RAIL     # pick ONE side and commit
                AISTAT.engage += 1
            end
        else
            (gap > car.v*1.7 + 30.0) && (car.tlane = 0.0; AISTAT.release += 1)   # clear ahead → ease back to the race line
            (gap < car.v*0.6 + CAR_LEN && abs(car.lane - blane) < 1.6) && (vt = min(vt, b[3]); AISTAT.match += 1)  # still stuck behind → match speed
        end
        isfinite(rel) && player !== nothing && (vt = min(vt, max(player[3]*rel, 6.0)))   # ~player pace — never run away
        gl = gpl_racelane(line, car.s)
        if gl === nothing
            tgt = clamp(racelane(line, car.s) + lanebias(i, length(cars)) + car.tlane, -LANE_MAX, LANE_MAX)   # racing line + per-car bias + pass deviation
            car.lane += clamp(tgt - car.lane, -2.4*dt, 2.4*dt)        # deliberate lane changes (not twitchy)
            car.lane  = clamp(car.lane, -LANE_MAX, LANE_MAX)
        else
            # E84-S8: GPL's own line and rails. The pass deviation uses GPL's rail on that side
            # (asymmetric, per record) instead of a fixed +/-RAIL; the lane is clamped to the wider
            # of our band and GPL's own table, never tighter than GPL drives.
            dev = car.tlane == 0.0 ? 0.0 : something(gpl_rail(line, car.s, car.tlane > 0 ? 1 : -1), car.tlane)
            tgt = gl + lanebias(i, length(cars)) + dev
            lim = max(LANE_MAX, abs(gl) + LANE_MAX)
            car.lane += clamp(tgt - car.lane, -2.4*dt, 2.4*dt)
            car.lane  = clamp(car.lane, -lim, lim)
        end
        car.v     = advance_speed(car.v, vt, dt)            # realistic accel/brake (not slot-car)
        car.spin *= exp(-dt/0.45)                           # collision yaw decays back to the line heading
        prev = mod(car.s, total); car.s += car.v*dt
        mod(car.s, total) < prev && (car.lap += 1)
    end
    # 2) keep cars from passing THROUGH each other: same-lane → queue single file; side-by-side
    #    overlap → push apart + add opposite yaw spin + bleed speed (a contact).
    n = length(cars)
    for a in 1:n, b in 1:n
        a == b && continue
        Δs = mod(cars[a].s - cars[b].s, total)              # how far a is AHEAD of b
        Δs > total/2 && continue                            # only handle b catching a (a ahead)
        dl = cars[a].lane - cars[b].lane
        Δs < CAR_LEN || continue
        if abs(dl) < CAR_WID*0.7                             # ~same lane → b queues single-file behind a
            AISTAT.qsnap += 1
            cars[b].s = cars[a].s - CAR_LEN
            cars[b].v = min(cars[b].v, cars[a].v)
        elseif abs(dl) < CAR_WID                             # side-by-side overlap → resolve to single file.
            # PO round 4: "AI had a lot of trouble with this track — I only saw them once, bunched up."  The
            # old yield multiplied the trailing car's speed by 0.90 EVERY FRAME while overlapping; at a tight
            # corner (the Lesmos chicane) step-1 re-converges both cars' target lanes within a car-width every
            # frame, so the *0.90 compounded (0.9^30 ≈ 0.04 in half a second) and the whole field crawled to a
            # stop and clumped.  Fix: the TRAILING car (b) TUCKS into single file behind a — eased apart a bit
            # laterally, dropped back to a clean following gap, speed matched (NOT multiplied) — exactly how a
            # field threads a chicane.  No per-frame compounding, so no crawl.
            push = (CAR_WID - abs(dl)) * 0.5; d = dl >= 0 ? 1.0 : -1.0; AISTAT.sidepush += 1
            cars[a].lane = clamp(cars[a].lane + d*push, -LANE_MAX, LANE_MAX)
            cars[b].lane = clamp(cars[b].lane - d*push, -LANE_MAX, LANE_MAX)
            cars[b].s = cars[a].s - CAR_LEN                  # fall in BEHIND a (single file) — bounded, no compounding decel
            cars[b].v = min(cars[b].v, cars[a].v)            # match a's speed, don't crawl to a halt
        end
    end
    # 3) contact with the HUMAN: the AI yields (steps aside + twitches + slows); flag a bump
    player_hit = false
    if player !== nothing
        for c in cars
            Δs = mod(c.s - player[1] + total/2, total) - total/2
            if abs(Δs) < CAR_LEN && abs(c.lane - player[2]) < CAR_WID
                d = (c.lane - player[2]) >= 0 ? 1.0 : -1.0
                c.lane = clamp(c.lane + d*1.3, -LANE_MAX, LANE_MAX)
                c.spin += 0.22*d; c.v *= 0.9
                player_hit = true
            end
        end
    end
    poses = NTuple{4,Float64}[]
    for c in cars
        p = pose_at(line, c.s, c.lane); push!(poses, (p[1], p[2], p[3], p[4] + c.spin))
    end
    (poses, player_hit)
end

"""Brain-only racecraft for the HYBRID-PHYSICS AI: decide each car's target rail (`tlane`,
with the same pass-hysteresis as the kinematic field) and target speed, WITHOUT moving the
car — the JM physics model + the controller do the motion.  Each `AICar` must already have
its `s`, `lane`, `v` updated from its physics car (project it onto the line).  Returns the
per-car target speed `vt`."""
function plan!(cars::Vector{AICar}, line::AILine; player = nothing, scale = 1.0, rel = Inf,
               amax = 11.0, vmax = 74.0, vmin = 12.0, dt = 1/60)
    total = line.total
    blocker(s_i, skip) = begin
        bg = Inf; res = nothing
        for (k,c) in enumerate(cars)
            k == skip && continue
            g = mod(c.s - s_i, total); (0.0 < g < bg) && (bg = g; res = (g, c.lane, c.v))
        end
        if player !== nothing
            g = mod(player[1] - s_i, total); (0.0 < g < bg) && (bg = g; res = (g, player[2], player[3]))
        end
        res
    end
    # peak curvature over [s, s+dist] → is the section ahead straight enough to PASS on?
    maxκ(s, dist) = begin κ = 1e-4; off = 0.0; while off <= dist; κ = max(κ, line.κ[_locate(line, s+off)[1]]); off += 6.0; end; κ end
    vts = Float64[]
    for (i, car) in enumerate(cars)
        # PER-CAR PHYSICS PACE (power/weight) so the field SPREADS like GPL — the Eagle out-paces the BRM
        # — plus a rare "brake too late" twitch (carry a touch too much speed in) and a GPL-style MISHAP
        # (run wide / spin → crawl, drop right back).  pace replaces the old index-based ±2.5 % fudge.
        gaffe = (rand() < 0.0015) ? 1.10 : 1.0
        if car.mishap > 0.0; car.mishap -= dt; elseif rand() < 8.0e-6; car.mishap = 2.4; end
        mish  = car.mishap > 0.0 ? 0.22 : 1.0
        vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale) * car.pace * gaffe * mish
        b = blocker(car.s, i); gap = b === nothing ? Inf : b[1]; blane = b === nothing ? 0.0 : b[2]; bv = b === nothing ? Inf : b[3]
        dlane  = b === nothing ? Inf : abs(car.lane - blane)            # lateral separation from the car ahead
        tail   = car.v*0.9 + 10.0                                       # following distance that counts as "tailgating"
        zone   = max(car.v*2.0, 45.0)                                   # passing-zone look-ahead
        straight = maxκ(car.s, zone) < 1/75.0                          # corner radius > 75 m ⇒ a straight to slingshot on
        overlap  = gap < CAR_LEN*0.7                                    # "front wheels past his cockpit" by corner entry
        patience = 1.2 + 1.8*((0.37*i) % 1.0)                          # staggered so the field doesn't pull out in unison
        edge   = bv + 1.0 < vt                                          # we'd be quicker than the car ahead if free
        if car.tlane == 0.0
            if gap < tail && dlane < 2.4                                # sitting in the dirty air behind a car
                car.follow += dt
                # COMMIT a pass once we've kept the pressure on (patience) AND have the pace, EITHER on a
                # straight (slingshot) OR — into a corner — only if we've already drawn alongside (the GPL
                # overlap rule: you may take the corner only with front-wheel overlap by entry; else you do
                # NOT own it → tuck in and wait for the leader to make a mistake).
                if car.follow > patience && edge && (straight || overlap)
                    car.tlane = blane >= 0.0 ? -RAIL : RAIL             # pull out to the side with room
                    car.follow = 0.0
                elseif gap < car.v*0.6 + CAR_LEN                        # else hold station — match speed, don't ram
                    vt = min(vt, bv)
                end
            else
                car.follow = max(0.0, car.follow - dt)                  # nobody ahead → patience resets
            end
        else
            if gap > car.v*1.7 + 30.0                                   # clear ahead → ease back to the racing line
                car.tlane = 0.0
            elseif !straight && !overlap                                # corner here and NOT alongside → yield it:
                car.tlane = 0.0; vt = min(vt, bv)                       #   tuck back in behind (don't dive-bomb)
            elseif gap < car.v*0.6 + CAR_LEN && dlane < 1.6
                vt = min(vt, bv)                                        # still stuck behind in the passing lane → match speed
            end
        end
        isfinite(rel) && player !== nothing && (vt = min(vt, max(player[3]*rel, 6.0)))
        push!(vts, vt)
    end
    vts
end

"""Steering/throttle/brake for one hybrid-physics AI to track the RACING LINE (plus a pass
`dev`iation, e.g. ±RAIL to pull out alongside) at speed `tv` (short-look-ahead pursuit +
cross-track + yaw-damp, corner throttle-cut).  `cs`/`clane` = the car's current arc-length/
lateral (from projection), `cθ`/`cv`/`r` its heading/speed/yaw-rate.  Returns (thr, brk, steer)."""
function controller(line::AILine, cs, clane, dev, tv, cx, cz, cθ, cv, r; power = 1.0)
    la = clamp(6.0 + cv*0.35, 6.0, 20.0)                  # look-ahead DISTANCE in metres (density-independent)
    # SHORTEN the look-ahead in a tight corner so the chord follows the arc instead of cutting the
    # apex to the inside (the T1-hairpin problem): cap it to a fraction of the corner radius.
    κloc = max(line.κ[_locate(line, cs)[1]], line.κ[_locate(line, cs + 0.5*la)[1]], 1e-4)
    la = clamp(min(la, 0.32/κloc), 4.0, 20.0)
    tlane = clamp(racelane(line, cs + la) + dev, -LANE_MAX, LANE_MAX)    # target = racing line ahead + pass offset
    here  = clamp(racelane(line, cs)      + dev, -LANE_MAX, LANE_MAX)
    lp = pose_at(line, cs + la, tlane)                    # look-ahead point ON the racing line
    herr = wrapπ(atan(lp[3]-cz, lp[1]-cx) - cθ)
    # E12/G2 ANTI-SPIN (catch the slide): a normal corner yaw rate is < ~1 rad/s (r = v·κ), so a HIGHER
    # r means the car is starting to slide/spin — the failure mode on the hilly/blind tracks (Spa,
    # Nürburgring), where the 3-D model's load transfers break grip and the aggressive line-chase gain
    # AMPLIFIES the slide.  As r climbs into the slide band: ease the line-chase gain (stop fighting it),
    # ramp the counter-yaw damping (steer into the slide), and LIFT the throttle (kill RWD power-oversteer).
    # Below SPIN_LO it's all unchanged ⇒ flat-track pace/line is untouched.
    slide = clamp((abs(r) - SPIN_LO) / (SPIN_HI - SPIN_LO), 0.0, 1.0)   # 0 = normal cornering → 1 = spinning
    hgain = 3.0 * (1.0 - 0.45*slide)                      # line-follow gain (eased when sliding)
    yawd  = 0.22 + 0.55*slide                             # counter-yaw damping (ramped when sliding)
    steer = clamp(hgain*herr - 0.24*(clane - here) - yawd*r, -1.0, 1.0)   # tight line-follow (don't flatten corners)
    # `power` = the AI's engine-power tune (set ONCE pre-race, not per frame): caps throttle so a
    # detuned car has lower accel/top speed → a fixed pace it can't exceed (and can wash out hot).
    thr = (cv < tv ? clamp((tv-cv)*0.25, 0, 1) * clamp(1.4 - 2.2*abs(steer), 0.0, 1.0) : 0.0) * power * (1.0 - 0.75*slide)
    brk = cv > tv + 1.0 ? clamp((cv-tv)*0.25, 0, 1) : 0.0
    # TRAIL BRAKING: don't dump the brake at turn-in — carry a little into the corner (loads the
    # front tyres, rotates the car to the apex), fading as the wheel unwinds.  Small so it never spins.
    (brk < 0.05 && abs(steer) > 0.2 && cv > tv*0.92) && (brk = clamp(0.10*abs(steer), 0.0, 0.18))
    (thr, brk, steer)
end

"""Grid order from a qualifying session.  `player_time` is the human's best qual lap
(`Inf` if they set none → starts last); `ai_times` the AI reference qual times.  Returns
the entrant ids sorted pole-first, where id 0 = the player and id i = AI car i.  The
position of id 0 in the result is the player's grid slot (1 = pole)."""
function grid_order(player_time, ai_times)
    entr = Tuple{Int,Float64}[(0, player_time)]
    for i in eachindex(ai_times); push!(entr, (i, Float64(ai_times[i]))); end
    sort!(entr, by = x -> x[2])
    [e[1] for e in entr]
end

"""Simulate one AI car around a full lap at the given `scale` and return the lap
time (s).  Used to calibrate the pace: knowing the natural lap time at scale 1.0,
the app picks the scale that makes a clean lap hit the GPL reference laptime ×
(100/pct).  Robust to a non-closing line (caps at ~2× the straight-line estimate)."""
function natural_laptime(line::AILine; scale = 1.0, dt = 1/60,
                        amax = 11.0, vmax = 74.0, vmin = 12.0)
    # E84-S2: amax/vmax forwarded so the pace anchor can be SWEPT (JM_PACEDIAG) instead of
    # guessed at.  Defaults are step!'s own, so every existing caller is unchanged.
    car = AICar(0.0, 25.0, 0, 0.0)
    t = 0.0; tmax = 4.0 * line.total / 10.0 + 30.0    # generous cap (≥ lap at ~10 m/s)
    while car.lap < 1 && t < tmax
        step!(car, line, dt; scale = scale, amax = amax, vmax = vmax, vmin = vmin)
        t += dt
    end
    t
end

end # module
