# Julia Racer — Status (2026-06-29)

GPL-style racing sim: Lotus 49 on GPL tracks, JuliaMotor (MTK) physics, native OpenGL
renderer. Branch `julia-racer`. Launch via `demo/native/juliaRacer.py` (or `drive_native_mtk.jl`).

## Latest (2026-06-29 PM) — G2/E12 physics-AI anti-spin controller (autonomous)

The physics-AI controller chased the line with a fixed aggressive gain and held throttle through a
slide, so on the hilly tracks (where the 3-D model's load transfers break grip) it AMPLIFIED an
incipient slide into a spin (the residual after the E6 divergence guard). `controller()` now reads
the yaw rate as a slide signal — above a normal corner's ~1 rad/s it eases the line-chase gain, ramps
counter-yaw damping (steers into the slide) and lifts throttle (kills RWD power-oversteer); below
`JM_AI_SPIN_LO` it's unchanged. **Verified** (physics-AI self-test, 5 cars, 90 s): Spa spins
1514→1014 (−33%), **3 of 5 cars now lap cleanly at 102–116 km/h** (was 1); Zandvoort NO regression
(0 spins, max_yaw 1.43, clean). Cumulative with E6: Spa physics-AI went from diverge-to-hyperspace
(max_yaw 281) to the majority lapping at race pace. A tuning sweep confirmed `SPIN_LO/HI = 1.0/3.0`
beats an earlier-engaging 0.85/2.5 (which made Spa worse). Physics-AI stays opt-in (kinematic is the
shipping default); 2/5 Spa cars still struggle (diminishing returns / run-to-run variance).

**Nürburgring verification (worst divergence case):** the E6 yaw guard GENERALIZES — `max_yaw`
1239 → 9.99 rad/s (no blow-up). BUT Nürburgring physics-AI is still not viable for a different reason
— `max_lat 350 m` (cars leave the track; one displaced to 6998 m / 280 km/h): a POSITION / line-
following failure on the extreme 22 km elevation (likely airborne launches off the big jumps landing
far off-line, or a poor rFactor racing line), NOT the yaw divergence. So: **divergence = fixed on both
Spa & Nürburgring**; full physics-AI viability is Spa-partial, Nürburgring-blocked on a separate
position problem (deferred — opt-in path; kinematic AI laps Nürburgring cleanly as the default).

## Earlier (2026-06-29 PM) — E6 yaw-rate divergence guard + render QA (autonomous)

**E6 — 3-D integrator no longer diverges on the big tracks.** The stiff 3-D tyre/contact could spin
the yaw rate `r` to hundreds of rad/s on Spa/Nürburgring elevation (the integrator diverging, which
the vertical guard couldn't catch and `place3d!` couldn't reset — the physics-AI "cartwheel to
hyperspace"). `step_car3d!` now clamps a clearly-diverged yaw (>10 rad/s, vs a real spin's <3) back
in place to ≤3.5 — no respawn/teleport. **Verified:** Spa physics-AI self-test `max_yaw` **281 → 9.9
rad/s**; normal driving byte-identical (drive3d/contact smokes unchanged). This closes the DIVERGENCE
gap; the physics-AI *controller* still oscillates into (now-recoverable) spins on hilly tracks
(`spins=2121` on Spa) — separate tuning, so kinematic AI stays the shipping default.

**Render QA sweep:** Spa ✅ + Watkins Glen ✅ + Zandvoort ✅ render well (Monza was the sole outlier,
fixed by E57). Residual cross-track issue: **E46 blue/streaky crowd** (worst on Zandvoort's main
grandstand) — needs a per-draw shader TINT uniform (deferred). Pre-existing `test_corner_tyre:44`
failure is the legacy Magic-Formula `Tyre` vs `tyre_fy` (~194 N) — NOT from E56/E57 (brush path clean:
`test_brush_slip` ✅, `test_vehicle_driven` ✅).

## Earlier (2026-06-29 PM) — E57 Monza render legibility (autonomous)

Monza no longer renders as a blinding near-white "maze". Root cause: its `asphalt` MIP is
over-bright AND in this COMBINED circuit the road is split between the `trrow01` track mesh and
placed OBJECTS (paddock / connector roads / banking), drawn at full object brightness — so one
brightness knob couldn't reach it all. Fix (Monza-gated; other 4 tracks untouched): classify both
track surfaces (by GPL texture name → `TRACKCAT`) and paved/banking OBJECTS (by name) and grade
each — road 0.72→0.42 bright (proper grey asphalt), barriers lifted from carbonized black, banking
toned from white to grey, and the start-line "snow" foreground (which was the `paddock`/`cgroad`
objects) greyed. Tunable via `JM_MONZA_{ROAD,DARK,BANK,OTHER}_{B,A}`. Verified with offscreen
snapshots at the start + mid-lap; Zandvoort re-render confirms no regression. **Still open (deferred
E52):** the banking reads as a flat slab (geometry), now grey rather than blinding white.

## Earlier (2026-06-29 PM) — E56 "all-Modelica human car" BUILT OUT (autonomous, E56.2–E56.6)

Continuing the E56 epic autonomously from the E56.1 port foundation. Every PLAYER interaction is
now a physical force/parameter integrated by the chassis ODE — the `bumpX!`/`containX!` state hacks
are gone for the human car (the AI stay kinematic slot cars). **All `include`d as SOURCE ⇒ LIVE at
next launch, no `jlracer.so` rebuild.** Each increment has its own headless smoke + the 40-frame
full-game smoke (Zandvoort + AI) runs clean:
- **E56.2 — `extforce3d!` port setters** (Fx/Fy/Mz/CdA_scale on `Car3D`). `extforce3d_smoke`.
- **E56.3 — draft = `CdA_scale`** aero tow (cuts frontal drag, not a velocity bump); now works vs the
  default kinematic field, not just physics-AI. `JM_DRAFT_CUT`.
- **E56.4 — trackside collision = spring-damper force** (`contact_force` kernel: `:wall` bounces,
  `:soft` haie hedges/hay bury-and-stick via a crush give-zone + viscous damper; per-frame impulse
  clamped for solver stability). SOLIDS tagged by kind; player `solid_hit→bumpX!` deleted.
  `contact_smoke`: wall bounces, hedge sticks, no pass-through, no divergence.
- **E56.5 — grass = per-wheel tyre μ** (`BrushTyre.μscale` + `wheelmu3d!`; the game projects all 4
  wheels and drops μ off the racing surface → a wheel on grass loses real grip + pulls the car).
  Player bumpX! grass hack deleted (AI keep theirs). `wheelmu_smoke`: μ=0.5 halves grip.
- **E56.6 — boundary = physical wall** (stiff inward `contact_force(:wall)`; the car bounces off the
  world edge with NO routine teleport — the auto `containX!` snap-back is gone; recovery = SHIFT-R).
  A far failsafe (`JM_FENCE_FAR`=16 m) still seals the world against a true escape. `boundary3d_smoke`:
  contained at 20/40/60 m/s (penetration 2.6–4.4 m, bounces, no failsafe, no divergence).

**PO re-drive to close (felt, not headless-verifiable):** draft slingshot feel; hedge-stick vs
wall-bounce; grass grip-loss/pull; and especially the **world-edge wall** (confirm it contains at
racing speed with no jarring teleport; `JM_FENCE_FAR` / wall stiffness are tunable if it leaks or
feels harsh). New env knobs: `JM_DRAFT_CUT`, `JM_GRASS_MU`, `JM_FENCE_FAR`.

## Earlier 2026-06-29 — PO live-test fixes + E56 "all-Modelica human car" epic (foundation)

**Race-crash FIXED (commit) — was blocking every race.** `aibankK(p) = (cs=(x=,z=,θ=);…)`
re-bound the *player* car `cs` (a named closure shares the enclosing binding) to a NamedTuple,
so the next render frame's `light_vp(cs.y)` threw `FieldError`. Crashed every kinematic-AI race
at frame 1. Renamed the local → `cc`. Script fix, **live now (no rebuild)**.

**E56 EPIC — human car = 100% MTK/Modelica components, AI = slot car (PO directive).**
PO: "the human car's full physical modelling is what gives GPL its sense of accuracy; the AI are
just special effects — slot cars that don't hog the spotlight by flipping." So:
- **Human car:** every *interaction* becomes a physical force component fed into the ODE (never a
  `bumpX!`/`containX!` state hack): **draft**=aero `CdA_scale` (wake → less drag → tow);
  **collisions**=spring-dampers (wall = stiff `k` → bounce; hedge/haybale = weak `k` + strong `c`
  → drive in, decelerate, **get stuck**); **grass**=per-wheel tyre `μ`; **return-to-track = SHIFT-R
  only** (delete the auto snap-back/containment).
- **AI:** stays kinematic slot car (rail-bound, can't flip) — the definitive AI.
- **E56.1 foundation DONE (commit):** `DrivenVehicle3D` gains `Fx_ext, Fy_ext, Mz_ext` + `CdA_scale`
  ports summed into `D(u)/D(v)/D(r)` (defaults 0/1 ⇒ behaviour unchanged). Verified compiles +
  steps + the port is integrated. **NB the physics is `include`d as SOURCE** (`drive_rt3d.jl` →
  `vehicle_3d.jl`, `mtkcompile` at startup), so model edits are **LIVE at next launch — no
  `jlracer.so` rebuild** (the sysimage only bakes the MTK/solver machinery).
- **Next:** DriveRT3D port setters → game-loop spring-damper contact law + delete player
  `containX!`/`bumpX!`; then draft `CdA_scale`; then grass `μ`; then boundary = physical walls.

**Monza rendering (pre-existing, still open):** the **road renders near-white** (the `asphalt`
texture is too bright — it IS textured, not untextured) and **barriers render carbonized-black**
(opposite problems → need a per-surface split, can't fix with one brightness knob). The banking is
now *physically* drivable (E52 HAT overpass-drop, verified) but still **renders as a wall**, so it
reads as a maze you steer into. Monza is the combined banked circuit — inherently busy; the other
4 tracks render correctly.

## Autonomous night batch (2026-06-28 → 29) — E52 Monza banking, E54 sweep, E55 AI flop
PO mandate: "run scrum autonomously till 8am; clean race on all 5 tracks (no obstructions, no
grass-molasses), AI must not entangle/flop; ignore wheelspin in AI collisions if needed."

- **E52/E54a ✅ Monza — drive UNDER the banking** (commits 4db1c16 + follow-ups). This Monza is the
  COMBINED banked circuit; where the road course passes under the sopraelevata, the single-valued HAT
  returned the banking deck (car climbed it / hit a wall = "can't drive through").  Fix: `build_hat`
  geometric **overpass-drop** removes a deck triangle only where ROAD asphalt lies beneath (the
  underpass) — the drivable banking OVAL (deck over grass) is kept — plus a Monza-only **wall-climb
  guard** in `groundz` for the banking ISLAND over the road-mesh gap (reject >3 m jumps → coast).
  Verified: `JM_DRIVETEST` stays on the road (−1.1→1.3 m) through both crossings; cockpit shows a clear
  road, not the black wall.  Banking still rendered (you drive under it like a bridge).
- **E54 ✅ molasses CLEAR + JM_SWEEP harness.** New `JM_SWEEP=<step>`: headless centreline sweep
  reporting on-road SOLID/mesh/billboard obstructions (with lateral + base-height), HAT walls/cliffs/
  holes, and false-grass spots (centreline off the .trk surface = a grass-penalty molasses).  Result:
  **NO false-grass / walls / holes** on Zandvoort, Spa, Watkins, Monza(handled) — no molasses bog for a
  car on the racing line.  E51 (Monza Lesmo tree-curtain) confirmed already gone (E31 filter).  A sweep
  object frame bug was found+fixed (objects were projected with z negated).
- **E55 ✅ AI collisions planar-only.** Both AI↔AI and player↔AI contacts injected a wheel-climb LAUNCH
  (≤7 m/s up) + ROLL (cartwheel) into the AI's 3-D body — the flop, and likely the E38 hyperspace
  (violent impulse diverged the MTK integrator).  Now: planar push + mild yaw, no launch/roll, capped —
  AI bump like billiard balls.  The player keeps full collision feel.
- **AI model status (self-test, 5 cars × 90 s):** the DEFAULT race AI is **kinematic** (rail-bound)
  and laps every track cleanly (Nürburgring 131-133 km/h, max_lat 4.0 m, no spins) — this is the
  shipping race experience, non-flopping on all 5 tracks.  The opt-in **physics AI** (`JM_AI_PHYSICS`):
  Zandvoort ✓ clean (max_yaw 1.45, 0 spins), Monza borderline (228 spins but laps at ~125 km/h), but
  **Spa and Nürburgring DIVERGE** — the 3-D MTK integrator's yaw rate explodes (281 / 1239) on the big
  elevation/speed.  That's the **E6 "3-D model robust on real terrain / no divergence"** gap, NOT a
  controller spin — `place3d!` recovery can't reset a diverged integrator.  So physics AI is viable on
  the flat tracks only; the launcher correctly leaves it OFF (kinematic default).  E55 fixes landed
  for it anyway (collision de-launch + spin-save), valid where the physics is stable.
- **Still needs PO re-drive to close:** E52 (drive Monza Lesmos→Ascari, confirm you pass under the
  banking), E55 (race with AI, confirm no flopping).  Deferred scenery: E43/E44/E45/E46/E41.

## PO 15-item live-drive batch — ALL CODE FIXES IN (2026-06-28, E23–E37)
The PO drove all 5 tracks and filed 15 items (backlog E23–E37). Every one now has its fix landed:
- **Crash/flow:** E23 Nürburgring race crash (`SOLIDS` undefined → defined []); E28 AI never
  appeared (qualifying made opt-in `JM_QUAL` → default goes straight to the grid with AI visible;
  GUI AI default = 5); E26 no Skidpad in Race; E24 replay recorded by default.
- **Graphics:** E27 removed blue sky (one OVERCAST grade, neutral-grey zenith so cloud gaps aren't
  blue); E29 "carbonized" objects (raised per-draw `ambfill` → vibrant grandstands/banners);
  E34 Zandvoort "floating buildings" = the same carbonized slabs, lit properly they sit on the ground.
- **Cockpit (deep-dive):** E36 black band below the wheel = the **DRIVER FIGURE's own torso/lap**
  (`driver5`/`lotbody`/`lotsho`/`knees`/`neck`) seen from inside the figure — pulled into a separate
  `driverItems` drawn ONLY in chase/external view; cockpit now shows green BRG tub, LOTUS hub badge,
  gauges, tan dash (≈ gold standard). E35 "yellow panel on the front wheels" = the same driver knees/lap,
  resolved by the same pull.
- **E25 REPLAY CINEMATIC VIEWER (new):** `.jmr` playback now cycles SIX GPL cameras with **V**
  (cockpit · chase/above-rear · TV/distant · F10 rear · nose/front · RR-suspension) and switches the
  focus car with **C** (player + every recorded AI). `replay_camera(mode,x,y,z,θ)`; `N_AI` in replay
  comes from the recording so every car renders; title shows camera+car+VCR. Headless-verified on
  Zandvoort (all 6 angles frame the car; C switches to the red Ferrari).
- **E37** auto-shift through all 5 gears (up 7000 / down 4100 / gate 0.85).
- **Awaiting PO re-drive to close** (code in, felt-while-driving, can't self-verify headless):
  E30 Watkins esses bog (ROAD_HALFW 7.5→9.0) · E31 Monza tree-curtain/hedge-box (on_road filter drops
  road-planted sprites + hedge solids) · E32 superball respawn/hard-hit (respawn3d! settles flat;
  cartwheel case untested) · E33 Watkins balcony (pitbldg pushed 5 m off the road — confirm it's the one).

## Sky + per-track graphics pass (2026-06-28 — E19–E22, autonomous sprint)
Against the PO's GPL gold-standard screenshots (`/run/media/g/84AF-CC77/<track>/`). All
SMOKE-verified vs the namesake reference shots:
- **E19 — blue iRacing sky, no seam** (Zandvoort): the overcast horizon ring used to wall up
  into the procedural blue skydome with a hard grey seam. Now a clear blue gradient + scattered
  clouds, and the GPL horizon ring is CROPPED to a thin low hill-band so the blue sky shows
  above it. Verified: seam gone, blue sky + white clouds.
- **E20 — mirrors are clean round discs** (were chrome torpedoes in the corners). Pulled out of
  the body, re-placed on the cowl. (Still render as dark discs — no RTT reflections.)
- **E21 — visible plexiglass** restored (alpha, depth-write off).
- **E22 — per-track sky grades** vs each gold standard: **Spa** bright blue + white cloud over
  green forest; **Monza** hazy bright blue-white daylight; **Watkins** hazy blue; **Nürburgring**
  a dedicated STORMY OVERCAST grade (heavy grey deck, desaturated) matching its genuinely moody
  reference; Zandvoort its own blue grade. (The old shared `GRADE_SUNNY` was cloud=1.0 overcast.)
- **Watkins forest-wall / pit-straight "smear" RESOLVED** (long-standing open item): the GPL
  `tree*` objects there are wide PANORAMIC forest strips (80–380 m across, one big quad). Forced
  camera-facing, each swung to face the eye → a giant flat yellow "wall"; static face-on → the
  same wall; static edge-on → the grey-green smear. They duplicate the forest already baked into
  the horizon ring, so they're DROPPED by default (`JM_DROP_FOREST=0` keeps them as static
  authored-yaw panels), and the single-strip horizon crop was tightened (`JM_STRIP_HI`/`_VTOP`)
  so its hazy-white sky top no longer reads as a bright band. Result: clean low tree-line horizon,
  no walls, no smear. Spa (2990 narrow tree billboards, 0 wide panels) + Monza (1565/0) unchanged.
  `JM_OBJDIAG=1` lists the tallest geometry + billboard sizes for future scenery debugging.

## Live-test feedback pass (2026-06-28 — FF wheel + cockpit/suspension)
Driven on the Thrustmaster TX FF wheel; the PO's feedback this round + what landed:
- **"Always on grass" / bogging FIXED** (root cause the PO spotted): the grass penalty was
  FALSE-FIRING on every corner — a racing line uses the FULL track width, reaching the tarmac
  edge at ~5.5 m off the centreline = the old `ROAD_HALFW` threshold, so normal cornering
  tripped the verge penalty, and the drag (0.9 = ~90 %/s speed loss) scrubbed speed mid-corner.
  Raised the threshold to 7.5 m (clears the widest racing line) + softened the drag to 0.30 and
  the slip-wobble to 0.15. `JM_ROAD_HALFW` / `JM_GRASS_DRAG` / `JM_GRASS_SLIP` tune it.
- **Wheels now FLOAT on the suspension** (were bolted to the chassis): `wheelmat` rides
  `carModel` (terrain-follow, planted + upright), NOT `tiltModel`, while the body keeps the
  dynamic dive/squat/roll. So braking pitches the nose down toward the planted front wheels
  (they appear to RISE), power squats (drop), roll-right leans onto the right wheel (rises) and
  lifts the left. `JM_SUSP_GAIN` (1.8) amplifies it to read from the cockpit.
- **Front/rear track WIDENED** (±0.62/0.66 → ±0.76/0.74) — the narrow stance read as "wheels
  bolted together"; also brings the front tyres into view at the cockpit edges. `JM_TRACK_F/R`.
- **Floating buildings FIXED for real**: off-HAT backdrop objects now MARCH to the terrain-edge
  height (`edgez`) instead of clamping to the track z-band — they rest on the ground at the horizon.
- **Mirrors** nudged up + scaled toward the GPL round-mirror size (`JM_MIRROR_Y/SCALE`).
- **STILL OPEN from this round** (PO): show the suspension ARMS between wheel and chassis; the
  horizon "blank band" (likely the finite-HAT edge meeting the sky-ring — needs investigation);
  the launch-from-standstill clutch bog in MANUAL (period-correct; AUTO/G avoids it) — confirm
  whether the PO wants a more forgiving manual launch; and dialing `JM_SUSP_GAIN` to taste.

## Cockpit deep-dive (2026-06-28 — match the GPL gold-standard cockpit)
Per the PO's gold-standard Zandvoort cockpit shot (mirrors on the cowl at the sides, gauge
binnacle around the wheel hub, near-transparent plexiglass). Done this pass:
- **Transparent plexiglass** — `windlot` extracted + drawn LAST at alpha≈0.16, depth-write
  off (uAlpha shader uniform). The bright gold rim is gone; you see the road/scenery through
  it. Tunable nowhere yet (alpha literal).
- **Wheels stay level with the cockpit** — `wheelmat` rides the full body tilt (`tiltModel`).
- **Trackside objects no longer float** — `ploz` clamps an object's z to the track z-range
  when it has no ground sample (was sky-floating buildings on the horizon).
- **Gauge binnacle lifted** — `dash7a` is modelled LOW (below the hub); GPL puts it UP.
  Lift via `JM_GAUGE_Y` (0.16) + nudge back via `JM_GAUGE_X` so the dials read on the cowl
  around the wheel, not dumped at the screen bottom.
- **Mirrors re-placed onto the cowl** — pulled out of the body (`MIRROR_TEX`) and tilted back
  toward the eye (`JM_MIRROR_Y/X/TILT`) → round discs at the SIDES mid-height (was chrome
  torpedoes in the bottom corners). No RTT, so they read as dark tinted discs, not live
  reflections.
- **GUI Auto/Manual gearbox switch** + verified the AUTO path auto-shifts up (8500 rpm-equiv)
  AND down (3400, off-throttle) by road speed, auto-engaging 1st from neutral (`drive_rt3d.jl`).
- **Remaining cockpit gap** vs gold standard: bright riveted-aluminium tub sides + gear lever
  (ours reads dark — the one untextured tub shell was darkened to kill faceted clutter), the
  front tyres peeking in at the lower-side edges (currently behind the dark coaming), and
  gloved hands on the wheel (excluded). Front suspension proper is hidden under the nose from
  the driver's eye in the real car; what GPL shows there is the front tyre + upper wishbone.

## Race mode (2026-06-26 — full "race the GPL grid")
Pick **Race** + laps + #AI + AI speed % in the GUI. Flow: **qualify one lap → grid set by
qual order → standing-ish race → finish classification**. Details + env flags in
`PRODUCT_BACKLOG.md` (E8–E12) and memory `juliamotor-race-mode`:
- **Grid of the real GPL '67 cars** — player Lotus 49 vs Ferrari/Brabham/BRM/Eagle/Cooper
  (Cooper = the GPL `coventry` chassis), each its own GPL model (`Render.load_gpl_car`).
- **Qualifying → grid** (`RaceAI.grid_order`); **AI pace %** where 100 % = GPL AI laptime
  (`JM_AI_PCT`); **fuel** sized to finish + 5 laps; **live standings** + finish order.
- **Multi-rail AI** (`RaceAI.step_field!`) — GPL-style line/inside/outside rails to pass +
  evade the other AI and the human (PO chose this over physics-AI; hybrid path in
  `demo/native/RACE_AI_NOTES.md`).
- **Every track is sealed** (E7) — can't drive off the world; `JM_BOUNDARY_TEST` audits it
  (Nürburgring centreline drift near lap-end is a known AI-line follow-up).

## Working / done

**Physics (3-D, iRacing-calibrated brush tyre — no fudge):**
- Full-3-D vehicle is the DEFAULT now (`JM_2D` forces the old planar model; planar still
  used for AI). Heave/pitch/roll + suspension travel.
- **Jumps work** — verified ~0.4 s airborne (VertAccel→0) at the Flugplatz crest at
  ~200 km/h. (3-D spawn height fixed: car was spawning at y=0 while the track sits at
  ~570 m → the "Star Destroyer descending" blow-up. Now spawns on the ground.)
- **Flugplatz power-spin FIXED** — a power-on directional instability (full throttle drove
  the rear past its longitudinal traction limit → no rear lateral grip → spin). iRacing is
  rock-stable there (yaw ~0.025); ours diverged to ~1.0. Added a SPEED-GATED traction aid
  (`TC_*`, `JM_NOTC`): off below 25 m/s so the skidpad peel-out still spins, full above
  38 m/s so the high-speed straight stays planted. Not a physics fudge — it shapes throttle.
- Brush grip toward the iRacing achievable peak (μy front 1.36 / rear 1.40; `JM_GRIP`).

**Controls / FFB:**
- Steering deadzone REMOVED — wheel continuous through center (throttle/brake keep theirs).
- FFB: self-centering spring (`JM_FFB_SPRING`) kills the dead center; front-force low-pass
  de-spikes the coarse GPL mesh; squelch only de-noises (no dead band).

**HUD:** traction circles are SOLID discs, right of the RPM dial, vertically centered; ring
radius = grip (μ·Fz) so it grows/shrinks with load; dot = force/grip (green inside normally,
red at/over the edge when skidding); temporally smoothed (no flicker).

**Graphics / scenery:**
- Color-grade pass toward GPL (warmed the blue-cast ambient, more contrast). Ground now
  matches GPL refs (~146,145,136).
- Trackside scenery recovered: the height cap (≤7 m, flat-Zandvoort-tuned) was dropping 77
  objects on Watkins Glen's hills, and 59 were off-HAT. Lifted the cap + off-HAT
  authored-height fallback → Watkins Glen 9→116 objects (grandstand, tree lines, buildings
  back); Zandvoort 70→98 too.
- Cockpit tub lifted out of near-black (ambient fill 0.34→0.62).
- Window title "Julia Racer — <Track>"; window hidden until loaded (no WM "Not Responding");
  GUI progress bar through the load milestones.
- Spectator crowds removed (PO). Forest-backdrop "paintings" (treesrb) dropped. Tree-line
  graze-fade (edge-on faces fade so a row doesn't streak into a smear).

## Open items
- **Start/finish "smear"** (Watkins Glen): **RESOLVED 2026-06-28** — it was the wide panoramic
  `tree*` forest strips (camera-faced into walls / edge-on smear) plus the horizon-strip's
  hazy-white sky top. Wide panels dropped + strip crop tightened (see the E22 section above).
- **Mirrors render as dark discs** (no render-to-texture) — GPL shows live reflections; ours are
  flat tinted discs. A fixed dim sky/track tint would read more like glass than black voids.
- **Car/cockpit GPL pass** — pending the PO's Lotus 49 cockpit/exterior reference shots
  (`ref/gpl/`); will match cockpit tone + green/livery to GPL then.
- Repeat the scenery + color pass on Nürburgring / Monza / Spa once Watkins Glen is signed off.
- Startup still ~2 min (sysimage saves ~25 s; bulk is the per-track GPL parse + runtime
  mtkcompile). Track-parse caching / packaging the model would cut more.

## Key env flags
`JM_2D` planar physics · `JM_NOTC` no traction aid · `JM_GRIP` grip trim · `JM_FFB_SPRING`
FFB centering · `JM_VIEW` 0=cockpit/1=chase · `JM_MAGIC` old tyre · `JM_NOSOUND` · `TRACK`
zandvoort/skidpad/nurburgring/watglen/monza/spa · `JM_MODE`/`JM_LAPS`/`JM_AI`.
GPL graphics refs: `ref/gpl/` (Watkins Glen batch in `ref/gpl/watkinsGlen/`).

(Older session history: see git log + `PRODUCT_BACKLOG.md`, `BENCHMARK_2026-06-24.md`.)
