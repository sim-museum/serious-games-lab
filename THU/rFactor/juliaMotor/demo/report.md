---
title: "juliaMotor — Project Report"
subtitle: "A Julia physics engine reproducing rFactor's isiMotor, toward racing with Julia-controlled car motion"
date: "2026-06-06"
geometry: margin=2.2cm
fontsize: 11pt
colorlinks: true
---

# 1. The goal

Replace rFactor 1's **isiMotor 2** physics engine with an acausal,
Modelica-style vehicle-dynamics engine written in **Julia**, calibrated to
reproduce rFactor's behaviour from rFactor's own data, and ultimately to
**race on a track with the car's motion computed entirely by the Julia
engine** — as a standalone Linux application that reuses rFactor's cars and
tracks.

The work is grounded throughout in the working rFactor install (running
under Wine) and in **four telemetry sessions the owner drove** (Monaco
1967 and three Zandvoort 1967 stints, logged at 10–50 Hz by the rFactor
DAQ plugin). Those laps are the ground truth every calibration and
validation step is measured against.

# 2. Approach

isiMotor's physics is almost entirely **data-driven**: chassis, tyres,
suspension, engine and gearing live in plain-text files, and the meshes /
textures in lightly-obfuscated binary archives. So this is a **system-
identification** problem, not a binary reverse-engineering one: parse the
files as the single source of truth, build matching physics components,
and validate their outputs against the driven telemetry. Where a
component's behaviour isn't fully determined by the files (integrator
details, undocumented constants), explicit **calibration knobs** absorb
the residual, and their fitted size measures how close the model is.

# 3. What has been done

All of the following is implemented, tested, and validated against the
owner's telemetry. Three Julia packages, ~10,600 passing tests total.

**Data layer (`RFactorData`).** Parsers for every rFactor format —
chassis (HDV), tyres (TBC), suspension multibody (PM), engine/gears
(INI), car wiring (VEH/GEN/SVM), track waypoints/events (AIW/GDB). The
two **binary** formats were reverse-engineered from scratch: the **MAS**
archive (all 274 archives in the install extract) and the **GMT** mesh
(full track geometry, 260/260 meshes of a track, ~12 k triangles). Every
one of the install's 1,172 cars resolves end-to-end through its files.

**Physics components (`JuliaMotor`), each bench- and telemetry-validated:**

| Component | Result vs telemetry |
|---|---|
| Tyre (TBC slip-curve + load/speed peak shift) | measured grip stays within the model's μ-envelope; driver reaches 98–99 % of peak |
| Engine (RPM-torque map) | 270 hp @ 7500 rpm — the historical Vanwall figure |
| Drivetrain | all 5 gear ratios match logged RPM÷wheel-speed to 4 sig figs |
| Brakes | bias convention pinned; ~0.69 g, torque-limited (period drums) |
| Suspension (PM multibody solver) | De Dion & Chapman kinematics exact; 484/484 corners of the corpus solve |
| Aero drag | `BodyDragBase` confirmed a CdA coefficient (½ρv² convention) |

**Calibration.** Phase-3 lateral calibration (Nelder–Mead over re-anchored
yaw-replay windows) reduced holdout yaw-rate error from 0.12 to
**0.07 rad/s**.

**Capstone validation (Figure 2).** The *complete coupled engine* —
longitudinal + lateral + yaw with load transfer — driven from **only the
logged steer/throttle/brake/gear** (nothing taken from telemetry),
re-anchored every 5 s: **speed RMS ≈ 3 km/h (correlation 0.99)** and
**yaw-rate RMS ≈ 0.06 rad/s** against a 0.31 rad/s signal. This is the
engine reproducing a real lap.

**Track surface (HAT).** `TriangleHAT` builds the collision surface from
the actual `HATTarget` meshes and answers height/normal under each tyre by
exact point-in-triangle: **median 0.10 m, p90 0.13 m** versus the racing
line — no ambiguity tail.

**Simulator.** A track-relative (Frenet) integrator drives the calibrated
car around a track with a racing-line controller; it **completes a full,
on-track lap** of Zandvoort (Figure 1) at a deliberately conservative pace.

![The Julia engine driving the Vanwall around Zandvoort, on track geometry extracted from rFactor's own files (road grey, grass green, gravel tan). Frame from `zandvoort_lap.mp4`.](track_render.png)

![Capstone validation: the full engine driven from only the owner's logged inputs (re-anchored every 5 s). Orange = measured, green = predicted. The small vertical steps in green are the 5-second re-anchor resets — an artifact of the *measurement* method, not the engine; in closed-loop driving the engine integrates continuously with no resets.](validation_plot.png)

# 4. Where this leaves us

Everything that turns **rFactor files → calibrated physics → an accurate,
queryable track surface** exists and is validated. In scope terms, Phases
0–3 of the original plan are complete, and the data/surface foundations of
the standalone app (Phase 4) are built. What remains is the engineering to
turn the validated engine into an actual **racing** experience.

# 5. What remains — the path to the goal

The goal ("race on a track, Julia-controlled motion") decomposes into five
workstreams. They are largely independent and can be sequenced by which
end-experience is wanted first.

**A. Driver / AI controller.** The current racing-line driver completes a
lap only at a conservative pace (it brakes hard whenever the rear slips).
A realistic-pace, robust driver is needed both for AI opponents and for a
credible hot-lap. The feasible-speed foundation (`qss_speed_profile`, a
friction-circle lap-optimal profile) is built and proven; the remaining
work is a **well-damped path/speed tracker** (LQR- or MPC-class) plus a
low-speed dynamics regime. *Not needed if only a human will drive.*

**B. Real-time drivable loop + input.** For a human to drive, the engine
must run at a fixed step (isiMotor's ~400 Hz) reading a wheel/joystick
(SDL2 on Linux) and producing force-feedback (the steering-arm force the
suspension model already computes). The plain-Julia components are far
from a performance limit, so real-time is expected to be straightforward.

**C. Rendering.** To *see* it, either (i) a minimal OpenGL renderer using
the extracted GMT meshes + DDS textures — which needs the remaining
**GMT UV/material extraction** (geometry is done; UVs are a bounded
follow-on), or (ii) the headless route already demonstrated: render to
video, or drive rFactor itself as a replay viewer.

**D. Race logic.** Multiple cars, a start grid (from the AIW), lap/sector
timing (waypoint crossings — already available), basic flags, fuel/tyre
wear (the engine already models consumption). This is what makes it
*racing* rather than a hot-lap.

**E. Audio + polish (optional).** RPM-pitched engine sound from the `.sfx`
samples, skids, gear changes.

**Remaining calibration refinements** (none block the above): attribute
the constant longitudinal-loss term (needs one long-straight telemetry
session — pending); a richer tyre-load model to close the self-contained
yaw gap; brake-temperature response; longitudinal slip-curve shapes.

# 6. Choice points

These are the decisions that shape the remaining route. None are forced
yet; each trades effort for a different end-experience.

**C1 — Who drives first: human or AI?**
*Human-first* prioritises B (real-time + input) + C (rendering): you get to
drive the Julia car yourself sooner, with a simple/no AI. *AI-first*
prioritises A (limit driver) + D (race logic): you get cars racing each
other, watched as video/replay, without building input/FFB. Human-first is
the more visceral demo; AI-first reuses more of what's already validated
and needs no real-time renderer.

**C2 — Rendering strategy.**
(a) **Custom OpenGL renderer** — full control, "near-identical" look
achievable since gauges/meshes/textures are all data, but it is the
single largest new subsystem. (b) **rFactor as replay viewer** — write
rFactor-compatible `.vcr` replays and watch Julia-simulated laps with
rFactor's own graphics; very high visual fidelity for low rendering effort,
but the `.vcr` format is proprietary binary and a malformed file can crash
rFactor (a real RE subproject, not yet attempted). (c) **Headless / video**
— already working (mp4); fine for validation and demos, not for live play.
A pragmatic order is (c) now → (a) for the standalone, with (b) as an
optional spectacle.

**C3 — Driver/AI controller class.**
The current Stanley + spin-catch controller is simple but fragile at the
limit. Options: a **QSS-optimal speed profile + tuned tracker** (the
foundation is built; the principled next step), an **MPC** controller
(highest fidelity, most effort), or a **learned/optimised** racing line.
The QSS+tracker path is recommended.

**C4 — Physics fidelity for real-time.**
The validated dynamics use a single-track (bicycle) model with load
transfer. Choices: keep the bicycle model (fast, already validated to
~3 km/h / 0.06 rad/s), or move to the **full four-corner PM multibody
suspension** (higher fidelity, must be benchmarked for 400 Hz). A two-tier
design — multibody as the calibration reference, bicycle/lookup as the
real-time engine — was anticipated in the scope and is the safe default.

**C5 — Scope of "racing".**
Single-car hot-lap vs full multi-car grid; one car/track vs many. The
parsers already handle the whole install (1,172 cars, 68 tracks), so
breadth is cheap; the cost is in A and D. A sensible MVP is **one AI
opponent on one track**, then scale.

**C6 — Where the loop lives.**
Pure Julia for the whole real-time + render loop, or **Julia physics core +
a thin renderer/input layer** in another language. Pure Julia keeps it
one stack; a hybrid may ease GPU/FFB integration. The physics is already
pure Julia and fast; this only affects B/C.

# 7. Recommended next step

Because the physics and the track surface are validated and accurate, the
highest-value, lowest-risk milestone is **a real-time, human-drivable loop
(C1: human-first) with the headless/video or a minimal renderer (C2c→a)**:
it makes the validated engine immediately tangible and exercises the
400 Hz path, input and FFB — after which AI opponents (A + D) turn it into
racing. The QSS-fed tracker (A/C3) is the recommended parallel solo track,
since it needs no new hardware and unlocks both AI and realistic hot-laps.

Pending from the owner: one long-straight telemetry session closes the
last open calibration item (the constant longitudinal-loss term).
