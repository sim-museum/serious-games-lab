# IRGOLD-1 S3: the STEADY-STATE characteristics of the car against the gold, deterministically, through the car.
#
# Why (S2's retro): fitting through 245 transient windows was dominated by discrete events -- settle failures and spins
# that flip with a 1 % parameter change -- so the objective was noise at the scale of the steps. The steady state is
# smooth and it carries the balance, the limit and the cornering drag, which is where the windows show the car differs.
#
# Gold CELLS: every skidpad file of the 261010 session (each is its own session car: bars, fuel, setup), each direction,
# 0.1 g bands from 0.25 g up; quasi-steady samples only (yaw acceleration < 0.03 rad/s² and |dV/dt| < 0.25 m/s² over 1 s,
# clutch in, off the brakes, |β| < 8°, 4,000-8,800 rpm). Per cell (n ≥ 60 rows): the medians of speed, yaw rate, road
# steer angle, sideslip, axle slip angles and the cornering DRAG (drive force from the pedal and rpm through the sim's
# own engine tables, minus m·dV/dt, aero at the session's air density and rolling).
# SIM: the same file's car settled on the cell's speed and yaw rate in the cell's gear (irgold_replay's settle_vr!, free
# PI throttle), then the same quantities and the drag from the sim's pedal by the identical formula. A cell the sim
# cannot hold (settle failure) costs a fixed 25.
# Score: Σ √n · [ (Δsteer/0.25°)² + (Δβ/0.25°)² + (Δdrag/150 N)² ] / Σ √n  (+ the failures).
#
#   JM_FRONTHUBS=1 JM_MASS1=1 julia --project=. tools/irgold_steady.jl                  (score the start, per cell)
#   JM_ST_PARAMS="muf=..,mur=.." JM_ST_MODE=nm JM_ST_FREE="muf,mur,caf,car" JM_ST_ITERS=60   (Nelder-Mead on FREE)
#   JM_ST_FILES="15-24-06,16-19-11"    a subset of the skidpad files;  JM_FIT_WORKERS=7
using Distributed, Printf, Statistics
const NW = parse(Int, get(ENV, "JM_FIT_WORKERS", "7"))
nprocs() == 1 && addprocs(NW; exeflags = "--project=$(dirname(@__DIR__))", env = [k => v for (k, v) in ENV if startswith(k, "JM_")])

@everywhere begin
    include(joinpath($(@__DIR__), "irgold_replay.jl"))
    include(joinpath($(@__DIR__), "irgold_params.jl"))
    smooth(x, n) = (h = n ÷ 2; [mean(@view x[max(1, k-h):min(length(x), k+h)]) for k in eachindex(x)])
    "Drive force at the wheels [N] from pedal, rpm and the total ratio, through the sim's own engine tables."
    drive_force(thr, rpm, Gt) = DriveRT3D.engine_torque(rpm, thr)*Gt*0.9/DriveRT3D.RW_R
    function gold_cells(g, sp)
        c = g.c; n = g.n; m = sum(values(sp.corner_weight_N))/9.81; sr = sp.steering_ratio
        a, b = DriveRT3D.cg_arms()
        v = smooth(c["Speed"], 61); dv = [0.0; diff(v)] .* 60; r = c["YawRate"]; rd = abs.(smooth([0.0; diff(smooth(r, 15))] .* 60, 61))
        ay = smooth(c["LatAccel"], 31) ./ G; ρ = median(c["AirDensity"]); dvs = abs.(smooth(dv, 61))
        cells = Dict{Tuple{Int,Int},Vector{NamedTuple}}()
        for k in 61:n-61
            ontrack(c, k) && v[k] > 15 && c["Brake"][k] < 0.02 && c["Clutch"][k] > 0.98 || continue
            gr = round(Int, c["Gear"][k]); (2 <= gr <= 5) || continue
            (4000 < c["RPM"][k] < 8800) && 0.05 < c["Throttle"][k] < 0.95 || continue
            rd[k] < 0.05 && dvs[k] < 0.4 || continue
            β = β_of(c, k); abs(β) < 8 || continue
            abs(ay[k]) >= 0.25 || continue
            vx, vy = c["VelocityX"][k], c["VelocityY"][k]; δ = c["SteeringWheelAngle"][k]/sr
            Gt = sp.gear_ratios[gr]*sp.final_drive
            drag = drive_force(c["Throttle"][k], c["RPM"][k], Gt) - m*dv[k] - 0.5*ρ*DriveRT3D.CDA_IBT*v[k]^2 - DriveRT3D.CRR_IBT*m*G -
                   m*G*sin(atan(c["grade"][k]))                     # the Ring's grade (Monza and the skidpad are flat)
            key = (Int(sign(ay[k])), floor(Int, abs(ay[k])/0.1))
            push!(get!(cells, key, NamedTuple[]), (V = vx, R = r[k], vy, δ = rad2deg(δ), β, gr, drag, ay = ay[k], thr = c["Throttle"][k],
                  αf = rad2deg(δ - atan(vy + a*r[k], vx)), αr = rad2deg(-atan(vy - b*r[k], vx))))
        end
        out = NamedTuple[]
        for (key, S) in cells
            length(S) >= 40 || continue
            med(f) = median(getproperty(s, f) for s in S)
            gm = round(Int, median(s.gr for s in S))
            push!(out, (dir = key[1], band = key[2], n = length(S), V = med(:V), R = med(:R), vy = med(:vy), δ = med(:δ), β = med(:β),
                        drag = med(:drag), ay = med(:ay), αf = med(:αf), αr = med(:αr), gr = gm, thr = med(:thr)))
        end
        sort(out; by = x -> (x.dir, x.band))
    end
    const SJOBS = Any[]
    function load_steady!(files)
        for fn in files
            g = goldfile(fn); sp = install!(fn)
            C = gold_cells(g, sp); isempty(C) && continue
            car = DriveRT3D.build_car3d(; v0 = 30.0); u0 = copy(car.integ.u)
            push!(SJOBS, (car, sp, u0, g, C, testof(fn), match(r"(\d\d-\d\d-\d\d)\.ibt$", fn).captures[1]))
        end
        sum(length(j[5]) for j in SJOBS; init = 0)
    end
    function sim_cell(car, sp, u0, g, cl)
        length(sp.gear_ratios) == length(DriveRT3D.GEARS) && (DriveRT3D.GEARS .= sp.gear_ratios)
        setprel!(car, g.prel); ModelingToolkit.setp(car.sys, car.sys.ρair)(car.integ, median(g.c["AirDensity"]))
        # the gold's own pedal as the start, trimmed ±0.2 to hold the speed (a free PI loop overshot to full throttle at the
        # limit and spun the car before it settled)
        δ, ok = settle_vr!(car, sp, u0, cl.V, cl.R, cl.gr; δcap = 0.3, δg = deg2rad(cl.δ), vy = cl.vy, thrg = cl.thr)
        # a cell the sim cannot hold: how far short of the gold's yaw rate it stayed (continuous), or a spin
        q = LASTSETTLE[]
        ok || return (fail = true, short = abs(q.r - q.R)/max(abs(q.R), 1.0), spun = abs(q.β) > 10, r = q.r, Rg = q.R, δs = q.δ, βs = q.β, us = q.u, thr = q.thr)
        s = car.sys
        u, v, r, rpm = ModelingToolkit.getsym(s, [s.u, s.v, s.r, s.rpm])(car.integ)
        a = ModelingToolkit.getp(s, s.a)(car.integ); b = ModelingToolkit.getp(s, s.b)(car.integ)
        Gt = sp.gear_ratios[cl.gr]*sp.final_drive; m = sum(values(sp.corner_weight_N))/9.81; ρ = median(g.c["AirDensity"])
        drag = drive_force(LASTSETTLE[].thr, rpm, Gt) - 0.5*ρ*DriveRT3D.CDA_IBT*u^2 - DriveRT3D.CRR_IBT*m*G
        (fail = false, δ = rad2deg(δ), β = rad2deg(atan(v, u)), drag, αf = rad2deg(δ - atan(v + a*r, u)), αr = rad2deg(-atan(v - b*r, u)), thr = LASTSETTLE[].thr)
    end
    function eval_steady(pv)
        out = NamedTuple[]
        for (car, sp, u0, g, C, test, stem) in SJOBS
            setparams!(car, pv)
            for cl in C
                sm = try sim_cell(car, sp, u0, g, cl) catch; nothing end
                push!(out, (; test, stem, dir = cl.dir, band = cl.band, n = cl.n, gold = cl, sim = sm))
            end
        end
        out
    end
end

parsepv(s) = Dict(String(strip(split(x, "=")[1])) => parse(Float64, split(x, "=")[2]) for x in split(s, ","; keepempty = false))
function sscore(rows)
    e = 0.0; w = 0.0
    for r in rows
        ww = sqrt(r.n); w += ww
        if r.sim === nothing || r.sim.fail
            e += ww*(r.sim === nothing || r.sim.spun ? 25.0 : min(25.0, 5.0 + 200.0*r.sim.short)); continue
        end
        e += ww*(((r.sim.δ - r.gold.δ)/0.25)^2 + ((r.sim.β - r.gold.β)/0.25)^2 + ((r.sim.drag - r.gold.drag)/150)^2)
    end
    e/w
end
function evaluate_steady(pv)
    rows = reduce(vcat, pmap(w -> remotecall_fetch(eval_steady, w, pv), workers()))
    (sscore(rows), rows)
end
function report_steady(rows)
    println("    test           dir  g     n   | steer gold  sim   | β gold   sim   | αf gold sim | αr gold sim | drag gold   sim")
    for r in sort(rows; by = r -> (r.test, r.dir, r.band))
        gd = r.gold; s = (r.sim === nothing || r.sim.fail) ? nothing : r.sim
        if r.sim !== nothing && r.sim.fail
            f = r.sim
            @printf("    %-14s %+d  %.2f %4d | FAILED: gold %.0f km/h r %.1f °/s steer %.2f° β %.2f | sim r %.1f °/s at %.0f km/h steer %.2f° β %.1f° pedal %.2f%s\n",
                    r.test, r.dir, abs(gd.ay), r.n, 3.6gd.V, rad2deg(gd.R), gd.δ, gd.β, f.r, f.us, f.δs, f.βs, f.thr, f.spun ? "  SPUN" : "")
            continue
        end
        @printf("    %-14s %+d  %.2f %4d | %6.2f %s | %5.2f %s | %5.2f %s | %5.2f %s | %5.0f %s\n", r.test, r.dir, abs(gd.ay), r.n,
                gd.δ, s === nothing ? "  FAIL" : @sprintf("%6.2f", s.δ), gd.β, s === nothing ? "  -  " : @sprintf("%5.2f", s.β),
                gd.αf, s === nothing ? "  - " : @sprintf("%5.2f", s.αf), gd.αr, s === nothing ? "  - " : @sprintf("%5.2f", s.αr),
                gd.drag, s === nothing ? "   -" : @sprintf("%5.0f", s.drag))
    end
end

function main()
    # every 261010 file (the skidpad's oval pressures, Monza's and the Ring's road pressures) + the 261004/5 skidpads
    files = vcat(filter(f -> endswith(f, ".ibt"), readdir(DG; join = true)),
                 [f for d in ("261004", "261005") for f in readdir(expanduser("~/gold standard/julia racer/$d"); join = true) if occursin("skidpad", f) && endswith(f, ".ibt")])
    only = split(get(ENV, "JM_ST_FILES", ""), ","; keepempty = false)
    isempty(only) || (files = filter(f -> any(o -> occursin(o, f), only), files))
    files = sort(files; by = filesize, rev = true)
    ws = workers(); share = [String[] for _ in ws]
    for (i, f) in enumerate(files); push!(share[mod1(i, length(ws))], f); end
    ncell = sum(fetch.([remotecall(load_steady!, w, share[i]) for (i, w) in enumerate(ws)]))
    @printf("%d files, %d gold cells on %d workers\n", length(files), ncell, length(ws)); flush(stdout)
    pv = parsepv(get(ENV, "JM_ST_PARAMS", ""))
    S, rows = evaluate_steady(pv)
    @printf("start %s  score %.3f  (%d cells failed)\n", pv, S, count(r -> r.sim === nothing || r.sim.fail, rows)); flush(stdout)
    report_steady(rows); flush(stdout)
    if get(ENV, "JM_ST_MODE", "eval") == "grid"
        # JM_ST_GRID="name=val,...;name=val,...;..." -- each set is applied ON TOP of JM_ST_PARAMS
        sets = [parsepv(x) for x in split(get(ENV, "JM_ST_GRID", ""), ";"; keepempty = false)]
        # every parameter any row touches is reset to the car's own value before each row: setp is persistent, so a row
        # that does not name a parameter otherwise inherited the previous row's (two rows came out identical)
        touched = unique(vcat([collect(keys(x)) for x in sets]...))
        base = remotecall_fetch(names -> begin
                car = SJOBS[1][1]; out = Dict{String,Float64}()
                for k in names
                    w, sy = PARAM_MAP[k]
                    sub = w === :veh ? car.sys : w === :col ? car.sys.col : getproperty(car.sys, w[1])
                    out[k] = ModelingToolkit.getp(car.sys, getproperty(sub, sy))(car.integ)
                end
                out end, workers()[1], touched)
        println("grid base: ", base)
        for set in sets
            p2 = merge(base, pv, set); S2, rows2 = evaluate_steady(p2)
            fails = filter(r -> r.sim === nothing || r.sim.fail, rows2); ok = filter(r -> !(r.sim === nothing || r.sim.fail), rows2)
            hi = filter(r -> abs(r.gold.ay) >= 0.9, ok); lo = filter(r -> abs(r.gold.ay) < 0.9, ok)
            m(f, R) = isempty(R) ? NaN : mean(f(r) for r in R)
            @printf("GRID %-60s score %7.3f  fail %2d | <0.9 g: Δsteer %+.2f Δβ %+.2f Δαf %+.2f Δαr %+.2f Δdrag %+4.0f | ≥0.9 g: Δsteer %+.2f Δβ %+.2f Δαf %+.2f Δαr %+.2f Δdrag %+4.0f\n",
                    join(["$k=$v" for (k, v) in set], ","), S2, length(fails),
                    m(r -> (r.sim.δ - r.gold.δ)*r.dir, lo), m(r -> (r.sim.β - r.gold.β)*r.dir, lo), m(r -> (r.sim.αf - r.gold.αf)*r.dir, lo), m(r -> (r.sim.αr - r.gold.αr)*r.dir, lo), m(r -> r.sim.drag - r.gold.drag, lo),
                    m(r -> (r.sim.δ - r.gold.δ)*r.dir, hi), m(r -> (r.sim.β - r.gold.β)*r.dir, hi), m(r -> (r.sim.αf - r.gold.αf)*r.dir, hi), m(r -> (r.sim.αr - r.gold.αr)*r.dir, hi), m(r -> r.sim.drag - r.gold.drag, hi))
            flush(stdout)
        end
        return
    end
    get(ENV, "JM_ST_MODE", "eval") == "nm" || return
    free = split(get(ENV, "JM_ST_FREE", ""), ","; keepempty = false)
    x0 = [pv[k] for k in free]; h = [parse(Float64, get(ENV, "JM_ST_STEP", "0.05"))*abs(x) + 1e-3 for x in x0]
    f(x) = (p2 = copy(pv); for (k, xi) in zip(free, x); p2[k] = xi; end; s = evaluate_steady(p2)[1]; @printf("  %s  score %.4f\n", join([@sprintf("%s=%.4f", k, xi) for (k, xi) in zip(free, x)], " "), s); flush(stdout); s)
    # Nelder-Mead (plain, bounded by the caller's sense of the parameters)
    n = length(x0); P = [copy(x0)]; for i in 1:n; xi = copy(x0); xi[i] += h[i]; push!(P, xi); end
    F = [f(p) for p in P]
    for it in 1:parse(Int, get(ENV, "JM_ST_ITERS", "60"))
        o = sortperm(F); P = P[o]; F = F[o]
        c = sum(P[1:n])/n; xr = c .+ (c .- P[end]); fr = f(xr)
        if fr < F[1]
            xe = c .+ 2 .* (c .- P[end]); fe = f(xe)
            (P[end], F[end]) = fe < fr ? (xe, fe) : (xr, fr)
        elseif fr < F[n]
            P[end] = xr; F[end] = fr
        else
            xc = c .+ 0.5 .* (P[end] .- c); fc = f(xc)
            if fc < F[end]; P[end] = xc; F[end] = fc
            else
                for i in 2:n+1; P[i] = P[1] .+ 0.5 .* (P[i] .- P[1]); F[i] = f(P[i]); end
            end
        end
        @printf("iter %d best %.4f  %s\n", it, minimum(F), join([@sprintf("%s=%.4f", k, xi) for (k, xi) in zip(free, P[argmin(F)])], " ")); flush(stdout)
    end
    best = P[argmin(F)]; for (k, xi) in zip(free, best); pv[k] = xi; end
    S, rows = evaluate_steady(pv); @printf("final %s  score %.3f\n", pv, S); report_steady(rows)
end
main()
