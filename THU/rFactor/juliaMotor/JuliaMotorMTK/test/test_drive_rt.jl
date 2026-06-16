# Headless test of the real-time driving adapter (no renderer): drive the MTK car
# with live inputs and confirm it moves/turns/accelerates sensibly + steps fast.
# Run: julia --project=. test/test_drive_rt.jl
include(joinpath(@__DIR__, "..", "src", "drive_rt.jl")); using .DriveRT

c = build_car(x0 = 100.0, z0 = 50.0, θ0 = 0.3, v0 = 10.0)
println("spawned at ($(c.x), $(c.z)) heading $(round(c.θ,digits=2)), v=$(c.v) m/s")

# drive: full-ish throttle + a steady right turn, 4 s
dt = 1/60; nstep = 240
x0, z0, θ0 = c.x, c.z, c.θ
t0 = time_ns()
for i in 1:nstep
    step_car!(c, 0.7, 0.0, 0.35, dt)
end
wall = (time_ns()-t0)/1e9
dist = hypot(c.x-x0, c.z-z0)
println("after 4 s: pos ($(round(c.x,digits=1)), $(round(c.z,digits=1)))  heading $(round(c.θ,digits=2))  "*
        "v=$(round(c.v*3.6,digits=1)) km/h  rpm=$(round(Int,c.rpm))  gear=$(c.gear)")
println("  travelled $(round(dist,digits=1)) m, turned $(round(rad2deg(c.θ-θ0),digits=1))°")
println("  step time $(round(wall/nstep*1000,digits=3)) ms/frame → real-time ×$(round(nstep*dt/wall,digits=0))")
println("  front-left traction circle (long,lat,|F| /·mg/4): $(round.(c.tc[1],digits=2))")

@assert c.v > 10.0  "should have accelerated"
@assert dist > 30.0 "should have moved"
@assert abs(c.θ - θ0) > 0.1 "should have turned"
@assert isfinite(c.x) && isfinite(c.v) "no NaNs"
@assert wall/nstep < 0.016 "must be real-time (<16ms/frame)"
println("\nADAPTER OK ✓ — the MTK car drives in real time with live inputs.")
