# Standing-start launch test: spawn at rest (engine idling), floor the throttle,
# confirm the clutch engages and the car launches from 0.  Also check it idles
# stably with no throttle.   Run: julia --project=. test/test_launch.jl
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT

println("=== 1) idle at standstill (no throttle, 3 s) ===")
c = build_car(v0 = 0.0)
for _ in 1:180; step_car!(c, 0.0, 0.0, 0.0, 1/60); end
println("  after 3 s idling: v=$(round(c.v*3.6,digits=2)) km/h  rpm=$(round(Int,c.rpm))  (should stay put, hold idle)")
@assert c.v < 0.5         "should stay stationary at idle"
@assert 1700 < c.rpm < 2400 "should hold ~idle rpm"

println("\n=== 2) standing-start launch (full throttle from rest) ===")
c = build_car(v0 = 0.0)
println("  t=0: v=$(round(c.v*3.6,digits=1)) km/h  rpm=$(round(Int,c.rpm)) gear=$(c.gear)")
for sec in 1:6
    for _ in 1:60; step_car!(c, 1.0, 0.0, 0.0, 1/60); end
    println("  t=$(sec)s: v=$(round(c.v*3.6,digits=1)) km/h  rpm=$(round(Int,c.rpm))  gear=$(c.gear)  rear κ-ish (v): launched=$(c.v>1)")
end
@assert c.v*3.6 > 60   "should have launched and accelerated past 60 km/h in 6 s"
@assert isfinite(c.v)  "no NaNs"

println("\n=== 3) launch then brake to a stop ===")
for _ in 1:120; step_car!(c, 0.0, 1.0, 0.0, 1/60); end   # 2 s hard braking
println("  after 2 s braking: v=$(round(c.v*3.6,digits=1)) km/h")
@assert c.v*3.6 < 40   "braking should slow it markedly"

println("\n=== 4) MANUAL clutch launch: rev with clutch in, then drop it ===")
c = build_car(v0 = 0.0)
for _ in 1:60; step_car!(c, 1.0, 0.0, 0.0, 1/60; clutch = 1.0, manual = true); end   # clutch IN, rev
println("  clutch in + full throttle 1 s: v=$(round(c.v*3.6,digits=1)) km/h  rpm=$(round(Int,c.rpm))  (revs, car still)")
@assert c.v < 1.0    "clutch in ⇒ car must stay put"
@assert c.rpm > 5000 "engine should rev freely with the clutch in"
for sec in 1:4
    for _ in 1:60; step_car!(c, 1.0, 0.0, 0.0, 1/60; clutch = 0.0, manual = true); end   # clutch OUT
    println("  clutch out t=$(sec)s: v=$(round(c.v*3.6,digits=1)) km/h  rpm=$(round(Int,c.rpm))  gear=$(c.gear)")
end
@assert c.v*3.6 > 40 "dropping the clutch should launch the car"

println("\nLAUNCH MODEL OK ✓ — idles, AUTO + MANUAL-clutch standing starts, brakes.")
