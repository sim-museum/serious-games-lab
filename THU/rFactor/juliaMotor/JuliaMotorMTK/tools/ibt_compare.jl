# ibt_compare.jl — side-by-side comparison of two iRacing-format .ibt telemetry
# files (the gold-standard iRacing run vs a juliaMotor JM_IBT run), for tuning the
# physics against measured telemetry.
#
#   julia ibt_compare.jl  "<iRacing.ibt>"  "<juliaracer.ibt>"
#
# Prints per-channel summary stats (min / mean / max, and peak |g| for the accels)
# plus a skidpad grip headline and an energy-conservation sanity check.  Steady-
# state skidpad runs aren't time-aligned, so we compare DISTRIBUTIONS, not samples.

include(joinpath(@__DIR__, "..", "src", "ibt.jl"));  using .IBT

length(ARGS) >= 2 || error("usage: julia ibt_compare.jl <iRacing.ibt> <juliaracer.ibt>")
ref = ibt_open(ARGS[1])      # iRacing gold
jm  = ibt_open(ARGS[2])      # juliaMotor

stat(f, ch) = (v0 = try channel(f, ch) catch; return nothing end;
               v = filter(isfinite, v0);   # real iRacing files have NaN rows (pit/pre-session)
               isempty(v) ? nothing : (n=length(v), lo=minimum(v), mu=sum(v)/length(v), hi=maximum(v),
                                        amax=maximum(abs, v)))
fmt(x) = lpad(x === nothing ? "—" : string(round(x, digits=2)), 9)

# (channel, scale, unit) — scale converts native irSDK units to the display unit
chans = [("Speed",1/0.27778,"km/h"), ("LatAccel",1/9.80665,"g"), ("LongAccel",1/9.80665,"g"),
         ("YawRate",180/π,"°/s"), ("SteeringWheelAngle",180/π,"°"), ("RPM",1.0,"rpm"),
         ("Gear",1.0,"-"), ("Throttle",1.0,"0..1"), ("Brake",1.0,"0..1")]

println("\n  iRacing : ", basename(ref.path), "  (", ref.nrows, " rows @ ", ref.tickRate, " Hz)")
println("  julia   : ", basename(jm.path),  "  (", jm.nrows,  " rows @ ", jm.tickRate,  " Hz)\n")
println(rpad("channel",20), rpad("unit",6), "│", rpad("  iRacing  min   mean    max",34), "│  julia    min   mean    max")
println("─"^20, "─"^6, "┼", "─"^34, "┼", "─"^34)
for (ch, sc, unit) in chans
    a = stat(ref, ch);  b = stat(jm, ch)
    row(s) = s === nothing ? "    —        —        —   " : string(fmt(s.lo*sc), fmt(s.mu*sc), fmt(s.hi*sc))
    println(rpad(ch,20), rpad(unit,6), "│", row(a), "  │", row(b))
end

println("\n  ── skidpad headline ───────────────────────────────────────────")
la_r = stat(ref,"LatAccel"); la_j = stat(jm,"LatAccel")
la_r === nothing || println("  peak lateral grip   iRacing ", round(la_r.amax/9.80665,digits=2), " g    julia ",
                            la_j===nothing ? "—" : string(round(la_j.amax/9.80665,digits=2), " g"))
sp_r = stat(ref,"Speed"); sp_j = stat(jm,"Speed")
if sp_r !== nothing && sp_j !== nothing
    println("  speed envelope      iRacing ≤", round(sp_r.hi*3.6,digits=0), " km/h   julia ≤", round(sp_j.hi*3.6,digits=0), " km/h")
    sp_j.hi > sp_r.hi*1.5 && println("  ⚠ ENERGY: julia top speed ≫ iRacing — possible runaway (energy not conserved)")
end
println()
