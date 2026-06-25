# fit_brush_long.jl — identify the brush tyre's LONGITUDINAL parameters (μx, Cκ)
# from the iRacing Nürburgring braking telemetry, the same physical way the lateral
# μ/Cα came from the skidpad.  Straight-line braking gives the longitudinal grip
# (−LongAccel/g) vs the slip ratio κ = (wheel_speed − speed)/speed; we fit the brush
# Fx law to that curve.  No fudge: μx = peak braking grip, Cκ = the low-slip slope.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/fit/fit_brush_long.jl

using Printf
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "components", "brush_tyre.jl"))
const G = 9.80665
const NUR = joinpath(@__DIR__, "..", "..", "data", "iracing",
                     "lotus49_nurburgring nordschleife 2026-06-14 11-25-36.ibt")

f = IBT.ibt_open(NUR); ch(n) = try IBT.channel(f, n) catch; fill(NaN, f.nrows) end
spd = ch("Speed"); la = ch("LongAccel"); lat = ch("LatAccel")
lf = ch("LFspeed"); rf = ch("RFspeed"); lr = ch("LRspeed"); rr = ch("RRspeed")
fin(x) = isfinite(x)

# straight-line braking samples: not cornering, decelerating, moving
κs = Float64[]; gs = Float64[]
for i in 1:f.nrows
    (fin(spd[i]) && spd[i] > 12) || continue
    (fin(la[i]) && la[i] < -0.4G) || continue       # braking
    (fin(lat[i]) && abs(lat[i]) < 0.35G) || continue # ~straight (low combined slip)
    ws = 0.0; nw = 0
    for w in (lf[i], rf[i], lr[i], rr[i]); fin(w) && (ws += w; nw += 1); end
    nw == 0 && continue
    κ = (ws/nw - spd[i]) / spd[i]                    # mean slip ratio (negative under braking)
    (-0.5 < κ < 0.02) || continue                    # sane braking-slip range
    push!(κs, -κ); push!(gs, -la[i]/G)               # |slip|, braking grip [g]
end
println("\n  straight-line braking samples: ", length(κs))
isempty(κs) && (println("  (no usable braking data)"); exit())

# bin by slip ratio → median grip
edges = range(0.0, 0.30; length=16); bx=Float64[]; by=Float64[]
for k in 1:length(edges)-1
    idx = findall(j -> edges[k] ≤ κs[j] < edges[k+1], eachindex(κs)); length(idx) < 10 && continue
    push!(bx, (edges[k]+edges[k+1])/2); push!(by, sort(gs[idx])[length(idx)÷2+1])
end
println("  binned grip-vs-slip points: ", length(bx))

# fit brush μx, Cκ (Fz=1 ⇒ Fx = normalized grip; no load sensitivity here)
function fit_long(bx, by)
    best = (Inf, 0.0, 0.0)
    for μ in 1.05:0.01:1.45, Cκ in 12.0:1.0:60.0
        pr = (μ=1.0, μx=μ, Cα=0.0, Cκ=Cκ, kμ=0.0, Fz0=1.0)
        pred = [brush_fx(1.0, x; p=pr) for x in bx]
        rms = sqrt(sum((pred .- by).^2)/length(by))
        rms < best[1] && (best = (rms, μ, Cκ))
    end
    best
end
best = fit_long(bx, by)
@printf("\n  ── longitudinal brush fit ──\n    μx = %.2f   Cκ = %.0f /-   RMS %.3f g   (peak %.2f g @ κ=%.0f%%)\n",
        best[2], best[3], best[1], best[2], 100*3*best[2]/best[3])
println("    slip%  iRacing  brush")
for k in 1:length(bx)
    @printf("    %-5.0f  %-7.2f  %.2f\n", 100bx[k], by[k],
            brush_fx(1.0, bx[k]; p=(μ=1.0,μx=best[2],Cα=0.0,Cκ=best[3],kμ=0.0,Fz0=1.0)))
end
@printf("\n  (current brush presets: Cκ_front=%.0f, Cκ_rear=%.0f — update from this fit)\n",
        BRUSH_FRONT.Cκ, BRUSH_REAR.Cκ)
