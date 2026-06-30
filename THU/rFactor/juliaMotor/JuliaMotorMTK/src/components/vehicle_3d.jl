# DrivenVehicle3D — a FULL 3-D Lotus 49: the planar (u,v,r) driven vehicle of
# vehicle_rt.jl PLUS a real sprung body with HEAVE (z), PITCH (θ) and ROLL (φ),
# and four UNSPRUNG masses with genuine suspension travel and GROUND CONTACT.
#
# Why this exists: the planar model can't leave the ground, so the Nürburgring
# Flugplatz jump benchmark was unrunnable and there was no real VertAccel / ride
# height / pitch / roll.  Here the vertical load on each tyre comes from the
# suspension state, and a smooth contact clamp lets Fz → 0 the instant a wheel
# lifts — so the car jumps, goes ballistic, and lands with a load spike, and the
# lateral/longitudinal LOAD TRANSFER emerges from body roll/pitch instead of an
# algebraic ΔFz formula.
#
# Coordinates are ABSOLUTE with explicit gravity (NOT the equilibrium coords of
# Corner): each suspension carries a static preload P_s = m_s·g and each tyre a
# static load Fz_static = (m_s+m_u)·g, so on the ground the body is in balance,
# and when airborne the (clamped) springs go slack and only gravity acts.
#
# Requires Tyre (tyre.jl) + engine_torque (powertrain.jl).  Real-time-steppable
# exactly like DrivenVehicleRT (driver inputs + road inputs are live parameters).

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

# smooth max(x,0): springs/tyres can only push, not pull — but keep the Jacobian
# bounded for the fixed-step real-time solver (ε sets the rounding scale, N).
smoothpos(x, ε) = 0.5*(x + sqrt(x^2 + ε^2))

function DrivenVehicle3D(; name,
        m = 617.0, Izz = 890.0, Ixx = 120.0, Iyy = 850.0,
        a = 1.314, b = 1.096, tf = 1.50, tr = 1.50, h = 0.30, front_frac = 0.455,
        Rw_f = 0.30, Rw_r = 0.33, Iw = 1.0, η = 0.9, final = 4.11,
        bias = 0.535, Tbrake_max = 4200.0, CdA = 0.9, ρair = 1.10, g = 9.80665,
        throttle0 = 0.0, brake0 = 0.0, steer0 = 0.0, gear0 = 1.72, brush = false,
        # PO: ct (tyre vertical DAMPING) was 300 ≈ 8% of critical for the unsprung mass → the car
        # "superball-bounced" on landing off a crest.  Raised to ~27% of critical so a jump landing is
        # absorbed (inelastic), not sprung back; mainly affects bumps/landings, not steady cornering.
        front_corner = (ks = 18_250.0, cs = 2500.0, m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 1000.0),
        rear_corner  = (ks = 29_200.0, cs = 3000.0, m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 1100.0))
    L = a + b; mf = m*front_frac; mr = m*(1 - front_frac)
    M_s = 2*(front_corner.m_s + rear_corner.m_s)          # total sprung mass

    # brush=true ⇒ physics-based brush tyre (no fudge); else the Magic-Formula preset
    FL = brush ? BrushTyre(; name=:FL, BRUSH_FRONT...) : Tyre(; name=:FL, TYRE_SKIDPAD_FRONT...)
    FR = brush ? BrushTyre(; name=:FR, BRUSH_FRONT...) : Tyre(; name=:FR, TYRE_SKIDPAD_FRONT...)
    RL = brush ? BrushTyre(; name=:RL, BRUSH_REAR...)  : Tyre(; name=:RL, TYRE_SKIDPAD_REAR...)
    RR = brush ? BrushTyre(; name=:RR, BRUSH_REAR...)  : Tyre(; name=:RR, TYRE_SKIDPAD_REAR...)

    ps = @parameters m=m Izz=Izz Ixx=Ixx Iyy=Iyy a=a b=b tf=tf tr=tr h=h mf=mf mr=mr L=L M_s=M_s g=g Rw_f=Rw_f Rw_r=Rw_r Iw=Iw η=η final=final bias=bias Tbrake_max=Tbrake_max CdA=CdA ρair=ρair throttle=throttle0 brake=brake0 δ=steer0 gear=gear0 clutch=0.0 Ie=0.18 c_c=60.0 T_cap=500.0 k_idle=0.5 idle_rpm=2000.0 zrFL=0.0 zrFR=0.0 zrRL=0.0 zrRR=0.0 vrFL=0.0 vrFR=0.0 vrRL=0.0 vrRR=0.0 Fx_ext=0.0 Fy_ext=0.0 Mz_ext=0.0 CdA_scale=1.0
    # in-plane + powertrain states
    vplane = @variables u(t)=0.0 v(t)=0.0 r(t)=0.0 ωf(t)=0.0 ωr(t)=0.0 ωe(t)=209.4 ay(t) ax(t) az(t) rpm(t) X(t)=0.0 Y(t)=0.0 ψ(t)=0.0
    # vertical / attitude states (sprung): heave z, pitch th, roll ph + rates
    vatt = @variables z(t)=0.0 w(t)=0.0 th(t)=0.0 q(t)=0.0 ph(t)=0.0 pp(t)=0.0
    # unsprung vertical states (one per corner)
    vuns = @variables zuFL(t)=0.0 vuFL(t)=0.0 zuFR(t)=0.0 vuFR(t)=0.0 zuRL(t)=0.0 vuRL(t)=0.0 zuRR(t)=0.0 vuRR(t)=0.0
    vfz  = @variables FzFL(t) FzFR(t) FzRL(t) FzRR(t)     # tyre vertical loads (observed)
    vars = vcat(vplane, vatt, vuns, vfz)

    # CdA_scale (≤1 in a leading car's slipstream) makes DRAFT a real aero effect — reduced frontal
    # drag in the wake → the tow, not a forward velocity bump.  Fx_ext/Fy_ext/Mz_ext are body-frame
    # external force/moment input ports for the spring-damper CONTACT components (walls = stiff spring,
    # hedge/haybale = weak spring + strong damper): the game loop computes F = kδ + cδ̇ from penetration
    # and feeds it here, so the impulse is INTEGRATED by the ODE (no ad-hoc bumpX!).
    gr = gear*final; drag = 0.5*ρair*CdA*CdA_scale*u*abs(u)
    rr = 0.026*m*g*tanh(u/0.12)
    εF = 80.0                                             # contact/clamp rounding scale [N]

    #            tyre  xi    yi    steer axle  m_s              m_u              ks/cs/kt/ct          zu     vu     zr     vr     Fz
    spec = ((FL,  a,  tf/2,  δ, :f, front_corner, zuFL, vuFL, zrFL, vrFL, FzFL),
            (FR,  a, -tf/2,  δ, :f, front_corner, zuFR, vuFR, zrFR, vrFR, FzFR),
            (RL, -b,  tr/2,  0, :r, rear_corner,  zuRL, vuRL, zrRL, vrRL, FzRL),
            (RR, -b, -tr/2,  0, :r, rear_corner,  zuRR, vuRR, zrRR, vrRR, FzRR))

    eqs = Equation[]; Fyb=Any[]; Fxb=Any[]; Mz=Any[]; Fx_f=Any[]; Fx_r=Any[]
    Fsusp=Any[]; xs=Any[]; ys=Any[]
    for (ty, xi, yi, st, axle, cor, zu, vu, zr, vr, Fz) in spec
        Rw  = axle == :f ? Rw_f : Rw_r
        ωax = axle == :f ? ωf : ωr
        m_s_i = cor.m_s; m_u_i = cor.m_u
        P_s   = m_s_i*g                                   # static suspension preload
        Fz_static = (m_s_i + m_u_i)*g                     # static tyre load
        # sprung-mount vertical motion at this corner (small-angle): up = +
        z_mount = z + xi*th + yi*ph
        v_mount = w + xi*q  + yi*pp
        # suspension force (up on sprung, down on unsprung), preloaded, can't pull
        Fs = smoothpos(P_s + cor.ks*(zu - z_mount) + cor.cs*(vu - v_mount), εF)
        # tyre vertical load from ground contact (zr road input), can't pull
        push!(eqs, Fz ~ smoothpos(Fz_static + cor.kt*(zr - zu) + cor.ct*(vr - vu), εF))
        # unsprung vertical dynamics
        append!(eqs, [D(zu) ~ vu, m_u_i*D(vu) ~ Fz - Fs - m_u_i*g])
        push!(Fsusp, Fs); push!(xs, xi); push!(ys, yi)
        # ---- in-plane tyre kinematics (as in vehicle_rt) ----
        vx = u - r*yi;  vy = v + r*xi
        Vref = sqrt(vx^2 + 1.0)
        α = st - atan(vy, Vref);  κ = (ωax*Rw - vx)/Vref
        append!(eqs, [ty.Fz ~ Fz, ty.α ~ α, ty.κ ~ κ])
        fxb = ty.Fx*cos(st) - ty.Fy*sin(st)
        fyb = ty.Fx*sin(st) + ty.Fy*cos(st)
        push!(Fxb, fxb); push!(Fyb, fyb); push!(Mz, ty.Mz)
        axle == :f ? push!(Fx_f, ty.Fx) : push!(Fx_r, ty.Fx)
    end
    ΣFx = Fxb[1]+Fxb[2]+Fxb[3]+Fxb[4];  ΣFy = Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4]
    ΣFs = Fsusp[1]+Fsusp[2]+Fsusp[3]+Fsusp[4]

    # --- slipping clutch / launch (identical to DrivenVehicleRT) ---
    ωgb = ωr*gr
    engage = (1.0 - clutch) * clamp(gear/0.5, 0.0, 1.0)
    Tcl   = clamp(c_c*(ωe - ωgb), -T_cap*engage, T_cap*engage)
    Tidle = clamp(k_idle*max(0.0, idle_rpm - rpm), 0.0, 120.0) * (1.0 - engage)
    run   = clamp((rpm - 300.0)/150.0, 0.0, 1.0)

    push!(eqs,
        rpm ~ ωe*60/(2π),
        # ---- in-plane body (total mass m; Fz now load-transferred by the suspension) ----
        ax ~ (ΣFx - drag - rr + Fx_ext)/m,
        ay ~ (ΣFy + Fy_ext)/m,
        m*(D(u) - v*r) ~ ΣFx - drag - rr + Fx_ext,
        m*(D(v) + u*r) ~ ΣFy + Fy_ext,
        Izz*D(r) ~ a*(Fyb[1]+Fyb[2]) - b*(Fyb[3]+Fyb[4])
                   - tf/2*(Fxb[1]-Fxb[2]) - tr/2*(Fxb[3]-Fxb[4]) + Mz[1]+Mz[2]+Mz[3]+Mz[4] + Mz_ext,
        # ---- sprung body vertical / attitude (explicit gravity → can go airborne) ----
        D(z) ~ w,
        M_s*D(w) ~ ΣFs - M_s*g,
        az ~ D(w) + g,                                    # accelerometer specific force (≈ g static, 0 in free-fall)
        D(th) ~ q,
        Iyy*D(q) ~ (xs[1]*Fsusp[1]+xs[2]*Fsusp[2]+xs[3]*Fsusp[3]+xs[4]*Fsusp[4]) + h*ΣFx,   # pitch: susp + braking dive
        D(ph) ~ pp,
        Ixx*D(pp) ~ (ys[1]*Fsusp[1]+ys[2]*Fsusp[2]+ys[3]*Fsusp[3]+ys[4]*Fsusp[4]) + h*ΣFy,  # roll: susp + cornering
        # ---- powertrain (identical to DrivenVehicleRT) ----
        Ie*D(ωe) ~ (engine_torque(rpm, throttle) + Tidle)*run - (1.0 - run)*45.0*ωe - Tcl,
        2*Iw*D(ωf) ~ -brake*Tbrake_max*bias*tanh(ωf) - (Fx_f[1]+Fx_f[2])*Rw_f,
        2*Iw*D(ωr) ~ Tcl*gr*η - brake*Tbrake_max*(1-bias)*tanh(ωr) - (Fx_r[1]+Fx_r[2])*Rw_r,
        # ---- world pose for rendering ----
        D(X) ~ u*cos(ψ) - v*sin(ψ),
        D(Y) ~ u*sin(ψ) + v*cos(ψ),
        D(ψ) ~ r,
    )
    System(eqs, t, vars, ps; systems = [FL, FR, RL, RR], name)
end
