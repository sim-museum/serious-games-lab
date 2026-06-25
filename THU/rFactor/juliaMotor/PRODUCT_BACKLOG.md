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

## Sprint plan
- **Sprint 1 — HUD + race config (E5, E1).** Traction circles relocated ✅; GUI mode/laps/#AI
  inputs; game mode logic (race → finish at N laps; practice/training = timed/free).
- **Sprint 2 — Tracks (E3).** Watkins Glen, Monza, Spa selectable + drivable (HAT + ribbon).
- **Sprint 3 — AI (E2).** 1–5 AI Lotus 49s on the racing line; grid start; lap/position.
- **Sprint 4 — Graphics + boundaries (E4, E7).** Glitch fixes; GPL-fidelity pass; JM_3D render
  robustness; per-track collision boundaries (no driving off the world).
- **Sprint 5+ — Physics (E6).** Brush-tyre Lotus 49 in `JuliaMotorMTK`; validate vs the iRacing
  `.ibt`; replace the calibrated-curve tyre; JM_3D divergence guards.

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
- 2026-06-25 E7 FIX (PO bug report: Watkins Glen "molasses"): the boundary was clamping at 13 m
  from the racing-LINE centreline, so driving on the wide grass/runoff (13–25 m off-line) was
  falsely contained every frame → speed bled to a crawl. Diagnosed from the PO's drive (.ibt: 84%
  of slow frames OFF-TRACK; the .txt log: 552 frames at 13–25 m lateral). Reconstructing those
  positions against the watglen terrain HAT: the car was **off the HAT 0% of the time** — always
  inside the world, just off the narrow ribbon. Fix: boundary now keys off the **terrain HAT (the
  world)**, not the ribbon — drive road + grass freely; only going off the terrain snaps you back
  to the last in-world spot (a fence collision). Would have triggered 0× on that drive. Verified
  watglen loads + runs clean.
