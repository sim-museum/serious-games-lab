---
title: "julia racer — iRacing test plan"
subtitle: "IRPLAN-2, 17 October 2026 — everything julia still needs from iRacing's Lotus 49"
---

# How to use this plan

The plan is in six parts, about **2 hours** in total. Any part can be done on its own, in any order. Parts A–C are in
the garage (no driving); D–F are on track.

| Part | What | Time | What it settles in julia |
|---|---|---|---|
| A | Export your 32 saved setups as setup sheets | 15 min | Every knob's exact value and limits |
| B | Garage ranges not yet captured | 20 min | The † (provisional) knobs in julia's Garage tab |
| C | Garage couplings | 15 min | Does camber, toe or pressure move the corner weights? How stiff is each bar? |
| D | The physics tests from 15 October (skidpad, pulls, coasts) | 30 min | The physics item (PHYSFID-1) |
| E | New on-track tests: aero, rear traction, roll | 25 min | Nose lift, the 35° diff, the bar split |
| F | Other cars: contact and drafting | 20 min | CARINTERACT-1 |

**Car:** Lotus 49, **track:** Monza GP *without* chicanes (as on 10–17), unless a test says Skidpad. Base setup: your
`261010_rung_official`.

# Before you start (2 minutes)

1. **Telemetry on** (Alt+L) for every on-track test. One file per test is ideal: stop and restart telemetry between tests.
2. **Screenshots in the garage — wait 3 seconds after each click.** On 10–17, two screenshots showed iRacing's *previous*
   solve, not the one for the knob shown (the LR 30 N/mm shot is really about 40 N/mm). Wait until the numbers stop
   changing and the labels lose their asterisk (`Spring rate:*`), then take the shot.
3. **One knob at a time, from the base setup.** Reload `261010_rung_official` before each new knob.
4. **Filing:** put everything on the USB stick under `2610xx/telemetry`, `2610xx/screenshots`, `2610xx/setups`,
   `2610xx/sheets`. Write a short note of anything you noticed (a text file is fine).

# Part A — Setup sheets (15 min, no driving)

The `.sto` files iRacing saves are encrypted, so julia cannot read the 32 setups you saved on 10–17. A setup **sheet**
lists every value in plain text.

1. In the garage, load each of the 32 setups (`261010_rung_official_<knob>_<end>`), then export it as a sheet: the
   **Export** button, or the save dialog's text/HTML copy option if it offers one.
2. Do the same for `261010_rung_official` itself and for `261005_jr_ww103`.
3. Copy the exported files to `2610xx/sheets`.

If iRacing offers no sheet export, a screenshot of each tab (Tires, Chassis, Drivetrain) per setup does the same job.

# Part B — Garage ranges (20 min, no driving)

For each knob: click to its **minimum**, wait, screenshot; then to its **maximum**, wait, screenshot; then reload the
base. For drop-down knobs, open the list and screenshot it (that shows every option).

| # | Knob | Where | How |
|---|---|---|---|
| B1 | Cold pressure (one corner) | Tires | min / max |
| B2 | Camber (LF, then LR) | Chassis, corners | min / max |
| B3 | Toe-in front, toe-in rear | Chassis, Front / Rear | min / max |
| B4 | Brake bias | Chassis, Front | min / max |
| B5 | Steering ratio | Chassis, Front | open the list (or min / max) |
| B6 | Rear ARB diameter | Chassis, Rear | open the list |
| B7 | Final drive | Drivetrain | open the list |
| B8 | First … Fifth gear | Drivetrain | open each list |
| B9 | Clutch plates, preload, drive ramp, coast ramp | Drivetrain | min / max each |

# Part C — Garage couplings (15 min, no driving)

Screenshot the **Chassis** tab with all four corners in view after each step (wait 3 s each time).

| # | Do | What it shows |
|---|---|---|
| C1 | LF camber: +5 clicks, then −5 clicks (from base) | Does a camber change move the corner weights or ride heights? (Two of your old setups suggest it moves weight sideways.) |
| C2 | Front toe: +3 clicks, then −3 | The same for toe |
| C3 | LF cold pressure: minimum, then maximum (Tires tab, then Chassis tab) | How tyre pressure moves the corner weights |
| C4 | **Big front twist:** LF perch +25 clicks (about +10 mm). Then, with that twist kept, step the front ARB arms through soft, 2, 3, 4, 5, 6, firm, then the diameters (Disconnected, 0.375, 0.4375) | The front bar's stiffness per hole and per diameter. On 10–17 the twist was only 2 mm, too small to read. |
| C5 | **Big rear twist:** reload; LR perch +25 clicks; step the rear arms and diameters the same way | The rear bar |

# Part D — The 15 October physics tests (30 min)

Unchanged from `iracing_tests_261015.txt`:

* **D1 Skidpad limit, both setups** (10 min). Skidpad, default setup: drive the circle clockwise at a steady speed, raising
  the speed in small steps (hold each step about 5 s) until the front starts to run wide. Repeat anticlockwise. Repeat
  both with WW103.
* **D2 Full-throttle pulls in 4th, both setups** (10 min). Monza main straight: from about 120 km/h in 4th, full throttle
  until the braking point. Three pulls per setup.
* **D3 Coast in gear, both setups** (5 min). At about 250 km/h lift completely (clutch in gear, no brake) and coast to 100
  km/h. Twice per setup.

# Part E — New on-track tests (25 min)

* **E1 Steady speeds on the straight** (8 min, default setup). Monza main straight: hold **150, 200 and 250 km/h** each
  for 5 seconds with a steady throttle (as steady as you can), then lift completely at 250 and coast to 150. Two runs.
  Then repeat once with the front springs at **35 N/mm**.
  *Why:* on 10–17 the nose rose 4.7–14 mm at 250 km/h depending on the spring. Holding a steady speed separates the
  aerodynamic lift from the load the drag moves to the rear; julia's nose currently rises too much on stiff springs.
* **E2 Corner exits on power, both diff ramps** (10 min). Drive ramp **35°**: five exits each from Parabolica and Lesmo 2,
  a smooth throttle squeeze from the apex, no wheelspin on purpose. Then the same at **75°**.
  *Why:* at 35° iRacing's outside rear runs about 8 % ahead while the inside rear keeps its grip; in julia the inside rear
  spins up. More exits than on 10–17 (6 at 35°) make it a fit, not a hint.
* **E3 Roll per bar on the skidpad** (7 min). Skidpad, default setup, a steady circle at about 0.8 g for 10 s, once each
  with: front bar **Disconnected**, **0.375 arms 2** (base), **0.4375 firm**; then the rear bar **Disconnected** and
  **firm** (front back to base).
  *Why:* the body roll per g at each bar setting tells how much of the car's roll stiffness each bar carries. julia
  currently judges that split (46 % front).

# Part F — Other cars: contact and drafting (20 min)

As Part 2 of `iracing_tests_261015.txt`: an AI race (Lotus 49 if AI is offered, lowest AI skill, 3–5 cars, practice
session, damage on). **F1 contact:** a light nudge at about 5 and 15 km/h closing speed, a side-by-side lean, and
(optional, last) a 30 km/h hit; one slow lap after each, and a sentence on what you saw (pull, damage, incident count).
**F2 drafting:** two lone runs down the main straight; two runs right behind an AI car, pulling out about 50 m before the
braking point; then one run each at about 10, 20 and 40 m behind.

# What julia does with the files

| Files | Tool (JuliaMotorMTK/tools) | Result |
|---|---|---|
| A, B screenshots / sheets | garage knob table | the † ranges in the Garage tab become iRacing's |
| C screenshots | `garage_fit_261017.jl` (new frames) | camber/toe/pressure couplings; each bar's rate |
| D | `irgold_steady.jl`, `longval`, `coast_compare.jl` | front/rear grip split, drive and engine-braking losses |
| E1 | `aeroheave_cmp_261017.jl` | lift vs drag transfer |
| E2 | `difframp_261017.jl`, `difframp_replay_261017.jl` | the 35° diff and rear traction |
| E3 | `arbfit_261005.jl` | the bar split |
| F | `irtest_contact_261015.jl`, `irtest_draft_261015.jl` | contact law, draft shape |
