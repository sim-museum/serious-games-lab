# Lap-time simulation on a racing line (quasi-steady-state friction-circle method),
# using the model's FITTED tyre grip and engine power.
#
# For each point on the line: the cornering speed limit is √(μ·g/κ); a forward pass
# limits acceleration to what the tyre (friction circle, after lateral demand) and
# the engine power allow; a backward pass limits speed so the tyre can brake for the
# next corner.  v(s) = min of the three; lap time = ∮ ds/v.
#
# Run:  julia --project=. fit/laptime.jl

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))         # tyre μ
include(joinpath(@__DIR__, "..", "src", "components", "powertrain.jl"))   # engine_torque

const g = 9.80665; const m = 617.0; const ρ = 1.10; const CdA = 0.9; const η = 0.9
const μ  = 1.25                       # peak combined grip (model's ~1.25 g lateral)
const final = 4.11

# peak engine power from the FITTED curve (crank, ×η at the wheels)
Pmax = maximum(engine_torque(rpm, 1.0)*rpm*2π/60 for rpm in 3000:50:9500) * η
println("model: μ=$(μ), peak power ≈ $(round(Pmax/745.7)) hp ($(round(Pmax/1000)) kW), mass $(m) kg")

# ---- racing line: a closed test circuit as (segment length [m], radius [m]) -----
# radius Inf = straight.  ~360° of total turning for a plausible loop.
segs = [(700.0, Inf), (88.0, 28.0), (350.0, Inf), (173.0, 110.0), (250.0, Inf),
        (94.0, 45.0), (450.0, Inf), (209.0, 200.0), (200.0, Inf), (73.0, 35.0),
        (300.0, Inf), (110.0, 70.0), (400.0, Inf)]
ds = 1.0
κ = Float64[]
for (len, R) in segs, _ in 1:round(Int, len/ds)
    push!(κ, R == Inf ? 0.0 : 1.0/R)
end
N = length(κ); S = N*ds
println("circuit: $(round(S/1000, digits=2)) km, $(count(s -> s[2] != Inf, segs)) corners (R $(round(Int,minimum(s[2] for s in segs if s[2]!=Inf)))–$(round(Int,maximum(s[2] for s in segs if s[2]!=Inf))) m)")

vmax = (Pmax/(0.5*ρ*CdA))^(1/3)                         # power-vs-drag top speed
vcorner(k) = k < 1e-5 ? vmax : sqrt(μ*g/k)
v = [min(vcorner(κ[i]), vmax) for i in 1:N]

# forward (accel) + backward (brake) passes, wrapped for closure, iterate to converge
for _ in 1:4
    for i in 1:N                                        # forward: traction + power limited
        j = i == 1 ? N : i-1
        alat = v[j]^2*κ[j]
        atyre = sqrt(max(0.0, (μ*g)^2 - alat^2))
        apow  = (Pmax/max(v[j],5.0) - 0.5*ρ*CdA*v[j]^2)/m
        vnew = sqrt(max(0.0, v[j]^2 + 2*min(atyre, apow)*ds))
        v[i] = min(v[i], vnew)
    end
    for i in N:-1:1                                     # backward: braking limited (drag aids)
        j = i == N ? 1 : i+1
        alat = v[j]^2*κ[j]
        abrake = sqrt(max(0.0, (μ*g)^2 - alat^2)) + 0.5*ρ*CdA*v[j]^2/m
        vnew = sqrt(max(0.0, v[j]^2 + 2*abrake*ds))
        v[i] = min(v[i], vnew)
    end
end

laptime = sum(ds/v[i] for i in 1:N)
imin = argmin(v)
println("\n  LAP TIME = $(floor(Int,laptime÷60)):$(lpad(round(laptime%60,digits=2),5,'0'))  ($(round(laptime,digits=2)) s)")
println("  top speed $(round(maximum(v)*3.6)) km/h   slowest corner $(round(minimum(v)*3.6)) km/h (R=$(round(Int,1/κ[imin])) m)")
println("  avg speed $(round(S/laptime*3.6)) km/h")

# ASCII speed-vs-distance trace
println("\n  speed profile (▁ slow → █ fast) over the lap:")
blocks = collect("▁▂▃▄▅▆▇█"); W = 100; line = Char[]
for c in 1:W
    i = clamp(round(Int, (c-0.5)/W*N)+1, 1, N)
    lvl = clamp(round(Int, (v[i]-minimum(v))/(maximum(v)-minimum(v))*7)+1, 1, 8)
    push!(line, blocks[lvl])
end
println("   ", String(line))
println("   start", " "^(W-9), "finish   ($(round(minimum(v)*3.6))–$(round(maximum(v)*3.6)) km/h)")

# ===========================================================================
# Dynamic confirmation: drive the CLOSED-LOOP car around the racing line.
# References are distance-based (speed profile v(s), yaw rate = u·κ(s)); a CVT-like
# gear holds the engine near peak power.  Lap time = sim time to cover one lap.
# ===========================================================================
using ModelingToolkit, OrdinaryDiffEq, DataInterpolations
using ModelingToolkit: t_nounits as t, D_nounits as D
for fnm in ("corner.jl","corner_assembly.jl","vehicle_driven.jl","driver.jl")
    include(joinpath(@__DIR__, "..", "src", "components", fnm))
end
sgrid = collect(0:ds:(N-1)*ds)
const VS = LinearInterpolation(v, sgrid);  const KS = LinearInterpolation(κ, sgrid)
fv(x) = VS(clamp(x, 0.0, sgrid[end]));  fk(x) = KS(clamp(x, 0.0, sgrid[end]))
@register_symbolic fv(t)
@register_symbolic fk(t)
function LapRun(; name)
    @named drv = ClosedLoopVehicle(Kpr = 0.5, Kir = 0.25)     # gentler steering (full-lap robustness)
    vars = @variables s(t)=0.0
    # target 85% of the QSS grip limit — a real driver leaves margin; running the
    # dynamic car at the theoretical limit through tight corners is on the stability edge.
    eqs = [D(s) ~ drv.car.u,
           drv.uref ~ 0.85*fv(s),
           drv.rref ~ drv.car.u*fk(s),                       # yaw to follow the path at the ACTUAL speed
           drv.gear_in ~ min(1.72, max(0.846, 50.0/(drv.car.u + 1.0)))]   # cap to 2nd → less slow-corner wheelspin
    System(eqs, t, vars, []; systems = [drv], name)
end
println("\n  driving the closed-loop car around the line (dynamic)…")
lap = mtkcompile(LapRun(name = :lap))
u0 = v[1]
prob = ODEProblem(lap, [lap.s => 0.0, lap.drv.car.u => u0,
                        lap.drv.car.ωf => u0/0.30, lap.drv.car.ωr => u0/0.33], (0.0, 120.0))
sol = solve(prob, FBDF(); reltol = 1e-5, abstol = 1e-5)
sv = sol[lap.s]; idx = findfirst(≥(S), sv)
println("  reached $(round(maximum(sv)/S*100))% of the lap (retcode=$(sol.retcode))")
if idx !== nothing
    dyn = sol.t[idx]
    println("  DYNAMIC lap time = $(round(dyn, digits=2)) s  (at 85% of the QSS limit, gentle driver)")
    println("  vs QSS optimal $(round(laptime, digits=2)) s   avg speed $(round(S/dyn*3.6)) km/h")
else
    println("  dynamic full-lap driver not robust enough through the tight corners — QSS ($(round(laptime,digits=2)) s) is the lap-time result")
end
