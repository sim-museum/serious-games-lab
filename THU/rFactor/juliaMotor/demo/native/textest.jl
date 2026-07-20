using GLFW, ModernGL, LinearAlgebra
using RFactorData
include("render.jl"); using .Render
RF=normpath(joinpath(@__DIR__,"..","..","..","WP","drive_c","Program Files","rFactor"))
u32(b,o)=reinterpret(UInt32,view(b,o+1:o+4))[1]
f32(b,o)=reinterpret(Float32,view(b,o+1:o+4))[1]
mas=read_mas(joinpath(RF,"GameData","Vehicles","F158","Vanwall","Vanwall VW58.mas"))
i=findfirst(e->lowercase(e.name)=="vanwall_body.gmt", mas.entries); b=extract(mas, mas.entries[i])
g=parse_gmt_indexed(b); P=g.positions; Nn=g.normals; T=g.triangles
vptr=Int(u32(b,0x190)); nv=Int(u32(b,0x17c)); attr=vptr+32nv
ok(p)=all(isfinite,p)&&all(c->abs(c)<50,p)
function bodyverts(stride)
    out=Float32[]
    uvf(k)= k<nv ? (f32(b,attr+stride*k), f32(b,attr+stride*k+4)) : (0f0,0f0)
    for t in T
        (ok(P[t[1]+1])&&ok(P[t[2]+1])&&ok(P[t[3]+1])) || continue
        for vi in t
            p=P[vi+1]; n=vi+1<=length(Nn) ? Nn[vi+1] : (0f0,1f0,0f0); all(isfinite,n)||(n=(0f0,1f0,0f0))
            uv=uvf(vi)
            append!(out, Float32[-p[3],p[2],p[1], -n[3],n[2],n[1], 1f0,1f0,1f0, uv[1],-uv[2]])
        end
    end
    out
end
const W,H=720,480
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
win=GLFW.CreateWindow(W,H,"t"); GLFW.MakeContextCurrent(win); glEnable(GL_DEPTH_TEST)
prog=Render.program(); glUseProgram(prog); glUniform3f(glGetUniformLocation(prog,"uLightDir"),0.4f0,1f0,0.3f0)
tex=Render.load_dds(read(joinpath(RF,"GameData","Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.dds")))
println("livery tex id=",tex)
function render(stride,fname)
    vao,n=Render.upload(bodyverts(stride)); it=Render.Item(vao,n,tex,(1f0,1f0,1f0))
    # 3/4 view of the body (centred near origin; body spans X≈[-2.1,2], Y[0,1.1], Z[-0.6,0.8])
    eye=[3.5,2.2,3.0]; ctr=[0.0,0.5,0.0]
    vp=Render.perspective(deg2rad(45f0),Float32(W/H),0.1f0,100f0)*Render.lookat(Float32.(eye),Float32.(ctr),Float32[0,1,0])
    glViewport(0,0,W,H); glClearColor(0.5,0.6,0.72,1); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    Render.draw(prog,it,vp,Render.ident()); glFinish()
    buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fname,"w") do io; write(io,"P6\n$W $H\n255\n"); for y in H:-1:1,x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
    println("wrote ",fname)
end
render(8,"/tmp/body_s8.ppm")
render(12,"/tmp/body_s12.ppm")
GLFW.Terminate()
