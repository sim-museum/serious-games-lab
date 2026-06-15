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

export IBTFile, channel, channels, ibt_open, session_yaml

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

end # module
