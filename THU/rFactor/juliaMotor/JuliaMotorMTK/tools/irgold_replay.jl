# IRGOLD-1 S1 (2026-10-11): the acceptance metric for "indistinguishable from the iRacing Lotus 49".
#
# Every kind of gold driving in the PO's 261010/11 test session, replayed through the session's own sim car (springs,
# bars, diff, toe, camber, bias, fuel = corner weights, from that .ibt) with the gold's OWN inputs -- steering, throttle,
# brake, clutch, gear -- and scored on what the driver feels: yaw rate, lateral g, sideslip, speed, roll and the rim
# torque (force feedback).
#
# Two kinds of window, found from the channels (no hand list):
#   :steady   the 0.5 s before the window holds yaw rate, lateral g, steering and speed nearly constant (a straight, a
#             gentle Ring curve, a skidpad circle), then something happens (steering, a brake, a lift, a squeeze). The
#             sim is settled onto the gold's speed AND yaw rate (4 s, integral steering on yaw rate, PI throttle), which
#             scores the steady state too (steer angle needed at > 0.4 g), then the gold's input CHANGES are applied from
#             0.25 s before the event for up to JM_IRG_SECS (5) s. Flicks, brake stops, slide initiations, Ring straights.
#   :brake    a stop from > 90 km/h (the brake-bias sweep): the pedal comes on after 0.5 s off it with |ay| < 0.25 g;
#             settled like :steady, replayed from 0.25 s before the pedal.
#   :dynamic  no steady start for 5 s (the slalom's continuous weave): the gold's u, v, r are injected at a lateral-g
#             zero crossing (body roll ~0) and the gold's steering is applied as it is.
# A window ends early when the gold leaves the track, drops below 10 m/s, or 0.5 s after its |β| passes 25° (a spin:
# whether the sim spins too is recorded, the trace after it is not scored).
#
# Road grade (the Ring stops): an external force −m·g·sin(grade), grade = dAlt/ds over ±1 s (Alt is quantised to
# ~0.1 m, harmless over 100 m). Monza and the skidpad are flat to < 0.3 %.
#
#   julia --project=. tools/irgold_replay.jl                        all windows, every 261010 file
#   JM_IRG_FILES="15-45-00,19-30-13"  JM_IRG_KIND=straight          a subset
#   JM_IRG_DUMP=<dir>                                               per-window CSV traces (gold and sim) for plots
using Printf, Statistics
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "replay_261005.jl"))             # settle!, install!, ibt_open, ch, setup_params, DriveRT3D, G, LWB
# IRGOLD-1 S17: the replays feed the driver's PEDAL (ClutchRaw) through the car's own anti-stall (S15) -- the gold's input is the
# foot; iRacing's engagement (Clutch) is its anti-stall's OUTPUT. JM_IRG_CLUTCH=engaged feeds Clutch with the anti-stall off (S1-S16).
const IRG_RAWCLUTCH = get(ENV, "JM_IRG_CLUTCH", "raw") != "engaged"
DriveRT3D.ANTISTALL[] = IRG_RAWCLUTCH
using ModelingToolkit, OrdinaryDiffEq

const DG = expanduser("~/gold standard/julia racer/261010")

# IRGOLD-1 S6 trial (JM_MAP2D=1): the part-throttle map by rpm -- measured on every 261010 row (261011/tools, the S8 method):
# the torque fraction falls with rpm at part throttle (pedal 0.5: 0.48 at 4-5.5k, 0.43 at 5.5-7k, 0.41 at 7-8k rpm).
# Overrides DriveRT3D.engine_torque in THIS process before any car is built (src untouched while gates run).
if get(ENV, "JM_MAP2D", "0") == "1"
    @eval DriveRT3D begin
        const _TK_LO = ((0.0, 0.0), (0.1, 0.02), (0.2, 0.12), (0.3, 0.22), (0.4, 0.34), (0.5, 0.48), (0.6, 0.62), (0.7, 0.77), (0.8, 0.90), (0.9, 0.96), (1.0, 1.0))
        const _TK_HI = ((0.0, 0.0), (0.1, 0.02), (0.2, 0.11), (0.3, 0.19), (0.4, 0.27), (0.5, 0.41), (0.6, 0.53), (0.7, 0.70), (0.8, 0.87), (0.9, 0.95), (1.0, 1.0))
        _ramps(thr, k) = (f = 0.0*thr; s0 = 0.0; for i in 1:length(k)-1; s = (k[i+1][2] - k[i][2])/(k[i+1][1] - k[i][1]); f += (s - s0)*max(0.0, thr - k[i][1]); s0 = s; end; f)
        function engine_torque(rpm, throttle; redline = 9500.0, T0 = EFRIC_T0, k = EFRIC_K, r0 = EFRIC_R0, w = EFRIC_W)
            wot = max(0.0, wot_torque(rpm)); cut = 0.5*(1 - tanh((rpm - redline)/200.0))
            fric = (T0 + k*rpm) * 0.5*(1 + tanh((rpm - r0)/w))
            wr = min(max((rpm - 4750.0)/2750.0, 0.0), 1.4)
            f = _ramps(throttle, _TK_LO) + wr*(_ramps(throttle, _TK_HI) - _ramps(throttle, _TK_LO))
            f*wot*cut - (1 - f)*fric
        end
    end
    println("JM_MAP2D: the 2-D part-throttle map is ON in this process")
end
const IRG_SECS = parse(Float64, get(ENV, "JM_IRG_SECS", "5"))
# Files that did not use the setup the test plan stipulated (PO 2026-10-12: "the chronologically first monza .ibt was
# using the wrong setup"; tools 261011/tools/setupcheck2.py): 19-30-13 ran the SKIDPAD variant (raised perches, right
# tyres 179 kPa) instead of the road setup for test 2. Excluded from every IRGOLD analysis.
const IRG_EXCLUDE = ("19-30-13",)
irg_files(fs) = filter(f -> !any(x -> occursin(x, f), IRG_EXCLUDE), fs)

"Test label per file (IRGOLD-1 table in PRODUCT_BACKLOG.md), from the file's clock time."
function testof(fn)
    t = match(r"(\d\d-\d\d-\d\d)\.ibt$", fn).captures[1]
    d = Dict("17-46-09" => "T1 slides", "19-18-36" => "T1 slides", "19-30-13" => "T2 slalom", "19-33-54" => "T2 slalom",
             "19-34-35" => "T2 slalom", "14-52-47" => "T3 bias50", "14-55-22" => "T3 bias50", "14-58-38" => "T3 bias50",
             "15-03-24" => "T3 bias53.5", "15-07-27" => "T3 bias58", "15-09-41" => "T3 bias58", "15-20-13" => "T4 arb soft",
             "15-24-06" => "T4 arb 4", "15-28-20" => "T4 arb firm", "15-34-40" => "T6 flicks", "15-35-50" => "T6 flicks",
             "15-45-00" => "T6 flicks", "15-54-13" => "T7 fuel20", "16-07-12" => "T7 fuel180", "16-12-38" => "T7 fuel145",
             "16-19-11" => "WW T1 slides", "16-43-06" => "WW T1 slides", "16-53-12" => "WW T6 flicks", "17-03-15" => "WW T2 slalom",
             # IRTEST-261012 (IRGOLD-1 S16): test 3 power drifts at Monza (Parabolica), free laps at Watkins Glen Classic,
             # tests 1-2 (free revs, standing starts) in the rest
             "21-22-33" => "WW T8 drifts", "21-41-42" => "T8 drifts", "21-52-34" => "T9 Glen", "21-53-58" => "T9 Glen",
             "21-55-38" => "T9 Glen", "21-57-57" => "WW T9 Glen", "21-10-22" => "WW T10 starts", "21-14-35" => "WW T10 starts",
             "21-16-02" => "WW T10 starts", "21-36-40" => "T10 starts", "21-38-38" => "T10 starts")
    occursin("261004", fn) ? "261004 skid" : occursin("261005", fn) ? "261005 skid" : get(d, t, "?")
end

sub(f, n) = hcat((channel(f, n; idx = i) for i in 1:6)...)        # 360 Hz sub-samples, rows × 6

"Gold channels of one file (60 Hz, plus row means of the 360 Hz channels)."
function goldfile(fn)
    f = ibt_open(fn); sp = setup_params(f.yaml)
    c = Dict{String,Vector{Float64}}()
    for n in ("Speed", "SteeringWheelAngle", "Throttle", "Brake", "Clutch", "ClutchRaw", "Gear", "RPM", "Alt", "IsOnTrackCar", "AirDensity",
              "PlayerTrackSurface", "Roll", "LFspeed", "RFspeed", "LRspeed", "RRspeed", "LapDist")
        x = ch(f, n); x === nothing || (c[n] = x)
    end
    for n in ("YawRate", "LatAccel", "LongAccel", "VelocityX", "VelocityY", "SteeringWheelTorque", "RollRate",
              "LFshockDefl", "RFshockDefl", "LRshockDefl", "RRshockDefl")
        c[n] = vec(mean(sub(f, n); dims = 2))
    end
    # suspension roll per axle [deg] from the shock deflections through the motion ratios (IRFIT-261004 SUSP-1);
    # + = the left side more compressed, as simroll(). The gold's `Roll` channel is not body roll (0.1-1.1 °/g by session).
    c["rollF"] = rad2deg.((c["LFshockDefl"] .- c["RFshockDefl"]) ./ 0.78 ./ 1.50)
    c["rollR"] = rad2deg.((c["LRshockDefl"] .- c["RRshockDefl"]) ./ 0.648 ./ 1.50)
    # PHYSFID-1 S8: axle heave at the wheel [mm] (shock deflection through the same motion ratios; + = compressed)
    c["heaveF"] = 1000 .* (c["LFshockDefl"] .+ c["RFshockDefl"]) ./ 2 ./ 0.78
    c["heaveR"] = 1000 .* (c["LRshockDefl"] .+ c["RRshockDefl"]) ./ 2 ./ 0.648
    v = c["Speed"]; n = length(v)
    s = cumsum(v) ./ 60                                          # distance [m]
    grade = zeros(n)
    for k in 61:n-60
        ds = s[k+60] - s[k-60]; ds > 30 && (grade[k] = (c["Alt"][k+60] - c["Alt"][k-60])/ds)
    end
    c["grade"] = grade
    # IRGOLD-1 S20: the road's BANK/CAMBER, measured by the gold itself (JM_IRG_BANK=1). The accelerometer reads the tyres'
    # force (specific force); the kinematic lateral acceleration is dVy/dt + Vx·r; the difference is gravity's lateral
    # component g·sin(bank), plus the accelerometer's tilt with the body's own roll (shock deflections). Per sample that is
    # noisy (sd ~2.7° on flat Monza), so it is averaged by position: 25 m LapDist bins, the median of each pass's median,
    # kept where ≥ 2 passes saw the bin (else 0). The replay applies it as Fy_ext = m·g·sin(bank): the sim's tyres then
    # need the gold's tyre force (its accelerometer), not the flat-road v·r. 0 everywhere without JM_IRG_BANK.
    bank = zeros(n)
    if get(ENV, "JM_IRG_BANK", "0") == "1" && haskey(c, "LapDist")
        vy = c["VelocityY"]; dvy = similar(vy); dvy .= 0.0
        for k in 7:n-6; dvy[k] = (vy[k+6] - vy[k-6])*60/12; end
        est = [asin(clamp((dvy[k] + c["VelocityX"][k]*c["YawRate"][k] - c["LatAccel"][k])/G, -1.0, 1.0)) +
               deg2rad(0.5*(c["rollF"][k] + c["rollR"][k])) for k in 1:n]
        ld = c["LapDist"]; pass = cumsum([0; diff(ld) .< -500])
        bins = Dict{Int,Dict{Int,Vector{Float64}}}()
        for k in 1:n
            (v[k] > 15 && isfinite(ld[k]) && ld[k] >= 0) || continue
            push!(get!(get!(bins, floor(Int, ld[k]/25), Dict{Int,Vector{Float64}}()), pass[k], Float64[]), est[k])
        end
        bmap = Dict(b => median([median(x) for x in values(P)]) for (b, P) in bins if length(P) >= 2)
        for k in 1:n
            isfinite(ld[k]) && ld[k] >= 0 && (bank[k] = get(bmap, floor(Int, ld[k]/25), 0.0))
        end
    end
    c["bank"] = bank
    # running tyre pressures (median while moving) relative to the 152 kPa reference: BrushTyre `prel`
    mv = v .> 15
    prel = Tuple(begin x = ch(f, w*"pressure"); x === nothing || !any(mv) ? 0.0 : median(x[mv])/152 - 1 end for w in ("LF", "RF", "LR", "RR"))
    (f = f, sp = sp, c = c, n = n, file = fn, prel = prel)
end

β_of(c, k) = rad2deg(atan(c["VelocityY"][k], max(c["VelocityX"][k], 1.0)))
ontrack(c, k) = c["IsOnTrackCar"][k] > 0.5 && (!haskey(c, "PlayerTrackSurface") || c["PlayerTrackSurface"][k] == 3)

"""Windows of one gold file: (kind, k0 = first replayed row, L rows, spun).
:steady = the 0.5 s before k0 holds yaw rate, lateral g, steering and speed nearly constant (a straight, a gentle curve
or a skidpad circle) and something changes after it; the sim is settled onto the gold's speed AND yaw rate.
:dynamic = no steady start for 5 s (continuous weaving): the gold's state (u, v, r) is injected at a lateral-g zero
crossing, where the body's roll is ~0."""
function windows(g)
    c = g.c; n = g.n; W = NamedTuple[]
    sw = rad2deg.(c["SteeringWheelAngle"]); r = rad2deg.(c["YawRate"]); ay = c["LatAccel"] ./ G; v = c["Speed"]
    nmax = round(Int, IRG_SECS*60)
    function wlen(k0)                                            # rows until the gold leaves the scored envelope
        spin = 0
        for j in k0:min(n, k0 + nmax)
            (ontrack(c, j) && v[j] > 10) || return (j - k0, spin > 0)
            abs(β_of(c, j)) > 25 && spin == 0 && (spin = j)
            spin > 0 && j > spin + 30 && return (j - k0, true)
        end
        (min(n, k0 + nmax) - k0, spin > 0)
    end
    quiet(k) = (w = k-29:k; all(j -> ontrack(c, j) && v[j] > 18 && c["Brake"][j] < 0.02 && abs(β_of(c, j)) < 6, w) &&
                maximum(r[w]) - minimum(r[w]) < 2.5 && maximum(ay[w]) - minimum(ay[w]) < 0.10 &&
                maximum(sw[w]) - minimum(sw[w]) < 4 && maximum(v[w]) - minimum(v[w]) < 0.17 && abs(ay[k]) < 1.25)
    k = 61; last = 61
    while k < n - 120
        # :brake -- a stop from speed (the bias sweep): the pedal comes on after 0.5 s off it, nearly straight
        if c["Brake"][k] > 0.1 && all(j -> c["Brake"][j] < 0.02, k-30:k-1) && v[k] > 25 && all(j -> ontrack(c, j) && abs(ay[j]) < 0.25, k-30:k)
            k0 = k - 15; L, spun = wlen(k0)
            L > 60 && push!(W, (kind = :brake, k0, L, spun))
            k = k0 + max(L, 60) + 1; last = k; continue
        end
        # :trail -- the brake applied while cornering (0.2-1.2 g): corner entry, where the car rotates under braking
        if c["Brake"][k] > 0.1 && all(j -> c["Brake"][j] < 0.02, k-30:k-1) && v[k] > 25 && 0.2 < abs(ay[k]) < 1.2 &&
           all(j -> ontrack(c, j), k-30:k) && abs(β_of(c, k)) < 6
            k0 = k - 15; L, spun = wlen(k0)
            L > 60 && push!(W, (kind = :trail, k0, L, spun))
            k = k0 + max(L, 60) + 1; last = k; continue
        end
        if quiet(k)
            # the event: the first row after k that leaves the quiet envelope
            e = findfirst(j -> abs(sw[j] - sw[k]) > 6 || abs(r[j] - r[k]) > 3 || c["Brake"][j] > 0.1 || abs(c["Throttle"][j] - c["Throttle"][k]) > 0.3,
                          k+1:min(n, k + 900))
            if e === nothing; k += 300; continue; end
            k0 = max(k + e - 15, k)
            L, spun = wlen(k0)
            L > 60 && push!(W, (kind = :steady, k0, L, spun))
            k = k0 + max(L, 60) + 1; last = k; continue
        end
        if k - last > 300 && ontrack(c, k) && v[k] > 20 && c["Brake"][k] < 0.05 && sign(ay[k]) != sign(ay[k-1]) && abs(β_of(c, k)) < 3
            L, spun = wlen(k)
            L > 60 && push!(W, (kind = :dynamic, k0 = k, L, spun))
            k += max(L, 60) + 1; last = k; continue
        end
        k += 1
    end
    W
end

const GETSYM = IdDict{Any,Any}()
const SETTLED = Ref{Any}(nothing)                                # the last settle's (state, δ, ie), for warm starts
simget(car) = get!(GETSYM, car.sys) do
    s = car.sys
    ModelingToolkit.getsym(s, [s.u, s.v, s.r, s.ay, s.ph, s.ωRL, s.ωRR, s.ωf, s.rpm])
end
const GETCOL = IdDict{Any,Any}()
"The front tyres' summed lateral force the column reads and their mean normalised slip ξ (kinematic when relaxed)."
function simcol(car)
    g = get!(GETCOL, car.sys) do
        s = car.sys
        try ModelingToolkit.getsym(s, [s.FL.Fyk, s.FR.Fyk, s.FL.ξk, s.FR.ξk]) catch
            ModelingToolkit.getsym(s, [s.FL.Fy, s.FR.Fy, s.FL.ξ, s.FR.ξ]) end
    end
    a = g(car.integ); (a[1] + a[2], 0.5*(a[3] + a[4]))
end
const GETSUSP = IdDict{Any,Any}()
"The sim's suspension roll per axle [deg]: (left compression − right) / track, compression = wheel up relative to its mount."
function simroll(car)
    g = get!(GETSUSP, car.sys) do
        s = car.sys
        (ModelingToolkit.getsym(s, [s.z, s.th, s.ph, s.wFL.zu, s.wFR.zu, s.wRL.zu, s.wRR.zu]), ModelingToolkit.getp(s, s.a)(car.integ), ModelingToolkit.getp(s, s.b)(car.integ))
    end
    (z, th, ph, fl, fr, rl, rr), a, b = g[1](car.integ), g[2], g[3]
    cmp(zu, xi, yi) = zu - (z + xi*th + yi*ph)
    (rad2deg((cmp(fl, a, 0.75) - cmp(fr, a, -0.75))/1.5), rad2deg((cmp(rl, -b, 0.75) - cmp(rr, -b, -0.75))/1.5),
     1000*(cmp(fl, a, 0.75) + cmp(fr, a, -0.75))/2, 1000*(cmp(rl, -b, 0.75) + cmp(rr, -b, -0.75))/2)   # PHYSFID-1 S8: + axle heave [mm]
end

"""Settle the sim onto the gold's speed V and yaw rate R [rad/s] in gear gr: 4 s of an integral steering loop on yaw
rate (rate-limited) and a PI throttle on speed. Returns the settled road steer angle [rad]."""
function settle_vr!(car, sp, u0, V, R, gr; δcap = 0.3, warm = nothing, δg = nothing, thrg = nothing, vy = 0.0)
    sys = car.sys
    get = simget(car)
    if warm !== nothing                                         # IRGOLD-1: the previous evaluation's settled state
        reinit!(car.integ, copy(warm[1])); car.gear = gr; car.s_gr(car.integ, sp.gear_ratios[gr])
        car.s_fx(car.integ, 0.0); car.s_fy(car.integ, 0.0); car.s_mz(car.integ, 0.0)
        delete!(DriveRT3D._VREF, car)
        δ = warm[2]; ie = warm[3]; nset = 60
    else
        reinit!(car.integ, copy(u0)); car.gear = gr; car.s_gr(car.integ, sp.gear_ratios[gr])
        ModelingToolkit.setu(sys, [sys.u, sys.v, sys.r])(car.integ, [V, vy, R])
        ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
        car.s_we(car.integ, V/DriveRT3D.RW_R*sp.gear_ratios[gr]*sp.final_drive)
        car.s_fx(car.integ, 0.0); car.s_fy(car.integ, 0.0); car.s_mz(car.integ, 0.0)
        delete!(DriveRT3D._VREF, car)
        # start AT the gold's operating point: its sideslip (vy), its road steer angle, its pedal (the throttle loop below
        # only trims ±0.2 around it) -- a free integral throttle from a cold kinematic start wound up and spun the car
        δ = δg === nothing ? R*(LWB/max(V, 5.0)) : δg; ie = 0.0; nset = parse(Int, Base.get(ENV, "JM_SETTLE_N", "240"))
    end
    for k in 1:nset
        u, v, r = get(car.integ)
        δ = clamp(δ + clamp(0.35*(R - r)/60*(30/max(V, 15)), -0.0006, 0.0006), -δcap, δcap)
        # from the gold's pedal, a gentle PI over the full range (the ±0.2 trim could not hold the speed when the gold was
        # coasting into a brake -- the sim started 10-15 km/h slow and the replay read it as over-braking)
        thr = thrg === nothing ? clamp(0.3 + 0.3*(V - u) + ie, 0, 1) : clamp(thrg + 0.1*(V - u) + ie, 0, 1)
        ie = thrg === nothing ? clamp(ie + 0.01*(V - u), -0.4, 0.8) : clamp(ie + 0.004*(V - u), -0.8, 0.8)
        DriveRT3D.step_car3d!(car, thr, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
    end
    SETTLED[] = (copy(car.integ.u), δ, ie)
    u, v, r = get(car.integ)
    # settled = the gold's yaw rate held within 5 % (or 0.5 °/s) without sliding; otherwise the sim cannot sustain the
    # gold's steady state at the gold's steering (+2°) -- reported as a failed window, not replayed
    ok = abs(r - R) < max(0.05abs(R), deg2rad(0.5)) && abs(atan(v, max(u, 1.0))) < deg2rad(10) && abs(u - V) < 0.5
    LASTSETTLE[] = (r = rad2deg(r), R = rad2deg(R), δ = rad2deg(δ), δcap = rad2deg(δcap), β = rad2deg(atan(v, max(u, 1.0))), u = 3.6u,
                    thr = thrg === nothing ? clamp(0.3 + 0.3*(V - u) + ie, 0, 1) : clamp(thrg + 0.1*(V - u) + ie, 0, 1))
    δ, ok
end
const LASTSETTLE = Ref{Any}(nothing)

"""Inject the gold's in-plane state (u, v, r) on a car settled straight at the same speed; body at static."""
function inject!(car, sp, u0, U, Vy, R, gr)
    δ0, _ = settle_vr!(car, sp, u0, U, 0.0, gr)
    ModelingToolkit.setu(car.sys, [car.sys.u, car.sys.v, car.sys.r])(car.integ, [U, Vy, R])
    OrdinaryDiffEq.SciMLBase.u_modified!(car.integ, true)
    δ0
end

"Each tyre's inflation (BrushTyre prel) from the gold file's running pressures; a car without the parameter is left alone."
function setprel!(car, prel)
    for (wh, x) in zip((:FL, :FR, :RL, :RR), prel)
        sub = getproperty(car.sys, wh)
        try ModelingToolkit.setp(car.sys, sub.prel)(car.integ, x) catch; end
    end
end

"Replay window `w` of gold file `g` through `car`; returns (gold, sim) traces as vectors of NamedTuples."
function replay(car, sp, u0, g, w; warm = nothing)
    # the job's own gearbox: step_car3d!'s shifts read the GLOBAL GEARS, which hold whichever file this process installed
    # last -- with several files per worker a WW103 upshift used the default box (and vice versa) until IRGOLD-1 S3
    length(sp.gear_ratios) == length(DriveRT3D.GEARS) && (DriveRT3D.GEARS .= sp.gear_ratios)
    setprel!(car, g.prel)
    # the session's own air density (the sim's is fixed at 1.10; Monza ran 1.151, the skidpad 1.135, the Ring 1.099)
    haskey(g.c, "AirDensity") && ModelingToolkit.setp(car.sys, car.sys.ρair)(car.integ, median(g.c["AirDensity"]))
    c = g.c; m = sum(values(sp.corner_weight_N))/9.81; sr = sp.steering_ratio
    car.s_fy(car.integ, m*G*sin(c["bank"][w.k0]))                 # S20: the settle on the window start's bank (0 if off)
    gr = clamp(round(Int, c["Gear"][w.k0]), 1, 5)
    off = rad2deg(c["SteeringWheelAngle"][w.k0])
    if w.kind === :steady || w.kind === :brake || w.kind === :trail
        δg = abs(c["SteeringWheelAngle"][w.k0])/sr
        k0 = w.k0
        δ0, ok = settle_vr!(car, sp, u0, c["VelocityX"][k0], c["YawRate"][k0], gr; δcap = δg + deg2rad(2), warm,
                            δg = c["SteeringWheelAngle"][k0]/sr, vy = c["VelocityY"][k0],
                            thrg = Base.get(ENV, "JM_IRG_FREETHR", "0") == "1" ? nothing : mean(c["Throttle"][max(1, k0-30):k0]))
        q = LASTSETTLE[]
        Base.get(ENV, "JM_IRG_THRLOG", "0") == "1" && @printf("    settle: %.0f km/h %.2f g  pedal gold %.3f sim %.3f  steer gold %.2f° sim %.2f°  β gold %.2f sim %.2f  %s\n",
            3.6c["Speed"][k0], c["LatAccel"][k0]/G, mean(c["Throttle"][max(1, k0-30):k0]), q.thr, rad2deg(c["SteeringWheelAngle"][k0]/sr), q.δ,
            β_of(c, k0), q.β, ok ? "ok" : "FAILED")
        ok || return (nothing, nothing, δ0)
    else                                                         # :dynamic -- the gold's steering as is, about the straight
        inject!(car, sp, u0, c["VelocityX"][w.k0], c["VelocityY"][w.k0], c["YawRate"][w.k0], gr)
        δ0 = 0.0; off = 0.0
    end
    get = simget(car)
    gold = NamedTuple[]; sim = NamedTuple[]
    gcur = gr
    # IRGOLD-1 S13: JM_IRG_CLOSED=1 -- a DRIVER on top of the gold's steering: PI on the yaw-rate error (sim's previous
    # step vs the gold's), scaled by wheelbase/speed (gain 1 = the neutral-steer correction), integral time 0.3 s.
    # The open-loop replay judges a held slide by whether the car follows the gold's own corrections; this one asks
    # how much DIFFERENT steering the car needs to follow the gold's path -- what the PO would have to do differently.
    # The sim's δ (and the dumps' s_d) then include the correction; s_d - g_d is the correction.
    closed = Base.get(ENV, "JM_IRG_CLOSED", "0") == "1"; cint = 0.0; rlast = c["YawRate"][w.k0]
    for j in w.k0:w.k0 + w.L - 1
        gj = clamp(round(Int, c["Gear"][j]), 0, 5)
        up = gj > gcur && gj > 0; dn = gj < gcur && gj > 0; (up || dn) && (gcur = gj)
        δ = δ0 + deg2rad(rad2deg(c["SteeringWheelAngle"][j]) - off)/sr
        if closed
            ek = (c["YawRate"][j] - rlast)*LWB/max(c["Speed"][j], 5.0)
            cint = clamp(cint + ek*(1/60)/0.3, -0.15, 0.15)
            δ += clamp(0.5ek + cint, -0.2, 0.2)
        end
        car.s_fx(car.integ, -m*G*sin(atan(c["grade"][j])))
        car.s_fy(car.integ, m*G*sin(c["bank"][j]))                 # S20 (JM_IRG_BANK): 0 on a flat road
        DriveRT3D.step_car3d!(car, c["Throttle"][j], c["Brake"][j], δ/DriveRT3D.MAXSTEER, 1/60;
                              clutch = 1.0 - clamp((IRG_RAWCLUTCH && haskey(c, "ClutchRaw") ? c["ClutchRaw"] : c["Clutch"])[j], 0, 1),
                              up = up, dn = dn, manual = true)
        u, v, r, ay, ph, wl, wr, wf, rpm = get(car.integ)
        rlast = r
        τ = something(DriveRT3D.rimtorque3d(car), NaN)
        sroll = simroll(car); scol = simcol(car)
        push!(sim, (r = rad2deg(r), ay = ay/G, β = rad2deg(atan(v, max(u, 1.0))), v = 3.6*hypot(u, v), roll = rad2deg(ph),
                    τ = τ, rpm = rpm, δ = rad2deg(δ), κr = (wl + wr)/2*DriveRT3D.RW_R/max(u, 1.0) - 1, thr = c["Throttle"][j],
                    rollF = sroll[1], rollR = sroll[2], fyf = scol[1], xif = scol[2], hF = sroll[3], hR = sroll[4],
                    κL = wl*DriveRT3D.RW_R/max(u, 1.0) - 1, κR = wr*DriveRT3D.RW_R/max(u, 1.0) - 1))
        push!(gold, (r = rad2deg(c["YawRate"][j]), ay = c["LatAccel"][j]/G, β = β_of(c, j), v = 3.6c["Speed"][j],
                     roll = haskey(c, "Roll") ? rad2deg(c["Roll"][j]) : NaN, τ = c["SteeringWheelTorque"][j], rpm = c["RPM"][j],
                     δ = rad2deg(c["SteeringWheelAngle"][j])/sr,
                     κr = (c["LRspeed"][j] + c["RRspeed"][j])/2/max(c["Speed"][j], 1.0) - 1, thr = c["Throttle"][j],
                     rollF = c["rollF"][j], rollR = c["rollR"][j], fyf = NaN, xif = NaN, hF = c["heaveF"][j], hR = c["heaveR"][j],
                     κL = c["LRspeed"][j]/max(c["Speed"][j], 1.0) - 1, κR = c["RRspeed"][j]/max(c["Speed"][j], 1.0) - 1))
        (isfinite(u) && u > 3) || break
        abs(rad2deg(atan(v, max(u, 1.0)))) > 60 && break
    end
    gold, sim, δ0
end

rmsd(a, b) = sqrt(mean((a .- b).^2))
"Per-window scores: RMS differences of yaw rate, lateral g, sideslip, speed drift, rim torque; peak yaw ratio."
function score(gold, sim; upto = nothing)
    n = min(length(gold), length(sim), upto === nothing ? typemax(Int) : upto)
    n < 10 && return nothing
    G_ = gold[1:n]; S_ = sim[1:n]
    f(x) = [getproperty(p, x) for p in G_]; h(x) = [getproperty(p, x) for p in S_]
    rg, rs = f(:r), h(:r)
    pk = maximum(abs, rg)
    (n = n, er = rmsd(rs, rg), rr = sqrt(mean(rg.^2)), eay = rmsd(h(:ay), f(:ay)), eβ = rmsd(h(:β), f(:β)),
     dv = h(:v)[end] - f(:v)[end], ev = rmsd(h(:v), f(:v)), eτ = rmsd(h(:τ), f(:τ)), τg = sqrt(mean(f(:τ).^2)),
     pkratio = pk > 2 ? maximum(abs, rs)/pk : NaN,
     βmaxg = maximum(abs, f(:β)), βmaxs = maximum(abs, h(:β)))
end

function main()
    only = split(get(ENV, "JM_IRG_FILES", ""), ","; keepempty = false)
    kinds = get(ENV, "JM_IRG_KIND", "")
    dump = get(ENV, "JM_IRG_DUMP", "")
    isempty(dump) || mkpath(dump)
    files = sort(filter(f -> endswith(f, ".ibt"), readdir(DG; join = true)); by = f -> match(r"2026-(.*)\.ibt", f).captures[1])
    # JM_IRG_DIRS="261004,261005": the earlier gold sessions too (their Ring laps hold most of the trail-braking entries)
    for dd in split(get(ENV, "JM_IRG_DIRS", ""), ","; keepempty = false)
        append!(files, sort(filter(f -> endswith(f, ".ibt"), readdir(expanduser("~/gold standard/julia racer/$dd"); join = true))))
    end
    isempty(only) || (files = filter(f -> any(o -> occursin(o, f), only), files))
    files = irg_files(files)
    rows = NamedTuple[]; fails = NamedTuple[]
    for fn in files
        g = goldfile(fn); W = windows(g)
        isempty(kinds) || (W = filter(w -> String(w.kind) == kinds, W))
        test = testof(fn); stem = match(r"(\d\d-\d\d-\d\d)\.ibt$", fn).captures[1]
        @printf("\n== %s  %s  (%d windows)\n", stem, test, length(W)); flush(stdout)
        isempty(W) && continue
        sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0)
        if !isempty(get(ENV, "JM_IRG_PARAMS", ""))           # IRGOLD-1: runtime parameters for A/B (irgold_params.jl names)
            isdefined(Main, :PARAM_MAP) || (Base.eval(Main, :(using ModelingToolkit)); include(joinpath(@__DIR__, "irgold_params.jl")))
            Base.invokelatest(setparams!, car, Dict(String(strip(split(x, "=")[1])) => parse(Float64, split(x, "=")[2]) for x in split(ENV["JM_IRG_PARAMS"], ",")))
        end
        u0 = copy(car.integ.u)
        for w in W
            gold, sim, δ0 = replay(car, sp, u0, g, w)
            if gold === nothing
                push!(fails, (; test, stem, t = w.k0/60))
                q = LASTSETTLE[]
                @printf("  %-8s t %6.1f  SETTLE FAILED: gold %.1f °/s at %.0f km/h, %.2f g, steer %.2f° road | sim r %.1f °/s at %.0f km/h, steer %.2f° (cap %.2f), β %.1f°\n",
                        w.kind, w.k0/60, q.R, 3.6g.c["Speed"][w.k0], g.c["LatAccel"][w.k0]/G, rad2deg(g.c["SteeringWheelAngle"][w.k0])/sp.steering_ratio,
                        q.r, q.u, q.δ, q.δcap, q.β); flush(stdout)
                continue
            end
            s = score(gold, sim); s === nothing && continue
            spun_s = s.βmaxs > 25
            push!(rows, (; test, stem, t = w.k0/60, kind = w.kind, v0 = gold[1].v, s..., spun_g = w.spun, spun_s,
                          δss = w.kind === :steady && abs(gold[1].ay) > 0.4 ? (rad2deg(δ0) - gold[1].δ)*sign(gold[1].ay) : NaN))
            x = rows[end]
            @printf("  %-8s t %6.1f  %3.0f km/h %3d rows | r %5.2f/%5.2f °/s  ay %.3f g  β %5.2f°  dv %+5.1f  τ %4.1f/%4.1f Nm  pk %.2f  βmax %4.1f/%4.1f%s%s\n",
                    w.kind, x.t, x.v0, x.n, x.er, x.rr, x.eay, x.eβ, x.dv, x.eτ, x.τg, x.pkratio, x.βmaxg, x.βmaxs,
                    isfinite(x.δss) ? @sprintf("  δss err %+.2f°", x.δss) : "", (x.spun_g || x.spun_s) ? "  SPIN gold $(x.spun_g) sim $(x.spun_s)" : "")
            if !isempty(dump)
                open(joinpath(dump, @sprintf("%s_%07.1f.csv", stem, x.t)), "w") do io
                    println(io, "k,g_r,s_r,g_ay,s_ay,g_b,s_b,g_v,s_v,g_roll,s_roll,g_tau,s_tau,g_d,s_d,g_kr,s_kr,thr,g_rpm,s_rpm,g_rollF,s_rollF,g_rollR,s_rollR,s_fyf,s_xif,g_kL,s_kL,g_kR,s_kR,g_hF,s_hF,g_hR,s_hR")
                    for k in 1:min(length(gold), length(sim))
                        a, b = gold[k], sim[k]
                        @printf(io, "%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.3f,%.3f,%.4f,%.4f,%.3f,%.3f,%.4f,%.4f,%.4f,%.4f,%.3f,%.0f,%.0f,%.4f,%.4f,%.4f,%.4f,%.1f,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.2f,%.2f,%.2f\n", k, a.r, b.r, a.ay, b.ay, a.β, b.β,
                                a.v, b.v, a.roll, b.roll, a.τ, b.τ, a.δ, b.δ, a.κr, b.κr, a.thr, a.rpm, b.rpm, a.rollF, b.rollF, a.rollR, b.rollR, b.fyf, b.xif, a.κL, b.κL, a.κR, b.κR, a.hF, b.hF, a.hR, b.hR)
                    end
                end
            end
            flush(stdout)
        end
    end
    println("\n== summary by test (mean over windows): yaw-rate RMS err / gold RMS, ay err, β err, |dv|, rim torque err, peak-yaw ratio")
    for test in unique(r.test for r in rows)
        R = filter(r -> r.test == test, rows)
        @printf("  %-14s %3d win | r %5.2f / %5.2f °/s (%.0f %%)  ay %.3f g  β %.2f°  |dv| %.1f km/h  τ %.2f / %.2f Nm  pk %.2f  spins gold %d sim %d  δss %s\n",
                test, length(R), mean(r.er for r in R), mean(r.rr for r in R), 100*mean(r.er for r in R)/mean(r.rr for r in R),
                mean(r.eay for r in R), mean(r.eβ for r in R), mean(abs(r.dv) for r in R), mean(r.eτ for r in R), mean(r.τg for r in R),
                (pk = filter(isfinite, [r.pkratio for r in R]); isempty(pk) ? NaN : mean(pk)),
                count(r -> r.spun_g, R), count(r -> r.spun_s, R),
                any(r -> isfinite(r.δss), R) ? @sprintf("%+.2f°", mean(filter(isfinite, [r.δss for r in R]))) : "-")
    end
    R = rows
    @printf("  %-14s %3d win | r err %.0f %% of gold RMS, ay %.3f g, β %.2f°   settle failures %d %s\n", "ALL", length(R),
            100*mean(r.er for r in R)/mean(r.rr for r in R), mean(r.eay for r in R), mean(r.eβ for r in R), length(fails),
            join(unique(f.test for f in fails), ", "))
    rows
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
