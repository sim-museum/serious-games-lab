# How GPL's AI cars drive (AIGPL-2, 2026-10-04)

The PO asked for the Julia AI to be rewritten on GPL's own method: *"Start by reverse engineering how GPL
does AI cars ... We're currently missing something fundamental about how AI cars choose their
trajectories."* This is what the program itself does, read from `gpl.exe` (Papyrus GPL, the 2007 build
in the PO's Wine prefix) with Ghidra 12.1 headless, cross-checked against `gpl_ai.ini`, the track `.lp`
files and the 2026-10-03 race replays. Addresses are for `gpl.exe`; the AI code is identical in
`gplc67.exe` (same strings and parameter table). No GPL code is copied here, only how it behaves.

Tooling (outside the repo): `~/tools/ghidra_12.1.4_PUBLIC`, project `~/tools/gplre/proj`, decompile
`~/tools/gplre/gpl/decomp_named.c` (all 7,032 functions, `P_<key>` = the `gpl_ai.ini` / `track.ini`
parameter, constants annotated), replay telemetry `~/tools/gplre/tel/*.txt` (`export_tel.sh`).

## 1. The fundamental difference

**A GPL AI car is not steered, and it does not invent a lane. It moves in track coordinates
(dlong, dlat) and tracks one of six lines authored per track, with a spring/damper whose goal
includes the line's own lateral velocity and lateral acceleration (feed-forward).** Every lateral
move is either "follow this line" or "change to the nearest authored line at an offset, through a
short goal blend", and the car's dlat is hard-clamped to the authored corridor `minrace..maxrace`.

Julia's AI (RaceAI, `ai.jl`) shares only the outer shape. The defects the PO sees come from what it
does instead:

| GPL | Julia RaceAI (before AIGPL-2) |
|---|---|
| goal = line(s + lookahead) + offset, goal *velocity* = line's dlat velocity × v/v_line, plus the line's lateral-acceleration feed-forward | goal = a lane value; the damper pulls the lateral velocity to **zero**, so on every curving line the car lags and is then yanked back |
| lines are authored (race, pass1, pass2, pit) and the corridor (minrace/maxrace) is a hard clamp | ±2.4 m rails, plus a **per-car lane bias** (±0.7 m, "so the field fans across the road") — the PO's "two abreast" is built in |
| pulls out only when held up for a while by a **clearly slower** car, into a lateral position its map says is free, then holds that line | pulls out as soon as `gap < v + 14 m` to anyone in its lane |
| when blocked and not passing: stays in line, speed limited by a separation law (single file) | queue-snap / side-push / yield in a post-step collision pass |
| height = spring/damper to the **track surface** (`.trk`), free flight above it | height = terrain mesh under the drawn point (can be a building — the "lurch up by the tower") |
| yaw = spring/damper to path heading + slip from the tyre lateral accel | heading from a chord tangent, then a separate low-pass |

## 2. Lines (`<track>/*.lp`)

Loaded per line index (`gpl.exe` names, `0x5578b0`): 0 RACE LINE `race.lp`, 1 MIN RACE LINE
`minrace.lp`, 2 MAX RACE LINE `maxrace.lp`, 3 PASS1 LINE `pass1.lp`, 4 PASS2 LINE `pass2.lp`,
5 PIT LINE `pit.lp` (also `pace`, `minpanic`, `maxpanic`, `spot1` names; not shipped per track).
Records every 3.0 m of dlong (index = round(dlong/3)), 5 × 32-bit:

| field | accessor | meaning |
|---|---|---|
| 0 | `0x44a6e0` | dlong speed, m/tick (36 ticks/s) |
| 1 | `0x44a8a0` | dlat velocity, m/tick, *at the line's speed* (checked: = d(dlat)/ds × speed, r 0.99, ratio 1.008, WG) |
| 2 | `0x44a7c0` | dlat, m |
| 3 | `0x44a920` | small (±0.017); read by the yaw pipeline (slot 12) — a heading/slip trim |
| 4 | `0x44a9f0` | **integer flags** (1, 2, 4, 16, 32, 65536 at WG) — waypoints (no-pass zone, straightaway, outbrake point); reads as ~0 when taken as a float |

`0x44a950` = (field1[i+1] − field1[i]) / 3: the line's lateral-velocity gradient per metre, used as
the acceleration feed-forward. Defaults when a line file is missing: race 0, min −6, max +6,
pass1 +3, pass2 −3, pit −5.

## 3. Per-tick motion (36 Hz) — `0x496930` and callees

State per car (offsets from the aiCar base): dlong `+1f6`, dlong index `+1fa`, dlong speed
`+1fe` (m/tick), dlat `+206`, dlat speed `+20a`, dlat accel `+20e`, yaw `+212`, yaw rate `+216`,
height above road `+21e` and its rate `+222`.

1. **Forces** (`0x497bc0`): centrifugal term of the track section (v²/R, signed) and the vertical
   load; height spring/damper `0x497ab0` (below).
2. **Grip available** (`0x4979b0`): traction circle × suspension/tyre condition, wheelspin.
3. **Lateral** (`0x497e00`, goal from `0x498080`):
   * lookahead la = `dlat_lookahead` (0 in the stock file); the line object returns
     `goal = line.dlat[idx(s + v·la)] + offset` (clamped into minrace..maxrace when in the corridor) and
     `goal_v = line.dlat_v[idx] × v / line.speed[idx]`;
   * `ff = d(line.dlat_v)/ds × v` (× 0.33 when it would push further out past min/max);
   * `a = k1·(goal − dlat) + k2·(goal_v − dlat_v)` — `0x496860`, evaluated with a Heun (half-step
     predictor/corrector) step — then `a += ff`;
   * k1, k2 = `dlat_accel_k1/k2` of the current *fuzzy line*, or the `cornering_` pair once
     |dlat_v| ≥ `switch_to_cornering_dlat_velocity` (0.10 m/tick);
   * the tyre must supply `a − centrifugal`; that is clamped to ±max(`max_lat_acc_from_speed`·v,
     |centrifugal|) and to the grip left (traction circle) — so an over-fast car drifts wide rather
     than turning harder;
   * yaw (`0x4982f0`): slip angle from the fraction of grip used through an inverse slip-curve
     table (`inverse_slipcurve_k`), then a spring/damper `yaw_accel_k1` (× driver scale), `yaw_accel_k2`.
4. **Longitudinal** (`0x4972c0`): target = line speed at lookahead (`0x445160`) × driver/track
   coefficients, capped; the acceleration goal (v_target − v) is limited by the **following law**
   (`+44a`, a smoothed minimum of the short/long-term map's allowed acceleration), by engine
   (`nominal_max_accel`, gear) and by braking (`braking_efficiency_coeff` × traction), and shares the
   traction circle with the lateral demand (lateral has priority; braking beyond the remaining grip
   scales the lateral down).
5. **Integrate**, then the **corridor clamp** (`0x496930`): if dlat < minrace or > maxrace, dlat is
   set to the bound (its velocity and acceleration adjusted by the same amount) — at most 11 ticks in
   a row, after which the car is left to its loss-of-control logic.
6. Pose: height above the road `0x497ab0` — while at or below ride height (0.4315 m),
   `a = k1·(ride − h) − k2·ḣ + g_ext` (`alt_accel_k1/k2` = 0.07/0.32 per tick²/tick), above it free
   flight `g_ext` (gravity plus the road's vertical curvature); pitch = `pitch_accel_coeff` × long
   accel, roll = `roll_accel_coeff` × lateral accel.

## 4. Fuzzy-line objects (how the goal is built)

One object per mode (vtables at `0x538cb0..`, parameters loaded by `0x444d30` from the same-named
`gpl_ai.ini` section, fields in this order): `dlat_lookahead, dlat_trans_time,
centrifugal_lookahead, desired_dlong_sep, short_term_lookahead, long_term_lookahead,
avoid_time_coeff, dlat_accel_k1, dlat_accel_k2, switch_to_cornering_dlat_velocity`, then the ten
`cornering_` twins. Modes: `follow_line`, `basic_line_transition`, `abrupt_line_transition`,
`try_to_draft_line_transition`, `panic_follow_line`, `follow_the_leader`, `crashing`, pit modes,
`line_improvement`.

* **follow_line**: goal as in §3 with a constant `offset` (set when the line was joined).
* **line transitions** (`0x4451d0` init / `0x4452a0` tick / `0x445300` goal): store the car's dlat
  and the old goal velocity; blend weight w rises by 1/T per tick, T = `dlat_trans_time` × driver
  scale² (basic 4 ticks, abrupt 3, cornering 3/2); goal = (1−w)·start + w·new line, goal velocity
  blended ×0.2 (abrupt: goal ×0.5 as well); at w ≥ 1 the mode becomes follow_line on the new line.
  The *goal* jumps in ~0.1 s; the car's motion is shaped by the k1/k2 spring/damper (follow_line:
  ω = 2.4 rad/s, ζ = 0.90; cornering ω = 3.3, ζ = 0.77), which is what makes GPL's moves smooth.
* **Joining a line** (`0x4477c0`): given a wanted dlat, pick the nearest of RACE / PASS1 / PASS2
  there and join it with `offset = wanted − line`.

## 5. Decisions — the BASIC RACING state (`0x442f60`, every tick)

`0x445c10` builds two **lateral maps** (`latmap`, 182 bins of 0.33 m from −30 m): short-term
(lookahead `short_term_lookahead` 17 ticks ≈ 0.47 s) and, above `long_term_check_min_speed`,
long-term (`long_term_lookahead` 108 ticks = 3 s). For every car ahead within ~98 m (`0x4481d0`)
its dlat *at the lookahead* is projected — an AI car along its own current line+offset, the
player along the race line at his current offset from it — and the bins it will cover (± its half
width + `min_dlat_sep`-type margin, +0.33 m for the player) get that car as blocker plus the
acceleration that would hold `desired_dlong_sep` (× `track_dlong_sep_coeff`; × `passee_dlong_sep_coeff`
for the designated passee) behind it. Cars beside (`0x447f50`) set left/right lateral bounds.

Then, in order:
1. **Avoid** (`0x4468f0`, short-term map): look up the bin at my own projected dlat. Not blocked →
   check side-by-side blockers (`0x445e50`: a car alongside converging → move away to the nearest
   free position, basic or abrupt transition by the lateral closing speed) and return.
   Blocked by car B:
   * if I am not faster than B, or the separation is still ≥ the desired one, or B is running at
     ≥ `auto_blocker_line_speed_pct` (0.85) of *its* line speed → **do not pass: stay on my line;
     the map's acceleration limit holds me at the following distance (single file)**;
   * otherwise a per-car counter counts the ticks I have wanted to pass; only when it exceeds
     (time to close the gap × `avoid_time_coeff`), and not in a no-pass zone (`0x800`) unless B is
     crawling (< `no_pass_zone_speed_pct_override` of line speed), search the map for the nearest
     free lateral position (`0x446ef0` / `0x4461a0`, scanning from the wanted side) and join the
     nearest line there (`0x4477c0`). A hold time is set (`0x447a60`: ≥ 36 ticks, ×1.5 for the
     designated passee, + random 0–35 ticks) before the car may return.
   * straightaway passes (long-term map, waypoint flag): only when closing faster than
     `straightaway_pass_closing_velocity` within `straightaway_pass_dlong_sep`.
2. If my dlat is outside the corridor → move to PASS1 or PASS2 on my side (`0x4472e0`).
3. Hold time expired and nothing pending → **return to the RACE LINE** (`0x4472e0`): only if the
   race line's bin at the lookahead is free; the join is a basic transition to the nearest line at
   the free point (offset 0 when the race line itself is free).
4. Off the track edge → STAY ON TRACK (`0x4464d0`).
5. Long-term avoidance with the 3 s map.

## 6. What the replays show (2026-10-03 races, GPLRA telemetry, 60 Hz)

| | Ring, 5 AI, 1 lap | WG, 4 AI, lap 1 |
|---|---|---|
| |dlat − race line|, median | 0.08 m | 0.08–0.11 m |
| p90 | 0.26–0.31 m | 0.22–0.60 m (one car 3.5 m: a pass) |
| time > 1 m off the race line | 1.6–4.9 % | 2.4–8.5 % (20.7 % for the passer) |
| max lateral speed | 5.7–7.9 m/s | 5.1–11.4 m/s |
| lateral accel p99 | 9–11 m/s² | 8–22 m/s² |
| pairs within 6 m along the track that are side by side (> 1 m apart), after the first 40 s | 24 % | 0 % |

The AI is on its racing line to within decimetres nearly all the time. When it is within 6 m of
another car it is usually directly behind it, not beside it.
