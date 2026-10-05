# IRFIT-261004 acceptance (torque): drive the REAL player car (DriveRT3D) through the PO's 2026-10-04 3rd- and
# 4th-gear full-throttle pulls to the limiter (test 4) and compare body acceleration per 250-rpm band.
# Gold acceleration is slope-corrected (Alt); the car is built on the gold file's gearbox and corner weights.
#
# Run:  julia --project=. tools/torqueval_261004.jl
using Printf, Statistics
const TT = joinpath(@__DIR__, "..")
include(joinpath(TT, "src", "ibt.jl"));   using .IBT
include(joinpath(TT, "src", "setup.jl")); using .Setup
include(joinpath(TT, "src", "drive_rt3d.jl")); using .DriveRT3D
const G = 9.80665; const HW = 15; const DT = 1/60
lslope(y, k) = (s = 0.0; for j in -HW:HW; s += j*y[k+j]; end; s / (DT * HW*(HW+1)*(2HW+1)/3))

const GOLD = get(ENV, "JM_TQGOLD", expanduser("~/gold standard/julia racer/261004/lotus49_nurburgring nordschleifetourist 2026-10-04 14-04-29.ibt"))
f = ibt_open(GOLD); sp = setup_params(f.yaml)
DriveRT3D.set_transmission!(sp.gear_ratios, sp.final_drive; source = basename(GOLD))
let (m, ff) = DriveRT3D.mass_from_corner_weights(sp.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(GOLD)); end
ch(n) = channel(f, n)
thr, brk, spd, gr, cl, rpm, lat, alt, on = ch.(["Throttle","Brake","Speed","Gear","Clutch","RPM","LatAccel","Alt","IsOnTrack"])
gold = Dict(3 => Tuple{Float64,Float64}[], 4 => Tuple{Float64,Float64}[])
for k in 1+2HW:f.nrows-2HW
    g = Int(gr[k]); haskey(gold, g) || continue
    on[k] > 0.5 || continue
    w = k-HW:k+HW
    all(j -> gr[j] == g, k-2HW:k+2HW) && all(j -> thr[j] > 0.98 && brk[j] < 0.01 && cl[j] > 0.95, w) || continue
    maximum(j -> abs(lat[j]), w) < 0.30G || continue
    push!(gold[g], (rpm[k], lslope(spd, k) + G*lslope(alt, k)/spd[k]))
end

function pull(gear, v0)
    c = DriveRT3D.build_car3d(; v0 = v0)
    c.gear = gear; c.s_gr(c.integ, DriveRT3D.gearratio(gear))
    c.s_we(c.integ, v0/DriveRT3D.RW_R*DriveRT3D.GEARS[gear]*DriveRT3D.FINAL[])
    vs = Float64[]; rp = Float64[]
    for k in 1:60*30
        DriveRT3D.step_car3d!(c, 1.0, 0.0, 0.0, DT; clutch = 0.0, manual = true)
        k > 30 && (push!(vs, c.v); push!(rp, c.rpm))
        c.rpm > 9600 && break
    end
    [(rp[k], lslope(vs, k)) for k in 1+HW:length(vs)-HW]
end

allr = Float64[]
for (g, v0) in ((3, 30.0), (4, 38.0))
    sim = pull(g, v0)
    println("\n$(g)th-gear WOT, body accel m/s^2  (gold n = $(length(gold[g])))")
    println("   rpm band   | gold n  gold  | sim    | sim/gold")
    for lo in 5000:250:9250
        gi = [a for (r, a) in gold[g] if lo <= r < lo+250]; si = [a for (r, a) in sim if lo <= r < lo+250]
        (length(gi) < 8 || isempty(si)) && continue
        gm = median(gi); sm = mean(si)
        lo < 9250 && push!(allr, sm/gm)
        @printf("   %4d-%4d  | %4d  %5.2f  | %5.2f  | %5.2f%s\n", lo, lo+250, length(gi), gm, sm, sm/gm, lo >= 9250 ? "   (limiter)" : "")
    end
end
@printf("\nOVERALL (below 9250 rpm): %d bands, median sim/gold %.3f, range %.3f..%.3f\n", length(allr), median(allr), extrema(allr)...)
