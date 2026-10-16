# GATE: DATFIX-1 (2026-10-16) -- GPL .dat directory records are fixed 27 bytes (13-byte name + offset + u16 + u32 + u32).
# The old "name to its null, skip null padding" read ate the low byte of any offset ending 0x00 (30 of Spa's 2,532 entries)
# and truncated other files: Spa's tr33.srb tree sprite came out 39,771 bytes and never decoded; house1a.3do was "absent".
# Asserted on the PO's GPL install: the fixed read gives tr33.srb whole (699,512 bytes, decodes 512x512) and house1a.3do;
# and the old read (JM_DAT_LEGACY=1) still shows the defect -- the known positive that proves this check can fail.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "gpldat.jl")); include(joinpath(@__DIR__, "..", "..", "demo", "native", "gplmip.jl"))
const DAT = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks", "spa67", "spa67.dat"))
isfile(DAT) || (println("GPL spa67.dat not found: $DAT"); exit(2))
ok = true
check(c, m) = (global ok &= c; println(c ? "PASS " : "FAIL ", m))
d = GPLDat.parse_dat(DAT)
check(length(d) == 2532, "spa67.dat: all 2,532 entries ($(length(d)))")
t = get(d, "tr33.srb", UInt8[])
check(length(t) == 699512, "tr33.srb whole: $(length(t)) bytes")
check((try; GPLMip.decode_srb_bytes(t)[1:2] == (512, 512); catch; false; end), "tr33.srb decodes 512x512")
check(haskey(d, "house1a.3do"), "house1a.3do present")
ENV["JM_DAT_LEGACY"] = "1"; dl = GPLDat.parse_dat(DAT); delete!(ENV, "JM_DAT_LEGACY")
check(length(get(dl, "tr33.srb", UInt8[])) == 39771, "known positive: the legacy read truncates tr33.srb (39,771)")
println("DATFIX: ", ok ? "PASS" : "FAIL"); exit(ok ? 0 : 1)
