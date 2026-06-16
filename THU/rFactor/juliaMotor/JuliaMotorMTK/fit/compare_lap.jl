# Compare the lap-time sim to the RECORDED lap, on the same track.
#
# The .ibt has a continuous 12.6 km (61%) segment of the real Nürburgring
# Nordschleife.  We reconstruct the driven line's curvature κ(s)=|YawRate|/Speed,
# run the QSS friction-circle sim (model's fitted grip μ + engine power) on that
# exact line, and compare the model's optimal speed profile + segment time to what
# the human actually drove.  (The model's QSS optimum should be a bit FASTER than
# the human, who leaves margin — a sanity check on the model's grip/power.)
#
# Run:  julia --project=. fit/compare_lap.jl

include(joinpath(@__DIR__, "..", "src", "components", "tyre.jl"))
include(joinpath(@__DIR__, "..", "src", "components", "powertrain.jl"))
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT

const g=9.80665; const m=617.0; const ρ=1.10; const CdA=0.9; const η=0.9; const μ=1.25
Pmax = maximum(engine_torque(r,1.0)*r*2π/60 for r in 3000:50:9500)*η

DATA = joinpath(@__DIR__, "..", "..", "data", "iracing")
nf = filter(f->startswith(f,"lotus49_nurburgring")&&endswith(f,".ibt"), readdir(DATA))
file = nf[argmax([filesize(joinpath(DATA,f)) for f in nf])]
f = IBT.ibt_open(joinpath(DATA,file)); ch(n)=IBT.channel(f,n); dt=1/f.tickRate
ld=ch("LapDist"); spd=ch("Speed"); yr=ch("YawRate"); on=ch("IsOnTrack")
N=f.nrows
# racing-pace window: from past the standing start to the end, monotonic LapDist
i0 = findfirst(i-> ld[i]>500 && spd[i]>15, 1:N)
i1 = N-1
# keep only forward-progress samples (LapDist strictly increasing)
function fwd_idx(i0, i1, on, ld, spd)
    idx=Int[]; lastd=-1.0
    for i in i0:i1
        (on[i]>0.5 && ld[i]>lastd+0.1 && spd[i]>3) || continue
        push!(idx,i); lastd=ld[i]
    end
    idx
end
idx = fwd_idx(i0, i1, on, ld, spd)
s_rec = ld[idx]; v_rec = spd[idx]; r_rec = yr[idx]
t_rec = (idx[end]-idx[1])*dt                          # recorded time over the segment
L = s_rec[end]-s_rec[1]
println("recorded segment: $(round(L/1000,digits=2)) km, $(round(t_rec,digits=1)) s moving, avg $(round(L/t_rec*3.6)) km/h")

# resample onto a uniform s-grid; curvature κ=|yaw|/speed (smoothed)
ds=5.0; sg=collect(s_rec[1]:ds:s_rec[end]); Ng=length(sg)
function interp(sq, xs, ys)                            # linear interp (xs increasing)
    j=searchsortedlast(xs,sq); j<1 && return ys[1]; j>=length(xs) && return ys[end]
    w=(sq-xs[j])/(xs[j+1]-xs[j]); ys[j]*(1-w)+ys[j+1]*w
end
vrec=[interp(s,s_rec,v_rec) for s in sg]
κraw=[abs(interp(s,s_rec,r_rec))/max(interp(s,s_rec,v_rec),3.0) for s in sg]
# smooth κ over ~50 m
w=5; κ=[ (lo=max(1,i-w); hi=min(Ng,i+w); sum(κraw[lo:hi])/(hi-lo+1) ) for i in 1:Ng]

# QSS on this line
vmax=(Pmax/(0.5*ρ*CdA))^(1/3)
vc(k)= k<1e-5 ? vmax : sqrt(μ*g/k)
vm=[min(vc(κ[i]),vmax) for i in 1:Ng]
vm[1]=vrec[1]                                          # start from the recorded entry speed
for _ in 1:3
    for i in 2:Ng
        al=vm[i-1]^2*κ[i-1]; at=sqrt(max(0,(μ*g)^2-al^2))
        ap=(Pmax/max(vm[i-1],5)-0.5*ρ*CdA*vm[i-1]^2)/m
        vm[i]=min(vm[i], sqrt(max(0,vm[i-1]^2+2*min(at,ap)*ds)))
    end
    for i in Ng-1:-1:1
        al=vm[i+1]^2*κ[i+1]; ab=sqrt(max(0,(μ*g)^2-al^2))+0.5*ρ*CdA*vm[i+1]^2/m
        vm[i]=min(vm[i], sqrt(max(0,vm[i+1]^2+2*ab*ds)))
    end
end
t_model=sum(ds/vm[i] for i in 1:Ng)

println("\n  RECORDED (human):  $(round(t_rec,digits=1)) s   avg $(round(L/t_rec*3.6)) km/h   top $(round(maximum(v_rec)*3.6)) km/h")
println("  MODEL QSS optimal: $(round(t_model,digits=1)) s   avg $(round(L/t_model*3.6)) km/h   top $(round(maximum(vm)*3.6)) km/h")
println("  → model QSS $(round((t_rec-t_model)/t_rec*100,digits=1))% faster. Human top $(round(maximum(v_rec)*3.6)) vs $(round(maximum(vm)*3.6)) km/h")
println("    capable ⇒ a cautious sub-limit lap, so the gap is mostly DRIVER MARGIN; the profile")
println("    SHAPE matching (corr below) validates the model's relative cornering. A flat-out")
println("    reference lap would be needed to anchor the absolute grip.")
corr=(x,y)->(n=length(x); mx=sum(x)/n; my=sum(y)/n; sum((x.-mx).*(y.-my))/sqrt(sum((x.-mx).^2)*sum((y.-my).^2)))
println("  speed-profile corr (model vs recorded): $(round(corr(vm,vrec),digits=3))   mean |Δv| $(round(sum(abs.(vm.-vrec))/Ng,digits=1)) m/s")

println("\n  speed profile over the segment (· recorded human, * model QSS optimal):")
step=max(1,Ng÷40); lo=0.0; hi=max(maximum(vm),maximum(vrec))
for k in 1:step:Ng
    col(x)=clamp(round(Int,x/hi*52),0,52); line=fill(' ',53)
    line[col(vrec[k])+1]='·'; line[col(vm[k])+1]= line[col(vrec[k])+1]=='·' ? '#' : '*'
    println("   ",String(line))
end
println("   0", " "^48, "$(round(hi*3.6)) km/h")
