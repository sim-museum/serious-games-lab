# GPLAI — Julia's AI cars driven the way GPL drives its own (AIGPL-2, PO 2026-10-04:
# "Make them use the algorithm GPL AI cars use, or close to it ... The julia AI car code needs to be
# rewritten. Start by reverse engineering how GPL does AI cars").
#
# The method is read from gpl.exe itself; doc/GPL_AI_REVERSE_ENGINEERING.md has the evidence (addresses,
# parameters, replay measurements). In one paragraph: a GPL AI car is a point that moves in TRACK
# coordinates (dlong along the track, dlat across it) at 36 ticks/s. It never invents a lane: it tracks
# one of the track's authored lines (race.lp, pass1.lp, pass2.lp) with a spring/damper whose goal
# carries the line's own lateral velocity and lateral acceleration, so it rides the line exactly and any
# move between lines is a smooth second-order response. Its dlat is clamped to the authored corridor
# (minrace.lp .. maxrace.lp). It follows the car ahead single file under a separation law and pulls out
# only after being held up by a car running clearly below its line speed, into a lateral position that a
# look-ahead map says is free, joining the nearest authored line there, and holds that line for a while.
# Height, pitch, roll and yaw are spring/dampers of their own -- height to the TRACK SURFACE.
#
# Everything here runs in GPL's frame. The world comes in through a `Ref` (a closed reference polyline in
# world x/z, lap length = GPL's) and a height function supplied by the caller.
module GPLAI
using Random

const TICK = 1/36                         # GPL's AI tick (gpl_ai.ini is in per-tick units)
const T2 = 36.0^2

# ------------------------------------------------------------------------------------------------ lines
"One GPL line (.lp), resampled for interpolation. Speeds in m/s, lateral velocity in m/s at line speed."
struct Line
    v::Vector{Float64}       # record speed (m/s)
    dv::Vector{Float64}      # dlat velocity at line speed (m/s)
    d::Vector{Float64}       # dlat (m)
    flags::Vector{UInt32}    # waypoint flags (field 4 as an integer)
end
const REC = 3.0                            # metres per record (GPL: index = round(dlong / 3))

function read_line(path)
    b = read(path)
    n = Int(reinterpret(UInt32, b[5:8])[1])
    f = reinterpret(Float32, b[9:8+20n]); u = reinterpret(UInt32, b[9:8+20n])
    Line(Float64.(f[1:5:end]) .* 36.0, Float64.(f[2:5:end]) .* 36.0, Float64.(f[3:5:end]), u[5:5:end])
end
@inline function _li(L::Line, s, f::Function)          # linear between records, wrapping
    n = length(L.d); x = mod(s, n*REC)/REC; i = floor(Int, x); u = x - i
    a = mod(i, n) + 1; b = mod(i + 1, n) + 1
    f(L, a)*(1 - u) + f(L, b)*u
end
dlat(L::Line, s)  = _li(L, s, (l, i) -> l.d[i])
dlatv(L::Line, s) = _li(L, s, (l, i) -> l.dv[i])
lspeed(L::Line, s) = _li(L, s, (l, i) -> l.v[i])
"d(lateral velocity)/ds -- the line's lateral-acceleration feed-forward per unit speed (GPL 0x44a950)"
function dlatv_ds(L::Line, s)
    n = length(L.d); i = mod(round(Int, mod(s, n*REC)/REC), n) + 1; j = mod(i, n) + 1
    (L.dv[j] - L.dv[i]) / REC
end
flags(L::Line, s) = (n = length(L.d); L.flags[mod(round(Int, mod(s, n*REC)/REC), n) + 1])

# ------------------------------------------------------------------------------------------- reference
"""GPL's own track frame: the .trk section chain, each section a constant-curvature ARC (length, start heading,
heading change), walked exactly -- position and heading are continuous by construction and the curvature is
piecewise constant, as in GPL (0x497d70 reads the section radius). Nothing here is a fitted or interpolated curve:
an interpolating spline through unevenly spaced samples of these arcs loops at short sections (radius 0.0 m at
Watkins Glen s = 1523 and 2858), and that loop is what threw the first draft's cars sideways (AIGPL-2, 2026-10-04).
World = similarity transform (a, b, tx, tz) of GPL's plane: (a*x - b*y + tx, b*x + a*y + tz); `sgn` maps +dlat
onto the left normal."""
struct Ref
    S0::Vector{Float64}; L::Vector{Float64}; th0::Vector{Float64}; kap::Vector{Float64}
    x0::Vector{Float64}; y0::Vector{Float64}                  # section start points (GPL plane)
    gx::Float64; gy::Float64                                  # loop-closure error, removed in proportion to dlong
    lap::Float64
    a::Float64; b::Float64; tx::Float64; tz::Float64          # GPL plane -> world
    sgn::Float64
    lx::Vector{Float64}; lz::Vector{Float64}; ls::Vector{Float64}   # a 1 m world sampling, used ONLY to locate the player
end
"Read the .trk section chain: lengths, start headings and the start point the sim's centreline uses."
function trk_sections(b::Vector{UInt8})
    u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o)); TRK = 19685.03937
    traces = Int(u32(12)); sections = Int(u32(16)); wallsize = Int(u32(20))
    secbase = 28 + 64 + sections*4 + 32*traces*sections + wallsize
    altbase = 28 + 64 + sections*4
    toff = [i32(28+t*4) for t in 0:15]; ctr = argmin(abs.(toff[1:traces])) - 1
    x = i32(altbase + ctr*32 + 24)/TRK; y = i32(altbase + ctr*32 + 28)/TRK
    L = [i32(secbase + s*52 + 8)/TRK for s in 0:sections-1]
    th = [i32(secbase + s*52 + 12) * 2pi / 2.0^32 for s in 0:sections-1]
    (L, th, x, y)
end
function Ref(L::Vector{Float64}, th::Vector{Float64}, x::Float64, y::Float64;
             a = 1.0, b = 0.0, tx = 0.0, tz = 0.0, sgn = 1.0)
    n = length(L); wrap(d) = d > pi ? d-2pi : d < -pi ? d+2pi : d
    S0 = zeros(n); kap = zeros(n); x0 = zeros(n); y0 = zeros(n)
    for k in 1:n
        k > 1 && (S0[k] = S0[k-1] + L[k-1])
        dth = wrap(th[mod1(k+1, n)] - th[k]); kap[k] = dth / max(L[k], 1e-9)
        x0[k] = x; y0[k] = y
        if abs(dth) < 1e-9
            x += L[k]*cos(th[k]); y += L[k]*sin(th[k])
        else
            R = L[k]/dth; x += R*(sin(th[k]+dth) - sin(th[k])); y += R*(cos(th[k]) - cos(th[k]+dth))
        end
    end
    lap = S0[end] + L[end]
    r = Ref(S0, L, th, kap, x0, y0, x0[1] - x, y0[1] - y, lap, Float64(a), Float64(b), Float64(tx), Float64(tz),
            Float64(sgn), Float64[], Float64[], Float64[])
    for s in 0:1.0:lap-1e-6
        w = world(r, s, 0.0); push!(r.lx, w[1]); push!(r.lz, w[2]); push!(r.ls, s)
    end
    r
end
"the same chain, placed in the world by `ref`'s transform fitted to points `Q` that correspond to `P` (GPL plane)"
function fit_transform(r::Ref, P::Vector{NTuple{2,Float64}}, Q::Vector{NTuple{2,Float64}}; sgn = r.sgn)
    n = min(length(P), length(Q))
    px = sum(p[1] for p in P[1:n])/n; py = sum(p[2] for p in P[1:n])/n
    qx = sum(q[1] for q in Q[1:n])/n; qz = sum(q[2] for q in Q[1:n])/n
    sxx = sum((P[k][1]-px)*(Q[k][1]-qx) + (P[k][2]-py)*(Q[k][2]-qz) for k in 1:n)
    sxy = sum((P[k][1]-px)*(Q[k][2]-qz) - (P[k][2]-py)*(Q[k][1]-qx) for k in 1:n)
    spp = sum((P[k][1]-px)^2 + (P[k][2]-py)^2 for k in 1:n)
    a = sxx/spp; b = sxy/spp
    Ref(r.L, r.th0, r.x0[1], r.y0[1]; a = a, b = b, tx = qx - (a*px - b*py), tz = qz - (b*px + a*py), sgn = sgn)
end
@inline function _sec(r::Ref, s)
    sm = mod(s, r.lap)
    k = clamp(searchsortedlast(r.S0, sm), 1, length(r.L))
    (k, sm - r.S0[k], sm)
end
"(x, y, heading) in GPL's plane at dlong s on dlat 0, closure removed"
function plane(r::Ref, s)
    k, u, sm = _sec(r, s); t0 = r.th0[k]; kp = r.kap[k]
    if abs(kp*u) < 1e-9
        x = r.x0[k] + u*cos(t0); y = r.y0[k] + u*sin(t0)
    else
        R = 1/kp; x = r.x0[k] + R*(sin(t0 + kp*u) - sin(t0)); y = r.y0[k] + R*(cos(t0) - cos(t0 + kp*u))
    end
    f = sm / r.lap
    (x + r.gx*f, y + r.gy*f, t0 + kp*u)
end
"world (x, z) of GPL (dlong, dlat), and the line's heading there"
function world(r::Ref, s, d)
    x, y, th = plane(r, s)
    x += -sin(th)*r.sgn*d; y += cos(th)*r.sgn*d
    (r.a*x - r.b*y + r.tx, r.b*x + r.a*y + r.tz, th + atan(r.b, r.a))
end
heading(r::Ref, s) = plane(r, s)[3] + atan(r.b, r.a)
"curvature toward +dlat (1/m of GPL dlong): the section's, constant along it"
curv(r::Ref, s) = r.sgn * r.kap[_sec(r, s)[1]]
"locate world (x, z): (dlong, dlat, sample index). `hint` = last sample index (0: search everything)"
function locate(r::Ref, x, z, hint::Int = 0)
    m = length(r.lx); best = Inf; bk = 1; bu = 0.0
    rng = hint == 0 ? (1:m) : ((hint - 80):(hint + 80))
    @inbounds for kk in rng
        k = mod1(kk, m); j = k == m ? 1 : k + 1
        ax = r.lx[k]; az = r.lz[k]; vx = r.lx[j] - ax; vz = r.lz[j] - az; L2 = vx*vx + vz*vz
        u = L2 > 0 ? clamp(((x - ax)*vx + (z - az)*vz)/L2, 0.0, 1.0) : 0.0
        dx = x - (ax + u*vx); dz = z - (az + u*vz); d2 = dx*dx + dz*dz
        d2 < best && (best = d2; bk = k; bu = u)
    end
    hint != 0 && best > 30.0^2 && return locate(r, x, z, 0)
    s = mod(r.ls[bk] + bu*1.0, r.lap)
    # exact lateral against the arc at s (one Newton step on dlong keeps it continuous)
    for _ in 1:2
        wx, wz, th = world(r, s, 0.0)
        s = mod(s + ((x - wx)*cos(th) + (z - wz)*sin(th)) / hypot(r.a, r.b), r.lap)
    end
    wx, wz, th = world(r, s, 0.0)
    d = r.sgn*(-(x - wx)*sin(th) + (z - wz)*cos(th)) / hypot(r.a, r.b)
    (s, d, bk)
end

# ------------------------------------------------------------------------------------------ parameters
"gpl_ai.ini's fuzzy-line parameter set (SI units)"
struct Fuzzy
    k1::Float64; k2::Float64; k1c::Float64; k2c::Float64   # dlat spring/damper [1/s^2], [1/s]; cornering pair
    vsw::Float64                                            # |dlat speed| at which the cornering pair applies [m/s]
    T::Float64; Tc::Float64                                 # dlat_trans_time [ticks]
    sep::Float64; sepc::Float64                             # desired_dlong_sep [m]
    st::Float64; lt::Float64                                # short/long term lookahead [ticks]
    avoid::Float64                                          # avoid_time_coeff
end
function Fuzzy(ini, sec, d)                                  # d = the stock values, used for any missing key
    g(k, x) = get(get(ini, sec, Dict{String,Float64}()), k, x)
    Fuzzy(g("dlat_accel_k1", d[1])*T2, g("dlat_accel_k2", d[2])*36, g("cornering_dlat_accel_k1", d[3])*T2,
          g("cornering_dlat_accel_k2", d[4])*36, g("switch_to_cornering_dlat_velocity", 0.10)*36,
          g("dlat_trans_time", d[5]), g("cornering_dlat_trans_time", d[6]),
          g("desired_dlong_sep", d[7]), g("cornering_desired_dlong_sep", d[8]),
          g("short_term_lookahead", 17.0), g("long_term_lookahead", 108.0), g("avoid_time_coeff", d[9]))
end
Base.@kwdef struct Params
    follow::Fuzzy; basic::Fuzzy; abrupt::Fuzzy
    traction::Float64 = 0.011154*T2        # nominal_traction_circle [m/s^2]
    brake_eff::Float64 = 0.80              # braking_efficiency_coeff
    max_accel::Float64 = 0.006806*T2       # nominal_max_accel [m/s^2]
    latk::Float64 = 0.0125*36              # max_lat_acc_from_speed [1/s]
    auto_blocker::Float64 = 0.85           # auto_blocker_line_speed_pct
    passee_sep::Float64 = 0.35             # passee_dlong_sep_coeff
    squeezed::Float64 = 0.85               # being_squeezed_speed_coeff
    dlat_sep::Float64 = 2.70               # min_dlat_sep_front [m] (centre to centre)
    sw_close::Float64 = 0.022*36           # straightaway_pass_closing_velocity [m/s]
    sw_sep::Float64 = 10.0                 # straightaway_pass_dlong_sep [m]
    pass_radius::Float64 = 400.0           # min_cornering_outside_pass_radius [m]
    yaw_k1::Float64 = 0.12*T2; yaw_k2::Float64 = 1.0*36
    alt_k1::Float64 = 0.07*T2; alt_k2::Float64 = 0.32*36
    ride::Float64 = 0.43152                # GPL's height reference above the road [m]
    pitch_k::Float64 = 2.0/T2              # pitch_accel_coeff [rad per m/s^2]
    roll_k::Float64 = 3.0/T2               # roll_accel_coeff
    slip_k::Float64 = 0.1667*T2            # inverse_slipcurve_k [(m/s^2)/rad]
    sep_coeff::Float64 = 1.0               # track.ini track_dlong_sep_coeff
    adj::Float64 = 1.0                     # track.ini dlong_speed_adj_coeff
    vcap::Float64 = 2.41*36                # track.ini dlong_speed_maximum [m/s]
    start_hiatus::Float64 = 18.0           # base_race_start_hiatus [ticks]
end
"Params from gpl_ai.ini (parsed: section => key => value) and the track.ini numbers."
function params(ini; sep_coeff = 1.0, adj = 1.0, vcap = 2.41*36)
    g(sec, k, x) = get(get(ini, sec, Dict{String,Float64}()), k, x)
    Params(follow = Fuzzy(ini, "follow_line", (0.0045, 0.1202, 0.0086, 0.1432, 4.0, 3.0, 14.0, 13.5, 0.10)),
           basic  = Fuzzy(ini, "basic_line_transition", (0.0056, 0.1254, 0.0092, 0.1524, 4.0, 3.0, 13.5, 12.5, 0.0875)),
           abrupt = Fuzzy(ini, "abrupt_line_transition", (0.0087, 0.1224, 0.0101, 0.1274, 3.0, 2.0, 13.0, 12.0, 0.06)),
           traction = g("GP", "nominal_traction_circle", 0.011154)*T2,
           brake_eff = g("GP", "braking_efficiency_coeff", 0.80),
           max_accel = g("GP", "nominal_max_accel", 0.006806)*T2,
           latk = g("physics", "max_lat_acc_from_speed", 0.0125)*36,
           auto_blocker = g("behavior", "auto_blocker_line_speed_pct", 0.85),
           passee_sep = g("behavior", "passee_dlong_sep_coeff", 0.35),
           squeezed = g("behavior", "being_squeezed_speed_coeff", 0.85),
           dlat_sep = g("behavior", "min_dlat_sep_front", 2.70),
           sw_close = g("behavior", "straightaway_pass_closing_velocity", 0.022)*36,
           sw_sep = g("behavior", "straightaway_pass_dlong_sep", 10.0),
           pass_radius = g("behavior", "min_cornering_outside_pass_radius", 400.0),
           yaw_k1 = g("physics", "yaw_accel_k1", 0.12)*T2, yaw_k2 = g("physics", "yaw_accel_k2", 1.0)*36,
           alt_k1 = g("physics", "alt_accel_k1", 0.07)*T2, alt_k2 = g("physics", "alt_accel_k2", 0.32)*36,
           pitch_k = g("physics", "pitch_accel_coeff", 2.0)/T2, roll_k = g("physics", "roll_accel_coeff", 3.0)/T2,
           slip_k = g("physics", "inverse_slipcurve_k", 0.1667)*T2,
           start_hiatus = g("behavior", "base_race_start_hiatus", 18.0),
           sep_coeff = sep_coeff, adj = adj, vcap = vcap)
end

# ---------------------------------------------------------------------------------------------- track
const RACE, MINR, MAXR, PASS1, PASS2 = 0, 1, 2, 3, 4
const CAR_LEN = 4.0; const CAR_W = 1.75
const EDGE = 0.30                         # the goal keeps this far inside the corridor (ours, not GPL's: see goal)
const GLASS = 0.10                        # track.ini glass_wall_offset (-0.1): the in-corridor test's tolerance
struct Track
    lines::Dict{Int,Line}
    ref::Ref
    lap::Float64
    P::Params
    height::Function          # height(dlong, dlat, x, z) -> road y in the world
    # SPATD-1 S4: the lateral correction (m of dlat, sampled every `dstep` m of arc) from the RIGID frame to our drawn road.
    # The frame is one similarity transform; our road differs from GPL's locally by metres, and the AI line was off our road
    # on 9 % of Spa (the PO's "off the road on the inside at red water"). Empty = no correction (as before).
    dsh::Vector{Float64}
    dstep::Float64
end
Track(lines, ref, lap, P, height) = Track(lines, ref, lap, P, height, Float64[], 3.0)
@inline function dshift(T::Track, sa)
    n = length(T.dsh); n == 0 && return 0.0
    t = mod(sa, T.ref.lap)/T.dstep; k = floor(Int, t); u = t - k
    a = T.dsh[mod(k, n) + 1]; b = T.dsh[mod(k + 1, n) + 1]
    a + (b - a)*u
end
L(T::Track, k) = T.lines[k]
# GPL's dlong runs over 3 m x records (the replays: Ring dlong 0..22773 for 7591 records) while the arc walk of the
# .trk is slightly longer (Ring 22815 m): GPL dlong maps onto the arc chain in proportion.
_k(T::Track) = T.ref.lap / T.lap
tworld(T::Track, s, d) = (sa = s*_k(T); world(T.ref, sa, d + dshift(T, sa)))
theading(T::Track, s) = heading(T.ref, s*_k(T))
tcurv(T::Track, s) = curv(T.ref, s*_k(T)) * _k(T)
"locate world (x, z) in GPL's frame: (dlong, dlat, hint)"
tlocate(T::Track, x, z, hint::Int = 0) = ((s, d, h) = locate(T.ref, x, z, hint); (s/_k(T), d - dshift(T, s), h))
corridor(T::Track, s) = (dlat(L(T, MINR), s), dlat(L(T, MAXR), s))

# ------------------------------------------------------------------------------------------------ cars
mutable struct Car
    id::Int
    s::Float64; v::Float64                   # dlong (m, unwrapped within the lap), speed (m/s)
    d::Float64; dv::Float64; da::Float64     # dlat, its rate and acceleration
    lap::Int
    line::Int; offset::Float64               # line followed and the offset from it
    mode::Int                                # 0 follow, 1 basic transition, 2 abrupt transition
    w::Float64; dw::Float64                  # transition blend weight and its step per tick
    d0::Float64; dv0::Float64                # transition start (dlat, goal velocity)
    fromline::Int
    hold::Int                                # ticks before the car may return to the race line
    passctr::Int                             # ticks spent wanting to pass the car ahead
    passctr2::Int                            # ... on the long-term map
    passee::Int                              # id of the designated passee (GPL +0x4ef), 0 = none
    passee_t::Int                            # ticks since it last held me up
    squeezed::Bool
    alim::Float64                            # smoothed following-law acceleration limit [m/s^2]
    along::Float64; atire::Float64           # applied longitudinal / tyre lateral acceleration
    yaw::Float64; yawr::Float64              # body yaw (world) and rate
    h::Float64; hv::Float64                  # height above the road and its rate
    yroad::Float64; yroadv::Float64          # road height under the car (world) and its rate
    pace::Float64                            # per-car speed factor (the caller's chassis/driver spread)
    react::Int                               # start reaction ticks left
    pose::NTuple{6,Float64}                  # (x, y, z, yaw, pitch, roll) at the last tick
    prev::NTuple{6,Float64}                  # ... and the tick before (for drawing between ticks)
    hint::Int
    contact::Int                             # ticks since the last contact (debug/statistics)
    why::Symbol                              # what made the last line change (debug)
end
function Car(T::Track, id, s, d; v = 0.0, pace = 1.0)
    lo, hi = corridor(T, s); d = clamp(d, min(lo + 0.2, 0.5*(lo + hi)), max(hi - 0.2, 0.5*(lo + hi)))   # placed inside the corridor
    c = Car(id, mod(s, T.lap), v, d, 0.0, 0.0, 0, RACE, d - dlat(L(T, RACE), s), 0, 1.0, 0.0, d, 0.0, RACE,
            0, 0, 0, 0, 0, false, 99.0, 0.0, 0.0, 0.0, 0.0, T.P.ride - 9.80665/T.P.alt_k1, 0.0, 0.0, 0.0, pace, 0,
            ntuple(_ -> 0.0, 6), ntuple(_ -> 0.0, 6), 0, 9999, :none)
    x, z, th = tworld(T, c.s, c.d); c.yaw = th + (T.ref.sgn < 0 ? 0.0 : 0.0)
    c.yroad = T.height(c.s, c.d, x, z)
    c.pose = _pose(T, c); c.prev = c.pose
    c
end

"the goal (dlat, dlat velocity, lateral feed-forward) of the line object the car is in -- GPL 0x498080/0x445300"
function goal(T::Track, c::Car, F::Fuzzy)
    s = c.s; v = c.v
    Ln = L(T, c.line)
    vl = max(lspeed(Ln, s), 1.0)
    g  = dlat(Ln, s) + c.offset
    gv = dlatv(Ln, s) * v / vl
    ff = dlatv_ds(Ln, s) * v
    if c.mode != 0                                   # transition: blend the goal from where the car was
        Lo = L(T, c.fromline)
        g  = (1 - c.w)*c.d0 + c.w*g
        gv = ((1 - c.w)*c.dv0 + c.w*gv) * (c.mode == 2 ? 0.1 : 0.2)
        ff = (1 - c.w)*dlatv_ds(Lo, s)*v + c.w*ff
    end
    lo, hi = corridor(T, s)
    la, ha = corridor(T, s + 0.5*v)                  # ... and inside where it will be in half a second (a narrowing edge)
    if lo - GLASS <= c.d <= hi + GLASS               # in the corridor (glass_wall_offset): the goal stays inside it,
        lo = max(lo, min(la, 0.5*(lo + hi))); hi = min(hi, max(ha, 0.5*(lo + hi)))
        g = clamp(g, min(lo + EDGE, 0.5*(lo + hi)), max(hi - EDGE, 0.5*(lo + hi)))   # by EDGE, so the spring's lag never reaches the hard clamp
    elseif (c.d > hi && ff > 0) || (c.d < lo && ff < 0)
        ff *= 0.33                                    # outside and the feed-forward pushes further out
    end
    (g, gv, ff)
end

"join the nearest of RACE/PASS1/PASS2 at dlat `want` through a line transition (GPL 0x4477c0 + 0x4451d0)"
function join!(T::Track, c::Car, want; at = c.s, abrupt = false, why = :join)
    c.why = why
    best = RACE; bo = want - dlat(L(T, RACE), at)            # RACE first: a pass line wins only if strictly nearer
    for k in (PASS1, PASS2)
        o = want - dlat(L(T, k), at); abs(o) < abs(bo) - 1e-6 && (best = k; bo = o)
    end
    (c.line == best && abs(c.offset - bo) < 0.3) && return false     # already going there: a re-join is a no-op
    F = abrupt ? T.P.abrupt : T.P.basic
    _, gv, _ = goal(T, c, T.P.follow)
    c.fromline = c.line
    c.d0 = c.d; c.dv0 = gv
    c.line = best; c.offset = bo
    Tt = (abs(c.dv) < F.vsw ? F.T : F.Tc)
    c.mode = abrupt ? 2 : 1; c.dw = 1/max(Tt, 1.0); c.w = c.dw
    true
end

"spring/damper with a Heun step, GPL 0x496860 (SI, dt = one tick)"
@inline function spring(x, g, v, gv, k1, k2, dt)
    a1 = k1*(g - x) + k2*(gv - v)
    xp = x + v*dt + 0.5*a1*dt^2; vp = v + a1*dt
    a2 = k1*(g - xp) + k2*(gv - vp)
    0.5*(a1 + a2)
end

# --------------------------------------------------------------------------------------- the look-ahead map
"""What car `c` sees of the others `τ` ticks ahead (GPL 0x445c10/0x4481d0/0x447f50): one entry per car within
98 m ahead -- its projected lateral interval and the acceleration that would keep the desired separation behind
it -- and, for cars overlapping me along the track (alongside), their lateral interval as plain occupancy.
`others` holds (s, d, dv, v, line, offset, is_player, id, longitudinal accel). Entry: (lo, hi, a_allow, projected gap, idx, kind),
kind 1 = ahead (a blocker), 2 = alongside (occupies lateral space only)."""
function look(T::Track, c::Car, others, τ, F::Fuzzy)
    P = T.P; out = NTuple{7,Float64}[]
    t = τ*TICK
    for (k, o) in enumerate(others)
        gap = mod(o[1] - c.s + T.lap/2, T.lap) - T.lap/2        # + ahead
        # behind me: only a car that will be alongside within the look-ahead matters (GPL 0x447cc0 walks the
        # cars behind for the lateral bounds); ahead: up to 98 m
        gapt = gap + (o[4] - c.v)*τ*TICK
        (-CAR_LEN < gap <= 98.27 || (gap <= -CAR_LEN && gapt > -CAR_LEN)) || continue
        isp = o[7] > 0.5
        pd = if t >= 1.0 && !isp                                # an AI car: where its own line+offset puts it
            dlat(L(T, Int(o[5])), o[1] + o[4]*t) + o[6]
        elseif t >= 1.0                                         # the player: the race line at his current offset from it
            dlat(L(T, RACE), o[1] + o[4]*t) + (o[2] - dlat(L(T, RACE), o[1]))
        else
            o[2] + o[3]*t
        end
        # lateral room it needs (GPL 0x4481d0): the full separation at speed, shrinking to 1.90 m for a slow car,
        # +0.33 m for the human (whose line the AI cannot predict)
        w = (o[4] < 0.6204*36 ? max(1.9035, o[4]/(0.6204*36)*P.dlat_sep) : P.dlat_sep) + (isp ? 0.33 : 0.0)
        a = min(pd, 0.5*(pd + o[2])); b = max(pd, 0.5*(pd + o[2]))  # the short map also covers where it is now
        if gap <= CAR_LEN                                       # alongside (now or within the look-ahead): occupies lateral space, is not followed
            push!(out, (min(a, o[2]) - w, max(b, o[2]) + w, -99.0, gap, Float64(k), 2.0, o[1] + o[4]*t))
            continue
        end
        sep = F.sep*P.sep_coeff
        braking = o[9] < -3.0                                   # the car ahead is braking hard
        (c.passee != 0 && Int(o[8]) == c.passee && !braking) && (sep = max(6.45, sep*P.passee_sep))   # GPL 0x4468f0: tuck in behind the passee
        dvc = c.v - o[4] + (braking ? -o[9]*0.5 : 0.0)         # closing speed, with half a second of its braking
        Tr = max((36.0 + 25.2292*(2.85384 - c.v/36))/36, 0.5)  # GPL 0x4985e0's speed-dependent reaction time
        gp = gap + (o[4] - c.v)*t                               # projected gap at the look-ahead
        aal = 2*(gap - sep - max(dvc, 0.0)*(Tr + t))/t^2
        push!(out, (a - w, b + w, aal, gp, Float64(k), 1.0, o[1] + o[4]*t))
    end
    out
end
"blocker AHEAD at lateral position x in map `m`: (a_allow, projected gap, idx) of the most restrictive, or nothing"
function blocked_at(m, x)
    r = nothing
    for e in m
        (e[6] == 1.0 && e[1] <= x <= e[2]) || continue
        (r === nothing || e[3] < r[1]) && (r = (e[3], e[4], e[5]))
    end
    r
end
"is lateral position x occupied by a car alongside?"
occupied(m, x) = any(e -> e[6] == 2.0 && e[1] <= x <= e[2], m)
"""scan from `from` toward `to` in 0.33 m bins for the first position that does not restrict car `c`
(GPL 0x4461a0); `need` = the acceleration the car wants, `lo/hi` the corridor"""
function free_toward(m, from, to, need, reach, lo, hi)
    st = to >= from ? 0.33 : -0.33
    n = max(1, ceil(Int, abs(to - from)/0.33))
    for k in 0:n
        x = clamp(from + k*st, lo, hi)
        occupied(m, x) && continue
        b = blocked_at(m, x)
        (b === nothing || b[1] >= need || b[2] >= reach) && return x
    end
    nothing
end

# -------------------------------------------------------------------------------------------- decision
"accel the car would like at speed v (engine-limited; GPL 0x497940 'max accel')"
a_engine(P::Params, v) = min(P.max_accel, 536.0/max(v, 1.0)) - 0.42/560*v^2

"no section tighter than min_cornering_outside_pass_radius within `dist` metres ahead"
function straight_ahead(T::Track, s, dist)
    for x in 0:10.0:dist
        abs(tcurv(T, s + x)) > 1/T.P.pass_radius && return false
    end
    true
end
"""pull out past blocker entry `bi`: the nearest free position beside its interval, inside the corridor; join the
nearest authored line there and hold it (0x446ef0 + 0x4477c0 + 0x447a60). true if a move was made."""
function try_pass!(T::Track, c::Car, m, bi, need, lo, hi, t, rng, tpass, sb = c.s + c.v*t, vb = 0.0)
    k = findfirst(e -> Int(e[5]) == bi && e[6] == 1.0, m); k === nothing && return false
    lo2, hi2 = corridor(T, sb); lo = max(lo, lo2); hi = min(hi, hi2)   # valid both here and beside the blocker
    e = m[k]; cand = Float64[]
    for x in (e[1] - 0.2, e[2] + 0.2)
        lo + 0.3 <= x <= hi - 0.3 || continue
        occupied(m, x) && continue
        bb = blocked_at(m, x); (bb === nothing || bb[1] >= need) && push!(cand, x)
    end
    # the line offset is taken where the blocker IS (the clearance matters there), not at my look-ahead point --
    # on a long look-ahead (3 s) the line can be metres elsewhere by then and line+offset would miss the gap
    gb = mod(sb - c.s, T.lap); at = c.s + clamp(gb, 0.0, c.v*t)
    isempty(cand) && return false
    join!(T, c, cand[argmin(abs.(cand .- c.d))]; at = at, why = :pass)
    # hold the new line until past the blocker (GPL 0x447a60: time to close the gap x 1.5, at least 1 s, + 0-35 ticks)
    tclear = (mod(sb - c.s, T.lap) + 2CAR_LEN) / max(c.v - vb, 1.0) * 36
    c.hold = clamp(round(Int, 1.5*max(tpass, tclear)), 36, 216) + rand(rng, 0:35)   # 1..6 s
    c.passctr = 0
    true
end

"the line join! would pick for `want` at `at`, followed with its offset from s0 to s1, stays inside the corridor"
function path_inside(T::Track, want, at, s0, s1)
    best = RACE; bo = want - dlat(L(T, RACE), at)
    for k in (PASS1, PASS2)
        o = want - dlat(L(T, k), at); abs(o) < abs(bo) - 1e-6 && (best = k; bo = o)
    end
    for x in s0:3.0:s1
        lo, hi = corridor(T, x); y = dlat(L(T, best), x) + bo
        (lo + 0.2 <= y <= hi - 0.2) || return false
    end
    true
end

"""where car `c` will be across the track `t` seconds ahead (GPL 0x44c920): beyond a second, along its own line +
offset at its projected dlong; nearer, its current lateral plus its rate -- clamped into the corridor there"""
function own_proj(T::Track, c::Car, t)
    sp = c.s + c.v*t
    lo, hi = corridor(T, sp)
    if t >= 1.0 || c.mode != 0
        clamp(dlat(L(T, c.line), sp) + c.offset, lo, hi)
    else
        g, gv, _ = goal(T, c, T.P.follow); clamp(g + gv*t, lo, hi)
    end
end

"""the most restrictive car ahead that my own path meets: for each map entry, my lateral where I reach its projected
station (along my line + offset when that is a second or more away), tested against its interval"""
function blocked_on_path(T::Track, c::Car, m, t)
    r = nothing
    for e in m
        e[6] == 1.0 || continue
        ahead = mod(e[7] - c.s, T.lap)
        tt = min(t, ahead/max(c.v, 1.0))
        pd = own_proj(T, c, tt)
        e[1] <= pd <= e[2] || continue
        (r === nothing || e[3] < r[1]) && (r = (e[3], e[4], e[5]))
    end
    r
end

"""GPL's avoidance (0x4468f0) on one look-ahead map: :acted (moved to pass), :blocked (stay in line behind the
blocker -- the following law holds the car), :free (nothing in my lane). `map` 1 = short term, 2 = long term."""
function avoid!(T::Track, c::Car, others, m, τ, map, rng, scale)
    P = T.P; F = P.follow; t = τ*TICK
    lo, hi = corridor(T, c.s)
    need = a_engine(P, c.v)
    # GPL 0xba0: a blocker projected further than my own travel over the look-ahead is no blocker; a car inside the
    # separation distance always counts (else a car that has STOPPED behind a stopped car never sees it again)
    reach = max(c.v*t, F.sep*P.sep_coeff + 6.0)
    b = blocked_on_path(T, c, m, t)
    (b !== nothing && b[1] < need && b[2] < reach) || return :free
    o = others[Int(b[3])]
    faster = c.v > o[4] || o[4] < 2.0                    # a (nearly) stopped car is always passable (low-speed override)
    ratio = o[4] / max(min(lspeed(L(T, RACE), o[1])*P.adj, P.vcap)*scale, 1.0)   # its pace against the line's
    slowB = ratio < P.auto_blocker || o[4] < 5.0
    gap = mod(o[1] - c.s + T.lap/2, T.lap) - T.lap/2
    vfree = min(lspeed(L(T, c.line), c.s)*P.adj, P.vcap)*c.pace*scale
    if map == 1 && vfree > o[4] + 0.5 && o[8] > 0.5     # it holds me up: it becomes my designated passee
        c.passee = Int(o[8]); c.passee_t = 0
    end
    # straightaway pass (long-term map): the passee, on a straight, while it holds me back
    if map == 2 && c.passee != 0 && Int(o[8]) == c.passee && straight_ahead(T, c.s, 150.0) &&
       (c.alim < 0.995*need || c.v - o[4] > P.sw_close) && gap < (2.0 - min(ratio, 1.0))*P.sw_sep + 2.0
        try_pass!(T, c, m, Int(b[3]), need, lo, hi, t, rng, 1.5*36.0, o[1], o[4]) && return :acted
    end
    ctr = map == 1 ? c.passctr : c.passctr2
    if !faster || !slowB
        ctr = max(ctr - 1, 0)                            # stay in line; the following law holds me back
    else
        ctr += 1
        # a crawling or stopped car is passed at once: the counter (GPL +0x43a) is for deciding to pass a car at speed
        tpass = o[4] < 5.0 ? 0.0 : max(gap, 1.0)/max(c.v - o[4], 0.3) * 36 * F.avoid * 4
        if ctr > tpass && try_pass!(T, c, m, Int(b[3]), need, lo, hi, t, rng, tpass, o[1], o[4])
            c.passctr = 0; c.passctr2 = 0; return :acted
        end
    end
    map == 1 ? (c.passctr = ctr) : (c.passctr2 = ctr)
    :blocked
end

"""GPL's BASIC RACING think step (0x442f60) for one car. `others` as in `look`; returns nothing.
`rng` gives the random part of the hold time."""
function think!(T::Track, c::Car, others, rng, scale = 1.0)
    P = T.P; F = P.follow
    c.hold > 0 && (c.hold -= 1)
    c.squeezed = false
    τs = F.st; t = τs*TICK
    m = look(T, c, others, τs, F)
    lo, hi = corridor(T, c.s)
    need = a_engine(P, c.v)
    reach = max(c.v*t, F.sep*P.sep_coeff + 6.0)
    r = avoid!(T, c, others, m, τs, 1, rng, scale)
    r == :acted && return nothing
    if r == :free
        c.passctr = max(c.passctr - 1, 0)
        c.passee_t += 1; c.passee_t > 108 && (c.passee = 0)
        pd = own_proj(T, c, t)
        # side by side (0x445e50): a car overlapping me along the track, converging on my lateral -> move away
        for (k, o) in enumerate(others)
            gap = mod(o[1] - c.s + T.lap/2, T.lap) - T.lap/2
            abs(gap) < 5.5 || continue
            od = o[2] + o[3]*t
            sep = abs(pd - od)
            sep < P.dlat_sep - 0.6 || continue
            side = c.d >= o[2] ? 1.0 : -1.0
            lo2, hi2 = corridor(T, c.s + c.v*t)
            want = clamp(od + side*(P.dlat_sep - 0.3), lo + 0.3, hi - 0.3)
            if abs(want - od) >= P.dlat_sep - 0.9
                join!(T, c, want; at = c.s, abrupt = (o[3] - c.dv)*side > 0.05*36, why = :side)   # alongside NOW: offset taken here
                c.hold = max(c.hold, round(Int, τs))
            else
                c.squeezed = true                         # no room: give way (being_squeezed_speed_coeff)
            end
            return nothing
        end
    end
    # out of the corridor: back toward the pass line on my side (0x4472e0 with PASS1/PASS2)
    if !(lo - GLASS <= c.d <= hi + GLASS) && c.mode == 0
        join!(T, c, clamp(c.d, lo + 0.5, hi - 0.5); why = :corridor); return nothing
    end
    # hold expired and not on the race line: approach it as far as the map allows (0x4472e0 with RACE)
    if c.hold <= 0 && (c.line != RACE || abs(c.offset) > 1e-3) && c.mode == 0
        target = dlat(L(T, RACE), c.s + c.v*t)
        lo2, hi2 = corridor(T, c.s + c.v*t)
        x = free_toward(m, target, c.d, need, reach, max(lo, lo2), min(hi, hi2))
        x !== nothing && join!(T, c, x; at = c.s + c.v*t, why = :approach)
    end
    # long-term avoidance (0x4468f0 with map 1, above long_term_check_min_speed): the 3 s look-ahead
    if c.v > 0.6204*36 && c.mode == 0
        avoid!(T, c, others, look(T, c, others, F.lt, F), F.lt, 2, rng, scale)
    end
    nothing
end

# --------------------------------------------------------------------------------------------- advance
"""one 36 Hz tick of car `c`'s motion (GPL 0x496930): longitudinal (line speed, following law, traction
circle), lateral (spring/damper on the goal, clamped by grip and the corridor), yaw, height."""
function advance!(T::Track, c::Car, m_follow, scale, vcap_rel)
    P = T.P; dt = TICK
    # ---- longitudinal
    Ln = L(T, c.line)
    vt = min(lspeed(Ln, c.s)*P.adj, P.vcap) * c.pace * scale
    c.squeezed && (vt *= P.squeezed)
    vt = min(vt, vcap_rel)
    aw = (vt - c.v)/dt
    alimf = m_follow === nothing ? 99.0 : m_follow
    c.alim += (alimf - c.alim)*0.3                       # GPL 0x44a: a smoothed minimum
    aw = min(aw, c.alim)
    amax = a_engine(P, c.v); abrk = P.brake_eff*P.traction
    lat_used = abs(c.atire)
    rem = sqrt(max(P.traction^2 - lat_used^2, 0.0))
    aw = clamp(aw, -min(abrk, max(rem, 0.3*abrk)), min(amax, rem))
    c.react > 0 && (c.react -= 1; aw = 0.0)
    c.along = aw
    c.v = max(c.v + aw*dt, 0.0)
    # ---- lateral
    F = c.mode == 2 ? P.abrupt : c.mode == 1 ? P.basic : P.follow
    corner = abs(c.dv) >= F.vsw
    k1 = corner ? F.k1c : F.k1; k2 = corner ? F.k2c : F.k2
    g, gv, ff = goal(T, c, F)
    a = spring(c.d, g, c.dv, gv, k1, k2, dt) + ff
    cen = tcurv(T, c.s) * c.v^2                       # the frame turns: holding dlat needs this much tyre force
    tyre = a + cen
    lim = min(max(P.latk*c.v, abs(cen)), P.traction)
    tyre = clamp(tyre, -lim, lim)
    c.atire = tyre
    c.da = tyre - cen
    c.dv += c.da*dt
    c.d  += c.dv*dt
    # ---- transition bookkeeping (0x4452a0)
    if c.mode != 0
        c.w += c.dw
        c.w > 1.0 && (c.mode = 0; c.w = 1.0)
    end
    # ---- along the track
    s0 = c.s
    c.s += c.v*dt                                        # GPL: dlong += dlong speed (no geometry in the motion)
    if c.s >= T.lap; c.s -= T.lap; c.lap += 1; end
    lo, hi = corridor(T, c.s)                            # GPL 0x496930: the authored corridor is a hard edge
    if c.d < lo || c.d > hi
        Δ = clamp(c.d, lo, hi) - c.d                     # GPL adds the displacement to the rate and the acceleration too
        c.d += Δ; c.dv += Δ/dt; c.da += Δ/dt^2
    end
    # ---- yaw: path heading + slip from the tyre force, through a spring/damper (0x4982f0)
    th = theading(T, c.s) + (T.ref.sgn > 0 ? 1 : -1)*atan(c.dv, max(c.v, 0.5)) * (c.v > 0.5 ? 1 : 0)
    slip = (T.ref.sgn > 0 ? 1 : -1) * tyre / P.slip_k
    yg = th + slip
    e = atan(sin(yg - c.yaw), cos(yg - c.yaw))
    yrg = tcurv(T, c.s)*c.v*(T.ref.sgn > 0 ? 1 : -1)
    c.yawr += (P.yaw_k1*e + P.yaw_k2*(yrg - c.yawr))*dt
    c.yaw += c.yawr*dt
    # ---- height above the road surface (0x497ab0): spring/damper in contact, free flight above
    x, z, _ = tworld(T, c.s, c.d)
    yr = T.height(c.s, c.d, x, z)
    yrv = (yr - c.yroad)/dt
    if !isfinite(yr); yr = c.yroad; yrv = 0.0; end
    jump = abs(yr - c.yroad) > 2.0                       # a discontinuity in the height source: re-seat, never fly
    yra = jump ? 0.0 : (yrv - c.yroadv)/dt
    c.yroad = yr; c.yroadv = jump ? 0.0 : yrv
    gext = -9.80665 - clamp(yra, -60.0, 60.0)
    ah = (c.h <= P.ride ? P.alt_k1*(P.ride - c.h) - P.alt_k2*c.hv : 0.0) + gext
    c.hv += ah*dt; c.h += c.hv*dt
    c.h < 0.0 && (c.h = 0.0; c.hv = max(c.hv, 0.0))
    c.prev = c.pose
    c.pose = _pose(T, c)
    nothing
end
function _pose(T::Track, c::Car)
    P = T.P
    x, z, _ = tworld(T, c.s, c.d)
    heq = P.ride - 9.80665/P.alt_k1                     # resting height: the car origin sits on the road there
    y = c.yroad + (c.h - heq)
    # road slope and camber under the car
    h1 = T.height(c.s + 2.0, c.d, tworld(T, c.s + 2.0, c.d)[1], tworld(T, c.s + 2.0, c.d)[2])
    h0 = T.height(c.s - 2.0, c.d, tworld(T, c.s - 2.0, c.d)[1], tworld(T, c.s - 2.0, c.d)[2])
    hl = T.height(c.s, c.d + 0.8, tworld(T, c.s, c.d + 0.8)[1], tworld(T, c.s, c.d + 0.8)[2])
    hr = T.height(c.s, c.d - 0.8, tworld(T, c.s, c.d - 0.8)[1], tworld(T, c.s, c.d - 0.8)[2])
    pr = isfinite(h1) && isfinite(h0) ? atan(h1 - h0, 4.0) : 0.0
    rr = isfinite(hl) && isfinite(hr) ? atan(hl - hr, 1.6) : 0.0
    pitch = pr - P.pitch_k*c.along
    roll  = T.ref.sgn*rr + P.roll_k*c.atire
    (x, isfinite(y) ? y : c.yroad, z, c.yaw, pitch, roll)
end

"""The speed factor that makes the race line's lateral demand fit the grip: GPL's line speeds were authored for
GPL's own AI grip, which is not the julia Lotus's. p98 of |centreline curvature x v^2 + line lateral accel| at
line speed must not exceed `frac` of the traction circle. 1.0 when it already fits."""
function grip_scale(T::Track; frac = 0.95, q = 0.98)
    Ln = L(T, RACE); dem = Float64[]
    for s in 0:REC:T.lap-REC
        v = min(lspeed(Ln, s)*T.P.adj, T.P.vcap)
        push!(dem, abs(tcurv(T, s)*v^2 + dlatv_ds(Ln, s)*v))
    end
    sort!(dem); d = dem[clamp(round(Int, q*length(dem)), 1, length(dem))]
    min(1.0, sqrt(frac*T.P.traction/max(d, 1e-6)))
end

# ---------------------------------------------------------------------------------------------- field
mutable struct Field
    T::Track
    cars::Vector{Car}
    acc::Float64                 # time not yet spent in whole ticks
    rng::Any
    stats::Dict{Symbol,Int}
end
Field(T::Track, cars; seed = 1967) = Field(T, cars, 0.0, MersenneTwister(seed), Dict{Symbol,Int}())


"""Advance the field by `dt` seconds of wall time (whole 36 Hz ticks; the remainder carries) and return the
drawn poses interpolated between the last two ticks. `player` = (dlong, dlat, dlat rate, speed) or nothing.
Returns (poses, player_hit)."""
function step!(f::Field, dt; player = nothing, scale = 1.0, vrel = Inf)
    f.acc += dt
    hit = false
    while f.acc >= TICK
        f.acc -= TICK
        hit |= tick!(f, player, scale, vrel)
    end
    α = f.acc / TICK
    poses = NTuple{6,Float64}[]
    for c in f.cars
        p = c.prev; q = c.pose
        dyaw = atan(sin(q[4] - p[4]), cos(q[4] - p[4]))
        push!(poses, (p[1] + α*(q[1]-p[1]), p[2] + α*(q[2]-p[2]), p[3] + α*(q[3]-p[3]), p[4] + α*dyaw,
                      p[5] + α*(q[5]-p[5]), p[6] + α*(q[6]-p[6])))
    end
    (poses, hit)
end
function tick!(f::Field, player, scale, vrel)
    T = f.T; P = T.P; n = length(f.cars)
    hit = false
    # what everyone sees: (s, d, dv, v, line, offset, is_player)
    view = NTuple{9,Float64}[(c.s, c.d, c.dv, c.v, Float64(c.line), c.offset, 0.0, Float64(c.id), c.along) for c in f.cars]
    player !== nothing && push!(view, (player[1], player[2], player[3], player[4], 0.0, 0.0, 1.0, 0.0, length(player) >= 5 ? player[5] : 0.0))
    for (i, c) in enumerate(f.cars)
        others = [view[k] for k in eachindex(view) if k != i]
        think!(T, c, others, f.rng, scale)
        # following law: the most restrictive car ahead in my own lane at the short look-ahead
        F = P.follow; t = F.st*TICK
        m = look(T, c, others, F.st, F)
        b = blocked_at(m, own_proj(T, c, t))
        al = b === nothing ? 99.0 : b[1]                 # GPL 0x4467f0: the cell at my PROJECTED lateral only
        advance!(T, c, al, scale, vrel)
    end
    # contact (should be rare): push apart laterally and match speeds, never teleport
    for a in 1:n-1, b in a+1:n
        ca = f.cars[a]; cb = f.cars[b]
        ds = mod(ca.s - cb.s + T.lap/2, T.lap) - T.lap/2
        (abs(ds) < CAR_LEN && abs(ca.d - cb.d) < CAR_W) || continue
        f.stats[:contact] = get(f.stats, :contact, 0) + 1
        sgn = ca.d >= cb.d ? 1.0 : -1.0
        cl = (cb.dv - ca.dv)*sgn                          # closing rate across the track (> 0: converging)
        cl > -0.5 && (ca.dv += sgn*(cl + 0.5)/2; cb.dv -= sgn*(cl + 0.5)/2)   # rubbing: leave them separating at 0.5 m/s
        # nose to tail: the follower matches the leader's speed. Side by side: NO speed matching -- that locks the pair
        # together and the squeezed car could never drop back (being_squeezed_speed_coeff)
        if abs(ds) > CAR_LEN/2
            if ds > 0; cb.v = min(cb.v, ca.v); else; ca.v = min(ca.v, cb.v); end
        end
        ca.contact = 0; cb.contact = 0
    end
    if player !== nothing
        for c in f.cars
            ds = mod(c.s - player[1] + T.lap/2, T.lap) - T.lap/2
            (abs(ds) < CAR_LEN && abs(c.d - player[2]) < CAR_W) || continue
            hit = true; f.stats[:player_contact] = get(f.stats, :player_contact, 0) + 1
            sg = c.d >= player[2] ? 1.0 : -1.0
            cl = (player[3] - c.dv)*sg; cl > 0 && (c.dv += sg*cl)      # the AI yields the converging rate
            ds < -CAR_LEN/2 && (c.v = min(c.v, player[4]))
        end
    end
    for c in f.cars; c.contact += 1; end
    hit
end

end
