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
        m = 617.0, Izz = nothing, Ixx = 120.0, Iyy = 850.0,
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
        # CARPHYS-1 S6: `bias`/`Tbrake_max` are now the fitted torque split and total AT THE REFERENCE 53.5 % pressure bias;
        # the session's own garage bias is `brake_bias_p` (pressure fraction), applied by the BrakeSystem object.
        brake_bias_p = 0.535,
        # CARPHYS-1 S7: per corner (FL FR RL RR) the wheel travel to the bump stop and to full droop [m] (TravelStops);
        # `nothing` = unlimited travel (the model before S7). `k_stop` [N/m] the stops' stiffness at the wheel.
        # Stiffnesses chosen on the gold's Flugplatz passes (tools/crestval_261004.jl): bump 500 kN/m, top-out 20 kN/m
        # (a stiff top-out yanks the body down at every take-off: crest dip −0.5 g vs the gold's −0.1).
        travel = nothing, k_stop = 5e5, k_stop_reb = 2e4,
        # CARPHYS-1 S11: tyre relaxation lengths (σ front, σ rear) [m] (TyreRelaxation); `nothing` = the force follows the
        # kinematic slip at once (the model before S11). σ is a parameter of each rxFL..rxRR, settable without a rebuild.
        relax = nothing,
        # IRGOLD-1 S2: `front_hubs = true` gives each front wheel its own rotation (the real car's free front hubs). Before,
        # one ωf drove both front wheels like a SPOOL: in a corner the inside and outside fronts were forced to one
        # speed, so their slip differed by ±(r·tf/2)/u and the pair made opposing Fx -- a yaw-resisting moment (understeer)
        # that grows as the radius shrinks (±0.8 % slip on the skidpad, ±5 % in a 15 m hairpin). States: ωf stays (the
        # axle MEAN, so every caller that sets it still works) plus ωfd, the half-difference: ωFL = ωf + ωfd,
        # ωFR = ωf − ωfd. `false` = the spool (the model before IRGOLD-1 S2).
        front_hubs = false,
        # IRGOLD-1 / FUEL-1: the fuel tank's position [m ahead of the CG] (FuelTank, chassis_parts.jl); the fuel in the
        # tank at build time is in `m`, `front_frac` and the corner masses already, the burnt part leaves through tank.dm
        tank_x = 0.5,
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
        # CAMBER-1 (2026-10-06): `camber = (FL, FR, RL, RR)` static camber [rad] in the GARAGE's convention (negative =
        # top leaning toward the car), `rc = (front, rear)` roll camber; `nothing` keeps the upright tyre (brush only).
        diff = nothing, toe_f = 0.0, toe_r = 0.0, karb_f = 0.0, karb_r = 0.0, camber = nothing, rc = CAMBER_RC)
    L = a + b; mf = m*front_frac; mr = m*(1 - front_frac)
    M_s = fl_corner.m_s + fr_corner.m_s + rl_corner.m_s + rr_corner.m_s   # total sprung mass

    # brush=true ⇒ physics-based brush tyre (no fudge); else the Magic-Formula preset
    cmb = brush && camber !== nothing
    # CAMBER-1 / TYRE-2: the camber tyre's lateral side is its own fit (TYRE2): the upright μ (the upright model's already
    # carries the lean loss) and the cornering stiffness refitted with camber, the LSD and the bars in the car
    # IRGOLD-1 S3: TYRE3 (shape nsh, kμ, ablation too) unless JM_TYRE2
    bf = !cmb ? BRUSH_FRONT : USE_TYRE3 ? merge(BRUSH_FRONT, (μ = TYRE3.μf*_GRIP, Cα = TYRE3.Cαf, kμ = TYRE3.kμ)) :
                                          merge(BRUSH_FRONT, (μ = TYRE2.μf*_GRIP, Cα = TYRE2.Cαf))
    br = !cmb ? BRUSH_REAR  : USE_TYRE3 ? merge(BRUSH_REAR,  (μ = TYRE3.μr*_GRIP, Cα = TYRE3.Cαr, kμ = TYRE3.kμ)) :
                                          merge(BRUSH_REAR,  (μ = TYRE2.μr*_GRIP, Cα = TYRE2.Cαr))
    nshf = cmb && USE_TYRE3 ? TYRE3.nshf : 3.0; nshr = cmb && USE_TYRE3 ? TYRE3.nshr : 3.0
    # IRGOLD-1 S3: free front hubs go WITH the tyre refitted with them (TYRE3, the session car's camber tyre). A car built
    # without a session setup carries the upright TYRE-1 tyre, which was fitted with the spool, and keeps the spool:
    # hubs + TYRE-1 spins at 8.6° of lock at 90 km/h (tyrepanel_smoke's control), the pairing the old fit never saw.
    front_hubs = front_hubs && cmb && USE_TYRE3
    # IRGOLD-1 S4: the yaw inertia identified on the PO's 261011 flicks and weaves (handling J by Izz 690/890/990/1090/1290 =
    # 0.2605/0.2353/0.2320/0.2321/0.2437: a minimum near 1,040 kg·m²) -- for the session car it was fitted on; 890 (hand-set)
    # for a setup-less car. An explicit Izz wins.
    Izz = Izz !== nothing ? Izz : cmb && USE_TYRE3 ? 1040.0 : 890.0
    kinF = brush && relax !== nothing && COLUMN_KIN         # IRGOLD-1 S5: the column reads the front force at the kinematic slip
    FL = brush ? BrushTyre(; name=:FL, bf..., camber=cmb, nsh=nshf, kin=kinF) : Tyre(; name=:FL, TYRE_SKIDPAD_FRONT...)
    FR = brush ? BrushTyre(; name=:FR, bf..., camber=cmb, nsh=nshf, kin=kinF) : Tyre(; name=:FR, TYRE_SKIDPAD_FRONT...)
    RL = brush ? BrushTyre(; name=:RL, br...,  camber=cmb, nsh=nshr) : Tyre(; name=:RL, TYRE_SKIDPAD_REAR...)
    RR = brush ? BrushTyre(; name=:RR, br...,  camber=cmb, nsh=nshr) : Tyre(; name=:RR, TYRE_SKIDPAD_REAR...)

    gv, kfv, krv = g, karb_f, karb_r                     # numeric values for the parts' own parameters (the next line rebinds the names)
    ps = @parameters m=m Izz=Izz Ixx=Ixx Iyy=Iyy a=a b=b tf=tf tr=tr h=h mf=mf mr=mr L=L M_s=M_s g=g Rw_f=Rw_f Rw_r=Rw_r Iw=Iw η=η final=final bias=bias Tbrake_max=Tbrake_max CdA=CdA ρair=ρair throttle=throttle0 brake=brake0 δ=steer0 gear=gear0 clutch=0.0 hrc_f=0.0 hrc_r=0.0 antistall=0.0 as_r0=1957.0 as_k=495.0 as_w=490.0 Ie=(ENGINE_LUMPED ? 0.18 : IE_ENGINE) Igb=(ENGINE_LUMPED ? 0.0 : DRIVELINE_INPUT ? 0.18 - IE_ENGINE : IE_DRIVELINE) c_c=60.0 T_cap=500.0 k_idle=0.5 idle_rpm=2000.0 zrFL=0.0 zrFR=0.0 zrRL=0.0 zrRR=0.0 vrFL=0.0 vrFR=0.0 vrRL=0.0 vrRR=0.0 Fx_ext=0.0 Fy_ext=0.0 Mz_ext=0.0 CdA_scale=1.0 c_abl=(cmb && USE_TYRE3 ? TYRE3.cabl : C_ABL) toe_f=toe_f toe_r=toe_r karb_f=karb_f karb_r=karb_r
    brk = BrakeSystem(; name = :brk, bias_p = brake_bias_p)   # CARPHYS-1 S6 (chassis_parts.jl)
    tank = FuelTank(; name = :tank, x = tank_x)               # IRGOLD-1 / FUEL-1
    if cmb
        append!(ps, @parameters camFL=camber[1] camFR=camber[2] camRL=camber[3] camRR=camber[4] rc_f=rc[1] rc_r=rc[2])
    end
    lsd = diff !== nothing
    if lsd
        lsd_ps = @parameters lsd_pre=diff[1] lsd_cotd=cotd(diff[2]) lsd_cotc=cotd(diff[3]) lsd_plates=diff[4] lsd_k=LSD_K lsd_weps=LSD_WEPS
        append!(ps, lsd_ps)
    end
    # in-plane + powertrain states
    # with an LSD the axle speed ωr is the MEAN of the two rear wheels (observed, so it must carry no start value)
    if lsd; @variables ωr(t); else; @variables ωr(t)=0.0; end
    vplane = [@variables(u(t)=0.0, v(t)=0.0, r(t)=0.0, ωf(t)=0.0)...; ωr; (front_hubs ? @variables(ωfd(t)=0.0) : [])...; @variables ωe(t)=209.4 ωRL(t)=0.0 ωRR(t)=0.0 Tlsd(t) ay(t) ax(t) az(t) rpm(t) X(t)=0.0 Y(t)=0.0 ψ(t)=0.0]
    # vertical / attitude states (sprung): heave z, pitch th, roll ph + rates
    vatt = @variables z(t)=0.0 w(t)=0.0 th(t)=0.0 q(t)=0.0 ph(t)=0.0 pp(t)=0.0
    vfz  = @variables FzFL(t) FzFR(t) FzRL(t) FzRR(t)     # tyre vertical loads (observed)
    lsd || (vplane = filter(x -> !any(isequal(x), (ωRL, ωRR, Tlsd)), vplane))
    vars = vcat(vplane, vatt, vfz)

    # CdA_scale (≤1 in a leading car's slipstream) makes DRAFT a real aero effect — reduced frontal
    # drag in the wake → the tow, not a forward velocity bump.  Fx_ext/Fy_ext/Mz_ext are body-frame
    # external force/moment input ports for the spring-damper CONTACT components (walls = stiff spring,
    # hedge/haybale = weak spring + strong damper): the game loop computes F = kδ + cδ̇ from penetration
    # and feeds it here, so the impulse is INTEGRATED by the ODE (no ad-hoc bumpX!).
    gr = gear*final; drag = 0.5*ρair*CdA*CdA_scale*u*abs(u)
    # the car's mass now: the fuel burnt since the build has left it. The tank's PARAMETER, not its observed `dm`: a mass
    # coefficient that depends on a variable makes MTK keep a mass matrix, and the integrator then re-initialised every
    # outside state edit away (a teleport snapped back to the spawn on the next step -- netcollide_smoke, IRGOLD-1 S2)
    mc = m - tank.m_burn
    rr = CRR_IBT*mc*g*tanh(u/0.12)                      # E91-S10: CdA/Crr from the ibt coast-downs (powertrain.jl)
    εF = 80.0                                             # contact/clamp rounding scale [N]

    #            tyre  xi    yi    steer axle  corner spec  zr    vr    Fz    key
    # toe-in turns each wheel toward the centreline: the LEFT wheel (+y) steers right (−), the right one left (+)
    spec = ((FL,  a,  tf/2,  δ - toe_f, :f, fl_corner, zrFL, vrFL, FzFL, :FL),
            (FR,  a, -tf/2,  δ + toe_f, :f, fr_corner, zrFR, vrFR, FzFR, :FR),
            (RL, -b,  tr/2,     -toe_r, :r, rl_corner, zrRL, vrRL, FzRL, :RL),
            (RR, -b, -tr/2,      toe_r, :r, rr_corner, zrRR, vrRR, FzRR, :RR))

    # ---- CARPHYS-1: the vertical load path as objects (chassis_parts.jl) ----
    # per corner: the body MOUNT (a point of the sprung body), the COIL-OVER, the WHEEL (unsprung mass), the tyre's
    # VERTICAL carcass and the ROAD under it; per axle one ANTI-ROLL BAR. The mounts and roads are flanges whose motion
    # this model prescribes (the body's heave/pitch/roll, the adapter's road input); the parts are joined by connect().
    karb(c) = hasproperty(c, :karb) ? c.karb : 0.0
    mount, road, wheel, strut, tyrev, arb, stops, rcl = quiet_flanges() do        # (MTK's false flange warning, chassis_parts.jl)
    mount = [PrescribedMotion(; name = Symbol(:m, s[10])) for s in spec]
    road  = [PrescribedMotion(; name = Symbol(:r, s[10])) for s in spec]
    wheel = [WheelMass(; name = Symbol(:w, s[10]), m_u = s[6].m_u, g = gv) for s in spec]
    strut = [CoilOver(; name = Symbol(:s, s[10]), ks = s[6].ks, P = s[6].m_s*gv, cs = s[6].cs,
                      cb = hasproperty(s[6], :cb) ? s[6].cb : NaN, cr = hasproperty(s[6], :cr) ? s[6].cr : NaN,
                      clo = hasproperty(s[6], :clo) ? s[6].clo : 1.0, vk = hasproperty(s[6], :vk) ? s[6].vk : 0.10, ε = εF)
             for s in spec]
    tyrev = [TyreVertical(; name = Symbol(:tv, s[10]), kt = s[6].kt, ct = s[6].ct, Fz_static = (s[6].m_s + s[6].m_u)*gv, ε = εF)
             for s in spec]
    # each bar: the IRFIT-261004 corner share (the rear's motion-ratio roll term, see drive_rt3d.jl _karb_r) + the
    # setup's bar (WWSETUP-1 karb_f / karb_r, from the garage's ArbDiameter/ArbArms through ARB_ID)
    arb = [AntiRollBar(; name = :arbF, k = 0.5*(karb(fl_corner) + karb(fr_corner)) + kfv),
           AntiRollBar(; name = :arbR, k = 0.5*(karb(rl_corner) + karb(rr_corner)) + krv)]
    rcl = [RollCentreLink(; name = Symbol(:rc, s[10])) for s in spec]   # IRGOLD-1 S18: the links' load transfer per corner
    stops = travel === nothing ? nothing :
        [TravelStops(; name = Symbol(:ts, s[10]), c_bump = travel[i][1], c_reb = travel[i][2], k = k_stop, kr = k_stop_reb) for (i, s) in enumerate(spec)]
    (mount, road, wheel, strut, tyrev, arb, stops, rcl)
    end

    rlx = relax === nothing ? nothing :
        [TyreRelaxation(; name = Symbol(:rx, k), σ = (k in ("FL", "FR") ? relax[1] : relax[2])) for k in ("FL", "FR", "RL", "RR")]
    eqs = Equation[]; Fyb=Any[]; Fxb=Any[]; Mz=Any[]; Fx_f=Any[]; Fx_r=Any[]; Pslip=Any[]
    Fsusp=Any[]; xs=Any[]; ys=Any[]
    for (idx, (ty, xi, yi, st, axle, cor, zr, vr, Fz, key)) in enumerate(spec)
        pidx = isodd(idx) ? idx + 1 : idx - 1                 # the other corner of this axle
        bar = arb[axle == :f ? 1 : 2]; left = isodd(idx)
        Rw  = axle == :f ? Rw_f : Rw_r
        ωax = axle == :f ? (!front_hubs ? ωf : idx == 1 ? ωf + ωfd : ωf - ωfd) : !lsd ? ωr : idx == 3 ? ωRL : ωRR
        mt, rd, wh, so, tv = mount[idx], road[idx], wheel[idx], strut[idx], tyrev[idx]
        zu = wh.zu
        append!(eqs, [
            mt.s ~ z + xi*th + yi*ph,                         # the sprung body's point above this wheel (small-angle, up +)
            mt.v ~ w + xi*q  + yi*pp,
            rd.s ~ zr, rd.v ~ vr,                             # the road under it (adapter input)
            (stops === nothing ? connect(mt.fl, so.a, left ? bar.mL : bar.mR, rcl[idx].a) :
                                 connect(mt.fl, so.a, left ? bar.mL : bar.mR, stops[idx].a, rcl[idx].a)),
            (stops === nothing ? connect(so.b, wh.fl, tv.a, left ? bar.wL : bar.wR, rcl[idx].b) :
                                 connect(so.b, wh.fl, tv.a, left ? bar.wL : bar.wR, stops[idx].b, rcl[idx].b)),
            connect(tv.b, rd.fl),
            so.Fbar ~ (left ? bar.FL : bar.FR),
            Fz ~ tv.Fz])
        push!(Fsusp, mt.f); push!(xs, xi); push!(ys, yi)
        # ---- in-plane tyre kinematics (as in vehicle_rt) ----
        vx = u - r*yi;  vy = v + r*xi
        Vref = sqrt(vx^2 + 1.0)
        α = st - atan(vy, Vref);  κ = (ωax*Rw - vx)/Vref
        if rlx === nothing
            append!(eqs, [ty.Fz ~ Fz, ty.α ~ α, ty.κ ~ κ])
        else                                                  # CARPHYS-1 S11: the tyre sees the relaxed slip
            append!(eqs, [ty.Fz ~ Fz, rlx[idx].α_in ~ α, rlx[idx].V ~ Vref, ty.α ~ rlx[idx].α, ty.κ ~ κ])
            kinF && idx <= 2 && push!(eqs, ty.αk ~ α)                 # the kinematic slip for the column's force
        end
        if cmb
            # CAMBER-1: inclination to the road, + = top toward +y (the tyre's thrust side). The garage's camber is
            # negative top-in, so the left wheel's static lean is +cam and the right's −cam. The SUSPENSION roll --
            # the body's roll ph less the axle's own (unsprung heights, so a banked road is not read as roll; ph > 0
            # lifts the left side and tips the tops toward −y) -- tilts the wheel by rc of it (1 = the wheel leans
            # with the body as on equal parallel wishbones, 0 = it stays upright to the road).
            camst = (camFL, -camFR, camRL, -camRR)[idx]
            zuo = wheel[pidx].zu; trk = axle == :f ? tf : tr
            φs = ph - (isodd(idx) ? zu - zuo : zuo - zu)/trk
            push!(eqs, ty.γ ~ camst - (axle == :f ? rc_f : rc_r)*φs)
        end
        fxb = ty.Fx*cos(st) - ty.Fy*sin(st)
        fyb = ty.Fx*sin(st) + ty.Fy*cos(st)
        push!(Fxb, fxb); push!(Fyb, fyb); push!(Mz, ty.Mz)
        push!(Pslip, sqrt((ty.Fy*sin(α))^2 + 1.0))       # |Fy·sinα| (smooth at 0): the brush's slip projection
        axle == :f ? push!(Fx_f, ty.Fx) : push!(Fx_r, ty.Fx)
    end
    # IRGOLD-1 S18: roll centres. An axle's lateral force F_y (+y = left) moves F_y·h_rc/track from the left (+y) wheel to
    # the right one through the links: the right link pushes (F > 0), the left pulls. hrc_f = hrc_r = 0: no link load.
    append!(eqs, [rcl[1].F ~ -(Fyb[1] + Fyb[2])*hrc_f/tf, rcl[2].F ~ (Fyb[1] + Fyb[2])*hrc_f/tf,
                  rcl[3].F ~ -(Fyb[3] + Fyb[4])*hrc_r/tr, rcl[4].F ~ (Fyb[3] + Fyb[4])*hrc_r/tr])
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
    # IRGOLD-1 S15: iRacing's ANTI-STALL clutch. In the gold the driver's pedal (ClutchRaw) is out further than the clutch's
    # actual engagement (Clutch) in 81 % of all partly-engaged in-gear rows: standing in gear with the pedal released the
    # engagement is 0 and the engine idles at 1,800-2,000 rpm; in a full-throttle launch it holds ~0.40 with the engine at
    # ~1,550-1,700 (261012/tools/antistall.py). The sim limits the engagement to emax = clamp((rpm − (as_r0 − as_k·throttle))
    # /as_w): at zero throttle it closes just below the 2,000 rpm idle (no stall, ~no creep) and falls with throttle so a
    # launch can load the engine down to ~1,600. Fitted (tools/antistall_fit_261012.jl) on the 34 IRTEST-261012 launches
    # driven by the RAW pedal: as_r0 1957, as_k 495, as_w 490 -> mean |Δv| at 1/2/3 s 0.55 m/s (iRacing's own engagement
    # fed instead: 0.90; the pedal without anti-stall: 1.4+). `antistall` = 1 on the game's cars (DriveRT3D.ANTISTALL); 0 where a tool
    # feeds iRacing's resulting engagement (which already contains it).
    epedal = (1.0 - clutch) * clamp(gear/0.5, 0.0, 1.0)
    emax   = clamp((ωe*60/(2π) - (as_r0 - as_k*throttle))/as_w, 0.0, 1.0)
    engage = epedal - antistall*max(0.0, epedal - emax)
    clu = Clutch(; name = :clu)                            # CARPHYS-1 S9: the measured bite point (chassis_parts.jl)
    append!(eqs, [clu.engage ~ engage, clu.slip ~ ωe - ωgb])
    Tcl   = clu.T
    # IRGOLD-1 S14: the engine alone on the crank (Ie 0.052, its own drag); the driveline behind the gearbox carries Igb
    # (at the rear axle Igb·final²·η, in every gear) and the gearbox takes the rest of the in-gear coast drag, `Tgd` at its
    # input shaft, while the clutch is in (`engage`: so a clutch-out coast keeps the E91 road load it was fitted with).
    # JM_ENGINE_LUMPED=1 builds the lumped engine of before (Ie 0.18 at the crank, EFRIC drag on it).
    Teng  = ENGINE_LUMPED ? engine_torque(rpm, throttle) : engine_torque_free(rpm, throttle)
    Tgd   = ENGINE_LUMPED ? 0.0 : engage*gearbox_drag(ωgb*60/(2π), throttle)
    Tidle = clamp(k_idle*max(0.0, idle_rpm - rpm), 0.0, 120.0) * (1.0 - engage)
    run   = clamp((rpm - 300.0)/150.0, 0.0, 1.0)

    push!(eqs,
        rpm ~ ωe*60/(2π),
        # ---- in-plane body (total mass m; Fz now load-transferred by the suspension) ----
        ax ~ (ΣFx - drag - rr - abl + Fx_ext)/mc,
        ay ~ (ΣFy + Fy_ext)/mc,
        mc*(D(u) - v*r) ~ ΣFx - drag - rr - abl + Fx_ext,
        mc*(D(v) + u*r) ~ ΣFy + Fy_ext,
        Izz*D(r) ~ a*(Fyb[1]+Fyb[2]) - b*(Fyb[3]+Fyb[4])
                   - tf/2*(Fxb[1]-Fxb[2]) - tr/2*(Fxb[3]-Fxb[4]) + Mz[1]+Mz[2]+Mz[3]+Mz[4] + Mz_ext,
        # ---- sprung body vertical / attitude (explicit gravity → can go airborne) ----
        D(z) ~ w,
        (M_s - tank.m_burn)*D(w) ~ ΣFs - (M_s - tank.m_burn)*g,     # FUEL-1: burnt fuel no longer weighs on the springs
        az ~ D(w) + g,                                    # accelerometer specific force (≈ g static, 0 in free-fall)
        D(th) ~ q,
        Iyy*D(q) ~ (xs[1]*Fsusp[1]+xs[2]*Fsusp[2]+xs[3]*Fsusp[3]+xs[4]*Fsusp[4]) + h*ΣFx + tank.m_burn*g*tank.x,   # pitch: susp + braking dive (+ FUEL-1: the burnt fuel's weight gone at the tank)
        D(ph) ~ pp,
        Ixx*D(pp) ~ (ys[1]*Fsusp[1]+ys[2]*Fsusp[2]+ys[3]*Fsusp[3]+ys[4]*Fsusp[4]) + h*ΣFy,  # roll: susp + cornering
        # ---- powertrain (identical to DrivenVehicleRT) ----
        Ie*D(ωe) ~ (Teng + Tidle)*run - (1.0 - run)*45.0*ωe - Tcl,
        (front_hubs ? 2*Iw*D(ωf) ~ -brk.TF/2*(tanh(ωf + ωfd) + tanh(ωf - ωfd)) - (Fx_f[1]+Fx_f[2])*Rw_f :
                      2*Iw*D(ωf) ~ -brk.TF*tanh(ωf) - (Fx_f[1]+Fx_f[2])*Rw_f),
        # ---- world pose for rendering ----
        D(X) ~ u*cos(ψ) - v*sin(ψ),
        D(Y) ~ u*sin(ψ) + v*cos(ψ),
        D(ψ) ~ r,
    )
    front_hubs && push!(eqs, 2*Iw*D(ωfd) ~ -brk.TF/2*(tanh(ωf + ωfd) - tanh(ωf - ωfd)) - (Fx_f[1]-Fx_f[2])*Rw_f)
    if !lsd
        push!(eqs, (2*Iw + Igb*(DRIVELINE_INPUT ? gr : final)^2*η)*D(ωr) ~ (Tcl - Tgd)*gr*η - brk.TR*tanh(ωr) - (Fx_r[1]+Fx_r[2])*Rw_r)
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
        Tin  = (Tcl - Tgd)*gr*η
        Igr  = Igb*(DRIVELINE_INPUT ? gr : final)^2*η/4                 # S14: the driveline's inertia at the carrier, ¼ in each half-shaft's row
        RLt  = Tin/2 + Tlsd/2 - brk.TR/2*tanh(ωRL) - Fx_r[1]*Rw_r
        RRt  = Tin/2 - Tlsd/2 - brk.TR/2*tanh(ωRR) - Fx_r[2]*Rw_r
        wdr  = 0.5*(1 + tanh(Tin/10.0))
        Tcap = lsd_pre + lsd_k*lsd_plates*(wdr*lsd_cotd + (1 - wdr)*lsd_cotc)*sqrt(Tin^2 + 1.0)
        append!(eqs, [
            Tlsd ~ Tcap*tanh((ωRR - ωRL)/lsd_weps),                       # >0: RR faster, torque passes to RL
            D(ωRL) ~ ((Iw + Igr)*RLt - Igr*RRt)/(Iw*(Iw + 2*Igr)),          # [Iw+Igr Igr; Igr Iw+Igr]·ω̇ = torques, solved
            D(ωRR) ~ ((Iw + Igr)*RRt - Igr*RLt)/(Iw*(Iw + 2*Igr)),          # explicitly (a coupled form keeps a mass matrix)
            ωr ~ (ωRL + ωRR)/2,
        ])
    end
    # CARPHYS-1 S5: the rim torque (force feedback), chassis_parts.jl; IRGOLD-1 S5: with the trail law on the session car
    col = kinF ? SteeringColumn(; name = :col, trail = COLUMN_TRAIL[1], tp = COLUMN_TRAIL[2]) : SteeringColumn(; name = :col)
    push!(eqs, col.Fy ~ (kinF ? FL.Fyk + FR.Fyk : FL.Fy + FR.Fy))
    push!(eqs, col.ξ ~ (kinF ? 0.5*(FL.ξk + FR.ξk) : brush ? 0.5*(FL.ξ + FR.ξ) : 1.0))
    append!(eqs, [brk.pedal ~ brake,                       # CARPHYS-1 S6: the brake system object; its calipers from the fit
                  brk.kF ~ Tbrake_max*bias/(brk.P_full*0.535), brk.kR ~ Tbrake_max*(1 - bias)/(brk.P_full*(1 - 0.535))])
    System(eqs, t, vars, ps; systems = [FL, FR, RL, RR, mount..., road..., wheel..., strut..., tyrev..., arb..., col, brk, clu, tank, (stops === nothing ? [] : stops)...,
                                        (rlx === nothing ? [] : rlx)..., rcl...], name)
end
