# E89 headless field measurement: 4 kinematic AI on Monza for 120 s, fall-back episodes and rail
# switches per car-lap, against a lone car's free profile. Arms via env: JM_AI_GAPCTL, JM_AI_GPLLINE.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack; include("ai.jl"); using .RaceAI; include("gpl_lp.jl"); using .GPLLP
using Statistics, Random
Random.seed!(7)
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
if get(ENV, "JM_AI_GPLLINE", "0") != "0"
    RaceAI.set_gpl_speeds!(min.(lp_speed_mps(read_lp(joinpath(T, "race.lp"))) .* 1.016, 2.41*36))
    if get(ENV, "JM_AI_GPLLAT", "0") != "0"
        r = read_lp(joinpath(T, "race.lp")); a = read_lp(joinpath(T, "pass1.lp")); b = read_lp(joinpath(T, "pass2.lp"))
        RaceAI.set_gpl_lateral!(r.dlat, a.dlat, b.dlat)
    end
end
amax = 8.0; vmax = 74.0; N = 4; secs = 300; dt = 1/60; warm = 30
(fs, fv) = RaceAI.free_speed_profile(line; amax, vmax, ds = 3.0)
RaceAI.aistat_reset!()
cars = RaceAI.init_cars(line, N; start_s = 30.0)
for (i, c) in enumerate(cars); c.pace = 1.0 + 0.01*(i-2); end       # a spread like the sim's per-car pace
# A LUNGE-FALL CYCLE: the car's deficit against the lone-car speed goes from >5 m/s back under 2 --
# it fell back, then caught up again. Steady following behind a slower car is NOT counted (the
# deficit stays), and the standing start is skipped (warm-up). Car-laps from distance, not the lap
# counter, so a 300 s run has a real denominator.
cyc = zeros(Int, N); deep = falses(N); worst = zeros(N); dist = zeros(N)
for f in 1:secs*60
    RaceAI.step_field!(cars, line, dt; amax, vmax, player = (-1e9, 0.0, 100.0))
    f <= warm*60 && continue
    for (i, c) in enumerate(cars)
        dist[i] += c.v*dt
        k = clamp(floor(Int, mod(c.s, line.total)/3.0) + 1, 1, length(fv)); dfc = fv[k] - c.v
        worst[i] = max(worst[i], dfc)
        if dfc > 5.0; deep[i] = true
        elseif dfc < 2.0 && deep[i]; deep[i] = false; cyc[i] += 1 end
    end
end
tl = max(0.1, sum(dist)/line.total); st = RaceAI.AISTAT
println("arm: GAPCTL=", RaceAI.GAPCTL, " GPLLINE=", RaceAI.GPLV[] !== nothing, "   ", N, " cars, ", secs-warm, " s measured, ", round(tl, digits=1), " car-laps")
println("  lunge-fall cycles (deficit >5 m/s then back <2): ", cyc, " = ", round(sum(cyc)/tl, digits=2), " per car-lap;  worst deficit ", round.(worst, digits=1), " m/s")
println("  lane use: max |lane| ", round(maximum(abs(c.lane) for c in cars), digits=2), " m (GPL race line spans -3.5..13.4 on Monza)")
println("  rail switches engage=", st.engage, " release=", st.release, " = ", round((st.engage+st.release)/tl, digits=2), " per car-lap;  speed-match frames ", st.match, "  queue-snaps ", st.qsnap, "  side-pushes ", st.sidepush, "  mishaps ", st.mishap)
