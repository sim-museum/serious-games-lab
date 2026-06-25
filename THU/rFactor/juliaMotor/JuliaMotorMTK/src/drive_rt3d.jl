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

export Car3D, build_car3d, step_car3d!, telemetry3d, respawn3d!, contain3d!

const GEARS = [2.23, 1.72, 1.32, 1.09, 0.916]
gearratio(g::Int) = g <= 0 ? 0.0 : GEARS[g]
const FINAL = 4.11
const MAXSTEER = 0.30
const RW_R = 0.33
const RH0 = 0.075                                  # static chassis ride height [m] (for the rideHeight channel)
const TC_ON   = !haskey(ENV, "JM_NOTC")            # traction aid (see drive_rt.jl) — keeps the rear below its slip limit
const TC_SLIP = parse(Float64, get(ENV, "JM_TC_SLIP", "0.06"))

# wheel body offsets (xi long +fwd, yi lat +left), from DrivenVehicle3D geometry
const WHEELS = ((1.314, 0.75), (1.314, -0.75), (-1.096, 0.75), (-1.096, -0.75))   # FL FR RL RR

mutable struct Car3D
    sys; integ
    s_thr; s_brk; s_st; s_gr; s_clu; s_we
    s_zr::NTuple{4,Any}                            # per-wheel road DISPLACEMENT setters
    s_vr::NTuple{4,Any}                            # per-wheel road VELOCITY setters (feed-forward)
    s_pos; s_vel                                   # world-pos (X,Y) + body-vel (u,v) STATE setters (boundary)
    s_vreset                                       # vertical-subsystem reset (divergence guard)
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

function build_car3d(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0, y0 = 0.0,
                     brush = !haskey(ENV, "JM_MAGIC"), dt = 1/300)
    sys = mtkcompile(DrivenVehicle3D(name = :car, brush = brush))   # physics brush by DEFAULT; JM_MAGIC ⇒ Magic-Formula tyre
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
        c.gear == 0 && (c.gear = 1; c.s_gr(c.integ, GEARS[1]))
        held = abs(c.v) < 1.0 && throttle < 0.05
        ae = held ? 0.0 : clamp((c.rpm - 1400.0)/1000.0, 0, 1) * clamp(max(2*throttle, c.v/2), 0, 1)
        c.s_clu(c.integ, clamp(1.0 - ae, 0, 1))
    end
    thr = clamp(throttle, 0, 1)
    if TC_ON && thr > 0.0                                  # traction aid: keep the rear below its slip limit
        a0 = c.getall(c.integ); κr = (a0[23]*RW_R - a0[4]) / max(abs(a0[4]), 3.0)
        κr > TC_SLIP && (thr *= clamp(1.0 - 4.0*(κr - TC_SLIP)/TC_SLIP, 0.05, 1.0))
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
    if !(isfinite(c.pitch) && isfinite(c.roll) && isfinite(c.heave)) ||
       abs(c.pitch) > 0.7 || abs(c.roll) > 0.7 || abs(c.heave) > 3.0
        c.s_vreset(c.integ, zeros(14))
        c.heave = 0.0; c.pitch = 0.0; c.roll = 0.0; c.vacc = 9.80665
    end
    if c.rpm < 350.0 && (clamp(clutch, 0, 1) > 0.5 || c.gear == 0)
        c.s_we(c.integ, 209.44); c.rpm = 2000.0
    end
    c.y = c.zref + c.heave                          # world body height (terrain ref + heave; rises in a jump)
    mg4 = 617.0*9.80665/4
    c.tc = ntuple(i -> (a[6+i]/mg4, a[10+i]/mg4, hypot(a[6+i], a[10+i])/mg4), 4)
    # per-corner ride height = static + chassis-mount rise − road drop (grows when a wheel droops in the air)
    c.rh = ntuple(i -> RH0 + (WHEELS[i][1]*c.pitch + WHEELS[i][2]*c.roll + c.heave) - (terr[i]-c.zref), 4)
    (!isfinite(c.v) || abs(c.v) > 110) && return respawn3d!(c)
    if !manual && c.gear >= 1
        grpm = (a[4]/RW_R)*GEARS[c.gear]*FINAL*60/(2π)
        if grpm > 8500 && c.gear < 5;                       c.gear += 1; c.s_gr(c.integ, GEARS[c.gear])
        elseif grpm < 3400 && c.gear > 1 && throttle < 0.9; c.gear -= 1; c.s_gr(c.integ, GEARS[c.gear]); end
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

"Fence collision: snap onto the boundary (xnew,znew) + bleed speed (E7)."
function contain3d!(c::Car3D, xnew, znew; vdamp = 0.45)
    a = c.getall(c.integ)
    c.s_pos(c.integ, [xnew, znew])
    c.s_vel(c.integ, [a[4]*vdamp, a[5]*vdamp])
    c.x = xnew; c.z = znew; c.v = sqrt((a[4]*vdamp)^2 + (a[5]*vdamp)^2)
    c
end

function respawn3d!(c::Car3D)
    reinit!(c.integ); c.gear = 1; c.s_gr(c.integ, GEARS[1])
    a = c.getall(c.integ); c.x = a[1]; c.z = a[2]; c.θ = a[3]; c.v = a[4]; c.rpm = a[6]
    c
end

end # module
