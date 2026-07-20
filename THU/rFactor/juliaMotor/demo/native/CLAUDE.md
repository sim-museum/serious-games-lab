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
python3 juliaRacer.py                                  # PyQt6 front-end: launch + controller calibration (recommended)
julia -t 2 --project=. drive_native.jl          # opens a GLFW window on your display
JM_SMOKE=1 julia -t 2 --project=. drive_native.jl   # headless self-test → dumps /tmp/zand_hud.ppm and exits
```
### It still needs a little rFactor data (2026-07-20)
Everything you *see* is GPL — the track (`WP/drive_c/Sierra/GPL/tracks/<track>`) and the Lotus 49
body/gauges/windscreen/mirrors (`.../cars/cars67/lotus`). But two things still resolve through the
**rFactor** GameData root (`RFactorData.default_gamedata()`, overridable with `RFACTOR_GAMEDATA`):
- `drive_native_mtk.jl:494` — `Vehicles/F158/Vanwall/Teams/LewisEvans/LewisEvans.veh` → the **physics
  parameters** (`VehicleModel`). The Lotus-49 calibration is still a TODO, so the car is *rendered* as
  a Lotus 49 but *handles* like a '58 Vanwall.
- `drive_native_mtk.jl:806` — `EngineAudio.build_lotus(gamedata = GD)` → **engine audio**.

**rFactor does not need to be installed.** Build a symlink-only GameData tree from the mod media and
point `RFACTOR_GAMEDATA` at it:
```
GD=~/sgl-julia-racer/rfactor-gamedata; mkdir -p $GD/Locations
M="~/sgl/THU/rFactor/INSTALL/F1 1958 by ORM - v4.35 COMPLETE/F1 1958 by ORM - v4.35 COMPLETE/Gamedata"
for d in Helmets Scripts Sounds Talent Vehicles; do ln -sfn "$M/$d" $GD/$d; done
ln -sfn ~/sgl/THU/rFactor/INSTALL/newTracks/2/Zandvoort67 $GD/Locations/Zandvoort67
export RFACTOR_GAMEDATA=$GD          # juliaRacer.py passes its environment to the sim
```
Without it you get `SystemError: opening file ".../rFactor/GameData/Vehicles/F158/.../LewisEvans.veh"`.

**tmdrv on this box** lives at `~/sgl/THU/INSTALL/tmdrv-master/` (the `/home/g/src/tmdrv` path below is
the original author's machine).

First load is ~2–3 min: ~40–80 s is one-time Julia/MTK/render JIT (track-independent),
the rest is the per-track GPL parse (extract ~70 objects, decode MIP textures, build the
HAT). **To cut the JIT:** `julia build_sysimage.jl` once (~20–40 min) writes `jlracer.so`;
`juliaRacer.py` then auto-launches with `-J jlracer.so` and only the per-track parse remains. The
sysimage is gitignored (large, machine-specific) — rebuild it after physics/render changes. Controls: **W/S** gas·brake, **A/D** steer, **E/Q** shift, **C** clutch,
**G** auto⇄manual, **V** view (cockpit/chase), **R** respawn, **M** mute, **Esc** quit.

## GUI + controller calibration (`juliaRacer.py`)
`juliaRacer.py` (PyQt6, system `python3-pyqt6`) is the front-end. Two tabs: **Drive** (pick
track Zandvoort/Skidpad/Nürburgring + mute/IBT options → launches `drive_native_mtk.jl`)
and **Calibrate controller** (live axis bars + button lamps + a hold-each-control wizard
→ writes `joystick.conf`). Works for the **Logitech Extreme 3D Pro** (as before) AND a
**Thrustmaster TX wheel with clutch/brake/accelerator pedals** (enumerates as "Generic
X-Box pad"); the wizard discovers each pedal/paddle so any layout maps.

### Thrustmaster TX wheel on Linux — REQUIRES tmdrv (2026-06-19)
The TX wheel ships in **Xbox/GIP mode** (USB `044f:b664`), where the generic `xpad`
driver exposes only steering + clutch + buttons — the **accelerator and brake pedals
send no axis data at all** (proven by GLFW capture; `xpad` doesn't decode the wheel's
pedal reports). The fix is **`tmdrv`** (her001/tmdrv, a Python USB mode-switch tool,
cloned to `/home/g/src/tmdrv`): `sudo ./tmdrv.py -d thrustmaster_tx` sends two control
transfers that re-enumerate the wheel to **full mode `044f:b669`** = a proper HID wheel
with 4 normalized axes (steer=axis1 ±1, accel=axis4, brake=axis2, clutch=axis3; pedals
rest +1.0 → press −1.0; TX brake is stiff, full press only ~+0.38) + paddles (up=btn2,
dn=btn1). Deps: `sudo pip3 install --break-system-packages libusb1` (apt's
`python3-libusb1` wasn't in the index). The committed `joystick.conf` / profile
`joystick_profiles/Thrustmaster_TX_Racing_Wheel.conf` capture this mapping.
**Auto-init on plug-in**: `/etc/systemd/system/tmdrv-tx.service` (oneshot, runs tmdrv)
triggered by `/etc/udev/rules.d/99-thrustmaster-tx.rules` (matches the b664 add event,
`systemctl --no-block restart tmdrv-tx.service`). Staged copies live in
`/home/g/src/tmdrv/`. The wheel reverts to b664 on power-cycle/unplug; the udev rule
re-runs tmdrv automatically. Force feedback would need the `hid-tmff2` DKMS module (not
installed). Diagnostic helpers: `joydiag.py` (axis range + movement-order timeline),
`joybtn.py` (button capture) — both stream via `joyserver.jl`.

KEY DESIGN: `joystick.conf` axis indices are in **GLFW's** ordering, so the GUI must read
the stick through GLFW, not pygame/evdev (which number axes differently). It does so via
`joyserver.jl` — a hidden-window GLFW poller that streams `{name,axes,buttons}` JSON lines
on stdout; `juliaRacer.py` spawns it and calibrates against exactly the indices the game uses.
The Python `JoyMap` in `juliaRacer.py` mirrors `joycfg.jl` (same file format, same `apply`).
`calibrate.jl` (terminal wizard) still works and writes the same file. Per-device configs
are also stashed under `joystick_profiles/` on Save. NOTE: `drive_native_mtk.jl` no longer
hardcodes clutch→axis 4; it honours `joystick.conf` when present (so the TX clutch pedal
works), falling back to the X3D slider only when no config exists.

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
- `juliaRacer.py` — PyQt6 front-end: launch tab + controller-calibration tab.
- `joyserver.jl` — GLFW joystick → JSON-line streamer that feeds `juliaRacer.py` (index parity).
- `joycfg.jl` / `calibrate.jl` — joystick mapping module + terminal calibration wizard.
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
