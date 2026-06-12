# Path B — A Physics-Based Lotus 49 Tyre/Vehicle Model in Julia

*Scope document. Companion to `juliaMotorProjectScope.md`. Written 2026-06-10.*

## 0. Where this fits

juliaMotor began by **reproducing rFactor 1's isiMotor** (Path A) — an empirical
tyre (TBC slip curves + imposed friction ellipse), validated against the user's own
DAQ telemetry. Path A is done and telemetry-validated (four-corner load model, yaw
RMS ~0.066).

**Path B** is the longer game: build a **physics-based brush tyre** that could be
*more correct than rFactor*, in the Kaemmer/iRacing direction. It diverges from
rFactor by design, so it needs a **physics-based reference** to validate against.
That reference is **iRacing Lotus 49 telemetry**.

The end goal of the whole project — *duplicate Grand Prix Legends with a Lotus 49* —
is best served by a 49 that is a Julia **modelling toolkit car**, not a hand-tuned
curve set: parameters that mean something physically, fit to real data.

## 1. Confirm the car first

This decides the aero model and therefore everything downstream:

- The **1967 Lotus 49 ran with NO wings** (wings arrived 1968). Aero is then just
  body **drag + a little lift** — almost **pure mechanical grip**. No
  downforce-vs-speed coupling to untangle. Ideal first validation target.
- iRacing also has the **Lotus 79** (1978, ground-effect, large downforce) — a
  completely different aero regime.

**Action:** confirm in the iRacing car list whether the available car is the '67/'68
**49** (no/early wings) before locking the aero assumption. The rest of this doc
assumes the 49.

## 2. What telemetry to capture

iRacing logs to `.ibt` at **60 Hz** (360 Hz disk logging if available — use it for
transients). Crucially, iRacing **does not expose tyre slip angles or tyre forces**
— those are its internal model. We validate against *observable* channels and
**derive** the rest, exactly as a real tyre rig is back-solved.

### 2.1 Channels present in `.ibt`
- **Inputs:** `Throttle`, `Brake`/`BrakeRaw`, `Clutch`, `SteeringWheelAngle`,
  `Gear`, `RPM`
- **Chassis motion:** `Speed`, `VelocityX/Y/Z`, `LongAccel`, `LatAccel`,
  `VertAccel`, `YawRate`, `PitchRate`, `RollRate`, and the `Yaw`/`Pitch`/`Roll`
  angles
- **Per-wheel suspension:** `LF/RF/LR/RRshockDefl` (m), `…shockVel` (m/s),
  `…rideHeight` — give load transfer and let us back out vertical load via the
  known wheel rates
- **Per-wheel tyre:** carcass + surface temps at 3 points
  (`…tempCL/CM/CR`, `…tempL/M/R`), `…pressure`/`…coldPressure`, `…wearL/M/R`,
  wheel speed (for slip ratio)

### 2.2 Quantities we derive (not logged)
- **Slip angle** (per wheel): from CG velocity + yaw rate + wheel position + steer
  geometry
- **Slip ratio**: wheel speed vs ground speed
- **Vertical load**: shock deflection × wheel rate + static + transfer
- **Axle/corner forces**: back-solved from the accelerations + yaw inertia

### 2.3 Test matrix — each run isolates one property
Record each as a **separate `.ibt`**:

| Maneuver | Pins down |
|---|---|
| Constant-radius skidpad, slowly increasing speed | Lateral force vs slip angle: cornering stiffness, peak μ, peak location |
| Slow ramp-steer at constant speed | Same, transient-free |
| Straight-line full accel, then threshold brake | Longitudinal force vs slip ratio |
| Coastdown in neutral from ~200 km/h | Drag + rolling resistance (also closes Path A's open "constant longitudinal-loss attribution") |
| Trail-brake in / power-on out | Combined slip (friction ellipse) |
| Out-lap from cold tyres | Temp-vs-grip (the tyre thermal model) |

### 2.4 Pipeline
`.ibt` → MoTeC `.ld`/CSV export. `RFactorTelemetry` already ingests **MoTeC CSV**,
so this path is largely built — minimal new plumbing (a derive layer for §2.2).

## 3. The Modelica-like Julia model

The Julia analog of Modelica is **ModelingToolkit.jl (MTK)** — acausal,
equation-based, component-oriented, symbolic. Strictly more capable than its sibling
**Modia.jl**, and it does **symbolic simplification → compiled DAE**, so the *same*
model runs offline for calibration **and** real-time at 400 Hz in the driving app.

### 3.1 Connectors (acausal)
- `Frame` — 3D position/orientation + force/torque (like
  `Modelica.Mechanics.MultiBody.Frame`)
- `Flange` — 1D rotational, for the driveline
- `Contact` — wheel ↔ road

### 3.2 Components (each a reusable equation block)
- **`Chassis`** — sprung mass, inertia tensor, CG
- **`Suspension ×4`** — Lotus 49 geometry (rocker/wishbone). Start as spring/damper
  + camber/toe curves; upgrade to full MultiBody linkage only if the data demands.
- **`Tyre ×4` — the brush model (heart of Path B).** Bristles in the contact patch
  deflect with slip until each hits its local friction limit (μ·load); integrate
  across the patch → Fx, Fy, aligning moment. The **friction ellipse, load
  sensitivity, peak-then-falloff, and relaxation lag all fall out of the physics**
  rather than being imposed. This is the opposite of rFactor's empirical TBC curves.
- **`TyreThermal ×4`** — heat in from slip power, out to air/road; temp feeds back
  into μ
- **`Driveline`** — engine torque curve → clutch → gearbox → diff → rear driveshafts
- **`Brakes`**, **`Steering`** (rack → road-wheel geometry), **`Aero`** (49: drag +
  small lift only)

### 3.3 Why brush, concretely
The brush model's parameters are physical and few: bristle stiffness, contact-patch
length (load-dependent), and μ(speed, temp, pressure). At steady moderate slip it
reduces to a Pacejka-like curve, so it cannot regress on Path A's validated
behaviour — it's a **strict generalization** that additionally predicts combined
slip and transients from first principles.

### 3.4 Reuse of existing JuliaMotor
- The validated **chassis + driveline + four-corner load** work from Path A ports in
  largely intact.
- Path B **swaps the tyre force law** (empirical → brush) and **adds thermal**.
- The existing **replay-and-compare harness** (`RFactorTelemetry`) is repurposed:
  inputs-in, motion-out, compare to telemetry.

### 3.5 Calibration
Feed the iRacing **driver inputs** into the Julia model; compare
**derived/observable outputs** (yaw rate, lat/long G, shock deflections, temps) to
the telemetry; **auto-fit** the brush parameters with `Optimization.jl` /
`DiffEqParamEstim`.

## 4. Phased plan

- **B0 — telemetry pipeline.** Export the §2.3 `.ibt`s, confirm MoTeC-CSV ingest,
  build the derive layer (slip / load / force from observable channels).
- **B1 — brush tyre in MTK.** Fit to skidpad + straight-line (steady-state).
- **B2 — thermal + combined slip.** Fit to warmup + trail-brake runs.
- **B3 — full MTK vehicle.** Validate predictively (inputs-in, motion-out) vs
  held-out laps.
- **B4 — real-time.** Wire the compiled DAE into the driving app (sand_racer) for
  driving on the brush tyre.

## 5. Open decisions

1. **Modeling depth** — full MTK MultiBody suspension (most faithful, more work) vs
   simplified spring/damper + camber/toe curves (faster, plenty accurate for tyre
   validation). *Recommendation: start simplified.*
2. **First fit scope** — lateral-only (skidpad first) vs lateral+long+combined in
   one pass. *Recommendation: nail lateral first.*

## 6. References
- iRacing tyre data / telemetry: Commodore's Garage #12 (Tire Data), #21 (Telemetry)
  — iracing.com
- ModelingToolkit.jl — github.com/SciML/ModelingToolkit.jl ; docs.sciml.ai/ModelingToolkit
- MTK vs Modelica/Modia — stochasticlifestyle.com "ModelingToolkit, Modelica, and
  Modia: The Composable Modeling Future in Julia"
