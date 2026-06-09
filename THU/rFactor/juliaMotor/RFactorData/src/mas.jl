# MAS archives (gMotor2 / rFactor 1) — the containers for GMT meshes and
# DDS/TGA/BMP textures.
#
# Format (recovered empirically from this install, verified by full
# decompression of vehicle and track archives):
#
#   header: 16-byte signature (constant, lightly obfuscated bytes),
#           then 3 × u32: unknown(0), entry count, data-section size
#   TOC:    at offset 28, `count` records of 256 bytes:
#           u32 flags, char[236] name (NUL-padded),
#           u32 offset (into data section), u32 usize, u32 zsize, u32 zero
#   data:   at 28 + count*256; each entry is one zlib stream of zsize
#           bytes inflating to exactly usize bytes
#
# Entries are stored sequentially: offset(k+1) = offset(k) + zsize(k).

using Zlib_jll: libz

const MAS_SIGNATURE = UInt8[0xc8, 0xcf, 0xd2, 0xd8, 0xce, 0xd8, 0xe6, 0xc9,
                            0xca, 0xdd, 0xd8, 0xbe, 0xbb, 0xa6, 0xbf, 0x90]

struct MASEntry
    name::String
    flags::UInt32
    offset::Int64        # into the data section
    usize::Int64
    zsize::Int64
end

struct MASFile
    path::String
    entries::Vector{MASEntry}
    data_base::Int64
end

Base.show(io::IO, m::MASFile) =
    print(io, "MASFile(\"", basename(m.path), "\", ", length(m.entries),
          " entries, ", round(sum(e -> e.usize, m.entries) / 1e6; digits=1),
          " MB uncompressed)")

entrynames(m::MASFile) = [e.name for e in m.entries]

"""
    read_mas(path) -> MASFile

Parse a MAS archive's table of contents (no data is decompressed).
"""
function read_mas(path::AbstractString)
    raw = open(io -> read(io, 28 + 256 * 65536), path)  # TOC region is small
    length(raw) >= 28 || error("$path: truncated MAS header")
    raw[1:16] == MAS_SIGNATURE ||
        error("$path: unrecognized MAS signature $(bytes2hex(raw[1:16]))")
    count = Int(reinterpret(UInt32, raw[21:24])[1])
    entries = Vector{MASEntry}(undef, count)
    for k in 1:count
        b = 28 + (k - 1) * 256
        length(raw) >= b + 256 || error("$path: truncated TOC")
        e = view(raw, b+1:b+256)
        flags = reinterpret(UInt32, e[1:4])[1]
        nul = findfirst(==(0x00), view(e, 5:240))
        name = String(e[5:(nul === nothing ? 240 : 3 + nul)])
        off, us, zs = Int64.(reinterpret(UInt32, e[241:252]))
        entries[k] = MASEntry(name, flags, off, us, zs)
    end
    MASFile(String(path), entries, 28 + count * 256)
end

function zuncompress(src::AbstractVector{UInt8}, usize::Integer)
    dest = Vector{UInt8}(undef, usize)
    destlen = Ref{Culong}(usize)
    ret = ccall((:uncompress, libz), Cint,
                (Ptr{UInt8}, Ref{Culong}, Ptr{UInt8}, Culong),
                dest, destlen, src, length(src))
    ret == 0 || error("zlib uncompress failed (code $ret)")
    Int(destlen[]) == usize || error("inflated $(destlen[]) bytes, expected $usize")
    dest
end

"""
    extract(m::MASFile, entry_or_name) -> Vector{UInt8}

Decompress one archive member (case-insensitive name lookup).
"""
function extract(m::MASFile, e::MASEntry)
    src = open(m.path) do io
        seek(io, m.data_base + e.offset)
        read(io, e.zsize)
    end
    # zsize == usize marks a stored (uncompressed) member, e.g. the
    # commentary MP3 archives
    e.zsize == e.usize ? src : zuncompress(src, e.usize)
end

function extract(m::MASFile, name::AbstractString)
    i = findfirst(e -> isequal_ci(e.name, name), m.entries)
    i === nothing && throw(KeyError(name))
    extract(m, m.entries[i])
end

"""All `*.mas` files under `root` (case-insensitive), sorted."""
find_mas_files(root::AbstractString=default_gamedata()) = find_ext(root, ".mas")
