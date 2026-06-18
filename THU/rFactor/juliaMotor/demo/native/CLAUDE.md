# zand_racer / native GPL Lotus 49 — status & guide

A native OpenGL (GLFW + ModernGL + GLSL) driving sim: a **1967 Lotus 49 on GPL's
Zandvoort**, driven by JuliaMotor physics. `drive_native.jl` is the dev app here;
it is packaged standalone as **`zand_racer`** at `/home/g/zand_racer/` (outside the
repo — it bundles copyrighted GPL assets, personal use). The exhaustive multi-session
history lives in the assistant memory `juliamotor-project.md`; this file is the
working summary.

## Run it
```
cd demo/native
julia -t 2 --project=. drive_native.jl          # opens a GLFW window on your display
JM_SMOKE=1 julia -t 2 --project=. drive_native.jl   # headless self-test → dumps /tmp/zand_hud.ppm and exits
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
- `zand_racer_*.txt` — per-run telemetry logs (gitignored).

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
- **Flicker / z-fight**: SOLVED with **reversed-Z** (GL 4.5 context + glClipControl
  ZERO_TO_ONE + reversed-Z projection `perspective_revz` near→1/far→0 + GL_GEQUAL +
  clearDepth 0 + 32F depth buffer). Per-pass: the shadow pass forces STANDARD depth
  (NEGATIVE_ONE_TO_ONE/LESS/clear-1) so the shadow map + FS sampler are untouched; only
  the main camera is reversed. The horizon-ring backdrop passes via GEQUAL. This killed
  the distant coplanar strobe (signs on fences) a [−1,1] 1/z buffer couldn't resolve.
  Within-mesh double-sided pairs are still collapsed by the centroid+area dedup. NOTE for
  future shader/depth work: the main pass is reversed-Z — don't assume LESS / clear-1.

## Physics caveat
Still **Vanwall-calibrated** physics (validated vs the user's rFactor DAQ). The end
goal is **Path B**: a physics-based brush-tyre Lotus 49 calibrated vs iRacing Lotus 49
telemetry — see `../../DOC/pathB-scope.md`. `zand_racer` ships a serialized
`lotus_physics.jls` so it needs no rFactor install.

## Open items
- Cockpit "shining rug" = the tan scuttle `windlot` (RGB 0.44,0.41,0.14); still too bright
  in the Nürburgring cockpit — matte or exclude it. Mirrors render black (no RTT).
- Floating hillside signs / horizontal people = GPL placement Euler pitch/roll the
  yaw-only `placemat` convention mis-applies (see `gpl_scenery` in drive_native_mtk.jl).
- Path B tyre/engine calibration vs iRacing 49 telemetry.
- Limit-handling autonomous driver (human driving is fine without it).
