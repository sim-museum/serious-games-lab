# ibt_provenance.jl — E91-S6.  WHICH .ibt FILES ARE THE iRACING REFERENCE, AND WHICH ARE OURS?
#
# julia racer WRITES its own telemetry in iRacing's .ibt format, with iRacing's filename
# convention ("lotus49_<track> <date>.ibt", drive_native_mtk.jl:9324), into
#     data/juliaracer/          (JM_IBT_DIR default)
# while the reference captures live in
#     /home/admin/gold standard/julia racer   (IBTDIR, drive_native_mtk.jl:513)
#
# Nothing in the FILENAME distinguishes the two, and a tool that points at the wrong directory
# compares the sim with itself while reporting a sim-vs-reference number.
#
# The discriminator is intrinsic and one-sided: JM fills ~30 channels (Speed, RPM, Gear, inputs,
# attitude, Alt); every other channel in the copied template stays 0.  Real iRacing captures carry
# a running car's housekeeping.  `Voltage` (12 V, constant) and `FuelLevel` are the cleanest:
# iRacing > 0 always, JM exactly 0 always.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/ibt_provenance.jl [dir ...]

using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT

const DIRS = isempty(ARGS) ? [joinpath(@__DIR__,"..","..","data","juliaracer"),
                              "/home/admin/gold standard/julia racer",
                              "/home/admin/gold standard/julia racer/260626telemetry",
                              joinpath(@__DIR__,"..","..","data","iracing")] : ARGS

ch(f,n) = try channel(f,n) catch; nothing end

"iRacing-written if any housekeeping channel the sim never fills is non-zero."
function classify(p)
    f = ibt_open(p)
    marks = Dict{String,Float64}()
    for nm in ("Voltage","FuelLevel","WaterTemp","OilTemp","FrameRate","AirTemp","Lat")
        v = ch(f,nm); v === nothing && continue
        marks[nm] = isempty(v) ? 0.0 : maximum(abs, v)
    end
    spd = ch(f,"Speed")
    iracing = any(v -> v > 0, values(marks))
    (; iracing, n = f.nrows, vmax = spd === nothing || isempty(spd) ? 0.0 : maximum(spd)*3.6, marks)
end

total = Dict{String,Tuple{Int,Int}}()
for d in DIRS
    isdir(d) || (println("\n(no such dir: ", d, ")"); continue)
    files = sort(filter(p -> endswith(lowercase(p), ".ibt"), readdir(d; join=true)))
    nir = njm = 0
    bad = String[]
    for p in files
        r = try classify(p) catch e; println("  ! ", basename(p), " : ", e); continue end
        r.iracing ? (nir += 1) : (njm += 1)
        r.iracing || push!(bad, @sprintf("%-58s n=%-6d vmax=%.0f", basename(p), r.n, r.vmax))
    end
    total[d] = (nir, njm)
    @printf("\n%s\n   %d .ibt:  %d iRacing-written, %d JULIA-RACER-written\n", d, length(files), nir, njm)
    if !isempty(bad) && length(bad) <= 6
        for b in bad; println("     sim: ", b); end
    elseif !isempty(bad)
        println("     sim: ", length(bad), " files (first 3)"); for b in bad[1:3]; println("       ", b); end
    end
end

println("\n── verdict ──")
for (d,(nir,njm)) in sort(collect(total))
    println(@sprintf("  %-70s %s", basename(rstrip(d,'/')),
        nir + njm == 0 ? "EMPTY" :
        njm == 0 ? "PURE REFERENCE ($nir iRacing)" :
        nir == 0 ? "PURE SIM OUTPUT ($njm own) — NOT a reference population" :
                   "MIXED ($nir iRacing / $njm own) — must be filtered before use"))
end
