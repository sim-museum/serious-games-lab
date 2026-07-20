# Offscreen integration test: the GPL Lotus 49 (body + 4 wheels) on the real
# Zandvoort track + JuliaMotor physics — for tuning body centering + wheel hub
# positions before wiring the same into drive_native.jl.  Renders chase + cockpit.
using GLFW, ModernGL, LinearAlgebra
using JuliaMotor, RFactorData
include("render.jl"); using .Render

const GD  = default_gamedata()
const DIR = joinpath(GD, "Locations", "Zandvoort67")
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH); const AIW = read_aiw(joinpath(DIR,"zandvoort67.AIW"))
const TERRAIN = TriangleHAT(DIR); const CAR = DriveCar(MODEL, AIW; terrain=TERRAIN)
const TRACK = Render.extract_track(DIR)

# ---- GPL Lotus 49 ----
const LOTDIR = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","cars","cars67","lotus"))
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOTBODY = Render.extract_gpl_car(joinpath(LOTDIR,"lotus.3do"); exclude=("ltraymap","lshad","lohand","lotarms",Render.STEER_TEX...))  # no hands
# wheels: KEEP untextured tris (the black tyre body) — only the body drops "".
const SWP,SWC,SWA = Render.extract_gpl_steering(joinpath(LOTDIR,"lotus.3do"))
SWANG = 0.0
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), grey=(0.13f0,0.13f0,0.14f0)), GPLTEX)

# tunables (rig frame: X fwd, Y up, Z left) -----------------------------------
const BODY_OFF = Float32[-0.55, 0.30, 0.0]    # center body on X, lift onto wheels
const FRONT_X  =  1.05f0; const REAR_X = -1.15f0
const TRACK_F  =  0.62f0; const TRACK_R = 0.66f0
const HUB_YF   =  0.31f0; const HUB_YR  = 0.34f0       # wheel-centre height = radius

const W,H = 1280, 720
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false); GLFW.WindowHint(GLFW.SAMPLES,4)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
win=GLFW.CreateWindow(W,H,"g"); GLFW.MakeContextCurrent(win)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
prog=Render.program(); glUseProgram(prog)
glUniform3f(glGetUniformLocation(prog,"uLightDir"),0.4f0,1.0f0,0.25f0)
skyprog=Render.skyprogram(); skyvao=Render.empty_vao()
depthprog=Render.depthprogram(); (shadowfbo,shadowtex)=Render.make_shadow_fbo()
const LIGHTDIR=Float32[0.4,1.0,0.25]
const TEXIDX=Render.texture_index(DIR)
trackItems=Render.build_track(TRACK,TEXIDX)
carItems=Render.build_gpl(LOTBODY, GPLTEX)
swItems=Render.build_gpl(SWP, GPLTEX)
wheelLF=load_wheel("lotwlf"); wheelRF=load_wheel("lotwrf"); wheelLR=load_wheel("lotwlr"); wheelRR=load_wheel("lotwrr")
# (mesh, hubX, hubZ, isFront, wheelItems)
WHEELS = [(FRONT_X, TRACK_F, true, wheelLF), (FRONT_X, -TRACK_F, true, wheelRF),
          (REAR_X,  TRACK_R, false, wheelLR), (REAR_X, -TRACK_R, false, wheelRR)]
const PROJ = Render.perspective(deg2rad(60f0), Float32(W/H), 0.3f0, 4000f0)

cs = spawn(CAR; v0=0.0)
for _ in 1:200; global cs = step!(cs, CAR, DriveInput(throttle=0.4); dt=1/60); end
wx,wy,wz = cs.x, cs.y, -cs.z
carModel = Render.translate(Float32[wx,wy,wz]) * Render.roty(Float32(cs.θ))
bodyModel = carModel * Render.translate(BODY_OFF)
δ = 0.35f0; spin = 1.2f0
function wheelmat(hx,hz,hyf,front)
    carModel * Render.translate(Float32[hx, front ? HUB_YF : HUB_YR, hz]) *
        (front ? Render.roty(δ) : Render.ident()) * Render.rotz(spin)
end

function snap(fn, eye, ctr)
    lightVP=Render.light_vp(Float32[wx,wy,wz],LIGHTDIR)
    Render.shadow_pass(depthprog,shadowfbo,lightVP) do dp
        for it in trackItems; Render.draw_depth(dp,it,Render.ident()); end
        for it in carItems; Render.draw_depth(dp,it,bodyModel); end
        for (hx,hz,fr,wh) in WHEELS, it in wh; Render.draw_depth(dp,it,wheelmat(hx,hz,HUB_YF,fr)); end
    end
    glViewport(0,0,W,H); glClearColor(0.2f0,0.22f0,0.25f0,1f0); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    vp=PROJ*Render.lookat(Float32.(eye),Float32.(ctr),Float32[0,1,0])
    Render.draw_sky(skyprog,skyvao,inv(vp),Float32.(eye),LIGHTDIR)
    Render.set_scene_uniforms(prog,Float32.(eye); fognear=160f0, fogfar=1300f0); Render.bind_shadow(prog,shadowtex,lightVP)
    for it in trackItems; Render.draw(prog,it,vp,Render.ident()); end
    for it in carItems; Render.draw(prog,it,vp,bodyModel; bright=1.15, spec=0.4); end
    swm=bodyModel*Render.translate(SWC)*Render.rotaxis(SWA,Float32(SWANG))*Render.translate(-SWC)
    for it in swItems; Render.draw(prog,it,vp,swm; bright=1.2); end
    for (hx,hz,fr,wh) in WHEELS, it in wh; Render.draw(prog,it,vp,wheelmat(hx,hz,HUB_YF,fr); bright=1.4); end
    glFinish(); buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fn,"w") do io; write(io,"P6\n$W $H\n255\n"); for y in H:-1:1,x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
    println("wrote ",fn)
end
# cockpit interior: eye in body-local rig frame (X fwd, Y up, Z lat), via bodyModel
bl(p) = (q = bodyModel * Float32[p[1],p[2],p[3],1f0]; [q[1],q[2],q[3]])
function cockpit(fn, ex,ey,ez, dropy)
    snap(fn, bl([ex,ey,ez]), bl([ex+4, ey-dropy, ez]))    # look forward (+X) and down
end
global SWANG=0.0
cockpit("/tmp/cp_a.ppm",  0.30, 0.56, 0.0, 1.25)   # higher+fwd to clear the tub edge
cockpit("/tmp/cp_b.ppm",  0.40, 0.54, 0.0, 1.20)
cockpit("/tmp/cp_c.ppm",  0.22, 0.62, 0.0, 1.40)
GLFW.Terminate()
