# GATE: the TRACK FRAME must be smooth -- both halves of SEAM-1 (PO 2026-09-26: "AI cars skitter
# (jump sideways) at times, often at corners ... the places where they do this on a track often
# coincide with locations where the user's car jolts or bounces ... seams in the road surface, where
# the track is piecewise linear rather than smooth").
#
# WHAT IS ASSERTED, and why these two numbers are the right ones:
#  1. THE PLAYER'S BOUNCE. Drive a car along a perfectly smooth path and read the road height the
#     way the sim does -- the .trk altitude spline evaluated at the ribbon's (lapdist, lateral).
#     On a smooth surface read through a smooth frame, the vertical velocity is smooth, so the
#     per-frame STEP in vertical velocity is the defect. The same spline read at the TRUE arc length
#     is the FLOOR (the .trk cubic is C1, not C2, so it is not zero) and the frame must not add much
#     to it.
#  2. THE AI'S SKITTER. The controller steers on (arc length, lateral) from RaceAI.project. If that
#     pair is quantised, the commanded wheel chatters on a smooth path -- visible as the arc length
#     STANDING STILL for most frames and then jumping a node, and as steer JERK.
#
# BOTH ARMS RUN IN-PROCESS (JuliaMotor.hat_polyline! / RaceAI.proj_node!). The control must SHOW the
# defect or the gate fails: a treatment-only gate proves nothing, and this project has booked that
# instrument fault three times (see the AI-skittering sprints). The env-var arm was itself dead the
# first time it was measured -- `Ref(get(ENV, ...))` at module scope is read at PRECOMPILE time --
# which is why the switches are function calls now.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS",
              normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl"));   using .GPLDat
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
include(joinpath(D, "ai.jl"));       using .RaceAI
using JuliaMotor, Statistics, Printf

pct(v, p) = isempty(v) ? NaN : (sort!(v); v[clamp(ceil(Int, p*length(v)), 1, length(v))])

"Load a GPL track's .trk out of its .dat and build (altitude spline, AI line, ribbon)."
function load_track(dir)
    name = basename(dir)
    dat = first(filter(f -> lowercase(basename(f)) == lowercase(name)*".dat", joinpath.(dir, readdir(dir))))
    d = GPLDat.parse_dat(dat)
    key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
    tmp = tempname()*".trk"; write(tmp, d[key])
    ta = GPLTrack.trk_altitude(tmp)
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x, z) -> 0.0)
    n = length(line.x)
    sv = zeros(n); for i in 2:n; sv[i] = sv[i-1] + hypot(line.x[i]-line.x[i-1], line.z[i]-line.z[i-1]); end
    ribbon = JuliaMotor.TrackSurface([(line.x[i], GPLTrack.trk_height(ta, sv[i], 0.0), line.z[i]) for i in 1:n];
                                     halfwidth = 9.0, cell = 25.0)
    (ta = ta, line = line, ribbon = ribbon)
end

"One arm: `polyline`/`nodeproj` select the pre-SEAM-1 behaviour. v=25 m/s, 2 m off the centreline."
function arm(tr; polyline::Bool, nodeproj::Bool, v = 25.0, lat = 2.0, dt = 1/60)
    JuliaMotor.hat_polyline!(polyline); RaceAI.proj_node!(nodeproj)
    ta, line, ribbon = tr.ta, tr.line, tr.ribbon
    nstep = round(Int, ta.total / (v*dt))
    hq = Float64[]; hs = Float64[]; ld = Float64[]; ps = Float64[]; pl = Float64[]; st = Float64[]
    hint = 0.0
    for k in 0:nstep
        s0 = mod(k*v*dt, line.total)
        p = RaceAI.pose_at(line, s0, lat)
        r = JuliaMotor.hat(ribbon, p[1], p[3])
        push!(ld, r.lapdist)
        push!(hq, GPLTrack.trk_height(ta, r.lapdist, r.lateral))
        push!(hs, GPLTrack.trk_height(ta, s0, lat))
        a, b = RaceAI.project(line, p[1], p[3]; hint = hint); hint = a
        push!(ps, a); push!(pl, b)
        push!(st, RaceAI.controller(line, a, b, 0.0, v, p[1], p[3], p[4], v, 0.0)[3])
    end
    # vertical-velocity step, lap-wrap frames excluded (mod(s) there is the PROBE's discontinuity)
    function wstep(h)
        w = [(h[i+1]-h[i])/dt for i in 1:length(h)-1]
        [abs(w[i+1]-w[i]) for i in 1:length(w)-1
         if abs(ld[i+1]-ld[i]) < 5.0 && abs(ld[i+2]-ld[i+1]) < 5.0]
    end
    dps = [ps[i+1]-ps[i] for i in 1:length(ps)-1 if abs(ps[i+1]-ps[i]) < 5.0]
    (hstep99 = pct(wstep(hq), 0.99), floor99 = pct(wstep(hs), 0.99),
     stall = count(<=(1e-9), dps) / max(length(dps), 1),
     jerk99 = pct([abs(st[i+2] - 2st[i+1] + st[i]) for i in 1:length(st)-2], 0.99),
     latmax = maximum(abs.(pl .- lat)), sadv = median(dps))
end

fails = Ref(0); WORST = Ref(0.0)
check(n, ok, m) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(n, 46), m))
println("SEAM-1 track-frame gate (two arms in-process; tracks under $G)")
const RAN = Ref(0)
for t in ["watglen", "monza", "rouen"]
    dir = joinpath(G, t)
    isdir(dir) || (println("  SKIP  $t (not installed)"); continue)
    tr = load_track(dir); RAN[] += 1
    c = arm(tr; polyline = true,  nodeproj = true)     # control: the pre-SEAM-1 polyline frame
    s = arm(tr; polyline = false, nodeproj = false)    # treatment: the C1 curve frame
    @printf("  %s\n", uppercase(t))
    @printf("    player  dw/frame p99 [m/s]: control %.4f   fixed %.4f   (spline floor %.4f)\n",
            c.hstep99, s.hstep99, s.floor99)
    @printf("    AI      arc length stalled: control %.1f%%   fixed %.1f%%   steer jerk p99 %.5f -> %.5f\n",
            100*c.stall, 100*s.stall, c.jerk99, s.jerk99)
    # premise: the control must reproduce the defect, on every track -- RELATIVE to that track's own
    # spline floor, not against an absolute bar. Monza is flat: its grades are so small that the same
    # frame seam is only 0.025 m/s there, 5x its floor, against 0.198 m/s (19x) at Watkins Glen. An
    # absolute 0.05 m/s bar failed Monza and would have read as "the control does not show the
    # defect" on the one track where the defect is simply quieter. Measured premise margins at
    # baseline: watglen 19.4x, monza 5.0x, rouen 26.1x. The absolute size is a SUITE-level premise
    # below (softband_smoke made the same move for the same reason).
    check("$t control shows the height seam", c.hstep99 > 4*s.floor99,
          @sprintf("%.4f m/s = %.1fx the floor %.4f", c.hstep99, c.hstep99/max(s.floor99,1e-9), s.floor99))
    check("$t control shows the AI staircase", c.stall > 0.5 && c.jerk99 > 0.01,
          @sprintf("stalled %.0f%%, jerk p99 %.4f", 100*c.stall, c.jerk99))
    # treatment: the frame must stop being the dominant source of either symptom
    # treatment: the frame must stop being the dominant source. Two bars, because either alone can be
    # gamed -- "close to the floor" would pass a track whose floor is huge, and "much better than the
    # control" would pass a track that is still kinked but was worse before.
    # Measured: fixed/floor watglen 1.3x, monza 1.0x, rouen 2.5x (rouen is the hilliest of the three);
    # control/fixed watglen 14.8x, monza 4.9x, rouen 10.6x.
    check("$t height seam gone", s.hstep99 <= 3.5*s.floor99,
          @sprintf("%.4f m/s = %.1fx floor (bar 3.5x)", s.hstep99, s.hstep99/max(s.floor99,1e-9)))
    check("$t height seam 4x better than control", s.hstep99 * 4 <= c.hstep99,
          @sprintf("%.4f vs %.4f m/s (%.1fx)", s.hstep99, c.hstep99, c.hstep99/max(s.hstep99,1e-9)))
    check("$t AI arc length advances every frame", s.stall == 0.0 && s.sadv > 0.9*25.0/60,
          @sprintf("stalled %.1f%%, median step %.3f m (expect %.3f)", 100*s.stall, s.sadv, 25.0/60))
    check("$t steer jerk cut 10x", s.jerk99 * 10 <= c.jerk99,
          @sprintf("%.5f vs %.5f", s.jerk99, c.jerk99))
    # the projection must still be ACCURATE, not merely smooth: a car 2 m off the centreline must
    # read as 2 m off it. (A smooth projection that quietly drifts would pass every check above.)
    check("$t projected lateral is accurate", s.latmax < 0.25, @sprintf("max error %.3f m", s.latmax))
    WORST[] = max(WORST[], c.hstep99)
end
# SUITE premise: the defect must be LARGE somewhere, or this gate is watching noise. Measured at
# baseline: 0.219 m/s (rouen), 0.198 (watglen) -- a 0.2 m/s step at 60 Hz is a 12 m/s^2 impulse.
check("suite: the seam is a real jolt somewhere", WORST[] > 0.1, @sprintf("worst control %.3f m/s", WORST[]))
# ---- the RIBBON the frame is carried on ------------------------------------------------------
# The checks above measure the frame's mathematics on a well-behaved centreline. The sim's ribbon is
# NOT well behaved: it is aligned and then re-centred on the visible road over four passes, and those
# passes left Watkins Glen with segments from 0.017 m to 27.1 m, 14 nodes where the path doubled back,
# and a minimum curvature radius of 1.8 m. A frame carried on that is multi-valued wherever the local
# radius is smaller than the lateral offset a car runs at -- which is what produced the last 0.2 m
# one-frame steps in the driven road height. build_surface now de-folds, resamples and smooths; these
# checks assert the three properties that matter, on a centreline deliberately given all three faults,
# and the control arm (JM_RIBBON_DEFOLD=0 JM_RIBBON_SMOOTH=0) must FAIL them.
println("  RIBBON QUALITY (a centreline given a fold, a 2 cm segment and a 2 m jog)")
let
    # a 400 m oval, then the three faults injected into it
    base = [(200.0*cos(t), 120.0*sin(t)) for t in range(0, 2pi, length = 301)][1:end-1]
    cl = copy(base)
    insert!(cl, 40, cl[40] .+ (0.02, 0.0))                 # a 2 cm segment
    insert!(cl, 80, cl[81] .+ (-6.0, 0.0))                 # a node that doubles back
    for k in 120:123; cl[k] = cl[k] .+ (k % 2 == 0 ? (1.6, 0.0) : (-1.6, 0.0)); end   # a tight zig-zag jog
    flat = JuliaMotor.TriangleHAT([JuliaMotor.Tri((-400.0, 0.0, -400.0), (400.0, 0.0, -400.0), (0.0, 0.0, 400.0))];
                                  cell = 200.0)
    function quality(ts)
        n = length(ts.pos)
        seg = [hypot(ts.pos[mod1(i+1,n)][1]-ts.pos[i][1], ts.pos[mod1(i+1,n)][3]-ts.pos[i][3]) for i in 1:n]
        rmin = Inf
        for k in 1:n
            a = ts.pos[mod1(k-1,n)]; b = ts.pos[k]; c = ts.pos[mod1(k+1,n)]
            ax = b[1]-a[1]; az = b[3]-a[3]; bx = c[1]-b[1]; bz = c[3]-b[3]
            la = hypot(ax,az); lb = hypot(bx,bz); (la < 1e-6 || lb < 1e-6) && continue
            dth = atan(ax*bz - az*bx, ax*bx + az*bz)
            rr = abs(dth) < 1e-9 ? Inf : (la+lb)/2/abs(dth)
            rr < rmin && (rmin = rr)
        end
        folds = 0
        for k in 1:n
            a = ts.pos[mod1(k-1,n)]; b = ts.pos[k]; c = ts.pos[mod1(k+1,n)]
            ((b[1]-a[1])*(c[1]-b[1]) + (b[3]-a[3])*(c[3]-b[3]) < 0) && (folds += 1)
        end
        (segmin = minimum(seg), segmax = maximum(seg), rmin = rmin, folds = folds,
         monotone = issorted(ts.lapdist))
    end
    fixed = quality(GPLTrack.build_surface(cl, flat))
    ctrl = withenv("JM_RIBBON_DEFOLD" => "0", "JM_RIBBON_SMOOTH" => "0") do
        quality(GPLTrack.build_surface(cl, flat))
    end
    @printf("    control: seg %.3f..%.2f m, min radius %.2f m, folds %d | fixed: seg %.3f..%.2f m, min radius %.2f m, folds %d\n",
            ctrl.segmin, ctrl.segmax, ctrl.rmin, ctrl.folds, fixed.segmin, fixed.segmax, fixed.rmin, fixed.folds)
    check("control ribbon shows the faults", ctrl.segmin < 0.5 || ctrl.folds > 0 || ctrl.rmin < 8.0,
          @sprintf("seg %.3f m, folds %d, min radius %.2f m", ctrl.segmin, ctrl.folds, ctrl.rmin))
    check("ribbon segments are uniform", fixed.segmin > 1.0 && fixed.segmax < 6.0,
          @sprintf("%.3f..%.2f m", fixed.segmin, fixed.segmax))
    check("ribbon does not double back", fixed.folds == 0, @sprintf("%d fold(s)", fixed.folds))
    check("ribbon radius clears the road half-width", fixed.rmin >= 8.0,
          @sprintf("min radius %.2f m (road half-width 5.5)", fixed.rmin))
    check("ribbon lapdist is monotone", fixed.monotone, "")
end

JuliaMotor.hat_polyline!(false); RaceAI.proj_node!(false)
RAN[] == 0 && (println("  FAIL  no track installed -- gate measured nothing"); fails[] += 1)
println(fails[] == 0 ? "  ✓ SEAM-1 GATE PASS" : "  ✗ SEAM-1 GATE FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
