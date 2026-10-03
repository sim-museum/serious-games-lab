# E91-S10 acceptance: drive the REAL player car (DriveRT3D / DrivenVehicle3D) through the gold's three
# straight-line manoeuvres and compare, band by band, against the 2026-10-02 iRacing Nordschleife runs:
#   clutch-in coast, 5th-gear zero-throttle coast, and 4th/5th full-throttle pulls.
# The car is built on the SAME session's gearbox and mass (set_transmission!/set_mass! from the gold
# file), at the session's air density (1.099 = the model's ρair 1.10). Gold decel is slope-corrected.
# No decomposition: total longitudinal acceleration, sim vs gold, at matched speed and gear.
#
# Run:  julia --project=. tools/longval_261002.jl
using Printf, Statistics
const TT = joinpath(@__DIR__, "..")
include(joinpath(@__DIR__, "longfit_261002.jl"))           # gold loader (load, Pt, REF)
include(joinpath(TT, "src", "drive_rt3d.jl")); using .DriveRT3D

ring = first(filter(f -> occursin("nurburgring", f) && endswith(f, ".ibt"), sort(readdir(REF; join = true))))
let p = setup_params(ibt_open(ring).yaml)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(ring))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N)
    DriveRT3D.set_mass!(m, ff; source = basename(ring))
    @printf("session: %s  gears %s x %.2f  m %.1f kg\n", basename(ring), p.gear_ratios, p.final_drive, m)
end

# returns (v, accel) samples at 60 Hz, accel from a ±0.25 s least-squares slope
function run(; v0, gear, thr, clutch, vstop_lo = 12.0, vstop_hi = 120.0, tmax = 120.0)
    c = DriveRT3D.build_car3d(; v0 = v0)
    c.gear = gear; c.s_gr(c.integ, DriveRT3D.gearratio(gear))
    gear > 0 && c.s_we(c.integ, v0/DriveRT3D.RW_R*DriveRT3D.GEARS[gear]*DriveRT3D.FINAL[])
    vs = Float64[]; rp = Float64[]
    for k in 1:round(Int, tmax*60)
        DriveRT3D.step_car3d!(c, thr, 0.0, 0.0, 1/60; clutch = clutch, manual = true)
        k > 30 && (push!(vs, c.v); push!(rp, c.rpm))           # drop 0.5 s of settling
        (c.v < vstop_lo || c.v > vstop_hi || c.rpm > 9400) && break
    end
    a = [sum(j*vs[k+j] for j in -15:15)/((1/60)*15*16*31/3) for k in 16:length(vs)-15]
    vs[16:end-15], a, rp[16:end-15]
end

function table(title, gold, sv, sa; bands = 10:5:65)
    println("\n", title); println("   km/h       | gold n   gold   | sim    | sim/gold")
    rs = Float64[]
    for k in 1:length(bands)-1
        lo, hi = bands[k], bands[k+1]
        gi = [p for p in gold if lo <= p.v < hi]; si = findall(v -> lo <= v < hi, sv)
        (length(gi) < 30 || isempty(si)) && continue
        g = mean(p.dec for p in gi); s = -mean(sa[si])
        push!(rs, s/g)
        @printf("   %3.0f-%3.0f    | %5d  %6.3f  | %6.3f | %5.2f\n", 3.6lo, 3.6hi, length(gi), g, s, s/g)
    end
    isempty(rs) || @printf("   median sim/gold %.3f  (range %.3f..%.3f, %d bands)\n", median(rs), extrema(rs)..., length(rs))
    rs
end

dis, eng, _ = load(REF); _, _, wot = load(dirname(REF))
dis = minseg(dis, 60); eng = minseg(eng, 30); wot = minseg(wot, 20)
isring(p) = occursin("nurburgring", p.file)
r1 = table("CLUTCH-IN COAST, decel m/s^2 (gold: Ring, disengaged)", filter(isring, dis), run(v0 = 63.0, gear = 5, thr = 0.0, clutch = 1.0)[1:2]...)
# the Ring's 36-54 km/h band is 221 points; the FLAT Centripetal Circuit has 2000+ there. Shown for
# reference (mixed masses 605/629 kg -- a ≤4 % effect on the aero term only), not counted in OVERALL.
table("CLUTCH-IN COAST, all three tracks (reference only)", dis, run(v0 = 63.0, gear = 5, thr = 0.0, clutch = 1.0)[1:2]...)
r2 = table("5th-GEAR ZERO-THROTTLE COAST, decel m/s^2 (gold: Ring, gear 5, clutch engaged)",
           filter(p -> isring(p) && p.gear == 5, eng), run(v0 = 63.0, gear = 5, thr = 0.0, clutch = 0.0)[1:2]...)
# WOT gold from sessions on the SAME gearing (the 2026-10-02 Ring set and any older 0.846x4.22 capture)
gr5 = DriveRT3D.GEARS[5]*DriveRT3D.FINAL[]; gr4 = DriveRT3D.GEARS[4]*DriveRT3D.FINAL[]
r3 = table("5th-GEAR WOT, ACCEL as negative decel m/s^2 (gold: gear 5 at this gearing)",
           filter(p -> p.gear == 5 && abs(p.gr - gr5) < 0.01, wot), run(v0 = 25.0, gear = 5, thr = 1.0, clutch = 0.0)[1:2]...)
r4 = table("4th-GEAR WOT (gold: gear 4 at this gearing)",
           filter(p -> p.gear == 4 && abs(p.gr - gr4) < 0.01, wot), run(v0 = 22.0, gear = 4, thr = 1.0, clutch = 0.0)[1:2]...)
allr = vcat(r1, r2, r3, r4)
@printf("\nOVERALL: %d bands, median sim/gold %.3f, worst %.3f\n", length(allr), median(allr), allr[argmax(abs.(allr .- 1))])
