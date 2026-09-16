# S-skitter: measure SKITTER on the built racing line, geometrically, with no sim and no eye.
#
# Skitter is the line changing direction back and forth over a few metres. Two numbers capture it:
#   * RMS of the SECOND difference of heading -- how much the curvature changes node to node;
#   * curvature SIGN REVERSALS -- a clean line turns one way through a corner, a skittering one
#     alternates. Reversals are the number the eye actually notices.
# Arms are set with JM_HW_SCALE (see ai.jl): 1 = shipped band, 10 = clamp effectively removed.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack
include("ai.jl"); using .RaceAI
using Statistics, Printf
T = get(ENV, "TRACK", "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/watglen")
name = basename(T)
# GPL track dirs are inconsistently cased (watglen.dat but monza.DAT), and a hand-written list of
# two spellings silently produced NO OUTPUT for monza -- which reads as "the track failed" rather
# than "the probe cannot spell". Match case-insensitively instead.
dat = first(filter(f -> lowercase(basename(f)) == lowercase(name)*".dat",
                   joinpath.(T, readdir(T))))
d = GPLDat.parse_dat(dat)
key = first(filter(k -> endswith(lowercase(k), ".trk"), collect(keys(d))))
tmp = tempname()*".trk"; write(tmp, d[key])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
# AILine stores the CENTRELINE in .x/.z and the racing line as the lateral offset .rl -- measuring
# .x/.z directly gives the centreline's roughness, which is identical in every arm by construction.
# (First version of this probe did exactly that and reported two arms matching to 5 decimals.)
n = length(line.x)
x = [line.x[i] + line.rl[i]*(-sin(line.θ[i])) for i in 1:n]
z = [line.z[i] + line.rl[i]*( cos(line.θ[i])) for i in 1:n]
wrap(a) = atan(sin(a), cos(a))
hdg = [atan(z[i%n+1]-z[i], x[i%n+1]-x[i]) for i in 1:n]
dh  = [wrap(hdg[i%n+1]-hdg[i]) for i in 1:n]
d2h = [wrap(dh[i%n+1]-dh[i])   for i in 1:n]
rev = count(i -> dh[i]*dh[i%n+1] < 0, 1:n)
# prove the arm actually differs: if the two arms produce the SAME line, a same-roughness result
# says nothing about the clamp. Report the line's own displacement so the arms are distinguishable.
cx = sum(x)/n; cz = sum(z)/n
@printf("[armcheck] JM_HW_SCALE=%s  sum|x|=%.3f sum|z|=%.3f  spread=%.3f\n",
        get(ENV,"JM_HW_SCALE","1"), sum(abs.(x)), sum(abs.(z)),
        sqrt(sum((x.-cx).^2 .+ (z.-cz).^2)/n))
# on-road check: the band exists to keep the apex off the grass, so a smoothness win that pushes
# |offset| past the halfwidth is not a fix. Default halfwidth is 3.0 m and the taper only shrinks it.
# AI-GOLD: roughness is a means, not the goal -- the PO's oracle is the 2-lap Watkins Glen gold
# replay, whose reference lap is REF_LAP["watglen"] = 66.912 s. Report the line's own natural lap
# time so a "smoother" line that is also SLOWER cannot be mistaken for progress.
let ref = Dict("watglen"=>66.912, "monza"=>90.202, "rouen"=>NaN)
    t = RaceAI.natural_laptime(line)
    r = get(ref, name, NaN)
    @printf("[laptime] natural=%.2f s  gold=%.3f s  delta=%+.2f s\n", t, r, t - r)
end
@printf("[onroad] max|rl|=%.3f m  (halfwidth 3.0 m -- must not exceed)\n", maximum(abs.(line.rl)))
@printf("[rough] track=%s nodes=%d  RMSd2h=%.5f  reversals=%d (%.1f%%)  maxd2h=%.4f\n",
        name, n, sqrt(mean(d2h.^2)), rev, 100*rev/n, maximum(abs.(d2h)))
