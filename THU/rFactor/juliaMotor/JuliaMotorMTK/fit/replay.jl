# Telemetry replay: feed a measured Nürburgring lap's speed / steering /
# longitudinal-accel into the chassis model and compare the model's YAW RATE to
# the recorded one.  This dynamically validates the lateral tyre + chassis + load
# transfer (the well-fit part) over real driving.  Speed is PRESCRIBED from the
# .ibt (not evolved from the heuristic engine) and slip ratio κ=0, so this isolates
# the handling model; combined-slip/longitudinal replay needs the engine fit first.
#
# Run:  julia --project=. fit/replay.jl

using ModelingToolkit, OrdinaryDiffEq, DataInterpolations
using ModelingToolkit: t_nounits as t, D_nounits as D
include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
for f in ("tyre.jl","corner.jl","corner_assembly.jl")
    include(joinpath(@__DIR__, "..", "src", "components", f))
end

const DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
nfiles = filter(f -> startswith(f,"lotus49_nurburgring") && endswith(f,".ibt"), readdir(DATA))
file = nfiles[argmax([filesize(joinpath(DATA,f)) for f in nfiles])]   # longest lap
f = IBT.ibt_open(joinpath(DATA, file))
p = Setup.setup_params(f.yaml)
ch(n) = IBT.channel(f, n)
dt = 1/f.tickRate

# clean cornering window (skip the start; pick a stretch fully on-track).
# Open-loop integration drifts over time (no path-following feedback), so we use a
# short window and report correlation over growing sub-windows to show tracking.
T0, T1 = 104.0, 112.0
i0 = round(Int, T0/dt)+1
i1 = min(round(Int, T1/dt), f.nrows-1)
idx = i0:i1
tg = collect(0:dt:(length(idx)-1)*dt)
sp  = ch("Speed")[idx];  stw = ch("SteeringWheelAngle")[idx];  lax = ch("LongAccel")[idx]
yr  = ch("YawRate")[idx]; la = ch("LatAccel")[idx]; vy0 = ch("VelocityY")[idx]
ratio = p.steering_ratio

# registered interpolated inputs (no derivatives needed — they appear algebraically)
const U  = LinearInterpolation(sp, tg)
const ST = LinearInterpolation(stw ./ ratio, tg)
const AX = LinearInterpolation(lax, tg)
f_u(τ)  = U(τ);  f_st(τ) = ST(τ);  f_ax(τ) = AX(τ)
@register_symbolic f_u(t)
@register_symbolic f_st(t)
@register_symbolic f_ax(t)

# geometry / mass from setup (same as the vehicle model)
m = sum(values(p.corner_weight_N))/9.80665
front_fr = (p.corner_weight_N[:LF]+p.corner_weight_N[:RF])/sum(values(p.corner_weight_N))
L=2.41; a=(1-front_fr)*L; b=front_fr*L; tf=1.5; tr=1.5; h=0.30; Izz=890.0
mf=m*front_fr; mr=m*(1-front_fr)
fc = (Fz_static=1376.0, ks=18_250.0, cs=2500.0, m_s=120.0, m_u=20.0, kt=180_000.0, ct=300.0)
rc = (Fz_static=1650.0, ks=29_200.0, cs=3000.0, m_s=148.0, m_u=20.0, kt=200_000.0, ct=300.0)

function ReplayCar(; name)
    @named FL = CornerAssembly(corner=fc, tyre=TYRE_SKIDPAD_FRONT)
    @named FR = CornerAssembly(corner=fc, tyre=TYRE_SKIDPAD_FRONT)
    @named RL = CornerAssembly(corner=rc, tyre=TYRE_SKIDPAD_REAR)
    @named RR = CornerAssembly(corner=rc, tyre=TYRE_SKIDPAD_REAR)
    vars = @variables v(t)=0.0 r(t)=0.0 ay(t)
    spec = ((FL,a, tf/2,true,-1,-1,mf,tf),(FR,a,-tf/2,true,+1,-1,mf,tf),
            (RL,-b,tr/2,false,-1,+1,mr,tr),(RR,-b,-tr/2,false,+1,+1,mr,tr))
    eqs=Equation[]; Fyb=Any[]; Mz=Any[]
    for (ca,xi,yi,isfront,slat,slong,maxle,trk) in spec
        st = isfront ? f_st(t) : 0.0
        vx = f_u(t) - r*yi;  vy = v + r*xi
        α  = st - atan(vy, vx)
        fyb = ca.tyre.Fx*sin(st) + ca.tyre.Fy*cos(st)
        push!(Fyb, fyb); push!(Mz, ca.tyre.Mz)
        ΔFz = slat*maxle*ay*h/trk + slong*m*f_ax(t)*h/(2L)
        append!(eqs, [ca.tyre.α ~ α, ca.tyre.κ ~ 0.0, ca.corner.zr ~ 0.0, ca.corner.Fext ~ -ΔFz])
    end
    push!(eqs,
        ay ~ (Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4])/m,
        m*(D(v) + f_u(t)*r) ~ Fyb[1]+Fyb[2]+Fyb[3]+Fyb[4],
        Izz*D(r) ~ a*(Fyb[1]+Fyb[2]) - b*(Fyb[3]+Fyb[4]) + Mz[1]+Mz[2]+Mz[3]+Mz[4])
    System(eqs, t, vars, []; systems=[FL,FR,RL,RR], name)
end

println("replay window $(T0)–$(T1)s of $file  ($(length(idx)) samples, m=$(round(m,digits=0))kg)")
sys = mtkcompile(ReplayCar(name=:rep))
prob = ODEProblem(sys, [sys.v => vy0[1], sys.r => yr[1]], (0.0, tg[end]))
sol  = solve(prob, FBDF(); reltol=1e-6, abstol=1e-6, saveat=tg)

rmod = sol[sys.r]; aymod = sol[sys.ay]
n = min(length(rmod), length(yr))
function corw(x, y, k)               # correlation over the first k samples
    xs=x[1:k].-sum(x[1:k])/k; ys=y[1:k].-sum(y[1:k])/k
    sum(xs.*ys)/sqrt(sum(abs2,xs)*sum(abs2,ys)+1e-12)
end
println("\n  open-loop yaw-rate tracking (model integrated from measured u, δ, ax):")
for sec in (2.0, 4.0, 6.0, 8.0)
    k = min(round(Int, sec/dt), n)
    rms = sqrt(sum(abs2, rmod[1:k].-yr[1:k])/k)
    println("    first $(sec)s:  corr=$(round(corw(rmod,yr,k),digits=3))  RMS=$(round(rms,digits=3)) rad/s")
end
println("  (tracks short-term then drifts — open-loop has no path feedback; the")
println("   rigorous force validation is the per-corner fit, lateral R²=0.96)")
# coarse ASCII overlay of yaw rate
println("\n  yaw rate trace (· measured, * model), $(T0)s→$(T1)s:")
step = max(1, n÷60)
for k in 1:step:n
    span=4.0; col(x)=clamp(round(Int,(x+span/2)/span*48),0,48)
    line=fill(' ',49); line[col(0.0)+1]='|'; line[col(yr[k])+1]='·'; line[col(rmod[k])+1]='*'
    println("   ", String(line))
end
