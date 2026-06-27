# Offscreen lineup of the player Lotus + the 5 AI chassis — verifies E8 (distinct
# GPL cars, auto-levelled onto a common floor).  No track/physics: just the cars.
using GLFW, ModernGL, LinearAlgebra
include("render.jl"); using .Render
const BASE = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/cars/cars67"
aiw(lf,rf,lr,rr) = Tuple{Float32,Float32,Bool,Float32,String}[
    ( 1.05f0, 0.62f0, true,  0.31f0, lf), ( 1.05f0, -0.62f0, true,  0.31f0, rf),
    (-1.15f0, 0.66f0, false, 0.34f0, lr), (-1.15f0, -0.66f0, false, 0.34f0, rr)]
SPECS = [("Lotus","lotus","lotus.3do",("lotwlf","lotwrf","lotwlr","lotwrr")),
         ("Ferrari","ferrari","ferrari.3do",("f222lf","f222rf","f444lr","f444rr")),
         ("Brabham","brabham","brabham.3do",("brablf","brabrf","brablr","brabrr")),
         ("BRM","brm","brm.3do",("brm2lf","brm2rf","brm4lr","brm4rr")),
         ("Eagle","eagle","eagle.3do",("eotwlf","eotwrf","eotwlr","eotwrr")),
         ("Cooper","coventry","coventry.3do",("cooplf","cooprf","cooplr","cooprr"))]
const W,H = 1600, 700
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false); GLFW.WindowHint(GLFW.SAMPLES,8)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
win=GLFW.CreateWindow(W,H,"grid"); GLFW.MakeContextCurrent(win)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
prog=Render.program(); glUseProgram(prog)
glUniform3f(glGetUniformLocation(prog,"uLightDir"),0.4f0,1.0f0,0.25f0)
skyprog=Render.skyprogram(); skyvao=Render.empty_vao()
depthprog=Render.depthprogram(); (shadowfbo,shadowtex)=Render.make_shadow_fbo()
const LIGHTDIR=Float32[0.4,1.0,0.25]
# a flat ground quad
ground = let v=Float32[]; g=40f0
  for (x,z) in ((-g,-g),(g,-g),(g,g),(-g,-g),(g,g),(-g,g))
    append!(v,(x,0f0,z, 0f0,1f0,0f0, 0.55f0,0.54f0,0.50f0, 0f0,0f0)); end
  vao,n=Render.upload(v); Render.Item(vao,n,GLuint(0),(0.55f0,0.54f0,0.50f0)); end
# load the 6 cars; level all to the Lotus floor
lotusparts = Render.extract_gpl_car(joinpath(BASE,"lotus","lotus.3do"); exclude=("ltraymap","lshad"), maxlat=0.9f0)
const FLOOR = Render.parts_bbox(lotusparts).ymin + 0.30f0
cars = [Render.load_gpl_car(nm, joinpath(BASE,dir), body, aiw(w...); exclude=("ltraymap","lshad"), maxlat=0.9f0, body_floor=FLOOR) for (nm,dir,body,w) in SPECS]
for c in cars; println(c.name, " off=", c.body_off, " parts=", length(c.body)); end
const PROJ = Render.perspective(deg2rad(40f0), Float32(W/H), 0.3f0, 600f0)
# place cars in a row along Z (lateral), facing +X (toward camera-ish)
carX(i) = Render.translate(Float32[0f0, 0f0, Float32((i-3.5)*3.2)]) * Render.roty(Float32(deg2rad(-25)))
spin=0f0
function draw_one(vp, c, i; depth=false, dp=nothing)
  M = carX(i)
  bodyM = M * Render.translate(collect(c.body_off))
  if depth
    for it in c.body; Render.draw_depth(dp,it,bodyM); end
    for (wx,wz,_,r,nm) in c.wheelspec, it in c.wheels[nm]; Render.draw_depth(dp,it, M*Render.translate(Float32[wx,r,wz])); end
  else
    for it in c.body; Render.draw(prog,it,vp,bodyM; bright=1.2, spec=0.1, ambfill=0.6); end
    for (wx,wz,_,r,nm) in c.wheelspec, it in c.wheels[nm]; Render.draw(prog,it,vp, M*Render.translate(Float32[wx,r,wz]); bright=1.3); end
  end
end
eye=Float32[9.0, 4.5, 0.0]; ctr=Float32[0.0, 0.5, 0.0]
lightVP=Render.light_vp(Float32[0,0,0],LIGHTDIR)
Render.shadow_pass(depthprog,shadowfbo,lightVP) do dp
  Render.draw_depth(dp, ground, Render.ident())
  for (i,c) in enumerate(cars); draw_one(nothing,c,i; depth=true, dp=dp); end
end
glViewport(0,0,W,H); glClearColor(0.5f0,0.6f0,0.7f0,1f0); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
vp=PROJ*Render.lookat(eye,ctr,Float32[0,1,0])
Render.draw_sky(skyprog,skyvao,inv(vp),eye,LIGHTDIR)
Render.set_scene_uniforms(prog,eye; fognear=200f0, fogfar=500f0); Render.bind_shadow(prog,shadowtex,lightVP)
Render.draw(prog, ground, vp, Render.ident(); bright=0.9)
for (i,c) in enumerate(cars); draw_one(vp,c,i); end
glFinish(); buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
fn="/tmp/claude-1001/-home-g-sgl-THU-rFactor-juliaMotor/1f4860c5-f78a-4dc6-91d6-37cdf6d8d318/scratchpad/grid.ppm"
open(fn,"w") do io; write(io,"P6\n$W $H\n255\n"); for y in H:-1:1,x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
println("wrote ",fn)
GLFW.Terminate()
