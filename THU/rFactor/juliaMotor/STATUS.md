# juliaMotor — status (2026-06-20)

Branch: `julia-racer`. A Julia physics engine (`JuliaMotorMTK`, ModelingToolkit) + a native
OpenGL renderer (`demo/native`) for a 1967 Lotus 49 on GPL tracks (Zandvoort, skidpad,
Nürburgring). Goal "Path B": a physics-based Lotus 49 tuned vs gold-standard iRacing telemetry.

## Apps / how to run
```
cd demo/native
python3 gui.py                                # PyQt6 front-end (recommended): launch + controller calibration
julia -t 2 --project=. drive_native_mtk.jl    # 3 tracks (Skidpad is the GUI default), TRACK=zandvoort|skidpad|nurburgring
JM_SMOKE=1 …                                  # headless self-test (forces Zandvoort), auto-exit
```
First load ~3–4 min. Env: `JM_NOSOUND`, `JM_NOIBT` (telemetry ON by default → `data/juliaracer/`),
`JM_FFB_GAIN`/`JM_FFB_SIGN`/`JM_NOFFB`.

## NEW this session — PyQt GUI + Thrustmaster TX wheel + FFB
- **`gui.py`** (PyQt6, system `python3-pyqt6`): **Drive** tab (track + mute + .ibt + Launch; Skidpad
  default) and **Calibrate controller** tab (live axis bars / button lamps + hold-each-control wizard →
  writes `joystick.conf`). Reads the stick through GLFW via **`joyserver.jl`** (a hidden-window GLFW
  poller streaming `{name,axes,buttons}` JSON) so calibrated axis indices match the game exactly.
  Python `JoyMap` mirrors `joycfg.jl`. Works for the Logitech X3D and the Thrustmaster TX.
- **Thrustmaster TX on Linux** (USB `044f:b664` Xbox/GIP mode exposes only steer+clutch+buttons via
  `xpad` — NO accel/brake pedals). Fix = **`tmdrv`** (`/home/g/src/tmdrv`, `sudo ./tmdrv.py -d
  thrustmaster_tx`) re-enumerates to full mode `044f:b669` (4 normalized axes). Auto-init on plug-in:
  `/etc/systemd/system/tmdrv-tx.service` + `/etc/udev/rules.d/99-thrustmaster-tx.rules`.
- **Force feedback WORKS**: built+installed **`hid-tmff2`** (`/home/g/src/hid-tmff2`, `make && sudo make
  install && sudo make udev-rules`), binds `TX_ACTIVE=0xb669`. FF bitmap `0x31fff0000` (FF_CONSTANT etc.).
  **`ffb.jl`** = Julia evdev FF writer (EVIOCSFF), wired into `drive_native_mtk.jl`: wheel force =
  self-aligning torque from front-axle Fy × pneumatic trail (you feel the front load up / lighten).
  `ffbtest.py` is the raw-evdev reference. `/dev/input/event5` is user-writable (uaccess ACL), no root.
- **Diagnostics**: `joydiag.py` (axis range / movement-order), `joybtn.py` (button capture).

## GPL force feedback (Wine)
- Switched the game runner **`lutris-5.7` → `lutris-fshack-7.2`** (modern DInput FFB) in BOTH
  `THU/gpl.sh` AND `config/wine_runners.csv` (the `~/sgl` launcher reads the CSV — that was the real one).
- Set `HKCU\Software\Wine\DirectInput "DisableHidraw"="Y"` in the WP prefix (legacy evdev path → wheel
  visible to GPL with FFB). FF tuning lives in GPL **`core.ini`** `[ Joy ]` (NOT `gpla67.ini` — that's AI
  physics): `force_feedback_damping 40→8`, `max_steering_torque 225→200`.

## Physics — DONE this session (toward iRacing skidpad: 1.40 g, 183°/s spin)
- **Removed the non-physical low-speed `α` fade** → single physical low-speed reference velocity
  `Vref = √(vx² + Vlow²)` (Vlow=1) — force opposes the slip velocity at any heading, dies only at rest,
  Jacobian bounded. (`vehicle_rt.jl`.)
- **Aero drag `u²` → `u·|u|`** (was injecting energy when the car moved backward post-spin) + **rolling
  resistance** added (Crr 0.026, tanh knee) — a coast actually stops.
- **Engine: stall + restart + WHEEL-LOCK.** Spawns in **neutral** (gear "N"); idle only acts when the
  clutch is decoupled (no idle-creep); a bogged engine **stalls** (combustion/idle die below ~300 rpm);
  a **dead engine resists being motored** (`−(1−run)·45·ωe`) so a stall in gear drags the wheels to lock
  → tyres skid at ~1 g → stops in ~3 s (was a 25 s glide). rF1-style restart on clutch-in OR shift-to-N.
- **MANUAL by default** — no auto-clutch, no auto-shift.
- **Tyre calibration** (`tyre_law.jl`): front μ1.45/Cy1.40, rear μ1.55/Cy1.45. Measured vs iRacing
  skidpad .ibt: **grip 1.45 g (iRacing 1.40 ✓)**; spin yaw ~247°/s (iRacing 183 — still a touch hot).
- Tests: `test_launch`, `test_drive_rt`, `test_vehicle_driven` pass.

## Renderer / HUD — DONE this session
- HUD: gear digit raised (was clipped) + shows **"N"** for neutral; pedal bars reordered to physical
  **clutch · brake · throttle** (+ a clutch bar); **RPM is now a tachometer DIAL** (2× size).
- Skidpad: orange **cones** in the centre circle; diameter labels **flat on the ground**, radial, at the
  4 cardinal points of the **yellow (50 m)** rings only (50/100/150/200); **Nürburgring horizon** backdrop
  for orientation (other scene choices removed).

## OPEN / next
- **Tyre direction-normalized combined slip** (the flagged refactor): the combined law uses the *lateral*
  curve (Cy) for the *longitudinal* force too, so front Cy couples into braking grip (LongAccel 1.12 g vs
  iRacing 2.19) and fails `test_combined_slip:34`. Proper fix = normalize slip per direction (long→Cx).
- Spin yaw 247 vs 183 — trim oversteer slightly from the next .ibt.
- Mirrors render black (no RTT). Nürburgring fence flicker / floating people (pre-existing).
