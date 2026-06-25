# vehicle3d_probe.jl — headless validation of the full-3D Lotus 49 (DrivenVehicle3D):
# static equilibrium, braking dive, cornering roll + lateral load transfer, and a
# JUMP (drop the road away → wheels unload → ballistic free-fall → landing spike).
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/vehicle3d_probe.jl

using Printf
using ModelingToolkit, OrdinaryDiffEq
using ModelingToolkit: t_nounits as t, D_nounits as D, setp, setu, getsym

const HERE = joinpath(@__DIR__, "..", "src", "components")
include(joinpath(HERE, "tyre.jl"))         # Tyre + tyre_law
include(joinpath(HERE, "powertrain.jl"))   # engine_torque
include(joinpath(HERE, "vehicle_3d.jl"))   # DrivenVehicle3D

const G = 9.80665
sys = mtkcompile(DrivenVehicle3D(name = :car))

mutable struct C; integ; set; get; end
function build(; v0=0.0, gear=0.0, w0=0.0)
    prob = ODEProblem(sys, [sys.u => v0, sys.ωf => v0/0.30, sys.ωr => v0/0.33, sys.ωe => 209.4,
                            sys.w => w0, sys.vuFL => w0, sys.vuFR => w0, sys.vuRL => w0, sys.vuRR => w0], (0.0, 1e6))
    integ = init(prob, Rosenbrock23(); save_everystep=false, dense=false, adaptive=false, dt=1/600)
    set = (; thr=setp(sys,sys.throttle), brk=setp(sys,sys.brake), st=setp(sys,sys.δ), gr=setp(sys,sys.gear),
            clu=setp(sys,sys.clutch),
            zr=(setp(sys,sys.zrFL),setp(sys,sys.zrFR),setp(sys,sys.zrRL),setp(sys,sys.zrRR)))
    set.gr(integ, gear)
    get = getsym(sys, [sys.z, sys.w, sys.th, sys.ph, sys.az, sys.u, sys.v, sys.r,
                       sys.FzFL, sys.FzFR, sys.FzRL, sys.FzRR, sys.ax, sys.ay, sys.rpm])
    C(integ, set, get)
end
rd(c) = (a=c.get(c.integ); (z=a[1],w=a[2],th=a[3],ph=a[4],az=a[5],u=a[6],v=a[7],r=a[8],
         FzFL=a[9],FzFR=a[10],FzRL=a[11],FzRR=a[12],ax=a[13],ay=a[14],rpm=a[15]))
function step!(c; thr=0.0,brk=0.0,st=0.0,clu=0.0, zr=(0.0,0.0,0.0,0.0), dt=1/300)
    c.set.thr(c.integ,thr); c.set.brk(c.integ,brk); c.set.st(c.integ,st); c.set.clu(c.integ,clu)
    for k in 1:4; c.set.zr[k](c.integ, zr[k]); end
    OrdinaryDiffEq.step!(c.integ, dt, true)
    rd(c)
end
settle(c; n=300, kw...) = (local s; for _ in 1:n; s=step!(c; kw...); end; s)

println("\n================ FULL-3D Lotus 49 validation ================")

# ---- 1. STATIC EQUILIBRIUM ----
c = build()
s = settle(c; n=600)
ΣFz = s.FzFL+s.FzFR+s.FzRL+s.FzRR
@printf("\n[static]  z=%.4f m  pitch=%.3f°  roll=%.3f°  VertAccel=%.3f g\n", s.z, rad2deg(s.th), rad2deg(s.ph), s.az/G)
@printf("          Fz  FL %.0f  FR %.0f  RL %.0f  RR %.0f  ΣFz=%.0f N  (mg=%.0f)\n",
        s.FzFL,s.FzFR,s.FzRL,s.FzRR, ΣFz, 617*G)
@printf("          front/rear split %.1f%% / %.1f%%\n", 100*(s.FzFL+s.FzFR)/ΣFz, 100*(s.FzRL+s.FzRR)/ΣFz)

# ---- 2. BRAKING DIVE (rolling, then brake) ----
c = build(; v0=40.0, gear=0.0)
settle(c; n=120)                                  # roll a moment
s = settle(c; n=150, brk=0.8)
@printf("\n[brake 0.8 @40m/s]  pitch=%+.3f° (<0 = nose-down dive)  ax=%.2f g\n", rad2deg(s.th), s.ax/G)
@printf("          front Fz %.0f  rear Fz %.0f   (Δ load forward = %.0f N)\n",
        s.FzFL+s.FzFR, s.FzRL+s.FzRR, (s.FzFL+s.FzFR)-(617*G*0.455))

# ---- 3. CORNERING ROLL + LATERAL LOAD TRANSFER ----
c = build(; v0=30.0, gear=0.0)
s = settle(c; n=250, st=0.12)                     # steady left-ish steer
left = s.FzFL+s.FzRL; right = s.FzFR+s.FzRR
@printf("\n[steer 0.12 @30m/s]  roll=%+.3f°  ay=%.2f g  yaw=%.1f°/s\n", rad2deg(s.ph), s.ay/G, rad2deg(s.r))
@printf("          left Fz %.0f  right Fz %.0f   (lateral transfer = %.0f N)\n", left, right, abs(left-right)/2)

# ---- 4. JUMP: launch the whole car upward (off a ramp), fly, land on flat ground ----
function jump(c)
    println("\n[jump]  launch the car up at 3 m/s (≈ off the Flugplatz crest), land on flat ground")
    println("        t(s)  VertAccel(g)  z(m)   ΣFz(N)   note")
    tt = 0.0; minfz=1e9; maxaz=0.0; airstart=0.0; airend=0.0; air=false
    for i in 1:300
        tt += 1/300
        s = step!(c; zr=(0.0,0.0,0.0,0.0))           # flat road; the car was launched with w0
        fz = s.FzFL+s.FzFR+s.FzRL+s.FzRR
        minfz = min(minfz, fz); maxaz = max(maxaz, s.az/G)
        (fz < 50 && airstart==0.0) && (airstart = tt; )
        (airstart>0 && airend==0.0 && fz>1000 && tt>airstart+0.05) && (airend = tt)
        report = (i % 12 == 0) || (fz<50 && !air) || (s.az/G>1.5)
        if report
            note = fz<50 ? "AIRBORNE (Fz→0)" : (s.az/G>1.4 ? "LANDING spike" : "")
            @printf("        %4.2f   %+6.2f      %+5.2f  %6.0f   %s\n", tt, s.az/G, s.z, fz, note)
        end
        air = fz<50
    end
    @printf("\n  airborne ≈ %.2f s   min ΣFz = %.0f N (≈0 ⇒ true free-flight)   peak landing = %.2f g\n",
            (airend>airstart ? airend-airstart : 0.0), minfz, maxaz)
    @printf("  iRacing Flugplatz gold: 0.42–0.53 s air, VertAccel −0.1g crest → +1.8g landing\n")
end
jump(build(; v0=55.0, gear=0.0, w0=3.0))
println("\n=============================================================")
