# CARINTERACT-1 (prepared 2026-10-16 for IRTEST-261015 test 4): iRacing's CONTACT law, measured from the PO's .ibt files.
#
# A contact is a velocity step our own driving cannot make: |d(LongAccel, LatAccel)| > JOLT g between two 60 Hz rows (a
# tyre cannot change the car's acceleration that fast) while a car is close (CarDistAhead or CarDistBehind < NEAR m), or
# any step of the incident counter. Per event: time, lap distance, speed, the closing speed just before (the rate the gap
# to the car ahead/behind shrank over the last 0.5 s), the velocity change over the next 0.25 s, the incident points it
# cost (PlayerCarMyIncidentCount), and the repair time it added (PitRepairLeft / PitOptRepairLeft, seconds).
# julia today (CARINTERACT-1 S1): car-to-car hits damage the player with the WALL law, from 3 m/s closing.
#
#   julia --project=. tools/irtest_contact_261015.jl <dir or .ibt files...>
using Printf
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
const G = 9.80665
const JOLT = parse(Float64, get(ENV, "JM_CONTACT_JOLT", "0.6"))    # g per row
const NEAR = 8.0

files = String[]
for a in ARGS
    isdir(a) ? append!(files, filter(f -> endswith(lowercase(f), ".ibt"), readdir(a; join = true))) : push!(files, a)
end
isempty(files) && (println("usage: irtest_contact_261015.jl <dir or .ibt files>"); exit(2))

for fn in files
    f = ibt_open(fn); c(n) = haskey(f.vars, n) ? Float64.(channel(f, n)) : nothing
    t = c("SessionTime"); v = c("Speed"); ax = c("LongAccel"); ay = c("LatAccel"); ld = c("LapDist")
    ahead = c("CarDistAhead"); behind = c("CarDistBehind"); inc = c("PlayerCarMyIncidentCount")
    rep = c("PitRepairLeft"); orep = c("PitOptRepairLeft")
    any(x -> x === nothing, (t, v, ax, ay)) && (println("  skip ", basename(fn), ": missing channels"); continue)
    n = length(v); ev = Int[]; last = -10^9
    for k in 2:n
        jolt = hypot(ax[k] - ax[k-1], ay[k] - ay[k-1])/G
        near = (ahead !== nothing && 0 < ahead[k] < NEAR) || (behind !== nothing && 0 < behind[k] < NEAR)
        incstep = inc !== nothing && inc[k] > inc[k-1]
        ((jolt > JOLT && near) || incstep) || continue
        k - last < 30 && continue                                           # one event per 0.5 s
        push!(ev, k); last = k
    end
    println("== ", basename(fn), ": ", length(ev), " contact event(s)")
    isempty(ev) && continue
    println("     t s   lapdist  speed km/h | closing m/s (ahead / behind) | dv in 0.25 s | incidents | repair s (+opt)")
    for k in ev
        k0 = max(1, k - 30); k1 = min(n, k + 15)
        cl(g) = (g === nothing || !(0 < g[k0] < 200) || !(0 < g[k] < 200)) ? NaN : (g[k0] - g[k]) / (t[k] - t[k0])
        dv = maximum(abs(v[j] - v[k-1]) for j in k:k1)
        di = inc === nothing ? 0 : Int(inc[min(n, k + 120)] - inc[k-1])               # points within 2 s
        dr = rep === nothing ? 0.0 : rep[min(n, k + 120)] - rep[k-1]
        dro = orep === nothing ? 0.0 : orep[min(n, k + 120)] - orep[k-1]
        @printf("  %7.2f %8.0f %10.1f  |  %+6.2f / %+6.2f              | %6.2f m/s   | %+3d       | %+.1f (%+.1f)\n",
                t[k], ld === nothing ? NaN : ld[k], 3.6v[k], cl(ahead), cl(behind), dv, di, dr, dro)
    end
end
