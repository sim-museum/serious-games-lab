# IRGOLD-1: identify runtime parameters of the car THROUGH the gold-input replay (tools/irgold_replay.jl).
#
# Each Distributed worker builds the session cars of its share of the gold files once (mtkcompile is the slow part)
# and keeps its windows; the master sends parameter sets, the workers replay every window under them (runtime
# parameters only -- setp, no rebuild) and return per-window scores. The objective is the mean over windows of
#     (yaw-rate RMS err / (gold yaw-rate RMS + 2 °/s))² + (ay RMS err / (gold ay RMS + 0.05 g))² + (β RMS err / (gold β RMS + 0.5°))²
#   + (speed RMS err / 2 km/h)²
# i.e. each channel's error relative to what there was to follow.
#
#   JM_IRG_FILES="15-35-50,15-45-00,19-30-13,19-34-35,16-53-12,17-03-15"   files (default: every 152 kPa file = Monza + Ring)
#   JM_FIT_WORKERS=6
#   JM_FIT_PARAMS="muf=1.347,mur=1.494,caf=26.17,car=27.77"                the start point (names: see PARAM_MAP)
#   JM_FIT_MODE=eval | coord   (one evaluation, or a coordinate search with JM_FIT_STEPS="muf=0.03,..." and JM_FIT_ITERS)
#   julia --project=. tools/irgold_fit.jl
using Distributed, Printf, Statistics

const NW = parse(Int, get(ENV, "JM_FIT_WORKERS", "6"))
nprocs() == 1 && addprocs(NW; exeflags = "--project=$(dirname(@__DIR__))", env = [k => v for (k, v) in ENV if startswith(k, "JM_")])

@everywhere begin
    include(joinpath($(@__DIR__), "irgold_replay.jl"))
    include(joinpath($(@__DIR__), "irgold_params.jl"))
    const JOBS = Any[]                                         # (car, sp, u0, g, windows, test, stem)
    const WARM = Dict{Tuple{String,Int},Any}()                 # (stem, k0) -> settled (state, δ, ie) of the last evaluation
    function load_jobs!(files)
        for fn in files
            g = goldfile(fn); W = windows(g); isempty(W) && continue
            sp = install!(fn); car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u)
            push!(JOBS, (car, sp, u0, g, W, testof(fn), match(r"(\d\d-\d\d-\d\d)\.ibt$", fn).captures[1]))
        end
        sum(length(j[5]) for j in JOBS; init = 0)
    end
    function eval_jobs(pv)
        out = NamedTuple[]
        for (car, sp, u0, g, W, test, stem) in JOBS
            setparams!(car, pv)
            for w in W
                key = (stem, w.k0); SETTLED[] = nothing
                gold, sim, _ = try replay(car, sp, u0, g, w; warm = get(WARM, key, nothing)) catch; (nothing, nothing, nothing) end
                # keep the settled state for the next evaluation (a failed or crashed settle starts cold next time)
                (gold !== nothing && SETTLED[] !== nothing) ? (WARM[key] = SETTLED[]) : delete!(WARM, key)
                s = gold === nothing ? nothing : score(gold, sim)
                # a failed settle (the sim cannot hold the gold's steady state) or a crash: the per-window cap, so failing a
                # window is never cheaper than following it badly (a 2.0 penalty let the fit drop front grip until the
                # hardest skidpad windows failed instead of being scored)
                s === nothing && (push!(out, (; test, stem, t = w.k0/60, J = 10.0, ok = false)); continue)
                rβ = sqrt(mean([p.β^2 for p in gold])); ray = sqrt(mean([p.ay^2 for p in gold]))
                # + the speed: RMS km/h error over the window, on a 2 km/h scale (braking, drive, cornering drag)
                J = (s.er/(s.rr + 2))^2 + (s.eay/(ray + 0.05))^2 + (s.eβ/(rβ + 0.5))^2 +
                    (get(ENV, "JM_FIT_NOSPEED", "0") == "1" ? 0.0 : (s.ev/2.0)^2)   # JM_FIT_NOSPEED: handling only
                push!(out, (; test, stem, t = w.k0/60, J = min(J, 10.0), ok = true, s...))
            end
        end
        out
    end
end

parsepv(s) = Dict(String(strip(split(x, "=")[1])) => parse(Float64, split(x, "=")[2]) for x in split(s, ","; keepempty = false))

const NFAIL = Ref(0)
function evaluate(pv)
    rs = pmap(w -> remotecall_fetch(eval_jobs, w, pv), workers())
    rows = reduce(vcat, rs)
    NFAIL[] = count(r -> !r.ok, rows)
    (mean(r.J for r in rows), rows)
end

function report(rows)
    for test in unique(r.test for r in rows)
        R = filter(r -> r.test == test && r.ok, rows); nf = count(r -> r.test == test && !r.ok, rows)
        isempty(R) && continue
        @printf("    %-14s %3d win %2d fail J %.3f | r %.2f/%.2f °/s  ay %.3f g  β %.2f°  v %.2f km/h (end %+.1f)  τ %.2f/%.2f Nm  pk %.2f\n", test, length(R), nf,
                mean(r.J for r in R), mean(r.er for r in R), mean(r.rr for r in R), mean(r.eay for r in R), mean(r.eβ for r in R),
                mean(r.ev for r in R), mean(r.dv for r in R),
                mean(r.eτ for r in R), mean(r.τg for r in R), (p = filter(isfinite, [r.pkratio for r in R]); isempty(p) ? NaN : mean(p)))
    end
end

function main()
    files = sort(filter(f -> endswith(f, ".ibt"), readdir(DG; join = true)); by = f -> match(r"2026-(.*)\.ibt", f).captures[1])
    only = split(get(ENV, "JM_IRG_FILES", ""), ","; keepempty = false)
    files = isempty(only) ? filter(f -> !occursin("skidpad", f), files) : filter(f -> any(o -> occursin(o, f), only), files)
    files = irg_files(files)                                   # the wrong-setup files (irgold_replay.jl IRG_EXCLUDE)
    # spread the files over the workers by size (big files first, round robin)
    files = sort(files; by = filesize, rev = true)
    ws = workers(); share = [String[] for _ in ws]
    for (i, f) in enumerate(files); push!(share[mod1(i, length(ws))], f); end
    nwin = sum(fetch.([remotecall(load_jobs!, w, share[i]) for (i, w) in enumerate(ws)]))
    @printf("%d files, %d windows on %d workers\n", length(files), nwin, length(ws)); flush(stdout)
    pv = parsepv(get(ENV, "JM_FIT_PARAMS", ""))
    J, rows = evaluate(pv); @printf("start %s  J %.4f  (%d failed)\n", pv, J, NFAIL[]); report(rows); flush(stdout)
    get(ENV, "JM_FIT_MODE", "eval") == "coord" || return
    steps = parsepv(get(ENV, "JM_FIT_STEPS", ""))
    for it in 1:parse(Int, get(ENV, "JM_FIT_ITERS", "3"))
        for (k, h) in steps
            base = get(pv, k, NaN); isfinite(base) || error("JM_FIT_PARAMS must give a start for $k")
            best = (J, base)
            for x in (base - h, base + h)
                p2 = copy(pv); p2[k] = x
                J2, _ = evaluate(p2)
                @printf("  it %d  %s = %.4f  J %.4f  (%d failed)%s\n", it, k, x, J2, NFAIL[], J2 < best[1] ? "  *" : ""); flush(stdout)
                J2 < best[1] && (best = (J2, x))
            end
            if best[2] != base
                pv[k] = best[2]; J = best[1]
                # keep going in the improving direction while it helps
                while true
                    p2 = copy(pv); p2[k] = pv[k] + (best[2] - base)
                    J2, _ = evaluate(p2)
                    @printf("  it %d  %s = %.4f  J %.4f  (%d failed)%s\n", it, k, p2[k], J2, NFAIL[], J2 < J ? "  *" : ""); flush(stdout)
                    J2 < J || break
                    pv = p2; J = J2
                end
            end
        end
        for k in keys(steps); steps[k] /= 2; end
        @printf("after iteration %d: %s  J %.4f\n", it, pv, J); flush(stdout)
    end
    J, rows = evaluate(pv); @printf("final %s  J %.4f\n", pv, J); report(rows)
end
main()
