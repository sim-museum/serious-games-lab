# Julia Racer — Status (2026-06-28)

GPL-style racing sim: Lotus 49 on GPL tracks, JuliaMotor (MTK) physics, native OpenGL
renderer. Branch `julia-racer`. Launch via `demo/native/gui.py` (or `drive_native_mtk.jl`).

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
