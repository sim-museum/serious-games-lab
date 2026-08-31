# Decoder for Grand Prix Legends .mip texture files (format by P.A.Flack 1998).
# A MIP holds several mipmap levels of one paletted image.  We decode the largest
# level to RGBA for upload as a GL texture (GL regenerates the mip chain).  This
# is the GPL analogue of render.jl's load_dds — the second half of the asset pivot.
#
# Layout: "PIM " hdr -> "DHPM"(MPHD) {type, powW, powH, avgcol, ?, nImages} ->
# (type 0/1) a shared "PAMC"(CMAP) palette -> nImages × "PAMB"(BMAP){ "DHMB"(BMHD)
# w,h,stride ; "ATAD"(DATA) indexed pixels }.  type2 = per-image palette, other = 16bit.
module GPLMip

export decode_mip, decode_mip_bytes, decode_srb_bytes

@inline u32(b,o) = (o+4 > length(b)) ? UInt32(0) :
    UInt32(b[o+1]) | (UInt32(b[o+2])<<8) | (UInt32(b[o+3])<<16) | (UInt32(b[o+4])<<24)
tag(b,o) = String(b[o+1:o+4])

# walk top-level sections (each: 4-byte tag + 0x00000000 + u32 datasize + data, pad to 4)
function sections(b, start)
    secs = Tuple{String,Int,Int}[]    # (tag, data_offset, data_size)
    o = start
    while o + 12 <= length(b)
        t = tag(b,o); sz = Int(u32(b,o+8)); data = o + 12
        push!(secs, (t, data, sz))
        o = data + sz; o += (4 - o % 4) % 4
    end
    secs
end

"""Decode a GPL .srb (sprite) -> the embedded MIP as (w,h,rgba).  An SRB is a small
size header + an embedded standard MIP file ("PIM "…)."""
function decode_srb_bytes(b::AbstractVector{UInt8})
    p = findfirst([0x50,0x49,0x4d,0x20], b)         # "PIM "
    p === nothing && error("no embedded MIP in SRB")
    decode_mip_bytes(b[first(p):end])
end

"""Decode a .mip file -> (width, height, rgba::Vector{UInt8}) of the largest level."""
decode_mip(path::AbstractString) = decode_mip_bytes(read(path))
"Palette byte order this decoder assumes; part of the decoded-texture cache key so a change here
cannot be served stale pixels from disk."
const CMAP_ORDER = "bgra-v2"

function decode_mip_bytes(b::AbstractVector{UInt8})
    tag(b,0) == "PIM " || error("not a MIP")
    # DHPM/MPHD section at offset 12
    tag(b,12) == "DHPM" || error("no MPHD")
    mp = 24                                  # MPHD data start (12 + 12-byte section hdr)
    mtype = Int(b[mp+1])
    powW  = Int(u32(b, mp+1)); powH = Int(u32(b, mp+5))
    W = 1 << powW; H = 1 << powH

    # palette: shared CMAP for type 0/1; for type 2 each BMAP carries its own
    # E83 (2026-08-30): CMAP entries are B,G,R,A -- Windows DIB order -- not R,G,B,A. Read as RGBA,
    # every palettised texture had red and blue exchanged: bushes teal, dry grass cyan, the BOSCH
    # banner blue, the German no-stopping sign a blue ring. That is the PO's "neon trees and
    # shrubs" (types 0/1 are the vegetation cutouts). Decided by textures whose colour is not in
    # doubt: BOSCH is red, dry grass is yellow. The 16-bit types (3/4/5) were already right.
    # Gate: JuliaMotorMTK/tools/mipcolor_smoke.jl. Changing this invalidates the decoded-texture
    # cache, which is why render.jl keys the cache on GPLMip.CMAP_ORDER.
    function read_cmap(off, sz)
        n = sz ÷ 4
        [(b[off+i*4+3], b[off+i*4+2], b[off+i*4+1], b[off+i*4+4]) for i in 0:n-1]
    end

    secs = sections(b, 12)                    # everything after PIM header
    cmap = NTuple{4,UInt8}[]
    bmaps = Int[]                             # data offsets of each PAMB
    bmsizes = Int[]
    for (t, off, sz) in secs
        if     t == "PAMC"; cmap = read_cmap(off, sz)
        elseif t == "PAMB"; push!(bmaps, off); push!(bmsizes, sz)
        end
    end
    isempty(bmaps) && error("no BMAP in $path")

    # largest level = first PAMB.  Its sub-sections: DHMB(BMHD) then ATAD(DATA),
    # plus (type 2) its own PAMC.
    b0 = bmaps[1]; bsz = bmsizes[1]
    subs = sections(b, b0 - 12)              # re-walk starting at this PAMB's data... use offsets
    # walk this BMAP's interior explicitly (offsets relative to b0)
    px_off = 0; px_sz = 0; local_cmap = cmap
    o = b0
    stop = b0 + bsz
    while o + 12 <= stop
        t = tag(b,o); sz = Int(u32(b,o+8)); data = o + 12
        if     t == "ATAD"; px_off = data; px_sz = sz
        elseif t == "PAMC"; local_cmap = read_cmap(data, sz)
        end
        o = data + sz; o += (4 - o % 4) % 4
    end
    px_off == 0 && error("no DATA in first BMAP of $path")

    rgba = Vector{UInt8}(undef, W*H*4)
    pal = local_cmap
    npal = length(pal)
    bytesper = px_sz / (W*H)
    @inline function put(i, idx)
        c = (idx >= 0 && idx < npal) ? pal[idx+1] : (0xff,0x00,0xff,0xff)
        rgba[i*4+1]=c[1]; rgba[i*4+2]=c[2]; rgba[i*4+3]=c[3]; rgba[i*4+4]=c[4]
    end
    if npal > 0 && bytesper <= 0.6            # 4-bit indexed (16-colour palette)
        for i in 0:W*H-1
            byte = b[px_off + (i>>1) + 1]
            idx = (i & 1) == 0 ? (byte & 0x0f) : (byte >> 4)   # low nibble first
            put(i, Int(idx))
        end
    elseif npal > 0 && bytesper <= 1.2        # 8-bit indexed (256-colour palette)
        for i in 0:W*H-1
            put(i, Int(b[px_off+i+1]))
        end
    elseif mtype == 3                         # 16-bit opaque  -> RGB 5-6-5
        for i in 0:W*H-1
            v = UInt16(b[px_off+i*2+1]) | (UInt16(b[px_off+i*2+2])<<8)
            r=((v>>11)&0x1f); g=((v>>5)&0x3f); bl=(v&0x1f)
            rgba[i*4+1]=UInt8((r*255)÷31); rgba[i*4+2]=UInt8((g*255)÷63); rgba[i*4+3]=UInt8((bl*255)÷31); rgba[i*4+4]=0xff
        end
    elseif mtype == 4                         # 16-bit 1-bit alpha -> ARGB 1-5-5-5
        for i in 0:W*H-1
            v = UInt16(b[px_off+i*2+1]) | (UInt16(b[px_off+i*2+2])<<8)
            a=(v>>15); r=((v>>10)&0x1f); g=((v>>5)&0x1f); bl=(v&0x1f)
            rgba[i*4+1]=UInt8((r*255)÷31); rgba[i*4+2]=UInt8((g*255)÷31); rgba[i*4+3]=UInt8((bl*255)÷31)
            rgba[i*4+4]= a==1 ? 0xff : 0x00
        end
    else                                      # type 5 -> ARGB 4-4-4-4 (smooth alpha: glass/chrome)
        for i in 0:W*H-1
            v = UInt16(b[px_off+i*2+1]) | (UInt16(b[px_off+i*2+2])<<8)
            a=((v>>12)&0xf); r=((v>>8)&0xf); g=((v>>4)&0xf); bl=(v&0xf)
            rgba[i*4+1]=UInt8(r*17); rgba[i*4+2]=UInt8(g*17); rgba[i*4+3]=UInt8(bl*17); rgba[i*4+4]=UInt8(a*17)
        end
    end
    (W, H, rgba)
end

end # module
