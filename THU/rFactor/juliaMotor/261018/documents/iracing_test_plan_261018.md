---
title: "julia racer — iRacing test plan"
subtitle: "IRPLAN-3, 18 October 2026 — updates the 17 October plan with what julia still needs from iRacing's Lotus 49"
---

# What changed since the 17 October plan

- **New E4, trail braking at high speed.** On 15 October julia took in iRacing's measured aero lift, which matched your
  laps better. It also made julia's car much looser when you brake while turning in at 250 km/h. One direct test in iRacing
  settles whether that is right.
- **D1 changed: hold the limit on the throttle.** After the understeer fix of 18 October, julia's car holds 67 of your 75
  steady skidpad circles. The 8 it can't hold are the fastest (110–160 km/h), where iRacing's car runs with the rear
  stepped out under power. D1 now asks for those steady power slides.
- **E2 matters more.** The same on-power rear grip shows up in the 35° diff test, so the corner exits double as a check.
- **No new work for fuel:** julia now records fuel in its telemetry, so every test below also gives a fuel comparison.

Everything else is as before. If you did any part of the 17 October plan, skip it here.

# How to use this plan

The plan is in six parts, about **2 hours 20 minutes** in all. Any part can be done on its own, in any order. Parts A–C
are in the garage (no driving); D–F are on track.

| Part | What | Time | What it settles in julia |
|---|---|---|---|
| A | Export your 32 saved setups as setup sheets | 15 min | Every knob's exact value and limits |
| B | Garage ranges not yet captured | 20 min | The † (provisional) knobs in julia's Garage tab |
| C | Garage couplings | 15 min | Does camber, toe or pressure move the corner weights? How stiff is each bar? |
| D | Skidpad limit on power, pulls, coasts | 35 min | The understeer item's last gap (UNDERSTEER-1), drive and engine-braking losses |
| E | Aero, rear traction, roll, **trail braking** | 35 min | Nose lift, the 35° diff, the bar split, braking stability at speed |
| F | Other cars: contact and drafting | 20 min | CARINTERACT-1 |

**Car:** Lotus 49. **Track:** Monza GP *without* chicanes, as on 10–17, unless a test says Skidpad. **Base setup:** your
`261010_rung_official`.

# Before you start (2 minutes)

1. **Telemetry on** (Alt+L) for every on-track test. One file per test is ideal: stop and restart telemetry between tests.
2. **Screenshots in the garage: wait 3 seconds after each click.** On 10–17, two screenshots showed iRacing's *previous*
   solve. Wait until the numbers stop changing and the labels lose their asterisk (`Spring rate:*`).
3. **One knob at a time, from the base setup.** Reload `261010_rung_official` before each new knob.
4. **Filing:** put everything on the USB stick under `2610xx/telemetry`, `2610xx/screenshots`, `2610xx/setups` and
   `2610xx/sheets`. A short note of anything you noticed helps (a text file is fine).

# Part A — Setup sheets (15 min, no driving)

The `.sto` files iRacing saves are encrypted, so julia cannot read the 32 setups you saved on 10–17. A setup **sheet**
lists every value in plain text.

1. In the garage, load each of the 32 setups (`261010_rung_official_<knob>_<end>`) and export it as a sheet: use the
   **Export** button, or the save dialog's text/HTML option if it has one.
2. Do the same for `261010_rung_official` itself and for `261005_jr_ww103`.
3. Copy the files to `2610xx/sheets`.

If iRacing has no sheet export, a screenshot of each tab (Tires, Chassis, Drivetrain) per setup does the same job.

# Part B — Garage ranges (20 min, no driving)

For each knob: click to its **minimum**, wait, screenshot; then to its **maximum**, wait, screenshot; then reload the
base. For drop-down knobs, open the list and screenshot it.

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
| C1 | LF camber: +5 clicks, then −5 clicks (from base) | Does a camber change move the corner weights or ride heights? |
| C2 | Front toe: +3 clicks, then −3 | The same for toe |
| C3 | LF cold pressure: minimum, then maximum (Tires tab, then Chassis tab) | How tyre pressure moves the corner weights |
| C4 | **Big front twist:** LF perch +25 clicks (about +10 mm). Then, keeping that twist, step the front ARB arms through soft, 2, 3, 4, 5, 6, firm, then the diameters (Disconnected, 0.375, 0.4375) | The front bar's stiffness per hole and per diameter |
| C5 | **Big rear twist:** reload; LR perch +25 clicks; step the rear arms and diameters the same way | The rear bar |

# Part D — Skidpad limit on power, pulls, coasts (35 min)

**D1 Skidpad: the limit, held on the throttle** (15 min, **changed**). Skidpad, default setup, clockwise first:

1. Drive the circle at a steady speed, raising it in small steps (hold each step about 5 s) until the front starts to run
   wide. Note roughly where that is.
2. **New:** at that speed, add throttle until the rear steps out a little, and hold the car in that gentle power slide on
   the circle for **10 seconds**, steady, with a little opposite lock if it needs it. Do this three times.
3. Repeat 1–2 anticlockwise, then both directions with WW103.

*Why:* julia's car holds 67 of the 75 circles from your earlier skidpad runs. iRacing holds the other 8, the fastest,
in exactly this power slide, and julia's car won't take that attitude yet. Steady slides tell how much grip the rear keeps under power.

**D2 Full-throttle pulls in 4th, both setups** (10 min). Monza main straight: from about 120 km/h in 4th, full throttle up
to the braking point. Three pulls per setup.

**D3 Coast in gear, both setups** (5 min). At about 250 km/h lift completely (in gear, clutch out, no brake) and coast to
100 km/h. Twice per setup.

# Part E — Aero, rear traction, roll, trail braking (35 min)

**E1 Steady speeds on the straight** (8 min, default setup). Monza main straight: hold **150, 200 and 250 km/h** for
5 seconds each on a steady throttle, then lift completely at 250 and coast to 150. Two runs. Then once more with the front
springs at **35 N/mm**.
*Why:* on 10–17 the nose rose 4.7–14 mm at 250 km/h depending on the spring. Steady speeds separate the aerodynamic
lift from the load that drag moves to the rear; julia's nose currently rises too much on stiff springs.

**E2 Corner exits on power, both diff ramps** (10 min). Drive ramp **35°**: five exits each from Parabolica and Lesmo 2,
squeezing the throttle smoothly from the apex, with no deliberate wheelspin. Then the same at **75°**.
*Why:* at 35° iRacing's outside rear runs about 8 % ahead while the inside rear keeps its grip; in julia the inside rear
spins up. It is the same on-power rear grip as D1's
slides.

**E3 Roll per bar on the skidpad** (7 min). Skidpad, default setup, a steady circle at about 0.8 g for 10 s, once each with:
front bar **Disconnected**, **0.375 arms 2** (base) and **0.4375 firm**; then the rear bar **Disconnected** and **firm**
(front back to base).
*Why:* the body roll per g at each setting tells how much of the car's roll stiffness each bar carries. julia
currently estimates that split (46 % front).

**E4 Trail braking at high speed** (10 min, **new**, default setup). Monza, the run to Curva Grande:

1. At about 250 km/h, brake at **roughly half pedal** in a straight line, release smoothly, and turn in. That is the
   reference. Twice.
2. Now **keep about 40 % brake on while you turn in** with a little steering, as if trail-braking deep into the corner.
   Twice. If the rear comes round, that is the result we want to see, so don't fight it beyond safety.
3. Repeat 1 and 2 with WW103.

*Why:* julia's car now slides a lot (up to about 30° of sideslip) when braked like this at 250 km/h. That comes from
iRacing's own measured lift, so it may well be right, but no test has checked it directly.

# Part F — Other cars: contact and drafting (20 min)

As Part 2 of `iracing_tests_261015.txt`: an AI race (Lotus 49 if AI is offered, lowest AI skill, 3–5 cars, practice
session, damage on).

- **F1 contact:** a light nudge at about 5 and 15 km/h closing speed, a side-by-side lean, and (optional, last) a 30 km/h
  hit. Drive one slow lap after each and write a sentence on what you saw (pull, damage, incident count).
- **F2 drafting:** two lone runs down the main straight; two runs right behind an AI car, pulling out about 50 m before the
  braking point; then one run each at about 10, 20 and 40 m behind.

# What julia does with the files

| Files | Tool (JuliaMotorMTK/tools) | Result |
|---|---|---|
| A, B screenshots / sheets | garage knob table | the † ranges in the Garage tab become iRacing's |
| C screenshots | `garage_fit_261017.jl` (new frames) | camber/toe/pressure couplings; each bar's rate |
| D1 | `irgold_steady.jl` | the on-power rear grip at the limit (UNDERSTEER-1) |
| D2, D3 | `longval`, `coast_compare.jl` | drive and engine-braking losses |
| E1 | `aeroheave_cmp_261017.jl` | lift vs drag transfer |
| E2 | `difframp_261017.jl`, `difframp_replay_261017.jl` | the 35° diff and rear traction |
| E3 | `arbfit_261005.jl` | the bar split |
| E4 | `irgold_replay.jl` (brake windows) | braking stability at speed (the 10-15 aero lift) |
| F | `irtest_contact_261015.jl`, `irtest_draft_261015.jl` | contact law, draft shape |
| every on-track file | julia's own .ibt export | fuel use, now that julia records it |
