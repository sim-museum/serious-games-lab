# juliaMotor — native (no-browser) drivable cockpit.  A real OpenGL renderer
# (GLFW/ModernGL/GLSL) driving the validated JuliaMotor physics over the real
# Zandvoort + Vanwall geometry, with native keyboard AND joystick input.  The
# first step toward an rF1-fidelity self-contained app; the rendering core is
# render.jl.
using GLFW, ModernGL, LinearAlgebra
using JuliaMotor, RFactorData
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack
include("audio.jl"); using .EngineAudio

# ---- load physics + geometry: the GPL Zandvoort track + Vanwall-calibrated physics ----
const GD = default_gamedata()
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)              # physics (Lotus-49 calibration is the future goal)
const ZD = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks/zandvort"
const ZTRK = joinpath(ZD, "zandvort.3do")
print("loading GPL track… "); flush(stdout)
const TRACKMESH = Render.GPL3DO.parse_3do(ZTRK)
const TERRAIN = GPLTrack.build_hat(TRACKMESH)            # ground/elevation from the .3do
const TRKSURF = GPLTrack.build_surface(GPLTrack.trk_centreline(joinpath(ZD,"zandvort.trk")), TERRAIN)
const CAR = DriveCar(MODEL, TRKSURF; terrain=TERRAIN)    # racing ribbon from the .trk centreline
println(TERRAIN, "  ", TRKSURF)
print("extracting geometry… "); flush(stdout)
const TRACK = Render.extract_gpl_car(ZTRK; track=true, mirror=true, exclude=("ltraymap","lshad","wiref_s"))   # GPL Zandvoort (no wire fences)
# ---- GPL Lotus 49 (replaces the rFactor Vanwall; the authentic GPL-pivot car) ----
const LOTDIR = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus"
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOT3DO = joinpath(LOTDIR,"lotus.3do")
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=("ltraymap","lshad","lohand","lotarms","lotmirt",Render.STEER_TEX...), exclude_groups=(6600,3560))  # no hands/dup-mirror/teal front-susp
const SWPARTS, SWCENTER, SWAXIS = Render.extract_gpl_steering(LOT3DO)   # steering wheel + pivot
println(length(TRACK), " track parts + ", length(CARP), " Lotus body parts")
const BODY_OFF = Float32[-0.55, 0.30, 0.0]     # centre body on X, lift onto the wheels
# wheel hubs (rig frame X fwd, Y=radius, Z left); front pair steers, all spin
const WHEELS = (( 1.05f0, 0.62f0,true, 0.31f0,"lotwlf"), ( 1.05f0,-0.62f0,true, 0.31f0,"lotwrf"),
                (-1.15f0, 0.66f0,false,0.34f0,"lotwlr"), (-1.15f0,-0.66f0,false,0.34f0,"lotwrr"))

# ---- GL init (visible window on the user's display) ----
const W, H = 1440, 810
const SMOKE = haskey(ENV, "JM_SMOKE")     # headless self-test: hidden window, auto-exit
GLFW.Init()
SMOKE && GLFW.WindowHint(GLFW.VISIBLE, false)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR, 3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR, 3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE, GLFW.OPENGL_CORE_PROFILE)
GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT, true)
GLFW.WindowHint(GLFW.SAMPLES, 4)                  # 4× MSAA — smooth the jaggies
win = GLFW.CreateWindow(W, H, "juliaMotor — 1967 Lotus 49 @ Zandvoort")
GLFW.MakeContextCurrent(win); GLFW.SwapInterval(1)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE)
glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)   # GPL cutout/glass alpha
prog = Render.program(); glUseProgram(prog)
glUniform3f(glGetUniformLocation(prog,"uLightDir"), 0.4f0, 1.0f0, 0.25f0)
skyprog = Render.skyprogram(); skyvao = Render.empty_vao()
hudprog = Render.hud_program(); (hudvao, hudvbo) = Render.hud_buffers()
depthprog = Render.depthprogram(); (shadowfbo, shadowtex) = Render.make_shadow_fbo()
const LIGHTDIR = Float32[0.4, 1.0, 0.25]
const ENG = EngineAudio.build(GD); EngineAudio.start(ENG)   # real onboard engine samples, RPM-crossfaded
print("loading textures… "); flush(stdout)
const TEXIDX = Render.gpl_texture_index(ZD)
trackItems = Render.build_gpl(TRACK, TEXIDX)
carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
# four Lotus wheels — keep the untextured black tyre body (only the car body drops "")
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(0.12f0,0.12f0,0.13f0)), GPLTEX)  # force dark tyre
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
println(count(it->it.tex!=0, trackItems), "/", length(trackItems), " track + ",
        count(it->it.tex!=0, carItems), "/", length(carItems), " Lotus parts textured")
const PROJ = Render.perspective(deg2rad(62f0), Float32(W/H), 0.3f0, 5000f0)

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; view::Int; auto::Bool; end
const CTL = Ctl(false,false,false,false,false, 0, true)   # auto-gearbox ON by default
key(k) = GLFW.GetKey(win, k) == GLFW.PRESS
function read_input()
    thr=brk=str=clu=0.0; up=dn=false
    js = GLFW.GetJoystickAxes(GLFW.JOYSTICK_1)
    if js !== nothing && length(js) >= 2
        ax0 = abs(js[1])<0.06 ? 0.0 : js[1]; ax1 = abs(js[2])<0.06 ? 0.0 : js[2]
        str = -ax0; thr = max(0.0,-ax1); brk = max(0.0, ax1)
        bs = GLFW.GetJoystickButtons(GLFW.JOYSTICK_1)
        if bs !== nothing
            b(i) = length(bs) >= i && bs[i] != 0     # GetJoystickButtons gives raw bytes, NOT Action
            up = b(1); dn = b(2); clu = b(3) ? 1.0 : 0.0
        end
    end
    # keyboard (adds to / overrides stick)
    key(GLFW.KEY_W) && (thr=1.0); key(GLFW.KEY_S) && (brk=1.0)
    key(GLFW.KEY_A) && (str=1.0); key(GLFW.KEY_D) && (str=-1.0)
    key(GLFW.KEY_C) && (clu=1.0)
    ku=key(GLFW.KEY_E); kd=key(GLFW.KEY_Q)
    upE = (ku && !CTL.prevUp) || (up && !CTL.prevUp); dnE = (kd && !CTL.prevDn) || (dn && !CTL.prevDn)
    CTL.prevUp = ku||up; CTL.prevDn = kd||dn
    (upE || dnE) && (CTL.auto = false)     # a manual shift hands the gearbox to you (G re-engages auto)
    kv = key(GLFW.KEY_V); (kv && !CTL.prevV) && (CTL.view = 1-CTL.view); CTL.prevV = kv
    kg = key(GLFW.KEY_G); (kg && !CTL.prevG) && (CTL.auto = !CTL.auto); CTL.prevG = kg
    km = key(GLFW.KEY_M); (km && !CTL.prevM) && (ENG.master[] = ENG.master[]>0 ? 0.0 : 0.7); CTL.prevM = km
    rst = key(GLFW.KEY_R)
    (DriveInput(throttle=clamp(thr,0,1), brake=clamp(brk,0,1), steer=clamp(str,-1,1),
                clutch=clu, shift_up=upE, shift_down=dnE, autoshift=CTL.auto), rst)
end

# ---- camera ----
function camera(cs)
    wx,wy,wz = cs.x, cs.y, -cs.z; fx,fz = cos(cs.θ), -sin(cs.θ)   # render world un-mirrors physics z
    if CTL.view == 1                                  # chase
        eye=[wx-fx*9, wy+3.2, wz-fz*9]; ctr=[wx+fx*3, wy+0.6, wz+fz*3]
    else                                             # cockpit: driver's eye in the body frame, over the wheel
        ex,ey,ez,drop = 0.30f0, 0.56f0, 0.0f0, 1.25f0           # eye in body-local rig (X fwd,Y up,Z lat)
        rx = BODY_OFF[1]+ex; ry = BODY_OFF[2]+ey; rz = BODY_OFF[3]+ez
        eye=[wx + rx*fx - rz*fz, wy + ry, wz + rx*fz + rz*fx]   # rig→world (roty θ + carpos)
        ctr=[wx + (rx+4)*fx - rz*fz, wy + (ry-drop), wz + (rx+4)*fz + rz*fx]
    end
    PROJ * Render.lookat(Float32.(eye), Float32.(ctr), Float32[0,1,0]), Float32.(eye)
end

# ---- main loop (in a function — avoids top-level soft scope, runs faster) ----
function main()
    cs = spawn(CAR; v0=0.0)
    spin = 0.0; last = time(); frames = 0; titleT = last
    println("\n  Drive:  W/S gas·brake   A/D steer   E/Q shift   C clutch   R respawn   V view   G auto-gearbox   M mute   Esc quit")
    println("  (Logitech joystick works natively — push=throttle, pull=brake, roll=steer)\n")
    while !GLFW.WindowShouldClose(win)
        GLFW.PollEvents()
        key(GLFW.KEY_ESCAPE) && break
        SMOKE && frames >= 40 && break
        now = time(); dt = clamp(now-last, 0.0, 0.05); last = now
        inp, rst = read_input()
        if rst; cs = spawn(CAR; v0=0.0)
        else; step!(cs, CAR, inp; dt = dt > 1e-4 ? dt : 1/60); end
        spin -= cs.v*dt/0.33
        ENG.rpm[] = cs.rpm                         # feed the engine-audio thread

        vp, eye = camera(cs)
        carModel = Render.translate(Float32[cs.x, cs.y, -cs.z]) * Render.roty(Float32(cs.θ))
        bodyModel = carModel * Render.translate(BODY_OFF)
        δ = Float32(inp.steer * CAR.max_steer)
        wheelmat(wx,wz,steer,r) = carModel * Render.translate(Float32[wx, r, wz]) *
                     (steer ? Render.roty(δ) : Render.ident()) * Render.rotz(Float32(spin))
        # ---- shadow pass: scene depth from the sun, light box on the car ----
        lightVP = Render.light_vp(Float32[cs.x, cs.y, -cs.z], LIGHTDIR)
        Render.shadow_pass(depthprog, shadowfbo, lightVP) do dp
            for it in trackItems; Render.draw_depth(dp, it, Render.ident()); end
            for it in carItems; Render.draw_depth(dp, it, bodyModel); end
            for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw_depth(dp, it, wheelmat(wx,wz,steer,r)); end
        end
        # ---- main pass ----
        glViewport(0,0,W,H); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        Render.draw_sky(skyprog, skyvao, inv(vp), eye, LIGHTDIR)
        Render.set_scene_uniforms(prog, eye; fognear=400f0, fogfar=2800f0); Render.bind_shadow(prog, shadowtex, lightVP)
        for it in trackItems; Render.draw(prog, it, vp, Render.ident(); bright=0.55); end
        for it in carItems; Render.draw(prog, it, vp, bodyModel; bright=1.15, spec=0.4); end
        for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw(prog, it, vp, wheelmat(wx,wz,steer,r)); end
        # steering wheel — spin about its column axis with steering input
        swModel = bodyModel * Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(inp.steer*2.5)) * Render.translate(-SWCENTER)
        for it in swItems; Render.draw(prog, it, vp, swModel; bright=1.2); end
        Render.hud_draw(hudprog, hudvao, hudvbo,
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, MODEL.eng.rev_limit, inp.throttle, inp.brake, cs.tc), W, H)
        GLFW.SwapBuffers(win)

        frames += 1
        if now - titleT > 0.25
            GLFW.SetWindowTitle(win, "juliaMotor — Lotus 49 — $(round(Int,cs.v*3.6)) km/h — gear $(cs.gear) ($(CTL.auto ? "AUTO" : "MANUAL")) — $(round(Int,cs.rpm)) rpm" *
                (cs.ontrack ? "" : "  [OFF TRACK]"))
            titleT = now
        end
    end
    EngineAudio.stop!(ENG)
    GLFW.Terminate()
    println("bye")
end
main()
