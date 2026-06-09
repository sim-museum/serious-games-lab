# juliaMotor

Replacing rFactor's isiMotor 2 physics with a Modelica-style
(ModelingToolkit.jl) engine in Julia, calibrated against rFactor's own
data files and telemetry. Project scope: `../DOC/juliaMotorProjectScope.md`.

## Layout

| Package | Purpose | Status |
|---------|---------|--------|
| `RFactorData/` | Parsers for the isiMotor data files (HDV/TBC/PM/ENG/VEH/SVM/GEN) — the single source of truth the Julia vehicle is assembled from | Phase 0 **done**: full corpus parses, all 1172 vehicles resolve end-to-end |
| `RFactorTelemetry/` | DAQ-plugin MoTeC-CSV ingestion, metadata/beacons, lap segmentation | **done** — verified + regression-pinned against a real 10-lap session |
| `JuliaMotor/` | The engine: component library, assembled vehicle | **Phase 1 complete** — tire, engine, drivetrain, suspension kinematics all bench- and telemetry-validated; Phase 2 (vehicle assembly + replay) started |
| `Calibrate/` | Bench rigs, replay harness, parameter estimation | Phase 2–3 |

**Tire model result (2026-06-05):** `TBCTire` implements the TBC
semantics (normalized cubic-spline slip curves, load/speed peak shift,
`DropoffFunction` remapping, quadratic-Hermite `LoadSens*`, friction-
ellipse combined slip).  Against the Monaco session, per corner: measured
grip never exceeds the model envelope (0 violations in ~1620 cornering
samples each), and at the limit the driver extracted 98.3–99.3 % of the
model's peak μ.  Grip magnitude, load sensitivity, and the slip-curve
interpretation are confirmed without any fitting.  Unmodeled (Phase 3
knobs): thermal/pressure/wear/camber effects, `SpeedEffects[1]`,
isiMotor's exact combined-slip method.

**Engine/drivetrain result (2026-06-05):** `EngineModel` (RPMTorque
interpolation, coast/full throttle blend, rev limiter) reproduces the
Vanwall's historical 270 hp @ 7500.  `Drivetrain` decodes
`Gear<N>Setting`/`FinalDriveSetting` as indices into the gear file's
ratio lists sorted descending — proven by telemetry: gears 1–3 logged
RPM/wheel-speed ratios match to 4 significant figures (file order would
put gear 3 at 4.789 vs the observed 4.694).  Rolling radius from the
undriven fronts matches TBC `Radius` within 0.5 %.  Full-throttle
acceleration: r = 0.995, RMS 0.09 m/s² with one fitted resistive term.
**Suspension result (2026-06-05):** Newton constraint solver over the PM
multibody graph (`Carrier`/`solve_carrier`/`sweep`): all 484 corners of
the 121-file PM corpus solve.  De Dion signatures exact (pure bump → 0°
camber change; pure roll → camber = axle roll, matching analytical to
4e-5 rad); Chapman strut camber/toe curves pinned as regressions.
Telemetry: `Damper Velocity` ≡ d/dt(`Suspension Pos`) (r > 0.999, slope
1.00); quasi-static bivariate regression recovers the front HDV spring
rate 37700 N/m at ratio 0.999.  The rear is not regression-separable —
De Dion link reactions carry load past the springs (adding the drive-
torque term lifts R² 0.57 → 0.85) — clean rear identification is a
Phase 2 force-balance item.

**Phase 2 opener (2026-06-05):** `VehicleModel` assembles mass/aero/
tire/engine/drivetrain from the parsed files.  Forward replay (inputs →
physics → speed, no logged RPM/accel) over Zandvoort's straight
full-throttle stretches: 0.8–2.3 km/h RMS, final-speed error ≤ 2.2 %.

**Brake model (50 Hz protocol session, 2026-06-05 night):** per-wheel
torque = corner `BrakeTorque` × axle bias (plain fraction — the ×2
renormalized reading over-brakes 2×) × pressure × temperature
effectiveness.  Cold 1958 drums measured at 0.857 (100–250 °C) rising
to 0.911 (250–400 °C); with the scalar knob at 0.87, four of five hard
stops replay at 0.6–1.4 km/h RMS (the hottest-drum stop drifts +10 km/h
— the full `BrakeResponseCurve` temp model is a Phase 3 knob).  The car
is brake-torque-limited (~0.69 g vs ~1.0 g of tire grip) — historically
faithful drums.  Also pinned: HDV `Range=(start, step, count)` semantics
with out-of-range settings clamped (the Vanwall ships SteerLockSetting=6
against count 6 → in-game lock is 20°, not 22°).

**Pre-peak shape: calibrated (first Phase 3 fit, 2026-06-05/06).**
The literal whole-curve-stretch reading of the TBC spec rises far too
slowly.  The game's own `Slide Pct` channel (steering-free) measured
isiMotor's effective curve on the free-rolling fronts — 11,237
cornering samples fit F/(μN) = A·(1−exp(−u/τ)) in normalized slip
u = s/peak with **τ = 0.0905, A = 0.97, R² = 0.947**; the driven rear
fits the same τ within 8 % with a depressed plateau (combined slip —
see open items).  `reaction()` now uses this calibrated exponential
pre-peak by default (`prepeak_tau=0.0905`; pass 0 for the literal spec
reading); both forms reach exactly 1.0 at the peak, so all grip-limit
validations stand.  Binned telemetry medians track the calibrated curve
within ±0.04 through the rise.

**Steering input map (same fit):** `Steered Angle` logs zeros and
`Controller.ini` has `Speed Sensitive Steering=0.6`, so the logged
`Steering Wheel Pct` maps to wheel angle as δ = pct × lock ×
min(1, c/v) with **c ≈ 10.2 m/s** (r(v)·v constant within ±7 % across
8–60 m/s; lock = 20° after Range-count clamping).  The geometric
slip-consistency check then agrees within 1.07° RMS / 0.22° bias over
680 high-G samples, but speed-sensitive steering confounds speed with
steer input, capping what that channel can prove.

**Yaw replay (direct-steering session, 2026-06-05 late):** with Speed
Sensitive Steering disabled, the implied lock measured 20.29° at low
speed (map confirmed: wheel angle = pct × 20°).  `replay_yaw` — forward
2-DOF (sideslip, yaw-rate) integration driven by logged steer, speed,
per-corner loads and engine drive force (continuous combined-slip
derate on the rear) — over re-anchored 10 s windows: median yaw-rate
correlation 0.74–0.79, median RMS 0.08–0.09 rad/s against a 0.31 rad/s
signal, no divergence anywhere in the 573 s stint.  Remaining defect: a
systematic yaw-gain deficit (pred ≈ 0.7–0.8 × measured).  A coarse knob
grid shows the gain responds to the front/rear pre-peak balance and
peak-slip scale (τf=0.0905, τr=0.13, κ=2 reaches slope 0.79 / cor 0.79
/ RMS 0.078) — proper multi-knob estimation over re-anchored segments
(the scope's Phase 3 SciML plan) is the next work item.

**Phase 3 lateral calibration: closed (2026-06-06).** Nelder–Mead over
re-anchored 10 s yaw-replay windows (trimmed objective, fit/holdout
split): τf=0.1953, τr=0.2627, lat_peak_scale=2.5, combined-slip
exponent 0.434 — see `LATERAL_CAL`, applied by `VehicleModel` defaults.
Holdout median yaw-rate RMS **0.121 → 0.0696 rad/s**, p90 **1.23 →
0.149** (signal std 0.31).  Only the τ×scale products are identified in
the driving envelope; (κ,τ) degeneracy resolved by convention κ=2.5.

**Phase 4 foundations (2026-06-06):** track layer in RFactorData —
`read_aiw` (all 68 tracks: waypoint chains with positions/widths/AI
speeds/sector distances, grids; Zandvoort lap length 4176.75 m matches
the telemetry Lap Distance channel within 2 %), `read_gdb`, and the
**MAS archive format fully recovered** (`read_mas`/`extract`: 16-byte
signature + 256-byte TOC records + zlib or stored members; all 274
archives in the install extract, including GMT meshes — magic
`f2225500` — and DDS textures).

**GMT mesh format cracked (2026-06-06).** `parse_gmt` decodes GMT
geometry — per-file signature + `0x04000020` version, 8-corner bounding
box (meters, Y-up), object name, stride-32 vertices (position float3,
normal float3, color u32, non-interleaved UVs), u16 triangle list.
Validated end-to-end on Zandvoort's `GROUNDPLANE.GMT` (6 verts, 2 tris,
all normals up, positions on the in-file bbox plane); header invariants
checked across the mesh corpus.  Full annotated layout in
`DOC/gmtFormat.md`.  This is the geometry source for both the renderer
(Phase 4.3) and the **HAT track-collision surface** that completes the
standalone physics — the next critical-path item.

**HAT track surface (2026-06-06).** `TrackSurface`/`hat` answer, under a
world (x, z): ground height, surface normal, on-track flag, signed
lateral offset, and lap distance — the per-tire queries the standalone
physics needs.  Built from the AIW ribbon (already parsed, validated,
populated for all 68 tracks) rather than ray-casting collision meshes:
each query projects onto the nearest ribbon segment via a uniform-grid
spatial index, interpolates height/normal/width, and offsets laterally
(banking from the perp vector's vertical component).  Cross-validated
against the independently-extracted asphalt GMT vertex cloud: away from
the racing line the surfaces agree to **~0.12 m median**.  Builds for all
68 tracks.  Known limitation: the 2D nearest-segment projection can snap
to the wrong segment where track sections run parallel/stacked (Zandvoort's
main straight vs return road) — a few-percent tail; full GMT-triangle
terrain (off-track grass/sand elevation + overpass disambiguation) is the
later refinement.

**Headless simulation (2026-06-06).** `simulate_lap` integrates the full
coupled vehicle — longitudinal + lateral + yaw + load transfer + the
calibrated TBC tires — over the HAT surface, in **track-relative (Frenet)
coordinates**: arc length `s` along the racing line, lateral offset `n`,
heading-relative `ψ`.  Because `s` advances with forward motion the car
cannot drive off and get lost (the failure mode of the earlier
position-space driver) — the integration is bounded by construction.  A
curvature-feedforward + lateral/heading-feedback controller with a
spin-catch steers to the line; speed tracks a braking-feasible profile
built from the AIW corner speeds.  **It completes a full, on-track lap**
of Zandvoort (4.18 km, max lateral 4.1 m) at a conservative pace
(~254 s — the spin-catch brakes early to stay completable).  Robust
completion across pace settings and tracks is not yet there: at racing
pace the car spins at certain fast corners (the classic limit-handling
problem).  That needs a proper limit controller (friction-circle throttle
budgeting, tuned path tracking) — a bounded refinement, not an
architectural gap.  The engine physics is independently validated
open-loop (the telemetry replay tests).

**Capstone validation (2026-06-06): full coupled replay from inputs
alone.** `replay_inputs` drives the *entire* engine — forward speed,
sideslip and yaw together, with longitudinal load transfer feeding the
lateral tire loads — from only the logged steer/throttle/brake/gear (no
channel taken from telemetry).  Validated on the direct-steering Zandvoort
session over re-anchored 5 s windows (free integration of an unstable
system diverges over a full lap — the scope's prescribed method): **speed
RMS 2.7 km/h (cor 0.99)** and **yaw-rate RMS 0.17 rad/s (cor 0.66)** vs a
0.31 rad/s signal.  The longitudinal engine is reproduced end-to-end; the
yaw is moderate self-contained (the load-fed `replay_yaw` reaches
0.07 rad/s — the gap is the tire-load model, i.e. the aero/bump content
the logged per-corner loads carry).  Lateral load transfer via tire
load-sensitivity was tried and *worsened* yaw, so isiMotor already folds
that into its per-tire μ — left out.

**GMT geometry + 3D TriangleHAT (2026-06-06).** The GMT parser now
recovers full track geometry — sequential triangle-soup indices, `nverts`
from the index run not the bbox; all 260 meshes of Zandvoort's archive
decode with in-range indices (11,940 triangles).  `TriangleHAT` builds the
collision surface from the 25 `HATTarget=True` meshes (6,066 triangles) on
a uniform X–Z grid and answers height/normal by exact point-in-triangle:
**every racing-line point covered, height error median 0.10 m / p90
0.13 m / max 0.15 m** vs the AIW — no ambiguity tail (the ribbon HAT's
2D projection had p90 ~5 m where the main straight runs beside the return
road).  This is the production track surface for the standalone physics.

`simulate_lap` accepts an optional `terrain::TriangleHAT` that adds the
surface grade (gravity along the slope in the travel direction) to the
longitudinal dynamics — the car slows uphill, gains downhill.  The physics
is sound and the flat path is unchanged by default, but enabling terrain
destabilizes the current conservative driver's knife-edge completion
(the grade shifts the speed balance it was tuned for) — terrain-mode
full-lap completion is gated on the limit-handling driver.

**Limit-driver investigation (2026-06-06).** Two hypotheses were tested
and *ruled out* with data:
- *Racing-line curvature noise* — disproved.  Laplacian-smoothing the AIW
  line barely moves the lateral-demand tail (p90 26.7→25.1 m/s²) and the
  tightest-corner radius is stable (~33 m).  The curvature is already
  clean; the high apparent "demand" is the artifact of pairing speed with
  curvature at corner-entry transition points (the car is braking through,
  not holding steady-state g).
- *Rear traction-circle throttle budget* — necessary but not sufficient.
  It prevents power-oversteer on exit and lets the car reach ~75 % of the
  lap at racing pace, but without the hard brake-on-slide it loses corners
  elsewhere; combining the two only shifts which corner fails.  Completion
  remains a knife-edge of the conservative spin-catch config (sf 0.7,
  254 s lap).
- *QSS lap-optimal speed profile* — built and proven correct
  (`qss_speed_profile`): friction-circle forward/backward passes from the
  clean curvature give a feasible target (zero friction-circle violations,
  v 17.7–56 m/s).  But driving it (with a softened catch) still doesn't
  complete — reaching ~47 % at sf 0.85.  So the feasible profile is
  necessary but the *crux is the tracker*: the curvature-feedforward +
  PD path/speed controller isn't precise enough at the limit.
  Diagnosed failure mode: the car slides, the spin-catch brakes it toward
  the v→0 floor where the bicycle model's slip angles degenerate, and it
  gets trapped (stopped, unable to re-accelerate).  So three coupled
  issues remain: tracker precision at the limit, the catch over-braking,
  and the low-speed singularity.
Conclusion: the feasible-speed foundation now exists; realistic-pace robust
completion is gated on a well-tuned path+speed tracker (LQR/MPC-class)
fed by the QSS profile, plus a low-speed dynamics regime — genuine
control-systems work, not spin-catch tuning.  `simulate_lap(...;
profile=:qss)` exposes the profile for that.  The default driver (AIW
profile + spin-catch) completes a conservative lap and all tests pass.

**Drivable standalone — a human drives it (2026-06-08).** The Phase 4.3
end-state: `JuliaMotor/src/drive.jl` (`DriveCar`/`CarState`/`step!`) is a
real-time, world-space (X, Z, heading) integrator driven by *live* driver
inputs — the same validated bicycle physics as the capstone `replay_inputs`
(load transfer → lateral tire loads, combined-slip rear derate, calibrated TBC
tires), plus three additions for free human driving: world-pose integration, a
**clutch/launch model** (the validated `longitudinal_accel` makes negative
torque below idle, so it cannot pull away from rest; while the wheel-geared RPM
is below the throttle-demanded engine speed the clutch slips and the engine
turns at `rpm_demand`, locking continuously once the wheels catch up), and a
low-speed kinematic-steering blend that removes the v→0 singularity (the one
that traps the *autonomous* driver).  Crucially, a human driving needs none of
the open limit-handling controller — the person is the control loop.
`demo/drive_server.jl` (pure Julia stdlib `Sockets`, no web framework) serves
the car + real Zandvoort GMT surface and steps the physics in wall-clock real
time; `demo/drive.html` is a browser front-end.  Open the URL it prints and
drive the 1958 Vanwall around Zandvoort.  Verified end-to-end: standing-start
launch, gear shifts, steering→yaw of the correct sign, on-track/lap tracking,
stable braking to a standstill — all from the JuliaMotor physics (7 drive tests;
381/381 green).

**Cockpit view + joystick (2026-06-08).** The front-end is now a **first-person
cockpit** rendered with three.js (vendored, offline) over the **full 3D track** —
every visible mesh from the `.mas`/`.gmt` archives in world coordinates (road,
curbs, grass, sand, grandstands, pit buildings, gantries; ~9.6k triangles after
dropping a handful of mis-parsed scenery meshes via a coordinate-sanity guard).
A perspective camera sits at the driver's eye; a modelled open-wheel cockpit
(steering wheel + front tyres) reacts to steering input.  Control is the
**Logitech Extreme 3D Pro** via the browser Gamepad API — push/pull = throttle/
brake, left/right = steer, trigger = shift up, side thumb = shift down, top-left
button = **clutch** (threaded through the physics: `DriveInput.clutch`
disengages drive).  An on-screen panel shows live axes/buttons for mapping;
keyboard remains a fallback.  The server gained `/scene.json` (3D geometry) and
`/three.min.js`; `demo/render_cockpit_preview.py` renders a still of the cockpit
view to verify geometry/camera without a browser.

**Open items:** limit-handling *autonomous* driver via QSS-optimal profile + damped
tracking (→ realistic pace, terrain-mode laps); richer tire-load model
(aero load) for the self-contained yaw gap; GMT UV/material extraction
(rendering); brake temperature response; constant-loss attribution;
longitudinal pre-peak shapes.

**Drag resolution (Zandvoort session, 2026-06-05 evening):** the 69–193
km/h full-throttle band separates the resistive terms:
F = 0.168·v² + 764 N (r = 0.982).  The v² coefficient lands on the CdA
convention — `BodyDragBase` enters as F = 0.5·ρ·base·v² (0.196 nominal),
not as a raw force coefficient (0.3202, 2× off).  All five gear totals
confirmed to 4 significant figures.  Remaining Phase 3 item: attribute
the constant ~764 N (TBC `RollingResistance` units / clutch drag /
torque-curve offset).

**Phase 0 complete (2026-06-05).** Reference setup: Vanwall VW10
(S. Lewis-Evans VEH; same tires/suspension/gears files as the BRM P25)
at Monaco 1967.  First calibration session:
`UserData/LOG/MoTeC/Monaco 1967-2026_06_05_13_24_33-stint3.csv` —
10 laps, 88 channels @ 10.24 Hz, 9 beacon crossings, fastest 2:37.71.
Static tire loads reproduce HDV mass + fuel to <1 % — files and
telemetry agree, which is the premise the whole calibration rests on.

To record more sessions: `./rFactor.sh`, CTRL-m toggles logging, logs
land in `UserData/LOG/MoTeC/`.  The DAQ plugin samples at 10.24 Hz by
default — raise `Sample Rate` in `DataAcquisitionPlugin.ini` (game root)
to 50 or 100 before the next session; Phase 2 replay wants the density.

Tests for either package: `julia --project=. -e 'using Pkg; Pkg.test()'`.
