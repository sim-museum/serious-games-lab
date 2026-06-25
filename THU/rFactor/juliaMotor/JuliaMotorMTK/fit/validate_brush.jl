# validate_brush.jl — does the PHYSICS-BASED brush tyre reproduce the iRacing Lotus
# 49 grip curve WITHOUT fudge factors?  Extracts the normalized lateral grip vs slip
# angle per axle from the skidpad .ibt (the exact ay/g identity, as fit_skidpad), and
# compares the brush model and the (fudged) Magic Formula to the measured curve.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/fit/validate_brush.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "components", "tyre_law.jl"))   # Magic Formula (fudged)
include(joinpath(@__DIR__, "..", "src", "components", "brush_tyre.jl")) # brush (physics)

const G = 9.80665
const L_WHEELBASE = 2.41
const SKID = joinpath(@__DIR__, "..", "..", "data", "iracing", "lotus49_skidpad 2026-06-14 10-49-07.ibt")

f = IBT.ibt_open(SKID); p = Setup.setup_params(f.yaml); ch(n) = IBT.channel(f, n)
vx = ch("VelocityX"); vy = ch("VelocityY"); r = ch("YawRate"); ay = ch("LatAccel"); spd = ch("Speed"); stw = ch("SteeringWheelAngle")
dt = 1.0/f.tickRate; N = f.nrows
front_fr = (p.corner_weight_N[:LF]+p.corner_weight_N[:RF])/sum(values(p.corner_weight_N))
a = (1-front_fr)*L_WHEELBASE; b = front_fr*L_WHEELBASE; δr = p.steering_ratio
rdot = zeros(N); for i in 2:N-1; rdot[i] = (r[i+1]-r[i-1])/(2dt); end

αf=Float64[]; gf=Float64[]; αr=Float64[]; gr=Float64[]
for i in 2:N-1
    (spd[i]<8 || vx[i]<4 || abs(ay[i])<1) && continue
    abs(atan(vy[i],vx[i]))>deg2rad(30) && continue
    abs(rdot[i])>0.6 && continue
    δ = stw[i]/δr; s = sign(ay[i])
    push!(αf, s*(δ - atan(vy[i]+a*r[i], vx[i]))); push!(gf, s*ay[i]/G)
    push!(αr, s*(  - atan(vy[i]-b*r[i], vx[i]))); push!(gr, s*ay[i]/G)
end
orient!(α,g) = (sum(sign.(α).*sign.(g))<0) && (α .*= -1)
orient!(αf,gf); orient!(αr,gr)

function curve(α, g; hi=deg2rad(13), n=20)
    edges = range(0.0, hi; length=n+1); bx=Float64[]; by=Float64[]
    for k in 1:n
        idx = findall(j -> edges[k] ≤ α[j] < edges[k+1], eachindex(α)); length(idx)<15 && continue
        push!(bx, (edges[k]+edges[k+1])/2); push!(by, sort(g[idx])[length(idx)÷2+1])  # median grip
    end
    bx, by
end

# Fz≈ static axle-corner load on the skidpad (the normalized grip is ~load-independent)
function report(name, α, g, bp, mfp, Fz)
    bx, by = curve(α, g)
    isempty(bx) && (println("  $name: no bins"); return)
    brush = [brush_fy(Fz, x; p=bp)/Fz for x in bx]
    mf    = [tyre_fy(Fz, x; p=mfp)/Fz for x in bx]
    rB = sqrt(sum((brush.-by).^2)/length(by)); rM = sqrt(sum((mf.-by).^2)/length(by))
    @printf("\n  %s axle  (peak meas %.2f g @ %.1f°)\n", name, maximum(by), rad2deg(bx[argmax(by)]))
    @printf("    %-6s %-8s %-8s %-8s\n", "slip°", "iRacing", "brush", "MagicF")
    for k in 1:length(bx)
        @printf("    %-6.1f %-8.2f %-8.2f %-8.2f\n", rad2deg(bx[k]), by[k], brush[k], mf[k])
    end
    @printf("    RMS vs iRacing:  brush %.3f g   MagicFormula %.3f g\n", rB, rM)
end
println("\n================ BRUSH vs iRacing skidpad grip curve ================")
println("  brush params are PHYSICAL (μ, Cα, Cκ, kμ) — no ×1.13 grip fudge, no Cy/Ey shape knobs")
report("FRONT", αf, gf, BRUSH_FRONT, TYRE_SKIDPAD_FRONT, 1415.0)
report("REAR",  αr, gr, BRUSH_REAR,  TYRE_SKIDPAD_REAR,  1670.0)

# ---- identify the PHYSICAL μ, Cα from the data (2-param grid; no shape knobs) ----
function fit_brush(α, g)
    bx, by = curve(α, g); isempty(bx) && return (NaN,NaN,NaN)
    best = (Inf, 0.0, 0.0)
    for μ in 1.05:0.01:1.40, Cα in 10.0:0.5:26.0
        pr = (μ=μ, Cα=Cα, Cκ=0.0, kμ=0.0, Fz0=1.0)
        pred = [brush_fy(1.0, x; p=pr) for x in bx]      # Fz=1 ⇒ Fy=normalized grip (kμ=0)
        rms = sqrt(sum((pred .- by).^2)/length(by))
        rms < best[1] && (best = (rms, μ, Cα))
    end
    best
end
println("\n  ── physics-identified brush parameters (fit to the measured curve) ──")
for (nm, α, g) in (("FRONT",αf,gf), ("REAR",αr,gr))
    rms, μ, Cα = fit_brush(α, g)
    @printf("    %-6s  μ = %.2f   Cα = %.1f /rad   (peak %.2f g @ %.1f° slip)   RMS %.3f g\n",
            nm, μ, Cα, μ, rad2deg(asin(clamp(3μ/Cα,0,1))), rms)
end
println("\n  → these come straight from the data: μ = the measured peak grip, Cα = the")
println("    measured low-slip cornering stiffness. No ×1.13, no Cy/Ey. That is E6.")
