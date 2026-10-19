# IRPLAN-3 ingest: one line per iRacing .ibt -- track, setup name, the knobs that differ between the plan's tests, and
# the driving signature that tells which test it is (skidpad direction, steady circles, straight-line speeds, trail
# braking at speed).  Writes a CSV next to the printout.
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/irsession_catalog_261018.jl <dir with .ibt> [out.csv]
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics

yamlget(y, key) = (m = match(Regex("\\n\\s*" * key * ":\\s*([^\\n]*)"), y); m === nothing ? "" : strip(m.captures[1]))
function section(y, name)            # the text of the first block `name:` up to the next line at its indent or less
    i = findfirst(Regex("\\n(\\s*)" * name * ":\\s*\\n"), y); i === nothing && return ""
    m = match(Regex("\\n(\\s*)" * name * ":\\s*\\n"), y); ind = length(m.captures[1])
    rest = y[last(i)+1:end]; out = IOBuffer()
    for ln in split(rest, '\n')
        isempty(strip(ln)) && continue
        length(ln) - length(lstrip(ln)) <= ind && break
        println(out, ln)
    end
    String(take!(out))
end

dir = ARGS[1]
files = sort(filter(f -> endswith(f, ".ibt"), readdir(dir)))
rows = String[]
push!(rows, "file,track,setup,dur_s,vmax_kph,laps,dir,steady_s,ay_p99_g,fspring,farb,rarb,ramp,trailbrake_s,coast_s")
for fn in files
    f = IBT.ibt_open(joinpath(dir, fn)); y = IBT.session_yaml(f)
    trk = yamlget(y, "TrackName"); setup = yamlget(y, "DriverSetupName")
    fr = section(y, "Front"); lf = section(y, "LeftFront"); rr = section(y, "Rear"); dif = section(y, "Differential")
    fspring = yamlget("\n" * section(section(y, "Chassis"), "LeftFront"), "SpringRate")
    ch = "\n" * section(y, "Chassis")
    farb = yamlget("\n" * section(ch, "Front"), "ArbDiameter") * "/" * yamlget("\n" * section(ch, "Front"), "ArbArms")
    rarb = yamlget("\n" * section(ch, "Rear"), "ArbDiameter") * "/" * yamlget("\n" * section(ch, "Rear"), "ArbArms")
    ramp = yamlget("\n" * section(y, "Differential"), "DriveRampAngle")
    v = IBT.channel(f, "Speed") .* 3.6; ay = IBT.channel(f, "LatAccel") ./ 9.80665
    yr = IBT.channel(f, "YawRate"); br = IBT.channel(f, "Brake"); th = IBT.channel(f, "Throttle")
    st = IBT.channel(f, "SteeringWheelAngle"); lap = IBT.channel(f, "Lap")
    n = length(v); dt = 1 / 60
    mov = v .> 20
    dirn = mov .& (abs.(ay) .> 0.3)
    nl = count(dirn .& (yr .> 0)); nr = count(dirn .& (yr .< 0))
    d = nl + nr == 0 ? "-" : (nl > 3nr ? "L" : nr > 3nl ? "R" : "LR")
    # steady circle: |ay| > 0.5 g held within +-0.05 g over 2 s windows
    steady = 0
    w = 120
    for i in 1:w:n-w
        seg = ay[i:i+w-1]
        (mean(abs.(seg)) > 0.5 && std(seg) < 0.05 && all(mov[i:i+w-1])) && (steady += w)
    end
    tb = count((v .> 200) .& (br .> 0.2) .& (abs.(st) .> 0.03)) * dt
    coast = count((v .> 100) .& (th .< 0.02) .& (br .< 0.02)) * dt
    r = @sprintf("%s,%s,%s,%.0f,%.0f,%d,%s,%.0f,%.2f,%s,%s,%s,%s,%.1f,%.0f", fn, trk, setup, n * dt, maximum(v),
                 maximum(lap) - minimum(lap), d, steady * dt, (any(mov) ? quantile(abs.(ay[mov]), 0.99) : 0.0), fspring, farb, rarb, ramp, tb, coast)
    push!(rows, r); println(r)
end
length(ARGS) > 1 && write(ARGS[2], join(rows, "\n") * "\n")
