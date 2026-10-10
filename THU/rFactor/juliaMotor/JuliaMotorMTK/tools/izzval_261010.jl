# CARPHYS-1 S10: the yaw inertia Izz (hand-set 890 kg·m²) against the gold's transients.
#
# A direct fit (Izz·r' = L·Fyf − b·m·ay with Fyf from the rim torque through the fitted steering column) explains
# nothing: R² < 0.03 at every smoothing window, on the skidpad and at the Ring -- the column's ~10 % error in front force
# (its trail collapses at the limit) is ~650 N·m of yaw moment, as large as Izz·r' itself. So Izz is judged by what it
# does: every gold skidpad event (gold_events -- power-on and lift-off, both setups) is replayed through its session
# car from the settled circle with the gold's own throttle and steering changes (as replay_261005) for JM_IZZ_SECS (2)
# s, once per Izz value, and the sim's yaw rate and sideslip are compared with the gold's every frame.
#
# CARPHYS-1 S11: JM_IZZ_PARAM=relax sweeps the tyre relaxation length σ (all four tyres) instead, on a car built with
# relaxation (JM_RELAX is set to a placeholder for the build; each run sets σ).
#
#   julia --project=. tools/izzval_261010.jl
#   JM_IZZ_PARAM=relax julia --project=. tools/izzval_261010.jl
using Printf, Statistics
const PARAM = get(ENV, "JM_IZZ_PARAM", "Izz")
PARAM == "relax" && (ENV["JM_RELAX"] = "0.4,0.4")
include(joinpath(@__DIR__, "replay_261005.jl"))             # gold_events, goldtrace, settle!, install!, FILES, D4, D5, ch

const IZZS = PARAM == "relax" ? (0.1, 0.2, 0.35, 0.5, 0.8) : (600.0, 750.0, 890.0, 1050.0, 1300.0)

function run(car, sp, u0, gt, rg, n, izz)
    sys = car.sys
    if PARAM == "relax"
        for x in (sys.rxFL.σ, sys.rxFR.σ, sys.rxRL.σ, sys.rxRR.σ); ModelingToolkit.setp(sys, x)(car.integ, izz); end
    else
        ModelingToolkit.setp(sys, sys.Izz)(car.integ, izz)
    end
    get = ModelingToolkit.getsym(sys, [sys.u, sys.v, sys.r])
    δ0 = settle!(car, sp, u0, gt)
    er = Float64[]; eb = Float64[]
    for k in 1:n
        δk = δ0 + (gt.δ[k] - gt.δ[1])
        DriveRT3D.step_car3d!(car, gt.thr[k], 0.0, δk/DriveRT3D.MAXSTEER, 1/60; clutch = 0.0, manual = true)
        u, v, r = get(car.integ)
        β = rad2deg(atan(v, max(u, 1.0)))
        abs(β) > 30 && break                                   # the sim spun: compare only what came before
        push!(er, abs(r) - abs(rg[k])); push!(eb, abs(β) - abs(gt.β[k]))
    end
    (rms_r = sqrt(mean(abs2, er)), rms_b = sqrt(mean(abs2, eb)), n = length(er))
end

function main()
    E = gold_events()
    cars = Dict{Symbol,Any}()
    for k in (:default, :ww)
        sp = install!(FILES[k]); car = DriveRT3D.build_car3d(; v0 = 30.0); cars[k] = (car, sp, copy(car.integ.u))
    end
    n = round(Int, parse(Float64, get(ENV, "JM_IZZ_SECS", "2"))*60)
    tot_r = Dict(z => Float64[] for z in IZZS); tot_b = Dict(z => Float64[] for z in IZZS)
    println("event                         | yaw-rate RMS error (deg/s) at ", PARAM, " ", join(IZZS, " / "))
    for e in E
        d = e.side === :default ? joinpath(D4, e.file) : joinpath(D5, e.file)
        isfile(d) || (d = joinpath(D5, e.file)); isfile(d) || (d = joinpath(D4, e.file))
        k0 = round(Int, e.t*60)
        gt = goldtrace(d, k0, n); rg = ch(ibt_open(d), "YawRate")[k0:k0+n]
        car, sp, u0 = cars[e.side]
        res = [run(car, sp, u0, gt, rg, min(n, length(gt.thr) - 1), z) for z in IZZS]
        @printf("%-8s %-20s |", e.kind, "$(e.file[17:min(end,32)]):$(round(e.t, digits=1))")
        for (z, s) in zip(IZZS, res)
            @printf(" %6.2f", rad2deg(s.rms_r)); push!(tot_r[z], s.rms_r); push!(tot_b[z], s.rms_b)
        end
        println()
    end
    println("\nmean over ", length(E), " events:")
    for z in IZZS
        @printf("  %s %6.2f: yaw-rate RMS %.2f deg/s, sideslip RMS %.2f deg\n", PARAM, z, rad2deg(mean(tot_r[z])), mean(tot_b[z]))
    end
end
abspath(PROGRAM_FILE) == (@__FILE__) && main()
