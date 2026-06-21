# Validate the aligning-torque FFB model offscreen with REALISTIC steering (small
# angles at speed, so the car corners instead of spinning). Want: force builds through
# turn-in, plateaus BELOW max (headroom so it can still "get stronger"), then lightens
# past the grip limit — but never goes fully dead (mechanical-trail floor).
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt.jl"); using .DriveRT

const A_F    = 1.314
const DELTA  = 0.30
const GAIN   = 1.3
const ATRAIL = 0.18          # slip [rad] where pneumatic trail is spent (~10°)
const TFLOOR = 0.40          # residual trail (caster) so the wheel lightens but isn't dead
softclip(x)  = tanh(x)
trailf(α)    = TFLOOR + (1 - TFLOOR) * clamp(1 - abs(α)/ATRAIL, 0.0, 1.0)

c = build_car(v0 = 0.0)
for _ in 1:180; step_car!(c, 1.0, 0.0, 0.0, 1/60); end          # ~18-20 m/s
println("v=$(round(c.v,digits=1)) m/s\n")
println(rpad("steer",7), rpad("front_lat",11), rpad("slipdeg",9), rpad("trail",8), rpad("mz",8), "force")
for st in 0.0:0.04:0.4
    for _ in 1:30; step_car!(c, 0.5, 0.0, st, 1/60); end
    tl = telemetry(c); u = max(tl.u, 1.0)
    αf = atan(tl.v + A_F*tl.r, u) - st*DELTA
    trail = trailf(αf); fl = c.tc[1][2] + c.tc[2][2]
    mz = fl * trail; spd = clamp(c.v/2.5, 0.0, 1.0)
    f  = softclip(-1.0 * GAIN * mz * spd)
    println(rpad(round(st,digits=2),7), rpad(round(fl,digits=2),11),
            rpad(round(rad2deg(αf),digits=1),9), rpad(round(trail,digits=2),8),
            rpad(round(mz,digits=2),8), round(f,digits=2))
    for _ in 1:8; step_car!(c, 0.5, 0.0, 0.0, 1/60); end
end
