# FULL driven telemetry replay: feed a measured lap's steering / throttle / brake /
# gear into DrivenVehicle and let SPEED evolve freely from the (now telemetry-fit)
# engine + driveline + brakes.  Compare the model's speed AND yaw rate to the
# recording — the end-to-end test of the whole longitudinal+lateral model.
#
# Open-loop: no path-following or speed feedback, so both drift over time (the real
# driver closes those loops).  Use a short window and report growing-window tracking.
#
# Run:  julia --project=. fit/replay_driven.jl

using ModelingToolkit, OrdinaryDiffEq, DataInterpolations
using ModelingToolkit: t_nounits as t, D_nounits as D
include(joinpath(@__DIR__, "..", "src", "ibt.jl"));   using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
for fnm in ("tyre.jl","corner.jl","corner_assembly.jl","powertrain.jl","vehicle_driven.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end

const DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
nfiles = filter(f -> startswith(f,"lotus49_nurburgring") && endswith(f,".ibt"), readdir(DATA))
file = nfiles[argmax([filesize(joinpath(DATA,f)) for f in nfiles])]
f = IBT.ibt_open(joinpath(DATA, file))
p = Setup.setup_params(f.yaml); gr_table = p.gear_ratios; ratio = p.steering_ratio
ch(n) = IBT.channel(f, n);  dt = 1/f.tickRate

T0, T1 = 60.0, 72.0                              # 12 s window with accel + braking
i0 = round(Int,T0/dt)+1; i1 = min(round(Int,T1/dt), f.nrows-1); idx = i0:i1
tg = collect(0:dt:(length(idx)-1)*dt)
spd=ch("Speed")[idx]; stw=ch("SteeringWheelAngle")[idx]; thr=ch("Throttle")[idx]
brk=ch("Brake")[idx]; gr=ch("Gear")[idx]; yr=ch("YawRate")[idx]; vy=ch("VelocityY")[idx]; la=ch("LatAccel")[idx]
grsel = [gr_table[clamp(round(Int,g),1,length(gr_table))] for g in gr]   # gear index → ratio

const ST=LinearInterpolation(stw./ratio,tg); const TH=LinearInterpolation(thr,tg)
const BR=LinearInterpolation(brk,tg);        const GR=LinearInterpolation(grsel,tg)
f_st(τ)=ST(τ); f_th(τ)=TH(τ); f_br(τ)=BR(τ); f_gr(τ)=GR(τ)
@register_symbolic f_st(t)
@register_symbolic f_th(t)
@register_symbolic f_br(t)
@register_symbolic f_gr(t)

function Replay(; name)
    @named car = DrivenVehicle()
    eqs = [car.δ ~ f_st(t), car.throttle ~ f_th(t), car.brake ~ f_br(t), car.gear ~ f_gr(t)]
    System(eqs, t, Num[], []; systems=[car], name)
end
println("FULL driven replay  $(T0)–$(T1)s of $file")
sys = mtkcompile(Replay(name=:r))
u0 = spd[1]
prob = ODEProblem(sys, [sys.car.u=>u0, sys.car.v=>vy[1], sys.car.r=>yr[1],
                        sys.car.ωf=>u0/0.30, sys.car.ωr=>u0/0.33], (0.0, tg[end]))
sol  = solve(prob, FBDF(); reltol=1e-6, abstol=1e-6, saveat=tg)
println("  retcode=$(sol.retcode)  states=$(length(unknowns(sys)))")

umod=sol[sys.car.u]; rmod=sol[sys.car.r]; n=min(length(umod),length(spd))
function rms(a,b,k); sqrt(sum(abs2,a[1:k].-b[1:k])/k); end
function corw(x,y,k); xs=x[1:k].-sum(x[1:k])/k; ys=y[1:k].-sum(y[1:k])/k; sum(xs.*ys)/sqrt(sum(abs2,xs)*sum(abs2,ys)+1e-12); end
println("\n  SPEED (model evolves freely from engine/brake) vs measured:")
for sec in (3.0,6.0,9.0,12.0)
    k=min(round(Int,sec/dt),n); k<2 && continue
    println("    first $(sec)s:  corr=$(round(corw(umod,spd,k),digits=3))  RMS=$(round(rms(umod,spd,k),digits=2)) m/s  (Δend=$(round(umod[k]-spd[k],digits=1)))")
end
println("  YAW RATE vs measured:")
for sec in (3.0,6.0,9.0,12.0)
    k=min(round(Int,sec/dt),n); k<2 && continue
    println("    first $(sec)s:  corr=$(round(corw(rmod,yr,k),digits=3))  RMS=$(round(rms(rmod,yr,k),digits=3)) rad/s")
end
println("\n  speed trace (· measured, * model), $(T0)→$(T1)s  [$(round(minimum(spd)))–$(round(maximum(spd))) m/s]:")
lo,hi=minimum(spd)-3,maximum(spd)+3; step=max(1,n÷55)
for k in 1:step:n
    col(x)=clamp(round(Int,(x-lo)/(hi-lo)*52),0,52)
    line=fill(' ',53); line[col(spd[k])+1]='·'; line[col(umod[k])+1]='*'
    println("   ",String(line))
end
