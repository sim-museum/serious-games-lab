# Native reader for iRacing .ibt (irSDK disk-telemetry) binary files.
# No external deps — the format is a fixed C-struct header + a YAML session
# string + fixed-stride data rows.  See data/iracing/parse_ibt.py for the
# reference layout; this is the Julia port used to feed the MTK model.
#
# Layout (little-endian):
#   irsdk_header (112 B): ver, status, tickRate, sessionInfoUpdate,
#       sessionInfoLen, sessionInfoOffset, numVars, varHeaderOffset, numBuf,
#       bufLen, pad[2], varBuf[4]{tickCount, bufOffset, pad[2]}
#   varHeader[numVars] @ varHeaderOffset (144 B each):
#       type, offset, count, countAsTime+pad[3], name[32], desc[64], unit[32]
#   sessionInfo YAML @ sessionInfoOffset (sessionInfoLen bytes)
#   data rows @ varBuf[0].bufOffset, stride = bufLen, one row per tick.

module IBT

export IBTFile, channel, channels, ibt_open, session_yaml, write_ibt

# irSDK var types → (julia type, byte size)
const VARTYPE = Dict(
    0 => (Int8,    1),   # char
    1 => (Bool,    1),   # bool
    2 => (Int32,   4),   # int
    3 => (UInt32,  4),   # bitfield
    4 => (Float32, 4),   # float
    5 => (Float64, 8),   # double
)

struct VarInfo
    type::Int
    offset::Int
    count::Int
    name::String
    desc::String
    unit::String
end

struct IBTFile
    path::String
    tickRate::Int
    bufLen::Int
    dataOffset::Int
    nrows::Int
    vars::Dict{String,VarInfo}
    yaml::String
    raw::Vector{UInt8}
end

cstr(b) = String(b[1:something(findfirst(==(0x00), b), length(b)+1)-1])

"""    ibt_open(path) -> IBTFile

Parse the header + var table + YAML of an .ibt file (loads the whole file into
memory; these are tens of MB).  Channel samples are read lazily via `channel`.
"""
function ibt_open(path::AbstractString)
    raw = read(path)
    gi(o) = reinterpret(Int32, raw[o+1:o+4])[1] |> Int     # int @ byte offset o
    tickRate         = gi(8)
    sessionInfoLen   = gi(16)
    sessionInfoOffset= gi(20)
    numVars          = gi(24)
    varHeaderOffset  = gi(28)
    bufLen           = gi(36)
    dataOffset       = gi(48 + 4)        # varBuf[0].bufOffset (tickCount @48, bufOffset @52)

    vars = Dict{String,VarInfo}()
    for i in 0:numVars-1
        b = varHeaderOffset + i*144
        vtype  = gi(b)
        voff   = gi(b+4)
        vcount = gi(b+8)
        name = cstr(raw[b+16+1 : b+16+32])
        desc = cstr(raw[b+48+1 : b+48+64])
        unit = cstr(raw[b+112+1: b+112+32])
        vars[name] = VarInfo(vtype, voff, vcount, name, desc, unit)
    end
    yaml = String(raw[sessionInfoOffset+1 : sessionInfoOffset+sessionInfoLen])
    nrows = bufLen > 0 ? (length(raw) - dataOffset) ÷ bufLen : 0
    IBTFile(String(path), tickRate, bufLen, dataOffset, nrows, vars, yaml, raw)
end

channels(f::IBTFile) = sort!(collect(keys(f.vars)))
session_yaml(f::IBTFile) = f.yaml

"""    channel(f, name; idx=1) -> Vector

Full time series of a scalar (or `idx`-th element of an array) channel, native
type converted to Float64.  Sampled at `f.tickRate` Hz.
"""
function channel(f::IBTFile, name::AbstractString; idx::Int=1)
    v = f.vars[name]
    T, sz = VARTYPE[v.type]
    out = Vector{Float64}(undef, f.nrows)
    base = f.dataOffset + v.offset + (idx-1)*sz
    @inbounds for r in 0:f.nrows-1
        o = base + r*f.bufLen
        out[r+1] = Float64(reinterpret(T, f.raw[o+1:o+sz])[1])
    end
    out
end

# ---- writing ----------------------------------------------------------------
# write one channel value (Float64) into a data row at its byte offset, as the
# channel's irSDK type (char/bool/int/bitfield/float/double).
function _putval!(buf::Vector{UInt8}, off::Int, vtype::Int, val::Real)
    T, sz = VARTYPE[vtype]
    x = T === Bool ? (val > 0.5) : T <: Integer ? round(T, clamp(val, Float64(typemin(T)), Float64(typemax(T)))) : T(val)
    b = reinterpret(UInt8, [x])
    @inbounds for k in 1:sz; buf[off+k] = b[k]; end
end

"""    write_ibt(out, template::IBTFile, samples) -> out

Write an iRacing-compatible .ibt at `out`, reusing `template`'s header + variable
table + session YAML verbatim (so any iRacing tool / our own reader parses it
identically), and filling the data buffer from `samples` — a vector of
`Dict{String,<:Real}` mapping iRacing channel names (e.g. "Speed", "RPM",
"LongAccel") to values, one dict per 1/`tickRate`-second tick.  Channels absent
from a sample are written as zero.  This lets juliaMotor emit telemetry in the
exact format iRacing produces, for side-by-side lap comparison / model tuning.
"""
function write_ibt(out::AbstractString, tmpl::IBTFile, samples::AbstractVector)
    hdr = copy(tmpl.raw[1:tmpl.dataOffset])             # header + var table + YAML, unchanged
    n = length(samples)
    hdr[48+1:48+4] = reinterpret(UInt8, Int32[n])       # varBuf[0].tickCount = sample count
    open(out, "w") do io
        write(io, hdr)
        row = Vector{UInt8}(undef, tmpl.bufLen)
        for s in samples
            fill!(row, 0x00)
            for (name, val) in s
                v = get(tmpl.vars, name, nothing); v === nothing && continue
                _putval!(row, v.offset, v.type, Float64(val))
            end
            write(io, row)
        end
    end
    out
end

end # module
