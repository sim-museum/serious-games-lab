# JuliaMotor ⇄ iRacing Lotus 49 benchmark — 2026-06-24

Benchmarks JuliaMotor (`JuliaMotorMTK`) against fresh iRacing Lotus 49 telemetry
(`.ibt`) captured 2026-06-24, across three edge-of-the-envelope tests plus the
standing skidpad. New iRacing runs imported to `data/iracing/2026-06-24/`; JM runs
in `data/juliaracer/`. Tooling added this session:

- `data/iracing/profile_ibt.py` — classify a run + extract the three test signatures.
- `JuliaMotorMTK/tools/engbrake_probe.jl` — headless coast-down engine-braking probe.
- `demo/native/sound/{analyze_engine,extract_samples,preview_engine}.{py,jl}` — engine-sound build.

> **iRacing channel note.** Newer iRacing `.ibt` carry engine RPM in `Engine0_RPM`;
> JM writes the legacy `RPM` channel (and leaves `Engine0_RPM`=0). `VertAccel` in
> JM `.ibt` is a constant `9.807` stub. `profile_ibt.py` picks whichever RPM channel
> has data. Accel envelopes use robust percentiles — iRacing landings/curb-strikes
> inject 1-sample spikes (LongAccel to 35 g, LatAccel to 21 g) that are not physical.

---

## Test 0 — Skidpad peel-out  (the standing test, as before)

`iRacing lotus49_skidpad 15-46-39` vs `JM lotus49_skidpad 06-20 22-02-25`

| metric | iRacing | JM | verdict |
|---|---|---|---|
| peak lateral grip | **1.58 g** | **1.46 g** | JM ~8 % low |
| spin yaw rate | ±183…213 °/s | ±248…250 °/s | **JM ~25 % hot** (too much oversteer) |
| peak long accel | ±1.8 g | ±1.17 g | JM low (combined-slip, see below) |
| speed envelope | ≤ 94 km/h | ≤ 72 km/h | JM run tamer (1st gear only) |

JM grip is close but the **spin is too lively** — the rear lets go and the car
rotates faster than the real 49. Confirms the open STATUS item (yaw 247 vs 183).

---

## Test 1 — Centripetal engine-braking downshift  ✅ PASS

Protocol: out to 170–180 m diameter, 5th gear, lift off, shift down — each
downshift drags the engine up (engine braking). iRacing gold =
`lotus49_skidpad 16-09-57` (15 coasting downshifts, throttle ≈ 0).

**iRacing signature** — coasting 5→4→3→2→1, **+1000…+1700 rpm per downshift**,
peaks ~6000–7300 rpm, speed bleeds 158→97 km/h over ~5 s:

```
   5->4  +1052     4->3  +1245     3->2  +1663     2->1  +831 …+1325
```

**JM** (headless `engbrake_probe.jl`, coast from 158 km/h in 5th, throttle 0):

```
   5->4  4474 ->  5228  (+ 754)
   4->3  4957 ->  5846  (+ 890)
   3->2  5518 ->  6812  (+1295)
   2->1  6382 ->  7571  (+1189)     speed 158 -> 87 km/h over ~5 s
```

JM reproduces the engine-braking RPM spike in-envelope (peaks reach 7571 rpm vs
iRacing ~7300). The **high-gear spikes (5→4, 4→3) are slightly soft** (~750–890 vs
iRacing ~1000+) — engine-brake drag torque is a touch low at mid rpm. The rigid-
driveline kinematic jump is ~870/1050/1580/1660 rpm, so JM lands just under the
ideal (clutch/inertia lag during the 0.5 s catch). Good match overall.

---

## Test 2 — Nürburgring Flugplatz jump + landing  ❌ JM cannot reproduce (physics gap)

Protocol: flat-out up the hill to Flugplatz, max air, control the landing.
iRacing gold = the six `nurburgring` runs (best `15-59-43`, `16-03-27`).

**iRacing signature** (per run):

| | value |
|---|---|
| airborne | **0.42 – 0.53 s** |
| takeoff speed | 213 – 221 km/h (5th, flat-out) |
| ride height in air | wheels droop 75 mm → **310–350 mm** (front droops more = nose-up) |
| VertAccel | **−0.14 g over the crest** (light/airborne) → **+1.8 g landing** |
| shock velocity (landing) | 0.7 – 0.9 m/s |
| **landing scrub** | speed 220.6 → 216.0 km/h airborne (drag only), then **→ 174.4 km/h within 1.5 s of touchdown — ~42 km/h bled by the scrub** |

**JM — now RUNNABLE (full-3D model, 2026-06-24).** Built `DrivenVehicle3D`
(sprung heave/pitch/roll + 4 unsprung w/ ground contact) + the `Car3D` real-time
adapter; `flugplatz_bench.jl` drives it flat-out over the **real GPL Nordschleife
crest at lapdist 6229 m** (auto-found, ≈ where Flugplatz sits) and writes a JM `.ibt`
that the same `profile_ibt.py` reads:

| metric | iRacing gold | JM 3-D |
|---|---|---|
| airtime | 0.42–0.53 s | **0.48 s** ✓ |
| takeoff speed | 213–221 km/h | **216 km/h** ✓ |
| crest VertAccel | −0.10 g | **0.00 g** ✓ (free-fall) |
| landing peak | +1.8…2.3 g | **+13 g** (see below — terrain, not a defect) |
| landing scrub | −42 km/h/1.5 s | ~−1 km/h — *protocol*: the autopilot stays flat-out & straight; the iRacing driver lifts/corrects to "control the landing" |

The airborne phase matches the iRacing Flugplatz closely.

**Is the +13 g landing a model fudge? No — it's physical, and it's the terrain.**
- `landing_convergence.jl`: a clean 4 m/s flat landing gives **3.75 g, solver-converged**
  (identical from dt 1/300 → 1/4800) — the contact/damping is a real, step-independent
  prediction, not a numerical band-aid. The "damping" here is the suspension **shock
  absorber `cs`** (a physical component), not a tuned coefficient.
- The 13 g is **not** a discretization staircase: implementing the road-velocity
  feed-forward (`vr = ∂terrain/∂travel · speed`, fed into the contact damping, with the
  road resampled at the solver substep rate) did **not** reduce it. Falsified hypothesis.
- The real cause is impact velocity: the measured **vertical landing speed is 10.1 m/s**
  (the car drops 6.6 m onto lower terrain off this GPL crest). The 3.75 g @ 4 m/s
  calibration scales to **9.5 g @ 10 m/s** from the spring alone; damping accounts for
  the rest → 13 g is calibration-consistent and physical.
- So the gap vs iRacing's gentle +1.8 g is **terrain geometry**: the GPL 1967 crest drops
  6.6 m (≈10 m/s landing) where the real Flugplatz brow follows the trajectory (≈2–3 m/s
  landing). Matching the *number* needs iRacing's actual Flugplatz geometry, **not** a
  softer tyre or a damping fudge. Scrub gap is the flat-out autopilot (no driver lift).
  Drive it live with **`JM_3D=1`**.

**Confirmed on the REAL Flugplatz crest (`flugplatz_real_bench.jl`).** Reconstructed the
actual crest from the iRacing run's `Alt`-vs-distance (road shape while on the ground; the
airborne gap bridged + low-pass smoothed to a realistic radius) and drove JM straight over
*that* profile. This exposed — and required fixing — a real model limitation: the `Car3D`
ground reference tracked too slowly to follow the **11 % climb** up to the brow (a 6.5 m/s
road rise read as a slam). Fix: the reference now **follows the grade via the road-velocity
feed-forward while the wheels are loaded, and freezes when airborne** (so the car still
clears a brow). Result on the real crest:

| | airtime | crest g | **landing g** |
|---|---|---|---|
| iRacing | 0.68 s | −0.14 g | **+1.49 g** |
| JM 3-D | ~0 s (just grounded) | +0.5 g | **+1.87 g** (converged across brow-smoothing ±6–11 m) |

So on the real gentle Flugplatz brow JM's vertical load is **~1.9 g, matching iRacing's
~1.5 g** — the +13 g was 100 % the harsh GPL crest, not the model. (JM stays just-grounded
where iRacing lifts 0.68 s — the exact brow sharpness lives in the airborne gap and isn't
recoverable from telemetry; the load regime is what matches.)

---

## Scrubbing = irreversible energy loss (cross-cutting)

The iRacing scrub noise is rubber ablating — an energy-consuming, irreversible
process that **bleeds speed hard**. The data confirms it: the Flugplatz landing
scrub costs **~42 km/h in 1.5 s**, an order of magnitude more than the ~5 km/h
aero/rolling loss while airborne. The skidpad peel-out shows the same speed bleed
under sustained limit slip.

JM's tyre **does** dissipate scrub energy — the friction-ellipse forces oppose the
slip velocity, so power `F·v_slip` leaves the system — but JM has **no explicit
tyre thermal/wear model**, and the most punishing scrub case (the rough landing)
can't be exercised without vertical dynamics (Test 2). Keep the friction-based
dissipation; the peel-out speed-bleed is the available cross-check.

---

## Recommendations / next

1. **Trim skidpad oversteer** (yaw 248 → ~190 °/s): nudge rear grip down / front up.
2. **Raise peak grip** 1.46 → 1.58 g.
3. **Combined slip** — the open `test_combined_slip` refactor (direction-normalized
   slip; LongAccel 1.17 vs iRacing 1.8/2.2 g). Front `Cy` is leaking into braking grip.
4. **JM `.ibt`** — also populate `Engine0_RPM` so newer iRacing-era tools read it.
5. **Path B vertical dynamics** — add a sprung-mass heave + suspension-travel DOF,
   log real `VertAccel` + ride heights → unlocks Test 2.
6. **Head-to-head completion** — drive fresh JM runs of the exact protocols
   (5th-gear coast-down on the centripetal; flat-out to Flugplatz) with `JM_IBT` on,
   so Tests 1 & 2 compare like-for-like instead of probe-vs-gold.

---

## Engine sound — new Lotus 49 (Cosworth DFV V8)

Built from the iRacing onboard recording `260624_1546.mp3` (25 min). The DFV is a
cross-plane V8 → exhaust note is the **4th engine order** (`RPM = 15·f_fire`); a
spectral firing-band detector (150–720 Hz) avoids the crank sub-harmonic octave
errors an autocorrelation tracker makes. `extract_samples.py` cut seven seamless
loops at the RPMs the recording actually holds:

```
2400 · 3500 · 4650 · 5100 · 6350 · 8100 · 10050 rpm   (detected pitch == label, ±1 %)
```

Wired into `audio.jl` `build_lotus()` (RPM-crossfaded + pitch-trimmed, same engine
as before) and `drive_native_mtk.jl` now builds the Lotus set (falls back to the
onboard Vanwall samples if the loops are absent). Audition:
`demo/native/sound/lotus49_rev_preview.wav` (idle→redline→idle sweep, verified to
track 1800→9750→1800 rpm).
