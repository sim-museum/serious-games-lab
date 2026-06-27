# juliaMotor — DRIVE THE MTK MODEL.  Same GPL Zandvoort + Lotus 49 renderer as
# drive_native.jl, but the physics is the iRacing-fit JuliaMotorMTK model (DriveRT).
# (GLFW/ModernGL/GLSL) driving the validated JuliaMotor physics over the real
# Zandvoort + Vanwall geometry, with native keyboard AND joystick input.  The
# first step toward an rF1-fidelity self-contained app; the rendering core is
# render.jl.
using GLFW, ModernGL, LinearAlgebra, Dates
using JuliaMotor, RFactorData
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt.jl"); using .DriveRT  # MTK physics (planar)
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/drive_rt3d.jl"); using .DriveRT3D  # full-3D physics (JM_3D=1)
include("/home/g/sgl/THU/rFactor/juliaMotor/JuliaMotorMTK/src/ibt.jl"); using .IBT           # iRacing .ibt telemetry writer
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack
include("audio.jl"); using .EngineAudio
include("joycfg.jl"); using .JoyCfg
include("ffb.jl"); using .FFB
include("ai.jl"); using .RaceAI           # rail-following race opponents (JM_AI)
# Force-feedback tuning (env-overridable). SIGN=-1 ⇒ force opposes the front lateral
# force, so the wheel self-centres (measured: steer-left gives +front_lat).
const FFB_ON     = !haskey(ENV, "JM_NOFFB")
const FFB_GAIN   = parse(Float64, get(ENV, "JM_FFB_GAIN", "1.3"))     # pre-soft-clip gain on the aligning torque
const FFB_SIGN   = parse(Float64, get(ENV, "JM_FFB_SIGN", "-1.0"))    # -1 ⇒ resist (self-centre)
const FFB_ATRAIL = parse(Float64, get(ENV, "JM_FFB_TRAIL", "0.18"))   # front slip [rad] where pneumatic trail is spent
const FFB_TFLOOR = 0.40                                               # residual mechanical trail (caster) — wheel lightens, not dead
const FFB_AF     = 1.314                                              # CG → front axle [m]
const FFB_DELTA  = 0.30                                               # road-wheel angle at full lock [rad] (matches DriveRT)
const FFB_SQ     = parse(Float64, get(ENV, "JM_FFB_SQ",  "0.03"))   # squelch knee on the ROAD term only (kills tyre-force noise; the spring keeps center alive)
const FFB_LP     = parse(Float64, get(ENV, "JM_FFB_LP",  "0.05"))   # low-pass time-constant [s] on the FFB force — smooths jostle, keeps it continuous
const FFB_SPRING = parse(Float64, get(ENV, "JM_FFB_SPRING", "0.55"))# self-centering SPRING ∝ wheel angle — smooth return-to-center so there's NO dead zone
const _JOYCONF = joinpath(@__DIR__, "joystick.conf")
const JOYMAP = if isfile(_JOYCONF)
    JoyCfg.loadmap(_JOYCONF)                                  # honour gui.py / calibrate.jl (TX clutch pedal, etc.)
else
    let m = JoyCfg.defaultmap()                              # no config → old Logitech X3D default
        JoyCfg.JoyMap(m.steer, m.throttle, m.brake, JoyCfg.Ctrl(4, -1.0, 1.0),   # clutch on the X3D SLIDER (axis 4)
                      m.up_btn, m.dn_btn, m.clutch_btn, m.deadzone)
    end
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

# ---- session mode + race config (GPL-style: Practice / Training / Race) ----
const MODE      = lowercase(get(ENV, "JM_MODE", "practice"))   # practice | training | race
const RACE_LAPS = max(1, tryparse(Int, get(ENV, "JM_LAPS", "3")) |> x -> x === nothing ? 3 : x)
const N_AI      = clamp(tryparse(Int, get(ENV, "JM_AI", "0")) |> x -> x === nothing ? 0 : x, 0, 5)
const IS_RACE   = MODE == "race"
const IS_TRAIN  = MODE == "training"
println("  → mode: ", uppercasefirst(MODE),
        IS_RACE ? "  ($RACE_LAPS laps" * (N_AI>0 ? ", $N_AI AI cars)" : ")") : "")

# ---- iRacing .ibt telemetry export (JM_IBT=1) ----
# Record the lap in iRacing's exact .ibt format so juliaMotor laps can be diffed
# against gold-standard iRacing telemetry (same car/track, similar laps) to tune the
# model.  We reuse a real iRacing .ibt of the matching car/track as the header+var-
# table+YAML template (so the file is byte-identical in structure / any iRacing tool
# reads it) and fill the channels juliaMotor produces.
const IBTREC = !haskey(ENV, "JM_NOIBT")          # .ibt telemetry ON by default (set JM_NOIBT to disable)
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
    # a flat number PAINTED on the pad at ring point (cx,cz), oriented RADIALLY (digit "up" =
    # radially outward, width along the tangent), so it reads upright from the centre. No back
    # face ⇒ no mirror ambiguity. Digit cell (u,v) → world via the radial/tangent basis, on the ground.
    FSEG = Dict(1=>(0.13f0,0.49f0,0.87f0,1f0), 2=>(0.49f0,0.62f0,0.5f0,0.87f0), 3=>(0.49f0,0.62f0,0.13f0,0.5f0),
                4=>(0.13f0,0.49f0,0f0,0.13f0), 5=>(0f0,0.13f0,0.13f0,0.5f0), 6=>(0f0,0.13f0,0.5f0,0.87f0),
                7=>(0.13f0,0.49f0,0.435f0,0.565f0))
    function flabel!(v, n::Int, cx, cz, s, c)
        r=sqrt(cx^2+cz^2); rx=cx/r; rz=cz/r; tx=-rz; tz=rx           # radial-out, tangent
        wpt(uu,vv) = (cx + uu*s*tx + vv*s*rx, cz + uu*s*tz + vv*s*rz)
        ds=string(n); adv=0.78f0; total=Float32((length(ds)-1)*adv+0.62f0); u0=-total/2
        for ch in ds
            S=get(SEG7,ch,(0,0,0,0,0,0,0))
            for k in 1:7
                S[k]==1 || continue; (a0,a1,b0,b1)=FSEG[k]
                (x00,z00)=wpt(u0+a0,b0); (x10,z10)=wpt(u0+a1,b0); (x11,z11)=wpt(u0+a1,b1); (x01,z01)=wpt(u0+a0,b1)
                push3!(v,x00,0.04f0,z00,c); push3!(v,x10,0.04f0,z10,c); push3!(v,x11,0.04f0,z11,c)
                push3!(v,x00,0.04f0,z00,c); push3!(v,x11,0.04f0,z11,c); push3!(v,x01,0.04f0,z01,c)
            end
            u0+=adv
        end
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
        # diameter label in metres — flat on the ground, on the yellow (50 m) rings only,
        # at the 4 cardinal points (each reads upright from the pad centre)
        if d % 50 == 0
            ls = clamp(Float32(d)*0.06f0, 2.0f0, 5.0f0)
            flabel!(labels, d, 0f0,  r, ls, lcol); flabel!(labels, d, 0f0, -r, ls, lcol)
            flabel!(labels, d,  r, 0f0, ls, lcol); flabel!(labels, d, -r, 0f0, ls, lcol)
        end
    end
    push!(parts, Render.TrackPart(labels, "", lcol))

    # ---- central orange cones (period 1967 skidpad markers) — orient the driver to the centre ----
    cones = Float32[]; ocol = (0.95f0, 0.42f0, 0.10f0)
    function cone!(v, cx, cz, h, rad, c)
        n = 6
        for i in 0:n-1
            a0 = 2f0*Float32(pi)*i/n; a1 = 2f0*Float32(pi)*(i+1)/n
            push3!(v, cx+rad*cos(a0), 0f0, cz+rad*sin(a0), c)
            push3!(v, cx+rad*cos(a1), 0f0, cz+rad*sin(a1), c)
            push3!(v, cx, h, cz, c)                          # apex
        end
    end
    for k in 0:5                                             # ring of 6 cones inside the 10 m circle
        ang = Float32(k)*Float32(pi)/3; cone!(cones, 2.6f0*cos(ang), 2.6f0*sin(ang), 0.62f0, 0.22f0, ocol)
    end
    cone!(cones, 0f0, 0f0, 0.7f0, 0.26f0, ocol)             # one dead centre
    push!(parts, Render.TrackPart(cones, "", ocol))
    # (distant scenery is BORROWED from GPL tracks — a horizon backdrop ring, see HORIZON_RING below)
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
    # Flat HORIZONTAL sprite stubs (UP-extent ≈ 0, small): GPL draws these camera-facing,
    # but rendering the raw quad as geometry lays them flat on the ground = the "horizontal
    # floating signs/people".  A real standing sign (XK_FLAT3, shell ~11 m) has vertical
    # extent; a flat stub (SIGN1/SIGNX/sign2m…) has UP≈0.  Skip the flat stubs.
    spritecache=Dict{String,Bool}()
    issprite(nm,mesh)=get!(spritecache,nm) do
        lo3=Inf;hi3=-Inf;loh=Inf;hih=-Inf
        for tr in mesh, p in tr.p
            lo3=min(lo3,p[3]);hi3=max(hi3,p[3]);loh=min(loh,p[1],p[2]);hih=max(hih,p[1],p[2])
        end
        (hi3-lo3) < 0.5 && (hih-loh) < 6.0
    end
    hat=Render.GPL3DO.Tri[]; groups=Dict{String,Vector{Float32}}(); nskip=0
    for (nm,t) in pls
        startswith(nm,"treesrb") && continue        # forest-BACKDROP "paintings" (streea/b/c) — render as a streaky smear
        mesh=getmesh(nm); (mesh===nothing || isempty(mesh)) && continue
        issprite(nm,mesh) && (nskip+=1; continue)   # flat horizontal sprite stub
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
    nskip > 0 && print("(skipped ", nskip, " flat sprite stubs) ")
    (hat, [Render.TrackPart(v, tex, (0.5f0,0.5f0,0.5f0)) for (tex,v) in groups])
end

# ---- load physics + geometry: the GPL Zandvoort track + Vanwall-calibrated physics ----
const GD = default_gamedata()
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)              # physics (Lotus-49 calibration is the future goal)
const GPLBASE = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks"
# TRACKSEL → GPL track folder (all share the .3do/.trk/.mip/.dat pipeline)
const GPLNAME = get(Dict("nurburgring"=>"nurburg", "zandvoort"=>"zandvort",
                         "watglen"=>"watglen", "monza"=>"monza10k", "spa"=>"spa67"),
                    TRACKSEL, "zandvort")
const ZD   = joinpath(GPLBASE, GPLNAME)
# the track's packed archive (geometry/centreline/textures/objects live here on most tracks)
const TRACKDAT = (p=joinpath(ZD, GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMPTRK = mktempdir()
"Path to a track file (`base`+`ext`, e.g. \".3do\"/\".trk\"): loose on disk if present, else extracted from the track .dat."
function track_file(base, ext)
    p = joinpath(ZD, base*ext); isfile(p) && return p
    v = get(TRACKDAT, lowercase(base*ext), nothing)
    v === nothing && return p
    q = joinpath(TMPTRK, base*ext); write(q, v); q
end
const ZTRK = track_file(GPLNAME, ".3do")
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
    const ALIGNED  = align_centreline(GPLTrack.trk_centreline(track_file(GPLNAME, ".trk")), TERRAIN0)
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
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=("ltraymap","lshad","lohand","lotarms","lotmirt","windlot",Render.STEER_TEX...), exclude_groups=(6600,3560), cockpit_clean=true, maxlat=0.85f0)  # no hands/dup-mirror/teal front-susp/tan scuttle "rug"; drop tan floor; clip splayed rear
const SWPARTS, SWCENTER, SWAXIS = Render.extract_gpl_steering(LOT3DO)   # steering wheel + pivot
println(length(TRACK), " track parts + ", length(CARP), " Lotus body parts")
const BODY_OFF = Float32[-0.55, 0.30, 0.0]     # centre body on X, lift onto the wheels
# wheel hubs (rig frame X fwd, Y=radius, Z left); front pair steers, all spin
const WHEELS = (( 1.05f0, 0.62f0,true, 0.31f0,"lotwlf"), ( 1.05f0,-0.62f0,true, 0.31f0,"lotwrf"),
                (-1.15f0, 0.66f0,false,0.34f0,"lotwlr"), (-1.15f0,-0.66f0,false,0.34f0,"lotwrr"))

# ---- GL init (visible window on the user's display) ----
const W, H = 1440, 810
# distance culling (squared, render-world units = m): skip far trackside objects/billboards
# per frame so the big layouts (Spa ~5.7k instances, Monza, Nürburgring) keep their FPS.
# Sized larger than small circuits (Zandvoort ~1.3 km) so those cull nothing — visible only
# on the big valleys where the far half-track would otherwise be drawn every frame.
const OBJ_CULL2 = 2200f0^2      # mesh objects (buildings/grandstands/trees) — keep distant landmarks
const BB_CULL2  = 1300f0^2      # billboards (tree/shrub/crowd sprites) — far ones add little
const SMOKE = haskey(ENV, "JM_SMOKE")     # headless self-test: hidden window, auto-exit
const CAR3D = !haskey(ENV, "JM_2D")       # full-3D vehicle (heave/pitch/roll + jumps) is the DEFAULT; JM_2D forces the planar model
# physics dispatch — Car3D is field/method-compatible with DriveRT.Car (superset)
build_carX(; kw...)        = CAR3D ? DriveRT3D.build_car3d(; kw...) : DriveRT.build_car(; kw...)
step_carX!(c, a...; kw...) = CAR3D ? DriveRT3D.step_car3d!(c, a...; kw...) : DriveRT.step_car!(c, a...; kw...)
telemetryX(c)              = CAR3D ? DriveRT3D.telemetry3d(c) : DriveRT.telemetry(c)
respawnX!(c)               = CAR3D ? DriveRT3D.respawn3d!(c) : DriveRT.respawn!(c)
containX!(c, x, z; kw...)  = CAR3D ? DriveRT3D.contain3d!(c, x, z; kw...) : DriveRT.contain!(c, x, z; kw...)
const FENCE = parse(Float64, get(ENV, "JM_FENCE", "13.0"))   # E7: track boundary (m from centreline) — you can't leave the world
println(CAR3D ? "  PHYSICS: full-3D vehicle (default) — heave/pitch/roll + suspension travel + jumps" :
                "  PHYSICS: planar 2-D model (JM_2D)")
GLFW.Init()
GLFW.WindowHint(GLFW.VISIBLE, false)   # stay HIDDEN through the long texture load (no WM "Not Responding"); shown once the render loop starts
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR, 4); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR, 5)  # 4.5 → glClipControl (reversed-Z)
GLFW.WindowHint(GLFW.OPENGL_PROFILE, GLFW.OPENGL_CORE_PROFILE)
GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT, true)
GLFW.WindowHint(GLFW.SAMPLES, 8)                  # 8× MSAA — smooth jaggies + finer alpha-to-coverage (cutout shimmer)
win = GLFW.CreateWindow(W, H, "Julia Racer — $(uppercasefirst(TRACKSEL)) (loading…)")
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
# ---- per-track colour grade -------------------------------------------------
# The road circuits (Nürburgring/Monza/Watkins Glen/Spa) get a bright-sunny-day
# grade matched to the iRacing reference shots: a saturated blue sky gradient,
# pale-blue haze, warm-white sun + cool-blue sky-fill (warm sun / cool shadow),
# punchier saturation, and a warmed/brightened GPL horizon ring so the overcast
# photographic band reads as hazy daylight rather than gloom.  Zandvoort and the
# skidpad keep the existing GPL overcast look.
struct ColourGrade
    zenith::NTuple{3,Float32}; horizon::NTuple{3,Float32}   # sky gradient; horizon also = fog/haze colour
    cloud::Float32                                          # procedural cloud coverage
    suncol::NTuple{3,Float32}; ambsky::NTuple{3,Float32}; sat::Float32   # sun tint / sky-fill tint / saturation
    ringtint::NTuple{3,Float32}                             # GPL horizon-ring multiply (warm + brighten)
end
const GRADE_GPL   = ColourGrade((0.40,0.56,0.78),(0.78,0.78,0.75),1.0, (1,1,1),(0.95,0.93,0.86),1.0, (1,1,1))
const GRADE_SUNNY = ColourGrade((0.20,0.47,0.85),(0.80,0.88,0.97),1.0, (1.07,1.0,0.85),(0.72,0.82,0.99),1.18, (1.28,1.27,1.30))
const GRADE_SKIDPAD = ColourGrade((0.20,0.42,0.78),(0.62,0.74,0.88),0.18, (1,1,1),(0.95,0.93,0.86),1.0, (1,1,1))
const GRADE = SKIDPAD ? GRADE_SKIDPAD :
              (TRACKSEL in ("nurburgring","monza","watglen","spa")) ? GRADE_SUNNY : GRADE_GPL
const ENG = EngineAudio.build_lotus(gamedata = GD)   # GPL Ford DFV V8, RPM-pitched; START is deferred to just before the game loop (below)
print("loading textures… "); flush(stdout)
const TEXIDX = Render.gpl_texture_index(ZD)
trackItems = Render.build_gpl(TRACK, TEXIDX)
# GPL sky dome: the 12-panel horizon ring (horiz0..11), camera-centred backdrop.
const HORIZON_RING = if !SKIDPAD
    Render.build_horizon(TEXIDX)
else   # skidpad: borrow the Nürburgring (Eifel forest) horizon backdrop for orientation
    try
        Render.build_horizon(Render.gpl_texture_index(joinpath(GPLBASE, "nurburg")))
    catch e
        println("  skidpad horizon (nurburg) unavailable (", e, ") — clear sky"); nothing
    end
end
# ---- Phase 3 (a): auto-place trackside objects (GPL .3do geometry, textured from
# loose files + the packed zandvort.dat).  Names + transforms come from the .3do
# instance records; geometry/textures resolve from loose files OR the .dat archive.
# (skidpad is bare; Nürburgring scenery is mostly baked into nurburg.3do — the
#  Zandvoort-tuned .dat object placement below is skipped for it for now.)
if SKIDPAD || NURB
    global OBJECTS = Any[]
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
else
const DATPACK = TRACKDAT     # trackside objects come from the track's own .dat (generic across tracks)
const TMPOBJ = mktempdir()
objpath(nm) = (p=joinpath(ZD, nm*".3do"); isfile(p) ? p :
    (v=get(DATPACK, lowercase(nm*".3do"), nothing); v===nothing ? "" :
     (tp=joinpath(TMPOBJ, nm*".3do"); isfile(tp)||write(tp,v); tp)))
# stands-only crowd policy (user): KEEP the seated grandstand/pit-wall crowds, so we no
# longer strip their painted-on people textures — only the GPL shadow/tray artifacts go.
# (Loose roadside people are dropped by name in drop() below, not by texture.)
const CROWD_TEX = ("ltraymap","lshad")
let objnames=Set{String}()
    for f in readdir(ZD); endswith(lowercase(f),".3do") && push!(objnames, lowercase(replace(f,r"\.3do$"i=>""))); end
    for k in keys(DATPACK); endswith(k,".3do") && push!(objnames, replace(k,r"\.3do$"=>"")); end
    insts = GPLTrack.trackside_objects(ZTRK; objnames=objnames)
    # Trees (tree*/newt*) ship as SINGLE flat textured panels with a chroma-key (green/grey)
    # background — fine in GPL where they're drawn as camera-facing sprites, but as a static
    # MESH our pipeline renders them face-on with raw UVs and no alpha cutout → a tall white
    # "smear" (the famous Watkins pit-straight artifact).  Force these down the BILLBOARD path
    # (clean 0-1 UVs + alpha-keyed cutout, always camera-facing) like Zandvoort's trees.
    treeish(nm) = startswith(nm,"tree") || startswith(nm,"newt")
    objmesh=Dict{String,Any}(); ymn=Dict{String,Float32}(); ymx=Dict{String,Float32}(); bbinfo=Dict{String,Any}()
    for inst in insts
        (haskey(objmesh, inst.name) || haskey(bbinfo, inst.name)) && continue
        p = objpath(inst.name)
        if p == ""; objmesh[inst.name]=nothing; continue; end
        try
            full = Render.extract_gpl_car(p; track=true, mirror=true)   # un-stripped: decides stub vs geometry
            if isempty(full) || treeish(inst.name)         # a billboard stub (tree/sprite) — or a tree panel forced to one
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
    groundz(x,y) = (h=JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(y); ref=Inf); h[3] ? Float32(h[1]) : -999f0)  # -999 = OFF the HAT
    # placement height: snap to OUR terrain where the HAT covers it (kills floaters from a
    # terrain mismatch); else fall back to the object's AUTHORED GPL height (same frame as the
    # track mesh) so far-trackside objects the HAT doesn't reach aren't lost.
    ploz(i)  = (gz = groundz(i.x, i.y); gz > -900f0 ? gz : Float32(i.z))
    # track's own vertical band (GPL-z, = HAT height) — some classic layouts are authored with a
    # large vertical offset (Spa sits at z≈294..498 m, not ≈0), so a hard-coded height window is
    # wrong.  On-HAT objects are snapped to the terrain ⇒ grounded by construction (always keep);
    # only OFF-HAT objects (authored-z fallback) get a sanity check, relative to the track band.
    trkzlo=Inf32; trkzhi=-Inf32
    for t in TRACKMESH.tris, vi in 1:3; z=Float32(t.p[vi][3]); trkzlo=min(trkzlo,z); trkzhi=max(trkzhi,z); end
    onground(i) = (gz = groundz(i.x, i.y); gz > -900f0 || (trkzlo-150f0 < Float32(i.z) < trkzhi+150f0))
    # crowd policy = STANDS ONLY: keep seated grandstand / pit-wall crowds (these read as
    # populated stands, matching the GPL screenshots), drop loose roadside people.
    standcrowd(nm) = startswith(nm,"grndpe") || startswith(nm,"pitpeo") || startswith(nm,"pitppl") ||
                     startswith(nm,"pplrow") || startswith(nm,"peprow") || startswith(nm,"plrow")
    # drop: ground-cover planes (grass/herbe/infield), white "fuel-tank" tents, infield/backdrop
    # tree smears, and LOOSE people only — marshals, photographers, rescue crews, lone figures,
    # and standing roadside spectators (Spa people*/pelf*).  Seated stand crowds are kept above.
    drop(nm) = !standcrowd(nm) && (
               startswith(nm,"grass") || startswith(nm,"herbe") || nm == "infield" ||
               startswith(nm,"tent") || startswith(nm,"single") ||
               startswith(nm,"intree") ||                                    # INFIELD tree lines (100s of m wide) → distant central "smear"
               startswith(nm,"treesrb") || startswith(nm,"treefill") ||      # forest-BACKDROP / gap-fill quads → streaky "painted tree" smear (Watkins pit-straight)
               startswith(nm,"ppl") || startswith(nm,"people") || startswith(nm,"pelf") ||  # loose standing spectators
               startswith(nm,"p_s") || startswith(nm,"pform") ||             # Spa distributed standing-spectator sprites (p_s1..19 = p_s1srb, ~900) + pform1 (foreground photographer); NB not p_armco/p_*
               nm in ("chrisa","sergioa","thomasa","hatzia","stefana","starter") ||  # Spa named loose figures (Chris/sergio/thomas/Hatzi/Stefan/starter) — NOT prinz*/spider* (cars)
               startswith(nm,"grndp") || startswith(nm,"crowd") || startswith(nm,"spect") ||
               startswith(nm,"flagger") || startswith(nm,"rescu") ||
               startswith(nm,"photo") || startswith(nm,"fotograf"))          # marshals/photographers = loose people
    istree(nm) = startswith(nm,"tree") || startswith(nm,"newt") || startswith(nm,"intree")  # foliage → graze-fade (no end-on smear)
    global OBJECTS = [(objmesh[i.name], Render.translate(Float32[i.x, ploz(i), -i.y]) * Render.roty(Float32(-i.yaw)), istree(i.name), (Float32(i.x), ploz(i), Float32(-i.y)))
                      for i in insts if get(objmesh,i.name,nothing) !== nothing &&
                          !drop(i.name) && (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && onground(i)]
    # billboards: (Item, render-pos base, width, height) — drawn camera-facing per frame
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
    for i in insts
        bb = get(bbinfo, i.name, nothing); (bb === nothing || drop(i.name)) && continue
        onground(i) || continue; gz = ploz(i)
        item, tw, th, h, wid = bb
        w = wid > 0f0 ? wid : h*tw/max(th,1f0)
        push!(BILLBOARDS, (item, (Float32(i.x), gz, Float32(-i.y)), Float32(w), Float32(h)))
    end
end
println(length(OBJECTS), " trackside objects + ", length(BILLBOARDS), " billboards placed"); flush(stdout)
end
carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
# four Lotus wheels — keep the untextured black tyre body (only the car body drops "")
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(0.12f0,0.12f0,0.13f0)), GPLTEX)  # force dark tyre
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
println(count(it->it.tex!=0, trackItems), "/", length(trackItems), " track + ",
        count(it->it.tex!=0, carItems), "/", length(carItems), " Lotus parts textured")

# ---- E8: the AI grid = the standard GPL '67 chassis (Ferrari/Brabham/BRM/Eagle/
# Cooper), each its OWN GPL car, not Lotus copies.  Auto-levelled onto a common
# floor (the Lotus body underside) and reusing the Lotus wheel geometry with each
# car's own wheel meshes ('67 cars are dimensionally near-identical).  The player
# is always the Lotus 49. ----
const AIBASE = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/cars/cars67"
const BODY_FLOOR = Render.parts_bbox(CARP).ymin + BODY_OFF[2]   # world-Y the body underside reaches
aiwheels(lf,rf,lr,rr) = Tuple{Float32,Float32,Bool,Float32,String}[
    ( 1.05f0, 0.62f0, true,  0.31f0, lf), ( 1.05f0, -0.62f0, true,  0.31f0, rf),
    (-1.15f0, 0.66f0, false, 0.34f0, lr), (-1.15f0, -0.66f0, false, 0.34f0, rr)]
# (display name, cars67 folder, body .3do, wheel meshes) — order = grid order
const AISPECS = [
    ("Ferrari", "ferrari",  "ferrari.3do",  ("f222lf","f222rf","f444lr","f444rr")),
    ("Brabham", "brabham",  "brabham.3do",  ("brablf","brabrf","brablr","brabrr")),
    ("BRM",     "brm",      "brm.3do",      ("brm2lf","brm2rf","brm4lr","brm4rr")),
    ("Eagle",   "eagle",    "eagle.3do",    ("eotwlf","eotwrf","eotwlr","eotwrr")),
    ("Cooper",  "coventry", "coventry.3do", ("cooplf","cooprf","cooplr","cooprr")),  # GPL Cooper = the coventry chassis
]
AICARMODELS = Render.GPLCarModel[]
if !SKIDPAD && N_AI > 0
    for (nm, dir, body, w) in AISPECS[1:N_AI]
        print("  loading AI car: $nm … "); flush(stdout)
        push!(AICARMODELS, Render.load_gpl_car(nm, joinpath(AIBASE,dir), body, aiwheels(w...);
                              exclude=("ltraymap","lshad"), maxlat=0.9f0, body_floor=BODY_FLOOR))
        println("$(length(AICARMODELS[end].body)) parts")
    end
end
const PROJ = Render.perspective_revz(deg2rad(62f0), Float32(W/H), 0.35f0, 3000f0)  # reversed-Z: near-uniform depth precision → kills distant z-fight (signs on fences)

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; view::Int; auto::Bool; end
# shift mode: MANUAL by default — no auto-shift, no auto-clutch (you work the clutch to
# launch and to shift E/Q, or it bogs). ZAND_SHIFT=auto opts into the assists; G toggles in-app.
const CTL = Ctl(false,false,false,false,false, parse(Int, get(ENV,"JM_VIEW","1")), get(ENV,"ZAND_SHIFT","manual") == "auto" || IS_TRAIN)   # view 1=chase 0=cockpit; MANUAL by default; Training = auto-shift aid
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
    LASTGX = Ref(cs0.x); LASTGZ = Ref(cs0.z)   # last position INSIDE the world (terrain HAT) — for the boundary
    function groundz(x, z)                            # HAT elevation; off-surface holds last height
        SKIDPAD && return 0.0   # flat skidpad → no elevation
        h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf)
        h[3] ? (LASTZ[] = Float64(h[1]); ONTRACK[] = true) : (ONTRACK[] = false)
        LASTZ[]
    end
    y0spawn = groundz(cs0.x, cs0.z)                          # terrain height at spawn (3-D needs it; else the car spawns 100s of m off the ground and the contact explodes)
    cs = build_carX(x0=cs0.x, z0=cs0.z, θ0=cs0.θ, v0=0.0, y0=y0spawn)   # MTK car — standing start (planar or full-3D)
    # ---- AI opponents (race field): rail-followers on the centreline ----
    AILINE = (!SKIDPAD && N_AI > 0) ? RaceAI.build_line(ALIGNED, groundz) : nothing
    AICARS = AILINE === nothing ? RaceAI.AICar[] : RaceAI.init_cars(AILINE, N_AI; start_s = 30.0)
    AICHASSIS = AICARMODELS[1:length(AICARS)]   # grid slot i → AISPECS[i] (Ferrari, Brabham, …)
    AILINE !== nothing && println("  → AI grid: ", join((m.name for m in AICHASSIS), ", "))
    # ---- force feedback: self-aligning torque from the front-axle lateral force ----
    # force = SIGN·GAIN·(Fy_FL+Fy_FR), faded out near standstill.  The front Fy rises as the
    # tyres bite and DROPS past the grip peak → the wheel goes light = you feel understeer.
    ffb = (FFB_ON && !SMOKE) ? FFB.open_ffb() : nothing
    (ffb !== nothing && ffb.ok) ? println("  force feedback: ON  (", ffb.path, ", gain ", FFB_GAIN, ")") :
                                  println("  force feedback: off", FFB_ON ? " (no wheel found)" : " (JM_NOFFB)")
    spin = 0.0; last = time(); frames = 0; titleT = last
    ffb_f = 0.0                                       # low-pass-filtered FFB force (continuity across frames)
    fy_lp = 0.0                                        # low-pass front-axle force for FFB (de-spikes the coarse mesh)
    tc_hud = ntuple(_->(0.0,0.0,1.0), 4)              # smoothed traction-circle display (kills coarse-mesh flicker)
    v_prev = cs.v; pitch_dyn = 0.0; pitch_ter = 0.0    # dive/squat + terrain-slope pitch (smoothed)
    # lap timing + telemetry log
    lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = cs.laps; tsamp = 0; race_done = false
    fmt_lap(s) = (m=floor(Int,s/60); sec=s-60m; si=floor(Int,sec); ms=round(Int,(sec-si)*1000);
                  "$m:$(lpad(si,2,'0')).$(lpad(ms,3,'0'))")
    ibt_samples = IBTREC ? Dict{String,Float64}[] : nothing      # iRacing-format telemetry rows
    IBTREC && println("  recording iRacing .ibt telemetry (JM_IBT) — template: ", basename(IBTTMPL))
    telem = SMOKE ? nothing : open("zand_racer_$(round(Int,time())).txt", "w")
    telem !== nothing && write(telem,
        "# zand_racer telemetry — Lotus 49 @ Zandvoort\n# t\tlap\tlapdist\tkmh\tthr\tbrk\tsteer\tclu\tgear\trpm\tx\tz\tlat\talong\tontrack\n")
    println("\n  Drive:  W/S gas·brake   A/D steer   E/Q shift   C clutch   R respawn   V view   G auto⇄manual   M mute   Esc quit"); flush(stdout)
    println("  Manual mode (G) is realistic: hold the clutch (C / stick button) to shift.")
    println("  Lap times top-left: white = last, green = best.  Telemetry → ./zand_racer_*.txt")
    println("  (Logitech joystick works natively — push=throttle, pull=brake, roll=steer)\n")
    EngineAudio.start(ENG)   # start audio NOW (after the long track load) — starting it mid-load
                             # let the stream underflow on big tracks (Nürburgring) and go silent
    SMOKE || GLFW.ShowWindow(win)   # reveal the window now that loading is done (avoids the WM "Not Responding")
    while !GLFW.WindowShouldClose(win)
        GLFW.PollEvents()
        key(GLFW.KEY_ESCAPE) && break
        SMOKE && frames >= 40 && break
        now = time(); dt = clamp(now-last, 0.0, 0.05); last = now
        inp, rst = read_input()
        if rst; respawnX!(cs)
        else; step_carX!(cs, inp.throttle, inp.brake, inp.steer, dt > 1e-4 ? dt : 1/60;
                        clutch=inp.clutch, up=inp.shift_up, dn=inp.shift_down, manual=!inp.autoshift,
                        groundz=groundz)
            if !SKIDPAD     # track position + lap timing (Zandvoort only)
            hr = JuliaMotor.hat(TRKSURF, cs.x, cs.z)            # track-relative position
            if hr.found
                (cs.lapdist > 0.75*LAPLEN && hr.lapdist < 0.25*LAPLEN) && (cs.laps += 1)  # crossed S/F
                cs.lapdist = hr.lapdist; cs.lateral = hr.lateral; cs.along = hr.lapdist; cs.ontrack = hr.on_track
            else; cs.ontrack = false; end
            # E7 boundary = the WORLD edge (the terrain HAT): you can drive the road AND the grass
            # freely, but if you go off the HAT you've left the world → snap back to the last spot
            # inside it (a fence/hedge collision) and bleed speed.  (Based on the HAT, NOT the racing
            # line, so it never slows you on a wide road/grass — that was the Watkins Glen "molasses".)
            if ONTRACK[]; LASTGX[] = cs.x; LASTGZ[] = cs.z         # remember where we were inside the world
            else; containX!(cs, LASTGX[], LASTGZ[]; vdamp=0.4); end # off the terrain → held at the edge
            end
        end
        spin -= cs.v*dt/0.33
        ENG.rpm[] = isfinite(cs.rpm) ? cs.rpm : 700.0   # feed the engine-audio thread (never NaN)

        # ---- force feedback: aligning torque = front-axle Fy × pneumatic trail ----
        # Builds through turn-in, then LIGHTENS as the front slip angle grows and the
        # pneumatic trail collapses (you feel understeer). A mechanical-trail floor keeps
        # it from going dead; tanh soft-clips so it never hard-pins (always some headroom).
        if ffb !== nothing && ffb.ok
            tl  = telemetryX(cs)
            αf  = atan(tl.v + FFB_AF*tl.r, max(tl.u, 1.0)) - clamp(inp.steer, -1, 1)*FFB_DELTA
            trail = FFB_TFLOOR + (1 - FFB_TFLOOR) * clamp(1 - abs(αf)/FFB_ATRAIL, 0.0, 1.0)
            fy = cs.tc[1][2] + cs.tc[2][2]                     # front-axle lateral force (mg/4 units) — the ROAD feel
            fy_lp += (fy - fy_lp) * clamp(dt/0.05, 0.0, 1.0)   # de-spike the coarse GPL mesh (1-frame 11g jolts → smooth)
            fy = fy_lp * fy_lp*fy_lp / (fy_lp*fy_lp + FFB_SQ*FFB_SQ)   # squelch tyre-force noise (jostle), not the spring
            mz  = fy * trail
            spd = clamp(cs.v/2.5, 0.0, 1.0)                    # road feel fades in with speed
            spr = FFB_SPRING * clamp(inp.steer, -1, 1)         # self-centering spring ∝ wheel angle — ALWAYS present ⇒ no dead center
            target = tanh(FFB_SIGN * (FFB_GAIN * mz * spd + spr))
            ffb_f += (target - ffb_f) * clamp(dt/FFB_LP, 0.0, 1.0)   # 1st-order low-pass: smooth, continuous
            FFB.set_force!(ffb, ffb_f)
        end

        # ---- iRacing .ibt telemetry sample (one row per frame, ~60 Hz) ----
        if ibt_samples !== nothing && !rst
            tl = telemetryX(cs); δw = inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer)
            row = Dict{String,Float64}(
                "SessionTime"=>cs.t, "SessionTick"=>Float64(length(ibt_samples)+1),
                "IsOnTrack"=>cs.ontrack ? 1.0 : 0.0,
                "Speed"=>cs.v, "RPM"=>cs.rpm, "Gear"=>Float64(cs.gear),
                "Throttle"=>inp.throttle, "Brake"=>inp.brake, "Clutch"=>1.0-inp.clutch,
                "SteeringWheelAngle"=>δw,
                "Lap"=>Float64(cs.laps+1), "LapCompleted"=>Float64(cs.laps),
                "LapDist"=>cs.lapdist, "LapDistPct"=>(SKIDPAD ? 0.0 : (LAPLEN>0 ? cs.lapdist/LAPLEN : 0.0)),
                "Yaw"=>cs.θ, "YawRate"=>tl.r,
                "VelocityX"=>tl.u, "VelocityY"=>tl.v, "VelocityZ"=>0.0,
                # VertAccel is REAL in 3-D mode (the planar model has no vertical DOF → 1 g stub)
                "LongAccel"=>tl.ax, "LatAccel"=>tl.ay, "VertAccel"=>(CAR3D ? tl.vacc : 9.80665),
                "LFspeed"=>tl.ωf*0.30, "RFspeed"=>tl.ωf*0.30, "LRspeed"=>tl.ωr*0.33, "RRspeed"=>tl.ωr*0.33,
                "Alt"=>cs.y)
            if CAR3D                                   # real ride heights + body attitude (Flugplatz benchmark)
                row["LFrideHeight"]=tl.rh[1]; row["RFrideHeight"]=tl.rh[2]
                row["LRrideHeight"]=tl.rh[3]; row["RRrideHeight"]=tl.rh[4]
                row["Pitch"]=tl.pitch; row["Roll"]=tl.roll
            end
            push!(ibt_samples, row)
        end

        # ---- lap timing + telemetry log ----
        if cs.laps > prev_laps
            last_lap = cs.t - lap_t0; lap_t0 = cs.t
            (best_lap == 0.0 || last_lap < best_lap) && (best_lap = last_lap)
            telem !== nothing && (write(telem, "# LAP $(cs.laps)  $(fmt_lap(last_lap))\n"); flush(telem))
            println("  lap $(cs.laps): $(fmt_lap(last_lap))", last_lap==best_lap ? "  (best)" : "")
            if IS_RACE && cs.laps >= RACE_LAPS && !race_done    # race distance complete
                race_done = true
                println("\n  ═══════ RACE FINISHED — $RACE_LAPS laps ═══════")
                println("  best $(fmt_lap(best_lap))   last $(fmt_lap(last_lap))\n")
            end
        elseif cs.laps < prev_laps                 # respawn reset the lap counter
            lap_t0 = cs.t
        end
        prev_laps = cs.laps
        if telem !== nothing && (tsamp += 1) % 6 == 0
            write(telem, "$(round(cs.t,digits=2))\t$(cs.laps)\t$(round(cs.lapdist,digits=1))\t$(round(cs.v*3.6,digits=1))\t$(round(inp.throttle,digits=2))\t$(round(inp.brake,digits=2))\t$(round(inp.steer,digits=2))\t$(round(inp.clutch,digits=2))\t$(cs.gear)\t$(round(Int,cs.rpm))\t$(round(cs.x,digits=1))\t$(round(cs.z,digits=1))\t$(round(cs.lateral,digits=2))\t$(round(cs.along,digits=2))\t$(cs.ontrack ? 1 : 0)\n")
        end

        # ---- body pitch: accel→squat (nose up), brake→dive (nose down); + terrain slope ----
        acc = clamp((cs.v - v_prev)/max(dt,1e-3), -15.0, 15.0); v_prev = cs.v
        pitch_ter += (terrain_pitch(cs) - pitch_ter) * min(1.0, dt*6)
        rollv = 0.0
        if CAR3D
            pitch_dyn = cs.pitch - pitch_ter          # REAL body pitch (minus the slope carModel already applies)
            rollv = cs.roll                           # REAL body roll
        else
            pitch_dyn += (clamp(0.0016*acc, -0.013, 0.013) - pitch_dyn) * min(1.0, dt*3.5)  # faked, heavily damped
        end
        vp, eye = camera(cs, pitch_ter + pitch_dyn)
        carModel = Render.translate(Float32[cs.x, cs.y, -cs.z]) * Render.roty(Float32(cs.θ)) *
                   Render.rotz(Float32(pitch_ter))                       # whole car follows the hill
        bodyModel = carModel * Render.rotz(Float32(pitch_dyn)) * Render.rotx(Float32(rollv)) * Render.translate(BODY_OFF)  # body dives/squats + rolls (3-D)
        δ = Float32(inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer))
        wheelmat(wx,wz,steer,r) = carModel * Render.translate(Float32[wx, r, wz]) *
                     (steer ? Render.roty(δ) : Render.ident()) * Render.rotz(Float32(spin))
        # advance + place the AI field (rail-followers on the centreline)
        ai_poses = AILINE === nothing ? NTuple{4,Float64}[] :
                   [RaceAI.step!(c, AILINE, dt > 1e-4 ? dt : 1/60) for c in AICARS]
        aiCar(p)  = Render.translate(Float32[p[1], p[2], -p[3]]) * Render.roty(Float32(p[4]))
        aiBody(p, cm) = aiCar(p) * Render.translate(collect(cm.body_off))
        aiWheel(p,wx,wz,r) = aiCar(p) * Render.translate(Float32[wx, r, wz]) * Render.rotz(Float32(spin))
        # ---- shadow pass: scene depth from the sun, light box on the car ----
        lightVP = Render.light_vp(Float32[cs.x, cs.y, -cs.z], LIGHTDIR)
        Render.shadow_pass(depthprog, shadowfbo, lightVP) do dp
            for it in trackItems; Render.draw_depth(dp, it, Render.ident()); end
            for it in carItems; Render.draw_depth(dp, it, bodyModel); end
            for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw_depth(dp, it, wheelmat(wx,wz,steer,r)); end
            for (p, cm) in zip(ai_poses, AICHASSIS)            # AI cars cast shadows too
                for it in cm.body; Render.draw_depth(dp, it, aiBody(p, cm)); end
                for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw_depth(dp, it, aiWheel(p,wx,wz,r)); end
            end
        end
        # ---- main pass (reversed-Z: [0,1] clip, near→1/far→0, GEQUAL, clear 0) ----
        glViewport(0,0,W,H)
        glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE); glDepthFunc(GL_GEQUAL); glClearDepth(0.0)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        Render.draw_sky(skyprog, skyvao, inv(vp), eye, LIGHTDIR;
                        cloud = GRADE.cloud, zenith = GRADE.zenith, horizon = GRADE.horizon)
        Render.set_scene_uniforms(prog, eye; fognear=400f0, fogfar=2800f0,
                                  fogcol=GRADE.horizon, suncol=GRADE.suncol, ambsky=GRADE.ambsky, sat=GRADE.sat)
        Render.bind_shadow(prog, shadowtex, lightVP)
        HORIZON_RING === nothing || Render.draw_horizon(prog, HORIZON_RING, vp, eye; tint=GRADE.ringtint)   # GPL horizon ring backdrop
        for it in trackItems; Render.draw(prog, it, vp, Render.ident(); bright=0.55); end
        glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 1)   # un-mirror far-side sign backs (objects only)
        for (items,mat,grz,opos) in OBJECTS                       # trackside objects (trees graze-fade)
            (eye[1]-opos[1])^2+(eye[2]-opos[2])^2+(eye[3]-opos[3])^2 > OBJ_CULL2 && continue   # distance cull
            for it in items; Render.draw(prog, it, vp, mat; bright=0.85, graze=grz); end
        end
        glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 0)
        for (it,pos,w,h) in BILLBOARDS                            # trees/sprites
            (eye[1]-pos[1])^2+(eye[2]-pos[2])^2+(eye[3]-pos[3])^2 > BB_CULL2 && continue       # distance cull
            Render.draw(prog, it, vp, Render.billboard_model(pos,w,h,eye); bright=1.05)
        end
        # ambfill lifts the self-shadowed cockpit interior out of black (GPL pre-lights it
        # evenly); lower spec so the cockpit floor stops reading as a "shining rug".
        for it in carItems; Render.draw(prog, it, vp, bodyModel; bright=1.25, spec=0.10, ambfill=0.62); end   # lift the self-shadowed cockpit tub out of black (GPL pre-lights it to grey)
        for (p, cm) in zip(ai_poses, AICHASSIS)                 # AI grid (Ferrari/Brabham/BRM/Eagle/Cooper)
            for it in cm.body; Render.draw(prog, it, vp, aiBody(p, cm); bright=1.25, spec=0.10, ambfill=0.62); end
            for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw(prog, it, vp, aiWheel(p,wx,wz,r)); end
        end
        for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw(prog, it, vp, wheelmat(wx,wz,steer,r)); end
        # steering wheel — spin about its column axis with steering input
        swModel = bodyModel * Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(inp.steer*2.5)) * Render.translate(-SWCENTER)
        for it in swItems; Render.draw(prog, it, vp, swModel; bright=1.2, ambfill=0.34); end
        α_tc = clamp(dt/0.10, 0.0, 1.0)              # smooth the traction-circle display (coarse-mesh Fz spikes → no flicker)
        tc_hud = ntuple(i -> ntuple(j -> tc_hud[i][j] + (cs.tc[i][j]-tc_hud[i][j])*α_tc, 3), 4)
        Render.hud_draw(hudprog, hudvao, hudvbo,
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, 9500.0, inp.throttle, inp.brake, inp.clutch, tc_hud;
                               lastlap=(SMOKE ? 94.3 : last_lap), bestlap=(SMOKE ? 92.1 : best_lap), manual=!CTL.auto), W, H)
        GLFW.SwapBuffers(win)
        if SMOKE && frames == 38                   # headless self-test: dump one frame
            buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
            open("/tmp/zand_hud.ppm","w") do io; write(io,"P6\n$W $H\n255\n")
                for y in H:-1:1, x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
        end

        frames += 1
        if now - titleT > 0.25
            GLFW.SetWindowTitle(win, "Julia Racer — $(uppercasefirst(TRACKSEL)) — $(round(Int,cs.v*3.6)) km/h — gear $(cs.gear == 0 ? "N" : string(cs.gear)) ($(CTL.auto ? "AUTO" : "MANUAL")) — $(round(Int,cs.rpm)) rpm" *
                (IS_RACE ? (race_done ? "  ✦ FINISHED" : "  — lap $(min(cs.laps+1,RACE_LAPS))/$RACE_LAPS") :
                           "  [$(uppercasefirst(MODE))]") *
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
    ffb !== nothing && FFB.close_ffb(ffb)
    EngineAudio.stop!(ENG)
    GLFW.Terminate()
    println("bye")
end
main()
