using GLFW, ModernGL, LinearAlgebra
using JuliaMotor, RFactorData
include("render.jl"); using .Render
const GD = default_gamedata()
const CARP = Render.extract_car_parts(GD)
const W,H = 1100, 700
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
win=GLFW.CreateWindow(W,H,"p"); GLFW.MakeContextCurrent(win); glEnable(GL_DEPTH_TEST)
prog=Render.program(); glUseProgram(prog); glUniform3f(glGetUniformLocation(prog,"uLightDir"),0.5f0,1f0,0.35f0)
carItems = Render.build_track(CARP, Render.car_texture_index(GD))
println("car parts textured: ", count(it->it.tex!=0,carItems),"/",length(carItems))
wheel = Render.item(Render.wheel_mesh(0.33f0,0.19f0))
WH=((1.4f0,0.33f0,0.735f0),(1.4f0,0.33f0,-0.735f0),(-1.4f0,0.34f0,0.705f0),(-1.4f0,0.34f0,-0.705f0))
function shot(fname, eye, ctr)
    vp=Render.perspective(deg2rad(40f0),Float32(W/H),0.1f0,100f0)*Render.lookat(Float32.(eye),Float32.(ctr),Float32[0,1,0])
    glViewport(0,0,W,H); glClearColor(0.55,0.63,0.73,1); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    for it in carItems; Render.draw(prog,it,vp,Render.ident(); bright=1.5); end
    for (x,y,z) in WH; Render.draw(prog,wheel,vp,Render.translate(Float32[x,y,z])); end
    glFinish()
    buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fname,"w") do io; write(io,"P6\n$W $H\n255\n"); for y in H:-1:1,x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
    println("wrote ",fname)
end
# front-3/4 from ahead-left-above (nose at +X), and a side view
shot("/tmp/car_34.ppm",  [4.5,1.7,2.6], [0.2,0.45,0.0])
shot("/tmp/car_side.ppm",[0.0,0.7,5.0], [0.0,0.5,0.0])
GLFW.Terminate()
