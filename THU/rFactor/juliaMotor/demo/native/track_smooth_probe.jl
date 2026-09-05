# AI-YAW / TRACKSMOOTH (PO 2026-09-05): "GPL tracks are smooth while julia tracks are piecewise
# linear. Is that why rail-follower AI cars have discontinuous yaw?"
# Measure the CENTRELINE ITSELF: node spacing, and the turn angle between consecutive segments.
# A polyline's heading is constant along a segment and STEPS at each node -- so the step size IS
# the yaw discontinuity the AI inherits, and node spacing sets how often it happens.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Statistics, Printf
wrapp(a) = atan(sin(a), cos(a))
for name in ["watglen","rouen","monza"]
    T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/"*name
    isdir(T) || continue
    dat = first(filter(f -> lowercase(basename(f)) == lowercase(name)*".dat", joinpath.(T, readdir(T))))
    d = GPLDat.parse_dat(dat); key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
    tmp = tempname()*".trk"; write(tmp, d[key])
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
    n = length(line.x)
    seg = [hypot(line.x[i%n+1]-line.x[i], line.z[i%n+1]-line.z[i]) for i in 1:n]
    turn = [abs(wrapp(line.θ[i%n+1]-line.θ[i])) for i in 1:n]      # heading STEP at each node
    st = sort(seg); tn = sort(turn)
    @printf("%-8s nodes=%5d  segment m: med=%5.1f p95=%6.1f max=%6.1f   turn-per-node deg: med=%5.2f p95=%6.2f MAX=%6.2f\n",
            name, n, st[n÷2], st[max(1,round(Int,0.95n))], st[end],
            rad2deg(tn[n÷2]), rad2deg(tn[max(1,round(Int,0.95n))]), rad2deg(tn[end]))
    # at 45 m/s, a node crossing turns the car by `turn` in ONE frame -> implied yaw rate
    implied = [t*60 for t in turn]   # rad per 1/60 s frame if the step lands in one frame
    si = sort(implied)
    @printf("%-8s implied yaw-rate STEP at a node (rad/s): med=%5.2f p95=%6.2f MAX=%6.2f   nodes>1rad/s: %d (%.1f%%)\n",
            name, si[n÷2], si[max(1,round(Int,0.95n))], si[end], count(>(1.0), implied), 100count(>(1.0), implied)/n)
end
