# Fit the isothermal tyre lateral grip curve to the iRacing skidpad telemetry.
#
# Method (minimal assumptions): on a flat skidpad in quasi-steady cornering,
# Newton's laws give, for EACH axle, the exact identity
#         Fy_axle / Fz_axle = ay / g
# (front:  Fyf = m·ay·b/L, Fzf = m·g·b/L  →  ratio ay/g; same for rear).
# So the normalised lateral force is just ay/g — independent of mass, CG height,
# track, and load transfer.  Only the *slip angle* needs geometry (wheelbase L
# and the static weight split set a, b).  We therefore read off the tyre's
# normalised grip curve  μ_used = ay/g  vs  slip angle, per axle, and fit a
# Magic Formula to it.  Front and rear are fitted separately (Lotus 49 = small
# front / big rear tyres, 152 vs 207 kPa).
#
# Run:  julia --project=. fit/fit_skidpad.jl

include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup

const G = 9.80665
const SKID = joinpath(@__DIR__, "..", "..", "data", "iracing",
                      "lotus49_skidpad 2026-06-14 10-49-07.ibt")
const L_WHEELBASE = 2.41   # Lotus 49 wheelbase [m] (not in .ibt — published spec)

# ---- load data + parameters --------------------------------------------------
f = IBT.ibt_open(SKID)
p = Setup.setup_params(f.yaml)
ch(n) = IBT.channel(f, n)

vx  = ch("VelocityX");  vy = ch("VelocityY");  r = ch("YawRate")
ay  = ch("LatAccel");   spd = ch("Speed")
stw = ch("SteeringWheelAngle")
dt  = 1.0 / f.tickRate
N   = f.nrows

m_total  = sum(values(p.corner_weight_N)) / G                 # kg (incl. setup fuel)
front_fr = (p.corner_weight_N[:LF] + p.corner_weight_N[:RF]) / sum(values(p.corner_weight_N))
a = (1 - front_fr) * L_WHEELBASE     # CG → front axle [m]
b =      front_fr  * L_WHEELBASE     # CG → rear  axle [m]
δ_ratio = p.steering_ratio           # 10:1
println("mass=$(round(m_total,digits=1)) kg  front_frac=$(round(front_fr,digits=3))  "*
        "a=$(round(a,digits=3)) b=$(round(b,digits=3)) m  steer ratio=$(δ_ratio):1")

# ---- yaw acceleration (central diff) for a quasi-steady gate -----------------
rdot = zeros(N)
@inbounds for i in 2:N-1
    rdot[i] = (r[i+1] - r[i-1]) / (2dt)
end

# ---- per-sample slip angles + normalised grip, with filtering ----------------
αf = Float64[];  gf = Float64[]      # front: (slip angle, ay/g)
αr = Float64[];  gr = Float64[]      # rear
for i in 2:N-1
    spd[i] < 8.0      && continue                 # must be moving
    vx[i]  < 4.0      && continue                 # forward only (drop spins/reverse)
    abs(ay[i]) < 1.0  && continue                 # actually cornering
    β = atan(vy[i], vx[i])
    abs(β) > deg2rad(30) && continue              # drop big slides/spins
    abs(rdot[i]) > 0.6 && continue                # quasi-steady (low yaw accel)
    δ  = stw[i] / δ_ratio                         # road-wheel steer angle [rad]
    af = δ - atan(vy[i] + a*r[i], vx[i])          # front slip angle
    ar =   - atan(vy[i] - b*r[i], vx[i])          # rear slip angle
    s  = sign(ay[i])                              # fold both turn directions
    push!(αf, s*af); push!(gf, s*ay[i]/G)
    push!(αr, s*ar); push!(gr, s*ay[i]/G)
end
println("kept $(length(gf)) quasi-steady cornering samples (of $N)")

# orient sign so grip is positive for positive slip (robust to convention)
orient!(α, g) = (sum(sign.(α).*sign.(g)) < 0) && (α .*= -1)
orient!(αf, gf); orient!(αr, gr)

# ---- bin by slip angle, robust median grip per bin ---------------------------
function bins(α, g; lo=0.0, hi=deg2rad(14), n=22)
    edges = range(lo, hi; length=n+1)
    bx = Float64[]; by = Float64[]; bw = Float64[]
    for k in 1:n
        idx = findall(j -> edges[k] ≤ α[j] < edges[k+1], eachindex(α))
        length(idx) < 15 && continue
        vals = sort(g[idx])
        push!(bx, (edges[k]+edges[k+1])/2)
        push!(by, vals[cld(length(vals),2)])      # median grip
        push!(bw, sqrt(length(idx)))               # weight ~ √count
    end
    bx, by, bw
end
bxf, byf, bwf = bins(αf, gf)
bxr, byr, bwr = bins(αr, gr)

# ---- Magic Formula + dependency-free Nelder-Mead -----------------------------
mf(α, μ, B, C, E) = μ * sin(C * atan(B*α - E*(B*α - atan(B*α))))

function loss(θ, bx, by, bw)
    μ, B, C, E = θ
    pen = 0.0
    μ<0.5||μ>2.5    ? (pen += 1e3*(min(abs(μ-0.5),abs(μ-2.5))+1)) : nothing
    B<2 ||B>40      ? (pen += 1e3) : nothing
    C<1 ||C>2.5     ? (pen += 1e3) : nothing
    E>1             ? (pen += 1e3) : nothing
    s = 0.0
    for k in eachindex(bx)
        s += bw[k] * (mf(bx[k], μ, B, C, E) - by[k])^2
    end
    s + pen
end

function nelder_mead(F, x0; iters=4000, step=0.15)
    n = length(x0)
    simplex = [copy(x0)]
    for i in 1:n
        x = copy(x0); x[i] += (x[i] != 0 ? step*abs(x[i]) : step); push!(simplex, x)
    end
    fv = [F(x) for x in simplex]
    for _ in 1:iters
        o = sortperm(fv); simplex = simplex[o]; fv = fv[o]
        xbar = sum(simplex[1:end-1]) / n
        xr = xbar + (xbar - simplex[end]); fr = F(xr)
        if fr < fv[1]
            xe = xbar + 2*(xbar - simplex[end]); fe = F(xe)
            simplex[end], fv[end] = fe < fr ? (xe, fe) : (xr, fr)
        elseif fr < fv[end-1]
            simplex[end], fv[end] = xr, fr
        else
            xc = xbar + 0.5*(simplex[end] - xbar); fc = F(xc)
            if fc < fv[end]
                simplex[end], fv[end] = xc, fc
            else
                for i in 2:n+1
                    simplex[i] = simplex[1] + 0.5*(simplex[i] - simplex[1]); fv[i] = F(simplex[i])
                end
            end
        end
    end
    o = sortperm(fv); simplex[o[1]], fv[o[1]]
end

const PKY2 = 2.2                       # load-sat shape (unidentified at single load — kept default)
const LOADF = sin(2*atan(1/PKY2))      # mf_stiffness factor at Fz=Fz0  (→ pKy1 mapping)

function fit_axle(name, bx, by, bw)
    μ0 = maximum(by) * 1.02
    # init slip stiffness from the first two bins' slope
    B0 = length(bx) ≥ 2 ? (by[2]-by[1])/(bx[2]-bx[1]) / (μ0*1.5) : 10.0
    θ0 = [μ0, clamp(B0, 4, 25), 1.5, -0.5]
    θ, L = nelder_mead(θ -> loss(θ, bx, by, bw), θ0)
    μ, B, C, E = θ
    rms = sqrt(sum(bw[k]*(mf(bx[k],μ,B,C,E)-by[k])^2 for k in eachindex(bx)) / sum(bw))
    # grip-limit slip = where the curve first reaches 95% of its max grip
    αg = range(0, deg2rad(16); length=400)
    fg = [mf(α,μ,B,C,E) for α in αg]
    pk = maximum(fg)
    α95 = rad2deg(αg[findfirst(≥(0.95pk), fg)])
    By = B                               # normalised stiffness/shape coeff (= Tyre's By)
    pKy1 = By * C * μ / LOADF            # → Tyre component pKy1 param (with pKy2=$PKY2)
    println("\n── $name axle fit ──")
    println("  μ=$(round(μ,digits=3))  B=$(round(B,digits=2))  C=$(round(C,digits=3))  E=$(round(E,digits=3))")
    println("  peak grip=$(round(pk,digits=3)) g, reached by $(round(α95,digits=1))° slip "*
            "(data plateaus — post-peak falloff not resolved by skidpad)")
    println("  → Tyre params: μy=$(round(μ,digits=3)) Cy=$(round(C,digits=3)) Ey=$(round(E,digits=3)) pKy1=$(round(pKy1,digits=1))")
    println("  weighted RMS over bins = $(round(rms,digits=4)) g   (n_bins=$(length(bx)))")
    (; name, μ, B, C, E, pKy1, bx, by)
end

front = fit_axle("FRONT", bxf, byf, bwf)
rear  = fit_axle("REAR",  bxr, byr, bwr)

# ---- loop closure: predict ay from the fitted curves vs measured ay ----------
# Each axle independently predicts grip = μ·MF(α); both should reproduce ay/g.
function closure(fit, α, g)
    pred = [mf(α[i], fit.μ, fit.B, fit.C, fit.E) for i in eachindex(α)]
    res  = pred .- g
    rms  = sqrt(sum(abs2, res)/length(res))
    ḡ = sum(g)/length(g)
    r2 = 1 - sum(abs2, res)/sum(x->abs2(x-ḡ), g)
    println("  $(fit.name): predicted vs measured grip  RMS=$(round(rms,digits=3)) g  R²=$(round(r2,digits=3))  (n=$(length(g)))")
end
println("\nLoop closure (model-predicted lateral grip vs measured ay/g, all kept samples):")
closure(front, αf, gf)
closure(rear,  αr, gr)

# ---- ASCII overlay: binned data (o) vs fitted curve (*) ----------------------
function ascii_curve(fit)
    println("\n  $(fit.name): grip vs slip angle   (o = telemetry median, * = fitted MF)")
    rows = 14; W = 56; ymax = 1.7
    αmax = deg2rad(15)
    grid = fill(' ', rows, W)
    for c in 1:W
        α = αmax * (c-1)/(W-1)
        y = mf(α, fit.μ, fit.B, fit.C, fit.E)
        rr = rows - clamp(round(Int, y/ymax*(rows-1)), 0, rows-1)
        grid[rr, c] = '*'
    end
    for k in eachindex(fit.bx)
        c = clamp(round(Int, fit.bx[k]/αmax*(W-1))+1, 1, W)
        rr = rows - clamp(round(Int, fit.by[k]/ymax*(rows-1)), 0, rows-1)
        grid[rr, c] = grid[rr,c]=='*' ? '⊛' : 'o'
    end
    for rr in 1:rows
        ylab = round(ymax*(rows-rr)/(rows-1), digits=2)
        println("  ", lpad(ylab,4), " │", String(grid[rr, :]))
    end
    println("       └", "─"^W); println("        0", " "^(W-6), "15°  slip")
end
ascii_curve(front); ascii_curve(rear)

println("\nSuggested Tyre params (normalised, isothermal) — wire into tyre.jl presets:")
println("  FRONT: μy=$(round(front.μ,digits=3)) Cy=$(round(front.C,digits=3)) Ey=$(round(front.E,digits=3)) pKy1=$(round(front.pKy1,digits=1))")
println("  REAR : μy=$(round(rear.μ,digits=3)) Cy=$(round(rear.C,digits=3)) Ey=$(round(rear.E,digits=3)) pKy1=$(round(rear.pKy1,digits=1))")
