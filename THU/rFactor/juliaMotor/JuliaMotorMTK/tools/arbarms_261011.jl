# IRGOLD-1: the FRONT anti-roll bar's ARM positions, identified through the car from the PO's 261011 test 4.
#
# The garage's bar is a diameter and an arm position (settings, not rates). Until now `chassis_from_setup` scaled bars by
# diameter⁴ and ignored the arms, so soft / 2 / 4 / firm were one car. Test 4 ran steady ~1 g circles at soft, 4 and firm
# (0.375"), the default (arms 2) is in test 1. For each session: the gold's roll gradient from its shock deflections
# (wwab_261005 steady(): (dL − dR)/MR/track, both axles, regressed on g), and the sim's from a constant-speed steering
# ramp (arbfit_261005 sim_curve) over a grid of front bar stiffness karb_f -- interpolated to the karb_f that gives the
# gold's gradient. Rear bar as the session's.
#   julia --project=. tools/arbarms_261011.jl
using Printf, Statistics
include(joinpath(@__DIR__, "arbfit_261005.jl"))              # steady, sim_curve, install!, DriveRT3D
const D10 = expanduser("~/gold standard/julia racer/261010")
const ARMS = [("2 (default)", "17-46-09"), ("2 (default)", "19-18-36"), ("soft", "15-20-13"), ("4", "15-24-06"), ("firm", "15-28-20")]

function gold_roll(fn)
    P = steady(fn); Q = [p for p in P if p.g > 0.3]
    X = hcat([p.ay/G for p in Q], ones(length(Q)))
    0.5*abs((X \ [rad2deg(p.φf) for p in Q])[1] + (X \ [rad2deg(p.φr) for p in Q])[1]), length(Q)
end

function main()
    grid = (0.0, 1121.0, 3000.0, 6000.0, 10000.0, 15000.0)
    for (lab, stem) in ARMS
        fn = first(filter(f -> occursin(stem, f), readdir(D10; join = true)))
        gr, n = gold_roll(fn)
        sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0)
        # the bar OBJECT's own stiffness (CARPHYS-1 S2): the vehicle-level karb_f is no longer connected to it; the front
        # corners carry no roll term, so arbF.k is exactly the front bar
        setkf = ModelingToolkit.setp(car.sys, car.sys.arbF.k)
        rolls = Float64[]
        for kf in grid
            setkf(car.integ, kf); u0 = copy(car.integ.u)
            push!(rolls, sim_curve(car, sp, u0).roll)
        end
        # interpolate karb_f at the gold's gradient (roll falls as kf rises)
        kfit = NaN
        for i in 1:length(grid)-1
            if (rolls[i] - gr)*(rolls[i+1] - gr) <= 0
                kfit = grid[i] + (gr - rolls[i])/(rolls[i+1] - rolls[i])*(grid[i+1] - grid[i]); break
            end
        end
        @printf("%-12s %s  gold roll %.3f °/g (n %d) | sim roll at karb_f %s = %s °/g  -> karb_f %.0f N/m   (%s)\n", lab, stem, gr, n,
                join(string.(round.(Int, grid)), "/"), join([@sprintf("%.3f", r) for r in rolls], "/"), kfit, sp.arb_front)
        flush(stdout)
    end
end
main()
