# SETUPMODEL-1 S4 (Part D2): front/rear aero lift from the PO's 261017 runs at front springs 18 / 30 / 35 N/mm.
# Straight, level samples: mean axle shock deflection = a + b·v² + c·ax (ax: the pitch transfer of thrust/drag). The
# axle's aero force = 2 · MR · k · b·v² (garage: front coil-over MR 0.81, rear spring ratio 0.67), so ClA = 2·MR·k·b/(ρ/2)
# with ρ = 1.2. The same lift whatever the spring = the springs are understood and the number is aero.
using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
const DIR = expanduser("~/gold standard/julia racer/261017/telemetry")
const G = 9.80665
for fn in sort(readdir(DIR; join = true))
    endswith(fn, ".ibt") || continue
    f = ibt_open(fn); sp = setup_params(f.yaml)
    v = channel(f, "Speed"); ax = channel(f, "LongAccel"); ay = channel(f, "LatAccel"); on = channel(f, "IsOnTrack")
    df = (channel(f, "LFshockDefl") .+ channel(f, "RFshockDefl")) ./ 2; dr = (channel(f, "LRshockDefl") .+ channel(f, "RRshockDefl")) ./ 2
    idx = [i for i in eachindex(v) if on[i] > 0.5 && v[i] > 20 && abs(ay[i]) < 0.08G]
    length(idx) < 500 && continue
    X = hcat(ones(length(idx)), v[idx].^2, ax[idx])
    bf = X \ df[idx]; br = X \ dr[idx]
    kf = sp.spring_rate_Npmm[:LF]*1000; kr = sp.spring_rate_Npmm[:LR]*1000
    claf = 2*0.81*kf*bf[2]/0.6; clar = 2*0.67*kr*br[2]/0.6        # + = the axle sinks with speed (downforce)
    @printf("%-26s springs %2.0f/%2.0f  n %6d  front: %.2f mm at 70 m/s -> ClA %+.3f m²   rear: %.2f mm -> ClA %+.3f m²\n",
            basename(fn)[24:end], kf/1000, kr/1000, length(idx), 1000bf[2]*70^2, claf, 1000br[2]*70^2, clar)
end
println("julia: ClAf $(-0.06) / ClAr $(-0.04) m² (powertrain.jl AERO_CLAF/CLAR, PHYSFID-1 S9; negative = lift)")
