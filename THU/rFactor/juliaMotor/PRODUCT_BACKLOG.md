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
