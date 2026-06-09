using Pkg; Pkg.activate(; temp=true, io=devnull)
Pkg.develop([PackageSpec(path="."), PackageSpec(path="../RFactorData")]; io=devnull)
using JuliaMotor, RFactorData
function main()
  dir=joinpath(default_gamedata(),"Locations","Zandvoort67")
  mas=read_mas(joinpath(dir,"Zand67.mas"))
  cls(n)= startswith(n,"asphalt")||n=="pitline.gmt"||startswith(n,"curb") ? "road" :
          startswith(n,"grass") ? "grass" :
          (startswith(n,"sand")||startswith(n,"hayba")) ? "sand" : "skip"
  open("/tmp/demo_track.csv","w") do io
    println(io,"type,x1,z1,x2,z2,x3,z3")
    for nm in JuliaMotor.hat_meshes(dir)
      c=cls(nm); c=="skip" && continue
      e=findfirst(x->lowercase(x.name)==nm,mas.entries); e===nothing && continue
      g=parse_gmt(extract(mas,mas.entries[e])); P=g.positions
      for t in g.triangles
        p1=P[t[1]+1];p2=P[t[2]+1];p3=P[t[3]+1]
        println(io, c,",",join(round.((p1[1],p1[3],p2[1],p2[3],p3[1],p3[3]);digits=2),","))
      end
    end
  end
  println("track re-exported with types")
end
main()
