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

## Sprint plan
- **Sprint 1 — HUD + race config (E5, E1).** Traction circles relocated ✅; GUI mode/laps/#AI
  inputs; game mode logic (race → finish at N laps; practice/training = timed/free).
- **Sprint 2 — Tracks (E3).** Watkins Glen, Monza, Spa selectable + drivable (HAT + ribbon).
- **Sprint 3 — AI (E2).** 1–5 AI Lotus 49s on the racing line; grid start; lap/position.
- **Sprint 4 — Graphics (E4).** Glitch fixes; GPL-fidelity pass; JM_3D render robustness.
- **Sprint 5+ — Physics (E6).** Brush-tyre Lotus 49 in `JuliaMotorMTK`; validate vs the iRacing
  `.ibt`; replace the calibrated-curve tyre; JM_3D divergence guards.

## Status log
- 2026-06-25 Sprint 1 started. E5 done (traction circles → beside RPM dial, `render.jl`).
