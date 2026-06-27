# Race AI — current design + the physics/hybrid path

## What ships now: GPL-style multi-rail kinematic AI (`ai.jl`, `RaceAI`)

The opponents are **kinematic** — they don't run the vehicle physics; they advance
along the track centreline (`AILine`) at a curvature-limited speed and move laterally
between **three rails** (race line / inside / outside), exactly like GPL's AI:

- **Pace** — `_vtarget` = `sqrt(amax/κ)` (slows for the corner ahead, runs out the
  straights), scaled by `AI_SCALE` so a clean lap hits the GPL reference laptime ×
  (100/`JM_AI_PCT`).  Calibrated via `natural_laptime`.
- **Racecraft** (`step_field!`) — each car looks at the nearest object ahead (another
  AI **or** the human, passed in as `(s, lateral, v)`).  If it's closing on it in the
  same lane, the car dives to the **rail away from it** (`tlane = ±RAIL`) to pass/evade,
  and **matches speed when too close to get by** (so it never rams).  When clear it
  drifts back to the race line.  Lateral motion is rate-limited and clamped to
  `±LANE_MAX` so cars stay on the track.
- **Grid** — set by qualifying (`grid_order` + `form_grid!`); standings rank by
  laps + lap-fraction.

**Strengths:** robust (no spins), cheap, authentic to GPL, evades the player and each
other, paced to GPL laptimes.

**Limitation:** kinematic — there is **no contact physics**.  The AI *avoid* the player,
but if the player drives into an AI, the player's car passes through it (no collision
response on the human side).  Wheel-to-wheel *contact* needs the AI in the physics world.

## The hybrid path (do this if there's time): physics cars + rail brain

Keep the rail **brain** (the `tlane` race-line/inside/outside selection in `step_field!`)
but replace the kinematic *advance* with the real **JM 2-D physics model** per AI, so the
cars collide and feel real — the rFactor-style "AI on a simplified physics model" the spec
asked for, with GPL's racecraft on top.

Sketch:
1. Each AI owns a `DriveRT.build_car(...)` (planar model — stable, and it already has a
   divergence safety-net: respawn on `|v|>110` or NaN, `drive_rt.jl:136`).
2. The **rail brain** picks a target: a point on the chosen rail a lookahead-distance
   ahead, plus the curvature-limited target speed (reuse `_vtarget`).
3. A **driver controller** turns that into inputs:
   - steering = pure-pursuit to the rail target (+ a small cross-track term);
   - throttle/brake = track the target speed.
4. Project each AI's physics `(x,z)` back onto the `AILine` (`project`) for `s`/lap/
   standings, and feed every car's `(s, lane, v)` into the brain for mutual awareness.
5. Add **car–car contact** so the player feels the AI (and vice-versa).

### Feasibility (measured — `scratchpad/ai_phys_probe.jl`, 2026-06-26)
- **Performance is a non-issue:** planar step ≈ **0.23 ms** → 5 AI ≈ **~1 ms/frame** of a
  16.7 ms budget.
- **Stability is the work:** the model tracks a straight perfectly (cross-track 0.03 m),
  but a *naive* pure-pursuit + speed controller **spins in a tight bend** (the 80 m-radius
  test corner: cross-track 37 m, 189 spin frames).  Holding racing pace without spinning is
  the project's long-flagged **"robust limit-handling autonomous driver"** problem.
- **Mitigations to try:** cap the cornering target **below** the grip limit (lower `amax`
  for the AI than the player), tune steering gain + lookahead vs. speed, add slip/yaw-rate
  feedback (ease off when the rear steps out), and lean on the built-in divergence net.
  Start conservative (a touch slow) and raise pace until just before it gets ragged.

This gives the most faithful result (physics + GPL racecraft + real contact) at the cost
of a controller-tuning effort that may need iteration across each track's corner types.

## GC controller — PROVEN viable (2026-06-26, autonomous; `scratchpad/test_hybrid.jl`)
Drove a real `DriveRT.build_car` around test tracks with a rail-targeting controller and
characterised every failure mode → a recipe that **tracks without spinning**:
- **Steering:** `steer = 2.6·headingErr − 0.14·crossTrack − 0.20·yawRate`, look-ahead
  `≈ 3 + 0.22·v` points (SHORT — a long look-ahead understeers wide).  Tracks moderate
  corners to **0.19 m** cross-track.
- **Gearbox:** use the AUTO path (`manual=false`).  In a fixed gear the car STALLS at
  corner speed (dist stops at the first bend, v→0); auto-clutch/shift fixes it.
- **Anti-spin:** conservative corner speed `vt ≈ 0.72·√(aκ/κ)` + a **corner throttle-cut**
  `thr ·= clamp(1.4 − 2.2·|steer|, 0, 1)` (don't power-on mid-corner) → **0 spin frames**
  even through the tight bend (vs 66 spins with full throttle).  Brake early (limiting-κ
  horizon `≈ 8 + 0.9·v`).
- **Result:** completes laps, no spins, tight tracking on corners ≥ ~30 m (real-track
  range).  Only an EXTREME r≈20 m hairpin (tighter than GPL corners) still runs wide —
  needs full-lock handling / a slower crawl there.
- **Perf:** ~0.23 ms/planar-step → 5 cars ≈ 1 ms/frame.  **Caveat:** `build_car` runs
  `mtkcompile` each call (~30-60 s) — 5 AI would add minutes at startup, so the integration
  MUST compile the system ONCE and create 5 integrators from it (share `sys`/setters/`getall`,
  per-car `integ`).
### Integration plan (the remaining large step — validate the FEEL before shipping default)
1. `DriveRT.build_cars(n)` — compile `sys` once, build n cars sharing setters/getall.
2. Replace the kinematic AI motion with n physics cars + the controller above; KEEP the rail
   brain (`step_field!` lane targets + hysteresis) as the steering target + the pace cap.
3. Bump the AI's physics car on collision (reuse `bump!`), not the kinematic `spin`.
4. Verify on ALL 6 real tracks (each ~2 min load): laps complete, no spins, pace ≈ player.
Ship OPT-IN (`JM_AI_PHYSICS`) first; make default only after a test-drive confirms the feel.
The current LIVE AI stays kinematic (physics accel + pace cap + no-skitter + collisions),
which already addresses every specific behaviour complaint.

## GA Lotus GPL-fidelity findings (2026-06-26, autonomous)
Decoded the Lotus textures to PNG (scratchpad/decode_tex.jl). What's where:
- `windlot` = tan leather SCUTTLE (restored ✓), `dash7a` = the GAUGE CLUSTER, `lotbody` =
  the DRIVER's suit, `lo133` = FORD engine, `frontlot`/`lid`/`lotsho` = suspension,
  `lotback` = black dash padding, `lo134`/`top`/`rear` = thin trim edges.
- **The green body livery + yellow nose stripe + #1 roundel + TEAM LOTUS are NOT in any
  accessible texture.** The body is flat green poly-colour; the painted number/stripe come
  from GPL's runtime driver-SKIN system (per-grid-slot), which we don't yet reproduce.
Deferred GA items (deep GPL RE, low ROI vs the AI epics):
- Gauge cluster renders dark/occluded at the cockpit camera though `dash7a` resolves +
  the poly survives filters (UV or normal/lighting issue).
- Driver arms (`lohand`/`lotarms`) render as splayed chrome "wings" (sub-object positioner
  geometry issue) — kept excluded.
- Body number/stripe/TEAM LOTUS = GPL driver-skin system (would need to emulate it).
The cockpit is much closer now (tan scuttle + red wheel + mirrors + green cowl); the AI
chassis already show their distinct GPL liveries (flat poly colours: red Ferrari, etc.).
