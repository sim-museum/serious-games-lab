# JuliaMotorMTK — a component-based (Modelica-style) Lotus 49 model

**Path B** of the juliaMotor project: instead of rFactor's feel-tuned isiMotor, an
**acausal, component-based vehicle model** built with **ModelingToolkit.jl** (Julia's
Modelica equivalent), its parameters and behaviour **matched to real iRacing Lotus 49
telemetry** (iRacing uses a genuinely physics-based tyre model).

The reference data is in `../data/iracing/` (5 `.ibt` files, gitignored): one
**skidpad** session and four **Nürburgring Nordschleife** laps, Lotus 49, 60 Hz, 276
channels each. Parse them with `data/iracing/parse_ibt.py <file> [channels|yaml|summary|stats …]`
or the native Julia reader `src/ibt.jl` (`IBT.ibt_open` / `IBT.channel`).

---

## 1. What the `.ibt` actually contains

The 276 channels split into **physics we must model** and **session/UI metadata we
ignore**. Confirmed against the data (skidpad + Nordschleife):

- Car = **Lotus 49** (`CarID 42`), 8-cyl, idle 2000 / redline 9500 rpm, 5-speed
  H-pattern, no ABS (`BrakeABSactive` is always 0), no hybrid/P2P.
- The `CarSetup` YAML block carries the full parameter set (corner weights, spring &
  damper rates, ARB, gear/final-drive ratios, LSD ramp angles, brake bias, steering
  ratio, cold pressures) — these become the model's **parameters**.

### Physics channels (the model must reproduce these)
| group | channels | drives / validates |
|---|---|---|
| Chassis motion | `Speed`, `Velocity{X,Y,Z}`, `Lat/Long/VertAccel`, `Yaw/Pitch/Roll`(+`*Rate`), `Lat`,`Lon`,`Alt`,`LapDist` | rigid-body 6-DOF |
| Driver inputs | `Throttle(Raw)`, `Brake(Raw)`, `Clutch(Raw)`, `SteeringWheelAngle`, `Gear`, `Shifter`, `HandbrakeRaw` | boundary conditions |
| Engine | `RPM`, `Engine0_RPM`, `ManifoldPress`, `FuelPress`, `FuelUsePerHour`, `OilPress/Temp`, `WaterTemp`, `Voltage` | engine + its thermal/fluids |
| Driveline | `Gear`, `RPM` vs wheel speeds | clutch, gearbox, final drive, LSD |
| Per-corner suspension ×4 | `{LF,RF,LR,RR}{shockDefl,shockVel,rideHeight,speed}` | spring/damper/ARB/unsprung |
| Per-corner tyre ×4 | `…{pressure,coldPressure, tempL/M/R, tempCL/CM/CR, wearL/M/R, odometer}` | tyre vertical+thermal+wear |
| Per-corner brake ×4 | `…brakeLinePress` | brake master + bias + caliper |
| Steering feedback | `SteeringWheelTorque`, `SteeringWheelTorque_ST[6]` (360 Hz), `SteeringWheelAngleMax` | steering rack + tyre Mz |
| Fuel/mass | `FuelLevel`, `FuelLevelPct`, `FuelUsePerHour` | fuel-tank mass + CG shift |
| Environment | `Air{Temp,Density,Pressure}`, `TrackTemp(Crew)`, `Wind{Vel,Dir}`, `TrackWetness`, `Precipitation`, `Alt` | ambient + road grade + grip |
| Surface | `PlayerTrackSurface(Material)`, `IsOnTrack` | grip / validity gating |

### Ignored (not vehicle physics)
Lap timing & deltas (`Lap*`, `LapDelta*`), `Session*`, weather *forecast*, pit
service (`Pit*`, `dp*`, `*TireSets*`), camera/radio, network (`Chan*`), perf
(`Cpu/Gpu/Mem*`, `FrameRate`), FFB *tuning* sliders (`SteeringWheelPct*`,
`…MaxForceNm`, `…Limiter` — these are wheel settings, not physics), incident counts,
`P2P*`/hybrid (n/a for this car).

### Data-handling notes (found while scanning)
- **Outliers**: Nordschleife shows reset/off-track spikes (`LatAccel` to 179, torque
  to −854). Gate on `IsOnTrack==1` and drop reset transients before fitting.
- Wheel speeds exceed body speed under power (`LRspeed` 55 vs `Speed` 37) — that gap
  **is** the slip-ratio signal (iRacing gives no direct slip channel; we derive it).
- Tyre `tempM` swings 36→141 °C and `Alt` climbs 293 m over a Nordschleife lap →
  tyre-thermal and road-grade effects are real, not negligible.

---

## 2. Components needed (the answer)

Acausal model: components expose **connectors** (potential + flow) and are wired
together; ModelingToolkit assembles + simplifies the DAE. Reuse
`ModelingToolkitStandardLibrary.Mechanical.{Translational,Rotational}` and `.Blocks`
where possible.

### Connectors / domains
- **Translational** (position `s` / force `f`) — vertical suspension travel.
- **Rotational** (angle `φ` / torque `τ`) — engine→clutch→gearbox→diff→wheel chain.
- **Planar chassis frame** (custom) — a body node carrying (x, y, ψ) + the vertical
  (z, pitch, roll) coupling to the four corners; tyre contact forces flow into it.
- **Signal** (`RealInput/Output`, Blocks) — driver inputs and sensor read-outs.

### Component inventory

**Boundary / sources**
1. **DriverInputs** — replays `Throttle, Brake, Clutch, SteeringWheelAngle, Gear`
   from the `.ibt` as `RealInput`s (later swappable for a driver model).
2. **Environment** — gravity, air (ρ, T, p → engine & aero), track temp & surface μ,
   and the **road profile** per corner (grade/elevation from `Alt`, bumps).

**Chassis**
3. **SprungBody** — 6-DOF rigid body: longitudinal, lateral, yaw + heave, pitch, roll.
   Params: mass, `Ixx/Iyy/Izz`, CG height, wheelbase (a,b), track widths. Validates
   `Velocity*`, `*Accel`, `Yaw/Pitch/Roll(+Rate)`.
4. **Aero** — drag + (small) front/rear lift vs speed. Params `CdA, ClA_f, ClA_r`.
5. **FuelTank** — mass & CG contribution, drains via `FuelUsePerHour`. Validates `FuelLevel`.

**Corner ×4** (a reusable `Corner` subassembly = items 6–10, instantiated LF/RF/LR/RR)
6. **Suspension** — spring (`SpringRate`, perch offset→preload, ride height) + **damper**
   (asymmetric bump/rebound curve from the click settings) + **bump-stop/packer**, via a
   **motion ratio** (shock travel ↔ wheel travel). Validates `shockDefl, shockVel, rideHeight`.
7. **AntiRollBar ×2** (front, rear) — couples the L/R suspensions. Params from `ArbDiameter, ArbArms`.
8. **UnsprungMass** — hub/upright vertical DOF between tyre and suspension.
9. **Tyre** — *the core*. Sub-parts:
   - vertical: contact load + pressure-dependent vertical stiffness;
   - slip: **slip ratio** (wheel vs contact-patch speed) and **slip angle** (body
     velocity + yaw + steer + toe);
   - forces: **brush / Pacejka** `Fx`, `Fy`, combined-slip friction ellipse, and
     **self-aligning moment `Mz`**;
   - thermal: surface (L/M/R) + carcass temps → μ and pressure build-up.
   Validates `pressure, temp*, wear*`, and feeds steering torque via `Mz`.
10. **WheelSpin** — rotational inertia of wheel/tyre, rolling, driven (rear) or free
    (front), braked. Validates wheel `speed`, `odometer`.
11. **Brake ×4** — caliper torque from line pressure. Validates `brakeLinePress`.

**Brake master**
12. **BrakeMaster** — pedal → front/rear **bias** split (`BrakeBias 53.5%`) → 4 line pressures.

**Powertrain (rotational chain)**
13. **Engine** — torque map(RPM, throttle) + inertia + friction + idle/anti-stall +
    redline cut. Validates `RPM, ManifoldPress, FuelUsePerHour`. (Optional thermal:
    `OilTemp/Press, WaterTemp`.)
14. **Clutch** — engagement from `Clutch` input; torque transfer engine↔gearbox.
15. **Gearbox** — 5 ratios + `FinalDrive 4.11`, H-pattern selection by `Gear`.
16. **Differential (LSD)** — clutch-pack limited slip: `Preload`, drive/coast ramp
    angles, `ClutchPlates` → rear L/R torque split.

**Steering**
17. **SteeringSystem** — `SteeringWheelAngle` → road-wheel angle (`SteeringRatio 10:1`,
    Ackermann, toe), and the reverse path: tyre `Mz` + caster → `SteeringWheelTorque`
    (and the 360 Hz `_ST[6]`).

**Observers (non-physical, optional)** — map model states to `.ibt` channels for the
fitting loss (CG accelerometer incl. gravity, GPS speed, IMU rates).

### Assembly
`Vehicle = SprungBody + Aero + FuelTank + 4×Corner + 2×AntiRollBar + Powertrain
(Engine→Clutch→Gearbox→Differential) + BrakeMaster + SteeringSystem`, driven by
`DriverInputs` over `Environment`. The skidpad session (steady high-g circles,
asymmetric "oval.sto" setup) isolates **tyre Fy + load transfer + LSD**; the
Nordschleife laps exercise **everything** (grade, bumps, full gear range, braking,
combined slip).

---

## 3. Status & next steps
- [x] `.ibt` reader (Python `parse_ibt.py` + Julia `src/ibt.jl`), channel inventory, data scan.
- [x] Component architecture (this document).
- [x] Parameter extraction from the `CarSetup` YAML (`src/setup.jl`).
- [x] **`Tyre`** (isothermal Magic Formula, `src/components/tyre.jl`) + **`Corner`**
      (quarter-car ride, `src/components/corner.jl`), built with MTK v11's functional
      `System` API. Validated by `test/test_corner_tyre.jl`: tyre `Fy` saturates at
      μ·Fz, MTK matches the pure law to ~1e-13 N; corner settles to the exact static
      load with 2.05 Hz body / 16.2 Hz wheel-hop modes.
- [x] **Skidpad tyre fit** (`fit/fit_skidpad.jl`). Method: on a flat skidpad in
      quasi-steady cornering each axle's normalised grip `Fy/Fz = ay/g` exactly
      (Newton), so μ is read off geometry-free; slip angle from `VelocityX/Y` +
      `YawRate` + steer (wheelbase 2.41 m, weight split → a,b). 11.4k quasi-steady
      samples (filtered for forward motion, |β|<30°, low yaw-accel). Magic Formula
      fitted per axle (dependency-free Nelder-Mead). **Results** (fitted into
      `tyre.jl` as `TYRE_SKIDPAD_FRONT/REAR`):
      - FRONT μy=1.21, Cy=1.35, Ey=0.40, pKy1=25.7 — peak grip 1.21 g by 7.6° slip.
      - REAR  μy=1.30, Cy=1.00, Ey=0.33, pKy1=33.8 — peak grip 1.27 g by 8.7° slip
        (rear stiffer — bigger rear tyre, physically correct).
      - Loop closure (predicted vs measured ay/g, 11.4k samples): front R²=0.90,
        rear R²=0.81. Caveats: axle-effective (L/R load-sensitivity folded in),
        single load (pKy2 unidentified), post-peak falloff not resolved (skidpad
        holds the limit, doesn't push deep past it), longitudinal not fitted.
- [x] **Nürburgring fit / cross-validation** (`fit/fit_nurburgring.jl`, 4 laps,
      45k clean samples). Forward-predicts `ay` from per-axle slip + loads (loads
      from measured `VertAccel`, so grade is handled implicitly) and `ax` from
      braking slip ratios.
      - **Cross-validation (headline):** the skidpad tyre predicts Nordschleife
        lateral accel at **R²=0.86** on 23k independent cornering samples — the
        grip curve generalises to a road course untouched.
      - **Longitudinal (new, adopted):** μx≈1.27 (matches lateral μ → friction
        isotropy), pKx1≈16.6, peak at κ≈−0.16; from braking events with κ down to
        −1 (full lock). Written into `tyre_law.jl`.
      - **Deliberately not adopted:** the free fit's μ_scale≈1.48 (overfits banked
        Karussell / compression high-g, where 2.1 g is car *tilt*, not grip) and
        CdA≈1.9 m² (lumps engine-braking + rolling into "drag"). pKy2 (load
        sensitivity) is **not identifiable** from forward-`ay` — barely moves.
- [x] **Per-corner load model** (`src/corner_loads.jl`, `fit/corner_loads.jl`).
      Real per-corner `Fz` from the measured shock channels:
      `Fz_i = cw_i + MR·ks_i·(shockDefl_i − ref_i) + cd·shockVel_i`, with `cw_i`/`ks_i`
      from CarSetup, `ref_i` from quasi-static cruising, and `MR`/`cd` **calibrated**
      by the constraint that the four corner loads sum to the measured total normal
      load `m·VertAccel`. Results: **MR=0.78** (physical — Lotus 49 inboard rockers),
      cd≈2050 N/(m/s), Σloads vs measured **R²=0.885**; per-corner loads physical
      (means match static corner weights).
- [x] **Load sensitivity identified**: feeding the *measured* per-corner loads into
      the four tyres, **pKy2=1.71** (from the 2.2 placeholder) with a sane μ_scale=1.08
      (vs the 1.48 overfit under assumed transfer) → lateral **R²=0.963**. Adopted into
      `tyre_law.jl`. The real outer/inner load split is what exposes the sensitivity.
- [x] **`Corner.Fz → Tyre.Fz` coupled** in the MTK assembly (`CornerAssembly`,
      `src/components/corner_assembly.jl`): one wheel station where the suspension's
      computed load drives the tyre. Test (`test/test_corner_assembly.jl`): static
      load → tyre Fy matches the pure law exactly; a road bump flows load to grip
      (Fz 0.76→3.2 kN, Fy tracks at corr 0.95); a load-transfer `Fext` shows more
      load → more force but Fy/Fz collapsing 0.98→0.43 — the load-sensitivity
      mechanism (pKy2) of outer-tyre overload in hard cornering, now in the model.
- [x] **Chassis body — closed four-corner car** (`src/components/vehicle.jl`).
      Planar body (states v, r; inputs u, δ) with 4 `CornerAssembly`s: computes each
      corner's slip angle from body kinematics + steer, sums the tyre forces into
      Newton-Euler (`m(v̇+u·r)=ΣFy`, `Izz·ṙ=Σ moments`), and distributes lateral/
      longitudinal **load transfer** back to each `Corner.Fext`. No algebraic loop
      (dynamic suspension breaks it). 18-state stiff DAE, solves with FBDF.
      Step-steer test (`test/test_vehicle.jl`): reaches steady cornering with
      **ay = u·r exactly**, load conserved (Σ = m·g), outer wheels loaded, and a
      realistic understeer balance.
- [x] **Combined-slip coupling** (friction ellipse, `tyre_law.jl` `tyre_forces` +
      MTK `Tyre`): pure-slip `Fx0(κ)`/`Fy0(α)` scaled by `g=min(1, 1/ρ)`,
      `ρ=√((Fx0/μxFz)²+(Fy0/μyFz)²)`, so sliding-while-cornering shares the friction
      budget and the resultant caps at the μ·Fz ellipse. Pure slip is untouched
      (one slip ⇒ ρ≤1 ⇒ g=1, fitted curves preserved). Test
      (`test/test_combined_slip.jl`): resultant pinned to the ellipse, `Fy` falls
      then recovers past the longitudinal peak; MTK `Tyre` matches; no vehicle
      regression. Camber still TODO.
- [x] **Powertrain + brakes** (`src/components/powertrain.jl`). DFV-like engine
      torque curve → rigid driveline (gear×final, engine inertia reflected) → rear
      wheels (RWD); brakes split front/rear by bias (53.5%) on all wheels. Wheel-spin
      states ωf/ωr generate **κ = (ω·Rw−u)/u** from throttle/brake; body speed u
      integrates ΣFx − drag. Validated (`test/test_powertrain.jl`): 2nd-gear WOT →
      20→46 m/s at 0.4 g with traction-limited **wheelspin** (κr→0.8, drive torque >
      grip — physical); 70% braking → **−1.27 g** (at the μx limit) with the front
      bias showing (κf→−0.98 near lockup, rear light). Engine curve to be fit from
      telemetry; LSD/clutch-slip are refinements (rigid driveline for now).
- [ ] Integrate powertrain into the full `Vehicle` (u a state, per-axle ωf/ωr,
      κ→tyres) so combined slip engages during braking-into-corners.
- [ ] **Telemetry replay**: feed a measured `.ibt` lap (δ, throttle, brake) → compare
      the model's yaw rate / speed / trajectory to the recording. End-to-end validation.
- [ ] Chassis body (load transfer via `Corner.Fext`), powertrain, steering, full assembly.

### MTK v11 API note
`@mtkmodel`/`@connector` moved into the un-bundled `SciCompDSL` sub-library, so the
components use the stable **functional** API: `System(eqs, t, vars, ps; name, systems)`
+ `mtkcompile` + `ODEProblem(sys, [], tspan)`. `ODESystem`→`System`,
`structural_simplify`→`mtkcompile`.
