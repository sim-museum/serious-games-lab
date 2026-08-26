# E69–E75 rotation ledger

PO directive (2026-08-26): cycle through the backlog items so that within ~7 hours **every track and
the car (cockpit + exterior) has had progress**. Several sprints may sit on one item, but no item
may be starved.

At ~10 min/sprint, 7 h ≈ 42 sprints ≈ 6 per item. **Spa has had 10 already** — it is ahead, not
behind, so the rotation starts elsewhere and returns to it last.

| item | subject | sprints so far | status |
|---|---|---|---|
| E71 | **Spa** | 10 (S1–S10) | characterised: `house43` @12010 to move; 26 buildings classified by extent; census built |
| E74 | **Cockpit** (the "Dali dials") | 2 (S1–S2) | ✅ **D1 badge FIXED** (U+V flip, render.jl:1059); D2 gauges washed out; D3 wheel oversized; D4 FOV — see e74_cockpit.md |
| E75 | **Exterior Lotus 49** (missing axles) | 7 (S1–S7) | D1 RESTATED (S2): suspension DOES draw (3250 px toggle) but is occluded — S3: that was REFUTED — wheels 0.74 vs hub line 0.772 agree to 3 cm; S4: NO fold angle works (0 deg = spears, 45/90 = invisible) — JM is rehabilitating GPL's runtime-HIDDEN branch; S5: parts NAMED (lshok/lsusp5/lsusp7/lbrdisc/frontlot, all present in the .3do, none excluded by name); maxlat REFUTED as the cause; S6: ⭐ FRONT suspension drawn NOWHERE — FSUSPP asks for lsusp1 while excluding every group containing it (all 36 tris in 6600/3560); S7: ✅ FRONT geometry now renders (clip by extent not group; +7397 px) — maxedge approximate, gold comparison pending; REAR (27288/39792 fold) still open; D2 track wide (already tuned, do not re-tune); D3 exhausts splayed; grey tyres = known asset gap — see e75_exterior.md |
| E69 | **Zandvoort** | 1 (S1) | on-track crowds NOT reproduced (2/96 rows near road, 11 shots clean); sky grade CORRECT; kerbs/crowd-density/road-tone candidates — see e69_zandvoort.md |
| E70 | **Nürburgring** | 2 (S1–S2) | STRUCTURAL: Ring scenery is track-mesh, not instances — E71 censuses produce NOTHING here; S2: censuses were UNREACHABLE here (inside the GPL objects block) — relocated so they run on every track; first real measurement: centreline CLEAN 46/46 over 22.7 km — see e70_nurburgring.md |
| E72 | **Watkins Glen** | 2 (S1–S2) | both censuses CLEAN (nearest crowd 13.2 m, 0 footprints crossing); PO crowd block not reproduced; S2: CLEAN on all three censuses at the corrected 5.05 m edge (0 footprints, 16/16 alignment, crowds ≥13.2 m); ⚠️ but the E68-S10 rail dedup drops just 1 tri where 13% was claimed — W7 likely still live — see e72_watkins.md |
| E73 | **Monza** | 4 (S1–S4) | 0 crowd rows (confirms E68); 23 objects cross asphalt (braking markers + tree strips, NO buildings); S2: ⭐ NO ROAD for s≈350–650 (visual + width census agree, bucket 500 absent); s=4500 likely same; S3: banking lead REFUTED (all mesh at z 2.6–2.9, nothing overhead); real cause = CENTRELINE OFF THE ROAD (road tris at lat +7…+19, none at lat 0) — alignment defect. S4: lap-wide map (centreline_on_road.md) — Monza has 2 road GAPS (s=2750 new, s=4500 predicted+confirmed) + s=500 8.2 m off; Watkins clean 16/16; Spa 5 marginal rows suspect (centroid test) |

**Rotation order:** E74 → E75 → E69 → E70 → E72 → E73 → (E71) → repeat.

Update the "sprints so far" column at the end of each sprint. If an item stalls (blocked on the PO,
or on a GL run that cannot get the display), skip to the next and record why — a stalled item must
not consume its slot silently.


## Cross-track limitation found during the first pass (E70/E72/E73)

`ROAD_TEX` (the road-triangle classifier behind `JM_ROADWIDTH`, and hence the asphalt edge used by
the footprint census) **works on Spa and fails on Monza and Watkins**:

| track | road tris | buckets reported | median width |
|---|---|---|---|
| Spa | 9,658 / 14,099 m | all | **8.2 m** (uniform, trustworthy) |
| Watkins | 3,124 / 3,750 m | 3 of 8 | 3.7 m — **artefact** (healthy bucket: 10.9 m) |
| Monza | 4,537 / 5,744 m | 4 of 12 | 0.6 m — **artefact** (healthy bucket: 13.1 m) |
| Nürburgring | n/a | none | scenery is track-mesh; the census does not run at all |

**RESOLVED** — and it was not a coverage problem. See `road_width.md`: the texture names were
recognised all along; the bucket half-width (±3 m) was too thin, so buckets could hold only the
narrow `groove` racing-line strip. Default widened to ±12 m; Monza 0.6 → **11.6 m**, Watkins
3.7 → **10.1 m**, Spa 8.2 → 8.5 m (barely moves — the control that says it is a fix, not a fudge).
