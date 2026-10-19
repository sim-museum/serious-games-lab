---
title: "julia racer — iRacing test plan"
subtitle: "IRPLAN-4, 19 October 2026 — what julia still needs from iRacing's Lotus 49 after the 18 October session"
---

# What the 18 October session settled

Thank you for the 18 October session: 38 telemetry files, 31 setup sheets and 3 AI races. What it settled in julia:

- **Anti-roll bars:** the five skidpad runs with front/rear arms soft and firm gave each bar its own stiffness law. julia's
  body roll per g now matches iRacing's to within 0.013°/g on all five.
- **Engine power and air:** your pulls showed iRacing's engine loses power in thinner air. julia now gives each track
  iRacing's air (Monza 1.151 kg/m³, Nürburgring 1.095–1.099), and its straight-line pulls went from 92 % to 98 % of yours.
- **Camber and the garage:** the setup sheets fitted how camber changes the corner weights and ride heights, so julia's
  Garage tab now shows the same numbers as iRacing's for every camber.

What it left open, and why this plan exists:

1. **Your accelerator only reached 80.7 %** in iRacing on 18 October (the files record it). Full-throttle tests at 80.7 %
   are part-throttle tests. That probably also explains the last 6 % of power missing at 8,000–9,000 rpm. **Part A fixes
   it first.**
2. **Part-throttle power.** julia's engine map at 25–75 % pedal was fitted before the air-density change and now
   disagrees with your files.
3. **Trail braking at 250 km/h** came out inconclusive: julia's car slid 5.0°, iRacing's 6.8°, on your inputs, but both
   runs were gentle. A firmer version settles it.
4. **The rear's grip under power** (the understeer item): julia's car needs 72 % throttle to hold a slide iRacing holds at
   48 %. Steps of throttle on a steady circle measure exactly that.
5. **Car-to-car contact** (your new backlog item): your three AI races have collisions in them. A few deliberate,
   controlled contacts tell julia what a touch of wheels does.
6. **Two garage questions:** the "tire pressure max" sheet reads 179 kPa, but 207 kPa appears in an earlier skidpad file;
   and the bars' stiffness for the holes you didn't test (3, 4, 6) and for the other diameters is still estimated.

# How to use this plan

Six parts, about **1 hour 50 minutes** in all. Any part can be done on its own, in any order, **except Part A, which goes
first.** Part B is in the garage; the rest are on track.

| Part | What | Time | What it settles in julia |
|---|---|---|---|
| A | Pedal check (and recalibrate if needed) + full-throttle pulls | 15 min | Full power at 8,000–9,000 rpm (ENGINERHO-1) |
| B | Garage: pressure range, list knobs, bar stiffness per hole | 15 min | The pressure question; every bar hole (RARBARMS-1) |
| C | Part-throttle steps on the straight | 15 min | The engine map at part throttle (ENGINERHO-1 S2) |
| D | Skidpad: throttle and brake steps on a steady circle | 25 min | The rear's grip under power and braking (UNDERSTEER-1) |
| E | Firm trail braking at 250 km/h | 15 min | Braking stability at speed (TRAILBRAKE-DRIFT) |
| F | Controlled car-to-car contacts | 25 min | How contact spins and launches cars (CARCOLLIDE-2) |

**Car:** Lotus 49. **Track:** Monza GP *without* chicanes, as before, unless a test says Skidpad. **Base setup:**
`261010_rung_official` (the default) unless a test says WW103 (`261005_jr_ww103`).

# Before you start (2 minutes)

1. **Telemetry on** (Alt+L) for every on-track test, one file per test if you can (stop and restart telemetry between
   tests).
2. **Garage screenshots: wait 3 seconds after each click**, until the numbers stop changing and no label has an asterisk.
3. **One knob at a time, from the base setup.** Reload the base before each new knob.
4. **Filing:** put everything on the USB stick under `261019/telemetry`, `261019/screenshots` and `261019/sheets`. A short
   text note of anything you noticed helps.

# Part A — Pedal check and full-throttle pulls (15 min, do this first)

**A1 Check the accelerator reaches 100 %** (3 min). In iRacing: Options → Controls, press the accelerator fully and watch
its bar. If it stops short of the end, run iRacing's **Calibrate** wizard for the pedals, pressing each pedal to the floor
when asked. Do the same check for the brake and clutch. A screenshot of the bars at full press is useful.

**A2 Full-throttle pulls in 4th, both setups** (12 min). Monza main straight: from about 120 km/h in 4th, **floor the
accelerator** up to the braking point. Three pulls with the default setup, three with WW103. Keep the pedal on the floor
the whole way.

*Why:* on 18 October the pulls topped out at 80.7 % pedal. julia matches your 80.7 % pulls to 98 %; a true 100 % pull
gives the engine's real top end.

# Part B — Garage questions (15 min, no driving)

**B1 Tyre pressure range** (3 min). Tires tab, any corner: click the cold pressure down to its **minimum**, wait,
screenshot; then up to its **maximum**, wait, screenshot. Reload the base.

**B2 The drop-down lists** (4 min). Open each list and screenshot it: steering ratio (Chassis, Front), rear ARB diameter
(Chassis, Rear), final drive and each of the five gears (Drivetrain).

**B3 Bar stiffness per hole, with a twist** (8 min). Screenshot the Chassis tab, all four corners in view, after each step:

1. LF spring perch **+25 clicks** from the base (this twists the car so the front bar shows in the corner weights).
2. Keeping that twist, set the front ARB arms to **soft, 2, 3, 4, 5, 6, firm** in turn.
3. Then the front diameters: **Disconnected, 0.375, 0.4375** (arms at 2).
4. Reload the base. LR perch **+25 clicks**; the rear arms **soft … firm** and rear diameters the same way.

*Why:* the 18 October roll runs measured the bars at soft, 2, firm (front) and soft, 5, firm (rear). The other holes and the
other diameters are still interpolated in julia. The corner weights under a twist give each one directly.

# Part C — Part-throttle steps on the straight (15 min, default setup)

Monza main straight, 4th gear. From about 120 km/h hold the accelerator **steady at about 25 %** until the braking point.
Then the same at **50 %** and **75 %**. Twice each. Exact percentages don't matter, but **steady** does: rest your foot,
don't chase a speed.

*Why:* julia's part-throttle map was fitted before it learned about air density, and at 25–75 % it now differs from your
files. Steady pedal positions give the map point by point.

# Part D — Skidpad: throttle and brake steps on a steady circle (25 min)

**D1 Throttle steps** (12 min). Skidpad, default setup, clockwise. Settle on a steady circle at about **0.8 g** (a bit
below the limit). Then, **without changing the steering**, add throttle in three steps, about **+10 %, +20 %, +30 %**, holding
each for 5 seconds. Let the car run wide or step out, whichever it does; just note which. Back to the steady circle between
steps. Three times, then anticlockwise, then WW103 in both directions.

**D2 Brake steps** (8 min). The same steady 0.8 g circle, default setup. Brake lightly in three steps, about **10 %, 20 %,
30 %** pedal, 3 seconds each, steering unchanged. Twice each direction.

**D3 One steady power slide** (5 min, optional). As 18 October's D1: at the limit, add throttle until the rear steps out a
little and hold that slide for 10 seconds. Once per direction, default setup. (Your 18 October slides are good; one more
pair with the pedal at a true 100 % available is a cross-check.)

*Why:* julia's car needs 72 % throttle to hold a slide that iRacing holds at 48 %: its rear tyres lose too little grip
when they also have to drive the car. Throttle and brake steps on a fixed circle show how much side grip each amount of
drive or braking costs, which is the shape julia's tyre model needs.

# Part E — Firm trail braking at 250 km/h (15 min)

Monza, the run to Curva Grande, default setup:

1. At about 250 km/h, brake firmly, about **60 % pedal**, in a straight line; release and turn in. Reference, twice.
2. Now **keep about 50 % brake on while turning in**, with more steering than on 18 October: the car should be turning
   noticeably while still braking hard. Three times. If the rear steps out, that is the result we want; keep it safe.
3. The same at the **Parabolica** entry (from about 230 km/h), three times.
4. Repeat 1–3 with WW103.

*Why:* on 18 October the trail braking was gentle (about 40 % pedal, little steering), and julia and iRacing differed by
less than 2° of slide angle, which doesn't settle anything. Firmer braking into a real turn-in shows whether julia's car
is as stable as iRacing's at 250 km/h.

# Part F — Controlled car-to-car contacts (25 min)

An AI session as on 18 October (Monza, Lotus 49 AI if offered, lowest AI skill, 3 cars, practice or race, damage on).
Do these at **low speed and on a straight**: they are about what contact does, not about racing.

| # | Do | Closing speed | Watch for |
|---|---|---|---|
| F1 | Your front wheel touches an AI car's **rear wheel** from behind (wheel to wheel, slightly offset) | 5, then 15 km/h | Does either car spin? Does one ride up? |
| F2 | Side by side, steer gently into the AI car so **the side wheels rub** | 0–5 km/h sideways | Do both cars turn? Which way? |
| F3 | Your **front wheel against its rear wheel** with more overlap, from behind | 20 km/h | Does a car launch or flip? |
| F4 | Your nose into its **rear wheel's side** at an angle (a "T-bone" on the wheel) | 15 km/h | Spin rate, damage |
| F5 | Optional, last: a 30–40 km/h version of F3 | 30–40 km/h | The launch |

After each contact: drive one slow lap and write one sentence (who spun, which way, did anything leave the ground, damage,
incident count). Keep telemetry running throughout. Restart the session if a car is wrecked.

*Why:* you asked for julia's collisions to behave like iRacing's. In iRacing a touch of a spinning tyre spins both cars and
wheel-over-wheel launches them; julia's cars bounce off each other "like beanbags". Your 18 October races have contacts
in them, but at unknown closing speeds and overlaps. These controlled ones give the law.

# What julia does with the files

| Files | Tool (JuliaMotorMTK/tools) | Result |
|---|---|---|
| A1 screenshots, A2 | `wot_density_261018.jl`, `irgold_replay.jl` | full power to 9,000 rpm (ENGINERHO-1) |
| B1 | garage knob table (`garage_lotus49.toml`) | the pressure range |
| B2 | garage knob table | every list knob's values |
| B3 | `garage_fit_261017.jl`, `arbarms_261018.jl` | each bar's stiffness per hole and diameter (RARBARMS-1) |
| C | `irtest_draft_261015.jl` (pedal-binned), `wot_density_261018.jl` | the part-throttle map (ENGINERHO-1 S2) |
| D1–D3 | `powerslide_261018.jl`, `irgold_steady.jl` | the rear's grip under drive and braking (UNDERSTEER-1) |
| E | `trailbrake_261018.jl`, `irgold_replay.jl` (inject) | braking stability at speed (TRAILBRAKE-DRIFT) |
| F | `irtest_contact_261015.jl` + your notes | the contact law: spin, ride-up, launch (CARCOLLIDE-2) |
