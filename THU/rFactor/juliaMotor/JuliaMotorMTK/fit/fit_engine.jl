# Fit the engine torque curve from telemetry.
#
# In gear at wide-open throttle, straight-line, with no wheelspin, the rear tyre
# drive force balances:  F_drive = m·LongAccel + ½ρ·CdA·v² + (I_rot/Rw²)·a + roll
# (LongAccel is specific force → road grade cancels; a = du/dt for the rotating
# inertia term).  Then  T_engine = F_drive·Rw / (gear·final·η),  plotted against
# the logged RPM.  Shape (peak torque, where it peaks, falloff) comes from data;
# absolute level carries ~±20% from CdA/η/Rw/inertia assumptions.
#
# Run:  julia --project=. fit/fit_engine.jl

include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "fitutil.jl")); using .FitUtil

const G = 9.80665
const DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
# driveline / resistance assumptions (shape is data-driven; these set the level)
const Rw = 0.33; const η = 0.90; const CdA = 0.9; const Crr = 0.015
const Ieng = 0.10; const Iwheel = 1.0; const finaldrive = 4.11

files = filter(f -> startswith(f,"lotus49_nurburgring") && endswith(f,".ibt"), readdir(DATA))
m = sum(values(Setup.setup_params(IBT.session_yaml(IBT.ibt_open(joinpath(DATA,files[1])))).corner_weight_N))/G
chs = ["RPM","Throttle","Gear","Speed","LongAccel","LatAccel","SteeringWheelAngle",
       "IsOnTrack","LRspeed","RRspeed","AirDensity"]

rpm_pts = Float64[]; T_pts = Float64[]
for fn in files
    f = IBT.ibt_open(joinpath(DATA, fn))
    gear_ratios = Setup.setup_params(f.yaml).gear_ratios     # per-file gearing
    c = Dict(n => IBT.channel(f, n) for n in chs)
    dt = 1/f.tickRate; N = f.nrows
    spd = c["Speed"]
    # smoothed du/dt (5-pt central) for the rotational-inertia term
    a = zeros(N)
    for i in 3:N-2; a[i] = (spd[i+2]+spd[i+1]-spd[i-1]-spd[i-2])/(6dt); end
    for i in 3:N-2
        g = Int(round(c["Gear"][i]))
        (1 <= g <= length(gear_ratios)) || continue
        c["IsOnTrack"][i] > 0.5            || continue
        c["Throttle"][i] > 0.95            || continue          # WOT
        spd[i] > 12                        || continue
        abs(c["LatAccel"][i]) < 3.0        || continue          # straight
        abs(c["SteeringWheelAngle"][i]) < 0.2 || continue
        a[i] > 0.3                         || continue          # accelerating
        v = spd[i]
        κr = ((c["LRspeed"][i]+c["RRspeed"][i])/2 - v)/v
        -0.02 < κr < 0.06                  || continue          # no wheelspin
        gr = gear_ratios[g]*finaldrive
        Irot = Ieng*gr^2 + 4*Iwheel                              # reflected to a wheel
        Fdrive = m*c["LongAccel"][i] + 0.5*c["AirDensity"][i]*CdA*v^2 + (Irot/Rw^2)*a[i] + Crr*m*G
        Teng = Fdrive*Rw/(gr*η)
        (0 < Teng < 800) || continue                            # sanity
        push!(rpm_pts, c["RPM"][i]); push!(T_pts, Teng)
    end
end
println("WOT accel samples: $(length(T_pts))  (m=$(round(m,digits=0))kg, per-file gearing)")

# bin by rpm, median torque
function binmed(x, y; lo=3000, hi=9500, n=26)
    edges = range(lo, hi; length=n+1); bx=Float64[]; by=Float64[]; bw=Float64[]
    for k in 1:n
        ii = findall(j -> edges[k] ≤ x[j] < edges[k+1], eachindex(x))
        length(ii) < 5 && continue
        vals = sort(y[ii]); push!(bx,(edges[k]+edges[k+1])/2)
        push!(by, vals[cld(length(vals),2)]); push!(bw, sqrt(length(ii)))
    end
    bx, by, bw
end
bx, by, bw = binmed(rpm_pts, T_pts)

# fit the engine_torque WOT shape: T(rpm) = Tpeak·max(0.2, 1 − ((rpm−rpm_peak)/spread)²)
wot(rpm, Tpeak, rpm_peak, spread) = Tpeak*max(0.2, 1 - ((rpm-rpm_peak)/spread)^2)
# rpm_peak bounded to the DFV-realistic range — the clean accel data only spans the
# RISING part of the curve (~4400–7500 rpm), so the peak location isn't directly
# observed; we pin it to where a 3.0 L Cosworth DFV peaks (~7500) rather than let it
# extrapolate to redline.
function loss(θ)
    Tpeak, rp, sp = θ
    (Tpeak<150||Tpeak>520||rp<7000||rp>8500||sp<2500||sp>6000) && return 1e12
    sum(bw[k]*(wot(bx[k],Tpeak,rp,sp)-by[k])^2 for k in eachindex(bx))
end
θ, _ = nelder_mead(loss, [410.0, 7500.0, 4000.0]; iters=3000)
Tpeak, rpm_peak, spread = θ
rms = sqrt(sum(bw[k]*(wot(bx[k],θ...)-by[k])^2 for k in eachindex(bx))/sum(bw))
pk_hp = Tpeak*rpm_peak*2π/60/745.7
println("\nFITTED engine torque curve:")
println("  peak torque Tpeak=$(round(Tpeak)) N·m  at rpm_peak=$(round(rpm_peak))  spread=$(round(spread))")
println("  (≈ $(round(pk_hp)) hp at the torque peak; bin RMS=$(round(rms,digits=1)) N·m, $(length(bx)) bins)")

println("\n  torque curve (o telemetry median, * fitted):")
for k in 1:length(bx)
    barT = round(Int, by[k]/8); barF = round(Int, wot(bx[k],θ...)/8)
    line = fill(' ', 60); line[clamp(barT,1,60)]='o'; line[clamp(barF,1,60)]='*'
    println("   $(lpad(round(Int,bx[k]),4)) rpm |", String(line), "  o=$(round(Int,by[k])) *=$(round(Int,wot(bx[k],θ...)))")
end
println("\n→ update powertrain.jl: Tpeak=$(round(Tpeak)), rpm_peak=$(round(rpm_peak)), spread=$(round(spread))")
