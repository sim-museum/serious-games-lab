# GPL .lp reader — Papyrus' AI line files (race.lp, pass1.lp, pass2.lp, minrace/maxrace.lp, pit.lp).
#
# These ARE "how GPL's AI behave" (PO, E89): the racing line GPL's cars follow, the two passing
# rails, and the speed GPL's AI carries at every point. Decoded 2026-08-30 from the Monza set:
#   header: u16 version (2), u16 (1), u32 n_records
#   record (20 bytes, n_records of them at ~3.0 m dlong spacing): 5 × Float32
#     [1] dlong speed in METRES PER TICK (36 ticks/s)  -> ×36 = m/s   (2.15 → 77 m/s on Monza's straight)
#     [2] dlat velocity (m/tick; r = 0.93 against the per-record dlat difference)
#     [3] dlat, metres. NB the passing rails are NOT a fixed offset: on the pit straight pass1/pass2 sit at
#         race ±4.0 m, but over the Monza lap pass1 is median +1.1 m (min −2.5) and pass2 median −3.4 m
#         (max +0.1) — asymmetric, hugging the race line and opening only where the road allows.
#     [4] small; uncorrelated with d(field2) — unknown, kept
#     [5] always 0 in every file inspected
# Validation: Σ 3.0 m / speed over the 1918 Monza records = 91 s, against the 86.5 s human replay.
# 🔒 The GPL install is read-only reference data; this module only reads.
module GPLLP
export read_lp, lp_speed_mps, GPL_TICK_HZ

const GPL_TICK_HZ = 36.0

struct LPLine
    v_tick::Vector{Float32}     # dlong speed, m/tick
    dlat_v::Vector{Float32}
    dlat::Vector{Float32}       # metres
    f4::Vector{Float32}
    f5::Vector{Float32}
end

function read_lp(path::AbstractString)
    b = read(path)
    length(b) >= 8 || error("read_lp: $path too short")
    n = Int(reinterpret(UInt32, b[5:8])[1])
    length(b) == 8 + 20n || error("read_lp: $path is $(length(b)) bytes, expected 8 + 20×$n")
    f = reinterpret(Float32, b[9:end])
    LPLine(f[1:5:end], f[2:5:end], f[3:5:end], f[4:5:end], f[5:5:end])
end

"Speed in m/s at every record."
lp_speed_mps(l::LPLine) = Float64.(l.v_tick) .* GPL_TICK_HZ

end
