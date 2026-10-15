# SETUPMODEL-1 test plan: the Lotus 49 as connected objects, from iRacing's garage

**Goal.** julia's car becomes a set of physical objects: corner springs on perches, packers, dampers, anti-roll bars, the
tyres, the fuel tank, the gearbox and the differential. Each object is set by **exactly the knobs on iRacing's setup
page**, with the same steps and limits.

The objects are wired so that turning one knob moves the **derived** numbers the way iRacing's garage does. Derived numbers
are corner weights, ride heights, shock deflection, cross weight and gear top speeds. julia's Setup tab then offers
iRacing's own list of settings.

**What julia has today** (from `setup.jl` / `chassis_from_setup`):
- It reads every field of the two .ibt sessions (default, WW103).
- The physics uses springs, ride heights, gears, the diff ramps, toe, camber and the brake bias.
- The anti-roll bars are a fitted stiffness, not a bar with arms and a diameter.
- The derived numbers are taken as given, not computed. So a changed knob cannot move them.
- The Setup tab moves 4 values by ±15 %.

## How the capture works

**Setting knobs.** These are the inputs to model:
- Cold pressure
- Spring perch offset, spring rate, packer
- Bump and rebound clicks
- Camber, toe
- ARB arms and ARB diameter
- Brake bias
- Fuel level
- Final drive and gear ratios
- Diff clutch plates, preload, drive ramp and coast ramp
- Steering ratio, if it is adjustable

**Derived numbers.** These are iRacing's static solution of the car on its springs. They are what the model must
reproduce:
- Corner weight, ride height and shock deflection (static of max) per corner
- Cross weight
- Each gear's top speed

**One knob at a time, from the same baseline.** Every sweep starts from the saved baseline. Otherwise a coupling from an
earlier sweep hides in the next one.

**Exact anchors.** Video digits can be misread. So each sweep's endpoints are also saved as setups (see A3). If that
isn't available, a 10-second telemetry outing (Alt+L) gives an .ibt whose `CarSetup` block holds every value exactly.

### Recording checklist (2 minutes, before anything else)
1. **Check the capture shows the game.** Make a 5-second test recording of the iRacing garage and play it back. The
   261013 recording captured the Files window instead of the game.
2. **Resolution and stills.** Record at 1080p or more. Hold each state still for **2 seconds**, with the mouse off the
   numbers. Change **one click at a time**.
3. **Name each sweep.** At the start of each sweep, hover over the knob being swept or say its name, so the video is
   self-labelling. Audio is fine.
4. **Use one track.** Monza GP without chicanes, as in the 261010-12 sessions; same car, Lotus 49.
5. **Filing.** Put the videos in `~/Videos/` as `2610xx_setup_<part>.mp4`. Several short files are fine.

## Part A: setup, anchors and limits (~10 min)

| Step | Do | Captures |
|---|---|---|
| A1 | Load iRacing's **default** Lotus 49 setup and save it as `jr_base`. Show every tab: Tires, Chassis, Drivetrain. | The baseline frame |
| A2 | For **every** knob, click down to its minimum and up to its maximum, then reload `jr_base`. | The range and step of each knob, which julia's Setup tab will copy |
| A3 | In the Save dialog, look for an option to write the setup as a text or HTML sheet. If there is one, turn it on. | Exact numbers per saved setup with no OCR |
| A4 | *(optional)* Leave the pits for 10 s with telemetry on, then return. | An exact .ibt anchor for the baseline |

## Part B: the static chassis (~30 min), the most important part

In each sweep, take **5 settings** spread across the knob's range (both ends included). After each click, show the
**Chassis** tab with all four corners in view.

| Sweep | Knob (left side only; the right mirrors it) | Watch | Identifies |
|---|---|---|---|
| B1 | **Fuel level**: minimum → maximum | All corner weights, ride heights, shock deflections, cross weight | Fuel tank position (front/rear and side) and the springs' wheel rates |
| B2 | **LF spring perch offset** | All four corner weights (the diagonal!), all ride heights, LF shock deflection, cross weight, **all cambers and toes** | Corner motion ratio; how the chassis/ARB pass weight across the diagonal; whether camber or toe move with ride height |
| B3 | **LR spring perch offset** | As B2 | The same at the rear |
| B4 | **RF spring perch offset**, 2 settings only | As B2 | Checks left/right symmetry |
| B5 | **LF spring rate**: every rate on offer, perch untouched | As B2, plus whether the **perch value itself** changes | Spring motion ratio and iRacing's perch convention (free length vs preload) |
| B6 | **LR spring rate** | As B5 | The same at the rear |
| B7 | **LF packer**, 3 settings | Ride heights, shock deflection | Whether packers act statically |
| B8 | **Front ARB arms**: all holes, then **diameter**: all sizes. Baseline car first. | Corner weights. Expect no change on a square car. | Confirms the bar is unloaded when the car is level |
| B9 | **Repeat B8 with the car twisted**: first set LF perch +5 clicks, then sweep the arms and diameters again | All four corner weights, cross weight | **The bar's stiffness per hole and per diameter**, relative to the springs |
| B10 | **Rear ARB**: B8 + B9 with the LR perch twisted | As B9 | The rear bar's stiffness |

## Part C: geometry, tyres and drivetrain (~20 min)

| Sweep | Knob | Watch | Identifies |
|---|---|---|---|
| C1 | **LF camber**, 5 settings | Ride heights, LF toe, other cambers | Camber–toe–height coupling, if any |
| C2 | **Front toe**, 5 settings | Both front cambers, ride heights | Toe–camber coupling |
| C3 | **LR camber**, then **rear toe**, 3 settings each | As C1/C2 | The same at the rear |
| C4 | **LF cold pressure**, 5 settings; show Chassis after each | LF ride height, corner weights | The tyre's vertical stiffness vs pressure |
| C5 | **Final drive**: every ratio | Every gear's km/h on the Drivetrain tab | Tyre rolling radius and the rev limit behind the km/h figures |
| C6 | **1st gear**: every ratio, then 2nd–5th, 3 settings each | Gear km/h | The available ratio sets; checks C5 |
| C7 | **Diff**: preload, clutch plates, drive ramp, coast ramp, each across its range | Anything else that moves (probably nothing) | The ranges, and that the diff has no static coupling |
| C8 | **Dampers**: LF bump and rebound clicks across the range | Anything else that moves (probably nothing) | The ranges |
| C9 | **Brake bias**; **steering ratio**, if adjustable | Anything else that moves | The ranges |

## Part D (optional, on track, ~15 min): what the garage cannot show

Telemetry on (Alt+L), Monza GP without chicanes. The .ibt has per-corner **ride height** at 60 Hz, but no shock velocity.
- **D1 Dampers.** 2 laps with all four dampers at **minimum** bump and rebound, then 2 laps at **maximum**. The body
  motion over the kerbs and bumps, against the same road, gives the damping per click.
- **D2 Springs at speed.** 1 lap each at the softest and stiffest front springs. Ride height against speed separates
  the springs from aero load.
- **D3 Differential.** Standing starts and corner exits, 3 each, at drive ramp 35° and at 75°. The rear wheel speeds show
  how hard the diff locks. This is also the open question from PHYSFID-1 (WW103's extra drive).
- Already planned in `iracing_tests_261015.txt` (skidpad, 4th-gear pulls, coast-downs). Do D1-D3 in the same outing if
  convenient.

## What I build from it (no PO time)

1. **Read the video.** Extract a still at each held state and read the numbers. Save them as one table per sweep:
   knob value → every derived number. Check each against the exact anchors (A3/A4).
2. **Fit the couplings.** Expect straight lines; any non-linearity will be visible in the 5-point sweeps.
   - Each corner's spring/perch motion ratios.
   - The tyre's vertical rate vs pressure.
   - Fuel tank position.
   - Each ARB setting's stiffness.
   - Camber/toe kinematics, if present.
   - Rolling radius and rev limit.
3. **Build the object model** in JuliaMotorMTK as typed components in a Modelica-like style:
   - `Corner(spring, perch, packer, damper, camber, toe)`
   - `AntiRollBar(diameter, arms)`
   - `Tyre(pressure)`
   - `FuelTank(level)`
   - `Gearbox(final, ratios)`
   - `LSD(preload, plates, ramps)`
   - `Brakes(bias)`

   The car connects them, and a **static solver** places the car on its springs. It answers with iRacing's derived
   numbers.
4. **Acceptance.** The model reproduces **every captured garage frame** within the display resolution: 1 N, 0.1 mm,
   0.1 km/h. On the two existing sessions (default, WW103), the replay fit to iRacing must be no worse than the current
   car (closed-loop J ≤ 1.0373).
5. **julia's Setup tab** lists iRacing's knobs, with the same names, steps and limits. "Reset" returns to the session
   setup, as today. A changed knob moves the derived numbers the way iRacing's garage does.

**Your time:** Parts A–C are about 60 minutes and can be split. Part D is about 15 minutes and optional.
