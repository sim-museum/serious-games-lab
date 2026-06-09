using Pkg; Pkg.activate(; temp=true, io=devnull)
Pkg.develop([PackageSpec(path="."), PackageSpec(path="../RFactorData"), PackageSpec(path="../RFactorTelemetry")]; io=devnull)
using JuliaMotor, RFactorData
function main()
  gd=default_gamedata(); dir=joinpath(gd,"Locations","Zandvoort67")
  v=load_vehicle(joinpath(gd,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh")); m=VehicleModel(v)
  a=read_aiw(joinpath(dir,"zandvoort67.AIW"))
  res=simulate_lap(m,a;speed_factor=0.7,record_every=2)   # dense for smooth video
  open("/tmp/vid_lap.csv","w") do io
    println(io,"t,x,z,speed,yaw,gear,throttle,brake,lapdist")
    for s in res.samples
      println(io, join(round.((s.t,s.x,s.z,s.speed*3.6,s.yaw,Float64(s.gear),s.throttle,s.brake,s.lapdist);digits=3),","))
    end
  end
  println("frames available: ",length(res.samples)," laptime=",round(res.laptime;digits=1))
end
main()
