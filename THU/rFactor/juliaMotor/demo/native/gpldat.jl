# Parser for GPL track .dat archives (e.g. zandvort.dat) — the packed bundle of a
# track's objects, textures and data files.  Format: a 12-byte header (u16 count,
# u16 version, u32, u32) then `count` directory entries, each = null-terminated
# filename (null-padded) + u32 OFFSET (absolute) + u16 flags + u32 + u32.  Files
# are stored uncompressed at their offset; size = gap to the next file by offset.
module GPLDat

export parse_dat

"""Parse a GPL .dat archive → Dict(lowercase filename => file bytes)."""
function parse_dat(path::AbstractString)
    b = read(path)
    u32(o) = UInt32(b[o+1]) | (UInt32(b[o+2])<<8) | (UInt32(b[o+3])<<16) | (UInt32(b[o+4])<<24)
    count = Int(UInt32(b[1]) | (UInt32(b[2])<<8))      # u16 entry count
    names = String[]; offs = Int[]
    pos = 12
    for _ in 1:count
        s = pos
        while pos < length(b) && b[pos+1] != 0x00; pos += 1; end
        push!(names, String(b[s+1:pos])); pos += 1                  # consume the terminating null
        while pos < length(b) && b[pos+1] == 0x00; pos += 1; end    # skip null padding
        push!(offs, Int(u32(pos)))                                  # v1 = absolute offset
        pos += 14                                                   # offset(4)+flags(2)+u32(4)+u32(4)
    end
    # size of each file = distance to the next file by offset (last → EOF)
    order = sortperm(offs)
    sizes = Dict{Int,Int}()
    for (i, idx) in enumerate(order)
        nxt = i < length(order) ? offs[order[i+1]] : length(b)
        sizes[idx] = nxt - offs[idx]
    end
    out = Dict{String,Vector{UInt8}}()
    for i in 1:length(names)
        o = offs[i]; sz = sizes[i]
        (o >= 0 && sz > 0 && o + sz <= length(b)) || continue
        out[lowercase(names[i])] = b[o+1 : o+sz]
    end
    out
end

end # module
