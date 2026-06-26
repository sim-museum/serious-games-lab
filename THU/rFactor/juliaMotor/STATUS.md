# Julia Racer — Status (2026-06-25)

GPL-style racing sim: Lotus 49 on GPL tracks, JuliaMotor (MTK) physics, native OpenGL
renderer. Branch `julia-racer`. Launch via `demo/native/gui.py` (or `drive_native_mtk.jl`).

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
- **Start/finish "smear"** (Watkins Glen, dark grey-green fuzzy mass behind the bridge): NOT
  fully resolved. Exhaustive elimination ruled out every named object group (trees, fence,
  tower, signs, billboards, crowds), the track mesh, the horizon ring, and the baked
  scenery. Dropping ALL objects faded it (region 91→111) but didn't clear it → it appears
  to be a COMBINATION (partly trackside trees, partly a track-mesh/backdrop-layer element
  not yet isolated). Next: a live "hide object group" debug toggle or a pixel→object picker
  instead of blind elimination.
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
