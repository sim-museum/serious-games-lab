# Julia Racer — Product Backlog & Sprint Plan

**Product Owner:** user (pre-approves sprint planning + reviews).
**Goal:** a complete Julia "GPL-like" racing app — Training / Practice / Race modes,
up to 5 AI cars, user-set lap count, GPL tracks (Zandvoort, Nürburgring, +Watkins
Glen, Monza, Spa), GPL-fidelity graphics (incl. the Lotus 49), glitch-free, and a
**physics-based (Modelica-like) iRacing Lotus 49** model — no fudge factors.

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

⚠️ **NOT done.** With the mirror pass removed entirely, BOTH views sit at ~15 fps / 65 ms — so
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
