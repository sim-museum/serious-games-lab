using GLFW, ModernGL, LinearAlgebra
using JuliaMotor, RFactorData
include("render.jl"); using .Render

const GD = default_gamedata()
const DIR = joinpath(GD, "Locations", "Zandvoort67")
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)
const AIW = read_aiw(joinpath(DIR,"zandvoort67.AIW"))
const TERRAIN = TriangleHAT(DIR)
const CAR = DriveCar(MODEL, AIW; terrain=TERRAIN)
println("extracting geometry…")
const TRACK = Render.extract_track(DIR);  println("  track parts: ", length(TRACK))
const CARP  = Render.extract_car_parts(GD)

const W,H = 1280, 720
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE, false)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR, 3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR, 3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE, GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT, true)
win = GLFW.CreateWindow(W,H,"snap"); GLFW.MakeContextCurrent(win)
glEnable(GL_DEPTH_TEST)
prog = Render.program(); glUseProgram(prog)
glUniform3f(glGetUniformLocation(prog,"uLightDir"), 0.4f0, 1.0f0, 0.25f0)
skyprog = Render.skyprogram(); skyvao = Render.empty_vao()
hudprog = Render.hud_program(); (hudvao, hudvbo) = Render.hud_buffers()
depthprog = Render.depthprogram(); (shadowfbo, shadowtex) = Render.make_shadow_fbo()
const LIGHTDIR = Float32[0.4, 1.0, 0.25]
print("loading textures… "); texidx = Render.texture_index(DIR); println(length(texidx), " dds in archive")
trackItems = Render.build_track(TRACK, texidx)
println("  track textured: ", count(it->it.tex!=0, trackItems), "/", length(trackItems))
const CARTEX = Render.car_texture_index(GD)
carItems  = Render.build_track(CARP, CARTEX)
println("  car textured: ", count(it->it.tex!=0, carItems), "/", length(carItems))
const SWPART = Render.extract_steering_wheel(GD)
swItem = Render.build_track([SWPART], CARTEX)[1]
const SWAXIS = Render.disc_normal(SWPART.verts)
println("  steering wheel tex: ", swItem.tex!=0, "  axis ", round.(SWAXIS,digits=2))
wheelItem = Render.item(Render.wheel_mesh(0.33f0, 0.13f0))
const WHEELS = ((1.4f0,0.33f0,0.735f0),(1.4f0,0.33f0,-0.735f0),(-1.4f0,0.34f0,0.705f0),(-1.4f0,0.34f0,-0.705f0))

SWSTEER = 0.0      # steering-wheel angle for the cockpit snapshots
wheelmat(carModel,wx,wy,wz)=carModel*Render.translate(Float32[wx,wy,wz])*Render.rotz(0.3f0)
function snap(fname, eye, ctr; carModel=Render.ident())
    vp = Render.perspective(deg2rad(60f0), Float32(W/H), 0.3f0, 4000f0) * Render.lookat(Float32.(eye), Float32.(ctr), Float32[0,1,0])
    # shadow pass: scene depth from the sun, light box on the car
    lightVP = Render.light_vp(Float32[cs.x, cs.y, -cs.z], LIGHTDIR)
    Render.shadow_pass(depthprog, shadowfbo, lightVP) do dp
        for it in trackItems; Render.draw_depth(dp, it, Render.ident()); end
        for it in carItems; Render.draw_depth(dp, it, carModel); end
        for (wx,wy,wz) in WHEELS; Render.draw_depth(dp, wheelItem, wheelmat(carModel,wx,wy,wz)); end
    end
    glViewport(0,0,W,H); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    Render.draw_sky(skyprog, skyvao, inv(vp), Float32.(eye), LIGHTDIR)
    Render.set_scene_uniforms(prog, Float32.(eye)); Render.bind_shadow(prog, shadowtex, lightVP)
    for it in trackItems; Render.draw(prog, it, vp, Render.ident()); end
    for it in carItems; Render.draw(prog, it, vp, carModel; bright=1.5); end
    for (wx,wy,wz) in WHEELS
        Render.draw(prog, wheelItem, vp, carModel*Render.translate(Float32[wx,wy,wz])*Render.rotz(0.3f0))
    end
    swModel = carModel * Render.translate(Float32[0.05,0.66,0]) * Render.rotaxis(SWAXIS, Float32(-SWSTEER*3.0))
    Render.draw(prog, swItem, vp, swModel; bright=1.3)
    hv = Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, MODEL.eng.rev_limit, 0.4, 0.0, cs.tc)
    Render.hud_draw(hudprog, hudvao, hudvbo, hv, W, H)
    glFinish()
    buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fname,"w") do io; write(io,"P6\n$W $H\n255\n")
        for y in H:-1:1, x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end
    end
    println("wrote ", fname)
end

cs = spawn(CAR; v0=0.0)
for _ in 1:200; step!(cs, CAR, DriveInput(throttle=0.4); dt=1/60); end
wx,wy,wz = cs.x, cs.y, -cs.z
carModel = Render.translate(Float32[wx,wy,wz]) * Render.roty(Float32(cs.θ))
fwd = [cos(cs.θ), 0.0, -sin(cs.θ)]
snap("/tmp/native_chase.ppm", [wx-fwd[1]*9, wy+3.2, wz-fwd[3]*9], [wx+fwd[1]*3, wy+0.6, wz+fwd[3]*3]; carModel=carModel)
eye=[wx-fwd[1]*0.35, wy+0.92, wz-fwd[3]*0.35]   # driver's eyes, behind the wheel
global SWSTEER = 0.0
snap("/tmp/native_cockpit.ppm", eye, [eye[1]+fwd[1]*9, eye[2]-1.8, eye[3]+fwd[3]*9]; carModel=carModel)
global SWSTEER = 0.8                              # wheel turned — verify column-axis spin
snap("/tmp/native_cockpit_turn.ppm", eye, [eye[1]+fwd[1]*9, eye[2]-1.8, eye[3]+fwd[3]*9]; carModel=carModel)
global SWSTEER = 0.0
# elevated front-right angle so the car's ground shadow is visible
side=[fwd[3], 0.0, -fwd[1]]
snap("/tmp/native_shadow.ppm", [wx+fwd[1]*5+side[1]*5, wy+5.0, wz+fwd[3]*5+side[3]*5], [wx,wy+0.3,wz]; carModel=carModel)
GLFW.Terminate()
