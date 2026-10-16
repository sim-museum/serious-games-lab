# Parser for GPL track .dat archives (e.g. zandvort.dat) — the packed bundle of a
# track's objects, textures and data files.  Format: a 12-byte header (u16 count,
# u16 version, u32, u32) then `count` directory entries of 27 bytes each = a 13-byte
# filename field (8.3 name, null-padded) + u32 OFFSET (absolute) + u16 flags + u32 + u32.
# Files are stored uncompressed at their offset; size = gap to the next file by offset.
#
# DATFIX-1 (2026-10-16): the directory was read as "name up to its null, then skip null padding" -- which also swallowed
# the first byte of any OFFSET whose low byte is 0x00, misreading that entry (30 of Spa's 2,532, 2 of the Ring's 860) AND
# truncating whichever file its wrong offset landed inside: Spa's tree/bush sprites tr33 and bu16 came out 39.8 / 341 KB
# of their 699.5 KB and failed to decode, so all 82 of their placements were never drawn. Records are fixed-size; read
# them so. `dat_layout()` is part of the texture cache key (render.jl), so nothing decoded from the old misreads survives.
module GPLDat

export parse_dat
# read at call time (this module is precompiled inside JRRender, where a module-level ENV const would be frozen)
dat_legacy() = get(ENV, "JM_DAT_LEGACY", "0") != "0"           # the old variable-length read, for A/B only
dat_layout() = dat_legacy() ? "legacy" : "fixed27"

"""Parse a GPL .dat archive → Dict(lowercase filename => file bytes)."""
function parse_dat(path::AbstractString)
    b = read(path)
    u32(o) = UInt32(b[o+1]) | (UInt32(b[o+2])<<8) | (UInt32(b[o+3])<<16) | (UInt32(b[o+4])<<24)
    count = Int(UInt32(b[1]) | (UInt32(b[2])<<8))      # u16 entry count
    names = String[]; offs = Int[]
    pos = 12
    if dat_legacy()
        for _ in 1:count
            s = pos
            while pos < length(b) && b[pos+1] != 0x00; pos += 1; end
            push!(names, String(b[s+1:pos])); pos += 1
            while pos < length(b) && b[pos+1] == 0x00; pos += 1; end
            push!(offs, Int(u32(pos))); pos += 14
        end
    else
    for _ in 1:count
        pos + 27 <= length(b) || break
        nb = b[pos+1:pos+13]; z = findfirst(==(0x00), nb)
        push!(names, String(nb[1:(z === nothing ? 13 : z - 1)]))   # 13-byte name field
        push!(offs, Int(u32(pos + 13)))                              # absolute offset
        pos += 27                                                     # name(13)+offset(4)+flags(2)+u32(4)+u32(4)
    end
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
