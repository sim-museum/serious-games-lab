# AI-YAW (PO 2026-09-05): is the AI's DRAWN heading continuous in time?
# pose_at() reads theta off the line's per-node tangent, so heading should be piecewise-linear in
# node index and its RATE a step function jumping at every node. Measure it directly.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Statistics, Printf
wrapp(a) = atan(sin(a), cos(a))
for name in ["watglen","rouen","monza"]
    T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/"*name
    isdir(T) || (println("no track $name"); continue)
    dat = first(filter(f -> lowercase(basename(f)) == lowercase(name)*".dat", joinpath.(T, readdir(T))))
    d = GPLDat.parse_dat(dat)
    key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
    tmp = tempname()*".trk"; write(tmp, d[key])
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
    dt = 1/60; v = 45.0
    s = 0.0; prev = nothing; prevrate = nothing; jumps = Float64[]; rates = Float64[]
    while s < line.total
        th = RaceAI.pose_at(line, s, 0.0)[4]
        if prev !== nothing
            r = wrapp(th - prev)/dt
            push!(rates, r)
            prevrate !== nothing && push!(jumps, abs(r - prevrate))
            prevrate = r
        end
        prev = th; s += v*dt
    end
    sort!(jumps); n = length(jumps)
    @printf("%-8s frames=%5d  |yaw rate| max=%.2f rad/s   yaw-rate JUMP: median=%.3f p95=%.3f MAX=%.3f rad/s\n",
            name, n, maximum(abs.(rates)), jumps[max(1,n÷2)], jumps[max(1,round(Int,0.95n))], jumps[end])
    @printf("%-8s frames whose yaw-rate jumps >1.0 rad/s: %d (%.2f%%)   >3.0: %d\n",
            name, count(>(1.0), jumps), 100count(>(1.0), jumps)/n, count(>(3.0), jumps))
end
