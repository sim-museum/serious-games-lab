# DrivenVehicleRT — real-time-steppable DrivenVehicle for interactive driving.
# Driver inputs (throttle, brake, δ, gear) are PARAMETERS (set live each frame via
# the integrator), and world-position states (X, Y, heading ψ) are added so the car
# can be placed on a track and rendered.  Step it with an OrdinaryDiffEq integrator.
#
# Requires Corner, Tyre, CornerAssembly, engine_torque (powertrain.jl).

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

function DrivenVehicleRT(; name,
        m = 617.0, Izz = 890.0, a = 1.314, b = 1.096, tf = 1.50, tr = 1.50,
        h = 0.30, front_frac = 0.455,
        Rw_f = 0.30, Rw_r = 0.33, Iw = 1.0, Ieng = 0.10, η = 0.9, final = 4.11,
        bias = 0.535, Tbrake_max = 3000.0, CdA = 0.9, ρair = 1.10,
        throttle0 = 0.0, brake0 = 0.0, steer0 = 0.0, gear0 = 1.72,
        front_corner = (Fz_static = 1376.0, ks = 18_250.0, cs = 2500.0,
                        m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 300.0),
        rear_corner  = (Fz_static = 1650.0, ks = 29_200.0, cs = 3000.0,
                        m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 300.0))
    L = a + b; mf = m*front_frac; mr = m*(1 - front_frac)
    @named FL = CornerAssembly(corner = front_corner, tyre = TYRE_SKIDPAD_FRONT)
    @named FR = CornerAssembly(corner = front_corner, tyre = TYRE_SKIDPAD_FRONT)
    @named RL = CornerAssembly(corner = rear_corner,  tyre = TYRE_SKIDPAD_REAR)
    @named RR = CornerAssembly(corner = rear_corner,  tyre = TYRE_SKIDPAD_REAR)

    # driver inputs are PARAMETERS (updated live); vehicle + clutch params too.
    # Clutch/launch: Ie engine inertia, c_c clutch coupling, T_cap capacity, idle.
    ps = @parameters m=m Izz=Izz a=a b=b tf=tf tr=tr h=h mf=mf mr=mr L=L Rw_f=Rw_f Rw_r=Rw_r Iw=Iw η=η final=final bias=bias Tbrake_max=Tbrake_max CdA=CdA ρair=ρair throttle=throttle0 brake=brake0 δ=steer0 gear=gear0 clutch=0.0 Ie=0.18 c_c=60.0 T_cap=500.0 k_idle=0.5 idle_rpm=2000.0
    # ωe = engine speed [rad/s], starts at idle (2000 rpm). ωf/ωr wheel speeds start ~0.
    vars = @variables u(t)=0.0 v(t)=0.0 r(t)=0.0 ωf(t)=0.0 ωr(t)=0.0 ωe(t)=209.4 ay(t) ax(t) rpm(t) X(t)=0.0 Y(t)=0.0 ψ(t)=0.0

    gr = gear*final; drag = 0.5*ρair*CdA*u^2
    spec = ((FL, a,  tf/2, δ, -1, -1, mf, tf, Rw_f, :f),
            (FR, a, -tf/2, δ, +1, -1, mf, tf, Rw_f, :f),
            (RL,-b,  tr/2, 0, -1, +1, mr, tr, Rw_r, :r),
            (RR,-b, -tr/2, 0, +1, +1, mr, tr, Rw_r, :r))
    eqs = Equation[]; Fyb=Any[]; Fxb=Any[]; Mz=Any[]; Fx_f=Any[]; Fx_r=Any[]
    for (ca, xi, yi, st, slat, slong, maxle, trk, Rw, axle) in spec
        vx = u - r*yi;  vy = v + r*xi
        # Energy conservation: the longitudinal slip denominator must be ≥ 0 at ANY heading.
        # The old `vx+0.5` went NEGATIVE for a corner moving backward in a spin, flipping κ's
        # sign so the "braking" force drove the car (it sped up while braking + pinwheeled).
        # Using |vx| keeps κ's sign tied to (ωRw−vx) ⇒ the force always opposes the longitudinal
        # slip.  α keeps its origin-safe forward-clamped form (atan's Jacobian is singular at a
        # standstill); the low-speed fade kills phantom cornering force there.
        α  = (st - atan(vy, max(vx, 0.5))) * min(1.0, abs(vx)/1.5)
        ωax = axle == :f ? ωf : ωr
        κ  = (ωax*Rw - vx)/(abs(vx) + 0.5)
        fxb = ca.tyre.Fx*cos(st) - ca.tyre.Fy*sin(st)
        fyb = ca.tyre.Fx*sin(st) + ca.tyre.Fy*cos(st)
        push!(Fyb, fyb); push!(Fxb, fxb); push!(Mz, ca.tyre.Mz)
        axle == :f ? push!(Fx_f, ca.tyre.Fx) : push!(Fx_r, ca.tyre.Fx)
        ΔFz = slat*maxle*ay*h/trk + slong*m*ax*h/(2L)
        append!(eqs, [ca.tyre.α ~ α, ca.tyre.κ ~ κ, ca.corner.zr ~ 0.0, ca.corner.Fext ~ -ΔFz])
    end
    ΣFx = Fxb[1]+Fxb[2]+Fxb[3]+Fxb[4];  ΣFy = Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4]
    # --- slipping clutch / standing-start launch ---
    ωgb = ωr*gr                                       # gearbox-input (clutch driven) speed
    # clutch engagement = clutch-released fraction (1−clutch) × anti-stall.  `clutch`
    # is the driver pedal (0 released/engaged, 1 pressed/disengaged); the adapter sets
    # it from the slider in MANUAL or computes an auto value in AUTO.  Anti-stall opens
    # the clutch below ~1000 rpm so it can't drag the engine to a dead stall.
    engage = clamp((rpm - 1000.0)/600.0, 0.0, 1.0) * (1.0 - clutch)
    Tcl = clamp(c_c*(ωe - ωgb), -T_cap*engage, T_cap*engage)   # viscous clutch, capped & slipping
    Tidle = k_idle*max(0.0, idle_rpm - rpm)            # idle controller (holds ~2000 rpm)
    push!(eqs,
        rpm ~ ωe*60/(2π),                             # engine rpm IS the engine-speed state
        ax ~ (ΣFx - drag)/m,
        ay ~ ΣFy/m,
        m*(D(u) - v*r) ~ ΣFx - drag,
        m*(D(v) + u*r) ~ ΣFy,
        Izz*D(r) ~ a*(Fyb[1]+Fyb[2]) - b*(Fyb[3]+Fyb[4])
                   - tf/2*(Fxb[1]-Fxb[2]) - tr/2*(Fxb[3]-Fxb[4]) + Mz[1]+Mz[2]+Mz[3]+Mz[4],
        Ie*D(ωe) ~ engine_torque(rpm, throttle) + Tidle - Tcl,        # engine spins freely vs clutch
        2*Iw*D(ωf) ~ -brake*Tbrake_max*bias*tanh(ωf) - (Fx_f[1]+Fx_f[2])*Rw_f,
        2*Iw*D(ωr) ~ Tcl*gr*η - brake*Tbrake_max*(1-bias)*tanh(ωr) - (Fx_r[1]+Fx_r[2])*Rw_r,
        # world-frame position for rendering (heading ψ, body vel u,v)
        D(X) ~ u*cos(ψ) - v*sin(ψ),
        D(Y) ~ u*sin(ψ) + v*cos(ψ),
        D(ψ) ~ r,
    )
    System(eqs, t, vars, ps; systems = [FL, FR, RL, RR], name)
end
