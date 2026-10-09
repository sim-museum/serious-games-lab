# CARPHYS-1 / HANDLING-1: the tyre's SIDEWAYS sliding friction, fitted through the player car against the gold's spins.
#
# Measured first (261009/slide_grip.py): once the car slides at 15–60° of body slip, iRacing's Lotus keeps 1.03–1.15 g
# of total grip, Julia's 0.80–0.87 g. The brush tyre's sliding drop `rs` (0.629) was fitted to locked-wheel BRAKING
# (tools/brakefit_261004.jl) and applied to the lateral force as well. BrushTyre's `rsy` gives the lateral force its own
# sliding fraction (rsy = rs is the old tyre exactly); this fits it.
#
# Method: every gold skidpad event that SPINS (gold_events: power-on squeezes and lift-offs, both setups), replayed
# through the session's car from the settled circle with the gold's own throttle, brake and steering changes, for up to
# JM_SLIDE_SECS (5) s or until the speed falls below 10 m/s. The replay diverges from the gold once the car spins, so
# the comparison is not the trajectory but the SLIDING REGIME: total grip |a| binned by |β|, pooled over the events.
#
#   julia --project=. tools/slidefit_261009.jl                    # rsy grid JM_SLIDE_RSY (default 0.629,0.70,0.75,0.80,0.85)
using Printf, Statistics
include(joinpath(@__DIR__, "replay_261005.jl"))               # goldtrace, settle!, gold_events, install!, FILES, D4, D5

const BINS = ((12.0, 20.0), (20.0, 30.0), (30.0, 45.0), (45.0, 60.0), (60.0, 90.0))
binof(b) = findfirst(r -> r[1] <= b < r[2], BINS)

"""Replay through the spin: no stop at large β (simreplay stops at 40°), with the gold's brake. Returns (β°, |a| g)."""
function simslide(car, sp, u0, gt, n)
    sys = car.sys
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.ax, sys.ay])
    δ0 = settle!(car, sp, u0, gt)
    out = Tuple{Float64,Float64}[]
    for k in 1:n
        δk = δ0 + (gt.δ[k] - gt.δ[1])
        DriveRT3D.step_car3d!(car, gt.thr[k], gt.brk[k], δk/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, ax, ay = get(car.integ)
        hypot(u, v) < 10 && break
        push!(out, (rad2deg(abs(atan(v, abs(u)))), hypot(ax, ay)/G))
    end
    out
end

function pool!(acc, pairs)
    for (b, a) in pairs
        i = binof(b); i === nothing || push!(acc[i], a)
    end
end

function main()
    E = filter(e -> e.spin, gold_events())
    secs = parse(Float64, get(ENV, "JM_SLIDE_SECS", "5"))
    n = round(Int, secs*60)
    rsys = parse.(Float64, split(get(ENV, "JM_SLIDE_RSY", "0.629,0.70,0.75,0.80,0.85"), ","))
    println("gold spin events: ", length(E), "  (", count(e -> e.kind === :power, E), " power-on, ", count(e -> e.kind === :lift, E), " lift-off)")
    cars = Dict{Symbol,Any}()
    for k in (:default, :ww)
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0); cars[k] = (car, sp, copy(car.integ.u))
    end
    traces = map(E) do e
        d = joinpath(e.side === :default ? D4 : D5, e.file)
        isfile(d) || (d = joinpath(D5, e.file)); isfile(d) || (d = joinpath(D4, e.file))
        goldtrace(d, round(Int, e.t*60), n)
    end
    gacc = [Float64[] for _ in BINS]
    for gt in traces
        m = min(n, length(gt.thr))
        pool!(gacc, [(abs(gt.β[k]), gt.amag[k]) for k in 1:m if gt.spd[k] >= 10])
    end
    @printf("%-8s", "rsy"); foreach(r -> @printf("  |β| %2.0f-%2.0f°   ", r...), BINS); println("  score")
    @printf("%-8s", "gold"); foreach(a -> @printf("  %5.3f g (%4d)", isempty(a) ? NaN : mean(a), length(a)), gacc); println()
    for rsy in rsys
        sacc = [Float64[] for _ in BINS]
        for (e, gt) in zip(E, traces)
            car, sp, u0 = cars[e.side]
            for ty in (:FL, :FR, :RL, :RR)
                ModelingToolkit.setp(car.sys, getproperty(getproperty(car.sys, ty), :rsy))(car.integ, rsy)
            end
            pool!(sacc, simslide(car, sp, u0, gt, min(n, length(gt.thr))))
        end
        sc = sum(i -> isempty(sacc[i]) || isempty(gacc[i]) ? 0.0 : min(length(sacc[i]), length(gacc[i]))*(mean(sacc[i]) - mean(gacc[i]))^2, eachindex(BINS))
        @printf("%-8.3f", rsy); foreach(a -> @printf("  %5.3f g (%4d)", isempty(a) ? NaN : mean(a), length(a)), sacc); @printf("  %.2f\n", sc)
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
