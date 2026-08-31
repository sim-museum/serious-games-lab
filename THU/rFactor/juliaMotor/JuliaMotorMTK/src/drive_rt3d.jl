# Real-time adapter for the FULL-3D vehicle (DrivenVehicle3D) — the 3-D analogue
# of drive_rt.jl.  Same live-input stepping + world placement, PLUS it samples the
# track under each wheel to drive the suspension, so the car pitches, rolls, and
# JUMPS on real terrain, and exposes genuine VertAccel / ride heights / pitch /
# roll for telemetry (the planar adapter stubbed these).
#
# Ground reference: each wheel's road input is its terrain height minus a slowly-
# tracked reference `zref` (follows terrain at the suspension settling rate).  On
# gentle ground zref keeps up → road input ≈ 0 → static load; over a SHARP crest
# zref lags → wheels unload (Fz→0) → the car goes airborne, then lands.

module DriveRT3D

using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t, D_nounits as D
const setp = ModelingToolkit.setp

const HERE = @__DIR__
for f in ("tyre.jl","powertrain.jl","vehicle_3d.jl")
    include(joinpath(HERE, "components", f))
end

export Car3D, build_car3d, step_car3d!, telemetry3d, respawn3d!, contain3d!, extforce3d!, contact_force, wheelmu3d!, world_velocity

# E100: the transmission is SESSION data, not a car constant. The Lotus 49's gears are
# adjustable and the ibt captures prove it -- Nurburgring runs [2.23,1.72,1.32,1.04,0.846]
# while the skidpad runs [2.23,1.72,1.32,1.09,0.916]. These defaults are the SKIDPAD setup,
# so anything that fails to call set_transmission! is driving a fast circuit on short-course
# gearing (4.8% short in 4th, 8.3% in 5th). Kept only as a last-resort fallback, and
# transmission_source() exists so a run can SAY which capture it is using -- a silent
# fallback to constants is the bug the PO's "physics entirely from the ibt data" forbids.
const GEARS = [2.23, 1.72, 1.32, 1.09, 0.916]
gearratio(g::Int) = g <= 0 ? 0.0 : GEARS[g]
const FINAL = Ref(4.11)
const TRANS_SRC = Ref("built-in fallback (SKIDPAD setup -- NOT from an ibt)")

"""    set_transmission!(gears, final; source) -> nothing

Install the gearbox read from an ibt session. Must be called BEFORE a Car3D is built: the
final drive is an MTK parameter baked in at construction, so a later change would silently
apply to the ratios and not to the drivetrain.
"""
function set_transmission!(gears::AbstractVector, final::Real; source::AbstractString="unknown")
    length(gears) == length(GEARS) ||
        error("set_transmission!: expected $(length(GEARS)) ratios, got $(length(gears))")
    all(g -> g > 0, gears) || error("set_transmission!: non-positive gear ratio in $gears")
    final > 0 || error("set_transmission!: non-positive final drive $final")
    GEARS .= float.(gears); FINAL[] = float(final); TRANS_SRC[] = source
    nothing
end

"""Where the live gearbox came from — print this at startup so a fallback cannot hide."""
transmission_source() = TRANS_SRC[]

# E100 S2: MASS is session data too. The ibt's four CornerWeights sum to the car's weight and
# give its front share, and they VARY between captures exactly as the gears do -- Nurburgring
# 1376/1376/1650/1650 (symmetric, 59.1 L of fuel), skidpad 1283/1547/1830/1509 (cross-weighted,
# 75.0 L). The defaults below are the NURBURGRING session's (6052 N / 9.81 = 616.9 kg, front
# share 0.4547), so they are right for the circuits and ~12 kg light for the skidpad.
# Smaller in effect than the gearbox, and recorded rather than waved away: the PO's constraint
# is that the physics comes from the data, not that the error is large enough to feel.
const MASS       = Ref(617.0)
const FRONT_FRAC = Ref(0.455)

"""    set_mass!(m, front_frac; source) -> nothing

Install the car mass and its front share, derived from an ibt session's CornerWeights. Like
set_transmission!, this must run BEFORE a Car3D is built — m and front_frac are MTK parameters
baked in at construction.
"""
function set_mass!(m::Real, front_frac::Real; source::AbstractString="unknown")
    m > 0 || error("set_mass!: non-positive mass $m")
    0.0 < front_frac < 1.0 || error("set_mass!: front_frac out of range: $front_frac")
    MASS[] = float(m); FRONT_FRAC[] = float(front_frac)
    nothing
end

"""
    wrecks(closing, bnd_peak, speed; close_ms, bnd_peak_max, vmin_ms) -> Bool

E95/E99: does this contact end the race?  PO 2026-08-30: *"a graze at speed should scrub you
but not end your race."*

Two independent ways to be a hard hit — a high CLOSING speed into a solid, or a large boundary
penetration peak (the fence/wall case, where the contact is spread over frames and the closing
speed alone under-reads it) — and then a speed gate, so a slow shunt in the pits never totals
the car however square it is.

Closing speed, not peak force: force saturates at ~296 kN for any real contact, so it cannot
tell a graze from a square hit. That was measured, and it is why this takes `closing`.

S371: extracted because the gate had its OWN copy of this rule and the two had already drifted —
the copy was missing the boundary branch entirely and hardcoded a threshold the sim exposes as
tunable. A gate asserting its own reimplementation tests nothing about the sim.
"""
function wrecks(closing::Real, bnd_peak::Real, speed::Real;
                close_ms::Real = 12.0, bnd_peak_max::Real = 1.0e3, vmin_ms::Real = 50.0/3.6)
    hard = (closing > close_ms) || (bnd_peak > bnd_peak_max)
    return hard && abs(speed) > vmin_ms
end

"""Mass and front share from an ibt session's corner weights (N) — the conversion in one place."""
function mass_from_corner_weights(cw)
    tot = sum(values(cw))
    tot > 0 || error("mass_from_corner_weights: corner weights sum to $tot")
    (tot / 9.81, (cw[:LF] + cw[:RF]) / tot)
end
const MAXSTEER = 0.30
const RW_R = 0.33
const RH0 = 0.075                                  # static chassis ride height [m] (for the rideHeight channel)
const TC_ON   = !haskey(ENV, "JM_NOTC")            # traction aid (see drive_rt.jl) — keeps the rear below its slip limit
const TC_SLIP = parse(Float64, get(ENV, "JM_TC_SLIP", "0.06"))
const TC_VLO  = parse(Float64, get(ENV, "JM_TC_VLO", "25.0"))   # speed gate: off below, full above (peel-out lives at low speed)
const TC_VHI  = parse(Float64, get(ENV, "JM_TC_VHI", "38.0"))

# wheel body offsets (xi long +fwd, yi lat +left), from DrivenVehicle3D geometry
const WHEELS = ((1.314, 0.75), (1.314, -0.75), (-1.096, 0.75), (-1.096, -0.75))   # FL FR RL RR

mutable struct Car3D
    sys; integ
    s_thr; s_brk; s_st; s_gr; s_clu; s_we
    s_zr::NTuple{4,Any}                            # per-wheel road DISPLACEMENT setters
    s_vr::NTuple{4,Any}                            # per-wheel road VELOCITY setters (feed-forward)
    s_pos; s_vel                                   # world-pos (X,Y) + body-vel (u,v) STATE setters (boundary)
    s_vreset                                       # vertical-subsystem reset (divergence guard)
    s_fx; s_fy; s_mz; s_cda                        # E56: body-frame external force/moment + drag-scale PORT setters
    s_mu::NTuple{4,Any}                            # E56: per-wheel tyre μscale setters (FL FR RL RR) — grass grip loss
    getall
    gear::Int
    zref::Float64                                  # tracked ground reference height [m]
    zr_prev::NTuple{4,Float64}                     # last road displacement (for the velocity feed-forward)
    # CarState-compatible render fields (mirror DriveRT.Car) + 3-D attitude
    x::Float64; y::Float64; z::Float64; θ::Float64
    v::Float64; t::Float64; rpm::Float64; gear_n::Int
    tc::NTuple{4,NTuple{3,Float64}}
    lapdist::Float64; laps::Int; lateral::Float64; along::Float64; ontrack::Bool
    pitch::Float64; roll::Float64; vacc::Float64; heave::Float64
    rh::NTuple{4,Float64}                           # per-corner ride height [m] (FL FR RL RR)
end

# E56: build the four per-wheel μscale setters (BrushTyre only; the JM_MAGIC Tyre has no μscale →
# fall back to no-op setters so wheelmu3d! is harmless there).
function _musetters(sys)
    try
        (setp(sys,sys.FL.μscale), setp(sys,sys.FR.μscale), setp(sys,sys.RL.μscale), setp(sys,sys.RR.μscale))
    catch
        nop = (integ, v) -> nothing
        (nop, nop, nop, nop)
    end
end

function build_car3d(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0, y0 = 0.0,
                     brush = !haskey(ENV, "JM_MAGIC"), dt = 1/300)
    sys = mtkcompile(DrivenVehicle3D(name = :car, brush = brush, final = FINAL[], m = MASS[], front_frac = FRONT_FRAC[]))   # physics brush by DEFAULT; JM_MAGIC ⇒ Magic-Formula tyre
    println(brush ? "  TYRE (3-D): physics-based brush model (default)" : "  TYRE (3-D): Magic-Formula tyre (JM_MAGIC)")
    prob = ODEProblem(sys, [sys.u => v0, sys.ωf => v0/0.30, sys.ωr => v0/RW_R,
                            sys.ωe => 209.4, sys.X => x0, sys.Y => z0, sys.ψ => θ0], (0.0, 1e7))
    # the divergence guard handles recovery from the rare hard-landing solver abort; a finer
    # `dt` (e.g. 1/1200) reduces those recoverable warnings further at some CPU cost.
    integ = init(prob, Rosenbrock23(); save_everystep = false, dense = false, adaptive = false, dt = dt)
    getall = ModelingToolkit.getsym(sys, [sys.X, sys.Y, sys.ψ, sys.u, sys.v, sys.rpm,
        sys.FL.Fx, sys.FR.Fx, sys.RL.Fx, sys.RR.Fx, sys.FL.Fy, sys.FR.Fy, sys.RL.Fy, sys.RR.Fy,
        sys.z, sys.th, sys.ph, sys.az, sys.FzFL, sys.FzFR, sys.FzRL, sys.FzRR, sys.ωr])
    c = Car3D(sys, integ, setp(sys,sys.throttle), setp(sys,sys.brake), setp(sys,sys.δ),
              setp(sys,sys.gear), setp(sys,sys.clutch), ModelingToolkit.setu(sys, sys.ωe),
              (setp(sys,sys.zrFL),setp(sys,sys.zrFR),setp(sys,sys.zrRL),setp(sys,sys.zrRR)),
              (setp(sys,sys.vrFL),setp(sys,sys.vrFR),setp(sys,sys.vrRL),setp(sys,sys.vrRR)),
              ModelingToolkit.setu(sys,[sys.X,sys.Y]), ModelingToolkit.setu(sys,[sys.u,sys.v]),
              ModelingToolkit.setu(sys,[sys.z,sys.w,sys.th,sys.q,sys.ph,sys.pp,
                  sys.zuFL,sys.vuFL,sys.zuFR,sys.vuFR,sys.zuRL,sys.vuRL,sys.zuRR,sys.vuRR]),
              setp(sys,sys.Fx_ext),setp(sys,sys.Fy_ext),setp(sys,sys.Mz_ext),setp(sys,sys.CdA_scale),
              _musetters(sys),
              getall, 1, y0, ntuple(_->0.0,4),
              x0, y0, z0, θ0, v0, 0.0, 0.0, 1, ntuple(_->(0.0,0.0,0.0),4),
              0.0, 0, 0.0, 0.0, true, 0.0, 0.0, 9.80665, 0.0, ntuple(_->RH0,4))
    c.s_gr(c.integ, GEARS[c.gear]); getall(integ)
    for _ in 1:3; step_car3d!(c, 0.3, 0.0, 0.0, 1/60); end
    for _ in 1:3; step_car3d!(c, 0.3, 0.0, 0.0, 1/60; clutch = 0.5, manual = true); end
    reinit!(c.integ); c.gear = 0; c.s_gr(c.integ, 0.0)
    a = getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = sqrt(a[4]^2 + a[5]^2); c.rpm = a[6]
    c.zref = y0; c.zr_prev = ntuple(_->0.0, 4)        # spawn on the ground (zr≈0) — no spurious first-step road velocity
    c
end

"""Compile the 3-D car ONCE and build `length(poses)` cars sharing the system (so a field of
3-D AI doesn't pay N× mtkcompile).  `poses` = Vector of (x0,z0,θ0,v0)."""
function build_cars3d(poses; brush = !haskey(ENV, "JM_MAGIC"), dt = 1/300)
    sys = mtkcompile(DrivenVehicle3D(name = :car, brush = brush, final = FINAL[], m = MASS[], front_frac = FRONT_FRAC[]))
    s_thr=setp(sys,sys.throttle); s_brk=setp(sys,sys.brake); s_st=setp(sys,sys.δ)
    s_gr=setp(sys,sys.gear); s_clu=setp(sys,sys.clutch); s_we=ModelingToolkit.setu(sys,sys.ωe)
    s_zr=(setp(sys,sys.zrFL),setp(sys,sys.zrFR),setp(sys,sys.zrRL),setp(sys,sys.zrRR))
    s_vr=(setp(sys,sys.vrFL),setp(sys,sys.vrFR),setp(sys,sys.vrRL),setp(sys,sys.vrRR))
    s_pos=ModelingToolkit.setu(sys,[sys.X,sys.Y]); s_vel=ModelingToolkit.setu(sys,[sys.u,sys.v])
    s_vreset=ModelingToolkit.setu(sys,[sys.z,sys.w,sys.th,sys.q,sys.ph,sys.pp,
                  sys.zuFL,sys.vuFL,sys.zuFR,sys.vuFR,sys.zuRL,sys.vuRL,sys.zuRR,sys.vuRR])
    s_fx=setp(sys,sys.Fx_ext); s_fy=setp(sys,sys.Fy_ext); s_mz=setp(sys,sys.Mz_ext); s_cda=setp(sys,sys.CdA_scale)
    s_mu=_musetters(sys)
    getall=ModelingToolkit.getsym(sys, [sys.X, sys.Y, sys.ψ, sys.u, sys.v, sys.rpm,
        sys.FL.Fx, sys.FR.Fx, sys.RL.Fx, sys.RR.Fx, sys.FL.Fy, sys.FR.Fy, sys.RL.Fy, sys.RR.Fy,
        sys.z, sys.th, sys.ph, sys.az, sys.FzFL, sys.FzFR, sys.FzRL, sys.FzRR, sys.ωr])
    cars=Car3D[]
    for (x0,z0,θ0,v0) in poses
        prob = ODEProblem(sys, [sys.u=>v0, sys.ωf=>v0/0.30, sys.ωr=>v0/RW_R,
                                sys.ωe=>209.4, sys.X=>x0, sys.Y=>z0, sys.ψ=>θ0], (0.0,1e7))
        integ = init(prob, Rosenbrock23(); save_everystep=false, dense=false, adaptive=false, dt=dt)
        c = Car3D(sys, integ, s_thr,s_brk,s_st,s_gr,s_clu,s_we, s_zr, s_vr, s_pos,s_vel, s_vreset,
                  s_fx,s_fy,s_mz,s_cda, s_mu,
                  getall, 1, 0.0, ntuple(_->0.0,4),
                  x0, 0.0, z0, θ0, v0, 0.0, 0.0, 1, ntuple(_->(0.0,0.0,0.0),4),
                  0.0, 0, 0.0, 0.0, true, 0.0, 0.0, 9.80665, 0.0, ntuple(_->RH0,4))
        c.s_gr(c.integ, GEARS[c.gear]); getall(integ)
        for _ in 1:3; step_car3d!(c, 0.3, 0.0, 0.0, 1/60); end
        for _ in 1:3; step_car3d!(c, 0.3, 0.0, 0.0, 1/60; clutch=0.5, manual=true); end
        reinit!(c.integ); c.gear=0; c.s_gr(c.integ, 0.0)
        a=getall(c.integ); c.x=a[1]; c.z=a[2]; c.θ=a[3]; c.v=sqrt(a[4]^2+a[5]^2); c.rpm=a[6]
        c.zref=0.0; c.zr_prev=ntuple(_->0.0,4)
        push!(cars, c)
    end
    cars
end

"Advance the 3-D car by dt.  Inputs as DriveRT.step_car!.  `groundz(x,z)->h`
gives terrain elevation (used to drive the suspension under each wheel)."
function step_car3d!(c::Car3D, throttle, brake, steer, dt;
                     clutch = 0.0, up = false, dn = false, manual = false,
                     groundz = (x,z)->0.0)
    if manual
        c.s_clu(c.integ, clamp(clutch, 0, 1))
        up && c.gear < 5 && (c.gear += 1; c.s_gr(c.integ, gearratio(c.gear)))
        dn && c.gear > 0 && (c.gear -= 1; c.s_gr(c.integ, gearratio(c.gear)))
    else
        # AUTO engages out of neutral — for a STANDING START, which is what this is for. It used
        # to engage 1st at ANY speed, which is reachable: select neutral in MANUAL, press G to hand
        # control to AUTO at 200 km/h, and the next step slams into 1st, spinning the engine up and
        # dumping a large negative torque into the rear wheels. Pick a gear the speed can accept.
        if c.gear == 0
            g = 1
            while g < 5 && abs(c.v) > 0.9 * (9500.0*2π/60) / (GEARS[g]*FINAL[]) * RW_R; g += 1; end
            c.gear = g; c.s_gr(c.integ, GEARS[g])
        end
        held = abs(c.v) < 1.0 && throttle < 0.05
        ae = held ? 0.0 : clamp((c.rpm - 1400.0)/1000.0, 0, 1) * clamp(max(2*throttle, c.v/2), 0, 1)
        c.s_clu(c.integ, clamp(1.0 - ae, 0, 1))
    end
    thr = clamp(throttle, 0, 1)
    if TC_ON && thr > 0.0                                  # traction aid: keep the rear below its slip limit (HIGH speed only)
        a0 = c.getall(c.integ)
        gate = clamp((abs(a0[4]) - TC_VLO) / (TC_VHI - TC_VLO), 0.0, 1.0)   # 0 at low speed → peel-out lives
        if gate > 0.0
            κr = (a0[23]*RW_R - a0[4]) / max(abs(a0[4]), 3.0)
            κr > TC_SLIP && (thr *= clamp(1.0 - 4.0*gate*(κr - TC_SLIP)/TC_SLIP, 0.05, 1.0))
        end
    end
    c.s_thr(c.integ, thr); c.s_brk(c.integ, clamp(brake, 0, 1))
    c.s_st(c.integ, clamp(steer, -1, 1) * MAXSTEER)
    # --- advance in solver-rate SUBSTEPS, resampling the road under each wheel every
    #     substep so the road input is CONTINUOUS (not a per-frame staircase), and
    #     feed-forward the road VERTICAL VELOCITY vr = d(zr)/dt into the tyre contact
    #     (so the contact damping ct·(vr−vu) sees the real road motion, not a step) ---
    Δ = max(dt, 1e-3); nsub = max(1, round(Int, Δ*300)); subdt = Δ/nsub
    local a = c.getall(c.integ)
    local terr = ntuple(_->0.0, 4)
    for _ in 1:nsub
        x = a[1]; z = a[2]; θ = a[3]; cosθ = cos(θ); sinθ = sin(θ)
        u = a[4]; v = a[5]
        vwx = u*cosθ - v*sinθ;  vwz = u*sinθ + v*cosθ            # world horizontal velocity (wheel travel)
        spd = hypot(vwx, vwz); dirx = spd>0.5 ? vwx/spd : cosθ;  dirz = spd>0.5 ? vwz/spd : sinθ
        terr = ntuple(4) do i
            xi, yi = WHEELS[i]
            wx = x + xi*cosθ - yi*sinθ;  wz = z + xi*sinθ + yi*cosθ
            h = groundz(wx, wz);  isfinite(h) ? Float64(h) : c.zref
        end
        # road VERTICAL VELOCITY = (∂terrain/∂travel)·speed — a SMOOTH spatial gradient over a
        # fixed 1 m lookahead × travel speed (NOT a finite-difference of zr, which spikes at the
        # contact transition and injects force through ct·vr).
        dL = 1.0
        vr = ntuple(4) do i
            xi, yi = WHEELS[i]
            wx = x + xi*cosθ - yi*sinθ;  wz = z + xi*sinθ + yi*cosθ
            ha = groundz(wx + dirx*dL, wz + dirz*dL)            # terrain 1 m ahead along travel
            isfinite(ha) ? clamp((Float64(ha) - terr[i]) / dL * spd, -25.0, 25.0) : 0.0
        end
        terr_cg = sum(terr)/4
        ΣFz = a[19] + a[20] + a[21] + a[22]                     # tyre vertical loads (getall idx 19–22)
        grounded = ΣFz > 0.15 * 617 * 9.80665                   # wheels loaded?
        vr_cg = (vr[1]+vr[2]+vr[3]+vr[4])/4
        # ground reference: while LOADED, follow the GRADE (feed-forward vr_cg) + a correction so
        # the suspension sits at static on any slope (a fast climb no longer reads as a slam); when
        # AIRBORNE, FREEZE it so the body falls relative to it and the car clears a brow / lands.
        (grounded && isfinite(terr_cg)) && (c.zref += vr_cg*subdt + clamp(terr_cg - c.zref, -1.5, 1.5)*10.0*subdt)
        zr = ntuple(i -> terr[i] - c.zref, 4)
        for i in 1:4; c.s_zr[i](c.integ, zr[i]); c.s_vr[i](c.integ, vr[i]); end
        c.zr_prev = zr
        step!(c.integ, subdt, true)
        a = c.getall(c.integ)
    end
    c.x = a[1]; c.z = a[2]; c.θ = a[3]
    c.v = sqrt(a[4]^2 + a[5]^2); c.t = c.integ.t; c.rpm = clamp(a[6], 0.0, 9700.0); c.gear_n = c.gear
    c.heave = a[15]; c.pitch = a[16]; c.roll = a[17]; c.vacc = a[18]
    # DIVERGENCE GUARD: the stiff tyre contact on extreme terrain can blow the vertical
    # subsystem up (pitch → 1e5°). If it leaves sane bounds, reset the vertical states to
    # static (keep the in-plane motion) so the renderer never draws garbage. The proper fix
    # is a more robust contact model (E6) — this keeps JM_3D usable meanwhile.
    # AIRBORNE-AWARE guard: on the ground, a big pitch/roll = the vertical solver diverging → reset.
    # But with NO wheel load (in the air, e.g. launched off another car's wheel or a ramp), a big
    # attitude is a legit TUMBLE/cartwheel — let it rotate; only catch true divergence (non-finite or
    # absurd).  On landing the on-ground branch snaps it back upright so the suspension model copes.
    fztot = a[19] + a[20] + a[21] + a[22]                       # total wheel load (N)
    airborne = fztot < 600.0
    if !(isfinite(c.pitch) && isfinite(c.roll) && isfinite(c.heave)) || abs(c.heave) > 12.0 ||
       (!airborne && (abs(c.pitch) > 0.7 || abs(c.roll) > 0.7)) ||
       (airborne && (abs(c.pitch) > 12.0 || abs(c.roll) > 12.0))
        c.s_vreset(c.integ, zeros(14))
        c.heave = 0.0; c.pitch = 0.0; c.roll = 0.0; c.vacc = 9.80665
    end
    if c.rpm < 350.0 && (clamp(clutch, 0, 1) > 0.5 || c.gear == 0)
        c.s_we(c.integ, 209.44); c.rpm = 2000.0
    end
    c.y = c.zref + c.heave                          # world body height (terrain ref + heave; rises in a jump)
    mg4 = 617.0*9.80665/4
    # tc[i] = (Fx, Fy, GRIP LIMIT μ·Fz) all in mg/4 units.  The 3rd entry is the
    # friction-circle RADIUS (the available grip, μ·Fz from the real per-corner load
    # a[18+i]=Fz), NOT the force magnitude — so the HUD dot sits INSIDE the ring in
    # normal driving and reaches/exceeds the edge only when the tyre is at its limit.
    # μ_f/μ_r match brush_tyre.jl BRUSH_FRONT.μ / BRUSH_REAR.μ (lateral grip).
    μc = (1.36, 1.36, 1.40, 1.40)
    c.tc = ntuple(i -> (a[6+i]/mg4, a[10+i]/mg4, μc[i]*max(a[18+i],1.0)/mg4), 4)
    # per-corner ride height = static + chassis-mount rise − road drop (grows when a wheel droops in the air)
    c.rh = ntuple(i -> RH0 + (WHEELS[i][1]*c.pitch + WHEELS[i][2]*c.roll + c.heave) - (terr[i]-c.zref), 4)
    # E6: YAW-RATE divergence guard.  The stiff 3-D tyre/contact can spin the yaw rate r up to 100s of
    # rad/s on the big elevation/speed (Spa Eau Rouge, Nürburgring) — the integrator diverging, which the
    # VERTICAL guard above can't catch and place3d! can't reset.  A real spin is < ~3 rad/s, so a > 10 rad/s
    # yaw is unphysical: clamp it back IN PLACE (not a respawn → no inchworm teleport, E38) so the car
    # stays on track and controllable instead of cartwheeling to hyperspace.  Player unaffected (never >10).
    let gs = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.r), ModelingToolkit.setu(c.sys, c.sys.r)), _RSET3D, c.sys)
        rr = gs[1](c.integ)
        # a diverged yaw is GARBAGE (no meaningful cornering intent in it), so STRAIGHTEN the car —
        # keep a small sign-preserving residual (≤0.8 rad/s) rather than leaving it spinning at the
        # clamp ceiling, which would re-seed the divergence next step.
        (!isfinite(rr) || abs(rr) > 10.0) && gs[2](c.integ, isfinite(rr) ? clamp(rr, -0.8, 0.8) : 0.0)
    end
    (!isfinite(c.v) || abs(c.v) > 110) && return respawn3d!(c)
    if !manual && c.gear >= 1
        # auto-shift on engine RPM.  The box is close-ratio with a TALL launch gear (1st pulls
        # to ~115 km/h at the old 8500 up-point), so on a tight circuit the car sat in 1st almost
        # the whole lap.  Shift up earlier (7000, still in the DFV power band) so it works UP through
        # the gears in normal driving, and downshift more readily (4100, off heavy throttle) so it
        # drops a gear into corners.  Hysteresis gap (7000↔4100) is wide enough that it never hunts.
        grpm = (a[4]/RW_R)*GEARS[c.gear]*FINAL[]*60/(2π)
        # E47: SHORT-SHIFT out of the low gears — the tall 1st/2nd multiply torque so much that holding
        # them to 7000 spins the wheels up ("almost peel out before it shifts").  Up-shift earlier in 1st/2nd
        # (5000/5800) so the launch is clean; keep 7000 for 3rd-5th where wheelspin isn't an issue.
        up_rpm = c.gear == 1 ? 5000 : c.gear == 2 ? 5800 : 7000
        if grpm > up_rpm && c.gear < 5;                      c.gear += 1; c.s_gr(c.integ, GEARS[c.gear])
        elseif grpm < 4100 && c.gear > 1 && throttle < 0.85; c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]); end
    end
    c
end

const _TC = IdDict{Any,Any}()
function telemetry3d(c::Car3D)
    g = get!(_TC, c.sys) do
        ModelingToolkit.getsym(c.sys, [c.sys.u, c.sys.v, c.sys.r, c.sys.ax, c.sys.ay, c.sys.ωf, c.sys.ωr])
    end
    a = g(c.integ)
    (u=a[1], v=a[2], r=a[3], ax=a[4], ay=a[5], ωf=a[6], ωr=a[7], vacc=c.vacc,
     pitch=c.pitch, roll=c.roll, rh=c.rh)
end

"Fence collision: snap onto the boundary (xnew,znew) + bleed speed (E7).
E42: `settle` zeroes the VERTICAL subsystem and re-anchors zref to the terrain under the
snap point — without it, snapping back from a steep off-world slide leaves the suspension
loaded against the old (down-a-field) height, so re-entry slams the contact and the car
'superball'-bounces back onto the track.  Pass `groundz` so zref lands on the real edge height."
function contain3d!(c::Car3D, xnew, znew; vdamp = 0.45, settle = false, groundz = nothing)
    a = c.getall(c.integ)
    c.s_pos(c.integ, [xnew, znew])
    c.s_vel(c.integ, [a[4]*vdamp, a[5]*vdamp])
    c.x = xnew; c.z = znew; c.v = sqrt((a[4]*vdamp)^2 + (a[5]*vdamp)^2)
    if settle
        c.s_vreset(c.integ, zeros(14))
        c.heave = 0.0; c.pitch = 0.0; c.roll = 0.0; c.vacc = 9.80665
        if groundz !== nothing
            h = groundz(xnew, znew); isfinite(h) && (c.zref = Float64(h))
        end
        c.zr_prev = ntuple(_ -> 0.0, 4); c.y = c.zref
    end
    c
end

function respawn3d!(c::Car3D; groundz = nothing)
    # PO 2026-08-27: "at the beginning, with car stationary at the start line, 1st gear engages
    # even when the clutch has disengaged the engine". Spawn in NEUTRAL and let each mode decide:
    # AUTO engages on its next step (above), MANUAL leaves the choice to the driver.
    # JM_SPAWN_IN_GEAR=1 restores the old always-1st behaviour.
    #
    # ⚠️ THIS IS THE FILE THAT MATTERS. The same two fixes were first written into drive_rt.jl and
    # had NO EFFECT, because CAR3D (this 3-D model) is the default and drive_rt.jl is the planar
    # fallback. The PO's next telemetry still read `gear=1` at t=0 and that is how it was caught.
    # Two physics models, the same function names in both: check which one the sim actually runs.
    g0 = get(ENV,"JM_SPAWN_IN_GEAR","0") != "0" ? 1 : 0
    reinit!(c.integ); c.gear = g0; c.s_gr(c.integ, gearratio(g0))
    c.s_vreset(c.integ, zeros(14))                 # zero the vertical subsystem → spawn settled (no "superball" bounce)
    a = c.getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = a[4]; c.rpm = a[6]
    c.heave = 0.0; c.pitch = 0.0; c.roll = 0.0; c.vacc = 9.80665
    # re-anchor the ground reference to the terrain UNDER the respawn point — otherwise zref keeps the
    # last (crash-site) height and the suspension sees a huge road step on the first frame → it bounces.
    if groundz !== nothing
        h = groundz(c.x, c.z); c.zref = isfinite(h) ? Float64(h) : 0.0
    end
    c.zr_prev = ntuple(_ -> 0.0, 4); c.y = c.zref
    c
end

"""E56 spring-damper trackside CONTACT kernel (the human car's all-Modelica collision response).
Given a penetration `δ` [m, >0] into an object, the world-frame OUTWARD normal `(nx,nz)` (object→car),
the car's velocity component `vn` along +n [m/s; <0 = driving INTO the object], heading `θ`, and the
object `kind`, return the body-frame `(Fx,Fy,Mz)` to feed `extforce3d!` BEFORE the step.

  :wall  — soft spring + STRONG two-sided damper ⇒ INELASTIC: drive in, stop dead, stay put.
           (E94: this line used to say "stiff spring ... ELASTIC bounce-back", which described
            neither the code below it nor the behaviour anyone wanted.)
  :soft  — weak spring (with a crush `give` dead-zone) + two-sided viscous damper ⇒ the car drives
           IN, the damper bleeds its speed, and the soft spring barely pushes back ⇒ it gets STUCK
           (a hedge / hay row), yet can't pass clean through (deep penetration past `give` resists).

The outward force is clamped to a per-frame impulse ≤ m·CONTACT_DVMAX (a penalty contact) so a stiff
wall held constant over a render frame can't blow the integrator up.  Contact can only PUSH, not pull."""
const SPRING_DMAX = parse(Float64, get(ENV, "JM_SPRING_DMAX", "0.25"))   # E94b: m of penetration the SPRING may store
# E96 (PO 2026-08-30): "car should never bounce back, ever. If it hits something, its forward
# motion should quickly damp to zero." The PO has removed tuning from the table, and rightly: E94
# softened k, E94b bounded the stored spring energy, E95 added a wreck latch, and the PO was still
# bouncing after every one of them. Each of those makes rebound SMALLER; none makes it IMPOSSIBLE,
# and a threshold-gated wreck cannot help at all below its threshold.
# So state it as an invariant the contact law cannot violate, at any speed, off any object: a
# contact may REMOVE approach velocity, but it may never ADD separation velocity beyond a slow
# ooze. VN_OUT_MAX is that ooze -- enough to ease out of a penetration instead of sticking inside
# geometry, far too little to read as a bounce (0.25 m/s is 0.9 km/h).
# This is NOT the loose-wheel restitution: a detached wheel is a different body with its own
# integrator (JM_WHEEL_REST), so the PO keeps "the front wheels should bounce back from the wall"
# while the car itself never does.
const VN_OUT_MAX = parse(Float64, get(ENV, "JM_VN_OUT_MAX", "0.25"))   # m/s of separation a contact may ever grant
const CONTACT_DVMAX = 8.0                                          # PO round-4: a hit must not FLING the car — cap the per-frame outward Δv (was 16 = "rubber-band sling-back")
function contact_force(δ, nx, nz, vn, θ; kind = :wall, m = 617.0, dt = 1/60, arm = 1.4)
    δ <= 0.0 && return (0.0, 0.0, 0.0)
    # PO round 4: trackside objects still felt like "a big rubber band that slings you back the other
    # way".  A stiff penalty SPRING is conservative — it stores k·δ² of energy on the way in and returns
    # all of it on the way out (the sling), no matter how much damping is layered on top (at rest vn≈0 so
    # the damper is silent and only the spring acts).  INELASTIC contact = a SOFT spring (just enough to
    # stop slow creep-through, its static push is a gentle nudge not a catapult) + a STRONG two-sided
    # damper that does the real work of killing the approach velocity.  You drive in, stop dead, and ease
    # back onto the road — no catapult.
    if kind === :soft
        k = 8.0e4; c = 7.0e4; give = 0.3; twoSided = true        # hedge/hay: weak spring, strong damp — crush in, bleed speed, no spring-back
    else
        # E94 (PO 2026-08-29: "when the car hits a barrier at speed it should damp out and get stuck
        # ... the car should not have an elastic collision causing it to trampoline, levitate").
        # The numbers here contradicted BOTH comments describing them: the docstring above calls
        # :wall "stiff spring ⇒ ELASTIC bounce-back", while this line called 4.0e5 a "soft spring
        # ⇒ inelastic". 4.0e5 is FIVE TIMES the :soft spring (8.0e4) -- the stiffest in the file --
        # and the comment at the top of this function already names a stiff conservative spring as
        # exactly what stores k·δ²/2 on the way in and returns all of it as a sling. So the wall was
        # documented as inelastic and parameterised as a catapult.
        # Inelastic contact = a spring just stiff enough to stop creep-through, plus a strong
        # two-sided damper that does the real work of killing approach speed.
        # JM_ELASTIC_WALL=1 restores the old 4.0e5/1.5e5 for an A/B.
        if get(ENV, "JM_ELASTIC_WALL", "0") != "0"
            k = 4.0e5; c = 1.5e5; give = 0.0; twoSided = true
        else
            k = 1.0e5; c = 3.0e5; give = 0.05; twoSided = true
        end
    end
    δeff = max(δ - give, 0.0)                                     # the soft give-zone holds the car with no push-back
    # E94b (PO 2026-08-29: "hit something at 200 km/h, same behavior as before - elastic collision,
    # bouncing back and forth"). Softening k alone did NOT fix a big hit, and the reason is here:
    # the spring force is k·δ, so a deep excursion (metres past the world edge at 200 km/h) drives it
    # straight into the CONTACT_DVMAX ceiling -- 617·8/dt ≈ 296 kN -- with BOTH the old 4.0e5 and the
    # new 1.0e5. Saturated is saturated: the two behave identically for exactly the impacts that
    # matter, which is precisely what the PO observed.
    # A spring is CONSERVATIVE: whatever k·δ²/2 it stores on the way in, it returns on the way out.
    # So bound the STORED ENERGY by capping the penetration the SPRING is allowed to see. Past
    # SPRING_DMAX the spring stops growing and the DAMPER -- which dissipates rather than stores --
    # does all the remaining work. That is what makes a deep hit inelastic instead of a catapult.
    δspring = min(δeff, SPRING_DMAX)
    damp = twoSided ? -c*vn : -c*min(vn, 0.0)                    # :wall damps approach only (so it rebounds)
    Fn = max(k*δspring + damp, 0.0)                               # along +n (outward); a contact never pulls
    Fn = min(Fn, m*CONTACT_DVMAX/max(dt, 1e-3))                  # clamp per-frame impulse → solver-stable
    # E96: THE NO-REBOUND INVARIANT. Everything above still ends in an outward spring term that
    # keeps pushing once the car has stopped (at rest vn≈0, so the damper is silent and only k·δ
    # acts) -- which is the bounce, and no choice of k removes it. Split the impulse budget
    # explicitly: enough to cancel whatever approach speed there is, plus at most VN_OUT_MAX of
    # separation. A 200 km/h hit and a 5 km/h nudge then both leave at ≤ 0.25 m/s, so "no bounce"
    # stops being a function of impact speed. Applies to every solid AND to the world-edge fence,
    # since both call this kernel.
    # Bound the RESULT, not the increment. The first cut of this capped the per-frame Δv at
    # (approach + VN_OUT_MAX), which is correct while the car is still moving INTO the wall
    # (vn < 0 ⇒ vn_after ≤ VN_OUT_MAX) but leaks once it is moving out: at vn > 0 each further
    # frame of penetration could add another VN_OUT_MAX, so a deeply buried car would ratchet
    # itself up to metres per second over a dozen frames -- the very bounce this exists to stop,
    # arrived at slowly. Capping the OUTCOME closes that: the push is whatever it takes to reach
    # VN_OUT_MAX and never more, so once the car is oozing out the contact stops pushing entirely.
    Fn = min(Fn, m*max(VN_OUT_MAX - vn, 0.0)/max(dt, 1e-3))
    # E96-S3: BLEED THE EXIT, do not just stop pushing. With the sign error fixed the contact
    # correctly stops pushing the moment the car turns around (measured: Fx drops to 0 on the
    # first retreating frame) -- but the car LEAVES contact carrying whatever the last approach
    # frame gave it, ~1.7 m/s after a 6.8 m/s hit, and then coasts metres with nothing acting on
    # it. Restitution ~0.25 instead of >1 is a big improvement and still not what the PO asked
    # for: "it should damp out and GET STUCK".
    # So while the car is separating and still inside the object, pull back on it. This is
    # DISSIPATIVE, never additive: the force opposes the motion, and it is capped at exactly the
    # impulse that cancels the remaining separation, so it can slow the car to rest but can never
    # drag it back INTO the barrier. A contact that can only push is what leaves a car skating
    # away from a wall it just buried itself in.
    # E96-S4: bleed across the WHOLE overlap, not just past the give zone. δeff subtracts `give`
    # (0.05 m for a wall), so the previous condition stopped bleeding while the car was still
    # inside the object -- it let go during the last 5 cm and the car left carrying whatever it
    # had. δ > 0 means "still overlapping", which is the honest test for "still in contact".
    if vn > 0.0 && δ > 0.0
        # Exactly the impulse that cancels the remaining separation -- no more, so it can bring the
        # car to rest but never drag it back INTO the barrier.
        # A spring-like coefficient (JM_STICK_C, N per m/s) was tried here first and MEASURED to be
        # inert: results were bit-identical at 6.0e4, 2.0e5 and 6.0e5, because this cap is always
        # the smaller term. It was removed rather than left in place, since a knob that cannot
        # change the outcome is a trap for whoever tunes it next.
        # Bleed only the EXCESS above the ooze, never the whole separation. Cancelling all of it
        # traps the car: with outward velocity zeroed every frame it is overlapping, a driver who
        # merely brushed a hedge could not reverse out under their own power, and the PO's rule for
        # soft scenery is "you plough through with a penalty", not "you are welded to it". Leaving
        # VN_OUT_MAX intact means a car can always creep free at walking pace while anything
        # faster -- which is what reads as a bounce -- is removed.
        Fn = -m*max(vn - VN_OUT_MAX, 0.0)/max(dt, 1e-3)
    end
    cθ = cos(θ); sθ = sin(θ)
    Fx = Fn*( nx*cθ + nz*sθ);  Fy = Fn*(-nx*sθ + nz*cθ)         # world force → body frame
    rx = (-nx*cθ - nz*sθ)*arm; ry = ( nx*sθ - nz*cθ)*arm        # contact point ≈ CG − n·arm, in body frame
    Mz = rx*Fy - ry*Fx                                           # yaw from the contact lever
    (Fx, Fy, Mz)
end

"""E56 ALL-MODELICA CONTACT: feed body-frame external force `Fx`,`Fy` [N] + yaw moment `Mz` [N·m]
and an aero drag scale `CdA_scale` (≤1 in a slipstream = less drag = tow) into the chassis ODE.
Unlike `bump3d!` (an instantaneous velocity/rate STATE hack), these are PARAMETER ports the solver
INTEGRATES over the step — so a spring-damper contact law `F = kδ + cδ̇` becomes a real, momentum-
conserving collision (wall = stiff k → bounce; hedge = weak k + strong c → drive in & get stuck).
Call once per frame BEFORE `step_car3d!`; the values HOLD until the next call, so pass the *total*
contact force for the frame and call with no contact (defaults) to release (`extforce3d!(c)`)."""
function extforce3d!(c::Car3D; Fx = 0.0, Fy = 0.0, Mz = 0.0, CdA_scale = 1.0)
    c.s_fx(c.integ, Fx); c.s_fy(c.integ, Fy); c.s_mz(c.integ, Mz)
    c.s_cda(c.integ, clamp(CdA_scale, 0.0, 2.0))
    c
end

"""E56 grass grip: set each wheel's tyre friction multiplier (FL,FR,RL,RR; 1 = tarmac, <1 = grass).
A wheel on the verge loses real grip in the brush tyre model — so two wheels on the grass pull the
car and cost cornering/braking, exactly as in GPL — replacing the bumpX! grass drag/yaw hack.  Call
before step_car3d! each frame; pass 1.0 for wheels on the racing surface."""
function wheelmu3d!(c::Car3D, μFL, μFR, μRL, μRR)
    c.s_mu[1](c.integ, clamp(μFL, 0.05, 1.0)); c.s_mu[2](c.integ, clamp(μFR, 0.05, 1.0))
    c.s_mu[3](c.integ, clamp(μRL, 0.05, 1.0)); c.s_mu[4](c.integ, clamp(μRR, 0.05, 1.0))
    c
end

const _RSET3D = IdDict()
function yawrate3d(c::Car3D)
    gs = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.r), ModelingToolkit.setu(c.sys, c.sys.r)), _RSET3D, c.sys)
    gs[1](c.integ)
end
const _PSI3D = IdDict()
"Place the 3-D car at world (x,z) facing θ with forward speed v (e.g. onto a grid slot)."
function place3d!(c::Car3D, x, z, θ; v = 0.0)
    c.s_pos(c.integ, [x, z])
    try
        pset = get!(() -> ModelingToolkit.setu(c.sys, c.sys.ψ), _PSI3D, c.sys)
        pset(c.integ, θ)
    catch; end
    c.s_vel(c.integ, [v, 0.0])
    c.x = x; c.z = z; c.θ = θ; c.v = v
    c
end
const _WSET3D = IdDict()
const _PPSET3D = IdDict()
const _QSET3D = IdDict()
"""
World-frame velocity `(vx, vz)` of the car, taken EXACTLY from the solver state.

E96-S6: contact code needs the true direction of travel, and `c.v` is an unsigned SPEED -- the
`v*cos(θ), v*sin(θ)` form cannot express a car moving opposite its own nose, which is what turned
the no-rebound clamp into an accelerator (E96-S2). E96-S2 worked around that by finite-differencing
the position, which is correct in direction but lags one frame; that lag is the leading suspect for
the residual overshoot E96-S3 could not remove.

The solver has carried the answer all along: `u` (longitudinal) and `v` (LATERAL) body-frame
velocities, which `bump3d!` already rotates into the world exactly this way. No differencing, no
lag, no extra state to keep in sync.
"""
function world_velocity(c::Car3D)
    a = c.getall(c.integ); θ = a[3]; u = a[4]; v = a[5]
    (u*cos(θ) - v*sin(θ), u*sin(θ) + v*cos(θ))
end

"""Rigid-body collision impulse (3-D car): world-frame velocity change (dvx,dvz) + yaw-rate dr
+ an optional VERTICAL kick `dvy` (heave velocity `w` → the car JUMPS) + a ROLL-rate kick `dpp`
(roll velocity → CARTWHEEL when a spinning wheel climbs) + a PITCH-rate kick `dq` (a rear wheel
climbing a hay bale pitches the nose down ⇒ LIFTS THE REAR, GPL-style)."""
function bump3d!(c::Car3D, dvx, dvz, dr, dvy = 0.0, dpp = 0.0, dq = 0.0)
    a = c.getall(c.integ); θ = a[3]; u = a[4]; v = a[5]
    wvx = u*cos(θ) - v*sin(θ) + dvx
    wvz = u*sin(θ) + v*cos(θ) + dvz
    nu =  wvx*cos(θ) + wvz*sin(θ)
    nv = -wvx*sin(θ) + wvz*cos(θ)
    c.s_vel(c.integ, [nu, nv])
    if dr != 0.0
        try
            gs = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.r), ModelingToolkit.setu(c.sys, c.sys.r)), _RSET3D, c.sys)
            gs[2](c.integ, gs[1](c.integ) + dr)
        catch; end
    end
    if dvy != 0.0
        try
            ws = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.w), ModelingToolkit.setu(c.sys, c.sys.w)), _WSET3D, c.sys)
            ws[2](c.integ, ws[1](c.integ) + dvy)     # add upward heave velocity → launch
        catch; end
    end
    if dpp != 0.0
        try
            ps = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.pp), ModelingToolkit.setu(c.sys, c.sys.pp)), _PPSET3D, c.sys)
            ps[2](c.integ, ps[1](c.integ) + dpp)     # add roll velocity → cartwheel
        catch; end
    end
    if dq != 0.0
        try
            qs = get!(() -> (ModelingToolkit.getsym(c.sys, c.sys.q), ModelingToolkit.setu(c.sys, c.sys.q)), _QSET3D, c.sys)
            qs[2](c.integ, qs[1](c.integ) + dq)      # add pitch velocity → nose down / rear lifts
        catch; end
    end
    c.v = sqrt(nu^2 + nv^2)
    c
end

"""
    stall_step(t, dt; auto, wrecked, rpm, clutch, rpm_floor, secs) -> (t′, fire)

E98: in MANUAL, a stalled engine drops straight to AUTO (PO 2026-08-30).

All four conditions are required, and each is load-bearing:
  * MANUAL — auto is already the destination, so firing there is meaningless.
  * rpm below the floor — the engine is actually dead.
  * clutch ENGAGED (< 0.4) — an idling engine with the clutch OUT is not stalled. That is the
    PO's own case: "applying throttle with the slider down just revs the engine, as it should".
    With the clutch riding, a low rpm is the driver's choice, not a failure.
  * NOT wrecked — a wreck decouples the engine deliberately and must not read as a stall.

Sustained for `secs` so a launch dip cannot trigger it; the timer resets the moment any
condition lifts. Returns the new accumulator and whether the switch should fire.

S366: extracted from the render loop so it can be gated. It was four booleans and an
accumulator woven into a 900-line frame body, which meant the only way to test the PO's
rule was to drive the car and watch — and every condition above is a place to get it
backwards silently.
"""
function stall_step(t::Float64, dt::Float64; auto::Bool, wrecked::Bool, rpm::Float64,
                    clutch::Float64, rpm_floor::Float64=300.0, secs::Float64=0.5)
    if !auto && !wrecked && rpm < rpm_floor && clutch < 0.4
        t += (dt > 1e-4 ? dt : 1/60)
        return t >= secs ? (0.0, true) : (t, false)
    end
    return (0.0, false)
end

end # module
