# coast_census.jl — E91-S7.  WHAT COAST-DOWNS DOES THE GOLD ACTUALLY CONTAIN?
#
# E91-S3 closed the derivation route with "the gold .ibt files contain no clean coast-down", and
# E91-S6 showed that claim was never tested against the gold files at all -- every probe had been
# reading data/juliaracer, which is the SIM's own output.  So: enumerate.
#
# For every iRacing capture in the gold store, find MAXIMAL runs of samples with
#   throttle == 0, brake == 0, speed >= 8 m/s
# and report each one's length, speed span, gear behaviour, straightness and elevation change.
# No fitting, no model, no conclusion -- a census, so the next sprint argues from a list rather
# than from an assertion about what the data "cannot" contain.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/coast_census.jl [dir]

using Printf, Statistics
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT

const DIR = length(ARGS) >= 1 ? ARGS[1] : get(ENV, "JM_REFDIR", "/home/admin/gold standard/julia racer")
const DT  = 1/60
ch(f,n) = try channel(f,n) catch; nothing end
is_iracing(f) = any(nm -> (v = ch(f,nm)) !== nothing && !isempty(v) && maximum(abs,v) > 0,
                    ("Voltage","FuelLevel","WaterTemp","OilTemp"))

files = String[]
for (root,_,fs) in walkdir(DIR), fn in fs
    endswith(lowercase(fn), ".ibt") && push!(files, joinpath(root,fn))
end
sort!(files)

segs = NamedTuple[]
for p in files
    f = try ibt_open(p) catch; continue end
    is_iracing(f) || (println("  skipped (sim-written): ", basename(p)); continue)
    thr, brk, spd = ch(f,"Throttle"), ch(f,"Brake"), ch(f,"Speed")
    gr, cl, alt   = ch(f,"Gear"), ch(f,"Clutch"), ch(f,"Alt")
    stw, lat      = ch(f,"SteeringWheelAngle"), ch(f,"LatAccel")
    any(isnothing, (thr,brk,spd,gr)) && continue
    n = minimum(length, (thr,brk,spd,gr))
    k = 1
    while k <= n
        if thr[k] <= 0.01 && brk[k] <= 0.01 && spd[k] >= 8.0
            j = k
            while j < n && thr[j+1] <= 0.01 && brk[j+1] <= 0.01 && spd[j+1] >= 8.0
                j += 1
            end
            len = (j - k + 1) * DT
            if len >= 1.0
                v = @view spd[k:j]
                gs = unique(Int.(round.(@view gr[k:j])))
                push!(segs, (file = basename(p), t0 = k*DT, len = len,
                             v0 = v[1]*3.6, v1 = v[end]*3.6,
                             vmax = maximum(v)*3.6, vmin = minimum(v)*3.6,
                             gears = gs,
                             clutch = cl === nothing ? NaN : mean(@view cl[k:j]),
                             dalt = alt === nothing ? NaN : (alt[j] - alt[k]),
                             stw = stw === nothing ? NaN : maximum(abs, @view stw[k:j]),
                             lat = lat === nothing ? NaN : maximum(abs, @view lat[k:j])))
            end
            k = j + 1
        else
            k += 1
        end
    end
end

@printf("\n%d coast segments (>= 1.0 s) across %d gold captures\n\n", length(segs), length(files))
@printf("%-46s %6s %7s %7s %6s %-10s %7s %6s %6s\n",
        "file", "t0 s", "len s", "km/h", "->", "gears", "|steer|", "|lat|", "dAlt m")
for s in sort(segs, by = x -> -(x.v0 - x.v1))[1:min(20,end)]
    @printf("%-46s %6.1f %7.2f %7.1f %6.1f %-10s %7.3f %6.2f %6.1f\n",
            first(s.file, 46), s.t0, s.len, s.v0, s.v1, string(s.gears), s.stw, s.lat, s.dalt)
end

# what the item actually needs: 200 -> 60 km/h, in gear, straight
want = [s for s in segs if s.v0 >= 150 && s.v1 <= 100 && s.stw < 0.15]
@printf("\nsegments spanning >=150 down to <=100 km/h with |steer| < 0.15 rad: %d\n", length(want))
for s in want
    @printf("   %-46s t=%.1f s  %.1f -> %.1f km/h over %.2f s  gears %s  dAlt %.1f m\n",
            first(s.file,46), s.t0, s.v0, s.v1, s.len, string(s.gears), s.dalt)
end
# and what the STRAIGHT ones look like, whatever their span -- plus a crash filter, because a
# 220->29 km/h "coast" in 4 s is 13 m/s^2 and that is an impact, not a deceleration.
straight = [s for s in segs if s.stw < 0.15 && (isnan(s.lat) || s.lat < 20)]
@printf("\nstraight-ish coast segments (|steer| < 0.15 rad, |lat| < 20 m/s^2): %d\n", length(straight))
for s in sort(straight, by = x -> -(x.v0 - x.v1))[1:min(8,end)]
    @printf("   %-46s %.2f s  %.1f -> %.1f km/h  gears %s\n",
            first(s.file,46), s.len, s.v0, s.v1, string(s.gears))
end
if !isempty(segs)
    @printf("\nlongest segment: %.2f s   widest speed span: %.1f km/h\n",
            maximum(s -> s.len, segs), maximum(s -> s.v0 - s.v1, segs))
end
