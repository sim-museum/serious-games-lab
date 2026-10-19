# IRDATA-261018 S2: does iRacing's engine make more torque in denser air?  Gold only: on full-throttle, straight,
# non-spinning samples, the engine torque implied by the car's acceleration
#   T = (m·ax + ½ρ·CdA·v² + Crr·m·g + m·g·sin(grade)) · Rw / (gear·final·η)
# binned by rpm, per file, with each file's own mass (corner weights), gearing and AirDensity.  If the engine scales
# with density, files at ρ 1.151 (Monza) read ~4.7 % above files at 1.099 (the Ring).
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/wot_density_261018.jl <file.ibt> ...
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
using Printf, Statistics
const G = 9.80665; const CDA = 0.480; const CRR = 0.015; const RW = 0.3337; const ETA = 0.9
println("file                                     rho     m    | T [N·m] by rpm band 4-5k 5-6k 6-7k 7-8k 8-9k")
for fn in ARGS
    f = ibt_open(fn); sp = setup_params(f.yaml); ch(n) = Float64.(channel(f, n))
    m = sum(values(sp.corner_weight_N))/G
    v = ch("Speed"); ax = ch("LongAccel"); thr = ch("Throttle"); gr = ch("Gear"); rpm = ch("RPM"); ρ = median(ch("AirDensity"))
    ay = ch("LatAccel"); lr = ch("LRspeed"); rr = ch("RRspeed"); alt = ch("Alt")
    # road grade over ±1 s (Alt is quantised to ~0.1 m): sin(grade) = dAlt / ds
    n = length(v); sg = zeros(n)
    for k in 61:n-60
        ds = sum(@view v[k-60:k+60])/60; ds > 20 && (sg[k] = (alt[k+60] - alt[k-60])/ds)
    end
    full = 0.98*maximum(thr)
    T = Dict(b => Float64[] for b in 4:8)
    for k in 31:length(v)
        (all(j -> thr[j] > full, k-30:k) && abs(ay[k]) < 1.0 && v[k] > 20 && 2 <= gr[k] <= 5 && all(j -> gr[j] == gr[k], k-30:k)) || continue
        abs(0.5*(lr[k] + rr[k])/v[k] - 1) < 0.08 || continue                     # not spinning
        g = sp.gear_ratios[round(Int, gr[k])]*sp.final_drive
        Tk = (m*ax[k] + 0.5*ρ*CDA*v[k]^2 + CRR*m*G + m*G*sg[k])*RW/(g*ETA)
        b = floor(Int, rpm[k]/1000); haskey(T, b) && push!(T[b], Tk)
    end
    @printf("%-40s %.3f %5.0f | %s\n", basename(fn)[9:min(end, 48)], ρ, m,
            join((length(T[b]) < 30 ? "   -" : @sprintf("%4.0f", median(T[b])) for b in 4:8), " "))
end
