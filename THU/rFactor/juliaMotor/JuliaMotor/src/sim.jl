# Headless full-lap simulation: the calibrated vehicle driven around a
# TrackSurface by a racing-line-following driver, no renderer.
#
# This is the Phase 2 closed-loop twin — a single-track (bicycle) car with
# load transfer and the calibrated TBC tires, a pure-pursuit steering
# controller aiming at the AIW racing line, and a speed controller tracking
# the AIW per-waypoint target speeds through the engine / brake / drag
# model.  It produces a lap time and a speed-vs-distance trace to compare
# against telemetry.
#
# Frame: world plane (X, Z); Y (height) from HAT.  Heading θ is the angle
# of the forward axis in the X–Z plane: forward = (cos θ, sin θ).

"""One recorded sample of a simulated lap."""
struct SimSample
    t::Float64
    x::Float64
    z::Float64
    speed::Float64
    yaw::Float64
    yawrate::Float64
    lateral::Float64
    lapdist::Float64
    gear::Int
    throttle::Float64
    brake::Float64
    steer::Float64
end

struct SimResult
    laptime::Float64
    completed::Bool
    samples::Vector{SimSample}
    max_lateral::Float64     # worst off-line excursion (m)
end

Base.show(io::IO, r::SimResult) =
    print(io, "SimResult(", r.completed ? "lap " * string(round(r.laptime; digits=2)) * " s" :
          "DNF", ", ", length(r.samples), " samples, max|lat| ",
          round(r.max_lateral; digits=2), " m)")

# monotonic forward progress: advance the waypoint index whenever the car
# has passed the current segment's end (projection parameter > 1).  Cannot
# stick or snap backward, so tight hairpins and parallel sections are safe.
function advance_index(ts::TrackSurface, X, Z, wpi)
    n = length(ts.pos)
    for _ in 1:60
        j = mod1(wpi + 1, n)
        ax, az = ts.pos[wpi][1], ts.pos[wpi][3]
        sx, sz = ts.pos[j][1] - ax, ts.pos[j][3] - az
        len2 = sx^2 + sz^2
        t = len2 > 1e-9 ? ((X - ax) * sx + (Z - az) * sz) / len2 : 2.0
        t > 1.0 ? (wpi = j) : break
    end
    wpi
end

# local racing-line radius at waypoint i: circumradius through i±span,
# evaluated at several scales and reduced to the tightest, so a sharp
# hairpin is not smoothed into a gentle (too-fast) radius by a wide span
function line_radius(ts::TrackSurface, i; spans=(2, 3, 4, 6))
    n = length(ts.pos)
    rmin = Inf
    for span in spans
        a = ts.pos[mod1(i - span, n)]; b = ts.pos[i]; c = ts.pos[mod1(i + span, n)]
        ax, az, bx, bz, cx, cz = a[1], a[3], b[1], b[3], c[1], c[3]
        ab = hypot(bx - ax, bz - az); bc = hypot(cx - bx, cz - bz); ca = hypot(ax - cx, az - cz)
        area2 = abs((bx - ax) * (cz - az) - (bz - az) * (cx - ax))
        area2 < 1e-6 && continue
        rmin = min(rmin, ab * bc * ca / (2 * area2))
    end
    rmin
end

"""
    speed_profile(ts, base; a_brake, a_accel) -> Vector{Float64}

Feasible per-waypoint speed limit: starts from `base` (the AIW per-waypoint
target speeds — rFactor's own racing speeds, which already encode each
corner's grip-limited apex speed) and applies a backward pass bounding
entry speed by braking capacity and a forward pass by acceleration
capacity, giving correct anticipatory braking points.  We trust the AIW
corner speeds rather than re-deriving them from the waypoint geometry,
whose small position jitter makes a curvature estimate unreliable.
"""
function speed_profile(ts::TrackSurface, base::AbstractVector;
                       a_brake=6.0, a_accel=4.0)
    n = length(ts.pos)
    seglen(i) = (j = mod1(i + 1, n);
                 hypot(ts.pos[j][1] - ts.pos[i][1], ts.pos[j][3] - ts.pos[i][3]))
    vp = collect(Float64, base)
    for _ in 1:2          # two sweeps converge the closed loop
        for i in n:-1:1   # backward: brake into corners
            j = mod1(i + 1, n)
            vp[i] = min(vp[i], sqrt(vp[j]^2 + 2 * a_brake * seglen(i)))
        end
        for i in 1:n       # forward: accelerate out
            j = i == 1 ? n : i - 1
            vp[i] = min(vp[i], sqrt(vp[j]^2 + 2 * a_accel * seglen(j)))
        end
    end
    vp
end

"""
    qss_speed_profile(ft; mu=0.95, vmax=56, a_drive=4.0) -> Vector{Float64}

Quasi-steady-state lap-optimal speed limit, computed directly from the
(clean, ±-smoothed) curvature and a friction circle — no AIW speeds.  The
cornering limit is `v = sqrt(μg / |κ|)`; the backward (braking) and forward
(acceleration) passes use only the longitudinal grip left after cornering,
`sqrt((μg)² − (v²κ)²)`, so the profile is feasible everywhere by
construction.  This is the principled basis for a limit-handling driver:
the target speed never demands beyond the tire circle, so the car need not
rely on a spin-catch to stay on track.
"""
function qss_speed_profile(ft; mu::Real=0.95, vmax::Real=56.0,
                           a_drive::Real=4.0)
    n = length(ft.s)
    g = mu * 9.81
    ds(i) = (j = mod1(i + 1, n); d = ft.s[j] - ft.s[i]; d <= 0 ? ft.total + d : d)
    κ(i) = abs(ft.kappa[i])
    v = [min(vmax, sqrt(g / max(κ(i), 1e-5))) for i in 1:n]
    for _ in 1:3
        for i in n:-1:1            # backward: brake into corners (friction circle)
            j = mod1(i + 1, n)
            ay = v[j]^2 * κ(j)
            ax = sqrt(max(0.0, g^2 - ay^2))
            v[i] = min(v[i], sqrt(v[j]^2 + 2 * ax * ds(i)))
        end
        for i in 1:n               # forward: accelerate out (grip ∩ engine)
            j = i == 1 ? n : i - 1
            ay = v[j]^2 * κ(j)
            ax = min(sqrt(max(0.0, g^2 - ay^2)), Float64(a_drive))
            v[i] = min(v[i], sqrt(v[j]^2 + 2 * ax * ds(j)))
        end
    end
    v
end

# target speed at a lap distance, from the AIW waypoint speeds
function target_speed(ts::TrackSurface, lapdist, wp_speed)
    n = length(ts.lapdist)
    # nearest waypoint by lapdist (ribbon is ordered)
    i = searchsortedlast(ts.lapdist, lapdist)
    i = clamp(i, 1, n - 1)
    t = (lapdist - ts.lapdist[i]) / max(ts.lapdist[i+1] - ts.lapdist[i], 1e-3)
    wp_speed[i] + clamp(t, 0, 1) * (wp_speed[i+1] - wp_speed[i])
end

# Track resampled by arc length, with tangent heading, smoothed curvature,
# half-widths and target speed — the centerline frame the Frenet driver
# integrates against.
struct FrenetTrack
    s::Vector{Float64}        # cumulative arc length at each node
    pos::Vector{NTuple{2,Float64}}   # (X, Z) centerline
    perp::Vector{NTuple{2,Float64}}  # lateral unit (X, Z)
    theta::Vector{Float64}    # tangent heading
    kappa::Vector{Float64}    # smoothed curvature (1/m), + = left turn
    hwl::Vector{Float64}
    hwr::Vector{Float64}
    vtar::Vector{Float64}     # braking-feasible target speed
    total::Float64
end

function FrenetTrack(ts::TrackSurface, vtar::AbstractVector; ksmooth=4)
    n = length(ts.pos)
    pos = [(ts.pos[i][1], ts.pos[i][3]) for i in 1:n]
    perp = [(ts.perp[i][1], ts.perp[i][3]) for i in 1:n]
    s = zeros(n)
    for i in 2:n
        s[i] = s[i-1] + hypot(pos[i][1]-pos[i-1][1], pos[i][2]-pos[i-1][2])
    end
    total = s[end] + hypot(pos[1][1]-pos[n][1], pos[1][2]-pos[n][2])
    θ = [atan(pos[mod1(i+1,n)][2]-pos[i][2], pos[mod1(i+1,n)][1]-pos[i][1]) for i in 1:n]
    # smoothed curvature: net heading change over ±ksmooth nodes / arc length
    κ = zeros(n)
    for i in 1:n
        a = mod1(i-ksmooth, n); b = mod1(i+ksmooth, n)
        dθ = atan(sin(θ[b]-θ[a]), cos(θ[b]-θ[a]))
        ds = 0.0
        for k in 0:2ksmooth-1
            j = mod1(i-ksmooth+k, n)
            ds += hypot(pos[mod1(j+1,n)][1]-pos[j][1], pos[mod1(j+1,n)][2]-pos[j][2])
        end
        κ[i] = ds > 1e-6 ? dθ/ds : 0.0
    end
    FrenetTrack(s, pos, perp, θ, κ,
                [ts.halfwidth[i][1] for i in 1:n], [ts.halfwidth[i][2] for i in 1:n],
                collect(Float64, vtar), total)
end

# interpolate a per-node field at arc length sq (wrapping the closed loop)
function at_s(ft::FrenetTrack, field::Vector{Float64}, sq; wrap=false)
    n = length(ft.s)
    sq = mod(sq, ft.total)
    i = searchsortedlast(ft.s, sq); i = clamp(i, 1, n)
    j = mod1(i+1, n)
    seg = (j == 1 ? ft.total : ft.s[j]) - ft.s[i]
    t = seg > 1e-6 ? (sq - ft.s[i]) / seg : 0.0
    if wrap   # angle interpolation
        d = atan(sin(field[j]-field[i]), cos(field[j]-field[i]))
        field[i] + clamp(t,0,1)*d
    else
        field[i] + clamp(t,0,1)*(field[j]-field[i])
    end
end

"""
    simulate_lap(model, aiw; dt=0.004, speed_factor=1.0, ...) -> SimResult

Drive one lap of `aiw` with `model`, integrating the vehicle in
track-relative (Frenet) coordinates: arc length `s` along the racing line,
lateral offset `n`, and heading relative to the track tangent.  Because
`s` advances with forward motion, the car cannot drive off and get lost —
the lap always completes (or is flagged a crash if `|n|` exceeds the
runoff).  A curvature-feedforward + lateral/heading-feedback controller
steers to the line; speed tracks the braking-feasible AIW profile.

Pass `terrain::TriangleHAT` to drive over the real track elevation: the
surface grade in the travel direction adds a gravity term to the
longitudinal dynamics (the car slows uphill, gains downhill).  Without it
the road is treated as flat.
"""
function simulate_lap(model::VehicleModel, aiw; dt::Real=0.004,
                      maxtime::Real=400.0, speed_factor::Real=1.0,
                      fuel::Real=40.0, record_every::Integer=25,
                      terrain::Union{Nothing,TriangleHAT}=nothing,
                      profile::Symbol=:aiw, mu::Real=0.95)
    ts = TrackSurface(aiw)
    wp = mainpath(aiw)
    vprof = speed_profile(ts, [Float64(w.speed) for w in wp])
    ft = FrenetTrack(ts, vprof)
    n = length(ft.s)
    # :qss replaces the AIW-derived target with a friction-circle lap-optimal
    # profile; being feasible by construction it needs no aggressive spin-catch
    qss = profile === :qss
    qss && (ft = FrenetTrack(ts, qss_speed_profile(ft; mu)))

    L = model.wheelbase
    a = L * model.rear_frac
    b = L - a
    mt0 = mass(model, fuel)
    # component arrays for at_s (precomputed to avoid per-step allocation)
    posx = [p[1] for p in ft.pos]; posz = [p[2] for p in ft.pos]
    perpx = [p[1] for p in ft.perp]; perpz = [p[2] for p in ft.perp]

    # state: arc length s, lateral n, heading-rel ψ, plus body v, β, r
    s = 0.0; nlat = 0.0; ψrel = 0.0
    v = max(ft.vtar[1] * speed_factor, 5.0)
    β = 0.0; r = 0.0
    gear = 3
    samples = SimSample[]
    maxlat = 0.0
    t = 0.0
    crashed = false

    nsteps = ceil(Int, maxtime / dt)
    for step in 1:nsteps
        κ = at_s(ft, ft.kappa, s)
        hwl = at_s(ft, ft.hwl, s); hwr = at_s(ft, ft.hwr, s)
        maxlat = max(maxlat, abs(nlat))

        # --- driver -------------------------------------------------------
        # steering: curvature feedforward + (gentle) feedback on lateral &
        # heading, plus countersteer into any oversteer slide
        δff = atan(L * κ)
        ss_yaw = v * δff / (L + 1e-3)          # steady-state yaw for the curve
        oversteer = r - ss_yaw                  # excess yaw = sliding rear
        δ = clamp(δff - 0.08 * nlat - 0.5 * ψrel - 0.35 * oversteer, -0.35, 0.35)

        # anticipatory target speed: min of the profile over the next ~60 m
        vtar = at_s(ft, ft.vtar, s)
        for ahead in (10.0, 20.0, 35.0, 50.0, 65.0)
            vtar = min(vtar, at_s(ft, ft.vtar, s + ahead))
        end
        vtar *= speed_factor
        throttle = 0.0; brake = 0.0
        if v < vtar - 0.5
            throttle = clamp(0.4 * (vtar - v), 0.0, 1.0)
        elseif v > vtar + 0.3
            brake = clamp(0.4 * (v - vtar), 0.0, 1.0)
        end
        throttle *= clamp(1.0 - 1.5 * abs(δ), 0.2, 1.0)   # ease power in corners
        # spin-catch: cut power and brake when the rear slides.  Braking (not
        # just lifting) reliably scrubs the slide and keeps the lap
        # completable; it makes the driver conservative.  NOTE: a proper
        # limit-handling driver (a quasi-steady-state lap-optimal speed
        # profile + well-damped tracking, or MPC) is the right path to
        # realistic pace — incremental tuning of this catch + a traction
        # circle was explored and only trades which corner fails (the
        # completion is a knife-edge).  See README open items.
        catch_os = qss ? 0.5 : 0.3
        catch_b = qss ? 0.25 : 0.15
        if abs(oversteer) > catch_os || abs(β) > catch_b
            throttle = 0.0
            brake = max(brake, qss ? 0.1 : 0.2)
        end

        # --- gear ---------------------------------------------------------
        rpm = engine_rpm(model.dt, gear, v / model.radius)
        if rpm > 7600 && gear < ngears(model.dt)
            gear += 1
        elseif rpm < 4200 && gear > 1
            gear -= 1
        end

        # --- forces (validated bicycle model) -----------------------------
        mt = mass(model, fuel)
        along, _ = longitudinal_accel(model, v, gear, throttle, fuel; brake=brake)
        # real terrain: gravity component along the slope in the travel
        # direction (slows uphill, gains downhill)
        if terrain !== nothing
            θw = at_s(ft, ft.theta, s; wrap=true) + ψrel
            cxw = at_s(ft, posx, s) + nlat * at_s(ft, perpx, s)
            czw = at_s(ft, posz, s) + nlat * at_s(ft, perpz, s)
            tx, tz = cos(θw), sin(θw)
            h1, _, f1 = hat3d(terrain, cxw - 3tx, czw - 3tz)
            h2, _, f2 = hat3d(terrain, cxw + 3tx, czw + 3tz)
            (f1 && f2) && (along -= 9.81 * (h2 - h1) / 6.0)   # grade = Δh/Δs
        end
        Fx = along * mt
        dW = mt * along * model.cg_h / L
        Fzf = max(mt * 9.81 * (1 - model.rear_frac) - dW, 0.0)
        Fzr = max(mt * 9.81 * model.rear_frac + dW, 0.0)
        vv = max(v, 3.0)
        αf = δ - atan(β + a * r / vv)
        αr = -atan(β - b * r / vv)
        Fyf = lateral_force(model.tire_f, sin(αf), Fzf, vv)
        capr = peak_mu_long(model.tire_r, Fzr / 2) * Fzr
        der = capr > 1 ? max(0.0, 1 - (min(max(Fx, 0.0), 0.92capr) / capr)^2)^LATERAL_CAL.slip_exponent : 1.0
        Fyr = der * lateral_force(model.tire_r, sin(αr), Fzr, vv)

        # --- integrate body dynamics --------------------------------------
        rdot = (a * Fyf * cos(δ) - b * Fyr) / model.iz
        βdot = (Fyf * cos(δ) + Fyr) / (mt * vv) - r
        r += rdot * dt
        β = clamp(β + βdot * dt, -1.0, 1.0)
        v = max(v + along * dt, 2.0)

        # --- Frenet kinematics --------------------------------------------
        course = ψrel + β
        denom = 1.0 - nlat * κ
        sdot = v * cos(course) / (abs(denom) < 0.1 ? sign(denom) * 0.1 : denom)
        ndot = v * sin(course)
        ψreldot = r - κ * sdot
        s += sdot * dt
        nlat += ndot * dt
        ψrel = atan(sin(ψrel + ψreldot * dt), cos(ψrel + ψreldot * dt))
        t += dt

        if step % record_every == 0
            cx = at_s(ft, posx, s)
            cz = at_s(ft, posz, s)
            θc = at_s(ft, ft.theta, s; wrap=true)
            push!(samples, SimSample(t, cx, cz, v, θc + ψrel, r, nlat,
                                     mod(s, ft.total), gear, throttle, brake, δ))
        end

        # crash: well beyond the runoff (still let s advance otherwise)
        if nlat > hwl + 25 || -nlat > hwr + 25
            crashed = true
            return SimResult(t, false, samples, maxlat)
        end
        # lap complete
        s >= ft.total && return SimResult(t, true, samples, maxlat)
    end
    SimResult(t, false, samples, maxlat)
end
