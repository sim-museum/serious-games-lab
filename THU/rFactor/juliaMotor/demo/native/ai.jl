# RaceAI — GPL-style multi-rail opponents for the race mode.  Each AI tracks the
# centreline at a curvature-limited speed (slows for corners, runs out the straights)
# and — like GPL's AI — moves between three rails (race line / inside / outside) to
# PASS slower cars and EVADE both the other AI and the human's car, matching speed when
# it can't get by yet (so it never rams).  This is a kinematic gameplay AI (not the full
# physics model); see RACE_AI_NOTES.md for the physics/hybrid path.
module RaceAI

struct AILine
    x::Vector{Float64}; z::Vector{Float64}; y::Vector{Float64}
    s::Vector{Float64}                 # cumulative arc length [m]
    θ::Vector{Float64}                 # tangent heading [rad]
    κ::Vector{Float64}                 # curvature [1/m]
    total::Float64                     # lap length [m]
end

wrapπ(a) = a > π ? a - 2π : a < -π ? a + 2π : a

"Build an AI racing line from centreline points `pts` (each (x,z) in physics frame)
and a `groundz(x,z)->y` elevation function."
function build_line(pts, groundz)
    n = length(pts)
    x = Float64[p[1] for p in pts]; z = Float64[p[2] for p in pts]
    s = zeros(n); for i in 2:n; s[i] = s[i-1] + hypot(x[i]-x[i-1], z[i]-z[i-1]); end
    θ = [atan(z[i%n+1]-z[i], x[i%n+1]-x[i]) for i in 1:n]
    κ = zeros(n)
    for i in 1:n
        j = i % n + 1; ds = max(j == 1 ? (s[end]-s[i]) : (s[j]-s[i]), 0.5)
        κ[i] = abs(wrapπ(θ[j]-θ[i])) / ds
    end
    y = Float64[(h = groundz(x[i], z[i]); isfinite(h) ? h : 0.0) for i in 1:n]
    AILine(x, z, y, s, θ, κ, s[end])
end

mutable struct AICar; s::Float64; v::Float64; lap::Int; lane::Float64; tlane::Float64; spin::Float64; end
AICar(s, v, lap, lane) = AICar(s, v, lap, lane, lane, 0.0)   # tlane defaults to current lane; spin = collision yaw

const RAIL     = 3.0    # inside/outside rail offset from the race line (m)
const LANE_MAX = 3.6    # never exceed this lateral offset (keeps the car on the track)
const CAR_LEN  = 4.2    # car length (m) — single-file spacing + collision longitudinal extent
const CAR_WID  = 1.7    # car width (m) — collision lateral extent

# Longitudinal physics so the AI ACCELERATE like cars (not slot cars): traction-limited
# off the line, power-limited + aero drag at speed → a natural build-up and top speed.
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
    [AICar(mod(start_s - 9.0*i, line.total), 25.0, 0, iseven(i) ? 2.4 : -2.4) for i in 1:n]

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
    (x + lane*(-sin(θ)), y, z + lane*cos(θ), θ)             # lane offset (left = (-sinθ, cosθ))
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

"Curvature-limited target speed for a car at arc-length `s` moving at `v` (m/s)."
function _vtarget(line::AILine, s, v; amax, vmax, vmin, scale)
    i, _  = _locate(line, s)
    ia, _ = _locate(line, s + max(v*0.9, 10.0))             # look ahead for the limiting corner
    κ = max(line.κ[i], line.κ[ia], 1e-4)
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
        vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale)
        b = blocker(car.s, i)
        gap   = b === nothing ? Inf : b[1]
        blane = b === nothing ? 0.0 : b[2]
        # HYSTERESIS so the AI commit to a pass instead of skittering between rails like a
        # water-insect: ENGAGE a move only when genuinely catching a car ahead in our lane;
        # once committed to a rail, HOLD it until well clear (a much larger release gap).
        if car.tlane == 0.0
            if gap < car.v*1.0 + 14.0 && abs(car.lane - blane) < 2.2
                car.tlane = blane >= 0.0 ? -RAIL : RAIL     # pick ONE side and commit
            end
        else
            (gap > car.v*1.7 + 30.0) && (car.tlane = 0.0)   # clear ahead → ease back to the race line
            (gap < car.v*0.6 + CAR_LEN && abs(car.lane - blane) < 1.6) && (vt = min(vt, b[3]))  # still stuck behind → match speed
        end
        isfinite(rel) && player !== nothing && (vt = min(vt, max(player[3]*rel, 6.0)))   # ~player pace — never run away
        car.lane += clamp(car.tlane - car.lane, -2.4*dt, 2.4*dt)   # deliberate lane changes (not twitchy)
        car.lane  = clamp(car.lane, -LANE_MAX, LANE_MAX)
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
        if abs(dl) < CAR_WID*0.7                             # ~same lane → b queues behind a (no pass-through)
            cars[b].s = cars[a].s - CAR_LEN
            cars[b].v = min(cars[b].v, cars[a].v)
        elseif abs(dl) < CAR_WID                             # side-by-side touch → rub + twitch
            push = (CAR_WID - abs(dl)) * 0.5; d = dl >= 0 ? 1.0 : -1.0
            cars[a].lane = clamp(cars[a].lane + d*push, -LANE_MAX, LANE_MAX)
            cars[b].lane = clamp(cars[b].lane - d*push, -LANE_MAX, LANE_MAX)
            cars[a].spin += 0.18*d; cars[b].spin -= 0.18*d
            cars[a].v *= 0.97; cars[b].v *= 0.97
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
               amax = 11.0, vmax = 74.0, vmin = 12.0)
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
    vts = Float64[]
    for (i, car) in enumerate(cars)
        vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale)
        b = blocker(car.s, i); gap = b === nothing ? Inf : b[1]; blane = b === nothing ? 0.0 : b[2]
        if car.tlane == 0.0
            (gap < car.v*1.0 + 14.0 && abs(car.lane - blane) < 2.2) && (car.tlane = blane >= 0.0 ? -RAIL : RAIL)
        else
            (gap > car.v*1.7 + 30.0) && (car.tlane = 0.0)
            (gap < car.v*0.6 + CAR_LEN && abs(car.lane - blane) < 1.6) && (vt = min(vt, b[3]))
        end
        isfinite(rel) && player !== nothing && (vt = min(vt, max(player[3]*rel, 6.0)))
        push!(vts, vt)
    end
    vts
end

"""Steering/throttle/brake for one hybrid-physics AI to track the rail at `tlane` at speed
`tv` (the PROVEN controller: short-look-ahead pursuit + cross-track + yaw-damp, corner
throttle-cut).  `cs`/`clane` = the car's current arc-length/lateral (from projection),
`cθ`/`cv`/`r` its heading/speed/yaw-rate.  Returns (throttle, brake, steer)."""
function controller(line::AILine, cs, clane, tlane, tv, cx, cz, cθ, cv, r)
    la = clamp(round(Int, 3 + cv*0.22), 3, length(line.x)-1) * (line.total/length(line.x))
    lp = pose_at(line, cs + la, tlane)                    # look-ahead point ON the target rail
    herr = wrapπ(atan(lp[3]-cz, lp[1]-cx) - cθ)
    steer = clamp(2.6*herr - 0.14*(clane - tlane) - 0.20*r, -1.0, 1.0)
    thr = cv < tv ? clamp((tv-cv)*0.25, 0, 1) * clamp(1.4 - 2.2*abs(steer), 0.0, 1.0) : 0.0
    brk = cv > tv + 1.0 ? clamp((cv-tv)*0.2, 0, 1) : 0.0
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
function natural_laptime(line::AILine; scale = 1.0, dt = 1/60)
    car = AICar(0.0, 25.0, 0, 0.0)
    t = 0.0; tmax = 4.0 * line.total / 10.0 + 30.0    # generous cap (≥ lap at ~10 m/s)
    while car.lap < 1 && t < tmax
        step!(car, line, dt; scale = scale)
        t += dt
    end
    t
end

end # module
