# carsetup_smoke.jl — WWSETUP-1 gate: the two selectable setups reach the model, and the diff physics separates them.
#
#   1. chassis_from_setup maps each gold session to its inputs: WW103 = LSD 35/85°, toe-out, its identified bars and
#      dampers, a 54 % bias; the 261004 default = 75/60°, its identified bars, unscaled dampers. Bars with no gold run
#      fall to the diameter⁴ estimate AND SAY SO in the source line (a silent fallback is the E100 defect).
#   2. The A/B the LSD was identified on: on a ~1 g circle at full throttle the WW103 diff (35° drive ramp) keeps the
#      rear wheels together (|ρ| small), the default's 75° ramp lets the inside wheel spin up (ρ well below 0).
#      ρ = rear wheel-speed split / an open diff's (tools/lsdfit_261005.jl).
#   3. The spool path (no Differential block) still builds -- every pre-WWSETUP tool runs on it.
#
#   julia --project=. tools/carsetup_smoke.jl
using Printf
ENV["JM_NOTC"] = "1"
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const GOLD = expanduser("~/gold standard/julia racer")
const WW  = joinpath(GOLD, "261005", "lotus49_skidpad 2026-10-06 00-21-30.ibt")
const DEF = joinpath(GOLD, "261004", "lotus49_skidpad 2026-10-04 14-36-48.ibt")
const OLD = joinpath(GOLD, "lotus49_nurburgring nordschleife 2026-06-24 15-53-11.ibt")
fails = String[]
check(ok, what) = (println(ok ? "  ok    " : "  FAIL  ", what); ok || push!(fails, what))

if !(isfile(WW) && isfile(DEF))
    println("  SKIP: the 261004/261005 gold sessions are not on this machine ($GOLD)"); exit(0)
end
sp(fn) = setup_params(ibt_open(fn).yaml)
cw = DriveRT3D.chassis_from_setup(sp(WW); source = "ww"); cd = DriveRT3D.chassis_from_setup(sp(DEF); source = "def")
println("  WW103:   ", DriveRT3D.describe_chassis(cw)); println("  default: ", DriveRT3D.describe_chassis(cd))
check(cw.diff == (41.0, 35.0, 85.0, 4.0) && cd.diff == (41.0, 75.0, 60.0, 4.0), "diff from the Differential block (WW 35/85, default 75/60)")
check(cw.toe[1] < 0 && cd.toe[1] < 0 && cw.toe[1] < cd.toe[1] && cw.toe[2] > cd.toe[2] > 0, "toe: WW more front toe-out and more rear toe-in than the default")
check(cw.karb == DriveRT3D.ARB_ID[("0.375\" 5", "0.6875\" firm")] && cd.karb == DriveRT3D.ARB_ID[("0.375\" 2", "0.6875\" 5")] &&
      sum(cw.karb) > sum(cd.karb), "bars: identified values, WW stiffer")
check(cw.cscale == (1.0, 1.15) && cd.cscale == (1.0, 1.0), "dampers: WW measured ratio, default unscaled")
check(cw.bias > cd.bias && abs(cd.bias - 0.585) < 1e-9, "brake split: 53.5 % -> 0.585 (BRAKE-2), 54 % slightly more front")
check(!occursin("estimated", cw.src) && !occursin("estimated", cd.src), "identified sessions carry no fallback note")
if isfile(OLD)
    co = DriveRT3D.chassis_from_setup(sp(OLD); source = "old")
    check(occursin("estimated from 261004's by diameter⁴", co.src) && co.karb[2] < cd.karb[2], "unidentified bars: d⁴ estimate, labelled")
end

function rho_fullthrottle(fn)
    p = sp(fn)
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(fn))
    m, ff = DriveRT3D.mass_from_corner_weights(p.corner_weight_N); DriveRT3D.set_mass!(m, ff; source = basename(fn))
    DriveRT3D.set_chassis!(DriveRT3D.chassis_from_setup(p; source = basename(fn)))
    car = DriveRT3D.build_car3d(; v0 = 30.0); sys = car.sys
    gs = ModelingToolkit.getsym(sys, [sys.u, sys.r, sys.ay, sys.ωRL, sys.ωRR])
    V = 34.0; g = 2; car.gear = g; car.s_gr(car.integ, p.gear_ratios[g])
    ModelingToolkit.setu(sys, [sys.u, sys.v])(car.integ, [V, 0.0])
    ModelingToolkit.setu(sys, [sys.ωf, sys.ωRL, sys.ωRR])(car.integ, [V/0.30, V/DriveRT3D.RW_R, V/DriveRT3D.RW_R])
    car.s_we(car.integ, V/DriveRT3D.RW_R*p.gear_ratios[g]*p.final_drive)
    δ = 0.0; ie = 0.0; ρs = Float64[]
    for n in 1:11*60
        u, r, ay = gs(car.integ)
        thr = if n < 8*60
            δ = clamp(δ + 0.004*(0.95 - abs(ay)/9.80665), 0.0, 0.25)
            t = clamp(0.3 + 0.3*(V - u) + ie, 0, 1); ie = clamp(ie + 0.01*(V - u), -0.4, 0.7); t
        else
            1.0
        end
        DriveRT3D.step_car3d!(car, thr, 0.0, δ/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, r, ay, ωL, ωR = gs(car.integ)
        n > 8*60 + 30 && abs(r) > 0.15 && push!(ρs, (ωR - ωL)*DriveRT3D.RW_R/(r*1.5))
    end
    isempty(ρs) ? NaN : sum(ρs)/length(ρs)
end
ρw = rho_fullthrottle(WW); ρd = rho_fullthrottle(DEF)
@printf("  full throttle on a ~0.95 g circle: rear split ρ  WW103 %.2f   default %.2f\n", ρw, ρd)
check(abs(ρw) < 0.4, "WW103 (35° drive ramp) holds the rear wheels together under power")
check(ρd < -0.5, "default (75° drive ramp) lets the inside rear wheel spin up under power")

DriveRT3D.set_chassis!(DriveRT3D.Chassis())
c0 = DriveRT3D.build_car3d(; v0 = 20.0)
for _ in 1:60; DriveRT3D.step_car3d!(c0, 0.5, 0.0, 0.0, 1/60); end
check(isfinite(c0.v) && c0.v > 15 && !hasproperty(c0.sys, :ωRL), "spool path (no diff) builds and drives")

println(isempty(fails) ? "\n  CARSETUP GATE: PASS ✓" : "\n  CARSETUP GATE: FAIL ✗  " * join(fails, "; "))
exit(isempty(fails) ? 0 : 1)
