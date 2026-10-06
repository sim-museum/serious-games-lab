# WWSETUP-1 acceptance (from crestval_261004.jl): the Flugplatz crest for BOTH setups, each car on its own ibt.
#   default: the 261004 passes, the car from 261004 13-34-46 (springs, gearbox, mass, chassis: LSD, bars, dampers)
#   ww:      the 261005 C1 passes (00-59-42, 4 passes 103-186 km/h, no spins), the car from that file
# The road is the 261004 reference pass's measured profile in both cases (the same Touristenfahrten crest, LapDist 3143).
#
# The source comment of crestval_261004.jl, kept:
# IRFIT-261004 SUSP-1 acceptance: the Lotus 49 over the iRacing Flugplatz crest, sim vs gold, OLD vs NEW suspension.
#
# Road: the gold's slowest clean pass (14-08-54, 122 km/h, steady 40 % throttle, no airtime) -- its Alt minus its
# mean ride height along LapDist is the crest's own profile (Alt alone carries the gold car's suspension motion, which
# rounds the crest off: at 122 km/h the gold unloads to +0.54 g there). Every other gold pass is then re-driven by the 3-D car
# over that profile at 360 Hz, with that pass's own throttle, brake and gear against distance, straight ahead, and
# compared on: time airborne (VertAccel < 0.5 g), the crest's lowest g, and the landing peak (highest g within 2 s
# after the crest). The iRacing Ring is today's laser scan (not GPL's 1967 crest), which is why the comparison is
# run on ITS road, not ours.
#
#   julia --project=. tools/crestval_261004.jl
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
const G = 9.80665
const D4 = expanduser("~/gold standard/julia racer/261004")
const D5 = expanduser("~/gold standard/julia racer/261005")
const SIDE = get(ENV, "JM_CREST_SIDE", "ww")
const CREST = 3143.0; const S0 = CREST - 250.0; const S1 = CREST + 200.0
fpath(tag) = (d = occursin("00-59-42", tag) ? D5 : D4; joinpath(d, first(filter(f -> occursin(tag, f), readdir(d)))))
hs(f, n) = (M = hcat([channel(f, n; idx = j) for j in 1:6]...); vec(permutedims(M)))

# gold passes: (file tag, row where LapDist crosses S0)
function passes(tags = ("13-28-39", "13-34-46", "14-08-54"))
    out = []
    for tag in tags
        f = ibt_open(fpath(tag)); ld = channel(f, "LapDist")
        for k in 2:f.nrows
            ld[k-1] < S0 <= ld[k] && k + 60*12 < f.nrows && push!(out, (tag, f, k))
        end
    end
    out
end
# the slice of a pass from S0 to S1, at 60 Hz (inputs) and 360 Hz (VertAccel)
function slice(f, k)
    ld = channel(f, "LapDist"); r1 = k; while r1 < f.nrows && ld[r1] < S1 && ld[r1] >= ld[k] - 1; r1 += 1; end
    rows = k:r1
    ch(n) = channel(f, n)[rows]
    va = hs(f, "VertAccel")[6(k-1)+1:6r1]
    rh = (ch("LFrideHeight") .+ ch("RFrideHeight") .+ ch("LRrideHeight") .+ ch("RRrideHeight")) ./ 4
    (s = ld[rows], alt = ch("Alt") .- rh, v = ch("Speed"), thr = ch("Throttle"), brk = ch("Brake"), gear = ch("Gear"), va = va)
end
lin(xs, ys, x) = (i = clamp(searchsortedlast(xs, x), 1, length(xs) - 1); w = clamp((x - xs[i])/(xs[i+1] - xs[i] + 1e-9), 0, 1); ys[i] + w*(ys[i+1] - ys[i]))
function metrics(s360, va)
    air = va .< 0.5G
    t_air = count(air[i] for i in eachindex(s360) if CREST - 60 < s360[i] < CREST + 120) / 360
    ic = findall(x -> CREST - 60 < x < CREST + 120, s360)
    isempty(ic) && return (air = NaN, crest = NaN, land = NaN)    # this run never reached the crest (stopped / spun before)
    imin = ic[argmin(va[ic])]
    after = findall(i -> i > imin && i <= imin + 720, eachindex(va))      # landing: within 2 s of the crest
    (air = t_air, crest = minimum(va[ic])/G, land = maximum(va[after])/G)
end

P = passes()
ref = let ps = [(p, slice(p[2], p[3])) for p in P]
    i = argmin(map(x -> (sl = x[2]; abs(mean(sl.v) - 122/3.6) + 100*(metrics(range(sl.s[1], sl.s[end], length = length(sl.va)), sl.va).air > 0)), ps))
    ps[i][2]
end
@printf("road profile: pass at %.0f km/h (mean), %d rows over s %.0f..%.0f\n", 3.6mean(ref.v), length(ref.s), ref.s[1], ref.s[end])
# The road under the reference pass = the gold CG's altitude minus its mean ride height. iRacing QUANTISES Alt to
# ~0.1 m (g + Alt'' over 0.1 s only takes the values -0.02 / 1.00 / 2.02 / 3.04 g), as large as the crest's own
# curvature over these distances, so Alt cannot give the shape. The shape comes from the 360 Hz VertAccel, double
# integrated; Alt only anchors its slow drift (start height, start velocity and an accelerometer bias, least squares
# against the quantised Alt) -- a complementary filter. Then a 0.5 m grid, smoothed over 2 m.
prof_s, prof_h = let n = length(ref.va), dt = 1/360
    vz = cumsum((ref.va .- G) .* dt); zz = cumsum(vz .* dt)            # double integral of the vertical accel
    rows = 1:length(ref.s); t = (rows .- 1) ./ 60; zi = [zz[clamp(6(r-1)+1, 1, n)] for r in rows]
    M = hcat(ones(length(t)), t, t.^2); c = M \ (ref.alt .- zi)        # ref.alt is already Alt - ride height
    road = zi .+ M*c
    s0 = collect(ref.s); xs = collect(s0[1]:0.5:s0[end]); hh = [lin(s0, road, x) for x in xs]
    w = 2; (xs, [mean(hh[max(1, i-w):min(end, i+w)]) for i in eachindex(hh)] .- hh[1])
end
groundz(x, z) = lin(prof_s, prof_h, Float64(x))

# the profile came from the 261004 passes; the passes DRIVEN are the chosen side's
SIDE == "ww" && (P = passes(("00-59-42",)))
let fn = fpath(SIDE == "ww" ? "00-59-42" : "13-34-46"), p = setup_params(ibt_open(fn).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(fn))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(fn))
    s = p.spring_rate_Npmm
    DriveRT3D.set_suspension!(wheel_rate(s[:LF]), wheel_rate(s[:RF]), wheel_rate(s[:LR]; rear = true), wheel_rate(s[:RR]; rear = true); source = basename(fn))
    get(ENV, "JM_CREST_CHASSIS", "1") == "1" && DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(p; source = basename(fn)))
    println("car: ", basename(fn), "\n   ", DriveRT3D.describe_chassis())
end

function drive(sl)
    c = DriveRT3D.build_car3d(; x0 = S0, z0 = 0.0, θ0 = 0.0, v0 = sl.v[1], y0 = groundz(S0, 0.0))
    g = Int(sl.gear[1])
    g >= 1 || (g = something(findfirst(i -> sl.v[1]/DriveRT3D.RW_R*DriveRT3D.GEARS[i]*DriveRT3D.FINAL[]*60/2π < 8500, 1:5), 5))   # neutral in the gold
    c.gear = g; c.s_gr(c.integ, DriveRT3D.gearratio(g))
    c.s_we(c.integ, sl.v[1]/DriveRT3D.RW_R*DriveRT3D.GEARS[g]*DriveRT3D.FINAL[])
    ss = Float64[]; va = Float64[]
    for i in 1:360*14
        x = c.x
        thr = lin(sl.s, sl.thr, x); brk = lin(sl.s, sl.brk, x); gg = round(Int, lin(sl.s, sl.gear, x))
        if 1 <= gg <= 5 && gg != c.gear; c.gear = gg; c.s_gr(c.integ, DriveRT3D.gearratio(gg)); end
        DriveRT3D.step_car3d!(c, thr, brk, 0.0, 1/360; clutch = 0.0, manual = true, groundz = groundz)
        push!(ss, c.x); push!(va, c.vacc)
        (c.x > S1 || c.v < 5) && break
    end
    ss, va
end

function run_all(label; quiet = false)
    quiet || println("\n", label)
    quiet || println("   pass                   | gold: air s  crest g  land g | sim: air s  crest g  land g")
    res = Float64[]
    for (tag, f, k) in P
        sl = slice(f, k)
        length(sl.s) > 100 || continue                # a LapDist wrap, not a pass
        gm = metrics(range(sl.s[1], sl.s[end], length = length(sl.va)), sl.va)
        ss, va = drive(sl)
        sm = metrics(ss, va)
        quiet || @printf("   %s %3.0f km/h thr %.2f | %5.2f    %+5.2f    %5.2f  | %5.2f    %+5.2f    %5.2f\n", tag, 3.6lin(sl.s, sl.v, CREST - 50),
                lin(sl.s, sl.thr, CREST - 20), gm.air, gm.crest, gm.land, sm.air, sm.crest, sm.land)
        isfinite(sm.air) && isfinite(gm.air) || (println("      ^ no crest window (sim reached s ", round(maximum(ss), digits = 0), ")"); continue)
        gm.land < 5 || continue                       # gold passes that SPUN on landing (9.4 / 7.5 g) are not crest behaviour
        push!(res, abs(sm.air - gm.air)); push!(res, abs(sm.land - gm.land)/5)
    end
    @printf("   %s mean |Δairtime| %.3f s, mean |Δlanding g| %.2f g  (%d non-spin passes)\n", quiet ? rpad(label, 44) : "", mean(res[1:2:end]), 5mean(res[2:2:end]), length(res)÷2)
end
run_all("$(SIDE): $(get(ENV, "JM_CREST_CHASSIS", "1") == "1" ? "WWSETUP-1 chassis (LSD, bars, dampers, toe, bias)" : "springs only (pre-WWSETUP chassis)")")
