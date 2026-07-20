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
include("joycfg.jl"); using .JoyCfg
const JOYMAP = JoyCfg.loadmap(joinpath(@__DIR__, "joystick.conf"))   # from calibrate.jl, or default

# ---- load physics + geometry: the GPL Zandvoort track + Vanwall-calibrated physics ----
const GD = default_gamedata()
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)              # physics (Lotus-49 calibration is the future goal)
const ZD = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks","zandvort"))
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
const LOTDIR = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","cars","cars67","lotus"))
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOT3DO = joinpath(LOTDIR,"lotus.3do")
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=("ltraymap","lshad","lohand","lotarms","lotmirt","windlot",Render.STEER_TEX...), exclude_groups=(6600,3560), cockpit_clean=true, maxlat=0.85f0)  # no hands/dup-mirror/teal front-susp/tan scuttle "rug"; drop tan floor; clip splayed rear
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
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR, 4); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR, 5)  # 4.5 → glClipControl (reversed-Z)
GLFW.WindowHint(GLFW.OPENGL_PROFILE, GLFW.OPENGL_CORE_PROFILE)
GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT, true)
GLFW.WindowHint(GLFW.SAMPLES, 8)                  # 8× MSAA — smooth jaggies + finer alpha-to-coverage
win = GLFW.CreateWindow(W, H, "juliaMotor — 1967 Lotus 49 @ Zandvoort")
GLFW.MakeContextCurrent(win); GLFW.SwapInterval(1)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE)
glEnable(GL_SAMPLE_ALPHA_TO_COVERAGE)                                   # MSAA-smooth the alpha cutout edges (signs/trees/crowd)
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
# GPL sky dome: the 12-panel horizon ring (horiz0..11), camera-centred backdrop.
const HORIZON_RING = Render.build_horizon(TEXIDX)
# ---- Phase 3 (a): auto-place trackside objects (GPL .3do geometry, textured from
# loose files + the packed zandvort.dat).  Names + transforms come from the .3do
# instance records; geometry/textures resolve from loose files OR the .dat archive.
const DATPACK = isfile(joinpath(ZD,"zandvort.dat")) ? Render.GPLDat.parse_dat(joinpath(ZD,"zandvort.dat")) : Dict{String,Vector{UInt8}}()
const TMPOBJ = mktempdir()
objpath(nm) = (p=joinpath(ZD, nm*".3do"); isfile(p) ? p :
    (v=get(DATPACK, lowercase(nm*".3do"), nothing); v===nothing ? "" :
     (tp=joinpath(TMPOBJ, nm*".3do"); isfile(tp)||write(tp,v); tp)))
# people textures painted onto the structures (pit wall, grandstands) — excluded so the
# stands/buildings stay but the crowds on them go (user: remove ALL people).
const CROWD_TEX = ("ltraymap","lshad","pplrow01","pplrow02","pplrow03","pplrow04",
    "pitppl01","pitppl02","pitppl03","pitppl04","crowdv","crowdw","crwdtop",
    "lcrowd3","lcrowd4","sidecrd2","people01","people02","people03","people04","people05","tmpstnd")
let objnames=Set{String}()
    for f in readdir(ZD); endswith(lowercase(f),".3do") && push!(objnames, lowercase(replace(f,r"\.3do$"i=>""))); end
    for k in keys(DATPACK); endswith(k,".3do") && push!(objnames, replace(k,r"\.3do$"=>"")); end
    insts = GPLTrack.trackside_objects(ZTRK; objnames=objnames)
    objmesh=Dict{String,Any}(); ymn=Dict{String,Float32}(); ymx=Dict{String,Float32}(); bbinfo=Dict{String,Any}()
    for inst in insts
        (haskey(objmesh, inst.name) || haskey(bbinfo, inst.name)) && continue
        p = objpath(inst.name)
        if p == ""; objmesh[inst.name]=nothing; continue; end
        try
            full = Render.extract_gpl_car(p; track=true, mirror=true)   # un-stripped: decides stub vs geometry
            if isempty(full)                               # a real billboard stub (tree/sprite)
                h, wid, strs = Render.billboard_stub(p); bb=nothing
                for s in strs; bb = Render.build_billboard(s, TEXIDX); bb !== nothing && break; end
                bbinfo[inst.name] = bb===nothing ? nothing : (bb[1], bb[2], bb[3], h, wid)
            else
                parts = Render.extract_gpl_car(p; track=true, mirror=true, exclude=CROWD_TEX)  # strip painted-on crowds
                if isempty(parts); objmesh[inst.name]=nothing    # was an all-crowd object → drop (NOT a billboard)
                else
                    lo=Inf32; hi=-Inf32; for pp in parts, k in 2:11:length(pp.verts); v=pp.verts[k]; lo=min(lo,v); hi=max(hi,v); end
                    ymn[inst.name]=lo; ymx[inst.name]=hi
                    objmesh[inst.name] = Render.build_gpl(parts, TEXIDX)
                end
            end
        catch; objmesh[inst.name]=nothing; end
    end
    # SNAP every object to OUR terrain (the HAT) instead of its authored GPL height —
    # this kills floaters (GPL placed trees/crowds on dune terrain that ours doesn't match).
    groundz(x,y) = (h=JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(y); ref=Inf); h[3] ? Float32(h[1]) : -999f0)  # -999 = OFF the HAT (would float)
    onground(gz) = -900f0 < gz <= 7f0       # on our terrain & not floating high (drops OFF-HAT + sky-high placements)
    # drop: ground-cover planes (grass/herbe/infield), white "fuel-tank" tents, and the
    # spectator OVERPOPULATION (single* ≈300, ppl_* crowds) — far more than real Zandvoort.
    drop(nm) = startswith(nm,"grass") || startswith(nm,"herbe") || nm == "infield" ||
               startswith(nm,"tent") || startswith(nm,"single") || startswith(nm,"ppl") ||
               startswith(nm,"flagger") || startswith(nm,"rescu") || startswith(nm,"photo")  # marshals/photographers = people too
    global OBJECTS = [(objmesh[i.name], Render.translate(Float32[i.x, groundz(i.x,i.y), -i.y]) * Render.roty(Float32(-i.yaw)))
                      for i in insts if get(objmesh,i.name,nothing) !== nothing &&
                          !drop(i.name) && (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && onground(groundz(i.x,i.y))]
    # billboards: (Item, render-pos base, width, height) — drawn camera-facing per frame
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
    for i in insts
        bb = get(bbinfo, i.name, nothing); (bb === nothing || drop(i.name)) && continue
        gz = groundz(i.x,i.y); onground(gz) || continue
        item, tw, th, h, wid = bb
        w = wid > 0f0 ? wid : h*tw/max(th,1f0)
        push!(BILLBOARDS, (item, (Float32(i.x), gz, Float32(-i.y)), Float32(w), Float32(h)))
    end
end
println(length(OBJECTS), " trackside objects + ", length(BILLBOARDS), " billboards placed")
carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
# four Lotus wheels — keep the untextured black tyre body (only the car body drops "")
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(0.12f0,0.12f0,0.13f0)), GPLTEX)  # force dark tyre
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
println(count(it->it.tex!=0, trackItems), "/", length(trackItems), " track + ",
        count(it->it.tex!=0, carItems), "/", length(carItems), " Lotus parts textured")
const PROJ = Render.perspective_revz(deg2rad(62f0), Float32(W/H), 0.35f0, 3000f0)  # reversed-Z: near-uniform depth precision → kills distant z-fight

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; view::Int; auto::Bool; end
# shift mode: AUTO (auto-shift, no clutch) by default; SAND_SHIFT=manual starts in
# realistic mode (you shift E/Q, clutch required).  G toggles in-app.
const CTL = Ctl(false,false,false,false,false, 0, get(ENV,"SAND_SHIFT","auto") != "manual")
key(k) = GLFW.GetKey(win, k) == GLFW.PRESS
function read_input()
    thr=brk=str=clu=0.0; up=dn=false
    js = GLFW.GetJoystickAxes(GLFW.JOYSTICK_1)
    if js !== nothing && !isempty(js)
        bs = GLFW.GetJoystickButtons(GLFW.JOYSTICK_1)
        str, thr, brk, clu, up, dn = JoyCfg.apply(JOYMAP, js, bs)   # configurable mapping (calibrate.jl)
    end
    # keyboard (adds to / overrides stick)
    key(GLFW.KEY_W) && (thr=1.0); key(GLFW.KEY_S) && (brk=1.0)
    key(GLFW.KEY_A) && (str=1.0); key(GLFW.KEY_D) && (str=-1.0)
    key(GLFW.KEY_C) && (clu=1.0)
    ku=key(GLFW.KEY_E); kd=key(GLFW.KEY_Q)
    upE = (ku && !CTL.prevUp) || (up && !CTL.prevUp); dnE = (kd && !CTL.prevDn) || (dn && !CTL.prevDn)
    CTL.prevUp = ku||up; CTL.prevDn = kd||dn
    # realistic clutch: in MANUAL mode a shift only engages with the clutch pressed
    (!CTL.auto && (upE || dnE) && clu < 0.4) && (upE = false; dnE = false)
    kv = key(GLFW.KEY_V); (kv && !CTL.prevV) && (CTL.view = 1-CTL.view); CTL.prevV = kv
    kg = key(GLFW.KEY_G); (kg && !CTL.prevG) && (CTL.auto = !CTL.auto); CTL.prevG = kg
    km = key(GLFW.KEY_M); (km && !CTL.prevM) && (ENG.master[] = ENG.master[]>0 ? 0.0 : 0.7); CTL.prevM = km
    rst = key(GLFW.KEY_R)
    (DriveInput(throttle=clamp(thr,0,1), brake=clamp(brk,0,1), steer=clamp(str,-1,1),
                clutch=clu, shift_up=upE, shift_down=dnE, autoshift=CTL.auto), rst)
end

# ---- terrain pitch: slope under the car from the HAT, sampled fore & aft ----
function terrain_pitch(cs)
    L = 1.5; fx = cos(cs.θ); fz = sin(cs.θ)               # physics forward (x, z)
    hf = JuliaMotor.hat3d(TERRAIN, cs.x+fx*L, cs.z+fz*L; ref=Inf)
    hr = JuliaMotor.hat3d(TERRAIN, cs.x-fx*L, cs.z-fz*L; ref=Inf)
    (hf[3] && hr[3]) ? atan(hf[1]-hr[1], 2L) : 0.0        # front higher → nose up (+)
end

# ---- camera (pitch = total body pitch, applied to the cockpit view only) ----
function camera(cs, pitch=0.0)
    wx,wy,wz = cs.x, cs.y, -cs.z; fx,fz = cos(cs.θ), -sin(cs.θ)   # render world un-mirrors physics z
    if CTL.view == 1                                  # chase — level horizon, so you see the body pitch
        eye=[wx-fx*9, wy+3.2, wz-fz*9]; ctr=[wx+fx*3, wy+0.6, wz+fz*3]
    else                                             # cockpit: driver's eye in the body frame, over the wheel
        ex,ey,ez,drop = 0.30f0, 0.56f0, 0.0f0, 1.25f0           # eye in body-local rig (X fwd,Y up,Z lat)
        rx = BODY_OFF[1]+ex; ry = BODY_OFF[2]+ey; rz = BODY_OFF[3]+ez
        fwd = 4*cos(pitch) + drop*sin(pitch); up = 4*sin(pitch) - drop*cos(pitch)  # tilt look dir by pitch
        eye=[wx + rx*fx - rz*fz, wy + ry, wz + rx*fz + rz*fx]   # rig→world (roty θ + carpos)
        ctr=[wx + (rx+fwd)*fx - rz*fz, wy + (ry+up), wz + (rx+fwd)*fz + rz*fx]
    end
    PROJ * Render.lookat(Float32.(eye), Float32.(ctr), Float32[0,1,0]), Float32.(eye)
end

# ---- main loop (in a function — avoids top-level soft scope, runs faster) ----
function main()
    cs = spawn(CAR; v0=0.0)
    spin = 0.0; last = time(); frames = 0; titleT = last
    v_prev = cs.v; pitch_dyn = 0.0; pitch_ter = 0.0    # dive/squat + terrain-slope pitch (smoothed)
    # lap timing + telemetry log
    lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = cs.laps; tsamp = 0
    fmt_lap(s) = (m=floor(Int,s/60); sec=s-60m; si=floor(Int,sec); ms=round(Int,(sec-si)*1000);
                  "$m:$(lpad(si,2,'0')).$(lpad(ms,3,'0'))")
    telem = SMOKE ? nothing : open("zand_racer_$(round(Int,time())).txt", "w")
    telem !== nothing && write(telem,
        "# zand_racer telemetry — Lotus 49 @ Zandvoort\n# t\tlap\tlapdist\tkmh\tthr\tbrk\tsteer\tclu\tgear\trpm\tx\tz\tlat\talong\tontrack\n")
    println("\n  Drive:  W/S gas·brake   A/D steer   E/Q shift   C clutch   R respawn   V view   G auto⇄manual   M mute   Esc quit")
    println("  Manual mode (G) is realistic: hold the clutch (C / stick button) to shift.")
    println("  Lap times top-left: white = last, green = best.  Telemetry → ./zand_racer_*.txt")
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

        # ---- lap timing + telemetry log ----
        if cs.laps > prev_laps
            last_lap = cs.t - lap_t0; lap_t0 = cs.t
            (best_lap == 0.0 || last_lap < best_lap) && (best_lap = last_lap)
            telem !== nothing && (write(telem, "# LAP $(cs.laps)  $(fmt_lap(last_lap))\n"); flush(telem))
            println("  lap $(cs.laps): $(fmt_lap(last_lap))", last_lap==best_lap ? "  (best)" : "")
        elseif cs.laps < prev_laps                 # respawn reset the lap counter
            lap_t0 = cs.t
        end
        prev_laps = cs.laps
        if telem !== nothing && (tsamp += 1) % 6 == 0
            write(telem, "$(round(cs.t,digits=2))\t$(cs.laps)\t$(round(cs.lapdist,digits=1))\t$(round(cs.v*3.6,digits=1))\t$(round(inp.throttle,digits=2))\t$(round(inp.brake,digits=2))\t$(round(inp.steer,digits=2))\t$(round(inp.clutch,digits=2))\t$(cs.gear)\t$(round(Int,cs.rpm))\t$(round(cs.x,digits=1))\t$(round(cs.z,digits=1))\t$(round(cs.lateral,digits=2))\t$(round(cs.along,digits=2))\t$(cs.ontrack ? 1 : 0)\n")
        end

        # ---- body pitch: accel→squat (nose up), brake→dive (nose down); + terrain slope ----
        acc = clamp((cs.v - v_prev)/max(dt,1e-3), -15.0, 15.0); v_prev = cs.v
        pitch_dyn += (clamp(0.0016*acc, -0.013, 0.013) - pitch_dyn) * min(1.0, dt*3.5)  # subtle, heavily damped (no rock)
        pitch_ter += (terrain_pitch(cs) - pitch_ter) * min(1.0, dt*6)
        vp, eye = camera(cs, pitch_ter + pitch_dyn)
        carModel = Render.translate(Float32[cs.x, cs.y, -cs.z]) * Render.roty(Float32(cs.θ)) *
                   Render.rotz(Float32(pitch_ter))                       # whole car follows the hill
        bodyModel = carModel * Render.rotz(Float32(pitch_dyn)) * Render.translate(BODY_OFF)  # body dives/squats
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
        # ---- main pass (reversed-Z: [0,1] clip, near→1/far→0, GEQUAL, clear 0) ----
        glViewport(0,0,W,H)
        glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE); glDepthFunc(GL_GEQUAL); glClearDepth(0.0)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        Render.draw_sky(skyprog, skyvao, inv(vp), eye, LIGHTDIR)
        Render.set_scene_uniforms(prog, eye; fognear=400f0, fogfar=2800f0); Render.bind_shadow(prog, shadowtex, lightVP)
        Render.draw_horizon(prog, HORIZON_RING, vp, eye)   # GPL horizon ring backdrop
        for it in trackItems; Render.draw(prog, it, vp, Render.ident(); bright=0.55); end
        glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 1)   # un-mirror far-side sign backs (objects only)
        for (items,mat) in OBJECTS, it in items; Render.draw(prog, it, vp, mat; bright=0.85); end  # trackside objects
        glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 0)
        for (it,pos,w,h) in BILLBOARDS; Render.draw(prog, it, vp, Render.billboard_model(pos,w,h,eye); bright=1.05); end  # trees/sprites
        for it in carItems; Render.draw(prog, it, vp, bodyModel; bright=1.15, spec=0.4); end
        for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw(prog, it, vp, wheelmat(wx,wz,steer,r)); end
        # steering wheel — spin about its column axis with steering input
        swModel = bodyModel * Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(inp.steer*2.5)) * Render.translate(-SWCENTER)
        for it in swItems; Render.draw(prog, it, vp, swModel; bright=1.2); end
        Render.hud_draw(hudprog, hudvao, hudvbo,
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, MODEL.eng.rev_limit, inp.throttle, inp.brake, cs.tc;
                               lastlap=(SMOKE ? 94.3 : last_lap), bestlap=(SMOKE ? 92.1 : best_lap), manual=!CTL.auto), W, H)
        GLFW.SwapBuffers(win)
        if SMOKE && frames == 38                   # headless self-test: dump one frame
            buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
            open("/tmp/zand_hud.ppm","w") do io; write(io,"P6\n$W $H\n255\n")
                for y in H:-1:1, x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
        end

        frames += 1
        if now - titleT > 0.25
            GLFW.SetWindowTitle(win, "juliaMotor — Lotus 49 — $(round(Int,cs.v*3.6)) km/h — gear $(cs.gear) ($(CTL.auto ? "AUTO" : "MANUAL")) — $(round(Int,cs.rpm)) rpm" *
                (cs.ontrack ? "" : "  [OFF TRACK]"))
            titleT = now
        end
    end
    telem !== nothing && close(telem)
    EngineAudio.stop!(ENG)
    GLFW.Terminate()
    println("bye")
end
main()
