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
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","drive_rt3d.jl"))); using .DriveRT3D
include(joinpath(@__DIR__,"people_filter.jl")); using .PeopleFilter   # E101: loose-people name rule, shared with its gate
include(joinpath(@__DIR__,"gpl_lp.jl")); using .GPLLP                    # E84/E89: GPL .lp AI lines (race.lp speed table)
include(joinpath(@__DIR__,"susp_pose.jl")); using .SuspPose
include(joinpath(@__DIR__,"wreck_seal.jl")); using .WreckSeal   # E103: where a wreck is sealed, shared with its gate             # E82: rear-suspension corrective transform, shared with its gate  # full-3D physics (JM_3D=1)
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

# PO 2026-08-27, standing: "I like the clutch attached to a slider - that way I can ride the
# clutch. The clutch should be an axis." A joystick.conf written by juliaRacer.py or calibrate.jl
# OVERRIDES the slider default above, and Ctrl(0,...) means "no axis, use clutch_btn" -- so a
# recalibration can silently demote the clutch to a button (or to nothing, since clutch_btn is 0
# in the shipped map) and the sim would just quietly stop having a ridable clutch. Say so loudly
# rather than leaving the driver to discover it mid-corner. Gated by tools/controls_smoke.jl.
if JOYMAP.clutch.axis < 1
    @warn """clutch is NOT on an axis (clutch.axis=$(JOYMAP.clutch.axis)) — the PO's standing
             requirement is a SLIDER you can ride. Check $(_JOYCONF); the X3D default is axis 4."""
else
    println("  clutch: axis ", JOYMAP.clutch.axis, " (ridable slider)",
            isfile(_JOYCONF) ? "  <- joystick.conf" : "  <- X3D default")
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
const ZANDV    = TRACKSEL == "zandvoort"
const SPA      = TRACKSEL == "spa"      # E71-S12: needs the road-only centreline oracle (see ROADHAT)
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
# E77-F (PO 2026-08-27/28): "when I try to go under the bridge at the ring, the car levitates and
# bounces". JM_SWEEP=10 found 8 height discontinuities in 22.76 km, all at two underpasses, and
# JM_BRIDGEPROBE named what sits over the racing line there:
#
#   s=21540   road 588.22   br_under 593.59   (+5.4 m)   <- the bridge UNDERSIDE
#   s=22250   road 603.32   villone  615.77   (+12.5 m)  <- a building passing over the line
#   s=22300   road 607.42   villone  655.31   (+48 m)
#
# Neither is ever a driving surface: `br_under` is the underside of a bridge you pass BENEATH, and
# `villone` is a building. They reach the car because hat3d returns the topmost surface at or below
# `ref` (= car y + 2 m) — so while the car is planted the road wins, but the moment it goes light
# over a crest (and both underpasses are on rising ground) `ref` climbs past the underside, the HAT
# hands back the bridge, and the car is snapped up onto it and dropped off the end.
#
# ⚠️ This is NOT `drop_overpass`. That drops any triangle with another surface below it, and its own
# docstring forbids it here because the Ring has bridges you genuinely drive OVER. Excluding two
# named textures leaves those intact. JM_HAT_KEEP_BRIDGE=1 restores the old behaviour for A/B.
const HAT_EXCLUDE = get(ENV,"JM_HAT_KEEP_BRIDGE","0") != "0" ? Set{String}() :
                    Set{String}(["br_under", "villone"])
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
                       startswith(lt,"atog") || startswith(lt,"a_l_g") || lt == "concrete" ||
                       # E71-S13 (Spa): the classifier recognised only 43.9% of Spa's near-centreline
                       # surface, and what it DID recognise was dominated by `groove` — the narrow
                       # racing-line strip. So every width measured at Spa was really the groove's.
                       # Added by the census's own rule ("whatever the car drives on IS the road"),
                       # using the on-road/off-road split of each name within |lat| < 5 m:
                       #   borcem   5431 on /1029 off  — the concrete edge strip, road at old Spa
                       #   borcem_k  723 on /  17 off
                       #   griline   196 on /   0 off  — grid markings
                       #   asfa      169 on / 149 off  — asphalt, spelled without the "asp" this
                       #                                 predicate tests for
                       # NOT added: bordo (184/3374), barr (290/3656), armco_s (165/713) — barriers,
                       # overwhelmingly off-road; and the *drt* per-corner names, which are genuinely
                       # mixed (e.g. lecdrtl2 168 on / 356 off) and need their own verdict.
                       startswith(lt,"borcem") || lt == "asfa" || lt == "griline"

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
# PO 2026-08-28: JM_AI_HEADSTART=<seconds> holds the FIELD on the grid for N seconds after the
# human launches, so the player gets a clean head start. The AI keep their grid poses until
# released (the existing "standing on the grid" branch below already draws them stationary), then
# launch normally -- including the per-car getaway fumbles. 0 = the usual simultaneous start.
const AI_HEADSTART = max(0.0, parse(Float64, get(ENV, "JM_AI_HEADSTART", "0")))
# PO 2026-08-31: "start as a countdown timer". JM_COUNTDOWN=<seconds> holds the whole field on the
# grid and counts down on the HUD; at zero the race goes GREEN for everyone at once. Default 0 keeps
# the previous behaviour exactly (green on the player's first throttle), so no existing run changes.
const COUNTDOWN = max(0.0, parse(Float64, get(ENV, "JM_COUNTDOWN", "0")))
# PO 2026-08-28: JM_POLE=1 puts the HUMAN on pole regardless of qualifying. Without a practice lap
# `grid_order` gives you no time and grids you LAST (correct, and what the PO saw as "P5 of 5").
const POLE = get(ENV, "JM_POLE", "0") != "0"
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
# E95h-S2: `hay04` matched none of these and so came back :wall -- a HARD barrier made of
# hay. The PO's rule for soft scenery is "you plough through with a penalty", so match the
# bale families by prefix rather than by one exact spelling.
solidkind(nm) = (startswith(nm,"haie")||startswith(nm,"bush")||startswith(nm,"shrub")||startswith(nm,"hedge")||
                 startswith(nm,"hay")||startswith(nm,"straw")) ? :soft : :wall
# E56: sum the spring-damper CONTACT forces from every SOLID the PLAYER car penetrates into one
# body-frame (Fx,Fy,Mz) to feed extforce3d! BEFORE the step (the solver integrates the collision —
# no bumpX! state hack).  Returns the net force/moment + a peak-penetration proxy for the FFB jolt.
# E96-S2 (2026-08-30): THE CAR'S WORLD VELOCITY, derived from the position delta.
# `cs.v` is an UNSIGNED SPEED, so `v*cos(θ), v*sin(θ)` cannot represent motion opposite to the
# heading -- a car being pushed backwards off a wall reads as though it were still driving INTO it.
# Every contact site here used that form, and it turns a no-rebound clamp into an accelerator:
# the clamp sizes its impulse to "cancel the approach", the phantom approach grows with each
# frame of retreat, and the push grows with it. Measured on the real solver (v0 = 30 m/s into a
# wall): the car stops correctly at v = 0.02 m/s, then v doubles every frame -- 0.05, 0.12, 0.35,
# 0.87, 1.91, 3.82, 7.65, 15.32, 30.83 -- while x DECREASES, ending 335 m behind the barrier at
# 57.9 m/s from a 200 km/h hit. That is the PO's "trampoline", and it is a sign error, not a
# stiffness problem, which is why four rounds of softening springs never touched it.
# The position delta carries the true direction, costs two subtractions, and needs nothing from
# the solver internals.
const WVX = Ref(0.0); const WVZ = Ref(0.0)
const PRVX = Ref(NaN); const PRVZ = Ref(NaN)
# E96-S6: take the velocity from the SOLVER, not from a position delta. The delta (E96-S2) has the
# right direction but lags one frame, and that lag is the leading suspect for the residual push-back
# E96-S3 could not remove. DriveRT3D.world_velocity rotates the body-frame (u, v) the integrator
# already carries into the world exactly -- no differencing, no lag, and nothing to keep in sync.
# The delta remains the fallback for the planar (JM_2D) path, which has no such accessor.
function update_world_velocity!(cs, x, z, dt)
    if CAR3D
        (WVX[], WVZ[]) = DriveRT3D.world_velocity(cs)
    elseif isfinite(PRVX[]) && dt > 1e-6
        WVX[] = (x - PRVX[])/dt; WVZ[] = (z - PRVZ[])/dt
    else
        WVX[] = 0.0; WVZ[] = 0.0        # first frame: no delta yet, and a guessed one would be worse
    end
    PRVX[] = x; PRVZ[] = z
    (WVX[], WVZ[])
end
function solid_contact(x, z, θ, v, dt)
    Fx = 0.0; Fy = 0.0; Mz = 0.0; peak = 0.0
    hardpk = 0.0      # E95c: peak from NON-HEDGE objects only -- a hedge must never total the car
    closing = 0.0     # E99: peak closing speed along a NON-HEDGE contact normal (m/s)
    @inbounds for (ox, oz, r, kind) in SOLIDS
        dx = x - ox; dz = z - oz; d = hypot(dx, dz)
        rr = r + CARHALF
        (d >= rr || d < 1e-3) && continue
        nx = dx/d; nz = dz/d
        vn = WVX[]*nx + WVZ[]*nz                          # E96-S2: TRUE world velocity along the outward
                                                          # normal (<0 = into it). Was v*cos/sin(θ),
                                                          # which is unsigned and so never reported
                                                          # retreat -- see update_world_velocity!.
        (fx, fy, mz) = DriveRT3D.contact_force(rr - d, nx, nz, vn, θ; kind = kind, dt = dt)
        Fx += fx; Fy += fy; Mz += mz; peak = max(peak, hypot(fx, fy))
        kind === :soft || (hardpk = max(hardpk, hypot(fx, fy)))
        # E99 (PO 2026-08-30: "a graze at speed should scrub you but not end your race"): keep the
        # CLOSING SPEED ALONG THE NORMAL. It is the physical difference between a graze and a shunt,
        # and it is the one thing the force cannot tell you -- `hypot(fx,fy)` saturates at
        # CONTACT_DVMAX (~296 kN) for a 3 cm clip just as it does for a square hit, which is why the
        # old `chard > 1.0e3` test fired on ANY contact and left the speed gate deciding everything.
        # Measured: at 108 km/h a 0.03 m graze keeps 84% of the car's energy through the contact and
        # a 0.64 m clip keeps 23% -- the contact law already scrubs correctly; only the WRECK trigger
        # could not tell them apart.
        kind === :soft || (closing = max(closing, -vn))   # vn < 0 is approach; store it positive
    end
    (Fx, Fy, Mz, peak, hardpk, closing)
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
const IBTREC0 = !haskey(ENV, "JM_NOIBT")         # .ibt telemetry ON by default (set JM_NOIBT to disable)
const REPLAY_FILE = get(ENV, "JM_REPLAY", "")    # E18: if set, PLAY BACK this .jmr recording instead of driving
# The repo's data/iracing/ holds only the parse/profile scripts — the reference .ibt captures live
# in the gold-standard store, which is why every session ended with ".ibt export failed ... (2)".
# Look there first, so the iRacing reference is actually reachable (PO 2026-08-27: the physics is to
# be determined by this data). JM_IBTDIR overrides the location, not the physics.
const IBTDIR = let repo = normpath(joinpath(@__DIR__,"..","..","data","iracing")),
                   gold = "/home/admin/gold standard/julia racer"
    d = get(ENV, "JM_IBTDIR", "")
    !isempty(d) ? d : (isdir(gold) && !isempty(filter(f->endswith(lowercase(f),".ibt"), readdir(gold))) ? gold : repo)
end
# E91 (2026-08-29): name the capture after the track it WAS. This fell through to "zandvoort"
# for monza and watglen, so a Monza run was saved as `lotus49_zandvoort ...ibt` -- a mislabelled
# capture is worse than no capture, because later analysis cannot tell it apart from the real
# Zandvoort references it sits beside. (A parity capture must record the state it claims.)
# E106-S11 (2026-09-02): the same fall-through bit SPA -- a Spa race was written as
# `lotus49_zandvoort ...ibt`. Fixing it track-by-track only postpones the next one, so the name now
# DERIVES from the track selection and the hardcoded default is gone: an unlisted track names
# itself instead of borrowing Zandvoort's identity. Only the long-form names that differ from the
# selector key stay listed.
const IBTNAME = get(Dict("nurburgring" => "nurburgring nordschleife",
                         "zandvort"    => "zandvoort"),   # dir spelling vs the reference captures
                    TRACKSEL, TRACKSEL)
# Pick the reference capture by PREFIX, not by an exact dated filename. The hardcoded
# "2026-06-14 11-11-37" names do not exist anywhere on this machine — the real captures are dated
# 2026-06-24 — so the lookup could never succeed and every session ended with a SystemError. A
# reference set that is addressed by an exact timestamp breaks the moment it is re-captured, which
# is the opposite of what a reference is for.
const IBTTMPL = let want = (SKIDPAD ? "lotus49_skidpad" : "lotus49_nurburgring"),
                    cands = isdir(IBTDIR) ? sort(filter(f -> startswith(lowercase(f), want) &&
                                                             endswith(lowercase(f), ".ibt"),
                                                        readdir(IBTDIR))) : String[]
    isempty(cands) ? joinpath(IBTDIR, want * " (none found).ibt") : joinpath(IBTDIR, cands[1])
end   # zandvoort/spa/monza/watkins borrow the Nordschleife layout (channel set is the same)

# ---- E100: the GEARBOX comes from the ibt session, not from source constants ----------------
# PO 2026-08-27: "the car physics should be determined entirely by the iracing ibt data, there
# should be no modifiable parameters." drive_rt3d.jl carried GEARS/FINAL as constants while
# Setup already parsed them out of the session YAML -- read, then ignored. Measured across the
# gold store: Nurburgring captures run [2.23,1.72,1.32,1.04,0.846], skidpad [.,.,.,1.09,0.916].
# The constants were the SKIDPAD pair, so every circuit drove on short-course gearing.
# IBTTMPL already resolves to the right capture (Nordschleife for the circuits, skidpad for the
# skidpad), so the gearbox simply comes from the file the session is already keyed to.
# Set BEFORE the car is built (line ~4358): the final drive is an MTK parameter baked in at
# construction, so a later change would move the ratios and not the drivetrain.
include(normpath(joinpath(@__DIR__,"..","..","JuliaMotorMTK","src","setup.jl"))); using .Setup
let
    if isfile(IBTTMPL)
        try
            pp = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(IBTTMPL)))
            DriveRT3D.set_transmission!(pp.gear_ratios, pp.final_drive; source = basename(IBTTMPL))
            # E100 S2: mass and its front share come from the same session's CornerWeights.
            (mm, ff) = DriveRT3D.mass_from_corner_weights(pp.corner_weight_N)
            DriveRT3D.set_mass!(mm, ff; source = basename(IBTTMPL))
            # E100 S4: and the SPRING RATES, which are per-corner and asymmetric in real setups.
            # The model used to share one spec per axle, so the rates could not follow the session
            # at all; they stayed frozen wherever they were once copied from. wheel_rate() carries
            # the N/mm -> N/m conversion and the motion ratio, so this stays a wiring job.
            # E100 S5: static ride heights, per corner, from the same session (mm -> m).
            let rh = pp.ride_height_mm
                if all(k -> haskey(rh, k) && isfinite(rh[k]) && rh[k] > 0, (:LF,:RF,:LR,:RR))
                    DriveRT3D.set_ride_height!(rh[:LF]/1000, rh[:RF]/1000, rh[:LR]/1000, rh[:RR]/1000;
                                               source = basename(IBTTMPL))
                end
            end
            let sp = pp.spring_rate_Npmm
                if all(k -> haskey(sp, k) && isfinite(sp[k]) && sp[k] > 0, (:LF,:RF,:LR,:RR))
                    DriveRT3D.set_suspension!(DriveRT3D.wheel_rate(sp[:LF]), DriveRT3D.wheel_rate(sp[:RF]),
                                              DriveRT3D.wheel_rate(sp[:LR]), DriveRT3D.wheel_rate(sp[:RR]);
                                              source = basename(IBTTMPL))
                end
            end
        catch e
            @warn "E100: could not read the gearbox from $(basename(IBTTMPL)); the built-in \
                   fallback is the SKIDPAD setup and is wrong for a circuit" e
        end
    else
        @warn "E100: no ibt at $IBTTMPL -- gearbox falls back to built-in constants (SKIDPAD setup)"
    end
    # Always SAY where it came from: a silent fallback to constants is the defect itself.
    println("  gearbox: ", DriveRT3D.GEARS, "  final ", DriveRT3D.FINAL[],
            "   <- ", DriveRT3D.transmission_source())
    println("  mass:    ", round(DriveRT3D.MASS[], digits=1), " kg  front ",
            round(100*DriveRT3D.FRONT_FRAC[], digits=1), "%")
    # Say where the rates came from, for the same reason the gearbox does: a silent fallback to
    # constants is the defect, not the absence of one.
    println("  springs: ", join((round(Int, k) for k in DriveRT3D.KS[]), " / "),
            " N/m (FL/FR/RL/RR)   <- ", DriveRT3D.KS_SRC[])
    println("  ride ht: ", join((round(1000*h, digits=1) for h in DriveRT3D.RIDE_H[]), " / "),
            " mm (FL/FR/RL/RR)   <- ", DriveRT3D.RIDE_H_SRC[])
end

# ---- E105: the SETUP TAB ---------------------------------------------------------------------
# PO 2026-08-31, amending the "lock physics to .ibt" rule: "yes, this is a modification of the
# original 'lock physics to .ibt' rule. Make it easy to return to default."
#
# The ibt session remains the SOURCE and the DEFAULT. This applies modest deltas on top, and it
# must run HERE -- after the session install, before the car is built -- because the rates and
# ratios are MTK parameters baked in at construction.
#
# JM_SETUP="springs=+5,ride=-3,final=+2,mass=-1"  (percentages of the SESSION value)
# JM_SETUP="reset"  or unset                      -> the session's car, untouched
# E105-S2: the tab is now a STEP IN THAT MENU (SetupTab.setup_menu!), shown after the session
# values are known -- it has to be, because the tab prints the session value beside the current one.
# The env still works and still WINS: JM_SETUP set (to anything, including "reset") means no prompt,
# so every gate, replay and scripted launch stays deterministic and nothing can block on stdin.
# ── E85-S5: NETPLAY IN THE SIM ──────────────────────────────────────────────────────────────────
# S1-S4 built the transport, dead reckoning and the staleness policy, and gated all of it -- but
# nothing in the game used any of it. A remote car had never been drawn. This wires it in:
#   JM_NET=host                 host on JM_NET_PORT (default 47700)
#   JM_NET=join                 join JM_NET_HOST:JM_NET_PORT
# JM_NET_ID gives this car its id (host 1, client 2 by default); JM_NET_HZ is the send rate.
# Off by default -- an unset JM_NET changes nothing.
# ⚠️ DEFINED HERE, above first use. The first cut put these next to JM_WHEELGAP a thousand lines
# BELOW the NETLINK block that reads them: it parsed clean, passed parse_smoke, and died at load
# with `UndefVarError: NETMODE`. This file already carries that warning about WTRACK_R -- "a
# forward reference here parses fine and dies at load, which is what happened" -- and I walked
# into it anyway. A parse check cannot see an undefined NAME; only running the sim can.
const NETMODE  = lowercase(get(ENV, "JM_NET", ""))
const NET_HOST = get(ENV, "JM_NET_HOST", "127.0.0.1")
const NET_PORT = parse(Int, get(ENV, "JM_NET_PORT", "47700"))
const NET_ID   = parse(Int, get(ENV, "JM_NET_ID", NETMODE == "host" ? "1" : "2"))
const NET_HZ   = parse(Float64, get(ENV, "JM_NET_HZ", "10"))
const NET_DIAG = parse(Int, get(ENV, "JM_NET_DIAG", "0"))
# E85-S6: drive the player car from the racing line, for headless measurement runs.
# E106-S15: driveability watch (see the per-frame block in the autodrive branch).
const FIXED_DT    = parse(Float64, get(ENV, "JM_FIXED_DT", "0"))   # >0 = fixed sim step (headless sweeps)
const AI_NOWHEELS = get(ENV, "JM_NO_AI_WHEELS", "0") != "0"   # E106-S25 probe
const DRIVECHECK  = get(ENV, "JM_DRIVECHECK", "0") != "0"
const DC_AIR_MAX  = parse(Float64, get(ENV, "JM_DC_AIR",   "0.75"))  # m above ground = "levitating"
const DC_VZ_MAX   = parse(Float64, get(ENV, "JM_DC_VZ",    "6.0"))   # m/s upward   = "bounced"
const DC_STUCK_V  = parse(Float64, get(ENV, "JM_DC_STUCKV","2.0"))   # m/s
const DC_STUCK_S  = parse(Float64, get(ENV, "JM_DC_STUCKS","8.0"))   # s under STUCKV = "stuck"
const DC_SETTLE_S = parse(Float64, get(ENV, "JM_DC_SETTLE","1.0"))   # s of spawn settle to ignore
mutable struct DriveCheck
    airmax::Float64; air_s::Float64; air_bad::Int
    vzmax::Float64;  vz_s::Float64;  vz_bad::Int
    stuck::Float64;  stuckmax::Float64; stuck_s::Float64
    lastz::Float64;  lastt::Float64;  maxs::Float64
    inair::Bool;     events::Vector{Tuple{Float64,Float64,Float64,Float64,Float64}}
end
const DC = Ref(DriveCheck(0.0,0.0,0, 0.0,0.0,0, 0.0,0.0,0.0, 0.0,0.0,0.0, false, Tuple{Float64,Float64,Float64,Float64,Float64}[]))
const AUTODRIVE   = get(ENV, "JM_AUTODRIVE", "0") != "0"
const AUTODRIVE_V = parse(Float64, get(ENV, "JM_AUTODRIVE_V", "45"))   # target speed m/s
const AUTODRIVE_DIAG = parse(Int, get(ENV, "JM_AUTODRIVE_DIAG", "0"))
const AI_LAPDIAG = get(ENV, "JM_AI_LAPDIAG", "0") != "0"   # report each AI lap as it completes
# Poses of the remote cars, refreshed each frame and read by the draw pass. A Ref rather than a
# closure capture because the draw pass is a nested function built before this is known.
const NETPOSES = Ref(NTuple{6,Float64}[])
# E85-S7: receiver-side prediction-error census (JM_NET_ERR=1).
const NET_ERR  = get(ENV, "JM_NET_ERR", "0") != "0"
const NET_PREV = Ref(Dict{UInt8,NamedTuple}())
const NET_ERRS = Float64[]
const NET_DTS  = Float64[]
# E85-S5: open the net link here -- after the world/car exist, before the game loop.
include(joinpath(@__DIR__,"netplay.jl")); using .NetPlay
const NETLINK = if NETMODE == "host"
        println("  net:     HOSTING on udp/", NET_PORT, " as car ", NET_ID); flush(stdout)
        NetPlay.netopen(port = NET_PORT)
    elseif NETMODE == "join"
        println("  net:     JOINING ", NET_HOST, ":", NET_PORT, " as car ", NET_ID); flush(stdout)
        NetPlay.netopen(port = NET_PORT + NET_ID, peer = (NET_HOST, NET_PORT))
    else
        nothing
    end

include(joinpath(@__DIR__,"setup_tab.jl")); using .SetupTab
const SETUP = SetupTab.session_setup(DriveRT3D.KS[], DriveRT3D.RIDE_H[],
                                     DriveRT3D.FINAL[], DriveRT3D.MASS[])
let spec = get(ENV, "JM_SETUP", "")
    SetupTab.apply_spec!(SETUP, spec)          # the one parser, shared with the menu
    # Prompt only when a human is actually there to answer. Same guards as `choose_track()`, plus
    # JM_SETUP itself: an explicit setup on the command line is an answer already given.
    if !haskey(ENV, "JM_SETUP") && !haskey(ENV, "JM_SMOKE") &&
       !haskey(ENV, "JM_NO_SETUP_MENU") && isa(stdin, Base.TTY)
        SetupTab.setup_menu!(SETUP)
    end
    if !SetupTab.is_default(SETUP)
        # Install the modified values through the SAME validating setters the session used.
        DriveRT3D.set_suspension!(SETUP.ks...; source = "player setup (from $(basename(IBTTMPL)))")
        DriveRT3D.set_ride_height!(SETUP.rh...; source = "player setup (from $(basename(IBTTMPL)))")
        DriveRT3D.set_mass!(SETUP.mass, DriveRT3D.FRONT_FRAC[]; source = "player setup")
        DriveRT3D.FINAL[] = SETUP.final
    end
    # Always say which car is being driven. A silent divergence from the reference is the failure
    # E100 exists to prevent, so "modified" has to be as loud as the provenance lines above.
    print("  setup:   ")
    println(SetupTab.is_default(SETUP) ? "session default (unmodified)" :
            "MODIFIED by the player -- the setup menu's R, or JM_SETUP=reset, restores the session")
    SetupTab.is_default(SETUP) || print(SetupTab.describe(SETUP))
end
# PO 2026-08-27 (found by a real drive): every session ended with
#   .ibt export failed: SystemError("opening file .../lotus49_... .ibt", 2, nothing)
# That is not a path bug -- data/iracing/ holds only parse_ibt.py and profile_ibt.py, so the
# TEMPLATE the writer copies its table+YAML layout from is not in this checkout at all. The export
# could never have worked here, and it announced that with a raw SystemError at every quit, which
# reads like something broke during the drive rather than a feature that was never available.
# Check once, at startup, and say it plainly.
const IBTREC = IBTREC0 && isfile(IBTTMPL)
if IBTREC0 && !IBTREC
    println("  (.ibt telemetry off: the iRacing template is not in this checkout — ",
            basename(IBTTMPL), ". The plain-text telemetry below is unaffected.)")
end

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
        # E84-S5 / E89: bound the SECOND DIFFERENCE, not just the magnitude.
        # `cap` limits how far a point may move; the box-smooth reduces jitter. Neither bounds how
        # much a point's shift may differ FROM ITS NEIGHBOURS -- and that difference is what a kink
        # IS. A kinked centreline spikes local curvature, which spikes vtarget, which is what the PO
        # sees as AI cars that "dart around, lunge ahead, then fall back" (E89): measured 12 steps
        # >10 m/s per Monza lap in the horizon target, peaking at 53.8 m/s between samples 9.6 m
        # apart. Clamp each shift to within SECONDDIFF of the mean of its neighbours; iterate a few
        # times so a run of points relaxes rather than just the worst one.
        # ⛔ DEFAULT OFF, ON EVIDENCE (2026-08-29). Measured against its own control on one binary:
        #   Monza   steps>10 m/s 12 -> 10,  p90 1.205 -> 0.993
        #   Watkins steps>10 m/s 10 -> 11,  p90 0.257 -> 1.159   <-- 4.5x WORSE
        # The target was 12 -> 0-2. It misses that badly at Monza and REGRESSES Watkins, so it ships
        # opt-in (JM_SHIFT_CLAMP=1), not on. Kept rather than deleted because the measurement is the
        # useful part: a lateral second-difference clamp does not remove these kappa spikes, which is
        # evidence for the node-spacing hypothesis (kappa = dtheta/ds blows up on a tiny ds however
        # smooth the line is laterally) -- see E84-S5 in PRODUCT_BACKLOG.md.
        if get(ENV, "JM_SHIFT_CLAMP", "0") == "1"
            sd = parse(Float64, get(ENV, "JM_SHIFT_SECONDDIFF", "0.05"))   # metres
            for _ in 1:8
                worst = 0.0
                for i in 1:n
                    mid = (sm[mod(i-2, n)+1] + sm[mod(i, n)+1]) / 2
                    d   = sm[i] - mid
                    if abs(d) > sd
                        worst = max(worst, abs(d) - sd)
                        sm[i] = mid + sign(d)*sd
                    end
                end
                worst < 1e-4 && break
            end
        end
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
        # E76-S5: this catch swallows the reason. 1865 of the Ring's 2231 failed placements have
        # their object present in the archive under exactly this key (E76-S4), so they fail HERE —
        # and the error that would say why is discarded. Record it: one run then says whether this
        # is a single parser limitation hitting most of the Ring's scenery, or scattered faults.
        # JM_MESHERR=1 prints the first occurrence per object name.
        m = try
                Render.GPL3DO.parse_3do(tp)
            catch e
                if get(ENV,"JM_MESHERR","") != ""
                    println("   [mesherr] ", rpad(nm,16), " bytes=", rpad(length(v),9),
                            typeof(e), " :: ", first(split(sprint(showerror, e), "\n")))
                    flush(stdout)
                end
                nothing
            end
        if m === nothing
            nothing
        else
            d = dedup_scenery(m.tris)
            if (d === nothing || isempty(d)) && get(ENV,"JM_MESHERR","") != ""
                println("   [mesherr] ", rpad(nm,16), " parsed OK but EMPTY after dedup (",
                        length(m.tris), " raw tris)"); flush(stdout)
            end
            d
        end
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
    ndrop_edge = Ref(0); ndrop_road = Ref(0); nkeep_t = Ref(0)   # E76-S10 per-object drop census
    scene_at = Tuple{String,Float64,Float64,Int}[]                # E70-S5: what stands near a lapdist
    # E76-S3: is the Ring's scenery even being LOADED? Its whole load is "184 groups / 4065 tris"
    # where Spa gets 1679 objects + 5132 billboards at a fifth the length (E76-S2), and gold's first
    # kilometre is lined with crowds and hoardings that native simply does not have. Before hunting
    # filters, count what this loop is OFFERED versus what each rule removes. JM_SCENEDIAG=1.
    local n_offered=0; local n_treesrb=0; local n_nomesh=0; local n_kept=0
    sprites = NamedTuple[]                                   # E76-S8: billboard-stub placements
    scene_names=Dict{String,Int}()
    for (nm,t) in pls
        n_offered += 1
        scene_names[nm] = get(scene_names,nm,0) + 1
        if startswith(nm,"treesrb"); n_treesrb += 1; continue; end   # forest-BACKDROP "paintings"
        mesh=getmesh(nm)
        if (mesh===nothing || isempty(mesh))
            n_nomesh += 1
            # E76-S8: THE RING'S MISSING BILLBOARDS. E76-S5 instrumented this drop; the answer (S8)
            # is that all 50 distinct failing objects PARSE FINE and carry 0 triangles — bush,
            # strauch*/stree* (shrubs), deadtree, flagger (marshals). They are billboard STUBS: GPL
            # draws them as camera-facing sprites from a texture, with no geometry to parse. The GPL
            # object pipeline (Spa/Zandvoort/Watkins/Monza) has exactly that path — `isempty(full)`
            # → billboard_stub → build_billboard. This Ring-specific loader never had one, so every
            # such placement was silently dropped. That is why the Ring loads "184 groups" while Spa
            # gets 1679 objects + 5132 billboards at a fifth the length.
            # Record the placement here; the sprite ITEMS are built later, once TEXIDX exists.
            tp = joinpath(tmp, "jm_nb_"*lowercase(nm)*".3do")
            if isfile(tp)
                try
                    hh, ww, strs, aax = Render.billboard_stub(tp)
                    M = placemat(t)
                    sc = t[7] <= 0 ? 1.0 : t[7]
                    push!(sprites, (name=nm, x=Float32(M[1,4]), y=Float32(M[2,4]), z=Float32(M[3,4]),
                                    h=Float32(hh*sc), w=Float32(ww*sc), texs=strs,
                                    yaw=Float32(t[4]), aax=Float32(aax)))   # for the static-panel path
                catch
                end
            end
            continue
        end
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
                # E76-S11: also report what the BILLBOARD path would recover for this stub.
                # The h/w printed above are the MESH extents, and for a degenerate stub they are
                # 0.0/0.1 by construction — they say the mesh is unusable, not that the object is.
                # billboard_stub reads the .3do's own vertex table and texture strings, which is a
                # different question and the one that decides whether these are restorable.
                bbs = "no .3do"
                tpq = joinpath(tmp, "jm_nb_"*lowercase(nm)*".3do")
                if isfile(tpq)
                    try
                        bh, bw, bstrs, _ = Render.billboard_stub(tpq)
                        bbs = string("bb h=", round(bh,digits=2), " w=", round(bw,digits=2),
                                     " tex=", isempty(bstrs) ? "NONE" : join(bstrs,","))
                    catch e
                        bbs = "billboard_stub THREW: " * string(e)
                    end
                end
                println("   [spriteskip] ", rpad(nm,16),
                        "h=", rpad(round(hi3-lo3,digits=2),7),
                        "w=", rpad(round(hih-loh,digits=2),7),
                        hr.found ? string("lapdist=", rpad(round(hr.lapdist,digits=0),9),
                                          "lat=", rpad(round(hr.lateral,digits=1),7)) : "off-ribbon  ",
                        bbs)
            end
            continue
        end
        M=placemat(t)
        # E70-S5: what scenery actually stands near a given lapdist? The PO's E76 asks for "buildings
        # and crowds shortly after the start-finish line"; the crowds are done (E76-S10) and the
        # buildings were never checked. The Ring bypasses the object pipeline, so JM_OBJFIND cannot
        # see it — this is the scenery-side equivalent. JM_SCENE_AT="lapdist" (±250 m).
        if get(ENV,"JM_SCENE_AT","") != ""
            _hr = JuliaMotor.hat(ribbon, Float64(M[1,4]), Float64(M[2,4]))
            if _hr.found && abs(_hr.lapdist - parse(Float64, ENV["JM_SCENE_AT"])) < 250.0
                push!(scene_at, (nm, _hr.lapdist, _hr.lateral, length(mesh)))
            end
        end
        ap(q)=(Float32(M[1,1]*q[1]+M[1,2]*q[2]+M[1,3]*q[3]+M[1,4]),
               Float32(M[2,1]*q[1]+M[2,2]*q[2]+M[2,3]*q[3]+M[2,4]),
               Float32(M[3,1]*q[1]+M[3,2]*q[2]+M[3,3]*q[3]+M[3,4]))
        rn(n)=(Float32(M[1,1]*n[1]+M[1,2]*n[2]+M[1,3]*n[3]),
               Float32(M[2,1]*n[1]+M[2,2]*n[2]+M[2,3]*n[3]),
               Float32(M[3,1]*n[1]+M[3,2]*n[2]+M[3,3]*n[3]))
        if get(ENV,"JM_SCENEDROP","") != "" && occursin(lowercase(ENV["JM_SCENEDROP"]), lowercase(nm))
            M0 = placemat(t)
            hr0 = JuliaMotor.hat(ribbon, Float64(M0[1,4]), Float64(M0[2,4]))
            println("   [scenedrop] ", nm, ": mesh has ", length(mesh), " tris; placed at ",
                    hr0.found ? string("lapdist ", round(Int,hr0.lapdist), " lat ", round(hr0.lateral,digits=1)) : "OFF-RIBBON",
                    "  origin z=", round(M0[3,4],digits=1))
        end
        # E70-S6: the object's own robust centre and extent (median-based, so a single junk vertex
        # cannot inflate it) — the reference the junk test is measured against.
        local ocx=0f0; local ocy=0f0; local ocz=0f0; local objext=1f0
        begin
            xs=Float32[]; ys=Float32[]; zs=Float32[]
            for tr in mesh, q in tr.p
                pw = ap(q); push!(xs,pw[1]); push!(ys,pw[2]); push!(zs,pw[3])
            end
            if !isempty(xs)
                sort!(xs); sort!(ys); sort!(zs)
                md(v) = v[cld(length(v),2)]
                ocx, ocy, ocz = md(xs), md(ys), md(zs)
                q95(v) = v[max(1,min(length(v), ceil(Int,0.95*length(v))))]
                q05(v) = v[max(1,min(length(v), ceil(Int,0.05*length(v))))]
                objext = max(q95(xs)-q05(xs), q95(ys)-q05(ys), q95(zs)-q05(zs), 1f0) / 2
            end
        end
        for tr in mesh
            w=(ap(tr.p[1]),ap(tr.p[2]),ap(tr.p[3])); nn=(rn(tr.n[1]),rn(tr.n[2]),rn(tr.n[3]))
            # DROP stray garbage geometry: a tri with a huge or wildly-stretched edge is a
            # vertex parsed at a junk coordinate — these render as the giant jagged "Star
            # Destroyer" shapes floating off in the sky.  Real scenery tris are < ~80 m.
            e1=hypot(w[2][1]-w[1][1],w[2][2]-w[1][2],w[2][3]-w[1][3])
            e2=hypot(w[3][1]-w[2][1],w[3][2]-w[2][2],w[3][3]-w[2][3])
            e3=hypot(w[1][1]-w[3][1],w[1][2]-w[3][2],w[1][3]-w[3][3])
            emax=max(e1,e2,e3); emin=min(e1,e2,e3)
            # E76-S10: name what this drops, per object. The "stretched garbage" rule was written for
            # vertices parsed at junk coordinates, but a CROWD TERRACE is legitimately long and thin —
            # ogrnd2's panels reach 108 m wide and 2 m tall, so emax > 70 && emax > 10*emin describes
            # them exactly. JM_SCENEDROP=<name substring> reports the drops for one object.
            # E70-S6: the absolute rule mistakes LEGITIMATE long spans for junk. It was written for
            # vertices parsed at nonsense coordinates, and those are OUTLIERS relative to the object's
            # own extent — whereas a grandstand's roof beam is long *and* inside its own bbox. Judge
            # each triangle against the object it belongs to: a vertex far outside the object's own
            # 95th-percentile extent is junk; a long edge wholly within it is architecture.
            # E76-S11 measured the cost of getting this wrong: grand116, the Ring's start/finish
            # grandstand, loses 16 of its 76 triangles (21%). JM_EDGE_ABS=1 restores the old rule.
            _junk = if get(ENV,"JM_EDGE_ABS","0") != "0"
                (emax > 150f0 || (emax > 70f0 && emax > 10f0*emin))
            else
                # objext = the object's own robust half-extent, computed once per mesh below
                far = max(abs(w[1][1]-ocx), abs(w[2][1]-ocx), abs(w[3][1]-ocx),
                          abs(w[1][2]-ocy), abs(w[2][2]-ocy), abs(w[3][2]-ocy),
                          abs(w[1][3]-ocz), abs(w[2][3]-ocz), abs(w[3][3]-ocz))
                (far > 3f0*objext + 20f0) || emax > 400f0
            end
            if _junk
                if get(ENV,"JM_SCENEDROP","") != "" && occursin(lowercase(ENV["JM_SCENEDROP"]), lowercase(nm))
                    ndrop_edge[] = ndrop_edge[] + 1
                end
                continue
            end
            # DROP scenery that intrudes into the road corridor (mis-placed/tilted objects
            # poking through the track) — render AND collision.  GPL world (gx,gy,gz=up);
            # the racing ribbon is queried in (gx,gy), road height is hr.height.
            cgx=(w[1][1]+w[2][1]+w[3][1])/3; cgy=(w[1][2]+w[2][2]+w[3][2])/3; cgz=(w[1][3]+w[2][3]+w[3][3])/3
            hr = JuliaMotor.hat(ribbon, cgx, cgy)
            if (hr.found && abs(hr.lateral) < 5.0 && abs(cgz - hr.height) < 3.0)
                if get(ENV,"JM_SCENEDROP","") != "" && occursin(lowercase(ENV["JM_SCENEDROP"]), lowercase(nm))
                    ndrop_road[] = ndrop_road[] + 1
                end
                continue
            end
            # COLLISION: only near-HORIZONTAL scenery (ground/banks) goes in the HAT — never
            # walls/buildings/bridges/signs, or the car climbs them.  GPL z is up, so a ground
            # tri's geometric normal is z-dominant; a vertical structure's is not.
            ux=w[2][1]-w[1][1]; uy=w[2][2]-w[1][2]; uz=w[2][3]-w[1][3]
            vx=w[3][1]-w[1][1]; vy=w[3][2]-w[1][2]; vz=w[3][3]-w[1][3]
            nz=ux*vy-uy*vx; nl=sqrt((uy*vz-uz*vy)^2+(uz*vx-ux*vz)^2+nz^2)
            (nl > 1f-6 && abs(nz)/nl > 0.4f0) && push!(hat, Render.GPL3DO.Tri(w, nn, tr.uv, tr.tex, tr.col, tr.flat, tr.ptype))
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
        # E76-S7: are the Ring's CROWD objects placed at all? S6 concluded "essentially no crowd
        # objects" from a search that returned only grand116 — but that pattern was never validated.
        # Validated since: on Zandvoort `ppl_*` returns exactly the names its census found, while the
        # Ring uses different naming entirely (people*, pplrow01, PPLv). So report every PLACED name
        # matching a crowd pattern, with whether its mesh loaded. JM_SCENEFIND=people|ppl|crowd|grand
        if get(ENV,"JM_SCENEFIND","") != ""
            pat = Regex(get(ENV,"JM_SCENEFIND",""), "i")
            hits = sort([(nm,c) for (nm,c) in scene_names if occursin(pat, nm)], by=x->-x[2])
            println("   -- PLACED names matching /", get(ENV,"JM_SCENEFIND",""), "/i: ", length(hits), " --")
            for (nm,c) in hits[1:min(end,20)]
                mm = getmesh(nm)
                st = mm === nothing ? "NO MESH" : (isempty(mm) ? "EMPTY (billboard)" : string(length(mm), " tris"))
                println("      ", rpad(nm,16), rpad(c,6), "placements   ", st)
            end
            isempty(hits) && println("      (none placed)")
        end
        miss = sort([(nm,c) for (nm,c) in scene_names if getmesh(nm)===nothing || isempty(getmesh(nm))], by=x->-x[2])
        if !isempty(miss)
            println("   -- most-placed names with NO MESH (top 15) --")
            for (nm,c) in miss[1:min(end,15)]; println("      ", rpad(nm,18), c, " placements"); end
        end
        flush(stdout)
    end
    if get(ENV,"JM_SCENE_AT","") != ""
        sort!(scene_at, by=x->abs(x[3]))
        println("== JM_SCENE_AT ", ENV["JM_SCENE_AT"], " ±250 m: ", length(scene_at), " scenery objects rendered ==")
        println("   name            lapdist   lateral   tris")
        for r in scene_at[1:min(end,22)]
            println("   ", rpad(r[1],15), rpad(round(Int,r[2]),10), rpad(round(r[3],digits=1),10), r[4])
        end
        flush(stdout)
    end
    if get(ENV,"JM_SCENEDROP","") != ""
        println("   [scenedrop] ", ENV["JM_SCENEDROP"], ": dropped ", ndrop_edge[],
                " by the stretched-edge rule, ", ndrop_road[], " by the road-corridor rule")
        flush(stdout)
    end
    (hat, [Render.TrackPart(v, tex, (0.5f0,0.5f0,0.5f0)) for (tex,v) in groups], sprites)
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
        # E73-S5: MONZA joins WATGLEN and NURB. Its centreline strayed 8.2 m off the road at s=500
        # (car floating over unmodelled ground for ~300 m) with road gaps at s=2750/4500. Measured:
        # the road-only oracle ALONE changes nothing (Monza was also excluded from re-centring), and
        # re-centring alone against the full-terrain oracle fixes only part of it (20/24 healthy,
        # gaps remain). Together they give 24/24 healthy, and the car photographs on asphalt at all
        # three previously-broken sites (near-white in frame: 93.5% -> 0.7%).
        # E71-S12: SPA joins them. Under the CORRECTED census (coverage of lat 0, not centroid
        # distance) Spa's shipped line has three buckets where no road triangle covers the centreline
        # — s=0, s=750, s=10000 — and the oracle takes it to 57/57. Confirmed independently of the
        # census, which is the standard E73-S5 set: photographed at s=750 and s=10000, the shipped
        # line has the car riding the grass verge (grass under the car 29.6% and 19.8% of the lower
        # frame); with the oracle it is centred on tarmac (0.6% and 0.1%).
        # ZANDVOORT deliberately NOT included: under the corrected census its shipped line is already
        # 17/17 clean, so it needs no change — which also preserves the line the PO verified.
        if (WATGLEN || NURB || MONZA || SPA || get(ENV,"JM_ROADHAT","0") != "0") && nroad >= 200
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
        # E73-S5: MONZA is excluded from re-centring outright, which is why its centreline strays
        # 8.2 m off the road at s=500 and shows road gaps at s=2750/4500 (E73-S3/S4) — the raw .trk
        # line is used uncorrected. Enabling the road-only oracle changed nothing precisely because
        # this step never runs. JM_FORCE_RECENTRE=1 lifts the exclusion so the effect can be measured
        # before deciding whether the exclusion is still justified.
        # E73-S5: the `|| MONZA` exclusion is REMOVED. It carried no comment explaining itself, and
        # with it in place Monza's raw .trk line ran off the circuit for ~300 m. JM_NO_RECENTRE=1
        # restores the raw line for every track, which is the revert path.
        haskey(ENV, "JM_NO_RECENTRE") ? a :
            haskey(ENV,"JM_NORECENTRE") ? (println("  re-centring SKIPPED (JM_NORECENTRE) — E84-S4 A/B"); a) :
            recentre_on_road(a, ROADHAT; passes = (ROADHAT === TERRAIN0 ? 1 : 4))
    end
    const RIBBON0  = GPLTrack.build_surface(ALIGNED, TERRAIN0)
    # GPL Nürburgring places its landmass/scenery as .dat sub-objects via 0x0E nodes;
    # load + place them so the road isn't floating over a void (Zandvoort has none).
    SECTRI = Render.GPL3DO.Tri[]; SECPARTS = Render.TrackPart[]; RINGSPRITES = NamedTuple[]
    if NURB && isfile(joinpath(ZD, "nurburg.dat"))
        print("scenery… "); flush(stdout)
        dp = Render.GPLDat.parse_dat(joinpath(ZD, "nurburg.dat"))
        SECTRI, SECPARTS, RINGSPRITES = gpl_scenery(ZTRK, dp, RIBBON0)
        print(length(SECPARTS), " groups / ", length(SECTRI), " tris / ",
              length(RINGSPRITES), " sprites… ")
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
        # COVERAGE, not centroid distance. The centroid form flagged rows at 3-5 m that are almost
        # certainly fine — a large road triangle centred 4 m off the line still covers it — and Spa's
        # s=0 pit straight, where the grid demonstrably sits on tarmac, was among them. Two decisions
        # now hang on this metric (whether to enable the road-only oracle on Spa and Zandvoort), so
        # measure the thing that matters: does any road triangle's own vertices STRADDLE lateral 0?
        # `near` keeps the centroid figure too, so the two readings can be compared rather than one
        # silently replacing the other.
        near = Dict{Int,Float64}(); cnt = Dict{Int,Int}(); covers = Dict{Int,Bool}()
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
            if !get(covers, b, false)
                lo = Inf; hi = -Inf
                for vi in 1:3
                    hv = JuliaMotor.hat(TRKSURF, Float64(t.p[vi][1]), Float64(t.p[vi][2]))
                    hv.found || continue
                    lo = min(lo, hv.lateral); hi = max(hi, hv.lateral)
                end
                (isfinite(lo) && lo <= 0.0 <= hi) && (covers[b] = true)
            end
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
            elseif !get(covers, b, false) && near[b] > 3.0
                println("   s=", rpad(b*step,8), "no road triangle COVERS the line; nearest centroid ",
                        round(near[b],digits=1), " m off   (", cnt[b], " tris)  *** LINE OFF ROAD ***")
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
            local v = part.verts; seen = Set{NTuple{4,Int}}()   # `local`: v shadows a global
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
# E106-S7 (PO video): "arms stationary and detached from gloves" -- the chrome shards around the
# wheel. The hands/arms ITEM is last in the PO's priority order, so until it runs the broken
# display is HIDDEN rather than shown wrong: an absent arm is a smaller lie than a detached one
# (the same principle as the netplay ghost cars). JM_HANDS=1 restores the old display.
const HANDS = get(ENV,"JM_HANDS","0") != "0"
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
# E106-S3: E60 retextured the WRONG part. helmeg.3do is two parts: a 176-tri "helblack" piece
# (the visor/trim -- black in gold too) and a 572-tri UNTEXTURED shell that fully envelops it
# (y 0.014..0.249 vs 0.09..0.167) -- the per-driver skin slot GPL binds at runtime (l01helm..
# l20helm / clahelm; twenty skins ship with the car). E60 mapped helblack->clahelm, which painted
# the hidden trim and left the visible shell untextured: the chase view's solid-black blob of a
# helmet. Texture the SHELL with Clark's skin and leave helblack black, as gold does.
# E106-S28 (from the S27 gold A/B): gold's helmet is BLUE -- its dome samples (85,91,128), i.e.
# blue-dominant. Measured against every skin the car ships (clahelm, hilhelm, l01..l20), `clahelm`
# -- what E60/S3 chose -- has NO blue at all (49,50,51; B/R 1.04) and `hilhelm` is blue but far too
# dark (18,28,49). The closest by hue AND brightness is `l10helm` (114,110,138; B/R 1.21).
# ⚠️ This is a COLOUR MATCH against one gold still, not proof of which skin GPL selects: the car's
# .gplw configs describe versions ("Standard version with 3D helmet") and never name a helmet, so
# there is nothing authoritative to read. JM_HELMET=<name> overrides.
const HELMET_TEX = get(ENV, "JM_HELMET", "l10helm")
const HELMP = [Render.TrackPart(p.verts, p.tex=="" ? HELMET_TEX : p.tex, p.col)
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
# E106-S6b: the EXTERIOR body renders through the lotd wrapper too (JM_BODY_WRAP=0 reverts to the
# bare mesh). GPL binds the exterior's slot table at runtime; lotd IS the painted livery -- green,
# yellow stripe, TEAM LOTUS roundels -- and gold's chase view shows exactly that paint where ours
# showed untextured green facets.
const _CARP_SRC = get(ENV,"JM_BODY_WRAP","1") != "0" ? joinpath(LOTDIR,"lotd.3DO") : LOT3DO
# E106-S8 (PO: "random shapes and colors on the engine" in nintendo view). The lotd wrapper binds
# the INTERIOR slot textures -- the dashboard dial faces (dash7/dash7a/ldashr) and the cockpit wall
# panels (lotinsa/lotinsid) -- and some of those polys sit low in the engine bay, so from the chase
# camera a DIAL FACE lies flat across the engine as a garish striped panel. Those textures belong
# to the DRIVER view only (CARPIN keeps them); the exterior body must not carry them.
const _COCKPIT_ONLY = ("dash7","dash7a","ldashr")   # dial faces only; lotinsa/lotinsid are also body panels, lotd is the paint
# E106-S10 (PO: "flicker on engine and inside of rear tires", Zandvoort video): the body carries
# 467 COINCIDENT SAME-FACING triangles out of 2219 (21%) -- stacked duplicates whose depth values
# tie, so the rasteriser picks a different winner per frame and the surface shimmers as the car
# moves. That is precisely what `dedup=:orient` exists for (its own comment: "z-FIGHT (flickers
# only when moving)"); :orient collapses same-facing stacks while KEEPING opposite-facing pairs,
# so double-sided panels still read correctly from each side. JM_CAR_DEDUP=0 reverts.
const _CAR_DEDUP = get(ENV,"JM_CAR_DEDUP","1") != "0" ? :orient : false
const CARP   = Render.extract_gpl_car(_CARP_SRC; exclude=(_HAND_EXC...,_LOTBLACK_EXC...,_EXTRA_EXC...,_GARBAGE_EXC...,DRIVER_TEX...,MIRROR_TEX...,Render.STEER_TEX...,"pipe3","plaface","plahelm",_COCKPIT_ONLY...), exclude_groups=(6600,3560,27288,39792), cockpit_clean=true, maxlat=CARP_MAXLAT, dedup=_CAR_DEDUP, grey=(TUB_GREY,TUB_GREY+0.01f0,TUB_GREY+0.02f0))   # driver body + gauge + windscreen + mirrors drawn separately; hands kept unless JM_HANDS=0.  E64 S4 (D12): groups 27288/39792 are WHOLE DISPLACED ASSEMBLIES (suspension+exhaust+driver textures at y 0.42…1.16 / −1.12…−0.42, mirror copies) — GPL runtime-hidden branches our positioner walk mis-places; they were the chase view's "chrome spider-legs" through the rear tyres
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
    # E82-S2: the front carries the same overhang -- 4 of its 98 triangles are 1.3 m strips spanning
    # x 1.54..2.73 at z = +-1.12, i.e. forward of the nose and outside the wheels. Clip at the wheel
    # face like the rear; the 94 that make up the actual wishbone assembly (x <= 1.8, |z| <= 0.63) stay.
    Render.extract_gpl_car(LOT3DO; only=("lsusp1","frontlot"), maxlat=parse(Float32,get(ENV,"JM_FSUSP_MAXLAT","0.85")),
                           # E82-S3: the front does NOT trim, and that is measured, not assumed.
                           # Its overhang is 4 whole 1.3 m strips spanning x 1.54..2.73 at |z| 1.12 --
                           # stray geometry, not a part that should reach the wheel. Trimming them at
                           # the 0.85 face keeps their inboard halves, which still reach x 2.13, i.e.
                           # forward of the nose (the gate goes red on exactly that). The rear is the
                           # opposite case: its driveshafts genuinely run out to the hub. Drop here,
                           # trim there.
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
# E75-S8: the REAR suspension, drawn the way the FRONT one now is. E75-S4 showed no fold angle
# works for RSUSPP_A/B (0 deg = spears past the wheels, 45/90 = invisible), and E75-S7 fixed the
# front by taking the parts DIRECTLY with an extent clip instead of excluding their group and then
# re-placing them with a corrective transform. Same treatment here: pull lshok/lsusp5/lsusp7/lbrdisc
# by texture, clip oversized tris by edge length, and draw them with NO fold — if the parts are
# authored in place, the fold was never needed and is what made them invisible.
# VERDICT (E75-S8): this does NOT work — the raw parts are UNFOLDED flat strips, so drawing them in
# place lays panels under the car. Default OFF (JM_RSUSP2=1 to re-enable for study). Kept because the
# measurement it enabled is what identified the unfolded-strip authoring; JM_RSUSP2_MAXEDGE tunes the clip.
const RSUSPP2 = Render.extract_gpl_car(LOT3DO; only=("lshok","lsusp5","lsusp7","lbrdisc"),
                                       maxlat=1.3f0,
                                       maxedge=parse(Float32,get(ENV,"JM_RSUSP2_MAXEDGE","1.5")))
if get(ENV,"JM_RSUSP2_DIAG","") != ""
    # E75-S8: the per-texture table (JM_CARPARTS) says these parts are compact, yet they render as
    # spears. Print the bbox of EXACTLY what is drawn, per part, so the two cannot disagree silently.
    println("== JM_RSUSP2_DIAG: the parts RSUSPP2 actually hands to the renderer ==")
    println("   tex           tris   longitudinal x     lateral z          height y           longest edge")
    for pp in RSUSPP2
        local v = pp.verts; n = length(v) ÷ 11   # `local`: v shadows a global
        ex = [Inf32,-Inf32,Inf32,-Inf32,Inf32,-Inf32]
        for i in 1:11:length(v)-10
            ex[1]=min(ex[1],v[i]);   ex[2]=max(ex[2],v[i])
            ex[3]=min(ex[3],v[i+2]); ex[4]=max(ex[4],v[i+2])
            ex[5]=min(ex[5],v[i+1]); ex[6]=max(ex[6],v[i+1])
        end
        # longest triangle edge, in the same units
        le = 0f0
        for t in 1:33:length(v)-32
            a=(v[t],v[t+1],v[t+2]); b=(v[t+11],v[t+12],v[t+13]); c=(v[t+22],v[t+23],v[t+24])
            for (u,w) in ((a,b),(b,c),(c,a))
                le = max(le, sqrt((u[1]-w[1])^2+(u[2]-w[2])^2+(u[3]-w[3])^2))
            end
        end
        println("   ", rpad(pp.tex,14), rpad(n,7),
                rpad(string(round(ex[1],digits=2),"…",round(ex[2],digits=2)),19),
                rpad(string(round(ex[3],digits=2),"…",round(ex[4],digits=2)),19),
                rpad(string(round(ex[5],digits=2),"…",round(ex[6],digits=2)),19),
                round(le,digits=2))
    end
    flush(stdout)
end
const MIRRORP = Render.extract_gpl_car(LOT3DO; only=MIRROR_DRAW, maxlat=0.95f0)  # rear-view mirrors — clean disc, re-placed on the cowl (see MIRRORMAT)
const HANDP  = Render.extract_gpl_car(LOT3DO; only=("lohand",),  maxlat=0.95f0)  # E64 S2: gloved hands on the rim — ride the wheel rotation
# E64 S7 (D12 residual): the runtime-hidden HIGH-DETAIL rear-suspension assemblies (groups
# 27288/39792 — the S4 exclusions).  S4 mis-read their raw GPL coords as displaced (raw y is
# LATERAL, not up): they are near-correctly authored left/right halves — arms/driveshafts/
# shocks/discs around the rear axle — but ~25% too wide/long (a positioner-scale mis-read:
# shocks reach lateral 1.06 vs the 0.85 wheel face = S4's spear tips through the tyres).
# Drawn separately in the chase view with a tunable corrective scale about the rear axle.
# E75-S12: the flat braces (lsusp2 0.76×0.03×0.50, lsusp7 0.89×0.03×0.48) render as broad specular
# PLATES where gold shows slender wishbones. JM_RS_FLAT=1 keeps them for A/B.
# VERDICT (E75-S12): excluding them changes the render almost not at all, so the broad chrome panels
# are NOT the flat braces. Default keeps them; JM_RS_NOFLAT=1 drops them for further A/B.
const _RSEXC = get(ENV,"JM_RS_NOFLAT","0") != "0" ? ("ltraymap","lshad","lsusp2","lsusp7") : ("ltraymap","lshad")
# E75-S13: draw the rear group ONE PART AT A TIME to find which renders as the broad chrome panel.
# JM_RS_ONLY=<texture> restricts the rear suspension to that texture alone.
const _RSONLY = get(ENV,"JM_RS_ONLY","")
# E82-S2 (2026-08-31): CLIP THE REAR HALVES AT THE WHEEL FACE. These assemblies reach lateral 1.12-1.16
# while the wheel face is 0.85 (CARP_MAXLAT) -- the code has recorded that overhang since E64-S4 as the
# chase view's "chrome spider-legs through the rear tyres", and the 90-degree fold had merely hidden
# them BELOW THE ROAD rather than fixing them (E82-S1). With the fold removed they became visible, so
# the overhang has to be clipped where it belongs: at the tyre. The inboard portion (z 0.42..0.85), the
# driveshaft and links gold shows between the wheels, is kept. JM_RSUSP_MAXLAT overrides.
# E82-S3: TRIM instead of DROP. maxlat used to discard any triangle with a vertex past the wheel
# face, so the driveshafts -- which run from the gearbox OUT to the hub at |lat| 0.772 and are built
# from triangles whose far vertices sit past the 0.85 face -- lost every one of those triangles and
# ended at 0.61 as stubs. Gold shows them reaching the wheel. `trim=true` cuts each triangle AT the
# plane (Sutherland-Hodgman, interpolating position/normal/UV) and keeps the inboard part.
# Measured on group 27288: dropping gives 83 tris spanning |lat| 0.422..0.61; trimming gives 176
# spanning 0.422..0.85 -- past the hub, terminating exactly at the wheel face, nothing outside it.
# JM_SUSP_TRIM=0 restores the drop behaviour as the negative control.
# Trim ONLY the driveshaft texture. Measured by texture (E82-S3): trimming the whole group also
# cuts down its `lid`/`arms`/`top`/`rear` mirror-copies -- the "spears" E64-S4 recorded in 27288/39792
# -- and a Monza chase capture showed them come back as wide chrome slabs lying across the tyres,
# plainly worse than the stubs. `axlelot` is the driveshaft itself and is the part that must reach
# the hub. Everything else in the group keeps the S2 drop. JM_SUSP_TRIM=0 = drop everything (S2).
const SUSP_TRIM = get(ENV,"JM_SUSP_TRIM","1") != "0" ? (split(get(ENV,"JM_SUSP_TRIM_TEX","axlelot"), ",")...,) : false
# E82-S3: clip the rear at the half-track the WHEELS ARE DRAWN AT (WTRACK_R), not at 0.85.
# 0.85 is CARP_MAXLAT -- the BODY mesh's clip -- and using it here was a frame confusion that cost
# this sprint two captures: the gate measured the part mesh against 0.85, reported "inside the
# tyres", and the screen showed chrome rods sticking out past and below the rear wheels. The wheels
# are drawn at half-track WTRACK_R = 0.74, so anything reaching 0.85 is 11 cm outside the wheel
# centre plane by construction. Clipping at WTRACK_R puts the shaft end at the hub, inside the tyre.
# (WTRACK_R itself is defined further down, so read the same env/default it does rather than
#  referring to it -- a forward reference here parses fine and dies at load, which is what happened.)
const RSUSP_MAXLAT = parse(Float32, get(ENV,"JM_RSUSP_MAXLAT", get(ENV,"JM_TRACK_R","0.74")))
# E102-S6 (PO: "axles should be HORIZONTAL between centre of wheel and chassis, not sticks pointing
# outward and downward from the back wheels"). E102-S4 decomposed this assembly into 5 connected
# solids and found the report's shape exactly: a 3-triangle `axlelot` solid spanning 0.62 m in x,
# reaching the wheel plane at |lat| 0.74 and DROPPING 0.099 m across that run -- a thin isolated
# stick, out at the wheel, sloping down. E102-S5 confirmed it on screen.
#
# Nothing that filters by texture or by lateral extent can remove it: the real driveshaft is the
# same texture and reaches the same place. Its SEPARABILITY is the only handle it offers, so the
# filter drops connected solids smaller than 4 triangles, restricted to `axlelot` so the rest of
# the assembly's small detail is untouched. Verified with JM_MC_DIAG=1: it drops EXACTLY one solid,
# and its measurements are S4's signature to the centimetre.
# ⚠️ Deliberately NOT "re-pose the shaft horizontal": E102-S4 established there is no shaft to
# re-pose -- 65 of the 89 triangles are one connected mesh spanning five textures, so the driveshaft,
# links and brake disc are a single solid. The stick is a separate artefact, not a mis-angled part.
# 🔴 DEFAULT OFF (0), because IT DOES NOT FIX THE REPORTED DEFECT. The filter works exactly as
# designed -- JM_MC_DIAG=1 shows it dropping precisely one solid, S4's signature to the centimetre --
# but a chase capture with it ON still shows the chrome rod pointing outward and downward from the
# rear wheel, unchanged. So the 3-triangle sliver is NOT what the PO is looking at.
# That also narrows E102 usefully: E102-S5 identified the sticks as `axlelot` via JM_RS_ONLY, and
# since the separable axlelot solid is not it, the stick must be the DRIVESHAFT ITSELF -- part of
# the 65-triangle connected solid that E82-S3 deliberately trims to reach the hub. The open question
# is therefore its POSE (the assembly's placement/angle), not its membership, and "there is no
# separable shaft to rotate" (E102-S4) is the obstacle to solve rather than a reason to stop.
# JM_RSUSP_MINCOMP=4 re-enables the filter for anyone continuing that line.
const RSUSP_MINCOMP = parse(Int, get(ENV, "JM_RSUSP_MINCOMP", "0"))
const RSUSPP_A = _RSONLY == "" ? Render.extract_gpl_car(LOT3DO; include_groups=(27288,), exclude=_RSEXC, maxlat=RSUSP_MAXLAT, trim=SUSP_TRIM, min_component=RSUSP_MINCOMP, min_component_tex=("axlelot",)) :
                                 Render.extract_gpl_car(LOT3DO; include_groups=(27288,), only=(_RSONLY,))   # one side each —
const RSUSPP_B = _RSONLY == "" ? Render.extract_gpl_car(LOT3DO; include_groups=(39792,), exclude=_RSEXC, maxlat=RSUSP_MAXLAT, trim=SUSP_TRIM, min_component=RSUSP_MINCOMP, min_component_tex=("axlelot",)) :
                                 Render.extract_gpl_car(LOT3DO; include_groups=(39792,), only=(_RSONLY,))   # the halves carry a residual ±roll our posmat mis-composes
# ── E106-S4: THE EXHAUSTS, placed where gold puts them ──────────────────────────────────────────
# `pipe3` (the chrome header bundles + megaphones, 293 tris) decomposes into 7 connected solids:
# two header bundles (x −0.72..−0.27), two megaphones (x −1.6..−0.69 — ending just past the rear
# axle, the right length), a small bracket, and two 7-tri TIPS parked at z ±1.0 / x to −2.5 —
# GPL runtime-hidden branches (the posmat-clamp family) that must never draw. In CARP the whole
# group drew at its authored height, megaphone centreline y ≈ −0.06: dangling at the car's
# underside, which is what every chase capture showed. Gold's megaphones run level with the rear
# hubs. So: extract pipe3 on its own, drop the parked tips with the lateral clip (they sit at
# |z| ≈ 1.0, everything real is inside 0.45), and draw lifted by JM_PIPE_LIFT (default 0.18 m,
# putting the centreline at ≈ +0.12 — hub height).
# ── E106-S5: THE COCKPIT VIEW GETS ITS OWN BODY, dressed as GPL dresses it ─────────────────────
# GPL renders the driver view through lotd.3DO: node 0x0E re-enters lotus.3do with a 9-slot
# texture table (lotd/plaface/plahelm/dash7/ldashr/lotinsid/lotinsa/dash7a) -- the SAME mesh, a
# different skin. The riveted-aluminium interior is not separate geometry; it is the tub re-skinned.
# So the port now does the same: CARPIN is the body extraction with the cockpit-region untextured
# panels dressed in `lotinsid` (their UVs are authored for it), drawn ONLY in cockpit view; the
# chase/exterior keeps the undressed CARP with the green tub. JM_COCKPIT_DRESS=0 disables.
# E106-S6: THE REAL THING. lotd.3DO re-enters lotus.3do with the cockpit texture table, and the
# slot selectors (0x2C in the car mesh, now implemented) bind it: 644 tris of painted body skin
# (lotd.mip -- green, yellow stripe, TEAM LOTUS roundels, rivets), the riveted interior panels
# (lotinsid/lotinsa), the real dash (dash7/dash7a/ldashr). This replaces the S5 geometric dress
# entirely. plaface/plahelm (the player face/helmet the mirrors reflect) are excluded here because
# the helmet is drawn separately at the head pivot (E60), as are the hands, pipes and windscreen.
const CARPIN = get(ENV,"JM_COCKPIT_DRESS","1") != "0" ?
    Render.extract_gpl_car(joinpath(LOTDIR,"lotd.3DO"); exclude=(_HAND_EXC...,_LOTBLACK_EXC...,_EXTRA_EXC...,_GARBAGE_EXC...,DRIVER_TEX...,MIRROR_TEX...,Render.STEER_TEX...,"pipe3","plaface","plahelm"), exclude_groups=(6600,3560,27288,39792), cockpit_clean=true, maxlat=parse(Float32,get(ENV,"JM_COCKPIT_MAXLAT","0.30")), dedup=_CAR_DEDUP, grey=(TUB_GREY,TUB_GREY+0.01f0,TUB_GREY+0.02f0)) :   # E106-S10: dedup coincident stacks (visor/mirror flicker)
    Render.TrackPart[]
# The lotd body carries its own MIRROR PODS, which land exactly where the port's live-RTT round
# mirrors already draw -- so the pods (and only the pods) are cut here, by centroid box in the
# render frame (x fwd, y up, z lateral). Stride 11 floats/vertex (pos+normal+uv+col).
function _drop_box!(parts, x0, x1, y0, z0)
    for (pi, p) in enumerate(parts)
        v = p.verts; n = length(v) ÷ 33
        keep = Float32[]
        for t in 0:n-1
            base = t*33
            cx = (v[base+1] + v[base+12] + v[base+23]) / 3
            cy = (v[base+2] + v[base+13] + v[base+24]) / 3
            cz = (v[base+3] + v[base+14] + v[base+25]) / 3
            inpod = (x0 <= cx <= x1) && (cy >= y0) && (abs(cz) >= z0)
            inpod || append!(keep, @view v[base+1:base+33])
        end
        parts[pi] = Render.TrackPart(keep, p.tex, p.col)
    end
    parts
end
# (pod box-cut superseded: the 0.30 lateral clamp removes the flanks, pods included)
# ── E106-S9: THE AXLES, synthesized straight (PO: "Axles are needed") ──────────────────────────
# Every attempt to re-pose GPL's rear-half assemblies has failed the same way: the halves compose
# several parts in DIFFERENT local frames through positioners our walk mis-chains, so any single
# corrective transform fixes the driveshaft and breaks the radius arms (roll 20° levelled the shaft
# and pointed the arms at the ground). Measured across E64/E75/E82/E102/S7/S9.
# So the driveshafts are BUILT, not extracted: two straight cylinders from the diff (|z|=0.16) to
# each hub (|z|=WTRACK_R), at hub height, wearing GPL's own axlelot texture -- correct pose by
# construction, GPL's look by its own art. The rest of the halves stays off until someone decodes
# the positioner chain. JM_AXLES=0 removes them; JM_AXLE_Y/R tune.
const AXLE_Y = parse(Float32, get(ENV, "JM_AXLE_Y", "0.02"))
const AXLE_R = parse(Float32, get(ENV, "JM_AXLE_R", "0.024"))
function _axle_part(zsign)
    segs = 10; x0 = -1.15f0
    # WTRACK_R is defined ~300 lines below -- "a forward reference here parses fine and dies at
    # load" (the file's own warning, now hit a third time). Read the same env/default it does.
    z0, z1 = zsign*0.16f0, zsign*parse(Float32, get(ENV,"JM_TRACK_R","0.74"))
    v = Float32[]
    for k in 0:segs-1
        a0 = 2f0*Float32(pi)*k/segs; a1 = 2f0*Float32(pi)*(k+1)/segs
        # two triangles per segment; cylinder axis along z, circle in x/y
        p00 = (x0 + AXLE_R*cos(a0), AXLE_Y + AXLE_R*sin(a0), z0)
        p01 = (x0 + AXLE_R*cos(a1), AXLE_Y + AXLE_R*sin(a1), z0)
        p10 = (x0 + AXLE_R*cos(a0), AXLE_Y + AXLE_R*sin(a0), z1)
        p11 = (x0 + AXLE_R*cos(a1), AXLE_Y + AXLE_R*sin(a1), z1)
        n0 = (cos(a0), sin(a0), 0f0); n1 = (cos(a1), sin(a1), 0f0)
        uv00 = (Float32(k/segs), 0f0); uv01 = (Float32((k+1)/segs), 0f0)
        uv10 = (Float32(k/segs), 1f0); uv11 = (Float32((k+1)/segs), 1f0)
        for (P,N,UV) in ((p00,n0,uv00),(p10,n0,uv10),(p11,n1,uv11),
                         (p00,n0,uv00),(p11,n1,uv11),(p01,n1,uv01))
            append!(v, Float32[P[1],P[2],P[3], N[1],N[2],N[3], UV[1],UV[2], 1f0,1f0,1f0])
        end
    end
    Render.TrackPart(v, "axlelot", (1f0,1f0,1f0))
end
const AXLEP = get(ENV,"JM_AXLES","1") != "0" ? [_axle_part(1f0), _axle_part(-1f0)] : Render.TrackPart[]
const PIPE_LIFT = parse(Float32, get(ENV, "JM_PIPE_LIFT", "0.18"))
# E106-S8 (PO: "still need to make those exhaust pipes symmetrical"): pipe3 carries a 5-tri
# bracket authored on the RIGHT side only (its own connected solid); min_component=6 drops exactly
# it. The remaining left/right header difference (102 vs 96 tris) is the authored art itself.
# E106-S26 (PO: "tailpipes better (but not symetrical)"). Measured: after S8 dropped the right-only
# bracket the two sides carry the same tri count (139 vs 140) and the same lateral span, but the
# AUTHORED geometry still differs by 2-3 cm -- left max height 0.067 vs right 0.040, mean fwd -0.669
# vs -0.686 -- and that is exactly the ~26 px height offset visible between the two megaphones in a
# chase capture. So it is not a placement bug to hunt: the art itself is slightly asymmetric.
# Make it symmetric by construction: keep ONE side and mirror it to the other, reversing the winding
# so the mirrored faces still point outward. JM_PIPE_MIRROR=0 keeps GPL's authored asymmetry.
function _mirror_pipes(parts)
    out = Render.TrackPart[]
    for p in parts
        v = p.verts; n = length(v) ÷ 33
        keep = Float32[]
        for t in 0:n-1
            b = t*33
            cz = (v[b+3] + v[b+14] + v[b+25]) / 3
            cz > 0 || continue                     # keep the LEFT side only
            append!(keep, v[b+1:b+33])             # the original
            # the mirror: negate lateral (z) on position and normal, and reverse the winding
            for k in (2,1,0)
                o = b + k*11
                append!(keep, Float32[v[o+1], v[o+2], -v[o+3],
                                      v[o+4], v[o+5], -v[o+6],
                                      v[o+7], v[o+8], v[o+9], v[o+10], v[o+11]])
            end
        end
        isempty(keep) || push!(out, Render.TrackPart(keep, p.tex, p.col))
    end
    out
end
const _PIPES_RAW = get(ENV, "JM_PIPES", "1") != "0" ?
    Render.extract_gpl_car(LOT3DO; only=("pipe3",), maxlat=0.9f0,
                           min_component=6, min_component_tex=("pipe3",)) : Render.TrackPart[]
const PIPEP  = get(ENV, "JM_PIPE_MIRROR", "1") != "0" ? _mirror_pipes(_PIPES_RAW) : _PIPES_RAW
const ARMP   = Render.extract_gpl_car(LOT3DO; only=("lotarms",), maxlat=0.95f0)  # forearms/upper arms — static (their wheel-side ends are what the eye sees)
# The dash panel's normal faces DOWN, so from the driver's eye (above) we see its back → the dials read
# upside-down.  Mirror the gauge in height about its own centre so the dial face turns up toward the eye.
const GCY = (b = Render.parts_bbox(GAUGEP); Float32((b.ymin + b.ymax)/2))
# GPL puts the gauge binnacle UP, just above the wheel hub (gauges read above the badge); dash7a is
# modelled LOW, so lift it (JM_GAUGE_Y) and nudge it back toward the eye (JM_GAUGE_X) onto the cowl.
# E74-S7 SHIPPED: 0.16 -> 0.28. At 0.16 the cluster sat at wheel-rim height and was occluded by the
# spokes and clipped at the frame edge, which is what the PO saw as "dials like a Salvador Dali
# painting". Verified at Spa s=500/8000/12500 and Zandvoort s=1000: at 0.28 (with JM_GAUGE_Z=0.10)
# the cluster sits ABOVE the rim with dial faces and markings legible, matching gold's arrangement
# of a tachometer above the hub. JM_GAUGE_Y=0.16 JM_GAUGE_Z=0.0 restores the old placement.
# 🔴 E106 (PO 2026-09-01): "in cockpit view the salvador dali dashboard is above the steering
# wheel, blocking the driver's view of the road". Measured at three heights on Watkins, same spot:
#   0.28 (E74-S7's value) -- the cluster is a BILLBOARD filling the windscreen; the road is gone.
#   0.20 -- the cluster sits in a dark binnacle behind the wheel, dials visible, road visible;
#           top edge grazes the horizon. Closest of the three to gold's arrangement (the gold
#           cockpit shows the binnacle BELOW the horizon with the road clearly over it).
#   0.14 -- road fully visible but the dials vanish behind the wheel, which is the occlusion
#           E74-S7 was fixing when it over-corrected to 0.28.
# E74-S7 verified 0.28 against "dials legible" and never against "road visible" -- the two halves
# of the same sightline, and fixing one broke the other. 0.20 holds both.
const GAUGE_DY = parse(Float32, get(ENV,"JM_GAUGE_Y","0.20"))
const GAUGE_DX = parse(Float32, get(ENV,"JM_GAUGE_X","-0.04"))
# E74-S4: a SCALE knob for the gauge cluster. E74-S3 refuted brightness as the cause of the PO's
# "Salvador Dali dials" and found the cluster is drawn far smaller than gold's — gold puts a large
# dominant tachometer above the wheel hub, ours sits small and far back — so the dial-face texture is
# minified into a mip-blurred smear. This tests that directly: if growing the cluster makes the
# numerals resolve, the defect is positional/scale, not texture or lighting. JM_GAUGE_S (default 1.0
# = unchanged, so the shipped look is untouched until the sweep says what is right).
const GAUGE_S = parse(Float32, get(ENV,"JM_GAUGE_S","1.0"))
# E74-S5: there is no LATERAL knob. JM_GAUGE_X is longitudinal ("nudge it back toward the eye" per
# its own comment) and JM_GAUGE_Y is height; the third component has always been a hard 0. But
# E74-S4's sweep showed the cluster sitting up-and-LEFT of where gold puts it — gold centres the
# tachometer directly above the wheel hub — so the axis that needs testing is the one nobody could
# adjust. JM_GAUGE_Z (default 0.0 = shipped behaviour unchanged).
const GAUGE_DZ = parse(Float32, get(ENV,"JM_GAUGE_Z","0.10"))   # E74-S7 SHIPPED (was 0.0 — see GAUGE_DY)
const GAUGEFLIP = Render.translate(Float32[GAUGE_DX,GCY+GAUGE_DY,GAUGE_DZ]) * Render.scalexyz(GAUGE_S,-GAUGE_S,GAUGE_S) * Render.translate(Float32[0,-GCY,0])
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
# E106-S10 (PO, Zandvoort video: "make visor more transluscent"). The opaque 1.0 came from an
# earlier PO call that the tan scuttle must not read as glassy; 0.55 keeps it clearly a scuttle
# while letting the road show through the screen area as the PO now wants.
const WIND_ALPHA   = parse(Float32, get(ENV,"JM_WIND_ALPHA","0.55"))      # PO: windlot = the tan LEATHER SCUTTLE (the defining GPL cockpit element). The earlier OFF default came from drawing it TRANSLUCENT (read as an angled "plywood board"); drawn OPAQUE (1.0) it is the GPL scuttle sweeping up to the cowl on both sides. JM_WIND_ALPHA<1 makes it glassy again.
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
# E106-S12: probe the PHYSICS ground height on a world-coordinate grid. JM_HATPROBE="x,z"
# prints the height the car's ground query returns around that point -- the instrument for
# "the car levitated on a building": scenery baked into the terrain mesh reads as drivable
# ground, and shows up here as a plateau metres above the surrounding road.
if get(ENV,"JM_HATPROBE","") != ""
    # a single "x,z" prints a grid; a ";"-separated LIST prints the height along a path (the
    # instrument for "where did the ground go" -- a gap is a hole the car can drop through).
    spec = get(ENV,"JM_HATPROBE","")
    if occursin(";", spec)
        println("== JM_HATPROBE path -- physics ground height along the car's track ==")
        for tok in split(spec, ";")
            isempty(strip(tok)) && continue
            local pr = split(tok, ",")                       # `local`: pr/px/pz shadow globals
            local px = parse(Float64, strip(pr[1]))
            local pz = parse(Float64, strip(pr[2]))
            h = JuliaMotor.hat3d(TERRAIN, px, pz; ref=Inf)
            println("   (", lpad(round(px,digits=1),9), ",", lpad(round(pz,digits=1),9), ")  ",
                    h[3] ? string("ground ", round(h[1], digits=2)) : "NO SURFACE  <-- HOLE")
        end
    else
        pr = split(spec, ",")
        px = parse(Float64, strip(pr[1])); pz = parse(Float64, strip(pr[2]))
        println("== JM_HATPROBE around (", px, ", ", pz, ") -- physics ground height, 4 m grid ==")
        for dz in -12:4:12
            row = String[]
            for dx in -12:4:12
                h = JuliaMotor.hat3d(TERRAIN, px+dx, pz+dz; ref=Inf)
                push!(row, h[3] ? string(round(h[1], digits=2)) : "  --  ")
            end
            println("   dz=", lpad(dz,4), "  ", join([lpad(r,8) for r in row]))
        end
    end
    flush(stdout)
end


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
# E70-S7: the restored billboards render vegetation CYAN (3.42% of frame vs 0.01% with them off).
# Several Ring bush textures are blue-green at source (hgbush 20,69,56; bush 39,80,70; kwbush6
# 30,67,62 — blue well above red), and drawing them at bright=1.55 pushes them past cyan.
# E83-S3 (2026-08-30): billboards are drawn UNLIT by default. The tree sprites decode to gold's colour
# (s_tree04 (57,80,45) vs gold forest (60,78,40)) yet rendered ~2x brighter ((137,154,86) at s=600)
# because the shader lit them as geometry -- ambient + 1.15x sun x BB_BRIGHT 1.55. GPL draws its
# sprites as pre-lit art. JM_BILLBOARD_LIT=1 restores the lit path (and BB_BRIGHT/BB_AMB with it).
const BB_LIT    = get(ENV,"JM_BILLBOARD_LIT","0") != "0"
const BB_BRIGHT = parse(Float32, get(ENV,"JM_BB_BRIGHT","1.55"))
const BB_AMB    = parse(Float32, get(ENV,"JM_BB_AMB","0.85"))
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
# E104-S4 (PO: "every car FLOATS 20-40 cm above the road"). The probes so far measured the AI LINE
# against the terrain (E104-S2/S3: exactly 0.0) and wheel RADII against their placement (within
# 4 mm) -- both clean, which sent the item back to "my own eye may be wrong".
# Neither measured the thing the eye actually sees. Both the player and every AI car are drawn as
#     <car origin> * translate([wx, r, wz])
# (`wheelmat` / `aiWheel`), so a wheel's contact patch lands on the road ONLY IF THE CAR ORIGIN'S
# HEIGHT IS THE GROUND HEIGHT. If a car's y is its chassis, hub or CoG height instead, every wheel
# on it is drawn exactly that far up -- player and AI alike, which is what "every car" means.
# That quantity had never been printed. JM_WHEELGAP=<n> prints it every n frames, for the player
# and for each AI car, in the RENDER frame the eye is looking at.
const WHEELGAP = parse(Int, get(ENV, "JM_WHEELGAP", "0"))
const FPSDIAG = parse(Int, get(ENV, "JM_FPSDIAG", "0"))   # E80: frame-time report, per view
const FRAMEPROF = parse(Int, get(ENV, "JM_FRAMEPROF", "0"))  # E80: per-PHASE frame profiler
const PROF_WORLD = Ref(0.0); const PROF_HUD = Ref(0.0); const PROF_N = Ref(0); const PROF_TOT = Ref(0.0)
# ---- E95 (PO 2026-08-29): "This is not a game of bumper cars. You hit something hard, your race
# is over." A hard impact WRECKS the car: the engine is PERMANENTLY disconnected from the
# drivetrain, the motion damps out, and the wheels nearest the impact come off and roll away.
#
# Threshold is on the CONTACT FORCE PEAK that solid_contact already returns, not on speed: what
# wrecks a car is the impulse it takes, and a slow scrape into a hedge must never trigger it.
const BND_PK = Ref(0.0)   # E95b: last frame's world-edge contact peak (N)
const BND_NX = Ref(0.0); const BND_NZ = Ref(0.0)   # E95f: world-frame wall normal, pointing INTO the world
const WHEEL_REST   = parse(Float64, get(ENV, "JM_WHEEL_REST", "0.35"))   # E95f: wheel/wall restitution (<1 = inelastic)
const WRECK_KMH    = parse(Float64, get(ENV, "JM_WRECK_KMH", "50.0"))    # E95c: any HARD contact above this totals the car
const WRECK_MS     = WRECK_KMH/3.6
# E99: closing speed along the contact normal above which a hit ends the race. A graze is oblique,
# so its normal component stays small however fast the car is travelling; a shunt is nearly head-on.
# CALIBRATED AGAINST ENERGY, not chosen by feel. Measured at 108 km/h into a 5 m obstacle, varying
# only the lateral offset, energy retained THROUGH the contact against closing speed:
#
#     offset 4.9 m   pen 0.03 m   closing  5.4 m/s   84% kept   <- unmistakably a graze
#     offset 4.6 m   pen 0.12 m   closing 10.7 m/s   72% kept
#     ------------------------------------------------ 12.0 m/s threshold
#     offset 4.2 m   pen 0.34 m   closing 13.8 m/s   59% kept
#     offset 3.0 m   pen 0.64 m   closing 22.2 m/s   24% kept
#     head-on        pen 1.16 m   closing 28.4 m/s    0% kept   <- unmistakably a shunt
#
# The line is drawn where the car stops keeping most of its energy: above it a contact takes more
# than 40% and the race is over; below it you are scrubbed and still driving, which is exactly the
# PO's rule ("a graze at speed should scrub you but not end your race", 2026-08-30).
# JM_WRECK_CLOSE re-grades it without a rebuild.
const WRECK_CLOSE  = parse(Float64, get(ENV, "JM_WRECK_CLOSE", "12.0"))
const WRECKED      = Ref(false)          # latched: a wreck is permanent, that is the point
const WRECK_FROZEN = Ref(false)          # E95g: the wreck has come to rest and is pinned there
const WRECK_PX     = Ref(0.0); const WRECK_PZ = Ref(0.0); const WRECK_PT = Ref(0.0)
const WRECK_DAMP   = parse(Float64, get(ENV, "JM_WRECK_DAMP", "6.0"))   # E95e: 1/s; raised from 2.2 -- a totalled car should stop in a car length or two, not coast on
# Detached wheels: each is (x, y, z, vx, vy, vz, spin, spinrate, name). World frame, metres.
# E95: 8 Float64s + the wheel's model NAME. Declared NTuple{9,Float64} at first, which threw
# `Cannot convert String to Float64` on the FIRST detachment and killed the sim mid-wreck --
# the wreck itself had fired correctly at 177 km/h. A container typed against what it holds.
const LooseWheel = Tuple{Float64,Float64,Float64,Float64,Float64,Float64,Float64,Float64,String}
const LOOSE_WHEELS = Vector{LooseWheel}()
is_loose(nm) = any(w -> w[9] == nm, LOOSE_WHEELS)   # E95: a detached corner is not drawn on the car
const WHEEL_NAMES  = ("lotwlf","lotwrf","lotwlr","lotwrr")

"""E95: latch the wreck — engine PERMANENTLY disconnected. Wheels are NOT chosen here.
PO 2026-08-29: "detach the wheel that hit the barrier - or both wheels, if two wheels hit before
the car comes to a stop". So which wheels leave is decided per-wheel, per-frame, by whether that
CORNER actually contacts something (see detach_hit_wheels!) — not by picking corners up front."""
function wreck!(v)
    WRECKED[] && return
    WRECKED[] = true
    println("  [WRECK] hard impact at ", round(v*3.6, digits=0), " km/h — engine disconnected, race over")
    flush(stdout)
end

"""E95: detach any still-attached wheel whose HUB is inside a solid. Runs every frame while the car
is still moving, so a second corner that reaches the barrier later comes off too — which is what
happens at higher impact speed, and is exactly what the PO described. Deliberately per-corner: at a
glancing hit only the corner that touched leaves the car."""
function detach_hit_wheels!(x, z, θ, v; fence_nx = 0.0, fence_nz = 0.0, fence = false)
    cθ, sθ = cos(θ), sin(θ)
    # E95b: a WORLD-EDGE hit has no SOLIDS near it, so the SOLIDS scan below finds nothing and the
    # car would be wrecked with all four wheels on. The fence is a wall like any other: take the
    # corners that are LEADING into it -- one on a glancing hit, two when the car is square on,
    # which is the PO's "both wheels, if two wheels hit before the car comes to a stop".
    if fence
        @inbounds for (bx, by, front, r, nm) in WHEELS
            is_loose(nm) && continue
            wx = x + bx*cθ - by*sθ
            wz = z + bx*sθ + by*cθ
            # how far this corner leads the CG along the outward direction (-fence normal)
            lead = (wx - x)*(-fence_nx) + (wz - z)*(-fence_nz)
            lead <= 0.35 && continue
            # E95f (PO): "the front wheels should bounce back from the wall (though the wheel/wall
            # collision shouldn't be entirely elastic)". So this is a proper restitution, not a
            # fixed kick: split the wheel's velocity into NORMAL and TANGENTIAL parts against the
            # wall, reverse the normal part scaled by e < 1, and scrub the tangential part. e = 1
            # would be a perfect bounce and e = 0 would drop it dead at the wall; JM_WHEEL_REST
            # sets it, defaulting to 0.35 -- a tyre is springy but lossy.
            vwx = v*cθ; vwz = v*sθ                                  # wheel velocity ≈ the car's at separation
            vn  = vwx*fence_nx + vwz*fence_nz                        # component along the INWARD normal
            tgx = vwx - vn*fence_nx; tgz = vwz - vn*fence_nz         # tangential (along the wall)
            outn = abs(vn)*WHEEL_REST                                # reversed, lossy
            push!(LOOSE_WHEELS, (wx, 0.33, wz,
                                 tgx*0.7 + fence_nx*outn,
                                 2.5 + 0.10*abs(v),                  # a little vertical hop off the rim
                                 tgz*0.7 + fence_nz*outn,
                                 0.0, v/max(r, 0.1), nm))
            println("  [WRECK] ", nm, " torn off on the wall at ", round(abs(v)*3.6, digits=0), " km/h")
            flush(stdout)
        end
    end
    @inbounds for (i, (bx, by, front, r, nm)) in enumerate(WHEELS)
        is_loose(nm) && continue
        wx = x + bx*cθ - by*sθ
        wz = z + bx*sθ + by*cθ
        for (ox, oz, orad, kind) in SOLIDS
            kind === :soft && continue                       # a hedge takes no wheels off
            dx = wx - ox; dz = wz - oz; d = hypot(dx, dz)
            d >= orad + 0.35 && continue                      # 0.35 m ~ wheel radius + rim
            nx = d > 1e-6 ? dx/d : 1.0; nz = d > 1e-6 ? dz/d : 0.0
            push!(LOOSE_WHEELS, (wx, 0.33, wz,
                                 v*cθ + nx*3.5,               # keeps the car's momentum plus a kick off the wall
                                 3.0 + 0.15*abs(v),           # hops off the hub, harder the faster the hit
                                 v*sθ + nz*3.5,
                                 0.0, v/max(r, 0.1), nm))
            println("  [WRECK] ", nm, " torn off at ", round(abs(v)*3.6, digits=0), " km/h")
            flush(stdout)
            break
        end
    end
end

"""E95: ballistic + bounce integration for the torn-off wheels. `gz` gives ground height."""
function step_loose_wheels!(dt, gz)
    isempty(LOOSE_WHEELS) && return
    @inbounds for i in eachindex(LOOSE_WHEELS)
        (x,y,z,vx,vy,vz,sp,sr,nm) = LOOSE_WHEELS[i]
        vy -= 9.81*dt
        x += vx*dt; y += vy*dt; z += vz*dt
        g = gz(x, z) + 0.33                       # wheel radius above the surface
        if y <= g
            y = g
            vy = -vy*0.35                          # inelastic bounce: a tyre does not superball either
            vx *= 0.86; vz *= 0.86                 # rolling/scrub loss on each contact
            abs(vy) < 0.4 && (vy = 0.0)
        end
        sp += sr*dt
        sr *= (1.0 - 0.25*dt)                      # spin bleeds off
        LOOSE_WHEELS[i] = (x,y,z,vx,vy,vz,sp,sr,nm)
    end
end
const CLU_LAST = Ref(-1.0)   # E93: last reported clutch value (JM_TRACE_CLUTCH)
# E98 (PO 2026-08-30): "if the user stalls out in manual mode, switch to auto mode immediately".
# There was no stall model and no definition of "stalled", so it was MEASURED before being detected.
# With the clutch ENGAGED and no throttle, the engine dies and stays dead:
#     at rest in 1st      rpm 1983 -> 0     (car stationary)
#     at rest in 3rd      rpm 1965 -> 0
#     lugging 5th, 2 m/s  rpm 1958 -> 0     (and the car is dragged to a stop)
# while a legitimate standing start dips to 466 rpm and recovers to 2268. So a floor of 300 rpm
# separates a dead engine from a hard launch with margin, and the SUSTAIN requirement stops a
# transient dip from throwing the driver into AUTO mid-launch.
const CLU_NOW    = Ref(0.0)                                                  # live clutch, every frame
const STALL_RPM  = parse(Float64, get(ENV, "JM_STALL_RPM",  "300.0"))        # below this the engine is dead
const STALL_SECS = parse(Float64, get(ENV, "JM_STALL_SECS", "0.5"))          # ...for this long
const STALL_T    = Ref(0.0)
const FPS_T0 = Ref(0.0); const FPS_ACC = Ref(0.0); const FPS_N = Ref(0)
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
# E75-S10: the grade's saturation boost is global, so it is a candidate for the car's paint reading
# 43% more saturated than gold's while its hue is correct. JM_SAT overrides it for A/B.
const GRADE0 = SKIDPAD ? GRADE_SKIDPAD :
              haskey(ENV, "JM_GRADE") ? get(GRADE_TAB, uppercase(ENV["JM_GRADE"]), GRADE_OVERCAST) :
              get(GRADE_BYTRACK, TRACKSEL, GRADE_OVERCAST)
const ENG = EngineAudio.build_lotus(gamedata = GD)   # GPL Ford DFV V8, RPM-pitched; START is deferred to just before the game loop (below)
# E72-S13: per-track exposure, measured on asphalt in COCKPIT view on both sides (E72-S12).
#   gold/native asphalt luminance: Spa 120.2/149.0 → 0.81   Watkins 120.0/143.8 → 0.83
#                                  Monza 117.5/101.3 → 1.16  Zandvoort 128.5/131.3 → 0.98
#                                  Nurburgring 104.0/105.7 → 0.98
# JM_EXPOSURE overrides for A/B; 1.0 disables.
if !haskey(ENV,"JM_EXPOSURE")
    # ⚠️ E72-S13 REVERTED to 1.0 (no correction). The constants above were derived from an asphalt
    # mask with ABSOLUTE thresholds (sat<22, 60<lum<200), which is NOT exposure-invariant: brightening
    # lifts dark non-road pixels above the lum>60 floor and admits them, so the metric moves for
    # reasons unrelated to exposure. Measured instead with a threshold-free fixed image region, native
    # was already within -7%..0% of gold and the "correction" made Spa and Watkins ~15% WORSE.
    # The uniform stays (JM_EXPOSURE) so a future, sounder measurement can drive it.
    Render.EXPOSURE[] = 1.0f0
end
const GRADE = haskey(ENV,"JM_SAT") ?
    ColourGrade(GRADE0.zenith, GRADE0.horizon, GRADE0.cloud, GRADE0.suncol, GRADE0.ambsky,
                parse(Float32, ENV["JM_SAT"]), GRADE0.ringtint) : GRADE0
tstamp("texture load begins"); print("loading textures… "); flush(stdout)
const TEXIDX = Render.gpl_texture_index(ZD)
tstamp("  texture INDEX built")   # E80: split the "texture load" phase -- at Spa it runs >13 min and
                                  # a 900 s run never reaches the frame loop, so which HALF matters.
const TRACK_BRIGHT = parse(Float32, get(ENV,"JM_TRACK_BRIGHT","0.72"))
const TRACK_AMB    = parse(Float32, get(ENV,"JM_TRACK_AMB","0.34"))
trackItems = Render.build_gpl(TRACK, TEXIDX)
tstamp("  build_gpl done (GL uploads)")   # E80
# E57: build_gpl is 1:1 with TRACK, but Items drop the texture NAME (GPL parts all carry the same
# fallback grey col) — so classify each track surface HERE from its TrackPart.tex name for the per-
# surface render grade below.  GPL Monza names: road = trrow*/asp* (the over-bright asphalt MIP),
# barriers = armco*/yarmc*/brdg(arm|fen)* (carbonized under the overcast).  Other tracks → :other.
monza_surf(t) = (startswith(t,"trrow") || startswith(t,"asp")) ? :road :
                (startswith(t,"armco") || startswith(t,"yarmc") || startswith(t,"brdgarm") || startswith(t,"brdgfen")) ? :dark :
                occursin(r"^s\d\d", t) ? :bank :    # the sopraelevata banking segments (s07b2, s12l1, …) — over-bright white slabs
                :other
tstamp("  [E80] track categories / crowd tint begins")
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
tstamp("  [E80] horizon ring begins")
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
    # E76-S8: THE RING'S MISSING BILLBOARDS.  The Ring does not use the GPL object pipeline below —
    # it loads scenery through its own gpl_scenery(), which had no billboard path at all, so every
    # placement whose .3do carries no geometry was silently dropped.  E76-S5 instrumented the drop
    # and S8 read the answer: all 50 distinct failing objects PARSE FINE with 0 triangles — bush,
    # strauch*/stree* (shrubs), deadtree, and flagger (marshals).  They are billboard STUBS, drawn
    # by GPL as camera-facing sprites from a texture.  That is 1865 placements, and it is why the
    # Ring loads "184 groups" while Spa gets 1679 objects + 5132 billboards at a FIFTH the length.
    # Build them here with the same construction the object pipeline uses.  JM_RING_BB=0 reverts.
    if !isempty(RINGSPRITES) && get(ENV,"JM_RING_BB","1") != "0"
        RING_BB_HALFW = parse(Float64, get(ENV,"JM_RING_BB_HALFW","5.0"))
        BB_MARKER_TEX = Set(["collision", "fake", "shadow", "lshad"])   # hull / placeholder markers, never artwork
        RING_BB_WIDE  = parse(Float32, get(ENV,"JM_WIDE_PANEL","30"))   # same constant the object pipeline uses
        local nbb=0; local notex=0; local onrd=0; local nwide=0
        bbcache = Dict{String,Any}()
        for sp in RINGSPRITES
            # The on-road drop uses a RING-SPECIFIC half-width, measured rather than inherited.
            # ROAD_HALFW is 9.0 m — a deliberately generous corridor tuned so the centreline-
            # projection wobble through Watkins' esses doesn't read as "on grass". Applied here it
            # dropped 847 of 1825 stubs. The lateral distribution (JM_RING_BB_DIAG) says why that is
            # wrong: only 3 stubs sit within 3 m of the centreline and 6 within 4 m — the authors
            # planted nothing on the racing surface — while the foliage band starts at p5 = 5.5 m and
            # is dense by 7 m. A 9 m corridor is therefore not deleting objects "on the road", it is
            # deleting the roadside treeline of a forest circuit ~8-9 m WIDE. 5.0 m drops 30 (1.6%),
            # the ones genuinely over the asphalt, and keeps the verge. JM_RING_BB_HALFW overrides.
            hr = JuliaMotor.hat(TRKSURF, Float64(sp.x), Float64(sp.y))
            if hr.found && abs(hr.lateral) < RING_BB_HALFW; onrd += 1; continue; end
            # E76-S8c: take the first texture that BUILDS, but never a non-visual marker. The tall
            # stub families list their textures as e.g. "collision | stree8": `collision` is the
            # collision-hull marker, and it resolves in the index, so a naive first-match binds every
            # 14-24 m tree to it — which is what rendered the restored sprites as giants. `FAKE` is
            # the same idea (an invisible placeholder); a stub with nothing but markers is dropped.
            bb = get!(bbcache, lowercase(sp.name)) do
                r = nothing
                for tn in sp.texs
                    lowercase(strip(tn)) in BB_MARKER_TEX && continue
                    r = Render.build_billboard(tn, TEXIDX)
                    r !== nothing && break
                end
                r
            end
            if bb === nothing; notex += 1; continue; end
            item, tw, th = bb
            w = sp.w > 0f0 ? sp.w : sp.h*tw/max(th,1f0)
            # E76-S8d: a camera-facing quad is only meaningful for a NARROW sprite. `ogrnd2` is one
            # placement 209.3 m wide and 25.1 m tall on the Grndpp1 ("ground people") sheet — swung
            # to face the eye it becomes the giant crowd WALL towering over the fence, which is what
            # the first capture showed. This is the same failure the object pipeline already names:
            # panels wider than JM_WIDE_PANEL are never camera-faced, and on every track except
            # Monza/Watkins its default is to drop them and let the horizon ring carry the backdrop.
            # Apply that rule here rather than invent a second one. (The Ring's REAL crowds are
            # people*/pplrow01, which carry geometry and come through the mesh path — E76-S7.)
            if w > RING_BB_WIDE
                # Not a sprite — but not rubbish either. ogrnd2 IS the start/finish crowd terrace
                # (Grndpp1 = "ground people"), and dropping it leaves the PO's complaint unfixed:
                # with it gone the billboards change 0.48% of the frame against a 0.24% null at S/F,
                # i.e. nothing. Draw it the way the object pipeline draws wide strips — a STATIC
                # panel at its authored yaw, not swung to face the eye. Same construction, same
                # graze-fade, no wall. JM_RING_WIDE_DROP=1 reverts to dropping them.
                if get(ENV,"JM_RING_WIDE_DROP","1") != "0"; nwide += 1; continue; end   # DEFAULT: drop — the static panel floats above the skyline (E76-S8e)
                push!(STATICTREES, (item, (sp.x, sp.z, -sp.y), Float32(w), Float32(sp.h),
                                    Float32(-(sp.yaw + sp.aax))))
                nwide += 1
                continue
            end
            push!(BILLBOARDS, (item, (sp.x, sp.z, -sp.y), Float32(w), Float32(sp.h)))
            nbb += 1
        end
        # E81 (PO 2026-08-27/28): "lots of odd buildings and parts of buildings" at the Ring, and
        # "check the floating or misplaced billboards and buildings at nurburgring, of which there
        # are many". The Ring's sprites are placed at their AUTHORED height (sp.z) and never
        # grounded against the terrain, so any placement whose height disagrees with the ground
        # floats above it or sinks into it. Measure the disagreement for every sprite.
        # JM_FLOATDIAG=1 (add JM_FLOATDIAG_N=<n> to list more than the worst 20).
        if get(ENV,"JM_FLOATDIAG","") != ""
            gaps = Tuple{Float64,String,Float64,Float64}[]
            for sp in RINGSPRITES
                # ⚠️ ref = the sprite's own base + 2 m, NOT Inf. hat3d returns the topmost surface
                # at or below `ref`, so ref=Inf measures to whatever is HIGHEST over that spot --
                # a tree canopy, a building roof -- rather than to the ground the sprite stands on.
                # The first run did exactly that and reported gaps of +/-290 m, which is a measure
                # of the scenery above the sprite, not of the sprite's placement. Same `ref`
                # subtlety that decided the bridge-underpass fix (E77-F).
                # +sp.y, not -sp.y. build_hat maps GPL (x,y,z) -> (x, z_up, y), so the HAT's second
                # horizontal axis is +GPL y; the RENDERER negates it (render z = -gy). Querying the
                # terrain in the render frame samples a mirrored point on a track that spans 300 m
                # of elevation, which is what produced a "median gap of 137 m". Both frames are
                # correct; the probe was using the wrong one.
                gh = JuliaMotor.hat3d(TERRAIN, Float64(sp.x), Float64(sp.y); ref=Float64(sp.z)+2.0)
                gh[3] || continue
                push!(gaps, (Float64(sp.z) - gh[1], String(sp.name), Float64(sp.z), gh[1]))
            end
            # ⚠️ POSITIVE CONTROL for the coordinate mapping, before any gap is believed. The first
            # run of this reported 411 of 413 sprites off the ground by up to +/-290 m, with bases
            # AND grounds both clustering at ~330 and ~620 -- a swap, not a placement defect. Print
            # the raw field ranges: on the Ring the terrain is ~560-680 m, so whichever field spans
            # that IS the height, and the other two are the horizontal pair.
            let xs=[Float64(sp.x) for sp in RINGSPRITES], ys=[Float64(sp.y) for sp in RINGSPRITES],
                zs=[Float64(sp.z) for sp in RINGSPRITES]
                println("   [ctrl] sp.x ", round(minimum(xs)), "..", round(maximum(xs)),
                        "   sp.y ", round(minimum(ys)), "..", round(maximum(ys)),
                        "   sp.z ", round(minimum(zs)), "..", round(maximum(zs)))
                # Which horizontal mapping is right? Sample with BOTH signs of the z-coordinate and
                # report the median |gap| for each. The correct mapping puts sprites ON the ground,
                # so it is the one with the small median; a mirrored sample sends them to an
                # unrelated part of a track that spans 300 m of elevation, which is what a 290 m
                # gap actually measures.
                for (lbl, zf) in (("-sp.y", -1.0), ("+sp.y", +1.0))
                    gs = Float64[]
                    for sp in RINGSPRITES
                        g = JuliaMotor.hat3d(TERRAIN, Float64(sp.x), zf*Float64(sp.y); ref=Float64(sp.z)+2.0)
                        g[3] && push!(gs, abs(Float64(sp.z) - g[1]))
                    end
                    isempty(gs) && continue
                    sort!(gs)
                    println("   [ctrl] z=", lbl, ": ", length(gs), " hits, median |gap| ",
                            round(gs[cld(length(gs),2)],digits=1), " m, 90th ",
                            round(gs[cld(9*length(gs),10)],digits=1), " m")
                end
            end
            if !isempty(gaps)
                sort!(gaps, by=g->-abs(g[1]))
                nfloat = count(g -> g[1] >  0.5, gaps)
                nsunk  = count(g -> g[1] < -0.5, gaps)
                println("== JM_FLOATDIAG: ", length(gaps), " Ring sprites grounded against the terrain ==")
                println("   floating >0.5 m above: ", nfloat, "   sunk >0.5 m below: ", nsunk,
                        "   within +/-0.5 m: ", length(gaps)-nfloat-nsunk)
                nlist = parse(Int, get(ENV,"JM_FLOATDIAG_N","20"))
                for g in gaps[1:min(end,nlist)]
                    println("   ", rpad(g[2],14), " base=", rpad(round(g[3],digits=1),9),
                            " ground=", rpad(round(g[4],digits=1),9),
                            " gap=", g[1] > 0 ? "+" : "", round(g[1],digits=1), " m")
                end
            end
            flush(stdout)
        end
        if get(ENV,"JM_RING_BB_DIAG","") != ""
            # Is a 9 m half-corridor right for a forest track ~8-9 m WIDE? Print the lateral
            # distribution of the stubs so the threshold is measured, not assumed.
            lats = Float64[]
            for sp in RINGSPRITES
                hr = JuliaMotor.hat(TRKSURF, Float64(sp.x), Float64(sp.y))
                hr.found && push!(lats, abs(hr.lateral))
            end
            sort!(lats)
            println("  == JM_RING_BB_DIAG: |lateral| of the ", length(lats), " on-ribbon stubs ==")
            for q in (0.05,0.1,0.25,0.5,0.75,0.9)
                println("     p", rpad(round(Int,100q),3), " = ", round(lats[max(1,ceil(Int,q*length(lats)))],digits=1), " m")
            end
            for edge in (3.0,4.0,5.0,6.0,7.0,9.0,12.0)
                println("     |lat| < ", rpad(edge,5), " → ", count(<(edge), lats), " dropped")
            end
            # E76-S8b: the restored sprites render as GIANTS floating at fence height. Height comes
            # from billboard_stub (mesh z-extent, else a 2.5 m human default) times the placement
            # scale; the base is the authored z. Report both against the ground the renderer uses,
            # so "too big" and "too high" are separated instead of guessed at.
            hs = Float64[]; dz = Float64[]
            for sp in RINGSPRITES
                push!(hs, Float64(sp.h))
                gh = JuliaMotor.hat3d(TERRAIN, Float64(sp.x), Float64(sp.y); ref=Inf)   # groundz is defined later
                gh[3] && push!(dz, Float64(sp.z) - Float64(gh[1]))
            end
            sort!(hs); sort!(dz)
            q(v,f) = v[max(1,ceil(Int,f*length(v)))]
            println("     sprite HEIGHT  m : p10=", round(q(hs,0.1),digits=1), " p50=", round(q(hs,0.5),digits=1),
                    " p90=", round(q(hs,0.9),digits=1), " max=", round(hs[end],digits=1))
            println("     base ABOVE ground: p10=", round(q(dz,0.1),digits=1), " p50=", round(q(dz,0.5),digits=1),
                    " p90=", round(q(dz,0.9),digits=1), " max=", round(dz[end],digits=1), "   (n=", length(dz), ")")
            # per-name, for the biggest families
            cnt = Dict{String,Int}(); hmax = Dict{String,Float64}()
            for sp in RINGSPRITES
                cnt[sp.name] = get(cnt,sp.name,0)+1
                hmax[sp.name] = max(get(hmax,sp.name,0.0), Float64(sp.h))
            end
            tex1 = Dict{String,String}(); wmax = Dict{String,Float64}()
            for sp in RINGSPRITES
                tex1[sp.name] = isempty(sp.texs) ? "(none)" : first(sp.texs)
                wmax[sp.name] = max(get(wmax,sp.name,0.0), Float64(sp.w))
            end
            println("     -- most-placed stub families (name, count, height, width, 1st texture) --")
            for (nm,c) in sort(collect(cnt), by=x->-x[2])[1:min(end,12)]
                println("        ", rpad(nm,14), rpad(c,6), rpad(string(round(hmax[nm],digits=1),"m"),8),
                        rpad(string(round(wmax[nm],digits=1),"m"),8), tex1[nm])
            end
            seenn = Set{String}()
            println("     -- ALL texture strings for the tall stubs --")
            for sp in RINGSPRITES
                (sp.h > 10 && !(sp.name in seenn)) || continue
                push!(seenn, sp.name)
                println("        ", rpad(sp.name,12), " → ", join(sp.texs, " | "))
                length(seenn) >= 8 && break
            end
            println("     -- families whose texture looks like PEOPLE/CROWD --")
            shown = Set{String}()
            for sp in RINGSPRITES
                tx = isempty(sp.texs) ? "" : lowercase(join(sp.texs," "))
                (occursin("pp",tx) || occursin("people",tx) || occursin("zusch",tx) ||
                 occursin("crowd",tx) || occursin("flag",tx) || occursin("mann",tx)) || continue
                sp.name in shown && continue; push!(shown, sp.name)
                println("        ", rpad(sp.name,12), rpad(string(round(sp.h,digits=1),"m"),8),
                        rpad(string("w=",round(sp.w,digits=1)),9), rpad(cnt[sp.name],5), join(sp.texs," | "))
            end
            println("     -- every family taller than 8 m --")
            shown2 = Set{String}()
            for (nm,h) in sort(collect(hmax), by=x->-x[2])
                h > 8 || break
                nm in shown2 && continue; push!(shown2, nm)
                println("        ", rpad(nm,12), rpad(string(round(h,digits=1),"m"),8), rpad(cnt[nm],5), tex1[nm])
            end
            println("     -- TALLEST families (these are what render as giants) --")
            for (nm,h) in sort(collect(hmax), by=x->-x[2])[1:min(end,12)]
                println("        ", rpad(nm,14), rpad(string(round(h,digits=1),"m"),8),
                        rpad(cnt[nm],6), tex1[nm])
            end
        end
        println("  E76-S8 Ring billboards: ", nbb, " placed, ", notex, " no texture, ", onrd,
                " on-road, ", nwide, " wide → static panels")
        flush(stdout)
    end
else
if get(ENV,"JM_HAT_COUNT","0") != "0"
    # E92: arm the hat() counters for exactly this block, so the figure is per-phase and not
    # contaminated by the physics/render loop that follows.
    JuliaMotor.HAT_COUNT_ON[] = true
    JuliaMotor.HAT_TIME_ON[]  = get(ENV,"JM_HAT_TIME","0") != "0"
    JuliaMotor.hat_reset!()
end

tstamp("  [E80] trackside objects + billboards + trees begin")
const DATPACK = TRACKDAT     # trackside objects come from the track's own .dat (generic across tracks)
const TMPOBJ = mktempdir()
objpath(nm) = (p=joinpath(ZD, nm*".3do"); isfile(p) ? p :
    (v=get(DATPACK, lowercase(nm*".3do"), nothing); v===nothing ? "" :
     (tp=joinpath(TMPOBJ, nm*".3do"); isfile(tp)||write(tp,v); tp)))
# stands-only crowd policy (user): KEEP the seated grandstand/pit-wall crowds, so we no
# longer strip their painted-on people textures — only the GPL shadow/tray artifacts go.
# (Loose roadside people are dropped by name in drop() below, not by texture.)
const CROWD_TEX = ("ltraymap","lshad")
# E71-S16: a `collision` texture EXCLUSION was tried here and REVERTED, recorded so it is not
# retried. 94 of Spa's 502 objects (19%) list a texture named `collision` in their string table and
# there is no collision.mip in the archive -- it is GPL's marker for an invisible hull, so feeding
# it to the footprint test looked like an obvious cause of false on-road hits. Excluding it changed
# the census by exactly 0 (108 -> 108), and the reason is that NO TRIANGLE REFERENCES IT: parsing
# ho18/armcow3/epolsp3 per face gives only real textures (Saeule, Ziegel, dach, armcow_s, polewbr1).
# The name is an unused string-table entry. Nothing to exclude, so no exclusion.
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
        # PO 2026-08-27: "restore the gantry to the start line". E58 pushed it 6 m OUTWARD because a
        # leg protruded into the road — but the DUNLOP bridge at Watkins SPANS the track at the line,
        # so moving it off the line trades one wrong picture for another. The roadward staircase/tower
        # and hay are already stripped separately (obj_extra_excl), which was the other half of E58 and
        # is the half that removes the actual obstruction. Default the push OFF and let the gantry sit
        # where it belongs; JM_STARTBOX_PUSH=6 restores E58's placement if a leg turns out to be in the way.
        boxpush = parse(Float64, get(ENV, "JM_STARTBOX_PUSH", "0.0"))
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
    # E92-S2: hat() was refuted at 0.003% of this phase, so measure what is actually left in it --
    # distinct-mesh loading. Ref accumulators, not plain locals, so the loop body mutates them
    # regardless of Julia's soft-scope rules. JM_MESH_TIME=1.
    _e92 = (n=Ref(0), ext=Ref(0.0), bld=Ref(0.0))
    for inst in insts
        (haskey(objmesh, inst.name) || haskey(bbinfo, inst.name)) && continue
        p = objpath(inst.name)
        if p == ""; objmesh[inst.name]=nothing; continue; end
        try
            _te = time(); full = Render.extract_gpl_car(p; track=true, mirror=true); _e92.ext[] += time() - _te; _e92.n[] += 1   # un-stripped: decides stub vs geometry
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
                    # E71-S16: the footprint must be the BUILT object, not the ground it is
                    # standing on. Several GPL scenery objects bundle their own apron -- eauhotel
                    # carries 17 grass/asphalt/tree triangles spanning 120.1 m around 1018 building
                    # triangles spanning 45.9 m, so 62% of its horizontal extent is lawn. The
                    # footprint test then reports the hotel "1.9 m from the centreline" when it is
                    # the lawn that reaches the road, and dropping the object on that basis would
                    # delete an Eau Rouge landmark because of its garden. ho18 is the contrast: no
                    # ground faces at all, and genuinely 0.2 m off the centreline.
                    # JM_FP_KEEP_GROUND=1 restores the old all-faces footprint.
                    fpground(t) = (l = lowercase(t);
                                   startswith(l,"grass") || startswith(l,"asph") ||
                                   startswith(l,"terr")  || startswith(l,"for_") ||
                                   startswith(l,"tre"))
                    fpkeep = get(ENV,"JM_FP_KEEP_GROUND","0") != "0"
                    vs = Tuple{Float32,Float32}[]
                    for pp in parts
                        (fpkeep || !fpground(pp.tex)) || continue
                        for k in 1:(11*13):length(pp.verts)-2
                            push!(vs, (pp.verts[k], pp.verts[k+2]))
                        end
                    end
                    # an object made ENTIRELY of ground faces has no built footprint; fall back to
                    # all faces rather than silently giving it an empty one (an empty lverts reads
                    # as "no footprint" and would exempt it from the test altogether).
                    if isempty(vs)
                        for pp in parts, k in 1:(11*13):length(pp.verts)-2
                            push!(vs, (pp.verts[k], pp.verts[k+2]))
                        end
                    end
                    lverts[inst.name] = vs
                    _tb = time(); objmesh[inst.name] = Render.build_gpl(parts, TEXIDX); _e92.bld[] += time() - _tb
                end
            end
        catch; objmesh[inst.name]=nothing; end
    end
    if get(ENV,"JM_MESH_TIME","0") != "0"
        println("[mesh] ", _e92.n[], " distinct meshes loaded   extract ",
                round(_e92.ext[],digits=2), " s   build_gpl ", round(_e92.bld[],digits=2), " s   total ",
                round(_e92.ext[]+_e92.bld[],digits=2), " s")
        flush(stdout)
    end
    tstamp("  [E80] .. distinct-mesh LOOP done (post-mesh per-instance work follows)")
    # SNAP every object to OUR terrain (the HAT) instead of its authored GPL height —
    # this kills floaters (GPL placed trees/crowds on dune terrain that ours doesn't match).
    groundz(x,y) = (h=JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(y); ref=Inf); h[3] ? Float32(h[1]) : -999f0)  # -999 = OFF the HAT
    # E106-S13 (PO 2026-09-02: "car crashed, levitated and bounced" at the Nurburgring).
    # E104(b) established the contract that off-mesh must reach the PHYSICS as NaN ("unknown"), and
    # offroad_smoke gates it -- but the PLAYER's closure above was never converted, so it still
    # handed the physics the -999 SENTINEL. drive_rt3d guards only `isfinite`, and -999 is finite:
    # a wheel sampling a hole was told the ground lay 999 m below, the car sank toward it, and the
    # correction on re-acquiring real terrain launched it. Measured on the PO's replay: sank 1.4 m,
    # rose 7 m over 0.8 s above ground that is FLAT at 620.1-620.4 (probed), then fell 6.65 m in a
    # single frame -- the PO's "levitated and bounced", and a breach of the standing rule that the
    # car must NEVER bounce back.
    # Converted HERE, at the physics boundary only: the app's own consumers below all test
    # `> -900f0` and keep the sentinel they were written against.
    # (the physics-facing converter is defined INSIDE main(); see E106-S13b below -- defining it
    # here put it in a scope main() cannot see, which is a runtime UndefVarError, not a parse error)
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
        # E72-S7: march toward the NEAREST CENTRELINE POINT, not the lap's geometric centre.
        # Marching to the centroid works only for objects OUTSIDE the loop; for anything on the
        # INSIDE — Watkins' pit buildings, 29 m off the road — the direction points away from the
        # track, deeper into unmodelled infield, so the march finds no HAT and returns trkzlo. That
        # buried newpit/pitfill2/pitgrnd1 ~29 m underground (E72-S6) while tower1, just inside the
        # HAT at 26.9 m, landed correctly. Aiming at the nearest ribbon point is right from either
        # side. JM_EDGEZ_CENTROID=1 restores the old target for A/B.
        # ⚠️ GATED to WATGLEN and SPA. The nearest-centreline target is right in principle, but the
        # cross-track check found a REGRESSION on Monza: at s=3000 a large tree/forest object is
        # raised into the sky and overhangs the road as a dark canopy (14.6% of the frame changed;
        # e72_monza_regression.jpg). Watkins gains its pit complex, Spa gains a buried structure,
        # Zandvoort is unaffected — so the win is kept where it is verified and the regression is
        # kept out until Monza's case is understood. Gating by track is a holding measure, not the
        # end state.
        local tx = TRKCX; local ty = TRKCY
        # E73-S12: GATE LIFTED. It was imposed in E72-S8 because Monza appeared to gain an
        # overhanging canopy. Two lines of evidence retire that:
        #   • E73-S11 — the nearest-centreline march reproduces each object's OWN AUTHORED z to
        #     within 0.1 m for all nine movers, while the centroid march buries them ~5 m; and
        #   • E73-S12 — a direct geometric test (JM_OVERHANG) finds 71 of 73 Monza tree strips with
        #     ZERO footprint points inside the road corridor, nearest laterals 7–25 m. The "canopy
        #     over the road" is perspective, not intrusion, by the PO's own criterion.
        # E73-S9's contrary gold check was withdrawn in S11 for not pinning location.
        # JM_EDGEZ_CENTROID=1 restores the old target.
        if !haskey(ENV, "JM_EDGEZ_CENTROID")
            bd = Inf
            for p in ALIGNED
                dd = (p[1]-x)^2 + (p[2]-y)^2
                dd < bd && (bd = dd; tx = p[1]; ty = p[2])
            end
        end
        dx = tx - x; dy = ty - y; d = hypot(dx, dy)
        d < 1f-3 && return trkzlo
        # E73-S10: take the LOWEST surface at the hit, not the highest. groundz queries the HAT with
        # ref=Inf, which returns the topmost layer where surfaces overlap. That is right for placing a
        # car (it drives on the top) and wrong for grounding a distant backdrop object, which belongs
        # on the ground. It is the mechanism behind the Monza regression, traced at trees03:
        #   nearest-centreline march, 8 m → h=9.1, surfaces at hit: 9.1, 6.3   ← grounded on the upper
        #   lap-centroid march,       8 m → h=6.3, surfaces at hit: 6.3
        # i.e. the two marches hit different spots and only one of them has an elevated layer; the
        # 2.8 m lift raised a long forest strip into the canopy that has gated this fix since E72-S8.
        # JM_EDGEZ_TOP=1 restores the old topmost-surface behaviour.
        lowest(px, py) = begin
            g = groundz(px, py)
            g <= -900f0 && return g
            get(ENV,"JM_EDGEZ_TOP","0") != "0" && return g
            r = Float64(g)
            for _ in 1:8
                h = JuliaMotor.hat3d(TERRAIN, Float64(px), Float64(py); ref = r - 0.6)
                h[3] || break
                r = h[1]
            end
            Float32(r)
        end
        # E73-S11: a single ray is direction-BIASED. E73-S10 ranked 9 of 40 Monza off-HAT objects as
        # moving >1 m purely because the nearest-centreline and lap-centroid rays reach different
        # ground — for an object the HAT does not cover, "the ground height" is not defined and one
        # ray is just a guess that happens to point somewhere. Sample a RING of directions at growing
        # radius and take the LOWEST hit at the first radius that finds any: no direction is
        # privileged, and a backdrop object cannot be perched on whatever a single ray struck.
        # JM_EDGEZ_RAY=1 restores the single-ray march.
        if get(ENV,"JM_EDGEZ_RAY","0") == "0"
            for rad in 8f0:8f0:Float32(min(d, 400.0))
                best = Inf32
                for k in 0:11
                    th = Float32(2pi*k/12)
                    g = lowest(x + cos(th)*rad, y + sin(th)*rad)
                    g > -900f0 && g < best && (best = g)
                end
                best < Inf32 && return best
            end
        end
        ux = dx/d; uy = dy/d; s = 0f0
        while s < d
            gz = lowest(x + ux*s, y + uy*s); gz > -900f0 && return gz
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
    # E79 (PO 2026-08-28): "remove line-of-people objects if there's any chance they could be in the
    # road or partially hanging in air; these objects don't add much and detract a lot if misplaced.
    # remove all line of people objects from zandervoort."
    # Zandvoort is unconditional, so it is a NAME rule and lands here — which also means it applies
    # to BOTH paths, the mesh objects and the billboard sprites, since this loop's guard calls
    # drop(i.name) too. That matters: the three rows the PO actually saw were already reported
    # "dropped" by the mesh footprint filter and were on screen anyway, because they arrive as
    # sprites. A name rule cannot be bypassed that way.
    # JM_KEEP_CROWDROWS=1 restores them.
    # E88 (PO 2026-08-28): "remove all lines of people objects from Watkins Glen, several of which
    # are right in the track on the back stretch" -- video 260828_watkins_race.mp4.
    # The guard used to read `ZANDV &&`. E79 carried out the PO's Zandvoort sentence literally and
    # left the GENERAL half of the same instruction unapplied everywhere else: "remove line-of-people
    # objects if there's any chance they could be in the road or partially hanging in air; these
    # objects don't add much and detract a lot if misplaced." Watkins therefore kept every
    # standcrowd row, including the ones the PO drove through on the back stretch.
    # Now unconditional (all tracks). JM_KEEP_CROWDROWS=1 restores them.
    _dropcrowdrows = get(ENV,"JM_KEEP_CROWDROWS","0") == "0"
    drop(nm) = (!isempty(_keeptest) && any(p->startswith(nm,p), _keeptest)) ? false :
               (_dropcrowdrows && standcrowd(nm)) ||
               (!isempty(_droptest) && any(p->startswith(nm,p), _droptest)) || (!standcrowd(nm) && (
               (startswith(nm,"grass") && !KEEP_GRASS) || (startswith(nm,"herbe") && !KEEP_GRASS) || nm == "infield" ||
               nm == "hotels" ||                                             # E45: Zandvoort backdrop building cluster — a 310 m garbage bbox that never grounds → floats in the sky above the grandstand; the horizon ring + dunes carry the backdrop without it
               startswith(nm,"tent") || startswith(nm,"single") ||
               (startswith(nm,"intree") && !WATGLEN) ||                      # INFIELD tree lines (100s of m wide) → distant central "smear".  WG3 (E64 S5): on WATKINS these + treefill/treesrb ARE the gold's close roadside autumn forest — the smear objection predates graze-fade (MZ3), which fixed it; kept there now
               ((startswith(nm,"treesrb") || startswith(nm,"treefill")) && !WATGLEN) ||  # forest-BACKDROP / gap-fill quads → streaky "painted tree" smear (non-Watkins; see WG3 note above)
               startswith(nm,"trbk") || startswith(nm,"brbk") ||             # Monza underpass tree/bush BANKS (trbk1-8/brbk1-3 at lapdist ~3100-3440, lat ~5 m) — MESH foliage that bypasses the sprite on-road filter and renders as dark vertical smears ACROSS the road (PO round 4: "7 stands of trees across the track near the underpass")
               startswith(nm,"tuntbk") ||                                    # tunnel-edge tree bank (same dark-smear foliage by the underpass)
               # E101: the loose-people list now lives in PeopleFilter, shared with the gate
               # that checks it (tools/people_smoke.jl). It was a closure nothing could test,
               # and a name list stops covering tracks added later without saying so.
               PeopleFilter.is_loose_person(nm)))
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
    # E69-S9: perp_crowd drops 40 of Zandvoort's 97 crowd instances (41%). E68-S1 justified it as
    # "a perpendicular row near the road can only be GPL cross-placement garbage - real fence crowds
    # run PARALLEL". That is sound IF our yaw convention matches the data's: if it is off by 90 deg we
    # would be deleting the parallel rows and keeping the garbage. Print the relative-yaw histogram so
    # the convention is checked rather than assumed. JM_PERPDIAG=1.
    if get(ENV,"JM_PERPDIAG","") != ""
        rys = Float64[]
        for i in insts
            standcrowd(i.name) || continue
            hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            hr.found || continue
            push!(rys, abs(rad2deg(rem2pi(Float64(i.yaw) - atan(-hr.perp[2], hr.perp[1]), RoundNearest))))
        end
        if !isempty(rys)
            println("== JM_PERPDIAG: crowd row yaw RELATIVE to the track perpendicular (", length(rys), " rows) ==")
            println("   0deg = row runs ALONG the perpendicular (crosses the track) ; 90deg = row runs PARALLEL to the track")
            for lo in 0:15:165
                c = count(r -> lo <= r < lo+15, rys)
                println("   ", rpad(string(lo,"-",lo+15,"deg"), 12), rpad(c,6), "#"^min(60, c))
            end
            println("   dropped by the 60-120deg window: ", count(r -> 60.0 <= r <= 120.0, rys))
        end
        flush(stdout)
    end
    perp_crowd(i) = get(ENV,"JM_NO_PERP","0") == "0" && standcrowd(i.name) && begin
        hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
        if hr.found && abs(hr.lateral) < ROAD_HALFW + 12.0
            ry = abs(rad2deg(rem2pi(Float64(i.yaw) - atan(-hr.perp[2], hr.perp[1]), RoundNearest)))
            60.0 <= ry <= 120.0
        else
            false
        end
    end
    # E69-S5 (PO: "move any objects that are on the actual road to the places they belong"):
    # every on-road filter above tests the object's ORIGIN — onroad_crowd, perp_crowd and
    # onroad_bldg all project (i.x, i.y). E71-S8 already showed that ordering is not the "is it in
    # the way" ordering, and Zandvoort proves it costs real defects: JM_FOOTPRINT finds 45 instances
    # whose GEOMETRY crosses the asphalt, led by a bushes01-04 thicket at s≈2310-2700 reaching to
    # 0.1 m of the centreline, and by ppl_l3 (@3256) and ppl_m1 (@3851) reaching 0.8 m and 0.2 m
    # from ORIGINS 12.3 m and 5.5 m out — origins no origin-based test can catch. Captures confirm
    # both: a grass bank engulfing the car's left flank at s=2300-2590, and a wall of spectators
    # across the track at s=3250.
    # So test the FOOTPRINT: the nearest transformed vertex, the same measure JM_FOOTPRINT reports.
    # Scoped to VEGETATION and CROWDS — the families the evidence covers. Buildings keep their own
    # (origin) rule for now and bridges//overhead structures are untouched, since a span across the
    # road is authored, not a defect. JM_ONROAD_FP=0 reverts.
    onroad_fp_edge = parse(Float64, get(ENV,"JM_ASPHALT_HALFW","4.1"))
    # E69-S12: BUILDINGS join the footprint test. E69-S5 scoped it to vegetation and crowds and left
    # buildings on the ORIGIN rule (onroad_bldg) "for now" — and the on-road census shows what that
    # costs: at Spa 129 intruding instances actually RENDER, dominated by houses reaching 0.1–0.8 m of
    # the centreline (house41 21 points over the road, house43 27, house35 17, house4 15). house43's
    # origin sits 6.0 m out (E71-S7), so an origin test can never catch it. This is the PO's headline
    # Spa complaint — "houses in the case of the spa track that are on the actual road".
    # JM_ONROAD_FP_BLDG=0 restores the vegetation/crowd-only scope.
    vegcrowd(nm) = startswith(nm,"bush") || startswith(nm,"shrub") || startswith(nm,"strauch") ||
                   startswith(nm,"hedge") || startswith(nm,"haie") || standcrowd(nm) ||
                   startswith(nm,"ppl") || startswith(nm,"people") || startswith(nm,"pplrow") ||
                   (get(ENV,"JM_ONROAD_FP_BLDG","1") != "0" && bldgish(nm))
    onroad_fp(i) = get(ENV,"JM_ONROAD_FP","1") != "0" && vegcrowd(lowercase(i.name)) && begin
        vs = get(lverts, i.name, nothing)
        if vs === nothing || isempty(vs)
            false
        else
            th = -Float64(i.yaw) + Float64(objyawfix(i.name)); c, sn = cos(th), sin(th)
            near = Inf
            for (lx, lz) in vs
                rx =  lx*c + lz*sn; rz = -lx*sn + lz*c
                hr = JuliaMotor.hat(TRKSURF, Float64(i.x) + rx, Float64(i.y) - rz)
                hr.found && (near = min(near, abs(hr.lateral)))
            end
            hit = near < onroad_fp_edge
            hit && get(ENV,"JM_ONROAD_FP_DIAG","") != "" &&
                println("  E69-S5: ", i.name, " footprint reaches ", round(near,digits=1),
                        " m of the centreline — dropped")
            hit
        end
    end
    # E68 S2 (PO: Monza "haze planes make the forest absent, then fade into view"): uGraze was
    # built to fade FLAT panels seen edge-on; on the E65 real folded tree MESHES it fades whole
    # forest walls with view angle.  Mesh-path trees (MONZA/WATGLEN) draw un-grazed — a folded
    # strip has no edge-on smear to hide.  JM_GRAZE_MESH=1 restores the old fade for A/B.
    # E73-S9: FOOTPRINT grounding. E73-S7 traced the Monza edgez regression to single-point
    # grounding: `ploz` samples the terrain at the object's ORIGIN and applies that one height to the
    # whole object, so a 19 m forest strip whose origin sits over high ground is lifted bodily and
    # its far end overhangs the road as a canopy. The same shape of error has now appeared three
    # times (E71-S8 origin-vs-footprint, E73-S7 grounding, E69-S5 on-road test), always because a
    # single point was asked to describe an extended object.
    # Sample the ground across the object's own FOOTPRINT and take a low quantile, so no part of a
    # long object hovers. JM_FPGROUND=1 enables; JM_FPGROUND_Q sets the quantile (0 = lowest point,
    # 0.5 = median). Default quantile 0.15 — near the low end without chasing a single outlier.
    FPGROUND = get(ENV,"JM_FPGROUND","0") != "0"
    FPQ      = parse(Float64, get(ENV,"JM_FPGROUND_Q","0.15"))
    plozfp(i) = begin
        base = ploz(i)
        vs = get(lverts, i.name, nothing)
        (!FPGROUND || vs === nothing || isempty(vs)) && return base
        th = -Float64(i.yaw) + Float64(objyawfix(i.name)); c, sn = cos(th), sin(th)
        zs = Float32[]
        for (lx, lz) in vs
            rx =  lx*c + lz*sn; rz = -lx*sn + lz*c
            px = Float32(i.x) + Float32(rx); py = Float32(i.y) - Float32(rz)
            # E73-S9b: sample the FULL grounding function, not just groundz. First attempt sampled
            # groundz alone — which returns "off the HAT" for precisely the objects edgez exists to
            # place, so every sample failed, plozfp fell back to the origin height, and the arm was
            # byte-identical to no fix at all (C vs B = 0.74% / 0.02%, at the noise floor). The A/B
            # caught it only because a fix that changes nothing is as suspicious as one that changes
            # everything.
            gz = groundz(px, py)
            gz <= -900f0 && (gz = edgez(px, py))
            gz > -900f0 && push!(zs, gz)
        end
        length(zs) < 3 && return base
        sort!(zs)
        zs[max(1, min(length(zs), ceil(Int, FPQ*length(zs))))]
    end
    # E73-S10: two mechanisms for the Monza canopy have been eliminated (S6 banking, S7/S9
    # single-point grounding). A third has never been tested: groundz queries the HAT with ref=Inf,
    # which returns the HIGHEST surface where layers overlap. If the edgez march's first hit lands on
    # an elevated layer, the object is grounded on that instead of the terrain beneath it. Enumerate
    # the surfaces at the march's first hit by lowering `ref` step by step — the HAT API allows it.
    # JM_EDGEZ_TRACE=<name substring>
    hr_lap(i) = (h = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y)); h.found ? h.lapdist : -1.0)
    if get(ENV,"JM_OVERHANG","") != ""
        # E73-S12: does an object actually INTRUDE over the racing surface? That is the PO's criterion
        # ("objects that are on the actual road"), and unlike a treeline's apparent height it can be
        # answered from geometry alone — no gold frame, no landmark matching, no percentage. For each
        # matching instance, transform its mesh by the SAME model matrix the renderer uses and count
        # vertices whose projection lands within the road corridor, reporting how high above the road
        # surface they sit. JM_OVERHANG=<name substring>
        pat = lowercase(ENV["JM_OVERHANG"])
        halfw = parse(Float64, get(ENV,"JM_OVERHANG_HALFW","6.0"))
        # a silent block cannot be distinguished from a block that never ran — say what was searched
        println("== JM_OVERHANG: /", pat, "/ over ", length(insts), " instances, corridor ±", halfw, " m ==")
        nointr = 0; nofp = 0; hits = Tuple{String,Int,Float64,Float64,Float64,Bool,Float64,Float64}[]
        for i in insts
            (pat == "1" || occursin(pat, lowercase(i.name))) || continue
            vs = get(lverts, i.name, nothing)
            if vs === nothing || isempty(vs)
                nofp += 1
                pat == "1" || println("   [overhang] ", rpad(i.name,10), " NO FOOTPRINT (billboard/panel path)")
                continue
            end
            th = -Float64(i.yaw) + Float64(objyawfix(i.name)); c, sn = cos(th), sin(th)
            base = Float64(plozfp(i))
            nover = 0; ntot = 0; minlat = Inf; hi = -Inf
            for (lx, lz) in vs
                rx =  lx*c + lz*sn; rz = -lx*sn + lz*c
                px = Float64(i.x) + rx; py = Float64(i.y) - rz
                hr = JuliaMotor.hat(TRKSURF, px, py)
                hr.found || continue
                ntot += 1
                minlat = min(minlat, abs(hr.lateral))
                if abs(hr.lateral) < halfw
                    nover += 1
                    hi = max(hi, base - Float64(hr.height))
                end
            end
            ntot == 0 && continue
            if nover > 0
                # E69-S12: an intrusion only matters if the object actually RENDERS. The census walks
                # every PLACED instance, including ones the on-road filters already remove, so the raw
                # count is an upper bound. Apply the same keep-test the OBJECTS comprehension uses.
                kept = get(objmesh,i.name,nothing) !== nothing && !drop(i.name) &&
                       !onroad_crowd(i) && !perp_crowd(i) && !onroad_bldg(i) && !onroad_fp(i) &&
                       (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && onground(i)
                # E71-S17: an intruder's ORIGIN lateral and its yaw RELATIVE TO THE ROAD. The
                # census has only ever reported how close the footprint gets, which cannot separate
                # "authored beside the road" from "placed beside the road and turned across it".
                # A 4.5 m car parked parallel with its origin 5 m out reaches ~4.1 m; the same car
                # turned 90 degrees reaches ~2.5 m. Same object, same origin, very different
                # verdict -- and the project already draws this distinction for crowds
                # (perp_crowd, "a perpendicular row near the road can only be GPL cross-placement
                # garbage - real fence crowds run PARALLEL"). Nothing applied it to anything else.
                _ho = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
                _olat = _ho.found ? _ho.lateral : NaN
                _ry = _ho.found ?
                      abs(rad2deg(rem2pi(Float64(i.yaw) - atan(-_ho.perp[2], _ho.perp[1]), RoundNearest))) : NaN
                _ry = isnan(_ry) ? _ry : (_ry > 90 ? 180 - _ry : _ry)   # fold to 0..90: 0 = parallel
                push!(hits, (i.name, nover, minlat, hi, hr_lap(i), kept, _olat, _ry))
            else
                nointr += 1
            end
            pat == "1" && continue
            println("   [overhang] ", rpad(i.name,10),
                    " footprint pts ", rpad(ntot,5),
                    " over road(<", halfw, "m): ", rpad(nover,5),
                    " nearest |lat| ", rpad(round(minlat,digits=1),7),
                    nover > 0 ? string(" base sits ", round(hi,digits=1), " m above road") : "")
        end
        if pat == "1"
            sort!(hits, by=h->(!h[6], h[3]))   # E69-S12: rendering intruders first — they are the actionable ones
            nkept = count(h->h[6], hits)
            println("   ", nointr, " instances clear of the road, ", length(hits), " intruding of which ",
                    nkept, " ACTUALLY RENDER, ", nofp, " without a mesh footprint (not tested)")
            # E71-S16: the list was capped at 14 while the count being quoted was 108, so the
            # remaining 94 were never once printed and "closing the rest is enumeration" could not
            # actually be done from this output. JM_OVERHANG_TOP=<n> (default 14, "all" for all).
            _topspec = get(ENV,"JM_OVERHANG_TOP","14")
            _top = _topspec == "all" ? length(hits) : parse(Int,_topspec)
            for h in hits[1:min(end,_top)]
                println("      ", h[6] ? "RENDERS " : "dropped ", rpad(h[1],12), "pts over road ", rpad(h[2],5),
                        " nearest |lat| ", rpad(round(h[3],digits=1),7),
                        " origin |lat| ", rpad(isnan(h[7]) ? "?" : string(round(abs(h[7]),digits=1)),7),
                        " yaw-vs-road ", rpad(isnan(h[8]) ? "?" : string(round(Int,h[8])), 4),
                        " base ", rpad(round(h[4],digits=1),7), " m   lapdist ", round(Int,h[5]))
            end
            # A per-FAMILY roll-up of the ones that render. Individual rows say where; the family
            # is what a filter rule can actually be written against, and it is the family counts
            # that say whether the remainder is one more name pattern or a long tail of singletons.
            fam = Dict{String,Vector{Tuple{Float64,Float64}}}()
            for h in hits
                h[6] || continue
                k = rstrip(h[1], ['0','1','2','3','4','5','6','7','8','9'])
                push!(get!(fam, k, Tuple{Float64,Float64}[]), (h[3], h[4]))
            end
            if !isempty(fam)
                println("   -- rendering intruders by family (", length(fam), " families, ", nkept, " instances) --")
                for k in sort!(collect(keys(fam)), by=k->(-length(fam[k]), k))
                    v = fam[k]
                    println("      ", rpad(k,14), rpad(length(v),5),
                            " nearest |lat| ", rpad(round(minimum(first.(v)),digits=1),7),
                            " base above road ", round(minimum(last.(v)),digits=1), " … ",
                            round(maximum(last.(v)),digits=1), " m")
                end
            end
        end
        flush(stdout)
        # E71-S16: JM_OVERHANG_EXIT=1 stops here. The census is a headless geometry question, but
        # reaching it costs the full texture + object load, and the only harness that ran past it
        # (JM_SWEEP) then walks the whole centreline and opens the game loop as well -- a 900 s
        # wrapper timeout killed the first attempt before a single census line was printed.
        get(ENV,"JM_OVERHANG_EXIT","") != "" && exit(0)
    end
    if get(ENV,"JM_EDGEZ_RANK","") != ""
        # E73-S10b: which OFF-HAT objects still move between the two march targets, after the
        # lowest-surface fix? Rank by |Δheight| so the remaining offenders are named rather than
        # hunted one at a time.
        rows = Tuple{String,Float64,Float64,Float64,Float64,Float64}[]
        for i in insts
            groundz(i.x, i.y) > -900f0 && continue
            bd = Inf; tx = TRKCX; ty = TRKCY
            for p2 in ALIGNED
                dd = (p2[1]-i.x)^2 + (p2[2]-i.y)^2
                dd < bd && (bd = dd; tx = p2[1]; ty = p2[2])
            end
            hs = Float64[]
            for (gx, gy) in ((tx, ty), (TRKCX, TRKCY))
                dx = gx - i.x; dy = gy - i.y; d = hypot(dx,dy)
                if d < 1e-3; push!(hs, NaN); continue; end
                ux = dx/d; uy = dy/d; sd = 0.0; got = NaN
                while sd < d
                    g = groundz(Float32(i.x+ux*sd), Float32(i.y+uy*sd))
                    if g > -900f0
                        r = Float64(g)
                        for _ in 1:8
                            h = JuliaMotor.hat3d(TERRAIN, Float64(i.x+ux*sd), Float64(i.y+uy*sd); ref=r-0.6)
                            h[3] || break
                            r = h[1]
                        end
                        got = r; break
                    end
                    sd += 8.0
                end
                push!(hs, got)
            end
            (isnan(hs[1]) || isnan(hs[2])) && continue
            hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            push!(rows, (i.name, hs[1], hs[2], hs[1]-hs[2], hr.found ? hr.lapdist : -1.0, Float64(i.z)))
        end
        sort!(rows, by=r->-abs(r[4]))
        println("== JM_EDGEZ_RANK: off-HAT objects by |nearest-march − centroid-march| height ==")
        # E73-S11: also print the object's OWN AUTHORED z. edgez exists to rescue objects the HAT
        # does not reach and whose authored height is wrong (Watkins' pit buildings sat 29 m
        # underground). If an object's authored z already matches the low march, marching it upward is
        # not a rescue — it is damage.
        println("   name          nearest   centroid   delta    authored-z   lapdist")
        for r in rows[1:min(end,12)]
            println("   ", rpad(r[1],13), rpad(round(r[2],digits=1),10), rpad(round(r[3],digits=1),11),
                    rpad(round(r[4],digits=1),9), rpad(round(r[6],digits=1),13), round(Int,r[5]))
        end
        println("   (", count(r->abs(r[4])>1.0, rows), " of ", length(rows), " off-HAT objects move >1 m)")
        flush(stdout)
    end
    if get(ENV,"JM_EDGEZ_TRACE","") != ""
        pat = lowercase(ENV["JM_EDGEZ_TRACE"])
        shown = 0
        for i in insts
            occursin(pat, lowercase(i.name)) || continue
            shown >= 4 && break
            gz0 = groundz(i.x, i.y)
            gz0 > -900f0 && continue                    # on-HAT: edgez is not used
            shown += 1
            # replay the march and report the first hit
            bd = Inf; tx = TRKCX; ty = TRKCY
            for p2 in ALIGNED
                dd = (p2[1]-i.x)^2 + (p2[2]-i.y)^2
                dd < bd && (bd = dd; tx = p2[1]; ty = p2[2])
            end
            for (lbl, gx, gy) in (("nearest-centreline", tx, ty), ("lap-centroid", TRKCX, TRKCY))
                dx = gx - i.x; dy = gy - i.y; d = hypot(dx,dy)
                d < 1e-3 && continue
                ux = dx/d; uy = dy/d; sdist = 0.0; hitx = NaN; hity = NaN; hz = -999f0
                while sdist < d
                    px = Float32(i.x + ux*sdist); py = Float32(i.y + uy*sdist)
                    g = groundz(px, py)
                    if g > -900f0; hitx=px; hity=py; hz=g; break; end
                    sdist += 8.0
                end
                if hz > -900f0
                    # enumerate overlapping surfaces at the hit
                    hs = Float64[]; r = Inf
                    for _ in 1:6
                        h = JuliaMotor.hat3d(TERRAIN, Float64(hitx), Float64(hity); ref=r)
                        h[3] || break
                        push!(hs, h[1]); r = h[1] - 0.6
                    end
                    println("   [edgez] ", rpad(i.name,10), rpad(lbl,20),
                            "march ", rpad(round(Int,sdist),5), "m → h=", rpad(round(hz,digits=1),7),
                            " surfaces at hit: ", join(round.(hs,digits=1), ", "))
                else
                    println("   [edgez] ", rpad(i.name,10), rpad(lbl,20), "march found NO HAT in ", round(Int,d), " m")
                end
            end
        end
        flush(stdout)
    end
    tstamp("  [E80] .. object mesh placement done; OBJECTS build begins")
    graze_mesh = get(ENV,"JM_GRAZE_MESH","0") != "0"
    global OBJECTS = [(objmesh[i.name], Render.translate(Float32[i.x, plozfp(i), -i.y]) * Render.roty(Float32(-i.yaw + objyawfix(i.name))), istree(i.name) && (graze_mesh || !(MONZA || WATGLEN)), (Float32(i.x), plozfp(i), Float32(-i.y)), lowercase(i.name))
                      for i in insts if get(objmesh,i.name,nothing) !== nothing &&
                          !drop(i.name) && !onroad_crowd(i) && !perp_crowd(i) && !onroad_bldg(i) && !onroad_fp(i) && (get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0 && onground(i)]
    # E97 (2026-08-30): watglen loads 66 trackside objects today; four E80/E88/E92-era logs record
    # 163 for the same track. Rather than argue from old logs -- which are themselves suspect, since
    # a Zandvoort-labelled one prints the identical 163/39/110 triple -- attribute every removal.
    # Each instance is charged to the FIRST predicate that rejects it, so the buckets sum to the
    # instances that did not become OBJECTS and no instance is counted twice. JM_OBJDIAG=1.
    if get(ENV,"JM_OBJDIAG","") != ""
        why = Dict{String,Int}(); kept = 0
        for i in insts
            r = get(objmesh,i.name,nothing) === nothing ? "no-mesh" :
                drop(i.name)              ? "drop() junk filter" :
                onroad_crowd(i)           ? "onroad_crowd" :
                perp_crowd(i)             ? "perp_crowd" :
                onroad_bldg(i)            ? "onroad_bldg" :
                onroad_fp(i)              ? "onroad_fp (footprint on road)" :
                !((get(ymx,i.name,0f0)-get(ymn,i.name,0f0)) > 1.0f0) ? "under 1 m tall" :
                !onground(i)              ? "not on ground" : ""
            r == "" ? (kept += 1) : (why[r] = get(why,r,0)+1)
        end
        println("== JM_OBJDIAG ", length(insts), " instances -> ", kept, " OBJECTS")
        for (k,v) in sort(collect(why), by=x->-x[2])
            println("   removed by ", rpad(k,32), v)
        end
        flush(stdout)
    end
    # E15: SOLID trackside objects the car can hit — (physics x, z, collision radius m).  Buildings,
    # barriers/hedges (haybales = Zandvoort `haie`), towers, parked vehicles.  NOT trees/signs/people.
    solidR(nm) = startswith(nm,"hut")||startswith(nm,"pitbldg")||startswith(nm,"hotel")||startswith(nm,"bigbosch")||nm=="mega2"||startswith(nm,"longtent")||
                 startswith(nm,"chut")||startswith(nm,"lasad")||startswith(nm,"haus")||startswith(nm,"house")||startswith(nm,"ferme") ? 5.0 :   # E68 S8: Spa houses are solid (no drive-through)
                 startswith(nm,"gstand")||startswith(nm,"grand")||startswith(nm,"tribun")||startswith(nm,"camstnd")||startswith(nm,"mgrand") ? 6.0 :   # PO: grandstands are SOLID (no driving through the stands)
                 startswith(nm,"tower")||startswith(nm,"megafon") ? 2.0 :
                 startswith(nm,"haie")||startswith(nm,"bush")||startswith(nm,"shrub")||startswith(nm,"hedge")||startswith(nm,"haystk") ? 1.5 :   # hay rows + trackside bushes/hedges (PO: more objects hittable when you run wide — soft, you plough through with a penalty).  SMALL radius so they don't clip the racing groove
                 startswith(nm,"armco")||startswith(nm,"barrier")||startswith(nm,"fence")||startswith(nm,"wall") ? 1.2 :
                 startswith(nm,"caravn")||startswith(nm,"vwvan")||startswith(nm,"ftruck")||startswith(nm,"ambul")||nm=="car2"||startswith(nm,"rescu") ? 2.4 : 0.0
    # E95h (PO 2026-08-29, Monza: "I drove through a lot of objects as if they were not there").
    # JM_SOLIDDIAG said it plainly: Monza built 2 solids out of 176 instances -- `tower`x2. The
    # cause is that solidR() above is a hardcoded NAME whitelist grown from Spa/Watkins/Zandvoort,
    # and Monza shares almost none of those names: its treeline is `trees01..trees73b`, its pit
    # walls are `pitwall/pitwall1/pitwall2` (which `startswith(nm,"wall")` does NOT match), its
    # barriers are `bar01..bar06` (which `startswith(nm,"barrier")` does NOT match), and its
    # grandstands are `front01..09`/`ter01..05`. 138 of 140 distinct names fell through to 0.0.
    #
    # Extending the whitelist name-by-name is how it got track-specific in the first place, so
    # measure the object instead: every mesh already has a local AABB here (lxmn/lxmx/lzmn/lzmx
    # from E71-S8, ymn/ymx). The one thing that must NOT become solid is a wide flat BACKDROP panel
    # -- Monza has many (`trbk1..8`, `tuntbk1/2`, `brbk1..3`, and the panoramic `trees*` strips the
    # billboard path already treats as static backdrop). Those are WIDE and PAPER-THIN, so:
    #
    #     r = min(w, d) / 2      <-- min, never max
    #
    # A 380 m x 0.2 m forest strip gives r = 0.1 -> rejected. A 4 x 4 m tree gives r = 2.0. A
    # grandstand 30 x 12 m gives r = 6.0. The shape does the classifying, so this generalises to
    # every track rather than to the names of one.
    #
    # This runs only where the whitelist declined, so no existing radius changes; and the render
    # -visibility filter below (mesh + drop() + height, plus the on-road predicates) still applies
    # afterwards, keeping E71-S18's invariant intact: IF IT IS NOT DRAWN, IT MUST NOT BE SOLID.
    GEOM_WMAX = parse(Float64, get(ENV,"JM_GEOM_WMAX","40.0"))  # long axis: above this it is a
                                                                #  backdrop or a composite block
    GEOM_RMAX = parse(Float64, get(ENV,"JM_GEOM_RMAX","8.0"))   # above this it is a COMPOSITE .3do
                                                                # holding a whole block (E71-S10),
                                                                # not one object: skip, do not drop
                                                                # a 20 m invisible disc on the map.
    # PEOPLE ARE NEVER SOLID. The PO's standing rule is that line-of-people objects come OUT if they
    # could be in the road or hanging in air; giving them collision discs is the opposite of that.
    person_like(n) = occursin(r"^(flagger|peo|ppl|crowd|grndpe|spect|marshal|pit(ppl|peo))", n)
    # E95h-S2: TERRAIN IS NOT AN OBJECT. Watkins' `pitfill2` (14.7 x 15.2 x 2.2) is a ground fill
    # patch and passed every shape test; Monza has `fillgrnd`/`pitgrnd1`/`ter01..05` of the same
    # kind. They are the surface the car DRIVES ON, so a collision disc on one is a wall in the
    # middle of the paddock. These are named by convention across all four tracks, and unlike the
    # object whitelist this is a small closed set describing terrain, not a per-track vocabulary.
    ground_like(n) = occursin(r"^(fill|.*fillgrnd|pitgrnd|pitfill|grnd|ground|terr|ter\d)", n)
    # E95h-S2: GPL names its backdrop panels with a `bk` tail -- Monza ships `trbk1..8` (track
    # backdrop), `brbk1..3` and `tuntbk1/2` (tunnel backdrop). Four of them still cleared the size
    # gates because they are genuinely chunky (trbk8 is 19.4 x 13.9 x 11.7), and no purely
    # dimensional test will separate a chunky backdrop from a building. The naming convention is
    # the only thing that actually knows, and unlike the object whitelist this is one small closed
    # set describing a RENDER ROLE, not a per-track vocabulary of object names.
    backdrop_like(n) = occursin(r"bk\d*$", n)
    _geomwhy = Dict{String,String}()            # name -> why the shape rule accepted/rejected it
    function geomR(orig, nm)
        person_like(nm) && (_geomwhy[nm] = "person"; return 0.0)
        ground_like(nm) && (_geomwhy[nm] = "terrain"; return 0.0)
        backdrop_like(nm) && (_geomwhy[nm] = "backdrop"; return 0.0)
        haskey(lxmn, orig) || (_geomwhy[nm] = "no-mesh"; return 0.0)
        w = lxmx[orig] - lxmn[orig]; d = lzmx[orig] - lzmn[orig]
        h = get(ymx, orig, 0f0) - get(ymn, orig, 0f0)
        dims = "$(round(w,digits=1))x$(round(d,digits=1))x$(round(h,digits=1))"
        h > 1.0f0 || (_geomwhy[nm] = "flat $dims"; return 0.0)
        # E95h-S2: min(w,d) ALONE does not identify a backdrop, which is what the first cut of this
        # assumed. Verified offline against all four installed tracks: Monza's `trbk3` is 63.8 x 9.6
        # -- a track backdrop 64 m wide, but 9.6 m DEEP, so min/2 = 4.8 sailed straight through, and
        # Spa gained 133 names the same way (`fe_sta6` at 83.2 x 13.7). Those are invisible walls,
        # and with E95g making a wreck permanent an invisible wall now ends the race outright.
        # A real trackside object is not 40 m across; a backdrop or a composite .3do block is. Gate
        # on the LONG axis too, so both dimensions have to be plausible for a single object.
        if max(w, d) > GEOM_WMAX
            _geomwhy[nm] = "wide $dims (backdrop/composite)"; return 0.0
        end
        r = Float64(min(w, d)) / 2                 # min: rejects wide/thin backdrop panels
        r < 0.5      && (_geomwhy[nm] = "thin $dims (backdrop panel)"; return 0.0)
        r > GEOM_RMAX && (_geomwhy[nm] = "huge $dims (composite .3do)"; return 0.0)
        _geomwhy[nm] = "SOLID r=$(round(r,digits=1)) $dims"
        r
    end
    global SOLIDS = Tuple{Float64,Float64,Float64,Symbol}[]
    SOLIDNAMES = String[]                        # parallel to SOLIDS, for the census only
    _geomn = 0
    for i in insts
        nml = lowercase(i.name)
        r = solidR(nml)
        if r <= 0.0 && get(ENV,"JM_GEOMSOLID","1") != "0"
            r = geomR(i.name, nml); r > 0.0 && (_geomn += 1)
        end
        (r <= 0.0 || !onground(i)) && continue
        on_road(i.x, i.y, SOLID_EXCL_HW) && continue   # E31: don't make a collidable wall ON the road (the trapping hedge-box) — but DO keep edge barriers/haybales solid (PO)
        # E71-S18 (PO 2026-08-27, Spa: "just driving along and suddenly I'm levitating and bouncing
        # like a ball"). Telemetry pinned it: at lapdist 6896 the car's speed doubled in one 0.2 s
        # tick (66 -> 131 km/h), lapdist ran BACKWARDS, and it flew 34 m sideways in 1.2 s. That is
        # a bump3d! collision impulse, not terrain — and there was nothing on screen to hit.
        #
        # THE RENDER FILTER AND THE COLLISION FILTER DISAGREED, AND THE DISAGREEMENT WAS INVISIBLE
        # BY CONSTRUCTION. `house25` sits at lapdist 6899 with its FOOTPRINT reaching 1.6 m of the
        # centreline. The renderer drops it (onroad_fp, a footprint test, E69-S5/E71-S16), so the
        # road looks clear. This loop tested only the ORIGIN (`on_road(i.x, i.y, ...)`) — the same
        # origin-vs-footprint mistake the render path was fixed for and this one never was — so the
        # origin sat off-road, the object stayed solid, and `house` carries a 5.0 m radius. An
        # invisible 5 m collision disc across the racing line.
        #
        # The invariant: IF IT IS NOT DRAWN, IT MUST NOT BE SOLID. Anything the render path removes
        # for being on the road is removed here too, by the same predicates rather than by a
        # parallel test that can drift out of agreement again.
        # JM_SOLID_KEEP_HIDDEN=1 restores the old behaviour for A/B.
        if get(ENV,"JM_SOLID_KEEP_HIDDEN","0") == "0"
            (onroad_fp(i) || onroad_bldg(i) || onroad_crowd(i) || perp_crowd(i)) && continue
            # E87-S2 (found BY the gate, at Zandvoort): the on-road predicates above were only
            # PART of what the render drops. OBJECTS also requires a mesh, survives drop(), and
            # is TALLER THAN 1 m -- and SOLIDS applied none of those, so:
            #   bushes01/02/03  x158  mesh=YES, not dropped, but UNDER 1 m -> never rendered,
            #                         yet solidR gives `bush*` a 1.5 m collision radius.
            #   hotels          x1    dropped by the junk filter, still solid (the SPA shape).
            #   ftruck/rescu*         no mesh at all -> cannot render, still solid.
            # 175 of Zandvoort's 269 solids were invisible. The invariant is the same one E71-S18
            # wrote for the on-road case -- IF IT IS NOT DRAWN, IT MUST NOT BE SOLID -- so mirror
            # the render's OWN conditions rather than inventing a parallel test that can drift.
            # ⚠️ EXEMPT CLASSES ARE VISIBLE BY ANOTHER PATH AND MUST STAY SOLID. The first cut of
            # this applied the mesh/drop/height tests to EVERYTHING and removed 157 of Spa's 808
            # solids -- including all 125 `armco*` barriers, which render as TRACK GEOMETRY and so
            # have no object mesh. That would have made the barriers DRIVE-THROUGH: trading
            # invisible walls for missing collision, a quieter failure than the one being fixed.
            # The gate's own exempt list already knew these render elsewhere; honour it here.
            solid_exempt(n) = startswith(n,"armco") || startswith(n,"fence") || startswith(n,"rail") ||
                              startswith(n,"barrier") || startswith(n,"wall") || startswith(n,"bushrow") ||
                              startswith(n,"haie")
            # ⚠️ ONLY JUDGE OBJECTS THAT COULD HAVE BEEN MESHES. BILLBOARDS is built AFTER this
            # loop (line ~2569), so a meshless object cannot be checked here -- it may well be a
            # billboard, i.e. VISIBLE. The first cut removed meshless objects too and took Spa's
            # `bush`/`bush2` with it: those are billboard-rendered (they showed up in the gate's
            # ANCHOR bucket, meaning drawn elsewhere), and the PO explicitly wants bushes hittable
            # ("more objects hittable when you run wide -- soft, you plough through with a
            # penalty", E15). Removing collision from something the player can SEE is the same
            # class of error as the armco regression one step earlier.
            # So: judge only has-mesh objects. Meshless ones stay solid and the gate keeps
            # REPORTING them -- an honest non-zero rather than a silent removal. Closing that gap
            # properly means building SOLIDS after BILLBOARDS (E87-S3).
            if !solid_exempt(nml) && get(objmesh, i.name, nothing) !== nothing
                drop(i.name) && continue
                (get(ymx,i.name,0f0) - get(ymn,i.name,0f0)) > 1.0f0 || continue
            end
        end
        push!(SOLIDS, (Float64(i.x), Float64(i.y), r, solidkind(nml)))
        push!(SOLIDNAMES, nml)   # E56: tag wall vs hedge/hay for the contact law
    end
    if get(ENV,"JM_SOLIDDIAG","")!=""
        # E95h: report what is ACTUALLY in SOLIDS. The previous version of this block recomputed
        # its own list from `solidR(...) > 0.0`, so it could not see the mesh-shape rule and kept
        # printing "tower×2" while SOLIDS held 14 -- a diagnostic disagreeing with the thing it
        # describes is worse than none, since it is the instrument used to judge every fix here.
        cnt = Dict{String,Int}(); for n in SOLIDNAMES; cnt[n]=get(cnt,n,0)+1; end
        println("== JM_SOLIDDIAG ", length(SOLIDS), " solids (", _geomn, " candidates from the shape rule): ",
                join(["$(n)×$(c)" for (n,c) in sort(collect(cnt))], ", "))
        # and why the shape rule turned the others down, grouped by reason
        rej = Dict{String,Vector{String}}()
        for (n,why) in _geomwhy
            startswith(why,"SOLID") && continue
            k = split(why)[1]; push!(get!(rej, k, String[]), n)
        end
        for (k,v) in sort(collect(rej))
            sort!(v)
            println("   shape rule rejected ", rpad(k,7), " ×", rpad(length(v),4), " e.g. ", join(v[1:min(end,8)], " "))
        end
        flush(stdout)
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
    tstamp("  [E80] .. OBJECTS built; billboard/tree loop begins")
    global BILLBOARDS = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32}[]
    global STATICTREES = Tuple{Render.Item,NTuple{3,Float32},Float32,Float32,Float32}[]
    for i in insts
        bb = get(bbinfo, i.name, nothing); (bb === nothing || drop(i.name)) && continue
        # E79: a crowd ROW is metres wide, so testing its ORIGIN answers the wrong question — the
        # same origin-vs-footprint mistake the mesh path was fixed for (E69-S5) and this one never
        # was. A sprite of width w centred on the origin reaches w/2 either side, so admit it only
        # if the WHOLE row clears the road, with a margin. The PO's instruction is deliberately
        # generous ("if there's any chance"), so this errs toward removal.
        if standcrowd(i.name)
            _w = 0.0
            let b = get(bbinfo, i.name, nothing)
                b !== nothing && (_w = Float64(b[5]) > 0 ? Float64(b[5]) : 0.0)
            end
            _hr = JuliaMotor.hat(TRKSURF, Float64(i.x), Float64(i.y))
            # ⚠️ Project the row's extent onto the ROAD NORMAL, not straight off the lateral.
            # A crowd row runs ALONG the track, so its width lies parallel to the road and
            # contributes almost nothing across it. The first version subtracted w/2 unconditionally
            # and dropped 700 rows at Spa -- a 40 m row sitting 25 m away scored as 5 m from the
            # centreline. That would have stripped the crowds and recreated the PO's own "objects
            # were simply removed" complaint from the Ring, i.e. traded one visible defect for the
            # other one they had already reported.
            _reach = 0.0
            if _hr.found
                _ry = Float64(i.yaw) - atan(-_hr.perp[2], _hr.perp[1])
                _reach = (_w/2) * abs(sin(_ry))      # 0 when parallel, w/2 when across the road
            end
            if _hr.found && abs(_hr.lateral) - _reach < ROAD_HALFW + 1.5
                get(ENV,"JM_CROWDROW_DIAG","") != "" &&
                    println("  E79: crowd row ", i.name, " reaches ", round(abs(_hr.lateral)-_reach, digits=1),
                            " m of the centreline (origin ", round(abs(_hr.lateral),digits=1),
                            ", width ", round(_w,digits=1), ", across-road reach ",
                            round(_reach,digits=1), ") — dropped")
                continue
            end
        end
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
    tstamp("  [E80] .. billboard/tree loop done")
    # Named instance table (name, world-x, world-z, base-y, kind, dropped?) for the JM_START_S
    # spot diagnostic — lets a mid-lap render report exactly which authored objects sit near the
    # car, even when their CENTROID is >13 m off-centreline but the mesh spans the road (E52: the
    # wide grandstand/wall whose centroid clears the on_road filter yet its extent blocks the track).
    # (name, world-x, world-z, base-y, RENDER fate, is-SOLID).  The fate mirrors the SAME filters that
    # build OBJECTS / BILLBOARDS / SOLIDS — drop(), onroad_crowd, on_road and onground — so the JM_SWEEP
    # harness sees exactly what is actually rendered / collidable (not the raw instance list).
    # NB store world-z in the PHYSICS / HAT / .trk frame (= GPL y, NOT the render frame's −y) so the
    # JM_SWEEP / JM_SPOT projections onto TRKSURF/CLINE match the on_road classifier exactly.
    # ---- E87 GATE: a collidable object must never be INVISIBLE -------------------------------
    # The class behind the PO's Spa levitate (E86/E71-S18) and the Ring underpasses: the RENDER
    # filter and the COLLISION filter drift apart, and the result is undetectable by looking — the
    # only way to find an invisible wall is to drive into it. It has now happened three times.
    #
    # ⚠️ THIS DELIBERATELY DOES NOT RE-TEST onroad_fp/onroad_bldg/... . Re-running the same
    # predicates the fix uses would pass BY CONSTRUCTION and could never catch the NEXT filter
    # someone adds without updating SOLIDS. Instead it compares the two FINAL SETS: every SOLID
    # must coincide with something actually submitted for RENDER (a mesh in OBJECTS or a sprite in
    # BILLBOARDS). Predicate-independent, or it is not a gate.
    #
    # Negative control, and it is measured: JM_SOLID_KEEP_HIDDEN=1 restores the pre-fix behaviour
    # and MUST make this report violations (27 at Spa). A gate that cannot fail proves nothing.
    if get(ENV,"JM_SOLIDGATE","") != ""
        q(v) = round(Int, v / 0.5)                       # 0.5 m quantisation: same object, same cell
        drawn = Set{Tuple{Int,Int}}()
        for o in OBJECTS;    p4 = o[4]; push!(drawn, (q(p4[1]), q(-p4[3]))); end
        for b in BILLBOARDS; pb = b[2]; push!(drawn, (q(pb[1]), q(-pb[3]))); end
        bad = Tuple{Float64,Float64,Float64,Symbol}[]
        for sd in SOLIDS
            (q(sd[1]), q(sd[2])) in drawn || push!(bad, sd)
        end
        # name the offenders by nearest instance, for a report that says WHAT is invisible
        nameat(x, z) = begin
            best = ""; bd = 4.0
            for i in insts
                d = hypot(Float64(i.x) - x, Float64(i.y) - z)
                d < bd && (bd = d; best = i.name)
            end
            best
        end
        # ⚠️ A POSITION MISS IS NOT PROOF OF INVISIBILITY. The first run of this gate reported 139
        # "violations" at Spa and every one was an armco barrier or a bush -- NOT the houses the
        # fix was about. Those classes reach the screen by a render path this gate does not model
        # (track parts / differently-anchored sprites), so a position-only test calls them
        # invisible when they are plainly on screen. Splitting by NAME separates the two cases:
        #   UNDRAWN  the name appears NOWHERE in the drawn sets -> genuinely not rendered (real)
        #   ANCHOR   the name IS drawn elsewhere -> our position match is wrong, not the object
        # Only UNDRAWN fails the gate. Reporting ANCHOR loudly keeps the blind spot visible
        # instead of hiding it behind a lowered threshold.
        drawnames = Set{String}()
        for o in OBJECTS;    push!(drawnames, String(o[5])); end
        for i in insts
            for b in BILLBOARDS
                if abs(Float64(b[2][1]) - Float64(i.x)) < 0.5 && abs(-Float64(b[2][3]) - Float64(i.y)) < 0.5
                    push!(drawnames, lowercase(i.name)); break
                end
            end
        end
        # EXEMPT CLASSES -- rendered as TRACK GEOMETRY, not as placed objects, so they are absent
        # from OBJECTS by design and are NOT invisible. The E87 spec allowed for exactly this
        # ("either renders, or is on an explicit exempt list"); the first two runs measured which
        # classes need to be on it. Rails/fences are extracted with the track mesh (see the
        # "rail/fence dedup" line during geometry extraction), and bushrow* likewise.
        # ⚠️ KEEP THIS LIST SHORT AND JUSTIFIED. Every entry is a hole in the gate: an exempt class
        # could go genuinely invisible and this would not notice. It exists so the gate can be
        # TRUSTED on the classes it does cover -- buildings above all, which is the class that
        # actually caught the PO at Masta -- not so the number can be made to look good.
        exempt(n) = startswith(n,"armco") || startswith(n,"fence") || startswith(n,"rail") ||
                    startswith(n,"barrier") || startswith(n,"wall") || startswith(n,"bushrow") ||
                    startswith(n,"haie")
        undrawn = Tuple{String,Float64,Float64}[]; anchor = Dict{String,Int}(); exempted = Dict{String,Int}()
        for b in bad
            n = lowercase(nameat(b[1], b[2])); n = isempty(n) ? "(unnamed)" : n
            if exempt(n);      exempted[n] = get(exempted,n,0)+1
            elseif n in drawnames; anchor[n] = get(anchor,n,0)+1
            else push!(undrawn, (n, b[1], b[2])); end
        end
        println("== JM_SOLIDGATE ", TRACKSEL, ": ", length(SOLIDS), " solids, ", length(drawn),
                " drawn cells -> ", length(undrawn), " UNDRAWN-BUT-SOLID (",
                length(anchor), " anchor classes / ", sum(values(anchor); init=0), " objs, ",
                sum(values(exempted); init=0), " track-geometry exempt)")
        if !isempty(undrawn)
            cnt = Dict{String,Int}()
            for (n,_,_) in undrawn; cnt[n] = get(cnt,n,0)+1; end
            for (n,c) in sort(collect(cnt)); println("     INVISIBLE: ", n, " ×", c); end
        end
        if !isempty(exempted)
            println("     (exempt: rendered as TRACK GEOMETRY, not placed objects -- gate does not cover these:)")
            for (n,c) in sort(collect(exempted)); println("       ", n, " ×", c); end
        end
        if !isempty(anchor)
            println("     (anchor-mismatch classes, drawn elsewhere -- gate blind spot, NOT a defect:)")
            for (n,c) in sort(collect(anchor)); println("       ", n, " ×", c); end
        end
        # E87-S2: WHY is each undrawn name undrawn? Three yes/no facts settle it without another
        # guess. OBJECTS requires `objmesh[name] !== nothing`, so a name with NO MESH can never be
        # in it and could only ever have been a billboard. `drop(name)` is the render junk filter.
        # If a name has a mesh AND is not dropped AND is still undrawn, it is genuinely invisible.
        if !isempty(undrawn) && get(ENV,"JM_SOLIDGATE_WHY","") != ""
            seen = Set{String}()
            println("     ---- why undrawn (name: has-mesh / dropped / billboard-name) ----")
            for (n,_,_) in undrawn
                n in seen && continue; push!(seen, n)
                # objmesh is keyed by the ORIGINAL-case name; find one inst that matches
                orig = ""; for i in insts; lowercase(i.name) == n && (orig = i.name; break); end
                hasmesh = !isempty(orig) && get(objmesh, orig, nothing) !== nothing
                dropped = !isempty(orig) && drop(orig)
                inbb    = n in drawnames
                println("       ", rpad(n, 12), "  mesh=", hasmesh ? "YES" : "no ",
                        "  dropped=", dropped ? "YES" : "no ", "  billboard-name=", inbb ? "YES" : "no ",
                        hasmesh && !dropped ? "   <-- GENUINELY INVISIBLE" : "")
            end
        end
        get(ENV,"JM_SOLIDGATE_EXIT","") != "" && exit(isempty(undrawn) ? 0 : 1)
    end

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
    if get(ENV,"JM_OBJFIND","") != ""
        # E72-S4: does a named object EXIST in the placement list, and what happened to it?
        # Watkins' archive holds pit.3do / tower1.3do yet no pit building renders, and JM_OBJDIAG's
        # lists are truncated (top 25 / top 22) so absence from them proves nothing. OBJINSTS carries
        # every instance with the fate the render filters gave it -- search that directly. It
        # distinguishes "never placed in the track data" from "placed and dropped", which need
        # entirely different fixes. JM_OBJFIND=pit|tower|grand
        let pat = _ofre = Regex(replace(get(ENV,"JM_OBJFIND",""), "," => "|"), "i")
            hits = [i for i in OBJINSTS if occursin(pat, String(i[1]))]
            println("== JM_OBJFIND /", get(ENV,"JM_OBJFIND",""), "/i -- ", length(hits), " placed instances ==")
            if isempty(hits)
                println("(none matched -- either not placed, OR the PATTERN did not match: it is a REGEX, so use pit|tower|grand. E72-S10: commas are now accepted as alternation, but a pattern that cannot match is indistinguishable from an absent object -- check a name you KNOW is placed before trusting a null.)")
            else
                for h in hits[1:min(end,20)]
                    hr = JuliaMotor.hat(TRKSURF, Float64(h[2]), Float64(h[3]))
                    # E72-S6: report the VERTICAL too. Watkins' pit structures are placed, kept, and
                    # invisible at their own lapdists (E72-S5), and lateral offset does not explain
                    # tower1 at 26.9 m. Objects here are SNAPPED to our terrain rather than their
                    # authored GPL height, so a snap that lands wrong buries them — which would make
                    # them invisible whatever their lateral position. base − ground says so directly.
                    gz = groundz(h[2], h[3])
                    dz = gz > -900f0 ? round(Float64(h[4]) - Float64(gz), digits=1) : NaN
                    println("   ", rpad(h[1],14), "fate=", rpad(String(h[5]),9), "solid=", rpad(h[6],7),
                            hr.found ? string("lapdist=", rpad(round(hr.lapdist,digits=0),9),
                                              "lat=", rpad(round(hr.lateral,digits=1),8)) : rpad("off-ribbon",19),
                            "base=", rpad(round(Float64(h[4]),digits=1),8),
                            gz > -900f0 ? string("ground=", rpad(round(Float64(gz),digits=1),8),
                                                 "Δ=", dz, dz < -1.0 ? "  *** BURIED ***" : "")
                                        : "OFF-HAT")
                end
                length(hits) > 20 && println("   ... ", length(hits)-20, " more")
            end
            flush(stdout)
        end
        # E69-S9: the listing is capped, so a truncated sample cannot be used to judge how much is
        # being dropped. Summarise EVERY match by fate.
        let tot = Dict{Symbol,Int}()
            for oi in OBJINSTS
                occursin(_ofre, oi[1]) || continue
                tot[oi[5]] = get(tot, oi[5], 0) + 1
            end
            println("   -- all matches by fate: ", join(["$(k)=$(v)" for (k,v) in sort(collect(tot), by=x->-x[2])], "  "))
        end
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
        println("== JM_CROWDDIAG crowd rows (lat NaN = off the road ribbon = out on the dunes; relyaw ±90 = PERPENDICULAR) ==")
        for (nm,lat,ld,ry) in cr; println("   ", rpad(nm,12), "lat=", rpad(lat,8), " lapdist=", rpad(ld,8), " relyaw=", ry); end
        # E88: `insts` is the RAW placement list (built ~line 1857, long before drop() exists), so
        # the count above is rows PLACED, not rows KEPT -- it cannot move when a drop rule changes.
        # It was labelled "kept" and read that way: the E88 before/after census came back 52 -> 52
        # and looked like a fix that did nothing, when it was a measurement that could not respond.
        # Report both, and say which is which.
        nkept = count(i -> standcrowd(i.name) && !drop(i.name), insts)
        println("   (", length(cr), " crowd rows PLACED)")
        println("   (", nkept, " crowd rows KEPT after drop())"); flush(stdout)
    end
end

println(length(OBJECTS), " trackside objects + ", length(BILLBOARDS), " billboards + ", length(STATICTREES), " forest panels + ", length(SOLIDS), " solid (collidable)"); flush(stdout)
if get(ENV,"JM_HAT_COUNT","0") != "0"
    st = JuliaMotor.hat_stats()
    print("[hat] ", st.calls, " calls in the placement block")
    get(ENV,"JM_HAT_TIME","0") != "0" && print("  total ", round(st.total_s,digits=2), " s  ",
                                               round(st.per_call_us,digits=2), " us/call")
    println(); flush(stdout)
    JuliaMotor.HAT_COUNT_ON[] = false
end
tstamp("  [E80] trackside objects/billboards/trees DONE")
end


# E70-S5: JM_TEXDIAG lived inside the GPL-object branch too, so it never ran on the Ring —
# the same trap E70/E75-S9 hoisted three road censuses out of. Moved to top level.

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

carItems   = Render.build_gpl(CARP, GPLTEX)        # Lotus body, GPL .mip textures
pipeItems  = Render.build_gpl(PIPEP, GPLTEX)       # E106-S4: exhausts, drawn lifted (see PIPEP)
axleItems  = Render.build_gpl(AXLEP, GPLTEX)       # E106-S9: straight synthesized driveshafts
carItemsIn = isempty(CARPIN) ? Render.Item[] : Render.build_gpl(CARPIN, GPLTEX)  # E106-S5: cockpit-view body
# PO 2026-08-27: "remove the cockpit gauge panel, hands and sleeves". JM_GAUGE=0 hides the cluster
# (hands + sleeves are JM_HANDS=0, which already existed).
# E106-S7 (PO video 2026-09-02): "spurious enlarged dashboard floating over visor blocking the
# driver's view of the road". That was the E74 gauge BILLBOARD -- the separately-lifted dash7a
# cluster -- still drawn on top of the REAL dash that arrived with the lotd cockpit (S6). Two
# dashboards, one of them floating. The billboard now defaults OFF whenever the lotd cockpit is
# active; JM_GAUGE=1 forces it back (and it remains the dash for JM_COCKPIT_DRESS=0).
gaugeItems = (get(ENV,"JM_GAUGE", get(ENV,"JM_COCKPIT_DRESS","1") != "0" ? "0" : "1") == "0") ?
    Render.Item[] : Render.build_gpl(GAUGEP, GPLTEX)
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
tstamp("  [E80] mirrors + wheels begin")
const MIRROR_RTT = get(ENV,"JM_MIRROR_RTT","1") != "0"    # JM_MIRROR_RTT=0 → old static silver discs
const MIRW, MIRH = 384, 192
(mirfbo, mirtex) = MIRROR_RTT ? Render.make_mirror_fbo(MIRW, MIRH) : (GLuint(0), GLuint(0))
const MIRROR_EVERY = parse(Int, get(ENV,"JM_MIRROR_EVERY","3"))   # E80: mirror RTT refresh interval
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
# E75-S16: ONE lateral correction, tested against BOTH ends of the car at once.
# E75-S15 established that this is a placement problem, not a content one: 14 of 17 rear parts sit
# outboard of the hub line (0.772 m), and the FRONT assembly -- different parts entirely -- reaches
# the same outer bound to within 13 mm (1.121 vs 1.117). Two assemblies landing on the same wrong
# number is one systematic placement, so the honest test is one number applied to both, not a part
# list edited per end.
# Shift each vertex TOWARD the centreline by JM_SUSP_INBOARD metres, sign-aware, never past zero.
# Predicted by S15: front 0.59..1.13 -> 0.29..0.83, rear 0.43..1.12 -> 0.13..0.82 -- inner pickups
# near the gearbox, outer ends just inside the 0.89 m wheel face, which is where gold keeps them.
# Default 0.0 = OFF, so this ships inert until the picture agrees with the arithmetic.
const SUSP_INBOARD = parse(Float32, get(ENV,"JM_SUSP_INBOARD","0.0"))
function susp_inboard(parts)
    SUSP_INBOARD == 0f0 && return parts
    out = Render.TrackPart[]
    for pp in parts
        v = copy(pp.verts)
        for k in 1:11:length(v)-2
            z = v[k+2]
            # move toward 0 by the shift, but never through it (a part straddling the centreline
            # would otherwise fold inside out, which reads as "the fix made it worse" rather than
            # "the fix was applied to the wrong thing")
            v[k+2] = z > 0 ? max(z - SUSP_INBOARD, 0f0) : min(z + SUSP_INBOARD, 0f0)
        end
        push!(out, Render.TrackPart(v, pp.tex, pp.col))
    end
    out
end
if get(ENV,"JM_SUSP_INBOARD_DIAG","") != ""
    for (nm, ps) in (("FSUSPP", FSUSPP), ("RSUSPP_A", RSUSPP_A), ("RSUSPP_B", RSUSPP_B))
        for (tag, q) in ((" before", ps), (" after ", susp_inboard(ps)))
            lo = Inf32; hi = -Inf32
            for pp in q, k in 1:11:length(pp.verts)-2
                z = abs(pp.verts[k+2]); lo = min(lo, z); hi = max(hi, z)
            end
            println("   [inboard] ", rpad(nm,10), tag, "  |z| ", round(lo,digits=3), " … ", round(hi,digits=3))
        end
    end
    # Exit HERE. The car parts are built at ~line 2770, well after JM_BOUNDARY_TEST's exit (1077)
    # and JM_OVERHANG_EXIT's (~2200), so neither of the existing headless exits can reach this --
    # the first run printed nothing at all for exactly that reason. A diagnostic that cannot be
    # reached by any harness is a diagnostic that will be read as "no output means no problem".
    flush(stdout); exit(0)
end

fsuspItems  = Render.build_gpl(susp_inboard(FSUSPP), GPLTEX)     # front suspension wishbones (visible through the screen)
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
# E106-S2: dress the wheels with GPL's own tyre art (see the wheel_dress comment in render.jl).
# Per-corner texture sets read off the GPL wrapper 3DOs (llftire0/lrftire0/llrtire0/lrrtire0):
# fronts tread with loftex1, rears with lortex1; the lettered outer face (l1out) goes on the
# OUTBOARD side, which is +y for the left wheels and -y for the right (verified by capture -- the
# Firestone lettering must face out, as in gold). JM_WHEEL_DRESS=0 restores the flat grey wheels.
# E106-S6: the wheels now load through GPL'"'"'s own WRAPPER 3DOs (llftire0 …), which bind the
# texture-slot table the slot selectors (0x20) resolve -- tread, both faces and the spinner land
# exactly as authored, replacing S2'"'"'s geometric dress. LOD0 = the hires texture set. Geometry
# matches the old lotw* meshes to a millimetre (radius 0.312 vs 0.311). JM_WHEEL_WRAP=0 restores
# the S2 path (mesh + geometric dress).
const WHEEL_WRAP = get(ENV, "JM_WHEEL_WRAP", "1") != "0" ? Dict(
    "lotwlf" => "llftire0", "lotwrf" => "lrftire0",
    "lotwlr" => "llrtire0", "lotwrr" => "lrrtire0") : Dict{String,String}()
const WHEEL_DRESS = Dict(
    "lotwlf" => ("l1out", "l1in", "loftex1"), "lotwrf" => ("l1in", "l1out", "loftex1"),
    "lotwlr" => ("l1out", "l1in", "lortex1"), "lotwrr" => ("l1in", "l1out", "lortex1"))
load_wheel(nm) = haskey(WHEEL_WRAP, nm) ?
    Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR, WHEEL_WRAP[nm]*".3do");
                    exclude=("ltraymap","lshad"), tint=(TYRE_ALB,TYRE_ALB,TYRE_ALB+0.02f0)), GPLTEX) :
    Render.build_gpl(Render.extract_gpl_car(joinpath(LOTDIR,nm*".3do");
                    exclude=("ltraymap","lshad"), tint=(TYRE_ALB,TYRE_ALB,TYRE_ALB+0.02f0),
                    wheel_dress=get(WHEEL_DRESS, nm, nothing)), GPLTEX)
const WHEELITEMS = Dict(nm => load_wheel(nm) for nm in ("lotwlf","lotwrf","lotwlr","lotwrr"))
tstamp("  [E80] wheel models loaded")
swItems = Render.build_gpl(SWPARTS, GPLTEX)        # steering wheel (rotated with steer)
handItems = Render.build_gpl(HANDP, GPLTEX)        # E64 S2: gloved hands (cockpit view, rotate with the wheel)
armItems  = Render.build_gpl(ARMP, GPLTEX)         # E64 S2: forearms (cockpit view, static)
rsusp2Items = Render.build_gpl(RSUSPP2, GPLTEX)     # E75-S8: rear suspension taken directly, no fold
rsuspItemsA = Render.build_gpl(susp_inboard(RSUSPP_A), GPLTEX)   # E64 S7: high-detail rear suspension halves (chase view)
rsuspItemsB = Render.build_gpl(susp_inboard(RSUSPP_B), GPLTEX)
# Corrective transform per side (E64 S8, settled by the POSITIONER-CHAIN DUMP): the chain to each
# half is [park d=(0,20,0) → clamped 0] · [LOD selectors] · [hub placement d=(−0.893, ±0.772, 0.02),
# yaw 2°, s=1.0] — so scale IS 1.0 and the hub translations are honoured; what remains is that the
# assemblies are AUTHORED in a flat horizontal pose (identity capture: wings splayed flat outward)
# and must fold ~90° about the HUB LINE (z=±0.772 — S7's 0.35 pivot was mid-driveshaft, hence the
# under-fold/backward-fan artifacts).  50° vs 90° A/B'd near-identical from the chase (tyres +
# gearbox occlude); 90° kept as the geometrically-motivated flat→vertical value.  JM_RS_* A/B.
# E82-S1: rsfix lives in demo/native/susp_pose.jl, shared with tools/susp_pose_smoke.jl so the gate
# tests the transform the sim actually applies. Measured: the positioner-placed geometry is already
# correctly posed (identity fits 84% of the rear suspension vertices in the hub-to-chassis envelope;
# no rotation fits better), and the 90-degree fold puts every rear part 1.2-1.9 m UNDER the road.
rsfix(side) = SuspPose.rsfix(side, Render.translate, Render.rotx, Render.scalexyz)
# which extracted group is which side is settled empirically: JM_RS_SWAP=1 flips the pairing
const RS_SWAP = get(ENV,"JM_RS_SWAP","0") != "0"
const RSFIX_A = rsfix(RS_SWAP ? -1 : 1)
const RSFIX_B = rsfix(RS_SWAP ? 1 : -1)
# ── E106-S7 / E102 FIX: CLIP THE REAR HALVES IN THE FRAME THEY ARE DRAWN IN ────────────────────
# The PO's "axles projecting improbably down and outward from the rear tires" (video,
# 2026-09-02) survived every mesh-frame trim because the trim ran BEFORE RSFIX: E82-S3 clips
# |lateral| at the wheel plane in MESH coordinates, then the fix matrix rotates the half -- so
# clipped geometry still lands outside the wheel and below the hub after the transform. Proven by
# A/B: JM_RSUSP=0 removes the sticks and nothing else.
# So the transform is BAKED into the vertices at load and the clip runs on the DRAWN positions:
# nothing survives outside the wheel plane (|z| > WTRACK_R + tyre halfwidth) or below the hub line
# (y < -0.30, i.e. under the axle by more than a link's depth). The draw then uses identity.
# JM_RS_BAKECLIP=0 restores the old order for A/B.
# zmax = the wheel-centre plane exactly, ymin = 12 cm under the hub line: the E102 rods angle
# down-forward INSIDE the old looser envelope (they pierce the wheels visually without exceeding
# them laterally), so the clip has to hug the hub. The real driveshaft/link geometry lives within
# a link-depth of the hub line; anything deeper is the mis-posed rod.
function _bake_clip(parts, M; zmax=Float32(WTRACK_R), ymin=-0.12f0)
    out = Render.TrackPart[]
    R = [M[r,c] for r in 1:3, c in 1:3]
    for p in parts
        v = p.verts; n = length(v) ÷ 33
        keep = Float32[]
        for t in 0:n-1
            base = t*33
            ok = true
            tv = zeros(Float32, 33)
            for k in 0:2
                o = base + k*11
                x=v[o+1]; y=v[o+2]; z=v[o+3]
                tx = Float32(M[1,1]*x+M[1,2]*y+M[1,3]*z+M[1,4])
                ty = Float32(M[2,1]*x+M[2,2]*y+M[2,3]*z+M[2,4])
                tz = Float32(M[3,1]*x+M[3,2]*y+M[3,3]*z+M[3,4])
                (abs(tz) > zmax || ty < ymin) && (ok = false)
                nx=v[o+4]; ny=v[o+5]; nz=v[o+6]
                tv[k*11+1]=tx; tv[k*11+2]=ty; tv[k*11+3]=tz
                tv[k*11+4]=Float32(R[1,1]*nx+R[1,2]*ny+R[1,3]*nz)
                tv[k*11+5]=Float32(R[2,1]*nx+R[2,2]*ny+R[2,3]*nz)
                tv[k*11+6]=Float32(R[3,1]*nx+R[3,2]*ny+R[3,3]*nz)
                tv[k*11+7]=v[o+7]; tv[k*11+8]=v[o+8]
                tv[k*11+9]=v[o+9]; tv[k*11+10]=v[o+10]; tv[k*11+11]=v[o+11]
            end
            ok && append!(keep, tv)
        end
        isempty(keep) || push!(out, Render.TrackPart(keep, p.tex, p.col))
    end
    out
end
const RS_BAKECLIP = get(ENV,"JM_RS_BAKECLIP","1") != "0"
if RS_BAKECLIP
    global rsuspItemsA = Render.build_gpl(_bake_clip(susp_inboard(RSUSPP_A), RSFIX_A), GPLTEX)
    global rsuspItemsB = Render.build_gpl(_bake_clip(susp_inboard(RSUSPP_B), RSFIX_B), GPLTEX)
end
# E64 S8: ON by default — the positioner-chain dump settled the transform (hub-line fold; see
# rsfix above); the gold nintendo chase shows this articulated rear end, so it ships.
# E75-S13: the rear parts are all <= 1.04 m and correctly placed, so the broad chrome "panels" cannot
# be oversized geometry — they must be shading. spec=0.25 on near-flat faces reads as a mirror plate.
const RS_SPEC = parse(Float32, get(ENV,"JM_RS_SPEC","0.25"))
# E106-S7 / E102 RESOLVED-BY-REMOVAL (PO video 2026-09-02: "axles still projecting improbably
# down and outward from rear tires"). The sticks are the rsuspItemsA/B rear-half sets: JM_RSUSP=0
# removes exactly them and nothing else (rsusp2Items was ALREADY default-off, so it was never the
# source -- an earlier "coincident copies" reading of the A/Bs was wrong and is corrected here).
# Clip-based fixes cannot work: in the body frame the rods sit at legitimate hub heights spanning
# ordinary lateral range -- the POSE (angle) is wrong, not the position, so any clip tight enough
# to cut the rods also cuts real links. Until the halves are re-posed, absence beats wrongness --
# the clean rear reads far closer to gold's fine wishbones than the rods did. JM_RSUSP=1 restores.
# E106-S29: still OFF. The re-pose attempt in that sprint was measured against the UNCLIPPED
# group geometry and was wrong; the production extraction already reaches the hub. See the backlog.
const RSUSP_ON = get(ENV,"JM_RSUSP","0") != "0"
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
if get(ENV,"JM_RSUSP_WORLD","") != ""
    # E75-S12: E75-S9 left a contradiction — every part in the rear groups measures <= 1.04 m, yet
    # drawing them at identity renders spears reaching metres past the wheels. bodyModel is a rigid
    # transform and cannot stretch anything, so if the geometry is compact BEFORE and AFTER RSFIX the
    # spears cannot come from this geometry at all, and S9 misattributed them.
    bb(parts) = begin
        lo = [Inf32,Inf32,Inf32]; hi = [-Inf32,-Inf32,-Inf32]
        for pp in parts, i in 1:11:length(pp.verts)-10
            for k in 1:3
                v = pp.verts[i+k-1]
                v < lo[k] && (lo[k] = v); v > hi[k] && (hi[k] = v)
            end
        end
        (lo, hi)
    end
    xf(parts, M) = [begin
        v = copy(pp.verts)
        for i in 1:11:length(v)-10
            x,y,z = v[i],v[i+1],v[i+2]
            v[i]   = M[1,1]*x + M[1,2]*y + M[1,3]*z + M[1,4]
            v[i+1] = M[2,1]*x + M[2,2]*y + M[2,3]*z + M[2,4]
            v[i+2] = M[3,1]*x + M[3,2]*y + M[3,3]*z + M[3,4]
        end
        (verts=v, tex=pp.tex)
    end for pp in parts]
    for (nm, parts, M) in (("RSUSPP_A raw", RSUSPP_A, nothing),
                           ("RSUSPP_A × RSFIX_A", RSUSPP_A, RSFIX_A),
                           ("RSUSPP_B raw", RSUSPP_B, nothing),
                           ("RSUSPP_B × RSFIX_B", RSUSPP_B, RSFIX_B))
        pl = M === nothing ? parts : xf(parts, M)
        lo, hi = bb(pl)
        println("   [rsusp] ", rpad(nm,22),
                " x ", rpad(string(round(lo[1],digits=2),"…",round(hi[1],digits=2)),16),
                " y ", rpad(string(round(lo[2],digits=2),"…",round(hi[2],digits=2)),16),
                " z ", rpad(string(round(lo[3],digits=2),"…",round(hi[3],digits=2)),16),
                " span ", round(max(hi[1]-lo[1], hi[2]-lo[2], hi[3]-lo[3]), digits=2), " m")
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
            zmn=Inf32; zmx=-Inf32; xmn=Inf32; xmx=-Inf32; ymn=Inf32; ymx=-Inf32
            for i in 1:11:length(pp.verts)-10
                x=pp.verts[i]; y=pp.verts[i+1]; z=pp.verts[i+2]
                zmn=min(zmn,z); zmx=max(zmx,z); xmn=min(xmn,x); xmx=max(xmx,x); ymn=min(ymn,y); ymx=max(ymx,y)
            end
            push!(rows, (pp.tex, n, zmn, zmx, xmx-xmn, ymx-ymn, zmx-zmn)); tot += n
        end
        println("== JM_CARGROUPS group ", g, ": ", length(rows), " parts, ", tot, " tris ==")
        # E75-S9: report the part's full 3-D SIZE too. E75-S8 found the textures it drew were flat
        # sheets (lsusp7: 0.03 m thick, 2.02 m wide) and concluded the rear parts are stored
        # UNFOLDED. That conclusion was drawn from the texture-selected set, not from these groups —
        # so print each group part's x/y/z extent and let the geometry say whether a real articulated
        # linkage exists in here or whether everything rear is flat.
        # E75-S9b: sort by SIZE, not triangle count, and print them all. Ranking by tri count hid
        # the parts that matter: the top-10-by-count listing showed nothing above 1.75 m, yet
        # rendering the group at identity spears the rear end several metres past the wheels. A part
        # that big must exist and was simply below the cut.
        for (tex,n,zmn,zmx,dx,dy,dz) in sort(rows, by=r->-max(r[5],r[6],r[7]))
            flat = (min(dx,dy,dz) < 0.06) ? "  FLAT" : "  3-D"
            mark = (tex in ("lshok","lsusp5","lsusp7","lsusp1","lbrdisc","frontlot") ? "   <<< MISSING FROM CARP" : "") *
                   string("   size ", round(dx,digits=2), "×", round(dy,digits=2), "×", round(dz,digits=2), flat)
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
    println("   texture       tris   longitudinal x     lateral z          height y           in CARP?  excluded by name?")
    rows = []
    for pp in allp
        local v = pp.verts; n = length(v) ÷ 11   # `local`: v shadows a global
        zmn=Inf32; zmx=-Inf32; ymn=Inf32; ymx=-Inf32; xmn=Inf32; xmx=-Inf32
        for i in 1:11:length(v)-10
            x=v[i]; y=v[i+1]; z=v[i+2]
            xmn=min(xmn,x); xmx=max(xmx,x)
            ymn=min(ymn,y); ymx=max(ymx,y); zmn=min(zmn,z); zmx=max(zmx,z)
        end
        push!(rows, (pp.tex, n, zmn, zmx, ymn, ymx, xmn, xmx))
    end
    for (tex,n,zmn,zmx,ymn,ymx,xmn,xmx) in sort(rows, by=r->-r[2])
        println("   ", rpad(tex,14), rpad(n,7),
                rpad(string(round(xmn,digits=2),"…",round(xmx,digits=2)),19),
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
tstamp("  [E80] track items counted")

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
tstamp("  [E80] AI car models begin")
# E85-S5: netplay needs a chassis to draw the remote car with, even when there is no AI field.
_ncars = max(N_AI, NETMODE == "" ? 0 : 1)
if !SKIDPAD && _ncars > 0
    for (nm, dir, body, w) in AISPECS[1:_ncars]
        print("  loading AI car: $nm … "); flush(stdout)
        # E106-S20 (PO: "at least one AI car has 3 outward-facing metal rods attached to each rear
        # tire"). The AI chassis were loaded at maxlat=0.9 while the PLAYER uses CARP_MAXLAT=0.85 --
        # and that 0.85 is documented as "skinny clip (garbage-free)", the value chosen precisely
        # because a wider clip "exposes the GPL-hidden spider-leg suspension". So every AI car kept a
        # band the player car throws away. Measured tris beyond 0.85: Ferrari 32, BRM 204,
        # Brabham 227, Eagle 309, Cooper 537 -- the PO's "at least one" is all five, worst on the
        # Cooper. Use the player's clip; JM_AI_MAXLAT overrides for A/B.
        push!(AICARMODELS, Render.load_gpl_car(nm, joinpath(AIBASE,dir), body, aiwheels(w...);
                              exclude=("ltraymap","lshad"),
                              maxlat=parse(Float32, get(ENV,"JM_AI_MAXLAT", string(CARP_MAXLAT))),
                              body_floor=BODY_FLOOR))
        println("$(length(AICARMODELS[end].body)) parts")
    end
end
const PROJ = Render.perspective_revz(deg2rad(62f0), Float32(W/H), 0.35f0, 3000f0)  # reversed-Z: near-uniform depth precision → kills distant z-fight (signs on fences)
tstamp("  [E80] AI car models done / projection")
# GPL's cockpit uses a WIDE field of view — the mirrors sit at the screen edges and you see lots of road.
# A separate wide projection for the cockpit view (tunable via JM_FOV) reproduces that immersive look.
const PROJ_COCKPIT = Render.perspective_revz(deg2rad(parse(Float32,get(ENV,"JM_FOV","80"))), Float32(W/H), 0.20f0, 3000f0)

# ---- input: edge-detected shift, view + auto-gearbox toggle ----
mutable struct Ctl; prevUp::Bool; prevDn::Bool; prevV::Bool; prevG::Bool; prevM::Bool; prevRec::Bool; view::Int; auto::Bool; cluWarned::Bool; end
# shift mode: AUTO by default (auto-clutch + auto-shift) — press throttle and GO, the car never bogs
# on the line or out of a slow corner.  Press G in-app for MANUAL (work the clutch on C, shift E/Q —
# release the clutch too low and it crawls/bogs, just like the real thing).  ZAND_SHIFT=manual forces it.
const CTL = Ctl(false,false,false,false,false,false, parse(Int, get(ENV,"JM_VIEW","1")), get(ENV,"ZAND_SHIFT","auto") != "manual", false)   # view 1=chase 0=cockpit; AUTO gearbox by default (G toggles)
key(k) = GLFW.GetKey(win, k) == GLFW.PRESS
const JOYREPORT = Ref(false)
const JOYTRACE_T = Ref(-1.0)
function read_input()
    thr=brk=str=clu=0.0; up=dn=false
    js = GLFW.GetJoystickAxes(GLFW.JOYSTICK_1)
    if !JOYREPORT[] && js !== nothing && !isempty(js)
        JOYREPORT[] = true
        println("  [joy] ", length(js), " axes raw = ", join(round.(js, digits=2), ", "))
        _bs = GLFW.GetJoystickButtons(GLFW.JOYSTICK_1)
        println("        buttons = ", _bs === nothing ? "none" : string(length(_bs)),
                "   shift-up btn ", JOYMAP.up_btn, ", shift-down btn ", JOYMAP.dn_btn,
                "   clutch axis ", JOYMAP.clutch.axis)
        flush(stdout)
    end
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
    # PO 2026-08-27b: "manual gear shift doesn't work anymore; stuck in 1st, joystick click to shift
    # up does nothing". The realism gate below required the CLUTCH AXIS >= 0.4 to complete a manual
    # shift — and that axis is the X3D slider, the same lever whose "clutch out" position is required
    # for the car to drive at all. One lever cannot satisfy both, so whichever end it sits at, either
    # drive or shifting is dead. (Moving it to fix the throttle is what broke shifting.)
    # A shift button should shift. The clutch requirement is now OPT-IN: JM_CLUTCH_REQ=1 restores it,
    # and holding C still declutches for feel. MANUAL shifting works from the stick or E/Q regardless.
    # PO 2026-08-27b/c: I made this opt-in believing the clutch axis was blocking drive. It was not
    # (the raw axes show clutch = 0), and the PO then confirmed "I had forgotten to use the clutch —
    # when I use it, manual seems to work". So the original behaviour was right and the change was
    # unnecessary: RESTORED to required-by-default. JM_CLUTCH_REQ=0 drops the requirement.
    if get(ENV,"JM_CLUTCH_REQ","1") != "0"
        (!CTL.auto && (upE || dnE) && clu < 0.4) && (upE = false; dnE = false)
    end
    kv = key(GLFW.KEY_V); (kv && !CTL.prevV) && (CTL.view = 1-CTL.view); CTL.prevV = kv
    # E93 (PO 2026-08-29): "Make auto easy, I never use it so I don't care. Make manual right.
    # Require that the slider be down before you can enter manual mode."
    # Entering MANUAL with the slider UP means the clutch is already ENGAGED, which is how a real
    # car is left stalled -- and it is also the state that made the launch assist look like a
    # reversed axis. So refuse the switch and say why. Leaving MANUAL is always allowed: you must
    # never be trapped in a mode you cannot exit.
    kg = key(GLFW.KEY_G)
    if kg && !CTL.prevG
        if CTL.auto && clu < 0.4
            CLUTCH_GATE[] = 2.0        # PO 2026-09-01: show it ON SCREEN for 2 s, not just here
            println("  [gearbox] staying in AUTO -- move the CLUTCH SLIDER to the DISENGAGED end ",
                    "before switching to MANUAL. Slider is at ", round(clu, digits=2), " (need > 0.4). ",
                    "The on-screen bar shows the axis and the threshold.")
            flush(stdout)
        else
            CTL.auto = !CTL.auto
            println("  [gearbox] ", CTL.auto ? "AUTO" : "MANUAL — the clutch slider is yours; no launch assist")
            flush(stdout)
        end
    end
    CTL.prevG = kg
    km = key(GLFW.KEY_M); (km && !CTL.prevM) && (ENG.master[] = ENG.master[]>0 ? 0.0 : 0.7); CTL.prevM = km
    # R = respawn at the start; SHIFT+R (GPL) = recover onto the centreline at the CURRENT lap position
    # (upright, stopped) so you can rejoin from the grass/a spin without teleporting to the line.  recover
    # is EDGE-triggered (one drop per press); both set `rst` so the per-frame respawn guards still apply.
    rkey  = key(GLFW.KEY_R); shift = key(GLFW.KEY_LEFT_SHIFT) || key(GLFW.KEY_RIGHT_SHIFT)
    recover = rkey && shift && !CTL.prevRec; CTL.prevRec = rkey && shift
    rst = (rkey && !shift) || recover
    # PO 2026-08-27: "pressing forward on the joystick causes the car to drift backward or stay
    # still; W has no effect" — with brake and steering working. Cause: the X3D SLIDER (axis 4) is
    # mapped to the CLUTCH, so a slider parked at the engaged end holds the clutch fully in. The
    # engine revs (1953 rpm on the title bar) and no drive reaches the wheels, which is exactly what
    # was seen. AUTO gearbox advertises an auto-clutch, so in AUTO the stick's clutch axis is now
    # ignored; the C key still works for a deliberate clutch. JM_JOYCLUTCH=1 restores the old
    # behaviour, and MANUAL mode is unchanged.
    # PO 2026-08-27, later the same day: "I like the clutch attached to a slider - that way I can
    # ride the clutch. The clutch should be an axis."
    #
    # The AUTO override that used to sit here is REMOVED. It zeroed the clutch axis whenever the
    # gearbox was in AUTO, which meant pressing G — a GEARBOX control — silently threw the driver's
    # clutch away. The PO's telemetry caught it exactly: clutch 1.00 while stationary, then 0.00 in
    # the same tick as the first throttle, and the car pulled away with the clutch held in.
    #
    # It was added this morning to explain "pressing forward on the joystick does nothing": the X3D
    # slider had been left at the clutch-IN end, so the car correctly refused to drive. That is a
    # PARKED CONTROL, not a broken axis, and the right answer is to say so rather than to disable
    # the axis — disabling it fixed the symptom by removing the feature the PO actually wants.
    # So: the axis is always honoured, in both modes, and the car warns ONCE if the clutch is held
    # in at a standstill with throttle applied, which is the state that looks like "it won't move".
    # E93 (PO 2026-08-29: "starting from stationary in 1st, the clutch is reversed -- the slider has
    # to be DOWN to start; slider UP prevents the car from moving. As soon as the car moves in first,
    # the slider sense reverses."). Every mapping I can check says the sense is CONSTANT:
    #   slider UP -> clu~0 -> s_clu(0) = ENGAGED;  slider DOWN -> clu~1 = DISENGAGED
    #   the shift gate below requires clu >= 0.4 (disengaged), which matches "I can only shift with
    #   the slider at the bottom", and the .ibt export writes 1-clu, so a coast at slider-up records
    #   Clutch=1.0 (iRacing convention: 1 = pedal released = engaged).
    # I could NOT reproduce an inversion by reading the code, so rather than "fix" a mapping that is
    # consistent everywhere -- which would silently invalidate the E91 captures -- make it OBSERVABLE.
    # JM_TRACE_CLUTCH=1 prints the derived clu on every material change; a standstill launch then
    # answers the question from data. Module-level Ref, NOT a CTL field: CTL's fields are fixed and
    # assigning a new one throws.
    CLU_NOW[] = clu                      # E98: published every frame, unconditionally -- CLU_LAST
                                         # only moves when JM_TRACE_CLUTCH is on and cannot be used
    if get(ENV,"JM_TRACE_CLUTCH","0") != "0" && abs(clu - CLU_LAST[]) > 0.05
        println("  [clutch] clu=", round(clu, digits=2),
                "   (0 = ENGAGED / slider up,  1 = DISENGAGED / slider down)   throttle ",
                round(thr, digits=2))
        flush(stdout)
        CLU_LAST[] = clu
    end
    if clu > 0.9 && thr > 0.2 && !CTL.cluWarned
        CTL.cluWarned = true
        println("  [clutch] held IN (", round(clu,digits=2), ") with throttle — the engine will rev ",
                "but the car will not move. If you are not holding it, the slider (axis 4) is parked ",
                "at the clutch-in end; move it to the other end to release.")
        flush(stdout)
    end
    (DriveInput(throttle=clamp(thr,0,1), brake=clamp(brk,0,1), steer=clamp(str,-1,1),
                clutch=(WRECKED[] ? 1.0 : clu),        # E95: wrecked = engine PERMANENTLY disconnected
                shift_up=(WRECKED[] ? false : upE), shift_down=(WRECKED[] ? false : dnE),
                autoshift=(WRECKED[] && false) || CTL.auto), rst, recover)
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

# E75-S9 / E70: these road censuses used to live INSIDE the GPL-object branch, so they never ran on
# the Nürburgring or skidpad at all. Two sprints (E71-S13, E69-S6) recorded the Ring as "not
# measured — load + census exceeds the run window"; that was wrong both times, and a clean exit with
# no output was read as a timeout instead of as an unreachable block. E70-S2 had already fixed this
# exact class for the on-road censuses; these three were missed. Hoisted out so every track reports.

if get(ENV,"JM_ROADTEX_CENSUS","")!=""
  let   # E75-S9: own scope — at top level these loops shadowed globals (px/py/b/nrt)
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
    # E73-S8: the same tally, but LOCALISED. The global census says 86% of Monza's
    # near-centreline tris are recognised, yet JM_ROADWIDTH still reports 0.6 m at s=5500 and
    # nothing at all at s=500/4500 — so the misses are not spread evenly, they are concentrated
    # where the surface changes (pit straight, start grid). Name the textures actually present at
    # the suspect lapdists rather than reasoning from a lap-wide percentage.
    # JM_ROADTEX_AT="500,4500,5500"
    if get(ENV,"JM_ROADTEX_AT","") != ""
        want = [parse(Float64,x) for x in split(ENV["JM_ROADTEX_AT"], ",")]
        for w in want
            loc = Dict{String,Int}(); nrec = 0; ntot = 0
            for t in TRACKMESH.tris
                cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
                cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
                hr = JuliaMotor.hat(TRKSURF, cx, cy)
                (hr.found && abs(hr.lapdist - w) < 125.0 && abs(hr.lateral) < 12.0) || continue
                lt = lowercase(t.tex); loc[lt] = get(loc,lt,0)+1
                ntot += 1; ROAD_TEX(lt) && (nrec += 1)
            end
            println("   -- lapdist ", round(Int,w), " ±125 m, |lat|<12 m: ", ntot, " tris, ",
                    nrec, " recognised as road --")
            for (nm,c) in sort(collect(loc), by=x->-x[2])[1:min(end,8)]
                println("        ", rpad(nm,14), rpad(c,6), ROAD_TEX(nm) ? "road" : "*** not road ***")
            end
            isempty(loc) && println("        (NO triangles at all within 12 m of the centreline)")
        end
    end
    # E69-S6: the recognition PERCENTAGE is not a quality metric. Zandvoort scores 73.6% and is
    # fine — everything it misses is grass, dune sand, fence and armco, all correctly excluded —
    # while Spa scored 43.9% and was badly wrong, because what it missed (`borcem`, 5431 on-road
    # vs 1029 off) was genuinely road. What matters is whether any MISSED texture is
    # predominantly ON the racing surface. Say so directly instead of leaving it to be eyeballed.
    suspect = [(nm, c, get(far,nm,0)) for (nm,c) in near
               if !ROAD_TEX(nm) && c >= 60 && c/(c + get(far,nm,0) + 1e-9) >= 0.65]
    sort!(suspect, by=x->-x[2])
    println("== E69-S6 VERDICT: missed textures that are mostly ON the racing surface ==")
    if isempty(suspect)
        println("   none — every unrecognised surface here is predominantly off-road (grass /")
        println("   sand / fence / barrier). The classifier is sound for this track regardless")
        println("   of the headline percentage.")
    else
        println("   ⚠️ these look like ROAD and are being excluded:")
        # E69-S6b: a texture can read "on-road" for the WRONG reason — if the centreline strays
        # onto the verge at that corner, verge triangles project to small |lateral|. Report WHERE
        # each suspect lives and how close to the centreline it actually gets, so a location check
        # is possible before anything is added to the classifier.
        for (nm,on,off) in suspect
            sd = Float64[]; lt2 = Float64[]
            for t in TRACKMESH.tris
                lowercase(t.tex) == nm || continue
                cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
                cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
                hr = JuliaMotor.hat(TRKSURF, cx, cy); hr.found || continue
                push!(sd, hr.lapdist); push!(lt2, abs(hr.lateral))
            end
            loc = isempty(sd) ? "?" : string(round(Int,minimum(sd)), "–", round(Int,maximum(sd)), " m")
            nearest = isempty(lt2) ? NaN : minimum(lt2)
            med = isempty(lt2) ? NaN : sort(lt2)[cld(length(lt2),2)]
            println("      ", rpad(nm,14), "on ", rpad(on,6), "off ", rpad(off,6),
                    rpad(string(round(100*on/(on+off), digits=1),"%"),8),
                    " lapdist ", rpad(loc,16),
                    " nearest |lat| ", rpad(round(nearest,digits=1),6),
                    " median |lat| ", round(med,digits=1))
        end
    end
    # E69-S6c: the same location check applied to textures the classifier ACCEPTS — including the
    # four E71-S13 added. If an accepted texture also sits at the road EDGE, it was added for the
    # same bad reason the suspects above were rejected for.
    if get(ENV,"JM_TEXLAT","") != ""
        println("== JM_TEXLAT: where the ACCEPTED road textures actually sit ==")
        for nm in split(ENV["JM_TEXLAT"], ",")
            lt3 = Float64[]
            for t in TRACKMESH.tris
                lowercase(t.tex) == lowercase(nm) || continue
                cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
                cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
                hr = JuliaMotor.hat(TRKSURF, cx, cy)
                hr.found && abs(hr.lateral) < 25.0 && push!(lt3, abs(hr.lateral))
            end
            if isempty(lt3)
                println("   ", rpad(nm,12), "(none)")
            else
                sort!(lt3)
                println("   ", rpad(nm,12), "n=", rpad(length(lt3),7),
                        "median |lat| ", rpad(round(lt3[cld(end,2)],digits=1),7),
                        "p25 ", rpad(round(lt3[max(1,cld(end,4))],digits=1),7),
                        ROAD_TEX(lowercase(nm)) ? "ACCEPTED" : "rejected")
            end
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
    end   # let
end

if get(ENV,"JM_ROADWIDTH","")!=""
  let   # E75-S9: own scope — at top level these loops shadowed globals (px/py/b/nrt)
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
    println("   ⚠️ E73-S8: this census samples road VERTICES inside a ±", halfb,
            " m LONGITUDINAL slice, so on a coarsely-meshed track (Monza, Watkins) a station can")
    println("      hold no vertices at all, or only the narrow `groove` strip's. Use JM_ROADWIDTH2")
    println("      (coverage) for any width verdict; this one is kept only to reproduce old numbers.")
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
                "   (⚠️ the old 'gold Spa ~11 m' reference is UNVERIFIED — E71-S13)")
    end
    flush(stdout)
    end   # let
end

if get(ENV,"JM_ROADWIDTH2","")!=""
  let   # E75-S9: own scope — at top level these loops shadowed globals (px/py/b/nrt)
    # E73-S8: JM_ROADWIDTH measures the lateral spread of road VERTICES inside a ±12 m
    # LONGITUDINAL slice at each station. That is why it returns nonsense on Monza and Watkins
    # and looked fine on Spa: it samples vertices, not surface. Monza's straights are meshed with
    # very large triangles, so a 24 m slice can contain NO road vertices at all (buckets 500 and
    # 4500 simply vanish) or only two from the narrow `groove` strip (0.6 m at s=5500) — while
    # the captures show perfectly good asphalt at every one of those stations. Spa's road mesh is
    # dense, so its vertices happen to land in every slice and the number came out right for the
    # wrong reason.
    # Measure COVERAGE instead: march laterally across the centreline and ask, for each offset,
    # whether any road TRIANGLE covers that point. Triangle size then cannot matter.
    stepS = parse(Float64, get(ENV,"JM_ROADWIDTH2_STEP","250.0"))
    maxlat = parse(Float64, get(ENV,"JM_ROADWIDTH2_MAXLAT","22.0"))
    dlat  = 0.25
    rt = [t for t in TRACKMESH.tris if ROAD_TEX(lowercase(t.tex))]
    # bucket road tris by centroid lapdist so each station tests only nearby ones
    cls = Dict{Int,Vector{Any}}()
    for t in rt
        cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
        cy = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3
        hr = JuliaMotor.hat(TRKSURF, cx, cy); hr.found || continue
        push!(get!(cls, round(Int, hr.lapdist/100.0), Any[]), t)
    end
    intri(px,py,t) = begin
        ax,ay = Float64(t.p[1][1]), Float64(t.p[1][2])
        bx,by = Float64(t.p[2][1]), Float64(t.p[2][2])
        cx2,cy2 = Float64(t.p[3][1]), Float64(t.p[3][2])
        d = (by-cy2)*(ax-cx2) + (cx2-bx)*(ay-cy2)
        abs(d) < 1e-12 && return false
        l1 = ((by-cy2)*(px-cx2) + (cx2-bx)*(py-cy2))/d
        l2 = ((cy2-ay)*(px-cx2) + (ax-cx2)*(py-cy2))/d
        l3 = 1.0 - l1 - l2
        l1 >= -1e-9 && l2 >= -1e-9 && l3 >= -1e-9
    end
    println("== E73-S8 road width by COVERAGE (road tris=", length(rt), ", step ", stepS, " m) ==")
    println("   lapdist   left    right   WIDTH   gaps")
    widths = Float64[]
    nst = max(1, floor(Int, LAPLEN/stepS))
    for k in 0:nst
        sdist = k*stepS
        # centreline point + perpendicular at this lapdist, from the aligned polyline
        bi = argmin([abs(TRKSURF.lapdist[i] - sdist) for i in 1:length(TRKSURF.lapdist)])
        p0 = ALIGNED[min(bi, length(ALIGNED))]
        p1 = ALIGNED[min(bi+1, length(ALIGNED))]
        tx, ty = Float64(p1[1]-p0[1]), Float64(p1[2]-p0[2])
        L = hypot(tx,ty); L < 1e-6 && continue
        nx, ny = -ty/L, tx/L
        cand = Any[]
        for kk in (round(Int,sdist/100.0)-1):(round(Int,sdist/100.0)+1)
            haskey(cls,kk) && append!(cand, cls[kk])
        end
        isempty(cand) && continue
        cov = Bool[]
        lats = collect(-maxlat:dlat:maxlat)
        for lt in lats
            px = Float64(p0[1]) + nx*lt; py = Float64(p0[2]) + ny*lt
            hit = false
            for t in cand; if intri(px,py,t); hit = true; break; end; end
            push!(cov, hit)
        end
        any(cov) || continue
        # the contiguous covered run containing the centreline (or the widest run)
        i0 = findfirst(x->x, cov); i1 = findlast(x->x, cov)
        mid = cld(length(cov),2)
        lo, hi = mid, mid
        if cov[mid]
            while lo > 1 && cov[lo-1]; lo -= 1; end
            while hi < length(cov) && cov[hi+1]; hi += 1; end
        else
            lo, hi = i0, i1
        end
        w = (hi-lo)*dlat
        ngap = count(i -> !cov[i] && cov[i-1], 2:length(cov))
        push!(widths, w)
        println("   ", rpad(round(Int,sdist),9), rpad(round(lats[lo],digits=1),8),
                rpad(round(lats[hi],digits=1),8), rpad(round(w,digits=1),8), ngap)
    end
    if !isempty(widths)
        st = sort(widths)
        println("   --> median ", round(st[cld(end,2)],digits=1), " m   min ", round(minimum(widths),digits=1),
                "   max ", round(maximum(widths),digits=1), "   stations ", length(widths), "/", nst+1)
    end
    flush(stdout)
    end   # let
end


# ---- main loop (in a function — avoids top-level soft scope, runs faster) ----
function main()
    # E106-S13b: the physics-facing ground closure. It converts the app's -999 "off the HAT"
    # SENTINEL into NaN, because drive_rt3d guards only `isfinite` and -999 is finite -- a wheel
    # over a hole was told the ground lay 999 m below, sank toward it, and the correction on
    # re-acquiring terrain launched the car (the PO's Nurburgring levitation; E106-S13).
    # Defined HERE rather than beside `groundz`: that spot is inside a nested block main() cannot
    # see, so the name resolved as a missing global and threw at RUNTIME -- parse_smoke cannot
    # catch that, and the suite's gates do not run this path. Caught by driving the sim.
    groundz_phys(x, y) = (g = groundz(x, y); g > -900f0 ? g : NaN32)
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
    # E106-S14 (PO: "ensure nurburgring and spa can be driven without obstacles"): census the
    # terrain HOLES along the whole lap instead of discovering them by crashing into one. Walks the
    # centreline and samples the physics ground across the corridor the car can actually reach; a
    # sample with no surface is a hole. E106-S13 made holes survivable -- this says how many there
    # are, which is the honest measure of a track's readiness. JM_HOLECENSUS=<half-width m>.
    if CLINE !== nothing && get(ENV,"JM_HOLECENSUS","") != ""
        halfw   = parse(Float64, get(ENV,"JM_HOLECENSUS","12"))
        step_s  = parse(Float64, get(ENV,"JM_HOLECENSUS_DS","10"))
        latstep = 1.5
        nlat = Int(floor(2*halfw/latstep)) + 1
        println("== JM_HOLECENSUS ", TRACKSEL, ": ground coverage ±", halfw, " m of the centreline, every ", step_s, " m ==")
        total = 0; holes = 0; worst_s = -1.0; worst_n = -1; badstations = 0
        holelist = Tuple{Float64,Int}[]
        sacc = 0.0
        while sacc < CLINE.total
            nhole = 0
            for k in 0:nlat-1
                lat = -halfw + k*latstep
                # pose_at returns (x, y, z, θ) and applies the lane offset itself -- use it rather
                # than recomputing the normal (and do not mistake y for z, which indexing (x,y,z,θ)
                # as (x,z) silently does).
                pp = RaceAI.pose_at(CLINE, sacc, lat)
                h = JuliaMotor.hat3d(TERRAIN, Float64(pp[1]), Float64(pp[3]); ref=Inf)
                total += 1
                h[3] || (holes += 1; nhole += 1)
            end
            nhole > 0 && (badstations += 1)
            nhole > worst_n && (worst_n = nhole; worst_s = sacc)
            nhole > 0 && push!(holelist, (sacc, nhole))
            sacc += step_s
        end
        println("   samples=", total, "  holes=", holes, " (", round(100*holes/max(total,1), digits=2), "%)",
                "   stations with any hole: ", badstations)
        println("   worst station: s=", round(worst_s, digits=1), " m with ", worst_n, " of ", nlat, " lateral samples missing")
        # the WORST TEN, so a driveability failure at a given s can be cross-referenced against the
        # terrain rather than guessed at (a single "worst" figure cannot be cross-referenced).
        sort!(holelist, by = x -> -x[2])
        println("   worst ten stations (s → missing/", nlat, "):")
        for (ss, nn) in holelist[1:min(10, end)]
            println("      s=", lpad(round(ss, digits=1), 9), "  ", lpad(nn, 3), " missing")
        end
        flush(stdout)
    end
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
    # E77-F: name the surfaces stacked over the racing line at given lapdists. JM_SWEEP reports THAT
    # the collision height jumps (Ring: +13.3 m at s=22250 then -35.3 m at 22300); this reports WHAT
    # is there, by walking the raw track mesh and listing every triangle whose XZ projection contains
    # the centreline point, with its height and texture. That is what a targeted collision exclusion
    # needs -- `drop_overpass` cannot be used here, because the Ring has bridges you genuinely drive
    # OVER and it would drop those too. JM_BRIDGEPROBE="21540,22250,22300"
    if CLINE !== nothing && get(ENV,"JM_BRIDGEPROBE","") != ""
        println("== JM_BRIDGEPROBE: surfaces over the racing line ==")
        for tok in split(get(ENV,"JM_BRIDGEPROBE",""), ",")
            sv = tryparse(Float64, strip(String(tok))); sv === nothing && continue
            pz = RaceAI.pose_at(CLINE, sv, 0.0); qx = Float64(pz[1]); qz = Float64(pz[3])
            hits = Tuple{Float64,String}[]
            # ⚠️ TRACKMESH, not TRACKMESH0. On the Ring the scenery is MERGED into the collision
            # mesh (TRACKMESH = TRACKMESH0.tris ++ SECTRI) and TERRAIN is built from that. Probing
            # the raw track mesh reported "only asphalt and groove, no stacked surface" at every
            # underpass — a clean null that simply looked at the wrong mesh, and the same mistake
            # that made an earlier analysis conclude the deck was not in collision at all.
            for t in TRACKMESH.tris
                ax,az = Float64(t.p[1][1]), Float64(t.p[1][2])
                bx,bz = Float64(t.p[2][1]), Float64(t.p[2][2])
                cx,cz = Float64(t.p[3][1]), Float64(t.p[3][2])
                d = (bz-cz)*(ax-cx) + (cx-bx)*(az-cz); abs(d) < 1e-9 && continue
                wa = ((bz-cz)*(qx-cx) + (cx-bx)*(qz-cz))/d
                wb = ((cz-az)*(qx-cx) + (ax-cx)*(qz-cz))/d
                wc = 1 - wa - wb
                (wa >= -0.02 && wb >= -0.02 && wc >= -0.02) || continue
                h = wa*Float64(t.p[1][3]) + wb*Float64(t.p[2][3]) + wc*Float64(t.p[3][3])
                push!(hits, (h, lowercase(t.tex)))
            end
            sort!(hits, by=first)
            print("   s=", round(Int,sv), " at (", round(qx,digits=1), ",", round(qz,digits=1), "): ")
            if isempty(hits)
                println("NO surface (hole)")
            else
                println(length(hits), " surfaces, low..high:")
                for (h,tx) in hits
                    println("      h=", rpad(round(h,digits=2),9), " tex=", tx)
                end
            end
        end
        flush(stdout); exit(0)
    end
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
    # E84/E89 (2026-08-30): JM_AI_GPLLINE=1 -- the AI take their target speed from GPL's OWN race.lp
    # (3.0 m records, index-aligned with our line on tracks that are not re-centred). Measured
    # headlessly on Monza: κ-model free lap 122.9 s vs GPL 89.6 with 147 speed steps >1 m/s per 3 m;
    # with the GPL table 94.8 s and 2 steps. The lone-car "lunge ahead, then fall back" was our
    # racing-line curvature swinging R=153..745 m inside the constant R=304 Curva Grande. Only on
    # tracks whose centreline is the raw .trk (Monza, Zandvoort): re-centring shifts the dlat frame
    # and the dlong index with it. Says which file it used -- a silent fallback is the defect again.
    if AILINE !== nothing && get(ENV, "JM_AI_GPLLINE", "1") != "0"     # DEFAULT ON (S2): JM_AI_GPLLINE=0 reverts to the κ model
        if MONZA || ZANDV
            lp = joinpath(ZD, "race.lp")
            if isfile(lp)
                gv = GPLLP.lp_speed_mps(GPLLP.read_lp(lp))
                ini = joinpath(ZD, "track.ini"); adj = 1.0; vcap = 2.41*36.0
                if isfile(ini)
                    for l in eachline(ini)
                        m = match(r"^\s*dlong_speed_adj_coeff\s*=\s*([0-9.]+)", l); m !== nothing && (adj = parse(Float64, m[1]))
                        m = match(r"^\s*dlong_speed_maximum\s*=\s*([0-9.]+)", l);   m !== nothing && (vcap = parse(Float64, m[1])*36.0)
                    end
                end
                RaceAI.set_gpl_speeds!(min.(gv .* adj, vcap))
                println("  AI speed profile: GPL race.lp (", length(gv), " records, adj ", adj, ", cap ", round(vcap, digits=1), " m/s)  <- ", lp)
            else
                @warn "JM_AI_GPLLINE: no race.lp in $ZD -- AI keep the κ speed model"
            end
        else
            @warn "JM_AI_GPLLINE: $(TRACKSEL) is re-centred, so GPL's dlong index does not align -- AI keep the κ speed model"
        end
    end
    # E104(a) probe (JM_LINE_Y=1): is the AI LINE's stored elevation the same as the TERRAIN's?
    # AI cars are drawn at pose_at(...)[2] = line.y (the rail-follower path is the default, since
    # AI_PHYSICS is opt-in), while the player's car takes cs.y from the physics, which tracks the
    # terrain. If line.y sits above groundz, every AI car floats by that much and the player's does
    # not -- which is exactly what the PO reported and what the capture shows.
    if AILINE !== nothing && haskey(ENV, "JM_LINE_Y")
        n = length(AILINE.x); diffs = Float64[]
        for k in 1:max(1, n ÷ 200):n
            g = groundz(AILINE.x[k], AILINE.z[k])
            push!(diffs, AILINE.y[k] - Float64(g))
        end
        sort!(diffs)
        md = diffs[max(1, length(diffs) ÷ 2)]
        println("  [line_y] ", length(diffs), " samples  line.y - groundz:  min ",
                round(minimum(diffs), digits=3), "  median ", round(md, digits=3),
                "  max ", round(maximum(diffs), digits=3), " m")
        flush(stdout)
    end
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
    # E84-S2 (JM_PACEDIAG): WHY is the rail 35-55 % slower than the pace it is told to run?
    # AI_SCALE is absorbing that gap (watglen 1.44, zandvoort 1.35, monza 1.55), so it is a
    # modelling shortfall wearing a multiplier, not a driver-skill percentage.  step!'s defaults
    # are amax=11.0, vmax=74.0 (= 266 km/h) -- below 1967 GP top speed, and MOST binding at the
    # fastest circuit, which is exactly where the scale is worst.  Sweep vmax and see.
    # Prediction, stated before the first run: if vmax dominates, Monza improves >= 10 % and
    # Zandvoort <= 5 %.  Runs during load and exits -- no render loop.
    if AILINE !== nothing && haskey(ENV, "JM_PACEDIAG")
        println("\n==== JM_PACEDIAG  $(TRACKSEL)  (lap $(round(AILINE.total, digits=0)) m) ====")
        base = RaceAI.natural_laptime(AILINE)
        println("  default (amax=11.0, vmax=74.0):  ", round(base, digits=1), " s")
        for vm in (74.0, 80.0, 85.0, 90.0, 100.0)
            t = RaceAI.natural_laptime(AILINE; vmax = vm)
            println("    vmax=", lpad(round(Int,vm),3), " m/s (", lpad(round(Int,vm*3.6),3), " km/h): ",
                    lpad(round(t, digits=1), 6), " s   (", lpad(round(100*(base-t)/base, digits=1), 5), " % faster)")
        end
        for am in (11.0, 14.0, 18.0)
            t = RaceAI.natural_laptime(AILINE; amax = am)
            println("    amax=", lpad(round(Int,am),3), " m/s2            : ",
                    lpad(round(t, digits=1), 6), " s   (", lpad(round(100*(base-t)/base, digits=1), 5), " % faster)")
        end
        t_both = RaceAI.natural_laptime(AILINE; vmax = 90.0, amax = 14.0)
        println("    vmax=90 + amax=14            : ", round(t_both, digits=1), " s   (",
                round(100*(base-t_both)/base, digits=1), " % faster)")
        println("  target (REF_LAP) = ", round(AI_REFLAP, digits=1), " s;  gold .rpy fastest is quicker still")
        # E84-S3: SEPARATE the two candidate causes. _vtarget takes the MAXIMUM curvature over a
        # look-ahead horizon (v*2.2 m, ~150 m at speed) with NO distance weighting -- a corner 150 m
        # away limits you exactly as much as one you are in.  So a low vtarget can mean either
        #   (a) the CENTRELINE is noisy      -> local kappa is high everywhere, or
        #   (b) the HORIZON RULE is too blunt -> local kappa is fine, the horizon max is not.
        # Reporting both tells them apart.  Predicted before running: median vtarget 40-50 m/s,
        # < 10 % of the lap at vmax.
        let n = 600, amax = 11.0, vmax = 74.0
            ks = Float64[]; vloc = Float64[]; vhor = Float64[]
            for i in 0:n-1
                sdist = AILINE.total * i / n
                kloc = max(AILINE.κ[RaceAI._locate(AILINE, sdist)[1]], 1e-4)
                push!(ks, kloc); push!(vloc, clamp(sqrt(amax/kloc), 12.0, vmax))
                kh = kloc; off = 5.0
                while off <= 150.0                      # the horizon a car at ~68 m/s would use
                    kh = max(kh, AILINE.κ[RaceAI._locate(AILINE, sdist+off)[1]]); off += 6.0
                end
                push!(vhor, clamp(sqrt(amax/kh), 12.0, vmax))
            end
            q(v,p) = sort(v)[clamp(round(Int, p*length(v)), 1, length(v))]
            # E89 (PO: AI cars "dart around like june bugs, lunge ahead, then fall back").
            # PERCENTILES CANNOT SEE THIS. A vtarget that alternates fast/slow every sample has the
            # same distribution as a perfectly smooth one -- the difference is entirely in the
            # ORDER. E84 found the pace shortfall comes from centreline kinks created by
            # re-centring; a kinked line gives an oscillating vtarget, which is what darting IS.
            # So report the step-to-step change, not the spread.
            # PREDICTION, stated before the first run: a smooth racing line should give a median
            # |dv| well under 1 m/s between adjacent samples (~9.7 m apart at Monza). If the kinks
            # drive the darting, expect median |dv| > 2 m/s and a long tail of >10 m/s jumps.
            # E84-S5 follow-on: is the culprit NODE SPACING rather than lateral kinks?
            # sim.jl computes kappa = dtheta/ds over +/-ksmooth nodes. A tiny ds -- two nearly
            # coincident centreline nodes -- blows kappa up however smooth the line is laterally,
            # collapsing vtarget for ONE sample. The lateral second-difference clamp moved Monza
            # only 12 -> 10 steps >10 m/s (target was 0-2) and Watkins 10 -> 11, which is what you
            # would expect if the spikes are not lateral at all.
            # PREDICTION, stated before the first run: if spacing is the cause, the smallest node
            # gaps are << the median (p01 under ~0.5 m against a median of several metres), and the
            # nodes carrying the largest kappa are drawn from those smallest gaps.
            # AILine's node coordinates are x/z (y is elevation) -- NOT `pos`, which is FrenetTrack's
            # field name. The first cut used AILINE.pos and threw FieldError at runtime.
            let X = AILINE.x, Z = AILINE.z, nn = length(AILINE.x)
                dss = [hypot(X[mod1(i+1,nn)]-X[i], Z[mod1(i+1,nn)]-Z[i]) for i in 1:nn]
                qq(v,p) = sort(v)[clamp(round(Int, p*length(v)), 1, length(v))]
                ordk = sortperm(AILINE.κ, by=abs, rev=true)[1:min(20,nn)]
                println("\n  ---- E84-S5: centreline NODE SPACING (", nn, " nodes) ----")
                println("    ds m: p01 ", round(qq(dss,0.01),digits=3), "  p10 ", round(qq(dss,0.10),digits=3),
                        "  p50 ", round(qq(dss,0.50),digits=3), "  min ", round(minimum(dss),digits=4))
                println("    ds at the 20 highest-|kappa| nodes: median ",
                        round(sort([dss[i] for i in ordk])[10], digits=3), " m   min ",
                        round(minimum(dss[i] for i in ordk), digits=4), " m")
            end
            dvl = [abs(vloc[i+1]-vloc[i]) for i in 1:length(vloc)-1]
            dvh = [abs(vhor[i+1]-vhor[i]) for i in 1:length(vhor)-1]
            spacing = AILINE.total / n
            println("\n  ---- E89: vtarget STEP-TO-STEP change (sample spacing ", round(spacing,digits=1), " m) ----")
            println("    |dv| local  m/s: p50 ", round(q(dvl,0.50),digits=3), "  p90 ", round(q(dvl,0.90),digits=3),
                    "  max ", round(maximum(dvl),digits=2), "   >10 m/s: ", count(>(10.0), dvl), "/", length(dvl))
            println("    |dv| horizon m/s: p50 ", round(q(dvh,0.50),digits=3), "  p90 ", round(q(dvh,0.90),digits=3),
                    "  max ", round(maximum(dvh),digits=2), "   >10 m/s: ", count(>(10.0), dvh), "/", length(dvh))
            println("\n  ---- kappa / vtarget profile (", n, " samples round the lap) ----")
            println("    kappa  1/m : p10 ", round(q(ks,0.10),digits=5), "  p50 ", round(q(ks,0.50),digits=5),
                    "  p90 ", round(q(ks,0.90),digits=5), "  max ", round(maximum(ks),digits=5))
            println("    radius   m : p10 ", round(Int,1/q(ks,0.90)), "  p50 ", round(Int,1/q(ks,0.50)),
                    "  p90 ", round(Int,1/q(ks,0.10)), "   (p10 radius = the TIGHTEST decile)")
            println("    vtarget LOCAL  kappa only : p10 ", round(q(vloc,0.10),digits=1),
                    "  p50 ", round(q(vloc,0.50),digits=1), "  p90 ", round(q(vloc,0.90),digits=1),
                    "   at vmax: ", round(100*count(>=(vmax-0.1), vloc)/n, digits=1), " %")
            println("    vtarget HORIZON max (150m): p10 ", round(q(vhor,0.10),digits=1),
                    "  p50 ", round(q(vhor,0.50),digits=1), "  p90 ", round(q(vhor,0.90),digits=1),
                    "   at vmax: ", round(100*count(>=(vmax-0.1), vhor)/n, digits=1), " %")
            println("    => median speed cost of the horizon rule: ",
                    round(q(vloc,0.50)-q(vhor,0.50), digits=1), " m/s")
            println("    (a clean 1967 Monza line should be near-straight over most of the lap:",
                    " median radius >> 500 m, median vtarget at vmax)")
            # E84-S3b: the MEDIAN is healthy, so the damage is in the TAIL. Count physically
            # impossible corners: no 1967 GP circuit has a radius under ~40 m (Monaco's Loews is
            # ~12 m and is the tightest corner in F1 anywhere). Anything below that is a defect in
            # the line, and because _vtarget takes a 150 m forward MAX, one spike poisons the
            # 150 m before it as well.
            for rlim in (80.0, 40.0, 20.0, 10.0)
                klim = 1/rlim; c = count(>=(klim), ks)
                println("    radius < ", lpad(round(Int,rlim),3), " m: ", lpad(c,4), " / ", n,
                        " samples (", lpad(round(100*c/n, digits=1),5), " %)  -> vtarget ",
                        round(clamp(sqrt(11.0/klim),12.0,74.0), digits=1), " m/s")
            end
            worst = sortperm(ks, rev=true)[1:min(8,length(ks))]
            println("    worst spikes (lap distance m -> radius m):")
            for w in worst
                println("      s=", lpad(round(Int, AILINE.total*(w-1)/n),5), "  r=",
                        round(1/ks[w], digits=1), " m")
            end
        end
        exit(0)
    end
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
                DriveRT3D.step_car3d!(pc, thr, brk, st, 1/60; manual=false, groundz=groundz_phys)
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
        # E89: "AI cars dart around like june bugs, lunge ahead, then fall back" -- MEASURE it.
        # A fall-back is a speed DEFICIT against what a lone car does at the same place on the line
        # (a car braking for Ascari is not falling back). Episode = deficit > 5 m/s held > 0.5 s.
        # Darting = target-rail switches (engage+release) per car-lap. The counters name which
        # racecraft rule fired: match (speed-matching), qsnap (queued back a car length), sidepush.
        let (fs, fv) = RaceAI.free_speed_profile(AILINE; scale=AI_SCALE),
            ds = length(fs) > 1 ? fs[2]-fs[1] : 5.0
            RaceAI.aistat_reset!()
            AICARS2 = RaceAI.init_cars(AILINE, N; start_s = 30.0)
            for (i, c) in enumerate(AICARS2); c.pace = AICARS[i].pace; end
            deficit_ep = zeros(Int, N); ep_run = zeros(Int, N); worst = zeros(N); lapsdone = zeros(Int, N)
            frames = nsec*60
            for f in 1:frames
                RaceAI.step_field!(AICARS2, AILINE, 1/60; scale=AI_SCALE, player=(-1e9,0.0,100.0), rel=AI_REL)
                for (i, c) in enumerate(AICARS2)
                    k = clamp(floor(Int, mod(c.s, AILINE.total) / ds) + 1, 1, length(fv))
                    d = fv[k] - c.v
                    worst[i] = max(worst[i], d)
                    if d > 5.0; ep_run[i] += 1; if ep_run[i] == 30; deficit_ep[i] += 1; end
                    else; ep_run[i] = 0; end
                    lapsdone[i] = c.lap
                end
            end
            st = RaceAI.AISTAT; tl = max(1, sum(lapsdone))
            println("  [E89] field of $N over $(nsec)s, $(sum(lapsdone)) car-laps:")
            println("  [E89]   fall-back episodes (deficit >5 m/s for >0.5 s) per car: ", deficit_ep,
                    "  = ", round(sum(deficit_ep)/tl, digits=2), " per car-lap;  worst deficit per car (m/s): ", round.(worst, digits=1))
            println("  [E89]   rail switches: engage=", st.engage, " release=", st.release,
                    "  = ", round((st.engage+st.release)/tl, digits=2), " per car-lap")
            println("  [E89]   speed-match frames=", st.match, "  queue-snaps=", st.qsnap, "  side-pushes=", st.sidepush, "  mishaps=", st.mishap)
        end
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
    net_last = Ref(-1.0)          # E85-S5: last time a pose was sent (sim seconds)
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
    cd_t0      = Ref(-1.0)      # wall time the countdown began (-1 = not started)
    cd_left    = Ref(-1.0)      # seconds remaining, for the HUD (-1 = do not draw)
    # PO 2026-09-01: seconds remaining to show the clutch-gate bar after a refused G.
    CLUTCH_GATE = Ref(-1.0)
    ai_release = Ref(-1.0)          # PO head start: wall time at which the FIELD may launch
    launch_done = Ref(false)     # the initial standing-start getaway is over (car has reached speed once)
    # AI reference qual times: the paced target + a small per-car spread so the grid lines
    # up in chassis order (~0.35 s/slot at 87 s) rather than a dead heat.
    ai_quals = [AI_TGT * (1 + 0.004*(i-1)) for i in 1:length(AICARS)]
    ROW = 9.0; GRID_LANE = 2.2          # grid row gap (m) + 2-wide lane offset
    function form_grid!(qtime)
        order = RaceAI.grid_order(qtime, ai_quals)        # pole-first entrant ids (0 = player)
        # PO: force the human to the front, keeping the AI's own pace order behind.
        POLE && (order = vcat(0, filter(!=(0), order)))
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
        println(POLE ? "\n  ═══ GRID (you on POLE — JM_POLE) ═══" :
                isfinite(qtime) ? "\n  ═══ GRID (from your practice best) ═══" : "\n  ═══ GRID ═══")
        for (p, id) in enumerate(order)
            println("   P$p  ", id==0 ? (isfinite(qtime) ? "You — $(fmt_lap(qtime))" : "You (no practice lap)") : AICHASSIS[id].name)
        end
        println("  → You start P$prank of $(length(order)) — $(COUNTDOWN > 0 ? "wait for the countdown" : "floor it to launch the field")\n"); flush(stdout)
        prank
    end
    COUNTDOWN > 0 && HOLD_START && println("\n  COUNTDOWN START — ", round(Int, COUNTDOWN),
        " s on the clock, then GREEN for the whole field at once.")
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
    # PO 2026-08-27: this was hardcoded "zand_racer_" with a "@ Zandvoort" header on EVERY track,
    # so the Nurburgring run just recorded landed as zand_racer_*.txt claiming to be Zandvoort.
    # Telemetry that misnames its own track is worse than none: it is wrong in a file that outlives
    # the session and looks authoritative.
    telem = SMOKE ? nothing : open("$(TRACKSEL)_racer_$(round(Int,time())).txt", "w")
    telem !== nothing && write(telem,
        "# $(TRACKSEL)_racer telemetry — Lotus 49 @ $(TRACKSEL)\n# t\tlap\tlapdist\tkmh\tthr\tbrk\tsteer\tclu\tgear\trpm\tx\tz\tlat\talong\tontrack\n")
    println("\n  Drive:  W/S gas·brake   A/D steer   E/Q shift   C clutch   R respawn   ⇧R recover-to-track   V view   G auto⇄manual   M mute   Esc quit"); flush(stdout)
    println("  AUTO gearbox by default — just press the throttle and go (no clutch needed).  Press G for")
    println("  MANUAL: hold the clutch (C / stick button) to shift E/Q (release it too low and it bogs).")
    println("  Lap times top-left: white = last, green = best.  Telemetry → ./$(TRACKSEL)_racer_*.txt")
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
        # E106-S16: the timestep is WALL-CLOCK, so a headless run spins as fast as the CPU allows
        # and advances almost no SIM time per frame -- the driveability sweep covered 0.1 s of sim
        # time in thousands of frames. JM_FIXED_DT=<seconds> advances a fixed step instead, which
        # both lets a headless run cover a whole lap and makes it DETERMINISTIC (a gate that
        # depends on machine speed is not a gate). Unset = the shipped wall-clock behaviour.
        now = time()
        dt = FIXED_DT > 0 ? FIXED_DT : clamp(now-last, 0.0, 0.05)
        last = now
        inp, rst, recover = read_input()
        # ── E85-S6: HEADLESS AUTODRIVE (JM_AUTODRIVE=1) ─────────────────────────────────────────
        # There was no way to make the PLAYER's car move without a human: `JM_AI_TEST` drives the AI
        # field with no player at all, and every headless capture so far has been of a stationary
        # car. That is fine for a screenshot and useless for measuring netplay, where a car that is
        # not moving makes dead reckoning trivially exact -- an error of 0.000 that means nothing.
        # Reuse the AI's own controller against the centreline: same code the field drives with, so
        # this adds no second driving model to keep true.
        if AUTODRIVE && CLINE !== nothing
            let (s0, lat0) = RaceAI.project(CLINE, cs.x, cs.z)
                # ⚠️ The 10th argument is the YAW RATE, not a gain. I first passed a placeholder
                # 1.0 and the car never moved: the controller's anti-spin logic reads ~1 rad/s as a
                # car already sliding and cuts the throttle, so telemetry showed `thr 0.0 kmh 0.0`
                # while steer twitched -- the controller WAS running and correctly refusing to
                # accelerate a car it believed was spinning. Pass the real rate.
                # `cs` has no yaw-rate FIELD -- the model exposes it as a function,
                # DriveRT3D.yawrate3d (aliased AIyaw), which is what the AI field itself uses.
                # `cs.r` would have thrown FieldError at runtime; parse_smoke cannot see that.
                yawrate = try; y = AIyaw(cs); isfinite(y) ? y : 0.0; catch; 0.0; end
                thr, brk, st = RaceAI.controller(CLINE, s0, lat0, 0.0, AUTODRIVE_V,
                                                 cs.x, cs.z, cs.θ, cs.v, yawrate; power = 1.0)
                # E106-S15 (PO: "ensure nurburgring and spa can be driven without obstacles
                # (levitation, bouncing) etc on the part of the human driver"). While autodrive is
                # running the lap, WATCH for the three failures the PO named, per frame:
                #   * levitation -- the car's height above the ground under it exceeds AIR_MAX;
                #   * bounce     -- an upward velocity spike with no jump to explain it;
                #   * stuck      -- moving under STUCK_V for STUCK_S seconds ("a graze should scrub
                #                   you but not end your race").
                # Reported at exit as a verdict, so a lap either states it is clean or names where
                # and by how much it was not. JM_DRIVECHECK=1.
                if DRIVECHECK
                    # cs.y is the car's WORLD HEIGHT (it is what the replay records as the pose's
                    # y and what read back as 620.x at the Ring); cs.x/cs.z are the plan coords.
                    # The step comes from the car's own clock, not an assumed `dt` in scope.
                    step = max(Float64(cs.t) - DC[].lastt, 1e-4)
                    DC[].lastt = Float64(cs.t)
                    gh = groundz(cs.x, cs.z)
                    if gh > -900f0
                        air = Float64(cs.y) - Float64(gh)
                        if air > DC[].airmax; DC[].airmax = air; DC[].air_s = s0; end
                        if air > DC_AIR_MAX
                            DC[].air_bad += 1
                            # log each DISTINCT excursion (a new one only after coming back down),
                            # so the verdict names the SITES rather than one global maximum -- a
                            # single "worst" figure cannot be cross-referenced against the track.
                            if !DC[].inair && length(DC[].events) < 24
                                push!(DC[].events, (s0, air, cs.v*3.6, Float64(cs.x), Float64(cs.z)))
                            elseif DC[].inair && !isempty(DC[].events)
                                # track the PEAK of this excursion, not its onset: recording only
                                # the crossing value made a 9.4 m launch read as 0.84 m, which is
                                # an instrument that understates exactly the thing it is for.
                                (es, epk, ekmh, ex, ez) = DC[].events[end]
                                air > epk && (DC[].events[end] = (es, air, ekmh, ex, ez))
                            end
                            DC[].inair = true
                        elseif air < DC_AIR_MAX*0.5
                            DC[].inair = false
                        end
                    end
                    # Skip the first second: the car SETTLES onto the track at spawn, which is a
                    # legitimate one-frame height step (27.7 m/s on the Glen). Counting it made
                    # every run report a "bounce" at s=0 -- an instrument that always fails is as
                    # useless as one that never does.
                    if DC[].lastz != 0.0 && cs.t > DC_SETTLE_S
                        vz = (Float64(cs.y) - DC[].lastz) / step
                        if vz > DC[].vzmax; DC[].vzmax = vz; DC[].vz_s = s0; end
                        vz > DC_VZ_MAX && (DC[].vz_bad += 1)
                    end
                    DC[].lastz = Float64(cs.y)
                    if cs.v < DC_STUCK_V
                        DC[].stuck += step
                        if DC[].stuck > DC[].stuckmax; DC[].stuckmax = DC[].stuck; DC[].stuck_s = s0; end
                    else
                        DC[].stuck = 0.0
                    end
                    DC[].maxs = max(DC[].maxs, s0)
                end
                if AUTODRIVE_DIAG > 0 && (frames % AUTODRIVE_DIAG) == 0
                    println("  [auto] t=", round(cs.t,digits=1), " v=", round(cs.v*3.6,digits=1),
                            " km/h  thr=", round(thr,digits=2), " brk=", round(brk,digits=2),
                            " steer=", round(st,digits=2), " s=", round(s0,digits=1))
                    flush(stdout)
                end
                inp = DriveInput(throttle = clamp(thr, 0, 1), brake = clamp(brk, 0, 1),
                                 steer = clamp(st, -1, 1), clutch = inp.clutch,
                                 shift_up = false, shift_down = false, autoshift = true)
            end
        end
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
            cd_t0[] = cs.t                              # countdown starts when the grid forms
            cs.laps = 0; last_lap = 0.0; best_lap = 0.0; race_done = false; lap_t0 = cs.t
            launch_done[] = false                       # re-arm the launch assist for the actual race start
            FUEL_ON && (fuel[] = burn_lap * fuel_laps)   # always start the race on a FULL tank (no practice carry-over)
        end
        enterPrev = accelNow
        # COUNTDOWN start (PO 2026-08-31). While it runs, nobody moves and the HUD shows the
        # seconds; at zero the race goes green for the whole field at once, with no throttle gate --
        # that is the difference between a countdown and the old "green when you decide to go".
        if COUNTDOWN > 0 && HOLD_START && !race_go[] && phase[] == :race
            # Arm on the first race frame, whatever put us here. The first cut armed cd_t0 ONLY in
            # the practice->race transition, so with JM_POLE (no qualifying, grid formed up front)
            # it stayed -1, the countdown never ran -- and because a countdown also disables the
            # old throttle gate, the race could never go green at all. Caught on the grid, before
            # the PO was left sitting on it.
            cd_t0[] < 0 && (cd_t0[] = cs.t)
            cd_left[] = COUNTDOWN - (cs.t - cd_t0[])
            if cd_left[] <= 0
                cd_left[] = 0.0
                race_go[] = true; lap_t0 = cs.t
                ai_release[] = cs.t + AI_HEADSTART
                println("  → GREEN"); flush(stdout)
                for c in AICARS
                    rand() < 0.45 && (c.mishap = 0.4 + 1.4*rand())
                end
            end
        elseif race_go[] && cd_left[] >= 0
            # keep GO on screen for a moment after the start, then clear it
            cd_left[] = (cs.t - cd_t0[] - COUNTDOWN) < 1.5 ? 0.0 : -1.0
        end
        # green light: the field launches the moment you ask for throttle (standing start)
        if COUNTDOWN <= 0 && HOLD_START && !race_go[] && phase[] == :race && inp.throttle > 0.15
            race_go[] = true; lap_t0 = cs.t          # start the clock at the launch
            ai_release[] = cs.t + AI_HEADSTART        # PO head start: field held this long
            AI_HEADSTART > 0 && println("  → HEAD START: you go now, the field launches in ",
                                        round(AI_HEADSTART, digits=1), " s")
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
        # E93 (PO 2026-08-29): "Make manual right." This assist fired ONLY in MANUAL (!CTL.auto) and
        # replaced the driver's clutch with 0.0 (engaged) plus autoshift=true for every throttle
        # application below 12 km/h, latching launch_done for the session. That is what made the
        # slider look reversed at a standing start: the axis was not inverted, it was DISCARDED.
        # It also contradicted the PO's standing instruction ("I like the clutch attached to a
        # slider -- that way I can ride the clutch"), removing the axis at the one manoeuvre where
        # riding the clutch matters most.
        # AUTO is untouched and still launches itself (step_car3d!'s auto-clutch), which is what the
        # PO asked for: "make auto easy, I never use it so I don't care".
        # JM_LAUNCH_ASSIST=1 restores the old behaviour for an A/B.
        if race_go[] && !rst && !CTL.auto && !launch_done[] && inp.throttle > 0.05 &&
           get(ENV, "JM_LAUNCH_ASSIST", "0") != "0"
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
        # PO 2026-08-27c: throttle still does nothing from stick OR W, while brake and steering work.
        # My clutch diagnosis was wrong (the raw axes show clutch = 0). Stop reasoning from the code
        # and print what the car is actually being asked to do, once a second. JM_JOYTRACE=1.
        if get(ENV,"JM_JOYTRACE","") != "" && cs.t - JOYTRACE_T[] >= 1.0
            JOYTRACE_T[] = cs.t
            _js = GLFW.GetJoystickAxes(GLFW.JOYSTICK_1)
            println("  [trace] thr=", round(inp.throttle,digits=2), " brk=", round(inp.brake,digits=2),
                    " clu=", round(inp.clutch,digits=2), " steer=", round(inp.steer,digits=2),
                    " | gear=", cs.gear, " rpm=", round(Int,cs.rpm), " v=", round(cs.v*3.6,digits=1), "km/h",
                    " | raw=", _js === nothing ? "nil" : join(round.(_js,digits=2), ","),
                    " | auto=", CTL.auto, " race_go=", race_go[])
            flush(stdout)
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
        elseif rst; respawnX!(cs; groundz=groundz_phys); DriveRT3D.damage_reset!()   # E94-P4: a respawn is a NEW car, not a repaired one
        else
            # E56 ALL-MODELICA human car: feed the trackside spring-damper CONTACT force (wall = bounce,
            # hedge/hay = bury & stick) + last frame's draft drag-scale into the chassis ODE BEFORE the
            # step, so both are forces the solver INTEGRATES — no post-step bumpX!/containX! state hack.
            if CAR3D
                cfx = cfy = cmz = 0.0
                if !SKIDPAD && !rst
                    update_world_velocity!(cs, cs.x, cs.z, dt > 1e-4 ? dt : 1/60)   # E96-S2/S6: once per frame, before every contact test
                    (cfx, cfy, cmz, cpk, chard, cclose) = solid_contact(cs.x, cs.z, cs.θ, cs.v, dt > 1e-4 ? dt : 1/60)
                    # E95: a hard enough hit ends the race. Triggered on the contact PEAK, not on
                    # speed -- what wrecks a car is the impulse it absorbs, and a slow scrape into a
                    # hedge must never latch it. The impact direction is taken from the net contact
                    # force, which points outward from whatever was hit.
                    # E95b: the first cut watched ONLY solid_contact, so a hit on the WORLD-EDGE
                    # FENCE -- a separate force (BND_*) -- could never wreck the car. That is what
                    # the PO hit at 200 km/h, and why nothing fired.
                    hitpk = max(cpk, BND_PK[])
                    # E95c (PO 2026-08-29): "any off-track collision at all at high speed should
                    # total the car ... Sure, if it's a hedge that gets hit it's ok to just bury the
                    # car in the hedge." So the test is CONTACT-WITH-SOMETHING-HARD + SPEED, not a
                    # force threshold: a force threshold made totalling depend on how deep the
                    # penetration got that frame, which is why a 200 km/h hit could slip under it.
                    # Hedges (:soft) are excluded by construction -- they contribute to cpk but not
                    # to chard, so you still just bury the car in them.
                    # E99 (PO 2026-08-30): "a graze at speed should scrub you but not end your race."
                    # The old test was `chard > 1.0e3 && |v| > WRECK_MS`, and chard saturates at
                    # ~296 kN for ANY non-hedge contact -- so it never discriminated and the speed
                    # gate ended the race for a 3 cm clip at 108 km/h just as for a square hit.
                    # Trigger on the CLOSING SPEED ALONG THE CONTACT NORMAL instead: that is small
                    # for a graze (the normal is mostly lateral) and near the full speed for a
                    # square hit, which is exactly the distinction the PO is drawing.
                    # The fence keeps its own peak test -- driving off the edge of the world is
                    # never a graze.
                    # S371: ONE implementation of the rule, shared with wreck_smoke.jl. A gate
                    # holding its own copy passes against a sim that has moved on -- this one had,
                    # missing the boundary branch below entirely.
                    if DriveRT3D.wrecks(cclose, BND_PK[], cs.v;
                                        close_ms = WRECK_CLOSE, bnd_peak_max = 1.0e3,
                                        vmin_ms = WRECK_MS)
                        wreck!(abs(cs.v))
                    end
                    # E98: a stall in MANUAL drops straight to AUTO. Conditions, all required:
                    # MANUAL, engine below the floor, clutch ENGAGED (an idling engine with the
                    # clutch OUT is not stalled -- that is the PO's own "applying throttle with
                    # slider down just revs the engine, as it should"), and NOT wrecked, because a
                    # wreck decouples the engine deliberately and must not look like a stall.
                    # Sustained, so a launch dip cannot trigger it.
                    # S366: the rule itself now lives in DriveRT3D.stall_step and is gated by
                    # JuliaMotorMTK/tools/stall_smoke.jl. Keep ONE implementation -- a copy here
                    # would drift from the one the gate checks, and the gate would still pass.
                    STALL_T[], _stallfire = DriveRT3D.stall_step(STALL_T[], dt;
                        auto = CTL.auto, wrecked = WRECKED[], rpm = cs.rpm, clutch = CLU_NOW[],
                        rpm_floor = STALL_RPM, secs = STALL_SECS)
                    if _stallfire
                        CTL.auto = true
                        println("  [gearbox] ENGINE STALLED (", round(Int, cs.rpm),
                                " rpm, clutch engaged) -- switched to AUTO")
                        flush(stdout)
                    end
                    # E95: while wrecked AND still moving, keep testing each corner -- a second wheel
                    # that reaches the barrier before the car stops comes off too. Gated on cpk so
                    # the per-corner SOLIDS scan only runs during an actual contact.
                    if WRECKED[] && hitpk > 1.0e3 && abs(cs.v) > 1.0
                        detach_hit_wheels!(cs.x, cs.z, cs.θ, cs.v;
                                           fence = BND_PK[] > 1.0e4,
                                           fence_nx = BND_NX[], fence_nz = BND_NZ[])
                    end
                    # E94-P4: a SURVIVABLE contact now costs something. Until this, a hit that did
                    # not end the race left the car mechanically perfect, so the E99 graze rule
                    # ("scrubs you but does not end your race") had no lasting cost at all -- you
                    # could bounce off the scenery all lap and finish on a factory-fresh car.
                    # Damage is accumulated from the CLOSING speed, the same quantity the wreck
                    # rule uses, so both read the impact the same way and a rub below the onset
                    # costs nothing (the PO's low-impulse exception).
                    # E94-P4 S2: the corners that FACED the blow take it. The contact point is
                    # not needed after all -- contact_force returns the force in the BODY frame
                    # and a contact can only push, so the impact arrived from the direction
                    # opposite that force. Each corner is weighted by how squarely it faces it.
                    if cpk > 1.0e3 && !WRECKED[] && cclose > 0.0
                        DriveRT3D.damage_impact!(cfx, cfy, cclose)
                        if DriveRT3D.damaged()
                            println("  [damage] contact at ", round(cclose, digits=1),
                                    " m/s closing -- corner grip now ",
                                    round(100*DriveRT3D.damage_mu(1)), "%")
                            flush(stdout)
                        end
                    end
                    cpk > 1.0e3 && (ffb_jolt = clamp(sign(cmz != 0 ? cmz : 1.0) * min(cpk/4.0e4, 1.0), -1.0, 1.0))  # feel the hit (stronger — PO: object kick was too small)
                end
                # add last frame's world-edge physical-wall force (E56.6) to the trackside contact force
                # E95: once wrecked the car's motion BLEEDS OUT. Fed through the same force port the
                # collision uses, so the solver integrates it -- not a velocity hack applied after
                # the step (which is what bumpX! does and why it was replaced in E56).
                # E95e (PO 2026-08-29: "hit the red wall, bounced back ... levitated and bounced.
                # There should be no bounce back. The car should come to a stop, not bounce back").
                # A wrecked car gets NO OUTWARD PUSH AT ALL. Every spring term -- trackside and
                # world-edge -- is dropped, because a spring is the only thing here that can return
                # energy, and bounding its stored energy (E94b) still leaves SOME. Zero is the only
                # value that cannot bounce. What remains is pure dissipation, so the car buries into
                # whatever it hit and stops there, which is what "totalled" should look like.
                if WRECKED[]
                    cfx = 0.0; cfy = 0.0; cmz = 0.0
                    BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0
                end
                wfx = WRECKED[] ? -617.0 * WRECK_DAMP * cs.v : 0.0
                DriveRT3D.extforce3d!(cs; Fx = cfx + BND_FX[] + wfx, Fy = cfy + BND_FY[], Mz = cmz + BND_MZ[],
                                      CdA_scale = PLAYER_CDA[])
                # E95g: a totalled car comes to REST and STAYS there. Once it is down to walking
                # pace, pin it: the alternative is a dead car creeping, drifting off the HAT and
                # re-entering the containment/levitation cycle the PO saw. Pinning is honest here in
                # a way it would never be for a driveable car -- the race is over by definition.
                if WRECKED[]
                    if !WRECK_FROZEN[] && abs(cs.v) < 2.0
                        WRECK_FROZEN[] = true
                        WRECK_PX[] = cs.x; WRECK_PZ[] = cs.z; WRECK_PT[] = cs.θ
                        println("  [WRECK] car came to rest"); flush(stdout)
                    end
                    if WRECK_FROZEN[]
                        DriveRT3D.place3d!(cs, WRECK_PX[], WRECK_PZ[], WRECK_PT[]; v=0.0)
                    end
                end
                # E95: the torn-off wheels live in the world now, not on the car.
                step_loose_wheels!(dt > 1e-4 ? dt : 1/60, (gx, gzz) -> (h = groundz(gx, gzz); h > -900 ? Float64(h) : 0.0))
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
                # E94-P4: damage MULTIPLIES into the surface grip rather than replacing it --
                # a bent corner on grass is worse than either alone, and overwriting here would
                # have quietly cancelled the grass-grip model whenever the car was damaged.
                DriveRT3D.wheelmu3d!(cs, μFL*DriveRT3D.damage_mu(1), μFR*DriveRT3D.damage_mu(2),
                                         μRL*DriveRT3D.damage_mu(3), μRR*DriveRT3D.damage_mu(4))
            end
            # E94-P4 S3: a damaged engine makes less power for the same pedal, and a dead one
            # makes none. Applied to the THROTTLE rather than inside the model so it cannot
            # disturb the ibt-derived engine curve -- the PO's constraint is that the physics
            # comes from the data, and this is the driver's input being throttled, not the
            # engine being re-specified. With a dead engine the revs fall and E98's stall rule
            # drops MANUAL to AUTO on its own, which is what a driver would want.
            step_carX!(cs, inp.throttle * DriveRT3D.engine_power(), inp.brake, inp.steer, dt > 1e-4 ? dt : 1/60;
                        clutch=inp.clutch, up=inp.shift_up, dn=inp.shift_down, manual=!inp.autoshift,
                        groundz=groundz_phys)
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
                BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0
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
                    pvx = WVX[]; pvz = WVZ[]                     # E96-S2: true world velocity, not v*cos/sin(θ)
                                                                 # -- cs.v is unsigned, so the old form
                                                                 # read a retreating car as approaching
                    vn = pvx*nwx + pvz*nwz                       # car speed along the INWARD normal (<0 = leaving)
                    gdt = dt > 1e-4 ? dt : 1/60
                    (bfx, bfy, bmz) = DriveRT3D.contact_force(nl - FENCE_GRACE, nwx, nwz, vn, cs.θ; kind = :wall, dt = gdt)
                    BND_FX[] = bfx; BND_FY[] = bfy; BND_MZ[] = bmz
                    BND_PK[] = hypot(bfx, bfy)   # E95b: the wreck trigger must SEE the world-edge wall
                    # E95f: keep the WORLD-frame wall normal (points INTO the world). contact_force
                    # returns BODY-frame forces, and the first cut dotted those against WORLD wheel
                    # displacements to pick the leading corner -- mixing frames, which is why the
                    # REAR wheels came off a head-on impact instead of the fronts.
                    BND_NX[] = nwx; BND_NZ[] = nwz
                    ffb_jolt = clamp(-vn*0.05, -1.0, 1.0)        # FF jolt off the world-edge wall
                    # E95g: skipping containment entirely for a wreck (E95e) was WRONG -- with no
                    # push-back AND no seal the car escaped the world, got caught somewhere else and
                    # was flung back to the start, over and over: the PO's infinite loop. Contain it,
                    # but with vdamp = 0 so the seal KILLS the velocity instead of returning any of
                    # it. A wreck is stopping; it must never be handed energy back.
                    # E103 (PO 2026-09-01): "when wheels come off during a collision, the car stops
                    # dead where the impact happened. It does not hyperspace back to the start line,
                    # which is the current behavior."
                    #
                    # THIS LINE WAS THE HYPERSPACE. containX! -> contain3d! does not push, it PLACES:
                    #   c.s_pos(c.integ, [xnew, znew]); c.x = xnew; c.z = znew
                    # and (LASTGX, LASTGZ) is the last position that was ON TRACK, which only updates
                    # while ONTRACK[]. A car that wrecks and leaves the mesh stops updating it, so the
                    # seal teleports the wreck back to wherever it last had grip -- and since both are
                    # initialised to the SPAWN point, a car that wrecks before ever registering
                    # on-track is sent to the start line exactly as the PO describes.
                    #
                    # E95g got close: it saw the car "flung back to the start, over and over" and
                    # fixed the ENERGY (vdamp = 0 for a wreck) without changing WHERE it is sealed to.
                    #
                    # A wreck is not lost, it is finished: seal it WHERE IT IS. For a driveable car
                    # the old behaviour stands -- putting it back on the track is a rescue and the
                    # race continues. JM_WRECK_SEAL_BACK=1 restores the old path.
                    if nl > FENCE_GRACE + FENCE_FAR                  # the wall failed to contain → last-resort seal (rare; never seen since E56)
                        (sealx, sealz) = WreckSeal.seal_target(WRECKED[], cs.x, cs.z,
                                             LASTGX[], LASTGZ[];
                                             seal_back = haskey(ENV, "JM_WRECK_SEAL_BACK"))
                        containX!(cs, sealx, sealz; vdamp=(WRECKED[] ? 0.0 : 0.3), settle=true, groundz=groundz_phys)
                        BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0; OFFDIST[] = 0.0
                    end
                else
                    BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0
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
        # E95: a torn-off wheel is in the WORLD, not on the car -- so it gets its own transform
        # rather than carModel's. Render axes are (x, up, -z), matching the trackside placement.
        loosemat(lx,ly,lz,sp) = Render.translate(Float32[lx, ly, -lz]) * Render.rotz(Float32(sp))
        # advance + place the AI field (rail-followers on the centreline)
        ai_hit = Ref(false); ddt = dt > 1e-4 ? dt : 1/60
        # an AI car's body orientation = its physics pitch (already settles to the fore/aft slope) +
        # (cross-slope terrain bank + physics roll) — so AI LIST on a dune side / roll in a collision,
        # exactly like the player's 3-D car (was yaw-only → they stayed flat).  6-tuple (x,y,z,θ,pitch,roll).
        aibankP(pc) = (isfinite(pc.pitch) ? pc.pitch : 0.0, (isfinite(pc.roll) ? pc.roll : 0.0) + terrain_roll(pc))
        aibankK(p)  = (cc=(x=p[1], z=p[3], θ=p[4]); (terrain_pitch(cc), terrain_roll(cc)))   # kinematic: terrain only (NB local must NOT be named `cs` — that would clobber the player car in the enclosing scope → cs.y FieldError)
        # ── E104(a) FIX (S4) ────────────────────────────────────────────────────────────────────
        # THE MEASURED DEFECT: AI cars are drawn up to 0.30 m off the terrain (median +0.09 m,
        # 13 of 45 samples at or above +0.20 m, min -0.19 m) while the player measures 0.00 m.
        # That is the PO's "every car floats 20-40 cm above the road", and the negatives are the
        # same bug sinking a car into it.
        #
        # THE CAUSE is one line in `RaceAI.pose_at`: it interpolates the centreline's x, y, z and
        # then applies the lane offset TO x AND z ONLY --
        #     (x + lane*(-sin θ),  y,  z + lane*cos θ,  θ)
        # -- so a car running `lane` metres to the side of the centreline is drawn at the
        # CENTRELINE's height. Across a cambered or cross-sloped road that is off by
        # lane x cross-slope, and lanes here are +-2.4 m, which is exactly the 0.2-0.3 m measured.
        # Every wheel then inherits it, because `aiWheel` places wheels at <origin> + [wx, r, wz].
        #
        # ⚠️ This is why E104-S2's mechanism was RIGHT and E104-S3's refutation of it was WRONG:
        # S3 measured `AILINE.y - groundz` at the line's OWN points, where lane = 0 and the error
        # is zero BY CONSTRUCTION. It never sampled a car at its actual laterally-offset position.
        # A refutation is only as wide as the case it tested.
        #
        # The fix re-grounds the drawn pose at the point the car is ACTUALLY drawn at. It is applied
        # here rather than inside `pose_at` because `pose_at` lives in ai.jl and has no terrain --
        # and because the same call feeds AI PLACEMENT, where the line's own y is what re-anchors a
        # stuck car. Only what is DRAWN is re-grounded.
        # ⚠️ hat3d, NOT groundz: groundz mutates LASTZ[]/ONTRACK[], the PLAYER's ground state, so
        # calling it five times a frame for the AI field would rewrite what the player's next
        # physics step reads. Off the terrain (h[3] false) the pose is left exactly as it was.
        # The mechanism itself is RaceAI.reground (ai.jl) so it can be gated; this supplies the
        # terrain query it needs, in the (y, ok) form it expects.
        ai_height(x, z) = (h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf); (Float64(h[1]), h[3]))
        ai_ground(p) = RaceAI.reground(p, ai_height)
        ai_poses = if REPLAY                                       # E18: AI poses straight from the recording
            NTuple{6,Float64}[(a[1],a[2],a[3],a[4],0.0,0.0) for a in rep_ai_raw]
        elseif AILINE === nothing || phase[] != :race              # AI hidden until the race starts (after qualifying)
            NTuple{6,Float64}[]
        elseif !race_go[] || (AI_HEADSTART > 0 && ai_release[] >= 0.0 && cs.t < ai_release[])
            # standing on the grid -- not yet launched, or held by the PO's head start
            AI_PHYSICS ? [(b=aibankP(pc); (pc.x, groundz(pc.x, pc.z), pc.z, pc.θ, b[1], b[2])) for pc in AIPHYS] :
                         [(p=RaceAI.pose_at(AILINE, c.s, c.lane); b=aibankK(p); ai_ground((p[1],p[2],p[3],p[4],b[1],b[2]))) for c in AICARS]
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
                DriveRT3D.step_car3d!(pc, thr, brk, st, ddt; manual=false, groundz=groundz_phys)
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
            [(b=aibankK(p); ai_ground((p[1],p[2],p[3],p[4],b[1],b[2]))) for p in poses]   # E104-S4: re-grounded at the DRAWN position; add terrain bank (kinematic has no body roll)
        end
        # C: time each AI lap — works for BOTH the physics and kinematic fields (we watch AICARS[i].lap,
        # which both paths bump as the car crosses start/finish).  ai_best[i] = that car's fastest lap.
        if phase[] == :race && race_go[]
            for i in 1:length(AICARS)
                if AICARS[i].lap > ai_lap_prev[i]
                    lt = cs.t - ai_lapt0[i]; ai_lapt0[i] = cs.t
                    ai_lap_prev[i] > 0 && (ai_best[i] = min(ai_best[i], lt))   # skip lap 0→1 (the grid launch)
                    # JM_AI_LAPDIAG=1: report each AI lap as it completes. Until now an AI lap time
                    # existed only in `last_race_result.txt`, written when the RACE ENDS -- so a
                    # session that is quit early (or any headless pace check) recorded nothing, and
                    # "the AI lap at 1:40" could only ever be quoted from the pacing arithmetic
                    # rather than measured. This makes the claim checkable in one run.
                    if AI_LAPDIAG && ai_lap_prev[i] > 0
                        println("  [ailap] ", rpad(ent_name(i), 9), " lap ", AICARS[i].lap,
                                "  ", fmt_lap(lt), "   best ", fmt_lap(ai_best[i]))
                        flush(stdout)
                    end
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
            # E96-S5: the PLAYER's world velocity, not speed x heading. `cs.v` is UNSIGNED, so a car
            # being shoved backwards after a clash still read as travelling along its nose -- and the
            # closing test below (`vrel <= 0.2 && continue`) would then see CLOSING where the cars are
            # actually separating, and hand out another impulse every frame. That is the same sign
            # error E96-S2 found in solid_contact and the world fence; this site was missed because
            # car-to-car contact was not what the PO was reporting at the time.
            # The AI side keeps v x heading: AI cars are driven along their own nose and are never
            # shoved backwards by this path (it bounds their response deliberately, R1), so their
            # speed and heading agree. The player is the body that gets pushed around.
            pvx = WVX[]; pvz = WVZ[]
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
        # ── E85-S5: exchange poses with the peer, and place its cars ON THE GROUND ───────────────
        if NETLINK !== nothing
            # ⚠️ YIELD FIRST. The socket reader is an `@async` task (netplay.jl keeps one long-lived
            # reader so `poll!` never blocks the frame), and a Julia task only runs when something
            # yields to the scheduler. The probe loops `sleep(0.002)` and so yields constantly; this
            # render loop does not sleep at all, so the reader was NEVER SCHEDULED and every packet
            # sat in the kernel buffer. Measured before this line existed: client `peers=1` (it was
            # sending) and host `rx=0 peers=0` (it received nothing, so never learned a peer, so
            # never replied) -- a one-way link that was really a starved task.
            yield()
            NetPlay.poll!(NETLINK)
            if cs.t - net_last[] >= 1/NET_HZ
                net_last[] = cs.t
                NetPlay.send_pose!(NETLINK, NET_ID, round(Int, cs.t*1000),
                                   cs.x, cs.y, cs.z, cs.θ, cs.v, inp.steer)
            end
            # ⚠️ THE E104(a) RULE, ENFORCED AT THE RECEIVING END. `predict` deliberately does not
            # extrapolate height, and the packet's y is the SENDER's ground -- which is not this
            # machine's ground if the two disagree by so much as a terrain rounding. A remote car's
            # height must come from the terrain UNDER IT, exactly as the AI field's does since
            # E104-S4, or remote cars float for the same reason the AI did.
            netp = NTuple{6,Float64}[]
            for (_, q) in NetPlay.remote_poses_at(NETLINK, time())
                b = aibankK((q.x, 0.0, q.z, q.yaw))
                push!(netp, ai_ground((q.x, q.y, q.z, q.yaw, b[1], b[2])))
            end
            # ── E85-S7: PREDICTION ERROR, measured receiver-side with no clock sync ─────────────
            # When a NEW packet arrives for a car, we already know what the PREVIOUS packet
            # predicted for that instant: dead-reckon the old pose forward by the tick difference
            # and compare against the position the new packet actually reports. Both numbers come
            # from the same sender's own clock, so nothing has to be synchronised and no two logs
            # have to be correlated afterwards -- which is what made S4's version need an analytic
            # trajectory. Here the trajectory is whatever the other car really did.
            if NET_ERR
                for (id, q) in NETLINK.remote
                    pv = get(NET_PREV[], id, nothing)
                    if pv !== nothing && q.tick != pv.tick
                        dt = (q.tick - pv.tick) / 1000
                        if 0 < dt < 1.0                       # ignore huge gaps (startup, stalls)
                            pr = NetPlay.predict(pv, dt)
                            push!(NET_ERRS, hypot(q.x - pr.x, q.z - pr.z))
                            push!(NET_DTS, dt)
                        end
                    end
                    NET_PREV[][id] = q
                end
                if !isempty(NET_ERRS) && (frames % 600) == 0
                    m = sum(NET_ERRS)/length(NET_ERRS)
                    println("  [neterr] n=", length(NET_ERRS),
                            "  interval mean=", round(sum(NET_DTS)/length(NET_DTS), digits=3), "s",
                            "  ERR mean=", round(m, digits=4), " m  max=",
                            round(maximum(NET_ERRS), digits=4), " m")
                    flush(stdout)
                end
            end
            NETPOSES[] = netp
            # JM_NET_DIAG=<n>: report the link every n frames. "No car appeared" has at least four
            # causes -- nothing sent, nothing received, everything judged stale, or nothing drawn --
            # and a screenshot cannot tell them apart, especially with the two cars 80 m apart on a
            # curving track. Print the counts instead of squinting.
            if NET_DIAG > 0 && (frames % NET_DIAG) == 0
                println("  [net] t=", round(cs.t,digits=1), " rx=", NETLINK.rx,
                        " dropped=", NETLINK.dropped, " peers=", length(NETLINK.peers),
                        " known=", length(NETLINK.remote), " drawn=", length(netp))
                flush(stdout)
            end
        end
        # E104-S4: the measurement the eye is actually making. See JM_WHEELGAP above.
        if WHEELGAP > 0 && (frames % WHEELGAP) == 0
            # ⚠️ MUST NOT call groundz(): it MUTATES LASTZ[] and ONTRACK[], the player's own
            # ground-tracking state. The first cut of this probe did, so querying five AI positions
            # per sample rewrote the height and on-track flag the PLAYER's next physics step reads --
            # an instrument that changes the thing it measures. hat3d is the pure query underneath
            # groundz; `ref=Inf` and the (x,z) order are copied from groundz itself so the probe and
            # the sim ask the terrain exactly the same question.
            wgap(y, x, z) = (h = JuliaMotor.hat3d(TERRAIN, x, z; ref=Inf);
                             h[3] ? round(y - Float64(h[1]), digits=3) : NaN)
            println("  [wheelgap] t=", round(cs.t, digits=1), "  player ", wgap(cs.y, cs.x, cs.z), " m",
                    isempty(ai_poses) ? "   (no AI on track yet)" : "")
            for (k, p) in enumerate(ai_poses)
                println("  [wheelgap]      AI ", k, "  ", wgap(p[2], p[1], p[3]), " m")
            end
            flush(stdout)
        end
        # ---- shadow pass: scene depth from the sun, light box on the car ----
        lightVP = Render.light_vp(Float32[cs.x, cs.y, -cs.z], LIGHTDIR)
        Render.shadow_pass(depthprog, shadowfbo, lightVP) do dp
            for it in trackItems; Render.draw_depth(dp, it, Render.ident()); end
            for it in carItems; Render.draw_depth(dp, it, bodyModel); end
            for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]
                is_loose(nm) && continue                                   # E95: this one came off
                Render.draw_depth(dp, it, wheelmat(wx,wz,steer,r))
            end
            for (lx,ly,lz,_,_,_,sp,_,nm) in LOOSE_WHEELS, it in WHEELITEMS[nm]
                Render.draw_depth(dp, it, loosemat(lx,ly,lz,sp))
            end
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
                    # E69-S7: make the track-draw lighting tunable so the warm cast measured against
                    # gold (asphalt R-B: gold -2.5..-5.3, native +7.8..+12.7 across three tracks
                    # each) can be attributed rather than guessed at.
                    Render.draw(prog, it, vp_, Render.ident(); bright=TRACK_BRIGHT, ambfill=TRACK_AMB)
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
                Render.draw(prog, it, vp_, Render.translate(Float32[pos[1],pos[2],pos[3]])*Render.roty(yaw)*Render.scalexyz(w,h,1f0); bright=1.3, ambfill=0.8, graze=true, unlit=!BB_LIT)   # E63/MZ3: the comment always claimed graze-fade but the call never passed it → a wide Monza forest strip seen EDGE-ON rendered as a dark triangular SLAB at the S/F. graze=true fades edge-on quads (uGraze) so the strip shows face-on as a tree-line and vanishes edge-on
            end
            OBJ_CULLFACE && glDisable(GL_CULL_FACE)
            glUniform1i(glGetUniformLocation(prog,"uBackFlip"), 0)
            for (it,pos,w,h) in BILLBOARDS                            # trees/sprites
                (eye_[1]-pos[1])^2+(eye_[2]-pos[2])^2+(eye_[3]-pos[3])^2 > BB_CULL2 && continue       # distance cull
                Render.draw(prog, it, vp_, Render.billboard_model(pos,w,h,eye_); bright=BB_BRIGHT, ambfill=BB_AMB, unlit=!BB_LIT)  # E83-S3: unlit by default (GPL pre-lit art); E70-S7 tunables only matter with JM_BILLBOARD_LIT=1
            end
            for (p, cm) in zip(ai_poses, AICHASSIS)                 # AI grid (Ferrari/Brabham/BRM/Eagle/Cooper)
                for it in cm.body; Render.draw(prog, it, vp_, aiBody(p, cm); bright=1.25, spec=0.10, ambfill=0.62); end
                # E106-S25: JM_NO_AI_WHEELS=1 suppresses the AI wheel draw. The rods on the AI rear
                # tyre are neither the wheel mesh (max radius 0.336, nothing beyond) nor the wrapper
                # (all variants complete) -- so shooting the SAME replay frame with the wheels gone
                # says whether the ring survives, i.e. whether it is drawn by something else.
                if !AI_NOWHEELS
                    for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw(prog, it, vp_, aiWheel(p,wx,wz,r)); end
                end
            end
            # E85-S5: the REMOTE cars, drawn through exactly the same path as the AI field -- same
            # body/wheel transforms, so anything true of an AI car's placement is true of theirs.
            if !isempty(NETPOSES[]) && !isempty(AICARMODELS)
                cm = AICARMODELS[1]
                for p in NETPOSES[]
                    for it in cm.body; Render.draw(prog, it, vp_, aiBody(p, cm); bright=1.25, spec=0.10, ambfill=0.62); end
                    for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw(prog, it, vp_, aiWheel(p,wx,wz,r)); end
                end
            end
        end
        # ---- E64 mirror pass: the rear view into the mirror RTT (cockpit view only) ----
        # E80 (PO 2026-08-27: "10 frames/sec in cockpit view, better in nintendo view"). MEASURED at
        # Spa, same spot, same settle:
        #     mirrors ON   cockpit 6.7-7.0 fps (144-149 ms)   chase 11.4-20.3 fps
        #     mirrors OFF  cockpit 14.9-16.4 fps (61-67 ms)   chase 13.5-16.0 fps (unchanged)
        # So this second render pass costs ~80 ms/frame and IS the whole cockpit/chase asymmetry --
        # chase never runs it. It re-renders the scene into a 384x192 texture EVERY frame.
        # Two round mirrors that small do not need a fresh image 60 times a second, so refresh them
        # every Nth frame instead. The car's own motion between updates is what a real mirror at
        # this size would blur away anyway. JM_MIRROR_EVERY=1 restores per-frame; =0 uses
        # JM_MIRROR_RTT=0's static discs.
        mirror_live = MIRROR_RTT && CTL.view == 0 && !REPLAY &&
                      (MIRROR_EVERY <= 1 || (frames % MIRROR_EVERY) == 0)
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
                for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]
                    is_loose(nm) && continue
                    Render.draw(prog, it, mvp, wheelmat(wx,wz,steer,r); bright=1.0, ambfill=0.75)
                end
                for (lx,ly,lz,_,_,_,sp,_,nm) in LOOSE_WHEELS, it in WHEELITEMS[nm]
                    Render.draw(prog, it, mvp, loosemat(lx,ly,lz,sp); bright=1.0, ambfill=0.75)
                end
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
        # E80: per-phase FRAME profiler. The entry pointed at JM_TIMING, which is a LAUNCH-phase
        # stopwatch ("cumulative seconds at each load phase") -- it profiles loading, not frames, and
        # JM_FPSDIAG times the whole frame as one number. So nothing could say where the ~65 ms goes.
        # JM_FRAMEPROF=<n> prints the split every n frames. Buckets are cheap wall-clock reads around
        # phases that already exist; no restructuring.
        _t_world = time()
        drawworld(vp, eye, false)
        FRAMEPROF > 0 && (PROF_WORLD[] += time() - _t_world)
        # ambfill lifts the self-shadowed cockpit interior out of black (GPL pre-lights it
        # evenly); lower spec so the cockpit floor stops reading as a "shining rug".
        # E106-S5: in cockpit view the body wears GPL'"'"'s interior skin (riveted aluminium);
        # every other view keeps the exterior body.
        let _items = (CTL.view == 0 && !isempty(carItemsIn)) ? carItemsIn : carItems
            for it in _items; Render.draw(prog, it, vp, bodyModel; bright=1.2, spec=0.08, ambfill=0.78); end
        end   # PO: lift the self-shadowed footwell/tub further out of black (GPL pre-lights the interior evenly)
        # E106-S4: exhausts at hub height (chrome: a touch of spec so the megaphones catch the sun)
        let pm = bodyModel * Render.translate(Float32[0, PIPE_LIFT, 0])
            for it in pipeItems; Render.draw(prog, it, vp, pm; bright=1.15, spec=0.25, ambfill=0.6); end
        end
        # E106-S9: the driveshafts, horizontal from diff to hub
        for it in axleItems; Render.draw(prog, it, vp, bodyModel; bright=1.1, spec=0.3, ambfill=0.55); end
        if CTL.view != 0   # the driver figure occludes the cockpit from the in-car eye (E36 black band) → chase only
            if get(ENV,"JM_RSUSP2","0") == "1"   # E75-S8: OFF by default — raw parts are unfolded strips, see e75_exterior.md
                for it in rsusp2Items; Render.draw(prog, it, vp, bodyModel; bright=1.15, spec=RS_SPEC, ambfill=0.55); end
            end
            if RSUSP_ON    # E64 S7: high-detail rear suspension (gold nintendo shows the full articulated rear end)
                let mA = RS_BAKECLIP ? bodyModel : bodyModel*RSFIX_A,
                    mB = RS_BAKECLIP ? bodyModel : bodyModel*RSFIX_B
                    for it in rsuspItemsA; Render.draw(prog, it, vp, mA; bright=1.15, spec=RS_SPEC, ambfill=0.55); end
                    for it in rsuspItemsB; Render.draw(prog, it, vp, mB; bright=1.15, spec=RS_SPEC, ambfill=0.55); end
                end
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
        for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]
            is_loose(nm) && continue
            Render.draw(prog, it, vp, wheelmat(wx,wz,steer,r); bright=1.0, ambfill=0.75)
        end
        for (lx,ly,lz,_,_,_,sp,_,nm) in LOOSE_WHEELS, it in WHEELITEMS[nm]
            Render.draw(prog, it, vp, loosemat(lx,ly,lz,sp); bright=1.0, ambfill=0.75)
        end
        # front suspension wishbones — ahead of the cockpit, visible through the plexiglass (PO gold standard)
        for it in fsuspItems; Render.draw(prog, it, vp, bodyModel; bright=1.1, spec=0.15, ambfill=0.5); end
        # rear-view mirrors — re-placed onto the cowl/plexiglass, faces tilted toward the eye (GPL look).
        # E64: with the RTT live, the silver disc is just the RIM/backing — the glass quad on top
        # carries the actual rear view (round-masked sample of the mirror FBO, uMirrorGlass).
        for it in mirrorItems; Render.draw(prog, it, vp, bodyModel*MIRRORMAT; bright=1.25, spec=0.30, ambfill=0.75, depthbias=true); end   # disc/rim (E106-S8: biased over the lotd pod faces)
        if mirror_live
            for it in mirGlassItems; Render.draw(prog, it, vp, bodyModel*MIRRORMAT; mirrorglass=true, depthbias=true); end   # live glass (E106-S8: biased)
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
            for it in windItems; Render.draw(prog, it, vp, bodyModel; bright=WIND_B, spec=0.02, ambfill=WIND_A, alpha=WIND_ALPHA, depthbias=true); end   # E106-S8: biased over the lotd frame faces
            glDepthMask(GL_TRUE)
        end
        α_tc = clamp(dt/0.10, 0.0, 1.0)              # smooth the traction-circle display (coarse-mesh Fz spikes → no flicker)
        tc_hud = ntuple(i -> ntuple(j -> tc_hud[i][j] + (cs.tc[i][j]-tc_hud[i][j])*α_tc, 3), 4)
        _t_hud = time()
        Render.hud_draw(hudprog, hudvao, hudvbo,
            Render.compose_hud(W, H, cs.v*3.6, cs.gear, cs.rpm, 9500.0, inp.throttle, inp.brake, inp.clutch, tc_hud;
                               lastlap=(SMOKE ? 94.3 : last_lap), bestlap=(SMOKE ? 92.1 : best_lap), manual=!CTL.auto,
                               countdown=cd_left[],
                               clutchgate=(CLUTCH_GATE[] > 0 ? inp.clutch : -1.0)), W, H)
        CLUTCH_GATE[] > 0 && (CLUTCH_GATE[] -= dt)
        # E80 (PO 2026-08-27): "frame rate was low (10 frames/sec or so) in cockpit view, better in
        # nintendo view ... no excuse for 10 frames/sec on a PC with a 6 GB nvidia graphics card".
        # Report the frame time per VIEW, because the cockpit/chase asymmetry is the whole clue:
        # the same scene from two cameras, so anything that costs the same in both is not the cause.
        # JM_FPSDIAG=<n> prints every n frames (default 120).
        FRAMEPROF > 0 && (PROF_HUD[] += time() - _t_hud)
        if FRAMEPROF > 0
            PROF_N[] += 1
            if PROF_N[] >= FRAMEPROF
                nn = PROF_N[]
                # PROF_TOT is filled by the FPSDIAG accumulator below when it is also on; when it is
                # not, report the phases alone rather than a percentage of an unknown whole. A split
                # that silently divides by a total nobody measured is the kind of confident-wrong
                # number this project keeps booking.
                tot = PROF_TOT[] > 0 ? PROF_TOT[]/nn*1000 : NaN
                println("  [frameprof] ", nn, " frames:  world ", round(1000*PROF_WORLD[]/nn, digits=2),
                        " ms   hud ", round(1000*PROF_HUD[]/nn, digits=2), " ms",
                        isnan(tot) ? "   (total not measured -- set JM_FPSDIAG too)" :
                                     "   of " * string(round(tot, digits=2)) * " ms total")
                flush(stdout)
                PROF_WORLD[] = 0.0; PROF_HUD[] = 0.0; PROF_N[] = 0; PROF_TOT[] = 0.0
            end
        end
        if FPSDIAG > 0
            _now = time()
            if FPS_T0[] > 0
                FPS_ACC[] += _now - FPS_T0[]; FPS_N[] += 1; FRAMEPROF > 0 && (PROF_TOT[] += _now - FPS_T0[])
                if FPS_N[] >= FPSDIAG
                    _ms = 1000*FPS_ACC[]/FPS_N[]
                    println("  [fps] view=", CTL.view == 0 ? "cockpit" : "chase  ",
                            "  ", round(1000/_ms, digits=1), " fps  (", round(_ms, digits=1), " ms/frame)")
                    flush(stdout); FPS_ACC[] = 0.0; FPS_N[] = 0
                end
            end
            FPS_T0[] = _now
        end
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
    if DRIVECHECK
        d = DC[]
        println("\n  ══ DRIVEABILITY (", TRACKSEL, ") — autodrive reached s=", round(d.maxs, digits=1), " m ══")
        println("    max height above ground : ", round(d.airmax, digits=2), " m at s=", round(d.air_s, digits=1),
                "   (", d.air_bad, " frames over ", DC_AIR_MAX, " m)")
        println("    max upward velocity     : ", round(d.vzmax, digits=2), " m/s at s=", round(d.vz_s, digits=1),
                "   (", d.vz_bad, " frames over ", DC_VZ_MAX, " m/s)")
        println("    longest slow spell      : ", round(d.stuckmax, digits=1), " s at s=", round(d.stuck_s, digits=1),
                "   (stuck threshold ", DC_STUCK_S, " s under ", DC_STUCK_V, " m/s)")
        if !isempty(d.events)
            println("    launch SITES (each distinct excursion above ", DC_AIR_MAX, " m; height = that excursion's PEAK):")
            for (es, eair, ekmh, ex, ez) in d.events
                println("      s=", lpad(round(es, digits=1), 9), " m   air ", lpad(round(eair, digits=2), 6),
                        " m   at ", lpad(round(ekmh, digits=0), 4), " km/h   world (",
                        round(ex, digits=1), ", ", round(ez, digits=1), ")")
            end
        end
        bad = (d.airmax > DC_AIR_MAX) + (d.vzmax > DC_VZ_MAX) + (d.stuckmax > DC_STUCK_S)
        println(bad == 0 ? "    VERDICT: CLEAN — no levitation, no bounce, never stuck" :
                           "    VERDICT: $(bad) FAILURE MODE(S) SEEN — see the lines above")
        flush(stdout)
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
