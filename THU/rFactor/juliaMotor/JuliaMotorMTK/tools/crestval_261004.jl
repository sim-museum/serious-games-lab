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
const CREST = 3143.0; const S0 = CREST - 250.0; const S1 = CREST + 200.0
fpath(tag) = joinpath(D4, first(filter(f -> occursin(tag, f), readdir(D4))))
hs(f, n) = (M = hcat([channel(f, n; idx = j) for j in 1:6]...); vec(permutedims(M)))

# gold passes: (file tag, row where LapDist crosses S0)
function passes()
    out = []
    for tag in ("13-28-39", "13-34-46", "14-08-54")
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

let p = setup_params(ibt_open(fpath("13-34-46")).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = "261004 Ring")
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = "261004 Ring")
end

function drive(sl)
    c = DriveRT3D.build_car3d(; x0 = S0, z0 = 0.0, θ0 = 0.0, v0 = sl.v[1], y0 = groundz(S0, 0.0))
    g = Int(sl.gear[1]); c.gear = g; c.s_gr(c.integ, DriveRT3D.gearratio(g))
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
        gm = metrics(range(sl.s[1], sl.s[end], length = length(sl.va)), sl.va)
        ss, va = drive(sl)
        sm = metrics(ss, va)
        quiet || @printf("   %s %3.0f km/h thr %.2f | %5.2f    %+5.2f    %5.2f  | %5.2f    %+5.2f    %5.2f\n", tag, 3.6lin(sl.s, sl.v, CREST - 50),
                lin(sl.s, sl.thr, CREST - 20), gm.air, gm.crest, gm.land, sm.air, sm.crest, sm.land)
        gm.land < 5 || continue                       # the two gold passes that SPUN on landing (9.4 / 7.5 g) are not crest behaviour
        push!(res, abs(sm.air - gm.air)); push!(res, abs(sm.land - gm.land)/5)
    end
    @printf("   %s mean |Δairtime| %.3f s, mean |Δlanding g| %.2f g  (7 non-spin passes)\n", quiet ? rpad(label, 44) : "", mean(res[1:2:end]), 5mean(res[2:2:end]))
end
haskey(ENV, "JM_CRESTDBG") || run_all("NEW (SUSP-1: measured rear motion ratio, roll coupling, measured dampers; frame $(DriveRT3D.VFRAME_INERTIAL ? "inertial" : "legacy"))")
# OLD: the hand-set suspension, for the A/B (method redefinition, this process only)
haskey(ENV, "JM_ALIGNDBG") && let
    sls = [slice(p[2], p[3]) for p in P]
    for x in CREST-60:8:CREST+60
        @printf("   s %6.0f |", x)
        for sl in sls
            gs = range(sl.s[1], sl.s[end], length = length(sl.va)); gi = argmin(abs.(gs .- x))
            @printf(" %+5.2f", mean(sl.va[max(1,gi-18):min(end,gi+18)])/G)
        end
        println()
    end
    println("   passes: ", join([@sprintf("%s %.0f", p[1], 3.6lin(sl.s, sl.v, CREST - 50)) for (p, sl) in zip(P, sls)], " | "))
    exit()
end
haskey(ENV, "JM_CRESTDBG") && let i = parse(Int, ENV["JM_CRESTDBG"]), sl = slice(P[i][2], P[i][3])
    gs = range(sl.s[1], sl.s[end], length = length(sl.va))
    ss, va = drive(sl)
    for x in CREST-40:6:CREST+110
        gi = argmin(abs.(gs .- x)); si = argmin(abs.(ss .- x))
        @printf("   s %6.0f  road %+6.2f m | gold va %+5.2f g | sim va %+5.2f g\n", x, groundz(x, 0.0), sl.va[gi]/G, va[si]/G)
    end
    exit()
end
@eval DriveRT3D _corner(axle::Symbol, ks::Real) = axle === :f ?
    (ks = float(ks), cs = 2500.0, m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 1000.0) :
    (ks = float(ks), cs = 3000.0, m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 1100.0)
DriveRT3D.set_suspension!(18_250.0, 18_250.0, 29_200.0, 29_200.0; source = "OLD")
run_all("OLD (MR² 0.6083 everywhere, hand-set dampers 2500/3000)")

# which part of SUSP-1 moves the crest: springs (rear motion ratio + roll coupling) vs dampers
haskey(ENV, "JM_CRESTVARIANTS") && for (lab, kr, newd) in (("old springs + old dampers", 29_200.0, false), ("new springs + old dampers", 20_150.0, false),
                                                           ("old springs + new dampers", 29_200.0, true),  ("new springs + new dampers", 20_150.0, true))
    @eval DriveRT3D _corner(axle::Symbol, ks::Real) = axle === :f ?
        (ks = float(ks), cs = 2500.0, cb = $newd ? 4017.0*sqrt(MR2) : 2500.0, cr = $newd ? 2855.0*sqrt(MR2) : 2500.0, karb = 0.0,
         m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 1000.0) :
        (ks = float(ks), cs = 3000.0, cb = $newd ? 1654.0*sqrt(MR2_R) : 3000.0, cr = $newd ? 788.0*sqrt(MR2_R) : 3000.0,
         karb = $kr < 25_000 ? _karb_r(ks) : 0.0, m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 1100.0)
    DriveRT3D.set_suspension!(18_250.0, 18_250.0, kr, kr; source = lab)
    run_all(lab; quiet = true)
end
