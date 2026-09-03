# Julia Racer — Product Backlog & Sprint Plan

**Product Owner:** user (pre-approves sprint planning + reviews).
**Goal:** a complete Julia "GPL-like" racing app — Training / Practice / Race modes,
up to 5 AI cars, user-set lap count, GPL tracks (Zandvoort, Nürburgring, +Watkins
Glen, Monza, Spa), GPL-fidelity graphics (incl. the Lotus 49), glitch-free, and a
**physics-based (Modelica-like) iRacing Lotus 49** model — no fudge factors.


## STATUS INDEX (rebuilt 2026-08-31)

Maintained by hand because the document cannot be scanned reliably: sections carry ✅/🔴 markers
from *sub-sprints*, so an automated pass mis-attributes a sub-item's marker to its parent, and
several parents are epics with mixed children. Two audits of this file gave different answers before
this index was written; that is what it exists to stop.

**Confidence is stated per row.** "assessed" = I verified it this session or landed it myself.
"needs review" = I could not establish it from the document and did not guess.

### 🔴 OPEN — PO-raised, actionable

| item | what | state |
|---|---|---|
| **E85** | EPIC: multiplayer, the way GPL did it | **sprint 1 DONE** (E85-S1): poses cross two processes exactly, both ways, gated. Sprints 2–4 open. |
| **E105** | a setup tab exposing modest chassis-setup changes | **values + reset DONE and gated** (E105-S1); the UI shell is the PO's call. NEW 2026-08-31. Relaxes the "no modifiable parameters" constraint, scoped to setup. assessed |
| **E104** | every car floats 20–40 cm above the road; off-road contact is elastic (levitate/bounce) | **half (b) FIXED** (E104-S1): a −999 "off the mesh" sentinel was passing an `isfinite` guard and reaching the physics — 20.9 m of vertical travel, now 0.00. Half (a), the floating, is still open and needs a capture. |
| **E102** | rear axles point outward/downward; must be horizontal, hub to chassis | **OPEN — two of my own diagnoses withdrawn** (S1: omitted BODY_OFF; S2: conflated components sharing a texture). Established: the assembly and wheels agree (brake disc within 2.8 mm). S4: 65 of 89 triangles are ONE connected mesh (so there is no separable shaft to level), but an isolated **3-triangle `axlelot` sliver** reaches the wheel plane and drops 0.099 m — the best candidate for the PO's "sticks". Needs a capture; three headless approaches are enough. |
| **E103** | wheel loss in a collision hyperspaces the car to the start line | **mechanism found + fixed + gated** (E103-S1): the containment seal PLACES the car at its last on-track point, which initialises to spawn. Not yet seen in a real wreck. |
| **E90** | Monza and Watkins have almost no collidable barrier objects | open; the gate passing IS the symptom. assessed |
| **E91** | "Tesla brakes" — lift-off decelerates ~1.67× too hard | PO confirmed right by measurement (S4). Fix not landed. assessed |
| **E80** | 10 fps at Spa in cockpit view | analysis to S4; 725 s of load attributed to the trackside block. No fix landed. assessed |
| **E81** | floating/misplaced billboards and buildings at the Ring | open; the Ring bypasses the pipeline the other tracks use. assessed |
| **E76** | restore objects deleted after the Ring start/finish | open, lead only. assessed |
| **E78** | improve all 5 tracks against the gold videos | epic, open. assessed |
| **E79** | audit every row-of-people object on all 5 tracks | partially served by E101's filter; the 5-track audit is not done. assessed |
| **E85** | EPIC: multiplayer, the way GPL did it | open, not started. assessed |
| **E60** | Zandvoort gold-video parity | epic, ongoing. assessed |
| **E64** | cockpit/chase parity | epic, ongoing (E82/E83 are its children). assessed |

### 🟡 AWAITING THE PO — implemented, needs your eye

| item | what | why it is not closed |
|---|---|---|
| **E83** | vegetation brightness | palette + unlit sprites fixed and seen on screen; a residual ~1.4× gap remains. Must NOT be closed with a grade change. |
| **E84** | GPL's lateral tables as the AI line | implemented behind `JM_AI_GPLLAT`, **default OFF** — it makes the field run as a train, which may be correct (GPL's fields do queue). Needs a re-drive. |

### ✅ CLOSED (assessed this session or landed by me)

E57, E77, E86, E87, E88, E89 (AI lunging 1.83→0.46 cycles/car-lap), E92, E93 (clutch — physics
exonerated), E94, E95, E96 (no bounce-back at any speed, S5), E97, E98, E99, E100 (gearbox, mass,
spring rates, ride height all from the ibt; camber is *unmodelled*, not frozen), E101.

**E82 is CLOSED-THEN-REOPENED:** the driveshafts were restored and verified on screen, and the PO
then reported the remaining defect as E102.

### ❓ NEEDS REVIEW — I could not establish these from the document

**E56** (all-Modelica epic — gates exist and pass, but the epic's own closure is unstated),
**E59** (sprint log; E59.2/E59.3 marked ◑ partial), **E65** (Monza banking & Lesmos scenery),
**E67** (launch time — the cache fix landed, 762 s → 1.5 s, but S1 is marked ◑ PARTIAL),
**E68** (per-face road-facing selection — an implementation spec; unclear whether built).


## Definition of Done (per item)
- Builds + headless smoke (`JM_SMOKE`) clean; no regressions in `JuliaMotorMTK` tests.
- For visible items: an offscreen snapshot verifies the change.
- Committed to `julia-racer` with a clear message.

## Epics → Backlog
- **E1 Modes & race config:** Training/Practice/Race; lap count input; race start/finish/results.
- **E2 AI:** up to 5 AI cars following the `.trk` racing line with pace + spacing control.
- **E3 Tracks:** add Watkins Glen, Monza, Spa (GPL `.dat`/`.3do`/`.trk` pipeline).
- **E4 Graphics:** fix glitches (flicker, cockpit "rug"/windlot, floating people); GPL look.
- **E5 HUD:** traction circles beside the RPM gauge. ✅
- **E6 Physics:** complete physics-based (brush-tyre) Lotus 49 vs iRacing telemetry; remove
  fudge factors; make the 3-D model robust (no divergence on real terrain).
- **E7 Track boundaries (PO-added 2026-06-25):** every track is bounded as in GPL — you can
  never sail off the edge of the world. Going off track quickly meets a fence/hedge/wall/Armco
  that collides and contains the car inside the game world (per-track boundary from the GPL
  geometry / ribbon edge). Slotted into Sprint 4 (world) — see plan.

### PO race-completeness batch (2026-06-26) — "use scrum to achieve these epics"
- **E8 Distinct GPL grid:** the 5 AI cars are the standard GPL '67 chassis — **Ferrari,
  Brabham, BRM, Eagle, Cooper** (= GPL `coventry`) — each rendered as its own GPL car, not
  copies of the Lotus 49. The player is the Lotus 49. All look like the GPL cars (PO ref shots
  on the `84AF-CC77` drive). Lotus 49 cockpit per the ref shots.
- **E9 Qualifying → grid:** a qualifying lap before the race sets the starting order (player's
  best qual lap vs the AI pace ranks the grid).
- **E10 Fuel:** the Lotus starts with enough fuel to finish **race length + ~5 laps** (tank
  sized from a per-lap burn model; HUD fuel readout). The AI need not model fuel.
- **E11 AI pace %:** the user sets AI speed as a percentage where **100 % = the GPL AI car
  laptime** for that track; the field's pace scales so a clean lap ≈ refLap / pct.
- **E12 AI control = JM 2-D model, rFactor-style:** the AI cars use the JuliaMotor **2-D**
  vehicle model, driven by a path-following controller (the way rFactor's AI drive the AIW
  line), not a kinematic rail. Robust kinematic fallback kept (`JM_AI_KINEMATIC`).

## Sprint plan
- **Sprint 1 — HUD + race config (E5, E1).** Traction circles relocated ✅; GUI mode/laps/#AI
  inputs; game mode logic (race → finish at N laps; practice/training = timed/free).
- **Sprint 2 — Tracks (E3).** Watkins Glen, Monza, Spa selectable + drivable (HAT + ribbon).
- **Sprint 3 — AI (E2).** 1–5 AI Lotus 49s on the racing line; grid start; lap/position.
- **Sprint 4 — Graphics + boundaries (E4, E7).** Glitch fixes; GPL-fidelity pass; JM_3D render
  robustness; per-track collision boundaries (no driving off the world).
- **Sprint 5+ — Physics (E6).** Brush-tyre Lotus 49 in `JuliaMotorMTK`; validate vs the iRacing
  `.ibt`; replace the calibrated-curve tyre; JM_3D divergence guards.

### "Comparable to GPL" epics (PO 2026-06-26, autonomous — PO away for hours)
Goal: make JM look + behave like GPL, but with the superior JM Modelica-style engine
(iRacing-calibrated). PO pre-approves all planning/reviews; work autonomously, verify with
offscreen snapshots (vs `ref/gpl/` + the PO's lotus49/AI shots) + headless tests.
- **G1 Cars look like GPL:** the Lotus 49 + 5 AI chassis match the GPL gold standard —
  body livery DECALS (yellow nose stripe, #1 roundel, TEAM LOTUS), the cockpit gauge
  cluster, the tan scuttle (done), driver. Crack the decal/UV gap (textures resolve but
  render flat green).
- **G2 Hybrid-physics AI:** AI run the JM 2-D physics model (real accel/grip/inertia)
  steered by a rail-targeting controller — robust (no spins) across all tracks.
- **G3 Realistic group behavior:** no slot-car/bead riding (done: longitudinal physics),
  no skittering between rails ("water-insect") — deliberate, committed passes with
  hysteresis; believable pack racing like GPL.
- **G4 Rigid-body collisions:** ram an AI → both cars react with impulse + yaw + rotating
  wheels (the player fully in the physics), as in GPL.
- **G5 Trackside-object collisions:** hit a fence/hedge/building → a physical collision
  response (not just the invisible HAT snap-back), as in GPL.

Sprint order (autonomous): **GA** Lotus/AI GPL fidelity (G1) → **GB** smooth racecraft,
kill skittering (G3) → **GC** hybrid-physics AI (G2) → **GD** rigid-body car collisions (G4)
→ **GE** trackside-object collisions (G5).

### Autonomous session log (2026-06-26, PO away)
- **GA Lotus fidelity** (partial): tan scuttle restored (`windlot`) — committed. Decoded all
  Lotus textures: the green-body livery (stripe/#1/TEAM LOTUS) is NOT in any texture (GPL
  driver-skin system); gauges (`dash7a`) + driver arms render dark/wing (UV/geometry) — deep
  RE deferred. AI chassis already show distinct GPL liveries.
- **GB skittering** ✅ (commit): pass hysteresis + commitment → 60 s packed field = 1 lane
  reversal (was hundreds). Also longitudinal PHYSICS accel + player-relative pace cap landed
  earlier (a844e17).
- **GD car collisions** ✅ (commit): `bump!`/`bump3d!` apply a real impulse to the player's
  vehicle state (velocity + yaw rate); momentum-exchange on player↔AI contact. Verified live.
- **GE trackside collisions** ✅ (commit): the world-edge boundary is now a physical bounce
  (restitution + fence-grab scrub + glance spin) via `bump!`, not a snap-back.
- **GC hybrid-physics AI** ✅ (commit e97cb45): INTEGRATED + live (default; JM_AI_KINEMATIC
  fallback). `DriveRT.build_cars` shares one compiled MTK system across 5 cars (~29 s, not 5×);
  `RaceAI.plan!` (brain) + `RaceAI.controller` (proven recipe) drive them; stuck-recovery snaps a
  stalled AI back to the line; collisions impulse the AI's physics car. Verified (JM_AI_TEST):
  Zandvoort 5 cars 0 spins ~110 km/h, Nürburgring 0 spins + drift recovery, ~1 ms/frame.
  **All five GPL-comparable epics (G1–G5) now delivered** (G1 Lotus livery/gauges partial — GPL
  skin/UV RE deferred).

### Race-completeness sprint plan (E8–E12, PO pre-approved 2026-06-26)
- **R-Sprint 1 — Distinct GPL grid (E8).** Generic GPL-car loader (`gplcar.jl`); AI field renders
  Ferrari/Brabham/BRM/Eagle/Cooper, auto-levelled, per-car wheels. Snapshot verifies 5 distinct cars.
- **R-Sprint 2 — AI pace % (E11).** Per-track GPL ref-laptime table; AI target speed scales to
  refLap/pct; `JM_AI_PCT` + GUI %.
- **R-Sprint 3 — Qualifying → grid (E9).** Qual phase sets grid; race starts in grid order.
- **R-Sprint 4 — Fuel (E10).** Per-lap burn, tank = (laps+5)·burn, HUD readout.
- **R-Sprint 5 — Physics-model AI + results (E12).** AI on the JM 2-D model + path controller;
  live standings + finish/results. Kinematic fallback retained.
- **R-Sprint 6 — Boundaries audit (E7).** Probe all 6 tracks; confirm the car can't leave the world.

## Status log
- 2026-06-25 Sprint 1 started. E5 done (traction circles → beside RPM dial, `render.jl`).
- 2026-06-25 Sprint 1 DONE (commit 71aa1ee): E5 + E1 modes/laps.
- 2026-06-25 Sprint 2 DONE (commit cf5e457): E3 — Watkins Glen (`watglen`), Monza (`monza10k`,
  10 km), Spa (`spa67`, 14 km) selectable + drivable. Generic track loader (`track_file`
  extracts `.3do`/`.trk` from the track `.dat`); fixed an `Int32` dedup overflow on monza10k's
  garbage verts (coord-sanity filter + Int64 keys). All 6 tracks load headless clean.
- 2026-06-25 Sprint 3 DONE (commit 91b8e31): E2 — up to 5 AI Lotus 49s (`ai.jl` RaceAI).
  Rail-followers on the `.trk` centreline at curvature-limited speed; grid start; lap counting;
  rendered as Lotus 49s with shadows. Verified: a 4-car field drives the racing line ahead of
  the player. Full-physics AI + live standings = future polish.
- 2026-06-25 Sprint 4 (in progress): E7 DONE — per-track collision boundary. `HATResult.perp`
  added (`JuliaMotor/hat.jl`); `contain!`/`contain3d!` state setters snap the car onto the fence
  line + bleed speed (both adapters); the game collides the car at `FENCE`=13 m from the
  centreline (`JM_FENCE` to tune). Verified (`boundary_probe.jl`): car steered off-track is held
  at 13.01 m, 89→1 km/h — cannot leave the world.
- 2026-06-25 Sprint 4: JM_3D divergence guard DONE (E4/E6). The 3-D model could blow the vertical
  subsystem up on extreme terrain (pitch→296556° on the full Nürburgring → renderer drew garbage
  = the "flickering/flung-parts" the PO saw). `step_car3d!` now resets the vertical states to
  static if pitch/roll>0.7 rad or |heave|>3 m or non-finite (keeps in-plane motion). Verified:
  3-D drive smoke runs clean, guard doesn't false-trigger on legit jumps (pitch 0.16°). JM_3D is
  still opt-in; default is the planar model. Remaining S4 (E4): flicker/cockpit-rug/floating-people
  polish — best verified by PO test-drives.
- 2026-06-25 Sprint 5 (E6) started — physics-based BRUSH tyre. `brush_tyre.jl`: force from
  contact-patch bristle mechanics (adhesion→sliding), `F = μ·Fz·(1−(1−ξ)³)`, params PHYSICAL
  (μ friction, Cα/Cκ stiffness, kμ load-sensitivity) — no Magic-Formula Cy/Ey knobs, no ×1.13
  grip fudge. `fit/validate_brush.jl` identifies μ, Cα straight from the iRacing skidpad grip
  curve: FRONT μ=1.19 Cα=20.5 (RMS 0.021 g), REAR μ=1.21 Cα=24.0 (RMS 0.042 g) — BETTER than the
  fudged Magic Formula (0.20/0.30 g, which overshot to 1.4 g). KEY: the real Lotus tyre is a soft
  bias-ply μ≈1.2 peaking ~9-10°, not the fudged 1.4 g.
- 2026-06-25 E6: brush tyre WIRED into the car (opt-in JM_BRUSH). `BrushTyre` MTK component
  (smooth/branchless brush law, tyre.jl); `CornerAssembly`/`DrivenVehicleRT`/`build_car` thread a
  `brush` flag. Verified (`brush_grip_probe.jl`): the wired brush car peaks at 1.03 g vs the Magic
  Formula's 1.24 g — ratio 0.83 = exactly the physical μ ratio (1.21/1.45): the fudge is gone.
  NEXT: brush for the 3-D car; fit Cκ (braking) + kμ (multi-load); make brush default; JM_3D contact.
- 2026-06-25 E6: brush longitudinal + friction ANISOTROPY identified + added. `fit/fit_brush_long.jl`
  fits the brush Fx to the iRacing straight-line braking curve: μx=1.42, Cκ=28 (RMS 0.076 g, 1232
  samples). KEY physics: the tyre BRAKES at 1.42 g but CORNERS at 1.2 g — a real friction anisotropy.
  `brush_tyre.jl` + `BrushTyre` now use an elliptical directional friction
  μ_dir=1/√((cosψ/μx)²+(sinψ/μy)²) (pure-lat ⇒ μy, pure-long ⇒ μx). Re-verified: anisotropic brush
  compiles + drives stably, lateral grip unchanged (1.03 g, ratio 0.83). NEXT: kμ multi-load fit;
  make brush default (needs a JM_BRUSH test-drive for feel); 3-D contact robustness.
- 2026-06-25 E6: brush works in the 3-D car too (3-D contact robustness). Root cause of the
  earlier instability = the friction-ellipse `μdir=1/√(…)` was 1/0 at EXACTLY zero slip (the build
  warmup starts the car at zero slip → NaN). Reformulated to per-axis normalized slip
  (ξx=Cκκ/3μx, ξy=Cα·sinα/3μy; F = μ·Fz·sat·ξ/|ξ|) — no 1/0, physics-equivalent (planar grip
  unchanged 1.03 g). brush now WIRED into DrivenVehicle3D + build_car3d (JM_BRUSH); verified it
  drives + JUMPS to finite/sane state (v, pitch finite; the divergence guard absorbs the few
  recoverable hard-landing solver aborts). `build_car3d` gained a `dt` knob for finer contact.
  Remaining polish: silence the recoverable landing warnings (finer substep / tyre relaxation).
- 2026-06-25 E6: brush is now the DEFAULT tyre (the fudge is retired). Found + fixed a subtle bug
  that had made the brush undriveable: `ξ=sqrt(ξx²+ξy²)` is `sqrt(0)` at zero slip, and the
  Rosenbrock autodiff JACOBIAN `0/(2·sqrt(0))=NaN` (the force VALUE is fine — a function sweep
  couldn't see it; the Magic Formula's smooth sin/atan has no sqrt(0)). Fix: floor INSIDE the sqrt
  (`sqrt(ξx²+ξy²+1e-9)`). Also clamped the friction load-factor >0. `build_car`/`build_car3d` now
  default to brush; `JM_MAGIC=1` restores the old fudged tyre. VERIFIED: car launches from rest +
  accelerates (72 km/h in test_drive_rt, was stuck at 36); live app runs clean by default, no NaN.
  E6 essentially DONE — the physics-based, no-fudge Lotus 49 tyre is the live model.
- 2026-06-25 E6: brush FIXES the long-standing combined-slip glitch. The Magic Formula's
  combined law borrowed the lateral curve for the longitudinal force (the `test_combined_slip:34`
  open item); the brush carries a separate stiffness AND friction per axis, so it doesn't. New
  `test/test_brush_slip.jl` proves it: friction ELLIPSE holds (anisotropic μx≠μy), per-axis
  consistency is EXACT (pure Fx=brush_fx, pure Fy=brush_fy — the assert the Magic Formula fails),
  and the MTK BrushTyre component matches the pure law. A physics glitch fixed by the physics model.
- 2026-06-25 E6: kμ (friction load-sensitivity) is NOT fittable from the data — the iRacing `.ibt`
  has shock deflections (→ per-corner load) but NO per-corner tyre-FORCE channels, so grip-vs-load
  can't be measured. Kept at the physical default (0.08). This exhausts the autonomous, data-
  supported E6 work. E6 (physics-based brush Lotus 49, no fudge) is the live default model. ✅
  REMAINING (PO-dependent / cosmetic): confirm the brush feel (drive `JM_BRUSH` vs `JM_MAGIC`);
  E4 graphics polish (needs PO eyes on a drive); silence the cosmetic JM_3D landing warnings.
- 2026-06-25 PO bug batch (test-drive): (1) **FFB straight-line wander** — added a soft
  deadzone on the front-axle lateral force (`FFB_DEAD`, `JM_FFB_DEAD`, default 0.06 mg/4) so
  contact-patch noise no longer tugs the wheel on a straight; the self-aligning torque on real
  cornering is untouched. (2) **Silent on Nürburgring** — audio was `start()`ed at build time, so
  it underflowed/died during the 3-min track load; moved `EngineAudio.start` to AFTER the load,
  just before the game loop. (3) **"Grip a little low / slid off the hill"** — the brush μy was
  fit to the binned-MEDIAN skidpad curve (≈1.2 g), which UNDER-states the achievable peak (iRacing
  raw peak lateral 1.4–1.58 g; the driver corners ~1.4 g). Re-set μy toward the achievable peak
  (front 1.36, rear 1.40; μx 1.42/1.45) — the measured low-slip stiffness Cα is preserved, so it's
  a calibration to the iRacing PEAK grip, not a fudge. `JM_GRIP` scales it for feel. test_brush_slip
  still green; smoke clean.
- 2026-06-25 PO bug batch 2 (Nürburgring test-drive): (1) **Flugplatz "magnet pulls right,
  slides off the hill"** — diagnosed from the JM .ibt: at the climb (dist ~3900-4075 m) the car,
  at FULL THROTTLE in 3rd gear (~7500 rpm) at 48-50 m/s, develops yaw with steer=EXACTLY 0.000
  and diverges into a grip-limit spin (yaw 0.03→1.0 rad/s, lat pinned 13.2 = 1.35 g). Planar
  physics never touches terrain (groundz only sets render height) so it's NOT terrain-coupled —
  it's a power-on directional instability. `stability_probe.jl` reproduces: full-throttle release
  of a 7° steer DIVERGES, coast/part-throttle (0.4) RECOVERS. Mechanism: full throttle puts the
  rear at its LONGITUDINAL traction limit (wheel force ~5600 N > rear grip ~4800 N ⇒ wheelspin)
  ⇒ the friction ellipse leaves the rear ~zero LATERAL grip ⇒ any yaw runs away. The iRacing .ibt
  is the gold standard: full-throttle high-speed near-straight yaw median 0.025, max 0.127 rad/s
  (rock stable) — so OUR model was genuinely too unstable, a real defect. FIX (no physics fudge):
  a **traction/stability aid** (`TC_ON`, `JM_NOTC` to disable, `JM_TC_SLIP`) trims the THROTTLE
  input to hold the rear just below its slip limit (target κ 0.06) — shapes the driver input like a
  careful right foot / period driving aid; tyre + engine physics unchanged. Verified: 48 m/s
  full-throttle release now DAMPS (yaw 0.32→0.12) and the car still accelerates to ~290 km/h with
  straight-line yaw ≈0; mirrored into the 3-D step. (2) **Sound dies after a moment** — the audio
  feeder thread closed the stream + exited on the first xrun (the frame-rate hitch starves it);
  now it REOPENS and keeps going, latency 0.08→0.20 to buffer hitches. (3) **FFB dead-band then
  snap** — replaced the hard deadzone with a smooth squelch fy·fy²/(fy²+SQ²) (no flat band) + a
  1st-order low-pass on the force (kills oscillatory wander, fully continuous). (4) **Startup
  delay** — built a PackageCompiler sysimage (`jlracer.so`, auto-used by gui.py): ~24 s faster
  (140→116 s on zandvoort). Bulk remaining = per-track GPL parse + runtime mtkcompile of the
  included model; further cuts need track-parse caching / packaging the model (follow-up).
- 2026-06-25 E7 FIX (PO bug report: Watkins Glen "molasses"): the boundary was clamping at 13 m
  from the racing-LINE centreline, so driving on the wide grass/runoff (13–25 m off-line) was
  falsely contained every frame → speed bled to a crawl. Diagnosed from the PO's drive (.ibt: 84%
  of slow frames OFF-TRACK; the .txt log: 552 frames at 13–25 m lateral). Reconstructing those
  positions against the watglen terrain HAT: the car was **off the HAT 0% of the time** — always
  inside the world, just off the narrow ribbon. Fix: boundary now keys off the **terrain HAT (the
  world)**, not the ribbon — drive road + grass freely; only going off the terrain snaps you back
  to the last in-world spot (a fence collision). Would have triggered 0× on that drive. Verified
  watglen loads + runs clean.
- 2026-06-26 R-Sprint 1 DONE (commit fc31dea): **E8** — the AI grid is the 5 standard GPL '67
  chassis (Ferrari/Brabham/BRM/Eagle/Cooper=`coventry`), each its own GPL car, not Lotus copies.
  `render.jl` generic loader (`parts_bbox`/`GPLCarModel`/`load_gpl_car`) auto-levels each chassis
  onto a common floor + reuses Lotus wheel geometry with per-car wheel meshes; `extract_gpl_car`
  drops the GPL reflection tray + blob shadow generically (`*traymap`/`*shad`) and an AI-only
  green-placeholder drop. Verified offscreen (5 distinct liveried cars) + in-cockpit grid view;
  player Lotus unchanged. Harness `grid_snapshot.jl`.
- 2026-06-26 R-Sprint 5 part 1 DONE (commit 797e454): **E12 results** — live standings (rank by
  laps+fraction; title "Pos P3/6") + a full finishing classification at the flag.
- 2026-06-26 R-Sprint 5 part 2 DONE (PO chose GPL-style 3-rail): **E12 AI control** — upgraded the
  single-rail follower to GPL-style **multi-rail racecraft** (`RaceAI.step_field!`). Each AI follows
  the race line but moves to an inside/outside RAIL to **pass/evade** the nearest car ahead — another
  AI or the **human** (fed in as (s, lateral, v)) — and **matches speed when too close to get by**
  (never rams). Lateral motion rate-limited + clamped to the track. Verified: unit test (faster car
  rails out 2.2 m and overtakes) + app smoke (field drives away clean). Physics-AI feasibility was
  probed (planar step 0.23 ms → 5 AI ≈ 1 ms/frame; model stable on straights, naive controller spins
  in tight bends = the open autonomous-driver problem); the **hybrid physics+rail-brain** path is
  written up in `demo/native/RACE_AI_NOTES.md` for when there's time. — confirmed every track is *sealed*:
  the terrain HAT is a finite mesh, so the off-HAT containment means the car can never reach empty
  space. New `JM_BOUNDARY_TEST` self-test (reuses the real loaded HAT): marches off the centreline
  to find the world edge + checks for on-line HAT holes. Results — Zandvoort/Watkins Glen/Monza/Spa:
  **0 on-line holes, bounded both sides** (run-off up to ~520 m, all finite). Nürburgring: world
  still sealed but **4 on-line holes (44–600 m, at line-fractions 0.13/0.93/0.94/0.96)** = the 22 km
  `.trk` centreline DRIFTS off the road mesh near the lap end (the player drives the road, which is
  on the HAT; the AI rail-follower keys off this centreline, so the drift is an AI-line follow-up, a
  track-data fix). Hardened containment with a small off-HAT distance grace (`FENCE_GRACE`, 6 m) so
  sub-car-length mesh cracks don't false-trigger while the off-world guarantee stays tight. Epic 2
  (can't drive off the edge of the world) is met on all 6 tracks.
- 2026-06-26 R-Sprint 4 DONE (commit pending): **E10** — fuel. The Lotus is fuelled to finish the
  race + a ~5-lap margin: `TANK = (RACE_LAPS + FUEL_MARGIN)·burn_lap`, `burn_lap = FUEL_LPK·lapKm`
  (DFV-ish 0.55 L/km). Distance-based burn (during the race), a dry tank starves the throttle,
  respawn refuels; title-bar readout "fuel NL (M laps)". Practice/Training get a 40-lap tank;
  skidpad has no fuel. `JM_FUEL_LPK`/`JM_FUEL_MARGIN` tune it. Verified: 3-lap race → 8 laps fuel.
- 2026-06-26 R-Sprint 3 DONE (commit pending): **E9** — qualifying → grid. Race mode opens in a
  QUALIFYING phase (AI hidden); the player's one completed lap sets the grid via
  `RaceAI.grid_order` (player + AI ref qual times sorted pole-first). The field is then arranged
  *around* the player by qual order — faster qualifiers ahead on track (+s), slower behind, 2-wide
  lane stagger — so the working player lap/finish logic is untouched (no player reposition).
  `JM_NOQUAL`/smoke/solo/skidpad skip it. Verified: `grid_order` (pole/mid/last/Inf) + placement
  invariants (ahead⇔out-qualified) unit-tested; race smoke still renders the field.
- 2026-06-26 R-Sprint 2 DONE (commit pending): **E11** — AI speed %, 100 % = the GPL AI laptime.
  `REF_LAP` table (per-track GPL '67 anchor, `JM_AI_REFLAP` override) + `RaceAI.natural_laptime`
  (measures the rail follower's own lap) → speed `scale = naturalLap / (refLap·100/pct)`, applied
  in `RaceAI.step!`. `JM_AI_PCT` env + GUI "AI speed %" spin. Verified: 100 % paces Zandvoort to
  87 s (scale 1.16 on a 101 s rail), 80 % → 109 s.

---

## 2026-06-28 — PO MISSION: "a racing sim that looks just like GPL" (5-hour autonomous block)

**Goal (PO):** complete a racing sim that *looks just like GPL* — the 5 GPL tracks, the human always
in the Lotus 49. PO pre-approves all planning/reviews; work autonomously; if blocked, switch tasks.

**Gold-standard refs:** `/run/media/g/84AF-CC77/` — per-track screenshot folders (new `zandervoort/`
incl. fresh GPL cockpit shots 2026-06-28 02:5x) + per-car folders. KEY: GPL tracks are **colourful,
not grey** (vivid green grass, colourful crowd/signs); the GPL cockpit eye sits **low, looking straight
down the road** (not high looking down at the nose), with a big dark dash, the red Lotus-badged wheel,
and round mirrors.

### New backlog (epics E13–E18)
- **E13 Cockpit fidelity (TOP PRIORITY):** match the GPL Lotus 49 cockpit exactly — eye position low +
  level (see the road, not the nose), dashboard geometry (big central tach + flanking gauges, dark dash),
  red Lotus wheel, round mirrors. **Remove the HUD clutter** (pedal bar charts, traction circles,
  hand-drawn RPM dial) for now. Iterate vs `zandervoort/` cockpit refs.
- **E14 Results screen:** race finish → on-exit results/classification; quit or restart/choose-track.
- **E15 Trackside-object collision:** haybales/fences/buildings solid for player+AI. Snout head-on =
  bounce back (current); a SPINNING WHEEL into the bales adds ANGULAR+linear momentum → lifts the rear.
- **E16 AI line discipline:** keep AI ≥ a car-width off both track edges; prefer the racing line.
- **E17 Per-track graphics grade:** for EACH track, tune colour/scenery vs that track's ref folder —
  GPL is more colourful, less grey. (Zandvoort first — has the most refs.)
- **E18 Replay:** record all car poses per race, save with the .ibt; GUI picks an .ibt → 3-D playback
  (cockpit/chase) with VCR controls (play/pause/FF/rewind/clickable slider).

### Sprint plan (PO pre-approved)
- **Sprint 1 — Cockpit (E13):** strip HUD clutter; eye position + dashboard + wheel + mirrors to match
  the GPL refs. *DoD:* offscreen cockpit snapshot visibly matches `ref_zand1`.
- **Sprint 2 — Race loop (E14) + AI line discipline (E16).**
- **Sprint 3 — Trackside collision + spinning-wheel lift (E15).**
- **Sprint 4 — Per-track colour grade (E17), Zandvoort then the rest.**
- **Sprint 5 — Replay (E18).**

Progress log appended below as each item lands.

### Sprint 1 progress

**Sprint 1–3 done (2026-06-28):**
- ✅ E13 Cockpit: wide cockpit FOV (PROJ_COCKPIT 80°), low+level eye (JM_EYE 0.46/0.40/0.55), big dash with
  upright dials, mirrors restored, HUD decluttered (no bars/traction/RPM-dial). Matches the GPL refs. (977833c)
- ✅ E16 AI line discipline: LANE_MAX 3.8 + racing-line band 3.0 (≥ a car-width off both edges). (f875e16)
- ◑ E17 Zandvoort grade: GRADE_ZAND (sat 1.40, lifted ambient) — crowd/signs colourful; green grass still
  needs track-mesh material work (verges are sandy grey). (f875e16)
- ✅ E15 Trackside collision: SOLIDS list (haie bales/barriers/buildings/vehicles), snout=bounce, spinning
  wheel climbs → launch+roll, rear-wheel climb → bump3d! pitch kick lifts the rear. Player+AI. (84a51d3)
- ⏳ E14 Results screen, E18 Replay — next.

**Sprint 5 done (2026-06-28) — E14 + E18:**
- ✅ E14 Results screen (458e129): race finish → last_race_result.txt → GUI Race-Result dialog
  (Race again / Choose track / Quit).
- ✅ E18 Replay (382007c record, 868ef49 playback, 3c943a5 GUI): races record all-car poses → .jmr;
  JM_REPLAY plays it back from cockpit/chase with VCR keys (SPACE/←→/↑↓/V); GUI "Replay" tab picks a .jmr.
  Remaining nicety: a clickable in-GUI timeline slider (needs GUI↔game IPC; keyboard scrub covers seeking).

**ALL six PO epics for the block delivered (E13✅ E14✅ E15✅ E16✅ E17◑ E18✅).** Remaining polish:
green grass (track-mesh material), mirror glass (RTT), the clickable replay slider, per-track grades for
the other 4 circuits.

### Cockpit deep-dive (2026-06-28) — PO gold-standard pass
Against the GPL Zandvoort cockpit shot (`/run/media/g/84AF-CC77/zandervoort/…02-53-08.png`):
- ✅ Transparent plexiglass (`windlot`→`windItems`, alpha 0.16, depth-write off) — gold rim gone, road shows through. (419e4ca)
- ✅ Wheels stay level with the cockpit (`wheelmat` on `tiltModel`). (419e4ca)
- ✅ Trackside objects no longer sky-float (`ploz` clamps z to the track z-range). (e73eaac)
- ✅ Gauge binnacle lifted onto the cowl around the hub (`JM_GAUGE_Y/X`); mirrors pulled out of the body and
  re-placed as round discs at the SIDES mid-height (`JM_MIRROR_Y/X/TILT`) — was chrome torpedoes at the
  bottom corners. (c84d7df)
- ✅ GUI Auto/Manual gearbox switch; verified AUTO auto-shifts up (8500) AND down (3400, off-throttle) by
  road speed + auto-engages 1st (`drive_rt3d.jl`).
- Eye position re-tested (forward/lower) and REVERTED — moving the eye forward loses the wheel/dash framing;
  GPL's "closer" look is dash-geometry, not camera. Current eye (0.46/0.40/0.55) is correct.
- ⏳ Remaining cockpit gap vs gold: bright riveted-aluminium tub sides + gear lever (the untextured tub shell
  is darkened to kill faceted clutter — needs a real aluminium texture, not a flat brighten), front tyres at
  the lower-side edges (behind the dark coaming), gloved hands on the wheel.

## Autonomous block — 2026-06-28 PM (PO away 3 h, scrum pre-approved)
PO feedback on the FF-wheel live test (Image #15 ours vs #16 gold standard):
✅ gear bogging FIXED (grass false-fire). Remaining + new epics:

- **E19 Blue sky / kill the horizon seam:** ours draws a blue procedural skydome AND the grey GPL
  overcast horizon-ring, meeting in a hard discontinuous seam. PO wants a consistent iRacing BLUE
  sky (not overcast). Crop the 12-panel ring to a thin low hill-band + blue-sky GRADE.
- **E20 Mirrors:** still too big/chrome (torpedoes). Match the GPL round-mirror size/position
  (small discs on thin stalks, mid-height). `JM_MIRROR_*`.
- **E21 Transparent screen + suspension wishbones:** PO says "transparent screen MISSING" — we over-
  did the alpha (it vanished). Restore a faintly-visible plexiglass (yellow arcs, like #16) with the
  front suspension wishbones/rockers + front tyres visible THROUGH it.
- **E22 Per-track graphics grade vs gold standard (PO):** for EACH track, tune colour + scenery
  against that track's gold-standard screenshots in `/run/media/g/84AF-CC77/<track>/` — e.g. Spa via
  `/run/media/g/84AF-CC77/spa`. Tracks: zandervoort (done-ish), spa, monza, nurburgring, watkinsGlenn.

### Sprint plan (PO pre-approved)
- **Sprint A — E19 sky seam** (current track, highest-visible).
- **Sprint B — E20 mirrors + E21 transparent screen/wishbones** (cockpit fidelity).
- **Sprint C — E22 per-track grades:** Spa → Monza → Nürburgring → Watkins Glen, each vs its ref folder.
Progress logged below.

### Sprint review (2026-06-28, autonomous) — E19–E22 DONE, all SMOKE-verified vs gold standards
- **E19 ✅** blue sky, horizon seam GONE (Zandvoort): blue skydome + cropped low hill-band ring.
- **E20 ✅** mirrors are clean round discs on the cowl (no RTT → dark discs; tint = future polish).
- **E21 ⬛ partial:** transparent plexiglass RESTORED (alpha, depth-write off). **Front tyres /
  wishbones through the screen still DEFERRED** — the front tyres sit behind the dark cockpit
  coaming from the driver eye; isolating the GPL upper-wishbone + framing the tyres into the lower
  corners (without the prior eye-move regressions) is the remaining work.
- **E22 ✅** per-track sky grades vs each gold standard: Spa (blue+forest), Monza (hazy bright),
  Nürburgring (STORMY OVERCAST — its real look), Watkins (hazy blue), Zandvoort (blue). BONUS:
  the long-standing **Watkins pit-straight "smear" / forest-wall RESOLVED** (wide panoramic
  `tree*` strips dropped — they duplicated the horizon ring; single-strip crop tightened).
  Spa/Monza confirmed unchanged (0 wide panels). Commits: E19 ebecafb, E20/E21 5c62db2,
  E22 grades 4394e31, Watkins f9a5112.

## PO live-drive batch (2026-06-28) — "drove all 5 tracks" — E23…E37
Reported after driving all five tracks; ref shots in track-namesake dirs on `84AF-CC77`.
Status: ✅ done+SMOKE-verified · ⬛ partial · ⏳ open.
- **E23 ✅ Nürburgring race crash:** `UndefVarError: SOLIDS not defined` (solid_hit) the instant
  you touch the throttle — the `SKIDPAD||NURB` branch never defined `SOLIDS`. Fixed (empty list).
- **E24 ⬛ Replay store-by-default:** GUI "Record race replay (all cars)" checkbox, ON by default
  (untick → `JM_NOREPLAY`). Records all 6 cars. (replay multi-cam viewer = E25.)
- **E25 ✅ Replay camera controls:** the replay viewer now switches (a) CAR with **C** (cycles player +
  every recorded AI) and (b) VIEW with **V** through six GPL cameras: COCKPIT · CHASE (above-rear/"Nintendo")
  · TV/DISTANT (high panning whole-car) · F10 REAR (low bumper) · NOSE/FRONT (driver + nose) · RR SUSPENSION
  (right-rear tyre/tailpipe close-up). `replay_camera(mode,x,y,z,θ)` builds each geometrically off the
  recorded pose; window title shows camera + car + VCR state. KEY FIX: in replay N_AI comes from the
  RECORDING's car count (not JM_AI) so every recorded car gets a chassis to draw + focus on (was: empty
  track when focusing an AI). `JM_REPLAY_CAM`/`_FOCUS`/`_T` env overrides. Headless-verified on Zandvoort
  (all 6 angles frame the car; C switches to the red Ferrari with the field rendered). gui.py hints updated.
  (Could add more angles later — RF susp, top-down, distant-rear — the camera table is data-driven.)
- **E26 ✅ No skidpad in Race:** GUI greys out Skidpad when Mode=Race (and bumps off it).
- **E27 ✅ Remove blue sky (seam):** one OVERCAST grade for all tracks — skydome grey matches the
  GPL horizon-ring grey → the blue/overcast seam is gone (Nürburgring keeps its moodier storm grey).
- **E28 ✅ AI never appeared (except Nürburgring):** TWO causes — (1) GUI "AI cars" defaulted to 0;
  now defaults to 5. (2) Even at AI=5 the field was HIDDEN during the default 15-min practice/qual
  phase (the "press T to start" hint was log-only, not on-window), so Race looked empty. FIX:
  qualifying is now OPT-IN (`JM_QUAL` / GUI checkbox, default OFF) → Race goes STRAIGHT TO THE GRID
  with all AI lined up ahead and visible; floor it to launch the field.
- **E29 ✅ "Post-Hiroshima" carbonized trackside objects:** shadowed/away faces fell to ~0.13 bright
  → near-black. Raised object+wall `ambfill` (flat overcast fill) → vibrant grandstands/banners/
  buildings matching the GPL gold standard. SMOKE-verified Zandvoort + Watkins.
- **E30 ⏳ Watkins esses BOG:** car bogs through the esses — is that section's surface tagged grass /
  high-drag? Audit the Watkins `.trk` surface-type → drag mapping.
- **E31 ⏳ Monza objects across the track:** a "curtain of tree silhouettes" spanning the track, and
  a hedge-box near the underpass that traps the car. Monza-specific object placement / collision.
- **E32 ⏳ Superball respawn / hard hit:** car bounces straight up-and-down (stays horizontal) on
  respawn and on a hard object hit — no cartwheel/roll. Vertical subsystem not re-settled (zref
  stale on respawn) + on-ground attitude guard kills roll/pitch before a cartwheel can develop.
- **E33 ⏳ Watkins balcony support in the road:** a grandstand/balcony support protrudes onto the
  racing surface (img #23). Object placement / collision footprint.
- **E34 ✅ Zandvoort "floating buildings":** the dark slabs floating against the sky were the
  CARBONIZED objects (E29) reading as black cut-outs against the bright sky — properly lit they sit
  on the ground. SMOKE chase-view at the start shows no floaters. (Re-confirm while driving.)
- **E35 ✅ Zandvoort yellow panel on the front wheels:** RESOLVED by the E36 driver-figure pull — the
  yellow/tan panel "stuck to the front of the wheels" was the driver's knees/lap (`knees`/`lotbody`)
  seen from inside the figure. With the driver hidden in cockpit, the cockpit render shows green tub +
  badge + gauges and NO yellow panel (SMOKE-verified Zandvoort cockpit). Re-confirm while driving.
- **E36 ✅ Black cockpit band — SOLVED (deep-dive):** the band was the DRIVER FIGURE's own torso/lap
  (`driver5`/`lotbody`/`lotsho`/`knees`/`neck`) — from the in-car eye (inside the driver) his body
  filled the lower view and OCCLUDED the green tub + LOTUS hub badge. Pulled the driver out of CARP
  (`DRIVER_TEX`) and draw it only in CHASE view → cockpit now shows green tub, badge, gauges (≈ gold
  standard). Also found: the `grey`/`JM_TUB_GREY` param was a no-op (baked vertex colour used t.col) —
  now revived (gated >0.2) as a real silver-tub knob; keeping the GPL yellow floor recolours to silver
  but it's jaggy, so left dark by default.
- **E37 ✅ Auto-shift "always in 1st":** (from the prior message) tall close-ratio 1st pulled to
  ~115 km/h before the old 8500 up-point. Up 7000 / down 4100 / gate 0.85 → shifts through all 5.

### Sprint plan (this batch, PO pre-approved "scrum as before")
- **Sprint D — stop-the-bleeding (DONE):** E23 crash, E27 sky, E29 carbon, E26/E28/E24 GUI, E37 shift.
- **Sprint E — physics/placement:** E32 superball → E30 Watkins bog → E31 Monza curtain → E33 balcony.
- **Sprint F — cockpit fidelity (DONE):** E36 black band + E35 yellow panel (both = driver-figure pull).
- **Sprint G — replay cinematics (DONE):** E25 multi-camera/car replay viewer (6 GPL angles + car-switch).

### Remaining open (post-Sprint-G)
- **E32 ⏳ Superball respawn / hard hit** — respawn3d! unit-tested settles flat; hard-hit cartwheel
  still untested (needs live PO re-drive into a wall).
- **E30 ⏳ Watkins esses bog** — ROAD_HALFW 7.5→9.0 widens the drivable corridor; PO re-drive to confirm.
- **E31 ⏳ Monza curtain / hedge box** — on_road filter dropped 1565→1342 billboards + hedge solids; re-drive.
- **E33 ✅(tentative) Watkins balcony support in road** — collision removed by on_road SOLIDS filter (E31).
  Diagnostic added (JM_OBJDIAG mesh-in-road report + JM_OBJDIAG_LAT) → the closest building to the road at
  the S/F is `pitbldg` (lat −13.2 m, lapdist 89 m), an 8.8 m pit/press box whose balcony cantilevers over
  the road edge. Pushed it 5 m outward along the track normal (JM_PITBLDG_PUSH, Watkins default) → lat −18.2 m,
  overhang clears the 9 m road. TENTATIVE: couldn't visually confirm pitbldg is THE balcony from the spawn
  view — needs a PO re-drive (or the PO's screenshot/location) to confirm; if wrong, the diagnostic pinpoints
  the real mesh and the push is harmless/tunable.

### NEEDS PO RE-DRIVE TO CLOSE (code done, awaiting live confirm)
All of E30/E31/E32/E33 have their code fix in; they can't be self-verified headless (they're
felt while driving). Next PO session on Watkins + Monza closes them — or reopens with specifics.
- E30 Watkins esses bog · E31 Monza curtain/hedge · E32 superball (esp. the hard-hit/cartwheel case)
  · E33 Watkins balcony (confirm pitbldg was the one) · E34 Zandvoort floaters (confirm while moving).

## PO live-drive batch #2 (2026-06-28 PM) — "Spa race + all tracks", 28 screenshots — E38…E52
**CRITICAL (race-breaking):**
- **E38 🔴 AI cars hyperspace off-track + cartwheel/tangle (Spa, Nürburgring):** on throttle the whole AI
  field vanishes, reappears OFF the road to the RIGHT, proceeds parallel to the track in a tangled
  "inchworm", clumps up bumping each other, then the clump disappears and pops back 5 car-lengths on
  "like beetles missing legs" (cartwheeling, upside-down, superball-bouncing). Screenshots show AI on the
  right verge tumbling. Happens on the two BIG tracks (Spa ~5.7k objects, Nürburgring); Zandvoort/Watkins
  grids looked OK. Likely the 3-D physics-AI (AIPHYS) blowing up on these tracks' terrain/centreline, or
  the AI rail/lane offset placing them off-line. THE top priority — makes racing unplayable.
- **E39 🔴 Player BOG on the big tracks (Spa, Nürburgring):** car won't accelerate — RPM pinned ~1950
  (idle) at Spa, speed crawls 0–26 km/h in 1st; Nürburgring "pinned at 35 floored in 1st, bogs immediately
  in 2nd". Looks like a per-frame speed-scrub (grass-drag false-trigger on-road, or off-HAT containment
  bleeding speed) keyed to these tracks' HAT/centreline. Possibly same root as E38 (bad lateral/HAT).
- **E42 ✅ Spa off-world slide + superball — FIXED (commit 19038b0):** the boundary snap reset only the
  HORIZONTAL pose, leaving the vertical suspension loaded against the down-a-field height → re-entry slammed
  the contact = superball. `contain3d!` now gains `settle`+`groundz`: on a boundary hit it zeroes the
  vertical states and re-anchors zref to the snap-point terrain (same reset respawn3d! uses). Also mitigates
  E52's "can't get out" bounce. Needs PO re-drive to confirm feel.

**Scenery/placement:**
- **E40 ✅ Spa people-line into the road — FIXED (commit 462a1cc):** stand-crowd rows (peprow*) that
  projected onto the paved surface (|lat|<ROAD_HALFW) by Eau Rouge + the start straight are now dropped
  (19 rows removed at Spa); grandstands set back (|lat|>9) stay. JM_OBJDIAG now prints per-object relyaw.
- **E41 ⏳ Spa storefronts perpendicular** to the road (should be parallel) — the ENGLEBERT/pit buildings
  on the right are rotated 90° (yaw wrong). DEFERRED: JM_OBJDIAG relyaw shows Spa houses have a WIDE yaw
  spread (28–160°), no clean systematic 90° error → can't fix blind. Needs a GPL reference screenshot of
  the offending storefronts to know the correct facing.
- **E43 🔁 Watkins balcony STILL protrudes into the road** — E33 pitbldg nudge did NOT fix it; the real
  offender is a different object (re-identify from the Watglen start shot; the gantry/timing structure).
- **E44 ⏳ Nürburgring right-side objects carbonized** — left-side crowd/banners colourful, RIGHT side
  (pit wall/buildings) still post-Hiroshima dark. Per-side lighting/ambfill gap.
- **E45 🔁 Zandvoort horizon buildings still floating midair** — E34 thought-fixed; still hanging. Re-open.
- **E46 ⏳ Zandvoort crowd too blue** at the left grandstand (colour grade / crowd texture tint).
- **E51 🔁 Monza tree-curtain across the road at the Lesmos** (E31 re-open — still there).
- **E52 🟡 Monza tunnel wall + hedge maze trap — PARTIALLY FIXED:** the "superball-bounce + can't get out"
  was the E42 vertical-bounce loop (now fixed). JM_OBJDIAG shows no hedge/wall MESH on the road at the
  tunnel (br_tun at lat 2.2 is the overhead structure, not collidable). Residual "thick wall" is likely the
  tunnel section in the collision HAT (TRACKMESH bypasses the object HAT filter) — needs PO re-drive to see
  if E42 resolved it before chasing the HAT.

**Car / cockpit:**
- **E47 ✅ Auto-shift short-shift 1st/2nd — FIXED (commit 2dc660a):** up-RPM lowered for the low gears
  (1st=5000, 2nd=5800, 3rd–5th=7000) so the launch is clean instead of peeling out. Gated to auto mode.
- **E48 ✅ Mirrors angled DOWN — FIXED (commit 2dc660a):** JM_MIRROR_TILT flipped +22→−25 so the discs
  stand UPRIGHT facing the driver (verified in the skidpad cockpit render).
- **E49 ✅ Plexiglass "plywood board" — FIXED (commit 6f8bac4):** the "glass" was windlot, the tan SCUTTLE,
  drawn translucent → read as an angled plywood board. JM_WIND_ALPHA defaulted to 0 (draw skipped); the
  cockpit scuttle is cleaner without it.
- **E50 ✅ Wheel-centre shimmer — FIXED (commit 6f8bac4):** the LOTUS badge (lsterlog) was coplanar with the
  red hub face → z-fight. Badge offset ~3 mm toward the driver along the column axis. (Read as the player's
  steering-wheel hub; verified the badge still renders proudly.)

**Cockpit camera (PO correction 2026-06-28):**
- **E53 ✅ GPL cockpit head stabiliser — FIXED (commit 446c821):** the camera was bolted to the FULL chassis
  tilt, so fast suspension jolts rolled the whole world → landscape strobe → headache. Now the camera
  pitch/roll follow only a LOW-PASS of the chassis tilt (τ=JM_CAM_TILT_TAU=0.35 s) while the chassis is drawn
  at FULL tilt. PO's rule: "the horizon may tilt slowly but not quickly; quick tilt → the CAR does the
  tilting." Slow bank → view rolls with car (horizon tilts, chassis fixed); fast curb → chassis rocks on
  screen, horizon stays level. Needs PO re-drive to confirm the feel/τ.

**Deferred — need a PO re-drive or GPL reference screenshot at the specific spot (can't verify/​fix headless; SMOKE only captures the spawn frame):**
- **E43** Watkins balcony-in-road · **E44** Nürburgring right-side carbonized (start straight looks fine on
  both sides — offender is out on the lap) · **E45** Zandvoort floating horizon buildings · **E46** Zandvoort
  blue crowd · **E51** Monza Lesmo tree-curtain (on-road sprites already dropped by E31; residual is a wide
  near-road tree billboard — needs the spot to retune without stripping legit roadside trees).

## PO autonomous mandate (2026-06-28 night) — "run scrum till 8am; GPL look-and-feel clone"
PO away until 08:00 2026-06-29. Standing order: **run the scrum process autonomously; if a sprint is
blocked by an impediment only the PO can clear, switch to another sprint — don't stop** until Julia Racer
is a GPL look-and-feel clone. Two new EPICS:

- **E54 🏁 Clean race on all 5 tracks (no road obstructions, no grass-molasses on the racing line):**
  I can run a race at **Spa, Monza, Zandvoort, Watkins Glen, or Nürburgring** vs 5 AI cars with
  **(a)** no objects/obstructions on the drivable road (as the Monza banking wall / hedge-box was), and
  **(b)** no grass-like hindrance bogging a car that is ON the road (as at Watkins Glen E30/E39). Method:
  **spawn at increments around each track** (JM_START_S sweep) and verify (i) nothing blocks the racing
  surface, (ii) `groundz`/surface-tag never reads "grass/off-HAT" for a car on the centreline (no
  molasses). Build an automated per-track sweep harness (HAT + object scan) so this is regression-checkable
  headless. *Acceptance:* a clean flying lap on each track at racing pace with no stop/▲-height/▲-drag
  anomaly on the centreline, and no mesh/billboard intruding within the road half-width.
  - **E54a (this commit):** Monza banking underpass — the road passes UNDER the sopraelevata; the banking
    deck was in the collision HAT so the car climbed it / hit a wall. FIX: `HAT_EXCLUDE` drops the
    banking deck + bridge-banking textures from the HAT (still rendered); the ~20 m road-mesh gap under
    the first crossing is bridged by the in-corridor coast branch (off-mesh but inside the .trk corridor
    ⇒ no fence). Verified by JM_DRIVETEST HAT scan (no more 3.6–11.7 m banking spikes on the centreline).

- **E55 🤖 AI cars must not entangle / flop:** AI cars should never get entangled with each other and
  "flop around in strange ways". **Authorised simplification:** *ignore wheelspin (and, more generally,
  fine tyre dynamics) in collisions involving AI cars* if that stabilises them — AI may use a simpler,
  robust contact/handling model. *Acceptance:* a full race where the AI field runs nose-to-tail through
  every corner without cartwheeling, stacking, or vibrating apart (relates to E38 hyperspace/tangle).

### Autonomous sprint plan (PO pre-approved)
- **Sprint A — E54a Monza road clear (banking HAT):** ✅ code done; re-drive to confirm.
- **Sprint B — E54 sweep harness:** automated JM_START_S HAT+object sweep over all 5 tracks → report any
  on-road mesh/billboard or grass-tag-on-centreline. Drives the rest of E54.
- **Sprint C — E54b grass-molasses:** wherever the sweep flags a grass/off-HAT tag on the racing line
  (Watkins esses E30, Spa/Nürburgring bog E39), widen/retag the corridor so an on-road car never bogs.
- **Sprint D — E55 AI stability:** de-tangle the AI contact model (simplified AI collision; ignore
  wheelspin) so the field never flops. Folds in E38.
- **Sprint E — remaining scenery (E51/E44/E43/E45/E46/E41):** spot-render each via JM_START_S, fix.

### E56 — "all-Modelica human car" epic (PO directive, 2026-06-29)
PO: "the human car's full physical modelling is what gives GPL its sense of accuracy; the AI are
just slot cars that mustn't hog the spotlight by flipping." Every PLAYER *interaction* becomes a
physical force/parameter fed into the chassis ODE (never a `bumpX!`/`containX!` state hack); the AI
stay kinematic. Return-to-track = SHIFT-R only.
- **E56.1 ✅ force ports** (commit 27fc6f1): `DrivenVehicle3D` gains `Fx_ext/Fy_ext/Mz_ext` + `CdA_scale`
  ports summed into `D(u)/D(v)/D(r)`/drag (defaults ⇒ unchanged).
- **E56.2 ✅ port setters + `extforce3d!`**: `Car3D` setters for the 4 ports + a per-frame setter API.
  Verified (extforce3d_smoke): Fy→drift, release→decays, CdA 0.6→+10 km/h, Mz→yaw.
- **E56.3 ✅ draft = `CdA_scale`**: the player slipstream cuts frontal drag (a real aero tow the solver
  integrates), not a forward velocity bump; works vs the default kinematic field too. JM_DRAFT_CUT.
- **E56.4 ✅ trackside collision = spring-damper force**: new `contact_force` kernel — `:wall` (stiff,
  elastic → bounce) vs `:soft` haie hedges/hay (weak spring + crush give + viscous damper → drive in,
  bleed speed, get STUCK), per-frame impulse clamped for stability. SOLIDS tagged by kind; fed before
  the step; player `solid_hit→bumpX!` deleted (AI keep it). Verified (contact_smoke): wall bounces,
  hedge buries & sticks, no pass-through, no divergence.
- **E56.5 ✅ grass = per-wheel tyre μ**: `BrushTyre` gains `μscale`; `wheelmu3d!` sets each wheel's μ;
  the game projects all 4 wheels and drops μ to JM_GRASS_MU off the surface (a wheel on grass loses
  real grip + pulls the car), replacing the player bumpX! grass hack (AI keep theirs). Verified
  (wheelmu_smoke): μ=0.5 halves cornering grip.
- **E56.6 ✅ boundary = physical wall**: the world edge is now a stiff inward `contact_force(:wall)` —
  the car bounces off physically with NO routine teleport (the auto containX! snap-back is gone);
  recovery is SHIFT-R. A far failsafe (JM_FENCE_FAR=16 m past the edge) still hard-seals the world so
  the car can never fall into the void. Verified (boundary3d_smoke): contained at 20/40/60 m/s
  (penetration 2.6–4.4 m, bounces back, failsafe never fires, no divergence).
- **Physics is `include`d as SOURCE** (`drive_rt3d.jl`→`vehicle_3d.jl`/`tyre.jl`, `mtkcompile` at
  startup) ⇒ all of the above are LIVE at next launch, **no `jlracer.so` rebuild**.
- **Awaiting PO re-drive to close (felt, can't self-verify headless):** the draft slingshot feel, the
  hedge "get stuck" vs wall bounce, grass grip-loss/pull, and especially the **world-edge wall** (confirm
  it contains at racing speed with no jarring teleport; tune JM_FENCE_FAR / wall stiffness if needed).
  All six increments pass their headless smokes + the 40-frame full-game smoke (Zandvoort, AI) runs clean.

### E57 — Monza render legibility (PO-flagged, 2026-06-29, autonomous) ✅
PO: Monza "road renders near-white, barriers carbonized-black, banking renders as a wall → reads as a
maze you steer into; the other 4 tracks render correctly." Fixed the brightness legibility:
- **Root cause:** the GPL `asphalt` MIP is over-bright, and in the COMBINED circuit the drivable
  surface is split between the `trrow01` track mesh and placed OBJECTS (paddock/connector/banking) —
  drawn at full object brightness — so the start-line "snow" foreground was actually the `paddock`/
  `cgroad` objects, not the road mesh. A single brightness knob couldn't reach both.
- **Fix (Monza-gated):** per-surface grade of BOTH the track surfaces (classified by GPL texture name
  into a parallel `TRACKCAT`: road `trrow*`/`asp*`, barriers `armco*`/`yarmc*`/`brdg*`, banking `s##*`)
  AND the paved/banking OBJECTS by name (`paddock`/`cgroad`/`chicane`/`ascari`/`sec*`, `nbank`/`sbank*`
  banking — keeping ad-boards/grandstands bright). Road 0.72→0.42, barriers lifted, banking→grey.
  `JM_MONZA_{ROAD,DARK,BANK,OTHER}_{B,A}` tune it.
- **Verified** by offscreen snapshots (start + mid-lap tree-lined straight) + a Zandvoort no-regression
  render. **Deferred (E52):** the banking still reads as a flat slab (geometry) — now grey, not white.

### Render QA sweep + test verification (2026-06-29, autonomous, post-E57)
- **Cross-track render sweep (offscreen start snapshots):** Spa ✅ excellent (grey asphalt + yellow
  line, Armco, ENGLEBERT/pits, flags, crowds), Watkins Glen ✅ good (asphalt + dashed lines, KENDALL/
  DUNLOP gantry, hay bales), Zandvoort ✅ good. **Monza was the sole outlier** (fixed by E57). So the
  renderer is solid track-wide.
- **E46 blue crowd — confirmed cross-track** (worst on Zandvoort's main grandstand = oversaturated blue
  horizontal STREAKS; mild at Watkins). It's not just a hue tint — the texture is smeared/stretched, and
  a proper de-blue needs a per-draw TINT uniform in the shader (the current `draw()` only exposes
  bright/ambfill, no colour tint). Deferred as a small shader change (or a GPL crowd-MIP reference).
- **Pre-existing TEST failure (NOT from E56/E57):** `test_corner_tyre.jl:44` fails — the MTK Magic-
  Formula `Tyre` Fy diverges from the pure `tyre_fy` law by ~194 N. `TyreSweep` uses `Tyre()` (the legacy
  MF path), which none of my changes touched (E56.5 only added `μscale` to `BrushTyre`); likely stale
  since the combined-slip Tyre reformulation (5721f32). The DEFAULT brush path is clean: `test_brush_slip`
  ✅ and `test_vehicle_driven` ✅. Tracked as a legacy-MF test-vs-law mismatch (brush is the shipping tyre).

### Physics-AI robustness + E46 crowd (2026-06-29, autonomous, post-QA)
- **E6 ✅ 3-D yaw divergence guard:** Spa physics-AI max_yaw 281→9.9, Nürburgring 1239→9.99 — the
  integrator no longer blows up on big terrain (player unaffected; clamp only >10 rad/s).
- **G2/E12 ✅ physics-AI anti-spin controller:** above ~1 rad/s yaw the controller catches the slide
  (ease line-chase gain, ramp counter-yaw, lift throttle). Spa 3/5 cars now lap at race pace (was 1),
  spins 1514→1014; Zandvoort no regression. `JM_AI_AMAX` knob added — 8.0 validated optimum (6.0 worse).
- **Nürburgring physics-AI ⏳ DEFERRED:** still not viable — a spin→launch→respawn loop on the extreme
  rFactor jumps (cars fly off-line, max_lat 350 m+). NOT controller/corner-speed-tunable — it's deep
  3-D-model AIRBORNE instability (a bigger E6 model-robustness effort). Opt-in; kinematic AI laps it.
- **E46 ✅ blue crowd de-blued:** per-draw `uTint` shader uniform + warm/de-blue tint on grandstand/
  crowd objects (cross-track, JM_CROWD_T*). The garish electric-blue → varied tones. Residual: the
  crowd MIP's horizontal SMEAR (UV/geometry, needs a re-map — separate from the tint).

### Physics-AI Nürburgring — failed experiments log (2026-06-29, autonomous)
Bounded controller fixes for the Nürburgring physics-AI stuck/launch loop, all TESTED and rejected
(so they're not re-tried). The kinematic AI laps Nürburgring cleanly; physics-AI is opt-in.
- **amax=6 (conservative corner speed):** WORSE on both tracks (Spa 1014→1434 spins, 3/5→1/5;
  Nürburgring catastrophic — a car into 17 km of teleport-loop). Reverted; JM_AI_AMAX=8.0 kept.
- **airborne-aware controller (coast straight / no throttle in free-fall, vacc<2.5):** marginal on
  Nürburgring (spins 1025→992, within noise; still 4/5 stuck + 1 launching) and slightly WORSE on Spa
  (1014→1479, 3/5→2/5). Reverted — the failure isn't airborne-input-driven.
- **CONCLUSION:** the Nürburgring physics-AI failure is deep 3-D-model airborne/contact instability on
  the extreme rFactor jumps (spin→launch→respawn), NOT controller-tunable. Needs core model work
  (landing-contact stability) — a large, separate E6 effort. Physics-AI is viable on the flatter GPL
  tracks (Zandvoort clean, Spa 3/5 lapping via the committed anti-spin); kinematic stays the default.

### PO Zandvoort drive feedback (2026-06-29, autonomous) — fixes
- **E45 ✅ floating horizon buildings = `hotels`** — identified by drop-test (310 m garbage bbox that
  never grounds → hovers above the grandstand). Dropped it; horizon now clean (ring+dunes carry the
  backdrop). New `JM_DROPTEST=<prefix,…>` env diagnostic for fast scenery ID.
- **AI line cuts grass at T1 ✅** — `build_line` now curvature-tapers the apex band (full ±halfwidth on
  fast corners, →halfwidth/2 at hairpins) so the racing line stays on tarmac at tight corners (Tarzan).
- **Audio device race ✅** (earlier) — the engine-audio open now RETRIES the PipeWire startup race
  instead of giving up → sound works (verified: game holds /dev/snd/pcmC0D0p).
- **Sound cut T1→S/F ⏳** — likely first-lap JIT starving the audio thread (recovers at lap end); awaiting
  PO confirm whether it recurs on lap 2+ (if so → a per-section render hitch to chase).
- **No carbonized objects ✅** (E57 grade) — PO confirmed "nice improvement".

### E59 — GPL-under-Wine screen parity, per track (PO-added 2026-07-25)
**PO directive:** match the native Julia Racer screens to the gold-standard screenshots of
**GPL (MS Windows) running under Wine**, now located under the project name on the
`BEA6-BBCE` drive: `/run/media/admin/BEA6-BBCE/julia racer/` — per-track folders:
`zandervoort/` (43 shots incl. the 02:5x cockpit series), `watkins glenn/` (4),
`nurburgring/` (3). **PO clarification 2026-07-25:** BOTH drives are gold sources —
BEA6-BBCE does not replace the older `84AF-CC77` USB (per-track ref folders incl. the
only Monza + Spa golds); its folders stand until/unless BEA6-BBCE grows those tracks.
NB the BEA6-BBCE `zandervoort` 02:5x cockpit series appears to be the same shots
previously cited from 84AF-CC77 — cross-reference, don't double-count. Builds on
E17/E22/E58 (per-track grades) but the acceptance is now a side-by-side native-vs-gold
comparison per screen/view, not a grade eyeball.
- **E59.1** Inventory: map every gold shot to a view (track, cockpit/chase/TV, landmark,
  approx lapdist) + the JM repro recipe (JM_START_S / camera / offscreen snapshot env);
  parity table committed next to this backlog.
- **E59.2** Zandvoort parity (richest gold set, 43 shots): iterate offscreen snapshots vs
  gold until layout/geometry/colour/scenery agree within stated tolerance; deviations
  fixed or PO-waived, each logged in the parity table.
- **E59.3** Watkins Glen + Nürburgring parity (4 + 3 shots) — same method.
- **E59.4 ⚠ PO input:** Monza/Spa golds live on **84AF-CC77** — **PO to re-attach that
  drive** (not attached this sprint; `/run/media/*/84AF-CC77` checked) so the same parity
  method can run on its `monza/` + `spa/` folders; no new GPL captures needed unless the PO
  prefers refreshing them onto BEA6-BBCE.

### E59 sprint log (2026-07-25, autonomous — E59.1 ✅, E59.2 ◑ major fixes landed, E59.3 ◑)
- **Method/tooling:** `JM_SHOTS="s:view:name;…"` multi-shot smoke added to
  `drive_native_mtk.jl` — one launched session teleports + photographs any number of
  lap points/views (21 Zandvoort shots ≈ 1 launch; the old single-shot `JM_DUMP` path
  is unchanged). `JM_SHOTS_DIR`/`JM_SHOT_SETTLE` tune it; `place_at_s!` now shared
  with `JM_START_S`.
- **E59.1 ✅ inventory:** all 50 gold shots classified (43 Zandvoort — ALL cockpit,
  one continuous lap, flat OVERCAST sky; 4 Watkins — 2 cockpit + 2 chase, hazy blue;
  3 Nürburgring — cockpit at the S/F complex, stormy grey). Parity tables + native
  repro recipes + committed side-by-side composites: `SCREEN_PARITY.md`, `parity/`.
- **E59.2 Zandvoort (fixed):** sky regraded to `GRADE_OVERCAST` (all 43 golds are
  overcast — restores the PO's E27 decision that E58 had overridden; `JM_GRADE=ZAND`
  A/Bs the blue); dash de-washed to matte black w/ legible dials (`JM_DASH_B/A`);
  footwell "checkerboard" of untextured tub facets capped to a dark interior
  (render.jl, driver hidden per E36 exposes them); tyres lifted from solid-black
  silhouettes to shaded dark-grey (`JM_TYRE_ALB`; tread texture impossible —
  `lotwlf.3do` is untextured). All verified by offscreen re-capture.
- **E59.2 Zandvoort (open/waived):** mirrored sign text (VREDESTEIN/DUNLOP — dedup
  can keep the away-facing decal; needs track-aware face selection) · crowd-MIP smear
  (E46 residual) · chase-view rear bodywork noise · cyan slab by the pits =
  **authentic GPL asset** (restzxc `hill.mip` avg RGB 61,119,129 teal pond — no fix)
  · waived per prior PO decisions: no driver hands (E36), plexiglass arcs (E21),
  no fence crowds, lap-time HUD (E13).
- **E59.3 ◑:** Watkins — sky/gantry/hay parity good, brown-vs-green terrain + chase
  body fidelity logged open. Nürburgring — storm grade + pit complex match gold;
  minor floating quad at the scoreboard logged.
- **DoD:** JM_SMOKE clean (race + AI), `test_brush_slip` + `test_vehicle_driven`
  green (pre-existing `test_corner_tyre:44` legacy-MF failure unchanged), every
  visible change verified by offscreen snapshot.
- **Sprint close (2026-07-26):** DoD gates run and green — Zandvoort `JM_SMOKE`
  race + 5-AI exit 0 (overcast regrade + AI grid in frame); `test_brush_slip` ✅,
  `test_vehicle_driven` ✅; `test_corner_tyre` fails only at the documented `:44`
  legacy-MF line (pre-existing, non-blocking). Cyan-slab D11 closed as authentic
  GPL asset in the parity table. 84AF-CC77 still not attached
  (`/run/media/*/84AF-CC77` empty) → **E59.4 remains open on the PO**. Sprint
  scope E59.1 ✅ / E59.2 ✅ (D6, D10, D12 tracked open; D8/D9/D13/D14 waived) /
  E59.3 ✅ verdicts logged (Watkins W2/W3, Nürburgring N2 open) / E59.4 blocked
  on the drive. Note: smoke prints an `.ibt export failed` warning (missing
  `data/iracing/` telemetry template) — pre-existing, unrelated to the parity
  diffs; exit still 0.

### E60 — Zandvoort gold-video parity (PO-directed 2026-08-01: "gold-standard-accurate
### Zandvoort the user can race in julia racer")
New gold: `/home/admin/gold standard/julia racer/zandervoort/` — the 43 stills PLUS two
260801 full-lap 1080p60 VIDEOS of GPL-under-Wine (cockpit + nintendo/chase — the first
Zandvoort chase gold). GPL utilities under `.../julia racer/gpl utilities/`. Full method
+ per-deviation verdicts: `SCREEN_PARITY.md` § E60.
- **Fixed (all verified by offscreen re-capture):** V1 sky flattened to the videos'
  featureless pale-grey overcast (`GRADE_ZANDOVER`, cloud 0.18, `JM_CLOUD`); V2 tyres
  to near-black rubber (`JM_TYRE_ALB` 0.17); V3 cockpit-cowl checkerboard harmonized
  to smooth BRG + dark pad (`JM_COWL_HARM`); V4 chase camera to GPL's low/close
  nintendo framing (4.6 m/1.35 m, `JM_CHASE_D/H/LY`); V5 chase driver completed —
  helmet mesh `helmeg.3do` extracted + retextured to Clark-blue `clahelm`, lid/arms
  moved into the driver set (closes the "skeletal car" read of E59 D12 together with
  V2; W3 on Watkins should re-verdict next Watkins pass).
- **D6 root cause found, still open:** Tarzan board wall = `chmp4-1.3do`, ONE mesh,
  4 boards on the `bilbrd01` sheet with per-face winding inconsistent within the
  object → no global two-sided/culled config can read all boards correctly (A/B
  matrix in the drive_native_mtk.jl comment; JM_OBJ_DEDUP/JM_OBJ_CULL/JM_OBJ_FF
  keep the experiments one env var away). Next step: per-face track-aware face
  selection at scenery build (instance transform × centreline normal test).
- **New open (logged in parity table):** V7 floating crowd billboards s≈1100;
  V8 white tower-ish object near Gerlach s≈700; V9 LOTUS hub badge upside-down;
  V10 roadside people billboards over-blue (CROWD_TINT is stand-objects-only).
- **Sprint close (2026-08-01):** 5 capture iterations (`native_fix1..5`), final
  full-lap 46-shot session `native_final`; composites `parity/zandvoort/video_*.jpg`;
  JM_SMOKE clean (exit 0, known benign `.ibt export` warning).

### E64 — cockpit/chase parity (PO priority after E63 objects; ongoing)
Scope: mirror RTT (PO-explicit) · driver-hands refit (Z-CK4) · chase-body LOD (D12) ·
then cross-track replication. Sprint log lives in `SCREEN_PARITY.md` §E64.
- **S1 ✅ (2026-08-08, `7c1729b`) "Mirrors show the road behind" — LIVE mirror RTT**, 8/8,
  goal met: rear view rendered per frame into a 384×192 FBO (X-mirrored, reversed-Z),
  round-masked glass quads derived from the mirror mesh sample per-disc halves; world draw
  factored into a shared `drawworld` closure (chase re-verified). `JM_MIRROR_RTT`/`JM_MIRROR_FOV`.
  DoD: race+5AI smoke exit 0, brush/driven tests green. Z-CK3 → FIXED.
- **S2 ✅ (2026-08-08) "Hands on the wheel" (Z-CK4)** — gold-layout gloved hands + sleeves:
  lotarms was positioner-orphaned (D12 family; raw it ran up-and-forward = the old "giant
  silver arms") → `ARMFIX` wrist-pivot mirror + squash/tuck; fists split by z sign and
  rotated to gold's 10-and-2 (`JM_HAND_GRIP`); JM_HANDS now defaults ON. Residual: chunky
  GPL-era mesh/weave (asset-limited, logged as polish). Details `SCREEN_PARITY.md` §E64 S2.
- **S3 ✅ (2026-08-08) "The cockpit generalizes"** — verification sprint: cockpit capture on
  the other 4 circuits; mirrors show each track's OWN rear world under its own grade (Monza
  per-surface grade holds in the mirror pass), hands identical. 5/5 tracks pass.
  Composite `parity/cockpit_e64_mirror_sweep.jpg`; details `SCREEN_PARITY.md` §E64 S3.
- **S4 ✅ (2026-08-08) "De-spider the chase car" (D12)** — spider-legs ELIMINATED: PRIM
  node 0x11 identified as GPL's LOD/distance switch (we drew every LOD at once; now
  highest-detail only, `JM_LOD_ALL` A/Bs) + displaced runtime-hidden assemblies (groups
  27288/39792, suspension+driver textures at y 0.42…1.16/−1.12…−0.42) excluded from
  CARP/DRIVERP/FSUSPP — the DRIVERP share (pale "arms" weave) was the visible spears.
  Before/after `parity/chase_e64_despider_ab.jpg`; cockpit + Monza re-verified; DoD green.
  D12 residual rescoped: rear-suspension DETAIL (positioner articulation) stays open.
- **S5 ✅ (2026-08-08) "The Watkins forest" (WG3)** — "asset-limited" OVERTURNED: the gold's
  dense roadside autumn forest ships with the track (tree3-18 strips + treefill + intree +
  treesrb) and every class was dropped by pre-graze-fade rules. WATGLEN now joins Monza's
  keep-as-static-graze-faded-panels default (0→30 forest panels + 13 billboards); pit
  straight verified still smear-free. `parity/watkins_wg3_forest_ab.jpg`. New: **WG4** —
  `place_at_s!` puts the car on the GRASS at Watkins s=300/1200 (mis-vantage also caused
  E63's wrong "barren" verdict); reconcile with E54's JM_SWEEP pass. `JM_KEEPTEST` diag added.
- **S6 ✅ (2026-08-08) "The road-only HAT that never was" (WG4)** — root cause of the
  stranded car: the "ROAD-only HAT" comment was a lie (build_hat keeps ALL terrain;
  road_pred only feeds Monza's overpass logic), so align/recentre measured grass as road
  and "100% on terrain" while the line ran the verge; the E54 sweep never caught it
  because its false-grass check is self-referential (centreline vs the ribbon built from
  it). Fixed for WATGLEN with a true road-texture HAT + off-road rescue + multi-pass
  recentre (4.0→1.0 m convergence, alignment refined ~18 m). **Gated to Watkins**: under
  the road oracle Zandvoort's PO-verified line would silently move 2.19 m and Nürburgring
  aligns at 54% (ROAD_TEX under-recognises its textures) — per-track extension is
  follow-up, each needing texture work + capture verification. `JM_ROADHAT=1` experiments.
  `parity/watkins_wg4_placement_ab.jpg`.
- **S7 ◑ (2026-08-08) "The articulated rear end" (D12 residual) — PARTIAL, shipped OFF.**
  Gold nintendo PROVES the articulated rear end is real parity work. S4's reading was
  axis-confused (GPL raw y = LATERAL): groups 27288/39792 are the left/right high-detail
  suspension halves, near-correctly authored but over-reaching (the spear tips). Harness
  landed default-off (`include_groups` extractor, per-side draw + `JM_RS_*` knobs, gold
  frames); 3 capture iterations bounded the residual mis-rotation as NOT a pure roll —
  next pass must dump the actual positioner chain and compose the real transform.
- **S8 ✅ (2026-08-09) "Read the positioner chain" (D12) — rear suspension SHIPPED ON.**
  The chain dump settled it: the file itself places each half AT ITS HUB (d=±0.772 =
  rear track, s=1.0) behind a clamped park-translation; the halves are authored FLAT and
  need a 90° fold about the hub line (S7 pivoted mid-driveshaft — its whole confusion).
  Baked: hub-pivot fold, scale 1.0, `JM_RSUSP` default ON. **D12 → CLOSE-minus** (visible
  delta vs gold modest from the low chase cam; structure present for other angles).
- **S9 ✅ (2026-08-09) "Does anyone else stand on the grass?"** — evidence-first survey
  (16 captures, 4 tracks × 4 positions): Zandvoort/Monza/Spa CLEAR (their ROADHAT
  extension closes as no-defect); **Nürburgring was a real offender** (s=17000 in the
  catch-fencing = the old lap-end-drift note). `ROAD_TEX` extended with the Ring's road
  vocabulary (atog*/a_l_g* edge strips + the Karussell's Concrete) → oracle converges
  (mean 2.41→0.04 m over 4 passes), all positions on tarmac; **NURB joins WATGLEN in the
  ROADHAT default**. `parity/nurburgring_wg4_oracle_ab.jpg`.
- **S10 ✅ (2026-08-09) "Mirrors at speed"** — the tail-dominated mirror residual closed
  with PER-DISC CAMERAS at the cowl positions (per-half FBO viewports, same pixel cost):
  tilt A/Bs proved an eye-centred rear camera can never match gold's backward-outward
  view. Discs now road-dominated, tail at the inner edge = gold's composition
  (`parity/mirrors_e64_percam_ab.jpg`). Hands at speed already match (S2). Knobs:
  `JM_MIRCAM_*`, `JM_MIRROR_{DROP,YAWOUT,FOV}`.
- **S11 ✅ (2026-08-09) "Nothing floats"** — the Ring's lime plates were 21 landmass
  sections whose `trowgl` texture ships only INSIDE nurburg.dat; the tex prefix-fallback
  now reads archive entries too (regression-safe) → textured tree rows
  (`parity/nurburgring_trowgl_ab.jpg`). Zandvoort V8 re-classified: the `cok` Coca-Cola
  board seen from its unpainted back — authentic asset, waive candidate.
- **E64 EPIC CLOSED (S1–S11).** Remaining polish → general backlog: D12 fold fine-tune,
  mirror tyre-vs-tail micro-read, V8/board-back waives, E46 crowd smear, E52 banking.

### E65 — Monza banking & Lesmos scenery (opened 2026-08-09)
- **S1 ✅ 7/8 "The phantom canopy"** — E52 re-scoped by capture-vs-gold: the worst "banking
  slab" reads are Lesmos forest STRIPS whose placement crosses the road; span-test added
  (29 crossers dropped, tree lines kept) → s=2100 matches gold's open sky.
  `parity/monza_e65_canopy_ab.jpg`. E65 CLOSED S1–S5 (see SCREEN_PARITY §E65): real-mesh strips fixed the
  canopy, slabs, Watkins forest density, the E52 underpass read AND (verified in E66 S1)
  the pit dark-sail. Remaining minors: E46 crowd smear, waive candidates (V8/board-backs,
  D11), D12 fold polish, mirror micro-read.


## PO DECISION QUEUE (consolidated 2026-08-09 — nothing blocks the scrum loop)
1. **Waive V8** — the "white tower near Gerlach" is the `cok` Coca-Cola board's unpainted
   BACK (authentic GPL asset; its face shows correctly in the mirrors). Evidence: E64 S11.
2. **Waive the D6-family blank board-backs** (MARTINI/2nd CALTEX at Tarzan) — same
   authentic-asset class as V8/D11 (cyan slab, already waived-as-authentic E59).
3. **Re-drive requests** (felt, not headless-verifiable): the E64 cockpit at speed — live
   per-disc mirrors + hands riding the wheel; Monza/Watkins with the real forest meshes
   (E65); the Ring line now ON the road everywhere (S9), incl. the Karussell approach.
4. **D12 fold fine-tune** — the articulated rear suspension ships at the chain-derived
   hub fold; if any angle reads off while driving, `JM_RS_*` knobs A/B live.

## Sprint-loop state (2026-08-09, after 18 closed sprints)
Deep backlog EXHAUSTED: E64 (cockpit/chase, S1–S11) and E65 (Monza/Watkins scenery,
S1–S5) epics closed; E46 crowd smear closed (filter, not art); WG3/WG4 closed; D12
CLOSE-minus; Ring placement + tree-row textures fixed. Remaining items are the PO queue
above + micro-polish only. Next sprint candidates when the loop continues: polish from
PO re-drive feedback, or the next PO directive.
EOF
### E67 — launch time (opened 2026-08-09)
- **S1 ◑ PARTIAL "The two-minute launch"** — measured (JM_TIMING stamps, verified twice):
  Zandvoort ≈2:45 = 19 s pkg/JIT head + 5 s track parse + 6.5 s extraction + **37 s texture
  decode** + **97 s mtkcompile**. Landed: phase stopwatch; decoded-RGBA texture cache
  (`~/.cache/juliamotor/tex`, **opt-in `JM_TEXCACHE=1`** until its cold/warm A/B runs — the
  box was contended with FF/BoB timing gates at close, and background jobs were being
  cleared). Deferred to a quiet window: the A/B (then flip the default), and the one-time
  `jlracer.so` sysimage build (**run UNLOCKED at nice-19 per the new CONCURRENCY rule** —
  a 40-min gl-lock hold was killed mid-build; lesson recorded in CONCURRENCY.md + memory).

## E68 — PO drive-feedback round (2026-08-09 re-drive of all 5 tracks; "drivable and a
## huge improvement" overall). Items verbatim-derived, prioritised by PO emphasis:
- **E68-CROWD (Zandvoort + Watkins + Ring)**: perpendicular spectator rows FLOAT above or
  sit ON the track — "every perpendicular block I saw" (Zandvoort several places; Watkins
  at the big bend; a block intruding between the Karussell and the back straight). → S1.
- **E68-M1 (Monza)**: translucent haze planes fade whole forests out/in with view angle;
  light/dark sheets appear over objects — suspect: uGraze applied to the REAL tree meshes
  (designed for flat panels). No misplaced crowds on Monza ✓.
- **E68-Z4**: Zandvoort signs mostly ILLEGIBLE vs the Ring's now-perfect signs — translate
  the Ring's success (its signs are .dat scenery meshes; Zandvoort's are D6-dedup decals).
- **E68-HILITE (Monza strong, Ring faint)**: white highlight in the road moving ~5 car
  lengths ahead of the car — suspect the shadow-map box edge fade ("light carpet").
- **E68-Z2**: shrubs near the Zandvoort bridge render WHITE (trowgl-family unresolved
  texture?). **E68-Z3**: the left grandstand before S/F juts into the track. **E68-Z5**:
  residual z-fighting T2R before the stands straight. **E68-W7**: guardrail z-fighting
  throughout Watkins. **E68-W1**: semi-transparent veil left after Watkins S/F.
- **E68-W3**: sleeves don't connect to gloves (S2 junction residual). **E68-W4**: bottom
  half of the dash occluded by a green block in cockpit. **E68-W5**: nintendo view shows
  no axles connecting wheels to chassis (D12 residual, now PO-visible).
- **E68-S1**: Spa Burnenville banner = jaggy polygons. **E68-S2**: Spa oversized buildings
  ON the track (drive through, see inside — E41 now REPRODUCED with a location). **E68-S3**:
  Spa trees yellow that should be green. **E68-S4**: missing tree stands on the right
  ~1 min before the hairpin (La Source) — the track start visible across the gap.


### E68 IMPLEMENTATION SPEC — per-face road-facing selection (three customers)
Customers: D6 blank sign boards (Zandvoort at scale), the white shrubs (E68-Z2), the
Watkins veil (giant Grass sheet backs).  Design, settled by this epic's evidence:
1. At the OBJECTS/track build, for instances of affected families (sign boards, shrub
   sheets, veil-class Grass mega-sheets), compute per FACE the world normal under the
   instance transform and the direction to the nearest ribbon point (JuliaMotor.hat perp).
2. Keep the face of each coplanar/offset pair whose normal · (toward-road) > 0; drop the
   other.  Per-instance mesh variants cached by (mesh, facing-sign) — two variants max.
3. Blanket single-sided culls are DISPROVEN for terrain (S11 regressions) and unavailable
   for signs (D6 needs the right face, not one arbitrary face) — per-face selection is the
   only correct mechanism.  Rails/sections keep their shipped whole-part culls.
4. Verify each customer at its known site: Tarzan boards s=380, bridge shrubs, veil s=60–180.

---

## PO batch 2026-08-26 — gold-VIDEO parity per track, cockpit, and external car

**New oracle type.** Every gold source used so far has been a still. These seven items are
anchored on **video** — two per track, one cockpit and one "nintendo" (chase) — which is a
strictly better oracle for the thing the PO is reporting: an object in the wrong PLACE is only
visible if you can see it from more than one angle and while moving past it. A still can hide a
house standing in the road; a lap cannot.

**Gold set** (`/home/admin/gold standard/julia racer/<track>/`, all 1920x1080):

| track | cockpit | nintendo | notes |
|---|---|---|---|
| zandervoort | `260801_zandervoort_cockpit.mp4` (181 s) | `260801_zandervoort_nintendo.mp4` (144 s) | |
| nurburgring | `260802_nurburgring_cockpit.mp4` (909 s) | `260802_nurburgring_nintendo.mp4` (904 s) | full Nordschleife lap, ~15 min |
| spa | `260802_spa_cockpit.mp4` (388 s) | `260802_spa_nintendo.mp4` (357 s) | |
| watkinsGlenn | `260802_watkinsGlen_cockpit.mp4` (112 s) | `260802_watkinsGlen_nintendo.mp4` (118 s) | plus `260823_gpl_watkin_glen_race_gold.mp4` (617 s), a full race |
| monza | `260802_monza_cockpit.mp4` (173 s) | `260802_monza_nintendo.mp4` (173 s) | |

**Method (applies to E69–E73; follows QA_METHOD_GOLD_PARITY.md).**
1. **Inventory the video as data before rendering anything** (method step 1). Extract frames at a
   fixed cadence, and build a **time → lapdist → landmark** map for each track so every finding
   gets a repro recipe (`s`, view) instead of "somewhere after the hairpin". Commit the map; it
   turns reruns into regression checks.
2. Capture the matching native frames with `JM_SHOTS` at those `s` values in ONE session per track
   (method step 2), both views.
3. **Triage every deviation into the four classes** (method step 4) before fixing: renderer bug /
   authentic-asset surprise / asset-capability gap / prior-owner decision. ⚠️ This project has
   already twice "fixed" toward the wrong oracle — the yellow Spa trees (E68-S3) turned out to be
   authentic autumn sprites, and an autonomous pass once graded the Zandvoort sky toward a
   superseded gold set. **Decode the source asset before calling a colour wrong.**
4. Commit side-by-side composites (gold left, native right) next to a per-track parity table.

**Priority order inside each track item, per the PO:** (a) objects standing ON the racing
surface — these break the game, not just the look; (b) object placement generally; (c) colour.

- **E69 Zandvoort — gold-video parity.** Match the JM track to the two gold videos. On-road
  objects first: the PO reports perpendicular spectator rows floating above or sitting on the
  track in several places. Then placement and colour throughout.
  *Absorbs:* E68-CROWD (Zandvoort part), E68-Z2 (white shrubs), E68-Z3 (left grandstand before
  S/F juts into the track — S13 classified this as track-mesh authored geometry, so re-decide it
  against the video), E68-Z4 (illegible signs), E68-Z5 (z-fighting T2R).

- **E70 Nürburgring — gold-video parity.** Match to the two gold videos. On-road objects first:
  the PO reports a spectator block intruding between the Karussell and the back straight. Then
  placement and colour throughout. ⚠️ 909 s of gold at ~22 km — the landmark map matters more
  here than anywhere else; do not sample this track by eye.
  *Absorbs:* E68-CROWD (Ring part), E68-HILITE (Ring, faint).

- **E71 Spa — gold-video parity.** Match to the two gold videos. On-road objects first: **the
  oversized buildings standing ON the track** — you can drive through them and see inside
  (E68-S2, reproduced with a location). Move them where the gold video puts them. Then placement
  and colour throughout.
  *Absorbs:* E68-S1 (Burnenville banner jaggy), E68-S2, E68-S3 (yellow trees — **check the source
  texture before treating this as a colour bug**; S12 evidence says they may be authentic), E68-S4
  (missing tree stand before La Source).

- **E72 Watkins Glen — gold-video parity.** Match to the two gold videos; the extra 617 s race
  video is a third oracle and covers traffic and more of the lap. On-road objects first: the PO
  reports a crowd block at the big bend. Then placement and colour throughout.
  *Absorbs:* E68-CROWD (Watkins part), E68-W1 (semi-transparent veil after S/F), E68-W7
  (guardrail z-fighting).

- **E73 Monza — gold-video parity.** Match to the two gold videos. No misplaced crowds were seen
  on Monza in the earlier pass, so this item is expected to be dominated by (b) placement and
  (c) colour rather than on-road objects — **which is a prediction, and the video may refute it.**
  *Absorbs:* E68-M1 (translucent haze planes fading forests with view angle), E68-HILITE (Monza,
  strong).

- **E74 Cockpit instrument panel — gold parity.** PO: *"the dials in the cockpit look like a
  Salvador Dali painting."* The instruments are distorted/melted rather than merely misplaced, so
  suspect the dial geometry or its UV/projection, not the dash layout. Correct the whole cockpit
  view against the gold cockpit videos — all five are cockpit-view laps, so this item has five
  independent oracles and every track's video is evidence for it.
  *Absorbs:* E68-W4 (bottom half of the dash occluded by a green block), E68-W3 (sleeves don't
  meet gloves). *Related, already known:* the driverless footwell and the tub-side/gear-lever gap
  recorded in STATUS.md.

- **E75 External Lotus 49 — gold parity.** Correct the external/chase ("nintendo") views of the
  car against the gold nintendo videos. PO's named example: **the JM nintendo view has no axles
  connecting the wheels to the chassis** (E68-W5, now PO-visible). Check the whole external
  silhouette while the car is moving — suspension travel, wheel attachment, body proportions —
  not just the static shape.
  *Absorbs:* E68-W5.

**Definition of Done for E69–E75.** Per-track (or per-view) parity table committed with
side-by-side composites at named landmarks; zero objects intersecting the racing surface; each
remaining deviation either fixed or explicitly classified (authentic asset / asset-capability gap
/ waived prior-owner decision) with the evidence that classified it. No regressions in
`JuliaMotorMTK` tests; `JM_SMOKE` clean.

### E76 (PO 2026-08-26) — restore the deleted objects just after the Nürburgring start/finish

PO: *"restore deleted objects shortly after start-finish line at nurburgring — many of the buildings
and crowds there were simply removed."*

⭐ **Immediate lead, from E70-S2's load trace.** The Ring's scenery line reads:

```
scenery… (skipped 37 flat sprite stubs) 184 groups / 4065 tris
```

**37 objects are being SKIPPED at load**, and "flat sprite stubs" is exactly what a crowd row or a
billboard-style building would be classified as. That is a strong candidate for the PO's missing
objects and it is checkable in one run: report what those 37 are, and where they sit along the lap.
If they cluster just after S/F, this item is solved by the census that names them.

**Second candidate, if the first does not account for it:** the Ring's scenery loads by a path that
bypasses the GPL object pipeline entirely (E70-S2), so its objects never pass through the
instance-placement, drop() and on-road filters the other four tracks use. Anything dropped on this
track is dropped by different code, and none of the E71–E73 censuses can see it.

⚠️ Note for whoever picks this up: **do not use `JM_CROWDDIAG` or `JM_OBJDIAG` here** — they read
`insts`, which is empty on the Ring, and will report "nothing" regardless of the truth (E70-S1 made
exactly that mistake). Use the mesh-based censuses, which E70-S2 relocated so they run on this track.

### E77 (PO 2026-08-27) — the Nürburgring bridge underpasses launch the car

PO, driving the Ring: *"when I went under the bridge at the ring the car went skittering up an
embankment, even though I was on the road"*, and on a second run confirming it: *"when I try to go
under the bridge at the ring, the car levitates and bounces"*.

**Located objectively.** `JM_SWEEP=10` walks the racing line and reports every height
discontinuity in the collision surface. Over the whole 22.76 km lap there are **8 anomalies and
2268 clean stations**, and the 8 fall in exactly two places:

| lapdist | Δh | |
|---|---|---|
| 21540 | **+5.8 m** | first underpass |
| 21550 | −5.1 m | |
| 22250 | **+13.3 m** | second underpass — Döttinger Höhe, before the finish |
| 22260 | +5.0 m | |
| 22270 | +5.2 m | |
| 22280 | +6.9 m | |
| 22290 | +9.9 m | |
| 22300 | **−35.3 m** | |

At the second one the collision surface **steps up ~13 m over 50 m, then falls 35 m**. The car
climbs the step and is thrown off the end — which is what "levitates and bounces" is. Both sit on
the racing LINE, not off it, so no driver error is involved.

**Cause:** the bridge DECK is in the collision HAT, so the car is given the deck's height instead of
the road's while passing beneath it.

⚠️ **`drop_overpass` is NOT the fix and must not simply be switched on here.** It drops any triangle
with another surface below it, and its own docstring says *"do NOT enable on tracks with real
drive-over bridges (Nürburgring)"* — the Ring has bridges you genuinely drive over, and dropping
them would replace this defect with a worse one. The fix has to be narrow: identify the surfaces at
these two lapdists and exclude only those from collision.

⚠️ **A prior analysis of this said the deck was NOT in the collision mesh, and was wrong.** It
searched the parsed `nurburg.3do` for triangles with another surface >2.5 m directly beneath their
centroid and found only 4, all `log_s` over `grass`. `JM_SWEEP` disagrees because it measures *the
surface the physics actually hands the car along the line*, not what the mesh is thought to contain.
Prefer the sweep here; a mesh-structure argument already produced one confident wrong answer.

**Next step:** probe the HAT at s≈21540–21550 and s≈22250–22300, name the textures of the triangles
being returned, and exclude those from the collision HAT (`HAT_EXCLUDE` / `HAT_EXCLUDE_PRED`) while
leaving the drive-over bridges intact. Re-run `JM_SWEEP=10`; the correct result is 0 anomalies.

*Also observed on the same drives, not yet triaged:* odd buildings and part-buildings around the
Ring; a grandstand facing the wrong way near the Watkins start line; lines of people across the
track at Zandvoort (`ppl_l3` @1016, `ppl_s2` @1345, `ppl_m1` @3851, `bushes01–04` @2309–2376, all
already dropped by the MESH filter, so they are reaching the screen via the BILLBOARD path, which
has no on-road filter); transparent openings in the Monza scenery just after the start line.

### E77-F — ✅ DONE (2026-08-28). The Nürburgring bridge underpasses no longer launch the car

**`JM_SWEEP=10`: 8 anomalies → 0, 2276 stations clean.** That was the stated done-criterion.

`JM_BRIDGEPROBE` (new) named what sat over the racing line, by listing every triangle whose XZ
projection contains the centreline point, with its height and texture:

| lapdist | road | over it | |
|---|---|---|---|
| 21540 | 588.22 | **`br_under`** 593.59 | +5.4 m — the bridge UNDERSIDE |
| 22250 | 603.32 | **`villone`** 615.77 | +12.5 m — a building over the line |
| 22300 | 607.42 | `villone` 655.31 | +48 m |

Both added to `HAT_EXCLUDE` — collision only. The bridge is still **rendered**; it is simply no
longer a surface you can land on. `JM_HAT_KEEP_BRIDGE=1` reverts.

**Why it only bit at the bridges:** `hat3d` returns the topmost surface at or below `ref` (= car
y + 2 m). Planted on the road the road wins; the instant the car goes light over a crest — and both
underpasses are on rising ground — `ref` climbs past the underside, the HAT hands back the bridge,
and the car is snapped up onto it and dropped off the far end. That is the "levitates and bounces".

**Two wrong answers on the way, both from probing the wrong mesh.** An early analysis searched the
parsed `nurburg.3do` for stacked triangles, found 4 (`log_s` over `grass`), and concluded the deck
was not in collision. The first version of `JM_BRIDGEPROBE` did the same thing and reported "only
asphalt and groove" at every underpass. Both walked **`TRACKMESH0`**, the raw track mesh — but on
the Ring the scenery is MERGED into the collision mesh (`TRACKMESH = TRACKMESH0.tris ++ SECTRI`) and
`TERRAIN` is built from that. Probing the merged mesh found the two surfaces immediately. ⚠️ On this
track, any collision question must be asked of `TRACKMESH`, never `TRACKMESH0`.

Verified: sweep 0/2276, boundary audit still PASS (world sealed, 0 on-line holes), bridge still drawn.

<details><summary>original item</summary>

E77 above locates and characterises the defect; this is the item to **fix** it. Done when
`JM_SWEEP=10` on the Ring reports **0 anomalies** (it currently reports 8, all at the two
underpasses), and the PO can drive under both bridges without the car climbing or being launched.
Constraint restated because it is the trap: the drive-OVER bridges must still be solid, so
`drop_overpass` cannot be enabled wholesale — exclude only the two decks involved.
</details>

### E78 (PO 2026-08-27) — improve all 5 tracks: gold videos vs the 2026-08-27 JM drives

The PO drove all five tracks on 2026-08-27 and recorded each one. Compare those against the gold
standard videos and fix what the comparison shows, per track.

| track | JM drive (2026-08-27) | gold |
|---|---|---|
| Nürburgring | `/home/admin/Videos/260827_nurburgring.mp4` | `gold standard/julia racer/nurburgring/` (2) |
| Spa | `/home/admin/Videos/260827_spa.mp4` | `gold standard/julia racer/spa/` (2) |
| Monza | `/home/admin/Videos/260827_monza.mp4` | `gold standard/julia racer/monza/` (2) |
| Watkins Glen | `/home/admin/Videos/260827_watkinsGlen.mp4` | `gold standard/julia racer/watkinsGlenn/` (3) |
| Zandvoort | `/home/admin/Videos/260827_zandervoort.mp4` | `gold standard/julia racer/zandervoort/` (2) |

These are the first JM videos shot after a full day of scenery/collision work, so they are the
current baseline. Named defects already called out by the PO while driving, to be covered here:
odd buildings and part-buildings at the Ring; a grandstand near the Watkins start line **pointed
the wrong way**; transparent openings in the Monza scenery just after the start line ("the worst
graphics glitch"); "many small graphics glitches" on several tracks.

⚠️ Method: match the LANDMARK and the VIEW before comparing anything. Gold has cockpit and nintendo
cuts per track, and this project has already withdrawn one cross-track exposure table (E69-S11 →
E72-S12) for comparing a gold nintendo frame against a native chase frame.

### E79 (PO 2026-08-27) — audit every row-of-people object on all 5 tracks

Two questions per crowd-row instance, on every track:

1. **Does it cross or intrude into the road?** The PO saw lines of people across the track at
   Zandvoort in three places, and at Spa/Watkins as well.
2. **Is it placed non-physically?** e.g. a row perched on a hill crest with the people at each end
   of the line **floating in mid-air**. Zandvoort "has quite a few of these."

⚠️ (1) is NOT already covered by the existing on-road filters, and the reason matters: at Zandvoort
the three rows the PO actually saw — `ppl_l3` @1016, `ppl_s2` @1345, `ppl_m1` @3851 — are all
already reported as **dropped** by the mesh footprint filter, yet they are on screen. So they are
reaching the renderer through the **billboard path**, which has no on-road filter at all. Auditing
the mesh path again will find nothing. Start at the billboard build.

(2) is a new class this project has never measured: a crowd row is grounded from a single point, so
on sloping ground the ends lift off or sink in. The PO also saw this as people "almost submerged in
the track" on the Zandvoort climb. A per-END ground check (both ends + midpoint against the HAT)
would quantify it.

### ✅ IMPLEMENTED 2026-08-28

- **Zandvoort: every crowd row removed**, as a NAME rule in `drop()`. That placement matters — the
  same guard runs on the billboard loop, so it cannot be bypassed the way the mesh footprint filter
  was. (The three rows the PO saw were already reported "dropped" by that filter and were on screen
  regardless, because they arrive as sprites.) `JM_KEEP_CROWDROWS=1` restores them.
- **Other tracks: a crowd row is admitted only if the WHOLE row clears the road** — the billboard
  test was origin-only, the same origin-vs-footprint mistake the mesh path was fixed for in E69-S5.
  Spa: **6 rows removed** (3 `people*`, 3 `p_s*`), 5.8–8.7 m from the centreline.

⚠️ **The first version of that test removed 700 rows at Spa** and would have shipped had the count
not looked absurd. It subtracted half the row's width straight off the lateral distance — but a
crowd row runs ALONG the track, so its width lies parallel to the road and contributes almost
nothing across it. A 40 m row sitting 25 m away scored as 5 m from the centreline. Projecting the
extent onto the road NORMAL (`(w/2)·|sin(row yaw − road yaw)|`, ~0 when parallel) gives 6.
**Stripping Spa's crowds would have recreated the PO's own "objects were simply removed" complaint
from the Ring** — one reported defect traded for another.

**PO 2026-08-28 — the disposition is REMOVAL, not repair.** *"remove line-of-people objects if
there's any chance they could be in the road or partially hanging in air; these objects don't add
much and detract a lot if misplaced. remove all line of people objects from zandervoort."*

So the rule for this item is now:
- **Zandvoort: remove ALL line-of-people objects**, unconditionally. No audit needed there — just
  take them out.
- **Other four tracks: remove any that COULD be in the road or partially in the air.** The test is
  deliberately generous, not marginal: if an instance might intrude or float, it goes. The PO's
  reasoning is a cost/benefit judgement about the asset class, and it is theirs to make — a correct
  crowd row adds little, a misplaced one is very visible.

This replaces "measure, then decide per instance" with "measure only to find them, then delete".
It also removes the need to fix the billboard-path on-road filter *for this asset class* — though
that filter gap is still real for everything else that goes through it, so do not close it on the
strength of this item.

### E80 (PO 2026-08-27) — frame rate: 10 fps at Spa is not acceptable

PO: *"frame rate was low (10 frames/sec or so) in cockpit view, better in nintendo view"*, and
separately *"there's no excuse for 10 frames/sec on a PC with a 6 GB nvidia graphics card"*.

The cockpit/chase asymmetry is the clue: the same scene renders acceptably from the chase camera
and badly from the cockpit, with the gauge panel and hands already OFF (`JM_GAUGE=0 JM_HANDS=0`).
So the cost is not the cockpit art itself. Profile before changing anything — per-phase timing
already exists (`JM_TIMING`), and the scenery/billboard draw counts are instrumented.

Done when Spa holds a stable frame rate in cockpit view on the PO's hardware, with the figure
measured and recorded rather than judged by feel.

### 2026-08-28 — the asymmetry is SOLVED; the base frame rate is not

`JM_FPSDIAG` reports frame time per view. At Spa, same spot, same settle:

| | cockpit | chase |
|---|---|---|
| mirrors every frame (was) | **6.8 fps** (146 ms) | 11–20 fps |
| mirrors off (`JM_MIRROR_RTT=0`) | 15.5 fps (65 ms) | 15 fps (**unchanged**) |
| **mirrors every 3rd frame (now)** | **11.7 fps** (85 ms) | — |

**The cockpit/chase asymmetry was entirely the mirror render-to-texture pass**, which re-rendered
the scene into a 384x192 texture *every frame* and cost **~80 ms**. Chase never runs it, which is
why it was faster. Two round mirrors that small do not need a fresh image 60 times a second, so
they now refresh every 3rd frame: **6.8 → 11.7 fps, +72%, mirrors still live.**
`JM_MIRROR_EVERY=1` restores per-frame, `JM_MIRROR_RTT=0` the old static discs.

✅ **DOES NOT REPRODUCE (2026-08-30) — the sim runs at the display refresh.** `JM_FRAMEPROF` +
`JM_FPSDIAG`, three configurations:

| config | fps | world | hud | frame |
|---|---|---|---|---|
| Monza, chase | 58.6–60.2 | 5.8–10.7 ms | 0.06–3.4 ms | 16.6–17.1 ms |
| Watkins, chase | 58.8 | 7.56 ms | 3.23 ms | 17.0 ms |
| Watkins, **cockpit** | 57.8 | 2.11 ms | 3.07 ms | 17.3 ms |

**All three sit at ~58–60 fps**, and `world + hud` accounts for only 5–11 ms of a ~17 ms frame — the
remainder is the vsync wait, i.e. there is real headroom rather than a hidden cost. The claim below
(*"BOTH views sit at ~15 fps / 65 ms … 15 fps is not acceptable either"*) does not reproduce on either
track or in either view.

⚠️ **Why it changed is NOT established.** Candidates: the mirror-every-3rd-frame change recorded just
above; other work since; or — worth taking seriously — **the original measurement having been taken on
a contended machine.** This session has already proved that two MiG Alley gates failed purely because
JuliaRacer smoke tests were running on the same four cores, so a 4× frame-time inflation from
contention is not hypothetical here. Whatever the cause, the blocker as written is stale.

✅ **SCOPE GAP CLOSED (same day): a FULL AI FIELD does not change it.** The measurements above had
`JM_AI` at its default of **0** — no opponents at all — which I flagged as uncovered. Re-run at Watkins
with `JM_AI=5` (Ferrari, Brabham, BRM, Eagle, Cooper), sampling the whole run rather than the end:

    10 fps samples:  min 57.7   median 59.9   max 60.4     samples below 30 fps: 0
    world ms:        min 4.09   median 5.50   max 9.84

**Not one sample dropped below 57.7 fps**, and `world` — which now includes simulating and drawing five
extra cars — peaks at 9.84 ms in a ~17 ms frame. So the AI field is not a meaningful cost, and E80's
recorded blocker does not reproduce with opponents either.

⚠️ **Still not covered:** a *collision-heavy* or tightly-packed moment, and the PO's own machine under
whatever else it is running. If the PO sees a low frame rate while racing, that remains a different
measurement and this does not refute it.

⚠️ ~~**NOT done.** With the mirror pass removed entirely, BOTH views sit at ~15 fps / 65 ms — so~~
there is a second, view-independent cost of the same order, and 15 fps is not acceptable either.
That is now the whole of E80. The mirror finding does not touch it, and the next sprint should
profile the base frame rather than assume the remaining cost is in the same place.

◐ **BUILT AND VALIDATED (2026-08-29): `JM_FRAMEPROF=<n>`** — buckets around `drawworld` (scenery)
and the HUD, printed beside `[fps]`. Validated at **Watkins, chase view**:

```
[frameprof] 120 frames:  world 3.44 ms   hud 0.07 ms   of 16.77 ms total
[fps] view=chase  60.4 fps  (16.5 ms/frame)
```

**Watkins is not slow — it is vsync-capped**, scenery costing 3.4 ms with ~13 ms of the frame spent
waiting. The instrument reads sensibly, so the E80 problem is track-specific.

⚠️ **The profiler covers TWO phases, not all of them.** At Watkins the unaccounted time is vsync
wait; at Spa it could be the shadow pass, the mirror RTT, the cockpit draw or a stall.
**`total − world − hud` is UNMEASURED, not "scenery-adjacent".**

⭐ **SPA CANNOT BE PROFILED AT ALL: ITS TEXTURE LOAD RUNS PAST 13 MINUTES.** A 900 s run timed out
**still printing "loading textures"** — the frame loop is never reached. `JM_TIMING` (the
launch-phase stopwatch, which is the right tool for THIS even though this entry once wrongly cited
it for frames) gives the split:

```
[t+25.8s] geometry extraction begins
[t+33.8s] texture load begins
loading textures…                  <- still running 800+ s later
```

**Everything except textures costs 34 s; the texture load alone exceeds 13 minutes.** That blocks
every automated measurement of the PO's worst-performing track — E88's Spa census died the same way
at 300 s — and is a defect in its own right.

⭐ **AND SPA'S ARCHIVE IS 150× WATKINS' (2026-08-29, measured on disk):**

| track | archive | directory total | loose `.mip` |
|---|---|---|---|
| **spa67** | **`spa67.dat` 785.7 MB** | **797 MB** | 0 |
| monza | `monza.DAT` 29.8 MB | 45 MB | 86 |
| zandvort | `zandvort.dat` 5.7 MB | 86 MB | 178 |
| watglen | `watglen.dat` 5.1 MB | 33 MB | 100 |

**Spa ships a 786 MB packed archive and nothing loose**, and `gpl_texture_index(ZD)` / `parse_dat`
work over it. A 13-minute "texture load" against a 786 MB archive is a very different problem from a
13-minute load against a 5 MB one, and it reframes the whole item: **this may not be a port defect at
all** — it may be a heavyweight community Spa (high-resolution texture pack) rather than stock GPL.

⛔ **CORRECTION (2026-08-29): "THE TEXTURE LOAD TAKES 13 MINUTES" WAS WRONG.** With the split
timestamps actually printing, a cold Spa load reads:

```
[t+ 34.0s] texture load begins
[t+116.1s]   build_gpl done (GL uploads)      <- 82 s, not 13 minutes
[t+841.3s] physics build (mtkcompile) begins  <- 725 SECONDS UNACCOUNTED
[t+936.2s] physics build done — game loop imminent
```

**`build_gpl` costs 82 s even cold. The missing 725 s is a gap AFTER it.** My earlier runs showed
`loading textures…` as the last line and I read that as "still loading textures" — but that line is
just the last thing PRINTED. Nothing between `build_gpl` and the physics build emitted anything, so
the run had moved on and looked stalled. **Absence of output read as evidence of state**, which is
the same error this file records against several other measurements.

⭐ **THE REAL COST IS IN THE 2364 LINES BETWEEN THEM** — `build_horizon`, then the `BILLBOARDS` /
`STATICTREES` construction with `Render.build_billboard(tn, TEXIDX)` per sprite texture, then the
object and solid passes. That is billboard/object texture work, NOT the track's own textures.
**Instrument that region before drawing any further conclusion** — it has already produced one wrong
one. (Physics `mtkcompile` is a further 95 s and is at least honestly labelled.)

⭐⭐ **THE TEXTURE CACHE IS ALSO DISABLED BY DEFAULT (2026-08-29) — still true, still worth having.**
Split timestamps put the cost precisely:

```
[t+34.2s] texture load begins
[t+35.3s]   texture INDEX built      <- indexing the 786 MB archive: 1.1 s
loading textures…                    <- build_gpl, still running 800+ s later
```

**Indexing is 1.1 s. All 13+ minutes are in `build_gpl` — the per-texture decode and GL upload.**
`tex_rgba` has a complete disk cache for exactly this (`~/.cache/juliamotor/tex/<hash>/<key>.rgba`,
read at `render.jl:887`, written at `:971`) — and `render.jl:878`:

```julia
cd = get(ENV,"JM_TEXCACHE","0") == "0" ? "" :   # default OFF until the deferred cold/warm A/B
```

**`JM_TEXCACHE` defaults to `"0"`, so the cache never activates and no cache directory has ever been
created** (`~/.cache/juliamotor` does not exist; `~/.cache` is writable, so it is the default, not a
permissions failure). Every load re-decodes everything, every time. The comment says the default is
OFF "until the deferred cold/warm A/B" — that A/B is the sprint, and it was deferred long enough for
the cost to become invisible.

**Test:** run Spa twice with `JM_TEXCACHE=1` and compare `[t+…]` at `build_gpl done`. **State the
expectation first: the cold run should be unchanged (13+ min) and the warm run dramatically faster.**
◐ **COLD RUN IN PROGRESS (2026-08-29): the cache DOES populate — `~/.cache/juliamotor` reached
**1.1 GB** for Spa alone while `build_gpl` was still running.** So the mechanism is functional and
genuinely just switched off; nothing is broken about it.

⚠️ **AND THAT SIZE IS A REAL REASON SOMEONE MIGHT HAVE LEFT IT OFF.** Decoded RGBA is uncompressed:
Spa's 786 MB archive expands past 1.1 GB of cache, and there are five tracks. **A default that
silently consumes several GB of `~/.cache` is a decision for the PO, not a performance tweak to
flip.** Report the final per-track sizes alongside the timing before proposing any default change —
"it loads faster" is only half the trade.

⚠️ The cold run must be allowed to COMPLETE or nothing is cached — every Spa run so far was killed
by a timeout mid-`build_gpl`, which is also why no partial cache exists to have hinted at this.

⚠️ **BUT DO NOT CLOSE E80 ON THIS.** It is a strong correlation and no more: the PO's complaint is
FRAME RATE in the cockpit, and archive size explains LOADING. Establishing that a big archive loads
slowly says nothing about why the frame takes 65 ms once loaded. Both may follow from one cause
(more/larger textures resident) — or the load may be an inefficient parse of a big file while the
frame cost lies elsewhere entirely. **The split timestamps around `gpl_texture_index` vs
`build_gpl` are still the next measurement**, and the frame profiler still needs to run on a track
it can actually reach.

⚠️ **DO NOT ASSUME IT SHARES A ROOT CAUSE WITH THE FRAME RATE.** A slow one-off upload and a slow
per-frame draw are different failures, and "Spa has too many textures, hence both" would explain
both without evidence for either. **Profile the texture-load loop itself** — count, total bytes,
time per upload — before connecting them.


⛔ **THE INSTRUMENT THIS ENTRY NAMES DOES NOT MEASURE FRAMES (2026-08-29).** It says *"per-phase
timing already exists (`JM_TIMING`)"*. `JM_TIMING` is a **launch-phase stopwatch** — its own
definition, line 9-11: *"prints cumulative seconds at each load phase"*, `tstamp(lbl)`. It profiles
LOADING. Following this entry gets you load timings and no frame breakdown at all.

What exists for frames is `JM_FPSDIAG`, and it times the **whole frame only** — one number, no
phases. So there is currently **no way to see where the ~65 ms goes**, and the "profile before
changing anything" instruction cannot be carried out with what is here.

**Build the missing thing first — a per-phase FRAME profiler.** Accumulate elapsed time into named
buckets around the draw sections that already exist in the loop (sky; scenery/objects; billboards;
car + suspension + driver + wheels; cockpit/gauges; mirrors; HUD; buffer swap) and print the
breakdown every N frames beside the existing `[fps]` line.

⚠️ **And check the obvious cheap thing before writing it:** there are only six `JM_NO*` toggles in
the whole file (`JM_NOFFB`, `JM_NOIBT`, `JM_NO_PERP`, `JM_NOQUAL`, `JM_NO_RECENTRE`, `JM_NOREPLAY`)
— **none disables scenery, objects or billboards**, so the cost cannot be bisected by switching
things off with what exists either. That is why the profiler is the sprint, not a shortcut around it.

⚠️ **State the expected split before running it.** At 65 ms with the mirrors gone, a plausible prior
is that scenery/object draw dominates; if it turns out to be the buffer swap or a stall, the fix is
in a completely different place and no amount of scenery culling will help.

### E81 (PO 2026-08-27) — floating and misplaced billboards and buildings at the Nürburgring

PO: *"lots of odd buildings and parts of buildings"* at the Ring, and *"check the floating or
misplaced billboards and buildings at nurburgring, of which there are many."*

⚠️ The Ring does NOT go through the instance/object pipeline the other four tracks use — its
scenery is loaded by the Ring-specific `gpl_scenery()` path (E70/E76). `JM_CROWDDIAG` and
`JM_OBJDIAG` read `insts`, which is EMPTY here, and will report "nothing" regardless of the truth —
E70-S1 made exactly that mistake. Use the mesh-based censuses and the billboard-stub path
(E76-S8), which is where the Ring's sprites actually come from.

Overlaps E78 for the Ring video; keep this one for the *placement* defects (floating, part-buildings,
wrong ground height) and E78 for the gold-vs-JM appearance comparison.

### ⚠️ 2026-08-28 — measured: the Ring's SPRITES are NOT floating. Look elsewhere.

`JM_FLOATDIAG` grounds every Ring sprite against the terrain beneath it:

**1777 of 1863 sprites, median gap 0.0 m, 90th percentile 1.1 m.**

So sprite height is not the defect, and "floating billboards" should not be the starting hypothesis.
The PO's report ("lots of odd buildings and parts of buildings", "floating or misplaced") is real,
but it is about something else — candidates, in order: the **mesh** scenery groups rather than the
sprite path; **part**-buildings from LOD/clipping (E70-S4's null-child LOD fix touched exactly this);
and objects that are correctly grounded but wrongly *placed* horizontally.

⚠️ **This measurement needed three corrections before it could be believed, and every uncorrected
version produced a confident, wrong, alarming number:**

1. `ref=Inf` measured to the topmost surface over each sprite — a tree canopy or a roof — instead
   of the ground. Reported "411 of 413 off the ground by up to ±290 m".
2. Sampling in the RENDER frame (`-sp.y`) instead of the physics frame (`+sp.y`). `build_hat` maps
   GPL `(x,y,z)` to `(x, z_up, y)`, so the HAT's second horizontal axis is `+gy` while the renderer
   uses `-gy`. On a track spanning 300 m of elevation a mirrored sample yields a *plausible* height
   for the wrong place: median gap 137 m, and only 256 of 1863 sprites even got a hit.
3. Only after both: 1777 hits and a median of 0.0 m.

The tell each time was the same — a number too large to be a placement error. **A 290 m "float" on a
track 300 m tall is a coordinate bug, not scenery.** Whoever picks E81 up should ground their
instrument against a known-good position before trusting any gap it reports.

### E82 (PO 2026-08-28) — the external (nintendo) car view is still wrong; no axles

PO: *"fix the car external view - e.g. it still has no axles in nintendo view; compare to gold
standard pictures and videos"*.

**E75 has had 16 sprints on this and the PO still sees no axles**, which is the plainest possible
statement that the epic has not delivered its headline defect. E82 is the item to finish it, judged
by the PO's own criterion — the external view compared against the gold pictures and videos — not
by internal geometry measurements.

What E75 established that is worth keeping:
- The suspension parts are present, extracted correctly, and DO draw (S2/S9/S13).
- Size, flat braces, specular and LOD were each eliminated as the cause.
- S15/S16: front and rear assemblies share an outer bound to within 13 mm (1.121 / 1.117 m) and
  both sit 0.25–0.35 m outboard of the hub line, so it is ONE systematic placement error, not a
  content problem. A single 0.30 m inboard shift (`JM_SUSP_INBOARD`) puts both inside the wheel
  face — verified geometrically and in a chase capture, and shipped OFF pending a gold comparison.

⚠️ What E75 never did, and E82 must: **compare against gold**. Every S15/S16 number was fitted to
the car's own hub line and wheel face, not to a gold frame. That is why "the arithmetic works" and
"the PO still sees no axles" can both be true. Start with a matched-landmark, matched-view gold
frame; the constant follows from it.

Gold references: `gold standard/julia racer/<track>/*_nintendo.mp4` (all five tracks) plus the
PO's 2026-08-27 drives in `/home/admin/Videos/` for the current state.

### E83 (PO 2026-08-28) — neon tree/shrub colouration

PO: *"fix neon tree/shrub coloration - compare today's videos to gold standard videos"*. First
reported on 2026-08-27 while driving the Ring — *"trees and shrubs have neon colors"* — and still
present.

Compare `/home/admin/Videos/260827_*.mp4` (all five tracks, 2026-08-27) against
`gold standard/julia racer/<track>/`. Judge it on the vegetation's colour against gold at a matched
landmark and view, and fix what that shows.

⚠️ Two live leads and one dead end, so this does not start from scratch:

- **The billboard/sprite path is the suspect, not the mesh trees.** E70-S7 and E76 saw the same
  cast on the Ring's billboard vegetation, and measured that the scene-wide median is *identical*
  with billboards on and off (137 vs 138) — so whatever is wrong is in how the SPRITES are
  coloured, not a global grade.
- **Alpha handling is a known contributor.** Colour-keyed sprites pull the key colour into their
  edges unless filtered as 1-bit masked; an alpha-bleed pass was added for exactly this class of
  fringing. Check whether the vegetation sheets are taking the smooth-alpha path (LINEAR) when they
  should be masked (NEAREST), which tints edges toward the key.
- ⚠️ **DEAD END — do not "fix" this by darkening.** The obvious move is a per-track exposure or
  grade correction, and it has been tried and withdrawn TWICE: E69-S11 ("the Ring is 35% too
  bright") was withdrawn by E72-S12 for comparing a gold *nintendo* frame against a native *chase*
  frame (+35% became +2% on matched views), and E72-S12's own replacement table was withdrawn by
  E72-S13 because the asphalt mask it used is not exposure-invariant. **There is no trusted
  per-track exposure figure**, and `GRADE_*` must not be changed on that evidence.


---

### E84 (PO 2026-08-28) — EPIC: a 5-car, 3-lap race at Watkins Glen, Zandvoort and Monza

PO: *"make 5 car race work at watkins glenn, zandervoort and monza. Keep track of lap times for 3
lap race. Use slot car opponent physics as in GPL. Look at sgl THU gpl .rpy files of races to
calibrate opponent cars"*.

**Scope.** A 5-car field (the player plus four opponents — say so if that reading is wrong) racing
three timed laps on the three named tracks. The Ring and Spa are explicitly NOT in scope for this
epic; they are the two tracks with open geometry/frame-rate items (E80, E81), and adding racing on
top of those would confound both.

**Opponent physics: slot-car, as GPL does it.** GPL's AI does not drive the full vehicle model —
opponents follow a fixed racing line at a commanded speed, with the line and speed profile doing
the work that grip and load transfer do for the player. That is the model to implement here, and it
is a deliberate simplification, not a shortcut to be upgraded later: it is cheap enough that four
opponents cost far less than four instances of `CAR3D`, which matters directly given E80 (the base
renderer still costs ~65 ms/frame in BOTH views, so there is no headroom to spend).

⚠️ **This does NOT weaken the PO's physics directive.** *"The car physics should be determined
entirely by the iracing ibt data, there should be no modifiable parameters"* governs the PLAYER's
car. Opponents are not the player's car and are not simulated from the ibt data; keep the two
completely separate so no opponent tuning knob can ever reach `CAR3D`, `vehicle_3d.jl` or
`powertrain.jl`. If implementing this needs a knob, it lives in the opponent module and nowhere
else.

**Calibration oracle — the GPL replays.** `/home/admin/sgl/THU/INSTALL/replay/` holds 348 `.rpy`
files, and all three target tracks carry a COMPLETE `67F1_Rob_Fle_<track>_<car>_<laptime>.rpy` set
across all seven 1967 chassis. The lap time is in the filename, so the reference field spread is
readable without decoding anything:

| | Lotus | Eagle | Ferrari | Brabham | Cooper | Honda | BRM | spread |
|---|---|---|---|---|---|---|---|---|
| **watglen** | 1:03.268 | 1:03.618 | 1:03.796 | 1:04.174 | 1:04.640 | 1:04.660 | 1:04.815 | **1.55 s** |
| **zandvort** | 1:22.657 | 1:22.924 | 1:23.169 | 1:23.282 | 1:23.929 | 1:24.384 | 1:24.542 | **1.89 s** |
| **monza** | 1:26.490 | 1:26.545 | 1:27.486 | 1:27.923 | 1:28.905 | 1:27.920 | 1:28.654 | **2.42 s** |

That spread — not quite two seconds over a lap, tightening at the shorter track — is what a credible
field looks like, and it is the acceptance target. Opponents that finish nose-to-tail, or strung out
by ten seconds, are both wrong.

🔒 **The `.rpy` files are IRREPLACEABLE and READ-ONLY.** Copy before parsing; never write into
`/home/admin/sgl/THU/INSTALL/replay/`. There are also per-track `fs_*` and `LOR_*` replays (hotlaps
and race stints) which carry richer line data than the filename does.

### 2026-08-28 — S1 MEASURED: this is NOT a greenfield, and the sprint plan below was wrong

⚠️ **I wrote the sprint split below assuming nothing existed. That assumption is false** and the
plan is corrected here rather than followed. Already present and working: `JM_MODE=race`,
`RACE_LAPS`, per-car lap counting (`car.lap += 1` on the start/finish wrap, `ai.jl:194/246`),
player lap counting (`cs.laps`), race-finish detection with a standings dump
(`drive_native_mtk.jl:4483`), fuel sized to race distance, a lap-time display, and a full `RaceAI`
multi-rail field with collision resolution and tailgating. **Building "lap timing" now would build
a second timing system beside the working one.**

**A 5-car race already grids and paces at all three target tracks.** Measured, one run each:

```
═══ GRID ═══   P1 Ferrari  P2 Brabham  P3 BRM  P4 Eagle  P5 You
→ AI pace spread (power/weight, gridded fastest-first): Ferrari 99%, Brabham 96%, BRM 97%, Eagle 100%
```

| track | CLINE | rail natural | target (`REF_LAP`) | **scale** | gold `.rpy` fastest |
|---|---|---|---|---|---|
| watglen | 3750 m | 96.4 s | 66.9 s | **1.44×** | 63.268 (Lotus) |
| zandvoort | 4181 m | 117.1 s | 86.8 s | **1.35×** | 82.657 (Lotus) |
| monza | 5760 m | 140.2 s | 90.2 s | **1.55×** | 86.490 (Lotus) |

**Two findings, and they change the order of work:**

1. **The field's pace rests on a large, track-varying fudge.** The rail follower's own natural lap
   is **35–55 % slower** than the pace it is commanded to run, and the gap differs per track. So
   `AI_SCALE` is absorbing a *modelling shortfall*, not expressing a driver-skill percentage.
2. **Re-anchoring to the `.rpy` times makes that WORSE, not better.** The gold replays are 4–6 %
   *quicker* than the current GPLrank `REF_LAP`, so adopting them (which is what the PO asked for)
   pushes the multiplier further from what the rail geometry naturally produces. ⭐ **Therefore:
   fix the rail's natural pace FIRST, then anchor it to the `.rpy` times.** Anchoring first buries
   a bigger modelling error under a bigger multiplier, and the per-chassis spread the PO wants
   (Lotus 1:22.657 → BRM 1:24.542, a ~2 % band) would then be a detail riding on a 55 % correction.

⚠️ **The per-chassis spread is currently derived from POWER/WEIGHT** (99/96/97/100 %), not from the
replays. Replacing that with the measured `.rpy` per-car table is the PO's stated intent and is
where the field's character comes from.

**Corrected sprint split:**

1. ~~Lap timing + race state~~ — **ALREADY EXISTS.** ✅ **S2 DONE: the speed caps are REFUTED as the
   cause.** See below.

### 2026-08-28 — S2: the pace shortfall is NOT the speed caps. Prediction refuted.

`JM_PACEDIAG` (new) sweeps `RaceAI.natural_laptime` — deterministic, no render loop, exits during
load. `natural_laptime` now forwards `amax`/`vmax` (defaults unchanged, so no caller moves).

**Stated before the run:** *"if `vmax` dominates, Monza improves ≥ 10 % and Zandvoort ≤ 5 %."*

| change | **monza** (target 90.2 s) | **zandvoort** (target 86.8 s) |
|---|---|---|
| baseline `amax=11, vmax=74` | 140.2 s | 117.1 s |
| `vmax` 74 → 100 (**+35 %**) | 135.6 s (**3.3 %**) | 115.9 s (**1.1 %**) |
| `amax` 11 → 18 (**+64 %**) | 126.2 s (10.0 %) | 99.2 s (15.3 %) |
| both (90 / 14) | 127.9 s (8.8 %) | 106.9 s (8.7 %) |

❌ **The Monza half of my prediction was WRONG — 2.7 %, not ≥ 10 %. `vmax` is not the limiter.**
A 35 % raise in top speed buys 1–3 %, which means **the car almost never reaches `vmax`**. Good
that this was a stated number: "raise vmax" would have shipped a 3 % gain as progress.

`amax` matters more, and more at the twisty track (15.3 % vs 10.0 %) exactly as cornering should —
but it is **not sufficient either**. At an unrealistic **1.8 g**, Monza is still **126 s against a
90 s target (40 % slow)** while Zandvoort reaches 99 s (14 % slow).

⭐ **The residual is TRACK-DEPENDENT, and that is the lead.** At identical `amax`, Zandvoort lands
within 14 % while Monza stays 40 % off — and **Monza is the FAST circuit**, mostly full throttle,
where the AI should be `vmax`-limited and plainly is not. So the car is being held below 74 m/s by
**curvature** almost everywhere on a track that has very little. Suspect an inflated κ from a noisy
centreline: Monza's load needs **four** re-centring passes (`max shift 4.0 m, mean 3.13 m` on
pass 1), and `vtarget = √(amax/κ)` punishes every spurious wiggle.

### 2026-08-28 — S3: the line is CLEAN. A handful of impossible KINKS cost the lap.

Both S3 hypotheses refuted, and both my numeric predictions with them. Predicted median `vtarget`
40–50 m/s and < 10 % of the lap at `vmax`; **measured 74.0 m/s (= `vmax`) and 84.2 %.**

| | measured | I predicted |
|---|---|---|
| median κ | **0.00046 /m → radius 2171 m** | "noisy line" |
| median `vtarget` (local κ) | **74.0 = `vmax`** | 40–50 m/s |
| lap at `vmax` (local) | **84.2 %** | < 10 % |
| median cost of the 150 m horizon rule | **0.0 m/s** | "the horizon rule is too blunt" |

**The centreline is clean and the horizon rule is free at the median.** The damage is entirely in
the TAIL:

| radius | samples | % of lap | `vtarget` there |
|---|---|---|---|
| < 80 m | 33/600 | 5.5 % | 29.7 m/s |
| < 40 m | 8/600 | 1.3 % | 21.0 m/s |
| < 20 m | 4/600 | 0.7 % | 14.8 m/s |
| **< 10 m** | 2/600 | 0.3 % | **12.0 = `vmin`** |

`max κ = 0.32 /m` is a **3.1 m radius**. No circuit has that — Monaco's Loews, the tightest corner
in F1, is ~12 m. And the spikes are **CLUSTERED, not scattered**:

```
s=2314 r=3.1 m   s=2477 r=11.8 m   s=2246 r=29.5 m   s=2141 r=35.8 m   s=2208 r=39.6 m
s= 950 r=6.7 m   s= 960 r=17.1 m                                       s=4944 r=38.8 m
```

**Five of the eight worst lie in one 336 m stretch (s≈2141–2477); two more at s≈950.** Two bad
regions in 5760 m — a localised construction defect, not general noise.

**Why that costs 55 %:** each spike pins `vtarget` to `vmin`, and recovering to 74 m/s at the
9 m/s² acceleration cap takes ~7 s and ~300 m — with the 150 m forward-max poisoning the approach
too (that is why `p10` falls 37.5 → 18.0 while the median does not move). Five clusters × ~300 m ≈
1.5 km of a 5.76 km lap compromised. Right order to explain the shortfall.

⚠️ **DO NOT FIX THIS BY SMOOTHING THE WHOLE LINE.** That would round off Lesmo, Ascari and the
Parabolica — trading a measured defect for an unmeasured one. The repair must be surgical.

**S4 hypothesis, to be tested not assumed:** the RE-CENTRING pass creates the kinks. Monza needs
**four** passes (`pass 1: max shift 4.0 m, mean 3.13 m`; `pass 4: max shift 4.0 m, mean 0.42 m,
at-start 2.43 m`) and it moves points LATERALLY — adjacent points shifted in opposite directions
produce exactly this signature: a near-zero radius between two otherwise sane points.
**Test:** re-measure the κ tail with re-centring disabled. If the spikes vanish, the re-centring
pass is the defect; if they survive, they are in the source geometry and the fix is a kink filter
in `build_line`. **State the expected spike count before running.**

### 2026-08-28 — S4: CONFIRMED — the re-centring pass creates the kinks

A/B on Monza, `JM_NORECENTRE=1` (new) vs the default 4 passes:

| | with re-centring | without |
|---|---|---|
| max κ | **0.32156 → r = 3.1 m** | **0.03403 → r = 29.4 m** |
| radius < 20 m | 4 / 600 | **0** |
| radius < 10 m | 2 / 600 | **0** |
| median κ | 0.00046 | 0.00015 |

**Every physically impossible corner disappears when re-centring is skipped.** The S3 hypothesis
was right.

⚠️ **My S4 pre-run prediction was WRONG and worth recording.** Reading `recentre_on_road` I argued
the spikes would SURVIVE, because the pass box-smooths its shift array (`W=3`) and a smoothed shift
"cannot" produce an isolated kink. That reasoning is incomplete: **the smooth averages the shift
MAGNITUDES, while `nrm(i)` computes each point's DIRECTION independently from its own neighbours.**
Smoothed magnitudes applied along divergent normals still kink — and the `tl < 1e-6` guard leaves a
point unmoved while its neighbours move, which is exactly a one-point spike.

🔒 **The fix is NOT to disable re-centring.** It exists for a measured reason (E64-S6: Watkins'
raw `.trk` line runs ~10 m onto the grass and must be walked back), and without it the line is
mis-placed even though it is smooth. **Fix the kink, keep the pass:** clamp per-point shift
*relative to its neighbours* (limit the second difference, not just the magnitude), and skip or
interpolate points whose normal is degenerate. Then re-measure BOTH the κ tail and the at-start
offset — a smoother line that sits off the road is not an improvement.

**Superseded:** measure the κ / `vtarget` profile, don't tune it. Report the distribution of
`vtarget` around each lap and the fraction of the lap below, say, 50 m/s. If Monza's median
`vtarget` is ~45 m/s where the circuit should be ~75, the CENTRELINE is the defect and no amount of
`amax` will fix it. **State the expected median before running.**
2. **Racing line extraction from the `.rpy` files.** Decode enough of the format to recover a
   position-vs-time line for one car at one track; validate by checking the lap time it implies
   matches the filename to within a few hundredths. **State the expected number BEFORE running it.**

   ◐ **FORMAT PARTLY DECODED (2026-08-28).** Corpus: **166** replays in
   `~/sgl/THU/INSTALL/replay/`, 77 with a lap time in the filename.

   Chunk layout — 4-byte tags stored byte-reversed, `tag + u32 + u32(size)`:
   `RPLY` (container) → `RPHD` (header: track name, driver, car count) → `CARS` → `DRLS`/`DRNT`
   (driver entries) → `LPTB` → **`LPRO`** (lap boundaries) → `RPTP` (the bulk tape) → `NVAP`.

   `LPRO` holds a monotonically increasing `u32` series in **MILLISECONDS, cumulative** — lap times
   are the successive DIFFERENCES, not stored values. (The first guess, that a lap time is stored
   directly as `86545` ms or `86.545f`, gave **zero** hits in the whole file. Recorded because the
   wrong guess is what identified the encoding.)

   **Validation, run over the whole corpus:** best lap == filename to <0.05 s in **57 of 77** files.
   ⚠️ The 20 misses are ALL 0.1–0.6 s **too SLOW, never too fast** — a systematic signature, not
   noise: the series is not a flat `u32` array (one interleaved record decodes as ASCII `PNPb`), so
   a naive walk drops the record carrying the true best lap and returns the second best. Finish by
   identifying the interleaved record type; the 57 exact matches say the ms/cumulative reading is
   right.

   ⚠️ **CORRECTION (2026-08-29).** An earlier note here claimed "these are HOTLAPS: `RPHD` car count
   is 1" on the strength of ONE file and a field at `DHPR+0x18`. Both halves were wrong:

   * **`DHPR+0x18` is not the car count.** It reads `1` for replays that contain 14, 17 and 18
     driver chunks. It looked corroborated (105/166 files) only because most of the corpus genuinely
     has one driver, so a field that is always 1 "agrees" by accident. **A candidate field that
     matches the COMMON case is not thereby identified — check it against the RARE case.**
   * **The corpus is NOT all hotlaps.** Counting `DRNT` (driver-entry) chunks finds **10 multi-car
     replays**, the largest carrying a full field:

     | drivers | file |
     |---|---|
     | 18 | `67F1_Rob_Fle_zandvort_Ferrari_1m 23.169s.rpy` |
     | 17 | `67F1_Rob_Fle_mosport_Ferrari_1m 19.559s.rpy` |
     | 14 | `67F1_Rob_Fle_kyalami_BRM_1m 19.533s.rpy` |
     | 12 | **`Demo lap with 11 cars Look and learn.rpy`** |
     | 11 | `67F1_Rob_Fle_monza_Brabham_1m 27.923s.rpy` |
     |  9 | `67F1_Rob_Fle_zandvort_BRM_1m 24.542s.rpy` |

     The demo file names its own car count and the chunk count agrees (12 = 11 cars + player) —
     independent corroboration that `DRNT` counting is sound.

   ⭐ **E89 CALIBRATION SOURCE IDENTIFIED — and the two multi-car sets are NOT the same thing.**
   Reading the `DRNT` payloads gives the driver names, which settles what each file records:

   * **`Demo lap with 11 cars Look and learn.rpy` (WATKINS) is GPL's own AI.** Its 12 entries are
     `Demo Driver` plus the historical 1967 grid — Clark, Brabham, Parkes, Irwin, McLaren, Surtees,
     Ickx, Hill, Ginther, Bandini, Bonnier. That is GPL's built-in AI roster, so this is a recording
     of **the AI itself**, at one of the PO's three tracks. **This is the reference for E89.**
   * **The 11-driver Monza file is a HUMAN online league race** — `UKGPL8`, `60fps`, and real
     entrants (Dean Logan, Fulvio Policardi, Andreas Gebhardt, Bob Whitwell, Robert Fleurke …).
     Useful as a picture of good racecraft, but it is **not** GPL AI, and calibrating "make the AI
     behave like GPL" against human drivers would be answering a different question. Same for the
     other `67F1_Rob_Fle_*` multi-car files.

   The PO's ask is *"Make AI cars behave as they do in GPL"* — so the demo replay is the oracle and
   the league races are, at most, a sanity check.

   Extract per-car position-vs-time from `RPTP` for the demo file and measure what the AI actually
   does: gap variance lap to lap, closing rates, whether cars hold station. **State the expected
   numbers before running** — the PO's report is "dart, lunge ahead, fall back", so the quantity
   that should separate ours from GPL's is gap variance per lap, not average pace.

   ◐ **`RPTP` probe (2026-08-29), demo file.** Payload `0xa54..0x12e988` = **1,236,788 bytes, 99.8%
   of the file** — the tape is essentially the whole replay. Its head carries a small `u16` table
   (`9,24,9,12,12,12,12,12,12,12,12,12,14,8`) that looks like a per-entry size map, twelve of them
   matching the twelve `DRNT` entries. Body is regular fixed-width records whose trailing 8 bytes
   read as two plausible `float32`s (~33.4 and ~8.5, drifting smoothly record to record).

   ⚠️ **`LPRO` is only 12 bytes = 3 entries, so this replay is ONE LAP** (consistent with the name).
   That is enough to measure car-to-car behaviour WITHIN a lap — closing rates, station-keeping,
   lateral darting — but it CANNOT give lap-to-lap gap variance. If lap-to-lap is wanted, a
   different multi-car file is needed, and the only other AI-roster candidates must be identified by
   `DRNT` names first (the `67F1_Rob_Fle_*` multi-car files are human league races, see above).

   ⛔ **THE TAPE IS NOT A FIXED-STRIDE ARRAY (2026-08-29, measured).** Scanned every record size
   8..72 at every field offset 0..24 for `float32`, `int32` and `int16` channels that behave like a
   position (small median step, wide overall spread, few discontinuities). **Zero candidates.**
   That also retires the earlier note here about "two `float32`s (~33.4 and ~8.5)" — that was
   pattern-matching on THREE consecutive records, and it does not survive a scan of the whole tape.
   `RPTP` is therefore delta-coded or bit-packed. Cracking it is its own project, not a step in E89.

   ⭐ **DO NOT BLOCK E89 ON THIS.** The stated goal is *"make AI cars behave as they do in GPL"*,
   and there is a leading hypothesis already in this backlog that needs no replay at all: **E84
   records that the AI pace shortfall comes from CENTRELINE KINKS created by re-centring**, not from
   speed caps. A kinked centreline gives an oscillating `vtarget` — which is exactly "dart around,
   lunge ahead, then fall back". Same defect, two symptoms.

   **Cheapest discriminating test, and it uses instruments that already exist:** log per-AI-car
   `vtarget` and lateral offset around a Monza lap (`JM_PACEDIAG`), and look for oscillation
   correlated with centreline curvature spikes. If the kinks drive it, E84-S5 (clamp the per-point
   shift relative to its NEIGHBOURS — limit the second difference) fixes both items. **State the
   expected oscillation amplitude before running.**

   ⭐ **MEASURED (2026-08-29, `JM_PACEDIAG` + new step-to-step block, `JM_AI=4`, 600 samples/lap):**

   | | median \|dv\| | p90 | max | steps >10 m/s |
   |---|---|---|---|---|
   | Monza, local κ | 0.0 | 18.51 | 62.0 | **70/599** |
   | Monza, horizon (**what the AI actually uses**) | 0.0 | 1.21 | 53.84 | **12/599** |
   | Watkins, local κ | 0.0 | 16.08 | 57.16 | 78/599 |
   | Watkins, horizon | 0.0 | 0.26 | 49.14 | 10/599 |

   ⚠️ **THE STATED PREDICTION WAS WRONG IN FORM.** It said "expect median `|dv|` > 2 m/s if the kinks
   drive the darting". The median is **0.0 on every track and both channels** — because most of a lap
   sits pinned at the `vmax` clamp, so the median measures THE CLAMP, not the line. A median was the
   wrong statistic for a signal that lives entirely in the tail. Recorded because the number came out
   "clean" and could easily have been read as refuting the hypothesis.

   **What the tail says.** The horizon channel is the one `_vtarget` uses, and the look-ahead max
   smooths the raw curvature hard (p90 18.5 → 1.2 m/s at Monza). But it leaves **12 discontinuities
   per lap above 10 m/s, peaking at 53.8 m/s** — a target speed that changes by ~190 km/h between two
   samples 9.6 m apart. A car chasing that target accelerates hard, then brakes hard, a dozen times a
   lap: **"dart around, lunge ahead, then fall back."** Consistent with the E84 centreline-kink
   cause, and it is the KINKS the fix must remove — smoothing the target instead would hide the
   symptom and keep the wrong line.

   **Next (E84-S5):** clamp the per-point centreline shift against its NEIGHBOURS (limit the second
   difference), then re-run this block. **Expected after the fix: horizon steps >10 m/s per lap goes
   from 12 to 0–2 at Monza; the p90 should barely move (it is already 1.2).** Judge it on the count
   of large steps, not the median or the p90.

   ◐ **E84-S5 IMPLEMENTED AND MEASURED — IT DOES NOT MEET ITS OWN TARGET (2026-08-29).** The clamp
   holds each re-centring shift within `JM_SHIFT_SECONDDIFF` (0.05 m) of its neighbours' mean,
   iterated to relax runs of bad points; `JM_SHIFT_CLAMP=1` ENABLES it (it is default OFF).

   | Monza, horizon | p90 | max | steps >10 m/s |
   |---|---|---|---|
   | before (E89 baseline) | 1.205 | 53.84 | **12/599** |
   | with the clamp | 0.993 | 57.11 | **10/599** |

   Full result, both tracks, each against its own control on one binary:

   | | p90 | steps >10 m/s |
   |---|---|---|
   | Monza control | 1.205 | 12 |
   | Monza clamped | 0.993 | 10 |
   | Watkins control | **0.257** | 10 |
   | Watkins clamped | **1.159** | 11 |

   **Target was 0–2 at Monza. Got 10 — and Watkins REGRESSED, its p90 4.5× worse.** ⛔ **The clamp is
   therefore DEFAULT OFF** (`JM_SHIFT_CLAMP=1` to enable). Kept rather than deleted, because the
   measurement is the valuable part: it is evidence AGAINST the lateral-kink cause. Recorded as a
   miss and a regression rather than reported as "12 → 10, an improvement", which is what the Monza
   column alone would have supported.

   ⭐ **BETTER HYPOTHESIS — NODE SPACING, NOT LATERAL KINKS.** `JuliaMotor/src/sim.jl:177` computes
   `κ[i] = dθ/ds`, already smoothed over ±`ksmooth` nodes. **If `ds` is tiny — two nearly-coincident
   centreline nodes — κ blows up no matter how smooth the line is laterally**, and `vtarget =
   sqrt(amax/κ)` collapses for one sample and recovers at the next: exactly a ~50 m/s discontinuity
   between adjacent samples. A lateral second-difference clamp cannot fix that, which is consistent
   with what was measured.

   **Test it before fixing anything:** report the distribution of node spacing `ds` around the lap
   and check whether the κ spikes coincide with the smallest `ds`. **State the expected p01 spacing
   first** — if the spikes sit on near-zero spacings, the fix is to resample the centreline to a
   minimum node separation, not to smooth it further.

   ⛔ **REFUTED (2026-08-29). Monza, 1925 nodes:**

   | track | nodes | ds p01 | ds p50 | ds min | ds at the 20 highest-\|κ\| nodes |
   |---|---|---|---|---|---|
   | Monza | 1925 | 2.952 m | 3.0 m | 0.544 m | median 2.996 m |
   | Watkins | 1251 | 2.967 m | 3.001 m | **2.873 m** | median 3.001 m, min 2.916 m |

   Watkins is the decisive one: its SMALLEST gap in the whole lap is 2.873 m against a median of
   3.001 m — there are no small gaps to blame, yet it still shows 10 steps >10 m/s.

   The prediction was "p01 under ~0.5 m against a median of several metres, with the high-κ nodes
   drawn from the smallest gaps". Spacing is **uniform at 3.0 m**, and the highest-κ nodes sit at
   entirely ordinary spacing. **Node spacing is not the cause.**

   ⭐ **SO BOTH CENTRELINE HYPOTHESES ARE DEAD, AND THE DATA READS DIFFERENTLY.** Neither lateral
   kinks (the second-difference clamp moved Monza 12 → 10 and made Watkins worse) nor node spacing
   explains the spikes. What is left is that **the spikes are CORRECT**: Monza has ~11 corners and
   the horizon target shows 12 steps >10 m/s; Watkins has ~11 turns and shows 10. **One large
   `vtarget` step per braking zone is what a right answer looks like** — a car SHOULD demand a big
   speed change entering Ascari.

   **That moves E89 from the target to the FOLLOWER.** If `vtarget` is right and the cars still
   "dart, lunge ahead, then fall back", the defect is in how they TRACK it — acceleration/braking
   limits, lag, or overshoot in the slot-car follower — not in the line they are given.

   **Next, and measure before changing anything:** log per-car `v` against `vtarget` around a Monza
   lap and look for overshoot/oscillation in the ERROR, not in the target. **State the expected
   settling behaviour first.** ⚠️ Do not smooth `vtarget` to make the symptom go away: that would
   slow the AI through every real corner, which is E84's pace complaint in a different disguise.

   ⭐ **CANDIDATE FOUND IN THE FOLLOWER (`demo/native/ai.jl:192`), sprint limit reached — recorded
   for the next sprint, NOT yet tested:**

   ```julia
   car.v += clamp(vt - car.v, -30.0*dt, 9.0*dt)   # brake harder than it accelerates
   ```

   **-30 m/s² is ≈3 g of braking.** A 1967 F1 car does ~1.1–1.3 g (11–13 m/s²); +9 m/s² acceleration
   is likewise well above what these cars manage at speed. So the follower can track an
   (established-correct) spiky `vtarget` almost exactly: hard decelerate into the step, hard
   accelerate out of it. That is what "lunge ahead, then fall back" describes, and it explains why
   the symptom survives however the LINE is smoothed — the two centreline fixes both failed because
   the line was never the problem.

   **Test, with the number stated first:** set the limits to physical values (brake ≈13, accel ≈5)
   and re-run the E89 step block. **Expected: the `vtarget` step counts DO NOT change at all** (the
   target is untouched — Monza should still read 12 steps >10 m/s), while the CARS' actual `v`
   traces stop surging. If the step counts move, the change is not doing what this predicts.

   ⚠️ Also on this line: `rand() < 8.0e-6` per car per step triggers a 2.4 s "mishap" at `vt *= 0.22`.
   That is deliberate GPL-style racecraft, but it is ALSO a car suddenly dropping back — check
   whether the PO's "fall back" is partly this before attributing all of it to the rate limits.

   ⚠️ The track-name field is NOT at a fixed offset from `DHPR` — reading `+0x10` yields "ami",
   "ort", "vort" (truncated `kyalami`, `mosport`, `zandvort`), so something variable-length precedes
   it. Fix that before trusting any per-track grouping.
3. **One slot-car opponent** driving that line, drawn with the existing car mesh, with collision
   against the player left OUT of this sprint.
4. **Four opponents, per-car pace offsets** calibrated to the table above, at all three tracks.
5. **Racing behaviour** — grid start, and whatever the videos show is missing.

**Done when** a 3-lap race at each of the three tracks runs start to finish with five cars, lap
times are recorded per car, and the finishing spread is within the shape of the table above — with
the measured numbers written into this item, not judged by feel.

⚠️ **Measure the frame cost with four opponents on screen before declaring any sprint done.** E80 is
open precisely because the base frame is already ~65 ms; four more cars is exactly the kind of
change that quietly turns 15 fps into 8 and gets attributed to something else later.


---

### E85 (PO 2026-08-28) — EPIC: multiplayer, the way GPL did it

PO: *"get multiplayer working"* + *"julia multiplayer should be like GPL multiplayer"*.

**What "like GPL" means, concretely.** GPL's multiplayer is peer-to-peer and deliberately thin:
every client simulates **only its own car** and broadcasts that car's state; remote cars are
received poses, dead-reckoned between packets. Nobody simulates anybody else's physics. A host
advertises a session (track, session type, laps); clients join and appear on the grid. Sessions run
the GPL ladder — **Practice → Qualify → Warmup → Race** — with a chat channel throughout. It was
famous for staying playable over a dial-up modem, which is a direct consequence of that design: the
per-car packet is tiny and sent at a low, fixed rate.

**Why that design fits this codebase almost exactly:**

- **Remote cars are already a solved rendering problem.** The AI field (`AICARS` / `AICHASSIS`,
  `ai.jl`) is a set of non-player cars drawn with real chassis meshes, placed by
  `RaceAI.pose_at`, and already collided against the player. **A remote human is an AI slot whose
  pose comes off the wire instead of off the rail.** Do not build a second car-drawing path.
- **The wire format already exists in another guise.** The `.jmr` replay records per-car poses per
  frame and plays them back (`JM_REPLAY`, and `N_AI` is taken from the recording so every recorded
  car gets a chassis). A replay IS a single-player recording of exactly the packet stream
  multiplayer needs. Mirror it rather than inventing a format.
- **There is a networking precedent in-tree:** `demo/drive_server.jl` serves live driving to a
  browser over **pure Julia stdlib `Sockets`**, no web framework. Same dependency budget.

🔒 **THE PHYSICS DIRECTIVE IS NOT WEAKENED.** *"The car physics should be determined entirely by
the iracing ibt data, there should be no modifiable parameters"* governs **the local player's car**,
and multiplayer must not become a back door around it. A remote car is a **received pose**. It is
never re-simulated locally, never given a tuning knob, and nothing in the netcode may reach
`CAR3D`, `vehicle_3d.jl` or `powertrain.jl`. Dead reckoning between packets is interpolation of a
received trajectory, not a physics model — keep it in the network module and say so in the code.

**Suggested sprint split** (each ~8 pts; the first two stand on their own):

1. **Two processes, one car each, same track — poses on the wire.** UDP, host + one client, fixed
   low tick rate. Success = each sees the other's car in the right place at the right time. No
   session logic, no lobby, no racing.
2. **Dead reckoning + jitter.** Extrapolate between packets; measure position error at a realistic
   packet rate and **write the number down**. State the expected error BEFORE measuring it.
3. **The session ladder** — Practice → Qualify → Warmup → Race, host-advertised, with the existing
   `JM_MODE` mapped onto it.
4. **Grid + results for N humans**, reusing E84's lap timing and standings.
5. **Chat**, and a join/leave that does not disturb a running session.

**Done when** two machines (or two processes) can run a 3-lap race together on the same track, each
driving its own car, with both cars in plausible positions throughout and a shared results table at
the end — **with the measured position error and packet rate recorded in this item**, not judged by
feel.

⚠️ **Order matters: E84 first.** Multiplayer reuses E84's remote-car slots, lap timing and
standings. Building it first means building those twice.

⚠️ **Measure the frame cost.** E80 has the base frame at ~65 ms with no headroom, and a network
thread that blocks the render loop will read as "multiplayer is slow" when it is the renderer.


---

### E86 (PO 2026-08-28) — REGRESSION BISECTED: Spa's levitate/bounce was 20 INVISIBLE houses

PO: *"in my previous spa test drive (before the drive yesterday) spa was drivable all the way
through, there was no levitate/bounce effect at the masta kink. This is a defect introduced since
my last prior test drive"*.

✅ **BISECTED, and ALREADY FIXED at HEAD** — but by accident, in a commit that did not know it was
fixing this.

**Measured.** `JM_SOLIDDIAG` at Spa, HEAD vs `JM_SOLID_KEEP_HIDDEN=1` (which restores the pre-fix
behaviour):

| | collidable solids at Spa |
|---|---|
| HEAD (fix active) | **808** |
| pre-fix (= the PO's drive) | **835** |

**27 objects were COLLIDABLE BUT INVISIBLE**, and 20 of them are houses:

```
house4×4  house25×3  house13  house1b  house21  house282  house29  house33
house35   house40    house41  house43  house47  house48            (= 20 houses)
bushrow2×2  bushrow3×2  bushrow5  shrub2  shrub4  chut              (= 7 others)
```

**Mechanism, and why it was drivable BEFORE:**

1. `271267f` (2026-08-27 11:46, **before** the PO's 21:56 drive) filtered these houses out of the
   **RENDER** — *"the PO's houses-on-the-road, found and filtered by RENDER FATE"*.
2. `SOLIDS` was built **independently of those render predicates**, so the filtered houses stayed
   **collidable while invisible**.
3. Before that commit the houses were VISIBLE — the PO could see and steer around them. After it
   they became invisible walls. Hence "drivable all the way through" → "suddenly I'm levitating".

⭐ **This unifies BOTH of the PO's Spa reports.** The "invisible-house collision" and the
"levitating and bouncing like a ball" are **one defect**, not two.

⚠️ **CORRECTION (same sprint): it was NOT fixed by accident.** My first write-up said `afe6ae3`
repaired this without noticing. Reading the code it shipped refutes that — `afe6ae3` contains a long
comment labelled **E71-S18** carrying the PO's own telemetry:

> *"at lapdist 6896 the car's speed doubled in one 0.2 s tick (66 → 131 km/h), lapdist ran BACKWARDS,
> and it flew 34 m sideways in 1.2 s … `house25` sits at lapdist 6899 with its FOOTPRINT reaching
> 1.6 m of the centreline. The renderer drops it (`onroad_fp`) so the road looks clear … an
> invisible 5 m collision disc across the racing line."*

So the Spa levitate was **diagnosed deliberately and fixed on purpose**, down to the exact object
(`house25`) and lap distance (6899 ≈ Masta). ⭐ **What actually failed was the COMMIT MESSAGE.** It
is headlined *"E77-F: the Ring bridge underpasses no longer launch the car"* — so the record showed
a Ring fix, the Spa regression looked untouched, and the PO reasonably reported it as still open.
**Two unrelated defects fixed under one headline is how a closed item reads as open.**

**E86's own contribution is the MEASUREMENT, not the diagnosis:** the bisect confirms no OTHER cause
in the window, and quantifies the blast radius — **27 objects, 835 → 808**, with all 27 named. The
code comment identified one house; the count shows there were twenty.

**Needs a PO re-drive to confirm by feel — the PO would be confirming a fix, not hunting a bug.**

---

### E87 — GATE: a collidable object must never be invisible

**The class, not the instance.** E86 is the third time render and collision have silently diverged
(Spa houses ×2 — the PO hit them twice — and the Ring bridge underpasses). **Nothing checks it**, and
the defect is undetectable by looking: the only way to find an invisible wall is to drive into it.

**The invariant:** every entry in `SOLIDS` either renders, or is on an explicit exempt list.

**Why this is cheap and worth doing now:** it is headless, it is per-track, and **the negative
control already exists and is measured** — `JM_SOLID_KEEP_HIDDEN=1` reintroduces exactly 27
violations at Spa, so the gate can be proven to fail before it is trusted to pass. (Compare
`maximized_nav` in the sister port, which passed its own negative control and had to be rewritten.)

⚠️ **Do NOT implement it by re-testing the same predicates the fix uses** (`onroad_fp` &c). That
would be circular — it would pass by construction and could never catch the NEXT filter someone adds
without updating `SOLIDS`. **Cross-check `SOLIDS` against the objects actually submitted for
RENDER.** Predicate-independent, or it is not a gate.

**Done when** it runs on all five tracks, reports 0 at HEAD, and reports 27 at Spa under
`JM_SOLID_KEEP_HIDDEN=1`.

### 2026-08-28 — IMPLEMENTED as `JM_SOLIDGATE=1` (+ `JM_SOLIDGATE_EXIT=1`), and the first run REFUTED my design

Built as specified — **predicate-independent**: it compares the two FINAL sets, asserting every
entry in `SOLIDS` coincides (0.5 m quantised) with something actually submitted for render
(`OBJECTS` mesh or `BILLBOARDS` sprite). It does **not** re-run `onroad_fp`/`onroad_bldg`/…, which
would pass by construction and never catch the next filter added without updating `SOLIDS`.

⚠️ **First run at Spa reported 139 "violations" — and every one was a FALSE POSITIVE.**

```
armco1×17  armco1s×15  armco2s×3  armco3×1  armcow1×19  armcow2×8  armcow3×22
armcow4×2  bush×5  bush2×9  bushrow5×38
```

**Not one house.** Armco barriers and bushes are plainly on screen when you drive Spa, so a
position-only match is the wrong test for classes that reach the display by another path (track
parts, or differently-anchored sprites). ⭐ **A position miss is not proof of invisibility.**

**Refined, by splitting on NAME rather than by lowering a threshold:**

| bucket | meaning | verdict |
|---|---|---|
| **UNDRAWN** | the name appears **nowhere** in the drawn sets | genuinely invisible → **FAILS** |
| **ANCHOR** | the name **is** drawn elsewhere | our position match is wrong, not the object → **reported as a gate BLIND SPOT, not a failure** |

Printing the ANCHOR bucket loudly is deliberate. Suppressing it would leave a green gate hiding a
known blind spot — the shape that let `maximized_nav` (sister port, same day) pass its own negative
control.

✅ **Already established by the failed run: NO HOUSES are invisible at HEAD**, so the E86/E71-S18
fix holds for the class that actually caught the PO.

✅ **BOTH ARMS MEASURED AT SPA — the gate detects the regression it was written for.**

| arm | solids | **UNDRAWN** | exempt | anchor |
|---|---|---|---|---|
| **HEAD** | 808 | **0** | 125 | 2 cls |
| **`JM_SOLID_KEEP_HIDDEN=1`** | 835 | **20** | 130 | 4 cls |

The 20 are **exactly the houses** — and include **`house25 ×3`**, the object the E71-S18 comment
named at **lapdist 6899 = Masta**, carrying an invisible 5 m collision disc. The gate names the
object the PO actually hit.

⚠️ **I predicted 27 and the answer is 20 — the gate is MORE discriminating than my prediction.**
The 27 was the raw solid-count delta from the E86 bisect. The gate splits it correctly:
**20 genuinely invisible houses + 5 `bushrow*` (exempt, track geometry) + 2 `shrub*` (anchor,
drawn elsewhere) = 27.** A count of solids that disappeared is not the same quantity as a count of
objects that were invisible, and conflating them would have overstated the defect by a third.

### 2026-08-28 — extended to three more tracks: two clean, ZANDVOORT IS NOT

| track | solids | drawn cells | **UNDRAWN** |
|---|---|---|---|
| monza | 2 | 137 | **0** ✅ |
| watglen | 5 | 126 | **0** ✅ |
| spa (HEAD) | 808 | 6572 | **0** ✅ |
| **zandvoort** | **269** | **199** | **175** ⚠️ |

```
zandvoort: bushes01 ×74   bushes02 ×37   bushes03 ×47   ftruck ×1   hotels ×1
```

⚠️ **DO NOT DISMISS THIS AS A GATE ARTEFACT, and do NOT blanket-exempt `bushes*`.** The arithmetic
matches the Spa defect exactly: the load reports **215 trackside objects + 39 billboards = 254
rendered things against 296 solids**, so Zandvoort genuinely carries more collidable objects than it
draws. That is the same shape as the 20 invisible houses, at a different scale.

**Two readings, and they need separating by measurement, not by assumption:**
1. **REAL** — 175 invisible collidable objects at Zandvoort. `bushes*` carry a 1.5 m radius
   (`solidR`), so each is a small invisible obstacle; `ftruck` and `hotels` are mesh-class names and
   would be *large* ones.
2. **GATE BLIND SPOT** — these render as BILLBOARDS and the position match misses them, exactly as
   `bush`/`bush2` did at Spa (which landed in ANCHOR). But note Zandvoort reports **0 anchor and 0
   exempt**, so the name-matching found nothing at all for them — a different failure from Spa's.

⭐ **The gate's credibility rests on both halves: it found a real defect at Spa and stayed silent at
Monza and Watkins.** It does not cry wolf everywhere, so a 175 at Zandvoort deserves investigation
rather than an exemption.

**Next:** check whether `bushes01` appears in the render sets AT ALL at Zandvoort (name-only, no
position test). If absent → real invisible collidables, and the PO can be told which. If present →
the billboard position match is the defect and must be fixed, not exempted. **Start with `ftruck`
and `hotels`** — two objects, mesh-class names, large radii, easiest to confirm by eye in a capture.

### 2026-08-28 — E87-S2: the Zandvoort finding was REAL. 159 invisible collidables removed.

`SOLIDS` honoured the `onroad_*` predicates (the E71-S18 fix) but **not the render's other three
conditions**. The `JM_SOLIDGATE_WHY` diagnostic separated the causes per name:

```
bushes01/02/03  mesh=YES  dropped=no   -> UNDER 1 m, so never rendered (OBJECTS needs >1 m)
                                          yet solidR gives bush* a 1.5 m collision radius   x158
hotels          mesh=YES  dropped=YES  -> dropped by the junk filter, still solid (the SPA shape)  x1
ftruck/rescu*   mesh=no                -> no mesh at all                                     x16
```

**Result — `SOLIDS` now mirrors the render's own conditions (`drop()`, the >1 m height test) for
mesh-capable objects:**

| track | solids before → after | undrawn before → after |
|---|---|---|
| **zandvoort** | 269 → **110** | 175 → **16** |
| **spa** | 808 → **808** | 0 → **0** |

⚠️ **TWO REGRESSIONS OF MY OWN, both caught by the gate's OWN reporting, both the same error:**

| I nearly removed | scale | why it looked removable | caught by |
|---|---|---|---|
| `armco*` barriers | 125 @ Spa | no object mesh — they are **baked track geometry** | exempt bucket 125 → **0** |
| `bush`/`bush2` | 14 @ Spa | no object mesh — they are **billboards** (and the PO wants bushes hittable, E15) | anchor bucket 14 → **0** |

⭐ **"Has no object mesh" is NOT "is invisible."** Objects reach the screen three ways — mesh,
billboard, baked track geometry — and `SOLIDS` can only see the first, because **`BILLBOARDS` is
built ~75 lines LATER**. Removing collision from something the player can SEE is a quieter and worse
failure than the invisible walls being fixed. ⭐ **Reporting three buckets separately is what made
both visible**: a single "0 undrawn" read as success while the barriers silently ceased to exist.

**The filter is therefore deliberately CONSERVATIVE — it judges only mesh-capable objects.** The 16
meshless ones stay solid and keep being REPORTED (an honest non-zero), because at that point in the
load the code cannot tell a billboard from nothing at all.

### E87 — RUN ON THE PO'S THREE TRACKS (2026-08-29, requested in 6b8cd00)

| track | solids | drawn cells | UNDRAWN-BUT-SOLID | verdict |
|---|---|---|---|---|
| Nürburgring | — | — | — | **did not run** (no gate line; load exceeded the poll window) |
| Monza | **2** | 137 | 0 | passes |
| Watkins | **5** | 79 | 0 | passes |

⚠️ **BOTH PASSES ARE UNINFORMATIVE, AND THAT IS THE FINDING.** Zandvoort reported **269** solids when
this gate found 175 invisible collidables. **2 and 5 are implausibly small for circuits lined with
armco.** A "0 undrawn-but-solid" verdict drawn from a population of two objects says almost nothing
about the property the gate exists to check.

⭐ **AND THE LOW COUNT MAY ITSELF BE A DEFECT, BIGGER THAN THE ONE THE GATE LOOKS FOR.**
`solid_exempt` deliberately keeps `armco`/`fence`/`rail`/`barrier`/`wall` collidable regardless of
mesh, precisely so barriers cannot be silently de-solidified. If Monza ends up with 2 solids, either
those objects are named differently there, or the drop rules have removed them — and **a circuit
whose barriers are not collidable is a car that drives through the armco**. That is a gameplay
defect, not a gate result.

**Next, and measure before concluding:** dump the NAMES in `SOLIDS` at Monza and Watkins
(`JM_SOLIDDIAG`), and compare against the instance names present. **State the expected count first**
— Monza 1967 has continuous armco down both straights, so the honest prior is dozens, not two.

⚠️ The Nürburgring row is "did not run", not "passed": `drive_native_mtk.jl:1648` notes the Ring has
no collidable trackside objects by design (scenery baked in), so a legitimate 0 is possible there —
but this run never printed a gate line at all, so nothing was measured. Do not record it as a pass.

⬜ **E87-S3, the proper close: build `SOLIDS` AFTER `BILLBOARDS`** so all three render paths are
visible at once and the invariant can be enforced exactly rather than conservatively. Then the 16
resolve one way or the other.
⬜ **PO 2026-08-28: RUN THE E87 GATE ON NÜRBURGRING, MONZA AND WATKINS.** Spa and Zandvoort are the
only tracks measured on BOTH sides of the `SOLIDS` changes. The changes themselves are **NOT
track-scoped** — the render-mirror filter (E87-S2), the on-road predicates (E77-F/E71-S18), and the
`powertrain.jl`/`vehicle_3d.jl`/`drive_rt3d.jl` physics edits are all global — so every track is
affected and three are unverified:

| track | solids before → after | state |
|---|---|---|
| spa | 808 → 808 | ✅ measured both sides |
| zandvoort | 269 → 110 | ✅ measured both sides |
| **monza** | 2 → **?** | ⚠️ measured only BEFORE the E87-S2 filter |
| **watglen** | 5 → **?** | ⚠️ measured only BEFORE |
| **nürburgring** | **?** → **?** | ❌ **NEVER measured** |

⭐ **The Ring is the priority.** It took the E77-F bridge fix (`HAT_EXCLUDE` = `br_under`/`villone`)
**plus** both global `SOLIDS` changes **plus** the physics edits — the most changed underneath it and
the least verified, and it is the track where the PO reported underpass levitation. Monza and Watkins
carry only 2 and 5 solids, so the filter has almost nothing to act on there, but that is a
prediction, not a measurement.

**Recipe** (each ~10–25 min; the Ring is slowest; **do NOT run two concurrently — they queue on
`gl-lock` and the second times out**):

```
TRACK=<t> JM_SOLIDGATE=1 JM_SOLIDGATE_EXIT=1 julia --project=. drive_native_mtk.jl
```

⚠️ **`JM_SOLIDGATE_EXIT=1` is not optional.** Without it the gate prints and the game continues into
the render loop, holding the display lock for the full timeout — this cost ~25 min of queue twice.

**Done when** all five tracks report **0 UNDRAWN**, or a non-zero is explained per object (the 16
meshless `ftruck`/`rescu*` at Zandvoort are the known open case, pending E87-S3).

⚠️ Each Spa arm costs ~20 min (14.1 km lap, 92 548 HAT triangles), so the pair is ~40 min — budget
for it, and do not run two arms concurrently against `gl-lock` (they queue and the second times out).


---

### E88 (PO 2026-08-28) — remove ALL line-of-people objects from Watkins Glen

PO: *"remove all lines of people objects from Watkins Glen, several of which are right in the track
on the back stretch"* — video `/home/admin/Videos/260828_watkins_race.mp4` (recorded during the
5-car race, 2026-08-28 20:32).

⭐ **CAUSE IS ALREADY IDENTIFIED — E79's removal is ZANDVOORT-ONLY.** `drive_native_mtk.jl:2116`:

```julia
_dropcrowdrows = ZANDV && get(ENV,"JM_KEEP_CROWDROWS","0") == "0"
```

The `ZANDV &&` guard means Watkins keeps every `standcrowd` row. E79 removed them at Zandvoort on
the PO's instruction (*"remove all line of people objects from zandervoort"*) and that guard was
written literally — so the **general** half of the same instruction (*"remove line-of-people objects
if there's any chance they could be in the road or partially hanging in air; these objects don't add
much and detract a lot if misplaced"*) was never applied anywhere else.

**Fix:** drop the `ZANDV &&` guard so `standcrowd` rows are removed on every track (or at minimum
add `|| WATGLEN`). `JM_KEEP_CROWDROWS=1` already exists as the revert.

⚠️ **Verify with the on-road census, not by eye.** E79's first attempt removed **700** rows at Spa
because it subtracted half the row width from the lateral distance — but rows run *along* the track,
not across it. Projecting onto the road normal cut that to 6. Whatever the Watkins number is, state
it before running and check it against the census.

⚠️ **Do NOT reuse the E79 "billboard crowd" test blindly** — same reason.

**Done when** no `standcrowd` row remains at Watkins, the count removed is recorded here, and the
other three tracks' counts are recorded too (the guard removal affects all of them).

☑ **FIXED AND VERIFIED FOR THE REPORTED TRACK (2026-08-29).** Guard is now unconditional
(`_dropcrowdrows = get(ENV,"JM_KEEP_CROWDROWS","0") == "0"`). Before/after measured on ONE binary
using `JM_KEEP_CROWDROWS=1` as the "before" arm, each run verifying its own `→ track:` banner:

| track | before | after |
|---|---|---|
| watglen | **52** | **0** |
| zandvoort | 96 | 0 |
| monza | 0 | 0 |
| spa | not measured | not measured |
| nurburgring | not measured | not measured |

Monza has no `standcrowd` placements at all, so the guard change is a no-op there.

⚠️ **Spa and the Nürburgring are NOT measured, and are not being reported as zero.** Both are the
largest tracks and were still loading textures when the census's 300 s poll killed them
(`e88_spa_1.log` ends mid-`loading textures…` with `→ track: Spa` already printed, so the run was
healthy — the window was too short, not the track). Re-run those two with a longer window to close
this row out.

⚠️ **THE FIRST CENSUS COULD NOT HAVE DETECTED THIS FIX.** `JM_CROWDDIAG` iterated `insts`, the RAW
placement list built ~270 lines before `drop()` exists, and printed the total as "crowd rows kept".
It therefore counts rows PLACED and cannot move when a drop rule changes: the first before/after
read `52 -> 52` and looked exactly like a fix that did nothing. It now reports PLACED and KEPT as
separate lines. A verification metric that is not downstream of the change under test will confirm
whatever you already believe.


---

### E89 (PO 2026-08-28) — AI cars "dart around like june bugs, lunge ahead, then fall back"

PO: *"AI cars at monza dart around like june bugs, lunge ahead, then fall back. Make AI cars behave
as they do in GPL; look at the .rpy GPL replay files under ~/sgl/THU"* — video
`/home/admin/Videos/260828_monza_race.mp4` (5-car race, pole start, 10 s head start,
`JM_AI_REFLAP=138`).

⭐ **THE "LUNGE AHEAD, THEN FALL BACK" IS ALREADY MEASURED — it is E84-S3's curvature spikes.**
Do not start from scratch. E84-S3 measured Monza's racing line and found **rare but physically
impossible kinks**: `max κ = 0.32 /m` = a **3.1 m radius**, where no F1 corner is tighter than
Monaco's ~12 m Loews. `_vtarget = √(amax/κ)` pins the commanded speed to **`vmin` = 12 m/s** at each
one — and recovering to 74 m/s at the 9 m/s² acceleration cap takes **~7 s and ~300 m**. The 150 m
forward-max then poisons the approach as well (`p10` vtarget falls 37.5 → 18.0 m/s while the median
does not move at all).

**A car that accelerates, slams to 12 m/s at an invisible point, then claws back up IS "lunge ahead,
then fall back."** Monza has **five spike clusters** — `s≈2141–2477` (five of the eight worst inside
336 m) and `s≈950` — so it happens several times a lap. E84-S4 then confirmed the **re-centring pass
creates the kinks** (`JM_NORECENTRE=1`: max κ 0.32 → 0.034, radius<20 m count 4 → 0).

⭐ **So E84's fix and this PO report are very likely the SAME DEFECT.** Fix the kinks first and
re-drive before touching the racecraft — most of the lunging may simply stop.

**The "darting like june bugs" is a SECOND, lateral mechanism.** `ai.jl:228` already carries
hysteresis added for exactly this, in the author's own words — *"so the AI commit to a pass instead
of skittering between rails like a water-insect"*. The PO is describing that behaviour anyway, so the
hysteresis is **insufficient, not absent**. Measure the lane-change RATE (switches per car per lap)
before changing thresholds.

**Third, smaller: the mishap system.** `ai.jl:220` — `rand() < 8.0e-6` per step gives a car a 2.4 s
crawl at **0.22× speed** (~1–2 per race across the field), and the launch adds a **45 %** chance of a
getaway fumble per car. Both are deliberate GPL-style imperfections, but they also read exactly as
"falls back". Check they are not firing far more often than intended at 60 Hz × 5 cars.

**Calibrate against the `.rpy` files, as the PO asks.** `/home/admin/sgl/THU/INSTALL/replay/` holds a
complete `67F1_Rob_Fle_monza_<car>_<laptime>.rpy` set for all seven 1967 chassis (Lotus 1:26.490 →
Cooper 1:28.905, a **2.42 s spread**). Those are real GPL driving: use them for **speed-vs-distance
smoothness and lane discipline**, not just lap time. 🔒 **READ-ONLY — copy before parsing.**

**Suggested order:**
1. Fix the E84-S4 kinks (clamp each re-centring shift relative to its neighbours; keep the pass).
2. **Re-drive Monza and re-report** — quantify what remains before tuning anything.
3. Measure lane-switch rate per car per lap; compare against a decoded `.rpy` line.
4. Only then touch hysteresis / mishap rates.

**Done when** a Monza AI car's speed-vs-lap-distance trace has no unexplained collapses to `vmin`,
its lane-switch rate is within the range measured from the `.rpy` replays, and the PO's re-drive
confirms it — **with the numbers recorded here, not judged by feel.**

### E90 (2026-08-29) — ⚠️ Monza and Watkins have almost no collidable barrier OBJECTS (largely explained — see the correction below)

Found while running E87 on the PO's three tracks. The gate passes at both — and the pass is the
symptom:

| track | solids | barrier objects present in the GPL track data |
|---|---|---|
| Zandvoort | **269** | `armcoend`, `armcopit`, `armco_s`, `armco_sh`, `wall_e/s/t` |
| Monza | **2** | `armco_s`, `FENCE_S`, `rail`, `Wall_e`, `Wall_s`, `Wall_t` |
| Watkins | **5** | `armco_s`, `fence` |

The barrier objects **exist in the data** for all three (read straight out of
`~/sgl/THU/WP/drive_c/Sierra/GPL/tracks/<t>/`), and `solid_exempt` in
`drive_native_mtk.jl` deliberately keeps `armco`/`fence`/`rail`/`barrier`/`wall` collidable
regardless of mesh — precisely so barriers cannot be silently de-solidified. Yet Monza ends up with
two collidable objects on a circuit with continuous armco down both straights.

**If this is what it looks like, the car drives THROUGH the armco at Monza and Watkins** — a
gameplay defect, and one that a passing E87 actively conceals, because a "0 undrawn-but-solid"
verdict over a population of 2 is vacuous.

⚠️ **WHAT IS AND IS NOT ESTABLISHED.** Established: the barrier NAMES exist in the track data, and
`SOLIDS` ends up at 2/5 versus Zandvoort's 269. NOT established: how many barrier INSTANCES are
placed on each circuit — name presence is not a placement count, and a track can ship an object it
never places. **Measure that first, with the expected number stated before the run.**

**Then find where they are lost.** Candidates in order: (a) `trackside_objects` does not return them
for these tracks; (b) a `drop()` rule removes them before `SOLIDS` is built; (c) the names differ in
case or suffix from what `solid_exempt` matches.

⭐ **NARROWED, 2026-08-29 — (c) and (b) ELIMINATED, (a) SUPPORTED:**

* **(c) eliminated by reading the call site**, as warned: `nml = lowercase(i.name)` (line 2543) and
  `solid_exempt(nml)` (2595). The name IS lowercased, so `FENCE_S`/`Wall_e` match fine.
* **the radius table is not the block either**: `solidR` gives `armco`/`barrier`/`fence`/`wall` a
  1.2 m radius. (⚠️ I also claimed **`rail` is NOT in `solidR`** and called it "small, separate,
  real". **It is not real** — checked across monza/watglen/zandvort/spa67/nurburg, both the packed
  archives and the loose files: **zero `rail*.3do` objects exist on any of them**. `rail`/`RAIL` in
  the data is a TEXTURE name, like `armco_s`. Nothing to make solid, so nothing to fix. Retracted
  rather than left as a phantom to-do.)
* **the road-exclusion is not the block**: `SOLID_EXCL_HW` is 4.0 m against `ROAD_HALFW` 9.0 m, so
  barriers at the road edge are not excluded by E31's rule.
* **(a) SUPPORTED — the geometry is never LOADED.** `objnames` (line 1885) is built from the `.3do`
  files present in the track directory plus `DATPACK` keys, so an object only loads if its `.3do`
  is found. On disk:

  | track | loose `.3do` files | barrier files present |
  |---|---|---|
  | Zandvoort (**269 solids**) | 69 | `armcopit.3do`, `armco_s.mip`, `armco_sh.mip`, `armcoend.mip` |
  | Watkins (**5 solids**) | 28 | only `armco_s.mip` — a TEXTURE, no geometry |
  | Monza (**2 solids**) | **0** | only `WALL_E.mip`; everything is packed in `monza.DAT` |

  **The one track with loose `.3do` barrier geometry is the one with 269 solids.** The other two
  depend entirely on `DATPACK` extraction from the packed archive.

**Next: does `DATPACK` yield the barrier `.3do` entries for Monza and Watkins?** Print the keys it
produces for each track and grep them for `armco`/`fence`/`wall`. **State the expected count first.**
If they are absent, this is an ARCHIVE EXTRACTION gap, not a collision-rule gap — and the fix is in
the loader, nowhere near `SOLIDS`.

⛔ **MEASURED, AND IT REVERSES THE HYPOTHESIS ABOVE (2026-08-29).** `parse_dat` on each archive:

| track | entries | `.3do` | barrier `.3do` |
|---|---|---|---|
| Monza | 701 | 149 | **3** — `pitwall.3do`, `pitwall1.3do`, `pitwall2.3do` |
| Watkins | 246 | 68 | **1** — `fence.3do` |
| Zandvoort | 316 | 76 | **0** |

**Zandvoort's archive contains NO barrier geometry at all** — its 269 solids come from the LOOSE
`.3do` files on disk (`armcopit.3do` …). And Monza's archive has no `armco.3do` whatever: its only
barrier objects are three pit walls.

**So there is no extraction gap, and probably no defect of the kind this item was filed for.** The
`armco_s` / `FENCE_S` / `Wall_e` strings that prompted E90 are **`.mip` TEXTURE names, not objects** —
at Monza and Watkins the armco is part of the BAKED TRACK GEOMETRY, and Zandvoort is the unusual
track that ships it as placeable objects. `SOLIDS` = 2 and 5 is then the correct count of discrete
collidable props, not evidence of missing barriers.

⚠️ **The original worry is NOT thereby answered, only relocated.** "Can the car drive through the
armco at Monza?" is still open — it now depends on whether the baked barrier geometry is collidable
through the track-surface path, which `SOLIDS` never covered. **That is the question to test, and it
needs a DRIVE, not a census:** put the car into the armco at a known lapdist and see whether it is
stopped. **State the expected outcome first.**

_Lesson recorded rather than quietly deleted: the loose-`.3do` count supported this item's original
hypothesis and the archive contents refuted it. One measurement agreeing is not the same as the
right measurement._

**Points:** 8

---

### ⚠️ AUDIT (2026-08-29): three documented env levers in this file DO NOT EXIST

Every `JM_*` name mentioned in this backlog was checked against the source (90 named). Four came
back absent; one (`JM_NO_SHIFTCLAMP`) was stale and has been corrected. The other three are still
documented here as working opt-ins and are **not in any `.jl` file**:

| lever | what this backlog claims | reality |
|---|---|---|
| `JM_BRUSH` | *"brush tyre WIRED into the car (opt-in `JM_BRUSH`)"*, and a planned task *"make brush default (needs a `JM_BRUSH` test-drive for feel)"* | absent. `BRUSH` appears in 8 `.jl` files, so the MODEL exists — but there is no env switch by that name, so the documented way to turn it on does nothing |
| `JM_AI_KINEMATIC` | *"robust kinematic fallback kept (`JM_AI_KINEMATIC`)"* | absent. `KINEMATIC` appears in 1 `.jl` file |
| `JM_FFB_DEAD` | *"deadzone on the front-axle lateral force (`FFB_DEAD`, `JM_FFB_DEAD`, default 0.06 mg/4)"* | absent, and `FFB_DEAD` is absent too — neither name exists |

**Why this matters more than a typo:** each of these tells a reader that a capability is available
behind a flag. Setting a non-existent env var fails silently and looks exactly like "I enabled it
and it made no difference" — which is a conclusion about the FEATURE drawn from a fact about the
FLAG. A planned sprint ("make brush default") is currently gated on a test-drive that cannot be
performed as written.

**Do not fix by adding the flags.** Find out what happened to each first: renamed, removed, or never
wired. Only the third case is a defect; the first two are documentation rot, and inventing a flag to
match a stale note would manufacture the feature's appearance without its substance.

### E91 (PO 2026-08-29) — 🔴 "Tesla brakes": lifting off the throttle decelerates the car like ABS

PO: *"Lifting completely off the throttle causes powerful antilock brakes to apply, quickly and
smoothly decelerating the car, such that applying the brakes (pulling back on the 3Dx joystick) is
never necessary. You retorted that I'm driving too slowly to make braking necessary - perhaps, but I
don't think so. Note that the iracing .ibt telemetry is the gold standard, tested with the
thrustmaster TX, not a mere joystick, so the physics model is correct, and should not be adjusted."*

⛔ **THE STANDING CONSTRAINT APPLIES AND IS NOT NEGOTIABLE HERE.** *"The car physics should be
determined entirely by the iracing ibt data, there should be no modifiable parameters."* So this is
**not** to be fixed by tuning a deceleration until it feels right. Either the coast deceleration is
faithfully what the `.ibt` model produces — in which case the fault is elsewhere — or it is coming
from something that is **not** in the `.ibt`, which is the defect.

⚠️ **AND MY EARLIER RESPONSE WAS NOT A DIAGNOSIS.** "You're driving too slowly to need the brakes" is
an explanation of the PO's EXPERIENCE, not a measurement of the CAR, and the PO has now rejected it
twice. It must not be offered again in place of a number.

⚠️ **THIS IS A RECURRENCE, NOT A NEW REPORT.** `joycfg.jl:45` already records: *"PO 2026-08-27: 'let
off the throttle and the car stops very quickly, even if I don't use brakes'. The trace shows
brk=0.07–0.11 throughout those coasts: throttle and brake share axis 2 (push/pull) and the
configured deadzone is only 0.06, so a stick resting slightly back applies a continuous light
brake."* A deadzone was applied and `JM_DEADZONE` added. **The PO is reporting it again**, so either
that was not the whole cause or the deadzone is still too small for their stick.

**MEASURE FIRST, IN THIS ORDER — the two causes need opposite fixes:**

1. **Is the brake actually being applied?** Log `inp.brake` through a full coast-down (the telemetry
   line at `drive_native_mtk.jl:4878` already writes `brk` per frame). **If `brk > 0` the input path
   is still the cause** — the shared push/pull axis is resting into brake territory — and the fix is
   in `joycfg.jl`, not the physics. **State the expected value first:** after the 2026-08-27 fix it
   should be exactly 0.0 on a released stick.
2. **If `brk == 0.0` throughout and the car still decelerates hard**, the deceleration is in the
   model — and the question becomes whether it is `.ibt`-derived. ⭐ **Three HARDCODED constants in
   `JuliaMotorMTK/src/components/vehicle_3d.jl` are not from any `.ibt`:**

   | line | term | value | note |
   |---|---|---|---|
   | 72 | rolling resistance | `rr = 0.026*m*g*tanh(u/0.12)` | Crr = 0.026, ~double a realistic tarmac figure |
   | 56 | clutch damping | `c_c = 60.0` | drives engine braking through the driveline at zero throttle |
   | 56 | torque cap | `T_cap = 500.0` | ditto |

   These are exactly the "modifiable parameters" the PO's standing constraint rules out. **The fix is
   to derive them from the `.ibt` or to record why they cannot be — not to retune them by feel.**

   ⭐ **COMPUTED (2026-08-29) — AERO + ROLLING ARE NOT THE CAUSE, AND `Crr` IS A RED HERRING.**
   With the model's own constants (`m=617`, `CdA=0.9`, `ρ=1.10`, `Crr=0.026`):

   | speed | drag | rolling | total | coast decel |
   |---|---|---|---|---|
   | 100 km/h | 382 N | 157 N | 539 N | **0.089 g** |
   | 200 km/h | 1528 N | 157 N | 1685 N | **0.278 g** |
   | 280 km/h | 2994 N | 157 N | 3152 N | **0.521 g** |

   That is an ordinary race-car coast, nowhere near "powerful antilock brakes" (a 1967 F1 car brakes
   at ~1.1–1.3 g). And **rolling resistance contributes a flat 0.026 g at every speed** — correcting
   `Crr` to a realistic 0.014 changes the retarding force by **73 N**, which is imperceptible.
   **So "fixing" `Crr` would have done nothing while looking like a fix**, and it is struck from the
   suspect list on arithmetic rather than opinion.

   ⭐ **MEASURED IN THE MODEL (2026-08-29) — THE DRIVELINE IS THE SOURCE, AND IT DOMINATES AT LOW
   SPEED.** `build_car3d` + `step_car3d!` coasted headless with `throttle=0, brake=0` for 2 s:

   | speed | aero+rolling (calculated) | **measured coast** | driveline contribution |
   |---|---|---|---|
   | 100 km/h | 0.089 g | **0.302 g** | **+0.213 g — 3.4× the aero figure** |
   | 200 km/h | 0.278 g | **0.377 g** | +0.099 g |
   | 280 km/h | 0.521 g | **0.622 g** | +0.101 g |

   At 100 km/h the car sheds **21 km/h in two seconds** with no brake applied. The PO's *"applying
   the brakes is never necessary"* is consistent with that: 0.3 g on lift-off does most of the work
   for any corner that does not need heavy braking. Note the driveline term is roughly CONSTANT in
   absolute terms (~0.1 g) but its RELATIVE share explodes at low speed, where aero has faded —
   which is exactly where a driver notices "it brakes itself".

   ⛔ **AND THE CONSTANTS THAT PRODUCE IT ARE NOT `.ibt`-DERIVED.** `c_c = 60.0` (clutch damping),
   `T_cap = 500.0`, `Ie = 0.18`, `k_idle = 0.5`, `idle_rpm = 2000.0` are all hardcoded defaults in
   `vehicle_3d.jl`. Under the PO's standing constraint — *"the car physics should be determined
   entirely by the iracing ibt data, there should be no modifiable parameters"* — these are the
   defect, whatever their value.

   **Next: compare this coast curve against the `.ibt` gold for the same car and speeds.** The `.ibt`
   records real coast-downs, so the comparison is direct and needs no judgement about feel. ⚠️ **Do
   not simply reduce `c_c` until it feels right** — that would replace one unjustified constant with
   another, and the constraint is about PROVENANCE, not magnitude.

   ⛔ **ATTEMPTED — THE AVAILABLE GOLD `.ibt` FILES CONTAIN NO CLEAN COAST-DOWN (2026-08-29).** Both
   sets in `~/gold standard/julia racer/` were scanned for runs of ≥30 consecutive samples with
   `Throttle < 2%` **and** `Brake < 2%` (sample rate verified as **60 Hz** from the `SessionTime`
   channel, not assumed):

   * **Nürburgring** — 2 coast runs, and one of them **ACCELERATES** (61 → 66 km/h over 3.1 s,
     i.e. −0.047 g). That is the Nordschleife's elevation: gravity contaminates every coast segment,
     so a deceleration read off this track is drag **plus or minus** an unknown slope term.
   * **Skidpad** — 13 coast runs, but the circuit is a continuous constant-radius corner, so the
     numbers are dominated by **cornering scrub**: 0.863 g (64 → 32 km/h in 1.05 s) and 0.625 g
     (76 → 37 km/h) with the brake at zero. Those are not straight-line drag figures. The quieter
     ones (0.014 g at 11–15 km/h, 0.054 g at 26 km/h) are at speeds far below where the PO drives.

   **So the comparison E91 needs cannot be made from the telemetry on hand**, and any number taken
   from it would be drag plus an uncontrolled contaminant. ⚠️ Note both contaminants push in the
   direction that would make our model look CORRECT — a hard-cornering "coast" at 0.86 g makes 0.302 g
   look conservative. Concluding "the model matches gold" from this data would be exactly backwards.

   **What would settle it:** one `.ibt` of a straight-line coast-down — lift off in top gear on a
   flat straight and let it run, no steering, no brake. That single lap answers the question outright,
   and it is the kind of thing only the PO can record.

   ⭐ **(SUPERSEDED REASONING, KEPT:) THAT PROMOTES ENGINE BRAKING TO PRIME PHYSICAL SUSPECT.** If `brk == 0` and the car still
   decelerates like ABS, the only remaining path is the driveline: at zero throttle with the clutch
   engaged in a low gear, engine drag reaches the wheels through `c_c` / `T_cap` / `Ie` and the
   `engine_torque(rpm, 0)` curve. **Measure the coast decel in the sim with `brk` pinned to 0 and
   compare it against the table above** — anything much beyond ~0.3 g at 200 km/h is coming from the
   driveline, not the air.

**Done when** a coast-down from a stated speed is logged with `brk` proven 0, the deceleration curve
is compared against the `.ibt` gold for the same car and speed, and any term not traceable to the
`.ibt` is either sourced from it or documented as an explicit, justified exception.

**Points:** 8

---

### STATUS — where the 2026-08-28/29 session stopped (written at the PO's request)

**In flight when work stopped:** a cold Spa load with `JM_TEXCACHE=1` under `gl-lock` (40-minute
window). It had reached `[t+936.2s] physics build done — game loop imminent` with 1.1 GB of texture
cache written. If it completed, a WARM run is the outstanding measurement.

#### julia

| item | state |
|---|---|
| **E88** — people in the Watkins track | ☑ **FIXED & VERIFIED.** `watglen 52 → 0` kept crowd rows, `zandvoort 96 → 0`, `monza 0 → 0`. Spa and the Nürburgring are recorded **not measured**, not zero. |
| **E89** — "june bugs" | Root cause NOT the centreline. Two hypotheses falsified by measurement: the second-difference clamp missed its target (Monza 12→10, Watkins 10→11 — **regressed**, so shipped OFF), and node spacing is uniform (Watkins' smallest gap 2.873 m vs 3.001 median). Live suspect: **`ai.jl:192` rate-limits speed change to −30/+9 m/s², i.e. ~3 g of braking**, which lets the follower track a spiky-but-CORRECT `vtarget`. Test stated: physical limits (≈13/≈5) must leave step counts unchanged while the cars stop surging. |
| **E80** — frame rate | `JM_FRAMEPROF` built and validated (Watkins: world 3.44 ms, hud 0.07 ms of 16.77 ms, vsync-capped 60 fps — **Watkins is not slow**). Spa: `build_gpl` is **82 s**, physics `mtkcompile` 95 s, and **725 s is unaccounted between them** (billboards/objects/horizon). ⛔ My earlier "the texture load takes 13 minutes" was WRONG — see the correction above. `JM_TEXCACHE` is default-OFF and works (1.1 GB for Spa alone; the disk cost is the PO's call). |
| **E90** — collidable barriers | Largely retracted: Monza/Watkins armco is BAKED track geometry, not props (their archives hold only `pitwall*`/`fence.3do`), and Zandvoort's 269 solids come from loose `.3do` files. Open question relocated: can the car drive THROUGH the baked armco? That needs a drive, not a census. |
| **E87** — invisible-collidable gate | Run on the PO's three tracks. Monza 2 solids / 0 undrawn, Watkins 5 / 0, **Nürburgring did not run**. ⚠️ Both passes are uninformative — a 0 verdict over a population of 2 says almost nothing. |
| **E82** — no axles in the external view | Gold reference frames extracted to `parity/e82_gold/` (Watkins nintendo video, t=20/45/70/95 s). This is the input E75 never had across 16 sprints: every prior number was fitted to our own hub line rather than to gold. |
| **E91** — "Tesla brakes" | Measured: coast at `throttle=0, brake=0` is **0.302 g at 100 km/h** vs 0.089 g from aero+rolling — the **driveline** adds 0.21 g, and at 100 km/h the car sheds 21 km/h in 2 s. `Crr` eliminated by arithmetic (0.026 g, flat). The constants responsible (`c_c`, `T_cap`, `Ie`, `k_idle`, `idle_rpm`) are **hardcoded, not `.ibt`-derived**, which under the PO's standing constraint is itself the defect. ⛔ **Blocked on the PO:** the gold `.ibt` files contain no clean coast-down (Nürburgring elevation makes one "coast" ACCELERATE; the skidpad is a continuous corner, giving 0.86 g "coasts"). Needs one straight-line coast-down recording. |

#### Cross-project

* **3 phantom `JM_*` levers** documented as working opt-ins do not exist (`JM_BRUSH`, `JM_AI_KINEMATIC`, `JM_FFB_DEAD`), and `JM_NO_SHIFTCLAMP` was stale (corrected). ma: 37 named / 0 missing; bob: 103 / 3 (2 false positives).
* **`grep` silently skips ~46 % of these trees** (ugrep treats any byte >127 as binary and says nothing). Recorded in both `CLAUDE.md` files and to memory. **A zero-result search here is not evidence of absence until repeated with `-a`.**

### E91-S1 (2026-08-29) — the engine-braking constant is still INVENTED, and the earlier split that justified it was arithmetically invalid

**Finding 1 — the knob was removed, the magic number was not.** `JuliaMotorMTK/src/components/powertrain.jl:43` holds `const ENGBRAKE = 0.012`. The comment directly above it quotes the PO's standing constraint — *"the car physics should be determined entirely by the iracing ibt data, there should be no modifiable parameters"* — and records that `JM_ENGBRAKE` was deleted for that reason. **Deleting the env var removed the KNOB but left the VALUE unsourced.** 0.012 is not derived from any `.ibt`; `tools/engbrake_probe.jl` (which the comment names as the thing that would source it) compares downshift rpm SPIKES, not the coast-down decay, so it cannot produce this number either.

**Finding 2 — the measurement that defended 0.012 subtracted baselines taken at the WRONG SPEEDS.** The note at `powertrain.jl:24-38` split the PO's coast-downs as clutch-IN 130 km/h → 1.24 m/s² and 96 km/h → 1.06, versus clutch-OUT 5th @161 km/h → 2.56 and 4th @126 km/h → 2.86, and reported the engine share as **0.7 and 1.6 m/s²**. Those subtractions pair 161 against 130, and 126 against 96. **Aero drag goes as v², so a baseline measured 20–30 % slower is not the baseline at the test speed.** Fitting the two clutch-in points to `a = A·v² + R` (exact, 2 points 2 unknowns: A = 3.04e-4, R = 0.844 m/s²) and evaluating the baseline AT EACH TEST SPEED gives engine shares **1.11 and 1.64 m/s²**, not 0.7 and 1.6.

**Finding 3 — corrected, the implied constant is 0.0137–0.0183 (mean 0.0160), so the code's 0.012 is 66–88 % of it — LOW, not high.** Solving the model's own form `T_eng = eb·rpm` ⇒ `eb = a_eng·Rw·m/(rpm·gear·final·η)`:

| gear | km/h | total | baseline @ that speed | engine | rpm | implied eb |
|---|---|---|---|---|---|---|
| 5th | 161 | 2.56 | 1.45 | **1.11** | 4872 | 0.01367 |
| 4th | 126 | 2.86 | 1.22 | **1.64** | 4537 | 0.01830 |

⚠️ **This does NOT license changing 0.012 to 0.016.** The spread is still **1.34×** across two points whose rpm differ by only 7 %, so `eb·rpm` cannot fit both even after the correction — the残 disagreement is either the model FORM or the input numbers. And the whole derivation rests on **four hand-copied numbers** and a **2-point fit** whose fitted rolling term (R = 0.844 m/s², 0.086 g) is ~4× a plausible race-car Crr, which suggests R is absorbing something that is not rolling resistance.

**Bearing on the PO's complaint:** the PO reports the car decelerating off-throttle *too hard*, like ABS. Corrected, engine braking comes out **higher** than the code models, not lower — so if these numbers hold, the excess the PO feels is **not** the engine-braking term, and lowering it (which was proposed and reverted once already) would be the wrong fix for the second time.

**NEXT (E91-S2):** stop reusing hand-copied numbers. Extract clutch-in and clutch-out zero-throttle coast-downs directly from the `.ibt` files already on disk (12+ Zandvoort/Nordschleife sessions under `data/juliaracer/`), fit `A·v² + R` over the full speed range rather than 2 points, and report `eb` with its scatter. Only then is a value change defensible under the PO's constraint.

### E91-S2 (2026-08-29) — measured from the `.ibt` directly. **My S1 conclusion was backwards: the code brakes ~3.5× TOO HARD, not too little.**

New tool `JuliaMotorMTK/tools/coastdown_probe.jl` reads the 16 `.ibt` sessions on disk, finds genuine coast segments (`throttle==0 && brake==0`), splits them by the **clutch** channel, fits the clutch-IN points to `a = A·v² + R` by least squares over the full speed range, and solves the model's own `T_eng = eb·rpm` for each clutch-OUT point.

**⚠️ FIRST PASS REFUTED ITSELF, and saying so is the point.** Accepting every `throttle=0, brake=0` sample on a ROAD COURSE let cornering, kerbs and elevation into the fit: baseline residual **5.619 m/s²**, which is LARGER than the 1–3 m/s² effect being measured, with an implausible **0.295 g** rolling term and a **3.76×** IQR spread. A fit whose residual exceeds its signal is not a measurement. Refined to use the MEASURED `LongAccel` channel (no differentiation noise) and to keep only straight-line samples (`|LatAccel| < 2`, `|steering| < 0.1 rad`, `|yaw rate| < 0.05`):

| | first pass | filtered |
|---|---|---|
| baseline residual sd | 5.619 m/s² | **0.732** |
| rolling term | 0.295 g | **0.108 g** |
| eb IQR spread | 3.76× | **1.71×** |

**RESULT (511 clutch-in points, 54–216 km/h; 87 usable clutch-out points):** implied `eb` **median 0.00341**, IQR 0.00244–0.00417. **The code's 0.012 is 352 % of the telemetry median — the model applies roughly 3.5× the engine braking the reference shows.**

⚠️ **THIS SUPERSEDES E91-S1, WHICH CONCLUDED THE OPPOSITE.** S1 derived 0.0137–0.0183 (code = 66–88 %, "too low") from **four hand-copied numbers and a 2-point fit**. Those four numbers came from lap telemetry with no straight-line filtering, i.e. from the same contaminated population that produced the 5.6 m/s² residual here. The direct measurement replaces them. **S1's "lowering eb would be wrong twice" is withdrawn** — the telemetry now points the same way as the PO's complaint of excessive off-throttle deceleration.

**STILL NOT A LICENCE TO SET eb = 0.0034.** (a) Only **87** usable clutch-out points survive the filters. (b) Per-gear medians disagree — gear 1 0.00341, gear 2 0.00229, **gear 3 0.03119**, gear 4 0.00110 — a 28× spread across gears. (c) IQR spread **1.71×** still exceeds the 1.5× consistency bar, so `eb·rpm` does not fit even filtered: **the model FORM is suspect, not just the constant.** (d) `LongAccel` includes the gravity component on a slope and Zandvoort has real elevation, which is not yet removed — a plausible source of the residual scatter.

**NEXT (E91-S3):** remove the elevation term (the `Alt` channel is present) and re-fit; investigate the gear-3 outlier; and test whether a two-term engine model (a constant pumping/friction torque plus an rpm-proportional term) collapses the per-gear spread. Only if `eb` becomes consistent across gears is a value change defensible under the PO's "physics entirely from the ibt" constraint.

### E91-S3 (2026-08-29) — slope removed, and the conclusion is NEGATIVE: **this telemetry cannot determine `ENGBRAKE`. Stop trying.**

Added the gravity term the S2 fit was missing. On a slope `m·dv/dt = -F_drag - m·g·sin θ`, so drag deceleration is `-dv/dt - g·(dAlt/dt)/v`. Uses `dv/dt` from ground speed (central difference, ±3 samples) rather than the `LongAccel` accelerometer, **because the accelerometer itself carries the gravity component being removed** — using it would have subtracted the term from a signal that already contained it.

**The baseline genuinely improved:** rolling **0.108 g → 0.0721 g** (now a plausible race-car figure), residual sd **0.732 → 0.657 m/s²**.

**But the engine estimate did not survive it:**

| | S2 (no slope term) | S3 (slope removed) |
|---|---|---|
| implied `eb` median | 0.00341 | **0.00845** |
| code 0.012 vs median | 352 % | **142 %** |
| IQR spread | 1.71× | **1.96×** |
| per-gear spread | 28× | **21×** (g3 0.03305 vs g4 0.00157) |

⭐ **THE DECIDING NUMBER IS R².** Fitting the derived engine torque against rpm:
* two-term `T = T0 + eb·rpm` → **R² = 0.064**, and `T0 = 109.5`, `eb = −0.0196` — a **NEGATIVE** rpm coefficient, i.e. less braking at higher rpm, which is physically backwards;
* one-term `T = eb·rpm` (the code's form) → **R² = −0.091**, *worse than predicting the mean*.

**rpm explains essentially none of the variance in the derived engine torque.** That is not "the model form is wrong" — it is "there is no engine signal left in this data after the subtraction". The derived quantity is dominated by residual noise from two much larger terms.

⚠️ **THEREFORE E91-S2'S HEADLINE IS WITHDRAWN AS A NUMBER.** S2 said "the code brakes 3.5× too hard". One modelling correction moved that to 1.42×. **An estimate that swings 2.5× on a single term is not a measurement**, and no value change may rest on it. What survives across S2 and S3 is only the DIRECTION — the code's `eb` sits above the telemetry-implied median in both — and even that rests on an `R² ≈ 0` fit, so it is weak support for the PO's complaint rather than a confirmation of it.

**AVENUE CLOSED, with evidence.** The `PRODUCT_BACKLOG` note at E91 originally asserted "the comparison E91 needs cannot be made from the telemetry on hand". Three sprints have now DEMONSTRATED that rather than asserted it: lap telemetry from a road course cannot separate engine braking from aero and rolling, because a coast segment long enough to fit is never straight, flat and un-steered for long enough.

**WHAT WOULD ACTUALLY SETTLE IT (PO action, ~2 minutes in iRacing):** one straight-line coast-down on a flat runway or the pit straight — get to ~200 km/h, lift fully off throttle, no brake, no steering, and let it roll down to ~60 km/h **twice**: once **in gear, clutch out** and once **clutch in**. The difference between those two curves IS engine braking, with no fitting and no subtraction of guessed terms. Save the `.ibt`. Until then `ENGBRAKE = 0.012` stays as it is: unsourced, but not replaceable by a number that is equally unsourced and merely newer.

### E91-S4 (2026-08-29) — ⭐ **THE PO IS RIGHT, MEASURED: the sim decelerates ~1.67× harder off-throttle than the iRacing reference.**

New tool `JuliaMotorMTK/tools/coast_compare.jl`. **The point is what it does NOT do.** S1–S3 tried to derive `ENGBRAKE` by subtracting aero and rolling out of a coast-down, and that failed on its own terms (derived engine torque vs rpm: R² = 0.064, and −0.091 for the code's own form). But the PO's complaint was never about a constant — *"lifting completely off the throttle decelerates the car like ABS"* is a claim about **total off-throttle deceleration**, which is directly observable in BOTH the sim and the reference. Compare those two numbers at matched speed and gear and **no decomposition is needed at all**: no aero fit, no rolling term, no slope correction, nothing to get wrong.

Reference: telemetry, clutch OUT, zero throttle, zero brake, straight-line only (`|LatAccel|<2`, `|steering|<0.1`, `|yaw|<0.05`), slope removed. Sim: `DriveRT.step_car!` coasting at the same speed and gear, clutch engaged, throttle and brake zero.

| gear | km/h | n(ref) | ref m/s² | sim m/s² | sim/ref |
|---|---|---|---|---|---|
| 1 | 90 | 58 | 1.639 | 2.832 | **1.73** |
| 2 | 90 | 31 | 0.856 | 2.087 | **2.44** |
| 2 | 126 | 61 | 1.220 | 3.030 | **2.48** |
| 3 | 90 | 22 | 1.251 | 1.565 | **1.25** |
| 3 | 126 | 108 | 1.195 | 2.315 | **1.94** |
| 3 | 171 | 254 | 2.191 | 3.414 | **1.56** |
| 4 | 90 | 31 | 1.233 | 1.304 | **1.06** |
| 4 | 126 | 86 | 1.217 | 1.958 | **1.61** |

**Median 1.67×, and every one of 8 matched bands is above 1.0.** The PO reported this after driving Monza (*"I never needed to use the brakes ever, which is not right"*) and again on 2026-08-29. **It is confirmed.** An earlier session offered the PO the explanation that they were driving too slowly to need brakes; that explanation is now positively refuted by measurement and must not be repeated.

**WHAT THIS DOES AND DOES NOT SAY.** It says the TOTAL off-throttle deceleration is ~1.67× the reference. It does **not** say which term is responsible — the excess could be engine braking, aero, rolling, or driveline losses, and S1–S3 established that this telemetry cannot apportion it. **So this is an acceptance criterion, not a fix**: any change must drive the median sim/ref ratio in this table toward 1.0, and the table is the test.

⚠️ **AND IT STILL DOES NOT LICENSE EDITING A CONSTANT.** The PO's standing constraint is that the physics come entirely from the `.ibt` with no modifiable parameters. Tuning `ENGBRAKE` (or `CdA`, or `Crr`) until this table reads 1.0 would be exactly the knob-twiddling that constraint forbids — it would fit one table rather than derive a value. The straight-line coast-down capture requested in E91-S3 (in gear and clutch-in, ~200→60 km/h) remains what is needed, and now has a **quantified target**: it must explain a 1.67× excess.

**REGRESSION USE:** re-run `coast_compare.jl` after any physics change. The ratio column is the gate.

### E80-S1 (2026-08-29) — the 725 s was unattributed because **2,364 consecutive lines carried no timestamp**

E80's standing finding is that `build_gpl` accounts for only **82 s** of a ~13-minute Spa load and **725 s is unaccounted**. The reason it stayed unaccounted is now plain: `JM_TIMING` stamps `texture load begins` (:1596), `texture INDEX built` (:1598) and `build_gpl done (GL uploads)` (:1603) — and then **the next stamp is `physics build begins` at :3967**. Everything in between ran untimed.

⚠️ **That is also how the original E80 claim went wrong.** An earlier session read *"loading textures…"* being the LAST PRINTED line as evidence that texture loading was where the time went. It was only evidence of where the last `print` was. **A phase boundary is not a measurement, and the absence of later output says nothing about what is running.**

**ADDED — 9 timestamps across the gap**, at the phase boundaries the code itself already marks with `const`/`println`:

| stamp | what it bounds |
|---|---|
| `track categories / crowd tint begins` | :1612 |
| `horizon ring begins` | :1636 |
| `trackside objects + billboards + trees begin` | :1876 |
| `trackside objects/billboards/trees DONE` | :3068 ← **the ~1,200-line prime suspect** |
| `mirrors + wheels begin` | :3101 |
| `wheel models loaded` | :3199 |
| `track items counted` | :3417 |
| `AI car models begin` | :3449 |
| `AI car models done / projection` | :3459 |

Syntax verified with `Meta.parseall` before running — inserting statements between top-level `const`s risks landing inside a multi-line expression, and a parse error would have looked like a load failure.

**Status: a timed Watkins load is running.** Watkins first because it is the cheap track; **Spa is where the 725 s was measured**, so the attribution run that actually settles E80 is Spa, and Watkins only proves the stamps fire. No conclusion is drawn until the numbers exist.

#### E80-S1 result (Watkins Glen, first attribution) — and a syntax check that lied

**The untimed region IS dominated by one block.** Timed Watkins load:

| t+ | phase |
|---|---|
| 18.6 s | track parse begins |
| 24.3 s | geometry extraction begins |
| 31.8 s | texture load begins |
| 34.6 s | `build_gpl` done (GL uploads) — **texture upload is 2.8 s here** |
| 34.6 s | track categories / crowd tint |
| 34.6 s | horizon ring |
| 38.4 s | **trackside objects + billboards + trees BEGIN** |
| 74.5 s | **… DONE — 36.1 s, the dominant cost** |
| 76.2 s | mirrors + wheels begin |
| 77.6 s | wheel models loaded |

So of ~43 s previously invisible after `build_gpl`, **36.1 s is the trackside objects/billboards/trees block** — the ~1,200-line stretch flagged as prime suspect. That is consistent with the earlier note that the Spa time is "unaccounted in billboards/objects", but it is now MEASURED at one track rather than supposed.

⚠️ **This is Watkins, not Spa. E80's 725 s was measured at SPA and is NOT yet attributed.** Watkins' whole load is ~78 s. Nothing here licenses a claim about the 13-minute Spa case; it only shows the instrument works and names the block to watch. Spa is the run that settles it.

⚠️ **MY SYNTAX CHECK WAS A FALSE NEGATIVE, and this is the reusable lesson.** I verified the 9 inserted timestamps with `Meta.parseall` and it printed **PARSE OK** — then the run died with `ParseError @ :3417`. **`Meta.parseall` does not throw on a syntax error: it returns an `Expr(:error, …)` node inside the toplevel expression, so calling it and not inspecting the result proves nothing.** One stamp had landed INSIDE a multi-line `println(...)` spanning three lines, because the insertion point was chosen from the statement's FIRST line. Now checked by walking the parse tree for `:error`/`:incomplete` nodes, which reports `PARSE CLEAN (0 error nodes)`. **A checker that cannot fail is not a check** — the same shape as this project's recurring instrument problem, in a new place.

#### E80-S2 — PREDICTION STATED BEFORE THE SPA RUN COMPLETED

Recorded in advance so the result can refute it, per the standing rule that a parity/attribution run must state its numbers first.

**Anchors:**

| | HAT triangles | grid | tris/cell | objects | objects-block time |
|---|---|---|---|---|---|
| Watkins Glen | 15,662 | 67×53 = 3,551 | 4.41 | 163 objects + 39 billboards + 110 solid | **36.1 s** |
| Spa | 92,548 | 202×251 = 50,702 | **1.83** | ? | ? |

**Mechanism:** the trackside block issues several `JuliaMotor.hat(TRKSURF, x, y)` terrain queries PER OBJECT INSTANCE (`drive_native_mtk.jl` :2200, :2219, :2235, :2277, :2358). So its cost ≈ objects × queries-per-object × per-query cost.

**Per-query cost should NOT be worse at Spa.** Spa's HAT grid is *finer* relative to its triangle count (1.83 tris/cell vs Watkins' 4.41), so a bucketed lookup does less work per call, not more. **The driver is therefore object COUNT, not terrain size.**

**PREDICTIONS:**
1. The `trackside objects/billboards/trees` block is the **largest single phase** in Spa's post-`build_gpl` region.
2. If per-object cost is constant, block time ≈ `36.1 s × (Spa objects / 202)`. For the block alone to account for the recorded **725 s** gap, Spa would need roughly **4,050 object instances** — about **20×** Watkins.
3. Texture upload (`build_gpl`) stays SMALL — it was 2.8 s at Watkins, and the original "texture load takes 13 minutes" claim is already known to be a misreading of which line printed last.

**Refutation conditions, stated now:** if Spa's object count is far below ~4,000 yet the gap is still ~725 s, per-object cost is NOT constant and the mechanism above is wrong — look for something super-linear in object count, or a phase outside this block. If the block is a minor share of the gap, the prediction fails outright and the remaining phases (mirrors/wheels, track items, AI car models) must be examined instead.

#### E80-S2 RESULT — **the 725 s is the trackside-objects block. Prediction confirmed, with one caveat I got wrong.**

Spa, `JM_TIMING=1`, full load **1122.8 s** (18.7 min):

| t+ | phase | duration |
|---|---|---|
| 34.6 s | texture load begins | |
| 115.4 s | `build_gpl` done (GL uploads) | **80.8 s** |
| 123.5 s | trackside objects + billboards + trees BEGIN | |
| 986.4 s | … DONE | ⭐ **862.9 s** |
| 989.5 s | mirrors + wheels loaded | 3.1 s |
| 994.4 s | track items + AI car models | 4.9 s |
| 1027.6 s | physics build begins | |
| 1122.8 s | physics build done | 95.2 s |

**Prediction 1 — CONFIRMED.** The trackside block is by far the largest phase: **862.9 s of 1122.8 s (77 %)**. Every other post-`build_gpl` phase together is **8 s**.

**Prediction 2 — MECHANISM CONFIRMED, MAGNITUDE SLIGHTLY UNDER.** Spa carries **1455 objects + 2433 billboards = 3888 instances** against Watkins' 202 — a ratio of **19.2×**, and I predicted ~4,050 would be needed. Constant per-object cost predicts `36.1 s × 19.25 = 694.9 s`; the measured **862.9 s is 1.24× that**. **So object count is indeed the driver, but the cost is mildly SUPER-LINEAR** — my "constant per-object cost" assumption was not quite right, and the residual 24 % is unexplained. Candidates: the HAT queries are bucketed by grid cell and Spa's objects may cluster (a per-cell list scan is not O(1) when a cell is dense), or billboards cost more than objects and Spa's mix is billboard-heavy (63 % vs Watkins' 19 %).

**Prediction 3 — CONFIRMED, and it finally kills the original claim with a number.** Texture upload at Spa is **80.8 s**, 7 % of the load — not 13 minutes. E80 began as *"texture load takes 13 minutes"*, which was an earlier session reading `loading textures…` as the LAST PRINTED LINE and inferring where the time went. **The whole 13 minutes was, to 77 %, one untimed block 2,000 lines further down.**

**E80's original question is now ANSWERED.** What remains is a different, better-posed one: why the trackside block costs ~0.22 s per instance, and whether the mildly super-linear term is HAT-cell clustering or a billboard/object cost difference — measurable by splitting the block's timer between the object loop and the billboard loop.

### E80-S3 (2026-08-29) — split the 862.9 s block into its three sub-phases

E80's original question is answered (the 725 s is the trackside block, 77 % of a Spa load). The remaining one is sharper: **the block costs ~0.22 s per instance and is mildly SUPER-linear** — Spa's 3888 instances against Watkins' 202 is 19.2×, but the time ratio is 862.9/36.1 = **23.9×**, i.e. **1.24× more than constant per-instance cost predicts**. Two candidate explanations were recorded and neither has been tested:
* **HAT-cell clustering** — the terrain queries are bucketed by grid cell, and a dense cell degrades a per-cell scan;
* **billboards costing more than objects** — Spa's mix is **63 % billboards** (2433 of 3888) against Watkins' **19 %** (39 of 202), so a billboard/object cost difference alone could produce a super-linear-looking ratio **with no non-linearity at all**.

**That second possibility matters: the "super-linear" term may be a MIX artefact rather than a scaling law.** Distinguishing them needs the block split by sub-phase, which is what this sprint adds:

| stamp | bounds |
|---|---|
| `object mesh placement done; OBJECTS build begins` | :2536 — everything before the `OBJECTS` comprehension |
| `OBJECTS built; billboard/tree loop begins` | :2634 |
| `billboard/tree loop done` | :2715 — the `for i in insts` billboard/tree loop |

With per-sub-phase times at both tracks, per-object and per-billboard costs are separable, and the mix hypothesis is testable arithmetically: if Watkins' per-billboard cost × 2433 + per-object cost × 1455 reproduces Spa's 862.9 s, **the mix explains it and there is no non-linearity to chase.**

⚠️ **Insertion verified with the ERROR-NODE walk, not `Meta.parseall` alone** — E80-S1 inserted a stamp inside a three-line `println` and `Meta.parseall` still printed "PARSE OK", because it returns `Expr(:error, …)` rather than throwing. Reports `PARSE CLEAN (0 error nodes)`.

Watkins run in flight (cheap track first); Spa is the comparison that settles the mix question.

#### E80-S3 RESULT — **the mix hypothesis is REFUTED. The cost is one phase: object mesh PLACEMENT.**

Watkins, sub-phase split (163 objects + 39 billboards + 110 solid):

| sub-phase | duration | share of block |
|---|---|---|
| **object mesh placement** (everything before the `OBJECTS` comprehension) | **34.6 s** | **94 %** |
| `OBJECTS` comprehension | 1.8 s | 5 % |
| **billboard / tree loop** | **0.1 s** | 0.3 % |

**39 billboards cost 0.1 s — ~2.6 ms each.** Scaled to Spa's 2433 billboards that is **~6 s of its 862.9 s**. **So the billboard/object MIX explains nothing, and E80-S2's suggestion that the super-linear term might be a mix artefact is WITHDRAWN.**

**Where the time actually goes:** the placement phase walks `insts` — ALL instances, objects and billboards and crowd rows alike — issuing the `hat()` terrain queries. So its cost scales with TOTAL instances, not with the object/billboard split:

| | instances | placement-dominated block | per instance |
|---|---|---|---|
| Watkins | 202 | 36.7 s | 0.18 s |
| Spa | 3888 | 862.9 s | 0.22 s |

Linear on total instances predicts `36.7 × (3888/202) = 706 s` against a measured **862.9 s** — **1.22×**. **The mild super-linearity is real and survives the mix being ruled out**, so the remaining candidate is the one originally paired with it: HAT-cell behaviour when a cell is dense (Spa's grid is finer per triangle, but its OBJECTS may cluster near the circuit).

**E80 is now well-posed for the first time:** one phase, one mechanism, ~0.2 s per instance, and a 1.22× residual. That is a different item from the one that began as "texture load takes 13 minutes".

### E80-S4 (2026-08-29) — Spa with the split. **Prediction stated before the run, again.**

From Watkins: placement **34.6 s / 202 instances = 0.1713 s per instance**.

**PREDICTIONS for the Spa split (3888 instances):**

| sub-phase | predicted | basis |
|---|---|---|
| object mesh **placement** | **~855 s** (>95 % of the block) | the block measured 862.9 s and the other two sub-phases are small |
| `OBJECTS` comprehension | 2–15 s | 1.8 s at Watkins, scaled by object count |
| billboard / tree loop | **~6 s** | 2433 × the 2.6 ms/billboard measured at Watkins |

**And the number that matters:** constant per-instance cost predicts `0.1713 × 3888 = 666 s`; the block measured **862.9 s**, i.e. **0.2219 s per instance = 1.30× Watkins**.

**WHAT EACH OUTCOME WOULD MEAN — written down before seeing it:**
* **Placement ≈855 s and per-instance ≈1.3× Watkins** → the excess is inside placement, where the `hat()` queries are. Since the query COUNT per instance is fixed by the code, a 1.3× per-instance cost means a 1.3× per-QUERY cost, which is what HAT-cell density predicts (Spa's objects cluster along a 14.1 km circuit; Watkins' along 4.2 km). **HAT density becomes the standing explanation.**
* **Billboard loop ≫6 s** → the Watkins per-billboard figure does not generalise and the mix question reopens, despite being refuted at Watkins.
* **Placement ≈666 s with the extra ~200 s elsewhere** → the super-linearity is NOT in placement at all and both current explanations are wrong.

⚠️ **This is E80's 4th sprint, so the item rotates after it regardless of outcome.** The original question — *where do the 725 s go* — is already answered (77 % in one previously untimed block). What remains is a follow-up worth its own item rather than more sprints under a title that no longer describes it.

#### E80-S4 RESULT — placement confirmed at 99.7 %; **HAT density is the standing explanation. One prediction was 20× wrong.**

Spa split (3888 instances), against the predictions committed before the run:

| sub-phase | predicted | **measured** | |
|---|---|---|---|
| object mesh **placement** | ~855 s, >95 % | **891.4 s, 99.7 %** | ✓ |
| `OBJECTS` comprehension | 2–15 s | 1.9 s | just under |
| billboard / tree loop | ~6 s | **0.3 s** | ✗ **20× too high** |

**Placement per instance: Watkins 0.1713 s → Spa 891.4/3888 = 0.2293 s = 1.34×.** That is the outcome recorded in advance as *"the excess is inside placement, where the `hat()` queries are… HAT density becomes the standing explanation"*. The query COUNT per instance is fixed by the code, so a 1.34× per-instance cost is a 1.34× per-QUERY cost — consistent with Spa's objects clustering along a 14.1 km circuit against Watkins' 4.2 km.

⚠️ **THE BILLBOARD PREDICTION WAS BADLY WRONG AND THE REASON MATTERS.** I extrapolated 2433 × 2.6 ms/billboard from Watkins (39 billboards in 0.1 s) and predicted ~6 s; the measured cost is **0.3 s — 0.12 ms each, 20× cheaper**. **Watkins' 0.1 s was dominated by fixed loop overhead, not per-billboard work**, so dividing it by 39 measured mostly the overhead. **A per-unit cost derived from a small sample can be almost entirely constant term** — the same shape as reading a rate off two points in E91-S1. The conclusion it fed (billboards are negligible) survives and is now stronger, but the number was fabricated by division.

**E80 CLOSES HERE** (4 sprints used). Its original question — *where do the 725 s go* — is answered: **99.7 % of one previously untimed block, which is 80 % of the whole load**, and texture upload, the original suspect, is 80.8 s of 1122.8 s. <br>**Successor item, to be opened fresh:** *object mesh placement costs ~0.23 s per instance and scales 1.34× super-linearly with instance count; is that HAT-cell density?* Test: instrument `hat()` with a call counter and total time inside placement, and compare per-query cost between the two tracks directly instead of inferring it from a division.

### E92 (opened 2026-08-29, successor to E80) — why does object mesh placement cost ~0.23 s per instance, and scale 1.34× super-linearly?

E80 closed with its question answered: the 725 s is **99.7 % object mesh placement**, one block that had carried no timestamps. What it could not answer is why that block costs what it does. E80-S4 named **HAT-cell density** as the standing explanation. **This item exists partly to check that, and the structures already argue against it.**

⚠️ **THE DENSITY HYPOTHESIS LOOKS WRONG BEFORE A SINGLE MEASUREMENT.** `hat()` (`JuliaMotor/src/hat.jl:139`) scans a **3×3 bucket neighbourhood**, so its cost tracks SEGMENTS PER CELL:

| | segments | grid | segments/cell | TriangleHAT tris/cell |
|---|---|---|---|---|
| Watkins | 450 | 49×37 = 1,813 | **0.248** | 4.41 |
| Spa | 1,180 | 152×190 = 28,880 | **0.041** | 1.83 |

**Spa is 6× SPARSER per cell on the TrackSurface and 2.4× sparser on the TriangleHAT.** Density predicts Spa should be FASTER per query — yet placement is **1.34× SLOWER per instance** there. So either the cost is not in `hat()` at all, or it is not density-driven.

**S1 — INSTRUMENT BUILT (`JM_HAT_COUNT=1`, `JM_HAT_TIME=1`).** `hat()` now counts calls and, separately, accumulates nanoseconds; `JuliaMotor.hat_stats()` reports calls, total time and µs/call. The counters are **armed and reset around the placement block only**, so the figure is per-phase and not contaminated by the render loop. Timing is a separate flag because `time_ns()` per call is itself overhead.

⭐ **THE POINT IS TO STOP DIVIDING.** E80-S4's per-billboard cost was obtained by dividing a phase time by a count, and came out **20× wrong** because the phase was almost all fixed overhead. Per-query cost derived the same way would be no better. **Measure the calls; do not infer them.**

**Discriminators, stated before the run:**
* **calls/instance similar at both tracks, µs/call ~1.34× higher at Spa** → cost IS in `hat()` and something other than cell density drives it (cache behaviour on a 28,880-cell grid, allocation, or bucket-list layout).
* **µs/call similar, calls/instance ~1.34× higher at Spa** → the extra work is more QUERIES per object, not slower ones — look at retry/fallback loops in the placement filters.
* **`hat()` accounts for a small share of the 891 s either way** → the cost is not in `hat()` at all, and the standing explanation is simply wrong; look at the per-instance filters (`drop`, `onroad_crowd`, `perp_crowd`, `onroad_bldg`, `onroad_fp`), any of which scanning other instances would make the block quadratic.

#### E92-S1 RESULT — **HAT-cell density is REFUTED by four orders of magnitude. `hat()` is not the cost.**

Watkins, counters armed around the placement block only:

```
[hat] 2127 calls in the placement block  total 0.0 s  0.39 us/call
```

* placement block: **30.7 s** (t+39.5 → t+70.2)
* `hat()` total: 2127 × 0.39 µs = **0.83 ms**
* **`hat()` is 0.003 % of the phase it was supposed to explain.**

**This is the third discriminator, stated before the run:** *"`hat()` accounts for a small share of the phase either way → the cost is not in `hat()` at all, and the standing explanation is simply wrong."* **E80-S4's "HAT density is the standing explanation" is WITHDRAWN**, and it was already suspect on structure (Spa is 6× SPARSER per cell, so density predicted the wrong sign).

⭐ **HOW THE WRONG ANSWER SURVIVED TWO SPRINTS:** it was produced by DIVIDING a phase time by an instance count and attributing the quotient to the most visible thing in the phase. That is the identical error that made the per-billboard estimate **20× too high** in E80-S4 — and I repeated it on the very next question. **A per-unit cost obtained by division is a hypothesis about where the time went, not a measurement of it.** Counting the calls took one sprint and settled it immediately.

**WHERE THE TIME ACTUALLY IS — next question, not yet answered.** The phase is named "object mesh placement" and `hat()` is exonerated, so the remaining work in it is **loading and parsing the object meshes themselves** (`objmesh[i.name]`, read out of the track's `.dat`). Spa's `spa67.dat` is **785.7 MB** against Watkins' far smaller pack, and Spa instantiates 1455 objects to Watkins' 163. **That also offers a natural explanation for the 1.34× "super-linearity" with no non-linearity at all:** distinct MESHES, not instances, drive the loading cost, and the two tracks need not share the same instance-to-distinct-mesh ratio. <br>**E92-S2:** count DISTINCT meshes loaded and time the load, exactly as this sprint counted `hat()` — measure it, do not divide for it.

### E92-S2 (2026-08-29) — measure distinct-mesh loading, the work `hat()`'s exoneration leaves behind

`hat()` is 0.003 % of the placement phase, so the phase's cost is elsewhere. What remains in the loop at `drive_native_mtk.jl:1948-2031` is **loading each DISTINCT object mesh once** (deduped at :1949): `Render.extract_gpl_car(path)` reads and parses the `.3do` out of the track pack, then `Render.build_gpl(parts, TEXIDX)` builds it.

**INSTRUMENTED (`JM_MESH_TIME=1`):** distinct meshes actually processed, seconds in `extract_gpl_car`, seconds in `build_gpl`, reported after the loop. `Ref` accumulators rather than plain locals, so the loop body mutates them regardless of Julia's soft-scope rules — a plain local would have silently produced zeros at top level.

⭐ **THE PREDICTION IS THAT THERE IS NO SUPER-LINEARITY AT ALL.** The dedup guard means cost tracks **distinct meshes, not instances**. E80/E92 have been dividing phase time by INSTANCE count (202 vs 3888, a 19.2× ratio) and calling the leftover 1.34× "super-linear". **If Spa's distinct-mesh count is ~1.34× further above Watkins' than its instance count is, the entire effect disappears and the scaling is linear in the quantity that actually drives it.** That would make "super-linear" an artefact of dividing by the wrong denominator — the third time in this epic that a per-unit figure obtained by division has misled (per-billboard 20× wrong, HAT density wrong by 10⁴).

**Discriminators, before the run:** <br>• `extract + build ≈ the whole placement phase` → mesh loading IS the cost, and the next question is only which half; <br>• `extract + build ≪ the phase` → the cost is in neither `hat()` nor mesh loading, and the per-instance FILTERS (`drop`, `onroad_crowd`, `perp_crowd`, `onroad_bldg`, `onroad_fp`) are the last candidate — any of them scanning other instances would make the block genuinely quadratic; <br>• distinct-mesh ratio ≈ instance ratio × 1.34 → the super-linearity was a denominator artefact and E80's 1.34× should be retracted outright.

#### E92-S2 RESULT — mesh loading is **half** the phase, and inside it **`build_gpl` is 218× the file cost**. My ".dat size" reasoning was wrong.

Watkins:

```
[mesh] 102 distinct meshes loaded   extract 0.07 s   build_gpl 15.28 s   total 15.35 s
```

placement phase = 36.5 → 68.7 = **32.2 s**

| | | share |
|---|---|---|
| `extract_gpl_car` (read + parse the `.3do`) | **0.07 s** | 0.2 % |
| `build_gpl` (build the mesh) | **15.28 s** | **47 %** |
| **still unaccounted** | **~16.9 s** | **52 %** |

⚠️ **FILE I/O IS NOT THE COST — 0.07 s for all 102 meshes.** E92-S1 closed by pointing at Spa's **785.7 MB** `spa67.dat` as the natural explanation. **That reasoning is withdrawn:** reading and parsing the meshes is 0.2 % of the phase, and pack size cannot matter at that scale. **That is the fourth guess in this epic to die on contact with a counter** (per-billboard 20× wrong, HAT density 10⁴ wrong, "super-linear" possibly a denominator artefact, and now pack size). The pattern is consistent: every one was a plausible story about where time goes, and every one was cheaper to measure than to argue.

**What IS established:** `build_gpl` costs **15.28 s / 102 meshes = 150 ms per distinct mesh**, and it scales with DISTINCT MESHES, not instances — the loop dedups at `:1949`. Watkins: 202 instances → 102 distinct (0.505 meshes/instance).

**The scaling test is now a single number: Spa's distinct-mesh count.** If Spa's meshes-per-instance ratio is HIGHER than 0.505, the "1.34× super-linearity" is explained with no non-linearity at all; if it is LOWER, Spa should be CHEAPER per instance and the effect is genuinely somewhere else.

**And ~52 % of the phase is still unattributed** — not `hat()` (0.003 %), not file I/O (0.2 %), not `build_gpl` (47 %). The remaining candidates are the per-instance loops AFTER the mesh loop: HAT snapping, the `lverts` footprint decimation, and the `ALIGNED` passes. **E92-S3: bracket those, and get Spa's distinct-mesh count in the same run.**

### E92-S3 (2026-08-29) — bracket the unaccounted 52 %, and a prediction Spa can refute in one number

⭐ **MEASURED (2026-08-30) — THE PREDICTION IS REFUTED, by 7.7×.**

    [mesh] 491 distinct meshes loaded   extract 0.89 s   build_gpl 627.76 s   total 628.65 s

**Predicted ~3,785 distinct meshes; Spa has 491.** Wrong by a factor of 7.7, and wrong in the same
way four earlier E80/E92 predictions were: a per-unit figure inferred by dividing a phase time by a
count I had not measured. The number was committed before the run precisely so it could do this.

**But the timing split is the real result, and it is decisive:**

| | time | share |
|---|---|---|
| `extract_gpl_car` | 0.89 s | **0.14 %** |
| `build_gpl` | **627.76 s** | **99.86 %** |

**`build_gpl` costs 1.28 s per distinct mesh** and accounts for essentially the entire distinct-mesh
loop — 10½ minutes of Spa's load, for 491 meshes. Extraction, the other half of the pair and the
obvious suspect for a file-parsing cost, is 0.0018 s per mesh: **700× cheaper**, and utterly
irrelevant.

This also settles the "~52 % unattributed" question the item was raised for: the unattributed time
was never spread across the per-instance loops, it is concentrated in one function. Anything that
wants to make Spa load faster has exactly one place to look, and a 1.28 s per-mesh GL build is a
very large number to explain.

**E92-S4 (2026-08-30) — the per-mesh texture cache is NOT the cost. Hypothesis refuted by counting.**
`build_gpl` creates its `cache` Dict fresh on every call, so a texture shared by N meshes looked like
it would be uploaded N times — an obvious candidate for 1.28 s per mesh. Counted instead of assumed:

    uploads=600  lookups=601  distinct names=558  redundant=42     (7% redundant)
    uploads=900  lookups=901  distinct names=743  redundant=157    (17% later, as sharing grows)

Uploads track distinct names closely. **The per-mesh cache is doing almost no harm**, and removing it
in favour of a global one would recover a fraction, not the bulk.

✅ **E92-S6 (2026-08-30) — GLOBAL TEXTURE CACHE SHIPPED. Spa's mesh loop: 627.76 s → 446.73 s.**
The cache was a local `Dict` created fresh on every `build_gpl` call. A GL texture id is valid for the
whole context and nothing here ever deletes one, so a texture decoded for one mesh is directly
reusable by every later mesh — hoisting the Dict to module scope is the entire fix.

    before   uploads=900   distinct=743   redundant=157      build_gpl 627.76 s
    after    uploads=900   distinct=900   redundant=0        build_gpl 446.73 s

**Redundant decodes eliminated entirely, and the saving is 181 s — nearly double the ~98 s I
predicted.** The estimate was low because redundancy keeps climbing after the 1500-upload sample it
was based on; extrapolating from a mid-load reading understated the total, in the same direction as
E92-S4's error and for the same reason.

Spa still loads all 1455 trackside objects / 2433 billboards / 1265 solids, no errors, smoke suite 5/5.

⚠️ Sharing texture ids across meshes is only safe while nothing deletes a GL texture. Nothing does
today; if per-mesh texture disposal is ever added, this cache must own the lifetime.

**Remaining:** ~245 s of first-time decode at ~270 ms per texture — genuinely new work, so the next
lever is making the decode itself cheaper (disk cache of the decoded RGBA, or threading it) rather
than avoiding repeats.

**E92-S5 (2026-08-30) — the cost is the DECODE, and the per-mesh cache matters more than S4 said.**
Timed `tex_rgba` (CPU decode) separately from `upload_rgba` (the GL call):

| sample | redundant uploads | decode | GL upload |
|---|---|---|---|
| 600 | 42 (7%) | 125.67 s (209.5 ms ea) | 2.04 s (3.4 ms ea) |
| 900 | 157 (17%) | 218.27 s | 2.72 s |
| **1500** | **402 (27%)** | **368.14 s (245.4 ms ea)** | **4.11 s (2.7 ms ea)** |

**The decode is ~90× the GL upload per texture** (245 ms vs 2.7 ms). `glTexImage2D` is not the
problem and never was; the cost is CPU-side — finding the `.mip`, unpacking it, expanding to RGBA.
That makes it *cacheable to disk* and *parallelisable*, neither of which is true of a driver-side
upload cost, so the fix direction is completely different from what a slow GL call would have needed.

⚠️ **AND THIS CORRECTS E92-S4.** That sprint sampled at 600 uploads, saw 7% redundancy, and concluded
the per-mesh cache "does almost no harm". **Redundancy GROWS with load progress** — 7% → 17% → 27% —
because later meshes increasingly reuse textures earlier ones already decoded. At 1500 uploads, 402
redundant decodes at ~245 ms each is **roughly 98 seconds of pure waste**. A global texture cache is
therefore worth about 98 s of Spa's load, not the "fraction" S4 claimed. It is still not the whole
story — the other ~270 s of decode is genuinely first-time work — but it is no longer negligible.
**Sampling early and generalising is what made S4 wrong**, and the same mistake would have been
invisible if the counter had only printed once.

**What the same numbers DO say:** ~600–900 texture uploads against 627.76 s of `build_gpl` is
**roughly one second per texture upload** — and that, not mesh count and not redundancy, is where
Spa's ten-minute load lives. The next question is the split inside a single upload: `tex_rgba`
(decode) versus `upload_rgba` (the GL call). They have completely different fixes — a slow decode is
CPU work that could be cached to disk or parallelised, while a slow `glTexImage2D` points at format
conversion or mipmap generation on the driver side.

⚠️ Spa's load exceeds 900 s to reach this point, so a capped run never gets here — the first attempt
at this measurement timed out before the loop and produced nothing.


**Added** a `distinct-mesh LOOP done` stamp so the placement phase splits cleanly into **mesh loop** and **post-mesh per-instance work** (HAT snapping, `lverts` footprint decimation, the `ALIGNED` passes). Verified with the error-node parse walk.

**Watkins, measured:**

| | |
|---|---|
| instances / distinct meshes | 202 / 102 = **0.505 meshes per instance** |
| `build_gpl` | 15.28 s / 102 = **150 ms per mesh** |
| post-mesh remainder | 16.9 s / 202 = **83.4 ms per instance** |

**PREDICTION for Spa (3888 instances, 891.4 s phase), stated before the run.** If both per-unit costs hold:

* post-mesh work at 83.4 ms/instance → **324 s**
* leaving **567 s** for `build_gpl` → **~3785 distinct meshes**, i.e. **0.974 meshes per instance**

⚠️ **That number is the test, and it is a demanding one.** Watkins reuses meshes heavily (0.505 — roughly every mesh placed twice). For the arithmetic to close, **Spa would have to reuse almost nothing** (0.974 — nearly every object a unique mesh). **That is a strong claim and it may well be false.** If Spa's distinct-mesh count comes back near Watkins' ratio (~1960 meshes), `build_gpl` supplies only ~294 s and **~600 s is unexplained by either term** — meaning the post-mesh work is NOT linear per instance and is the real story.

**So the outcomes are:** <br>• **~3785 meshes** → everything is linear in the right denominators, and E80's "1.34× super-linear" was a denominator artefact all along — retract it. <br>• **~1960 meshes** → post-mesh per-instance work is super-linear and is where the remaining ~600 s lives; the mesh loop is a side-show. <br>• anything else → both per-unit costs are track-dependent and neither generalises.

**This is the fifth prediction in this epic to be written down before its run.** The four before it (per-billboard cost, HAT density, `.dat` size, and "the briefing was never reached" over in BoB) were all wrong, and each was cheaper to refute than to defend because the number was committed first.

### E93 (PO 2026-08-29) — "starting from stationary in 1st, the clutch is reversed"

PO: *"The slider has to be DOWN to start; slider UP prevents the car from moving. As soon as the car moves in first, the slider sense reverses."* Also: *"I can only shift with the slider at the bottom."*

⚠️ **NOT FIXED, and deliberately so. Every mapping I can check says the sense is CONSTANT:**

| | slider UP | slider DOWN |
|---|---|---|
| derived `clu` | ~0 | ~1 |
| `s_clu()` (drive_rt3d.jl:148) | **ENGAGED** | **DISENGAGED** |
| shift gate (`clu >= 0.4`) | blocked | **allowed** |
| `.ibt` export (`1-clu`) | records **1.0** | records 0.0 |

The shift observation **confirms** rather than contradicts this: shifting requires the clutch disengaged, which is the bottom. And the PO's own E91 run A recorded `Clutch=1.0` throughout a slider-up coast, with a dip to 0.0 exactly at the 4→5 shift — both consistent with the table above.

**So the standstill behaviour is what a manual clutch DOES:** disengaged (down) to let the engine spin up, then released (up) to take up drive. What reads as "the sense reverses once moving" is the same convention with a different requirement at each stage.

✅ **RESOLVED (2026-08-30) — the physics is exonerated; the anomaly was the axis MAPPING, not the engine.**
Measured headlessly on the real solver, standstill in 1st, full throttle, 4 s:

| clutch | v after 4 s | distance | rpm |
|---|---|---|---|
| 0.0 (engaged) | 10.70 m/s | 23.7 m | 2911 |
| 0.5 (slipping) | 15.60 m/s | 32.8 m | 4501 |
| 1.0 (disengaged) | **0.0** | **0.0 m** | **9700** |

**The car DOES pull away with the clutch engaged**, so the concern recorded below — "it should pull away
with the clutch engaged … that it does not is unaccounted for" — is refuted: no stall model is missing and
no idle governor is needed. Clutch fully OUT gives precisely the PO's own description of the *correct* case,
*"applying throttle with slider down just revs the engine, as it should"* — 9700 rpm, zero motion. A slipping
clutch launching hardest (0.5 beats both extremes) is also right.

So *"slider-UP at a standstill prevents motion entirely"* means slider-UP was mapping to clutch = 1.0 at that
moment, which is the reversed-sense bug E93 fixed — not a defect in the drivetrain model. Nothing further is
owed here.

~~⚠️ **BUT I COULD NOT REPRODUCE THE PO'S EXACT REPORT BY READING, AND I AM NOT CLOSING IT ON THAT BASIS.**~~ Specifically unexplained: *why slider-UP at a standstill prevents motion entirely.* There is **no stall model and no idle governor**, and `engine_torque` has a `Tmin_frac = 0.2` floor — so at 0 rpm and full throttle the engine still makes ~82 N·m, which through 1st (2.23 × 4.11 × 0.9 / 0.33 m) is ~2 kN on a 617 kg car. **It should pull away with the clutch engaged.** That it does not is unaccounted for.

**Deliberately NOT "fixed" by inverting the axis.** The mapping is consistent across four independent places, and inverting it would (a) contradict the shift gate, and (b) silently invalidate the E91 coast-down captures, whose whole value is knowing which side of the clutch each run was on.

**ADDED: `JM_TRACE_CLUTCH=1`** prints the derived `clu` on every material change (module-level `Ref`, not a `CTL` field — `CTL`'s fields are fixed and assigning a new one throws). **A single standstill launch with it on answers the question from data.**

**PO, the one observation that would settle it:** with `JM_TRACE_CLUTCH=1`, at a standstill in 1st, put the slider UP and apply full throttle. If the trace prints `clu=0.0` and the car still will not move, the defect is in the LAUNCH physics, not the axis sense — and that is a different and more interesting bug than a reversed slider.

#### E93 ROOT CAUSE (2026-08-29) — **a LAUNCH ASSIST discards the driver's clutch until 12 km/h**

`drive_native_mtk.jl:4663-4667`:

```julia
race_go[] && cs.v > 12.0 && (launch_done[] = true)
if race_go[] && !rst && !CTL.auto && !launch_done[] && inp.throttle > 0.05
    inp = DriveInput(..., clutch=0.0, ..., autoshift=true)
end
```

In MANUAL, **any throttle before the car reaches 12 km/h replaces the driver's clutch with `0.0` (engaged) and forces `autoshift=true`.** `launch_done[]` then latches for the rest of the session.

**That accounts for the PO's report in all three parts, with nothing left over:**
* *"at the start, applying throttle with slider down moves the car"* → the override replaces the disengaged clutch with an engaged one;
* *"after that, slider down means engine disconnected"* → the latch fires at 12 km/h and the override stops;
* *"if I come to a stop, applying throttle with slider down just revs the engine, as it should"* → the latch never resets, so the assist never returns.

**Nothing is reversed.** The axis sense is constant (verified in four places); it is simply **ignored during the first launch**. The PO's phrase *"as soon as the car moves in first, the slider sense reverses"* is precisely the 12 km/h latch.

⚠️ **This directly contradicts the PO's standing instruction**, recorded in this same file at :3560 — *"I like the clutch attached to a slider — that way I can ride the clutch. The clutch should be an axis."* A launch assist that overrides the axis for the one manoeuvre where riding the clutch matters most **removes the feature at exactly the moment it is wanted**. The comment above the block shows it was added for AI race starts on uphill grids (Spa/Nürburgring bogging), which is a real problem — but it is applied unconditionally in MANUAL rather than only where it was needed.

**SEPARATE, STILL UNEXPLAINED:** with the clutch ENGAGED at a standstill and throttle applied, **rpm reads 0.0 across all 56 such ticks and the car never moves** (against 118/213 moving when disengaged). `vehicle_3d.jl:56` declares `k_idle=0.5, idle_rpm=2000.0`, so an idle governor exists and is evidently not holding the engine up. That is a second defect and should not be folded into this one.

**PROPOSED FIX (not yet applied — it changes driving feel, so it is the PO's call):** gate the assist on what it was built for. Either restrict it to race starts with AI (`!isempty(AICARS) && IS_RACE`), or honour the driver's clutch whenever the slider is meaningfully disengaged (`clu > 0.4`), so riding the clutch always wins over the assist. **`JM_NO_LAUNCH_ASSIST=1` as an immediate opt-out is the smallest honest step.**

#### E93 FIXED (2026-08-29) — PO: *"Make auto easy, I never use it so I don't care. Make manual right. Require that the slider be down before you can enter manual mode."*

**1. MANUAL is now honest — the launch assist is OFF.** The override at `:4664` fired **only** in MANUAL (`!CTL.auto`), so gating it off changes MANUAL and nothing else. **AUTO is untouched** and still launches itself through `step_car3d!`'s auto-clutch, which is exactly what "make auto easy" asks for. `JM_LAUNCH_ASSIST=1` restores the old behaviour for an A/B.

In MANUAL the slider is now the clutch, always — including from a standstill. Riding it out from rest is a real clutch release, which is what the PO asked for on 2026-08-27 (*"I like the clutch attached to a slider — that way I can ride the clutch"*) and what the assist had been quietly removing at the one manoeuvre where it matters most.

**2. Entering MANUAL requires the slider DOWN.** `G` now refuses the AUTO→MANUAL switch while `clu < 0.4` and says why:

```
[gearbox] staying in AUTO -- put the CLUTCH SLIDER DOWN (disengaged) before switching
to MANUAL. Slider is at 0.02 (need > 0.4).
```

Otherwise you would drop into MANUAL with the clutch already **engaged** — the state that leaves a real car stalled, and the same state that made the assist look like a reversed axis. **Leaving MANUAL is always allowed**: a mode you cannot exit is a worse bug than the one being fixed. Both directions now announce the mode, so it is never ambiguous which one you are in.

The default gearbox is AUTO (`ZAND_SHIFT`), so the gate is reached on the normal path; `ZAND_SHIFT=manual` still starts in MANUAL as an explicit opt-in.

⚠️ **STILL OPEN, deliberately separate:** with the clutch ENGAGED at a standstill and throttle applied, **rpm reads 0.0 across all 56 such ticks and the car does not move**, while `vehicle_3d.jl:56` declares `k_idle=0.5, idle_rpm=2000.0`. An idle governor exists and is not holding the engine up. **This fix does not address that** — and with the assist gone, a MANUAL driver who releases the clutch too early at rest will now meet it directly, so it matters more than before, not less.

### E94 (PO 2026-08-29) — barrier hits must be INELASTIC, not a trampoline

PO: *"when the car hits a barrier at speed it should damp out and get stuck, indicating an inelastic collision that causes damage. Popping off the relevant wheel or wheels, which then roll and bounce away, would be nice (that's what GPL does). When it hits a barrier at speed, the car should not have an elastic collision causing it to trampoline, levitate, etc. as my car just did on the last run."*

#### Part 1 — the trampoline. **FIXED, and the parameters contradicted their own documentation.**

`drive_rt3d.jl` `contact_force`, `:wall` branch:

| | `:soft` (hedge/hay) | `:wall` (barrier) — BEFORE |
|---|---|---|
| spring `k` | 8.0e4 | **4.0e5 — 5× STIFFER, the stiffest in the file** |
| damper `c` | 7.0e4 | 1.5e5 |

**Three statements in the same function disagreed with each other:**
1. the docstring called `:wall` *"stiff spring + one-sided damper ⇒ **ELASTIC bounce-back**"*;
2. the inline comment on the very same line called 4.0e5 *"**soft** spring … ⇒ inelastic, no sling"*;
3. the reasoning comment above it states plainly that a stiff conservative spring *"stores k·δ² on the way in and returns all of it on the way out (the sling), no matter how much damping is layered on top"*.

**(3) is correct, and (1) and (2) were both wrong about the same number.** The wall was documented as inelastic and parameterised as a catapult — hence the PO trampolining.

**Now:** `k = 1.0e5` (soft enough that stored energy is small), `c = 3.0e5` (double the damping, doing the real work), `give = 0.05`. Docstring corrected to match. `JM_ELASTIC_WALL=1` restores the old values for an A/B.

⚠️ **These numbers are a FIRST PASS and need the PO's feel-test, not just a parse check.** The direction is certain — less stored energy, more dissipation — but the exact stiffness that stops creep-through without feeling mushy is a judgement only driving can settle.

⚠️ **`CONTACT_DVMAX = 8.0` m/s per frame is ALSO suspect and deliberately untouched.** It clamps contact to `m·8.0/dt` ≈ **296 kN**, which barely limits anything — a "cap" that permits a 480 m/s² fling is not a cap. Changing it affects every contact in the game, so it wants its own measured pass rather than being bundled into this one.

#### Part 2 — levitation. **NOT addressed.**

`contact_force` returns only in-plane `(Fx, Fy, Mz)`; there is no vertical term, so the car being thrown UPWARD must come from elsewhere — the suspension reacting to a huge in-plane impulse, or `contain3d!`'s reset path (whose own comment mentions a *"superball bounce"* and a *"huge road step on the first frame"*). Softening the spring should reduce it, but **the mechanism is unidentified and I am not claiming this fixes it.**

#### Part 3 — wheels popping off (the GPL behaviour). **NOT implemented.**

A real feature, not a parameter change: detach a wheel above a contact-impulse threshold, hand it its own rigid body with the car's velocity plus the contact impulse, and let it roll/bounce under gravity while the corner it left drags. Wants its own item and its own sprint.

#### Part 4 — damage. **NOT implemented, and nothing currently tracks it.** The PO's "causes damage" implies persistent state (a bent corner, lost grip, a dead engine). No such model exists.

### E95 (PO 2026-08-29) — **"This is not a game of bumper cars. You hit something hard, your race is over."**

PO: hard impact must (a) damp the car's motion out, (b) **permanently disconnect the engine from the drivetrain**, and (c) detach *"the wheel that hit the barrier — or both wheels, if two wheels hit before the car comes to a stop, something that happens at higher impact speed."*

**IMPLEMENTED.**

⚠️ **CORRECTION (2026-08-30, measured): the trigger is de facto SPEED-GATED, not impulse-gated.**
The peak contact force saturates `CONTACT_DVMAX` on *any* wall contact — measured **266 kN at 18 km/h**
and 296 kN at every speed above it — so `chard > 1.0e3` is trivially true for every non-hedge touch and
never discriminates. The `|v| > WRECK_MS` gate decides every case on its own. The claim below describes
the intent, not the behaviour; the two are recorded together rather than the wrong one being deleted.
The hedge exclusion IS real and does work (`:soft` never contributes to `chard`), so "bury the car in a
hedge, total it on a wall" holds — it is only the *speed vs impulse* half that is misdescribed.
**Verified after E96 that the wreck still fires**: no trigger at 18/47 km/h, fires at 54/108/200 km/h,
i.e. E96's clamps did not break E95.

**Trigger — on IMPULSE, not speed.** `solid_contact` already returns a contact-force peak; the wreck latches at `cpk > JM_WRECK_PEAK` (6.0e4 N) with `|v| > 8 m/s`. **Speed alone would be wrong**: a slow scrape into a hedge at 30 km/h must never end a race, and a heavy hit at 40 km/h should. Hedges (`:soft`) are excluded from wheel loss entirely.

**Engine permanently disconnected.** Once `WRECKED[]` latches, the driver's clutch input is replaced by `1.0` (fully disengaged) for the rest of the session, and shift inputs are dropped. **The latch is never reset — that is the point.**

**Motion bleeds out.** An extra retarding force `−m·2.2·v` is fed through `extforce3d!`, the **same port the collision uses**, so the solver integrates it. Deliberately not a post-step velocity hack: that is what `bumpX!` did and what E56 replaced.

**Wheels come off PER CORNER, PROGRESSIVELY.** The first cut chose corners up front from the impact normal; the PO's clarification is sharper, so `detach_hit_wheels!` now runs **every frame while wrecked and still moving** and detaches any still-attached wheel whose hub is inside a solid. A glancing hit loses **one** wheel; a heavy one loses a second when that corner reaches the barrier later — which is the PO's *"two wheels hit before the car comes to a stop"* falling out of the geometry rather than being special-cased. Gated on `cpk > 1e3` so the per-corner scan only runs during real contact.

**Detached wheels are world objects**: ballistic with gravity, bouncing at **restitution 0.35** (a tyre does not superball either — the same reasoning as E94), scrubbing 14 % of horizontal speed per bounce, spin bleeding at 25 %/s. They keep the car's momentum plus a kick off the wall. `loosemat()` gives them a world transform instead of `carModel`, and `is_loose(nm)` stops the car drawing a corner that has left it.

⚠️ **NOT YET DRIVEN — loads clean, no runtime errors, but nobody has hit anything.** Everything above is verified only by a clean load and the error-node parse walk. **The thresholds are first guesses**: `JM_WRECK_PEAK` may fire too eagerly or not at all, and only driving into a barrier will tell.

✅ **IMPLEMENTED (E94-P4, 2026-08-30): DAMAGE IS NOW PERSISTENT STATE.** Per-corner, accumulated from the CLOSING speed (the same quantity the wreck rule reads, so both judge an impact the same way), multiplied into per-wheel grip via the existing `wheelmu3d!` path. A rub below 3 m/s costs nothing — the PO's low-impulse exception. Repeated knocks worsen a corner and saturate at 1.0; a ruined corner keeps 35% grip, because a bent corner still rolls. Respawn clears it: that is a new car, not a repaired one. **No tuning knobs** — the damage model exposes no `JM_` env vars, and the gate asserts that by reading the source, because a constant that reads `getenv` is a fudge factor whatever it is called. ✅ **S3: the ENGINE too.** The PO named three things damage should mean — *"a bent corner, lost grip, or a **dead engine**"* — and the corner model was only the first two. Engine damage accumulates from the same impact with a HIGHER onset (8 m/s against a corner's 3), because a knock that bends suspension usually leaves the engine running; the gate asserts that difference rather than leaving two constants that might as well be equal. A sick engine still pulls (25% floor); a dead one makes no power at all, the revs fall, and **E98's stall rule then drops MANUAL to AUTO on its own** — the two rules compose without either knowing about the other. Applied to the driver's THROTTLE, not inside the model, so it cannot disturb the ibt-derived engine curve. Gated by `tools/damage_smoke.jl`. ✅ **S2 (same day): DIRECTIONAL after all.** The contact POINT was never needed. `contact_force` returns the force in the BODY frame and a contact can only PUSH, so the blow arrived from the direction opposite the force it produced; each corner is weighted by how squarely it faces that direction and a corner facing away takes nothing. Measured: a blow from the right gives FR=0.73 RR=0.85 with FL/RL untouched (the rear takes more because its corner vector is more lateral — the rear track is shorter than the front overhang); a head-on blow gives FL=FR=0.85 with the rear clean. A degenerate force still spreads, which is the honest behaviour when the direction genuinely is not known. No tuning constants. Gate proved able to fail: ignoring direction turns both 'spares' arms red. <br>~~⚠️ NOT implemented: DAMAGE as persistent state.~~ The PO's "causes damage" is satisfied here only in the sense that the race is over. There is still no model of a bent corner, lost grip, or a dead engine that a rejoin would have to respect.


### E96 (PO 2026-08-30) — **"The car should never bounce back, ever."**

PO, verbatim: *"car should never bounce back, ever. If it hits something, its forward motion should quickly damp to zero. If it hits with enough impact, the wheel or wheels that hit should come off, and the engine should be permanently decoupled from the drive train."*

This restates E95 as an **absolute**, and the absolute is the point. E95 treated bounce-back as a tuning problem — soften `k`, cap the spring penetration, raise the damping — and every one of those rounds still left the PO bouncing. The PO has now removed tuning from the table: **no rebound is acceptable at any speed, off any object.** E95's own trigger is a threshold (`cpk > JM_WRECK_PEAK` AND `|v| > 8 m/s`), so every impact BELOW it still runs the ordinary elastic contact law and can still throw the car back. That gap is E96.

**Acceptance (all four, and the first is not negotiable):**
1. **No impact at any speed returns the car in the direction it came from.** A sub-threshold tap is allowed to stop the car, scrub it along, or bury it — never to reverse it. This is a property to enforce structurally, not a constant to tune: the contact law should be capable of removing normal velocity but not of restoring it.
2. Forward motion damps **quickly** to zero after a hit.
3. Impact above the threshold detaches the wheel(s) that struck — already E95's behaviour, restated here.
4. Above the threshold the engine is permanently decoupled — already E95's behaviour, restated here.

**Why this is its own item and not an E95 tweak:** E95 asks "was this hit hard enough to end the race?" and E96 asks "may a collision EVER hand energy back?" The second question has one answer for every impact, so it belongs in the contact law itself rather than behind a wreck latch. The four rounds of E95 parameter changes that did not satisfy the PO are the evidence that a threshold-gated fix cannot close this.

**Open question for the sprint:** whether restitution should be clamped to zero for the car body against ALL `:wall` solids (leaving `:soft` to plough), and what that does to the loose-wheel bounce, which the PO explicitly wants to keep (*"the front wheels should bounce back from the wall"*, E95). **Wheels bouncing and the car never bouncing are not in conflict — they are different bodies — but the code currently derives both from the same contact path.**

### E97 (2026-08-30) — Watkins' trackside object count does not match the historical logs

Measured today, TRACK=watglen:

    66 trackside objects + 13 billboards + 0 forest panels + 22 solid (collidable)

Four logs from the E80/E88/E92 era report, for the SAME track:

    163 trackside objects + 39 billboards + 0 forest panels + 110 solid (collidable)

**Not caused by E95h.** That rule only ever ADDS (`geomR` is consulted solely where the
whitelist returned 0.0), and the trackside/billboard counts it does not touch at all moved too.
At Watkins E95h is a clear improvement — the whitelist alone yields ~5 solids on today's 66
objects, and the shape rule takes it to 22.

**Not the hidden-object filter either.** The obvious suspect was E87-S2 ("IF IT IS NOT DRAWN, IT
MUST NOT BE SOLID"), which deliberately removed 175 of Zandvoort's 269 solids. Tested with its own
A/B switch: `JM_SOLID_KEEP_HIDDEN=1` returns **exactly** 66/13/22, byte-identical to the default.
So the objects are not being filtered out late — they are not there in the first place.

⚠️ **The old logs may not be trustworthy evidence.** `/tmp/e88_zandvoort_0.log` records
`→ track: Zandvoort` and then prints the identical 163/39/110 triple. Two different circuits
cannot have the same three counts by chance, so either those runs all loaded the same data
regardless of the label, or that census line was reporting something other than the loaded track.
Per the standing rule that a capture must record the state it claims, these logs do not.

**RESOLVED (2026-08-30, JM_OBJDIAG) — NOTHING WAS LOST; THE OLD LOGS ARE NOT ABOUT THIS DATA.**
Every removal is now attributed to the first predicate that rejects it, so the buckets sum exactly:

    == JM_OBJDIAG 147 instances -> 66 OBJECTS
       removed by drop() junk filter    53
       removed by no-mesh               21
       removed by under 1 m tall          7        (53+21+7 = 81; 147-81 = 66)

No on-road predicate fires at all. **The decisive number is 147 — the TOTAL instance count is
smaller than the 163 OBJECTS the old logs claim.** No filter change can yield 163 objects from 147
instances, so that figure cannot describe this track's data under any settings. Together with the
Zandvoort-labelled log printing the identical 163/39/110 triple, those logs are not evidence about
Watkins and should not be cited as a baseline again.

The 53 `drop()` removals are deliberate and individually justified in the filter's own comments
(grass/herbe, `infield`, Zandvoort's floating `hotels` cluster, non-Watkins `intree`/`treesrb`
smears, Monza's `trbk`/`brbk` banks). Worth noting that `drop()` already rejects `trbk`/`brbk` by
name for rendering reasons — independent corroboration of the backdrop-name exclusion E95h-S2 added
for collision.

⚠️ Closed as **no defect**. The instrument (`JM_OBJDIAG`) stays: the reason this took a sprint is
that a bare count could not distinguish "objects were lost" from "the baseline was never ours".

~~**The sprint is therefore to establish which is true before changing anything:**~~ whether ~97
trackside objects genuinely disappeared from Watkins at some point (scenery the PO would notice
missing), or whether the historical figure was never Watkins' to begin with. Re-measure from the
track data itself — the offline census in this session read 63 distinct names straight from
`watglen.dat` with no GL context, which is an independent instrument and a good starting oracle.

### E98 (PO 2026-08-30) — a stall in MANUAL must drop straight to AUTO

PO, verbatim: *"if the user stalls out in manual mode, switch to auto mode immediately"*.

✅ **IMPLEMENTED (2026-08-30).** "Stalled" was **measured before it was detected**, since no stall
model existed. With the clutch engaged and no throttle the engine dies and stays dead — at rest in 1st
`rpm 1983 → 0`, in 3rd `1965 → 0`, lugging 5th at 2 m/s `1958 → 0` (and the car is dragged to a stop) —
while a legitimate standing start dips to **466 rpm** and recovers to 2268. So the definition is
**below 300 rpm, with the clutch engaged, sustained for 0.5 s**, which clears a hard launch by 166 rpm
and cannot be tripped by a transient dip.

Verified against the false-positive cases, which matter more than the positive ones here:

| situation | min rpm | detector |
|---|---|---|
| stall at rest, 1st | 0 | **fires at 0.63 s** |
| stall lugging 5th at 2 m/s | 0 | **fires at 0.60 s** |
| standing start, full throttle | 466 | silent ✓ |
| idling, clutch OUT | 1953 | silent ✓ — the PO's own *"applying throttle with slider down just revs the engine, as it should"* |
| cruising 5th at 30 m/s | 1958 | silent ✓ |

Announced on switch (`[gearbox] ENGINE STALLED (… rpm, clutch engaged) — switched to AUTO`), because a
mode that changes under you silently is worse than the stall. **Excluded while WRECKED**: a wreck
decouples the engine deliberately and must not read as a stall. `JM_STALL_RPM` / `JM_STALL_SECS` re-grade.

**Why it matters:** E93 made MANUAL the honest mode — the clutch is a real axis and you can ride it —
and the cost of honesty is that you can stall. Being stalled with no way forward is a dead end in a
driving sim, not a lesson; the PO wants the sim to rescue itself rather than leave the car sitting.

**Acceptance:**
1. Detect a stall in MANUAL — engine rpm collapsed with the clutch engaged and the car stopped or
   nearly so. (There is currently **no stall model**: E93's follow-up measured the engine still
   producing torque at 0 rpm through the `Tmin_frac` floor, and the car pulls away from rest with the
   clutch in. So "stalled" has to be **defined** before it can be detected — that definition is part
   of this item, not a prerequisite for it.)
2. On detection, switch to AUTO **immediately** — no key press, no prompt.
3. Say so on screen/stdout, the way the G-key mode changes already announce themselves: a mode that
   changes under you silently is worse than the stall.
4. Leaving MANUAL must stay always-allowed (E93's rule); this item only adds an automatic exit.

**Open question for the sprint:** whether re-entering MANUAL afterwards should still require the
clutch-down gate E93 added. Probably yes — the gate exists so you never drop into MANUAL with the
clutch already engaged, which is the state that stalls you.

### E99 (PO 2026-08-30) — after a collision the car's ENERGY must go to zero quickly

PO, verbatim: *"insure that after a collision with an object, car energy goes to zero quickly. The car
should quickly LOSE all kenetic and potential energy (exception: if impulse is low total energy may not
be effected much, or may not go to zero)"*.

**This is the energy-domain statement of E96**, and it is a stronger claim than E96 verified. E96
proved the car cannot be *pushed back* (no rebound at any speed, ≤0.26 m/s outward, verified on the
real solver). It did **not** measure what happens to the car's total energy: a car that stops
translating can still retain energy as heave, pitch, roll or spin — and E95's own wreck report from
the PO was *"levitated and bounced"*, which is exactly energy that went somewhere other than away.

**Acceptance:**
1. After a HIGH-impulse collision, total energy — translational **and** rotational **and** the
   suspension/heave potential — decays to ~zero quickly. "Quickly" needs a number: propose one from
   measurement, then let the PO judge it at the wheel.
2. **The low-impulse exception is explicit and must be honoured**: a gentle touch may leave the car's
   energy largely unchanged. This is NOT "clamp all energy to zero on any contact" — that would make
   a light scrape feel like hitting a wall, which is the opposite of E15/E96's soft-scenery rule.
3. Measured, not asserted: instrument total energy (½mv² + ½Iω² + heave/pitch/roll terms) across an
   impact and show the decay curve for both a heavy and a light hit.

**MEASURED (2026-08-30, sprint 1) — the main requirement is ALREADY MET; the exception is half met.**
Total energy instrumented across an impact on the real solver: translational KE from the body-frame
`(u,v)`, heave KE from `ż`, heave PE from `z`, plus the yaw rate. Head-on into a wall:

| impact | E before (J) | E after | time to <5% |
|---|---|---|---|
| 7 km/h | 12,841 | 0.0 | 0.02 s |
| 29 km/h | 16,100 | 0.0 | 0.02 s |
| 108 km/h | 249,096 | 0.0 | 0.03 s |
| 200 km/h | **916,728** | **0.0** | **0.08 s** |

Zero residual in translation, heave KE, heave PE **and** yaw rate — so the "levitated and bounced"
energy has nowhere left to hide. E96's contact work carried this case; nothing further is needed for
a square hit.

**The low-impulse exception, tested with GLANCING contacts** (a head-on stop is correct at any speed —
you are against a wall — so the exception can only be tested obliquely):

| case | energy kept |
|---|---|
| head-on, 108 km/h | 0% ✓ |
| **glancing, 29 km/h** | **78.4%** ✓ the exception is honoured at low impulse |
| glancing, 108 km/h, offsets 3.0 / 4.2 / 4.6 / 4.9 m | **5.6%**, *identical at every offset* |

⚠️ **TWO OPEN QUESTIONS, one technical and one for the PO.**
**(technical)** The 5.6% is *bit-identical across every offset from 3.0 m to 4.9 m against a 5 m
obstacle* — a barely-clipping graze and a near-square hit produce exactly the same terminal state
(~25 km/h). Geometry that different should not converge, which suggests the contact is saturating
somewhere and the obliqueness is not reaching the result. That is worth finding regardless of the
answer to the next question.
**(PO)** Whether a high-speed graze *should* keep more energy is a genuine conflict between two of
the PO's own rules: E95 says *"any off-track collision at all at high speed should total the car"*,
while E99 says low impulse should not kill energy. A 108 km/h clip is high speed but arguably low
impulse. **Not guessed here** — it needs the PO to say which rule wins for a fast graze.

⚠️ **E96's guarantee does not imply this one.** No-rebound is about the *direction* energy may flow
through a contact; this is about how fast it *leaves the car*. The wreck damping (E95, `−m·2.2·v`)
acts on translation only.

---

## E100 — 🔴 The gearbox is HARDCODED, and it is the wrong car setup for every track but one

**Violates the PO's standing constraint** (2026-08-27, verbatim): *"the car physics should be
determined entirely by the iracing ibt data, there should be no modifiable parameters."*

`JuliaMotorMTK/src/drive_rt3d.jl:25` carries the transmission as source constants:

```julia
const GEARS = [2.23, 1.72, 1.32, 1.09, 0.916]
const FINAL = 4.11
```

`Setup.setup_params` already extracts `gear_ratios` and `final_drive` from the ibt session
YAML (`setup.jl:75,84-85`) — the data is parsed, and then not used by the physics.

**Measured across the whole gold-standard ibt store (2026-08-30):**

| capture | gear ratios | final |
|---|---|---|
| `lotus49_nurburgring nordschleife` ×6 | `[2.23, 1.72, 1.32, 1.04, 0.846]` | 4.11 |
| `lotus49_skidpad` ×3 | `[2.23, 1.72, 1.32, 1.09, 0.916]` | 4.11 |

**The ratios are per-session data, not a car constant** — the Lotus 49's gears are adjustable,
and these two setups genuinely differ. The hardcoded values are the **skidpad** setup, so every
track is currently driven on short-course gearing: 4th is 4.8% short (1.09 vs 1.04) and 5th is
8.3% short (0.916 vs 0.846). That is wrong rpm and wrong top speed in exactly the gears a fast
circuit spends its time in, and it is invisible from inside the sim — the car simply pulls
slightly wrong, which reads as "the physics feels off" rather than as a bug with an address.

`final_drive` happens to agree at 4.11 in every capture, which is the trap: spot-checking ONE
of the two numbers would have shown a match and closed the question.

**Fix:** the transmission must come from the loaded session, not from source. Note the wrinkle
before starting — the sim currently opens an ibt only as a *header template* for export
(`IBTREC0`, `IBTDIR`), chosen by track name, so there is no "current setup" object yet. Whatever
supplies it must also decide what happens when no matching ibt exists, and must SAY which
capture the gearing came from (a run that silently falls back to constants is the bug again).

✅ **FIXED and VERIFIED IN A REAL LAUNCH (2026-08-30).** A Spa run prints `gearbox: [2.23, 1.72, 1.32, 1.04, 0.846]  final 4.11  <- lotus49_nurburgring nordschleife 2026-06-24 15-53-11.ibt` and `mass: 616.9 kg  front 45.5%` — the circuit capture, not the skidpad, so the short-course gearing is gone from every track. Gated headlessly by `tools/transmission_smoke.jl` (15/15) and run by `tools/gates.sh` (8/8).

**Gate it:** assert the live gear ratios equal the ones parsed from the session actually loaded.
An equality assertion is what makes the constraint enforceable rather than aspirational.

### E100 S3 — audit of the remaining car parameters (no code change; two false alarms retired)

Widening the E100 audit past the gearbox and mass. Recorded because "looks hardcoded" and
"is wrong" are different claims, and two candidates here died on inspection.

**Innocent — genuine car constants.** `idle_rpm = 2000.0` and the `9500` rpm shift point match
the ibt exactly and are identical in all nine captures. `n_gears = 5` matches the 5-element
gear table. I predicted these would disagree; they do not.

**Innocent — derived, not guessed.** `front_corner.ks = 18_250` and `rear_corner.ks = 29_200`
look like magic numbers next to the ibt's 30 and 48 N/mm. They are not: both are the ibt value
× **0.6083**, the *same* factor to four figures, which is a motion ratio squared (MR ≈ 0.78) —
i.e. they are WHEEL rates correctly derived from SPRING rates. `corner_loads.jl` calibrates MR
by least squares against telemetry, so the conversion is real physics with a measured constant.
⚠️ Changing these to the raw ibt numbers would have stiffened the car by 64% while looking like
a fix that "removes a hardcoded parameter". The factor is undocumented at the constant, which is
what made it look like a violation — worth a comment there.

**Real, but structurally blocked.** The rates are still frozen to the *Nürburgring* session, and
spring rates are per-corner session data like the gears: skidpad runs LF 26 / RF 28 / LR 39 /
RR 53 N/mm, asymmetric, against the Nordschleife's symmetric 30/30/48/48. The model carries ONE
`front_corner` and ONE `rear_corner` spec, so **it cannot represent an asymmetric setup at all** —
this is not a wiring job like the gearbox was. Same for `ride_height_mm` and `camber_deg`, which
also differ per corner between sessions.

**Next:** decide whether per-corner suspension is worth the model change. The circuits all use
the symmetric Nordschleife setup, so the current constants are correct for every track actually
driven; only the skidpad diverges, and it is a physics test rig rather than a track the PO
drives. Recommend LOW priority against that, and record the limitation rather than pretending
the constants are session-derived.

### E89-S1 (2026-08-30) — the "fix the kinks first" step is already dead; the live mechanism is the follower

**The guidance above is STALE.** E84-S5/S6 (2026-08-29) refuted both centreline hypotheses after E89 was
written: the second-difference clamp moved Monza 12 → 10 and made Watkins 4.5× worse; node spacing is
uniform at 3.0 m with the highest-κ nodes at ordinary spacing. The conclusion that stood is that one
large `vtarget` step per braking zone **is the right answer**. So E89 does not start there.

**The Monza race ran the KINEMATIC field** (`step_field!` is the default; physics AI is opt-in via
`JM_AI_PHYSICS`, and the video's env did not set it). Reading `step_field!` shows a textbook
lunge-and-fall-back mechanism that owes nothing to the centreline:

- an uncommitted follower (`tlane == 0`) has **no speed matching at all** — it closes at full target
  speed until `gap < v·1.0 + 14`, then commits to a passing rail;
- while committed and within `gap < v·0.6 + 4.2` it snaps its target to the leader's speed (braking at
  16 m/s²), and the release gap is `v·1.7 + 30`, so it drops back to the line, catches up again, repeats;
- phase 2's queue rule **teleports** a same-lane trailing car back to `s_leader − 4.2` and clamps its
  speed — a visible jump backwards, every frame the overlap persists.

A bang-bang follower with a dead band. The fix will be a proportional gap controller (target speed
ramping from the leader's speed at the minimum gap to free speed at a larger one), not tuning.

**Instrument built, parse-checked, NOT YET RUN** (the display is held by bob's suite): `RaceAI.AISTAT`
counts engage/release/match/queue-snap/side-push/mishap events; `RaceAI.free_speed_profile` runs a lone
car for a lap to give `v_free(s)` — the baseline a "fall back" must be measured against, because a car
braking for Ascari is not falling back; and `JM_AI_TEST` now reports **fall-back episodes** (deficit
> 5 m/s vs `v_free` held > 0.5 s) and **rail switches** per car-lap. State the prediction now: several
episodes per car-lap and switches ≥ 2 per car-lap; after the fix, episodes ≈ 0 outside mishaps.

**`.rpy`: partially decoded, body is not fixed-stride.** Header `RPLY` / `RPHD`, track name at 0x1c,
frame count 5343 at 0x28, body length 361332, driver name at 0x38. No 4-byte field advances
monotonically at any stride 48–128 across 2000 records, so frames are variable-length (delta-coded),
and the two public projects (gplreplay.sourceforge.net, GPL Replay Analyser) publish no format. GPLRA
exports telemetry to text and has command-line support, and the box has GPL under Wine — **running
GPLRA under that prefix is the realistic route to the PO's "refer to the .rpy files"**, not writing a
decoder blind. Files are 🔒 read-only; work on copies in `/tmp/rpy/`.

**E89-S1 correction (GPL rails):** they are not a fixed ±4 m — that was the pit straight. Monza, per record: pass1−race: median +1.08 m, p10 +0.00, p90 +3.91, |dev|>1 m on 55% of the lap; pass2−race: median -3.39 m, p10 -4.24, p90 +0.00, |dev|>1 m on 78%; both rails within 0.5 m of the race line on 0% of records. GPL's passing space is asymmetric and opens only where the road allows; a fixed `RAIL = ±2.4` on both sides everywhere is not what GPL does.

### E83 — ✅ ROOT-CAUSED AND FIXED (2026-08-30): the MIP palette is B,G,R,A and was read as R,G,B,A

Judged the PO's way first — a gold Ring `nintendo` frame beside the PO's 2026-08-27 Ring drive: gold
forest is deep green (mean 77,98,53 — red above blue); the PO frame's trees are **cyan** (129,201,155,
blue above red) and its bushes pale yellow-white. Not a grade: the saturation medians match (0.41–0.47
vs 0.36–0.48); the HUE is wrong on specific sprites.

A per-MIP-type census of every Ring texture found it: **type 1 (shared-palette cutouts — the
vegetation sprites): 47 of 60 green-dominant textures had B > R**, while the 16-bit types 3/4/5 were
right (`brd_shel` = Shell red-yellow (191,117,1), `cocacol` red). The decoder's `read_cmap` took
palette entries as R,G,B,A. Rendering the strongest R/B-asymmetric palettised textures both ways
settled it by eye: `bo_sign2` is **BOSCH in red**, `x-sign` the German no-stopping sign (red ring, blue
centre), `drygrass` yellow, `hgbush` olive green — only with B,G,R,A. GPL's CMAP is Windows DIB order.

Fix: `gplmip.jl` `read_cmap` reads B,G,R,A; `GPLMip.CMAP_ORDER` is part of the decoded-texture cache
key so 1.2 GB of swapped pixels on disk cannot be served again (and that cache was deleted). After the
fix: type 1 teal 47 → 11, type 2 → 0. Gate `tools/mipcolor_smoke.jl` (in `gates.sh`) pins six
known-colour textures including two 16-bit ones that must NOT change; proven to fail with RGBA
restored (3 arms red).

⚠️ This also rewrites the premise of **E70-S8**: the "alpha bleed" note measured `hgbush` opaque as
(20,69,56) — that was the swapped decode; the true opaque colour is (56,69,20). The bleed pass itself is
still valid (it acts on alpha, not hue), but any colour conclusion drawn from pre-fix decodes should be
re-read. **Not yet verified on screen** — needs a Ring capture with the display, which bob's suite holds;
queued after the E89 runs. The E69/E72 exposure dead end stands untouched: nothing here changes `GRADE_*`.

### E84 — design note from the .lp decode (2026-08-30): GPL's own AI lines are usable directly

The PO's E84 brief is "AI slot cars as in GPL, behaving as they do in GPL". The GPL install carries the
AI's lines themselves, and they map onto our track frame without transformation:

- `race.lp` / `pass1.lp` / `pass2.lp` / `pit.lp`: 8-byte header, then N records of 5 × Float32 at
  **exactly 3.0 m dlong** from the `.trk` start (Monza: 1918 × 3.0 = 5754 m against a 5747 m
  centreline from `trk_centreline`). Our `build_line` also resamples to 3.0 m from the same `.trk`
  start, so on tracks that are NOT re-centred (Monza is excluded from re-centring) the records are
  **index-aligned with our `AILine`**: `s = 3·i`.
- field 3 is **dlat in metres, positive to the LEFT** of the `.trk` centreline (Monza's pit lane is on
  the right and `pit.lp` sits at −13 m while `race.lp` sits at +13 m) — the same sign as our `rl`.
- field 1 is the AI's dlong speed in m/tick; × 36 = m/s. Smooth: ≤ 1.92 m/s change per 3 m.

So a "GPL line" AI mode is a data swap, not a physics change: `AILine.rl ← race.lp dlat`, corner
speed ← `race.lp` speed × `dlong_speed_adj_coeff` (track.ini, Monza 1.016) capped at
`dlong_speed_maximum` (2.41 m/tick = 86.8 m/s), rails ← `pass1`/`pass2` dlat (asymmetric, per record),
following ← `gpl_ai.ini` `desired_dlong_sep` 14 m. On re-centred tracks the dlat frame shifts by the
re-centring offset per node and must be corrected before use. Reader: `demo/native/gpl_lp.jl`.

### E89-S1 addendum / E84-S7 (2026-08-30) — GPL's line is the oracle, and it says the kinks were real

Headless, single free-running AI car on Monza against GPL's own `race.lp` speed at every 3 m:

| target speed model | free lap | mean \|Δv\| vs GPL | speed steps >1 m/s per 3 m | min speed |
|---|---|---|---|---|
| shipped κ model, `amax=8` | **122.9 s** | 11.94 m/s | **147** | 15.3 |
| κ model, `amax=14`, `vmax=86.8` | 101.7 s | 8.91 | 117 | 20.3 |
| **GPL `race.lp` speeds** (`JM_AI_GPLLINE=1`) | **94.8 s** | **3.1** | **2** | 31.6 |
| GPL itself | 89.6 s | — | 13 | 31.6 |

Two things this settles:

1. **E84-S5/S6's "the spikes are correct — one braking zone per corner" is REFUTED by the oracle it
   lacked.** Through Curva Grande the `.trk` is a single R = 304 m arc for 382 m; our racing-line κ
   there swings R = 350 → 515 → **153** → 745 → 426, and at s = 1012 that collapses `vtarget` to
   34.9 m/s where GPL carries 66.5. A lone car braking hard mid-corner and recovering **is** "lunge
   ahead, then fall back" — E89's symptom, with no other car involved. The noise comes from the
   racing-line construction (relaxation + apex shift), not the centreline nodes (E84-S6 was right
   that spacing is uniform) and not lateral kinks alone (E84-S5's clamp could not touch it).
2. **Our grip cap is half of GPL's.** GPL's speeds on the `.trk` radii imply lateral p50 10.8, p90
   14.1, max 16.9 m/s²; ours is `amax = 8`. That alone is 21 s of the 33 s lap gap.

The fix that follows the PO's brief ("AI slot cars as in GPL") is to take GPL's speed table directly
where the index aligns (Monza, Zandvoort — not re-centred). Implemented behind `JM_AI_GPLLINE=1`;
the app says which file supplied it. Re-centred tracks (Watkins, Ring, Spa) need the dlat/dlong frame
correction before they can use it. The remaining 5 s to GPL is our `advance_speed` accel/brake model.
**Not yet run in the sim** — three self-test arms (baseline / gap control / gap control + GPL line) are
queued behind the display.

### E89-S2 (2026-08-30) — measured headlessly, fixed, gated: the lunging was mostly OUR speed model

The field measurement ran without the display after all: `build_line` on the raw Monza `.trk` is
pure, and so is `step_field!`. Four cars, 300 s, 30 s warm-up, against a lone car's free speed:

| arm | lunge-fall cycles / car-lap | rail switches / car-lap | queue-snap teleports |
|---|---|---|---|
| shipped (κ speeds, no gap control) | **1.83** | 1.26 | **739** |
| GPL `race.lp` speeds only | **0.09** | 0.91 | 505 |
| gap control only (τ = 1.5 s) | 3.68 ✗ | 1.15 | 1 |
| GPL speeds + gap control τ = 1.5 | 1.29 ✗ | 0.64 | 0 |
| GPL speeds + gap control τ = 3 / 5 / 8 | 0.46 / 0.46 / 0.92 | 0.55 / 0.46 / 0.46 | 0 / 0 / 0 |

**Shipped now (defaults on, `JM_AI_GPLLINE=0` / `JM_AI_GAPCTL=0` revert):** GPL's `race.lp` speed
table as the target, plus a proportional follower (target = leader speed + excess gap over
`desired_dlong_sep` 14 m closed over τ = 4 s), with the speed-governing car being the nearest one
**in our path** while the pass hysteresis keeps its any-lane blocker.

Three of my own attempts failed on the way and are recorded so they are not retried:
- a GPL-style "settled + quicker + straight" ENGAGE rule flapped (24.6 → 171 switches per car-lap)
  because with GPL speeds every car's free speed is near-equal, so "we are quicker" flickers;
- using the in-path car for the hysteresis too: the in-path car changes the instant we pull out, so
  release fired at once — 925 engage/release pairs in 270 s;
- τ = 1.5 s is an underdamped follower hunting round the desired gap — more cycles than no control.

The remaining 0.46 cycles are cars 3–4 (the fastest pace) catching and being held behind slower cars,
which is racing. Gate `tools/ai_field_smoke.jl` runs BOTH arms — the control must still show the
defect (1.83 / 739) or the treatment's clean numbers mean nothing. Suite 13/13. ⚠️ Not yet re-driven
by the PO; the three sim self-test arms are still queued behind the display and will confirm the same
code path live. Watkins/Ring/Spa keep the κ model until the re-centred dlat/dlong frame is mapped.

### E82-S1 (2026-08-30) — the axles are not missing; the shipped fold draws them 1.2–1.9 m underground

Gold (Monza/Ring `nintendo` frames): two driveshafts, radius arms and shocks run from the rear hubs
inboard to the gearbox, clearly visible between the rear tyres. E75 spent 16 sprints on transforms
without a gold comparison; this starts from the geometry itself, headlessly.

`lotus.3do` inventory (`demo/native/lotus_inventory.jl`, `lotus_groups.jl`): the rear running gear IS
in the model — `axlelot` 76 tris, `lsusp2–7`, `lshok`, `lbrdisc`, `rear`, `top` — and groups 27288 /
39792 (the two halves `RSUSPP_A/B` extract) each carry the full set. `parse_3do` applies the positioner
chain, so extracted vertices are already in car space. In car space (`rs_fold_probe.jl`, x fwd / y up /
z lateral), group 27288 RAW:

| part | x | y (up) | z (lateral) |
|---|---|---|---|
| `axlelot` | −1.80..−0.77 | **−0.08..0.23** | **−0.86..−0.42** |
| `lsusp2` (upper link) | −1.76..−1.00 | 0.22..0.25 | −1.02..−0.52 |
| `lsusp7` (lower link) | −1.66..−0.77 | −0.08..−0.05 | −1.01..−0.52 |
| `lshok` | −1.74..−0.75 | −0.10..0.21 | −1.06..−0.49 |

That is a correctly posed left-side rear assembly: driveshaft at hub height running from the gearbox
(z −0.42) to the hub (−0.86), upper links above lower links. **It does not need folding.** The shipped
`rsfix` (E64-S8: "authored flat, fold 90° about the hub line z=+0.772") rotates this LEFT-side half
about the RIGHT hub line and lands every part at **y = −1.17..−1.87** — deep under the road — at
z 0.55..0.9. With the matching side the fold still turns a horizontal shaft vertical and puts it at
y ≈ −0.25. So the PO sees no axles because the axles are under the track, and E64-S8's "unfolded flat"
reading was wrong: the "wings splayed flat" ARE the links, correctly horizontal.

Prediction, stated before the capture: `JM_RS_ROLL=0` (identity — the positioner already placed
the parts) shows driveshafts and links between the rear tyres in the chase view; the default shows
none. Two Monza chase-shot runs (default / `JM_RS_ROLL=0`) are queued behind the display.

**E89-S2 live confirmation (2026-08-30, first display slot):** the sim's own `JM_AI_TEST` on Monza
prints `AI speed profile: GPL race.lp (1918 records, adj 1.016, cap 86.8 m/s) <- .../monza/race.lp`
and reports **queue-snaps 0, side-pushes 0, rail switches 1.2 per car-lap**, four cars averaging
229–234 km/h over 120 s (the shipped κ model averaged far less). Note: the run queued as the
"baseline" launched *after* the defaults flipped on, so it measured the treatment — the sim-side
control is the headless gate's control arm, not this run.

**E84 frame caveat (2026-08-30, measured):** GPL's `race.lp` dlat and our `rl` are NOT in the same
lateral frame even on Monza. Our centreline is `align_centreline(trk, ROADHAT)` — aligned onto the
road even where it is not re-centred — so on the pit straight GPL's line sits at dlat **+13.4 m** from
the raw `.trk` centreline while ours reads 0 there; lap-wide the median offset is 2.34 m and the
correlation only 0.37. **The speed table is index-aligned (dlong) and safe; the lateral tables
(`race`/`pass1`/`pass2` dlat) need the per-node align shift subtracted before use.** That shift is
`ALIGNED − trk_centreline` projected on the left normal, available in the sim. GPL's rails relative to
its own race line are asymmetric: left median +1.08 m, right −3.39 m, against our fixed ±2.4.

**E84 frame caveat — CORRECTED (2026-08-30, measured):** `align_centreline` on Monza returns the
identity (raw-`.trk` road coverage 0.979 > the 0.6 threshold), so GPL's dlat and our `rl` ARE in the
same frame there. The 13.4 m on the pit straight is real: the `.trk` centreline runs down the middle
of the pit-lane-plus-track area and GPL's line is 13 m left of it, while our synthesised line is
clamped to ±3.8 m of the centreline — so on **30% of the lap GPL uses road our AI may not**, and on
the pit straight our cars run 13 m right of GPL's line, toward the pit wall. The caveat stands only
for tracks that re-centre (Watkins, Ring, Spa). On Monza/Zandvoort GPL's `race`/`pass1`/`pass2` dlat
can drive the AI's lateral position directly. (`demo/native/e84_frame_shift.jl`.)

### E84-S8 (2026-08-30) — GPL's lateral tables wired in behind `JM_AI_GPLLAT=1` (default OFF, measured)

`race.lp` dlat as the racing line, `pass1`/`pass2` dlat as the two rails (asymmetric, per record), the
lane clamp lifted to GPL's own extent. Monza, 4 cars, 270 s, headless field probe:

| arm | lunge-fall cycles / car-lap | rail switches | queue-snaps | side-pushes | max \|lane\| |
|---|---|---|---|---|---|
| GPL speeds + gap control (shipped) | 0.46 | 0.46 | 0 | 3 | 2.6 m |
| + GPL lateral tables | 1.2 | 0.28 | 0 | 6 | **12.9 m** |

Lane use now follows GPL's line (12.9 m on the pit straight, where ours was pinned at 2.6) and rail
switching drops further — but the field forms a **train**: speed-matched frames go 6402 → 38540 and
trailing cars show 1.2 deficit cycles per car-lap, above the E89 gate's 1.0. With everyone on GPL's
single line and rails of +1.1/−3.4 m, cars queue rather than run staggered. GPL's real fields do
queue, so this may be right — but it is a visible behaviour change and stays **default OFF** until the
PO's re-drive judges it. Not a fix candidate for E89's symptom; it is the E84 "as in GPL" lane model.

### E83-S2 (2026-08-30) — first on-screen check after the palette fix: the cyan is gone; a brightness gap remains

Ring chase captures (`JM_SHOTS`, s = 600/2400/9000) after the BGRA fix, green-dominant vegetation
pixels in the mid-band: **B > R ("teal") on 0.2–10.6%** of them (the PO's frame before the fix: the
bushes were cyan outright). By eye the bushes are yellow-green/olive, no turquoise anywhere. But the
native vegetation is **~1.7× brighter and yellower than gold** — mean RGB (137,154,86) at s=600 and
(106,124,68) at s=2400 against gold's (60,78,40) — so "neon" may still read as *too bright* even though
the hue is right. ⛔ Per the E69/E72 dead end this must NOT be answered with a grade change; the
remaining candidates are the vegetation sprites' own decode brightness (4-bit vs 8-bit palette
paths, the alpha-bleed pass pushing bright colour into edges) and the scene lighting on billboards.
Needs the PO's eye on the Ring. Also visible in these captures, unrelated to colour: the horizon ring
shows a hard seam and one enormous floating panel — that is E81 territory, noted for it.

**E82 note from the same investigation:** the two depth-1 "park" positioners (d = (0,20,0)) hold the
BODY group as well as the rear halves, so "parked" does not mean "hidden" in this model — that lead is
closed. The front chrome legs need the Monza roll-0 / roll-90 captures against the gold Monza frame,
which are queued.

### E83-S3 (2026-08-30) — the residual brightness is LIGHTING: sprites were lit as geometry; now drawn unlit like GPL's

After the palette fix the Ring's tree textures decode to gold's colour (`s_tree04` (57,80,45),
`dopptann` (27,45,27) vs gold forest (60,78,40)) — yet the captures show them at ~(137,154,86): about
2× too bright, pale mint. The shader lit every billboard as geometry — ambient + 1.15 × sun, then
`BB_BRIGHT = 1.55` (an E70-S7 tunable added to fight the *cyan*, which was the palette all along).
GPL's sprites are pre-lit art drawn at texture brightness. New `uUnlit` shader path: texture × tint,
fog, white balance, exposure — no lighting. Billboards and forest-edge panels use it by default;
`JM_BILLBOARD_LIT=1` restores the old path. **Prediction, before the capture:** vegetation mean in the
Ring chase shots falls to ≈ the texture mean (≈ 57,80,45), i.e. within ~15% of gold, with no teal.
Not a grade change — `GRADE_*`, `uExposure` and `uWBal` are untouched, so the E69/E72 dead end is respected.

**E83-S3 CONFIRMED ON SCREEN (2026-08-31).** Ring chase captures with the unlit sprite path, mid-band
vegetation mean RGB, against the same points lit and against gold:

| point | lit (before) | unlit (now) | gold Ring |
|---|---|---|---|
| s=600 | (137,154,86) | **(84,93,47)** | (58,78,41) |
| s=2400 | (106,124,68) | **(89,96,42)** | (61,78,39) |
| s=9000 | (80,90,46) | (79,89,44) | (59,74,37) |

Teal ≤ 0.2% at the near points. By eye the bushes are olive/green, no mint, no cyan. The remaining
gap to gold is ~1.4× on red and ~1.2× on green — smaller than the lighting error just removed, and
NOT to be closed with a grade change (E69/E72 dead end). Candidate for the residue: the sprites are
still fogged and white-balanced, and gold's forest is mostly mesh trees rather than billboards, so
some of the difference is scene composition rather than sprite colour. **PO's eye needed on the Ring.**

### E82-S2 (2026-08-31) — ✅ THE CHROME SPIDER-LEGS ARE GONE, verified on screen

S1's roll fix was necessary but not sufficient, and the capture said so: with the 90° fold removed the
rear assemblies stopped being *under the road* and became **visible chrome legs through the tyres** —
the fold had been hiding a second defect, not fixing it.

Measured, in car space (wheel face = 0.85 = `CARP_MAXLAT`, front axle x = +1.31, rear axle x = −1.10):

| assembly | before | after clip at 0.85 |
|---|---|---|
| rear group 27288 | 456 v, x −2.50..−0.73, **z −1.12..−0.42** | 249 v, x −1.06..−0.73, z −0.61..−0.42 |
| front (lsusp1+frontlot) | 294 v, x −1.06..**+2.73**, **z ±1.12** | 282 v, x −1.06..+1.63, z ±0.63 |

The front's overhang is 4 triangles of 1.3 m strips reaching past the nose; the rear's is 42% of its
triangles reaching through the tyres. The code has recorded this overhang since E64-S4 ("spear tips
through the tyres", "shocks reach lateral 1.06 vs the 0.85 wheel face") without clipping it. Now
clipped where the car ends. Monza chase capture: the starburst is gone, the car reads as wheels +
gearbox + links. `JM_RSUSP_MAXLAT` / `JM_FSUSP_MAXLAT` override.

⚠️ **Honest limit:** `maxlat` drops whole triangles, so the driveshafts now stop at z = 0.61 instead of
reaching the hub at 0.772 — stubs rather than full shafts. Gold shows them running to the wheel. That
is a smaller, different error than a starburst through the tyres, and closing it needs per-triangle
*trimming* rather than dropping. Gate `susp_pose_smoke` now asserts the envelope on front and rear;
unclipped it fails 4 arms.

### E82-S3 (2026-08-31) — ✅ the driveshafts reach the hub: `maxlat` now TRIMS the rear instead of dropping it

S2 closed the starburst and named its own residue honestly: `maxlat` discards any triangle with a
vertex past the wheel face, so the driveshafts — which run from the gearbox **out** to the hub at
|lat| 0.772, built from triangles whose far vertices sit past the 0.85 face — lost every one of those
triangles and ended at **0.61 as stubs**. Gold shows them running to the wheel.

Fixed by cutting the triangle at the plane rather than throwing it away: `Render._clip_lat` does a
Sutherland–Hodgman clip against `gy = ±maxlat`, interpolating position, normal and UV at each
crossing and fan-triangulating the 3–5-gon. A triangle wholly inside is returned untouched, so
`trim=true` is a no-op wherever nothing crosses.

| rear group 27288, maxlat 0.85 | tris | x | \|lat\| |
|---|---|---|---|
| drop (shipped since S2) | 83 | −1.06..−0.73 | 0.422..**0.61** |
| trim (S3) | 176 | −2.15..−0.73 | 0.422..**0.85** |
| unclipped, for reference | 152 | −2.50..−0.73 | 0.422..1.117 |

So the shafts now pass the hub at 0.772 and stop exactly at the wheel face, with nothing outside it.

⚠️ **The front does NOT trim, and that is measured rather than assumed.** Turning trim on there took
the front assembly to **x max 2.13** — forward of the nose — and the gate went red on it. The front's
overhang is 4 whole 1.3 m strips at |z| 1.12: stray geometry, not a part that should reach the wheel,
so cutting them merely keeps their inboard halves. Drop at the front, trim at the rear.

⚠️ **The gate was measuring the wrong build, and would have gone on doing so.** `susp_pose_smoke.jl`
called `extract_gpl_car` **without** `trim`, so once the sim started trimming the gate kept printing
the old `|z| max 0.61` — green, and reporting a number the shipped build no longer produces. It now
mirrors the sim's `JM_SUSP_TRIM` default. It also only ever checked an **upper** bound, which is why
stubs were invisible to it for a sprint; it now asserts the shafts **reach** the hub (|z| ≥ 0.772).
That check is deliberately **not** guarded on `TRIM` — guarded, `JM_SUSP_TRIM=0` reported PASS while
putting the stubs back, i.e. the gate went green on the defect it exists to catch. Unguarded, the
knob is a real negative control: **treatment 0.85 PASS / control 0.61 FAIL (2)**.

**The capture then refuted the first two versions of this fix, and the third is what shipped.**
Three Monza chase arms, `parity/e82_s3/compare.png` (drop / trim@0.85 / trim@0.74, rear corner):

| arm | what the screen showed |
|---|---|
| drop (S2, shipped) | correct car, **no driveshaft** — the stub gap S2 named |
| trim everything @ 0.85 | **wide chrome slabs lying across both tyres** — 16921 px changed |
| trim `axlelot` only @ 0.85 | slabs gone, but **a chrome rod out past the tyre and down to the road** |
| trim `axlelot` @ 0.74 | **driveshaft from the gearbox to the hub, ending at the wheel** ✅ |

Two distinct errors, both caught only by looking:

1. **Trimming the whole group re-admits the mirror-copies.** By texture, trimming brought back
   `lid`, `arms`, `top`, `rear` — the driver/body "spears" E64-S4 recorded in 27288/39792. Dropping
   had been removing them as whole polys; trimming turns each into a wide sliver. `trim` now takes a
   set of texture names, and only `axlelot` — the driveshaft itself — is trimmed.
2. **The clip limit was in the wrong frame, and so was the gate.** 0.85 is `CARP_MAXLAT`, the
   *body* mesh's clip. The wheels are **drawn** at half-track `WTRACK_R` = **0.74**, so anything
   reaching 0.85 stands 11 cm outside the wheel centre plane by construction. The gate measured the
   part mesh against 0.85, printed "inside the tyres (|z| < 0.95)", and passed — while the screen
   showed rods sticking out past the rear tyres. **A gate whose frame is not the frame the eye
   judges will certify anything.** Both the clip and the gate now use the drawn half-track.

So the reach threshold is 0.73–0.74, not the 0.772 of `rsfix`'s hub line: **treatment 0.74 PASS /
control (`JM_SUSP_TRIM=0`) 0.61 FAIL (2)**. Full suite **14/14**.

⚠️ Also of note for any sprint that edits this file: `Meta.parseall` cannot see an undefined name.
Setting `RSUSP_MAXLAT` from `WTRACK_R` parsed clean and died at load with `UndefVarError` — the
constant is defined 80 lines further down.

### E96-S5 (2026-08-31) — ✅ acceptance 1 holds at EVERY approach speed, and the gate can now prove it

E96's first acceptance is an absolute — *"no impact at ANY speed returns the car in the direction it
came from"* — and `contact_smoke.jl` tested exactly **one** speed (30 m/s). One speed cannot support
an "any speed" claim, and a spring-damper contact fails at the *ends*: too slow and the spring wins,
too fast and the penetration does. Swept 5 → 80 m/s:

| v0 | final x | maxpen | peak reverse | reversing for | carried back |
|---|---|---|---|---|---|
| 5 | −15.1 | 0.00 | +0.0 | 0.00 s | 0.0 |
| 10 | −2.6 | 0.10 | −3.0 | 0.03 s | 0.0 |
| 30 | −1.6 | 1.18 | −3.9 | 0.03 s | −0.6 |
| 60 | +0.5 | 2.42 | −13.1 | 0.05 s | −2.3 |
| 80 | +0.4 | 2.52 | −26.4 | 0.08 s | −1.8 |

**No speed returns the car.** The reversal never lasts beyond 0.08 s and never carries the car back
past where it first touched — that is the spring unloading the car out of its own penetration, not a
bounce. **Acceptance 1 is met across the range.**

⚠️ **Two instrument failures found on the way, and the second is the important one.**

1. **The first metric flagged everything.** Peak instantaneous reverse velocity alone called 10 m/s
   a bounce at −3.0 m/s — with **0.0 m** of actual backward travel. Position-delta velocity during a
   stiff contact step is a spike, not a motion. Sustained duration + net displacement is the honest
   measure.
2. **`JM_ELASTIC_WALL` IS A DEAD KNOB.** It is documented as *"restores the old 4.0e5/1.5e5 for an
   A/B"*, and it changes **nothing** — measured directly on `contact_force`, both settings return
   **identical forces at every penetration and closing speed tested**, saturated and unsaturated
   alike. E96's own outcome cap `Fn = min(Fn, m·(VN_OUT_MAX − vn)/dt)` bounds the RESULT, so the
   spring/damper constants beneath it no longer reach the output. **Anyone reaching for it as a
   negative control — as I did — gets a control arm identical to the treatment and would conclude
   the fix does not matter.** The live knob is `JM_VN_OUT_MAX`.
3. **And with a working control, the gate failed to fail.** `JM_VN_OUT_MAX=8` reverses the car for
   **0.70 s** at 10 m/s and sends it **50–60 m clean through the wall** at 60–80 m/s — and the
   sweep still printed *"no bounce-back ✓"*, because it required sustained reversal **AND**
   displacement together, and computed "carried back" in a way that reports a pass-through as a
   large positive. Three separate failure modes now, as alternatives: sustained reversal (>0.15 s),
   returned (>3 m behind first contact), passed through (beyond the obstacle).

**Treatment: all 7 speeds ok, exit 0. Control (`JM_VN_OUT_MAX=8`): 6 of 7 red, naming SUSTAINED
REVERSAL at 10–45 m/s and PASSED THROUGH at 60–80. Suite 14/14.**

### E100-S4 (2026-08-31) — ✅ spring rates now come from the ibt, per corner; the model can represent an asymmetric setup

E100-S3 recorded the rates as *"real, but structurally blocked … the model carries ONE `front_corner`
and ONE `rear_corner` spec, so **it cannot represent an asymmetric setup at all** — this is not a
wiring job like the gearbox was."*

**It was a wiring job.** `DrivenVehicle3D` already builds four corner assemblies (FL/FR/RL/RR); it
simply passed the *same* spec to both sides of each axle (`vehicle_3d.jl:76–79`). Each corner now
takes its own spec, defaulting to the axle-shared values, so a caller that passes nothing gets the
previous model unchanged.

`set_suspension!(fl, fr, rl, rr)` joins `set_transmission!` (E100) and `set_mass!` (E100-S2), and
`drive_native_mtk.jl` installs all three from the same session. `wheel_rate(N/mm)` holds the unit
change and the motion ratio in one place.

| session | ibt SpringRate N/mm (LF/RF/LR/RR) | installed wheel rate N/m |
|---|---|---|
| Nordschleife 15-53-11 | 30 / 30 / 48 / 48 | 18249 / 18249 / 29198 / 29198 |
| skidpad 15-46-39 | 26 / 28 / 39 / 53 | **15816 / 17032 / 23724 / 32240** |

The circuit session reproduces the shipped constants **18250 / 29200 to within 1–2 N/m**, which is
both a clean regression check and independent confirmation of the motion ratio: the constants always
*were* the ibt values × 1000 × 0.6083. E100-S3 nearly "fixed" them to the raw ibt numbers, which
would have stiffened the car by 64% while looking like the removal of a hardcoded parameter — the
factor is now named at the constant (`MR2`) instead of waiting to be rediscovered.

The skidpad row is the point: four distinct rates where the model could previously hold two.

Gated in `transmission_smoke.jl` (the session-data gate): the ibt carries four SpringRates in 9
sessions, the rates vary between sessions, **3 sessions are genuinely asymmetric left/right** — so
per-corner plumbing cannot pass by construction — the live `KS` equals the installed session's, and
`wheel_rate` reproduces both shipped constants. Rubbish rates are refused. Suite **14/14**.

⚠️ Still frozen, and honestly not fixed: `ride_height_mm` and `camber_deg` are also per-corner
session data and are still constants. Same shape, same fix; not done here.

### E100-S5 (2026-08-31) — ✅ static ride height comes from the ibt, per corner; the model had no rake at all

E100-S4 closed by naming what was still frozen: *"`ride_height_mm` and `camber_deg` are also
per-corner session data and are still constants."* This is the ride-height half.

`RH0 = 0.075` was **one** number for all four corners. Measured against the sessions, it is wrong
for both axles and cannot express rake at all:

| session | ibt RideHeight mm (LF/RF/LR/RR) |
|---|---|
| Nordschleife (×6 captures) | 82.9 / 82.9 / **105.2 / 105.2** |
| skidpad (×3) | 86.7 / 92.1 / 102.7 / 108.3 |

Every session is **raked** — rear 22 mm higher than front on the circuit — and the skidpad is
asymmetric as well. The shipped 75 mm matched **no corner of any session**.

`set_ride_height!(fl, fr, rl, rr)` joins `set_transmission!`, `set_mass!` and `set_suspension!`, and
`drive_native_mtk.jl` installs all four from the same session and prints where each came from.

⚠️ **Scope, stated honestly: this is a TELEMETRY defect, not a handling one.** `c.rh` feeds only the
exported `LF/RF/LR/RRrideHeight` channels (`drive_native_mtk.jl:5485`); it is not read by the
physics. The cost is that every ride-height comparison against a reference ibt — which is exactly
what `ibt_compare.jl` exists to do — was measured off a baseline that was wrong by 8 mm at the front
and 30 mm at the rear, and rakeless where the real car is raked.

Gated in `transmission_smoke.jl`: 9 sessions carry four RideHeights, they vary between sessions,
**every session is raked** (so a single shared constant cannot pass), the live `RIDE_H` equals the
installed session's, and **the shipped 75 mm matched no corner of it**. Rubbish heights are refused.

⚠️ Still frozen: `camber_deg` (Nordschleife −0.4/−0.4/−0.5/−0.5, skidpad +0.5/−0.5/+0.3/−0.5 — sign
changes across the car). Same shape again; not done here.

### E100-S6 (2026-08-31) — camber is not "still frozen": it is NOT MODELLED, so wiring it would change nothing

E100-S4 and S5 both signed off with *"still frozen: `camber_deg`"*, which reads like a third wiring
job waiting to be done. It is not, and a sprint that took it at face value would have added a setter
feeding nothing.

`camber_deg` is read from the ibt by `setup.jl` and has **no consumer on the live path**:

* the only camber term in the codebase is `Fz*Cγ*γ` in `components/tyre_thermal.jl`;
* `tyre_thermal.jl` and `thermal_vehicle.jl` are included **only by `test/`** — `test_tyre_thermal.jl`
  and `test_thermal_vehicle.jl`;
* the sim's chain is `drive_rt3d.jl` → `for f in ("tyre.jl","powertrain.jl","vehicle_3d.jl")`, and
  **`tyre.jl` contains no camber term at all** (no `γ`, no `camber`).

So the running car has no camber input to install one into. The correct entry is not "frozen
constant" but **"unmodelled parameter"** — a much bigger and quite different piece of work
(a camber-sensitive tyre), and one nobody has asked for.

Recorded so the note in S4/S5 stops advertising a wiring job that does not exist. The genuinely
frozen-and-wired trio is closed: **gearbox (E100), mass (E100-S2), spring rates (E100-S4), static
ride height (E100-S5)** — all four now installed from the session and reported with their source.

### E102 (PO 2026-08-31) — 🔴 the rear axles point OUTWARD AND DOWNWARD from the wheels; they must be HORIZONTAL

PO, verbatim: *"julia car axles should be horizontal between center of wheel and chassis, not sticks
pointing outward and downward from the back wheels."*

**This is a defect in E82-S3's own fix, reported against the shipped build.** That sprint restored
the driveshafts by trimming them at the drawn wheel plane instead of dropping them, and the capture
I judged it on (`parity/e82_s3/compare.png`, bottom panel) showed a shaft running from the gearbox
out to the hub. The PO is looking at the same geometry and sees **sticks angled outward and down**,
which the capture does not refute — a shaft that starts inboard-high and ends outboard-low reads
exactly that way from the chase camera, and I called it "reaching the hub" without checking its
ELEVATION at either end.

**Acceptance:** the axle runs **horizontally** from the chassis/gearbox to the **centre of the
wheel** — same height at both ends, at hub height. Not angled down, not projecting past the wheel.

**Where to look, and what NOT to assume:**
* `demo/native/susp_pose.jl` — `rsfix` places the rear halves. `RS_ROLL_DEG` is 0 (E82-S1 measured
  the positioner already poses them); the remaining suspects are the `y0`/`z0` offsets
  (`JM_RS_Y0=0.02`, `JM_RS_Z0=0.772`) and the per-corner draw placement.
* ⚠️ **`JM_RS_Z0` is 0.772 but the wheels are DRAWN at half-track `WTRACK_R` = 0.74** (E82-S3). The
  same frame confusion that made the gate certify protruding rods may also be tilting the shaft:
  if the hub end is placed at 0.772 while the wheel centre is at 0.74, the shaft is aimed 3 cm past
  the wheel and any height mismatch shows as a downward angle.
* **Measure the shaft's y at BOTH ends before changing anything**, and state the expected numbers
  first. `susp_pose_smoke` currently asserts only |z| bounds and a y RANGE for the whole group — it
  cannot see a tilt, which is why this reached the PO. The gate needs a per-part elevation check.

⚠️ Do not close this on a geometry table. E82-S3 passed its gate twice while being wrong on screen;
this one is judged in the chase view.

### E103 (PO 2026-08-31) — 🔴 losing wheels in a collision HYPERSPACES the car back to the start line

PO, verbatim: *"when wheels come off during a collision, the car stops dead there the impact
happened. It does not hyperspace back to the start line, which is the current behavior."*

Current behaviour teleports the car to the start line when wheels detach. Required: **the car stops
where it was hit and stays there.** That is the same principle as E95/E96 — *"you hit something
hard, your race is over"*, *"the car should never bounce back, ever"* — extended to the wreck's
aftermath: a wreck ENDS where it happened, it does not relocate.

**Acceptance:**
1. A collision that detaches a wheel leaves the car at the impact site, motion damped to zero.
2. No teleport, respawn or reset of position is triggered by wheel loss.
3. Position is preserved for the rest of the session — the wreck stays visible where it occurred.
4. Deliberate `R` (respawn) / ⇧R (recover-to-track) are UNAFFECTED: those are the player asking.

**Where to look:** the wreck latch (`WRECKED[]`, `drive_rt3d.jl`) and the damage/detach path
(`damage_hit!`/`damage_impact!`), then whatever calls `respawn3d!` — that is the prime suspect for
the teleport, and the question is what condition reaches it on wheel loss. E99's wreck rule and
E94-P4's per-corner damage are the neighbouring code.

⚠️ Check whether the teleport is the WRECK path or a containment/failsafe path (`contain3d!`,
world-edge fence) firing on the wreck's low speed or odd pose — they would need different fixes, and
the boundary gate's failsafe has been mistaken for game logic before.

### E104 (PO 2026-08-31, seen in the Watkins race) — 🔴 every car FLOATS 20–40 cm above the road, and going off-road produces elastic levitating/bouncing

PO, verbatim: *"at watkin's glenn all cars are displayed as floating about 20 cm - 40 cm above the
road, elastic collisions (if any) if a car goes off the road, leading to levitating and bouncing."*

**Two symptoms, and they are probably NOT one bug.** Recorded together because the PO saw them
together, but they have different suspects and must not be collapsed into a single hypothesis:

**(a) Every car floats 20–40 cm above the road.** Affects *all* cars, player and AI, so it is a
placement/draw-height issue rather than a per-car physics state. 20–40 cm is roughly a wheel radius
(`Rw_f = 0.30`, `Rw_r = 0.33`), which makes a **double-counted wheel radius** the first thing to
test: a body drawn at `terrain + Rw` when the model origin is already at hub height would float by
exactly that. Look at the car draw placement against `hat3d(TERRAIN, …)` and at whether the chassis
origin is hub-height or ground-height in the 3DO.

⚠️ **Ruled out already: E100-S5.** Static ride height changed today (75 mm → 82.9/105.2 mm from the
ibt), which is temporally suspicious. It is not the cause: `RIDE_H`/`c.rh` appear only in the struct
init, the telemetry computation and the `.ibt` export rows — **nothing in the render path** — and
3 cm is the wrong order of magnitude for 20–40 cm anyway. Checked rather than assumed.

**(b) Off-road contact is elastic — levitating and bouncing.** `JM_WHEEL_REST = 0.35`
(`drive_native_mtk.jl:1613`, *"wheel/wall restitution (<1 = inelastic)"*) is a **non-zero
restitution on the wheel/wall path**. E96 established the PO's rule as an absolute — *"the car should
never bounce back, ever"* — and E96-S5 proved the **car-body** contact obeys it at every approach
speed from 5 to 80 m/s. **The wheel path was never covered by that work**, and 0.35 is precisely the
"lossy but springy" behaviour the PO is describing.

⚠️ **Do NOT assume the two halves share a cause, and do not assume this is only `WHEEL_REST`:**
* **E86 precedent** — Spa's levitate/bounce turned out to be **20 INVISIBLE collidable houses**. If
  Watkins has solids off-road that are not drawn, the car bounces off nothing visible, which reads
  exactly like this report.
* **E90 tension** — Monza and Watkins were measured to have *almost no collidable barrier objects*.
  If that is still true, then whatever the car is hitting off-road is terrain or an invisible solid,
  not a barrier — and that changes the fix.
* The world-edge fence (`contain3d!`) and the boundary failsafe have been mistaken for game logic in
  this codebase before.

**Acceptance:** (1) cars sit ON the road with the tyre contact patch at the surface, on all tracks;
(2) leaving the road produces no bounce and no levitation — consistent with E96's absolute.

**First step is a capture, not a code read.** The floating is a visual claim and this backlog has
twice certified geometry that was wrong on screen (E82-S3, and the susp_pose gate's frame). Take a
Watkins chase shot on the road and one off it, measure the wheel-to-terrain gap, and state the
expected numbers before the run.

### E105 (PO 2026-08-31) — 🔴 a SETUP TAB, allowing modest changes to the chassis values easiest to set in the physics model

PO, verbatim: *"setup tab, allowing modest changes to whatever chassis setup values are easiest to
set in the physics model."*

✅ **THE PO HAS CONFIRMED THIS AMENDS THE ORIGINAL RULE (2026-08-31):** *"yes, this is a
modification of the original 'lock physics to .ibt' rule. Make it easy to return to default."*

So the 2026-08-27 instruction — *"the car physics should be determined entirely by the iracing ibt
data, there should be no modifiable parameters"* — **is now amended, not worked around.** The amended
rule, to be treated as standing from here:

> **The ibt session is the SOURCE and the DEFAULT for car physics. The player may make modest setup
> changes from it, and returning to the session's values must be EASY and OBVIOUS.**

What does *not* change: the ibt remains the origin of every value, a silent divergence from it is
still the failure mode E100 exists to prevent, and this is **not** a licence to reintroduce tuning
knobs elsewhere in the physics (`JM_BRAKE_MAX`/`JM_BRAKE_BIAS` stay removed).

**The easiest values are already known, because E100 wired exactly them.** Each has a setter that
must run before the car is built, validates its input, and prints its provenance:

| value | setter | per corner? | notes |
|---|---|---|---|
| spring rates | `set_suspension!` | yes (FL/FR/RL/RR) | E100-S4. `wheel_rate(N/mm)` holds the units + motion ratio |
| static ride height | `set_ride_height!` | yes | E100-S5. **Telemetry only** — changing it will not alter handling, so it must not be presented as if it does |
| gearbox ratios + final drive | `set_transmission!` | n/a | E100 |
| mass + front share | `set_mass!` | n/a | E100-S2, derived from CornerWeights |

**Not easy, and the tab should NOT offer them without new physics:**
* **camber** — read from the ibt but **NOT MODELLED** (E100-S6): the live tyre has no camber term at
  all. A slider here would move nothing.
* **tyre pressures** — only the thermal tyre models pressure, and that file is loaded by `test/`
  only, not the live sim.
* **brake bias / `Tbrake_max` / `CdA`** — constants, deliberately, under the standing constraint.

**Design notes:**
* **There is no UI framework to hang a tab on.** The only front end today is `choose_track()`, a
  `readline()` menu on stdin (`drive_native_mtk.jl:64`). A "tab" therefore means either extending
  that text menu or building an in-window screen — a real decision the PO should make, not one to
  assume. Cheapest useful version is a pre-race text screen listing the session's values with
  ±modest deltas.
* **Defaults must remain the ibt session's values**, so "touch nothing" reproduces today's car
  exactly and no existing capture or gate moves.
* Keep the provenance line printing (`<- <session>.ibt`), and say when a value has been **modified
  from** the session rather than read from it — a silent divergence from the reference is the exact
  failure E100 exists to prevent.
* **Ranges should be modest and validated.** The setters already reject non-positive values; the tab
  should clamp to a sane band around the session value rather than exposing the full range.

**Acceptance:**
1. A pre-race screen exposes at least spring rates and gearbox ratios as modest deltas from the
   loaded session, and the car is built with them.
2. The provenance line distinguishes **"from the ibt"** from **"modified by the player"**.
3. ⭐ **RETURN TO DEFAULT IS EASY AND OBVIOUS** (PO 2026-08-31, explicit). Both scopes:
   * **reset ONE value** to the session's number, without having to remember what it was;
   * **reset EVERYTHING** to the session in a single action.
   The session's own value stays displayed beside the player's, so "what was it?" never needs
   answering from memory — and a car that has been reset must be **byte-identical** to one that was
   never touched, not merely close. That is gateable: build both and compare the installed values.

### E85-S1 (2026-08-31) — ✅ sprint 1 done: car poses cross two processes, exactly, both ways

The epic's own first sprint: *"Two processes, one car each, same track — poses on the wire. UDP,
host + one client, fixed low tick rate."* Delivered as `demo/native/netplay.jl` (the transport),
`demo/native/netplay_probe.jl` (host/join/solo) and `JuliaMotorMTK/tools/netplay_smoke.jl` (the
gate, now in the suite).

```
control: no peer -> nothing received   PASS
host received the client's poses       PASS   rx=20 dropped=0 sent=20  maxerr=0.0000
client received the host's poses       PASS   rx=20 dropped=0 sent=20  maxerr=0.0000
```

Poses are compared against a known non-trivial trajectory, so a zeroed or truncated payload cannot
pass; `maxerr=0.0000` is exact agreement on x/y/z/yaw. The **solo** arm is the negative control and
is what makes the rest mean anything — it proves the probe can report ZERO.

🔒 **The physics directive is untouched, and that is enforced by what the module does not import.**
`netplay.jl` reaches nothing in `Car3D`, `vehicle_3d.jl` or `powertrain.jl`. A remote car is a
received pose.

⭐ **THE BUG WORTH REMEMBERING: in Julia/libuv, `send` on a UDPSocket with a pending `recvfrom`
CANCELS that receive.** The host — which receives before it ever sends — worked perfectly and took
all 20 packets. The client, which sends first, killed its own reader on its first send and reported
**`rx=0 dropped=0` with a live reader task and no error**: not "packets rejected", not "reader
died", simply permanent deafness. It presented as a one-way transport.

Found by reproducing it with raw sockets outside the module and then **inverting the order** —
starting the reader *after* the first send makes the identical code work. Fix: **two sockets per
peer**, `rsock` bound and receive-only, `ssock` unbound and send-only. Because `ssock`'s source port
is then ephemeral, every packet carries the sender's **listen port**, and that is what a host learns
a peer by. Verified 5/5 bidirectional where it had been 0/5.

⚠️ **Two of my own test-shape errors nearly hid this, and both are worth keeping:**
1. The first probe had the host *wait* for the client and only then echo. Julia's startup meant the
   client's packets landed after the wait expired, so the echo loop ran with an **empty peer list**
   and sent nothing — host `rx=20`, client `rx=0`. That is a one-way TEST, not a one-way transport,
   and the two look identical in the output.
2. Top-level `while` loops in the probe hit Julia's soft-scope rule (`i += 1` became a new local and
   threw `UndefVarError`). Each arm is now a function.

**Next (sprint 2):** dead reckoning + jitter — extrapolate between packets and measure the position
error at a realistic packet rate. **State the expected error before measuring it.**

### E105-S1 (2026-09-01) — ✅ the setup tab's VALUES and RESET are built and gated; the UI shell is still the PO's call

The PO amended the physics rule and attached one condition — *"Make it easy to return to default."*
That condition is the part with teeth, so it is what the gate asserts, **exactly**.

`demo/native/setup_tab.jl` holds session and current values **separately**, so reset is a copy and
can never fail because a file moved. Deltas are percentages **of the session value**, clamped to
±15%, so repeated nudges cannot walk past the band and "+5%" always means the same car. Reset works
at both scopes the PO named: one value, or everything.

Wired into the sim between the session install and the car build — it has to be there, because the
rates and ratios are MTK parameters baked in at construction. `JM_SETUP="springs=+5,ride=-3"`;
`JM_SETUP=reset` or unset gives the session's car. Verified live on Monza, three arms:

| arm | printed |
|---|---|
| unset | `setup: session default (unmodified)` |
| `springs=+5,ride=-3` | `setup: MODIFIED by the player — JM_SETUP=reset restores the session` |
| `reset` | `setup: session default (unmodified)` |

`setup_tab_smoke` (in the suite) asserts 14 properties, and the reset ones use `===`: **a reset car
must be byte-identical to one never touched, not merely close.** "Close to the session" is the real
failure mode — it turns the tab into a one-way door away from the reference, which is what E100
exists to prevent. Also asserted: the session values are never overwritten, a modified setup reports
itself modified, per-corner edits touch only that corner, and **camber and tyre pressure are
REFUSED** — E100-S6 established camber is not modelled and the thermal tyre is not on the live path,
so a control for either would move nothing, which is worse than no control.

⚠️ **Not done, and it is the PO's decision:** the tab has no UI. `choose_track()` — a `readline()`
menu on stdin — is the only front end this sim has, so a "tab" means either extending that or
building an in-window screen. The values and reset semantics are settled and gated either way; only
the shell is open.

⚠️ Two of my own errors worth keeping: `describe` first told the player to *"press R"*, an
instruction that does not work — worse than none, since it makes the way back look available when
it is not. And the gate's camber check read FAIL on working code, because a `try/catch` at top level
hits Julia's soft-scope rule and `threw` became a new local; the check is a function now. That is
the same trap that bit the netplay probe earlier the same night.

### E104-S1 (2026-09-01) — ✅ half (b) ROOT-CAUSED AND FIXED: an "off the terrain" sentinel was reaching the physics

PO: *"elastic collisions (if any) if a car goes off the road, leading to levitating and bouncing."*

**It is not a collision at all.** `groundz` reports "off the terrain mesh" as the sentinel **−999**,
and render-side callers test it as `gz > -900f0`, so the sentinel is load-bearing and correct there.
But `drive_rt3d.jl:454` guards the height it receives with

```julia
h = groundz(wx, wz);  isfinite(h) ? Float64(h) : c.zref
```

and **−999 is finite.** It sails through the guard, the wheel is told the ground is 999 m below it,
the suspension goes to full droop, the car falls — and the next sample that IS on the mesh slams it
back. Levitating and bouncing, with nothing hit. **The guard was written to catch exactly this case
and checks the wrong property.**

**Measured, both arms** (`JuliaMotorMTK/tools/offroad_smoke.jl`, in the suite — a physics test, no
display needed):

| ground query off-mesh | vertical travel |
|---|---|
| **−999 (the old path)** | y −14.1 … +6.8 → **20.9 m** |
| **NaN (a real "unknown")** | y −0.0 … 0.0 → **0.00 m** |

Fix: the physics is fed through `groundz_phys`, which maps the sentinel to `NaN` so the existing
`isfinite` guard rejects it as designed and the car keeps its own `zref`. Renderers keep the
sentinel — several depend on it. All six physics call sites now use the wrapper.
`JM_GZ_SENTINEL=1` restores the old behaviour as the negative control.

⚠️ **The sentinel arm is the control and MUST misbehave.** If both arms were quiet the guard would
not be the mechanism and the gate would be testing nothing.

⚠️ **CORRECTION to E104 as filed:** it named `JM_WHEEL_REST = 0.35` as the suspect for the elastic
behaviour. **That is wrong** — `WHEEL_REST` scales the velocity given to a **detached wheel** flying
off after a wreck (`drive_native_mtk.jl:1726`, inside the loose-wheel push). It never touches the
car's own contact response, which E96-S5 already proved inelastic from 5 to 80 m/s. Anyone chasing
it would have found a correct value doing an unrelated job.

**Still open — half (a):** cars drawn floating 20–40 cm above the road. Untouched by this fix: a
20–40 cm offset is the wrong order of magnitude for a 999 m sentinel, it affects cars *on* the road,
and it is a draw-height question. Needs a capture, which needs the display.

### E103-S1 (2026-09-01) — ✅ found the hyperspace: the containment seal PLACES the car at its last on-track point

PO: *"when wheels come off during a collision, the car stops dead where the impact happened. It does
not hyperspace back to the start line, which is the current behavior."*

**The teleport is `containX!(cs, LASTGX[], LASTGZ[])`.** `contain3d!` does not push — it PLACES:

```julia
c.s_pos(c.integ, [xnew, znew]); c.x = xnew; c.z = znew
```

and `(LASTGX, LASTGZ)` is the last position that was **on track**, which stops updating the moment
the car leaves the terrain mesh. **Both are initialised to the spawn point**, so a car that wrecks
before ever registering on-track is sealed to the start line — precisely the report.

⚠️ **E95g had already seen the symptom and fixed the wrong half.** Its note reads *"the car escaped
the world, got caught somewhere else and was flung back to the start, over and over: the PO's
infinite loop"* — and it changed the ENERGY of the seal (`vdamp = 0` for a wreck) without changing
**where** the seal puts the car. The flinging was never about energy.

**Fix:** a wreck is sealed **where it lies**; a driveable car is still rescued to its last on-track
point, because that is a rescue and the race continues. The rule lives in `demo/native/wreck_seal.jl`
and the sim calls it, so the gate tests the sim's rule rather than a copy — S371 caught a gate here
carrying its own drifted reimplementation of the wreck rule, and *"a gate asserting its own
reimplementation tests nothing about the sim."*

`wreck_seal_smoke` (in the suite, no display needed) asserts: a wreck seals at the impact site,
**882 m from spawn** in the modelled case; a driveable car is still rescued; `JM_WRECK_SEAL_BACK=1`
reproduces the hyperspace on demand as the negative control; and — the assumption everything else
rests on — **`contain3d!` really does teleport** (x 100.0 → 7.0), because if it merely pushed, where
it is pointed would not matter and this whole item would be moot.

⚠️ **Not yet seen in a real wreck.** This is the mechanism and its rule, gated headlessly. Confirming
it end to end means wrecking a car on track and watching where it comes to rest, which needs the
display. Suite **18/18**.

### E102-S1 (2026-09-01) — ⭐ measured: the WHOLE rear assembly sits ~0.3 m below the wheel centre, and that may be E104(a) too

PO: *"axles should be horizontal between center of wheel and chassis, not sticks pointing outward
and downward from the back wheels."*

**The shaft does point downward, measured:** `axlelot` drops **0.1095 m** from its inboard end
(mean y 0.174) to its outboard end (mean y 0.065). So the PO's description is exact.

**But the tilt is not the whole defect, and fixing the tilt alone would have been wrong.** The hub is
at a known height: `wheelmat(wx,wz,steer,r) = carModel * translate([wx, r, wz])` places each wheel at
**y = r = 0.34**. Against that, every part of the rear group:

| part | mean y | vs hub (0.34) |
|---|---|---|
| lbrdisc (brake disc) | 0.037 | **−0.303** |
| frontlot | 0.061 | −0.279 |
| (untextured) | 0.060 | −0.280 |
| axlelot (driveshaft) | 0.067 | −0.273 |
| lsusp6 | 0.084 | −0.256 |
| lsusp2 | 0.238 | −0.102 |

⭐ **`lbrdisc` is the oracle: a brake disc is concentric with its wheel by construction.** It is
**0.303 m below** where the wheel is drawn. So this is not a mis-authored driveshaft — **the rear
assembly and the wheels disagree about where the hub is, by about 0.3 m.**

⚠️ **AND THAT IS THE ORDER OF MAGNITUDE OF E104(a).** The PO separately reports *"all cars are
displayed as floating about 20 cm – 40 cm above the road"*. A ~0.3 m mismatch between wheel
placement (`y = r`) and the body/suspension model space would show as exactly that: wheels drawn
high relative to the body, the body appearing to hover. **The two reports may be one defect.** Filed
as a hypothesis, not a finding — it is consistent with both, which is not the same as proven.

**What would settle it, and it needs no display:** find where the body model's ground reference is.
If the chassis origin is at hub height rather than at the contact patch, then `translate([wx, r, wz])`
is adding a radius that is already there. Compare the body mesh's lowest vertex against 0 and
against −0.34.

⚠️ **Do NOT "fix" this by tilting the driveshaft level.** That would put a level shaft 0.3 m below
the hub it is supposed to reach, and the gate would pass it. The tilt is a symptom of the offset.

### E102-S2 (2026-09-01) — 🔴 **S1 IS WRONG AND IS WITHDRAWN.** The assembly is correctly placed; the shaft's CHASSIS end is 13 cm too high

**S1 claimed the whole rear assembly sits ~0.3 m below the hub, and offered that as a possible
single cause for E104(a) as well. Both claims are withdrawn — the measurement omitted a transform.**

The rear suspension is drawn with **`bodyModel * RSFIX_A`**, and `bodyModel = tiltModel *
translate(BODY_OFF)` where **`BODY_OFF = [-0.55, 0.30, 0.0]`** — its own comment reads *"centre body
on X, **lift onto the wheels**"*. S1 measured raw model space and never applied that +0.30. The
"0.3 m too low" was the lift, not a defect.

**With the lift applied, against a hub at y = 0.34:**

| part | mean y | vs hub |
|---|---|---|
| **lbrdisc (brake disc)** | **0.3372** | **−0.0028** |
| frontlot | 0.3607 | +0.021 |
| (untextured) | 0.3601 | +0.020 |
| axlelot | 0.3673 | +0.027 |
| lsusp6 | 0.3838 | +0.044 |
| lsusp2 | 0.5375 | +0.198 |

⭐ **The brake disc lands within 2.8 mm of the hub.** A brake disc is concentric with its wheel by
construction, so that is a strong validation: **the assembly is placed correctly and the wheels are
placed correctly.** The two agree.

**What survives S1 — and it is the PO's actual complaint — is the TILT**, which is a relative
measurement inside one part and so is unaffected by any uniform offset:

* driveshaft **hub end**: y 0.3647 — **+0.025 above the hub, near enough right**
* driveshaft **chassis end**: y 0.4742 — **+0.134, i.e. 13 cm too high**
* drop across the shaft: **0.1095 m**

**So the fix is to bring the INBOARD end down to hub height, not to move the group.** The shaft
should run level from the gearbox to the hub; today it starts 13 cm high at the chassis and slopes
down to meet a hub that is in the right place. That is exactly *"sticks pointing outward and
downward from the back wheels"*.

⚠️ **E104(a) loses its proposed explanation.** S1 offered the 0.3 m as a possible single cause for
the floating cars; there is no 0.3 m. The wheel model is centred on its own origin (−0.336…+0.336)
and `wheelmat` places it at y = r = 0.34, putting its contact patch at **0.004** — on the ground.
E104(a) needs its own investigation and probably a capture.

⚠️ **Why this went wrong, worth keeping:** S1 compared numbers from two different coordinate spaces
and did not check that they were in the same one. The brake disc was even used *as an oracle* — the
right instinct — but against an unlifted figure, so the oracle "confirmed" a defect that was not
there. **When a part is drawn through a chain of matrices, measure it through the same chain.**

### E102-S3 (2026-09-01) — ⚠️ S2's tilt figure is ALSO an artifact. `axlelot` is not one part, and I should stop slicing geometry by texture

S2 corrected S1 and then made the same class of mistake one level down. **The 0.1095 m "tilt" and
the "chassis end 13 cm too high" are both artifacts of treating one TEXTURE as one PART.**

Clustering `axlelot`'s 31 triangles by position instead:

| region | n | y range | mean | vs hub (0.34) |
|---|---|---|---|---|
| x −1.30…−1.10 | 4 | 0.304–0.361 | **0.333** | −0.007 |
| x −1.10…−0.95 (the axle line) | 4 | 0.285–0.349 | **0.310** | −0.030 |
| x > −0.95 (forward of the axle) | 23 | 0.278–0.481 | 0.383 | +0.043 |

**The pieces at the axle line — the actual shaft — sit at hub height.** The 23 triangles that
dragged the average up and produced the apparent slope are **forward of the rear axle entirely**,
so they are a different component that happens to share the texture (gearbox/housing). A linear fit
across all of them gives −26.8°, which is a number about nothing.

**So E102 has now produced two confident wrong answers from me**: S1 (whole assembly 0.3 m low —
omitted `BODY_OFF`) and S2 (shaft tilted, chassis end 13 cm high — conflated components). Both were
measurements; neither was the wrong *kind* of work; both sliced the model along an axis that does
not correspond to the object being described.

**What is actually established, and it is not nothing:**
* the rear assembly and the wheels agree — `lbrdisc` within **2.8 mm** of the hub;
* the shaft geometry at the axle line is at hub height;
* `axlelot` spans at least two distinct components, so **any per-texture statistic about it is
  meaningless** and the three published in S1/S2 should not be quoted.

⚠️ **STOP MEASURING THIS BY TEXTURE.** The next step is either proper connected-component analysis
(cluster triangles by shared vertices, then measure each solid separately) or — far cheaper — **a
chase capture, which is how the PO reported it in the first place.** E82-S3's two failed attempts
were caught the same way: by looking, after the geometry had said they were fine.

### E102-S4 (2026-09-01) — connected-component analysis: the assembly is ONE mesh, but a 3-triangle sliver matches the report exactly

The method S3 said to use instead of texture slicing: union-find over triangles sharing a vertex
(quantised to 1 mm), then measure each **connected solid** separately. 89 triangles → **5 solids**:

| n | x | y | \|lat\| | drop | textures |
|---|---|---|---|---|---|
| **65** | −1.48…−0.75 | 0.220…0.552 | 0.42…0.74 | 0.332 | axlelot, lbrdisc, lsusp2, lsusp6, untextured |
| 17 | −1.06…−0.94 | 0.258…0.460 | 0.54…0.60 | 0.202 | frontlot |
| **3** | **−1.48…−0.86** | **0.283…0.382** | **0.53…0.74** | **0.099** | **axlelot** |
| 2 | −1.04…−0.73 | 0.177…0.483 | 0.58…0.59 | 0.306 | lbrdisc |
| 2 | −1.04…−0.73 | 0.177…0.483 | 0.60…0.61 | 0.306 | lbrdisc |

**Two conclusions, and the first closes off a whole line of work.**

**1. There is no separable "driveshaft" to level.** 65 of the 89 triangles are ONE connected mesh
spanning five textures — brake disc, links and shaft are a single solid. So "rotate the shaft about
the hub to make it horizontal" is not implementable as posed: there is no shaft to rotate. That
retires the fix S2 proposed, on top of S3 retiring its diagnosis.

**2. ⭐ But the 3-triangle `axlelot` component is exactly the shape the PO describes.** It is
separable, it is **thin** (3 triangles spanning 0.62 m in x), it reaches **|lat| 0.74 — the wheel
plane** — and it **drops 0.099 m** across that run. A thin isolated sliver reaching out to the wheel
and sloping down is *"sticks pointing outward and downward from the back wheels"*, almost verbatim.

⚠️ **Still a candidate, not a finding.** It is consistent with the report and it is the only
separable piece that is, but consistency is not identification — S1 and S2 were both consistent with
the report too. **What settles it is one chase capture**, with this component drawn in isolation
(`JM_RS_ONLY=axlelot` already exists for exactly that kind of A/B).

**Three headless approaches have now been spent on E102** — per-texture statistics, positional
binning, connected components. The third is the one that produced something usable, and it says the
remaining question is visual. **Do not open a fourth: capture it.**

### E103-S2 / TOOLING (2026-09-01) — 🔴 **I shipped a sim that would not load, and my parse check could never have caught it**

Found by accident: a capture run died with `ParseError` at `drive_native_mtk.jl:5551`. **E103-S1's
edit had joined two statements onto one line** — the replacement consumed a newline — so the sim
has not loaded since that commit, four sprints ago. It was committed and pushed.

**Two failures made that possible, and the second is worse than the first.**

**1. No gate loads the main sim file.** The suite stayed **18/18 green** throughout, because every
gate exercises `JuliaMotorMTK` modules and small shared includes. The 5,900-line file the game
actually runs was covered by nothing.

**2. ⚠️ `Meta.parseall` DOES NOT THROW on a syntax error.** After every edit I ran

```julia
Meta.parseall(read(f, String)); println("parse ok")
```

and it printed "parse ok" every time — **including on the broken file**. Measured directly: given
`"function f()\n  x = 1\n"` (no `end`) it returns an `Expr` normally, and the top-level args do not
even contain a direct `:error` node; the error is nested. **The check could not fail.** It gave the
same output for valid and invalid input, and I quoted it as evidence a dozen times.

**Fixed:** the line is split, and `JuliaMotorMTK/tools/parse_smoke.jl` now **walks** the parse tree
for `:error`/`:incomplete` nodes across all **110** `.jl` files, and runs **first** in the suite.
It **self-tests before it scans** — it must reject known-bad syntax and accept known-good, printed
every run — because the whole reason it exists is that the previous check could not fail.

⭐ **It immediately found a second, pre-existing break:** `demo/native/render_obj.jl` had a trailing
comment sitting **between the `?` branch and the `:`** of a ternary, so that tool has been
unparseable for some time. Nothing includes it, so nothing noticed. Also fixed.

Suite now **19/19**.

### E102-S5 (2026-09-01) — ✅ **IDENTIFIED ON SCREEN: the "sticks" are `axlelot`, and julia captures never needed the display lock**

Two results, and the second one unblocks a queue I had been treating as blocked for nineteen sprints.

**1. ⭐ The capture confirms the PO exactly.** `parity/e102/e102_rear.png` — Watkins, chase view —
shows **two chrome sticks protruding from behind each rear wheel, angling outward and downward to
the road.** *"Sticks pointing outward and downward from the back wheels"*, verbatim.

**And `JM_RS_ONLY=axlelot` identifies them** (`parity/e102/e102_only.png`): with only that texture
drawn in the rear group the sticks remain — longer, since that path bypasses the E82-S3 trim — and
nothing else does. **So S4's 3-triangle `axlelot` sliver is the culprit**, promoted from candidate
to identified. Three headless approaches could not settle this; one capture did, in one run.

**2. ⚠️ Julia captures do NOT need `gl-lock`.** The sim creates its window **hidden**
(`GLFW.VISIBLE, false`) and `JM_SHOTS` reads the framebuffer with `glReadPixels`. This capture ran
**alongside the PO's live BoB session**, no lock, no interference. E102 and E104(a) were never
display-blocked; I assumed they were and never tested the assumption — the same error as
`parity_2d` (headless all along) and BoB's four gates (guarded, not blocked).

⚠️ **AND THE ATTEMPT EXPOSED TWO REAL DEFECTS I HAD SHIPPED:**
* the sim would not load at all — E103's edit had joined two statements (fixed, and
  `parse_smoke` now guards it);
* **E104-S1's `groundz_phys` was defined in the wrong scope** and threw `UndefVarError` at runtime.
  There are **TWO `groundz`** in this file: a local one at :2407 inside a `let` (object placement,
  returns the −999 sentinel) and **`function groundz` at :4503**, which the render loop actually
  uses — and which **never returns −999**: off the HAT it holds `LASTZ[]` and clears `ONTRACK`.
  **So E104(b)'s diagnosis was wrong for the sim and its fix was inert.** Reverted; the physics
  points at the live `groundz` again. `offroad_smoke` still tests a real robustness property of
  `drive_rt3d` (a sentinel WOULD launch the car) but must not be read as describing the sim.
  Same trap the codebase already warns about for `drive_rt.jl` vs `drive_rt3d.jl`: *"two physics
  models, the same function names in both: check which one the sim actually runs."*

**Next:** the sliver is 3 triangles of `axlelot` reaching |lat| 0.74. Decide whether it should be
trimmed harder, excluded, or is mis-posed — with the capture as the oracle, not geometry.

### E104-S2 (2026-09-01) — ⭐ half (a) MECHANISM FOUND: AI cars take their height from the RACING LINE, not the terrain

Captured headlessly (julia needs no display lock — E102-S5). A race at Watkins with 5 AI cars:
`parity/e104/ai_zoom.png` shows an AI car with **a clear gap under its tyres and no contact
shadow** — it is floating, exactly as reported. The player's own car, in the same frame and in the
E102 capture, sits planted.

**That asymmetry is the clue, and the code explains it:**

```julia
aiCar(p) = translate([p[1], p[2], -p[3]]) * ...      # AI height = p[2]
```

and `p[2]` comes from one of two paths:

| path | height source |
|---|---|
| `AI_PHYSICS` | `groundz(pc.x, pc.z)` — **the terrain** |
| rail follower (**the default**) | `RaceAI.pose_at(...)` → `y = line.y[i]` — **the racing line's stored elevation** |

`const AI_PHYSICS = haskey(ENV, "JM_AI_PHYSICS")` — **off unless asked for**, so the rail follower
is what actually runs. And `pose_at` interpolates `line.y` and never samples the terrain.

**So every AI car is drawn at the AI line's height.** The player's car uses `cs.y` from the physics,
which tracks `zref` off the terrain — hence one planted car and five floating ones, which is why
this reads as "all cars" from behind a field.

⚠️ **Suggestive but NOT yet the confirmed cause.** The confirming measurement is one comparison:
**`line.y` against `groundz(x, z)` at the same points along the lap.** If the line sits 0.2–0.4 m
high, that is the defect and its size. The centreline is known to be re-centred laterally onto the
visible road (the loader logs *"re-centred on the visible road … max shift 4.0 m"*) — **whether its
ELEVATION was corrected the same way is exactly the open question.**

⚠️ Do not "fix" this by adding an offset. If `line.y` is wrong, the line is what to correct — or the
AI should sample the terrain like the physics path already does. Three E102 sprints were lost to
adjusting numbers before the object was identified.

### E104-S3 (2026-09-01) — 🔴 BOTH mechanisms REFUTED by measurement, including S2's. And my reading of the capture may itself be wrong

**S2's mechanism is dead.** It proposed that AI cars take their height from the racing line rather
than the terrain. Measured directly in the sim (`JM_LINE_Y=1`, 209 samples round Watkins):

```
line.y - groundz:   min 0.0   median 0.0   max 0.0 m
```

**The AI line's elevation IS the terrain height, exactly.** The rail-follower path places AI cars on
the ground, same as the player.

**The follow-up hypothesis is dead too.** `wheelspec` reuses the Lotus hub geometry for every AI
chassis while each loads its own wheel mesh, so a mismatched radius would float that car. Measured
across all six:

| chassis | front radius | rear radius |
|---|---|---|
| Lotus / Ferrari / Brabham / BRM / Eagle / Cooper | 0.311–0.312 | 0.336 |

against placements of **0.31 front / 0.34 rear** — so every wheel's contact patch is **within 4 mm
of the ground**. Nothing floats by construction.

⚠️ **So the geometry says the cars are planted, and I should be honest that S2's evidence was my own
eye on a 4× upscale of a distant car.** I described "a clear gap under its tyres and no contact
shadow"; at that scale, on a receding road, that reading is not safe. Two measured refutations
against one visual impression means **the impression is now the weakest link**, not the code.

**What E104(a) actually needs next, and it is not another hypothesis:**
1. a capture with a **known scale** — the car close to the camera, ideally side-on, where a 20–40 cm
   gap is tens of pixels rather than three;
2. the PO's own view: he reported it while driving, so **which cars, at what distance, on which
   track** would narrow it far faster than more geometry.

⚠️ Do not open a third mechanism before that. E102 cost three sprints to hypotheses that a single
capture then settled; this item has now cost two.

### E105-S2 (2026-09-01) — ✅ the tab has a front end: it is a step in the track menu, and it is gated

S1 built the values and reset semantics and left the shell as "the PO's decision". On reflection
that was holding an ordinary judgement call for the PO: the request was for a **setup tab**, and the
only front end this sim has is `choose_track()`, a readline menu on stdin. A step in that menu is
the routine reading; an in-window screen would have been a bigger guess, not a smaller one.

**Where it lives matters more than how it looks.** `setup_menu!` is in `SetupTab`, not inline in
`drive_native_mtk.jl`, and takes `input`/`output` as parameters. That file cannot be loaded by a
test — it launches the sim — so a menu written inside it could never be gated, and **E103-S2 is the
standing reminder of what ships when nothing loads the file**: a sim that would not start, through
an 18-gate suite, green. With stream parameters the gate drives the whole tab from an `IOBuffer`.

The PO's condition — *"make it easy to return to default"* — decides the layout:

* `R) reset EVERYTHING to the ibt session` is on screen at **all times**, not inside a submenu;
* every value's own prompt offers `r` for **just that one** — the two scopes S1 gated;
* `describe` reprints before every prompt, so the session value sits **beside** the current one
  while you decide. "What was it?" is never answered from memory.

`JM_SETUP` still works and now **wins**: set to anything (including `reset`), no prompt. So gates,
replays and scripted launches stay deterministic and **nothing can block on stdin** — the menu also
returns on EOF at either prompt, which the gate proves by terminating.

One parser, `apply_spec!`, is shared by the env and the menu, and an arm asserts the two produce the
**same car** — otherwise they drift into meaning different things.

**11 new arms, all passing** (31 in the gate): the menu applies a delta and leaves the *session*
values alone; `R` resets everything `===`; `r` resets one and leaves the others modified; junk input
neither crashes nor applies anything; the ±15% band holds *through the menu* and **says** it
clamped; the way back is visible without asking; and `+5` from the env equals `+5` from the menu.

⚠️ **One arm of mine was worthless and is replaced.** I wrote `is_default(m5) || !is_default(m5)`
to assert "the menu returns on EOF". That is true for every input — an arm that cannot fail is not
an arm, it is decoration that makes the count look better. It now asserts the *value*: the answer
given before EOF survives. The no-hang property is proved by the gate terminating, and the comment
says so rather than pretending a predicate covers it.

⚠️ **`describe` had a stale way-back line** (`JM_SETUP=reset (or unset)`), which was the only way
back when S1 wrote it. It now names `R` too. S1's own lesson was that an instruction which does not
work is worse than none; an instruction that is merely *incomplete* fails the same way once a better
route exists.

### E104-S4 (2026-09-01) — ✅ **E104(a) FOUND, FIXED AND GATED. S2 was right; S3's refutation was too narrow.**

**The measurement nobody had made.** Both the player and every AI car are drawn as
`<car origin> * translate([wx, r, wz])` (`wheelmat` / `aiWheel`), so a wheel meets the road **only
if the car origin's height is the ground height**. That single number had never been printed.
`JM_WHEELGAP=<n>` now prints it, per car, in the render frame the eye is looking at.

Watkins, 5 AI, before the fix:

| | min | median | max | ≥ +0.20 m |
|---|---|---|---|---|
| **AI cars** | −0.192 m | **+0.093 m** | **+0.302 m** | **13 of 45 samples** |
| player | — | **0.000 m** | — | 0 |

That is the PO's *"every car floats 20–40 cm above the road"*, measured. The negatives are the same
bug sinking a car **into** the road.

**The cause is one line in `RaceAI.pose_at`:** it interpolates the centreline's `x, y, z` and then
applies the lane offset **to `x` and `z` only** — `y` is never re-sampled. A car running `lane`
metres to the side is posed at the *centreline's* height, wrong by `lane × cross-slope`. Lanes here
are ±2.4 m, and 2.4 × a ~10 % camber is 0.24 m — the measured range.

⚠️ **So E104-S2's mechanism was RIGHT and E104-S3's refutation of it was WRONG.** S3 measured
`AILINE.y − groundz` **at the line's own points**, where `lane = 0` and the error is zero *by
construction*, and reported `min 0.0 median 0.0 max 0.0` as if it closed the question. It never
sampled a car at its actual laterally-offset position. **A refutation is only as wide as the case it
tested** — and the "0.0 exactly" that made it feel conclusive was the tell, not the proof: an
identity, not a measurement. S3 then concluded my eye was the weakest link and told the next sprint
not to open another mechanism. My eye was right.

**Fix:** `RaceAI.reground(pose, height)` re-grounds a pose at its own `(x, z)`. Applied to both
kinematic draw branches (grid and racing). After: **every AI reads exactly 0.000 m — min, median
and max.**

⚠️ **NOT applied to placement**, only to what is DRAWN — re-anchoring a stuck AI onto the rail
deliberately wants the line's own `y`.

⚠️ **`hat3d`, never `groundz`.** `groundz` **mutates `LASTZ[]` and `ONTRACK[]`**, the *player's*
ground-tracking state. **My first probe called it** — so sampling five AI positions per frame
rewrote the height and on-track flag the player's next physics step reads: an instrument that
changes what it measures. Re-measured through the pure `hat3d` query; the numbers held, but they
were not entitled to.

**Gated: `reground_smoke` (9 arms, suite now 20).** A straight road with a known constant
cross-slope, so the correct height is closed-form and no terrain or sim is needed. It asserts the
correction, that only the height changes, 4- and 6-tuples, that an off-terrain query returns the
pose **untouched**, and — as a **positive control** — that the raw `pose_at` really is off by
`lane × slope`, so the gate goes red instead of passing vacuously if that is ever fixed upstream.
One arm pins S3's own trap: **at lane 0 there is nothing to correct.**

`reground` lives in `ai.jl`, not inline in `drive_native_mtk.jl`, because that file launches the sim
and no test can load it (E103-S2) — the same rule E105-S2 applied to the setup menu.

⚠️ **Still open, and it needs the PO:** this fixes the AI field. If cars still look high after it,
the remaining half is the *player's* car — which measures 0.000 m, so it would be a different
mechanism entirely.

### E85-S2 (2026-09-01) — ✅ dead reckoning, with the expected error stated BEFORE the measurement

S1's closing instruction was *"extrapolate between packets and measure the position error at a
realistic packet rate. **State the expected error before measuring it.**"* So, stated first:

> A remote pose arrives at the packet rate, not the frame rate. At R Hz the newest packet is 0–1/R
> old (mean 1/2R). **Holding** it is a first-order error of `v·age` — at 10 Hz and 60 m/s, **mean
> 3.0 m, max 6.0 m**. **Extrapolating** along the heading cancels that term exactly and leaves only
> curvature, `½·a_lat·age²` — at 1.5 g, **mean ≈0.025 m, max ≈0.075 m**. So: ~100× better in a
> corner, and **exact** on a straight.

Measured:

| | mean | max |
|---|---|---|
| hold | **3.000 m** | **6.000 m** |
| extrapolate | **0.0252 m** | **0.0750 m** |

**118.8×**, and the straight-line arm comes back at `3.6e-15 m` — exact to floating point. The
prediction held to three significant figures, which is the point of stating it first: a number that
merely *looks* small proves nothing, and I would have accepted anything under a metre as a success.

`predict(pose, dt)` is a **pure function**, so the gate drives it against a closed-form
constant-speed arc — no sockets, no second process, no stopwatch. **The error is measured against
analysis, not against another run of the same code.**

Deliberately NOT a filter: no smoothing, no history. A filter would need tuning, would hide the
transport's real behaviour, and would leave the gate with no closed-form expectation to check.

**`netplay_dr_smoke`, 11 arms, suite now 21.** Two are the positive control — the harness must
reproduce `v·age` and `v/R` before any "improvement" against it means anything. Others pin the
shape: `predict(p,0)` and `predict(p,−t)` are no-ops (**clock skew cannot rewind a car**), and speed
and heading are carried rather than invented.

⭐ **`y` is NEVER extrapolated, and that is a cross-item lesson, not a detail.** A remote car's
height must come from the ground beneath it. E104(a), fixed the same day, was exactly this mistake
in the AI field: a height carried from somewhere other than the terrain under the car, which drew
every car 20–40 cm into the air.

**Next (sprint 3):** jitter and loss. Dead reckoning is measured here against a *perfect* 10 Hz
stream; the real question is what happens when packets arrive late, out of order, or not at all.
State the expected behaviour first again — in particular what should happen when a car goes
silent, because extrapolating a missing car forever is how a ghost keeps driving.

### E85-S3 (2026-09-01) — ✅ loss, jitter and silence: the error is quadratic, so extrapolation is capped and a silent car is REMOVED

Stated before running, from the same `½·a·Δt²` S2 confirmed:

> Loss and jitter only make the newest pose **older**, and the error grows with the **square** of
> the gap — one dropped packet at 10 Hz doubles Δt and should **quadruple** the error, 0.075 →
> ~0.30 m, against 12 m for holding. Two dropped packets would be ~9×, which is why extrapolation
> must be **capped**. And **silence is different in kind**: a peer that stops sending is not a peer
> moving predictably.

Measured: **0.0750 → 0.3000 m, exactly 4.0×**, against **12.0 m** for holding at the same age.

**The two failure modes are handled differently, deliberately:**

* **Loss/jitter** needs nothing special — the degradation is graceful and the arm proves it stays
  ~40× better than holding even with a packet gone.
* **Silence** would otherwise produce a **ghost**: a car driving on smoothly, through corners it
  cannot take, into scenery, for the rest of the session. That is worse than showing nothing,
  because it is indistinguishable from a real car right up to the moment you crash into it.

So: extrapolation is capped at **`EXTRAP_MAX = 0.25 s`** (past it the pose **freezes** — a frozen
car is a smaller lie than a confidently wrong one), and past **`STALE_S = 2.0 s`** the peer is
**dropped from the field**. `remote_poses_at` applies both, so a caller cannot forget to. An arm
pins the ordering: **freeze first, then remove** — the cap must be shorter than the timeout.

⚠️ **Two of my arms FAILED, and they were the wrong half.** I asserted that past the cap the
*error* stops growing. It does not, and should not: a frozen pose does not freeze the error,
because the real car keeps moving away from it. The property the cap actually guarantees is about
the **pose**, and that is what is asserted now — identical at 1 s and 2 s, equal to the pose at
`EXTRAP_MAX`, and *having advanced* up to it (so "capped" cannot be satisfied by never moving at
all). **A gate that fails is only useful if you check which half is at fault.**

Suite **21/21**.

**Next (sprint 4):** two real processes rather than one process and analysis — a host and a client
driving the same track, with the packet rate and the observed position disagreement measured on
both sides. State the expected disagreement first: at 10 Hz it should be the S2/S3 figures plus
whatever the loopback adds, and anything larger is a defect in the wiring rather than in the model.

### E85-S4 (2026-09-01) — ✅ dead reckoning measured across TWO REAL PROCESSES, and the wiring adds nothing

S2 and S3 measured `predict` against a closed-form arc **inside one process**. That establishes the
model and is deliberately blind to everything the *wiring* can get wrong: real latency, real jitter,
a peer learned late, a clock read at the wrong moment. So, as S3's note required, this sprint puts
two actual processes on a socket — and states the expectation first:

> On loopback the transport adds sub-millisecond latency, so the host's drawn error should be the
> S2/S3 figure and nothing more: **mean ≈0.025 m, worst ≈0.075 m**, with packet age between 0 and
> 100 ms. Anything materially larger is a **wiring** fault, not a model limit.

Measured, host and client as separate `julia` processes over UDP:

| | age mean | age max | **err mean** | **err max** |
|---|---|---|---|---|
| two processes, 10 Hz | 0.041 s | 0.089 s | **0.0276 m** | **0.0625 m** |

against a predicted 0.025 / 0.075. The client sent **120 packets in 12.0 s — exactly 10.0 Hz**.
**The wiring contributes nothing measurable.**

No shared clock is needed and none is assumed: the client stamps each packet with its own elapsed
milliseconds, and the host reconstructs "where was it when I drew this frame?" as `stamp + age` —
age being the one quantity it already tracks. A gate that needed two clocks agreed would be
measuring the clocks.

**`netplay_dr2_smoke`, 7 arms, suite now 22.** Its thresholds are deliberately **loose** (0.20 m
mean, 1.0 m max) because it exists to catch a wiring fault — which shows up as metres, or as no
samples at all — not to re-measure the model. The tight figures stay in `netplay_dr_smoke`, against
closed form, where no scheduler can perturb them. One arm asserts the error is **non-zero**: a
perfect 0.0 here would mean the comparison compared nothing, which is the failure this shape is
most likely to hide.

**Next (sprint 5):** two processes each running the SIM rather than a probe — the remote car drawn
by `remote_poses_at` in the real render loop, with the E104(a) rule enforced end to end: a remote
car's height must come from the terrain under it, never from the packet.

### E102-S6 (2026-09-01) — 🔴 the 3-triangle sliver is NOT the stick: removing it changes nothing on screen

S4 identified a 3-triangle `axlelot` solid whose measurements match the PO's report almost verbatim —
thin, isolated, reaching the wheel plane at |lat| 0.74, dropping 0.099 m across 0.62 m of x — and S5
confirmed `axlelot` as the texture on screen. This sprint built the only handle that shape offers
and pulled it.

**The tool works exactly as intended.** `min_component=N` drops connected solids below N triangles
(union-find over vertices quantised to 1 mm — S4's own method, now in the extractor), restricted by
texture so the assembly's legitimate small detail is untouched. `JM_MC_DIAG=1` reports it dropping
**precisely one solid: `n=3, x −1.48..−0.86, |lat| 0.53..0.74, ydrop 0.099, tex axlelot`** — S4's
signature to the centimetre, and nothing else.

**And the chase capture with it ON still shows the chrome rod pointing outward and downward from the
rear wheel, unchanged.** So the sliver is not what the PO is looking at. **Default OFF**
(`JM_RSUSP_MINCOMP=4` re-enables); shipping a change that deletes geometry and fixes nothing would
be worse than shipping none.

⚠️ **This is a useful negative, not a wasted sprint — it eliminates the last separable candidate.**
S5 established the sticks are `axlelot`; S6 establishes they are not the *separable* `axlelot` solid.
By elimination the stick is **the driveshaft itself**, inside the 65-triangle connected mesh that
E82-S3 deliberately trims to reach the hub. So the open question is its **POSE** — the angle the
assembly is placed at — and E102-S4's *"there is no separable shaft to rotate"* is the obstacle to
solve rather than the reason to stop.

⚠️ **Two measurement errors of mine, both from working in the wrong frame.**
`extract_gpl_car` returns PARTS with a flat strided vertex array, not triangles. I read
`length(parts)` as a triangle count ("6 triangles"), then `length(verts) ÷ 3` as another
("121 triangles removed") — both meaningless. The diagnostic now lives **inside** the extractor,
where triangles are still triangles, and it reported the true figure immediately: one solid, three
triangles. *The frame the data is in decides whether a measurement means anything* — the same lesson
E104(a) taught in the render frame.

**Next:** measure the driveshaft's angle as drawn against the horizontal, in the render frame — if
the assembly carries a residual rotation our positioner mis-composes (the ±roll E82 notes on these
halves), correcting the pose is what the PO asked for and would leave the geometry intact.

Suite 22/22.

### E85-S5 (2026-09-01) — ✅ **TWO SIMS SEE EACH OTHER: a remote car is drawn, on the ground, in the real render loop**

S1–S4 built the transport, dead reckoning and the staleness policy and gated all of it — and
**nothing in the game used any of it.** `grep netplay drive_native_mtk.jl` returned nothing; a remote
car had never been drawn. This wires it in: `JM_NET=host` / `JM_NET=join` (with `JM_NET_HOST`,
`JM_NET_PORT`, `JM_NET_ID`, `JM_NET_HZ`), off by default so an unset `JM_NET` changes nothing.

Measured, two `julia` processes on Watkins, each with the other's car on screen:

| | rx | peers | known | **drawn** |
|---|---|---|---|---|
| host | 363 | 1 | 1 | **1** |
| client | 380 | 1 | 1 | **1** |

~360 packets over ~40 s ≈ **9 Hz**, against the configured 10. The host's capture shows the client's
Ferrari **on the road ahead**, correctly placed and grounded.

⭐ **The remote car is drawn through the AI field's own path** (`aiBody`/`aiWheel`), so anything true
of an AI car's placement is true of a remote one — including **E104(a)'s rule, enforced at the
receiving end**: `predict` deliberately never extrapolates height, and the packet's `y` is the
*sender's* ground, which is not this machine's ground. Every remote pose goes through `ai_ground`
before it is drawn.

🔴 **The bug that cost this sprint: the socket reader task was NEVER SCHEDULED.**
First run: client `peers=1` (it was sending), host `rx=0 peers=0` (it received nothing, so never
learned a peer, so never replied) — a one-way link. Not a port clash (nothing held 47700, no stale
process) and not the transport (`netplay_dr2_smoke` proves it end to end). The reader is an `@async`
task, and **a Julia task only runs when something yields.** The probe loops `sleep(0.002)` and yields
constantly; the render loop does not sleep at all, so every packet sat in the kernel buffer. One
`yield()` per frame took the host from `rx=0` to `rx=363`.
**A design that works in a probe can fail in the sim for reasons the probe cannot express** — the
probe's `sleep` was load-bearing and invisible.

⭐ **And the staleness policy was observed working, unplanned:** the client's last sample reads
`known=1 drawn=0` — the host had exited, and `STALE_S` dropped it rather than leaving a ghost
driving on. S3 predicted that; here it is in a live run.

⚠️ **I also re-committed a trap this very file warns about.** The `JM_NET_*` constants went in next
to `JM_WHEELGAP`, a thousand lines *below* the `NETLINK` block that reads them. It parsed clean,
passed `parse_smoke`, and died at load with `UndefVarError: NETMODE`. The file already carries that
warning about `WTRACK_R` — *"a forward reference here parses fine and dies at load, which is what
happened"*. **A parse check cannot see an undefined NAME; only running the sim can.**

Suite 22/22.

**Next (sprint 6):** measure the position disagreement between the two SIMS the way S4 measured it
between two probes — each side logging where it thinks the other is against where that side says it
was. State the expected figure first: it should be the S4 envelope (~0.03 m mean) plus whatever the
sim's frame pacing adds over a probe's fixed 10 Hz.

### E85-S6 (2026-09-01) — ⭐ the sim can now DRIVE ITSELF headlessly, which the sim-to-sim measurement needs

S5's next step was to measure the position disagreement between two SIMS the way S4 measured it
between two probes. That turned out to need something the harness did not have: **a way to make the
PLAYER's car move without a human.** `JM_AI_TEST` drives the AI field with *no player at all*, and
every headless capture to date has been of a **stationary** car — fine for a screenshot, useless
here, because a car that is not moving makes dead reckoning trivially exact. The measurement would
have reported an error of 0.000 that meant nothing, which is the "arm that cannot fail" in another
costume.

**`JM_AUTODRIVE=1`** drives the player from the racing line using **the AI's own controller**
against `CLINE` — deliberately the same code the field drives with, so this adds no second driving
model to keep true. `JM_AUTODRIVE_V` sets the target speed (default 45 m/s),
`JM_AUTODRIVE_DIAG=<n>` reports.

Measured on Watkins: **0 → 38.7 → 154.0 km/h**, covering **s 39 → 417 m** of track under its own
throttle and steering.

⚠️ **Its limit, stated rather than discovered later:** it spins at around s 675 m
(`thr=0.0 steer=-1.0 v=3.5 km/h`). That is ~20–30 s of clean driving — enough for a netplay
measurement window and **not** enough to call this a lap-capable autopilot. Do not cite it as one.

🔴 **Two of my own bugs, both in the same call, and both instructive.**
1. I passed **`1.0` as the 10th argument** because I had not read what it was. It is the **YAW
   RATE**, and the controller's anti-spin logic reads ~1 rad/s as a car already sliding — so it
   correctly refused to accelerate a car it believed was spinning. Telemetry showed
   `thr 0.0  kmh 0.0` while steer twitched: **the controller was working perfectly and I had told
   it the car was in a spin.** A placeholder in a parameter whose semantics you have not read is
   not a placeholder, it is a wrong value.
2. The fix reached for **`cs.r`**, which does not exist — the model exposes yaw rate as a
   *function*, `DriveRT3D.yawrate3d` (aliased `AIyaw`), which is what the AI field itself calls.
   `cs.r` would have thrown `FieldError` at runtime; **`parse_smoke` cannot see a missing field**,
   exactly as it cannot see an undefined name (E85-S5, E103-S2).

Suite 22/22.

**Next (sprint 7):** the measurement S5 asked for, now that it can be taken — both sims autodriving,
each logging where it thinks the other is against where that side says it was. **State the expected
figure first:** the S4 envelope (~0.03 m mean, <0.10 m max) plus whatever the sim's frame pacing adds
over a probe's fixed 10 Hz, and bounded by the ~20 s the autodrive stays on track.

### E85-S7 (2026-09-01) — ✅ sim-to-sim prediction error measured, and the aggregate figure is a trap

Stated before the run, from S4's probe-to-probe 0.0276 m mean / 0.0625 max: two autodriving sims
accelerate and corner variably rather than following a constant arc, so **~0.03–0.10 m mean with
peaks of a few tenths**, bounded by the ~20 s S6's autodrive stays on track.

**The measurement needs no clock sync and no log correlation.** When a new packet arrives, compare
where the PREVIOUS packet predicted that car would be at the new packet's tick against where the new
packet says it actually is. Both numbers come from the sender's own clock. That is what let S4's
analytic trajectory be replaced by "whatever the other car really did".

Measured, both sims autodriving on Watkins, correlated against speed:

| phase | speed / control | packets | **err mean** | **err max** |
|---|---|---|---|---|
| **driving cleanly** (t≈10 s) | 57 → 150 km/h, `thr 1.0` | 114 | **0.096 m** | **0.401 m** |
| losing control (t≈21 s) | 124 km/h, `steer −1.0` | 211 | 0.307 m | 1.99 m |
| spun, stopped (t≈31 s) | 3.6 km/h, stuck at s 624 | 314 | 0.590 m | 2.89 m |

Packet interval **0.104 s** throughout — the 10 Hz send rate holds even while the car is out of
control.

**So the prediction was right for the regime it described, and the aggregate is a trap.** A single
mean over the whole run reads **0.52 m** and reports the CRASH, not the model. Had I quoted that one
number, I would have concluded dead reckoning was five times worse than S4 measured; had I quoted
only the clean phase I would have hidden a real weakness. Both belong in the record.

⭐ **The real finding is where the model fails.** Dead reckoning assumes constant velocity along the
heading, and a spinning car violates that completely — so the error is worst **exactly when a car is
out of control**, which is also when it is most likely to be close to someone. That is an argument
for the `EXTRAP_MAX` freeze (S3) doing real work, and a candidate for sending more often when yaw
rate is high rather than at a fixed 10 Hz.

⚠️ **Bounded by S6's autodrive**, which spins at ~675 m. The clean-driving row rests on ~14 s of
data; a longer measurement needs an autopilot that can hold a lap, which does not exist yet.

Suite 22/22.

### E106 (PO 2026-09-01) — 🔴 EPIC: make the cars look like GPL's — cockpit AND exteriors, player AND AI

PO, verbatim: *"make the cars look better; refer to the gold standard car screenshots and videos.
Right now the cars look like a dog's breakfast"* — and, clarifying scope: *"this includes the
cockpit, but also the exterior views of player car and AI cars. All the graphics data used to make
the GPL cars is available, along with gold standard data to compare to. The car look is so important
for emersion, and GPL does this well, duplicating it would be great."*

So the acceptance standard is GPL itself, and the method is the one every visual item here has
converged on: **capture ours, put it beside gold, fix the largest visible difference, recapture.**
Gold references already in the tree: `parity/watglen/sf_cockpit_gold_vs_native.jpg`,
`parity/watglen/chase_gold_vs_native.jpg`, the `parity/gold_index/` set, and the gold screenshot
archive at `/run/media/g/84AF-CC77/<track>/` (currently unmounted — remount for the full set).

**Folded in:** the PO's same-day report *"the salvador dali dashboard is above the steering wheel,
blocking the driver's view of the road"* — fixed this sprint, see E106-S1.

**Known gaps vs the gold cockpit A/B, as a starting inventory (from
`sf_cockpit_gold_vs_native.jpg`):**
1. ~~gauge cluster blocks the road~~ (S1)
2. no driver hands/sleeves on the wheel in-frame at rest (gold: white sleeves + gloves dominate)
3. tub interior reads as flat green geometric shapes; gold is dark matte with riveted aluminium side
   panels
4. mirrors: ours are chunky trapezoids on the cowl; gold has round discs low at the frame edges,
   with live reflections
5. front tyres: ours read flat grey; gold shows tread + sidewall shading
6. windscreen: ours is a strong yellow slab; gold is a faint low plexiglass
**⚠️ Corrected same day — the PO: "E106 says nothing about car exteriors." Right: the heading
claimed exterior scope but the inventory above is all cockpit. The exterior half, from
`chase_gold_vs_native.jpg` (gold: the Lotus from behind, close) plus today's E85-S5 chase
captures:**

7. **tyres** — gold shows moulded tread and sidewall shading, and they dominate the rear view; ours
   are smooth flat dark-grey cylinders (the single largest exterior difference by screen area)
8. **rear assembly** — gold shows a detailed silver suspension/driveshaft/exhaust cluster between
   the wheels; ours is the E102 stick (pose, tracked under its own number) plus chrome slab
   remnants; exhausts absent
9. **driver figure** — gold's chase view is dominated by the blue helmet and shoulders above the
   roll hoop; ours barely reads as occupied
10. **livery** — gold's green + yellow nose stripe is crisp; ours is flat green with the tub's
    geometric facets showing through (same root cause as cockpit item 3)
11. **wheels/rims** — gold shows silver rims distinct from rubber; ours blur into the tyre
12. **chase camera framing** — the old A/B shows gold low-and-close vs ours far-and-high; today's
    captures sit closer, so REMEASURE before treating this as open (the A/B may be stale on this
    axis)
13. **AI car exteriors** — all five chassis (Ferrari/Brabham/BRM/Eagle/Cooper) load their own GPL
    meshes but have NO gold A/B at all yet; every judgement so far has been about the Lotus. Fresh
    captures of each chassis beside its GPL gold still is the first exterior task, because nothing
    can be fixed against a reference that has not been looked at.

### E106-S1 (2026-09-01) — ✅ the dashboard no longer blocks the road, and the G-key refusal is visible

**1. The Dali dashboard.** `JM_GAUGE_Y` default 0.28 → **0.20**, measured at three heights on the
same Watkins spot: 0.28 is a billboard filling the windscreen (what the PO raced against), 0.14
hides the dials behind the wheel (the occlusion E74-S7 was fixing when it over-corrected), **0.20
holds both** — dials in a dark binnacle behind the wheel, road visible, top edge at the horizon.
E74-S7's mistake is worth naming: it verified 0.28 against *"dials legible"* and never against
*"road visible"* — two halves of one sightline, and fixing one broke the other.

**2. "pressing g had no effect - I was stuck in automatic."** G was not broken — entering MANUAL
requires the clutch disengaged (E93, the PO's own rule: slider past 0.4) — but the refusal was a
`println` to the TERMINAL, and the player is looking at the game window. **A key that appears to do
nothing is indistinguishable from a broken key.** The refusal now draws ON SCREEN: a transient bar
(2 s) showing the clutch axis with an amber tick at the 0.4 threshold, so "move this past the line"
needs no words. Transient because E13 asked for a decluttered HUD. Verified inert when not
triggered: the three gauge-height captures were taken with the code live and show no stray bar.

**3. AI lap times are now measurable per lap** (`JM_AI_LAPDIAG=1`): they existed only in
`last_race_result.txt` at race END, so a session quit early recorded nothing — and the PO's
"AI best lap about 1:40" could only be quoted from pacing arithmetic. Measured on Watkins at
`JM_AI_PCT=66.9`: Eagle 1:37.1, Ferrari 1:38.2, BRM 1:40.6, Brabham 1:41.7, Cooper 1:44.4 —
the field straddles 1:40 but the best is 3% quick. **`JM_AI_PCT=64.9` puts the best lap at ≈1:40.**

### E106-S2 (2026-09-01) — ✅ **THE TYRES: dressed with GPL's own art, player and all five AI cars**

The largest exterior gap (inventory item 7) is closed. The mechanism explains why the wheels ever
looked wrong at all:

**GPL never textures its wheel meshes directly.** Each corner has a ~120-byte WRAPPER 3DO
(`llftire0.3do`, `flftire0.3do`, …) whose string table reads
`<mesh> <outboard face> <inboard face> <tread> [spinner]`, bound to the mesh through a selector
subtype (0x11) and an external-mesh node (0x0E) our parser never walked. Loading the mesh alone
yields mostly-untextured geometry, which the port then tinted rubber-grey — the "smooth flat grey
cylinders". The wheel textures were sitting unused in the install the whole time: `l1out`/`l1in`
(the complete Firestone-lettered faces with silver spokes), `loftex1`/`lortex1` (tread),
`lspinn1` (knock-off spinner).

**Fix, in two parts:**
1. `extract_gpl_car(...; wheel_dress=(posy, negy, tread))` — classify untextured triangles by face
   normal in the mesh frame (axle = GPL y): |n_y| dominant = a face disc, else tread. Authored UVs
   are KEPT where present (the 0x821 polys were authored for these textures); UV-less polys get
   disc-projected / cylindrical coordinates (tread repeats ×4 around, GL_REPEAT).
2. The texture set is read off the WRAPPERS themselves (`wheel_dress_for`): the wrapper encodes the
   left/right outboard swap in its slot order, so no per-corner logic exists anywhere in our code —
   for the player (hand table matching the Lotus wrappers) and all five AI cars (parsed at load).

**Verified by capture, chase and cockpit:** cross-groove tread around every tyre, sidewall ring
with gold pinstripe, spoke detail behind — player and AI both. The cockpit view now shows treaded
front tyres either side of the (no-longer-blocking, S1) dash.

⚠️ **One bug of mine cost a capture round: the 3DO magic is byte-reversed on disk (`"4OD3"`), like
every chunk tag in this format (`NRTS`, `MIRP`).** The first cut checked `"3DO4"`, matched nothing,
and every AI wheel silently rendered undressed — an empty cache and a missing feature look
identical from outside. The parser's own source spells the reversed tags out; I typed the
human-readable one anyway.

`JM_WHEEL_DRESS=0` restores the flat wheels (player); suite 22/22.

**Next (S3), from the inventory in impact order:** exhausts — `PIPE3.mip`/`lexhsup.mip` and the
`trumplo/trumphi` intake meshes exist in the install and nothing loads them; gold's rear view shows
the megaphone exhausts prominently between the rear wheels. Then the driver figure in chase
(helmet/shoulders), then the tub interior + livery (items 3/10).

### E106-S3 (2026-09-01) — ✅ the helmet wears GPL's own skin; the hands' art is located

**The chase view's solid-black helmet blob: E60 retextured the WRONG PART.** `helmeg.3do` is two
parts — a 176-tri `helblack` piece (visor/trim, black in gold too) and a **572-tri untextured shell
that fully envelops it** (y 0.014..0.249 vs 0.09..0.167). The shell is the per-driver skin slot GPL
binds at runtime (twenty `lNNhelm` skins ship with the car, plus `clahelm`). E60 mapped
`helblack → clahelm`, painting the hidden trim and leaving the visible shell untextured black.
Now the SHELL takes `clahelm` and `helblack` stays black, as gold does. Captured: a properly shaded
dome with peak trim instead of a silhouette.

⚠️ Checked against the art rather than assumed: `clahelm` decodes to a **dark** helmet (mean RGB
50,49,50) with white peak strips — so a dark helmet is *faithful*, and the gold video's blue helmet
is simply a different one of the twenty skins. Do not "fix" the colour.

**The cockpit's chrome-jumble hands are NOT missing art.** `lohand.mip` decodes to four crisp
white-gloved fist views and `lotarms.mip` to white sleeve fabric — the textures are right and the
hands sit correctly at 10-and-2. The remaining wrongness is **UV smear** (the fist shows several
texture views at once). That is S4's first task, and it is a mapping bug, not an asset hunt.

Suite 22/22.

### E106 priority change (PO 2026-09-02)

*"do not add the hands and gloves yet. It is last in the priority list."*

So the working order is now: **exhausts → tub interior → livery → mirrors → windscreen → chase
framing/AI gold A/Bs → hands/gloves LAST.** The S3 hands finding (textures right, UV smear, at
10-and-2) stays on file for when the item comes up; nothing further on it until then.

### E106-S4 (2026-09-02) — ✅ exhausts at hub height, parked branches gone; and a stride correction to S2/S3's numbers

**The exhausts were never missing — they were drawn dangling under the car.** `pipe3` (the chrome
headers + megaphones) decomposes into **7 connected solids**: two header bundles, two megaphones
(x −1.6..−0.69 — ending just past the rear axle, the correct length), a bracket, and **two 7-tri
tips PARKED at z ±1.0 / x to −2.5** — GPL runtime-hidden branches (the posmat-clamp family) that
drew as stray chrome off the car's tail. The megaphone centreline sat at y ≈ −0.06: the underside.
Gold runs them level with the rear hubs.

**Fix:** `pipe3` is excluded from the body and drawn as its own item set, clipped at `maxlat=0.9`
(the parked tips sit at |z| ≈ 1.0; everything real is inside 0.45 — so the standing lateral clip
removes exactly the junk) and lifted `JM_PIPE_LIFT` (default **0.18 m**, centreline → +0.12 ≈ hub
height), with a touch of specular so the chrome catches the sun. `JM_PIPES=0` removes them.
Captured: megaphones visible at hub height on both sides, no stray tips.

⚠️ **Open residual:** gold's megaphones run straighter and more inboard than ours, which angle
slightly outward. Height and membership are right; the angle needs the gold A/B treatment next
pass.

⚠️ **CORRECTION to every triangle count in S2/S3 (and some earlier items): `TrackPart.verts` is a
FLAT float array with an 11-float stride** (pos+normal+uv+col), and I had been quoting
`length(verts) ÷ 3` — floats over three, a meaningless number, 11× too high. pipe3 is **293 tris**,
not "3223"; the wheel is ~700, not "7700"; the helmet shell ~52, not "572". The *identifications*
stand (they rested on textures and bboxes, and `parts_bbox` reads the stride correctly) — only the
tri counts were nonsense. **This is the third frame/stride error in this epic's family**
(E102-S6 logged two); the union-find above reads stride 11 and its solids match the on-screen
structure exactly.

Suite 22/22. Next per the PO's order: **tub interior, then livery** (mirrors after; hands LAST).

### E106-S5 (2026-09-02) — ◐ the tub interior: mechanism FOUND, partially applied; the slot binding is now the gating work

**The discovery that reframes the whole interior item: GPL's cockpit is not separate geometry.**
`lotd.3DO` (172 bytes) is a WRAPPER: node 0x0E re-enters `lotus.3do` with a **9-slot texture table**
bound by selector subtype 0x11 — `[lotd, lotd, plaface, plahelm, dash7, ldashr, lotinsid, lotinsa,
dash7a]`. The driver view is the SAME monocoque re-skinned: riveted-aluminium walls, real dash, even
the player's face/helmet for the mirror reflection. That is the identical wrapper mechanism the
tyres used (llftire0), now seen carrying a full view's worth of textures.

**What shipped this sprint:** the port now mirrors the two-rendering structure — `CARPIN`, a
cockpit-view body with the cockpit-region untextured panels dressed in `lotinsid`, drawn only when
`view == 0`; chase keeps the green exterior. The visible tub wall goes from flat dark green to a
brushed-aluminium tone — closer to gold — **but the panel art does not map correctly**: a magnified
corner of the texture (the strap) spans the wall. `JM_COCKPIT_DRESS=0` disables;
`JM_COCKPIT_TEX` A/Bs (`lotinsa` measured worse — it samples a dark corner).

**Why it cannot be finished geometrically: the authored UVs are per-SLOT.** Each untextured poly
was authored against ONE of the nine slot textures, and the mesh records WHICH via a slot index the
parser does not yet read (the poly types' third word, bound through the 0x0E/0x11 chain). Binding
one texture to all of them is exactly why the wall shows the wrong region. The same mechanism gates
the **body livery** (`lotd` is the full body skin — the exterior's lo133/lo134 are only decals) and
the proper **dash**. Three items now converge on one piece of parser work:

**NEXT (S6): implement the wrapper chain in gpl3do.jl** — node 0x0E (external mesh reference),
selector subtype 0x11 (texture-slot table), and per-poly slot indices resolved against the bound
table. Verify against the tyres first (the geometric dress already shows what RIGHT looks like, so
the slot-bound render must match it), then render lotd.3DO directly for the cockpit and the body
wrappers for the exterior.

Suite 22/22.

### E106-S6 (2026-09-02) — ⭐ **THE SLOT-BINDING MECHANISM IS IMPLEMENTED. Wheels are pixel-faithful; the cockpit has its real dash and painted cowl.**

The wrapper chain GPL actually uses is now in the parser (`gpl3do.jl`), measured piece by piece:

* **selector subtype 0x11** — binds a texture-slot TABLE (count + string offsets), as carried by
  the wrapper 3DOs (`llftire0`: 4 slots; `lotd.3DO`: 9 slots);
* **selector subtypes 0x20 / 0x24 / 0x2C** — select a 0-based SLOT from the bound table. Found by
  instrumented walk: the tyre mesh uses 0x20 with slots {0,1,1,2,3}; `lotus.3do` uses 0x2C with
  slots running exactly 0..8 against lotd's 9-entry table (slot 0 = `lotd`, the painted body skin,
  ×21 sites);
* **node 0x0E** — re-enter an external sibling .3do with the bound table and the current transform,
  keeping the SUB-parse's group ids (overwriting them would silently break the
  displaced-assembly excludes).

**Verified against ground truth first**: parsing `llftire0.3do` directly yields the fully-textured
wheel — `l1out` 166 / `loftex1` 104 / `l1in` 22 + disc — matching what S2's geometric dress
established as correct.

**Shipped on it:**
1. **All wheels — player and every AI car — now load through their wrappers** (`JM_WHEEL_WRAP=0`
   reverts). The tread is GPL's fine-ribbed pattern with authored UVs, visibly closer to gold than
   S2's ×4 cylindrical guess; sidewall pinstripes and disc detail land as authored. Geometry matches
   the old meshes to a millimetre (r 0.312 vs 0.311).
2. **The cockpit body renders through `lotd.3DO`** — 644 tris of painted cowl (green, yellow
   stripe, TEAM LOTUS roundels), the riveted interior panels, and the REAL dash (`dash7`/`dash7a`/
   `ldashr`), replacing S5's single-texture dress. The dash dials are visible behind the wheel for
   the first time. `plaface`/`plahelm` (the face/helmet GPL puts there for mirror reflections) are
   excluded — ours draw separately.

**Open polish, catalogued:** the cockpit sills show a pale mis-mapped region of `lotd` where gold
has aluminium (tonally close, wrong texture region — isolated by a JM_COCKPIT_DRESS=0 control
capture); the cowl reads washed vs gold's deep green (lighting pass); megaphone angle; E102's stick.

Suite 22/22.

### E106-S6b (2026-09-02) — ✅ the EXTERIOR body also renders through the wrapper

GPL binds the exterior's slot table at runtime; `lotd` is the painted livery. The chase body now
extracts from `lotd.3DO` with the standard excludes (`JM_BODY_WRAP=0` reverts to the bare mesh), so
the painted cowl — green, yellow stripe, roundels — is what the outside views draw instead of
untextured green facets. Verified from behind: no regression, helmet present, wrapper wheels on
player and AI. A three-quarter gold A/B is the next judgement angle (the stripe runs along the
nose, invisible from dead astern).

Suite 22/22.

### E106-S7 (2026-09-02) — ✅ the PO's video triage: floating dashboard GONE, arm shards GONE, E102's sticks GONE

Worked directly from frames of the PO's own video (`~/Videos/260902_first_look_new_cockpit.mp4`),
which is the right reference: it shows the real session, not my captures.

**PO's list → outcomes:**

1. *"spurious enlarged dashboard floating over visor blocking driver's view of the road"* —
   that was the **E74 gauge BILLBOARD still drawn on top of the real lotd dash** from S6: two
   dashboards, one floating. The billboard now defaults OFF whenever the lotd cockpit is active
   (`JM_GAUGE=1` forces it back; it remains the dash for `JM_COCKPIT_DRESS=0`). The cockpit capture
   now shows: road fully visible, real dial panel below the wheel, nothing floating.

2. *"arms stationary and detached from gloves"* — the chrome shards around the wheel. The
   hands/arms ITEM is last by the PO's order, so until it runs the broken display is **hidden**
   rather than shown wrong (`JM_HANDS=1` restores) — an absent arm is a smaller lie than a detached
   one, the same principle as the netplay ghost cars.

3. *"axles still projecting improbably down and outward from rear tires"* (**E102**) — the sticks
   are the `rsuspItemsA/B` rear-half sets: `JM_RSUSP=0` removes exactly them and nothing else.
   **Clip-based fixes cannot work** — measured in the baked frame, the rods sit at legitimate hub
   heights across ordinary lateral range; the POSE (angle) is wrong, not the position, so any clip
   tight enough to cut the rods also cuts real links. Until the halves are re-posed: default OFF.
   The clean rear reads far closer to gold's fine wishbones than the rods ever did.
   ⚠️ Two of my own mis-reads on the way are corrected in the code comment: I first read an A/B
   pair as "sticks gone" when they were not (then over-corrected to a wrong "coincident copies"
   theory when they were in fact gone the first time — rsusp2 was already default-off). The
   pixel-diff harness stays; eyes alone mis-read near-identical captures twice today.

4. *"tailpipes better but not symmetrical"* — **confirmed and still open**: `pipe3` carries an
   asymmetric 5-tri bracket (right side only) and slightly different header bundles (102 vs 96
   tris after trims); next pass.

**Also recorded (PO, same day): the car art is GPL COMMUNITY-made content** — the hires packs,
skins and wrapper files come from the GPL modding community, not the game's original publishers.
The epic's fidelity target ("look like GPL") is thus a tribute to that community's work, and the
provenance belongs in the record.

Suite 22/22. Remaining, in order: tailpipe symmetry → cockpit sill mis-map + cowl saturation →
mirrors/windscreen polish → AI gold A/Bs → rear-half re-pose (restores articulated suspension) →
hands/arms LAST.

### E106-S8 (2026-09-02) — cockpit flicker biased, exhaust bracket dropped; engine UV diagnosed (not yet fixed)

From the PO's second video (`~/Videos/260902-better.mp4`, "much better overall"):

**1. "flicker, especially around visor and mirrors"** — z-fighting: the lotd cockpit shell's
slot-bound windscreen-frame and mirror-pod faces sit at the SAME depth as the separately-drawn
windscreen glass and mirror discs, so the rasteriser picks a winner per-pixel per-frame. Added a
`depthbias` option to `Render.draw` (GL_POLYGON_OFFSET_FILL, −1/−1) and applied it to the three
later coplanar draws — mirror disc, live mirror glass, windscreen. Deterministic front/back order
now; a still can't prove a flicker gone, but the coplanar pair it removes is exactly the cause.

**2. "make those exhaust pipes symmetrical"** — pipe3 carries a 5-tri BRACKET authored on the
right side only (its own connected solid). `min_component=6` on the pipe extraction drops exactly
it. ⚠️ Residual: the left/right HEADER bundles still differ (102 vs 96 tris) — that is the authored
art, not a placement bug, so true symmetry needs mirroring one bundle onto the other; catalogued.

**3. "engine in nintendo view … flicker and random shapes and colors"** — DIAGNOSED, deferred as
its own careful task. The garish pink/purple striped panel low in the engine bay is `lo133` (the
Ford-Cosworth DFV engine atlas — a correct, detailed texture) sampled at the WRONG region: the
engine polys carry authored UVs spanning only U 0..0.58 / V 0..0.61, and the black inter-panel
gaps of the atlas sit around U/V 0.5, so parts of the engine land in the gaps and read as garbage.
This is the same slot-UV subtlety as the cockpit sills (S6): the wrapper binds the texture but the
per-poly UVs need the slot-relative offset the parser does not yet apply. **Not a one-liner; not
rushed.** Ruled out first: the texture resolves fine (`LO133.mip`, case-insensitive) and is the
right art; dash-face textures are NOT the cause (excluding dash7/dash7a/ldashr left the panel).

**4. "Axles are needed"** (reversing S7's removal) — the PO wants the rear suspension BACK, but
correctly posed. That is the rear-half RE-POSE task already queued; it moves UP the priority order
now that the PO has asked for it explicitly. S7 hid the sticks as a stopgap; the real fix is the
pose, and it is next after the engine UV.

**PO also confirmed:** cockpit "good except flicker", external "better". Overall "much better".

Suite 22/22. Revised order: **engine UV (lo133 slot offset) → rear-half re-pose (axles back,
posed) → exhaust header mirroring → cockpit sills/cowl saturation → mirrors/windscreen polish →
AI gold A/Bs → hands/arms LAST.**

### E106-S9 (2026-09-02) — ✅ the axles are back, straight, by CONSTRUCTION

The PO asked for the axles back after S7 hid the mis-posed halves. One more re-pose attempt was
measured first: **roll 20° levels the driveshaft exactly (drop 0.192 → 0.039 m) — and points the
radius arms at the ground.** That is the fifth failure of the same shape across E64/E75/E82/E102/S7:
the halves compose parts in DIFFERENT local frames through positioners our walk mis-chains, so any
single corrective transform fixes one part and breaks another. The transform family is exhausted.

So the driveshafts are **built, not extracted**: two straight cylinders from the diff (|z| 0.16) to
each hub (|z| = the drawn half-track), at hub height, wearing GPL's own `axlelot` texture with a
cylindrical wrap. Correct pose by construction, GPL's look from its own art. `JM_AXLES=0` removes
them; `JM_AXLE_Y`/`JM_AXLE_R` tune. The rest of the halves stays off until someone decodes the
positioner chain properly.

Also this sprint (S8 continuation): the engine "random shapes and colors" got further diagnosis —
the striped pixels sample pink/salmon consistent with `lo133`'s own fuel/oil-line art (204 of 210
engine tris map inside the atlas detail; only 6 stray past U 0.48), so the *colors* may be
legitimate DFV plumbing rendered noisily, and the FLICKER component points at coplanar engine
panels z-fighting — same family as the visor. Needs the live flicker, not stills; queued with the
sills.

⚠️ The `WTRACK_R` forward-reference trap fired a THIRD time (parses clean, dies at load); caught by
running the sim, per the standing rule, and the constant is now read via its env default as the
file's own comment instructs.

Suite 22/22.

### E106-S10 (2026-09-02) — flicker: 467 duplicate tris removed; visor translucent; the S8 engine diagnosis RETRACTED

From the PO's Zandvoort video ("much improved!"):

**1. "flicker on engine and inside of rear tires" / "fix flicker on mirrors"** — measured cause:
the body carries **467 COINCIDENT SAME-FACING triangles out of 2219 (21%)**. Stacked duplicates
tie on depth, so the rasteriser picks a different winner per frame and the surface shimmers as the
car moves — the extractor's own `dedup` comment already describes exactly this ("z-FIGHT, flickers
only when moving"). `dedup=:orient` now runs on the body AND the cockpit: it collapses same-facing
stacks while KEEPING opposite-facing pairs, so double-sided panels still read from each side.
`JM_CAR_DEDUP=0` reverts. The mirror polygon offset also went from −1/−1 to −2.5/−4 after the
weaker value left the mirrors flickering.

**2. "make visor more transluscent"** — `JM_WIND_ALPHA` default 1.0 → 0.55. (The opaque default
came from an earlier PO call that the tan scuttle must not read glassy; this is the newer call.)

**3. ⚠️ THE S8 ENGINE DIAGNOSIS WAS WRONG AND IS RETRACTED.** S8 recorded that the engine's UVs
"span only U 0..0.58 / V 0..0.61" and land in the atlas's black gaps, needing a slot-relative UV
offset. That was measured with the **wrong vertex offsets**: the interleaved layout is
pos(3), normal(3), **colour(3), uv(2)** — floats 7-9 are the COLOUR and the UV is at 10-11, as
`upload()`'s attribute pointers show. Re-measured correctly, the engine UVs span a full 0..1 and
are fine. No slot-relative offset is needed; that work item is cancelled.

**What the engine mess actually is (measured, fix not yet shippable):** 46 of 156 engine polys and
65 of 464 body polys are GPL **flat-shaded** polys — all three UVs identical — that nonetheless
carry a texture, so each samples ONE arbitrary texel and paints a solid slab of it (the copper /
magenta wiring strip of `back4` and `lo133`: the PO's "random polygon/colors"). Their authored
colours are the right ones (BRG 0,0.24,0.12; the yellow stripe 0.75,0.64,0.22; silver; dark engine
tones). Drawing them in those colours instead (`JM_FLATPOLY=1`) **visibly fixes the engine — and
turns the cockpit cowl bright yellow**, because those baked colours are GPL's MODULATION colours
(texture × colour), not replacements. Implemented, measured, and **default OFF** until the
modulation path is done; that is the next task and it is now well-specified.

Suite 22/22 (re-run after every edit).

### E106-S11 (2026-09-02) — the .ibt mislabel bit again, at Spa; fixed at the root this time

A Spa race wrote its telemetry as `lotus49_zandvoort 2026-09-02 21-44-59.ibt`. This is the SAME
fall-through E91 fixed for Monza and Watkins Glen: `IBTNAME` was a chain of per-track ternaries
ending in a hardcoded `"zandvoort"`, so every track nobody had listed borrowed Zandvoort's
identity — and E91's own note says a mislabelled capture is worse than none, because later analysis
cannot tell it from the real references it sits beside.

Fixing it track-by-track only postpones the next one, so the name now **derives from the track
selection** and the hardcoded default is gone: an unlisted track names itself. Only `nurburgring`
(long form) and the `zandvort`/`zandvoort` directory-vs-reference spelling stay aliased. Verified
by running Spa: writes `lotus49_spa …ibt`. The mislabelled capture was renamed to its true
identity (data preserved, not deleted).

Suite 22/22.

## BACKLOG ITEM (PO, 2026-09-02): THE ENGINE GRAPHICS FIX

**Ask:** fix the engine's appearance in nintendo/chase view — "random polygon/colors on back of
engine, also flicker on engine" (PO video `260902_zand.mp4`). The engine fills the view whenever
the chase camera is used, so it is high-visibility.

**State: diagnosed, mechanism measured, fix specified but NOT yet shippable.**

* The engine atlas (`lo133`) and the gearbox/back texture (`back4`) are CORRECT art — a detailed
  Ford-Cosworth DFV. The UVs are fine (a full 0..1 span; the earlier "UV smear" claim was measured
  with the wrong vertex offsets and is retracted — see E106-S10).
* The actual defect: **46 of 156 engine polys are GPL flat-shaded polys** — all three UVs identical
  — that still carry a texture. Each therefore samples ONE arbitrary texel and paints itself a solid
  slab of that colour, which is why the engine shows magenta/copper patches taken from the wiring
  strip of the atlas. Their authored colours are the right ones.
* Drawing them in their own colour (`JM_FLATPOLY=1`) fixes the engine **and turns the cockpit cowl
  bright yellow**, because those baked colours are GPL's MODULATION colours (texture × colour), not
  replacements.

**The fix to build:** modulate rather than substitute — sample the texture and multiply by the
poly's colour, as GPL does, instead of choosing one or the other. That should fix the engine
without touching the cowl. Verify with a chase capture AND a cockpit capture before shipping.

**Flicker component:** partly addressed in E106-S10 (467 coincident duplicate tris removed by
`dedup=:orient`); re-check on the PO's next video whether any engine flicker remains after that.

## BACKLOG ITEM (PO, 2026-09-02): FIX AI CAR EXTERNAL GRAPHICS — outward rods on the rear tyres

**Ask:** at least one AI car has **3 outward-facing metal rods attached to each rear tyre**.

**Likely the same defect already solved for the player car, not a new one.** E102/E106-S7 measured
exactly this on the Lotus: the rear-half assemblies (`rsuspItemsA/B`) compose parts in different
local frames through positioners our walk mis-chains, so they render as rods spearing out past the
wheels. The player car ships with them OFF (`JM_RSUSP=0` default) and the driveshafts synthesized
straight instead (E106-S9).

**Why the AI cars still show them:** the AI chassis (Ferrari, Brabham, BRM, Eagle, Cooper) load
through a SEPARATE path from the player's Lotus, so neither the S7 suppression nor the S9
synthesized axles were applied to them.

**To do:** (1) identify which AI chassis show the rods and which mesh group they come from;
(2) apply the same treatment as the player car — suppress the mis-posed halves and, if the axles
read as missing, synthesize straight shafts as in S9; (3) verify with a chase capture of each of
the five AI chassis beside its GPL gold still (that per-chassis A/B is itself an open E106 item
and can be done in the same pass).

### E106-S13 (2026-09-02) — ✅ THE LEVITATION AND BOUNCE: root cause found, fixed at the boundary, gated

PO (Nurburgring): *"car crashed, levitated and bounced near the last grandstand building on the
right."* Two standing rules broken at once — the car must NEVER bounce back, and a graze should
scrub you but not end your race (it ended pinned at 0 km/h, race over).

**Measured from the PO's own replay and telemetry, before touching anything:**
* deceleration 177 → 5 km/h while drifting right (lateral 2.3 → 6.7 m), ending pinned;
* the car **sank 1.4 m**, then **rose 7 m in 0.8 s** (620.28 → 627.26), then **fell 6.65 m in a
  single frame**;
* the ground under that whole climb is **flat: 620.11 → 620.39** (probed directly with a new
  `JM_HATPROBE` instrument, grid and path modes). So it was neither a building plateau nor a hole
  the car fell into — something applied a large upward impulse over flat terrain.
* `SOLIDS` is EMPTY at the Ring by design, so it was not an object collision either.

**Root cause:** the player's `groundz` closure returns the **sentinel −999** for "off the HAT", and
was wired straight into `step_car3d!`. `drive_rt3d` guards only `isfinite` — and **−999 is finite**.
A wheel sampling a hole in the mesh was therefore told the ground lay 999 m below: the car sank
toward it, and the correction on re-acquiring real terrain launched it.

**E104(b) had already established the right contract** — off-mesh must reach the physics as NaN —
and `offroad_smoke` gates the physics side of it. The player's closure was simply never converted.
Fixed at the **physics boundary only** (`groundz_phys`), leaving the app's twelve internal
consumers on the `> -900f0` sentinel they were written against.

⚠️ **A wrong first fix, caught by the suite.** I first guarded the sentinel inside `drive_rt3d`.
That passed my own new gate — and broke `offroad_smoke`, whose CONTROL arm deliberately proves the
sentinel still misbehaves in the physics. The suite caught me changing a contract another gate was
built on; the fix moved to the producer, where it belonged.

**New gate `hat_hole_smoke` (suite now 23).** It guards the half that was missing: `offroad_smoke`
proves the physics handles NaN, this proves the APP actually sends it — no physics call site may
pass the raw closure, the boundary closure must map the sentinel to NaN, and the mapping is
exercised. Negative control: against the pre-fix wiring it flags all **5** raw call sites.

Suite 23/23.

## BACKLOG ITEM (PO, 2026-09-02): NURBURGRING AND SPA MUST BE DRIVEABLE END TO END

**Ask:** ensure the Nurburgring and Spa can be driven by a human without obstacles — levitation,
bouncing, and the like.

**Standing rules this protects:** the car must NEVER bounce back; a graze at speed should scrub you
but not end your race.

**Already done (E106-S13):** the specific Nurburgring levitation the PO hit is fixed at the root —
the off-mesh sentinel (−999) was reaching the physics, which guards only `isfinite`, so a wheel over
a hole in the terrain mesh was told the ground lay 999 m below; it sank, then the correction
launched it (+7 m, then a 6.65 m drop, measured from the PO's replay). Gated by `hat_hole_smoke`.

**What this item still needs — the general case, not the one incident:**
1. **A full-lap sweep of both circuits** that drives the racing line (the sim can drive itself
   headlessly — E85-S6's autodrive) and asserts NO vertical excursion beyond a threshold, NO
   bounce-back, and NO terminal stop. One pass per track, run as a gate.
2. **A terrain-hole census** for both meshes: `JM_HATPROBE` (E106-S13) reads the physics ground
   height anywhere, so sweep the corridor either side of the centreline and REPORT the holes rather
   than discovering them by crashing into one. Holes are now survivable, but a hole is still a
   missing surface and the count is the honest measure of each track's readiness.
3. **Verify Spa specifically** — it has never been driven far in this port (the PO's session
   reached 442 m). Spa is 14.1 km with 92,548 terrain triangles, so it has the most opportunity for
   mesh gaps.
4. Re-check the "stuck against scenery, race over" half: the Nurburgring run ended pinned at 0 km/h
   at lateral 6.7 m. The levitation fix does not by itself address being unable to continue.

### E106-S14 (2026-09-03) — the terrain-hole census: both tracks measured, and Spa is worse than the Ring

Deliverable 2 of the PO's driveability item. `JM_HOLECENSUS=<half-width m>` walks the centreline and
samples the PHYSICS ground across the corridor the car can actually reach; a sample with no surface
is a hole. E106-S13 made holes survivable — this says **how many there are**, which is the honest
measure of a track's readiness, and it replaces discovering them by crashing into one.

| track | samples | holes | stations with any hole | worst station |
|---|---|---|---|---|
| Nürburgring | 38,692 | **486 (1.26%)** | 154 | s=19,960 m — 5 of 17 lateral samples missing |
| Spa | 24,004 | **365 (1.52%)** | 120 | **s=270 m — 8 of 17 missing** |

Both circuits have holes, and **Spa is the worse of the two** — a higher rate, and its worst station
is 270 m from the start with nearly half the sampled corridor missing. That is consistent with the
PO's Spa session never getting far, and it is the first hard evidence about Spa's readiness, which
had none.

⚠️ Caveat stated rather than buried: the ±12 m corridor is wider than the racing surface, so some of
these holes are off-track ground the car only reaches when it runs wide — which is exactly what the
PO was doing at the Ring when it launched. The census counts reachable ground, not road.

⚠️ A bug of my own, caught before it produced a number: `pose_at` returns `(x, y, z, θ)` and my first
census read element 2 as z — the HEIGHT. It would have sampled a diagonal line through the terrain
and reported confident nonsense. Fixed to use `pose_at`'s own lane offset instead of recomputing the
normal.

Still open on this item: the full-lap driveability sweep (autodrive both circuits, assert no vertical
excursion / no bounce-back / no terminal stop), and the "stuck against scenery, race over" half — the
Ring run ended pinned at 0 km/h, which the levitation fix does not by itself address.

Suite 23/23.

### E106-S15 (2026-09-03) — 🔴 **I SHIPPED A SIM THAT WOULD NOT RUN. Fixed, and the gap that let it through is named.**

**The regression, plainly:** E106-S13's `groundz_phys` closure was defined at file scope beside
`groundz` — which is inside a nested block `main()` cannot see. So `main()` resolved the name as a
missing global and threw `UndefVarError: groundz_phys` **on every track**. That state was committed
AND PUSHED (1998c2c, and carried through S14's 197731a). **Any race the PO started between those
commits and this one died at startup.** The levitation fix itself was correct; its placement was not.

Now defined INSIDE `main()`, where `groundz` is demonstrably in scope (the call sites already use
it). Verified by running all three tracks to a clean exit: watglen, nurburgring, spa.

**Why nothing caught it — the honest answer, because this is the second time (cf. E103-S2):**
* `parse_smoke` walks the syntax tree, so a name that resolves at RUNTIME is invisible to it;
* the 23-gate suite exercises modules and pure functions — **no gate starts the sim**;
* the suite went 23/23 on the broken tree, and I trusted that instead of running the thing.

The rule this re-proves: **a green suite is not a running program.** A sim change is not verified
until the sim has been launched. I launched it only when the driveability sweep needed it — by luck
of the next task, not by discipline.

**Also this sprint — the driveability watch (`JM_DRIVECHECK=1`).** Per frame under autodrive it
tracks the three failures the PO named — height above the ground beneath the car (levitation),
upward velocity spikes (bounce), and time under a crawl (stuck, "a graze should scrub you but not
end your race") — and prints a verdict naming where and by how much. It works and reports; ⚠️ the
**sweep it was built to drive does not yet run a lap**: under `JM_SMOKE` the autodrive controller
returns `thr=0.0` and the loop ends after ~0.1 s of sim time, so the numbers so far describe the
first moments on the grid, not a lap. That is the next sprint's work, and the watch is ready for it.

⚠️ My own `hat_hole_smoke` gate failed on this change — it asserted the closure's byte-exact
spelling, so reformatting tripped it. Relaxed to a whitespace-tolerant match of the CONTRACT (maps
the sentinel to NaN). A gate that fails on formatting trains people to ignore it.

Suite 23/23, and the sim actually starts.

### E106-S16 (2026-09-03) — ✅ the driveability sweep RUNS, and it localises real defects on both tracks

Deliverable 1 of the PO's driveability item. Two blockers had to go first:

* **The timestep is WALL-CLOCK** (`dt = now - last`), so a headless run spins as fast as the CPU
  allows and advances almost no SIM time — S15's sweep covered 0.1 s of sim time in thousands of
  frames. `JM_FIXED_DT=<s>` advances a fixed step: a lap becomes possible AND the run becomes
  deterministic (a gate whose result depends on machine speed is not a gate).
* **`JM_SHOTS`' first field is a LAPDIST in metres, not a frame number** — so "run for 8000 frames"
  was actually "place the car at s=8000 m and shoot immediately". `JM_SHOT_SETTLE` is the run
  length. My S15 note that "the controller returns thr=0" was therefore reading a car that had been
  alive for three frames.

**Results — the sweep drives, and the three tracks differ sharply:**

| track | from | reached | max air | max upward | longest stall | verdict |
|---|---|---|---|---|---|---|
| Watkins Glen | s=0 | **3,543 m of 3,750** | 0.10 m | 3.93 m/s | 12.8 s | clean but for one stall |
| Nürburgring | s=0 | 776 m of 22,756 | **10.94 m** | 32.5 m/s | 372 s | fails near the start |
| Spa | s=0 | 273 m of 14,125 | **11.02 m** | 104 m/s | 383 s | fails near the start |
| Spa | s=4,000 | **8,440 m** (4.4 km driven) | **9.41 m at s≈6,760** | 18.5 m/s | 4.0 s | one launch site |

**Watkins Glen completes 94% of a lap cleanly**, which is what makes the other two meaningful: the
instrument can report clean, so the failures are not the harness. And starting Spa at s=4,000 drives
4.4 km, so **the spawn is not inherently broken either** — the start REGION is.

**Cross-referenced against the hole census (now listing the worst ten stations, not just one):**
Spa's holes cluster at **s=270–520** — exactly where the from-zero sweep dies. But **s≈6,760, where
the car was thrown 9.4 m into the air, is NOT in the hole list at all.** Those are two different
defects and must not be conflated: a holed start region, and a launch site with another cause.

⚠️ **Instrument fault of mine, fixed:** the bounce test counted the car SETTLING onto the track at
spawn (27.7 m/s in one frame), so every run reported a "bounce" at s=0 — a check that always fails is
as useless as one that never does. The first second is now excluded.

**Next:** characterise s≈6,760 on Spa (probe the ground and the car's state through it — not a hole,
so suspect geometry or a seam), and the Ring's failure before s=776.

Suite 23/23.

### E106-S17 (2026-09-03) — ⭐ Spa's ejection site NAMED: a terrain SEAM — a 2 m step with a gap running through it

The sweep localised a launch on Spa; this sprint identifies it. The verdict now logs **each distinct
excursion with its own peak and world position**, so a defect can be probed rather than guessed at.

**Spa, driving from s=4,000:**

| site | peak air | speed | reading |
|---|---|---|---|
| s=6,650.8 | 0.96 m | 131 km/h | a small hop at speed — plausibly a legitimate crest |
| **s=6,758.8** | **9.41 m** | **23 km/h** | **an ejection** |
| s=6,761.8 | 8.37 m | 21 km/h | the same event repeating |

**A car cannot jump 9 m at 23 km/h.** Probing the physics ground at the exact world position
(−15.7, −2935.2) with `JM_HATPROBE` shows why — a **diagonal line of MISSING triangles** running
through the car's position, separating a lower plateau at ~330.3 m from a higher one at ~332.4 m:

```
dz= -4   330.35    --    331.54  331.73 ...
dz=  0   330.34  330.35  330.37    --   331.66     <- the car is here
dz=  4   330.32  330.33  330.33  330.35   --
```

So: **a ~1.4–2 m terrain STEP with a gap along the seam.** E106-S13 made a missing sample survivable
(the sentinel no longer drags the car down), but a step immediately beside a hole still resolves as a
violent contact — which is what throws the car.

**Why the hole census did not flag this** (worth recording, because the two instruments look
redundant and are not): the census reports stations by how MANY lateral samples are missing, and this
seam loses only one or two per station — far below the worst-ten cut, which needed five. **The census
finds WIDE holes; the sweep finds the ones a car actually hits.** Neither alone would have found this.

⚠️ **Two instrument faults of mine, both caught before they misled the record:** the event log first
recorded each excursion's ONSET height, so a 9.41 m launch printed as 0.84 m — an instrument that
understates precisely what it exists to measure; now it tracks the peak. And it had no world
position, so nothing could be probed; now it logs one.

**Next:** the same treatment for the Nürburgring (it fails before s=776 from a standing start), and
then decide the fix — the honest options are to repair the two meshes' seams, or to make the physics
tolerant of a step-beside-a-hole, which would cover every track including ones not yet tested.

Suite 23/23.

### E106-S18 (2026-09-03) — ⭐⭐ **THE GRANDSTAND IS IN THE PHYSICS SURFACE. The PO's original words were exactly right.**

PO, on the Nürburgring: *"car crashed, levitated and bounced near the last grandstand building on
the right."* Four sprints later the instruments name it, and the PO's reading of it was correct.

**The Ring sweep's event log:**

| site | peak air | speed | world |
|---|---|---|---|
| s=773.5 | 2.41 m | 56 km/h | (−1385.9, −2900.7) |
| s=0.0 ×7 | **8.12 → 10.94 m** | **0 km/h** | **(−940.2, −2308.5)** — the same point each time |

A car at **0 km/h** thrown 8–11 m into the air, repeatedly, at one fixed position. Probing the
physics ground there:

```
dz=  8   619.78  627.86  619.91  619.96 ...
dz= 12   627.85  628.21  627.99  619.98 ...
```

Smooth terrain at ~619.8 m — and a cluster of cells at **627.9–628.2 m, an 8.4 m STEP**. That is a
**building baked into the terrain mesh and treated as drivable ground**. The car's excursions
(8.12–10.94 m) match the step's height. It is the grandstand.

**Why this was invisible before:** `SOLIDS` is EMPTY at the Ring by design — the code says "scenery
baked in" — so the buildings are not collidable OBJECTS, they are part of the driving SURFACE. There
was never a collision to find. And my earlier probe of the PO's own crash coordinates showed flat
terrain because that is where the car came to REST; the offending geometry is ~70 m away, which is
why the autodrive found it and a point-probe did not.

**Both tracks now have a named defect, and they are the same family** — a step in the physics
surface that a car cannot survive:
* **Spa, s≈6,759**: a ~2 m step with a diagonal gap along the seam (E106-S17).
* **Nürburgring, (−940, −2308)**: an 8.4 m building plateau.

**The fix, and the choice for the PO.** A mechanism already exists: `HAT_EXCLUDE` drops named
textures (`br_under`, `villone`) from the physics HAT, with the standing warning that
`drop_overpass` must NOT be used because the Ring has bridges one genuinely drives over. Two honest
options:
1. **Name the offending geometry** (identify the grandstand's texture, add it to `HAT_EXCLUDE`) —
   surgical, faithful, but per-building and per-track, and it will need repeating.
2. **Make the physics tolerant of a step** — reject a ground sample that is implausibly far above
   the car's current reference, the way E106-S13 now rejects the off-mesh sentinel. One rule,
   covers every track including untested ones, and cannot be defeated by a building nobody has
   named. Risk: it must not swallow legitimate terrain (the Ring's real jumps and banks), so the
   threshold needs measuring against the steepest genuine ground on each circuit.

**Recommendation: (2), with the threshold measured rather than guessed** — and (1) kept for anything
that survives it. This is the PO's call and the item is ready for it.

⚠️ Four sprints reached on this backlog item; switching projects next per the standing rule.

Suite 23/23.
