# Probe: (A) verify the Julia FFB writer actuates the wheel (gentle L/R), and
# (B) drive the physics to measure the sign of front-axle lateral force vs steer,
# so the in-game FFB resists the turn (self-centering) instead of assisting it.
include(joinpath(@__DIR__, "ffb.jl")); using .FFB
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","drive_rt.jl"))); using .DriveRT

println("── A: FFB writer test (hold the wheel; gentle pulls) ──")
d = open_ffb()
if d.ok
    println("opened $(d.path)  id=$(d.id)")
    println("  +level (should pull ONE way)…");  set_force!(d, 0.25); sleep(0.9); set_force!(d, 0.0); sleep(0.5)
    println("  -level (should pull the OTHER way)…"); set_force!(d, -0.25); sleep(0.9); set_force!(d, 0.0)
else
    println("  no FFB device found (ok=false) — is the wheel plugged in?")
end

println("\n── B: physics sign probe (building car, ~30-60 s) ──")
c = build_car(v0 = 0.0)
for _ in 1:300; step_car!(c, 1.0, 0.0, 0.0, 1/60); end          # accelerate ~5 s
println("  reached v=$(round(c.v,digits=1)) m/s, rpm=$(round(Int,c.rpm))")
for _ in 1:90;  step_car!(c, 0.5, 0.0,  1.0, 1/60); end          # steer LEFT (+1)
flL = c.tc[1][2] + c.tc[2][2]
println("  steer LEFT (+1):  front_lat = $(round(flL,digits=3))   v=$(round(c.v,digits=1))")
for _ in 1:45;  step_car!(c, 0.5, 0.0,  0.0, 1/60); end          # recenter
for _ in 1:90;  step_car!(c, 0.5, 0.0, -1.0, 1/60); end          # steer RIGHT (-1)
flR = c.tc[1][2] + c.tc[2][2]
println("  steer RIGHT(-1):  front_lat = $(round(flR,digits=3))   v=$(round(c.v,digits=1))")

# We want the wheel to RESIST: during a LEFT turn (steer>0) the force must pull RIGHT.
# In ffb.jl, +level and -level pull opposite ways (which is which we confirm by feel in A).
sign_for_resist = flL > 0 ? -1 : 1
println("\n  => FFB force = SIGN * front_lat,  with SIGN = $(sign_for_resist)  (so a left turn pulls back toward center)")
println("     (front_lat ~ $(round(abs(flL),digits=2)) at this speed/steer → pick gain so that ≈ 0.5-0.7 force)")
d.ok && close_ffb(d)
println("done.")
