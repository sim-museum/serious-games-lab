using Pkg; Pkg.activate(; temp=true, io=devnull)
Pkg.develop([PackageSpec(path="."), PackageSpec(path="../RFactorData"), PackageSpec(path="../RFactorTelemetry")]; io=devnull)
using JuliaMotor, RFactorData, RFactorTelemetry, Statistics
function main()
  gd=default_gamedata(); dir=joinpath(gd,"Locations","Zandvoort67")
  v=load_vehicle(joinpath(gd,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh")); m=VehicleModel(v)
  a=read_aiw(joinpath(dir,"zandvoort67.AIW")); mp=mainpath(a)
  mas=read_mas(joinpath(dir,"Zand67.mas"))

  # 1) track road triangles (asphalt + pitline + curb) as X,Z polygons
  open("/tmp/demo_track.csv","w") do io
    println(io,"x1,z1,x2,z2,x3,z3")
    for nm in ("asphalt01.gmt","asphalt03.gmt","asphalt04.gmt","pitline.gmt","curb01.gmt")
      e=findfirst(x->lowercase(x.name)==nm,mas.entries); e===nothing && continue
      g=parse_gmt(extract(mas,mas.entries[e])); P=g.positions
      for t in g.triangles
        p1=P[t[1]+1];p2=P[t[2]+1];p3=P[t[3]+1]
        println(io, join(round.((p1[1],p1[3],p2[1],p2[3],p3[1],p3[3]);digits=2),","))
      end
    end
  end

  # 2) simulated lap trajectory
  res=simulate_lap(m,a;speed_factor=0.7,record_every=5)
  open("/tmp/demo_simlap.csv","w") do io
    println(io,"t,x,z,speed,lapdist")
    for s in res.samples
      println(io, join(round.((s.t,s.x,s.z,s.speed*3.6,s.lapdist);digits=2),","))
    end
  end
  println("sim lap: completed=",res.completed," time=",round(res.laptime;digits=1),"s samples=",length(res.samples))

  # 3) capstone replay window vs telemetry (speed + yaw from inputs alone)
  s=read_daq_csv(only(filter(p->occursin("21_05_55",basename(p)),find_daq_logs())))
  t=s["Time"];spd=s["Ground Speed"]./3.6;yawm=s["Gyro - Yaw Angular Velocity"]
  steer=deg2rad.(s["Steering Wheel Pct"].*0.2);thr=s["Throttle Position"]./100;brk=s["Brake Pedal Position"]./100
  gear=s["Gear"];fuel=s["Fuel Level"]
  # pick a clean 30s window with cornering
  i0=findfirst(i->t[i]>60 && all(spd[i:i+1500].>8), eachindex(t)); win=1500
  rng=i0:i0+win
  vp,rp=replay_inputs(m,t[rng],steer[rng],thr[rng],brk[rng],gear[rng],fuel[rng];v0=spd[i0],yaw0=yawm[i0])
  open("/tmp/demo_replay.csv","w") do io
    println(io,"t,meas_speed,pred_speed,meas_yaw,pred_yaw")
    for (k,i) in enumerate(rng)
      println(io, join(round.((t[i]-t[i0], spd[i]*3.6, vp[k]*3.6, yawm[i], rp[k]);digits=3),","))
    end
  end

  # 4) tire lateral-force curve (calibrated)
  open("/tmp/demo_tire.csv","w") do io
    println(io,"slip_deg,fy_per_load")
    for sl in 0:0.5:25
      fy=lateral_force(m.tire_f, sind(sl), 3000.0, 30.0)/3000.0
      println(io, round(sl;digits=2),",",round(fy;digits=4))
    end
  end
  println("demo data exported")
end
main()
