# coastdown_probe.jl — E91-S2. Derive ENGINE BRAKING from the iRacing .ibt directly.
#
# WHY
#   ENGBRAKE = 0.012 in powertrain.jl is an INVENTED constant. The PO's standing constraint is
#   "the car physics should be determined entirely by the iracing ibt data, there should be no
#   modifiable parameters", so the value must come from the reference. E91-S1 showed the earlier
#   defence of 0.012 subtracted clutch-in baselines measured at 130/96 km/h from clutch-out totals
#   at 161/126 km/h -- and aero goes as v^2, so those baselines are not valid at the test speeds.
#   This reads the coast-downs out of the telemetry instead of reusing four hand-copied numbers.
#
# METHOD
#   1. Find segments with throttle==0 AND brake==0 (a genuine coast), lasting >= MINLEN seconds.
#   2. Split by CLUTCH: clutch pressed => no engine braking => that segment measures aero+rolling.
#      clutch released, in gear   => aero + rolling + engine.
#   3. Fit the clutch-IN segments to  a = A*v^2 + R  over the FULL speed range (least squares,
#      many points), not two hand-picked points.
#   4. For each clutch-OUT segment, engine share = measured decel - (A*v^2 + R) at that speed,
#      then eb = a_eng*Rw*m/(rpm*gear*final*eta) from the model's own T_eng = eb*rpm.
#   5. Report the SCATTER, not just a mean. If eb is not roughly constant across speed and gear,
#      the model FORM is wrong and no single constant is defensible.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/coastdown_probe.jl [dir-with-ibt]

using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT

const GEARS = [2.23, 1.72, 1.32, 1.09, 0.916]
const FINAL = 4.11
const RW_R  = 0.33
const M     = 617.0
const ETA   = 0.9
const MINLEN = 1.0          # seconds of continuous coast
const G      = 9.80665

ch(f, name) = try channel(f, name) catch; nothing end

function first_present(f, names)
    for n in names
        v = ch(f, n)
        v === nothing || return (n, v)
    end
    (nothing, nothing)
end

function analyse(path)
    f = try ibt_open(path) catch e; @printf("  %-52s SKIP (%s)\n", basename(path), e); return nothing end
    nthr, thr = first_present(f, ["Throttle"])
    nbrk, brk = first_present(f, ["Brake"])
    nspd, spd = first_present(f, ["Speed"])
    ncl , cl  = first_present(f, ["Clutch"])
    ngr , gr  = first_present(f, ["Gear"])
    nrpm, rpm = first_present(f, ["RPM"])
    # E91-S2b: measured LongAccel beats differentiating Speed (no numerical noise), and the
    # straight-line filters below are what make a ROAD-COURSE lap usable at all: the first pass
    # accepted any throttle=0 brake=0 sample, so cornering, kerbs and elevation entered the fit and
    # the baseline residual came out 5.619 m/s^2 -- LARGER than the 1-3 m/s^2 effect. A fit whose
    # residual exceeds its signal is not a measurement.
    _, lat  = first_present(f, ["LatAccel"])
    _, lng  = first_present(f, ["LongAccel"])
    _, stw  = first_present(f, ["SteeringWheelAngle"])
    _, yaw  = first_present(f, ["YawRate"])
    _, alt  = first_present(f, ["Alt"])
    if any(isnothing, (thr, brk, spd, gr, rpm))
        @printf("  %-52s SKIP: missing channels (thr=%s brk=%s spd=%s gear=%s rpm=%s)\n",
                basename(path), nthr, nbrk, nspd, ngr, nrpm); return nothing
    end
    n = min(length(thr), length(brk), length(spd), length(gr), length(rpm))
    dt = 1/60
    tick = ch(f, "SessionTime")
    if tick !== nothing && length(tick) > 1
        d = median(diff(tick[1:min(end,2000)])); d > 0 && (dt = d)
    end
    coasting = falses(n)
    for i in 1:n
        ok = thr[i] <= 0.01 && brk[i] <= 0.01 && spd[i] > 8.0
        ok &= lat === nothing || abs(lat[i]) < 2.0            # not cornering
        ok &= stw === nothing || abs(stw[i]) < 0.10           # wheel essentially straight (rad)
        ok &= yaw === nothing || abs(yaw[i]) < 0.05           # not rotating
        coasting[i] = ok
    end
    segs = Tuple{Int,Int}[]
    i = 1
    while i <= n
        if coasting[i]
            j = i; while j < n && coasting[j+1]; j += 1; end
            (j - i) * dt >= MINLEN && push!(segs, (i, j))
            i = j + 1
        else
            i += 1
        end
    end
    isempty(segs) && (@printf("  %-52s no coast segments\n", basename(path)); return nothing)
    inpts  = Tuple{Float64,Float64}[]                    # (v, decel) clutch IN
    outpts = Tuple{Float64,Float64,Float64,Int}[]        # (v, decel, rpm, gear) clutch OUT
    for (a,b) in segs
        for k in (a+3):(b-4)
            v0 = spd[k]
            # E91-S3: GRAVITY. On a slope, m*dv/dt = -F_drag - m*g*sin(theta), so the DRAG
            # deceleration is  -dv/dt - g*sin(theta), and sin(theta) = (dAlt/dt)/v. Zandvoort has
            # real elevation, and S2 left this term in -- a plausible source of the residual
            # scatter that made eb look inconsistent. Use dv/dt (rate of change of ground speed),
            # NOT the LongAccel accelerometer, because the accelerometer itself carries the gravity
            # component we are trying to remove. Central difference over +/-3 samples for noise.
            dvdt = (spd[k+3] - spd[k-3]) / (6*dt)
            dec  = -dvdt
            if alt !== nothing && v0 > 1.0
                dadt = (alt[k+3] - alt[k-3]) / (6*dt)
                dec -= G * (dadt / v0)          # remove the slope term
            end
            (dec <= 0 || dec > 15.0) && continue
            clutch_in = cl !== nothing && cl[k] > 0.5          # 1 = pedal down (disengaged)
            g = Int(round(gr[k]))
            if clutch_in
                push!(inpts, (v0, dec))
            elseif 1 <= g <= length(GEARS)
                push!(outpts, (v0, dec, rpm[k], g))
            end
        end
    end
    (basename(path), inpts, outpts)
end

dir = length(ARGS) >= 1 ? ARGS[1] : joinpath(@__DIR__, "..", "..", "data", "juliaracer")
files = sort(filter(p -> endswith(p, ".ibt"), readdir(dir; join=true)))
@printf("coastdown_probe: %d .ibt files in %s\n\n", length(files), dir)

allin  = Tuple{Float64,Float64}[]
allout = Tuple{Float64,Float64,Float64,Int}[]
for p in files
    r = analyse(p)
    r === nothing && continue
    nm, ip, op = r
    @printf("  %-52s clutch-IN pts %6d   clutch-OUT pts %6d\n", nm, length(ip), length(op))
    append!(allin, ip); append!(allout, op)
end

println()
if length(allin) < 50
    @printf("INCONCLUSIVE: only %d clutch-in coast points. Without them the aero+rolling baseline\n", length(allin))
    @printf("cannot be separated from engine braking, and eb is not derivable. Need clutch-in coasts.\n")
    exit(2)
end
# least squares  dec = A*v^2 + R
X = [ [p[1]^2 for p in allin] ones(length(allin)) ]
y = [ p[2] for p in allin ]
coef = X \ y
A, R = coef[1], coef[2]
resid = y .- (X*coef)
@printf("clutch-IN baseline fit over %d points (full speed range):\n", length(allin))
@printf("  a = %.6g * v^2 + %.4f      (rolling %.4f g)   residual sd %.3f m/s^2\n", A, R, R/G, std(resid))
@printf("  speed range %.0f..%.0f km/h\n\n", minimum(p[1] for p in allin)*3.6, maximum(p[1] for p in allin)*3.6)

if isempty(allout)
    println("INCONCLUSIVE: no clutch-out coast points -> engine braking not observable here.")
    exit(2)
end
ebs = Float64[]
bygear = Dict{Int,Vector{Float64}}()
for (v, dec, r, g) in allout
    base = A*v^2 + R
    aeng = dec - base
    aeng <= 0 && continue
    r <= 100 && continue
    eb = aeng * RW_R * M / (r * GEARS[g] * FINAL * ETA)
    push!(ebs, eb); push!(get!(bygear, g, Float64[]), eb)
end
if length(ebs) < 20
    @printf("INCONCLUSIVE: only %d usable clutch-out points after baseline subtraction.\n", length(ebs)); exit(2)
end
# E91-S3: does a TWO-TERM engine model fit where eb*rpm did not?  T_eng = T0 + eb*rpm
let
    rows = Tuple{Float64,Float64}[]      # (rpm, T_eng)
    for (v, dec, r, g) in allout
        aeng = dec - (A*v^2 + R)
        (aeng <= 0 || r <= 100) && continue
        T = aeng * RW_R * M / (GEARS[g] * FINAL * ETA)
        push!(rows, (r, T))
    end
    if length(rows) >= 20
        X2 = [ ones(length(rows))  [x[1] for x in rows] ]
        y2 = [ x[2] for x in rows ]
        c2 = X2 \ y2
        r2 = y2 .- X2*c2
        ss = 1 - sum(r2.^2)/sum((y2 .- mean(y2)).^2)
        @printf("two-term engine fit  T_eng = %.3f + %.6f * rpm   (R^2 = %.3f, n=%d)\n",
                c2[1], c2[2], ss, length(rows))
        # one-term for comparison: T = eb*rpm through the origin
        eb1 = sum([x[1]*x[2] for x in rows]) / sum([x[1]^2 for x in rows])
        r1 = y2 .- eb1 .* [x[1] for x in rows]
        ss1 = 1 - sum(r1.^2)/sum((y2 .- mean(y2)).^2)
        @printf("one-term (code form) T_eng = %.6f * rpm            (R^2 = %.3f)\n\n", eb1, ss1)
    end
end
@printf("engine-braking constant implied by the telemetry (%d points):\n", length(ebs))
@printf("  median %.5f   mean %.5f   sd %.5f   IQR %.5f..%.5f\n",
        median(ebs), mean(ebs), std(ebs), quantile(ebs,0.25), quantile(ebs,0.75))
for g in sort(collect(keys(bygear)))
    v = bygear[g]
    @printf("    gear %d: n=%-6d median %.5f\n", g, length(v), median(v))
end
spread = quantile(ebs,0.75)/max(quantile(ebs,0.25), 1e-9)
@printf("\n  code ENGBRAKE = 0.01200  ->  %.0f%% of the telemetry median\n", 100*0.012/median(ebs))
@printf("  IQR spread %.2fx -- %s\n", spread,
        spread > 1.5 ? "eb*rpm does NOT fit: the model FORM is wrong, no single constant is defensible" :
                       "roughly constant, so a single eb is defensible")
