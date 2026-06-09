# juliaMotor — native (no-browser) drivable cockpit

A real **OpenGL** renderer (GLFW + ModernGL + GLSL) driving the validated
JuliaMotor physics over the actual Zandvoort + Vanwall geometry — no browser,
no web server. This is the first step toward a self-contained app with
rF1-equivalent graphics; it replaces the three.js/browser front-end with a
native window and a hand-written GL pipeline that can grow toward textures,
materials, shadows and post-processing.

```sh
cd /home/g/sgl/THU/rFactor/juliaMotor/demo/native
julia --project=. drive_native.jl        # opens a native window; drive it
```

First launch precompiles GLFW/ModernGL (one-time, ~a minute) and extracts the
track/car geometry; after that it's instant.

**Controls** — keyboard *and* the Logitech joystick natively (no browser
Gamepad API): `W`/`S` throttle/brake, `A`/`D` steer, `E`/`Q` shift up/down,
`C` clutch, `R` respawn, `V` cockpit↔chase view, `Esc` quit. On the stick:
push = throttle, pull = brake, roll = steer, trigger/side = shift, top-left =
clutch. Speed/gear/rpm show in the window title bar.

## Architecture

- **`render.jl`** — the rendering core (a module): geometry extraction
  (`extract_track`/`extract_car`, reusing `RFactorData`'s `parse_gmt` /
  `parse_gmt_indexed`), the GLSL shaders (two-sided Lambert + hemispheric
  ambient, matching the browser look), mat4 camera math (`perspective` /
  `lookat` / `translate` / `roty` / `rotz`), procedural `wheel_mesh`, and the
  mesh upload / draw helpers.
- **`drive_native.jl`** — the app: loads physics + geometry, opens the GLFW
  window, and runs the game loop (poll input → `step!` the physics by
  wall-clock dt → update camera + car/wheel model matrices → draw → swap). The
  real Vanwall body/cockpit/driver are the decoded GMT meshes; the four wheels
  are procedural period tyres at the real PM hub positions.

## Verify without a window

`snapshot.jl` renders cockpit + chase frames **offscreen** (hidden window,
`glReadPixels` → PPM) — used to validate the renderer headlessly:

```sh
julia --project=. snapshot.jl            # writes /tmp/native_{chase,cockpit}.ppm
JM_SMOKE=1 julia --project=. drive_native.jl   # runs 40 loop frames hidden, then exits
```

## Next toward rF1 fidelity

Textures (decode the `.dds` from the `.mas` archives, add UVs to the GMT
parse), per-material shading, shadow mapping, a proper text HUD (font atlas),
sky/fog, and the instrument cluster + minimap from the browser build.
