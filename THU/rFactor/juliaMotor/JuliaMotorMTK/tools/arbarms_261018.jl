# RARBARMS-1 S1: the REAR anti-roll bar's ARM positions (and a check of the front's), identified through the car exactly
# as arbarms_261011.jl did the front: the bar object's stiffness that gives the gold session's roll gradient. Data: the
# PO's IRPLAN-3 E3 (2026-10-18, skidpad, default car, ~0.8 g circles): base, front arms soft / firm, rear arms soft / firm.
#   julia --project=. tools/arbarms_261018.jl            (JM_ARB_AXLE=front|rear|both, default both)
using Printf, Statistics
include(joinpath(@__DIR__, "arbfit_261005.jl"))              # steady, sim_curve, install!, DriveRT3D
const D18 = expanduser("~/gold standard/julia racer/261018/telemetry")
const RUNS = [("base 2/5", "14-07-37", :rear), ("base 2/5", "14-07-37", :front), ("front soft", "14-11-39", :front),
              ("front firm", "14-13-23", :front), ("rear soft", "14-15-00", :rear), ("rear firm", "14-16-45", :rear)]

function gold_roll(fn)
    P = steady(fn); Q = [p for p in P if p.g > 0.3]
    X = hcat([p.ay/G for p in Q], ones(length(Q)))
    0.5*abs((X \ [rad2deg(p.φf) for p in Q])[1] + (X \ [rad2deg(p.φr) for p in Q])[1]), length(Q)
end

function main()
    ax = get(ENV, "JM_ARB_AXLE", "both")
    for (lab, stem, axle) in RUNS
        (ax == "both" || ax == String(axle)) || continue
        fn = first(filter(f -> occursin(stem, f), readdir(D18; join = true)))
        gr, n = gold_roll(fn)
        sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0)
        sym = axle === :front ? car.sys.arbF.k : car.sys.arbR.k
        setk = ModelingToolkit.setp(car.sys, sym); k0 = ModelingToolkit.getp(car.sys, sym)(car.integ)
        grid = axle === :front ? (0.0, 1121.0, 3000.0, 6000.0, 10000.0, 15000.0) : (3000.0, 7000.0, 12714.0, 18000.0, 25000.0, 35000.0)
        rolls = Float64[]
        for k in grid
            setk(car.integ, k); u0 = copy(car.integ.u)
            push!(rolls, sim_curve(car, sp, u0).roll)
        end
        kfit = NaN
        for i in 1:length(grid)-1
            if (rolls[i] - gr)*(rolls[i+1] - gr) <= 0
                kfit = grid[i] + (gr - rolls[i])/(rolls[i+1] - rolls[i])*(grid[i+1] - grid[i]); break
            end
        end
        @printf("%-11s %s %-5s gold roll %.3f °/g (n %d) | sim at k %s = %s °/g -> k %.0f N/m (session's own %.0f; %s / %s)\n",
                lab, stem, axle, gr, n, join(string.(round.(Int, grid)), "/"), join([@sprintf("%.3f", r) for r in rolls], "/"), kfit, k0,
                sp.arb_front, sp.arb_rear)
        flush(stdout)
    end
end
main()
