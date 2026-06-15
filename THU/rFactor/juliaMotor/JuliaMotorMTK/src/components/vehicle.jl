# Vehicle — the chassis body tying the four corners into a closed car.
#
# Planar body: states v (lateral velocity) and r (yaw rate); u (longitudinal
# speed) and δ (front road-steer angle) are inputs (prescribed, or from a driver /
# telemetry).  Each corner is a `CornerAssembly` (dynamic suspension + tyre).
#
# The body:
#   • computes each corner's slip angle from body kinematics + steer,
#   • sums the four tyre forces (rotated to body frame) into Newton-Euler:
#         m(v̇ + u·r) = ΣFy_body ,   Izz·ṙ = Σ(x_i·Fy_body,i − y_i·Fx_body,i + Mz,i)
#   • distributes lateral/longitudinal LOAD TRANSFER back to each corner's Fext.
#
# No algebraic loop: the dynamic Corner makes Fz depend on suspension *states*,
# not instantaneously on Fext, so the load-transfer feedback is well-posed.
# Pure-slip lateral for now (κ=0; combined slip + powertrain come next).
#
# Requires Corner (corner.jl), Tyre (tyre.jl), CornerAssembly (corner_assembly.jl).

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

function Vehicle(; name,
        m = 617.0, Izz = 890.0, a = 1.314, b = 1.096, tf = 1.50, tr = 1.50,
        h = 0.30, front_frac = 0.455,
        # Fz_static = corner weight (already the full static tyre load); m_s = sprung
        # corner mass = cw/g − m_u (used only for ride dynamics, decoupled from Fz_static)
        front_corner = (Fz_static = 1376.0, ks = 18_250.0, cs = 2500.0,
                        m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 300.0),
        rear_corner  = (Fz_static = 1650.0, ks = 29_200.0, cs = 3000.0,
                        m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 300.0))
    L = a + b
    mf = m*front_frac; mr = m*(1 - front_frac)        # axle masses (load transfer)
    @named FL = CornerAssembly(corner = front_corner, tyre = TYRE_SKIDPAD_FRONT)
    @named FR = CornerAssembly(corner = front_corner, tyre = TYRE_SKIDPAD_FRONT)
    @named RL = CornerAssembly(corner = rear_corner,  tyre = TYRE_SKIDPAD_REAR)
    @named RR = CornerAssembly(corner = rear_corner,  tyre = TYRE_SKIDPAD_REAR)

    ps = @parameters m=m Izz=Izz a=a b=b tf=tf tr=tr h=h mf=mf mr=mr L=L
    vars = @variables v(t)=0.0 r(t)=0.0 u(t) δ(t) ay(t) ax(t) β(t)
    #   v lateral vel [m/s], r yaw rate [rad/s] (states); u speed, δ steer (inputs);
    #   ay/ax body accel [m/s²]; β body slip [rad].

    # per-corner: position (xi,yi), steer, lateral/longitudinal transfer signs
    spec = ((FL, a,  tf/2, δ, -1, -1, mf, tf),
            (FR, a, -tf/2, δ, +1, -1, mf, tf),
            (RL,-b,  tr/2, 0, -1, +1, mr, tr),
            (RR,-b, -tr/2, 0, +1, +1, mr, tr))

    eqs = Equation[]
    Fyb = Any[]; Fxb = Any[]; Mz = Any[]
    for (ca, xi, yi, st, slat, slong, maxle, trk) in spec
        vx = u - r*yi;  vy = v + r*xi
        α  = st - atan(vy, vx)
        fxb = ca.tyre.Fx*cos(st) - ca.tyre.Fy*sin(st)
        fyb = ca.tyre.Fx*sin(st) + ca.tyre.Fy*cos(st)
        push!(Fyb, fyb); push!(Fxb, fxb); push!(Mz, ca.tyre.Mz)
        ΔFz = slat*maxle*ay*h/trk + slong*m*ax*h/(2L)   # load transfer at this corner
        append!(eqs, [
            ca.tyre.α    ~ α,
            ca.tyre.κ    ~ 0.0,
            ca.corner.zr ~ 0.0,
            ca.corner.Fext ~ -ΔFz,                       # Fz = Fz_static − Fext  ⇒  +ΔFz load
        ])
    end
    push!(eqs,
        ax ~ D(u),
        ay ~ (Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4]) / m,
        β  ~ atan(v, u),
        m*(D(v) + u*r) ~ Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4],
        Izz*D(r) ~ (a*(Fyb[1]+Fyb[2]) - b*(Fyb[3]+Fyb[4])
                    - tf/2*(Fxb[1]-Fxb[2]) - tr/2*(Fxb[3]-Fxb[4])
                    + Mz[1]+Mz[2]+Mz[3]+Mz[4]),
    )
    System(eqs, t, vars, ps; systems = [FL, FR, RL, RR], name)
end
