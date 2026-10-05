# AIGPL-2 acceptance probe: run the GPLAI field headless in GPL's own frame (GPL's .trk centreline and surface,
# no renderer, no julia mesh) and measure it the way doc/GPL_AI_REVERSE_ENGINEERING.md §6 measured GPL's own AI
# from the 2026-10-03 replays.
#
#   julia --project=. gplai_probe.jl [track=watglen] [ncars=5] [laps=3]
#   JM_GPLAI_PACE="1,0.97,0.95,0.93,0.90"   per-car pace (default: the sim's power/weight spread)
using Printf, Statistics, Random
include("gpltrack.jl"); using .GPLTrack
include("gpldat.jl"); using .GPLDat
include("gplai.jl"); using .GPLAI
include("ai.jl"); using .RaceAI               # only for the gpl_ai.ini parser

const TR = length(ARGS) >= 1 ? ARGS[1] : "watglen"
const N  = length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 5
const LAPS = length(ARGS) >= 3 ? parse(Float64, ARGS[3]) : 3.0
const GD = joinpath(homedir(), "sgl", "THU", "WP", "drive_c", "Sierra", "GPL", "tracks", TR)

function trackini(path)
    adj = 1.0; vcap = 2.41*36; sepc = 1.0
    for l in eachline(path)
        m = match(r"^\s*dlong_speed_adj_coeff\s*=\s*([0-9.]+)", l); m !== nothing && (adj = parse(Float64, m[1]))
        m = match(r"^\s*dlong_speed_maximum\s*=\s*([0-9.]+)", l); m !== nothing && (vcap = parse(Float64, m[1])*36)
        m = match(r"^\s*track_dlong_sep_coeff\s*=\s*([0-9.]+)", l); m !== nothing && (sepc = parse(Float64, m[1]))
    end
    (adj, vcap, sepc)
end

function build(tr = TR)
    lines = Dict(k => GPLAI.read_line(joinpath(GD, f * ".lp")) for (k, f) in
                 ((GPLAI.RACE, "race"), (GPLAI.MINR, "minrace"), (GPLAI.MAXR, "maxrace"), (GPLAI.PASS1, "pass1"), (GPLAI.PASS2, "pass2")))
    trk = joinpath(GD, tr * ".trk")
    if !isfile(trk)                                   # inside the track .dat archive
        dat = GPLDat.parse_dat(joinpath(GD, first(filter(f -> lowercase(f) == tr * ".dat", readdir(GD)))))
        trk = joinpath(mktempdir(), tr * ".trk"); write(trk, dat[tr * ".trk"])
    end
    ta = GPLTrack.trk_altitude(trk)
    secs = GPLAI.trk_sections(read(trk))
    r1 = GPLAI.Ref(secs...; sgn = 1.0)
    lap = 3.0*length(lines[GPLAI.RACE].d)          # GPL dlong (see GPLAI._k)
    # which side is +dlat? GPL's race line is on the INSIDE of corners: pick the sign that makes it so.
    num = 0.0
    for s in 0:3.0:lap-3
        k = GPLAI.curv(r1, s*r1.lap/lap); abs(k) > 1/150 && (num += sign(k)*GPLAI.dlat(lines[GPLAI.RACE], s))
    end
    sgn = num >= 0 ? 1.0 : -1.0
    ref = GPLAI.Ref(secs...; sgn = sgn)
    adj, vcap, sepc = trackini(joinpath(GD, "track.ini"))
    P = GPLAI.params(RaceAI.gpl_ai(); sep_coeff = sepc, adj = adj, vcap = vcap)
    height(s, d, x, z) = GPLTrack.trk_height(ta, s*ref.lap/lap, d)
    @printf("%s: %d records (%.1f m), lap %.1f m (.trk alt %.1f), closure gap %.2f m, dlat sign %+.0f, adj %.3f cap %.1f m/s sep x%.2f\n",
            tr, length(lines[GPLAI.RACE].d), 3.0*length(lines[GPLAI.RACE].d), lap, ta.total, hypot(ref.gx, ref.gy), sgn, adj, vcap, sepc)
    GPLAI.Track(lines, ref, lap, P, height)
end

T = build()
if !haskey(ENV, "JM_GPLAI_BUILDONLY")
paces = haskey(ENV, "JM_GPLAI_PACE") ? parse.(Float64, split(ENV["JM_GPLAI_PACE"], ",")) :
        [1.0, 0.985, 0.975, 0.965, 0.955, 0.945, 0.935][1:N]
cars = [GPLAI.Car(T, i, mod(-9.0*i, T.lap), (isodd(i) ? -1.3 : 1.3) + GPLAI.dlat(GPLAI.L(T, GPLAI.RACE), mod(-9.0*i, T.lap));
                  pace = paces[i]) for i in 1:N]
for c in cars; c.react = round(Int, T.P.start_hiatus) + rand(0:9); end
F = GPLAI.Field(T, cars)
const GS = GPLAI.grip_scale(T); @printf("grip scale %.3f\n", GS)
# ---- run at 60 fps like the sim, record per tick
dt = 1/60
rec = [NTuple{6,Float64}[] for _ in 1:N]          # (t, s_unwrapped, d, dv, da, v)
lapsdone = zeros(Int, N); laptimes = [Float64[] for _ in 1:N]; tlap = zeros(N)
t = 0.0
while minimum(c.lap + c.s/T.lap for c in cars) < LAPS && t < 60*60
    global t
    lapb = [c.lap for c in cars]
    GPLAI.step!(F, dt; scale = GS)
    t += dt
    for (i, c) in enumerate(cars)
        push!(rec[i], (t, c.lap*T.lap + c.s, c.d, c.dv, c.da, c.v))
        if c.lap > lapb[i]; push!(laptimes[i], t - tlap[i]); tlap[i] = t; end
    end
end
# ---- measure
race = GPLAI.L(T, GPLAI.RACE)
lapref = sum(3.0 ./ max.(race.v .* T.P.adj, 1.0))
@printf("race.lp lap at line speed x adj: %.2f s\n", lapref)
function report(rec, F, laptimes, paces, dt)
offrace = Float64[]; lat_a = Float64[]; lat_v = Float64[]; outc = 0; nn = 0
for i in 1:N
    for r in rec[i]
        r[6] > 20 || continue
        s = mod(r[2], T.lap); dr = GPLAI.dlat(race, s)
        push!(offrace, abs(r[3] - dr)); push!(lat_a, abs(r[5])); push!(lat_v, abs(r[4]))
        lo, hi = GPLAI.corridor(T, s); (r[3] < lo - 1e-6 || r[3] > hi + 1e-6) && (outc += 1); nn += 1
    end
end
@printf("|dlat - race|: p50 %.2f p90 %.2f p99 %.2f max %.2f m; >1 m %.1f %% | dlat' p99 %.2f max %.2f m/s | dlat'' p99 %.1f m/s2 | outside corridor %.2f %%\n",
        median(offrace), quantile(offrace, 0.9), quantile(offrace, 0.99), maximum(offrace), 100*mean(offrace .> 1),
        quantile(lat_v, 0.99), maximum(lat_v), quantile(lat_a, 0.99), 100*outc/max(nn, 1))
# side by side: pairs within 6 m along the track (after 40 s), how many > 1 m apart laterally
close = 0; sbs = 0; k0 = round(Int, 40/dt)
m = minimum(length.(rec))
for a in 1:N, b in a+1:N, k in k0:m
    ra = rec[a][k]; rb = rec[b][k]
    ds = mod(ra[2] - rb[2] + T.lap/2, T.lap) - T.lap/2
    (abs(ds) < 6 && ra[6] > 20) || continue
    close += 1; abs(ra[3] - rb[3]) > 1.0 && (sbs += 1)
end
@printf("pairs within 6 m (after 40 s): %d samples, side by side (>1 m apart) %d (%.0f %%)\n", close, sbs, 100*sbs/max(close, 1))
# smoothness: the largest one-frame change of lateral velocity (the 'jump sideways' measure)
jv = Float64[]
for i in 1:N, k in 2:length(rec[i])
    rec[i][k][6] > 20 && push!(jv, abs(rec[i][k][4] - rec[i][k-1][4]))
end
@printf("one-frame (60 Hz) change of lateral speed: p99 %.3f p999 %.3f max %.3f m/s (GPL replays: 0.18-0.22 / 0.30-0.65 / 0.6-1.9); contacts %d\n",
        quantile(jv, 0.99), quantile(jv, 0.999), maximum(jv), get(F.stats, :contact, 0))
for i in 1:N
    @printf("  car %d pace %.3f laps %s\n", i, paces[i], join([@sprintf("%.2f", x) for x in laptimes[i]], " "))
end
end
report(rec, F, laptimes, paces, dt)
end
