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

mutable struct AICar; s::Float64; v::Float64; lap::Int; lane::Float64; tlane::Float64; end
AICar(s, v, lap, lane) = AICar(s, v, lap, lane, lane)   # tlane defaults to the current lane

const RAIL     = 3.0    # inside/outside rail offset from the race line (m)
const LANE_MAX = 3.6    # never exceed this lateral offset (keeps the car on the track)

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

"""Advance the whole AI field for `dt` with GPL-style racecraft: each car follows the
race line but moves to an inside/outside RAIL to pass or evade the nearest car ahead —
another AI OR the human (`player` = (s, lateral, v) or nothing) — and matches speed when
it's too close to get by (so it never rams).  Returns each car's world pose, in order."""
function step_field!(cars::Vector{AICar}, line::AILine, dt;
                     scale = 1.0, player = nothing, amax = 11.0, vmax = 74.0, vmin = 12.0)
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
    poses = NTuple{4,Float64}[]
    for (i, car) in enumerate(cars)
        vt = _vtarget(line, car.s, car.v; amax, vmax, vmin, scale)
        b = blocker(car.s, i)
        if b !== nothing && b[1] < car.v*0.9 + 12.0 && abs(car.lane - b[2]) < 2.2
            car.tlane = b[2] >= 0.0 ? -RAIL : RAIL          # dive to the rail away from the car ahead
            (b[1] < car.v*0.5 + 6.0 && abs(car.lane - b[2]) < 1.8) && (vt = min(vt, b[3] + 0.5))  # too close → match speed, don't ram
        else
            car.tlane = 0.0                                 # clear → drift back to the race line
        end
        car.lane += clamp(car.tlane - car.lane, -3.5*dt, 3.5*dt)   # blend to the target rail
        car.lane  = clamp(car.lane, -LANE_MAX, LANE_MAX)           # stay on track
        car.v    += clamp(vt - car.v, -30.0*dt, 9.0*dt)
        prev = mod(car.s, total); car.s += car.v*dt
        mod(car.s, total) < prev && (car.lap += 1)
        push!(poses, pose_at(line, car.s, car.lane))
    end
    poses
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
