# AIW track waypoint files (Phase 4: track layer).
#
# An AIW carries everything rF1 knows about a track's logical layout:
# the waypoint chain (positions, lateral frame, widths, per-waypoint AI
# speeds, sector/lap distance), the starting grid, pit/garage spots.
# Flat ISI text: [Waypoint] holds repeated wp_* keys, one record per
# wp_pos; [GRID] holds GridIndex/Pos/Ori triplets.

struct AIWWaypoint
    pos::Vector{Float64}       # world position (ISI frame: +x left, +y up, +z rearward)
    perp::Vector{Float64}      # lateral unit vector
    normal::Vector{Float64}
    width::Vector{Float64}     # track half-widths (left, right, far left, far right)
    groove_lat::Float64        # racing-line offset from pos along perp (wp_path[1])
    speed::Float64             # AI target speed (wp_test_speed, m/s)
    sector::Int
    lapdist::Float64           # distance into lap (wp_score[2])
    branch::Int                # 0 = main path, ≥1 = pit lanes
end

struct AIWFile
    path::String
    lap_length::Float64
    sector_lengths::Tuple{Float64,Float64}
    waypoints::Vector{AIWWaypoint}
    grid::Vector{NamedTuple{(:pos, :ori),Tuple{Vector{Float64},Vector{Float64}}}}
    raw::ISIFile
end

Base.show(io::IO, a::AIWFile) =
    print(io, "AIWFile(\"", basename(a.path), "\", ",
          length(a.waypoints), " waypoints, lap ",
          round(a.lap_length; digits=1), " m, ", length(a.grid), " grid spots)")

vec3f(v) = v isa Vector ? Float64[Float64(x) for x in v if x isa Number] :
           v isa Number ? Float64[Float64(v)] : Float64[]

"""
    read_aiw(path) -> AIWFile
"""
function read_aiw(path::AbstractString)
    raw = parse_isi(readtext(path); path)
    wsec = section(raw, "Waypoint")
    wps = AIWWaypoint[]
    if wsec !== nothing
        cur = Dict{String,Any}()
        flush!() = if haskey(cur, "wp_pos")
            score = vec3f(get(cur, "wp_score", [0, 0]))
            pathv = vec3f(get(cur, "wp_path", [0.0]))
            push!(wps, AIWWaypoint(
                vec3f(cur["wp_pos"]),
                vec3f(get(cur, "wp_perp", Float64[])),
                vec3f(get(cur, "wp_normal", Float64[])),
                vec3f(get(cur, "wp_width", Float64[])),
                isempty(pathv) ? 0.0 : pathv[1],
                Float64(get(cur, "wp_test_speed", 0.0)),
                length(score) >= 1 ? Int(score[1]) : 0,
                length(score) >= 2 ? score[2] : 0.0,
                Int(something(get(cur, "wp_branchID", 0), 0))))
        end
        for e in wsec.entries
            if isequal_ci(e.key, "wp_pos")
                flush!()
                cur = Dict{String,Any}()
            end
            cur[e.key] = e.value
        end
        flush!()
    end

    grid = NamedTuple{(:pos, :ori),Tuple{Vector{Float64},Vector{Float64}}}[]
    gsec = section(raw, "GRID")
    if gsec !== nothing
        pos = nothing
        for e in gsec.entries
            if isequal_ci(e.key, "Pos")
                pos = vec3f(e.value)
            elseif isequal_ci(e.key, "Ori") && pos !== nothing
                push!(grid, (pos=pos, ori=vec3f(e.value)))
                pos = nothing
            end
        end
    end

    lap = 0.0; s1 = 0.0; s2 = 0.0
    if wsec !== nothing
        lap = Float64(get(wsec, "lap_length", 0.0))
        s1 = Float64(get(wsec, "sector_1_length", 0.0))
        s2 = Float64(get(wsec, "sector_2_length", 0.0))
    end
    AIWFile(String(path), lap, (s1, s2), wps, grid, raw)
end

"""Main-path waypoints (branch 0), ordered by lap distance."""
mainpath(a::AIWFile) =
    sort([w for w in a.waypoints if w.branch == 0]; by=w -> w.lapdist)

"""All `*.aiw` files under `root` (case-insensitive), sorted."""
find_aiw_files(root::AbstractString=joinpath(default_gamedata(), "Locations")) =
    find_ext(root, ".aiw")

"""
    read_gdb(path) -> GENFile

GDB track/event files use the GEN brace-block syntax.
"""
read_gdb(path::AbstractString) = parse_gen(readtext(path); path)
