# Julia Racer — next plans (written 2026-10-01)

Where each backlog item worked in the 2026-09-30 / 10-01 sessions stands, and what comes next. The full
record of each sprint is in `PRODUCT_BACKLOG.md`. This file is the to-do list.

**Rules carried forward:** at most 4 sprints per item before rotating. Before restarting an item that already
has 4 sprints, run a review and retrospective sprint first. Follow `260928/TOKEN_EFFICIENCY.md`, and start a
fresh session per cycle.

---

## Waiting on the PO

| item | the ask | why |
|---|---|---|
| **E108** | the track and station (or a screenshot) where the road or white line looks faceted | shading and finer rounding were both ruled out by A/B at Watkins Glen's gentle curves; there is nothing left to measure without a location |
| **E81** | a screenshot or station of any building or billboard that looks wrong | one real defect found (Ring s≈1350–1500); "many" were never located |
| **E91** | one iRacing session on a straight: coast from ~220 km/h to 60 with the **clutch held in**, then the same **in gear** | pins drag (CdA, Crr) and engine braking together; current data stops at 126 km/h |
| **E109** | a GPL screenshot of the Ring at s≈8400 and s≈21355 | tells whether the ~1 m tree intrusion is GPL's data or our rotation pivot |
| **E90** | a look at Monza s≈1000–1500 and Watkins Glen s≈500–750 / 2500–3000 | 54 / 84 rail sections stand on road-textured triangles; relaxing the guard blind risks invisible walls |
| **PERF-3** | build a new AppImage? | the shipped one predates every frame-rate fix; HEAD runs 55–60 fps |
| — | push? | commits since the last push are local only |

---

## Next cycle, in order

The cycle repeats E107 → E108 → PERF-3 → E81 → E78 → AI-CARGFX. Every item except PERF-3 has used 4
sprints, so each opens with a review and retrospective sprint.

### 1. E107 — AI as close as possible to GPL's (state: GPL's line on 4 of 5 tracks)
- **Retro first.**
- **Spa (94.0 %, bar 95 %):** replace the binary on-road bar with the graded test S4 proposed (p90 distance to
  road < ~1 m), then re-score all five tracks. Don't just lower the bar.
- **Check the rigid refit beyond GPL's line:** the ribbon itself (`ALIGNED`) still uses texture-based
  re-centring; measure whether the rigid placement plus GPL's own road-edge traces should replace it.
- Then plan items 4–6: per-rail speeds (pass1 vs race differ by up to 24.5 m/s at the Ring), `driver.ini`
  personalities and overtaking rules, and GPL's `aiAdvanceCarOnLine()` against our tyre model.

### 2. E108 — tracks as close as possible to GPL's (blocked: PO location)
- **Retro first.** Don't build another ruler (S1–S4 rebuilt one seven times).
- With the PO's location: A/B screenshots there (rounding off / tolerance 0.05 / 0.01) at full resolution.
- If geometry is the cause: plan item 4, generate the road from the `.trk`, **starting from E107's rigid
  placement** (otherwise the generated road lands 2–4 m off its own kerbs).
- Smooth road normals exist behind `JM_ROAD_SMOOTHN=1` (off by default; no visible effect measured).

### 3. PERF-3 — frame rate (state: 55–60 fps, mid-race freeze removed)
- If the PO builds an AppImage: confirm 60 fps on their machine, which settles the item.
- Remaining: a ~280 ms first-frame compile burst during the countdown. A hidden warm-up frame before the
  window is revealed would hide it.
- Run the full gate suite once before the AppImage.

### 4. E81 — misplaced buildings at the Ring (state: one real defect, unidentified)
- **Retro first.**
- **Fix the `JM_SCENE_AT` object listing first:** its name/lapdist columns are paired with the wrong z-road rows.
- Identify the skewed grey panel at s≈1350–1500 (`260930/e78/ring1350_skewed_panel.png`). It's not
  `walls2` or `tires` (yaw-flip A/B), so it's in the track `.3do` or the drawn scenery groups. Dump the triangles
  that project onto that screen region.
- Judge at full resolution, at a matched location (memory `jr-judge-geometry-full-res`).

### 5. E78 — tracks against the gold videos (state: Ring Hinter den Boxen leads)
- **Retro first.**
- Do the 36 `bannr_s` (Continental banner) triangles at Ring s≈1400 reach the screen? Check face culling and depth
  fighting against the wall. Full-res crop vs the gold frame at ~66 s of `260802_nurburgring_cockpit.mp4`.
- Then widen: the same matched-frame comparison on the other four tracks' gold videos.

### 6. AI-CARGFX — AI car graphics vs GPL (state: retro done; capture hook needed)
- Build `JM_AICAM=<ai index>`: point the chase camera at AI car *i* (pose from `AIPHYS[i]` / `RaceAI.pose_at`)
  for the smoke frame dump.
- Capture each chassis beside its GPL chase-from-behind still (`gold standard/julia racer/<chassis>/`),
  recording chassis, camera and art set. **Eagle first.**
- List the differences by eye, then theorise. The order was reversed for four sprints.

---

## Items from the earlier rotation (2026-09-30), still open

| item | next step |
|---|---|
| **RACESTART-1** | the second AI car still stalls behind a stalled player: it engages, but stops at lane 1.56, v = 0, inside the player-blocker window. Same shape as the fixed engage-trigger bug, one layer down. Repro: `JM_RS_FINAL=1 JM_RS_V0=25 JM_RS_BACK=150 JM_RS_SECS=60 julia --project=demo/native demo/native/racestart_probe.jl` |
| **E91** | blocked on the coast-down above; then refit CdA, Crr, torque and `ENGBRAKE` together from the gold (the torque fit assumed CdA 0.9) |
| **E109** | blocked on the GPL screenshot above; if it's our pivot, fix rotation for placements whose yaw isn't ±90° to the road |
| **E90** | blocked on the look above; tools ready: `JM_RAILHIT_SELFTEST=1`, `JM_RAILBOX_DIAG=1`, `JM_ROADSWEEP=2` |
| *(unfiled)* | Ring pit-straight structures at s≈1620 stand 1.1–1.3 m onto the road; this is the real "Hinter den Boxen", so probably correct, but not confirmed against gold |

## Tools added in these sessions

| hook | what it does |
|---|---|
| `JM_SHIFT_PROFILE=1` | re-centre shift in 20 lap bins + rigid-fit residual, then exit (E107) |
| `JM_GPLREF=aligned0\|rigid\|recentred` | which reference line GPL's records are placed on (default `rigid`) |
| `JM_ROAD_SMOOTHN=1` | smooth road normals (off) |
| `JM_YAWFLIP=<names>` | +180° yaw on named placements (test only) |
| `JM_ROADBLOCK_PLACE_NEAR=<s>` | now also prints pitch/roll and yaw-to-road |
| `JM_ASPHALT_PAT`, `JM_ASPHALT_GAP`, `JM_ASPHALT_NOALPHA` | asphalt-intrusion census (E109) |
| `JM_RAILHIT_SELFTEST`, `JM_RAILBOX_DIAG`, `JM_RAIL_OBB=0` | rail-box contact test, rejected-cell log, revert to axis-aligned (E90) |
| `JM_RS_V0`, `JM_RS_BACK`, `JM_RS_SECS`, `JM_RS_TRACE`, `JM_RS_FINAL` | race-start probe scenarios (RACESTART-1) |
| `JM_AI_ENGAGE_MARGIN=0` | revert the overtake-trigger fix |
| `JuliaMotorMTK/tools/coast_split.jl`, `coast_drag.jl` | clutch-split coast-down analysis (E91) |
