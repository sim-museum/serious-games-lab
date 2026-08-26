# juliaMotor — DRIVE THE MTK MODEL.  Same GPL Zandvoort + Lotus 49 renderer as
# drive_native.jl, but the physics is the iRacing-fit JuliaMotorMTK model (DriveRT).
# (GLFW/ModernGL/GLSL) driving the validated JuliaMotor physics over the real
# Zandvoort + Vanwall geometry, with native keyboard AND joystick input.  The
# first step toward an rF1-fidelity self-contained app; the rendering core is
# render.jl.
using GLFW, ModernGL, LinearAlgebra, Dates, Serialization

# E67 S1: launch-phase stopwatch — JM_TIMING=1 prints cumulative seconds at each load phase
const _T0 = time()
tstamp(lbl) = get(ENV,"JM_TIMING","0") != "0" && println("[t+", round(time()-_T0, digits=1), "s] ", lbl)
using JuliaMotor, RFactorData
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","drive_rt.jl"))); using .DriveRT  # MTK physics (planar)
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","drive_rt3d.jl"))); using .DriveRT3D  # full-3D physics (JM_3D=1)
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","ibt.jl"))); using .IBT           # iRacing .ibt telemetry writer
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
    JoyCfg.loadmap(_JOYCONF)                                  # honour juliaRacer.py / calibrate.jl (TX clutch pedal, etc.)
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
const MONZA    = TRACKSEL == "monza"
const WATGLEN  = TRACKSEL == "watglen"
# E57: Monza-only per-surface brightness — its `asphalt` MIP is over-bright (the road renders near-white,
# washing the scene to "snow") while the barriers/armco render carbonized-black under the flat overcast.
# The default track bright/ambfill (0.72/0.34) is fine on the other 4 GPL tracks, so this is gated to Monza.
# Road: pull bright/ambfill WAY down to land the asphalt on a real grey.  Barriers ("dark" category):
# lift like the trackside objects do.  Tunable via JM_MONZA_* if the PO wants to re-grade.
const MZ_ROAD_B = parse(Float64, get(ENV, "JM_MONZA_ROAD_B", "0.42"))   # road brightness  (default 0.72)
const MZ_ROAD_A = parse(Float64, get(ENV, "JM_MONZA_ROAD_A", "0.10"))   # road ambient fill (default 0.34)
const MZ_DARK_B = parse(Float64, get(ENV, "JM_MONZA_DARK_B", "1.05"))   # barrier brightness
const MZ_DARK_A = parse(Float64, get(ENV, "JM_MONZA_DARK_A", "0.55"))   # barrier ambient fill (lift the carbonized black)
const MZ_BANK_B = parse(Float64, get(ENV, "JM_MONZA_BANK_B", "0.55"))   # sopraelevata banking deck: tone the glaring white concrete down toward grey
const MZ_BANK_A = parse(Float64, get(ENV, "JM_MONZA_BANK_A", "0.22"))   # (geometry still reads as a wall — that's the deferred E52 banking-mesh issue — but at least not blinding white)
const MZ_OTHER_B = parse(Float64, get(ENV, "JM_MONZA_OTHER_B", "0.72")) # everything else (grass/verge/kerb/structure) — default grade (diagnostic-tunable)
const MZ_OTHER_A = parse(Float64, get(ENV, "JM_MONZA_OTHER_A", "0.34"))
println("  → track: ", uppercasefirst(TRACKSEL))
# E52: this Monza is the COMBINED banked circuit — the road course AND the high-speed BANKING oval are
# BOTH part of the lap, but where they cross the banking deck sits ABOVE the road course.  A single-
# valued HAT returns the topmost surface (the banking), so the car climbs onto it / hits a "wall" at the
# underpass ("can't drive through").  build_hat's geometric overpass-drop removes a deck triangle ONLY
# where a ROAD-asphalt surface lies beneath it (the underpass), so the drivable banking OVAL (deck over
# GRASS) is untouched.  The road + banking SHARE the sNN[bl]N section textures, so this can't be done by
# name.  ROAD_PRED classifies the lower surface; HAT_EXCLUDE stays empty (no blanket texture drop).
const HAT_EXCLUDE = Set{String}()
const HAT_EXCLUDE_PRED = nothing
const ROAD_PRED = MONZA ? (lt -> occursin("asp", lt) || startswith(lt,"groove") || startswith(lt,"kerb")) : nothing
# E64 S6 (WG4): a GENERAL road-texture classifier for the racing-surface HAT.  The old comment at the
# TERRAIN0 build claimed a "ROAD-only HAT" but build_hat keeps ALL horizontal terrain (road_pred only
# informs Monza's overpass logic) — so the centreline align + recentre midpoint scans measured GRASS
# APRONS as road, which is exactly why the Watkins line strands ~10 m onto the grass at s≈300 (WG4)
# while printing "100% on terrain".  GPL road/paint textures across the shipped tracks: asp*/Asphalt,
# groove, curb/kerb, and the start-line paint (sline/sgrid/start).  Grass/bank*/edge*/sideroad/pit
# aprons stay out.  If a track's mesh yields too few road tris (unknown naming), fall back to the full
# terrain HAT — behaviour unchanged there.
const ROAD_TEX = lt -> occursin("asp", lt) || startswith(lt,"groove") || startswith(lt,"curb") ||
                       startswith(lt,"kerb") || lt in ("sline","sgrid","start") ||
                       # E64 S9 (Nürburgring): atog*/a_l_g* = asphalt-to-grass transition strips lining
                       # the road edge; Concrete = the Karussell banking.  Without them the road oracle
                       # recognised only 54% of the line's surface and the alignment optimised against
                       # a partial road.  (Names are Ring-specific; no collisions on the other tracks.)
                       startswith(lt,"atog") || startswith(lt,"a_l_g") || lt == "concrete"

# ---- session mode + race config (GPL-style: Practice / Training / Race) ----
const MODE      = lowercase(get(ENV, "JM_MODE", "practice"))   # practice | training | race
const RACE_LAPS = max(1, tryparse(Int, get(ENV, "JM_LAPS", "3")) |> x -> x === nothing ? 3 : x)
const PRACTICE_SEC = 60.0 * (tryparse(Float64, get(ENV, "JM_PRACTICE_MIN", "15")) |> x -> x === nothing ? 15.0 : x)   # GPL-style practice session length before the race (T = accelerate time)
# In REPLAY the field size comes from the RECORDING (so every recorded car gets a chassis to
# draw + camera-focus), not JM_AI — else focusing the replay camera on an AI shows empty track.
const N_AI      = let rf = get(ENV, "JM_REPLAY", "")
    if !isempty(rf) && isfile(rf)
        try; clamp(deserialize(rf).ncar - 1, 0, 5); catch; 5; end
    else
        clamp(tryparse(Int, get(ENV, "JM_AI", "0")) |> x -> x === nothing ? 0 : x, 0, 5)
    end
end
const IS_RACE   = MODE == "race"
const IS_TRAIN  = MODE == "training"
# E11: AI speed as a percentage — 100 % = the GPL AI car laptime for the track.
const AI_PCT    = clamp(tryparse(Float64, get(ENV, "JM_AI_PCT", "100")) |> x -> x === nothing ? 100.0 : x, 30.0, 200.0)
# GPL spread: by DEFAULT the field runs its own (physics-paced) speed and SPREADS OUT — the Eagle
# pulls away from the BRM, exactly as the PO wants.  The field pace is anchored to the human via the
# GUI's per-track % preset (≈ the human's best lap), so it doesn't run away.  Opt back into the old
# "never more than JM_AI_REL × the player's current speed" rubber-band by setting JM_AI_REL.
const AI_REL    = haskey(ENV, "JM_AI_REL") ? clamp(parse(Float64, ENV["JM_AI_REL"]), 1.0, 4.0) : Inf
# E12/G2: physics-AI corner-speed limit (lateral m/s² assumed for vtarget=√(amax/κ)).  Lower = the AI
# brakes earlier / takes corners slower → fewer over-speed-entry spins on the hilly tracks, at some pace.
const AI_AMAX   = clamp(parse(Float64, get(ENV, "JM_AI_AMAX", "8.0")), 4.0, 14.0)
# AI model: KINEMATIC multi-rail field by DEFAULT (RaceAI.step_field! — robust, GPL-authentic,
# never spins or leaves the rail; the PO's chosen "GPL 3-rail" AI).  The physics-AI path is
# OPT-IN via JM_AI_PHYSICS, per RACE_AI_NOTES.md ("ship opt-in first; default only after a
# test-drive confirms the feel").  E38: the physics AI were defaulted ON by a regression and
# blew up on the big tracks (Spa Eau Rouge, Nürburgring) — cartwheeling off the road, the
# recovery snap-forward producing the "inchworm" teleport, and clustering on the player so it
# bogged (E39).  Kinematic AI track the line cleanly and don't contact the player on the grid.
const AI_PHYSICS = haskey(ENV, "JM_AI_PHYSICS")
# Physics-AI pace is set ONCE here via ENGINE POWER (throttle cap), NOT a per-frame rubber-band:
# the AI race at a fixed pace they can't exceed (and can wash out if hot), so a fast human gets
# legitimately ahead.  1.0 = full DFV power (GPL-fast); lower detunes them.  JM_AI_POWER tunes it.
const AI_POWER  = clamp(tryparse(Float64, get(ENV, "JM_AI_POWER", "0.90")) |> x -> x === nothing ? 0.90 : x, 0.4, 1.0)
const CONTACT_D = parse(Float64, get(ENV, "JM_CONTACT_D", "2.1"))   # collision = ACTUAL contact (≈ car width); no repel-from-afar
# E55/E38: a physics AI whose heading deviates more than this from the rail tangent has SPUN OUT (the
# controller can oscillate into a spin on the hilly/blind tracks).  It won't trip the slow/off-line
# recovery (it's still fast + near the line), so it spins forever → "flopping/strange" field.  Treat a
# >SPIN_LIM heading error as off-line and snap it back to the rail heading fast.  (≈80°.)
const SPIN_LIM  = parse(Float64, get(ENV, "JM_SPIN_LIM", "1.4"))
# SLIPSTREAM (GPL models it): tucking into the hole a car ahead punches in the air gives a forward
# tow → you reel them in on a straight and slingshot past.  Returns the tow accel (m/s²) on a
# follower at (fx,fz,fθ,fv) from the nearest aligned car ahead in `leads` = [(x,z,θ,v)…].
const DRAFT_LEN = 26.0; const DRAFT_LAT = 2.8; const TOW_MAX = 4.0   # draft reach (m), lateral catch (m), max tow (m/s²)
# E56: the PLAYER's draft is a real AERO effect — tucking into the wake cuts frontal drag
# (CdA_scale<1 fed through the chassis ODE), it is NOT a forward velocity bump.  DRAFT_DRAG_CUT
# = the max fraction of drag removed right in the tow (≈45 %); it tapers to 0 at the draft edge.
const DRAFT_DRAG_CUT = clamp(parse(Float64, get(ENV, "JM_DRAFT_CUT", "0.45")), 0.0, 0.8)
function draft_tow(fx, fz, fθ, fv, leads)
    fv < 26.0 && return 0.0                                          # the tow only matters at speed (straights)
    hx = cos(fθ); hz = sin(fθ); best = 0.0
    for L in leads
        dx = L[1]-fx; dz = L[2]-fz; ahead = dx*hx + dz*hz            # distance the lead is in FRONT of us
        (ahead < 2.0 || ahead > DRAFT_LEN) && continue
        abs(-dx*hz + dz*hx) > DRAFT_LAT && continue                 # must be lined up behind it, not beside
        abs(RaceAI.wrapπ(L[3]-fθ)) > 0.5 && continue                # headings aligned (same way down the road)
        best = max(best, TOW_MAX*(1.0 - ahead/DRAFT_LEN))           # closer = stronger tow
    end
    best
end

# E15: collide a car (x,z,θ,v) with the nearest SOLID trackside object (haybales/fences/buildings).
# Returns the impulse (dvx,dvz,dr,dvy,dpp) to feed bump3d!, or nothing.  A square SNOUT hit (contact on
# the car's centreline) bounces it straight back; a hit toward a WHEEL (offset to the side) makes the
# spinning wheel CLIMB the obstacle → a vertical launch + roll (angular + linear momentum), per the PO.
const CARHALF = 1.4    # car collision half-extent (m)
function solid_hit(x, z, θ, v)
    v < 1.2 && return nothing
    @inbounds for (ox, oz, r, _kind) in SOLIDS
        dx = x - ox; dz = z - oz; d = hypot(dx, dz)
        rr = r + CARHALF
        (d >= rr || d < 1e-3) && continue
        nx = dx/d; nz = dz/d                              # outward normal (object → car)
        vn = v*cos(θ)*nx + v*sin(θ)*nz                    # car speed along it (<0 = driving INTO the object)
        vn >= -0.3 && continue                            # not closing on it
        across = -dx*sin(θ) + dz*cos(θ)                   # contact across the car (which side/wheel)
        along  =  dx*cos(θ) + dz*sin(θ)                   # >0 ⇒ object behind the car (a REAR-wheel hit)
        e = 0.45; j = (1+e)*(-vn)                         # bounce straight back (linear)
        lift  = clamp(abs(across)/CARHALF * (-vn) * 0.45, 0.0, 6.0)   # a WHEEL (offset) hit climbs → launch
        droll = clamp(sign(across)*lift*0.8, -5.0, 5.0)               # …and rolls toward the climb
        dpitch = clamp(-sign(along)*lift*0.7, -4.0, 4.0)             # rear wheel climbs ⇒ nose down ⇒ REAR LIFTS
        dr    = clamp(-sign(across)*(-vn)*0.04, -1.0, 1.0)            # yaw twitch off the obstacle
        return (j*nx, j*nz, dr, lift, droll, dpitch)
    end
    nothing
end
# E56: object collision CLASS for the all-Modelica PLAYER contact law — hedges/hay rows (Zandvoort
# `haie`) are soft (drive in, bleed speed, get stuck); everything else (walls/armco/fences/buildings/
# towers/parked vehicles) is a hard elastic wall (bounce).  The AI still use the kinematic solid_hit.
solidkind(nm) = (startswith(nm,"haie")||startswith(nm,"bush")||startswith(nm,"shrub")||startswith(nm,"hedge")||startswith(nm,"haystk")) ? :soft : :wall
# E56: sum the spring-damper CONTACT forces from every SOLID the PLAYER car penetrates into one
# body-frame (Fx,Fy,Mz) to feed extforce3d! BEFORE the step (the solver integrates the collision —
# no bumpX! state hack).  Returns the net force/moment + a peak-penetration proxy for the FFB jolt.
function solid_contact(x, z, θ, v, dt)
    Fx = 0.0; Fy = 0.0; Mz = 0.0; peak = 0.0
    @inbounds for (ox, oz, r, kind) in SOLIDS
        dx = x - ox; dz = z - oz; d = hypot(dx, dz)
        rr = r + CARHALF
        (d >= rr || d < 1e-3) && continue
        nx = dx/d; nz = dz/d
        vn = v*cos(θ)*nx + v*sin(θ)*nz                    # car speed along the outward normal (<0 = into it)
        (fx, fy, mz) = DriveRT3D.contact_force(rr - d, nx, nz, vn, θ; kind = kind, dt = dt)
        Fx += fx; Fy += fy; Mz += mz; peak = max(peak, hypot(fx, fy))
    end
    (Fx, Fy, Mz, peak)
end
# GPL '67 AI reference laptimes (s) — the "100 %" anchor.  Sourced from GPL AI/hotlap
# pace per circuit; tunable per car/setup via JM_AI_REFLAP (overrides the table).  At
# AI_PCT=100 the field is paced to hit exactly this laptime regardless of the rail
# follower's own natural pace (see RaceAI.natural_laptime).
# GPLrank (1967) benchmark laptimes (gplrank.schuerkamp.de) — 100 % AI pace = the FASTEST car
# achieves this.  Monza = the 1967 ROAD course (GPLrank 1:30.202), now that we run `monza` not monza10k.
const REF_LAP = Dict("zandvoort"=>86.848, "nurburgring"=>501.931, "watglen"=>66.912,
                     "monza"=>90.202, "spa"=>200.342, "skidpad"=>30.0)
const AI_REFLAP = (v = tryparse(Float64, get(ENV, "JM_AI_REFLAP", ""));
                   v === nothing ? get(REF_LAP, TRACKSEL, 90.0) : v)
println("  → mode: ", uppercasefirst(MODE),
        IS_RACE ? "  ($RACE_LAPS laps" * (N_AI>0 ? ", $N_AI AI cars)" : ")") : "")
# ---- E10: fuel.  The Lotus is fuelled to finish the race + a margin of ~5 laps. ----
# GPL Ford-DFV-ish burn (L/km); the tank is sized to (laps+margin)·burn so the player
# always has enough to finish with a cushion.  Distance-based so the laps-of-fuel figure
# is honest.  Practice/Training get a generous tank; the skidpad has no laps → no fuel.
const FUEL_LPK    = clamp(tryparse(Float64, get(ENV,"JM_FUEL_LPK","0.55")) |> x-> x===nothing ? 0.55 : x, 0.05, 5.0)
const FUEL_MARGIN = max(0, tryparse(Int, get(ENV,"JM_FUEL_MARGIN","10")) |> x-> x===nothing ? 10 : x)   # generous margin so a long session can't strand you

# ---- iRacing .ibt telemetry export (JM_IBT=1) ----
# Record the lap in iRacing's exact .ibt format so juliaMotor laps can be diffed
# against gold-standard iRacing telemetry (same car/track, similar laps) to tune the
# model.  We reuse a real iRacing .ibt of the matching car/track as the header+var-
# table+YAML template (so the file is byte-identical in structure / any iRacing tool
# reads it) and fill the channels juliaMotor produces.
const IBTREC = !haskey(ENV, "JM_NOIBT")          # .ibt telemetry ON by default (set JM_NOIBT to disable)
const REPLAY_FILE = get(ENV, "JM_REPLAY", "")    # E18: if set, PLAY BACK this .jmr recording instead of driving
const IBTDIR = normpath(joinpath(@__DIR__,"..","..","data","iracing"))
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

# D4 (PO): the GPL .trk DRIVING line hugs the road EDGE through corners (it is the racing groove, not the
# geometric centre of the tarmac), so lane-0 — what SHIFT-R drops you onto and what the AI takes as its
# reference — sits at the road edge, half on the grass, and the AI apexes even further inside onto the
# grass ("as if the road is two car-widths wider on the inside").  Re-centre each centreline point on the
# VISIBLE road: scan left + right along the lateral normal to the road-mesh edges (the road-only HAT) and
# move the point toward the MIDPOINT (a damped, clamped, smoothed fraction so a one-sided pit-lane/apron
# can't drag it and the line stays continuous).  JM_NO_RECENTRE=1 restores the raw .trk line.
function recentre_on_road(cl, hat; reach = 14.0, step = 0.5, frac = 1.0, cap = 4.0, passes = 1)
    n = length(cl)
    on(x, z) = JuliaMotor.hat3d(hat, x, z; ref = Inf)[3]
    for pass in 1:passes
        nrm(i) = (q = cl[mod(i, n)+1]; r = cl[mod(i-2, n)+1]; tx = q[1]-r[1]; ty = q[2]-r[2];
                  tl = hypot(tx, ty); tl < 1e-6 ? (0.0, 0.0) : (-ty/tl, tx/tl))   # left-hand normal
        raw = zeros(n)
        for i in 1:n
            p = cl[i]; (nx, ny) = nrm(i)
            (nx == 0.0 && ny == 0.0) && continue
            if on(p[1], p[2])                                              # on road: move toward the edge midpoint
                hi = 0.0; while hi < reach && on(p[1]+nx*(hi+step), p[2]+ny*(hi+step)); hi += step; end
                lo = 0.0; while lo < reach && on(p[1]-nx*(lo+step), p[2]-ny*(lo+step)); lo += step; end
                raw[i] = clamp(frac*(hi - lo)/2, -cap, cap)                # +→ shift LEFT toward the midpoint
            else
                # E64 S6 (WG4): a point OFF the road used to be skipped — with a true road-only HAT the
                # stranded sections (Watkins s≈300: the raw .trk ~10 m onto the grass) must be RESCUED:
                # scan both ways along the normal for the road, and step toward the nearest road sample
                # (capped like everything else; multiple passes walk it home).
                hit = 0.0
                for d in step:step:reach
                    if     on(p[1]+nx*d, p[2]+ny*d); hit =  d; break
                    elseif on(p[1]-nx*d, p[2]-ny*d); hit = -d; break
                    end
                end
                raw[i] = clamp(hit, -cap, cap)
            end
        end
        sm = zeros(n); W = 3                                               # box-smooth (discrete edge sampling is jittery)
        for i in 1:n; a = 0.0; for d in -W:W; a += raw[mod(i-1+d, n)+1]; end; sm[i] = a/(2W+1); end
        cl = [(p = cl[i]; (nx, ny) = nrm(i); (p[1]+nx*sm[i], p[2]+ny*sm[i])) for i in 1:n]
        println("centreline re-centred on the visible road (pass ", pass, "/", passes, "): max shift ",
                round(maximum(abs, sm), digits=1), " m, mean ", round(sum(abs, sm)/n, digits=2),
                " m, at-start ", round(sm[1], digits=2), " m")
        maximum(abs, sm) < 0.3 && break                                    # converged
    end
    cl
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
    # E76-S3: is the Ring's scenery even being LOADED? Its whole load is "184 groups / 4065 tris"
    # where Spa gets 1679 objects + 5132 billboards at a fifth the length (E76-S2), and gold's first
    # kilometre is lined with crowds and hoardings that native simply does not have. Before hunting
    # filters, count what this loop is OFFERED versus what each rule removes. JM_SCENEDIAG=1.
    local n_offered=0; local n_treesrb=0; local n_nomesh=0; local n_kept=0
    scene_names=Dict{String,Int}()
    for (nm,t) in pls
        n_offered += 1
        scene_names[nm] = get(scene_names,nm,0) + 1
        if startswith(nm,"treesrb"); n_treesrb += 1; continue; end   # forest-BACKDROP "paintings"
        mesh=getmesh(nm)
        if (mesh===nothing || isempty(mesh)); n_nomesh += 1; continue; end
        n_kept += 1
        if issprite(nm,mesh)
            nskip+=1
            # E76-S1 (PO: "many of the buildings and crowds shortly after S/F were simply removed"):
            # name what this skip drops and where it sits. The test is height < 0.5 m AND footprint
            # < 6 m — intended for degenerate stubs, but a crowd row or building authored as a low
            # placeholder would match it too, and 37 objects are dropped on the Ring. Report each
            # one's extent and lapdist so the PO's missing objects can be identified rather than
            # guessed at. JM_SPRITESKIP=1.
            if get(ENV,"JM_SPRITESKIP","") != ""
                lo3=Inf;hi3=-Inf;loh=Inf;hih=-Inf; cx=0.0; cy=0.0; np=0
                for tr in mesh, q in tr.p
                    lo3=min(lo3,q[3]);hi3=max(hi3,q[3]);loh=min(loh,q[1],q[2]);hih=max(hih,q[1],q[2])
                end
                M=placemat(t)
                px = M[1,4]; py = M[2,4]
                hr = JuliaMotor.hat(ribbon, Float32(px), Float32(py))
                println("   [spriteskip] ", rpad(nm,16),
                        "h=", rpad(round(hi3-lo3,digits=2),7),
                        "w=", rpad(round(hih-loh,digits=2),7),
                        hr.found ? string("lapdist=", rpad(round(hr.lapdist,digits=0),9),
                                          "lat=", round(hr.lateral,digits=1)) : "off-ribbon")
            end
            continue
        end
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
            # E68 S9 (PO/Ring ~s18400): a section's UNLIT UNDERSIDE hovered beside the crest as a
            # dark angular slab — we render scenery two-sided, GPL's single-sided cull hides these.
            # Skip strongly DOWN-facing faces that sit ABOVE road level BESIDE the corridor
            # (5–30 m out); faces directly OVER the road stay (bridge undersides must render).
            if nl > 1f-6 && nz/nl < -0.5f0
                hrz = JuliaMotor.hat(ribbon, cgx, cgy)
                if hrz.found && 5.0 < abs(hrz.lateral) < 30.0 && cgz > hrz.height + 3.0
                    continue
                end
            end
            v=get!(groups, tr.tex, Float32[])
            for i in 1:3
                q=w[i]; n=nn[i]; uv=tr.uv[i]
                append!(v, Float32[q[1],q[3],-q[2], n[1],n[3],-n[2], tr.col[1],tr.col[2],tr.col[3], uv[1],uv[2]])
            end
        end
    end
    nskip > 0 && print("(skipped ", nskip, " flat sprite stubs) ")
    if get(ENV,"JM_SCENEDIAG","") != ""
        println()
        println("== JM_SCENEDIAG scenery placements offered to the loader ==")
        println("   offered              ", n_offered)
        println("   dropped: treesrb*    ", n_treesrb)
        println("   dropped: NO MESH     ", n_nomesh, "   <-- placement exists but its object could not be loaded")
        println("   dropped: sprite stub ", nskip)
        println("   reached the renderer ", n_kept - nskip)
        println("   distinct object names: ", length(scene_names))
        # E76-S4: is this a LOOKUP failure rather than missing content? getmesh does
        #   get(datpack, lowercase(nm*".3do"))
        # and `strings nurburg.dat` shows BOTH "strauch" and "STRAUCH" — a mixed-case archive. If the
        # keys keep their original case, a lowercase lookup finds only the already-lowercase ones,
        # which would explain 841 loading and 2231 not. Test it directly: for every name that failed,
        # try a case-INSENSITIVE match against the archive keys.
        let keys_ci = Dict(lowercase(k) => k for k in keys(datpack))
            nlower = count(k -> k == lowercase(k), keys(datpack))
            println("   -- archive keys: ", length(datpack), " total, ", nlower, " already lowercase, ",
                    length(datpack)-nlower, " mixed/upper --")
            found_ci = 0; total_missing = 0
            for (nm,c) in scene_names
                (getmesh(nm)===nothing || isempty(getmesh(nm))) || continue
                total_missing += c
                haskey(keys_ci, lowercase(nm*".3do")) && (found_ci += c)
            end
            println("   -- of ", total_missing, " failed placements, ", found_ci,
                    " WOULD resolve with a case-insensitive archive lookup --")
        end
        miss = sort([(nm,c) for (nm,c) in scene_names if getmesh(nm)===nothing || isempty(getmesh(nm))], by=x->-x[2])
        if !isempty(miss)
            println("   -- most-placed names with NO MESH (top 15) --")
            for (nm,c) in miss[1:min(end,15)]; println("      ", rpad(nm,18), c, " placements"); end
        end
        flush(stdout)
    end
    (hat, [Render.TrackPart(v, tex, (0.5f0,0.5f0,0.5f0)) for (tex,v) in groups])
end

# ---- load geometry + physics: GPL track/car assets; handling = the MTK Lotus 49 (DriveRT) ----
# The .veh load is vestigial-but-load-bearing (see CLAUDE.md): without a resolvable GameData the sim
# dies at startup.  default_gamedata()'s wine-prefix fallback doesn't exist on this box, so when
# RFACTOR_GAMEDATA is unset prefer the repo's symlink-only `rfactor-gamedata` tree (built from the
# mod media; juliaRacer.py launches don't set the env var).
const _REPO_GD = normpath(joinpath(@__DIR__,"..","..","..","..","..","rfactor-gamedata"))
const GD = haskey(ENV,"RFACTOR_GAMEDATA") ? ENV["RFACTOR_GAMEDATA"] :
           isdir(_REPO_GD)                ? _REPO_GD : default_gamedata()
const VEH = load_vehicle(joinpath(GD,"Vehicles","F158","Vanwall","Teams","LewisEvans","LewisEvans.veh"))
const MODEL = VehicleModel(VEH)              # NOT the driving physics: handling is the MTK Lotus 49
                                             # (DriveRT, fitted to iRacing lotus49 .ibt). MODEL only fills
                                             # DriveCar's `model` field, which this path never reads —
                                             # see demo/native/CLAUDE.md. Vestigial; keeps the .veh load alive.
const GPLBASE = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks"))
# TRACKSEL → GPL track folder (all share the .3do/.trk/.mip/.dat pipeline)
const GPLNAME = get(Dict("nurburgring"=>"nurburg", "zandvoort"=>"zandvort",
                         "watglen"=>"watglen", "monza"=>"monza", "spa"=>"spa67"),   # PO: the regular Monza road course (not the broken monza10k banked combined circuit)
                    TRACKSEL, "zandvort")
const ZD   = joinpath(GPLBASE, GPLNAME)
# the track's packed archive (geometry/centreline/textures/objects live here on most tracks)
# CASE-INSENSITIVE on disk: GPL ships mixed case (e.g. Monza's `monza.DAT`), and Linux is case-sensitive,
# so match the wanted name against the real directory entries.
find_ci(dir, name) = (isdir(dir) || return joinpath(dir, name);
                      m = filter(f -> lowercase(f) == lowercase(name), readdir(dir));
                      isempty(m) ? joinpath(dir, name) : joinpath(dir, m[1]))
const TRACKDAT = (p = find_ci(ZD, GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMPTRK = mktempdir()
"Path to a track file (`base`+`ext`, e.g. \".3do\"/\".trk\"): loose on disk if present, else extracted from the track .dat."
function track_file(base, ext)
    p = find_ci(ZD, base*ext); isfile(p) && return p
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
    tstamp("track parse begins"); print("loading GPL ", GPLNAME, "… "); flush(stdout)
    const TRACKMESH0 = Render.GPL3DO.parse_3do(ZTRK)
    # Align the racing line against the ROAD-only HAT (precise — scenery terrain in the
    # full HAT would let the line drift onto the grass verge); the road ribbon then doubles
    # as the corridor filter for scenery placement.
    const TERRAIN0 = GPLTrack.build_hat(TRACKMESH0; exclude=HAT_EXCLUDE, exclude_pred=HAT_EXCLUDE_PRED, drop_overpass=MONZA, road_pred=ROAD_PRED)
    # E64 S6 (WG4): the TRUE road-only HAT — road/kerb/paint textures only — for centreline work.
    # Physics keeps the full TERRAIN0 (grass must stay drivable).  GATED TO WATGLEN, where it is
    # capture-verified (car on tarmac at s=5/300/1200): the cross-track gate showed the other
    # circuits' lines MOVE under the road-only oracle (Zandvoort pass-1 mean 2.19 m vs the old
    # PO-verified 0.12 m; Nürburgring aligns at only 54% = its road textures are under-recognised
    # by ROAD_TEX) — extending them needs per-track texture work + capture verification, not a
    # blanket switch.  JM_ROADHAT=1 forces it on for experiments.
    const ROADHAT = let rp = ROAD_TEX
        nroad = count(t -> rp(lowercase(t.tex)), TRACKMESH0.tris)
        # E64 S9: NURB joins WATGLEN — with atog*/a_l_g*/concrete recognised its oracle converges
        # (recentre mean 2.41→0.04 m over 4 passes) and all four survey positions land on tarmac,
        # including the old lap-end drift at s=17000 (car was in the catch-fencing).
        if (WATGLEN || NURB || get(ENV,"JM_ROADHAT","0") != "0") && nroad >= 200
            h = GPLTrack.build_hat(TRACKMESH0; exclude=HAT_EXCLUDE, exclude_pred=(lt -> !rp(lt)), drop_overpass=MONZA, road_pred=ROAD_PRED)
            println("  road-only HAT: ", nroad, " road tris (align/recentre oracle)"); h
        else
            println("  road-only HAT: off for this track (", nroad, " road tris recognised) — full-terrain oracle as before")
            TERRAIN0
        end
    end
    const ALIGNED  = let a = align_centreline(GPLTrack.trk_centreline(track_file(GPLNAME, ".trk")), ROADHAT)
        # D4: pull lane-0 to the road's geometric centre (Zandvoort).  SKIP on Monza — its wide pit
        # straight + pit lane skew the "midpoint" so the recentre over-shifts the racing line toward the
        # pit wall (4 m, capped); the raw GPL .trk line is the correct groove there.
        # E64 S6: on WATGLEN, recentre against the ROAD-only HAT (was: full terrain incl. grass
        # aprons) with multi-pass so a line stranded ~10 m off (s≈300, WG4) walks home 4 m per
        # pass; other tracks keep their verified single-pass full-terrain behaviour.
        (haskey(ENV, "JM_NO_RECENTRE") || MONZA) ? a : recentre_on_road(a, ROADHAT; passes = (ROADHAT === TERRAIN0 ? 1 : 4))
    end
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
    const TERRAIN  = isempty(SECTRI) ? TERRAIN0 : GPLTrack.build_hat(TRACKMESH; exclude=HAT_EXCLUDE, exclude_pred=HAT_EXCLUDE_PRED, drop_overpass=MONZA, road_pred=ROAD_PRED)
    const TRKSURF  = GPLTrack.build_surface(ALIGNED, TERRAIN)
    const LAPLEN = maximum(TRKSURF.lapdist)              # lap length [m], for start/finish wrap detection
    const CAR = DriveCar(MODEL, TRKSURF; terrain=TERRAIN)    # racing ribbon from the .trk centreline
    println(TERRAIN, "  ", TRKSURF)
    # E70-S2: these mesh censuses live HERE, not in the GPL objects block below, because that block
    # is never entered on the Nürburgring — its scenery loads by a different path ("scenery… 184
    # groups" vs "N trackside objects"). Every census built for E71–E73 was therefore unreachable on
    # the Ring, and printed NOTHING there: E70-S1 read that as "no crowds near the road" when it was
    # an instrument that was never connected. Anything needing only TRACKMESH + TRKSURF belongs
    # above the split so it runs on every track.
    if get(ENV,"JM_LINEONROAD","")!=""
        # E73-S4: map where the CENTRELINE leaves the road, lap-wide. E73-S3 found Monza's line
        # 7–19 m off the asphalt at s≈500 — the car is placed on unmodelled ground while the real
        # road runs to one side. The width census cannot show this: its lat_min/lat_max span
        # includes aprons and paddock, so its midpoint is not the road centre.
        # The robust question is BINARY: at this lapdist, is there any road-textured triangle AT
        # lateral 0? Report the nearest road triangle to the centreline per bucket; anything above a
        # car's half-width means the line is off the running surface there.
        step = parse(Float64, get(ENV,"JM_LINEONROAD_STEP","250"))
        halfb = parse(Float64, get(ENV,"JM_LINEONROAD_BUCKET","20"))
        near = Dict{Int,Float64}(); cnt = Dict{Int,Int}()
        for t in TRACKMESH.tris
            ROAD_TEX(lowercase(t.tex)) || continue
            cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
            cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
            hr = JuliaMotor.hat(TRKSURF, cx, cy)
            hr.found || continue
            b = round(Int, hr.lapdist/step)
            abs(hr.lapdist - b*step) <= halfb || continue
            a = abs(hr.lateral)
            near[b] = min(get(near, b, Inf), a)
            cnt[b] = get(cnt, b, 0) + 1
        end
        # NB CLINE is not defined this early in the load — derive the lap extent from the buckets
        # themselves. (The first version used CLINE.total and every run died with UndefVarError,
        # which printed NO census output at all: a silent-looking "clean" result that was really a
        # crash. Checked the exit status rather than the absence of findings.)
        total = isempty(near) ? 0 : maximum(keys(near))
        # `local` because this census now runs at TOP LEVEL (E70-S2 moved it out of the GPL objects
        # block so the Ring reaches it). In Julia's soft scope a bare `bad += 1` inside the loop
        # binds a NEW local and throws UndefVarError — which Monza hit on its first bad bucket while
        # the Ring, having none, ran to completion and looked fine. A crash that only fires when
        # there is something to report is the worst kind: the clean track "passes".
        local bad = 0
        local gap = 0
        println("== JM_LINEONROAD: nearest ROAD triangle to the centreline, per ", step, " m ==")
        for b in 0:total
            if !haskey(near, b)
                println("   s=", rpad(b*step,8), "NO ROAD TRIANGLES within ±", halfb, " m  *** GAP ***")
                gap += 1
            elseif near[b] > 3.0
                println("   s=", rpad(b*step,8), "nearest road is ", round(near[b],digits=1),
                        " m off the line   (", cnt[b], " tris)  *** LINE OFF ROAD ***")
                bad += 1
            end
        end
        println("   --> ", total+1, " buckets: ", gap, " with no road, ", bad,
                " with the line >3 m off the road, ", total+1-gap-bad, " healthy")
        flush(stdout)
    end
    tstamp("geometry extraction begins"); print("extracting geometry… "); flush(stdout)
    const TRACKMAIN0 = Render.extract_gpl_car(ZTRK; track=true, mirror=true, exclude=("ltraymap","lshad","wiref_s"))
    # E68 S10 (PO: "lots of z-fighting on guardrails throughout" Watkins + residuals elsewhere):
    # 13% of Watkins Armco tris and 10% of its fence tris are EXACT coplanar duplicates that the
    # track path never collapsed.  Dedup rail/fence-family parts by quantized centroid+area
    # (first face wins — identical geometry, so either is fine).  JM_RAIL_DEDUP=0 restores.
    railfam(tx) = (lt = lowercase(tx); startswith(lt,"armco") || startswith(lt,"fenc") || startswith(lt,"stfce") ||
                   startswith(lt,"sarmc") || startswith(lt,"yarmc") || startswith(lt,"gd_rail") || startswith(lt,"rail"))
    # E68 S11 verdict: terrain sheets must NOT join the blanket cull — winding varies per sheet
    # (culling ate the s=2500 embankment + Zandvoort dune faces while fixing one veil of two).
    # The Watkins veil (giant Grass sheet BACKS over the road) needs PER-FACE road-facing
    # selection — the same implementation the D6 sign boards await.  Reverted to rails-only.
    # E72-S3: the E68-S10 dedup drops ONE triangle at Watkins where its own justification claimed
    # "13% of Watkins Armco tris ... are EXACT coplanar duplicates". Count it properly before
    # believing either number. The `seen` set below is PER-PART, so duplicates living in DIFFERENT
    # parts cannot be caught — this reports per-part and GLOBAL duplicate counts side by side, which
    # separates "the key is wrong" from "the scope is wrong".
    if get(ENV,"JM_RAILDIAG","") != ""
        key(v,t) = begin
            cx=(v[t]+v[t+11]+v[t+22])/3; cy=(v[t+1]+v[t+12]+v[t+23])/3; cz=(v[t+2]+v[t+13]+v[t+24])/3
            ux=v[t+11]-v[t]; uy=v[t+12]-v[t+1]; uz=v[t+13]-v[t+2]
            wx=v[t+22]-v[t]; wy=v[t+23]-v[t+1]; wz=v[t+24]-v[t+2]
            a=0.5*sqrt((uy*wz-uz*wy)^2+(uz*wx-ux*wz)^2+(ux*wy-uy*wx)^2)
            (round(Int,cx*50), round(Int,cy*50), round(Int,cz*50), round(Int,a*100))
        end
        # `local` for every accumulator — top-level soft scope again. E70-S2 documented this exact
        # trap one sprint ago and I reproduced it here within the hour: a bare `n += 1` inside a
        # top-level loop binds a new local and throws. Writing the lesson down did not stop me
        # repeating it; declaring the scope explicitly does.
        local tot=0; local perpart=0; local gdup=0; local nparts=0
        glob=Set{NTuple{4,Int}}()
        for part in TRACKMAIN0
            railfam(part.tex) || continue
            nparts += 1
            v=part.verts; seen=Set{NTuple{4,Int}}()
            for t in 1:33:length(v)-32
                tot += 1; k=key(v,t)
                k in seen ? (perpart += 1) : push!(seen,k)
                k in glob  ? (gdup   += 1) : push!(glob,k)
            end
        end
        println("== JM_RAILDIAG rail/fence triangles ==")
        println("   parts=", nparts, "  triangles=", tot)
        println("   duplicates found PER-PART (what the shipped dedup can see): ", perpart,
                tot>0 ? string("  (", round(100perpart/tot,digits=1), "%)") : "")
        println("   duplicates found GLOBALLY (across parts too):               ", gdup,
                tot>0 ? string("  (", round(100gdup/tot,digits=1), "%)") : "")
        flush(stdout)
    end
    const TRACKMAIN = get(ENV,"JM_RAIL_DEDUP","1") == "0" ? TRACKMAIN0 : begin
        ndrop = Ref(0)
        out = map(TRACKMAIN0) do part
            railfam(part.tex) || return part
            v = part.verts; keep = Float32[]; seen = Set{NTuple{4,Int}}()
            for t in 1:33:length(v)-32
                cx=(v[t]+v[t+11]+v[t+22])/3; cy=(v[t+1]+v[t+12]+v[t+23])/3; cz=(v[t+2]+v[t+13]+v[t+24])/3
                ux=v[t+11]-v[t]; uy=v[t+12]-v[t+1]; uz=v[t+13]-v[t+2]
                wx=v[t+22]-v[t]; wy=v[t+23]-v[t+1]; wz=v[t+24]-v[t+2]
                a=0.5*sqrt((uy*wz-uz*wy)^2+(uz*wx-ux*wz)^2+(ux*wy-uy*wx)^2)
                k=(round(Int,cx*50), round(Int,cy*50), round(Int,cz*50), round(Int,a*100))
                if k in seen; ndrop[] += 1; else; push!(seen,k); append!(keep, @view v[t:t+32]); end
            end
            Render.TrackPart(keep, part.tex, part.col)
        end
        ndrop[] > 0 && println("  E68 S10: rail/fence dedup dropped ", ndrop[], " coplanar-duplicate tris")
        out
    end
    const TRACK = [TRACKMAIN; SECPARTS]
    const SEC_FROM = length(TRACKMAIN) + 1        # E68 S9b: trackItems[SEC_FROM:end] = landmass sections
    # E68 S10b: rails/fences are modeled as OFFSET front+back faces; GPL culls the back single-
    # sided, we drew both → grazing-angle poke-through = the PO's "z-fighting on guardrails
    # throughout".  (Exact-duplicate dedup was a near-no-op: extraction already collapses those.)
    # Per-part single-sided rendering for the rail family only — sign parts keep both faces (D6).
    const TRACK_RAILCULL = Bool[railfam(p.tex) for p in TRACK]
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
const LOTDIR = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","cars","cars67","lotus"))
const GPLTEX = Render.gpl_texture_index(LOTDIR)
const LOT3DO = joinpath(LOTDIR,"lotus.3do")
# GPL-fidelity cockpit: KEEP windlot (the tan leather scuttle — the defining GPL cockpit
# element; the earlier "rug" was the untextured yellow floor, which cockpit_clean drops, not
# windlot which is properly tan-textured).  Still drop hands/dup-mirror/teal front-susp/tan
# floor + clip the splayed-rear chrome.
# grey = the fallback colour for the one UNTEXTURED body part (a big inner-tub/underside shell, 2043
# verts) — the default light grey rendered it as white faceted clutter in the cockpit corners; a dark
# cockpit-interior grey hides it (it's interior/underside, invisible externally).
# mirror parts — pulled OUT of the body so they can be re-placed onto the cowl/plexiglass and
# tilted toward the eye (GPL: two round mirrors at the SIDES, mid-height; the default render
# saw the chrome housing torpedo-on at the bottom corners).
# ALL mirror parts excluded from the body; but we only DRAW the round face + rim (mirror/lrm/lrimext)
# — the bulky chrome HOUSING (lotmirt) + stalk (lotubase/lotubas2) read as a "chrome torpedo" (no RTT),
# so dropping them leaves a clean round disc on the cowl like the GPL gold standard.
const MIRROR_TEX  = ("mirror","lotmirt","lrm","lrimext","lotubase","lotubas2")   # excluded from CARP
const MIRROR_DRAW = ("mirror","lrm")                                             # actually drawn (glass disc only — the chrome rim "lrimext" sat in front of the glass and read as a torpedo TUBE, so it's dropped)
const TUB_GREY = parse(Float32, get(ENV,"JM_TUB_GREY","0.11"))   # untextured cockpit-tub shade (raise to lift the dark coaming "black band" toward the GPL aluminium tub)
# GPL gold standard shows the gloved hands/forearms filling the lower cockpit (where we otherwise
# see a black band).  E64 S2 (Z-CK4): the old JM_HANDS=1 kept lohand+lotarms inside CARP, where the
# body extraction (grey-tint + group handling) turned them into "giant silver arms" — but the RAW
# mesh sits exactly at the wheel (lohand x 0.68–0.80 vs rim x 0.74–0.76, SWCENTER x 0.75).  So they
# are now ALWAYS excluded from CARP and extracted separately like DRIVERP (textures lohand.mip /
# lotarms.mip ship with the car); the hands ride the wheel rotation, the forearms draw static.
const HANDS = get(ENV,"JM_HANDS","1") != "0"   # default ON to match gold; JM_HANDS=0 hides them
const _HAND_EXC = ("ltraymap","lshad","lohand","lotarms","dash7a","windlot")
# E36 black band: `lotblack` is the matte-black cockpit surround/dash that fills the lower view as a
# full-width band — the angular black "plywood" facets the PO flagged.  DROPPED by default now that the
# tan windlot scuttle (WIND_ALPHA=1) covers that area like the GPL gold standard; JM_KEEP_LOTBLACK=1
# brings the black band back.
const _LOTBLACK_EXC = get(ENV,"JM_KEEP_LOTBLACK","0") != "0" ? () : ("lotblack",)
const _EXTRA_EXC = Tuple(split(get(ENV,"JM_EXTRA_EXCLUDE",""), ",", keepempty=false))   # E36 band bisection: drop these textures from CARP
# E36: the "black band" below the wheel was the DRIVER FIGURE's own torso/lap — from the cockpit eye
# (inside the driver) his body filled the lower view, occluding the green tub + LOTUS hub badge.  Pull
# the driver body OUT of CARP and draw it only in CHASE view (driverItems below) so the cockpit is clear.
# E60 (nintendo gold video): the chase gold shows the BLUE HELMET + upper arms prominently — without
# "lid" (helmet shell) + "arms" (upper arms) the chase driver read as absent and the car skeletal (D12).
const DRIVER_TEX = ("driver5","lotbody","lotsho","knees","neck","lid","arms")
# E60: the HELMET is a separate head-pivot mesh (helmeg.3do, modeled around its own origin) that GPL
# places at the head position with the per-driver helmet skin — the chase gold shows Clark's blue
# clahelm.  Retexture helblack→clahelm and place it at the neck top (JM_HELM_X/Y tune).
const HELM_OFF = (parse(Float32,get(ENV,"JM_HELM_X","0.14")), parse(Float32,get(ENV,"JM_HELM_Y","0.34")), 0f0)
const HELMP = [Render.TrackPart(p.verts, p.tex=="helblack" ? "clahelm" : p.tex, p.col)
               for p in Render.extract_gpl_car(joinpath(LOTDIR,"helmeg.3do"); maxlat=0.95f0)]
# E62 (D12 chase body) — INVESTIGATED; the skinny 0.85 clip is confirmed correct, the residual is asset-LOD.
# A per-part 3do audit (scratchpad lot_parts.jl) + a JM_CARP_MAXLAT=1.15 capture proved WHY opening the clip
# fails: beyond 0.85 lateral sit the rear suspension/axle (lsusp2-7, lshok, axlelot) — they carry .mip
# textures yet render as chrome "spider-leg" sheets to the ground.  A drop-by-hide-marker attempt (skip any
# positioner offset >5 m) was tried in the parser and REVERTED: this model routes MOST of its real body
# through large-offset positioners that posmat deliberately clamps to origin ("so the body stays put"), so
# offset magnitude can't separate GPL's hidden LOD parts from real bodywork — dropping >5 m cut the car
# 2253→387 tris.  So the coherent chase body needs GPL's actual per-LOD geometry selection, not an
# inclusion rule; logged asset-limited.  front1/front3 (untextured cyan placeholders) are excluded
# unconditionally (pure garbage).  JM_CARP_MAXLAT stays an A/B knob; DEFAULT 0.85 = the coherent clip.
const _GARBAGE_EXC = ("front1","front3")
const CARP_MAXLAT  = parse(Float32, get(ENV,"JM_CARP_MAXLAT","0.85"))   # 0.85 = skinny clip (garbage-free); >1.0 exposes the GPL-hidden spider-leg suspension — see note above
const CARP   = Render.extract_gpl_car(LOT3DO; exclude=(_HAND_EXC...,_LOTBLACK_EXC...,_EXTRA_EXC...,_GARBAGE_EXC...,DRIVER_TEX...,MIRROR_TEX...,Render.STEER_TEX...), exclude_groups=(6600,3560,27288,39792), cockpit_clean=true, maxlat=CARP_MAXLAT, grey=(TUB_GREY,TUB_GREY+0.01f0,TUB_GREY+0.02f0))   # driver body + gauge + windscreen + mirrors drawn separately; hands kept unless JM_HANDS=0.  E64 S4 (D12): groups 27288/39792 are WHOLE DISPLACED ASSEMBLIES (suspension+exhaust+driver textures at y 0.42…1.16 / −1.12…−0.42, mirror copies) — GPL runtime-hidden branches our positioner walk mis-places; they were the chase view's "chrome spider-legs" through the rear tyres
const DRIVERP = Render.extract_gpl_car(LOT3DO; only=DRIVER_TEX, maxlat=0.95f0, exclude_groups=(6600,3560,27288,39792))   # the driver figure — drawn only in CHASE view (occludes the cockpit from the in-car eye).  E64 S4: the displaced assemblies 27288/39792 carry lid/arms-textured tris too — without the group filter they drew as the chase view's remaining "spears"
const GAUGEP = Render.extract_gpl_car(LOT3DO; only=("dash7a",), maxlat=0.85f0)   # gauge cluster — drawn separately, bright (dial faces in the texture's lower-V region; keep default vflip)
const WINDP  = Render.extract_gpl_car(LOT3DO; only=("windlot",), maxlat=0.95f0)  # the plexiglass windscreen — drawn LAST, faintly visible glass, so the suspension shows through (GPL gold standard)
# FRONT SUSPENSION (lsusp1 = the front rocker/wishbone, only in the front groups 6600/3560 — so no
# double-draw with CARP) — drawn with the body so the wishbones show ahead through the plexiglass (PO).
# E75-S7 FIX: this used to read `only=("lsusp1",) … exclude_groups=(6600,3560,27288,39792)` — it
# asked for lsusp1 while excluding EVERY GROUP THAT CONTAINS IT (all 36 tris are in 6600+3560), so
# FSUSPP was empty and the front suspension was drawn NOWHERE (E75-S6). The exclusion was added for a
# real reason — E64-S4's "group 6600 carries 1.65 m-edge lsusp1 garbage 2 m ahead of the car" — but
# aimed at the group rather than the garbage, and took the feature with it.
# Clip the garbage by EXTENT instead: maxedge=1.0 drops the 1.65 m-edge tris and keeps the wishbones
# (a Lotus 49 front wishbone is well under 1 m). JM_FSUSP_OLD=1 restores the empty-FSUSPP behaviour.
const FSUSPP = haskey(ENV,"JM_FSUSP_OLD") ?
    Render.extract_gpl_car(LOT3DO; only=("lsusp1",), maxlat=1.3f0, exclude_groups=(6600,3560,27288,39792)) :
    Render.extract_gpl_car(LOT3DO; only=("lsusp1","frontlot"), maxlat=1.3f0,
                           maxedge=parse(Float32,get(ENV,"JM_FSUSP_MAXEDGE","1.5")))
# Two corrections to the first attempt at this fix, both found by counting instead of eyeballing:
#   (a) maxedge=1.0 dropped ALL of lsusp1 — measured survival 0 / 0 / 4 / 12 / 12 tris at
#       0.5 / 1.0 / 1.5 / 2.0 / Inf. The real wishbone strips have >1 m edges, so a 1.0 clip is not
#       "conservative", it is total. 1.5 keeps 4 and still drops E64-S4's 1.65 m garbage.
#   (b) `only=("lsusp1",)` was too narrow: `frontlot` (94–114 tris) is the bulk of the front end and
#       was ALSO drawn nowhere — same self-defeating exclusion, never noticed because the search was
#       for "suspension" by name.
# ⚠️ maxedge is a blunt instrument here: lsusp1's real geometry and its garbage BOTH have long
# edges, so this separates them only approximately. The precise clip is longitudinal (the garbage
# sits ~2 m ahead of the car) and wants a new extractor parameter — noted, not yet built.
const MIRRORP = Render.extract_gpl_car(LOT3DO; only=MIRROR_DRAW, maxlat=0.95f0)  # rear-view mirrors — clean disc, re-placed on the cowl (see MIRRORMAT)
const HANDP  = Render.extract_gpl_car(LOT3DO; only=("lohand",),  maxlat=0.95f0)  # E64 S2: gloved hands on the rim — ride the wheel rotation
# E64 S7 (D12 residual): the runtime-hidden HIGH-DETAIL rear-suspension assemblies (groups
# 27288/39792 — the S4 exclusions).  S4 mis-read their raw GPL coords as displaced (raw y is
# LATERAL, not up): they are near-correctly authored left/right halves — arms/driveshafts/
# shocks/discs around the rear axle — but ~25% too wide/long (a positioner-scale mis-read:
# shocks reach lateral 1.06 vs the 0.85 wheel face = S4's spear tips through the tyres).
# Drawn separately in the chase view with a tunable corrective scale about the rear axle.
const RSUSPP_A = Render.extract_gpl_car(LOT3DO; include_groups=(27288,), exclude=("ltraymap","lshad"))   # one side each —
const RSUSPP_B = Render.extract_gpl_car(LOT3DO; include_groups=(39792,), exclude=("ltraymap","lshad"))   # the halves carry a residual ±roll our posmat mis-composes
const ARMP   = Render.extract_gpl_car(LOT3DO; only=("lotarms",), maxlat=0.95f0)  # forearms/upper arms — static (their wheel-side ends are what the eye sees)
# The dash panel's normal faces DOWN, so from the driver's eye (above) we see its back → the dials read
# upside-down.  Mirror the gauge in height about its own centre so the dial face turns up toward the eye.
const GCY = (b = Render.parts_bbox(GAUGEP); Float32((b.ymin + b.ymax)/2))
# GPL puts the gauge binnacle UP, just above the wheel hub (gauges read above the badge); dash7a is
# modelled LOW, so lift it (JM_GAUGE_Y) and nudge it back toward the eye (JM_GAUGE_X) onto the cowl.
const GAUGE_DY = parse(Float32, get(ENV,"JM_GAUGE_Y","0.16"))
const GAUGE_DX = parse(Float32, get(ENV,"JM_GAUGE_X","-0.04"))
const GAUGEFLIP = Render.translate(Float32[GAUGE_DX,GCY+GAUGE_DY,0]) * Render.scalexyz(1f0,-1f0,1f0) * Render.translate(Float32[0,-GCY,0])
const SWPARTS, SWCENTER, SWAXIS = Render.extract_gpl_steering(LOT3DO)   # steering wheel + pivot
# Mirrors: GPL gold standard = two round discs LOW at the screen edges (level with the front-tyre
# tops), on outward stalks — NOT high near the wheel.  Mesh frame: x=fwd, y=up, z=lateral (the two
# discs sit at z=±0.36).  So MIRROR_Y lowers them, MIRROR_X moves them fwd, and MIRROR_SPREAD scales
# the z separation to push the pair OUT toward the edges (the old scale=0.62 about z=0 pulled them
# INboard + up — "too high").  Tuned via JM_MIRROR_*.
const MCEN = (b = Render.parts_bbox(MIRRORP); Float32[(b.xmin+b.xmax)/2, (b.ymin+b.ymax)/2, 0f0])
const MIRROR_DY   = parse(Float32, get(ENV,"JM_MIRROR_Y","-0.02"))   # LOWER onto the cowl sides (was +0.10 = too high) — fully-visible discs just above the tub edge
const MIRROR_DX   = parse(Float32, get(ENV,"JM_MIRROR_X","0.075"))
const MIRROR_TILT = deg2rad(parse(Float32, get(ENV,"JM_MIRROR_TILT","-25")))   # E48: stand the discs UPRIGHT facing the eye (+22 read as "angled down" — we saw the top faces)
const MIRROR_SCALE = parse(Float32, get(ENV,"JM_MIRROR_SCALE","0.5"))    # disc SIZE (round-mirror size)
const MIRROR_SPREAD = parse(Float32, get(ENV,"JM_MIRROR_SPREAD","1.7"))   # lateral separation multiplier — push the pair out to the screen edges
const WIND_ALPHA   = parse(Float32, get(ENV,"JM_WIND_ALPHA","1.0"))      # PO: windlot = the tan LEATHER SCUTTLE (the defining GPL cockpit element). The earlier OFF default came from drawing it TRANSLUCENT (read as an angled "plywood board"); drawn OPAQUE (1.0) it is the GPL scuttle sweeping up to the cowl on both sides. JM_WIND_ALPHA<1 makes it glassy again.
# E61/E62 (gold cockpit videos): windlot was drawn bright=0.82/ambfill=0.72 → the lit scuttle wedge reached
# ~0.56 albedo, a glaring olive-GOLD; the gold cockpit scuttle is a MUTED ~0.39 olive-grey.  E61 dimmed to
# 0.60/0.55 but a fresh capture still read glary olive-gold; E62 dims further to 0.45/0.45 so it reads as
# gold's matte tan, not a bright plank (verified vs 260801 cockpit gold).  JM_WIND_B/A tune.
const WIND_B = parse(Float32, get(ENV,"JM_WIND_B","0.45"))
const WIND_A = parse(Float32, get(ENV,"JM_WIND_A","0.45"))
const MIRRORMAT = Render.translate(Float32[MIRROR_DX,MIRROR_DY,0]) *
                  Render.translate(MCEN) * Render.rotz(MIRROR_TILT) * Render.scalexyz(MIRROR_SCALE,MIRROR_SCALE,MIRROR_SCALE*MIRROR_SPREAD) * Render.translate(-MCEN)
println(length(TRACK), " track parts + ", length(CARP), " Lotus body parts")
const BODY_OFF = Float32[-0.55, 0.30, 0.0]     # centre body on X, lift onto the wheels
# Visual suspension-travel gain: amplifies the chassis dive/squat/roll the wheels FLOAT against, so the
# 1967 car's soft suspension reads clearly from the cockpit (the wheels are decoupled — see wheelmat).
const SUSP_GAIN = parse(Float32, get(ENV,"JM_SUSP_GAIN","0.9"))   # PO: cockpit motion must be SUBTLE — just a suggestion — and never rise enough to obscure the road ahead.  Halved from 1.8: the body (and the eye's dynamic gaze shift) pitch/roll/squat far less, so the dash barely moves and the view down the track stays clear.  (No structural camera change — that caused the pogo; this is amplitude only.)
# GPL cockpit head stabiliser (E53): the camera UP follows only the LOW-FREQUENCY chassis tilt.
# A slow road bank rolls the view WITH the car (head → road normal, chassis fixed on screen, horizon
# tilts); a fast jolt (curb strike) does NOT roll the view — the CHASSIS rocks on screen while the head
# stays toward vertical.  So the landscape no longer strobes back-and-forth (which gave the PO a headache).
# τ = the follow time-constant (s): banks held >~τ are fully followed; sub-τ jolts are largely rejected.
const CAM_TILT_TAU = parse(Float64, get(ENV,"JM_CAM_TILT_TAU","0.35"))
# wheel hubs (rig frame X fwd, Y=radius, Z left); front pair steers, all spin.  Front/rear track WIDENED
# (was ±0.62/±0.66) — the Lotus 49 ran ~1.52 m tracks; the narrow stance read as "wheels bolted together".
const WTRACK_F = parse(Float32, get(ENV,"JM_TRACK_F","0.78"))   # front half-track (m) — E62: 0.90 splayed the fronts well outboard of the tub in the chase gold; 0.78 (≈ the real Lotus 49 ~1.52 m track) tucks them back toward the body
const WTRACK_R = parse(Float32, get(ENV,"JM_TRACK_R","0.74"))   # rear half-track (m)
const WHEELS = (( 1.05f0, WTRACK_F,true, 0.31f0,"lotwlf"), ( 1.05f0,-WTRACK_F,true, 0.31f0,"lotwrf"),
                (-1.15f0, WTRACK_R,false,0.34f0,"lotwlr"), (-1.15f0,-WTRACK_R,false,0.34f0,"lotwrr"))

# ---- GL init (visible window on the user's display) ----
const W, H = 1440, 810
# distance culling (squared, render-world units = m): skip far trackside objects/billboards
# per frame so the big layouts (Spa ~5.7k instances, Monza, Nürburgring) keep their FPS.
# Sized larger than small circuits (Zandvoort ~1.3 km) so those cull nothing — visible only
# on the big valleys where the far half-track would otherwise be drawn every frame.
# E60 (D6 mirrored signs): draw trackside OBJECTS back-face-culled like GPL does, with dedup=:orient
# keeping both decals of double-sided signs.  JM_OBJ_CULL=0 restores the two-sided+flip path;
# JM_OBJ_FF flips the winding convention if the culled world renders inside-out (mirror remap parity).
const OBJ_CULLFACE = get(ENV,"JM_OBJ_CULL","0") != "0"
const OBJ_FF_CW    = get(ENV,"JM_OBJ_FF","cw") == "cw"
const OBJ_CULL2 = 2200f0^2      # mesh objects (buildings/grandstands/trees) — keep distant landmarks
const BB_CULL2  = 1300f0^2      # billboards (tree/shrub/crowd sprites) — far ones add little
const SMOKE = haskey(ENV, "JM_SMOKE")     # headless self-test: hidden window, auto-exit
# E59 multi-shot smoke: JM_SHOTS="s:view:name;s:view:name;…" photographs MANY points of the lap in ONE
# session (Julia startup is ~2 min/track — the relaunch, not the render, is the expensive part).
# s = metres along the centreline, view = 0 cockpit / 1 chase, name = output basename.  Each frame lands
# in JM_SHOTS_DIR (default /tmp) as <name>.ppm; after each teleport the render runs JM_SHOT_SETTLE frames
# so the physics/camera/HUD smoothing settle before the dump (38 = the classic single-smoke warmup).
struct SmokeShot; s::Float64; view::Int; name::String; end
const SHOTS = [let f = split(String(spec), ":")
                   SmokeShot(parse(Float64, f[1]), length(f) >= 2 ? parse(Int, f[2]) : 0,
                             length(f) >= 3 ? String(f[3]) : "shot$(i)")
               end for (i, spec) in enumerate(filter(!isempty, split(get(ENV, "JM_SHOTS", ""), ";")))]
const SHOTS_DIR   = get(ENV, "JM_SHOTS_DIR", "/tmp")
const SHOT_SETTLE = parse(Int, get(ENV, "JM_SHOT_SETTLE", "38"))
const CAR3D = !haskey(ENV, "JM_2D")       # full-3D vehicle (heave/pitch/roll + jumps) is the DEFAULT; JM_2D forces the planar model
# physics dispatch — Car3D is field/method-compatible with DriveRT.Car (superset)
build_carX(; kw...)        = CAR3D ? DriveRT3D.build_car3d(; kw...) : DriveRT.build_car(; kw...)
step_carX!(c, a...; kw...) = CAR3D ? DriveRT3D.step_car3d!(c, a...; kw...) : DriveRT.step_car!(c, a...; kw...)
telemetryX(c)              = CAR3D ? DriveRT3D.telemetry3d(c) : DriveRT.telemetry(c)
respawnX!(c; groundz=nothing) = CAR3D ? DriveRT3D.respawn3d!(c; groundz=groundz) : DriveRT.respawn!(c)
containX!(c, x, z; kw...)  = CAR3D ? DriveRT3D.contain3d!(c, x, z; kw...) : DriveRT.contain!(c, x, z; kw...)
bumpX!(c, dvx, dvz, dr, dvy=0.0, dpp=0.0, dq=0.0) = CAR3D ? DriveRT3D.bump3d!(c, dvx, dvz, dr, dvy, dpp, dq) : DriveRT.bump!(c, dvx, dvz, dr)   # GD: collision impulse (+vertical launch + roll/pitch for cartwheels + rear-lift, 3-D)
# AI run the full 3-D physics model too (weight transfer + jumps).  Aliases keep call sites tidy.
const AICarT  = DriveRT3D.Car3D
const AIbuild = DriveRT3D.build_cars3d
const AIyaw   = DriveRT3D.yawrate3d
const AIbump! = DriveRT3D.bump3d!
const AIplace! = DriveRT3D.place3d!
const FENCE = parse(Float64, get(ENV, "JM_FENCE", "13.0"))   # E7: track boundary (m from centreline) — you can't leave the world
const FENCE_GRACE = parse(Float64, get(ENV, "JM_FENCE_GRACE", "2.5"))   # off-HAT distance before the trackside collision fires (tolerates sub-car mesh cracks; small so the fence feels like a wall)
const FENCE_FAR  = parse(Float64, get(ENV, "JM_FENCE_FAR", "16.0"))     # E56: the physical wall contains within a few m; if the car is STILL this far past the edge the wall failed → a last-resort (non-routine) hard containment so it can never escape into the void
# GRASS PENALTY (feel): SOFTENED — at 0.9 the drag scrubbed ~90 %/s of speed, and the 5.5 m threshold
# false-fired on every corner exit (the racing line legitimately uses the FULL track width, reaching the
# tarmac edge at ~5.5 m off the centreline) → the car felt like it was "always on grass" / bogging.  Now
# the threshold clears the widest racing line (only a genuine off-track excursion trips it) and the drag is
# a gentle "slow grass", never a molasses bog.
const GRASS_DRAG = parse(Float64, get(ENV, "JM_GRASS_DRAG", "0.30"))     # grass penalty: per-second velocity loss on the verge (GPL "slow grass") — now AI-only (player uses μ)
const GRASS_SLIP = parse(Float64, get(ENV, "JM_GRASS_SLIP", "0.15"))     # grass penalty: random yaw wobble (reduced grip feel) — AI-only
const GRASS_MU   = clamp(parse(Float64, get(ENV, "JM_GRASS_MU", "0.5")), 0.1, 1.0)   # E56: PLAYER grass = per-wheel tyre friction fraction (a wheel off the surface loses real grip + pulls)
const ROAD_HALFW = parse(Float64, get(ENV, "JM_ROAD_HALFW", "9.0"))      # racing-surface half-width (m); beyond it = grass. Matched to the robust 9 m TrackSurface corridor so the centreline-projection wobble through tight ESSES (Watkins) no longer reads as "on grass" and bogs the car on the real road (E30).
# PO: barriers/haybales/stands LINING the track (centre-to-object ≈ the real ~5.5 m road edge) must be
# SOLID — you can't drive through them.  The old exclusion (ROAD_HALFW−2 = 7 m) was wider than the real
# road, so edge barriers fell inside it and got dropped from SOLIDS.  Exclude collidables only INSIDE the
# real road (this half-width); anything at/beyond the edge stays solid.  JM_SOLID_EXCL_HW tunes it.
const SOLID_EXCL_HW = parse(Float64, get(ENV, "JM_SOLID_EXCL_HW", "4.0"))
# PO: per-name RENDER yaw correction (deg) for mis-oriented grandstands.  Verified the Zandvoort S/F
# `gstand` is ALREADY ~parallel (a +90° test swung it fully ACROSS the track — clearly wrong), so the
# default is 0; the relyaw≈88° reading is just the mesh's reference axis, not the visual length.  The
# knob stays for fine angle tweaks (JM_GSTAND_YAW, deg).  Collision is centre+radius (orientation-free).
const GSTAND_YAW = deg2rad(parse(Float64, get(ENV, "JM_GSTAND_YAW", "0")))
objyawfix(nm) = startswith(lowercase(nm), "gstand") ? GSTAND_YAW : 0.0
const KEEP_GRASS = haskey(ENV, "JM_KEEP_GRASS")    # E17 experiment: render the GPL green grass-cover planes (dropped by default)
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
# E19 (PO): BLUE SKY per iRacing (not GPL overcast).  The old overcast grade (cloud=1, grey horizon)
# seamed against the procedural blue skydome.  Now a clear blue gradient + scattered clouds; the GPL
# horizon ring is cropped to a thin low hill-band (build_horizon) so it no longer walls up into the sky.
const GRADE_ZAND  = ColourGrade((0.24,0.46,0.80),(0.74,0.83,0.92),0.45, (1.07,1.0,0.85),(0.70,0.80,0.98),1.30, (1.12,1.10,1.06))
# E22 (PO): per-track grades vs the GPL gold-standard screenshots on the USB ref drive.
# SPA  — bright blue + puffy white cloud over lush green forest (sunny, saturated green).
# MONZA — hazy bright blue-white daylight (light haze, near-white horizon, thin cloud).
# WATKINS — hazy blue with a warm ring tint for the autumn tree-line.
# NURB  — genuinely STORMY OVERCAST in the gold standard (heavy grey cloud, moody, desaturated);
#         keep the full cloud deck but cool + darken it rather than the blue-sky look.
# E61 (260802 gold VIDEO): the Spa gold sky is a bright but HAZY pale blue (sampled zenith≈(0.64,0.72,0.80)),
# while native rendered it a deep saturated blue (zenith read (0.48,0.63,0.88)).  Pale the zenith/horizon
# (same nudge as Monza MZ1); the lush-green fields/forest (sat 1.34) already match gold, so leave sat.
# JM_GRADE=SPAOLD A/Bs the old deeper blue.
const GRADE_SPA   = ColourGrade((0.40,0.56,0.70),(0.80,0.85,0.90),0.50, (1.07,1.0,0.86),(0.76,0.83,0.94),1.34, (1.10,1.13,1.05))
const GRADE_SPA_OLD = ColourGrade((0.22,0.45,0.82),(0.72,0.82,0.93),0.50, (1.07,1.0,0.85),(0.70,0.80,0.98),1.34, (1.10,1.13,1.05))
# E61 (260802 gold VIDEO): the Monza gold sky is a HAZY PALE blue (sampled zenith≈(0.58,0.69,0.75)),
# not the deeper blue the E22/E58 grade renders (native zenith read (0.52,0.65,0.86) — blue too dominant).
# Pale the zenith + lift a little more cumulus to match; forest green (sat) already reads right.
# JM_GRADE=MONZAOLD A/Bs the old bluer sky.  (The banking/barrier SLABS are geometry — E52, still open.)
const GRADE_MONZA = ColourGrade((0.40,0.57,0.68),(0.86,0.89,0.92),0.42, (1.07,1.02,0.90),(0.74,0.83,0.95),1.16, (1.17,1.15,1.11))
const GRADE_MONZA_OLD = ColourGrade((0.31,0.51,0.80),(0.85,0.90,0.96),0.34, (1.07,1.02,0.90),(0.74,0.83,0.97),1.18, (1.17,1.15,1.11))
# E61 (260802 gold VIDEOS): the Watkins gold sky is a HAZY PALE grey-blue, not the saturated blue+puffy
# cloud the E22/E58 grade drew.  Sampled gold zenith≈(0.70,0.75,0.81), horizon≈(0.79,0.81,0.83) — pale,
# near-neutral, only faintly cool.  Raise zenith toward that pale value + cut its blue dominance, thin the
# cloud deck (haze not cumulus), and drop sat 1.26→1.12 (the old sat made the autumn verge garish yellow).
# Keep the warm ringtint so the horizon autumn-forest band stays coloured.  JM_GRADE=WATK A/Bs the old blue.
const GRADE_WATK  = ColourGrade((0.60,0.66,0.74),(0.80,0.82,0.84),0.28, (1.08,1.02,0.90),(0.82,0.85,0.90),1.12, (1.24,1.15,1.03))
const GRADE_WATK_OLD = ColourGrade((0.28,0.48,0.80),(0.82,0.87,0.93),0.40, (1.10,1.02,0.86),(0.74,0.82,0.96),1.26, (1.21,1.16,1.06))
# E61 (260802 gold VIDEO, full 15-min Nordschleife lap): the video is NOT the uniform dark storm the 3
# GPLMotecAdd stills implied — it is a bright PARTLY-CLOUDY day (dramatic grey cloud over the S/F pit
# complex, opening to blue sky + white cumulus out on the lap) over LUSH GREEN forest.  The old storm
# grade (cloud=1.0 deck, sat 0.88 desaturated, darkened ring) rendered the whole Nordschleife brown/grey.
# Re-green it: sat 0.88→1.10, let blue through (cloud 1.0→0.70, bluer zenith), warm the sun, stop
# darkening the horizon ring so the green forest backdrop reads green.  JM_GRADE=NURBOLD A/Bs the storm.
const GRADE_NURB  = ColourGrade((0.38,0.48,0.62),(0.72,0.76,0.80),0.70, (1.02,1.00,0.92),(0.74,0.80,0.90),1.10, (1.02,1.05,1.00))
const GRADE_NURB_OLD = ColourGrade((0.42,0.48,0.56),(0.66,0.68,0.70),1.0, (0.92,0.92,0.95),(0.72,0.74,0.80),0.88, (0.90,0.91,0.96))
# PO (2026-06-28): REMOVE the blue sky from ALL tracks — the procedural blue skydome seamed against
# the GPL overcast horizon ring (overcast lower sky vs blue upper sky).  One even OVERCAST grade whose
# skydome grey MATCHES the GPL horizon-ring grey → no seam.  Bright ambsky + high sat keep the trackside
# objects VIBRANT (not the "carbonized" look) under the flat overcast light, matching the GPL gold standard.
# NEUTRAL GREY zenith (only a hint cool) — a bluish zenith showed through the GAPS between the
# procedural clouds and still read as "blue sky" (Monza).  Grey gaps + white cloud texture = a flat
# overcast deck at any camera position.
const GRADE_OVERCAST = ColourGrade((0.66,0.67,0.69),(0.76,0.765,0.77),1.0, (1.0,1.0,0.98),(0.88,0.89,0.92),1.12, (1.10,1.10,1.10))
# E58 (graphics QA vs the GPL gold-standard USB shots, 2026-07-05): the GPL gold standard for
# Monza / Spa / Watkins / Zandvoort is BRIGHT BLUE DAYLIGHT, not the flat grey GRADE_OVERCAST the
# earlier seam-avoidance pass fell back to.  The seam it was avoiding (blue skydome walling against
# the overcast horizon ring) is gone now that build_horizon crops the ring to a thin low hill-band —
# verified in scenery_snap.jl across all 4 blue tracks: the ring's autumn/green forest band blends
# cleanly into the blue sky at every camera pitch.  So restore the PO's own per-track sunny grades.
# Nürburgring stays STORMY (its gold standard genuinely is).  JM_GRADE=<NAME> overrides for A/B tests.
# E59 (2026-07-25, canonical gold on BEA6-BBCE): ALL 43 Zandvoort GPL-under-Wine gold shots show a
# FLAT OVERCAST pale-grey sky — not blue.  This also restores the PO's E27 decision ("one overcast
# grade") that E58 had overridden for Zandvoort.  Watkins stays hazy blue and Nürburgring stormy —
# their gold folders agree.  JM_GRADE=ZAND still A/Bs the old blue look.
# E60 (260801 gold VIDEOS, both full laps): the Zandvoort sky is a near-FEATURELESS pale grey — the
# cloud=1.0 procedural deck read as heavy cumulus streaks in every frame and brightened the zenith.
# Zandvoort gets a faint-cloud overcast; JM_CLOUD overrides the coverage for A/B.
const ZAND_CLOUD = parse(Float32, get(ENV,"JM_CLOUD","0.18"))
const GRADE_ZANDOVER = ColourGrade(GRADE_OVERCAST.zenith, GRADE_OVERCAST.horizon, ZAND_CLOUD,
                                   GRADE_OVERCAST.suncol, GRADE_OVERCAST.ambsky, GRADE_OVERCAST.sat,
                                   GRADE_OVERCAST.ringtint)
const GRADE_BYTRACK = Dict("nurburgring"=>GRADE_NURB, "monza"=>GRADE_MONZA, "spa"=>GRADE_SPA,
                           "watglen"=>GRADE_WATK, "zandvoort"=>GRADE_ZANDOVER)
const GRADE_TAB = Dict("OVERCAST"=>GRADE_OVERCAST, "NURB"=>GRADE_NURB, "MONZA"=>GRADE_MONZA,
                       "SPA"=>GRADE_SPA, "WATK"=>GRADE_WATK, "WATKOLD"=>GRADE_WATK_OLD,
                       "NURBOLD"=>GRADE_NURB_OLD, "MONZAOLD"=>GRADE_MONZA_OLD,
                       "SPAOLD"=>GRADE_SPA_OLD, "ZAND"=>GRADE_ZAND,
                       "SUNNY"=>GRADE_SUNNY, "GPL"=>GRADE_GPL, "SKIDPAD"=>GRADE_SKIDPAD)
const GRADE = SKIDPAD ? GRADE_SKIDPAD :
              haskey(ENV, "JM_GRADE") ? get(GRADE_TAB, uppercase(ENV["JM_GRADE"]), GRADE_OVERCAST) :
              get(GRADE_BYTRACK, TRACKSEL, GRADE_OVERCAST)
const ENG = EngineAudio.build_lotus(gamedata = GD)   # GPL Ford DFV V8, RPM-pitched; START is deferred to just before the game loop (below)
tstamp("texture load begins"); print("loading textures… "); flush(stdout)
const TEXIDX = Render.gpl_texture_index(ZD)
trackItems = Render.build_gpl(TRACK, TEXIDX)
# E57: build_gpl is 1:1 with TRACK, but Items drop the texture NAME (GPL parts all carry the same
# fallback grey col) — so classify each track surface HERE from its TrackPart.tex name for the per-
# surface render grade below.  GPL Monza names: road = trrow*/asp* (the over-bright asphalt MIP),
# barriers = armco*/yarmc*/brdg(arm|fen)* (carbonized under the overcast).  Other tracks → :other.
monza_surf(t) = (startswith(t,"trrow") || startswith(t,"asp")) ? :road :
                (startswith(t,"armco") || startswith(t,"yarmc") || startswith(t,"brdgarm") || startswith(t,"brdgfen")) ? :dark :
                occursin(r"^s\d\d", t) ? :bank :    # the sopraelevata banking segments (s07b2, s12l1, …) — over-bright white slabs
                :other
const TRACKCAT = MONZA ? [monza_surf(lowercase(p.tex)) for p in TRACK] : Symbol[]
# E57: in the COMBINED Monza the paddock + banking + road-course corner sections are placed OBJECTS
# (not part of trrow01), drawn at full object brightness ⇒ the paddock/connector pavement glares white
# and the banking deck blinds.  Grade those paved/banking objects by NAME like the track surfaces;
# leave grandstands/towers/ad-boards (front*/tower*/nbnkads*) at the normal bright object grade.
monza_obj_grade(nm) =
    (nm in ("paddock","cgroad","chicane","ascari","bnk_trcr") || occursin(r"^sec\d", nm)) ? :road :
    ((startswith(nm,"nbank")||startswith(nm,"sbank")||startswith(nm,"sbnk")||startswith(nm,"nbnk")||startswith(nm,"bnk")) &&
        !occursin("ads",nm) && !occursin("shel",nm) && !occursin("pep",nm)) ? :bank :
    :keep
# E46: the GPL crowd MIP renders over-BLUE (worst on Zandvoort's main grandstand — garish blue rows).
# A per-draw colour multiply warms + de-blues the grandstand/crowd objects toward varied skin/clothing
# tones (it can't fix the texture's horizontal SMEAR, which is UV/geometry — that needs a re-map).
# Cross-track by name pattern; default tint warms red/green a touch and cuts blue ~22 %.  Tunable.
const CROWD_TINT = (parse(Float32, get(ENV,"JM_CROWD_TR","1.16")),
                    parse(Float32, get(ENV,"JM_CROWD_TG","1.02")),
                    parse(Float32, get(ENV,"JM_CROWD_TB","0.66")))   # E63: the restored fence-crowd rows read garish BLUE at 0.78; 0.66 warms them to gold's tan/khaki varied tones
is_crowd_obj(nm) = occursin("stand", nm) || occursin("tribun", nm) || occursin("crowd", nm) ||
                   occursin("spect", nm) || startswith(nm,"grnd") || startswith(nm,"pplrow") ||
                   startswith(nm,"peprow") || startswith(nm,"plrow") || startswith(nm,"pitpe") ||
                   startswith(nm,"ppl") || startswith(nm,"people") || startswith(nm,"pelf") ||
                   startswith(nm,"p_s")   # E63: the newly-restored fence crowd ROWS get the same warm de-blue tint
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
    global STATICTREES = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32,Float32}[]
    global SOLIDS = Tuple{Float64,Float64,Float64,Symbol}[]   # no collidable trackside objects on skidpad / Nürburgring (scenery baked in) — without this solid_hit()/solid_contact() throws UndefVarError on the first collision check
    global OBJINSTS = Tuple{String,Float32,Float32,Float32,Symbol,Bool}[]   # no placed objects here, but JM_SWEEP/JM_SPOT still need it defined to run the HAT/molasses checks
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
    # E33 (Watkins): the pit/press building (`pitbldg`) sits ~13 m off the racing line at the S/F,
    # and its cantilevered balcony overhangs the road edge ("balcony support protrudes into the road").
    # Nudge any too-close pitbldg OUTWARD (away from the nearest centreline point) so the overhang
    # clears the road.  Per-track + named so no other scenery moves; the collision was already removed
    # by the E31 on_road SOLIDS filter.  Tunable / disable via JM_PITBLDG_PUSH (metres, 0 = off).
    let pitpush = parse(Float64, get(ENV, "JM_PITBLDG_PUSH", TRACKSEL=="watglen" ? "5.0" : "0.0")),   # E58 fix: the track id is "watglen", not "watkinsglen" — so this 5 m S/F pit-building nudge NEVER fired; the balcony/scaffold overhang stayed in the road
        boxpush = parse(Float64, get(ENV, "JM_STARTBOX_PUSH", TRACKSEL=="watglen" ? "6.0" : "0.0"))
        # E58 (PO): the Watkins DUNLOP start/finish gantry (`startbox`, a perpendicular span at the S/F,
        # relyaw≈82°) has its origin only ~5 m right of the racing line, so a leg protrudes into the road.
        # Push it OUTWARD (away from the line) so the whole span clears the track edge.  Per-name distance.
        pushof(nm) = nm=="pitbldg" ? pitpush : nm=="startbox" ? boxpush : 0.0
        if (pitpush > 0.0 || boxpush > 0.0) && !isempty(ALIGNED)
            nearest(ix,iy) = (bd=Inf; bj=1; for (j,p) in enumerate(ALIGNED); d=(p[1]-ix)^2+(p[2]-iy)^2; d<bd && (bd=d; bj=j); end; ALIGNED[bj])
            insts = map(insts) do i
                push = pushof(i.name); push <= 0.0 && return i
                lx,ly = nearest(i.x, i.y); dx=i.x-lx; dy=i.y-ly; d=hypot(dx,dy)
                (d < 1e-3 || d > 18.0) && return i      # only nudge the close copy at the S/F, push outward along the normal
                GPLTrack.ObjInst(i.name, i.x+dx/d*push, i.y+dy/d*push, i.z, i.yaw, i.scale)
            end
        end
    end
    # Trees (tree*/newt*) ship as SINGLE flat textured panels with a chroma-key (green/grey)
    # background — fine in GPL where they're drawn as camera-facing sprites, but as a static
    # MESH our pipeline renders them face-on with raw UVs and no alpha cutout → a tall white
    # "smear" (the famous Watkins pit-straight artifact).  Force these down the BILLBOARD path
    # (clean 0-1 UVs + alpha-keyed cutout, always camera-facing) like Zandvoort's trees.
    treeish(nm) = startswith(nm,"tree") || startswith(nm,"newt")
    # E58 (PO): the Watkins DUNLOP start/finish gantry (`startbox`) bundles a staircase/tower
    # (sfbox01/02/03) + hay bales (hay01/hay02) that reach TOWARD the racing line (object-space z→4.6,
    # while the λ frame + banner stay back at z≤1.6).  In-game they read as "a 2nd lambda + a dark hay
    # bale protruding into the road"; the GPL gold standard shows a single-λ gantry off the road.  Strip
    # those roadward parts from THIS object only (per-name, scoped) — keep the λ frame + DUNLOP banner +
    # marshals.  Toggle/extend via JM_STARTBOX_KEEP=1 (keep everything).
    obj_extra_excl(nm) = (nm=="startbox" && !haskey(ENV,"JM_STARTBOX_KEEP")) ?
        ("sfbox01","sfbox02","sfbox03","hay01","hay02") : ()
    objmesh=Dict{String,Any}(); ymn=Dict{String,Float32}(); ymx=Dict{String,Float32}(); bbinfo=Dict{String,Any}()
    lxmn=Dict{String,Float32}(); lxmx=Dict{String,Float32}(); lzmn=Dict{String,Float32}(); lzmx=Dict{String,Float32}()   # E71-S8 local horizontal AABB
    lverts=Dict{String,Vector{Tuple{Float32,Float32}}}()   # E71-S9 decimated local (x,z) footprint points
    for inst in insts
        (haskey(objmesh, inst.name) || haskey(bbinfo, inst.name)) && continue
        p = objpath(inst.name)
        if p == ""; objmesh[inst.name]=nothing; continue; end
        try
            full = Render.extract_gpl_car(p; track=true, mirror=true)   # un-stripped: decides stub vs geometry
            # E65 S3: the treeish() force flattened every tree strip to a synthesized quad even when
            # the .3do carries REAL geometry — the E22-era anti-wall move, pre-graze-fade.  Monza's
            # strips are FOLDED PANORAMAS (S2 finding) that only render correctly as their real
            # multi-segment mesh, so on MONZA a tree strip with real geometry takes the MESH path
            # (graze-fade applies via istree(); JM_FLATTREES=1 restores the flat panels).
            force_flat = treeish(inst.name) && !((MONZA || WATGLEN || get(ENV,"JM_MESHTREES","0") != "0") && get(ENV,"JM_FLATTREES","0") == "0")   # E65 S4: Watkins joins — same folded-panorama family; JM_MESHTREES=1 forces the mesh path on any track (S5 probes)
            if isempty(full) || force_flat                 # a billboard stub (tree/sprite) — or a tree panel forced to one
                h, wid, strs, aax = Render.billboard_stub(p); bb=nothing
                for s in strs; bb = Render.build_billboard(s, TEXIDX); bb !== nothing && break; end
                bbinfo[inst.name] = bb===nothing ? nothing : (bb[1], bb[2], bb[3], h, wid, aax)   # E65 S2: + authored axis angle
            else
                # E60 (D6) A/B matrix, tested vs the 260801 gold videos — no config wins outright:
                #   old collapse + two-sided + backflip (DEFAULT): VREDESTEIN/DUNLOP-pit mirrored,
                #     MARTINI blank, roofs solid;
                #   JM_OBJ_DEDUP=orient + JM_OBJ_CULL=1 + JM_OBJ_FF=ccw: VREDESTEIN+DUNLOP correct,
                #     MARTINI still blank, S/F grandstand roof gets culling holes;
                #   orient + two-sided (no cull): coincident pairs z-fight (mangled text) — worst.
                # Root cause found: the Tarzan wall is chmp4-1.3do — ONE combo mesh, four boards on
                # the bilbrd01 ad sheet, with per-face winding INCONSISTENT inside the object (Castrol
                # correct while MARTINI flips in every config).  Full closure needs per-face
                # track-aware face selection at scenery-build time (instance transform × centreline).
                parts = Render.extract_gpl_car(p; track=true, mirror=true, dedup=(get(ENV,"JM_OBJ_DEDUP","old")=="orient" ? :orient : true), exclude=(CROWD_TEX..., obj_extra_excl(inst.name)...))  # strip painted-on crowds + per-object roadward parts (E58 startbox)
                if isempty(parts); objmesh[inst.name]=nothing    # was an all-crowd object → drop (NOT a billboard)
                else
                    lo=Inf32; hi=-Inf32; for pp in parts, k in 2:11:length(pp.verts); v=pp.verts[k]; lo=min(lo,v); hi=max(hi,v); end
                    ymn[inst.name]=lo; ymx[inst.name]=hi
                    # E71-S8: HORIZONTAL extent too. E71-S7 showed the asphalt half-width is ~4.1 m
                    # while house43's ORIGIN sits at -6.0 m and yet photographs standing in the road —
                    # only possible if the mesh reaches inward past its origin. Ranking by origin
                    # (E71-S3) therefore cannot find the real offenders. Keep the local x/z bounds so
                    # a footprint can be transformed per instance.
                    xl=Inf32; xh=-Inf32; zl=Inf32; zh=-Inf32
                    for pp in parts, k in 1:11:length(pp.verts)-2
                        vx=pp.verts[k]; vz=pp.verts[k+2]
                        xl=min(xl,vx); xh=max(xh,vx); zl=min(zl,vz); zh=max(zh,vz)
                    end
                    lxmn[inst.name]=xl; lxmx[inst.name]=xh; lzmn[inst.name]=zl; lzmx[inst.name]=zh
                    # E71-S9: the AABB SATURATES — GPL .3do objects are composite (several buildings,
                    # a ground plane, a whole block in one file), so a box around all of it spans the
                    # road wherever the building actually stands, and every instance scored the same
                    # full-road-width penetration (E71-S8). Keep a DECIMATED VERTEX LIST instead: the
                    # true horizontal points, so the lateral min/max is the mesh's, not its bounding
                    # box's. Every ~13th vertex is ample for a footprint and stays cheap.
                    vs = Tuple{Float32,Float32}[]
                    for pp in parts, k in 1:(11*13):length(pp.verts)-2
                        push!(vs, (pp.verts[k], pp.verts[k+2]))
                    end
                    lverts[inst.name] = vs
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
    # off the finite HAT (distant backdrop) the GPL data's own z is used — but it can place buildings
    # floating in the sky; clamp it to the track's vertical extent so they sit on the ground at the horizon.
    # track XY centre — the march target for grounding OFF-HAT backdrop objects.
    TRKCX = sum(p[1] for p in ALIGNED)/length(ALIGNED); TRKCY = sum(p[2] for p in ALIGNED)/length(ALIGNED)
    # OFF-HAT objects (distant backdrop the finite terrain doesn't reach): the GPL authored-z floats
    # buildings in the sky.  March from the object TOWARD the track centre until we hit the HAT, and sit
    # the object at that terrain-EDGE height — so far grandstands/buildings rest on the ground at the
    # horizon instead of hovering above it.  Fall back to the track's low point if the march finds nothing.
    function edgez(x, y)
        dx = TRKCX - x; dy = TRKCY - y; d = hypot(dx, dy)
        d < 1f-3 && return trkzlo
        ux = dx/d; uy = dy/d; s = 0f0
        while s < d
            gz = groundz(x + ux*s, y + uy*s); gz > -900f0 && return gz
            s += 8f0
        end
        trkzlo
    end
    ploz(i)  = (gz = groundz(i.x, i.y); gz > -900f0 ? gz : edgez(Float32(i.x), Float32(i.y)))
    # track's own vertical band (GPL-z, = HAT height) — some classic layouts are authored with a
    # large vertical offset (Spa sits at z≈294..498 m, not ≈0), so a hard-coded height window is
    # wrong.  On-HAT objects are snapped to the terrain ⇒ grounded by construction (always keep);
    # only OFF-HAT objects (authored-z fallback) get a sanity check, relative to the track band.
    trkzlo=Inf32; trkzhi=-Inf32
    for t in TRACKMESH.tris, vi in 1:3; z=Float32(t.p[vi][3]); trkzlo=min(trkzlo,z); trkzhi=max(trkzhi,z); end
    onground(i) = (gz = groundz(i.x, i.y); gz > -900f0 || (trkzlo-150f0 < Float32(i.z) < trkzhi+150f0))
    # E31: drop trackside obstacles that sit ON the racing surface.  GPL authored some object rows
    # ACROSS the road (Monza tree "curtains" the car drives through) + hedge boxes that TRAP the car
    # (the Monza underpass).  An object whose (x,y) projects inside the paved corridor is in the way.
    # Mesh objects that legitimately SPAN the track (bridges/gantries) are kept — only camera-facing
    # tree billboards + collidable SOLIDS are filtered, and solids use a tighter band so genuine
    # apex hay bales / edge barriers survive.
    function on_road(x, y, halfw)
        hr = JuliaMotor.hat(TRKSURF, Float64(x), Float64(y))
        hr.found && abs(hr.lateral) < halfw
    end
    # crowd policy = STANDS ONLY: keep seated grandstand / pit-wall crowds (these read as
    # populated stands, matching the GPL screenshots), drop loose roadside people.
    # E63 (PO: the gold videos show DENSE crowds lining every fence/bank — put them BACK; the earlier
    # D8 "remove spectators" is superseded).  Keep the standing crowd ROWS as populated crowd: Zandvoort
    # ppl_l*/ppl_m*/ppl_s*, Spa p_s*/people*/pelf*, plus generic crowd/spect.  The onroad_crowd filter
    # below still drops any row that projects onto the paved surface (E40 people-in-the-road), and single
    # loose figures (marshals/photographers: flagger/rescu/photo/fotograf/pform/named) stay dropped in drop().
    standcrowd(nm) = startswith(nm,"grndpe") || startswith(nm,"pitpeo") || startswith(nm,"pitppl") ||
                     startswith(nm,"pplrow") || startswith(nm,"peprow") || startswith(nm,"plrow") ||
                     startswith(nm,"ppl") || startswith(nm,"people") || startswith(nm,"pelf") ||
                     startswith(nm,"p_s") || startswith(nm,"spect") || startswith(nm,"crowd") ||
                     startswith(nm,"grndp")
    # drop: ground-cover planes (grass/herbe/infield), white "fuel-tank" tents, infield/backdrop
    # tree smears, and LOOSE people only — marshals, photographers, rescue crews, lone figures,
    # and standing roadside spectators (Spa people*/pelf*).  Seated stand crowds are kept above.
    _droptest = split(get(ENV,"JM_DROPTEST",""), ',', keepempty=false)   # diagnostic: drop comma-listed name PREFIXES
    _keeptest = split(get(ENV,"JM_KEEPTEST",""), ',', keepempty=false)   # diagnostic: FORCE-KEEP comma-listed name prefixes past every drop rule (WG3 forensics)
    drop(nm) = (!isempty(_keeptest) && any(p->startswith(nm,p), _keeptest)) ? false :
               (!isempty(_droptest) && any(p->startswith(nm,p), _droptest)) || (!standcrowd(nm) && (
               (startswith(nm,"grass") && !KEEP_GRASS) || (startswith(nm,"herbe") && !KEEP_GRASS) || nm == "infield" ||
               nm == "hotels" ||                                             # E45: Zandvoort backdrop building cluster — a 310 m garbage bbox that never grounds → floats in the sky above the grandstand; the horizon ring + dunes carry the backdrop without it
               startswith(nm,"tent") || startswith(nm,"single") ||
               (startswith(nm,"intree") && !WATGLEN) ||                      # INFIELD tree lines (100s of m wide) → distant central "smear".  WG3 (E64 S5): on WATKINS these + treefill/treesrb ARE the gold's close roadside autumn forest — the smear objection predates graze-fade (MZ3), which fixed it; kept there now
               ((startswith(nm,"treesrb") || startswith(nm,"treefill")) && !WATGLEN) ||  # forest-BACKDROP / gap-fill quads → streaky "painted tree" smear (non-Watkins; see WG3 note above)
               startswith(nm,"trbk") || startswith(nm,"brbk") ||             # Monza underpass tree/bush BANKS (trbk1-8/brbk1-3 at lapdist ~3100-3440, lat ~5 m) — MESH foliage that bypasses the sprite on-road filter and renders as dark vertical smears ACROSS the road (PO round 4: "7 stands of trees across the track near the underpass")
               startswith(nm,"tuntbk") ||                                    # tunnel-edge tree bank (same dark-smear foliage by the underpass)
               startswith(nm,"ppl") || startswith(nm,"people") || startswith(nm,"pelf") ||  # loose standing spectators
               startswith(nm,"p_s") || startswith(nm,"pform") ||             # Spa distributed standing-spectator sprites (p_s1..19 = p_s1srb, ~900) + pform1 (foreground photographer); NB not p_armco/p_*
               nm in ("chrisa","sergioa","thomasa","hatzia","stefana","starter") ||  # Spa named loose figures (Chris/sergio/thomas/Hatzi/Stefan/starter) — NOT prinz*/spider* (cars)
               startswith(nm,"grndp") || startswith(nm,"crowd") || startswith(nm,"spect") ||
               startswith(nm,"flagger") || startswith(nm,"rescu") ||
               startswith(nm,"photo") || startswith(nm,"fotograf")))         # marshals/photographers = loose people
    istree(nm) = startswith(nm,"tree") || startswith(nm,"newt") || startswith(nm,"intree")  # foliage → graze-fade (no end-on smear)
    # E40: a kept STAND crowd row must not sit on the paved racing surface — at Spa the peprow* rows
    # by Eau Rouge (and on the start straight) projected to |lat| < ROAD_HALFW = a "line of people
    # standing in the road".  Drop crowd that lands on the road; the grandstands (set further back) stay.
    onroad_crowd(i) = standcrowd(i.name) && on_road(i.x, i.y, ROAD_HALFW)
    # E68 S8 (PO: Spa "oversized buildings right on the track — you drive through them").
    # lasad1's centroid sits 0.6 m from the road centre at s=13641.  A BUILDING centred on
    # the corridor cannot be right; drop building-family meshes with |lat| < 4 m (logged).
    bldgish(nm) = startswith(nm,"lasad") || startswith(nm,"chut") || startswith(nm,"haus") ||
                  startswith(nm,"house") || startswith(nm,"ferme") || startswith(nm,"bldg") ||
                  startswith(nm,"hotel") || startswith(nm,"bld")
    onroad_bldg(i) = bldgish(lowercase(i.name)) && begin
        hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
        hit = hr.found && abs(hr.lateral) < 4.0
        hit && println("  E68: building ", i.name, " centred ON the road (lat=", round(hr.lateral,digits=1), " m, s=", round(Int,hr.lapdist), ") — dropped")
        hit
    end
    # E68 S1 (PO re-drive): "every perpendicular block of spectators was floating in air or on
    # the track."  JM_CROWDDIAG confirms: Zandvoort keeps 97 crowd rows of which a dozen+ sit
    # PERPENDICULAR (relyaw ≈ ±90°) within ~18 m of the road at exactly the PO's spots (Tarzan
    # ~130–520, east loop ~3100, Bos Uit ~3950–4035; Watkins big bend ~1492).  A perpendicular
    # row near the road can only be GPL cross-placement garbage — real fence crowds run PARALLEL.
    perp_crowd(i) = standcrowd(i.name) && begin
        hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
        if hr.found && abs(hr.lateral) < ROAD_HALFW + 12.0
            ry = abs(rad2deg(rem2pi(Float64(i.yaw) - atan(-hr.perp[2], hr.perp[1]), RoundNearest)))
            60.0 <= ry <= 120.0
        else
            false
        end
    end
    # E68 S2 (PO: Monza "haze planes make the forest absent, then fade into view"): uGraze was
    # built to fade FLAT panels seen edge-on; on the E65 real folded tree MESHES it fades whole
    # forest walls with view angle.  Mesh-path trees (MONZA/WATGLEN) draw un-grazed — a folded
    # strip has no edge-on smear to hide.  JM_GRAZE_MESH=1 restores the old fade for A/B.
    graze_mesh = get(ENV,"JM_GRAZE_MESH","0") != "0"
    global OBJECTS = [(objmesh[i.name], Render.translate(Float32[i.x, ploz(i), -i.y]) * Render.roty(Float32(-i.yaw + objyawfix(i.name))), istree(i.name) && (graze_mesh || !(MONZA || WATGLEN)), (Float32(i.x), ploz(i), Float32(-i.y)), lowercase(i.name))
                      for i in insts if get(objmesh,i.name,nothing) !== nothing &&
                          !drop(i.name) && !onroad_crowd(i) && !perp_crowd(i) && !onroad_bldg(i) && (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && onground(i)]
    # E15: SOLID trackside objects the car can hit — (physics x, z, collision radius m).  Buildings,
    # barriers/hedges (haybales = Zandvoort `haie`), towers, parked vehicles.  NOT trees/signs/people.
    solidR(nm) = startswith(nm,"hut")||startswith(nm,"pitbldg")||startswith(nm,"hotel")||startswith(nm,"bigbosch")||nm=="mega2"||startswith(nm,"longtent")||
                 startswith(nm,"chut")||startswith(nm,"lasad")||startswith(nm,"haus")||startswith(nm,"house")||startswith(nm,"ferme") ? 5.0 :   # E68 S8: Spa houses are solid (no drive-through)
                 startswith(nm,"gstand")||startswith(nm,"grand")||startswith(nm,"tribun")||startswith(nm,"camstnd")||startswith(nm,"mgrand") ? 6.0 :   # PO: grandstands are SOLID (no driving through the stands)
                 startswith(nm,"tower")||startswith(nm,"megafon") ? 2.0 :
                 startswith(nm,"haie")||startswith(nm,"bush")||startswith(nm,"shrub")||startswith(nm,"hedge")||startswith(nm,"haystk") ? 1.5 :   # hay rows + trackside bushes/hedges (PO: more objects hittable when you run wide — soft, you plough through with a penalty).  SMALL radius so they don't clip the racing groove
                 startswith(nm,"armco")||startswith(nm,"barrier")||startswith(nm,"fence")||startswith(nm,"wall") ? 1.2 :
                 startswith(nm,"caravn")||startswith(nm,"vwvan")||startswith(nm,"ftruck")||startswith(nm,"ambul")||nm=="car2"||startswith(nm,"rescu") ? 2.4 : 0.0
    global SOLIDS = Tuple{Float64,Float64,Float64,Symbol}[]
    for i in insts
        nml = lowercase(i.name)
        r = solidR(nml); (r <= 0.0 || !onground(i)) && continue
        on_road(i.x, i.y, SOLID_EXCL_HW) && continue   # E31: don't make a collidable wall ON the road (the trapping hedge-box) — but DO keep edge barriers/haybales solid (PO)
        push!(SOLIDS, (Float64(i.x), Float64(i.y), r, solidkind(nml)))   # E56: tag wall vs hedge/hay for the contact law
    end
    if get(ENV,"JM_SOLIDDIAG","")!=""
        nm_solid = sort([(i.name, solidkind(lowercase(i.name))) for i in insts
                         if solidR(lowercase(i.name)) > 0.0 && onground(i) && !on_road(i.x, i.y, SOLID_EXCL_HW)], by=x->x[1])
        cnt = Dict{String,Int}(); for (n,_) in nm_solid; cnt[n]=get(cnt,n,0)+1; end
        println("== JM_SOLIDDIAG ", length(SOLIDS), " solids: ", join(["$(n)×$(c)" for (n,c) in sort(collect(cnt))], ", "))
    end
    # billboards: (Item, render-pos base, width, height) — drawn camera-facing per frame.
    # WIDE panoramic forest strips (GPL Watkins `tree*` 80–380 m across, authored as one big
    # quad) must NOT be camera-faced — a 380 m sprite swung to face the eye becomes a giant flat
    # "wall" across the view.  They're STATIC backdrop panels: draw at their AUTHORED yaw (lining
    # the forest edge) with the clean alpha-keyed billboard quad + graze-fade.  Only narrow
    # individual-tree / sign sprites stay camera-facing.
    WIDE_PANEL = parse(Float32, get(ENV,"JM_WIDE_PANEL","30"))
    # KEEP the wide forest panels on MONZA (PO round 4: "once you leave the grandstands you're driving on a
    # ribbon of road over a void/desert — need all the roadside trees back").  Monza's tree line (trees01-23,
    # 100-160 m strips) is what fills the void around the road; its horizon ring doesn't carry trees the way
    # Watkins' does.  Drawn as STATIC authored-yaw backdrop panels (graze-fade), they line the circuit without
    # the camera-faced "wall".  Other tracks keep the default (drop, let the horizon ring carry the tree-line).
    # WG3 (E64 S5): WATKINS joins Monza — its tree3-18 strips (19-39 m tall × 78-380 m wide) ARE
    # the gold's dense roadside autumn forest; as static authored-yaw graze-faded panels (MZ3)
    # they line the circuit without the old camera-faced "wall" / edge-on smear.
    DROP_FOREST = get(ENV,"JM_DROP_FOREST", (MONZA || WATGLEN) ? "0" : "1")!="0"
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
    global STATICTREES = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32,Float32}[]
    for i in insts
        bb = get(bbinfo, i.name, nothing); (bb === nothing || drop(i.name) || (standcrowd(i.name) && on_road(i.x, i.y, ROAD_HALFW+1.0))) && continue   # E68 S8b: billboard crowds drop only when ON the road (perp test is mesh-path-only — camera-facing sprites have no rendered yaw)
        onground(i) || continue
        on_road(i.x, i.y, ROAD_HALFW) && continue   # E31: drop sprites planted ON the road (the Monza tree "curtain" across the track)
        gz = ploz(i)
        item, tw, th, h, wid, aax = bb
        w = wid > 0f0 ? wid : h*tw/max(th,1f0)
        # E65 S2 verdict: the authored-axis experiment (farthest vertex pair → panel yaw) moved some
        # strips right (Lesmos left flank ≈ gold) but broke others incl. a Watkins canopy REGRESSION —
        # these strips are FOLDED PANORAMAS, so no single flat-quad yaw can represent them; the
        # farthest-pair axis is a diagonal across the fold.  Proper fix (E65-3, logged): build the
        # strip item from the stub's REAL vertex geometry (multi-segment), as GPL draws it.
        # Until then aax is measurement-only (JM_AAX=1 experiments); shipped behaviour = S1.
        eyaw = Float64(i.yaw) + (get(ENV,"JM_AAX","0") != "0" ? Float64(aax) : 0.0)
        if w > WIDE_PANEL
            # WIDE panoramic forest strip (80–380 m).  These duplicate the distant forest already
            # baked into the GPL horizon ring AND can only render as a near-field "wall" (face-on) or
            # an edge-on smear — the famous Watkins pit-straight artifact.  Drop them by default and
            # let the horizon ring carry the tree-line (JM_DROP_FOREST=0 → keep as static panels).
            # E65 S1: a kept panel must not CROSS the road corridor — Monza's trees14 (21×84 m) runs
            # its span over the Lesmos approach and canopies the cockpit where the gold shows open
            # sky.  The E31 centre test can't see it (the strip's CENTRE is 25 m off-road), so sample
            # along the strip's authored axis and drop any panel with a sample on the corridor.
            # A mere corridor-entry test over-fires (first cut dropped 33/53 Monza panels —
            # roadside strips along CURVES graze the corridor at their ends).  A true offender
            # CROSSES the road: samples on BOTH sides of the centreline while near it.
            spans_road = false
            if !DROP_FOREST
                # E65 S2: sample along the strip's EFFECTIVE axis (authored mesh axis + placement
                # yaw) — measured directly in the GPL frame, no render-convention gymnastics.
                sx, sy = cos(eyaw), sin(eyaw)
                sawpos = false; sawneg = false
                for f in -0.5:0.0625:0.5
                    hr = JuliaMotor.hat(TRKSURF, Float64(i.x + sx*f*w), Float64(i.y + sy*f*w))
                    (hr.found && abs(hr.lateral) < ROAD_HALFW) || continue
                    hr.lateral >= 0 ? (sawpos = true) : (sawneg = true)
                    if sawpos && sawneg; spans_road = true; break; end
                end
                spans_road && println("  E65: forest panel ", i.name, " (", round(Int,h), "×", round(Int,w), " m) CROSSES the road — dropped")
            end
            # render yaw: the panel's local x-axis under roty(ψ) maps to GPL (cos ψ, −sin ψ), so
            # ψ = −eyaw reproduces the measured axis (old code: −i.yaw, i.e. aax silently 0).
            (DROP_FOREST || spans_road) || push!(STATICTREES, (item, (Float32(i.x), gz, Float32(-i.y)), Float32(w), Float32(h), Float32(-eyaw)))
        else
            push!(BILLBOARDS, (item, (Float32(i.x), gz, Float32(-i.y)), Float32(w), Float32(h)))
        end
    end
    # Named instance table (name, world-x, world-z, base-y, kind, dropped?) for the JM_START_S
    # spot diagnostic — lets a mid-lap render report exactly which authored objects sit near the
    # car, even when their CENTROID is >13 m off-centreline but the mesh spans the road (E52: the
    # wide grandstand/wall whose centroid clears the on_road filter yet its extent blocks the track).
    # (name, world-x, world-z, base-y, RENDER fate, is-SOLID).  The fate mirrors the SAME filters that
    # build OBJECTS / BILLBOARDS / SOLIDS — drop(), onroad_crowd, on_road and onground — so the JM_SWEEP
    # harness sees exactly what is actually rendered / collidable (not the raw instance list).
    # NB store world-z in the PHYSICS / HAT / .trk frame (= GPL y, NOT the render frame's −y) so the
    # JM_SWEEP / JM_SPOT projections onto TRKSURF/CLINE match the on_road classifier exactly.
    global OBJINSTS = [begin
        ismesh = get(objmesh,i.name,nothing) !== nothing; isbb = get(bbinfo,i.name,nothing) !== nothing; og = onground(i)
        kmesh  = ismesh && !drop(i.name) && !onroad_crowd(i) && !perp_crowd(i) && (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && og
        kbb    = isbb   && !drop(i.name) && !(standcrowd(i.name) && on_road(i.x, i.y, ROAD_HALFW+1.0)) && og && !on_road(i.x, i.y, ROAD_HALFW)   # E68 S8b: billboard crowds are camera-facing (yaw meaningless) — drop only when ON the road; perp_crowd wiped Spa's Eau Rouge line
        issolid = solidR(lowercase(i.name)) > 0.0 && og && !on_road(i.x, i.y, SOLID_EXCL_HW)
        (i.name, Float32(i.x), Float32(i.y), ploz(i), kmesh ? :mesh : kbb ? :bb : :dropped, issolid)
    end for i in insts]
    if get(ENV,"JM_FOOTPRINT","")!=""
        # E71-S8: rank objects by how far their FOOTPRINT penetrates the asphalt, not by how far
        # their ORIGIN sits from the centreline. E71-S4 showed the origin ordering is not the
        # "is it in the way" ordering (bu5 at +6.3 m is off the road, house43 at -6.0 m is on it),
        # and E71-S7 put the asphalt edge at ~4.1 m. Transform each instance's local AABB corners by
        # its own roty+translate, project through hat, and report the lateral span.
        edge = parse(Float64, get(ENV,"JM_ASPHALT_HALFW","4.1"))
        rows = NTuple{6,Any}[]
        for i in insts
            haskey(lverts, i.name) || continue
            drop(i.name) && continue
            isempty(lverts[i.name]) && continue
            th = -Float64(i.yaw) + Float64(objyawfix(i.name))
            c, sn = cos(th), sin(th)
            lats = Float64[]
            for (lx, lz) in lverts[i.name]
                rx =  lx*c + lz*sn
                rz = -lx*sn + lz*c
                hr = JuliaMotor.hat(TRKSURF, Float64(i.x) + rx, Float64(i.y) - rz)
                hr.found && push!(lats, hr.lateral)
            end
            isempty(lats) && continue
            lo, hi = minimum(lats), maximum(lats)
            # E71-S9b: penetration = how close the NEAREST vertex gets to the centreline, NOT the
            # lateral SPAN intersected with the road. The span metric conflated laterals measured at
            # DIFFERENT lapdists: a 16 m-wide building beside a curve has one corner projecting at
            # lapdist X and another at Y, and min/max across them describes no real geometry — which
            # is why it still saturated at exactly the full road width for every instance after the
            # AABB fix. A vertex is on the asphalt iff |lateral| < edge, so the honest measure is
            # edge − min|lateral|.
            near = minimum(abs.(lats))
            pen = max(0.0, edge - near)
            hr0 = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            pen > 0.05 && push!(rows, (i.name, round(near,digits=1), round(hi,digits=1), round(pen,digits=1),
                                       hr0.found ? round(hr0.lapdist,digits=0) : -1.0,
                                       hr0.found ? round(hr0.lateral,digits=1) : 999.0))
        end
        sort!(rows, by=x->-x[4])
        println("== E71-S8 footprints crossing the asphalt (edge ±", edge, " m) — ", length(rows), " instances ==")
        println("   name            near|lat|  lat_hi   PENETRATION  lapdist   origin_lat")
        for r in rows[1:min(end,30)]
            println("   ", rpad(r[1],16), rpad(r[2],8), rpad(r[3],8), rpad(r[4],13), rpad(r[5],10), r[6])
        end
        # E71-S10: is a flagged building an OVERSIZED SINGLE house, or a COMPOSITE .3do whose second
        # building happens to sit near the road? Both put a mesh vertex on the asphalt from an origin
        # 6 m away, and they need opposite fixes: rescale the mesh vs. re-anchor/split the object.
        # The local AABB answers it — a cottage is ~10 m across; 40 m means the file holds a block.
        println("   -- local mesh extents of the flagged buildings (w x d x h, m) --")
        seenb = Set{String}()
        for r in rows
            occursin(r"^(house|bu\d|casa|clhouse|eauhotel|ho\d)", r[1]) || continue
            r[1] in seenb && continue; push!(seenb, r[1])
            haskey(lxmn,r[1]) || continue
            w = lxmx[r[1]]-lxmn[r[1]]; d = lzmx[r[1]]-lzmn[r[1]]; h = get(ymx,r[1],0f0)-get(ymn,r[1],0f0)
            npts = haskey(lverts,r[1]) ? length(lverts[r[1]]) : 0
            println("      ", rpad(r[1],12), rpad(round(w,digits=1),8), "x ", rpad(round(d,digits=1),8),
                    "x ", rpad(round(h,digits=1),7), "  pts=", npts,
                    (w>25 || d>25) ? "   <-- COMPOSITE (too big for one building)" : "")
            length(seenb) > 14 && break
        end
        bl = filter(r -> occursin(r"^(house|bu\d|casa|clhouse|eauhotel)", r[1]), rows)
        println("   -- of which BUILDINGS: ", length(bl))
        for r in bl[1:min(end,15)]
            println("      ", rpad(r[1],16), "pen=", rpad(r[4],7), "lapdist=", rpad(r[5],10), "origin_lat=", r[6])
        end
        flush(stdout)
    end
    if get(ENV,"JM_SPOTMESH","")!=""
        # E73-S3: name whatever is covering the road. E73-S2 found a ~300 m stretch of Monza
        # (s≈350–650) with NO road surface — the car floats over a pale sheet — confirmed
        # independently by the width census having no bucket at s=500. The leading hypothesis is
        # E52's note that Monza's BANKING is a large mesh ABOVE the road, excluded from the collision
        # HAT because "the road passes under it": a car beneath it would see its underside fill the
        # frame. Test it by listing every track-mesh triangle near a lapdist with its texture and
        # HEIGHT — banking overhead shows up as a distinct high band, missing road as an absence.
        # JM_SPOTMESH="500,1500" (comma-separated lapdists).
        for tok in split(get(ENV,"JM_SPOTMESH",""), ",")
            isempty(strip(tok)) && continue
            want = parse(Float64, strip(tok))
            acc = Dict{String,Vector{Float64}}(); lats = Dict{String,Vector{Float64}}()
            for t in TRACKMESH.tris
                cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
                cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
                cz = (Float64(t.p[1][3])+Float64(t.p[2][3])+Float64(t.p[3][3]))/3
                hr = JuliaMotor.hat(TRKSURF, cx, cy)
                (hr.found && abs(hr.lapdist - want) < 40.0 && abs(hr.lateral) < 30.0) || continue
                lt = lowercase(t.tex); lt = lt=="" ? "<none>" : lt
                push!(get!(acc, lt, Float64[]), cz)
                push!(get!(lats, lt, Float64[]), hr.lateral)
            end
            println("== JM_SPOTMESH lapdist ", want, " ±40 m, |lat|<30 m — meshes present ==")
            println("   texture          tris   z_min    z_mean   z_max    lat range        road?")
            if isempty(acc); println("   (nothing found)"); end
            for (lt,zs) in sort(collect(acc), by=x->-length(x[2]))
                ls = lats[lt]
                println("   ", rpad(lt,16), rpad(length(zs),7),
                        rpad(round(minimum(zs),digits=1),9), rpad(round(sum(zs)/length(zs),digits=1),9),
                        rpad(round(maximum(zs),digits=1),9),
                        rpad(string(round(minimum(ls),digits=1),"..",round(maximum(ls),digits=1)),17),
                        ROAD_TEX(lt) ? "ROAD" : "")
            end
            flush(stdout)
        end
    end
    if get(ENV,"JM_ROADTEX_CENSUS","")!=""
        # First-pass finding (E70/E72/E73): ROAD_TEX recognises Spa's road (9658 tris, uniform
        # 8.2 m) but only a quarter of Watkins' and Monza's, so JM_ROADWIDTH returns nonsense there
        # (medians of 3.7 m and 0.6 m against healthy buckets of 10.9 m and 13.1 m) and every
        # width-dependent verdict on those tracks is unsupported. ROAD_TEX is a NAME list, tuned for
        # GPL and Ring naming; the fix is to learn the names each track actually uses rather than
        # guess more prefixes. Tally the textures of triangles lying within |lat| < 5 m of the
        # centreline — whatever surfaces the car drives on IS the road, whatever it is called.
        near = Dict{String,Int}(); far = Dict{String,Int}()
        for t in TRACKMESH.tris
            cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
            cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
            hr = JuliaMotor.hat(TRKSURF, cx, cy)
            hr.found || continue
            lt = lowercase(t.tex)
            if abs(hr.lateral) < 5.0
                near[lt] = get(near,lt,0) + 1
            elseif abs(hr.lateral) < 25.0
                far[lt] = get(far,lt,0) + 1
            end
        end
        println("== ROAD_TEX census: textures of tris within |lat| < 5 m of the centreline ==")
        println("   (recognised? = does the current ROAD_TEX classifier accept the name)")
        for (lt,n) in sort(collect(near), by=x->-x[2])[1:min(end,18)]
            println("   ", rpad(lt=="" ? "<none>" : lt, 16), rpad(n,7),
                    ROAD_TEX(lt) ? "recognised" : "*** MISSED ***",
                    "   (off-road count ", get(far,lt,0), ")")
        end
        tot = sum(values(near)); rec = sum(n for (lt,n) in near if ROAD_TEX(lt); init=0)
        println("   --> ", rec, "/", tot, " near-centreline tris recognised (",
                tot>0 ? round(100rec/tot,digits=1) : 0.0, "%)")
        flush(stdout)
    end
    if get(ENV,"JM_ROADWIDTH","")!=""
        # E71-S7: measure the RENDERED road width in METRES, from the mesh — not from pixels.
        # E71-S6 measured gold's Spa road at ~11 m using the Lotus as a ruler, but could not measure
        # the native one: at the car's row the road leaves the frame, and the two chase cameras sit at
        # different distances so ratios from different rows are not comparable. Geometry has neither
        # problem. For each sample lapdist, take every ROAD_TEX triangle vertex whose projection lands
        # within ±HALF a bucket of it and report the lateral min/max — that IS the asphalt edge.
        # Two open questions fall out at once: does the visual road match gold's 11 m, and where does
        # the real edge sit for re-filtering the 372-object candidate list (E71-S3/S4).
        step = parse(Float64, get(ENV,"JM_ROADWIDTH_STEP","500"))
        # Default 12.0, not 3.0. At ±3 m a bucket catches only a thin slice of the ribbon, and on
        # tracks whose road carries a NARROW `groove` racing-line strip a bucket can end up holding
        # groove vertices ONLY — so the "width" measured is the groove's, not the road's. That is why
        # Monza reported a 0.6 m median and Watkins 3.7 m while Spa (denser road mesh) reported a
        # sound 8.2 m. Widening the bucket fixed all three at once: Monza 0.6 -> 11.6 m, Watkins
        # 3.7 -> 10.1 m, Spa 8.2 -> 8.5 m (i.e. Spa barely moves, which is the check that the change
        # is a coverage fix and not a thumb on the scale).
        halfb = parse(Float64, get(ENV,"JM_ROADWIDTH_BUCKET","12.0"))
        buckets = Dict{Int,Vector{Float64}}()
        nrt = 0
        for t in TRACKMESH.tris
            ROAD_TEX(lowercase(t.tex)) || continue
            nrt += 1
            for vi in 1:3
                x = Float64(t.p[vi][1]); y = Float64(t.p[vi][2])
                hr = JuliaMotor.hat(TRKSURF, x, y)
                hr.found || continue
                b = round(Int, hr.lapdist / step)
                r = hr.lapdist - b*step
                abs(r) <= halfb || continue
                push!(get!(buckets, b, Float64[]), hr.lateral)
            end
        end
        println("== E71-S7 rendered road width from the mesh (ROAD_TEX tris=", nrt,
                ", bucket ±", halfb, " m, step ", step, " m) ==")
        println("   lapdist    lat_min   lat_max    WIDTH    n")
        tot = Float64[]
        for b in sort(collect(keys(buckets)))
            v = buckets[b]; length(v) >= 6 || continue
            lo, hi = minimum(v), maximum(v)
            push!(tot, hi-lo)
            println("   ", rpad(b*step,10), rpad(round(lo,digits=1),10), rpad(round(hi,digits=1),10),
                    rpad(round(hi-lo,digits=1),9), length(v))
        end
        if !isempty(tot)
            st = sort(tot)
            println("   --> median width ", round(st[cld(end,2)],digits=1), " m   min ",
                    round(minimum(tot),digits=1), "   max ", round(maximum(tot),digits=1),
                    "   (gold Spa measured ~11 m, E71-S6)")
        end
        flush(stdout)
    end
    if get(ENV,"JM_TEXDIAG","")!=""
        # track-mesh textures by HEIGHT band — to spot the Monza banking surface (a large mesh high
        # above the road) so it can be excluded from the collision HAT (E52: road passes under it).
        th = Dict{String,Vector{Float32}}()
        for t in TRACKMESH.tris, vi in 1:3; push!(get!(th,t.tex,Float32[]), Float32(t.p[vi][3])); end
        rows = [(tex, length(zs)÷3, minimum(zs), sum(zs)/length(zs), maximum(zs)) for (tex,zs) in th]
        sort!(rows, by=r->-r[4])
        println("== JM_TEXDIAG track-mesh textures by mean height (tex  ntri  zmin  zmean  zmax) ==")
        for (tex,n,zmn,zmu,zmx) in rows; println("   ", rpad(tex=="" ? "<none>" : tex,14), rpad(n,7), " zmin=", rpad(round(zmn,digits=1),8), "zmean=", rpad(round(zmu,digits=1),8), "zmax=", round(zmx,digits=1)); end
        flush(stdout)
    end
    if get(ENV,"JM_OBJDIAG","")!=""
        # E71-S5: is GPL's PER-INSTANCE SCALE being honoured?  The PO reports that the Spa houses
        # standing on the road are "often also scaled up compared to gold standard", and the OBJECTS
        # transform built below is translate * roty with NO scale term, while ObjInst carries a
        # `scale` field parsed from the .3do positioner (gpltrack.jl, word [10]).  If GPL authors
        # scale != 1 for these instances, every one of them renders at the wrong size — and an
        # oversized building's FOOTPRINT spills onto the road even when its origin is correctly off
        # it, which would make "too big" and "on the road" the same defect rather than two.
        let sc = [i.scale for i in insts]
            nz = count(x -> !(0.999 <= x <= 1.001), sc)
            println("== E71-S5 instance scale: n=", length(sc), "  min=", round(minimum(sc),digits=3),
                    "  max=", round(maximum(sc),digits=3), "  mean=", round(sum(sc)/length(sc),digits=3),
                    "  non-unity=", nz, " (", round(100nz/length(sc),digits=1), "%)")
            hs = [(i.name, i.scale) for i in insts if occursin(r"^(house|bu\d|casa)", i.name)]
            if !isempty(hs)
                hv = [x[2] for x in hs]
                println("   buildings only: n=", length(hs), "  min=", round(minimum(hv),digits=3),
                        "  max=", round(maximum(hv),digits=3), "  mean=", round(sum(hv)/length(hv),digits=3))
                for nm in ("house43","house29","house26","house4","bu5")
                    v = [x[2] for x in hs if x[1]==nm]
                    isempty(v) || println("     ", rpad(nm,10), "n=", rpad(length(v),5),
                                          "scale ", round(minimum(v),digits=3), " … ", round(maximum(v),digits=3))
                end
            end
            flush(stdout)
        end
        kn = unique([i.name for i in insts if get(objmesh,i.name,nothing)!==nothing && !drop(i.name) && onground(i)])
        tall = sort([(nm, get(ymx,nm,0f0)-get(ymn,nm,0f0)) for nm in kn], by=x->-x[2])
        println("== JM_OBJDIAG tallest kept geometry objects =="); for (nm,h) in tall[1:min(end,25)]; println("   ", rpad(nm,16), round(h,digits=1), " m"); end
        bbn = unique([i.name for i in insts if get(bbinfo,i.name,nothing)!==nothing && !drop(i.name) && onground(i)])
        bbt = sort([(nm, bbinfo[nm][4], bbinfo[nm][5]) for nm in bbn], by=x->-x[2])
        println("== JM_OBJDIAG billboards (name  h×w m) =="); for (nm,h,wd) in bbt; println("   ", rpad(nm,16), round(h,digits=1), " × ", round(wd,digits=1)); end
        # floaters: objects/billboards placed high above the track low point (trkzlo) — the PO's
        # "buildings floating high overhead".  on=on-HAT (snapped), off=off-HAT (edgez/trkzlo fallback).
        flo = sort([(i.name, ploz(i), groundz(i.x,i.y)>-900f0) for i in insts
                    if (get(objmesh,i.name,nothing)!==nothing||get(bbinfo,i.name,nothing)!==nothing) && !drop(i.name) && onground(i)], by=x->-x[2])
        println("== JM_OBJDIAG highest-placed (trkzlo=", round(trkzlo,digits=1), " trkzhi=", round(trkzhi,digits=1), ") =="); seen=Set{String}()
        for (nm,py,onhat) in flo; nm in seen && continue; push!(seen,nm); length(seen)>22 && break; println("   ", rpad(nm,16), "y=", rpad(round(py,digits=1),7), onhat ? "on-HAT" : "OFF-HAT"); end; flush(stdout)
        # E33: MESH objects whose base sits IN/NEAR the road corridor (the Watkins balcony-support-in-road).
        # on_road returns |lateral| under the halfwidth; report any kept mesh within ROAD_HALFW+4 m of centre.
        onroad_objs = NTuple{4,Any}[]
        for i in insts
            (get(objmesh,i.name,nothing)===nothing || drop(i.name) || !onground(i)) && continue
            (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 || continue
            hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            # road tangent angle from perp (lateral unit vec rotated -90°); object yaw RELATIVE to it:
            # |relyaw| near 0/180 = wall runs PARALLEL to the road, near ±90 = PERPENDICULAR storefront (E41)
            roadθ = atan(-hr.perp[2], hr.perp[1])
            relyaw = rad2deg(rem2pi(Float64(i.yaw) - roadθ, RoundNearest))
            hr.found && abs(hr.lateral) < parse(Float64,get(ENV,"JM_OBJDIAG_LAT","$(ROAD_HALFW+4.0)")) && push!(onroad_objs, (i.name, round(hr.lateral,digits=1), round(hr.lapdist,digits=0), round(relyaw,digits=0)))
        end
        sort!(onroad_objs, by=x->abs(x[2]))
        println("== JM_OBJDIAG mesh objects in/near the road (|lat| < ROAD_HALFW+4 = ", round(ROAD_HALFW+4.0,digits=1), " m;  relyaw 0/±180=parallel, ±90=PERPENDICULAR) ==")
        for (nm,lat,ld,ry) in onroad_objs; println("   ", rpad(nm,16), "lat=", rpad(lat,7), " lapdist=", rpad(ld,7), " relyaw=", ry, "°"); end; flush(stdout)
    end
    # D3 (PO): the dune spectators run PERPENDICULAR to the road and hang off the dunes.  List every kept
    # crowd row with its lateral offset + orientation so we can tell grandstand crowds (near, parallel)
    # from loose dune lines (far, perpendicular).  relyaw near ±90 = the row faces ACROSS the road.
    if get(ENV,"JM_CROWDDIAG","")!=""
        cr = NTuple{4,Any}[]
        for i in insts
            standcrowd(i.name) || continue
            hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            lat = hr.found ? round(hr.lateral,digits=1) : NaN
            ry  = hr.found ? round(rad2deg(rem2pi(Float64(i.yaw)-atan(-hr.perp[2],hr.perp[1]), RoundNearest))) : NaN
            push!(cr, (lowercase(i.name), lat, hr.found ? round(hr.lapdist,digits=0) : NaN, ry))
        end
        sort!(cr, by=x->(x[1], isnan(x[2]) ? 1e9 : abs(x[2])))
        println("== JM_CROWDDIAG kept crowd rows (lat NaN = off the road ribbon = out on the dunes; relyaw ±90 = PERPENDICULAR) ==")
        for (nm,lat,ld,ry) in cr; println("   ", rpad(nm,12), "lat=", rpad(lat,8), " lapdist=", rpad(ld,8), " relyaw=", ry); end
        println("   (", length(cr), " crowd rows kept)"); flush(stdout)
    end
end
println(length(OBJECTS), " trackside objects + ", length(BILLBOARDS), " billboards + ", length(STATICTREES), " forest panels + ", length(SOLIDS), " solid (collidable)"); flush(stdout)
end
carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
gaugeItems = Render.build_gpl(GAUGEP, GPLTEX)      # gauge cluster (drawn near-unlit so it reads)
windItems  = Render.build_gpl(WINDP, GPLTEX)       # plexiglass windscreen (drawn last, transparent)
mirrorItems = Render.build_gpl(MIRRORP, GPLTEX)    # rear-view mirrors (re-placed on the cowl, MIRRORMAT)
# ---- E64: LIVE mirrors — a small rear-view RTT + a glass quad on each disc ----------------
# One wide rear view is rendered per frame into a MIRW×MIRH FBO (X-mirrored in clip space,
# like a real mirror); the LEFT disc samples the left half, the RIGHT disc the right half.
# Each glass quad is built in the SAME raw-mesh frame as MIRRORP (drawn with
# bodyModel*MIRRORMAT) so it lands exactly on its disc: per-disc bbox (the discs sit at raw
# z ≈ ∓0.36) → thinnest bbox axis = the glass normal, quad spans the two in-plane axes,
# nudged 4 mm along the normal toward the eye so it sits ON the glass, not in it.  vC.xy
# carries disc-local 0..1 coords for the round mask (uMirrorGlass in the FS).
const MIRROR_RTT = get(ENV,"JM_MIRROR_RTT","1") != "0"    # JM_MIRROR_RTT=0 → old static silver discs
const MIRW, MIRH = 384, 192
(mirfbo, mirtex) = MIRROR_RTT ? Render.make_mirror_fbo(MIRW, MIRH) : (GLuint(0), GLuint(0))
const MIRROR_GLASS_FRAC = 0.88f0                          # glass diameter as a fraction of the disc (keeps the rim)
function mirror_glass_quads(parts, tex)
    items = Render.Item[]
    for side in (-1, 1)
        xmn=ymn=zmn=Inf32; xmx=ymx=zmx=-Inf32
        for p in parts
            v = p.verts
            for i in 1:11:length(v)-10
                sign(v[i+2]) == side || continue
                xmn=min(xmn,v[i]); xmx=max(xmx,v[i]); ymn=min(ymn,v[i+1]); ymx=max(ymx,v[i+1]); zmn=min(zmn,v[i+2]); zmx=max(zmx,v[i+2])
            end
        end
        isfinite(xmn) || continue
        c  = Float32[(xmn+xmx)/2, (ymn+ymx)/2, (zmn+zmx)/2]
        e  = Float32[xmx-xmn, ymx-ymn, zmx-zmn]
        na = argmin(e)                                     # thinnest bbox axis = glass normal
        ua, va = na==1 ? (3,2) : na==2 ? (3,1) : (1,2)     # in-plane axes (u = lateral-ish, v = up-ish)
        eyerig = Float32[0.46, 0.40, 0]                    # driver eye in the rig frame (JM_EYE_* defaults)
        ns = Float32(sign(eyerig[na] - c[na])); ns == 0 && (ns = -1f0)   # face the glass toward the eye
        hu = e[ua]/2 * MIRROR_GLASS_FRAC; hv = e[va]/2 * MIRROR_GLASS_FRAC
        nrm = Float32[0,0,0]; nrm[na] = ns
        u0, u1 = side < 0 ? (0f0, 0.5f0) : (0.5f0, 1f0)    # left disc ← left half of the rear view
        q = Float32[]
        corner(mu, mv) = begin
            p = copy(c); p[na] += ns*(e[na]/2 + 0.004f0)
            p[ua] += (mu-0.5f0)*2hu*ns; p[va] += (mv-0.5f0)*2hv   # ns also flips u so the image reads upright from the viewing side
            append!(q, p); append!(q, nrm); push!(q, mu, mv, 0f0, u0+(u1-u0)*mu, mv)
        end
        for (mu,mv) in ((0f0,0f0),(1f0,0f0),(1f0,1f0), (0f0,0f0),(1f0,1f0),(0f0,1f0)); corner(mu,mv); end
        vao, n = Render.upload(q)
        push!(items, Render.Item(vao, n, tex, (1f0,1f0,1f0)))
    end
    items
end
mirGlassItems = MIRROR_RTT ? mirror_glass_quads(MIRRORP, mirtex) : Render.Item[]
fsuspItems  = Render.build_gpl(FSUSPP, GPLTEX)     # front suspension wishbones (visible through the screen)
driverItems = Render.build_gpl(DRIVERP, GPLTEX)    # driver figure — drawn only in chase view (E36)
helmItems   = Render.build_gpl(HELMP, GPLTEX)      # Clark-blue helmet at the head pivot (chase view, E60)
# four Lotus wheels — keep the untextured black tyre body (only the car body drops "")
# E59 parity: 0.12 albedo rendered the tyres as SOLID BLACK silhouettes from the cockpit (no texture in
# lotwlf.3do to carry detail).  The GPL gold cockpit shows dark-grey tyres whose curvature SHADES —
# lift the flat albedo so the smooth-normal cylinder shading reads while staying tyre-dark.  JM_TYRE_ALB.
# E60 (260801 gold videos): 0.26 read as light-grey ALLOY, not rubber — both gold videos show
# near-black treaded tyres (~0.16 screen).  0.17 + the ambfill-lifted wheel draw keeps the cylinder
# shading while reading as dark rubber in both cockpit and chase.
const TYRE_ALB = parse(Float32, get(ENV,"JM_TYRE_ALB","0.17"))
load_wheel(nm) = Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(TYRE_ALB,TYRE_ALB,TYRE_ALB+0.02f0)), GPLTEX)
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
handItems = Render.build_gpl(HANDP, GPLTEX)        # E64 S2: gloved hands (cockpit view, rotate with the wheel)
armItems  = Render.build_gpl(ARMP, GPLTEX)         # E64 S2: forearms (cockpit view, static)
rsuspItemsA = Render.build_gpl(RSUSPP_A, GPLTEX)   # E64 S7: high-detail rear suspension halves (chase view)
rsuspItemsB = Render.build_gpl(RSUSPP_B, GPLTEX)
# Corrective transform per side (E64 S8, settled by the POSITIONER-CHAIN DUMP): the chain to each
# half is [park d=(0,20,0) → clamped 0] · [LOD selectors] · [hub placement d=(−0.893, ±0.772, 0.02),
# yaw 2°, s=1.0] — so scale IS 1.0 and the hub translations are honoured; what remains is that the
# assemblies are AUTHORED in a flat horizontal pose (identity capture: wings splayed flat outward)
# and must fold ~90° about the HUB LINE (z=±0.772 — S7's 0.35 pivot was mid-driveshaft, hence the
# under-fold/backward-fan artifacts).  50° vs 90° A/B'd near-identical from the chase (tyres +
# gearbox occlude); 90° kept as the geometrically-motivated flat→vertical value.  JM_RS_* A/B.
rsfix(side) = begin      # side = +1 (z>0 half) / −1
    ax, ay = -1.05f0, 0.31f0
    sx = parse(Float32, get(ENV,"JM_RS_SX","1.0")); sy = parse(Float32, get(ENV,"JM_RS_SY","1.0")); sz = parse(Float32, get(ENV,"JM_RS_SZ","1.0"))
    dx, dy = parse(Float32, get(ENV,"JM_RS_DX","0.0")), parse(Float32, get(ENV,"JM_RS_DY","0.0"))
    y0, z0 = parse(Float32, get(ENV,"JM_RS_Y0","0.02")), parse(Float32, get(ENV,"JM_RS_Z0","0.772"))
    roll   = deg2rad(parse(Float32, get(ENV,"JM_RS_ROLL","90")))
    Render.translate(Float32[dx, dy, 0]) *
        Render.translate(Float32[ax, ay, 0]) * Render.scalexyz(sx, sy, sz) * Render.translate(Float32[-ax, -ay, 0]) *
        Render.translate(Float32[0, y0, side*z0]) * Render.rotx(Float32(-side*roll)) * Render.translate(Float32[0, -y0, -side*z0])
end
# which extracted group is which side is settled empirically: JM_RS_SWAP=1 flips the pairing
const RS_SWAP = get(ENV,"JM_RS_SWAP","0") != "0"
const RSFIX_A = rsfix(RS_SWAP ? -1 : 1)
const RSFIX_B = rsfix(RS_SWAP ? 1 : -1)
# E64 S8: ON by default — the positioner-chain dump settled the transform (hub-line fold; see
# rsfix above); the gold nintendo chase shows this articulated rear end, so it ships.
const RSUSP_ON = get(ENV,"JM_RSUSP","1") != "0"
# E75-S5: what does the Lotus .3do actually CONTAIN, and which exclusion eats gold's rear linkage?
# Four sprints of transform-tuning are closed (E75-S4: no fold angle works), and the code's own
# words — "runtime-hidden branches" — suggest JM has been rehabilitating geometry GPL never draws.
# Gold's wishbones/driveshafts run INBOARD from the hub (z≈0.772) to the gearbox (z≈0.2), so they
# should survive CARP_MAXLAT=0.85. List every texture in the UNFILTERED model with its extent, and
# mark what each exclusion list drops, so the missing linkage can be found by name rather than guess.
if get(ENV,"JM_FSUSP_DIAG","") != ""
    # E75-S7: is FSUSPP actually non-empty after the fix? The A/B changed 0 pixels in BOTH views,
    # which means either the parts are still absent or they are invisible — different problems.
    # Count the triangles that survive at several maxedge values so the clip can be seen working.
    for me in (0.5f0, 1.0f0, 1.5f0, 2.0f0, Inf32)
        pp = Render.extract_gpl_car(LOT3DO; only=("lsusp1",), maxlat=1.3f0, maxedge=me)
        n = sum(length(x.verts) ÷ 11 for x in pp; init=0) ÷ 3
        println("   FSUSPP maxedge=", me, "  -> ", length(pp), " parts, ", n, " tris")
    end
    for me in (1.0f0, Inf32)
        pp = Render.extract_gpl_car(LOT3DO; only=("frontlot",), maxlat=1.3f0, maxedge=me)
        n = sum(length(x.verts) ÷ 11 for x in pp; init=0) ÷ 3
        println("   frontlot maxedge=", me, " -> ", length(pp), " parts, ", n, " tris")
    end
    flush(stdout)
end
if get(ENV,"JM_CARGROUPS","") != ""
    # E75-S6: WHICH excluded group holds gold's rear linkage? E75-S5 named the missing parts
    # (lshok, lsusp5/7, lsusp1, lbrdisc, frontlot — all present in the .3do, none excluded by name)
    # and refuted CARP_MAXLAT as the cause, leaving exclude_groups=(6600,3560,27288,39792) by
    # elimination. Extract each excluded group ALONE and list what it carries: that says whether the
    # exclusions are removing geometry gold displays, and which exclusion to re-examine.
    for g in (6600, 3560, 27288, 39792)
        parts = Render.extract_gpl_car(LOT3DO; include_groups=(g,))
        tot = 0
        rows = []
        for pp in parts
            n = length(pp.verts) ÷ 11
            zmn=Inf32; zmx=-Inf32
            for i in 1:11:length(pp.verts)-10
                z=pp.verts[i+2]; zmn=min(zmn,z); zmx=max(zmx,z)
            end
            push!(rows, (pp.tex, n, zmn, zmx)); tot += n
        end
        println("== JM_CARGROUPS group ", g, ": ", length(rows), " parts, ", tot, " tris ==")
        for (tex,n,zmn,zmx) in sort(rows, by=r->-r[2])[1:min(end,10)]
            mark = tex in ("lshok","lsusp5","lsusp7","lsusp1","lbrdisc","frontlot") ? "   <<< MISSING FROM CARP" : ""
            println("     ", rpad(tex,14), rpad(n,7), rpad(string(round(zmn,digits=2),"…",round(zmx,digits=2)),18), mark)
        end
    end
    flush(stdout)
end
if get(ENV,"JM_CARPARTS","") != ""
    allp = Render.extract_gpl_car(LOT3DO)      # no exclusions, no group filter, no maxlat
    kept = Set{String}()
    for pp in CARP; push!(kept, pp.tex); end
    excl = Set{String}((_HAND_EXC...,_LOTBLACK_EXC...,_EXTRA_EXC...,_GARBAGE_EXC...,
                        DRIVER_TEX...,MIRROR_TEX...,Render.STEER_TEX...))
    println("== JM_CARPARTS: Lotus 49 .3do contents (unfiltered) ==")
    println("   texture       tris   lateral z          height y           in CARP?  excluded by name?")
    rows = []
    for pp in allp
        v = pp.verts; n = length(v) ÷ 11
        zmn=Inf32; zmx=-Inf32; ymn=Inf32; ymx=-Inf32
        for i in 1:11:length(v)-10
            y=v[i+1]; z=v[i+2]
            ymn=min(ymn,y); ymx=max(ymx,y); zmn=min(zmn,z); zmx=max(zmx,z)
        end
        push!(rows, (pp.tex, n, zmn, zmx, ymn, ymx))
    end
    for (tex,n,zmn,zmx,ymn,ymx) in sort(rows, by=r->-r[2])
        println("   ", rpad(tex,14), rpad(n,7),
                rpad(string(round(zmn,digits=2),"…",round(zmx,digits=2)),19),
                rpad(string(round(ymn,digits=2),"…",round(ymx,digits=2)),19),
                rpad(tex in kept ? "yes" : "NO", 10),
                tex in excl ? "EXCLUDED" : "")
    end
    flush(stdout)
end
# E75-S3: the wheels are placed from a PHYSICS constant (WTRACK_F/R) while the body and suspension
# come from the GPL mesh at its own scale. E75-S2 showed narrowing the drawn track ~18% makes the car
# read as a connected assembly, so the two disagree — but "~18%" came from eyeballing a probe. Print
# both numbers so the disagreement is exact and it is clear WHICH side is wrong.
# In the render frame the car's lateral axis is z (extract remaps p[1],p[3],p[2]).
if get(ENV,"JM_WHEELFIT","") != ""
    ba = Render.parts_bbox(RSUSPP_A); bb = Render.parts_bbox(RSUSPP_B)
    bc = Render.parts_bbox(CARP)
    outb = max(abs(ba.zmin), abs(ba.zmax), abs(bb.zmin), abs(bb.zmax))
    println("== JM_WHEELFIT: drawn wheel placement vs the mesh the suspension is authored at ==")
    println("   rear-susp mesh lateral  A: ", round(ba.zmin,digits=3), " … ", round(ba.zmax,digits=3),
            "   B: ", round(bb.zmin,digits=3), " … ", round(bb.zmax,digits=3))
    println("   outermost suspension point   |z| = ", round(outb,digits=3), " m")
    println("   car body (CARP) lateral       ", round(bc.zmin,digits=3), " … ", round(bc.zmax,digits=3))
    println("   wheels drawn at half-track    front ", WTRACK_F, "   rear ", WTRACK_R, " m")
    println("   REAR gap wheel-centre − suspension outermost = ",
            round(WTRACK_R - outb, digits=3), " m")
    println("   (a positive gap is empty space the linkage cannot span — the visual 'detached wheels')")
    flush(stdout)
end
# E64 S2: the raw fists sit at 3-and-9 on the rim; the gold cockpit video grips at 10-AND-2 —
# opposite per-hand rotations about the wheel axis, so split the two fists by z sign (rig +z =
# car's left) and give each its own grip rotation (JM_HAND_GRIP degrees, left +, right −).
function split_fists(parts, tex)
    L=Float32[]; R=Float32[]
    for p in parts
        v = p.verts
        for t in 1:33:length(v)-32                     # one triangle = 3 verts × 11 floats
            zm = (v[t+2]+v[t+13]+v[t+24])/3
            append!(zm > 0 ? L : R, @view v[t:t+32])
        end
    end
    [Render.Item(Render.upload(a)..., tex, (1f0,1f0,1f0)) for a in (L, R)]
end
handLR = isempty(handItems) ? Render.Item[] : split_fists(HANDP, handItems[1].tex)
const HAND_GRIP = deg2rad(parse(Float32, get(ENV,"JM_HAND_GRIP","30")))
gripmat(sgn) = Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(sgn*HAND_GRIP)) * Render.translate(-SWCENTER)
# E64 S2: corrective transform for the positioner-orphaned lotarms mesh (see the draw site).
# JM_ARM_* iterate it from captures without a code edit: FLIP = 180° yaw about the wheel-plane
# pivot (sweeps the arms BACK toward the driver), SY squashes them below the eye about Y0,
# DX/DY nudge.  JM_ARMS=0 drops the arms entirely (hands only).
const ARMS = get(ENV,"JM_ARMS","1") != "0"
# Vertex scatter (proj_xy/zy in the sprint scratchpad): each arm runs from its wrist (at the
# hand, x≈0.74 y≈0.26) UP-AND-FORWARD to x 1.01 / y 0.52 — inverted from reality, where the
# forearm drops DOWN-AND-BACK to an elbow at the cockpit side.  So: 180° rotation in the x-y
# plane about the wrist point (mirror x about X0, y about Y0) with a y-squash so the far ends
# land at lap height, z untouched (the wide ±0.37 elbows match gold's frame-edge sleeves).
const ARMFIX = begin
    px, py = parse(Float32, get(ENV,"JM_ARM_X0","0.74")), parse(Float32, get(ENV,"JM_ARM_Y0","0.26"))
    sy     = parse(Float32, get(ENV,"JM_ARM_SY","0.62"))   # E68 S5: sleeves reach the gloves (PO: "sleeves don't connect")
    sz     = parse(Float32, get(ENV,"JM_ARM_SZ","0.55"))   # tuck the ±0.37 elbows toward the body sides
    dx, dy = parse(Float32, get(ENV,"JM_ARM_DX","-0.02")), parse(Float32, get(ENV,"JM_ARM_DY","-0.06"))   # E68 S5 re-tune: junction closed (was fix4 -0.05)
    Render.translate(Float32[dx, dy, 0]) *
        Render.translate(Float32[px, py, 0]) * Render.scalexyz(-1f0, -sy, sz) * Render.translate(Float32[-px, -py, 0])
end
println(count(it->it.tex!=0, trackItems), "/", length(trackItems), " track + ",
        count(it->it.tex!=0, carItems), "/", length(carItems), " Lotus parts textured")

# ---- E8: the AI grid = the standard GPL '67 chassis (Ferrari/Brabham/BRM/Eagle/
# Cooper), each its OWN GPL car, not Lotus copies.  Auto-levelled onto a common
# floor (the Lotus body underside) and reusing the Lotus wheel geometry with each
# car's own wheel meshes ('67 cars are dimensionally near-identical).  The player
# is always the Lotus 49. ----
const AIBASE = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","cars","cars67"))
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
# B (PO): per-car (power bhp, mass kg) — period GPL '67 specs — so the field spreads by PHYSICS, not a
# fudge.  Pace ∝ power/weight (tempered: most of a lap is grip-limited, shared, so a big power/weight
# gap → a smaller laptime gap).  Order matches AISPECS.  The Eagle-Weslake out-paces the heavy BRM H16.
const AICAR_PHYS = [
    (390.0, 560.0),   # Ferrari 312        V12
    (330.0, 525.0),   # Brabham BT24       Repco V8 (light)
    (400.0, 615.0),   # BRM P115           H16 (heavy)
    (395.0, 555.0),   # Eagle T1G          Weslake V12
    (360.0, 600.0),   # Cooper T81         Maserati V12 (heavy)
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
# GPL's cockpit uses a WIDE field of view — the mirrors sit at the screen edges and you see lots of road.
# A separate wide projection for the cockpit view (tunable via JM_FOV) reproduces that immersive look.
const PROJ_COCKPIT = Render.perspective_revz(deg2rad(parse(Float32,get(ENV,"JM_FOV","80"))), Float32(W/H), 0.20f0, 3000f0)

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; prevRec::Bool; view::Int; auto::Bool; end
# shift mode: AUTO by default (auto-clutch + auto-shift) — press throttle and GO, the car never bogs
# on the line or out of a slow corner.  Press G in-app for MANUAL (work the clutch on C, shift E/Q —
# release the clutch too low and it crawls/bogs, just like the real thing).  ZAND_SHIFT=manual forces it.
const CTL = Ctl(false,false,false,false,false,false, parse(Int, get(ENV,"JM_VIEW","1")), get(ENV,"ZAND_SHIFT","auto") != "manual")   # view 1=chase 0=cockpit; AUTO gearbox by default (G toggles)
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
    # R = respawn at the start; SHIFT+R (GPL) = recover onto the centreline at the CURRENT lap position
    # (upright, stopped) so you can rejoin from the grass/a spin without teleporting to the line.  recover
    # is EDGE-triggered (one drop per press); both set `rst` so the per-frame respawn guards still apply.
    rkey  = key(GLFW.KEY_R); shift = key(GLFW.KEY_LEFT_SHIFT) || key(GLFW.KEY_RIGHT_SHIFT)
    recover = rkey && shift && !CTL.prevRec; CTL.prevRec = rkey && shift
    rst = (rkey && !shift) || recover
    (DriveInput(throttle=clamp(thr,0,1), brake=clamp(brk,0,1), steer=clamp(str,-1,1),
                clutch=clu, shift_up=upE, shift_down=dnE, autoshift=CTL.auto), rst, recover)
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

# ---- camera (pitch/roll = total body orientation, applied to the cockpit view only) ----
const CHASE_D  = parse(Float32, get(ENV,"JM_CHASE_D","4.6"))    # metres behind the car
const CHASE_H  = parse(Float32, get(ENV,"JM_CHASE_H","1.35"))   # metres above the car origin
const CHASE_LY = parse(Float32, get(ENV,"JM_CHASE_LY","0.80"))  # look-at height 2 m ahead
function camera(cs, pitch=0.0, roll=0.0)
    wx,wy,wz = cs.x, cs.y, -cs.z; fx,fz = cos(cs.θ), -sin(cs.θ)   # render world un-mirrors physics z
    if CTL.view == 1                                  # chase — level horizon, so you SEE the body pitch/roll
        # E60 (260801 nintendo gold video): GPL's chase cam sits LOW and CLOSE — the car fills the lower
        # frame, horizon mid-frame.  The old 9 m/3.2 m read as a high TV crane shot.  JM_CHASE_* A/Bs.
        eye=[wx-fx*CHASE_D, wy+CHASE_H, wz-fz*CHASE_D]; ctr=[wx+fx*2, wy+CHASE_LY, wz+fz*2]
        return PROJ * Render.lookat(Float32.(eye), Float32.(ctr), Float32[0,1,0]), Float32.(eye)
    end
    # COCKPIT: the camera takes yaw from the chassis and pitch/roll from the LOW-PASS head tilt (E53,
    # caller-supplied cam_pitch/cam_roll).  On a slow road bank that low-pass ≈ the chassis tilt, so the
    # cockpit is stationary on screen and the WORLD tilts (head → surface normal, GPL behaviour); on a fast
    # jolt the low-pass lags, so the chassis (drawn at FULL tilt) rocks on screen while the horizon stays
    # level — no headache-inducing landscape strobe.
    ex,ey,ez,drop = parse(Float32,get(ENV,"JM_EYE_X","0.46")), parse(Float32,get(ENV,"JM_EYE_Y","0.40")), 0.0f0, parse(Float32,get(ENV,"JM_EYE_DROP","0.55"))   # GPL: low seat just behind the wheel, ~level gaze (see the road), dash fills the lower frame; tunable via JM_EYE_*
    R = Render.roty(Float32(cs.θ)) * Render.rotz(Float32(pitch)) * Render.rotx(Float32(roll))   # = the chassis rotation
    R3(a,b,c) = (w = R * Float32[a,b,c,0f0]; Float32[w[1],w[2],w[3]])     # rotate a body-frame direction into the world
    eye = Float32[wx,wy,wz] + R3(BODY_OFF[1]+ex, BODY_OFF[2]+ey, BODY_OFF[3]+ez)   # eye fixed in the body frame
    ctr = eye + R3(4f0, -drop, 0f0)                                       # look forward + a slight downward drop
    up  = R3(0f0, 1f0, 0f0)                                               # camera up = the body's up (= surface normal)
    PROJ_COCKPIT * Render.lookat(eye, ctr, up), eye                       # WIDE FOV cockpit (GPL look)
end

# ---- E64: rear-view camera for the mirror RTT — same eye as the cockpit camera, looking
# BACKWARD, X-mirrored in clip space like a real mirror (a mirror shows the rear world
# left-right flipped relative to a rear-facing camera).  One wide view feeds both discs
# (left disc samples the left half).  NB the X flip reverses triangle winding, so the
# object-pass face cull swaps its culled side in the mirror pass (drawworld flip arg).
# E64 S10 (gold cockpit video at speed): the gold mirrors are ROAD-dominated — the rear tyre
# sits at the INNER edge and the tail bodywork is mostly out of frame, because each real mirror
# sees backward-OUTWARD from its cowl position.  A single eye-centred rear camera can never match
# that (the tail fills frame centre at any tilt — verified by the −0.45/−0.8 drop A/B), so each
# disc now gets its OWN camera at the mirror's position (per-half FBO viewports; same pixel cost).
# Aspect is per-half (square).  JM_MIRCAM_X/Y/Z = camera rig position (z mirrored per side),
# JM_MIRROR_YAWOUT = outward look component, JM_MIRROR_DROP = downward look component.
const PROJ_MIRROR = Render.scalexyz(-1f0,1f0,1f0) *
                    Render.perspective_revz(deg2rad(parse(Float32,get(ENV,"JM_MIRROR_FOV","78"))), Float32(MIRW÷2)/Float32(MIRH), 0.35f0, 3000f0)
function mirror_camera(cs, pitch=0.0, roll=0.0, side=1)
    wx,wy,wz = cs.x, cs.y, -cs.z
    R = Render.roty(Float32(cs.θ)) * Render.rotz(Float32(pitch)) * Render.rotx(Float32(roll))
    R3(a,b,c) = (w = R * Float32[a,b,c,0f0]; Float32[w[1],w[2],w[3]])
    mx = parse(Float32,get(ENV,"JM_MIRCAM_X","0.55")); my = parse(Float32,get(ENV,"JM_MIRCAM_Y","0.33")); mz = parse(Float32,get(ENV,"JM_MIRCAM_Z","0.31"))
    eye = Float32[wx,wy,wz] + R3(BODY_OFF[1]+mx, BODY_OFF[2]+my, side*mz)
    drop = parse(Float32, get(ENV,"JM_MIRROR_DROP","-0.2")); yawout = parse(Float32, get(ENV,"JM_MIRROR_YAWOUT","0.5"))
    ctr = eye + R3(-4f0, drop, side*yawout)
    PROJ_MIRROR * Render.lookat(eye, ctr, R3(0f0,1f0,0f0)), eye
end

# ---- E25: replay cinematic cameras — GPL-style angles for the multi-cam replay viewer ----
# Each follows the FOCUS car (player or any AI) from its recorded pose (x,y,z,θ); no driving
# state, so cameras are purely geometric off the pose.  Cycle with V; switch focus car with C.
const REPLAY_CAMS  = (:cockpit, :chase, :tv, :f10, :nose, :rsusp)
const REPLAY_CAM_LABEL = ("COCKPIT", "CHASE (above rear)", "TV / DISTANT",
                          "F10 REAR", "NOSE / FRONT", "RR SUSPENSION")
function replay_camera(mode, x, y, z, θ)
    wx, wy, wz = Float32(x), Float32(y), Float32(-z)        # render world un-mirrors physics z
    fx, fz = Float32(cos(θ)), Float32(-sin(θ))             # render forward (horizontal)
    rx, rz = -fz, fx                                        # render right = forward × up (horizontal)
    P = Float32[wx, wy, wz]
    if mode === :cockpit
        ex,ey,drop = parse(Float32,get(ENV,"JM_EYE_X","0.46")), parse(Float32,get(ENV,"JM_EYE_Y","0.40")), parse(Float32,get(ENV,"JM_EYE_DROP","0.55"))
        R = Render.roty(Float32(θ))
        R3(a,b,c) = (w = R*Float32[a,b,c,0f0]; Float32[w[1],w[2],w[3]])
        eye = P + R3(BODY_OFF[1]+ex, BODY_OFF[2]+ey, 0f0)
        ctr = eye + R3(4f0, -drop, 0f0); up = R3(0f0,1f0,0f0)
        return PROJ_COCKPIT * Render.lookat(eye, ctr, up), eye
    end
    eye, ctr = if mode === :chase
        (Float32[wx-fx*9, wy+3.2f0, wz-fz*9],  Float32[wx+fx*3, wy+0.6f0, wz+fz*3])
    elseif mode === :tv                                    # high & to the side, panning — the GPL "distant" TV cam
        (Float32[wx+rx*15-fx*5, wy+9.5f0, wz+rz*15-fz*5],  Float32[wx, wy+0.6f0, wz])
    elseif mode === :f10                                   # GPL F10 = low bumper cam just behind, looking forward
        (Float32[wx-fx*6, wy+1.3f0, wz-fz*6],  Float32[wx+fx*8, wy+0.9f0, wz+fz*8])
    elseif mode === :nose                                  # camera ahead, looking back at the nose + driver
        (Float32[wx+fx*7, wy+1.2f0, wz+fz*7],  Float32[wx, wy+0.7f0, wz])
    else                                                   # :rsusp — close-up on the right-rear corner (tyre/tailpipe)
        cx = wx - fx*1.8f0 + rx*1.0f0; cz = wz - fz*1.8f0 + rz*1.0f0
        (Float32[cx+rx*1.6f0-fx*0.4f0, wy+0.75f0, cz+rz*1.6f0-fz*0.4f0],  Float32[cx, wy+0.40f0, cz])
    end
    PROJ * Render.lookat(eye, ctr, Float32[0,1,0]), eye
end

# ---- main loop (in a function — avoids top-level soft scope, runs faster) ----
function main()
    cs0 = SKIDPAD ? (x=0.0, z=0.0, θ=0.0) : spawn(CAR; v0=0.0)   # spawn pose (skidpad: pad centre)
    LASTZ = Ref(0.0); ONTRACK = Ref(true)
    LASTGX = Ref(cs0.x); LASTGZ = Ref(cs0.z)   # last position INSIDE the world (terrain HAT) — for the boundary
    OFFDIST = Ref(0.0)                          # distance travelled off the HAT (grace before containing)
    PLAYER_CDA = Ref(1.0)                        # E56: player drag scale fed to the chassis ODE next frame (draft tow)
    BND_FX = Ref(0.0); BND_FY = Ref(0.0); BND_MZ = Ref(0.0)   # E56: world-edge physical-wall force (body frame) fed next frame
    # The Monza banking deck-over-road is removed from TERRAIN by build_hat's overpass-drop, so the
    # topmost remaining surface under the crossings is the road.  Where the banking deck spans a GAP in
    # the road mesh (first underpass) there is nothing below to keep, so the deck survives — guard it
    # here: a car can't instantly climb several metres, so a height that jumps > WALL_CLIMB above the
    # last on-road height is a wall/island; reject it (coast at the held height, off-surface) instead of
    # teleporting up onto it.  `acquire=true` bypasses the guard to re-anchor from scratch (spawn/teleport).
    WALL_CLIMB = parse(Float64, get(ENV, "JM_WALL_CLIMB", "3.0"))
    function groundz(x, z; acquire = false)
        SKIDPAD && return 0.0   # flat skidpad → no elevation
        h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf)
        # Wall guard gated to MONZA: Monza is flat, so the only multi-metre upward jump is the banking
        # island over the road gap.  On hilly tracks (Nürburgring) real crests + the shared LASTZ across
        # the AI field would false-fire, so those keep the unguarded path.
        if h[3] && (acquire || !MONZA || Float64(h[1]) <= LASTZ[] + WALL_CLIMB)
            LASTZ[] = Float64(h[1]); ONTRACK[] = true
        else
            ONTRACK[] = false      # off the HAT, or an implausible upward jump (wall/island) → hold last height
        end
        LASTZ[]
    end
    y0spawn = groundz(cs0.x, cs0.z; acquire=true)            # terrain height at spawn (3-D needs it; else the car spawns 100s of m off the ground and the contact explodes) — bootstrap LASTZ from topmost

    # robust spawn heading: the single S/F seam segment can give a sideways tangent, so
    # take the heading from a few points DOWN the centreline (the real start-straight direction).
    θ0spawn = if SKIDPAD
        cs0.θ
    else
        # walk ~8 m down the centreline from PAST the S/F seam (point 2) for a clean straight-ahead
        # heading — a fixed point-count baseline gave a cock-eyed grid pose where the seam kinks.
        base = min(2, length(ALIGNED)-1); j = base; acc = 0.0
        while acc < 8.0 && j < length(ALIGNED)
            acc += hypot(ALIGNED[j+1][1]-ALIGNED[j][1], ALIGNED[j+1][2]-ALIGNED[j][2]); j += 1
        end
        atan(ALIGNED[j][2]-ALIGNED[base][2], ALIGNED[j][1]-ALIGNED[base][1])
    end
    tstamp("physics build (mtkcompile) begins")
    cs = build_carX(x0=cs0.x, z0=cs0.z, θ0=θ0spawn, v0=0.0, y0=y0spawn)   # MTK car — standing start (planar or full-3D)
    tstamp("physics build done — game loop imminent")
    # ---- AI opponents (race field): rail-followers on the centreline ----
    # CLINE = the centreline, built ALWAYS (off-skidpad) so the PLAYER's lap counting can use a
    # robust projection wrap instead of the ribbon lapdist (the ribbon has a seam at S/F that
    # broke the wrap → laps never counted → no finish).  AILINE = CLINE when there's a field.
    CLINE  = !SKIDPAD ? RaceAI.build_line(ALIGNED, groundz) : nothing
    CLINE !== nothing && println("  CLINE: centreline length = ", round(Int, CLINE.total), " m  (", TRACKSEL, ")")
    if CLINE !== nothing && haskey(ENV,"JM_LATDIAG")   # diagnose grass-threshold false-fire at the start
        pl = RaceAI.project(CLINE, cs.x, cs.z); ph = JuliaMotor.hat(TRKSURF, cs.x, cs.z)
        println("  LATDIAG spawn: CLINE lat=", round(pl[2],digits=2), "  TRKSURF found=", ph.found,
                " lat=", round(ph.lateral,digits=2), " on_track=", ph.on_track, " (ROAD_HALFW=", ROAD_HALFW, ")")
        for d in 5.0:5.0:40.0
            sp = RaceAI.pose_at(CLINE, RaceAI.project(CLINE, cs.x, cs.z)[1]+d, 0.0)
            ph2 = JuliaMotor.hat(TRKSURF, sp[1], sp[3]); pl2 = RaceAI.project(CLINE, sp[1], sp[3])
            println("    +", Int(d), "m on centreline: CLINE lat=", round(pl2[2],digits=2), "  TRKSURF lat=", round(ph2.lateral,digits=2), " on_track=", ph2.on_track)
        end
        flush(stdout)
    end
    # JM_START_S=<metres>: teleport the standing car to this distance along the centreline before the
    # game loop starts — lets a SMOKE render photograph ANY point on the lap (scenery QA: the Watkins
    # balcony, the Nürburgring carbonized stretch, …), not just the start/finish line.  Re-anchors the
    # vertical state to the terrain there so the car doesn't slam/diverge on a big-elevation track.
    # Teleport the standing car to s metres along the centreline + re-anchor the vertical state to the
    # terrain there (no slam/divergence on big-elevation tracks).  Shared by JM_START_S and JM_SHOTS.
    place_at_s! = function (s0raw::Float64)
        (CLINE === nothing || !CAR3D) && return nothing
        s0 = clamp(s0raw, 0.0, CLINE.total)
        p  = RaceAI.pose_at(CLINE, s0, 0.0)                 # (x, y, z, θ) on the racing line
        DriveRT3D.place3d!(cs, p[1], p[3], p[4]; v = 0.0)
        cs.s_vreset(cs.integ, zeros(14))                    # zero the vertical subsystem (no spawn bounce)
        h = groundz(p[1], p[3]; acquire=true); isfinite(h) && (cs.zref = Float64(h))
        cs.heave = 0.0; cs.pitch = 0.0; cs.roll = 0.0; cs.y = cs.zref
        p
    end
    if CLINE !== nothing && CAR3D && haskey(ENV, "JM_START_S")
        s0 = clamp(parse(Float64, ENV["JM_START_S"]), 0.0, CLINE.total)
        p  = place_at_s!(s0)
        println("  JM_START_S: car placed at s=", round(Int, s0), " m on the centreline (x=",
                round(Int, p[1]), " z=", round(Int, p[3]), ")")
        if get(ENV,"JM_OBJDIAG","")!="" && isdefined(Main,:OBJINSTS)
            rad = parse(Float64, get(ENV,"JM_SPOT_RAD","70"))
            near = NTuple{3,Any}[]
            for (nm,ox,oz,oy,kind,issolid) in OBJINSTS
                d = hypot(Float64(ox)-p[1], Float64(oz)-p[3])
                d < rad && push!(near, (round(d,digits=1), "$nm $(kind)$(issolid ? "·SOLID" : "")", round(Float64(oy),digits=1)))
            end
            sort!(near, by=x->x[1])
            println("  JM_SPOT objects within ", round(Int,rad), " m of the car (d  name kind  base-y):")
            for (d,lbl,oy) in near; println("     d=", rpad(d,7), rpad(lbl,22), " y=", oy); end
            # Forward HAT scan: sample the terrain height ahead along the centreline both as the
            # physics currently queries it (ref=Inf → TOPMOST surface) and following the road
            # (ref = road height + clearance).  A spike in the ref=Inf column at the Monza
            # banking underpass = the car gets lifted onto the overpass deck ("can't drive through").
            road_h = JuliaMotor.hat3d(TERRAIN, p[1], p[3]; ref=Inf)[1]
            println("  JM_HATSCAN ahead (s  top=ref∞  follow=road+3):  road_h@car=", round(road_h,digits=1))
            for ds in 0.0:10.0:140.0
                sp = RaceAI.pose_at(CLINE, min(s0+ds, CLINE.total), 0.0)
                ht = JuliaMotor.hat3d(TERRAIN, sp[1], sp[3]; ref=Inf)
                hf = JuliaMotor.hat3d(TERRAIN, sp[1], sp[3]; ref=road_h+3.0)
                println("     +", rpad(Int(ds),4), "m  top=", rpad(ht[3] ? round(ht[1],digits=1) : "MISS", 8),
                        "follow=", rpad(hf[3] ? round(hf[1],digits=1) : "MISS", 8),
                        (ht[3] && hf[3] && ht[1]-hf[1] > 1.5) ? "  <== OVERPASS SPIKE" : "")
            end
            # Simulate the car stepping forward: groundz with the live follow-ref (LASTZ updates each
            # step, exactly as the game loop drives it).  If it stays on the road (no jump to the 3.6-11.7
            # banking deck) the height fix holds; ontrack=false across the gap = the corridor-coast branch.
            # which TRACKMESH textures cover the spike points? (point-in-tri in XZ → tex + interpolated h)
            function cover_tex(qx, qz)
                out = Tuple{String,Float64}[]
                for t in TRACKMESH.tris
                    ax,az = Float64(t.p[1][1]), Float64(t.p[1][2]); bx,bz = Float64(t.p[2][1]), Float64(t.p[2][2]); cx,cz = Float64(t.p[3][1]), Float64(t.p[3][2])
                    d = (bz-cz)*(ax-cx)+(cx-bx)*(az-cz); abs(d) < 1e-9 && continue
                    wa = ((bz-cz)*(qx-cx)+(cx-bx)*(qz-cz))/d; wb = ((cz-az)*(qx-cx)+(ax-cx)*(qz-cz))/d; wc = 1-wa-wb
                    (wa>=-0.01 && wb>=-0.01 && wc>=-0.01) || continue
                    h = wa*Float64(t.p[1][3])+wb*Float64(t.p[2][3])+wc*Float64(t.p[3][3])
                    push!(out, (t.tex, round(h,digits=1)))
                end
                sort!(out, by=x->-x[2]); out
            end
            for ds in (15.0, 120.0)
                sp = RaceAI.pose_at(CLINE, min(s0+ds,CLINE.total), 0.0)
                println("  JM_COVER s+", Int(ds), " (x=", round(Int,sp[1]), " z=", round(Int,sp[3]), "): ",
                        join([string(tx=="" ? "<none>" : tx, "@", h) for (tx,h) in cover_tex(sp[1], sp[3])], "  "))
            end
            LASTZ[] = road_h
            println("  JM_DRIVETEST follow-ref groundz stepping forward from s=", round(Int,s0), ":")
            for ds in 0.0:5.0:160.0
                sp = RaceAI.pose_at(CLINE, min(s0+ds, CLINE.total), 0.0)
                hrb = JuliaMotor.hat(TRKSURF, sp[1], sp[3])
                g = groundz(sp[1], sp[3])
                println("     +", rpad(Int(ds),4), "m  groundz=", rpad(round(g,digits=1),7),
                        " ribbon=", rpad(hrb.found ? round(hrb.height,digits=1) : "MISS",7),
                        " lat=", rpad(round(hrb.lateral,digits=1),6), " ontrack=", ONTRACK[])
            end
            flush(stdout)
        end
    end
    # ---- E54 sweep harness: walk the whole centreline and report anything that would block or bog a
    # car ON the racing line — on-road mesh/billboard obstructions, HAT walls/cliffs/holes, and
    # "false-grass" spots (the centreline projecting off the .trk racing surface ⇒ a grass-penalty
    # MOLASSES even though the car is on the road).  Headless, no game loop.  JM_SWEEP=<step m> (or 1).
    if CLINE !== nothing && haskey(ENV,"JM_SWEEP") && isdefined(Main,:OBJINSTS)
        olat(ox,oz) = (hr = JuliaMotor.hat(TRKSURF, Float64(ox), Float64(oz)); hr.found ? round(hr.lateral,digits=1) : 999.0)
        step = (v = tryparse(Float64, get(ENV,"JM_SWEEP","")); v === nothing || v < 1 ? 15.0 : v)
        # project each kept object's centroid onto the .trk → its lateral offset.  An object whose
        # CENTROID is well inside the road half-width (|lat| < ROAD_HALFW-1) is a genuine blocker; one
        # near/beyond the edge (|lat| ≈ 9+) is roadside furniture (signs/flags/edge trees) — exclude it.
        BLOCK_LAT = ROAD_HALFW - 1.0
        # an object only blocks if its base sits near ROAD level — a gantry/bridge/sign spanning OVER
        # the track (base ≫ road height) is overhead furniture, not a blocker.  dy = base-y − road-y.
        OBJ_MAX_DY = parse(Float64, get(ENV,"JM_OBJ_MAX_DY","3.0"))
        objdy(ox,oz,oy) = (rh = JuliaMotor.hat3d(TERRAIN, Float64(ox), Float64(oz); ref=Inf); rh[3] ? round(Float64(oy)-rh[1],digits=1) : 0.0)
        kept_mesh  = [(nm,ox,oz,olat(ox,oz),objdy(ox,oz,oy)) for (nm,ox,oz,oy,kind,issolid) in OBJINSTS if kind===:mesh]
        kept_bb    = [(nm,ox,oz,olat(ox,oz),objdy(ox,oz,oy)) for (nm,ox,oz,oy,kind,issolid) in OBJINSTS if kind===:bb]
        kept_solid = [(nm,ox,oz,olat(ox,oz),objdy(ox,oz,oy)) for (nm,ox,oz,oy,kind,issolid) in OBJINSTS if issolid]
        println("\n==== JM_SWEEP ", uppercasefirst(TRACKSEL), "  (step=", round(Int,step),
                " m, total=", round(Int,CLINE.total), " m, ROAD_HALFW=", ROAD_HALFW, ") ====")
        groundz(RaceAI.pose_at(CLINE,0.0,0.0)[1], RaceAI.pose_at(CLINE,0.0,0.0)[3]; acquire=true)
        prevtop = JuliaMotor.hat3d(TERRAIN, RaceAI.pose_at(CLINE,0.0,0.0)[1], RaceAI.pose_at(CLINE,0.0,0.0)[3]; ref=Inf)
        nclean = 0; anoms = String[]
        s = 0.0
        while s <= CLINE.total
            p = RaceAI.pose_at(CLINE, s, 0.0); px, pz = p[1], p[3]
            top = JuliaMotor.hat3d(TERRAIN, px, pz; ref=Inf)
            hr  = JuliaMotor.hat(TRKSURF, px, pz)
            flags = String[]
            top[3] || push!(flags, "OFF-HAT(hole)")
            (top[3] && prevtop[3] && abs(top[1]-prevtop[1]) > 3.0) && push!(flags, "WALL/CLIFF Δh=$(round(top[1]-prevtop[1],digits=1))m")
            (!hr.found || abs(hr.lateral) > ROAD_HALFW) && push!(flags, "FALSE-GRASS lat=$(hr.found ? round(hr.lateral,digits=1) : "MISS")")
            sobs = ["$nm(lat=$lat,dy=$dy)" for (nm,ox,oz,lat,dy) in kept_solid if hypot(ox-px, oz-pz) < ROAD_HALFW && abs(lat) < ROAD_HALFW && dy < OBJ_MAX_DY]
            mobs = ["$nm(lat=$lat,dy=$dy)" for (nm,ox,oz,lat,dy) in kept_mesh if hypot(ox-px, oz-pz) < ROAD_HALFW && abs(lat) < BLOCK_LAT && dy < OBJ_MAX_DY]
            bobs = ["$nm(lat=$lat,dy=$dy)" for (nm,ox,oz,lat,dy) in kept_bb   if hypot(ox-px, oz-pz) < ROAD_HALFW && abs(lat) < BLOCK_LAT && dy < OBJ_MAX_DY]
            isempty(sobs) || push!(flags, "SOLID-ON-ROAD(collidable!): " * join(unique(sobs)[1:min(end,4)], ","))
            isempty(mobs) || push!(flags, "ON-ROAD MESH: " * join(unique(mobs)[1:min(end,4)], ","))
            isempty(bobs) || push!(flags, "ON-ROAD BILLBOARD: " * join(unique(bobs)[1:min(end,4)], ","))
            if isempty(flags); nclean += 1
            else; push!(anoms, string("  s=", lpad(round(Int,s),5), "  ", join(flags, " | ")))
            end
            prevtop = top; s += step
        end
        println(length(anoms), " anomaly point(s), ", nclean, " clean:")
        for a in anoms; println(a); end
        flush(stdout); exit(0)
    end
    AILINE = (CLINE !== nothing && N_AI > 0) ? CLINE : nothing
    AICARS = AILINE === nothing ? RaceAI.AICar[] : RaceAI.init_cars(AILINE, N_AI; start_s = 30.0)
    # B (PO): physics-based per-car pace.  power/weight → pace, tempered + normalised so the FASTEST car
    # present = 1.0 (it hits the GPLrank ref at 100 %); the rest spread back by their deficit so the field
    # strings out like GPL (the Eagle pulls away from the BRM) instead of running as a tight bunch.
    if !isempty(AICARS)
        pw = [AICAR_PHYS[i][1]/AICAR_PHYS[i][2] for i in 1:length(AICARS)]
        pwmax = maximum(pw)
        for (i, c) in enumerate(AICARS); c.pace = 1.0 - 0.35*(1.0 - pw[i]/pwmax); end
        # GRID by pace (fastest at the front — what qualifying would do) so the field spreads in the
        # RIGHT order: the quick cars lead and stretch the gap, instead of a fast car stuck mid-pack
        # behind a slower one on a tight track.  Keeps each car's identity; only the start slot moves.
        for (rank, ci) in enumerate(sortperm([c.pace for c in AICARS], rev=true))
            # s = 9·(N+1−rank): front car (rank 1) furthest along, all POSITIVE and < total so NO car
            # wraps just behind S/F (which made the back grid cross the line on frame 1 → a spurious +1
            # lap, the residual standings error).  Start every car cleanly on lap 0, just past the line.
            AICARS[ci].s = 9.0*(length(AICARS) + 1 - rank); AICARS[ci].lap = 0; AICARS[ci].lane = isodd(rank) ? -2.4 : 2.4
        end
        println("  → AI pace spread (power/weight, gridded fastest-first): ",
                join(["$(AISPECS[i][1]) $(round(Int,AICARS[i].pace*100))%" for i in 1:length(AICARS)], ", "))
    end
    AICHASSIS = AICARMODELS[1:length(AICARS)]   # grid slot i → AISPECS[i] (Ferrari, Brabham, …)
    # GC: build the AI as PHYSICS cars (one shared compile) placed on the grid; AICARS stays the
    # rail "brain" (s/lane/v/tlane/lap), updated each frame from the physics by projection.
    AIPHYS = AICarT[]
    if AI_PHYSICS && AILINE !== nothing && isempty(REPLAY_FILE)   # replay: AI poses come from the recording, no physics build needed
        print("  building $(length(AICARS)) physics AI (shared JM 3-D model)… "); flush(stdout)
        poses = [(p = RaceAI.pose_at(AILINE, c.s, c.lane); (p[1], p[3], p[4], 0.0)) for c in AICARS]
        AIPHYS = AIbuild(poses)
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
        for (i,pc) in enumerate(AIPHYS); p = RaceAI.pose_at(AILINE, AICARS[i].s, AICARS[i].lane); AIplace!(pc, p[1], p[3], p[4]; v=12.0); end
        N=length(AIPHYS); maxr=0.0; spins=0; maxlat=0.0; aidist=zeros(N); stuck=zeros(Int,N); scon=zeros(Int,N); lastx=[pc.x for pc in AIPHYS]; lastz=[pc.z for pc in AIPHYS]
        nstep=5400   # 90 s
        for _ in 1:nstep
            for (i,pc) in enumerate(AIPHYS)
                s,lat = RaceAI.project(AILINE, pc.x, pc.z); AICARS[i].s=s; AICARS[i].lane=lat; AICARS[i].v=pc.v
                maxlat = max(maxlat, abs(lat))
                aidist[i] += hypot(pc.x-lastx[i], pc.z-lastz[i]); lastx[i]=pc.x; lastz[i]=pc.z
                offhat = !JuliaMotor.hat3d(TERRAIN, pc.x, pc.z; ref=Inf)[3]
                railθ = RaceAI.pose_at(AILINE, s, 0.0)[4]
                spun = abs(atan(sin(pc.θ - railθ), cos(pc.θ - railθ))) > SPIN_LIM
                if pc.v < 1.4 || abs(lat) > 9.0 || offhat || spun      # mirror the live recovery (+ spin-save)
                    stuck[i]+=1; scon[i]+=1
                    lim = (offhat || abs(lat)>12.0 || spun) ? 6 : (abs(lat)>9.0 ? 18 : 90)
                    if scon[i] > lim; rp=RaceAI.pose_at(AILINE, s+10.0, 0.0); AIplace!(pc, rp[1], rp[3], rp[4]; v=max(8.0,pc.v*0.6)); scon[i]=0; end
                else; scon[i]=0; end
            end
            vts = RaceAI.plan!(AICARS, AILINE; scale=1.0, amax=AI_AMAX)
            for (i,pc) in enumerate(AIPHYS)
                r = AIyaw(pc); maxr = max(maxr, abs(r)); abs(r) > 2.5 && (spins += 1)
                thr,brk,st = RaceAI.controller(AILINE, AICARS[i].s, AICARS[i].lane, AICARS[i].tlane, vts[i], pc.x, pc.z, pc.θ, pc.v, r; power=AI_POWER)
                DriveRT3D.step_car3d!(pc, thr, brk, st, 1/60; manual=false, groundz=groundz)
                ho = solid_hit(pc.x, pc.z, pc.θ, pc.v); ho !== nothing && AIbump!(pc, ho[1], ho[2], ho[3], ho[4], ho[5], ho[6])   # E15 in the self-test too
            end
        end
        avgkmh = round.(Int, aidist ./ 90 .* 3.6)
        println("  AI self-test on $(TRACKSEL) (90s): dist=", round.(Int,aidist), "m  avg_kmh=$avgkmh  max_yaw=$(round(maxr,digits=2))  spins=$spins  max_lat=$(round(maxlat,digits=1))m  stuck=$stuck")
        println(spins < 30 && minimum(aidist) > 800 && maximum(stuck) < 200 ? "  ✓ physics AI lap the real track cleanly" : "  ⚠ AI struggle here — tune controller")
        exit(0)
    end
    # JM_AI_TEST for the KINEMATIC field (the default): step_field! for 90 s, report tracking.
    # Kinematic AI are rail-bound so they can't spin/leave the line — this verifies the field
    # ADVANCES (laps the track) and stays on-rail (low max_lat) on the big tracks (E38).
    if !AI_PHYSICS && haskey(ENV, "JM_AI_TEST") && AILINE !== nothing && !isempty(AICARS)
        nsec = clamp(something(tryparse(Int, get(ENV,"JM_AI_TEST","90")), 90), 1, 1200)
        N=length(AICARS); maxlat=0.0; aidist=zeros(N)
        lastp=[RaceAI.pose_at(AILINE, c.s, c.lane) for c in AICARS]
        for _ in 1:nsec*60
            poses,_ = RaceAI.step_field!(AICARS, AILINE, 1/60; scale=AI_SCALE, player=(-1e9,0.0,100.0), rel=AI_REL)
            for (i,p) in enumerate(poses)
                maxlat = max(maxlat, abs(RaceAI.project(AILINE, p[1], p[3])[2]))   # true lateral off the line (p[2] is ELEVATION)
                aidist[i] += hypot(p[1]-lastp[i][1], p[3]-lastp[i][3]); lastp[i]=p
            end
        end
        avgkmh = round.(Int, aidist ./ nsec .* 3.6)
        println("  KINEMATIC AI self-test on $(TRACKSEL) ($(nsec)s): dist=", round.(Int,aidist), "m  avg_kmh=$avgkmh  max_lat=$(round(maxlat,digits=1))m")
        # R1 PROOF: progress = lap + lap-fraction.  The OLD standings used c.lap + c.s/total, but c.s
        # ACCUMULATES so c.s/total == the lap count again → ~2× (the bug).  The FIX uses the fraction.
        for (i,c) in enumerate(AICARS)
            oldp = c.lap + c.s/AILINE.total; newp = c.lap + mod(c.s, AILINE.total)/AILINE.total
            println("    ", rpad(AISPECS[i][1],8), " lap=", c.lap, "  OLD prog=", round(oldp,digits=2),
                    " (2× bug)   NEW prog=", round(newp,digits=2), " ✓")
        end
        println(minimum(aidist) > 800 && maxlat < 12.0 ? "  ✓ kinematic AI lap the real track on-rail (no spins possible)" : "  ⚠ field not advancing / off-rail — check AILINE")
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
    ai_lap_prev = zeros(Int, length(AICARS))  # C: previous-frame AI lap counter → detect a completed lap → time it
    ai_onroad = trues(length(AIPHYS))         # per-AI: on the real racing surface this frame? (grass + draft gate)
    ffb_f = 0.0                                       # low-pass-filtered FFB force (continuity across frames)
    ffb_jolt = 0.0                                    # transient FFB jolt on collisions/impacts (decays each frame)
    fy_lp = 0.0                                        # low-pass front-axle force for FFB (de-spikes the coarse mesh)
    tc_hud = ntuple(_->(0.0,0.0,1.0), 4)              # smoothed traction-circle display (kills coarse-mesh flicker)
    v_prev = cs.v; pitch_dyn = 0.0; pitch_ter = 0.0; roll_ter = 0.0    # dive/squat + terrain-slope pitch + cross-slope roll (smoothed)
    cam_pitch = 0.0; cam_roll = 0.0                                    # E53: low-pass head tilt for the cockpit camera (lags fast jolts)
    # lap timing + telemetry log
    lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = cs.laps; tsamp = 0; race_done = false; enterPrev = false
    # C (PO): GPL-style results — the player's per-lap times, plus each AI car's lap clock so we can
    # report the best lap turned by ANYONE.  ai_lapt0 = the wall-clock at which each AI's current lap began.
    player_laps = Float64[]                                   # the player's completed lap times (s), in order
    ai_lapt0 = zeros(length(AICARS)); ai_best = fill(Inf, length(AICARS))   # AI lap timing → best lap per car
    player_s_prev = CLINE === nothing ? 0.0 : RaceAI.project(CLINE, cs.x, cs.z)[1]   # for robust lap detection
    player_prog = 0.0                                                                # accumulated track arc-length (laps = ⌊prog/total⌋)
    fmt_lap(s) = (m=floor(Int,s/60); sec=s-60m; si=floor(Int,sec); ms=round(Int,(sec-si)*1000);
                  "$m:$(lpad(si,2,'0')).$(lpad(ms,3,'0'))")
    # A3: maintain a per-track human-best-lap file (human_best.txt: "<track>\t<seconds>") the GUI reads to
    # pre-set the AI-speed %.  Merge-and-rewrite so existing tracks survive; only overwrite if this is faster.
    function save_human_best(track, t)
        try
            path = joinpath(@__DIR__, "human_best.txt")
            bests = Dict{String,Float64}()
            isfile(path) && for ln in eachline(path)
                sp = split(strip(ln), '\t')
                length(sp) == 2 && (v = tryparse(Float64, sp[2])) !== nothing && (bests[sp[1]] = v)
            end
            (!haskey(bests, track) || t < bests[track]) || return     # not an improvement → leave the file
            bests[track] = t
            open(path, "w") do io; for (k,v) in bests; println(io, "$k\t$(round(v, digits=3))"); end; end
        catch e; @warn "human_best write failed" e; end
    end
    # ---- E9: qualifying → grid order ----
    # One qualifying lap sets the grid: the field is arranged around the player by qual
    # time (faster qualifiers start ahead on track, slower behind).  Skipped for solo
    # races, the skidpad, JM_NOQUAL, and headless smoke (which can't drive a lap).
    # Qualifying is OPT-IN (JM_QUAL).  By default a Race goes STRAIGHT TO THE GRID with all AI lined
    # up ahead (form_grid!(Inf) below) and visible — floor it to launch.  The old default ran a 15-min
    # PRACTICE first during which the AI were HIDDEN, so "select Race" looked like "no AI appeared" (PO).
    DO_QUAL  = IS_RACE && N_AI > 0 && !SKIDPAD && haskey(ENV,"JM_QUAL") && !SMOKE
    phase    = Ref(DO_QUAL ? :practice : :race)
    player_grid = Ref(0); player_finpos = Ref(0)
    # Standing start: in a race the AI sit on the grid until YOU floor the throttle, then
    # the whole field launches together — so you never miss the start by looking away.
    HOLD_START = IS_RACE && N_AI > 0 && !SKIDPAD && !SMOKE
    race_go    = Ref(!HOLD_START)
    launch_done = Ref(false)     # the initial standing-start getaway is over (car has reached speed once)
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
            # a car gridded BEHIND the player wraps to just-behind S/F, so it crosses the line on the first
            # frames — that start-line crossing is NOT a completed lap, so start it on lap −1 to absorb it
            # (else its lap count runs 1 high and it "laps" you in the standings).
            c.v = 0.0; c.lap = (r > prank) ? -1 : 0
            c.lane = isodd(r) ? GRID_LANE : -GRID_LANE; c.tlane = c.lane
            AI_PHYSICS && (gp = RaceAI.pose_at(AILINE, c.s, c.lane); AIplace!(AIPHYS[i], gp[1], gp[3], gp[4]; v=0.0))
        end
        println(isfinite(qtime) ? "\n  ═══ GRID (from your practice best) ═══" : "\n  ═══ GRID ═══")
        for (p, id) in enumerate(order)
            println("   P$p  ", id==0 ? (isfinite(qtime) ? "You — $(fmt_lap(qtime))" : "You (no practice lap)") : AICHASSIS[id].name)
        end
        println("  → You start P$prank of $(length(order)) — floor it to launch the field\n"); flush(stdout)
        prank
    end
    DO_QUAL && println("\n  PRACTICE ($(round(Int,PRACTICE_SEC/60)) min) — lap to set your grid slot (your best lap = your\n  starting position; no lap = back of the grid).  Press T to ACCELERATE TIME straight to the race.")
    # NO-QUAL race: form a proper 2-wide grid up front with YOU at the back (no qual time ⇒ last),
    # so the field starts in ordered rows ahead and you watch them launch — instead of the ad-hoc
    # init-stagger that put cars beside you and then snapped them into line on the first frames.
    if !DO_QUAL && HOLD_START
        player_grid[] = form_grid!(Inf)
    end
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
            # R1 FIX: c.s ACCUMULATES (never wrapped) and c.lap already counts the laps, so c.s/total is
            # the lap COUNT again — the old `c.lap + c.s/total` double-counted (2× laps) and "lapped" you.
            # Use only the FRACTION of the current lap.
            push!(entries, (i, c.lap + (AILINE === nothing ? 0.0 : mod(c.s, AILINE.total)/AILINE.total)))
        end
        sort!(entries, by = e -> -e[2])                # most progress = P1
        entries
    end
    ent_name(id) = id == 0 ? "You" : AICHASSIS[id].name
    ibt_samples = IBTREC ? Dict{String,Float64}[] : nothing      # iRacing-format telemetry rows
    # E18: record ALL car poses (player + AI) for replay — a flat Float32 buffer, ~15 Hz, written .jmr at exit
    REPLAY_REC = IS_RACE && N_AI > 0 && isempty(REPLAY_FILE) && !haskey(ENV,"JM_NOREPLAY") && (!SMOKE || haskey(ENV,"JM_REPLAY_REC"))
    replay_buf = REPLAY_REC ? Float32[] : nothing; replay_t = Ref(-1.0); REPLAY_NCAR = 1 + length(AICARS)
    IBTREC && println("  recording iRacing .ibt telemetry (JM_IBT) — template: ", basename(IBTTMPL))
    # E18 PLAYBACK: load the recording; the loop sets poses from it instead of simulating (VCR keys below).
    REPLAY = !isempty(REPLAY_FILE)
    repd = REPLAY ? deserialize(REPLAY_FILE) : nothing
    rep_rt = Ref(parse(Float64,get(ENV,"JM_REPLAY_T","0.0"))); rep_play = Ref(true); rep_speed = Ref(1.0)
    rep_psp = Ref(false); rep_pup = Ref(false); rep_pdn = Ref(false)   # VCR key edge-detect
    rep_focus = Ref(clamp(parse(Int,get(ENV,"JM_REPLAY_FOCUS","0")), 0, REPLAY ? repd.ncar-1 : 0))   # E25: focus car (0=player, 1.. = AI)
    rep_cam = Ref(clamp(parse(Int,get(ENV,"JM_REPLAY_CAM","2")), 1, length(REPLAY_CAMS)))             # E25: camera mode index (start CHASE)
    rep_pn = Ref(false); rep_pv = Ref(false)                          # E25: C (switch car) / V (switch angle) edge-detect
    rep_dur = REPLAY ? max(repd.nframes - 1, 0)/repd.fps : 0.0
    rep_st  = REPLAY ? 1 + 4*repd.ncar : 0
    # interpolated poses at replay time rt → (player (x,y,z,θ), Vector of AI (x,y,z,θ))
    function replay_poses(rt)
        d = repd.data; nf = repd.nframes; f = clamp(rt*repd.fps, 0.0, nf-1.0)
        i0 = floor(Int, f); i1 = min(i0+1, nf-1); g = f - i0
        b0 = i0*rep_st; b1 = i1*rep_st
        lerp(o) = d[b0+o]*(1-g) + d[b1+o]*g
        lerpθ(o) = (a=d[b0+o]; a + (mod(d[b1+o]-a+π, 2π)-π)*g)   # shortest-arc heading lerp
        player = (lerp(2), lerp(3), lerp(4), lerpθ(5))
        ais = NTuple{4,Float64}[]
        for k in 1:(repd.ncar-1); o = 5 + 4*(k-1); push!(ais, (lerp(o+1), lerp(o+2), lerp(o+3), lerpθ(o+4))); end
        (player, ais)
    end
    REPLAY && println("  ▶ REPLAY: $(basename(REPLAY_FILE)) — $(repd.nframes) frames, $(round(rep_dur,digits=1))s, $(repd.ncar) cars\n" *
        "  SPACE play/pause · ←/→ seek · ↑/↓ speed · V switch ANGLE (cockpit/chase/TV/F10/nose/RR-susp) · C switch CAR · Esc quit")
    telem = SMOKE ? nothing : open("zand_racer_$(round(Int,time())).txt", "w")
    telem !== nothing && write(telem,
        "# zand_racer telemetry — Lotus 49 @ Zandvoort\n# t\tlap\tlapdist\tkmh\tthr\tbrk\tsteer\tclu\tgear\trpm\tx\tz\tlat\talong\tontrack\n")
    println("\n  Drive:  W/S gas·brake   A/D steer   E/Q shift   C clutch   R respawn   ⇧R recover-to-track   V view   G auto⇄manual   M mute   Esc quit"); flush(stdout)
    println("  AUTO gearbox by default — just press the throttle and go (no clutch needed).  Press G for")
    println("  MANUAL: hold the clutch (C / stick button) to shift E/Q (release it too low and it bogs).")
    println("  Lap times top-left: white = last, green = best.  Telemetry → ./zand_racer_*.txt")
    println("  (Logitech joystick works natively — push=throttle, pull=brake, roll=steer)\n")
    EngineAudio.start(ENG)   # start audio NOW (after the long track load) — starting it mid-load
                             # let the stream underflow on big tracks (Nürburgring) and go silent
    SMOKE || GLFW.ShowWindow(win)   # reveal the window now that loading is done (avoids the WM "Not Responding")
    # E59 multi-shot smoke state: current shot, the frame it was placed on, all-done flag.
    shot_idx = Ref(0); shot_t0 = Ref(0); shots_done = Ref(isempty(SHOTS))
    if SMOKE && !isempty(SHOTS)
        shot_idx[] = 1; shot_t0[] = 0
        CTL.view = SHOTS[1].view
        place_at_s!(SHOTS[1].s)
        println("  JM_SHOTS: ", length(SHOTS), " shots → ", SHOTS_DIR); flush(stdout)
    end
    while !GLFW.WindowShouldClose(win)
        GLFW.PollEvents()
        key(GLFW.KEY_ESCAPE) && break
        SMOKE && isempty(SHOTS) && frames >= 40 && break
        SMOKE && shots_done[] && !isempty(SHOTS) && break
        now = time(); dt = clamp(now-last, 0.0, 0.05); last = now
        inp, rst, recover = read_input()
        if REPLAY                                   # E18 PLAYBACK: VCR + set poses from the recording, skip the sim
            sp = key(GLFW.KEY_SPACE); (sp && !rep_psp[]) && (rep_play[] = !rep_play[]); rep_psp[] = sp
            up = key(GLFW.KEY_UP);   (up && !rep_pup[]) && (rep_speed[] = clamp(rep_speed[]*2, 0.25, 8.0)); rep_pup[] = up
            dn = key(GLFW.KEY_DOWN); (dn && !rep_pdn[]) && (rep_speed[] = clamp(rep_speed[]/2, 0.25, 8.0)); rep_pdn[] = dn
            key(GLFW.KEY_RIGHT) && (rep_rt[] = clamp(rep_rt[] + 8*dt, 0.0, rep_dur))   # hold to scrub
            key(GLFW.KEY_LEFT)  && (rep_rt[] = clamp(rep_rt[] - 8*dt, 0.0, rep_dur))
            rep_play[] && (rep_rt[] = clamp(rep_rt[] + dt*rep_speed[], 0.0, rep_dur))
            cf = key(GLFW.KEY_C); (cf && !rep_pn[]) && (rep_focus[] = mod(rep_focus[]+1, repd.ncar)); rep_pn[] = cf   # E25: switch CAR
            cvv = key(GLFW.KEY_V); (cvv && !rep_pv[]) && (rep_cam[] = mod1(rep_cam[]+1, length(REPLAY_CAMS))); rep_pv[] = cvv  # E25: switch ANGLE
            (pp, rep_ai_raw) = replay_poses(rep_rt[])
            cs.x = pp[1]; cs.y = pp[2]; cs.z = pp[3]; cs.θ = pp[4]; cs.v = 0.0; cs.pitch = 0.0; cs.roll = 0.0
            # cockpit interior only renders for the player car in COCKPIT mode; every other angle shows the driver figure + full car
            CTL.view = (REPLAY_CAMS[rep_cam[]] === :cockpit && rep_focus[] == 0) ? 0 : 1
            @goto skipsim
        end
        # E9: end qualifying on ENTER (or it auto-ends on a clean lap).  This guarantees you
        # can always start the race even if the S/F line doesn't register the lap (the ribbon
        # can have a seam at start/finish).  Your qual time = best clean lap, else estimated
        # from how far round you got (so a near-complete lap still earns a fair grid slot).
        # END PRACTICE → go to the race grid: press T (accelerate time) or ENTER, or the practice clock
        # runs out (PRACTICE_SEC).  Your grid slot = your best practice lap (none → back of the grid).
        accelNow = key(GLFW.KEY_T) || key(GLFW.KEY_ENTER) || key(GLFW.KEY_KP_ENTER)
        if phase[] == :practice && ((accelNow && !enterPrev) || cs.t >= PRACTICE_SEC)
            qt = best_lap > 0.0 ? best_lap : Inf       # no clean practice lap ⇒ start at the back
            player_grid[] = form_grid!(qt)
            phase[] = :race
            cs.laps = 0; last_lap = 0.0; best_lap = 0.0; race_done = false; lap_t0 = cs.t
            launch_done[] = false                       # re-arm the launch assist for the actual race start
            FUEL_ON && (fuel[] = burn_lap * fuel_laps)   # always start the race on a FULL tank (no practice carry-over)
        end
        enterPrev = accelNow
        # green light: the field launches the moment you ask for throttle (standing start)
        if HOLD_START && !race_go[] && phase[] == :race && inp.throttle > 0.15
            race_go[] = true; lap_t0 = cs.t          # start the clock at the launch
            # PO: the AI must NOT all launch perfectly — some bog / fluff a shift / spin up at the getaway.
            # Each car independently has a chance to fumble (a brief mishap = crawl), varying in severity, so
            # the field doesn't magically sail away in formation; the rest get clean launches.
            for c in AICARS
                rand() < 0.45 && (c.mishap = 0.4 + 1.4*rand())
            end
        end
        # LAUNCH ASSIST: the on-screen prompt is "floor the throttle to start", so flooring it MUST get
        # you rolling even in MANUAL — auto-engage the gearbox + drop the clutch for the initial getaway
        # only (until the car first reaches speed), then hand fully back to manual shifting.  Without it
        # the car sits in neutral / bogs on the line.
        # E39: latch launch_done only once the car is genuinely ROLLING (12 km/h), and keep the assist
        # engaged the WHOLE way there (no speed ceiling) — the old assist cut out at 6 km/h while the
        # latch was at 9, leaving a 6–9 km/h dead gap where, on the uphill Spa/Nürburgring starts, the
        # clutch returned to manual, the engine fell to idle (~1950 rpm pinned) and the car bogged/oscillated.
        race_go[] && cs.v > 12.0 && (launch_done[] = true)
        if race_go[] && !rst && !CTL.auto && !launch_done[] && inp.throttle > 0.05
            inp = DriveInput(throttle=inp.throttle, brake=inp.brake, steer=inp.steer,
                             clutch=0.0, shift_up=false, shift_down=false, autoshift=true)
        end
        # E10: burn fuel by distance (only once the race is GREEN — never while you sit on the grid
        # waiting to launch, or you could starve the tank before you've even pressed the throttle).
        if FUEL_ON && race_go[] && !rst
            fuel[] = max(0.0, fuel[] - FUEL_LPK * cs.v * (dt > 1e-4 ? dt : 1/60) / 1000)
            fuel[] <= 0 && (inp = DriveInput(throttle=0.0, brake=inp.brake, steer=inp.steer,
                            clutch=inp.clutch, shift_up=inp.shift_up, shift_down=inp.shift_down, autoshift=inp.autoshift))
        end
        rst && FUEL_ON && (fuel[] = burn_lap * fuel_laps)        # respawn refuels
        if recover && CLINE !== nothing && CAR3D
            # SHIFT-R: drop back onto the centreline at the CURRENT lap position, upright + stopped.
            sR = RaceAI.project(CLINE, cs.x, cs.z)[1]; pR = RaceAI.pose_at(CLINE, sR, 0.0)
            # PO round 4: "SH-R never puts you in the CENTRE of the track, always off to one side."  On Monza
            # the recentre is OFF, so lane-0 is the raw .trk GROOVE — which hugs the road edge.  Drop on the
            # road's GEOMETRIC centre instead: scan left+right along the lateral normal to the road-mesh edges
            # and offset to the midpoint.  (On recentred tracks the offset comes out ≈0 — lane-0 is already
            # centred — so this is safe everywhere.)
            cx0, cz0, θ0 = pR[1], pR[3], pR[4]
            nLx = -sin(θ0); nLz = cos(θ0)                              # left-hand normal
            onroadR(x, z) = JuliaMotor.hat3d(TERRAIN0, x, z; ref = Inf)[3]
            hiR = 0.0; while hiR < 10.0 && onroadR(cx0 + nLx*(hiR+0.5), cz0 + nLz*(hiR+0.5)); hiR += 0.5; end
            loR = 0.0; while loR < 10.0 && onroadR(cx0 - nLx*(loR+0.5), cz0 - nLz*(loR+0.5)); loR += 0.5; end
            offR = clamp((hiR - loR)/2, -5.0, 5.0)
            cxR = cx0 + nLx*offR; czR = cz0 + nLz*offR
            DriveRT3D.place3d!(cs, cxR, czR, θ0; v=0.0)
            pR = (cxR, pR[2], czR, θ0)
            cs.s_vreset(cs.integ, zeros(14))
            hR = groundz(pR[1], pR[3]; acquire=true); isfinite(hR) && (cs.zref = Float64(hR))
            cs.heave = 0.0; cs.pitch = 0.0; cs.roll = 0.0; cs.y = cs.zref
        elseif rst; respawnX!(cs; groundz=groundz)
        else
            # E56 ALL-MODELICA human car: feed the trackside spring-damper CONTACT force (wall = bounce,
            # hedge/hay = bury & stick) + last frame's draft drag-scale into the chassis ODE BEFORE the
            # step, so both are forces the solver INTEGRATES — no post-step bumpX!/containX! state hack.
            if CAR3D
                cfx = cfy = cmz = 0.0
                if !SKIDPAD && !rst
                    (cfx, cfy, cmz, cpk) = solid_contact(cs.x, cs.z, cs.θ, cs.v, dt > 1e-4 ? dt : 1/60)
                    cpk > 1.0e3 && (ffb_jolt = clamp(sign(cmz != 0 ? cmz : 1.0) * min(cpk/4.0e4, 1.0), -1.0, 1.0))  # feel the hit (stronger — PO: object kick was too small)
                end
                # add last frame's world-edge physical-wall force (E56.6) to the trackside contact force
                DriveRT3D.extforce3d!(cs; Fx = cfx + BND_FX[], Fy = cfy + BND_FY[], Mz = cmz + BND_MZ[],
                                      CdA_scale = PLAYER_CDA[])
                # E56 grass = per-wheel tyre μ: any wheel off the racing surface loses real grip (and
                # pulls the car) in the brush model — replaces the bumpX! grass drag/yaw hack (which is
                # now AI-only).  Only project the 4 wheels when the car is near/over the edge (cheap on-track).
                μFL = μFR = μRL = μRR = 1.0
                if !SKIDPAD && !rst
                    hc = JuliaMotor.hat(TRKSURF, cs.x, cs.z)
                    if hc.found && abs(hc.lateral) > ROAD_HALFW - 1.2
                        cθg = cos(cs.θ); sθg = sin(cs.θ)
                        wmu(xi, yi) = (wx = cs.x + xi*cθg - yi*sθg; wz = cs.z + xi*sθg + yi*cθg;
                                       hw = JuliaMotor.hat(TRKSURF, wx, wz);
                                       (hw.found && abs(hw.lateral) > ROAD_HALFW) ? GRASS_MU : 1.0)
                        μFL = wmu( 1.314,  0.75); μFR = wmu( 1.314, -0.75)
                        μRL = wmu(-1.096,  0.75); μRR = wmu(-1.096, -0.75)
                    end
                end
                DriveRT3D.wheelmu3d!(cs, μFL, μFR, μRL, μRR)
            end
            step_carX!(cs, inp.throttle, inp.brake, inp.steer, dt > 1e-4 ? dt : 1/60;
                        clutch=inp.clutch, up=inp.shift_up, dn=inp.shift_down, manual=!inp.autoshift,
                        groundz=groundz)
            if !SKIDPAD     # track position + lap timing
            hr = JuliaMotor.hat(TRKSURF, cs.x, cs.z)            # track-relative position (for lapdist/lateral HUD)
            if hr.found
                cs.lapdist = hr.lapdist; cs.lateral = hr.lateral; cs.along = hr.lapdist; cs.ontrack = hr.on_track
            else; cs.ontrack = false; end
            # ROBUST lap counting via ACCUMULATED track progress (a lap = a lap's worth of arc-length
            # covered), so it counts even if you cross the line OFF the road (slid wide at the finish).
            if CLINE !== nothing
                ps = RaceAI.project(CLINE, cs.x, cs.z)[1]
                ds = ps - player_s_prev
                ds < -CLINE.total/2 && (ds += CLINE.total); ds > CLINE.total/2 && (ds -= CLINE.total)  # unwrap
                race_go[] && abs(ds) < CLINE.total*0.4 && (player_prog += ds)   # ignore projection jumps
                player_s_prev = ps
                while cs.laps < floor(Int, player_prog/CLINE.total); cs.laps += 1; end
            end
            # E56: the PLAYER grass penalty is now per-wheel tyre μ applied BEFORE the step (above) —
            # a wheel off the racing surface loses real grip in the brush model and pulls the car, rather
            # than the old post-step bumpX! drag/yaw scrub.  (The AI keep the bumpX! grass penalty.)
            # E7 boundary = the WORLD edge (the terrain HAT): you can drive the road AND the grass
            # freely, but if you go off the HAT you've left the world → snap back to the last spot
            # inside it (a fence/hedge collision) and bleed speed.  (Based on the HAT, NOT the racing
            # line, so it never slows you on a wide road/grass — that was the Watkins Glen "molasses".)
            # A short off-HAT distance GRACE (JM_FENCE_GRACE m) lets the car cross narrow mesh seams
            # / bridge gaps in the HAT (e.g. 4 on the Nürburgring racing line) without a false
            # containment; a genuine excursion exceeds it within a few metres and is held at the edge.
            if ONTRACK[]; LASTGX[] = cs.x; LASTGZ[] = cs.z; OFFDIST[] = 0.0   # inside the world
                BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0               # E56: release the world-edge wall
            elseif hr.found && abs(hr.lateral) < ROAD_HALFW
                # E52: off the TERRAIN .3do mesh but still inside the road corridor (the .trk ribbon
                # is continuous) → a gap in the collision mesh UNDER the Monza banking overpass, not the
                # world edge.  Coast through at the held height; advance the in-world anchor so the
                # FENCE_GRACE containment never fires across the (~20 m) underpass.
                LASTGX[] = cs.x; LASTGZ[] = cs.z; OFFDIST[] = 0.0
                BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0
            else
                OFFDIST[] += cs.v * (dt > 1e-4 ? dt : 1/60)
                # E56: the WORLD EDGE is now a PHYSICAL WALL, not a position snap-back.  nl = the car's
                # straight-line distance past the last in-world spot = the instantaneous penetration; feed a
                # stiff spring-damper (the same contact_force(:wall) kernel) back INTO the world so the car
                # bounces off the edge as a real wall — no teleport.  Recovery from a spin/excursion is
                # SHIFT-R only (the auto routine snap-back is gone).  FENCE_GRACE keeps the wall off narrow
                # HAT mesh seams; a last-resort hard containment (FENCE_FAR) still seals the world if the
                # wall somehow fails (so the car can NEVER fall into the void).
                nwx = LASTGX[]-cs.x; nwz = LASTGZ[]-cs.z; nl = hypot(nwx,nwz)   # wall normal: back into the world
                nl < 1e-3 && (nwx = cos(cs.θ+π); nwz = sin(cs.θ+π); nl = 1.0)
                nwx /= nl; nwz /= nl
                if nl > FENCE_GRACE
                    pvx = cs.v*cos(cs.θ); pvz = cs.v*sin(cs.θ)
                    vn = pvx*nwx + pvz*nwz                       # car speed along the INWARD normal (<0 = leaving)
                    gdt = dt > 1e-4 ? dt : 1/60
                    (bfx, bfy, bmz) = DriveRT3D.contact_force(nl - FENCE_GRACE, nwx, nwz, vn, cs.θ; kind = :wall, dt = gdt)
                    BND_FX[] = bfx; BND_FY[] = bfy; BND_MZ[] = bmz
                    ffb_jolt = clamp(-vn*0.05, -1.0, 1.0)        # FF jolt off the world-edge wall
                    if nl > FENCE_GRACE + FENCE_FAR              # the wall failed to contain → last-resort seal (rare; never in normal play)
                        containX!(cs, LASTGX[], LASTGZ[]; vdamp=0.3, settle=true, groundz=groundz)
                        BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; OFFDIST[] = 0.0
                    end
                else
                    BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0
                end
            end
            end
        end
        # E56: the player's trackside-object collision is now the all-Modelica spring-damper CONTACT
        # force applied BEFORE the step (above) — the old post-step solid_hit→bumpX! state hack is gone.
        # (The AI still use the kinematic solid_hit; they're slot cars.)
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
            # the impact JOLT takes PRIORITY over the steering force: scale the road/spring force down by
            # the jolt size so a hit is always FELT, even mid-corner when ffb_f is already near full lock
            # (otherwise `ffb_f + jolt` just clamps and you feel nothing — why AI hits read as "no kick").
            FFB.set_force!(ffb, clamp(ffb_f*(1.0 - min(abs(ffb_jolt), 1.0)) + ffb_jolt, -1.0, 1.0))
        end
        ffb_jolt *= exp(-(dt > 1e-4 ? dt : 1/60)/0.06)              # the impact jolt decays fast (~60 ms)

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
            improved = best_lap == 0.0 || last_lap < best_lap
            improved && (best_lap = last_lap)
            phase[] == :race && push!(player_laps, last_lap)   # C: bank this lap for the per-lap results tab
            # A3: persist the player's best lap for THIS track (practice OR race) the moment it improves, so
            # the GUI can pre-set the AI-speed % to the pace matching the human's best (≈ GPLrank/best·100).
            improved && cs.laps >= 1 && save_human_best(TRACKSEL, best_lap)
            telem !== nothing && (write(telem, "# LAP $(cs.laps)  $(fmt_lap(last_lap))\n"); flush(telem))
            println(phase[] == :practice ? "  practice lap: $(fmt_lap(last_lap))" : "  lap $(cs.laps): $(fmt_lap(last_lap))",
                    last_lap==best_lap ? "  (best)" : "")   # practice laps just bank your best for the grid
            begin
            if phase[] == :race && cs.laps >= RACE_LAPS && !race_done    # race distance complete
                race_done = true
                println("\n  ═══════ RACE FINISHED — $RACE_LAPS laps ═══════")
                order = isempty(AICARS) ? [(0, 0.0)] : standings()
                player_finpos[] = findfirst(e -> e[1] == 0, order)
                println("\n  ══════ YOU FINISHED — P$(player_finpos[]) of $(length(order)) ══════")
                println("  started P$(player_grid[])   best lap $(fmt_lap(best_lap))   total $(fmt_lap(cs.t))")
                # R1 DIAG (PO finished-6th-when-1st): dump the ACTUAL progress the standings ranked on, so a
                # mismatch with what you saw on track is unambiguous.  AI pace + the raw lap+fraction each.
                println("  ── R1 DIAG  (AI pace ", round(Int,AI_PCT), "% → target ", round(AI_TGT,digits=1),
                        "s/lap;  YOU laps=", cs.laps, " prog=", round(player_prog/(CLINE===nothing ? 1 : CLINE.total), digits=2), ") ──")
                for (i,c) in enumerate(AICARS)
                    println("     ", rpad(AISPECS[i][1],8), " lap=", c.lap, " prog=", round(c.lap + mod(c.s, AILINE.total)/AILINE.total, digits=2),
                            " v=", round(Int,c.v*3.6), "km/h pace=", round(Int,c.pace*100), "%")
                end
                println("  ── final classification ──")
                for (p, (id, _)) in enumerate(order)
                    println("   P$p  ", ent_name(id), id==0 ? "  ← YOU (best $(fmt_lap(best_lap)))" : "")
                end
                println()
                # C (PO): GPL-style classification with a TIME GAP to the winner.  Each car's total race
                # time is its elapsed time scaled to the full distance (cs.t · LAPS / progress) — the leader
                # (most progress) has the smallest, so gap = est − leader_est ≥ 0; a car a full lap or more
                # down is shown "+N lap(s)" instead.  Best lap of ANYONE = min(player best, every AI best).
                lead_prog = order[1][2]
                est_time(prog) = cs.t * RACE_LAPS / max(prog, 0.01)
                lead_est = est_time(lead_prog)
                # best lap turned by anyone in the field (player or an AI)
                best_any = best_lap > 0 ? best_lap : Inf; best_any_who = best_lap > 0 ? "You" : "-"
                for i in 1:length(AICARS)
                    if ai_best[i] < best_any; best_any = ai_best[i]; best_any_who = ent_name(i); end
                end
                # E14: write the result for the GUI's post-race results screen (quit / race again / choose track)
                try
                    open(joinpath(@__DIR__, "last_race_result.txt"), "w") do io
                        println(io, "track\t$(TRACKSEL)"); println(io, "laps\t$RACE_LAPS")
                        println(io, "you_pos\t$(player_finpos[])"); println(io, "field\t$(length(order))")
                        println(io, "you_start\t$(player_grid[])")
                        println(io, "you_best\t$(best_lap > 0 ? fmt_lap(best_lap) : "-")"); println(io, "you_total\t$(fmt_lap(cs.t))")
                        println(io, "best_any\t$(isfinite(best_any) ? fmt_lap(best_any) : "-")\t$best_any_who")
                        println(io, "you_laps\t", join((fmt_lap(t) for t in player_laps), ","))   # C: per-lap times tab
                        println(io, "win_total\t$(fmt_lap(lead_est))")   # PO: the WINNER's total elapsed time (top row, right)
                        for (p, (id, prog)) in enumerate(order)
                            laps_down = floor(Int, lead_prog - prog)
                            # PO: the winner's row shows the winner's TOTAL TIME; everyone else a gap (or +N laps)
                            gap = p == 1 ? fmt_lap(lead_est) :
                                  (laps_down >= 1 ? "+$laps_down lap$(laps_down>1 ? "s" : "")" :
                                                    "+$(fmt_lap(est_time(prog) - lead_est))")
                            println(io, "P$p\t$(ent_name(id))\t$gap")   # name + gap-to-winner column
                        end
                    end
                catch e; @warn "result write failed" e; end
                # B (PO): pre-fill the AI % from the driver's MOST RECENT race AVERAGE on this track (not the
                # best lap) — so the field is paced to how you ACTUALLY race, not a one-off hot lap.  Overwrite
                # (most-recent, not best) with this race's mean lap time.
                if !isempty(player_laps)
                    avg = sum(player_laps)/length(player_laps)
                    try
                        rp = joinpath(@__DIR__, "human_recent.txt"); recents = Dict{String,Float64}()
                        isfile(rp) && for ln in eachline(rp)
                            sp = split(strip(ln), '\t'); length(sp)==2 && (v=tryparse(Float64,sp[2]))!==nothing && (recents[sp[1]]=v)
                        end
                        recents[TRACKSEL] = avg
                        open(rp, "w") do io; for (k,v) in recents; println(io, "$k\t$(round(v,digits=3))"); end; end
                    catch e; @warn "human_recent write failed" e; end
                end
            end
            end
        elseif cs.laps < prev_laps                 # respawn reset the lap counter
            lap_t0 = cs.t
        end
        prev_laps = cs.laps
        if telem !== nothing && (tsamp += 1) % 6 == 0
            write(telem, "$(round(cs.t,digits=2))\t$(cs.laps)\t$(round(cs.lapdist,digits=1))\t$(round(cs.v*3.6,digits=1))\t$(round(inp.throttle,digits=2))\t$(round(inp.brake,digits=2))\t$(round(inp.steer,digits=2))\t$(round(inp.clutch,digits=2))\t$(cs.gear)\t$(round(Int,cs.rpm))\t$(round(cs.x,digits=1))\t$(round(cs.z,digits=1))\t$(round(cs.lateral,digits=2))\t$(round(cs.along,digits=2))\t$(cs.ontrack ? 1 : 0)\n")
        end

        @label skipsim   # E18 replay jumps here — cs pose is already set from the recording
        # ---- body pitch: accel→squat (nose up), brake→dive (nose down); + terrain slope ----
        acc = clamp((cs.v - v_prev)/max(dt,1e-3), -15.0, 15.0); v_prev = cs.v
        pitch_ter += (terrain_pitch(cs) - pitch_ter) * min(1.0, dt*6)
        roll_ter  += (terrain_roll(cs)  - roll_ter)  * min(1.0, dt*6)   # car lists with the cross-slope (3-D)
        rollv = 0.0
        if CAR3D
            pitch_dyn = (cs.pitch - pitch_ter) * SUSP_GAIN   # REAL body pitch (minus the slope carModel already applies), visually amplified
            rollv = cs.roll * SUSP_GAIN                      # REAL body roll
        else
            # planar model has no 3-D body state — synthesise dive/squat + corner roll from the
            # longitudinal accel / steering so the chassis still pitches/rolls over the planted wheels.
            pitch_dyn += (clamp(-0.010*acc, -0.06, 0.06)*SUSP_GAIN - pitch_dyn) * min(1.0, dt*4.0)   # brake → nose DOWN
            rollv     += (clamp(-0.05*inp.steer*min(cs.v/20,1.0), -0.05, 0.05)*SUSP_GAIN - rollv) * min(1.0, dt*4.0)  # corner lean
        end
        pitch_dyn = clamp(pitch_dyn, -0.11, 0.11); rollv = clamp(rollv, -0.10, 0.10)   # ±~6° cap (no over-rotate)
        REPLAY && (pitch_dyn = 0.0; rollv = 0.0)      # replay: body follows the terrain only (no recorded suspension state)
        # E53: the cockpit camera follows only the LOW-FREQUENCY chassis tilt — slow banks roll the view
        # with the car (chassis fixed on screen, horizon tilts); fast jolts are rejected so the head stays
        # toward vertical and the CHASSIS rocks on screen instead (no headache-inducing landscape strobe).
        αcam = 1.0 - exp(-(dt > 1e-4 ? dt : 1/60)/CAM_TILT_TAU)
        cam_pitch += ((pitch_ter + pitch_dyn) - cam_pitch) * αcam
        cam_roll  += ((roll_ter  + rollv    ) - cam_roll ) * αcam
        vp, eye = camera(cs, cam_pitch, cam_roll)     # head = low-pass tilt; body keeps full tilt → high-freq rock shows on the chassis
        if REPLAY     # E25: cinematic cameras follow the FOCUS car (player or any AI) from its recorded pose
            fp = rep_focus[] == 0 ? (cs.x, cs.y, cs.z, cs.θ) :
                 (rf = rep_ai_raw[rep_focus[]]; (rf[1], rf[2], rf[3], rf[4]))
            vp, eye = replay_camera(REPLAY_CAMS[rep_cam[]], fp[1], fp[2], fp[3], fp[4])
        end
        carModel = Render.translate(Float32[cs.x, cs.y, -cs.z]) * Render.roty(Float32(cs.θ)) *
                   Render.rotz(Float32(pitch_ter)) * Render.rotx(Float32(roll_ter))   # whole car follows the hill (pitch + cross-slope roll)
        tiltModel = carModel * Render.rotz(Float32(pitch_dyn)) * Render.rotx(Float32(rollv))   # full body tilt (terrain + dynamic)
        bodyModel = tiltModel * Render.translate(BODY_OFF)  # body dives/squats + rolls (3-D)
        δ = Float32(inp.steer * (SKIDPAD ? 0.30 : CAR.max_steer))
        # WHEELS FLOAT ON THE SUSPENSION (PO): the wheels stay PLANTED on the road (carModel = terrain
        # follow only, NO dynamic dive/squat/roll), while the CHASSIS pitches/rolls/heaves above them
        # (bodyModel = tiltModel).  So under braking the nose dives toward the planted front wheels → the
        # front wheels appear to RISE relative to the cockpit; squat on power → they drop; roll right →
        # the body leans onto the planted right wheel (it rises) and lifts off the left (it drops).  The
        # wheels stay UPRIGHT/level (they never get the body lean) — they're not bolted to the chassis.
        wheelmat(wx,wz,steer,r) = carModel * Render.translate(Float32[wx, r, wz]) *
                     (steer ? Render.roty(δ) : Render.ident()) * Render.rotz(Float32(spin))
        # advance + place the AI field (rail-followers on the centreline)
        ai_hit = Ref(false); ddt = dt > 1e-4 ? dt : 1/60
        # an AI car's body orientation = its physics pitch (already settles to the fore/aft slope) +
        # (cross-slope terrain bank + physics roll) — so AI LIST on a dune side / roll in a collision,
        # exactly like the player's 3-D car (was yaw-only → they stayed flat).  6-tuple (x,y,z,θ,pitch,roll).
        aibankP(pc) = (isfinite(pc.pitch) ? pc.pitch : 0.0, (isfinite(pc.roll) ? pc.roll : 0.0) + terrain_roll(pc))
        aibankK(p)  = (cc=(x=p[1], z=p[3], θ=p[4]); (terrain_pitch(cc), terrain_roll(cc)))   # kinematic: terrain only (NB local must NOT be named `cs` — that would clobber the player car in the enclosing scope → cs.y FieldError)
        ai_poses = if REPLAY                                       # E18: AI poses straight from the recording
            NTuple{6,Float64}[(a[1],a[2],a[3],a[4],0.0,0.0) for a in rep_ai_raw]
        elseif AILINE === nothing || phase[] != :race              # AI hidden until the race starts (after qualifying)
            NTuple{6,Float64}[]
        elseif !race_go[]                                         # standing on the grid (not yet launched)
            AI_PHYSICS ? [(b=aibankP(pc); (pc.x, groundz(pc.x, pc.z), pc.z, pc.θ, b[1], b[2])) for pc in AIPHYS] :
                         [(p=RaceAI.pose_at(AILINE, c.s, c.lane); b=aibankK(p); (p[1],p[2],p[3],p[4],b[1],b[2])) for c in AICARS]
        elseif AI_PHYSICS
            # GC HYBRID: project each physics car onto the line → update the brain → the controller
            # steers it toward its rail at the planned speed → step the JM 2-D physics.
            for (i, pc) in enumerate(AIPHYS)
                s, lat = RaceAI.project(AILINE, pc.x, pc.z); prevs = AICARS[i].s
                AICARS[i].s = s; AICARS[i].lane = lat; AICARS[i].v = pc.v
                (prevs > AILINE.total*0.7 && s < AILINE.total*0.3) && (AICARS[i].lap += 1)
                # recovery: a stalled AI, or one that's run WAY off the racing line (off track at a
                # corner), is snapped back onto the line — so an AI can never drive off and vanish.
                # recover BEFORE it can climb a dune/leave the world: at the road-edge (not 14 m out),
                # and hard-recover if it's off the terrain HAT entirely (the "mid-air on the dune" case).
                offhat = !JuliaMotor.hat3d(TERRAIN, pc.x, pc.z; ref=Inf)[3]
                railθ = RaceAI.pose_at(AILINE, s, 0.0)[4]
                spun = abs(atan(sin(pc.θ - railθ), cos(pc.θ - railθ))) > SPIN_LIM   # heading way off the rail = spun out
                off = pc.v < 1.4 || abs(lat) > 9.0 || offhat || spun
                if off
                    ai_stuck[i] += 1
                    lim = (offhat || abs(lat) > 12.0 || spun) ? 6 : (abs(lat) > 9.0 ? 18 : 90)   # snap back fast when truly off / spun
                    if ai_stuck[i] > lim
                        rp = RaceAI.pose_at(AILINE, s + 10.0, 0.0); AIplace!(pc, rp[1], rp[3], rp[4]; v = max(8.0, pc.v*0.6)); ai_stuck[i] = 0
                    end
                else; ai_stuck[i] = 0; end
            end
            # physics handles the pace (engine + grip); no per-frame rubber-band (rel=Inf), no corner-speed
            # scaling — the FIXED tune is the engine power (AI_POWER).  Conservative grip cap (amax).
            # The HUMAN is fed in as a racecraft object so the AI tailgate-then-pass the player too
            # (strategic: wait for a straight, own the corner — see RaceAI.plan!).
            ppr = RaceAI.project(AILINE, cs.x, cs.z)
            vts = RaceAI.plan!(AICARS, AILINE; scale = 1.0, amax = AI_AMAX, dt = ddt,
                               player = (ppr[1], ppr[2], cs.v))
            for (i, pc) in enumerate(AIPHYS)
                thr, brk, st = RaceAI.controller(AILINE, AICARS[i].s, AICARS[i].lane, AICARS[i].tlane, vts[i],
                                                 pc.x, pc.z, pc.θ, pc.v, AIyaw(pc); power = AI_POWER)
                DriveRT3D.step_car3d!(pc, thr, brk, st, ddt; manual=false, groundz=groundz)
                # GRASS by the rendered road half-width (|lateral|>ROAD_HALFW), the SAME yardstick as the
                # player — NOT TRKSURF.on_track, whose 9 m half-width is far wider than the visible road, so
                # AI ran the verge near the finish straight penalty-free + drafting (PO saw them do exactly that).
                hs = JuliaMotor.hat(TRKSURF, pc.x, pc.z)
                ai_onroad[i] = !(hs.found && abs(hs.lateral) > ROAD_HALFW)
                if !ai_onroad[i] && pc.v > 2.5                        # AI off the racing surface → grass penalty
                    AIbump!(pc, -GRASS_DRAG*pc.v*cos(pc.θ)*ddt, -GRASS_DRAG*pc.v*sin(pc.θ)*ddt, (2*rand()-1)*GRASS_SLIP*ddt)
                end
                ho = solid_hit(pc.x, pc.z, pc.θ, pc.v)               # E15: AI vs solid objects (no driving through bales)
                ho !== nothing && AIbump!(pc, ho[1], ho[2], ho[3], ho[4], ho[5], ho[6])
            end
            # slipstream: each AI tucked behind the player or another AI on a straight gets a forward tow
            let plead = (cs.x, cs.z, cs.θ, cs.v)
                for (i, pc) in enumerate(AIPHYS)
                    ai_onroad[i] || continue                         # no slingshot while off the road (you crawl on grass)
                    leads = NTuple{4,Float64}[plead]
                    for j in 1:length(AIPHYS); j != i && push!(leads, (AIPHYS[j].x, AIPHYS[j].z, AIPHYS[j].θ, AIPHYS[j].v)); end
                    tw = draft_tow(pc.x, pc.z, pc.θ, pc.v, leads)
                    tw > 0.0 && AIbump!(pc, tw*cos(pc.θ)*ddt, tw*sin(pc.θ)*ddt, 0.0)
                end
            end
            # AI↔AI collisions (physics): pairwise overlap + closing → PLANAR momentum exchange only.
            # E55 (PO-authorised "ignore wheelspin in AI collisions"): the old response injected a
            # wheel-climb LAUNCH (upward heave) + ROLL into each car's 3-D body, so AI flipped, cartwheeled
            # and — the violent impulse diverging the MTK integrator — hyperspaced off-track (E38).  AI now
            # bump like billiard balls: push apart along the contact normal + a mild yaw nudge, NO vertical
            # launch and NO roll, so the field stays flat and nose-to-tail.  Impulse capped (no hyperspace).
            for a in 1:length(AIPHYS)-1, b in a+1:length(AIPHYS)
                pa = AIPHYS[a]; pb = AIPHYS[b]
                dx = pb.x-pa.x; dz = pb.z-pa.z; d = hypot(dx,dz)
                (d < 1e-3 || d > CONTACT_D) && continue   # actual contact only
                nx = dx/d; nz = dz/d
                vrel = (pa.v*cos(pa.θ)-pb.v*cos(pb.θ))*nx + (pa.v*sin(pa.θ)-pb.v*sin(pb.θ))*nz
                vrel <= 0.2 && continue
                imp = clamp(1.45*vrel*280.0/560, 0.0, 4.0)   # (1+e)·vrel·reduced-mass / m, capped at 4 m/s
                AIbump!(pa, -imp*nx, -imp*nz, clamp(-imp*0.04, -0.6, 0.6))   # planar push + mild yaw; no dvy/dpp
                AIbump!(pb,  imp*nx,  imp*nz, clamp( imp*0.04, -0.6, 0.6))
            end
            [(b=aibankP(pc); (pc.x, isfinite(pc.y) ? pc.y : groundz(pc.x, pc.z), pc.z, pc.θ, b[1], b[2])) for pc in AIPHYS]   # pc.y = 3-D height → AI visibly jump/heave; pitch/roll → list + roll
        else
            pp = RaceAI.project(AILINE, cs.x, cs.z)                # the human as a racecraft object (s, lateral, speed)
            poses, hit = RaceAI.step_field!(AICARS, AILINE, ddt; scale = AI_SCALE, player = (pp[1], pp[2], cs.v), rel = AI_REL)
            ai_hit[] = hit
            [(b=aibankK(p); (p[1],p[2],p[3],p[4],b[1],b[2])) for p in poses]   # add terrain bank (kinematic has no body roll)
        end
        # C: time each AI lap — works for BOTH the physics and kinematic fields (we watch AICARS[i].lap,
        # which both paths bump as the car crosses start/finish).  ai_best[i] = that car's fastest lap.
        if phase[] == :race && race_go[]
            for i in 1:length(AICARS)
                if AICARS[i].lap > ai_lap_prev[i]
                    lt = cs.t - ai_lapt0[i]; ai_lapt0[i] = cs.t
                    ai_lap_prev[i] > 0 && (ai_best[i] = min(ai_best[i], lt))   # skip lap 0→1 (the grid launch)
                    ai_lap_prev[i] = AICARS[i].lap
                end
            end
        end
        # GD: rigid-body collision — when the player and an AI overlap and are CLOSING, apply a
        # momentum-exchange impulse: the player (real vehicle physics) is knocked off line + spun
        # via bumpX!, the AI is shoved aside + spun + scrubbed.  The wheels keep spinning with motion.
        CAR3D && (PLAYER_CDA[] = 1.0)             # E56: default = full drag; the draft below cuts it for next frame's step
        if !REPLAY && race_go[] && !rst && !isempty(ai_poses)
            # E56 slipstream for the PLAYER: tuck behind a car on a straight → reduced frontal drag
            # (CdA_scale<1) → you reel them in + slingshot past.  A REAL aero effect integrated by the
            # chassis ODE next frame, not a forward velocity bump.  Works vs the default kinematic field too.
            if CAR3D && (ph = JuliaMotor.hat(TRKSURF, cs.x, cs.z); ph.found && abs(ph.lateral) <= ROAD_HALFW)
                plds = [(p[1], p[3], p[4], AICARS[k].v) for (k,p) in enumerate(ai_poses)]
                ptw = draft_tow(cs.x, cs.z, cs.θ, cs.v, plds)
                ptw > 0.0 && (PLAYER_CDA[] = 1.0 - DRAFT_DRAG_CUT * clamp(ptw/TOW_MAX, 0.0, 1.0))
            end
            pm = 560.0; am = 560.0; restn = 0.12; mr = pm*am/(pm+am)   # PO: car-to-car INELASTIC (was 0.45 = bouncy) — a hit shoves + scrubs, doesn't ping-pong
            pvx = cs.v*cos(cs.θ); pvz = cs.v*sin(cs.θ)
            for (k, p) in enumerate(ai_poses)
                dx = p[1] - cs.x; dz = p[3] - cs.z; d = hypot(dx, dz)
                (d < 1e-3 || d > CONTACT_D) && continue       # ACTUAL contact only (≈ a car width — no "repel from afar")
                nx = dx/d; nz = dz/d                          # contact normal, player → AI
                ac = AICARS[k]; aθ = p[4]
                lat = -dx*sin(cs.θ) + dz*cos(cs.θ)            # contact offset in the player's frame → spin sign
                # ANY car contact (even a sustained scrape, before the closing-impulse test) gives a clear
                # FF kick, so you always FEEL the AI — not just on a square closing hit.
                ffb_jolt = clamp(-sign(lat)*0.6, -1.0, 1.0)
                avx = ac.v*cos(aθ); avz = ac.v*sin(aθ)
                vrel = (pvx-avx)*nx + (pvz-avz)*nz            # closing speed along the normal
                vrel <= 0.2 && continue                       # separating → no new closing impulse (the contact kick already fired)
                j = (1+restn)*vrel*mr
                # PO round 4: "colliding with AI should be a LOT more of a jolt — right now I have no fear,
                # it just knocks us both a little and I get the better of it."  The player (a REAL physics
                # car) now takes a HARD knock so a clash with another car is a genuine event to be feared —
                # PLAYER_HIT amplifies the lateral/normal shove well past the symmetric momentum exchange.
                # (The AI stays BOUNDED below — R1: it must not be rocketed / have its lap count inflated.)
                PLAYER_HIT = 1.8
                # subtle VERTICAL unsettle on a side (wheel-to-wheel) hit — the PO asked for "the wheelspin
                # vertical element back, but not exaggerated, and no superball": a small hop + body rock, not
                # a launch.  Capped low (3.0 m/s, was 7 = superball) and only on a glancing/offset contact.
                across_p = -nx*sin(cs.θ) + nz*cos(cs.θ)
                vlaunch = clamp(abs(across_p)*(j/pm)*0.45, 0.0, 3.0)
                droll = clamp(sign(across_p)*vlaunch*0.7, -4.0, 4.0)   # wheel-climb → body rock (bounded — no cartwheel)
                bumpX!(cs, -PLAYER_HIT*(j/pm)*nx, -PLAYER_HIT*(j/pm)*nz,
                       clamp(-sign(lat)*PLAYER_HIT*(j/pm)*0.06, -2.2, 2.2), vlaunch, droll)
                # PO: a clash must COST you SPEED — not just when you rear-end a car (along_p>0) but on ANY
                # solid contact, so you can't trade paint and sail on.  A bigger scrub for driving INTO a car,
                # a smaller one for a side-swipe — a real crash bleeds your momentum either way.
                along_p = nx*cos(cs.θ) + nz*sin(cs.θ)
                scrub = along_p > 0.25 ? clamp(PLAYER_HIT*(j/pm)*along_p*0.7, 0.0, cs.v*0.6) :
                                         clamp((j/pm)*0.35, 0.0, cs.v*0.25)   # side contact still bleeds some speed
                cs.v = max(0.0, cs.v - scrub)
                ffb_jolt = clamp(ffb_jolt - sign(lat)*PLAYER_HIT*(j/pm)*0.22 - 0.5*sign(vrel), -1.0, 1.0)   # a CLOSING hit adds a bigger kick
                if AI_PHYSICS                                  # the AI is a real physics car → impulse it too
                    alat = -dx*sin(aθ) + dz*cos(aθ)
                    # E55: PLANAR push + mild yaw only — no vertical launch / roll on the AI (it must not
                    # flip or cartwheel when the player nudges it), even though the player still feels the hit.
                    AIbump!(AIPHYS[k], (j/am)*nx, (j/am)*nz, clamp(sign(alat)*(j/am)*0.05, -1.0, 1.0))
                else
                    # PO: the kinematic AI must NOT "flit off like an insect" or get ROCKETED forward (which
                    # inflated its lap count — see R1).  A real crash is ENERGY-LOSSY: it does not propel the
                    # victim.  So the AI HOLDS its line (tiny lateral shove + a decaying yaw twitch carry the
                    # "knocked" look) and its speed change is BOUNDED — nosed ⇒ slowed, rear-ended ⇒ only a
                    # small bounded nudge, never dragged up toward the (fast) player's speed.
                    along  = nx*cos(aθ) + nz*sin(aθ); across = -nx*sin(aθ) + nz*cos(aθ)
                    ac.v   = max(0.0, ac.v + clamp((j/am)*along, -8.0, 2.5))            # bounded: no escape-velocity boost
                    ac.lane = clamp(ac.lane + clamp((j/am)*across*0.04, -0.7, 0.7), -RaceAI.LANE_MAX, RaceAI.LANE_MAX)  # gentle nudge, not a dart
                    ac.spin += clamp((j/am)*across*0.06, -0.8, 0.8)   # yaw twitch (decays) — looks knocked, not weightless
                end
            end
        end
        # E18: record all car poses (player + AI) at ~15 Hz once the race is GREEN, for replay
        if replay_buf !== nothing && race_go[] && !rst && length(ai_poses) == length(AICARS) && (cs.t - replay_t[]) >= 1/15
            replay_t[] = cs.t
            push!(replay_buf, Float32(cs.t), Float32(cs.x), Float32(cs.y), Float32(cs.z), Float32(cs.θ))
            for p in ai_poses; push!(replay_buf, Float32(p[1]), Float32(p[2]), Float32(p[3]), Float32(p[4])); end
        end
        aiCar(p)  = Render.translate(Float32[p[1], p[2], -p[3]]) * Render.roty(Float32(p[4])) *
                    Render.rotz(Float32(p[5])) * Render.rotx(Float32(p[6]))   # body follows the hill (pitch + cross-slope/collision roll)
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
        # ---- shared world draw: everything both the main pass and the E64 mirror pass see.
        # flip=true = the X-mirrored rear view: the clip-space flip reverses winding, so the
        # object-pass face cull swaps its culled side (same faces kept, opposite GL name).
        drawworld = function(vp_, eye_, flip::Bool)
            HORIZON_RING === nothing || Render.draw_horizon(prog, HORIZON_RING, vp_, eye_; tint=GRADE.ringtint)   # GPL horizon ring backdrop
            # E60 (D6, 260801 gold video): TRACK-mesh signs (VREDESTEIN at Tarzan …) drew with uBackFlip=0, so
            # when the coplanar dedup keeps the away-facing decal the text renders MIRRORED.  Objects already
            # un-mirror back faces; give the track mesh the same treatment (road/kerb back faces are unseen).
            glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 1)
            secfrom = (@isdefined SEC_FROM) ? SEC_FROM : typemax(Int)
            for (ti, it) in enumerate(trackItems)                        # ambfill lifts shadowed walls/fences out of the "carbonized" black under the flat overcast light
                # E68 S9b: landmass SECTIONS draw single-sided like GPL — culls the dark edge-skirt
                # slabs (Ring s≈18400) that our two-sided draw exposed.  Winding per OBJ_FF_CW.
                # E68 S10b: rail-family parts also draw single-sided (guardrail shimmer).
                if ti == secfrom; glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
                elseif ti < secfrom && (@isdefined TRACK_RAILCULL) && ti <= length(TRACK_RAILCULL)
                    if TRACK_RAILCULL[ti]; glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
                    else; glDisable(GL_CULL_FACE); end
                end
                if MONZA                                                 # E57: per-surface grade — its asphalt MIP is over-bright, its barriers carbonized
                    cat = TRACKCAT[ti]
                    b, a = cat === :road ? (MZ_ROAD_B, MZ_ROAD_A) : cat === :dark ? (MZ_DARK_B, MZ_DARK_A) :
                           cat === :bank ? (MZ_BANK_B, MZ_BANK_A) : (MZ_OTHER_B, MZ_OTHER_A)
                    Render.draw(prog, it, vp_, Render.ident(); bright=b, ambfill=a)
                else
                    Render.draw(prog, it, vp_, Render.ident(); bright=0.72, ambfill=0.34)
                end
            end
            (@isdefined SEC_FROM) && length(trackItems) >= SEC_FROM && glDisable(GL_CULL_FACE)   # E68 S9b: section cull off before objects
            if OBJ_CULLFACE                                           # E60: GPL culls single-sided faces —
                # double-sided signs keep both decals (dedup=:orient), each visible only from its own side.
                # NEVER touch glFrontFace: the two-sided-Lambert shader keys off gl_FrontFacing globally
                # (flipping the convention darkened the whole world) — pick the culled SIDE instead.
                # GPL is D3D-era (CW front); after the winding-preserving remap those faces are GL "back",
                # so cull GL_FRONT to keep them.  JM_OBJ_FF=ccw culls GL_BACK if a track's data disagrees.
                glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
                glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 0)
            end
            for (items,mat,grz,opos,onm) in OBJECTS                   # trackside objects (trees graze-fade; uBackFlip stays 1 when un-culled)
                (eye_[1]-opos[1])^2+(eye_[2]-opos[2])^2+(eye_[3]-opos[3])^2 > OBJ_CULL2 && continue   # distance cull
                ob, oa = 1.05, 0.55                                    # default object grade (grandstands/buildings)
                if MONZA                                               # E57: tone the combined-circuit paved/banking object surfaces
                    g = monza_obj_grade(onm)
                    g === :road && ((ob, oa) = (MZ_ROAD_B, MZ_ROAD_A)); g === :bank && ((ob, oa) = (MZ_BANK_B, MZ_BANK_A))
                end
                otint = is_crowd_obj(onm) ? CROWD_TINT : (1f0,1f0,1f0)   # E46: warm/de-blue the over-blue grandstand crowd MIP
                for it in items; Render.draw(prog, it, vp_, mat; bright=ob, ambfill=oa, graze=grz, tint=otint); end   # grandstands/buildings: ambfill kills the "post-Hiroshima carbonized" shadow faces → vibrant GPL look
            end
            for (it,pos,w,h,yaw) in STATICTREES                      # wide forest-edge panels (authored yaw, graze-fade)
                (eye_[1]-pos[1])^2+(eye_[2]-pos[2])^2+(eye_[3]-pos[3])^2 > BB_CULL2 && continue
                Render.draw(prog, it, vp_, Render.translate(Float32[pos[1],pos[2],pos[3]])*Render.roty(yaw)*Render.scalexyz(w,h,1f0); bright=1.3, ambfill=0.8, graze=true)   # E63/MZ3: the comment always claimed graze-fade but the call never passed it → a wide Monza forest strip seen EDGE-ON rendered as a dark triangular SLAB at the S/F. graze=true fades edge-on quads (uGraze) so the strip shows face-on as a tree-line and vanishes edge-on
            end
            OBJ_CULLFACE && glDisable(GL_CULL_FACE)
            glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 0)
            for (it,pos,w,h) in BILLBOARDS                            # trees/sprites
                (eye_[1]-pos[1])^2+(eye_[2]-pos[2])^2+(eye_[3]-pos[3])^2 > BB_CULL2 && continue       # distance cull
                Render.draw(prog, it, vp_, Render.billboard_model(pos,w,h,eye_); bright=1.55, ambfill=0.85)  # sprites read near-unlit (colorful signs, not "burned")
            end
            for (p, cm) in zip(ai_poses, AICHASSIS)                 # AI grid (Ferrari/Brabham/BRM/Eagle/Cooper)
                for it in cm.body; Render.draw(prog, it, vp_, aiBody(p, cm); bright=1.25, spec=0.10, ambfill=0.62); end
                for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw(prog, it, vp_, aiWheel(p,wx,wz,r)); end
            end
        end
        # ---- E64 mirror pass: the rear view into the mirror RTT (cockpit view only) ----
        mirror_live = MIRROR_RTT && CTL.view == 0 && !REPLAY
        if mirror_live
            glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE); glDepthFunc(GL_GEQUAL); glClearDepth(0.0)   # same reversed-Z as the main pass
            glBindFramebuffer(GL_FRAMEBUFFER, mirfbo); glViewport(0,0,MIRW,MIRH)
            glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
            # E64 S10: one camera PER DISC at the mirror's own cowl position (left half of the FBO =
            # left/z+ mirror), so each glass sees backward-outward like the gold — tail at the inner
            # edge only, road dominating.  The glass quads' per-half UV split is unchanged.
            for (x0, side) in ((0, 1), (MIRW÷2, -1))
                glViewport(x0, 0, MIRW÷2, MIRH)
                mvp, meye = mirror_camera(cs, cam_pitch, cam_roll, side)
                Render.draw_sky(skyprog, skyvao, inv(mvp), meye, LIGHTDIR;
                                cloud = GRADE.cloud, zenith = GRADE.zenith, horizon = GRADE.horizon)
                Render.set_scene_uniforms(prog, meye; fognear=400f0, fogfar=2800f0,
                                          fogcol=GRADE.horizon, suncol=GRADE.suncol, ambsky=GRADE.ambsky, sat=GRADE.sat)
                Render.bind_shadow(prog, shadowtex, lightVP)
                drawworld(mvp, meye, true)
                for it in carItems; Render.draw(prog, it, mvp, bodyModel; bright=1.2, spec=0.08, ambfill=0.78); end   # your own tail at the inner edge
                for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw(prog, it, mvp, wheelmat(wx,wz,steer,r); bright=1.0, ambfill=0.75); end
            end
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
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
        drawworld(vp, eye, false)
        # ambfill lifts the self-shadowed cockpit interior out of black (GPL pre-lights it
        # evenly); lower spec so the cockpit floor stops reading as a "shining rug".
        for it in carItems; Render.draw(prog, it, vp, bodyModel; bright=1.2, spec=0.08, ambfill=0.78); end   # PO: lift the self-shadowed footwell/tub further out of black (GPL pre-lights the interior evenly) so it stops reading as a hard black "plywood" notch
        if CTL.view != 0   # the driver figure occludes the cockpit from the in-car eye (E36 black band) → chase only
            if RSUSP_ON    # E64 S7: high-detail rear suspension (gold nintendo shows the full articulated rear end)
                for it in rsuspItemsA; Render.draw(prog, it, vp, bodyModel*RSFIX_A; bright=1.15, spec=0.25, ambfill=0.55); end
                for it in rsuspItemsB; Render.draw(prog, it, vp, bodyModel*RSFIX_B; bright=1.15, spec=0.25, ambfill=0.55); end
            end
            for it in driverItems; Render.draw(prog, it, vp, bodyModel; bright=1.2, spec=0.10, ambfill=0.55); end
            helmModel = bodyModel * Render.translate(Float32[HELM_OFF[1],HELM_OFF[2],HELM_OFF[3]])
            for it in helmItems; Render.draw(prog, it, vp, helmModel; bright=1.2, spec=0.12, ambfill=0.60); end
        end
        # gauge cluster (real GPL dash7A dial faces): the dash sits BELOW the scuttle/black panels in the
        # mesh, so it's occluded from the driver's eye → draw it depth-test-OFF so the dials read on the
        # dash, near-unlit (bright + ambfill) so the faces are legible.  Only matters in the cockpit view.
        # E59 parity: bright 1.6/ambfill 0.95 over-exposed the dash — the GPL gold cockpit has a MATTE
        # BLACK dash with crisp white-on-black dials; ours read as a washed-out silver plank.  Near-unlit
        # but at unity brightness keeps the dials legible AND the panel black.  JM_DASH_B/JM_DASH_A tune.
        dash_b = parse(Float64, get(ENV,"JM_DASH_B","1.2")); dash_a = parse(Float64, get(ENV,"JM_DASH_A","0.9"))   # E62: gold cockpit dials read crisp white-on-black; 1.0/0.60 left ours dim — lift fill so the dial faces/markings are legible
        if CTL.view == 0
            glDisable(GL_DEPTH_TEST)
            for it in gaugeItems; Render.draw(prog, it, vp, bodyModel*GAUGEFLIP; bright=dash_b, spec=0.0, ambfill=dash_a); end
            glEnable(GL_DEPTH_TEST)
        else
            for it in gaugeItems; Render.draw(prog, it, vp, bodyModel*GAUGEFLIP; bright=dash_b, spec=0.0, ambfill=dash_a); end
        end
        # (AI grid drawn in drawworld — shared with the E64 mirror pass)
        # E59 parity: default lighting rendered the tyres as solid BLACK silhouettes from the cockpit —
        # the GPL gold cockpit shows readable dark-grey tread + sidewall.  Lift the fill (not the sun).
        for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]; Render.draw(prog, it, vp, wheelmat(wx,wz,steer,r); bright=1.0, ambfill=0.75); end
        # front suspension wishbones — ahead of the cockpit, visible through the plexiglass (PO gold standard)
        for it in fsuspItems; Render.draw(prog, it, vp, bodyModel; bright=1.1, spec=0.15, ambfill=0.5); end
        # rear-view mirrors — re-placed onto the cowl/plexiglass, faces tilted toward the eye (GPL look).
        # E64: with the RTT live, the silver disc is just the RIM/backing — the glass quad on top
        # carries the actual rear view (round-masked sample of the mirror FBO, uMirrorGlass).
        for it in mirrorItems; Render.draw(prog, it, vp, bodyModel*MIRRORMAT; bright=1.25, spec=0.30, ambfill=0.75); end   # disc/rim (and the whole mirror when JM_MIRROR_RTT=0)
        if mirror_live
            for it in mirGlassItems; Render.draw(prog, it, vp, bodyModel*MIRRORMAT; mirrorglass=true); end   # live glass
        end
        # steering wheel — spin about its column axis with steering input
        swModel = bodyModel * Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(inp.steer*2.5)) * Render.translate(-SWCENTER)
        for it in swItems; Render.draw(prog, it, vp, swModel; bright=1.2, ambfill=0.34); end
        # E64 S2 (Z-CK4): gloved hands + forearms, cockpit view only (the chase driver figure has its
        # own DRIVER_TEX arms).  Hands turn with the wheel, forearms stay put — GPL-era articulation.
        # The lotarms mesh is authored in a positioner-local frame (D12 posmat-clamp family): raw it
        # sits FORWARD of the wheel (x 0.68…1.01) and too high (y→0.52) → the old "giant silver arms".
        # ARMFIX mirrors it back through the wheel plane toward the driver + squashes it under the eye.
        if HANDS && CTL.view == 0
            if ARMS
                for it in armItems;  Render.draw(prog, it, vp, bodyModel*ARMFIX; bright=1.15, spec=0.05, ambfill=0.60); end
            end
            if length(handLR) == 2                      # left fist +grip, right fist −grip → gold's 10-and-2
                Render.draw(prog, handLR[1], vp, swModel*gripmat(+1); bright=1.15, spec=0.05, ambfill=0.60)
                Render.draw(prog, handLR[2], vp, swModel*gripmat(-1); bright=1.15, spec=0.05, ambfill=0.60)
            else
                for it in handItems; Render.draw(prog, it, vp, swModel; bright=1.15, spec=0.05, ambfill=0.60); end
            end
        end
        # plexiglass WINDSCREEN — drawn LAST, FAINTLY VISIBLE glass (PO: it had vanished at 0.16), depth-write
        # OFF so the front suspension + track read through it (GPL gold standard) but the screen still reads as
        # a tinted curved plexiglass, not a bright opaque gold rim.  JM_WIND_ALPHA tunes it.
        if WIND_ALPHA > 0
            glDepthMask(GL_FALSE)
            # PO: flatter, dimmer lighting so the leather scuttle reads as smooth matte tan — not stark
            # cream "plywood" wedges clashing with the dark footwell notch the (omitted) driver would fill.
            for it in windItems; Render.draw(prog, it, vp, bodyModel; bright=WIND_B, spec=0.02, ambfill=WIND_A, alpha=WIND_ALPHA); end
            glDepthMask(GL_TRUE)
        end
        α_tc = clamp(dt/0.10, 0.0, 1.0)              # smooth the traction-circle display (coarse-mesh Fz spikes → no flicker)
        tc_hud = ntuple(i -> ntuple(j -> tc_hud[i][j] + (cs.tc[i][j]-tc_hud[i][j])*α_tc, 3), 4)
        Render.hud_draw(hudprog, hudvao, hudvbo,
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, 9500.0, inp.throttle, inp.brake, inp.clutch, tc_hud;
                               lastlap=(SMOKE ? 94.3 : last_lap), bestlap=(SMOKE ? 92.1 : best_lap), manual=!CTL.auto), W, H)
        GLFW.SwapBuffers(win)
        if SMOKE && frames == 38 && isempty(SHOTS)  # headless self-test: dump one frame
            buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
            open(get(ENV,"JM_DUMP","/tmp/zand_hud.ppm"),"w") do io; write(io,"P6\n$W $H\n255\n")
                for y in H:-1:1, x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
        end
        # E59 multi-shot: dump the settled frame for the current shot, then teleport to the next.
        if SMOKE && !isempty(SHOTS) && !shots_done[] && frames - shot_t0[] == SHOT_SETTLE
            sh = SHOTS[shot_idx[]]
            buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
            open(joinpath(SHOTS_DIR, sh.name * ".ppm"),"w") do io; write(io,"P6\n$W $H\n255\n")
                for y in H:-1:1, x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
            println("  JM_SHOTS: dumped ", sh.name, " (", shot_idx[], "/", length(SHOTS), ")"); flush(stdout)
            if shot_idx[] < length(SHOTS)
                shot_idx[] += 1; shot_t0[] = frames + 1
                nxt = SHOTS[shot_idx[]]; CTL.view = nxt.view; place_at_s!(nxt.s)
            else
                shots_done[] = true
            end
        end

        frames += 1
        if now - titleT > 0.25 && REPLAY
            carname = rep_focus[] == 0 ? (isempty(repd.names) ? "Player" : repd.names[1]) :
                      (rep_focus[] < length(repd.names) ? repd.names[rep_focus[]+1] : "AI $(rep_focus[])")
            GLFW.SetWindowTitle(win, "▶ REPLAY — $(uppercasefirst(TRACKSEL)) — 📷 $(REPLAY_CAM_LABEL[rep_cam[]]) — 🏎 $carname [$(rep_focus[]+1)/$(repd.ncar)]" *
                "  —  $(round(rep_rt[],digits=1))/$(round(rep_dur,digits=1))s  $(rep_play[] ? "▶" : "⏸")×$(rep_speed[])   ·  V angle · C car · SPACE play · ←/→ seek · ↑/↓ speed")
            titleT = now
        elseif now - titleT > 0.25
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
    if replay_buf !== nothing && !isempty(replay_buf)   # E18: save the all-car replay alongside the .ibt
        try
            ts = Dates.format(Dates.now(), "yyyy-mm-dd HH-MM-SS")
            odir = get(ENV, "JM_IBT_DIR", joinpath(dirname(dirname(@__DIR__)), "data", "juliaracer"))
            mkpath(odir)
            out = joinpath(odir, "replay_$(TRACKSEL) $(length(AICARS))ai $(ts).jmr")   # filename encodes track + AI count for the GUI picker
            names = String["Lotus 49"]; for m in AICHASSIS; push!(names, m.name); end
            nf = length(replay_buf) ÷ (1 + 4*REPLAY_NCAR)
            serialize(out, (track=TRACKSEL, ncar=REPLAY_NCAR, names=names, fps=15, nframes=nf, data=replay_buf))
            println("  wrote replay: ", out, "  (", nf, " frames, ", filesize(out)÷1024, " KB)")
        catch e; println("  replay export failed: ", e); end
    end
    ffb !== nothing && FFB.close_ffb(ffb)
    EngineAudio.stop!(ENG)
    GLFW.Terminate()
    println("bye"); flush(stdout); flush(stderr)
    # HARD exit: skip Julia's atexit handlers.  PortAudio registers one that calls Pa_Terminate, which
    # SEGFAULTS in the ALSA/PipeWire stream teardown ("free(): corrupted unsorted chunks") on this box —
    # a noisy crash AFTER the race is already fully written (telemetry/replay/result all flushed above).
    # _exit terminates the process cleanly at the OS level, so the post-race exit is no longer a crash.
    ccall(:_exit, Cvoid, (Cint,), 0)
end
main()
