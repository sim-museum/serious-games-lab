# AI-GOLD: derive the AI's pace anchors from the .ibt telemetry instead of hand-set constants.
# The PO's standing rule is that car physics comes from the ibt data; amax/vmax are exactly the
# constants that rule exists to remove.
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf
f = ibt_open(ARGS[1])
ch = try channels(f) catch e; String[] end
pick(names...) = for n in names; n in ch && return n; end
get1(n) = filter(isfinite, channel(f, n))
lat = pick("LatAccel", "LateralAccel"); lon = pick("LongAccel", "LongitudinalAccel")
spd = pick("Speed", "GroundSpeed")
println("using channels: lat=", lat, " lon=", lon, " speed=", spd)
# Peaks are the wrong statistic for an anchor: a single kerb strike or a spike gives a number the
# car cannot actually sustain. Report high PERCENTILES alongside the peak so the difference is
# visible rather than assumed.
pct(v, q) = (u = sort(abs.(v)); u[clamp(ceil(Int, q*length(u)), 1, length(u))])
if lat !== nothing
    v = get1(lat)
    @printf("lat accel : peak=%.2f m/s2 (%.2f g)  p99=%.2f (%.2f g)  p95=%.2f (%.2f g)  n=%d\n",
            maximum(abs,v), maximum(abs,v)/9.81, pct(v,0.99), pct(v,0.99)/9.81,
            pct(v,0.95), pct(v,0.95)/9.81, length(v))
end
if lon !== nothing
    v = get1(lon)
    @printf("lon accel : peak=%.2f m/s2 (%.2f g)  p99=%.2f  p01(brake)=%.2f\n",
            maximum(abs,v), maximum(abs,v)/9.81, pct(v,0.99), minimum(v))
end
if spd !== nothing
    v = get1(spd)
    @printf("speed     : max=%.1f m/s (%.0f km/h)  p99=%.1f m/s (%.0f km/h)\n",
            maximum(v), 3.6*maximum(v), pct(v,0.99), 3.6*pct(v,0.99))
end
