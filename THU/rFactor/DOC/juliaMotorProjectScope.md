# juliaMotor — Project Scope

Replace rFactor's isiMotor 2 physics engine with an acausal, Modelica-style
vehicle-dynamics engine built in Julia (ModelingToolkit.jl), calibrated and
scaffolded to reproduce rFactor's results from its own data files and
telemetry.

Scoped against the working installation at
`WP/drive_c/Program Files/rFactor` (rFactor 1, wine, lutris-fshack-7.2
runner), 2026-06-04.

---

## 1. What we are replacing

isiMotor 2 (rF1's engine) is a fixed-step (~400 Hz internal) rigid-multibody
vehicle simulator. Critically for this project, **its physics is almost
entirely data-driven from plain-text files** that we can parse directly:

| File | Count here | Contents |
|------|-----------:|----------|
| `*.hdv` | 202 | Chassis: mass, inertia tensor, CG, fuel tank, body aero (drag/lift/rotational damping), undertray contact points, suspension rates, brakes, diff, steering |
| `*.tbc` | 193 | Tires: lateral/longitudinal/braking slip curves (cubic-spline data points), load/speed-dependent peak shift (`SpeedEffects`, `LatPeak`, `LongPeak`), `DropoffFunction`, pressure/temperature/wear model parameters |
| `*.pm`  | 121 | Suspension as an explicit multibody graph: `[BODY]` (mass, inertia, pos), `[JOINT&HINGE]`, `[BAR]` link definitions — e.g. `GameData/Vehicles/F158/1958FrontChapman-RearLeafAndDeDion.pm` |
| engine `*.ini` | per car | RPM–torque curves, inertia, friction, boost/lifetime models |
| `*.gen` / `*.veh` | 357 / 1172 | Car instance wiring (which hdv/tbc/pm/eng a car uses), upgrades |
| `*.svm` (UserData) | per setup | Garage setup overrides applied on top of HDV ranges |

The semantics of these formats are well documented in-file (the TBC header
alone is a half-page spec of the slip-curve model) and by the modding
community. **We don't have isiMotor source, but we have its complete
parameterization plus its observable outputs** — that makes this a
system-identification problem, not a reverse-engineering-from-binary problem.

### Ground truth: telemetry

- **rFactor DAQ Plugin 1.3.2** (installer in `INSTALL/`, deployed by
  `addTelemetryLoggerToRfactor.sh`) logs CSV at up to **100 Hz** to
  `UserData/LOG/MoTeC/`. Channels (see `INSTALL/DataAcquisitionPlugin.ini`):
  driver inputs (throttle/brake/clutch/steer), per-corner **tire load, lateral
  force, slip %, pressure, 3-zone temps, wear**, damper velocities, ride
  heights, suspension positions, wheel speeds, gyro angles + rates, body
  velocities, engine RPM, gear, fuel.
- **InternalsPlugin C++ API** (headers public) if we later need
  higher-rate or extra channels (e.g. longitudinal tire force, which the DAQ
  channel list lacks) — we'd build a minimal custom logger DLL with winelib
  or mingw-w64.

### Reference vehicle

Start with the **F1 1958 mod (ORM 4.35)** — e.g. `F158/BRM/BRM P25`:

- No wings: body aero is a handful of coefficients (`BodyDragBase=0.349`,
  `BodyUp/Down/Fore/Aft`, `BodyRot`), no diffuser/CoP maps to chase.
- Manual H-pattern box, no driver aids, simple mechanical setup space.
- Cross-ply tire TBC with clean, well-commented curves.
- The `.pm` files are small (front Chapman strut, rear De Dion) — tractable
  for an exact multibody replica.

Modern cars (FBMW07, Formula E mod) become later validation targets where
aero and load sensitivity dominate.

---

## 2. Target architecture (Julia)

**Stack:** ModelingToolkit.jl (acausal components) + DifferentialEquations.jl
(stiff/fixed-step solvers) + Multibody.jl (PM suspension graphs) +
Optimization.jl / SciMLSensitivity.jl (calibration) + CSV/DataFrames.jl
(telemetry) + Makie.jl (comparison dashboards).

```
juliaMotor/
├── RFactorData.jl      # parsers: HDV, TBC, PM, ENG, GEN/VEH, SVM, AIW/GDB
├── RFactorTelemetry.jl # DAQ CSV ingestion, lap segmentation, channel mapping
├── JuliaMotor.jl       # the engine: MTK component library + assembled vehicle
│   ├── components/     #   tire (TBC-semantics), spring/damper, engine,
│   │                   #   drivetrain, diff, brakes, aero, fuel-slosh,
│   │                   #   contact (undertray), steering
│   ├── suspension/     #   (a) lookup-table kinematics from PM
│   │                   #   (b) full Multibody.jl translation of PM graphs
│   └── track/          #   flat plane → AIW ribbon → GMT mesh terrain
├── Calibrate.jl        # bench rigs, replay harness, parameter estimation
└── harness/            # wine automation, golden-lap regression suite
```

Design rules:

- **Every isiMotor data file is the single source of truth.** The Julia
  vehicle is assembled *from the same HDV/TBC/PM/ENG files rFactor reads*,
  so any car in `GameData/Vehicles` instantiates without hand-porting.
- **Acausal components mirror the file structure**: one MTK component per
  file section (`[BODYAERO]` → `BodyAero`, `[SLIPCURVE]` → spline-backed
  `TBCTire`, each PM `[BODY]`/`[BAR]` → Multibody bodies and rods).
- **Calibration parameters are explicit residual knobs** layered on top of
  the file-derived values — they absorb only what the files don't determine
  (integrator artifacts, undocumented load-sensitivity constants, contact
  patch details), and their fitted magnitudes tell us how close our model
  semantics are to isiMotor's.

---

## 3. Phases

### Phase 0 — Data foundations (1–2 weeks)
- Parsers for HDV/TBC/PM/ENG/GEN/VEH/SVM with round-trip tests over all 202
  HDVs / 193 TBCs in this install (the corpus *is* the parser test suite).
- Telemetry pipeline: run the DAQ installer script, drive the BRM P25,
  ingest CSVs, lap segmentation, unit normalization.
- **Exit criteria:** every physics file in `GameData/Vehicles` parses; one
  telemetry session of ≥10 laps loaded into DataFrames with labeled laps.

### Phase 1 — Component library & bench validation (3–4 weeks)
Build each component and validate it *open-loop* against known inputs before
any whole-vehicle assembly:
- **Tire rig:** sweep slip angle/ratio × load × speed; check the produced
  force surface against the TBC spec (normalized spline, peak shift via
  `load + speed·equivalency`, `DropoffFunction` stretch). Validate against
  in-game steady-state skidpad telemetry (tire load + lat force channels).
- **Suspension rig:** quasi-static wheel travel sweep from the PM multibody;
  compare camber/toe/motion-ratio curves against rFactor ride-height &
  suspension-position telemetry over bumps/kerbs. Lookup-table fallback if
  full multibody is too stiff for real-time later.
- **Engine/drivetrain:** torque curve + gear ratios → straight-line
  acceleration runs vs telemetry (RPM, wheel speeds, ground speed).
- **Exit criteria:** each subsystem within ~2 % of telemetry on its bench
  test, on a flat-track straight-line / skidpad protocol.

### Phase 2 — Whole-vehicle replay twin (4–6 weeks)
- Assemble full vehicle in MTK; flat plane first.
- **Input replay harness:** feed recorded driver inputs (steer/throttle/
  brake/gear from telemetry) into the Julia model; compare state
  trajectories (speed, yaw rate, lat/long g, per-corner loads).
- Open-loop replay of an unstable system diverges — so compare on
  **short re-anchored segments** (reset model state to telemetry every
  N seconds, score divergence rate), plus steady-state maneuvers (constant-
  radius corners) where open-loop is well-posed.
- Track model ladder: flat plane → AIW waypoint ribbon (centerline +
  elevation + camber, plain text) → extracted GMT meshes from `.mas`
  archives (community extractors exist) for real bump content.
- **Exit criteria:** 5-second re-anchored segments stay within 5 % speed /
  10 % yaw-rate envelope over a full lap at a real track.

### Phase 3 — Calibration (3–5 weeks)
- SciML parameter estimation (multiple-shooting / collocation) on the
  residual knobs, per-subsystem first, then jointly.
- Fit on one car/track; **validate on held-out laps, then held-out cars**
  (same TBC family) and a second track — the point of file-driven assembly
  is that calibration constants should transfer.
- Acceptance metrics, tracked in a regression dashboard: segment-divergence
  rate, RMSE on speed/yaw-rate/loads, simulated-vs-real lap time delta for a
  simple feedback driver model following the AIW racing line (target: ±1 %).

### Phase 4 — Engine scaffolding & "replacement" path (open-ended)
- **Golden-lap regression suite:** scripted pipeline — launch rFactor under
  wine (existing `rFactor.sh` env), record a standard protocol (launch,
  skidpad, flying lap), run the Julia twin, emit a scored report. Re-run on
  every engine change; this is the project's CI.
- Real-time decision point: MTK-generated RHS compiled and driven at fixed
  step (400 Hz to match isiMotor). Benchmark early — if the full Multibody
  suspension can't hit real-time, the kinematic-lookup variant is the
  real-time engine and full multibody stays the calibration reference.
- Replacement end-states, in increasing ambition:
  1. **Offline twin** (Phases 0–3): setup analysis, lap simulation, AI
     tuning — already independently useful.
  2. **Live shadow:** Julia engine consumes shared-memory state from an
     InternalsPlugin in real time, runs alongside isiMotor, continuous
     residual monitoring.
  3. **Drivable standalone:** Julia engine + joystick input + AIW/GMT track
     + simple renderer (or headless with rFactor as the replay viewer via
     `.vcr`). This is "replacing isiMotor" in the literal sense.

---

## 4. Key risks

| Risk | Mitigation |
|------|------------|
| Undocumented isiMotor internals (tire load sensitivity constants, contact patch, integrator order) | That's what the calibration knobs + telemetry fitting are for; TBC/HDV comments and modding-community docs cover most semantics |
| DAQ plugin lacks longitudinal tire force; 100 Hz may under-sample 400 Hz dynamics | Custom InternalsPlugin logger DLL (mingw-w64) if/when Phase 2 shows it matters |
| Open-loop replay divergence makes naive comparison meaningless | Re-anchored segment scoring + steady-state maneuvers + closed-loop driver model for lap-time metric |
| Setup (.svm) silently changes effective HDV values between sessions | Parse SVM in Phase 0; always log/pin the setup used for a telemetry session |
| Track mesh extraction from `.mas`/`.gmt` | Defer — flat plane and AIW ribbon carry Phases 1–2; community gMotor tools exist for Phase 2+ |
| Full PM multibody too slow/stiff for real-time | Two-tier suspension design from day one (multibody reference + kinematic lookup) |

## 5. Effort summary

~3–4 months part-time to the calibrated offline twin (end of Phase 3), with
useful artifacts at every phase boundary (parsers, tire/suspension rigs,
replay harness). Real-time drivable replacement (Phase 4.3) is a separate
follow-on decision once the twin's accuracy and performance numbers are in.

First concrete step: run `addTelemetryLoggerToRfactor.sh`, drive 10 laps in
the BRM P25, and start `RFactorData.jl` with the HDV parser.
