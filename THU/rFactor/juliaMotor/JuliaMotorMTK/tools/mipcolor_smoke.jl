# GATE: E83 -- palettised GPL textures must decode with the right channel order.
#
# PO 2026-08-27/28: "trees and shrubs have neon colors". Root cause (2026-08-30): GPL's MIP palette
# (PAMC/CMAP) stores entries as B,G,R,A and the decoder read them as R,G,B,A, so every palettised
# texture (types 0/1/2 -- the vegetation cutouts, signs, dry grass, earth banks) had red and blue
# swapped: bushes teal, dry grass cyan, the BOSCH banner blue. The 16-bit types (3/4/5) were right.
#
# Asserted on textures whose true colour is not in doubt, so no grade can satisfy it: the Bosch
# banner is red, the German "no stopping" sign is a red ring, dry grass is yellow -- and a 16-bit
# Shell board must STAY red (a fix that swapped everything would turn it blue).
include(joinpath(@__DIR__, "..", "..", "demo", "native", "gplmip.jl")); using .GPLMip
include(joinpath(@__DIR__, "..", "..", "demo", "native", "gpldat.jl")); using .GPLDat
const ZD = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks", "nurburg"))
isdir(ZD) || (println("GPL nurburg track not found: $ZD"); exit(2))
blobs = Dict{String,Vector{UInt8}}()
for f in readdir(ZD; join=true)
    lf = lowercase(f); endswith(lf, ".mip") && (blobs[lowercase(basename(f))] = read(f))
    endswith(lf, ".dat") && (try; for (k,v) in GPLDat.parse_dat(f); endswith(k, ".mip") && (blobs[k] = v); end; catch; end)
end
function meanrgb(nm)
    b = blobs[nm]; w,h,px = GPLMip.decode_mip_bytes(b); sr=0; sg=0; sb=0; na=0
    for i in 1:4:length(px)-3; if px[i+3]>=0x80; sr+=Int(px[i]); sg+=Int(px[i+1]); sb+=Int(px[i+2]); na+=1 end; end
    (Int(b[25]), div(sr,na), div(sg,na), div(sb,na))
end
fails = Ref(0)
function check(nm, pred, what)
    t = meanrgb(nm); ok = pred(t[2], t[3], t[4]); ok || (fails[] += 1)
    println("  ", ok ? "PASS" : "FAIL", "  ", rpad(nm, 14), "type ", t[1], "  rgb=(", t[2], ",", t[3], ",", t[4], ")  ", what)
end
println("E83 MIP palette channel-order gate (nurburg)")
check("bo_sign2.mip", (r,g,b) -> r > b + 60, "BOSCH banner is RED")
check("x-sign.mip",   (r,g,b) -> r > b + 40, "no-stopping sign: red ring")
check("drygrass.mip", (r,g,b) -> r > b + 60 && g > b, "dry grass is YELLOW")
check("hgbush.mip",   (r,g,b) -> g > r && r >= b, "bush is olive green (R >= B), not teal")
check("brd_shel.mip", (r,g,b) -> r > b + 100, "16-bit Shell board STAYS red (types 3/4/5 were never swapped)")
check("boschb.mip",   (r,g,b) -> r > b + 100, "16-bit Bosch board stays red")
println(fails[] == 0 ? "MIPCOLOR GATE: PASS" : "MIPCOLOR GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
