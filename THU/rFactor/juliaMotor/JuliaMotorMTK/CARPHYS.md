# CARPHYS-1 — the car model as physical objects, from the .ibt

PO 2026-10-09: *"for car physics modeling, use .ibt and julia equivalent of modelica objects. If the .ibt contains a
rollbar, the julia model should contain a rollbar object. The car physics model is the sine qua non here — make it as
accurate as possible."*

The Julia equivalent of a Modelica object is a ModelingToolkit component: a `System` with its own parameters, states and
equations, joined to its neighbours through connectors (flanges carrying force and velocity, or torque and speed).
`mtkcompile` flattens the assembly into the same kind of equation set the sim steps today, so splitting the car into
objects costs nothing at run time. The point is that each physical part has one home, its parameters come from one
place (the session's .ibt or a fit against it), and it can be tested on its own.

## Today's structure (2026-10-09)

`DrivenVehicle3D` (`src/components/vehicle_3d.jl`) is one 240-line equation set. Only the four tyres are subsystems
(`BrushTyre`). Everything else is an inline term: springs, dampers and anti-roll bars are summed into one suspension
force per corner, the brakes are a torque split in the wheel equations, the clutch, engine, LSD and aero are lines in
the same block. It is fitted carefully — most of its numbers come from iRacing data through the tools in `tools/` —
but no part can be swapped, tested or read on its own.

## The objects (2026-10-09, CARPHYS-1 S2)

`src/components/chassis_parts.jl`, assembled in `DrivenVehicle3D`. Connector: a translational `Flange` (position s,
velocity v, flow force f), Modelica's `Translational.Interfaces.Flange` plus its velocity.

| Object | Per | Parameters (source) |
|---|---|---|
| `PrescribedMotion` | 4 body mounts + 4 road points | — (the body's heave/pitch/roll; the adapter's road input) |
| `CoilOver` (spring + damper + seat) | corner | wheel rate `ks` (ibt SpringRate × MR²), preload `P` (corner weight), damping `cs` / `cb`,`cr` |
| `AntiRollBar` | axle | roll stiffness `k` (ibt ArbDiameter via ARB_ID; the rear also carries the motion-ratio roll term) |
| `WheelMass` | corner | unsprung mass `m_u` (hand-set 20 kg) |
| `TyreVertical` | corner | carcass `kt`, `ct`, static load (hand-set rates) |
| `BrushTyre` | corner | μ, μx, Cα, Cκ, kμ, sliding drop, camber (fitted) |

Assembly per corner: mount → coil-over (+ the axle's bar) → wheel → tyre carcass → road. `tools/carphys_regress.jl`
proves the assembly reproduces the single-block model: same 23/24 unknowns, every channel within 1e-10 over six
manoeuvres and both setups. Still inline in `DrivenVehicle3D` (next objects): brakes, clutch, gearbox, LSD, engine,
aero, the rigid body's planar motion, steering.

## Inventory: every physical quantity the .ibt carries, and what the model has

✅ = an object or a fitted term that uses the session's value · 🟡 = present but lumped, hand-set or not from the ibt ·
❌ = missing.

| .ibt quantity (setup YAML / channel) | Physical object | In the model today | State |
|---|---|---|---|
| CornerWeight ×4, FuelLevel | sprung + unsprung masses, CG | total mass + front share from the four weights; sprung/unsprung split hand-set (m_u 20 kg); fuel mass fixed for the session | 🟡 |
| — (not in the ibt) | inertias Ixx Iyy Izz, CG height | hand-set (120 / 850 / 890 kg·m², h 0.30 m) | 🟡 |
| SpringRate ×4 | **Spring** per corner | wheel rate = rate × motion ratio² (MR measured: front 0.78, rear 0.648) | ✅ (inline) |
| SpringPerchOffset ×4, RideHeight ×4 | spring preload / static ride height | static ride heights taken from the ibt; perch offsets unused | 🟡 |
| Packer ×4, ShockDeflection (static, max) | **Bump stop / packer**, travel limits | none — the suspension has unlimited travel | ❌ |
| BumpStiffness / ReboundStiffness clicks ×4, shockVel channels | **Damper** per corner (bump ≠ rebound) | hand-set 2500 / 3000 N·s/m, symmetric, scaled per known setup; the measured bump/rebound fit was rejected by the crest test | 🟡 |
| ArbDiameter + ArbArms, front and rear | **Anti-roll bar** front, rear | a roll-only stiffness per axle inside the corner spring sum, total fitted to the gold's roll gradient; diameter⁴ for unseen bars, arms ignored | 🟡 (lumped) |
| Camber ×4 | wheel inclination | static camber + roll camber into the tyre | ✅ |
| ToeIn front / rear | wheel toe | per wheel | ✅ |
| SteeringRatio, SteeringWheelAngle(Max) | **Steering rack / column** | ratio maps wheel to road angle; MAXSTEER 0.30 rad | 🟡 |
| SteeringWheelTorque (360 Hz) | aligning torque through the rack (= force feedback) | FFB hand-shaped: front Fy × a hand trail curve + a spring, two 50 ms low-passes, tanh clip; never compared with the gold torque | ❌ |
| BrakeBias, brakeLinePress ×4 | **Master cylinder + calipers** (pressure → torque per wheel) | pedal → total torque (fitted 2956 N·m) split front/rear by a fitted torque ratio; line pressures unused | 🟡 |
| — | brake temperature / fade | none | ❌ (not in the ibt) |
| Gear ratios, FinalDrive | **Gearbox, final drive** | from the session | ✅ |
| Differential: preload, ramps, plates | **LSD** (ramp clutch-pack) | ramp LSD, one friction constant fitted to the gold's wheel-speed split | ✅ |
| Clutch / ClutchRaw | **Clutch** | slipping clutch, capacity 500 N·m (hand), c_c 60 | 🟡 |
| RPM, ManifoldPress, shift light | **Engine** (torque map, friction, inertia) | WOT torque knots + friction fitted to the gold; part throttle = throttle × WOT; Ie 0.18 corroborated | ✅ / 🟡 (part throttle) |
| LF/RF/LR/RRspeed | wheel rotation, rolling radius | front Rw 0.30 (hand), rear 0.334 (measured); wheel inertia Iw 1.0 (hand) | 🟡 |
| tyre: ColdPressure, pressure, tempL/M/R + carcass ×4, wear | **Tyre** (brush) + its pressure and temperature | brush tyre fitted (μ, Cα, μx, Cκ, load sensitivity, camber, sliding drop); no pressure or temperature dependence in the sim (a thermal component exists in `components/tyre_thermal.jl`, not used) | 🟡 |
| — (vertical) | tyre vertical stiffness / damping | hand-set kt 180/200 kN/m, ct 1000/1100 | 🟡 |
| AirDensity, coast-downs | **Aero drag**, rolling resistance | CdA 0.480, Crr 0.0139 fitted; ρ fixed 1.10 rather than the session's | ✅ / 🟡 |
| — | aero lift / downforce | none (the 1967 car has no wings — right) | ✅ |
| — | **Traction control** | a throttle-cutting aid above 25 m/s, ON by default — no such device in the real car, iRacing's or GPL's | ❌ non-physical |

## Non-physical behaviour found so far (2026-10-09)

1. **Sliding is too slippery.** Once the car slides at 15–60° of body slip, iRacing's Lotus keeps 1.03–1.11 g of
   total grip on the skidpad and about 1.0 g at the Ring. Julia's keeps 0.80–0.87 g in the PO's races of 10-08 (on
   track, contact spikes removed). The tyre's sliding drop (`rs` 0.629, fitted to locked-wheel BRAKING) multiplies
   the direction-dependent peak, so a sideways slide falls to 0.63 × μy. iRacing's slide is about the same in every
   direction (locked-wheel stop ≈ 1.0 g, sideways slide ≈ 1.05 g), while its peaks differ (1.44 vs 1.35). This is
   the PO's "washes out in a non-physical way" and the 200 m slide at 50°.
2. **A traction aid nobody asked for.** `TC_ON` (default on) cuts the throttle when the rear slip passes 7.2 % above
   25 m/s. iRacing's own full-throttle pulls run 4–13 % rear wheelspin. In the PO's races it was cutting in 0.2–2.5 %
   of on-throttle time above 25 m/s — the at-the-limit moments.
3. **Force feedback is hand-shaped and late.** It is not the aligning torque of a steering system: a front-force ×
   hand-trail term plus a centring spring, passed through two 50 ms low-pass filters (~100 ms of lag felt in the
   hands), never compared with iRacing's recorded steering-shaft torque.

## Plan

* Build the component library (Spring, Damper, BumpStop, AntiRollBar, Brake, SteeringRack, ...) and assemble a car
  that reproduces today's trajectories exactly (a regression harness) before any physics change.
* Then change physics one decision at a time, each fitted against the gold and checked by the existing acceptance
  tools (stability suite, crest, brake, scrub, skidpad).
* What the gold cannot answer goes on the evening iRacing test list (`IRTEST-261009` in the backlog).
