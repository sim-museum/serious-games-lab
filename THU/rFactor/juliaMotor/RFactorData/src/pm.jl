# PM physical-model (suspension multibody) files.
#
# A PM is a sequence of repeated sections describing a multibody graph:
#   [BODY]        name=fl_wheel mass=(12.5) inertia=(1.25,0.7,0.7)
#                 pos=(0.735,0,-1.40) ori=(0.0,0.0,0.0)
#   [JOINT&HINGE] posbody=fl_wheel negbody=fl_spindle pos=fl_wheel axis=(-1,0,0)
#   [JOINT]       (rare: one file in the corpus)
#   [BAR]         name=... posbody=body negbody=fl_spindle pos=(...) neg=(...)
#
# Several pairs per line is the normal syntax (handled by `split_pairs`);
# keys appear in mixed case (`Name=`, `Posbody=`).  Positions are either a
# 3-vector or the name of a body whose position is referenced (`pos=fl_wheel`).

"""A `pos=` / `neg=` / `axis=` attachment: either explicit coordinates or a
reference to a named body's position."""
const PMPoint = Union{Vector{Float64},String}

struct PMBody
    name::String
    mass::Float64
    inertia::Vector{Float64}
    pos::Vector{Float64}
    ori::Vector{Float64}
end

"""A `[JOINT&HINGE]` (kind == :joint_hinge) or `[JOINT]` (kind == :joint)
constraint between `posbody` and `negbody`."""
struct PMJoint
    kind::Symbol
    posbody::String
    negbody::String
    pos::PMPoint
    axis::Union{PMPoint,Nothing}   # JOINT has no axis
end

"""A `[BAR]` rigid link from `pos` (on `posbody`) to `neg` (on `negbody`)."""
struct PMBar
    name::String                   # often unnamed -> ""
    posbody::String
    negbody::String
    pos::PMPoint
    neg::PMPoint
end

struct PMFile
    path::String
    bodies::Vector{PMBody}
    joints::Vector{PMJoint}
    bars::Vector{PMBar}
    raw::ISIFile
end

issues(p::PMFile) = p.raw.issues

Base.show(io::IO, p::PMFile) =
    print(io, "PMFile(\"", basename(p.path), "\", ",
          length(p.bodies), " bodies, ", length(p.joints), " joints, ",
          length(p.bars), " bars)")

"""Body by name (case-insensitive), or `nothing`."""
function body(p::PMFile, name::AbstractString)
    i = findfirst(b -> isequal_ci(b.name, name), p.bodies)
    i === nothing ? nothing : p.bodies[i]
end

"""Resolve a `PMPoint` to coordinates (body-name references resolve to that
body's position)."""
function resolve(p::PMFile, pt::PMPoint)
    pt isa Vector{Float64} && return pt
    b = body(p, pt)
    b === nothing && throw(KeyError(pt))
    b.pos
end

# lenient: corpus tuples contain occasional junk tokens; they become NaN
# (the verbatim text is always recoverable from the entry's `raw`)
vec3(v) = v isa Vector ? Float64[x isa Number ? Float64(x) : NaN for x in v] :
          v isa Number ? Float64[Float64(v)] : Float64[]

aspoint(v)::PMPoint = v isa String ? v : vec3(v)

"""
    parse_pm(text; path="<string>") -> PMFile
"""
function parse_pm(text::AbstractString; path::AbstractString="<string>")
    raw = parse_isi(text; path)
    bodies = PMBody[]
    joints = PMJoint[]
    bars = PMBar[]
    for s in raw.sections
        if isequal_ci(s.name, "BODY")
            push!(bodies, PMBody(get(s, "name", ""),
                                 Float64(get(s, "mass", 0.0)),
                                 vec3(get(s, "inertia", Float64[])),
                                 vec3(get(s, "pos", Float64[])),
                                 vec3(get(s, "ori", Float64[]))))
        elseif isequal_ci(s.name, "JOINT&HINGE") || isequal_ci(s.name, "JOINT")
            kind = isequal_ci(s.name, "JOINT") ? :joint : :joint_hinge
            ax = entry(s, "axis")
            push!(joints, PMJoint(kind, get(s, "posbody", ""), get(s, "negbody", ""),
                                  aspoint(get(s, "pos", Float64[])),
                                  ax === nothing ? nothing : aspoint(ax.value)))
        elseif isequal_ci(s.name, "BAR")
            push!(bars, PMBar(get(s, "name", ""),
                              get(s, "posbody", ""), get(s, "negbody", ""),
                              aspoint(get(s, "pos", Float64[])),
                              aspoint(get(s, "neg", Float64[]))))
        end
    end
    PMFile(String(path), bodies, joints, bars, raw)
end

"""
    read_pm(path) -> PMFile
"""
read_pm(path::AbstractString) = parse_pm(readtext(path); path)

"""All `*.pm` files under `root` (case-insensitive), sorted."""
find_pm_files(root::AbstractString=default_gamedata()) = find_ext(root, ".pm")
