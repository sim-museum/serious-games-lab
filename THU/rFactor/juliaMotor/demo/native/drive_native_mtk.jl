# juliaMotor — DRIVE THE MTK MODEL.  Same GPL Zandvoort + Lotus 49 renderer as
# drive_native.jl, but the physics is the iRacing-fit JuliaMotorMTK model (DriveRT).
# (GLFW/ModernGL/GLSL) driving the validated JuliaMotor physics over the real
# Zandvoort + Vanwall geometry, with native keyboard AND joystick input.  The
# first step toward an rF1-fidelity self-contained app; the rendering core is
# render.jl.
using GLFW, ModernGL, LinearAlgebra, Dates
using JuliaMotor, RFactorData
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt.jl"); using .DriveRT  # MTK physics
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/ibt.jl"); using .IBT           # iRacing .ibt telemetry writer
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack
include("audio.jl"); using .EngineAudio
include("joycfg.jl"); using .JoyCfg
const JOYMAP = let m = JoyCfg.loadmap(joinpath(@__DIR__, "joystick.conf"))
    JoyCfg.JoyMap(m.steer, m.throttle, m.brake, JoyCfg.Ctrl(4, -1.0, 1.0),   # clutch on the X3D SLIDER (axis 4)
                  m.up_btn, m.dn_btn, m.clutch_btn, m.deadzone)
end

# ---- track selection (upfront, before the long load) ----
# Honour TRACK=zandvoort|skidpad if set; otherwise, when launched interactively,
# prompt the driver to choose.  (nurburgring = TBD, shown but not yet selectable.)
function choose_track()
    haskey(ENV, "TRACK")     && return lowercase(ENV["TRACK"])
    haskey(ENV, "JM_SMOKE")  && return "zandvoort"          # headless self-test
    isa(stdin, Base.TTY)     || return "zandvoort"          # non-interactive → default
    println("""

      ╔════════════════════════════════════════════════╗
      ║          juliaMotor — choose your track         ║
      ╠════════════════════════════════════════════════╣
      ║   1) Zandvoort     GPL 1967 circuit (default)   ║
      ║   2) Skidpad       flat centripetal pad,        ║
      ║                    Ø10–200 m circles (10 m step) ║
      ║   3) Nürburgring   rFactor Nordschleife 1967,   ║
      ║                    22.7 km, full elevation      ║
      ╚════════════════════════════════════════════════╝""")
    print("\n  Track [1/2/3] (Enter = 1): "); flush(stdout)
    s = strip(readline())
    return s == "2" ? "skidpad" : s == "3" ? "nurburgring" : "zandvoort"
end
const TRACKSEL = choose_track()
const SKIDPAD  = TRACKSEL == "skidpad"
const NURB     = TRACKSEL == "nurburgring"
println("  → track: ", uppercasefirst(TRACKSEL))

# ---- iRacing .ibt telemetry export (JM_IBT=1) ----
# Record the lap in iRacing's exact .ibt format so juliaMotor laps can be diffed
# against gold-standard iRacing telemetry (same car/track, similar laps) to tune the
# model.  We reuse a real iRacing .ibt of the matching car/track as the header+var-
# table+YAML template (so the file is byte-identical in structure / any iRacing tool
# reads it) and fill the channels juliaMotor produces.
const IBTREC = haskey(ENV, "JM_IBT")
const IBTDIR = "/home/g/sgl/THU/rFactor/juliaMotor/data/iracing"
const IBTNAME = NURB ? "nurburgring nordschleife" : SKIDPAD ? "skidpad" : "zandvoort"
const IBTTMPL = NURB ? joinpath(IBTDIR, "lotus49_nurburgring nordschleife 2026-06-14 11-11-37.ibt") :
                SKIDPAD ? joinpath(IBTDIR, "lotus49_skidpad 2026-06-14 10-49-07.ibt") :
                joinpath(IBTDIR, "lotus49_nurburgring nordschleife 2026-06-14 11-11-37.ibt")  # zandvoort: borrow layout

# Procedural skidpad / centripetal pad: flat asphalt + concentric measurement
# circles, diameters 10..200 m (radii 5..100 m).  Returns Render.TrackParts
# (11-float verts: pos3, normal3, col3, uv2; up-normal, no texture → vertex colour).
# 7-segment lit-segment table (a top, b TR, c BR, d bottom, e BL, f TL, g mid)
const SEG7 = Dict('0'=>(1,1,1,1,1,1,0),'1'=>(0,1,1,0,0,0,0),'2'=>(1,1,0,1,1,0,1),
                  '3'=>(1,1,1,1,0,0,1),'4'=>(0,1,1,0,0,1,1),'5'=>(1,0,1,1,0,1,1),
                  '6'=>(1,0,1,1,1,1,1),'7'=>(1,1,1,0,0,0,0),'8'=>(1,1,1,1,1,1,1),'9'=>(1,1,1,1,0,1,1))
function skidpad_parts()
    up = (0f0,1f0,0f0)
    push3!(v,x,y,z,c) = append!(v, Float32[x,y,z, up[1],up[2],up[3], c[1],c[2],c[3], 0f0,0f0])
    # quad on the pad (xz plane at height y), 2 tris, ccw from above
    quad!(v,x0,z0,x1,z1,y,c) = (push3!(v,x0,y,z0,c);push3!(v,x1,y,z1,c);push3!(v,x1,y,z0,c);   # CCW from above
                                push3!(v,x0,y,z0,c);push3!(v,x0,y,z1,c);push3!(v,x1,y,z1,c))
    # a flat 7-segment digit in a (u,v) cell [0..0.62]×[0..1]; map u→x, v→z
    function digit!(v, ch, x0, z0, s, th, c)
        S = get(SEG7, ch, (0,0,0,0,0,0,0)); W=0.62f0
        seg = Dict(1=>(th,W-th, 1-th,1f0), 2=>(W-th,W, 0.5f0,1-th), 3=>(W-th,W, th,0.5f0),
                   4=>(th,W-th, 0f0,th),   5=>(0f0,th, th,0.5f0),   6=>(0f0,th, 0.5f0,1-th),
                   7=>(th,W-th, 0.5f0-th/2,0.5f0+th/2))
        for k in 1:7
            S[k]==1 || continue; (u0,u1,v0,v1)=seg[k]
            quad!(v, x0+u0*s, z0+v0*s, x0+u1*s, z0+v1*s, 0.03f0, c)
        end
    end
    # a number string centred at (cx,cz), digit height `s`, placed flat
    function label!(v, n::Int, cx, cz, s, c)
        ds = string(n); nd=length(ds); adv=0.78f0*s; total=(nd-1)*adv + 0.62f0*s
        x0 = cx - total/2
        for ch in ds; digit!(v, ch, x0, cz - s/2, s, 0.13f0, c); x0 += adv; end
    end
    parts = Render.TrackPart[]
    # ground: medium-grey macadam, 320 x 320 m at y=0
    g = Float32[]; asph=(0.62f0,0.63f0,0.64f0); S=160f0
    for (ax,az,bx,bz,cx,cz) in ((-S,-S, S,-S, S,S), (-S,-S, S,S, -S,S))
        push3!(g,ax,0f0,az,asph); push3!(g,cx,0f0,cz,asph); push3!(g,bx,0f0,bz,asph)  # CCW from above (front-facing)
    end
    push!(parts, Render.TrackPart(g, "", asph))
    # circles: a thin band (annulus) per diameter, white; 50 m multiples brighter/yellow
    labels = Float32[]; lcol = (1f0,0.95f0,0.45f0)
    for d in 10:10:200
        r = Float32(d/2); ring=Float32[]; w=(d%50==0 ? 0.30f0 : 0.16f0); y=0.02f0
        col = d%50==0 ? (1f0,0.92f0,0.35f0) : (0.92f0,0.93f0,0.96f0)
        seg = max(72, round(Int, r*3.5))
        for i in 0:seg-1
            a0=2f0*Float32(pi)*i/seg; a1=2f0*Float32(pi)*(i+1)/seg
            xi0=(r-w)*cos(a0); zi0=(r-w)*sin(a0); xo0=(r+w)*cos(a0); zo0=(r+w)*sin(a0)
            xi1=(r-w)*cos(a1); zi1=(r-w)*sin(a1); xo1=(r+w)*cos(a1); zo1=(r+w)*sin(a1)
            push3!(ring,xi0,y,zi0,col); push3!(ring,xo1,y,zo1,col); push3!(ring,xo0,y,zo0,col)  # CCW from above
            push3!(ring,xi0,y,zi0,col); push3!(ring,xi1,y,zi1,col); push3!(ring,xo1,y,zo1,col)
        end
        push!(parts, Render.TrackPart(ring, "", col))
        # diameter label in metres, just outside the ring at the +x and -x edges
        ls = clamp(Float32(d)*0.18f0, 2.0f0, 9.0f0)         # bigger circles → bigger label
        label!(labels, d,  r + ls*0.9f0, 0f0, ls, lcol)
        label!(labels, d, -(r + ls*0.9f0), 0f0, ls, lcol)
    end
    push!(parts, Render.TrackPart(labels, "", lcol))
    parts
end

# GPL .trk centreline ↔ mesh alignment.  The .trk start point can be parsed with a
# large constant offset from the .3do mesh (the GPL Nürburgring start sits ~87 km off
# in z), which would float the racing line off the ground.  The line's SHAPE is
# correct, so we slide it (pure translation) to maximise overlap with the terrain HAT:
# estimate the offset from bbox centres, then grid-search + refine.  Zandvoort already
# aligns (offset ≈ 0) so it's returned untouched.
function align_centreline(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return cl                              # already on the mesh (Zandvoort)
    xs = Float64[]; zs = Float64[]
    for tr in hat.tris, p in (tr.a, tr.b, tr.c); push!(xs, p[1]); push!(zs, p[3]); end
    dx0 = (minimum(xs)+maximum(xs))/2 - (minimum(p[1] for p in cl)+maximum(p[1] for p in cl))/2
    dz0 = (minimum(zs)+maximum(zs))/2 - (minimum(p[2] for p in cl)+maximum(p[2] for p in cl))/2
    best = (cov(dx0, dz0), dx0, dz0)
    for dx in dx0-400:40:dx0+400, dz in dz0-400:40:dz0+400
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    for dx in best[2]-40:8:best[2]+40, dz in best[3]-40:8:best[3]+40
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    println("centreline aligned: ", round(Int, best[1]*100), "% on terrain, offset (",
            round(Int, best[2]), ", ", round(Int, best[3]), ")")
    [(p[1]+best[2], p[2]+best[3]) for p in cl]
end

# GPL scenery placement: load the .dat sub-object meshes the main .3do places via its
# 0x0E nodes (corner terrain sections, trees, signs, buildings — the Nordschleife
# landmass), transform each to world coords, and emit (a) world-space GPL tris for the
# collision HAT and (b) render TrackParts (GPL→render remap (gx,gz,-gy), grouped by
# texture).  This is what fills the void around the road on the GPL Nürburgring.
# Collapse a GPL .dat sub-object's coplanar front/back face pairs (thin signs, fences,
# billboards are modelled two-sided) into one face — the duplicate pair z-fights at
# distance and "flickers like fluorescent lights".  Keyed on quantised centroid+area;
# textured faces win so the survivor keeps its texture.  Rendering is two-sided
# (no backface cull) so the single face still shows from both sides.
function dedup_scenery(tris)
    isempty(tris) && return tris
    seen = Set{NTuple{4,Int}}(); keep = eltype(tris)[]
    for i in sort(collect(eachindex(tris)); by = j -> isempty(tris[j].tex) ? 1 : 0)
        tr = tris[i]; a,b,c = tr.p[1], tr.p[2], tr.p[3]
        cx=(a[1]+b[1]+c[1])/3; cy=(a[2]+b[2]+c[2])/3; cz=(a[3]+b[3]+c[3])/3
        ux=b[1]-a[1];uy=b[2]-a[2];uz=b[3]-a[3]; vx=c[1]-a[1];vy=c[2]-a[2];vz=c[3]-a[3]
        ar=0.5*sqrt((uy*vz-uz*vy)^2+(uz*vx-ux*vz)^2+(ux*vy-uy*vx)^2)
        key=(round(Int,cx/0.08),round(Int,cy/0.08),round(Int,cz/0.08),round(Int,ar/0.05))
        key in seen && continue
        push!(seen,key); push!(keep,tr)
    end
    keep
end

function gpl_scenery(ztrk, datpack, ribbon)
    pls = Render.GPL3DO.gpl_placements(ztrk)
    function placemat(t)
        d=(t[1],t[2],t[3]); m=(t[4],t[5],t[6]); s = t[7] <= 0 ? 1.0 : t[7]
        # GPL placement Euler angles: the 1st is YAW about UP (GPL comp-3), not roll about
        # the long axis — applied as yaw, terrain sections orient to the track and towers/
        # signs stay upright (just turned); applied as roll they all tilt over.  2nd = pitch
        # (comp-2), 3rd = roll (comp-1); rare in scenery.
        ca,sa=cos(m[1]),sin(m[1]); cb,sb=cos(m[2]),sin(m[2]); cc,sc=cos(m[3]),sin(m[3])
        Ryaw=[ca -sa 0; sa ca 0; 0 0 1.0]; Rpit=[cb 0 sb; 0 1.0 0; -sb 0 cb]; Rrol=[1.0 0 0; 0 cc -sc; 0 sc cc]
        R=(Rrol*Rpit*Ryaw).*s
        [R[1,1] R[1,2] R[1,3] d[1]; R[2,1] R[2,2] R[2,3] d[2]; R[3,1] R[3,2] R[3,3] d[3]; 0 0 0 1.0]
    end
    cache=Dict{String,Any}(); tmp=tempdir()
    getmesh(nm)=get!(cache, lowercase(nm)) do
        v=get(datpack, lowercase(nm*".3do"), nothing); v===nothing && return nothing
        tp=joinpath(tmp,"jm_nb_"*lowercase(nm)*".3do"); isfile(tp)||write(tp,v)
        m = try Render.GPL3DO.parse_3do(tp) catch; nothing end
        m===nothing ? nothing : dedup_scenery(m.tris)
    end
    hat=Render.GPL3DO.Tri[]; groups=Dict{String,Vector{Float32}}()
    for (nm,t) in pls
        mesh=getmesh(nm); mesh===nothing && continue
        M=placemat(t)
        ap(q)=(Float32(M[1,1]*q[1]+M[1,2]*q[2]+M[1,3]*q[3]+M[1,4]),
               Float32(M[2,1]*q[1]+M[2,2]*q[2]+M[2,3]*q[3]+M[2,4]),
               Float32(M[3,1]*q[1]+M[3,2]*q[2]+M[3,3]*q[3]+M[3,4]))
        rn(n)=(Float32(M[1,1]*n[1]+M[1,2]*n[2]+M[1,3]*n[3]),
               Float32(M[2,1]*n[1]+M[2,2]*n[2]+M[2,3]*n[3]),
               Float32(M[3,1]*n[1]+M[3,2]*n[2]+M[3,3]*n[3]))
        for tr in mesh
            w=(ap(tr.p[1]),ap(tr.p[2]),ap(tr.p[3])); nn=(rn(tr.n[1]),rn(tr.n[2]),rn(tr.n[3]))
            # DROP stray garbage geometry: a tri with a huge or wildly-stretched edge is a
            # vertex parsed at a junk coordinate — these render as the giant jagged "Star
            # Destroyer" shapes floating off in the sky.  Real scenery tris are < ~80 m.
            e1=hypot(w[2][1]-w[1][1],w[2][2]-w[1][2],w[2][3]-w[1][3])
            e2=hypot(w[3][1]-w[2][1],w[3][2]-w[2][2],w[3][3]-w[2][3])
            e3=hypot(w[1][1]-w[3][1],w[1][2]-w[3][2],w[1][3]-w[3][3])
            emax=max(e1,e2,e3); emin=min(e1,e2,e3)
            (emax > 150f0 || (emax > 70f0 && emax > 10f0*emin)) && continue
            # DROP scenery that intrudes into the road corridor (mis-placed/tilted objects
            # poking through the track) — render AND collision.  GPL world (gx,gy,gz=up);
            # the racing ribbon is queried in (gx,gy), road height is hr.height.
            cgx=(w[1][1]+w[2][1]+w[3][1])/3; cgy=(w[1][2]+w[2][2]+w[3][2])/3; cgz=(w[1][3]+w[2][3]+w[3][3])/3
            hr = JuliaMotor.hat(ribbon, cgx, cgy)
            (hr.found && abs(hr.lateral) < 5.0 && abs(cgz - hr.height) < 3.0) && continue
            # COLLISION: only near-HORIZONTAL scenery (ground/banks) goes in the HAT — never
            # walls/buildings/bridges/signs, or the car climbs them.  GPL z is up, so a ground
            # tri's geometric normal is z-dominant; a vertical structure's is not.
            ux=w[2][1]-w[1][1]; uy=w[2][2]-w[1][2]; uz=w[2][3]-w[1][3]
            vx=w[3][1]-w[1][1]; vy=w[3][2]-w[1][2]; vz=w[3][3]-w[1][3]
            nz=ux*vy-uy*vx; nl=sqrt((uy*vz-uz*vy)^2+(uz*vx-ux*vz)^2+nz^2)
            (nl > 1f-6 && abs(nz)/nl > 0.4f0) && push!(hat, Render.GPL3DO.Tri(w, nn, tr.uv, tr.tex, tr.col))
            v=get!(groups, tr.tex, Float32[])
            for i in 1:3
                q=w[i]; n=nn[i]; uv=tr.uv[i]
                append!(v, Float32[q[1],q[3],-q[2], n[1],n[3],-n[2], tr.col[1],tr.col[2],tr.col[3], uv[1],uv[2]])
            end
        end
    end
    (hat, [Render.TrackPart(v, tex, (0.5f0,0.5f0,0.5f0)) for (tex,v) in groups])
end

# ---- load physics + geometry: the GPL Zandvoort track + Vanwall-calibrated physics ----
const GD = default_gamedata()
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)              # physics (Lotus-49 calibration is the future goal)
const GPLBASE = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks"
const GPLNAME = NURB ? "nurburg" : "zandvort"           # both are GPL tracks (same .3do/.trk/.mip pipeline)
const ZD   = joinpath(GPLBASE, GPLNAME)
const ZTRK = joinpath(ZD, GPLNAME * ".3do")
if SKIDPAD
    print("building skidpad... "); flush(stdout)
    const TRACK = skidpad_parts()
    println("flat pad + 20 measurement circles, diameters 10-200 m")
else
    print("loading GPL ", GPLNAME, "… "); flush(stdout)
    const TRACKMESH0 = Render.GPL3DO.parse_3do(ZTRK)
    # Align the racing line against the ROAD-only HAT (precise — scenery terrain in the
    # full HAT would let the line drift onto the grass verge); the road ribbon then doubles
    # as the corridor filter for scenery placement.
    const TERRAIN0 = GPLTrack.build_hat(TRACKMESH0)
    const ALIGNED  = align_centreline(GPLTrack.trk_centreline(joinpath(ZD, GPLNAME*".trk")), TERRAIN0)
    const RIBBON0  = GPLTrack.build_surface(ALIGNED, TERRAIN0)
    # GPL Nürburgring places its landmass/scenery as .dat sub-objects via 0x0E nodes;
    # load + place them so the road isn't floating over a void (Zandvoort has none).
    SECTRI = Render.GPL3DO.Tri[]; SECPARTS = Render.TrackPart[]
    if NURB && isfile(joinpath(ZD, "nurburg.dat"))
        print("scenery… "); flush(stdout)
        dp = Render.GPLDat.parse_dat(joinpath(ZD, "nurburg.dat"))
        SECTRI, SECPARTS = gpl_scenery(ZTRK, dp, RIBBON0)
        print(length(SECPARTS), " groups / ", length(SECTRI), " tris… ")
    end
    const TRACKMESH = isempty(SECTRI) ? TRACKMESH0 :
        Render.GPL3DO.Mesh3DO([TRACKMESH0.tris; SECTRI], TRACKMESH0.textures,
                              [TRACKMESH0.groups; fill(0, length(SECTRI))])
    const TERRAIN  = isempty(SECTRI) ? TERRAIN0 : GPLTrack.build_hat(TRACKMESH)
    const TRKSURF  = GPLTrack.build_surface(ALIGNED, TERRAIN)
    const LAPLEN = maximum(TRKSURF.lapdist)              # lap length [m], for start/finish wrap detection
    const CAR = DriveCar(MODEL, TRKSURF; terrain=TERRAIN)    # racing ribbon from the .trk centreline
    println(TERRAIN, "  ", TRKSURF)
    print("extracting geometry… "); flush(stdout)
    const TRACK = [Render.extract_gpl_car(ZTRK; track=true, mirror=true, exclude=("ltraymap","lshad","wiref_s")); SECPARTS]
end
# ---- GPL Lotus 49 (replaces the rFactor Vanwall; the authentic GPL-pivot car) ----
const LOTDIR = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus"
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOT3DO = joinpath(LOTDIR,"lotus.3do")
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=("ltraymap","lshad","lohand","lotarms","lotmirt",Render.STEER_TEX...), exclude_groups=(6600,3560), cockpit_clean=true, maxlat=0.85f0)  # no hands/dup-mirror/teal front-susp; drop tan floor; clip splayed rear (insect legs)
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
const HORIZON_RING = SKIDPAD ? nothing : Render.build_horizon(TEXIDX)   # skidpad: clear blue sky, no GPL ring
# ---- Phase 3 (a): auto-place trackside objects (GPL .3do geometry, textured from
# loose files + the packed zandvort.dat).  Names + transforms come from the .3do
# instance records; geometry/textures resolve from loose files OR the .dat archive.
# (skidpad is bare; Nürburgring scenery is mostly baked into nurburg.3do — the
#  Zandvoort-tuned .dat object placement below is skipped for it for now.)
if SKIDPAD || NURB
    global OBJECTS = Any[]
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
else
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
end
carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
# four Lotus wheels — keep the untextured black tyre body (only the car body drops "")
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(0.12f0,0.12f0,0.13f0)), GPLTEX)  # force dark tyre
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
println(count(it->it.tex!=0, trackItems), "/", length(trackItems), " track + ",
        count(it->it.tex!=0, carItems), "/", length(carItems), " Lotus parts textured")
const PROJ = Render.perspective(deg2rad(62f0), Float32(W/H), 0.35f0, 3000f0)  # tighter range → less distant z-fight (horizon ring R=2500 < far)

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; view::Int; auto::Bool; end
# shift mode: AUTO (auto-shift, no clutch) by default; SAND_SHIFT=manual starts in
# realistic mode (you shift E/Q, clutch required).  G toggles in-app.
const CTL = Ctl(false,false,false,false,false, 1, get(ENV,"ZAND_SHIFT","manual") == "auto")   # MANUAL by default
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
    SKIDPAD && return 0.0   # flat pad → no slope
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
    cs0 = SKIDPAD ? (x=0.0, z=0.0, θ=0.0) : spawn(CAR; v0=0.0)   # spawn pose (skidpad: pad centre)
    LASTZ = Ref(0.0); ONTRACK = Ref(true)
    function groundz(x, z)                            # HAT elevation; off-surface holds last height
        SKIDPAD && return 0.0   # flat skidpad → no elevation
        h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf)
        h[3] ? (LASTZ[] = Float64(h[1]); ONTRACK[] = true) : (ONTRACK[] = false)
        LASTZ[]
    end
    cs = build_car(x0=cs0.x, z0=cs0.z, θ0=cs0.θ, v0=0.0)   # MTK car — standing start
    spin = 0.0; last = time(); frames = 0; titleT = last
    v_prev = cs.v; pitch_dyn = 0.0; pitch_ter = 0.0    # dive/squat + terrain-slope pitch (smoothed)
    # lap timing + telemetry log
    lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = cs.laps; tsamp = 0
    fmt_lap(s) = (m=floor(Int,s/60); sec=s-60m; si=floor(Int,sec); ms=round(Int,(sec-si)*1000);
                  "$m:$(lpad(si,2,'0')).$(lpad(ms,3,'0'))")
    ibt_samples = IBTREC ? Dict{String,Float64}[] : nothing      # iRacing-format telemetry rows
    IBTREC && println("  recording iRacing .ibt telemetry (JM_IBT) — template: ", basename(IBTTMPL))
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
        if rst; respawn!(cs)
        else; step_car!(cs, inp.throttle, inp.brake, inp.steer, dt > 1e-4 ? dt : 1/60;
                        clutch=inp.clutch, up=inp.shift_up, dn=inp.shift_down, manual=!inp.autoshift,
                        groundz=groundz)
            if !SKIDPAD     # track position + lap timing (Zandvoort only)
            hr = JuliaMotor.hat(TRKSURF, cs.x, cs.z)            # track-relative position
            if hr.found
                (cs.lapdist > 0.75*LAPLEN && hr.lapdist < 0.25*LAPLEN) && (cs.laps += 1)  # crossed S/F
                cs.lapdist = hr.lapdist; cs.lateral = hr.lateral; cs.along = hr.lapdist; cs.ontrack = hr.on_track
            else; cs.ontrack = false; end
            end
        end
        spin -= cs.v*dt/0.33
        ENG.rpm[] = cs.rpm                         # feed the engine-audio thread

        # ---- iRacing .ibt telemetry sample (one row per frame, ~60 Hz) ----
        if ibt_samples !== nothing && !rst
            tl = telemetry(cs); δw = inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer)
            push!(ibt_samples, Dict{String,Float64}(
                "SessionTime"=>cs.t, "SessionTick"=>Float64(length(ibt_samples)+1),
                "IsOnTrack"=>cs.ontrack ? 1.0 : 0.0,
                "Speed"=>cs.v, "RPM"=>cs.rpm, "Gear"=>Float64(cs.gear),
                "Throttle"=>inp.throttle, "Brake"=>inp.brake, "Clutch"=>1.0-inp.clutch,
                "SteeringWheelAngle"=>δw,
                "Lap"=>Float64(cs.laps+1), "LapCompleted"=>Float64(cs.laps),
                "LapDist"=>cs.lapdist, "LapDistPct"=>(SKIDPAD ? 0.0 : (LAPLEN>0 ? cs.lapdist/LAPLEN : 0.0)),
                "Yaw"=>cs.θ, "YawRate"=>tl.r,
                "VelocityX"=>tl.u, "VelocityY"=>tl.v, "VelocityZ"=>0.0,
                "LongAccel"=>tl.ax, "LatAccel"=>tl.ay, "VertAccel"=>9.80665,
                "LFspeed"=>tl.ωf*0.30, "RFspeed"=>tl.ωf*0.30, "LRspeed"=>tl.ωr*0.33, "RRspeed"=>tl.ωr*0.33,
                "Alt"=>cs.y))
        end

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
        δ = Float32(inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer))
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
        Render.draw_sky(skyprog, skyvao, inv(vp), eye, LIGHTDIR;
                        cloud = SKIDPAD ? 0.18 : 1.0,                       # skidpad: near-clear blue sky
                        zenith = SKIDPAD ? (0.20f0,0.42f0,0.78f0) : Render.ZENITH,
                        horizon = SKIDPAD ? (0.62f0,0.74f0,0.88f0) : Render.HORIZON)
        Render.set_scene_uniforms(prog, eye; fognear=400f0, fogfar=2800f0); Render.bind_shadow(prog, shadowtex, lightVP)
        HORIZON_RING === nothing || Render.draw_horizon(prog, HORIZON_RING, vp, eye)   # GPL horizon ring backdrop
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
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, 9500.0, inp.throttle, inp.brake, cs.tc;
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
    if ibt_samples !== nothing && !isempty(ibt_samples)
        try
            tmpl = ibt_open(IBTTMPL)
            ts = Dates.format(Dates.now(), "yyyy-mm-dd HH-MM-SS")
            odir = get(ENV, "JM_IBT_DIR", joinpath(dirname(dirname(@__DIR__)), "data", "juliaracer"))
            mkpath(odir)
            out = joinpath(odir, "lotus49_$(IBTNAME) $(ts).ibt")   # iRacing filename convention
            write_ibt(out, tmpl, ibt_samples)
            println("  wrote iRacing telemetry: ", out, "  (", length(ibt_samples), " ticks, ", filesize(out)÷1024, " KB)")
        catch e
            println("  .ibt export failed: ", e)
        end
    end
    EngineAudio.stop!(ENG)
    GLFW.Terminate()
    println("bye")
end
main()
