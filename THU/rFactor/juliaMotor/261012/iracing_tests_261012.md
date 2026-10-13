---
title: "iRacing test session — 2026-10-12"
subtitle: "Lotus 49 data for julia racer (IRTEST-261012)"
---

# Every run

- **Car:** Lotus 49. Turn telemetry logging on at 360 Hz (`irsdkLog360Hz=1`), as last time.
- **One .ibt per test:** return to the garage between tests.
- **Setup:** `261010_rung_official.sto` (the official Ring setup), unless the test says WW103 (`261005_jr_ww103.sto`).
  - After loading, check in the garage that the setup name is right. Last session one file ran the wrong setup.
  - Use the road setup, not `261010_rung_official_raised_for_skidpad`.
- **Tyre pressures:** 152 kPa cold on all four wheels. Both road setups already have this; just check it.
- **Notes:** keep a `notes_261012.txt` with which file is which test, and any spins or anything odd.
- **Time:** about 30 minutes of driving in all.

# Order

| Part | Tests | Setup | Time |
|---|---|---|---|
| 1 | 1, 2, 3 | Official Ring setup | about 20 min |
| 2 | 3 | WW103 | about 10 min |

If time runs short, skip part 2.

# The tests

## 1. Free revs in neutral (any track, standing still, about 2 min)

- Stand still in neutral with the clutch pedal released.
- **Blips:** floor the throttle until about 9,000 rpm, then release it completely. Let the revs fall all the way back
  to idle. Do this 5 times. Don't sit on the rev limiter.
- **Steady holds:** hold the throttle steady at 25 % for about 3 s, then release. Then hold 50 % for about 3 s and
  release.
- **Why:** how fast the revs rise and fall gives the engine's inertia and internal drag. The steady holds give the
  part-throttle torque at high rpm, which can't be measured while driving.

## 2. Standing starts at a fixed pedal (Monza GP Without Chicanes, main straight, about 5 min)

- Stop in a straight line on the main straight, in 1st gear with the clutch pressed.
- Hold the throttle steady at about 50 %.
- Release the clutch slowly, over about 1 s, keeping the throttle at 50 %.
- Once the car is rolling, go to full throttle and accelerate through 1st and 2nd. Then stop and repeat.
- Do 5 starts.
- **Why:** in iRacing the engine bogs down at the clutch bite (from about 9,000 to about 1,800 rpm) and the rear tyres
  grip. In julia racer the engine stays high and the rears spin, so launches are about 20 % slow.

## 3. Held power drifts (Watkins Glen Classic, about 10 min per setup)

Use **Watkins Glen Classic**, the 1956-70 course, which is the same layout as julia racer's Glen. "Classic Boot" is the
later layout and is not the one. If the Glen isn't available, use **Monza GP Without Chicanes** at the Parabolica
(right-handers only).

How to hold a drift:

1. **Gear:** choose one that gives 7,000-8,000 rpm mid-corner. With the official gearing, 2nd is about 57 rpm per
   km/h and 3rd about 44 rpm per km/h. So use 2nd at about 120-135 km/h, or 3rd at about 160-180 km/h.
2. **Entry:** take the corner at about 80-90 % of your normal speed. Brake in a straight line, turn in, then settle
   for about 1 s at about 30 % throttle with the car gripping.
3. **Break the rear loose:** squeeze the throttle to 60-100 % over about half a second, until the rear steps out.
4. **Catch it small:** as the tail starts to come round, wind on just enough opposite lock to stop the rotation. Aim
   to catch it at 5-10° of body slip, not let it swing wide. At that angle the steering is roughly straight, or a little
   opposite lock.
5. **Hold for 2-3 s:** keep the throttle and steering nearly constant. The throttle sets the angle (more throttle =
   wider). The steering points the nose. A steady stretch matters more than hitting exactly 7°.
6. **Don't lift sharply:** that throws the weight forward and snaps the car round. If the angle grows past about 15°,
   ease the throttle a little.
7. **Exit:** ease off the throttle gently and unwind the steering.

How many:

- 4-6 good holds **each direction**. Spins are fine; note them.
- Then drive 2-3 normal laps at your usual pace.

Part 2: repeat test 3 with the WW103 setup.

**Why:** the skidpad slides (test 1 on 10-10) were big ones, 20-50°, at oval pressures (152 left / 207 right).
Steady cornering at the limit is also measured. iRacing and julia racer differ most between the two: iRacing's Lotus
drifts about 4° wider (default setup) and about 2.7° wider (WW103) while turning at the same rate. Because the Glen
layout matches, you can afterwards drive the same drifts in julia racer and compare by feel.

# Afterwards

Copy the .ibt files and `notes_261012.txt` to this stick under `261012/telemetry/`. They will then be copied to
`~/gold standard/julia racer/261012/`.
