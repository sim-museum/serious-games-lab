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
# E11: AI speed as a percentage — 100 % = the GPL AI car laptime for the track.
const AI_PCT    = clamp(tryparse(Float64, get(ENV, "JM_AI_PCT", "100")) |> x -> x === nothing ? 100.0 : x, 30.0, 200.0)
# AI never run away from the human: each is capped to AI_REL × the player's current speed
# (default 1.10 = at most 10 % faster) so it stays a close, raceable field.
const AI_REL    = clamp(tryparse(Float64, get(ENV, "JM_AI_REL", "1.10")) |> x -> x === nothing ? 1.10 : x, 1.0, 4.0)
# GC: the AI run the JM 2-D PHYSICS model (real grip/inertia) steered by a rail controller,
# by default.  JM_AI_KINEMATIC falls back to the (also-good) kinematic rail field.
const AI_PHYSICS = !haskey(ENV, "JM_AI_KINEMATIC")
# GPL '67 AI reference laptimes (s) — the "100 %" anchor.  Sourced from GPL AI/hotlap
# pace per circuit; tunable per car/setup via JM_AI_REFLAP (overrides the table).  At
# AI_PCT=100 the field is paced to hit exactly this laptime regardless of the rail
# follower's own natural pace (see RaceAI.natural_laptime).
const REF_LAP = Dict("zandvoort"=>87.0, "nurburgring"=>500.0, "watglen"=>67.0,
                     "monza"=>105.0, "spa"=>213.0, "skidpad"=>30.0)
const AI_REFLAP = (v = tryparse(Float64, get(ENV, "JM_AI_REFLAP", ""));
                   v === nothing ? get(REF_LAP, TRACKSEL, 90.0) : v)
println("  → mode: ", uppercasefirst(MODE),
        IS_RACE ? "  ($RACE_LAPS laps" * (N_AI>0 ? ", $N_AI AI cars)" : ")") : "")
# ---- E10: fuel.  The Lotus is fuelled to finish the race + a margin of ~5 laps. ----
# GPL Ford-DFV-ish burn (L/km); the tank is sized to (laps+margin)·burn so the player
# always has enough to finish with a cushion.  Distance-based so the laps-of-fuel figure
# is honest.  Practice/Training get a generous tank; the skidpad has no laps → no fuel.
const FUEL_LPK    = clamp(tryparse(Float64, get(ENV,"JM_FUEL_LPK","0.55")) |> x-> x===nothing ? 0.55 : x, 0.05, 5.0)
const FUEL_MARGIN = max(0, tryparse(Int, get(ENV,"JM_FUEL_MARGIN","5")) |> x-> x===nothing ? 5 : x)

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
# ---- E7 boundary audit (JM_BOUNDARY_TEST): confirm the terrain HAT BOUNDS the world ----
# The game holds the car at the last in-world spot whenever it steps off the HAT, so the
# world is "sealed" iff (a) the HAT has no holes on the racing line and (b) there is a
# finite HAT edge to either side everywhere (so going off-track always meets a boundary).
function boundary_audit()
    println("\n  ═══ E7 BOUNDARY AUDIT — $(uppercasefirst(TRACKSEL)) ═══")
    onhat(x,z) = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf)[3]
    n = length(ALIGNED); step = max(1, n ÷ 120); ks = 1:step:n
    CAP = 1500.0                                    # the HAT is a finite mesh → there IS an edge; this just bounds the search
    holes = Int[]; edges = Float64[]; wide = 0
    for k in ks
        x,z = ALIGNED[k]; x2,z2 = ALIGNED[k % n + 1]
        tx,tz = x2-x, z2-z; tl = hypot(tx,tz); tl < 1e-6 && continue
        px,pz = -tz/tl, tx/tl                       # left-perpendicular unit
        onhat(x,z) || push!(holes, k)               # racing-line hole?
        for sgn in (1.0, -1.0)
            d = 0.0; hit = false
            while d < CAP
                d += 1.0
                if !onhat(x + sgn*px*d, z + sgn*pz*d); push!(edges, d); hit = true; break; end
            end
            hit || (wide += 1)                       # run-off wider than CAP (still finite/bounded, just big)
        end
    end
    # measure each on-line hole's length along the centreline (1 m march) — the FENCE_GRACE
    # must exceed it for the car to cross without a false containment.
    holelen(k) = begin
        x,z = ALIGNED[k]; x2,z2 = ALIGNED[k % n + 1]
        tx,tz = x2-x, z2-z; tl = hypot(tx,tz); tl < 1e-6 && return 0.0
        tx,tz = tx/tl, tz/tl; fwd = 0.0; bwd = 0.0
        while fwd < 300 && !onhat(x+tx*fwd, z+tz*fwd); fwd += 1.0; end
        while bwd < 300 && !onhat(x-tx*bwd, z-tz*bwd); bwd += 1.0; end
        fwd + bwd
    end
    println("  samples: $(length(ks))   on-line holes: $(length(holes))",
            isempty(holes) ? "" : "  at line-fractions $(round.([h/n for h in holes],digits=2)) lengths $(round.(holelen.(holes),digits=0)) m")
    isempty(edges) || println("  lateral world-edge: min $(round(minimum(edges),digits=1)) m  ",
            "median $(round(sort(edges)[max(1,end÷2)],digits=1)) m  max $(round(maximum(edges),digits=1)) m  ($(length(edges)) probes)")
    println("  sides whose run-off exceeds $(round(Int,CAP)) m (still bounded — finite mesh): $wide")
    # Epic 2 (no driving off the world) is satisfied iff the HAT has no on-line holes — the
    # finite mesh guarantees containment everywhere off-line regardless of run-off width.
    println(isempty(holes) ?
        "  ✓ PASS — world is sealed (finite HAT, no on-line holes): the car cannot leave the world." :
        "  ⚠ on-line holes (false containment risk on the racing line) — see fractions above.")
end
if haskey(ENV, "JM_BOUNDARY_TEST") && !SKIDPAD
    boundary_audit(); exit(0)
end
# ---- GPL Lotus 49 (replaces the rFactor Vanwall; the authentic GPL-pivot car) ----
const LOTDIR = "/home/g/sgl/THU/WP/drive_c/Sierra/GPL/cars/cars67/lotus"
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOT3DO = joinpath(LOTDIR,"lotus.3do")
# GPL-fidelity cockpit: KEEP windlot (the tan leather scuttle — the defining GPL cockpit
# element; the earlier "rug" was the untextured yellow floor, which cockpit_clean drops, not
# windlot which is properly tan-textured).  Still drop hands/dup-mirror/teal front-susp/tan
# floor + clip the splayed-rear chrome.
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=("ltraymap","lshad","lohand","lotarms","lotmirt",Render.STEER_TEX...), exclude_groups=(6600,3560), cockpit_clean=true, maxlat=0.85f0)
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
bumpX!(c, dvx, dvz, dr)    = CAR3D ? DriveRT3D.bump3d!(c, dvx, dvz, dr)    : DriveRT.bump!(c, dvx, dvz, dr)   # GD: collision impulse
const FENCE = parse(Float64, get(ENV, "JM_FENCE", "13.0"))   # E7: track boundary (m from centreline) — you can't leave the world
const FENCE_GRACE = parse(Float64, get(ENV, "JM_FENCE_GRACE", "2.5"))   # off-HAT distance before the trackside collision fires (tolerates sub-car mesh cracks; small so the fence feels like a wall)
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

# ---- terrain ROLL: cross-slope under the car (left vs right), so a 3-D car on a banked
# embankment LISTS with the surface (its up-normal stays perpendicular to the ground) ----
function terrain_roll(cs)
    SKIDPAD && return 0.0
    L = 1.3; lx = -sin(cs.θ); lz = cos(cs.θ)               # car's LEFT direction (perp to heading)
    hl = JuliaMotor.hat3d(TERRAIN, cs.x+lx*L, cs.z+lz*L; ref=Inf)
    hr = JuliaMotor.hat3d(TERRAIN, cs.x-lx*L, cs.z-lz*L; ref=Inf)
    (hl[3] && hr[3]) ? atan(hl[1]-hr[1], 2L) : 0.0         # left higher → list right
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
    OFFDIST = Ref(0.0)                          # distance travelled off the HAT (grace before containing)
    function groundz(x, z)                            # HAT elevation; off-surface holds last height
        SKIDPAD && return 0.0   # flat skidpad → no elevation
        h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf)
        h[3] ? (LASTZ[] = Float64(h[1]); ONTRACK[] = true) : (ONTRACK[] = false)
        LASTZ[]
    end
    y0spawn = groundz(cs0.x, cs0.z)                          # terrain height at spawn (3-D needs it; else the car spawns 100s of m off the ground and the contact explodes)
    # robust spawn heading: the single S/F seam segment can give a sideways tangent, so
    # take the heading from a few points DOWN the centreline (the real start-straight direction).
    θ0spawn = if SKIDPAD
        cs0.θ
    else
        look = min(4, length(ALIGNED)-1)
        atan(ALIGNED[1+look][2]-ALIGNED[1][2], ALIGNED[1+look][1]-ALIGNED[1][1])
    end
    cs = build_carX(x0=cs0.x, z0=cs0.z, θ0=θ0spawn, v0=0.0, y0=y0spawn)   # MTK car — standing start (planar or full-3D)
    # ---- AI opponents (race field): rail-followers on the centreline ----
    # CLINE = the centreline, built ALWAYS (off-skidpad) so the PLAYER's lap counting can use a
    # robust projection wrap instead of the ribbon lapdist (the ribbon has a seam at S/F that
    # broke the wrap → laps never counted → no finish).  AILINE = CLINE when there's a field.
    CLINE  = !SKIDPAD ? RaceAI.build_line(ALIGNED, groundz) : nothing
    AILINE = (CLINE !== nothing && N_AI > 0) ? CLINE : nothing
    AICARS = AILINE === nothing ? RaceAI.AICar[] : RaceAI.init_cars(AILINE, N_AI; start_s = 30.0)
    AICHASSIS = AICARMODELS[1:length(AICARS)]   # grid slot i → AISPECS[i] (Ferrari, Brabham, …)
    # GC: build the AI as PHYSICS cars (one shared compile) placed on the grid; AICARS stays the
    # rail "brain" (s/lane/v/tlane/lap), updated each frame from the physics by projection.
    AIPHYS = DriveRT.Car[]
    if AI_PHYSICS && AILINE !== nothing
        print("  building $(length(AICARS)) physics AI (shared JM 2-D model)… "); flush(stdout)
        poses = [(p = RaceAI.pose_at(AILINE, c.s, c.lane); (p[1], p[3], p[4], 0.0)) for c in AICARS]
        AIPHYS = DriveRT.build_cars(poses)
        println("done")
    end
    # E11: pace the field.  Target laptime = refLap × (100/pct); the speed scale that
    # hits it = naturalLap / targetLap (lap time ∝ 1/speed).  Clamped to a sane band.
    AI_T0    = AILINE === nothing ? 0.0 : RaceAI.natural_laptime(AILINE)
    AI_TGT   = AI_REFLAP * 100.0 / AI_PCT
    AI_SCALE = AILINE === nothing ? 1.0 : clamp(AI_T0 / max(AI_TGT, 1.0), 0.4, 2.2)
    if AILINE !== nothing
        println("  → AI grid: ", join((m.name for m in AICHASSIS), ", "))
        println("  → AI pace: ", round(Int,AI_PCT), "% of GPL (ref ", round(AI_REFLAP,digits=1),
                "s → target ", round(AI_TGT,digits=1), "s; rail ", round(AI_T0,digits=1),
                "s, scale ", round(AI_SCALE,digits=2), ")")
    end
    # JM_AI_TEST: drive the physics field on the REAL loaded track (no player) → laps/spins, exit.
    if AI_PHYSICS && haskey(ENV, "JM_AI_TEST") && !isempty(AIPHYS)
        for (i,pc) in enumerate(AIPHYS); p = RaceAI.pose_at(AILINE, AICARS[i].s, AICARS[i].lane); DriveRT.place!(pc, p[1], p[3], p[4]; v=12.0); end
        N=length(AIPHYS); maxr=0.0; spins=0; aidist=zeros(N); stuck=zeros(Int,N); scon=zeros(Int,N); lastx=[pc.x for pc in AIPHYS]; lastz=[pc.z for pc in AIPHYS]
        nstep=5400   # 90 s
        for _ in 1:nstep
            for (i,pc) in enumerate(AIPHYS)
                s,lat = RaceAI.project(AILINE, pc.x, pc.z); AICARS[i].s=s; AICARS[i].lane=lat; AICARS[i].v=pc.v
                aidist[i] += hypot(pc.x-lastx[i], pc.z-lastz[i]); lastx[i]=pc.x; lastz[i]=pc.z
                if pc.v < 1.4 || abs(lat) > 14.0      # mirror the live recovery: stalled OR off-track
                    stuck[i]+=1; scon[i]+=1
                    if scon[i] > (abs(lat)>14.0 ? 24 : 100); rp=RaceAI.pose_at(AILINE, s+10.0, 0.0); DriveRT.place!(pc, rp[1], rp[3], rp[4]; v=max(8.0,pc.v*0.7)); scon[i]=0; end
                else; scon[i]=0; end
            end
            vts = RaceAI.plan!(AICARS, AILINE; scale=AI_SCALE, player=(1e7,0.0,40.0), rel=AI_REL, amax=8.0)
            for (i,pc) in enumerate(AIPHYS)
                r = DriveRT.yawrate(pc); maxr = max(maxr, abs(r)); abs(r) > 2.5 && (spins += 1)
                thr,brk,st = RaceAI.controller(AILINE, AICARS[i].s, AICARS[i].lane, AICARS[i].tlane, vts[i], pc.x, pc.z, pc.θ, pc.v, r)
                DriveRT.step_car!(pc, thr, brk, st, 1/60; manual=false)
            end
        end
        avgkmh = round.(Int, aidist ./ 90 .* 3.6)
        println("  AI self-test on $(TRACKSEL) (90s): dist=", round.(Int,aidist), "m  avg_kmh=$avgkmh  max_yaw=$(round(maxr,digits=2))  spins=$spins  stuck_frames=$stuck")
        println(spins < 30 && minimum(aidist) > 800 && maximum(stuck) < 200 ? "  ✓ physics AI lap the real track cleanly" : "  ⚠ AI struggle here — tune controller")
        exit(0)
    end
    # ---- force feedback: self-aligning torque from the front-axle lateral force ----
    # force = SIGN·GAIN·(Fy_FL+Fy_FR), faded out near standstill.  The front Fy rises as the
    # tyres bite and DROPS past the grip peak → the wheel goes light = you feel understeer.
    ffb = (FFB_ON && !SMOKE) ? FFB.open_ffb() : nothing
    (ffb !== nothing && ffb.ok) ? println("  force feedback: ON  (", ffb.path, ", gain ", FFB_GAIN, ")") :
                                  println("  force feedback: off", FFB_ON ? " (no wheel found)" : " (JM_NOFFB)")
    spin = 0.0; last = time(); frames = 0; titleT = last
    ai_stuck = zeros(Int, length(AIPHYS))     # GC: per-AI stalled-frame counter (stuck-recovery)
    ffb_f = 0.0                                       # low-pass-filtered FFB force (continuity across frames)
    fy_lp = 0.0                                        # low-pass front-axle force for FFB (de-spikes the coarse mesh)
    tc_hud = ntuple(_->(0.0,0.0,1.0), 4)              # smoothed traction-circle display (kills coarse-mesh flicker)
    v_prev = cs.v; pitch_dyn = 0.0; pitch_ter = 0.0; roll_ter = 0.0    # dive/squat + terrain-slope pitch + cross-slope roll (smoothed)
    # lap timing + telemetry log
    lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = cs.laps; tsamp = 0; race_done = false; enterPrev = false
    player_s_prev = CLINE === nothing ? 0.0 : RaceAI.project(CLINE, cs.x, cs.z)[1]   # for robust lap-wrap detection
    fmt_lap(s) = (m=floor(Int,s/60); sec=s-60m; si=floor(Int,sec); ms=round(Int,(sec-si)*1000);
                  "$m:$(lpad(si,2,'0')).$(lpad(ms,3,'0'))")
    # ---- E9: qualifying → grid order ----
    # One qualifying lap sets the grid: the field is arranged around the player by qual
    # time (faster qualifiers start ahead on track, slower behind).  Skipped for solo
    # races, the skidpad, JM_NOQUAL, and headless smoke (which can't drive a lap).
    DO_QUAL  = IS_RACE && N_AI > 0 && !SKIDPAD && !haskey(ENV,"JM_NOQUAL") && !SMOKE
    phase    = Ref(DO_QUAL ? :qual : :race)
    player_grid = Ref(0); player_finpos = Ref(0)
    # Standing start: in a race the AI sit on the grid until YOU floor the throttle, then
    # the whole field launches together — so you never miss the start by looking away.
    HOLD_START = IS_RACE && N_AI > 0 && !SKIDPAD && !SMOKE
    race_go    = Ref(!HOLD_START)
    # AI reference qual times: the paced target + a small per-car spread so the grid lines
    # up in chassis order (~0.35 s/slot at 87 s) rather than a dead heat.
    ai_quals = [AI_TGT * (1 + 0.004*(i-1)) for i in 1:length(AICARS)]
    ROW = 9.0; GRID_LANE = 2.2          # grid row gap (m) + 2-wide lane offset
    function form_grid!(qtime)
        order = RaceAI.grid_order(qtime, ai_quals)        # pole-first entrant ids (0 = player)
        prank = findfirst(==(0), order)
        for (i, c) in enumerate(AICARS)
            r = findfirst(==(i), order)
            c.s = mod(-(r - prank)*ROW, AILINE.total)      # ahead (+s) if it out-qualified the player
            c.v = 0.0; c.lap = 0
            c.lane = isodd(r) ? GRID_LANE : -GRID_LANE; c.tlane = c.lane
            AI_PHYSICS && (gp = RaceAI.pose_at(AILINE, c.s, c.lane); DriveRT.place!(AIPHYS[i], gp[1], gp[3], gp[4]; v=0.0))
        end
        println("\n  ═══ GRID (from qualifying) ═══")
        for (p, id) in enumerate(order)
            println("   P$p  ", id==0 ? "You — $(fmt_lap(qtime))" : AICHASSIS[id].name)
        end
        println("  → You qualified P$prank of $(length(order))\n"); flush(stdout)
        prank
    end
    DO_QUAL && println("\n  QUALIFYING — drive a lap then press ENTER to start the race (it also\n  auto-starts if the start/finish line registers a clean lap).  ENTER = go racing.")
    # ---- E10: fuel load ----  tank sized so the player can finish + ~FUEL_MARGIN laps.
    FUEL_ON   = !SKIDPAD
    burn_lap  = FUEL_ON ? FUEL_LPK * LAPLEN/1000 : 0.0          # litres per lap (distance-based)
    fuel_laps = IS_RACE ? (RACE_LAPS + FUEL_MARGIN) : 40        # practice/training: a generous tank
    fuel      = Ref(FUEL_ON ? burn_lap * fuel_laps : 0.0)
    if FUEL_ON
        println("  → fuel: ", round(fuel[],digits=1), " L = ", fuel_laps, " laps",
                IS_RACE ? " ($RACE_LAPS race + $FUEL_MARGIN margin)" : "",
                "  (", round(burn_lap,digits=2), " L/lap)")
    end
    # ---- live race standings: rank everyone by race progress (laps + lap fraction) ----
    function standings()
        pp = cs.laps + (FUEL_ON && LAPLEN > 0 ? clamp(cs.lapdist/LAPLEN, 0.0, 1.0) : 0.0)
        entries = Tuple{Int,Float64}[(0, pp)]
        for (i,c) in enumerate(AICARS)
            push!(entries, (i, c.lap + (AILINE === nothing ? 0.0 : c.s/AILINE.total)))
        end
        sort!(entries, by = e -> -e[2])                # most progress = P1
        entries
    end
    ent_name(id) = id == 0 ? "You" : AICHASSIS[id].name
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
        # E9: end qualifying on ENTER (or it auto-ends on a clean lap).  This guarantees you
        # can always start the race even if the S/F line doesn't register the lap (the ribbon
        # can have a seam at start/finish).  Your qual time = best clean lap, else estimated
        # from how far round you got (so a near-complete lap still earns a fair grid slot).
        enterNow = key(GLFW.KEY_ENTER) || key(GLFW.KEY_KP_ENTER)
        if phase[] == :qual && enterNow && !enterPrev
            qt = best_lap > 0.0 ? best_lap :
                 (cs.lapdist > 0.30*LAPLEN ? (cs.t - lap_t0) * LAPLEN / max(cs.lapdist, 1.0) : Inf)
            player_grid[] = form_grid!(qt)
            phase[] = :race
            cs.laps = 0; last_lap = 0.0; best_lap = 0.0; race_done = false; lap_t0 = cs.t
        end
        enterPrev = enterNow
        # green light: the field launches the moment you ask for throttle (standing start)
        if HOLD_START && !race_go[] && phase[] == :race && inp.throttle > 0.15
            race_go[] = true; lap_t0 = cs.t          # start the clock at the launch
        end
        # E10: burn fuel by distance (only once racing); a dry tank starves the engine.
        if FUEL_ON && phase[] == :race && !rst
            fuel[] = max(0.0, fuel[] - FUEL_LPK * cs.v * (dt > 1e-4 ? dt : 1/60) / 1000)
            fuel[] <= 0 && (inp = DriveInput(throttle=0.0, brake=inp.brake, steer=inp.steer,
                            clutch=inp.clutch, shift_up=inp.shift_up, shift_down=inp.shift_down, autoshift=inp.autoshift))
        end
        rst && FUEL_ON && (fuel[] = burn_lap * fuel_laps)        # respawn refuels
        if rst; respawnX!(cs)
        else; step_carX!(cs, inp.throttle, inp.brake, inp.steer, dt > 1e-4 ? dt : 1/60;
                        clutch=inp.clutch, up=inp.shift_up, dn=inp.shift_down, manual=!inp.autoshift,
                        groundz=groundz)
            if !SKIDPAD     # track position + lap timing
            hr = JuliaMotor.hat(TRKSURF, cs.x, cs.z)            # track-relative position (for lapdist/lateral HUD)
            if hr.found
                cs.lapdist = hr.lapdist; cs.lateral = hr.lateral; cs.along = hr.lapdist; cs.ontrack = hr.on_track
            else; cs.ontrack = false; end
            # ROBUST lap counting: wrap of the centreline-projection arc-length (the ribbon lapdist
            # has a seam at S/F that never wrapped → laps stayed 0 → no finish).  Same method the AI use.
            if CLINE !== nothing
                ps = RaceAI.project(CLINE, cs.x, cs.z)[1]
                (player_s_prev > CLINE.total*0.7 && ps < CLINE.total*0.3 && race_go[]) && (cs.laps += 1)
                player_s_prev = ps
            end
            # E7 boundary = the WORLD edge (the terrain HAT): you can drive the road AND the grass
            # freely, but if you go off the HAT you've left the world → snap back to the last spot
            # inside it (a fence/hedge collision) and bleed speed.  (Based on the HAT, NOT the racing
            # line, so it never slows you on a wide road/grass — that was the Watkins Glen "molasses".)
            # A short off-HAT distance GRACE (JM_FENCE_GRACE m) lets the car cross narrow mesh seams
            # / bridge gaps in the HAT (e.g. 4 on the Nürburgring racing line) without a false
            # containment; a genuine excursion exceeds it within a few metres and is held at the edge.
            if ONTRACK[]; LASTGX[] = cs.x; LASTGZ[] = cs.z; OFFDIST[] = 0.0   # inside the world
            else
                OFFDIST[] += cs.v * (dt > 1e-4 ? dt : 1/60)
                if OFFDIST[] > FENCE_GRACE       # G5: hit the trackside boundary → a PHYSICAL collision
                    nwx = LASTGX[]-cs.x; nwz = LASTGZ[]-cs.z; nl = hypot(nwx,nwz)   # wall normal: back into the world
                    nl < 1e-3 && (nwx = cos(cs.θ+π); nwz = sin(cs.θ+π); nl = 1.0)
                    nwx /= nl; nwz /= nl
                    pvx = cs.v*cos(cs.θ); pvz = cs.v*sin(cs.θ)
                    vn = pvx*nwx + pvz*nwz                       # inward-normal speed (<0 = leaving the world)
                    tx = -nwz; tz = nwx; vt = pvx*tx + pvz*tz    # tangent (along the fence)
                    e = 0.30; fric = 0.55                        # restitution + fence grab (scrub tangential)
                    dvn = (vn < 0 ? -e*vn : 0.0) - vn; dvt = -fric*vt
                    containX!(cs, LASTGX[], LASTGZ[]; vdamp=1.0)  # shove back to the edge (position), keep velocity
                    bumpX!(cs, dvn*nwx+dvt*tx, dvn*nwz+dvt*tz, clamp(sign(vt)*abs(vn)*0.05, -1.2, 1.2))  # bounce + scrub + glance-spin
                    OFFDIST[] = 0.0
                end
            end
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
            if phase[] == :qual                              # qualifying lap done → form the grid, start the race
                player_grid[] = form_grid!(last_lap)
                phase[] = :race
                cs.laps = 0; last_lap = 0.0; best_lap = 0.0; race_done = false   # race starts fresh
            else
            (best_lap == 0.0 || last_lap < best_lap) && (best_lap = last_lap)
            telem !== nothing && (write(telem, "# LAP $(cs.laps)  $(fmt_lap(last_lap))\n"); flush(telem))
            println("  lap $(cs.laps): $(fmt_lap(last_lap))", last_lap==best_lap ? "  (best)" : "")
            if IS_RACE && cs.laps >= RACE_LAPS && !race_done    # race distance complete
                race_done = true
                println("\n  ═══════ RACE FINISHED — $RACE_LAPS laps ═══════")
                if !isempty(AICARS)
                    fin = standings()
                    player_finpos[] = findfirst(e -> e[1] == 0, fin)
                    println("\n  ══════ YOU FINISHED — P$(player_finpos[]) of $(length(fin)) ══════")
                    println("  started P$(player_grid[])   best lap $(fmt_lap(best_lap))   total $(fmt_lap(cs.t))")
                    println("  ── final classification ──")
                    for (p, (id, _)) in enumerate(fin)
                        println("   P$p  ", ent_name(id), id==0 ? "  ← YOU (best $(fmt_lap(best_lap)))" : "")
                    end
                else
                    player_finpos[] = 1
                    println("  YOU FINISHED   best $(fmt_lap(best_lap))   total $(fmt_lap(cs.t))")
                end
                println()
            end
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
        roll_ter  += (terrain_roll(cs)  - roll_ter)  * min(1.0, dt*6)   # car lists with the cross-slope (3-D)
        rollv = 0.0
        if CAR3D
            pitch_dyn = cs.pitch - pitch_ter          # REAL body pitch (minus the slope carModel already applies)
            rollv = cs.roll                           # REAL body roll
        else
            pitch_dyn += (clamp(0.0016*acc, -0.013, 0.013) - pitch_dyn) * min(1.0, dt*3.5)  # faked, heavily damped
        end
        vp, eye = camera(cs, pitch_ter + pitch_dyn)
        carModel = Render.translate(Float32[cs.x, cs.y, -cs.z]) * Render.roty(Float32(cs.θ)) *
                   Render.rotz(Float32(pitch_ter)) * Render.rotx(Float32(roll_ter))   # whole car follows the hill (pitch + cross-slope roll)
        bodyModel = carModel * Render.rotz(Float32(pitch_dyn)) * Render.rotx(Float32(rollv)) * Render.translate(BODY_OFF)  # body dives/squats + rolls (3-D)
        δ = Float32(inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer))
        wheelmat(wx,wz,steer,r) = carModel * Render.translate(Float32[wx, r, wz]) *
                     (steer ? Render.roty(δ) : Render.ident()) * Render.rotz(Float32(spin))
        # advance + place the AI field (rail-followers on the centreline)
        ai_hit = Ref(false); ddt = dt > 1e-4 ? dt : 1/60
        ai_poses = if AILINE === nothing || phase[] != :race      # AI hidden until the race starts (after qualifying)
            NTuple{4,Float64}[]
        elseif !race_go[]                                         # standing on the grid (not yet launched)
            AI_PHYSICS ? [(pc.x, groundz(pc.x, pc.z), pc.z, pc.θ) for pc in AIPHYS] :
                         [RaceAI.pose_at(AILINE, c.s, c.lane) for c in AICARS]
        elseif AI_PHYSICS
            # GC HYBRID: project each physics car onto the line → update the brain → the controller
            # steers it toward its rail at the planned speed → step the JM 2-D physics.
            for (i, pc) in enumerate(AIPHYS)
                s, lat = RaceAI.project(AILINE, pc.x, pc.z); prevs = AICARS[i].s
                AICARS[i].s = s; AICARS[i].lane = lat; AICARS[i].v = pc.v
                (prevs > AILINE.total*0.7 && s < AILINE.total*0.3) && (AICARS[i].lap += 1)
                # recovery: a stalled AI, or one that's run WAY off the racing line (off track at a
                # corner), is snapped back onto the line — so an AI can never drive off and vanish.
                off = pc.v < 1.4 || abs(lat) > 14.0
                if off
                    ai_stuck[i] += 1
                    lim = abs(lat) > 14.0 ? 24 : 100      # off-track: recover within ~0.4 s; stalled: ~1.7 s
                    if ai_stuck[i] > lim
                        rp = RaceAI.pose_at(AILINE, s + 10.0, 0.0); DriveRT.place!(pc, rp[1], rp[3], rp[4]; v = max(8.0, pc.v*0.7)); ai_stuck[i] = 0
                    end
                else; ai_stuck[i] = 0; end
            end
            pp = RaceAI.project(AILINE, cs.x, cs.z)
            vts = RaceAI.plan!(AICARS, AILINE; scale = AI_SCALE, player = (pp[1], pp[2], cs.v), rel = AI_REL, amax = 8.0)  # conservative corner speed → don't run wide
            for (i, pc) in enumerate(AIPHYS)
                thr, brk, st = RaceAI.controller(AILINE, AICARS[i].s, AICARS[i].lane, AICARS[i].tlane, vts[i],
                                                 pc.x, pc.z, pc.θ, pc.v, DriveRT.yawrate(pc))
                DriveRT.step_car!(pc, thr, brk, st, ddt; manual = false)
            end
            [(pc.x, groundz(pc.x, pc.z), pc.z, pc.θ) for pc in AIPHYS]
        else
            pp = RaceAI.project(AILINE, cs.x, cs.z)                # the human as a racecraft object (s, lateral, speed)
            poses, hit = RaceAI.step_field!(AICARS, AILINE, ddt; scale = AI_SCALE, player = (pp[1], pp[2], cs.v), rel = AI_REL)
            ai_hit[] = hit; poses
        end
        # GD: rigid-body collision — when the player and an AI overlap and are CLOSING, apply a
        # momentum-exchange impulse: the player (real vehicle physics) is knocked off line + spun
        # via bumpX!, the AI is shoved aside + spun + scrubbed.  The wheels keep spinning with motion.
        if race_go[] && !rst && !isempty(ai_poses)
            pm = 560.0; am = 560.0; restn = 0.15; mr = pm*am/(pm+am)
            pvx = cs.v*cos(cs.θ); pvz = cs.v*sin(cs.θ)
            for (k, p) in enumerate(ai_poses)
                dx = p[1] - cs.x; dz = p[3] - cs.z; d = hypot(dx, dz)
                (d < 1e-3 || d > 3.6) && continue            # not touching
                nx = dx/d; nz = dz/d                          # contact normal, player → AI
                ac = AICARS[k]; aθ = p[4]
                avx = ac.v*cos(aθ); avz = ac.v*sin(aθ)
                vrel = (pvx-avx)*nx + (pvz-avz)*nz            # closing speed along the normal
                vrel <= 0.2 && continue                       # separating → no new impulse
                j = (1+restn)*vrel*mr
                lat = -dx*sin(cs.θ) + dz*cos(cs.θ)            # contact offset in the player's frame → spin sign
                bumpX!(cs, -(j/pm)*nx, -(j/pm)*nz, clamp(-sign(lat)*(j/pm)*0.05, -1.5, 1.5))
                if AI_PHYSICS                                  # the AI is a real physics car → impulse it too
                    alat = -dx*sin(aθ) + dz*cos(aθ)
                    DriveRT.bump!(AIPHYS[k], (j/am)*nx, (j/am)*nz, clamp(sign(alat)*(j/am)*0.05, -1.5, 1.5))
                else
                    along  = nx*cos(aθ) + nz*sin(aθ); across = -nx*sin(aθ) + nz*cos(aθ)
                    ac.v   = max(0.0, ac.v + (j/am)*along*0.6)    # pushed along its heading (rear-ended ⇒ sped up; nosed ⇒ slowed)
                    ac.lane = clamp(ac.lane + (j/am)*across*0.12, -RaceAI.LANE_MAX, RaceAI.LANE_MAX)  # shoved aside
                    ac.spin += clamp((j/am)*across*0.04, -0.6, 0.6)   # yaw twitch
                end
            end
        end
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
            Render.draw(prog, it, vp, Render.billboard_model(pos,w,h,eye); bright=1.55, ambfill=0.85)  # sprites read near-unlit (colorful signs, not "burned")
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
                (phase[] == :qual ? "  ⏱ QUALIFYING — drive a lap, then press ENTER to start the race" :
                 (!race_go[]) ? "  🏁 GET READY — floor the throttle to start (the field launches with you)" :
                 IS_RACE ? (race_done ? "  ✦ FINISHED P$(player_finpos[])/$(length(AICARS)+1) — best $(fmt_lap(best_lap)) (started P$(player_grid[]))" :
                            "  — lap $(min(cs.laps+1,RACE_LAPS))/$RACE_LAPS" *
                            (isempty(AICARS) ? "" : "  Pos P$(findfirst(e->e[1]==0, standings()))/$(length(AICARS)+1)")) :
                           "  [$(uppercasefirst(MODE))]") *
                (FUEL_ON ? "  — fuel $(round(Int,fuel[]))L ($(round(burn_lap>0 ? fuel[]/burn_lap : 0,digits=1)) laps)" : "") *
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
