# TRACKSEG-1: where GPL's own trackside SECTION SIGNS stand, as lap distance on the sim's ribbon.
#   julia --project=../demo/native tools/section_signs.jl nurburg si_
# TRACKSEG-5: the Ring's add-on section boards (TS_*, "Traffic-signs" add-on, installed in the PO's GPL) beside
# Papyrus's own s_* boards; a third argument also writes the ribbon (s, x, z, y per point) as CSV for
# tools/bapom_names.py, which places the names of the track's BAPOM map:
#   JM_GPL_TRACKS=~/sgl/THU/WP/drive_c/Sierra/GPL/tracks julia --project=../demo/native tools/section_signs.jl nurburg '^(ts_|s_)' rib.csv
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS",
              normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl"));   using .GPLDat
include(joinpath(D, "gpl3do.jl"))
# roadcurve.jl is written as a submodule of the renderer (`using ..Render.GPL3DO`); the renderer itself
# needs a GL context, so bind the loader under that name instead of pulling OpenGL into a gate.
module Render
    const GPL3DO = Main.GPL3DO
end
include(joinpath(D, "roadcurve.jl")); using .RoadCurve
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
using JuliaMotor, Statistics, Printf

pct(v, p) = isempty(v) ? NaN : (u = sort(copy(v)); u[clamp(ceil(Int, p*length(u)), 1, length(u))])

function load_track(name)
    dir = joinpath(G, name)
    ci(n) = (m = filter(f -> lowercase(f) == lowercase(n), readdir(dir)); isempty(m) ? "" : joinpath(dir, m[1]))
    dat = (p = ci(name*".dat"); p == "" ? Dict{String,Vector{UInt8}}() : GPLDat.parse_dat(p))
    function getf(ext)
        p = ci(name*ext); p != "" && return p
        v = get(dat, lowercase(name*ext), nothing); v === nothing && return ""
        q = tempname()*ext; write(q, v); q
    end
    (trk = getf(".trk"), mesh = getf(".3do"))
end

function main(name, pat, ribcsv = "")
    f = load_track(name)
    mesh = GPL3DO.parse_3do(f.mesh); hat = GPLTrack.build_hat(mesh)
    cl = GPLTrack.align_centreline(GPLTrack.trk_centreline(f.trk), hat)
    rib = GPLTrack.build_surface(cl, hat)
    isempty(ribcsv) || open(ribcsv, "w") do io
        for i in eachindex(rib.pos); println(io, rib.lapdist[i], ",", rib.pos[i][1], ",", rib.pos[i][3], ",", rib.pos[i][2]); end
    end
    dir = joinpath(G, name)
    re = Regex(pat, "i")
    nm = Set(lowercase(replace(x, r"\.3do$"i => "")) for x in readdir(dir) if occursin(re, x) && endswith(lowercase(x), ".3do"))
    for fn in readdir(dir)                                     # ...and the objects packed in the track's .dat
        endswith(lowercase(fn), ".dat") || continue
        for k in keys(GPLDat.parse_dat(joinpath(dir, fn)))
            endswith(k, ".3do") && occursin(re, k) && push!(nm, replace(k, ".3do" => ""))
        end
    end
    ins = GPLTrack.trackside_objects(f.mesh; objnames = nm)
    println(name, ": lap ", round(rib.lapdist[end], digits=1), " m, ", length(ins), " placements of ", length(nm), " names")
    rows = []
    for o in ins
        best = (Inf, 0)
        for i in eachindex(rib.pos)
            d = (rib.pos[i][1]-o.x)^2 + (rib.pos[i][3]-o.y)^2
            d < best[1] && (best = (d, i))
        end
        i = best[2]; p = rib.pos[i]; q = rib.perp[i]
        lat = (o.x-p[1])*q[1] + (o.y-p[3])*q[3]
        push!(rows, (rib.lapdist[i], o.name, lat, sqrt(best[1])))
    end
    for r in sort(rows); @printf("  s %7.1f  %-10s lat %+6.1f  dist %5.1f\n", r...); end
end
main(ARGS[1], ARGS[2], get(ARGS, 3, ""))
