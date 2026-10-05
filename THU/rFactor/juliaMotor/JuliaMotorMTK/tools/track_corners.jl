# TRACKSEG-1: the corners of a GPL track, from its .trk arcs -- each section is a constant-curvature arc
# (length, start heading), so consecutive sections turning the same way at R < RMAX are one corner.
# Prints s_start..s_end [m], total turn [deg], tightest radius [m] and direction (L/R as driven; the sign
# is calibrated on known corners: Ring Karussell = L, Watkins carousel = R, Zandvoort Tarzan = R).
#   julia --project=../demo/native tools/track_corners.jl watglen [RMAX=600]
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
include(joinpath(D, "gpldat.jl")); using .GPLDat
using Printf
function trkbytes(name)
    dir = joinpath(G, name)
    for f in readdir(dir); lowercase(f) == name*".trk" && return read(joinpath(dir, f)); end
    for f in readdir(dir)
        endswith(lowercase(f), ".dat") || continue
        d = GPLDat.parse_dat(joinpath(dir, f)); haskey(d, name*".trk") && return d[name*".trk"]
    end
    error("no .trk for $name")
end
function corners(name; rmax = 600.0, sgn = parse(Float64, get(ENV, "JM_TURNSIGN", "1")))
    b = trkbytes(name)
    u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o)); TRK = 19685.03937
    traces = Int(u32(12)); nsec = Int(u32(16)); wallsize = Int(u32(20))
    secbase = 28 + 64 + nsec*4 + 32*traces*nsec + wallsize
    ang(s) = i32(secbase + s*52 + 12) * 2pi / 2.0^32
    wrap(d) = d > pi ? d-2pi : d < -pi ? d+2pi : d
    S = 0.0; secs = NTuple{4,Float64}[]
    for s in 0:nsec-1
        L = i32(secbase + s*52 + 8)/TRK; dth = sgn*wrap(ang(mod(s+1, nsec)) - ang(s))
        push!(secs, (S, L, dth, abs(dth) > 1e-6 ? L/abs(dth) : Inf)); S += L
    end
    @printf("%s: %d sections, lap %.1f m\n", name, nsec, S)
    cur = nothing; out = []
    flush!() = (cur !== nothing && abs(cur[3]) > deg2rad(12) && push!(out, cur); cur = nothing)
    for (s0, L, dth, R) in secs
        if R < rmax
            d = sign(dth)
            if cur !== nothing && sign(cur[3]) == d && s0 - cur[2] < 40
                cur = (cur[1], s0 + L, cur[3] + dth, min(cur[4], R))
            else
                flush!(); cur = (s0, s0 + L, dth, R)
            end
        else
            cur !== nothing && s0 - cur[2] > 40 && flush!()
        end
    end
    flush!()
    for c in out
        @printf("  s %7.0f .. %7.0f  (%5.0f m)  %s %4.0f deg  Rmin %5.0f m\n", c[1], c[2], c[2]-c[1], c[3] > 0 ? "L" : "R", rad2deg(abs(c[3])), c[4])
    end
end
corners(ARGS[1]; rmax = length(ARGS) > 1 ? parse(Float64, ARGS[2]) : 600.0)
