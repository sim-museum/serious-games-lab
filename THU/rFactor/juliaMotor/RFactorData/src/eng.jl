# Engine and gear-ratio INI files.
#
# Engine files (HDV [ENGINE] Normal= / RestrictorPlate=) are flat
# key=value text — everything lands in the parser's preamble section —
# with the torque map as repeated entries:
#
#   RPMTorque=( 4000.0, -41.7, 229.5)   // rpm, coast (back) torque, full torque
#
# Gear files (HDV [DRIVELINE] GearFile=) hold the garage's available
# ratio options as repeated `ratio=(pinion, ring)` pairs under
# [GEAR_RATIOS]; the effective ratio is ring/pinion.

struct EngineFile
    path::String
    rpm::Vector{Float64}        # sample RPMs, ascending
    coast::Vector{Float64}      # engine-braking torque at each RPM (Nm, <= 0)
    torque::Vector{Float64}     # full-throttle torque at each RPM (Nm)
    raw::ISIFile
end

issues(e::EngineFile) = e.raw.issues

Base.show(io::IO, e::EngineFile) =
    print(io, "EngineFile(\"", basename(e.path), "\", ",
          length(e.rpm), " torque samples, ",
          isempty(e.rpm) ? "" : "$(round(Int, e.rpm[end])) rpm max)")

"""Scalar engine parameter by key (searched across all sections), or `default`."""
function param(e::EngineFile, key::AbstractString, default=nothing)
    for s in e.raw.sections
        v = get(s, key, nothing)
        v === nothing || return v
    end
    default
end

"""
    parse_engine(text; path="<string>") -> EngineFile
"""
function parse_engine(text::AbstractString; path::AbstractString="<string>")
    raw = parse_isi(text; path)
    rpm, coast, torque = Float64[], Float64[], Float64[]
    for s in raw.sections, e in entries(s, "RPMTorque")
        v = e.value
        if v isa Vector && length(v) >= 3 && all(x -> x isa Number, v[1:3])
            push!(rpm, v[1]); push!(coast, v[2]); push!(torque, v[3])
        else
            push!(raw.issues, "$(path):$(e.line): unparseable RPMTorque: $(e.raw)")
        end
    end
    EngineFile(String(path), rpm, coast, torque, raw)
end

"""
    read_engine(path) -> EngineFile
"""
read_engine(path::AbstractString) = parse_engine(readtext(path); path)

"""
    gear_ratios(f::ISIFile; section_name="GEAR_RATIOS") -> Vector{Float64}

The garage's selectable ratios from a gear file's `ratio=(pinion, ring)`
entries, as ring/pinion.  HDV `Gear<N>Setting`/`FinalDriveSetting` values
are 0-based indices into these lists.
"""
function gear_ratios(f::ISIFile; section_name::AbstractString="GEAR_RATIOS")
    s = section(f, section_name)
    s === nothing && return Float64[]
    [Float64(v[2]) / Float64(v[1])
     for v in (e.value for e in entries(s, "ratio"))
     if v isa Vector && length(v) >= 2 && all(x -> x isa Number, v[1:2])]
end

"""
    final_drive_ratios(f::ISIFile) -> Vector{Float64}

Selectable final-drive ratios from `[FINAL_DRIVE]`, with the section's
`bevel=(pinion, ring)` pair (if any) multiplied in.
"""
function final_drive_ratios(f::ISIFile)
    ratios = gear_ratios(f; section_name="FINAL_DRIVE")
    s = section(f, "FINAL_DRIVE")
    s === nothing && return ratios
    b = get(s, "bevel", nothing)
    bevel = b isa Vector && length(b) >= 2 && all(x -> x isa Number, b[1:2]) ?
            Float64(b[2]) / Float64(b[1]) : 1.0
    ratios .* bevel
end

"""
    read_gears(path) -> ISIFile
"""
read_gears(path::AbstractString) = parse_isi(readtext(path); path)
