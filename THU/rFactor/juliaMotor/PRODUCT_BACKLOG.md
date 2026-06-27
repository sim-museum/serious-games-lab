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
