# Closed-loop driver model — wraps DrivenVehicle in a controller that follows
# reference targets (speed + yaw rate), so the car tracks a trajectory instead of
# drifting open-loop.  This is the controls layer that lets the model drive itself
# (lap-time sim) and removes the open-loop replay drift.
#
#   • LONGITUDINAL: PI on (u_ref − u) → a combined pedal; +pedal = throttle, −pedal
#     = brake (the driver modulates the pedals to hold the target speed).
#   • LATERAL: kinematic feedforward δ_ff = r_ref·L/u plus PI on (r_ref − r) → steer
#     (steer to achieve the target yaw, correcting the model's understeer/drift).
#   • leaky integrators (anti-windup).
#
# References u_ref, r_ref, gear are inputs (constants, a manoeuvre, or telemetry).
# Requires DrivenVehicle (vehicle_driven.jl) and its deps.

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

function ClosedLoopVehicle(; name, Kpu = 0.25, Kiu = 0.15, Kpr = 0.7, Kir = 0.5,
                           leak = 0.1, L = 2.41, vehicle = (;))
    @named car = DrivenVehicle(; vehicle...)
    ps = @parameters Kpu=Kpu Kiu=Kiu Kpr=Kpr Kir=Kir leak=leak L=L
    vars = @variables uref(t) rref(t) gear_in(t) eu(t) er(t) eui(t)=0.0 eri(t)=0.0 pedal(t) steer(t)
    eqs = [
        eu ~ uref - car.u,
        er ~ rref - car.r,
        D(eui) ~ eu - leak*eui,                       # leaky PI integrators (anti-windup)
        D(eri) ~ er - leak*eri,
        pedal ~ Kpu*eu + Kiu*eui,                      # >0 throttle, <0 brake
        steer ~ rref*L/(car.u + 1.0) + Kpr*er + Kir*eri,   # kinematic FF + PI feedback
        car.throttle ~ min(1.0, max(0.0,  pedal)),
        car.brake    ~ min(1.0, max(0.0, -pedal)),
        car.δ        ~ steer,
        car.gear     ~ gear_in,
    ]
    System(eqs, t, vars, ps; systems = [car], name)
end
