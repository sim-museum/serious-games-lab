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
        Rw_f = 0.30, Rw_r = 0.334, Iw = 1.0, η = 0.9, final = 4.11,
        # PO 2026-08-27: "the car physics should be determined entirely by the iracing ibt data,
        # there should be no modifiable parameters." JM_BRAKE_MAX / JM_BRAKE_BIAS were added here
        # earlier the same day and are REMOVED again: a tuning knob is precisely the thing that lets
        # the model drift away from the reference instead of being pinned to it.
        # These two are therefore constants, and the open question is not what they should be tuned
        # to but what the iRacing telemetry SAYS they are — see BENCHMARK_2026-06-24.md and
        # JuliaMotorMTK/tools/ibt_compare.jl.
        # BRAKE-1 (2026-10-03, PO: can't settle the car to trail-brake into the carousel): MEASURED from the
        # 261002 gold's steady straight-line braking. Pedal 0.5-0.7 gives 0.906 g with the FRONT tyres working
        # harder (rear/front slip 0.61); the sim gave 1.32 g with the REAR working harder (1.59-1.75), so the
        # rear saturated first and the car stepped out. iRacing's 53.5 % BrakeBias is a PRESSURE split (bigger
        # front brakes); applied here as a TORQUE split it put only 56 % of the braking force on the front.
        # Simulated stops fitted to both gold numbers: torque split 0.617 front, 2800 N·m at full pedal (was
        # 0.535 / 4200 -- the 4200 was raised by feel). Trail-braking from 250 km/h: max sideslip <= 2.6° at
        # every pedal (was a spin at pedal 0.6-0.8).
        # IRFIT-261004 BRAKE-2 (2026-10-04): refit with the tyre's longitudinal side and its sliding drop against
        # the 261004 steady-pedal stops (tools/brakefit_261004.jl): split 0.617 -> 0.585, 2800 -> 2956 N·m.
        bias = 0.585, Tbrake_max = 2956.0,
        CdA = CDA_IBT, ρair = 1.10, g = 9.80665,
        throttle0 = 0.0, brake0 = 0.0, steer0 = 0.0, gear0 = 1.72, brush = false,
        # PO: ct (tyre vertical DAMPING) was 300 ≈ 8% of critical for the unsprung mass → the car
        # "superball-bounced" on landing off a crest.  Raised to ~27% of critical so a jump landing is
        # absorbed (inelastic), not sprung back; mainly affects bumps/landings, not steady cornering.
        front_corner = (ks = 18_250.0, cs = 2500.0, m_s = 120.0, m_u = 20.0, kt = 180_000.0, ct = 1000.0),
        rear_corner  = (ks = 29_200.0, cs = 3000.0, m_s = 148.0, m_u = 20.0, kt = 200_000.0, ct = 1100.0),
        # E100-S4 (PO: "physics entirely from the ibt data"): spring rates are SESSION data, exactly
        # like the gearbox (E100) and the corner weights (E100-S2). The ibt carries a SpringRate per
        # corner and real setups are asymmetric -- the skidpad session runs LF 26 / RF 28 / LR 39 /
        # RR 53 N/mm against the Nordschleife's symmetric 30/30/48/48. Sharing one spec per axle,
        # as the four `spec` rows below did, cannot represent that at all, so the rates stayed
        # frozen to whichever session they were once copied from.
        # Each corner may now carry its own spec. Defaults keep the axle-shared behaviour exactly,
        # so a caller that passes nothing gets the previous model unchanged.
        fl_corner = front_corner, fr_corner = front_corner,
        rl_corner = rear_corner,  rr_corner = rear_corner,
        # WWSETUP-1 (2026-10-06): the setup quantities iRacing's garage exposes and the gold shows an effect of.
        # `diff = nothing` keeps the SPOOL (one rear wheel speed), which every pre-WWSETUP tool was fitted on.
        # `diff = (preload, drive_ramp, coast_ramp, plates)` [N·m, deg, deg, count] gives each rear wheel its
        # own speed, coupled by a ramp-type clutch-pack LSD (see below). `toe_f`/`toe_r` are toe-IN per wheel
        # [rad] (negative = toe-out), as the iRacing garage sets them.
        # `karb_f`/`karb_r`: the anti-roll bars, roll-only stiffness per axle [N/m] on top of the corner specs' (total
        # fitted to the gold's roll gradient: tools/arbfit_261005.jl).
        diff = nothing, toe_f = 0.0, toe_r = 0.0, karb_f = 0.0, karb_r = 0.0)
    L = a + b; mf = m*front_frac; mr = m*(1 - front_frac)
    M_s = fl_corner.m_s + fr_corner.m_s + rl_corner.m_s + rr_corner.m_s   # total sprung mass

    # brush=true ⇒ physics-based brush tyre (no fudge); else the Magic-Formula preset
    FL = brush ? BrushTyre(; name=:FL, BRUSH_FRONT...) : Tyre(; name=:FL, TYRE_SKIDPAD_FRONT...)
    FR = brush ? BrushTyre(; name=:FR, BRUSH_FRONT...) : Tyre(; name=:FR, TYRE_SKIDPAD_FRONT...)
    RL = brush ? BrushTyre(; name=:RL, BRUSH_REAR...)  : Tyre(; name=:RL, TYRE_SKIDPAD_REAR...)
    RR = brush ? BrushTyre(; name=:RR, BRUSH_REAR...)  : Tyre(; name=:RR, TYRE_SKIDPAD_REAR...)

    ps = @parameters m=m Izz=Izz Ixx=Ixx Iyy=Iyy a=a b=b tf=tf tr=tr h=h mf=mf mr=mr L=L M_s=M_s g=g Rw_f=Rw_f Rw_r=Rw_r Iw=Iw η=η final=final bias=bias Tbrake_max=Tbrake_max CdA=CdA ρair=ρair throttle=throttle0 brake=brake0 δ=steer0 gear=gear0 clutch=0.0 Ie=0.18 c_c=60.0 T_cap=500.0 k_idle=0.5 idle_rpm=2000.0 zrFL=0.0 zrFR=0.0 zrRL=0.0 zrRR=0.0 vrFL=0.0 vrFR=0.0 vrRL=0.0 vrRR=0.0 Fx_ext=0.0 Fy_ext=0.0 Mz_ext=0.0 CdA_scale=1.0 c_abl=C_ABL toe_f=toe_f toe_r=toe_r karb_f=karb_f karb_r=karb_r
    lsd = diff !== nothing
    if lsd
        lsd_ps = @parameters lsd_pre=diff[1] lsd_cotd=cotd(diff[2]) lsd_cotc=cotd(diff[3]) lsd_plates=diff[4] lsd_k=LSD_K lsd_weps=LSD_WEPS
        append!(ps, lsd_ps)
    end
    # in-plane + powertrain states
    # with an LSD the axle speed ωr is the MEAN of the two rear wheels (observed, so it must carry no start value)
    if lsd; @variables ωr(t); else; @variables ωr(t)=0.0; end
    vplane = [@variables(u(t)=0.0, v(t)=0.0, r(t)=0.0, ωf(t)=0.0)...; ωr; @variables ωe(t)=209.4 ωRL(t)=0.0 ωRR(t)=0.0 Tlsd(t) ay(t) ax(t) az(t) rpm(t) X(t)=0.0 Y(t)=0.0 ψ(t)=0.0]
    # vertical / attitude states (sprung): heave z, pitch th, roll ph + rates
    vatt = @variables z(t)=0.0 w(t)=0.0 th(t)=0.0 q(t)=0.0 ph(t)=0.0 pp(t)=0.0
    # unsprung vertical states (one per corner)
    vuns = @variables zuFL(t)=0.0 vuFL(t)=0.0 zuFR(t)=0.0 vuFR(t)=0.0 zuRL(t)=0.0 vuRL(t)=0.0 zuRR(t)=0.0 vuRR(t)=0.0
    vfz  = @variables FzFL(t) FzFR(t) FzRL(t) FzRR(t)     # tyre vertical loads (observed)
    lsd || (vplane = filter(x -> !any(isequal(x), (ωRL, ωRR, Tlsd)), vplane))
    vars = vcat(vplane, vatt, vuns, vfz)

    # CdA_scale (≤1 in a leading car's slipstream) makes DRAFT a real aero effect — reduced frontal
    # drag in the wake → the tow, not a forward velocity bump.  Fx_ext/Fy_ext/Mz_ext are body-frame
    # external force/moment input ports for the spring-damper CONTACT components (walls = stiff spring,
    # hedge/haybale = weak spring + strong damper): the game loop computes F = kδ + cδ̇ from penetration
    # and feeds it here, so the impulse is INTEGRATED by the ODE (no ad-hoc bumpX!).
    gr = gear*final; drag = 0.5*ρair*CdA*CdA_scale*u*abs(u)
    rr = CRR_IBT*m*g*tanh(u/0.12)                       # E91-S10: CdA/Crr from the ibt coast-downs (powertrain.jl)
    εF = 80.0                                             # contact/clamp rounding scale [N]

    #            tyre  xi    yi    steer axle  m_s              m_u              ks/cs/kt/ct          zu     vu     zr     vr     Fz
    # toe-in turns each wheel toward the centreline: the LEFT wheel (+y) steers right (−), the right one left (+)
    spec = ((FL,  a,  tf/2,  δ - toe_f, :f, fl_corner, zuFL, vuFL, zrFL, vrFL, FzFL),
            (FR,  a, -tf/2,  δ + toe_f, :f, fr_corner, zuFR, vuFR, zrFR, vrFR, FzFR),
            (RL, -b,  tr/2,     -toe_r, :r, rl_corner, zuRL, vuRL, zrRL, vrRL, FzRL),
            (RR, -b, -tr/2,      toe_r, :r, rr_corner, zuRR, vuRR, zrRR, vrRR, FzRR))

    eqs = Equation[]; Fyb=Any[]; Fxb=Any[]; Mz=Any[]; Fx_f=Any[]; Fx_r=Any[]; Pslip=Any[]
    Fsusp=Any[]; xs=Any[]; ys=Any[]
    # IRFIT-261004 SUSP-1: suspension compression per corner (wheel up relative to its body mount), for the
    # anti-roll coupling between the two corners of an axle (karb, roll-only: zero in heave and pitch).
    comp = [s[7] - (z + s[2]*th + s[3]*ph) for s in spec]
    karb(c) = hasproperty(c, :karb) ? c.karb : 0.0
    for (idx, (ty, xi, yi, st, axle, cor, zu, vu, zr, vr, Fz)) in enumerate(spec)
        pidx = isodd(idx) ? idx + 1 : idx - 1                 # the other corner of this axle
        kab = 0.5*(karb(cor) + karb(spec[pidx][6])) + (axle == :f ? karb_f : karb_r)
        Rw  = axle == :f ? Rw_f : Rw_r
        ωax = axle == :f ? ωf : !lsd ? ωr : idx == 3 ? ωRL : ωRR
        m_s_i = cor.m_s; m_u_i = cor.m_u
        P_s   = m_s_i*g                                   # static suspension preload
        Fz_static = (m_s_i + m_u_i)*g                     # static tyre load
        # sprung-mount vertical motion at this corner (small-angle): up = +
        z_mount = z + xi*th + yi*ph
        v_mount = w + xi*q  + yi*pp
        # suspension force (up on sprung, down on unsprung), preloaded, can't pull. SUSP-1: bump/rebound damping
        # (measured) when the corner spec carries them, blended smoothly through zero velocity; + anti-roll coupling.
        vrel = vu - v_mount
        cdmp = hasproperty(cor, :cb) ? cor.cr + (cor.cb - cor.cr)*0.5*(1 + tanh(vrel/0.01)) : cor.cs
        Fs = smoothpos(P_s + cor.ks*(zu - z_mount) + cdmp*vrel + kab*(comp[idx] - comp[pidx]), εF)
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
        push!(Pslip, sqrt((ty.Fy*sin(α))^2 + 1.0))       # |Fy·sinα| (smooth at 0): the brush's slip projection
        axle == :f ? push!(Fx_f, ty.Fx) : push!(Fx_r, ty.Fx)
    end
    # TYRE-1 (2026-10-03): ABLATION. The PO, after Kaemmer: the tyre does not interact elastically with the
    # road, it ablates, and that absorbs energy in a corner. Measured on the 261002 gold: steady cornering
    # coasts lose MORE speed than the brush's own slip projection Σ|Fy|·sin|α| accounts for (P = 0.008,
    # tools/tyrefit_261002.jl). The excess is a drag on the body, like rolling resistance, scaling with the
    # slip work: c_abl·Σ|Fy·sinα|; c_abl (brush_tyre.jl C_ABL) is identified against the gold's scrub.
    abl = c_abl*(Pslip[1] + Pslip[2] + Pslip[3] + Pslip[4] - 4.0)*tanh(u/0.12)
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
        ax ~ (ΣFx - drag - rr - abl + Fx_ext)/m,
        ay ~ (ΣFy + Fy_ext)/m,
        m*(D(u) - v*r) ~ ΣFx - drag - rr - abl + Fx_ext,
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
        # ---- world pose for rendering ----
        D(X) ~ u*cos(ψ) - v*sin(ψ),
        D(Y) ~ u*sin(ψ) + v*cos(ψ),
        D(ψ) ~ r,
    )
    if !lsd
        push!(eqs, 2*Iw*D(ωr) ~ Tcl*gr*η - brake*Tbrake_max*(1-bias)*tanh(ωr) - (Fx_r[1]+Fx_r[2])*Rw_r)
    else
        # WWSETUP-1 LSD: a ramp-type (Salisbury) clutch-pack diff. The input torque Tin = Tcl·gr·η splits equally,
        # as in an open diff; the clutch packs then pass torque Tlsd from the faster half-shaft to the slower one,
        # up to their capacity Tcap = preload + k·plates·cot(ramp)·|Tin| -- the ramp's wedge loads the packs in
        # proportion to the torque through it, and a STEEPER ramp wedges less (cot 75° = 0.27, cot 35° = 1.43).
        # The drive ramp acts under power, the coast ramp under engine braking (blended through Tin = 0).
        # Below capacity the packs stick and both wheels turn together; the tanh is that stick-slip, regularised
        # over ωε (the solver is implicit, so the stiff locked branch is safe at the 1/300 s step).
        # k (LSD_K, powertrain.jl) is the one constant the garage does not give -- friction faces × μ × the
        # ramp/clutch radius ratio -- and is identified from the gold's rear wheel-speed split
        # (tools/lsdfit_261005.jl), with BOTH setups' ramps on the same k.
        Tin  = Tcl*gr*η
        wdr  = 0.5*(1 + tanh(Tin/10.0))
        Tcap = lsd_pre + lsd_k*lsd_plates*(wdr*lsd_cotd + (1 - wdr)*lsd_cotc)*sqrt(Tin^2 + 1.0)
        append!(eqs, [
            Tlsd ~ Tcap*tanh((ωRR - ωRL)/lsd_weps),                       # >0: RR faster, torque passes to RL
            Iw*D(ωRL) ~ Tin/2 + Tlsd/2 - brake*Tbrake_max*(1-bias)/2*tanh(ωRL) - Fx_r[1]*Rw_r,
            Iw*D(ωRR) ~ Tin/2 - Tlsd/2 - brake*Tbrake_max*(1-bias)/2*tanh(ωRR) - Fx_r[2]*Rw_r,
            ωr ~ (ωRL + ωRR)/2,
        ])
    end
    System(eqs, t, vars, ps; systems = [FL, FR, RL, RR], name)
end
