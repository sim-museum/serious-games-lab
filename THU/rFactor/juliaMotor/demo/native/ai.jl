# RaceAI — simple, robust rail-following opponents for the race mode.  Each AI car
# tracks the track centreline at a curvature-limited speed (slows for corners, runs
# out the straights) and is rendered as a Lotus 49.  This is a VISUAL/gameplay AI
# (not the full physics model) — enough for a field of up to 5 opponents that drive
# a believable line, start on a grid, and complete laps.
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

mutable struct AICar; s::Float64; v::Float64; lap::Int; lane::Float64; end

"Grid of `n` AI cars staggered ~9 m apart behind arc-length `start_s`, alternating lanes."
init_cars(line::AILine, n; start_s = 0.0) =
    [AICar(mod(start_s - 9.0*i, line.total), 25.0, 0, iseven(i) ? 2.4 : -2.4) for i in 1:n]

function _locate(line::AILine, sq)
    sq = mod(sq, line.total)
    i = clamp(searchsortedlast(line.s, sq), 1, length(line.s)-1)
    f = (sq - line.s[i]) / max(line.s[i+1]-line.s[i], 1e-6)
    i, f
end

"Advance one AI car by `dt`; returns its world pose (x, y, z, heading).  `scale`
multiplies the target/limit speed so the field can be paced to a chosen laptime
(see `natural_laptime` + the `JM_AI_PCT` calibration)."
function step!(car::AICar, line::AILine, dt; amax = 11.0, vmax = 74.0, vmin = 12.0, scale = 1.0)
    i, _  = _locate(line, car.s)
    ia, _ = _locate(line, car.s + max(car.v*0.9, 10.0))     # look ahead for the limiting corner
    κ = max(line.κ[i], line.κ[ia], 1e-4)
    vtarget = clamp(sqrt(amax/κ)*scale, vmin, vmax*scale)
    car.v += clamp(vtarget - car.v, -30.0*dt, 9.0*dt)       # brake harder than it accelerates
    prev = mod(car.s, line.total)
    car.s += car.v*dt
    mod(car.s, line.total) < prev && (car.lap += 1)         # crossed start/finish
    i, f = _locate(line, car.s); j = i % length(line.x) + 1
    x = line.x[i]*(1-f) + line.x[j]*f
    z = line.z[i]*(1-f) + line.z[j]*f
    y = line.y[i]*(1-f) + line.y[j]*f
    θ = line.θ[i] + f*wrapπ(line.θ[j]-line.θ[i])
    x += car.lane * (-sin(θ));  z += car.lane * cos(θ)      # lane offset (left = (-sinθ, cosθ))
    (x, y, z, θ)
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
