# TBC tire files.
#
# A TBC is a sequence of [SLIPCURVE] sections (named curves, sampled at
# uniform `Step` and connected by cubic spline per the in-file spec) and
# [COMPOUND] sections.  Inside a compound, entries before any marker apply
# to both axles; `FRONT:` / `REAR:` markers (case-insensitive) scope what
# follows to one axle.  Compounds reference slip curves by name
# (e.g. DryLatCurve="Lateral").

"""
A `[SLIPCURVE]`: normalized reaction-vs-slip samples at uniform `step`.
isiMotor normalizes the peak to 1.0 and moves it with load/speed (see the
`SpeedEffects`/`LatPeak`/`LongPeak` compound parameters); `dropoff`
controls how the post-peak shape stretches when the peak moves.
"""
struct SlipCurve
    name::String
    step::Float64
    dropoff::Float64
    data::Vector{Float64}
end

"""Slip values (x-axis) for the curve's samples: `0, step, 2step, ...`"""
slips(c::SlipCurve) = range(0.0; step=c.step, length=length(c.data))

"""
A `[COMPOUND]`.  Entries are grouped by their scope marker: `""` (before
any marker, applies everywhere), `"FRONT"`/`"REAR"`, and — in the stock-car
tires — per-corner `"FRONTLEFT"`/`"FRONTRIGHT"`/`"REARLEFT"`/`"REARRIGHT"`.
`getindex`/`get` resolve a wheel position through corner -> axle -> common.
"""
struct TBCCompound
    name::String
    scopes::Dict{String,ISISection}
end

const TBC_SCOPE_CHAIN = Dict(
    :front      => ["FRONT", ""],
    :rear       => ["REAR", ""],
    :frontleft  => ["FRONTLEFT", "FRONT", ""],
    :frontright => ["FRONTRIGHT", "FRONT", ""],
    :rearleft   => ["REARLEFT", "REAR", ""],
    :rearright  => ["REARRIGHT", "REAR", ""],
)

"""Entries for one scope (`:front`, `:rearleft`, ... or a raw scope string);
empty section if the compound has none."""
function axle(c::TBCCompound, which::Union{Symbol,AbstractString})
    s = which isa Symbol ? String(first(TBC_SCOPE_CHAIN[which])) : uppercase(which)
    get(c.scopes, s, ISISection("COMPOUND", nothing, ISIEntry[]))
end

function Base.get(c::TBCCompound, (key, which)::Tuple{AbstractString,Symbol}, default)
    for scope in TBC_SCOPE_CHAIN[which]
        s = get(c.scopes, scope, nothing)
        s === nothing && continue
        e = entry(s, key)
        e === nothing || return e.value
    end
    default
end

function Base.getindex(c::TBCCompound, key::AbstractString, which::Symbol)
    v = get(c, (key, which), nothing)
    v === nothing && throw(KeyError(key))
    v
end

struct TBCFile
    path::String
    slipcurves::Vector{SlipCurve}
    compounds::Vector{TBCCompound}
    raw::ISIFile
end

issues(t::TBCFile) = t.raw.issues

Base.show(io::IO, t::TBCFile) =
    print(io, "TBCFile(\"", basename(t.path), "\", ",
          length(t.slipcurves), " slip curves, ",
          length(t.compounds), " compounds)")

"""First slip curve named `name` (case-insensitive), or `nothing`."""
function slipcurve(t::TBCFile, name::AbstractString)
    i = findfirst(c -> isequal_ci(c.name, name), t.slipcurves)
    i === nothing ? nothing : t.slipcurves[i]
end

"""Compound by name or index, or `nothing`.  HDV `FrontTireCompoundSetting`
is a 0-based index into this list."""
function compound(t::TBCFile, name::AbstractString)
    i = findfirst(c -> isequal_ci(c.name, name), t.compounds)
    i === nothing ? nothing : t.compounds[i]
end
compound(t::TBCFile, index0::Integer) = t.compounds[index0 + 1]

"""
    parse_tbc(text; path="<string>") -> TBCFile
"""
function parse_tbc(text::AbstractString; path::AbstractString="<string>")
    raw = parse_isi(text; path, data_blocks=true, scopes=true)
    curves = SlipCurve[]
    compounds = TBCCompound[]
    for s in raw.sections
        if isequal_ci(s.name, "SLIPCURVE")
            data = get(s, "Data", Float64[])
            push!(curves, SlipCurve(get(s, "Name", ""), Float64(get(s, "Step", 0.0)),
                                    Float64(get(s, "DropoffFunction", 1.0)),
                                    data isa Vector{Float64} ? data : Float64[]))
        elseif isequal_ci(s.name, "COMPOUND")
            grouped = Dict{String,Vector{ISIEntry}}()
            for e in s.entries
                push!(get!(grouped, uppercase(e.scope), ISIEntry[]), e)
            end
            push!(compounds, TBCCompound(get(s, "Name", ""),
                Dict(scope => ISISection(s.name, s.comment, es)
                     for (scope, es) in grouped)))
        end
    end
    TBCFile(String(path), curves, compounds, raw)
end

"""
    read_tbc(path) -> TBCFile
"""
read_tbc(path::AbstractString) = parse_tbc(readtext(path); path)

"""All `*.tbc` files under `root` (case-insensitive), sorted."""
find_tbc_files(root::AbstractString=default_gamedata()) = find_ext(root, ".tbc")
