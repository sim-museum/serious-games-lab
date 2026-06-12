# sand_racer / native GPL Lotus 49 — status & guide

A native OpenGL (GLFW + ModernGL + GLSL) driving sim: a **1967 Lotus 49 on GPL's
Zandvoort**, driven by JuliaMotor physics. `drive_native.jl` is the dev app here;
it is packaged standalone as **`sand_racer`** at `/home/g/sand_racer/` (outside the
repo — it bundles copyrighted GPL assets, personal use). The exhaustive multi-session
history lives in the assistant memory `juliamotor-project.md`; this file is the
working summary.

## Run it
```
cd demo/native
julia -t 2 --project=. drive_native.jl          # opens a GLFW window on your display
JM_SMOKE=1 julia -t 2 --project=. drive_native.jl   # headless self-test → dumps /tmp/sand_hud.ppm and exits
```
First load is ~3–4 min (parses the track, extracts ~70 trackside objects, decodes
MIP textures). Controls: **W/S** gas·brake, **A/D** steer, **E/Q** shift, **C** clutch,
**G** auto⇄manual, **V** view (cockpit/chase), **R** respawn, **M** mute, **Esc** quit.
Logitech Extreme 3D Pro works natively (push=throttle, pull=brake, roll=steer);
`calibrate.jl` (terminal wizard) writes `joystick.conf`.

GOTCHAS (and see memory `sandracer-launch`):
- The live (non-SMOKE) run **block-buffers stdout** to a log file — it can sit at
  "loading textures…" while the window is actually open and rendering. Confirm via
  `DISPLAY=:0 xwininfo -root -tree | grep juliaMotor` (the title shows live telemetry)
  or `ps -o pcpu -C julia` (~15–20% render loop), NOT the log. SMOKE prints fully
  because it exits (flush on exit).
- A clean **"bye"** in the log = the window CLOSED, usually the user closing it — NOT
  a crash. Launch once; don't build relaunch-on-"bye" loops. Real crashes show a
  Julia stacktrace.
- Wayland: launch detached as `setsid env DISPLAY=:0 julia … &`.

## Layout (demo/native/)
- `drive_native.jl` — the app: GLFW window + game loop, camera, HUD, object placement.
- `render.jl` — renderer module: GLSL shaders (Lambert + hemispheric ambient, shadow
  mapping, distance fog, FXAA), GPL geometry/texture extraction, camera math, HUD,
  the horizon sky-dome, billboards.
- `gpl3do.jl` / `gplmip.jl` / `gpldat.jl` / `gpltrack.jl` — GPL asset loaders:
  `.3do` meshes, `.mip`/`.srb` textures, the `.dat` archive, `.trk` centreline + HAT.
- `joycfg.jl` / `calibrate.jl` — joystick mapping + calibration wizard.
- `sand_racer_*.txt` — per-run telemetry logs (gitignored).

## Current state (2026-06-11)
Drivable and visually close to GPL Zandvoort:
- GPL Lotus 49 (real green/gold livery, cockpit, red wheel that steers, small front /
  big rear tyres), GPL Zandvoort track + terrain HAT (ground-following physics),
  ~70 trackside objects + ~19 billboards (grandstands, readable signs, trees, towers),
  shadows, distance fog.
- **Sky dome**: GPL's 12-panel horizon ring (`horiz0..11.mip`), drawn unlit/unfogged
  as a camera-centred backdrop (`build_horizon`/`draw_horizon`, `uSky` shader path).
  Always overcast (static GPL textures).
- Lap timing + on-screen lap times + ~10 Hz telemetry logging; traction circles (per-
  wheel grip, 2×2) on the black cowl in the line of sight; clutch/auto shift (G).
- **Flicker**: GPL double-sided panels (signs/awnings) z-fight at distance. Mitigated
  by a centroid+area dedup that collapses the thin front/back face pairs (the surviving
  face renders two-sided via the `uBackFlip` uniform). Depth is near 0.35 / far 3000;
  precision at distance is near-plane-bound (~3.8mm @150m) and can't improve much
  without reversed-Z (deferred — touches the shadow pass + GL context version).

## Physics caveat
Still **Vanwall-calibrated** physics (validated vs the user's rFactor DAQ). The end
goal is **Path B**: a physics-based brush-tyre Lotus 49 calibrated vs iRacing Lotus 49
telemetry — see `../../DOC/pathB-scope.md`. `sand_racer` ships a serialized
`lotus_physics.jls` so it needs no rFactor install.

## Open items
- Reversed-Z (or GPL polygon-priority sort) for the last coplanar-decal z-fighting.
- Path B tyre/engine calibration vs iRacing 49 telemetry.
- Limit-handling autonomous driver (human driving is fine without it).
