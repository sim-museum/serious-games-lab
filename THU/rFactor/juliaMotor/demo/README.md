# juliaMotor demonstration

**Drive it yourself — cockpit view + joystick** — `drive_server.jl` +
`drive.html`: a human drives the 1958 Vanwall around Zandvoort in real time,
from a **first-person cockpit view** over the **full 3D track** (road, curbs,
grass, sand, grandstands, pit buildings, gantries — every visible mesh from the
`.mas`/`.gmt` files, ~9.6k triangles in world coordinates), with the car's
motion governed entirely by the JuliaMotor physics engine (validated bicycle
model + calibrated TBC tires + engine/drivetrain/brakes + clutch, over the real
GMT surface).  This is the Phase 4.3 "drivable standalone" end-state — and it
does *not* need the open limit-handling autonomous driver, because the human is
the control loop.

```sh
cd ~/sgl/THU/rFactor/juliaMotor/demo
julia --project=../JuliaMotor drive_server.jl 8090   # serves http://127.0.0.1:8090/
# then open that URL in a browser and drive.
```

**Logitech Extreme 3D Pro** (read in-browser via the Gamepad API): push the
stick forward = throttle, pull back = brake, left/right = steer, front trigger =
shift up, side thumb button = shift down, top-left button = clutch.  An on-screen
panel shows the live axes/buttons so you can confirm the mapping (adjust the
`MAP` object at the top of `drive.html` if your unit reports different button
indices).  **No stick?** keyboard fallback: `W`/`S` gas/brake, `A`/`D` steer,
`C` clutch, `E`/`Q` shift, `R` respawn, plus an "auto gearbox" checkbox.

On-screen instruments (since the demo has no sound or rich visuals):
* a **North-up minimap** (bottom-right) — orientation matches the printed
  Zandvoort map: pit straight up the left, Tarzan hairpin top-left;
* an **instrument cluster** (bottom-centre) — a **traction circle for each of
  the four wheels** (FL/FR/RL/RR), an **RPM** bar, and a **scrolling
  throttle / brake / clutch telemetry trace** (a live data-logger plot of the
  last ~3 s of inputs).  In each traction circle the **circle size is that
  wheel's current grip** (load) and the **dot is the force it's making**; a dot
  on its own rim = that tyre at the limit.  Because the model now resolves all
  four wheels (see below), in a corner the **loaded outer wheels grow and the
  light inner wheels shrink** — the weight transfer made visible — and under
  combined braking-and-turning each wheel's dot moves independently.  The
  three captured states in `instrument_preview.png` (straight-line accel,
  steady corner, trail-braking) show the layout.

**Four-corner tyre model.**  The cockpit physics resolves the car as four
independent wheels, not two axles.  Per-corner vertical loads carry both
longitudinal (pitch) and lateral (roll) transfer; each axle's force is split
left/right by the corner's grip capacity.  The lateral-transfer gains and the
force split are **calibrated and validated against the measured per-corner
`Tire Load` and `Lat Force` telemetry channels** (the load model reproduces the
logged loads to ~198 N / 9.5 %, and the force split is unbiased at 7–12 % RMS —
the measured outer front tyre carries 67 % of the axle's cornering force at
0.4 g, which the model captures).  The validated 2-axle body dynamics are kept
unchanged (a full four-corner *dynamic* replacement over-fits — better fit,
worse holdout — so the data doesn't support it); the per-corner resolution
feeds the traction circles and an inside-wheel-lift grip limit that only binds
when a wheel unloads (a kerb, the grass), beyond the symmetric envelope the
telemetry covers.  See `LOAD4_CAL` / `corner_loads` in `JuliaMotor/src`.

The track is rendered in the correct chirality: rFactor's left-handed world is
converted to three.js' right-handed frame (Z negated) so corners turn the right
way and steering is intuitive — Tarzan is the right-hander it should be.

The server is pure Julia stdlib (`Sockets`) — no web framework; it also serves
the vendored `three.min.js` and the 3D scene (`/scene.json`).  The browser polls
`/step` at its frame rate sending the live input; the server advances the physics
by the elapsed wall-clock time and returns the car pose + HUD (incl. per-wheel
traction); the page renders it with three.js (perspective cockpit camera, lit
track, sky/fog, a modelled open-wheel cockpit whose steering wheel and front
tyres react to your steering).
`render_cockpit_preview.py` renders a still of the cockpit view from a saved
`/scene.json` + pose (used to verify the geometry/camera without a browser);
`render_drive_view.py` is the earlier top-down still renderer.

**Video** — `zandvoort_lap.mp4` (1280×720, 40 s): the 1958 Vanwall driven by
the Julia engine around Zandvoort, on the real track geometry extracted
from rFactor's `.gmt`/`.mas` files (road / grass / gravel coloured), with a
live speed / gear / throttle-brake HUD.

```sh
xdg-open ~/sgl/THU/rFactor/juliaMotor/demo/zandvoort_lap.mp4
```

**Interactive report** — `zandvoort_lap.html`, self-contained (no internet,
no dependencies): animated lap + the physics-vs-telemetry validation plots.

```sh
xdg-open ~/sgl/THU/rFactor/juliaMotor/demo/zandvoort_lap.html
```

What it shows, all from the rFactor install + your driven telemetry:

1. **Animated lap** — the Julia engine (calibrated tires/engine/drivetrain/
   suspension) driving a 1958 Vanwall around Zandvoort, on the **actual
   collision-mesh geometry** extracted from the `.mas`/`.gmt` files. The
   racing line is coloured by speed.
2. **Capstone validation** — the full engine driven from *only* your logged
   steer/throttle/brake/gear (re-anchored every 5 s), with predicted vs
   measured **speed** (≈3 km/h RMS) and **yaw rate** (≈0.06 rad/s). This is
   the physics reproducing a real lap.
3. **Sim speed trace** around the lap, and the **calibrated tyre curve**.

Honest notes shown in the report: the autonomous driver runs a
conservative pace (~254 s lap); realistic-pace driving is a scoped
controls follow-on. The engine physics is validated open-loop regardless.

Regenerate after code changes (scripts are versioned here):
```sh
cd ../JuliaMotor
julia --project=. ../demo/export_data.jl     # → /tmp/demo_*.csv  (report data)
julia --project=. ../demo/export_track.jl    # → /tmp/demo_track.csv (typed surface)
julia --project=. ../demo/export_video.jl    # → /tmp/vid_lap.csv  (dense trajectory)
python3 ../demo/build_report.py              # → zandvoort_lap.html
python3 ../demo/render_video.py              # → zandvoort_lap.mp4 (needs ffmpeg, Pillow)
```
