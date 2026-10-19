# SETUPMODEL-1: identify Garage.GarageParams from iRacing's own garage numbers.
#
# Data: 261017/garage/frames_screens.csv (the PO's 261017 garage screenshots, transcribed) and frames_ibt.csv (every
# distinct CarSetup in the gold .ibt store, exact to display resolution). Residuals are scaled by the display
# resolution (1 N, 0.1 mm, 0.1 deg), so a residual of 1 = one displayed digit.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/garage_fit_261017.jl [--fit] [--report]
#   GF_STALE_W=0.3   weight of screenshot frames whose labels carry the "not re-solved" asterisk
#   GF_OUT=path      write the fitted constants as Julia (default 261017/garage/garage_params_fit.jl)
#   GF_DROP=a,b      leave out frames whose name contains any of these (e.g. spring_perch_low: the LF shock past full
#                    extension, a regime the model does not have)
#   GF_SHEETS=0      leave out 261018/ingest/frames_sheets.csv (the PO's 261018 setup sheets: exact solves, IRPLAN-3 A)
using Printf
include(joinpath(@__DIR__, "..", "src", "garage.jl")); using .Garage

const ROOT = normpath(joinpath(@__DIR__, "..", "..", "261017", "garage"))
const STALE_W = parse(Float64, get(ENV, "GF_STALE_W", "0.3"))
const ONLY = get(ENV, "GF_ONLY", "")          # e.g. "trusted": drop stale screenshots

function readcsv(fn)
    lines = filter(l -> !isempty(strip(l)) && !startswith(l, "#"), readlines(fn))
    hdr = split(lines[1], ',')
    rows = Dict{String,String}[]
    for l in lines[2:end]
        # the src column is quoted and may hold commas
        q = findfirst('"', l)
        src = q === nothing ? "" : strip(l[q:end], '"')
        f = split(q === nothing ? l : l[1:q-1], ',')
        d = Dict{String,String}()
        for (i, h) in enumerate(hdr)
            i <= length(f) && (d[h] = f[i])
        end
        d["src"] = src
        push!(rows, d)
    end
    rows
end
num(d, k) = (v = get(d, k, ""); isempty(v) ? NaN : something(tryparse(Float64, v), NaN))

struct Frame
    name::String
    w::Float64
    K::Knobs
    track::Symbol                      # :flat or a warped garage floor
    cw::NTuple{4,Float64}; rh::NTuple{4,Float64}; sh::NTuple{4,Float64}; ca::NTuple{4,Float64}
    cross::Float64; toe::Float64; usecam::Bool
end

function frames()
    F = Frame[]
    srcs = [("frames_screens.csv", :screen), ("frames_ibt.csv", :ibt)]
    get(ENV, "GF_SHEETS", "1") == "1" && push!(srcs, (joinpath(ROOT, "..", "..", "261018", "ingest", "frames_sheets.csv"), :ibt))
    for (fn, kind) in srcs
        for d in readcsv(joinpath(ROOT, fn))
            c4(p) = (num(d, p*"LF"), num(d, p*"RF"), num(d, p*"LR"), num(d, p*"RR"))
            arm(s) = (s = strip(s); endswith(s, ".0") ? s[1:end-2] : s)
            pk = kind == :ibt ? c4("pack") : (num(d, "packLF"), 0.0, 0.0, 0.0)
            pk = map(x -> isnan(x) ? 0.0 : x, pk)
            K = Knobs(; perch = c4("p"), spring = c4("k"), packer = pk, fuel = num(d, "fuel"),
                      farb_dia = num(d, "fdia"), farb_arm = arm(d["farm"]), rarb_dia = num(d, "rdia"), rarb_arm = arm(d["rarm"]),
                      camber = kind == :screen ? (-0.4, -0.4, -0.5, -0.5) : c4("ca"),
                      toe_front = kind == :screen ? -1.0 : num(d, "toeF"),
                      pressure = kind == :screen ? (152.0, 152.0, 152.0, 152.0) : c4("pr"))
            src = d["src"]
            track = occursin("skidpad", src) ? :skidpad : occursin("charlotte", src) ? :charlotte : :flat
            nm = kind == :screen ? "snip" * d["snip"] : first(split(first(split(basename(src), ".ibt")), ".htm"))
            w = kind == :screen && d["stale"] == "1" ? STALE_W : 1.0
            ONLY == "trusted" && w < 1 && continue
            if ONLY == "sym"
                c = c4("p"); k = c4("k")
                (c[1] == c[2] && c[3] == c[4] && k[1] == k[2] && k[3] == k[4] && w == 1) || continue
            end
            any(x -> occursin(x, nm), split(get(ENV, "GF_DROP", ""), ","; keepempty = false)) && continue
            push!(F, Frame(nm, w, K, track, c4("cw"), c4("rh"), c4("sh"), c4("ca"), num(d, "cross"), num(d, "toeF"),
                           kind == :screen))
        end
    end
    F
end

# ── parameter vector <-> GarageParams ─────────────────────────────────────────────────────────────────────────────────
const PNAMES = [:L1, :L2, :MR1, :MR2, :MRq1, :MRq2, :s01, :s02, :R01, :R02, :u1, :u2, :kt1, :kt2, :karb1, :karb2,
                :beta1, :beta2, :kbump1, :kbump2, :trackratio, :scrub1, :scrub2, :W0, :front0, :fuel_kgL, :fuel_front,
                :cam1, :cam2, :camroll1, :camroll2, :toe_gain, :warp_skid, :warp_charlotte, :kt_p, :rp1, :rp2, :MRk1, :MRk2, :mix1, :mix2, :bar_shown, :gap1, :gap2, :cam_patch]
function toparams(θ)
    v = Dict(zip(PNAMES, θ))
    P = GarageParams(; L = (v[:L1], v[:L2]), MR = (v[:MR1], v[:MR2]), MRq = (v[:MRq1], v[:MRq2]),
                     s0 = (v[:s01], v[:s02]), R0 = (v[:R01], v[:R02]), unsprung = (v[:u1], v[:u2]),
                     kt = (v[:kt1], v[:kt2]), karb = (v[:karb1], v[:karb2]), arm_beta = (v[:beta1], v[:beta2]),
                     kbump = (v[:kbump1], v[:kbump2]), trackratio = v[:trackratio], scrub = (v[:scrub1], v[:scrub2]),
                     W0 = v[:W0], front0 = v[:front0], fuel_kgL = v[:fuel_kgL], fuel_front = v[:fuel_front],
                     cam_gain = (v[:cam1], v[:cam2]), cam_roll = (v[:camroll1], v[:camroll2]), toe_gain = v[:toe_gain],
                     kt_p = v[:kt_p], rp = (v[:rp1], v[:rp2]),
                     MRk = (v[:MRk1], v[:MRk2]), rh_mix = (v[:mix1], v[:mix2]), bar_shown = v[:bar_shown], bump_gap = (v[:gap1], v[:gap2]), cam_patch = v[:cam_patch])
    P, Dict(:flat => 0.0, :skidpad => v[:warp_skid], :charlotte => v[:warp_charlotte])
end
const θ0 = Float64[149.7, 89.4, 0.804, 0.646, 0.0, 0.0, 61.7, 58.7, 87.6, 110.5, 221.0, 250.0, 430.0, 430.0, 10.0, 10.0,
                   0.08, 0.08, 200.0, 200.0, 1.0, 0.0, 0.0, 5936.0 - 43.2*0.75*9.80665, 0.448, 0.75, 0.66,
                   0.027, 0.02, 0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.804, 0.64, 0.03, 0.03, 1.0, 10.0, 10.0, 0.0]
# GF_INIT=path: start from a previous fit (θ_fit), e.g. the symmetric stage
const θINIT = (fn = get(ENV, "GF_INIT", ""); isempty(fn) ? nothing : (include(fn); θ_fit))
const FIXED = Set(Symbol.(split(get(ENV, "GF_FIX", "MRq1,MRq2,kbump1,kbump2"), ',')))

function residuals(θ, F; detail = false)
    P, warp = toparams(θ)
    r = Float64[]; rows = []
    for f in F
        D = solve_static(f.K, P; warp = warp[f.track])
        if !f.usecam && all(!isnan, f.ca)
            # .ibt frame: its camber KNOB is unknown -- set it so the displayed camber is the one recorded, and re-solve
            K2 = deepcopy(f.K)
            for _ in 1:2
                K2.camber = ntuple(i -> f.ca[i] + (f.K.camber[i] - D.camber[i]) + (K2.camber[i] - f.K.camber[i]), 4)
                D = solve_static(K2, P; warp = warp[f.track])
            end
        end
        rr = Float64[]
        if !D.ok
            n = count(!isnan, (f.cw..., f.rh..., f.sh...))
            append!(r, fill(1e3, n)); detail && push!(rows, (f, D, fill(1e3, n))); continue
        end
        for i in 1:4
            isnan(f.cw[i]) || push!(rr, f.w*(D.cw[i] - f.cw[i])/1.0)
            isnan(f.rh[i]) || push!(rr, f.w*(D.rh[i] - f.rh[i])/0.1)
            isnan(f.sh[i]) || push!(rr, f.w*(D.shock[i] - f.sh[i])/0.1)
            f.usecam && !isnan(f.ca[i]) && push!(rr, 0.5*f.w*(D.camber[i] - f.ca[i])/0.1)
        end
        append!(r, rr)
        detail && push!(rows, (f, D, rr))
    end
    # physical bounds (soft walls): unsprung 120..450 N, ratios 0.3..1.2, tyre 100..600 N/mm, mix -0.2..0.2
    v = Dict(zip(PNAMES, θ))
    wall(x, lo, hi) = 30*(max(0, lo - x) + max(0, x - hi))
    for k in (:u1, :u2); push!(r, wall(v[k], 120, 450)/10); end
    for k in (:MR1, :MR2, :MRk1, :MRk2); push!(r, wall(v[k], 0.3, 1.2)*100); end
    for k in (:kt1, :kt2); push!(r, wall(v[k], 100, 600)/10); end
    for k in (:mix1, :mix2); push!(r, wall(v[k], -0.2, 0.2)*100); end
    for k in (:gap1, :gap2); push!(r, wall(v[k], 1, 40)); end
    for k in (:kbump1, :kbump2); push!(r, wall(v[k], 20, 3000)/10); end
    for k in (:beta1, :beta2); push!(r, wall(v[k], -0.15, 0.15)*100); end
    SB = parse(Float64, get(ENV, "GF_SCRUB_MAX", "0.5"))
    for k in (:scrub1, :scrub2); push!(r, wall(v[k], -SB, SB)*100); end
    detail ? rows : r
end

function lm(θ, F; iters = 60)
    free = [i for i in eachindex(θ) if !(PNAMES[i] in FIXED)]
    r = residuals(θ, F); c = sum(abs2, r); λ = 1e-2
    for it in 1:iters
        J = zeros(length(r), length(free))
        for (jj, j) in enumerate(free)
            h = 1e-5*max(1.0, abs(θ[j]))
            θp = copy(θ); θp[j] += h
            J[:, jj] = (residuals(θp, F) .- r) ./ h
        end
        A = J'J; g = J'r
        improved = false
        for _ in 1:12
            δ = -(A + λ*Diagonal(diag(A) .+ 1e-9)) \ g
            θn = copy(θ); θn[free] .+= δ
            rn = residuals(θn, F); cn = sum(abs2, rn)
            if isfinite(cn) && cn < c
                θ, r, c = θn, rn, cn; λ = max(λ/3, 1e-7); improved = true; break
            end
            λ *= 4
        end
        @printf("  it %2d  cost %.1f  rms %.3f digits  λ %.1e\n", it, c, sqrt(c/length(r)), λ)
        improved || break
    end
    θ
end
using LinearAlgebra

function report(θ, F)
    rows = residuals(θ, F; detail = true)
    for (f, D, rr) in rows
        mx = isempty(rr) ? 0.0 : maximum(abs, rr)/f.w
        @printf("%-44s w%.1f  max %5.1f digits | cw %s  rh %s  sh %s  ca %s  cross %.1f (%.1f)\n",
                first(f.name, 44), f.w, mx,
                join((@sprintf("%d(%s)", round(Int, D.cw[i]), isnan(f.cw[i]) ? "-" : string(round(Int, f.cw[i]))) for i in 1:4), " "),
                join((@sprintf("%.1f(%.1f)", D.rh[i], f.rh[i]) for i in 1:4), " "),
                join((@sprintf("%.1f(%.1f)", D.shock[i], f.sh[i]) for i in 1:4), " "),
                join((@sprintf("%.1f(%.1f)", D.camber[i], f.ca[i]) for i in 1:4), " "), D.cross, f.cross)
    end
    for (n, v) in zip(PNAMES, θ)
        @printf("  %-12s %10.4f%s\n", n, v, n in FIXED ? "  (fixed)" : "")
    end
end

F = frames()
println("frames: ", length(F), "  (", count(f -> f.w < 1, F), " stale screenshots at weight ", STALE_W, ")")
θ = θINIT === nothing ? copy(θ0) : (t = copy(θ0); t[1:min(end, length(θINIT))] .= θINIT[1:min(end, length(θINIT))]; t)
if "--fit" in ARGS
    θ = lm(θ, F)
    out = get(ENV, "GF_OUT", joinpath(ROOT, "garage_params_fit.jl"))
    open(out, "w") do io
        println(io, "# written by tools/garage_fit_261017.jl -- θ in PNAMES order")
        println(io, "θ_fit = ", repr(θ))
    end
elseif isfile(joinpath(ROOT, "garage_params_fit.jl"))
    include(joinpath(ROOT, "garage_params_fit.jl")); θ = θ_fit
end
"--report" in ARGS && report(θ, F)

# --emit: print the fitted constants as the GarageParams(...) literal garage.jl installs as PARAMS
if "--emit" in ARGS
    P, w = toparams(θ)
    println("GarageParams(")
    for f in fieldnames(GarageParams)
        v = getfield(P, f)
        r(x) = round(x, sigdigits = 6)
        println("    ", f, " = ", v isa Tuple ? "(" * join(r.(v), ", ") * ")" : r(v), ",")
    end
    println(")")
end
