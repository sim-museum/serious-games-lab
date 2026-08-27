# E69–E75 rotation ledger

PO directive (2026-08-26): cycle through the backlog items so that within ~7 hours **every track and
the car (cockpit + exterior) has had progress**. Several sprints may sit on one item, but no item
may be starved.

At ~10 min/sprint, 7 h ≈ 42 sprints ≈ 6 per item. **Spa has had 10 already** — it is ahead, not
behind, so the rotation starts elsewhere and returns to it last.

| item | subject | sprints so far | status |
|---|---|---|---|
| E71 | **Spa** | 12 (S1–S12) | characterised: house43 @12010 to move; 26 buildings by extent. S12: ✅ centreline FIXED — shipped line had the car on the grass verge at s=750/10000 (grass under car 29.6%/19.8% → 0.6%/0.1%); road-only oracle now on for Spa |
| E74 | **Cockpit** (the "Dali dials") | 7 (S1–S7) | ✅ **D1 badge FIXED** (U+V flip, render.jl:1059); D2 gauges washed out — S3: brightness REFUTED as cause (3 arms); S4: minification test FAILED to isolate (scaling displaces the dials) — but revealed the cluster sits up-and-LEFT of gold's, partly clipped; S5: no lateral knob existed — added JM_GAUGE_Z; z=0.10 visibly improves legibility (occlusion/clipping confirmed as a major cause) but gold puts the dial ABOVE the rim, S6: ⭐ z=0.10 y=0.28 puts the cluster ABOVE the rim with readable dials — the Dali effect is largely PLACEMENT (clipping+occlusion), not texture/lighting; S7: ✅ SHIPPED (verified 4 viewpoints / 2 tracks) — dials no longer clipped or spoke-occluded; dial SIZE and D3/D4 still open; D3 wheel oversized; D4 FOV — see e74_cockpit.md |
| E75 | **Exterior Lotus 49** (missing axles) | 7 (S1–S7) | D1 RESTATED (S2): suspension DOES draw (3250 px toggle) but is occluded — S3: that was REFUTED — wheels 0.74 vs hub line 0.772 agree to 3 cm; S4: NO fold angle works (0 deg = spears, 45/90 = invisible) — JM is rehabilitating GPL's runtime-HIDDEN branch; S5: parts NAMED (lshok/lsusp5/lsusp7/lbrdisc/frontlot, all present in the .3do, none excluded by name); maxlat REFUTED as the cause; S6: ⭐ FRONT suspension drawn NOWHERE — FSUSPP asks for lsusp1 while excluding every group containing it (all 36 tris in 6600/3560); S7: ✅ FRONT geometry now renders (clip by extent not group; +7397 px) — maxedge approximate, gold comparison pending; REAR (27288/39792 fold) still open; D2 track wide (already tuned, do not re-tune); D3 exhausts splayed; grey tyres = known asset gap — see e75_exterior.md |
| E69 | **Zandvoort** | 4 (S1–S4) | S2 CORRECTION: on-track crowds ARE reproduced — ppl_m1 @3851 and ppl_l3 @3256 reach 0.2/0.8 m from the centreline from origins 5.5/12.3 m out (S1 used the origin-based census); + bushes at 2309–2405. S3: ppl_l3 renders as a WALL across the left (billboard drawn flat); S4 RETRACTS that: the main straight is NOT empty — native s=0 matches gold; the s=3851 comparison used a linear time→lapdist map that drifts 330 m near lap end; sky grade CORRECT; kerbs/crowd-density/road-tone candidates — see e69_zandvoort.md |
| E70 | **Nürburgring** | 2 (S1–S2) | STRUCTURAL: Ring scenery is track-mesh, not instances — E71 censuses produce NOTHING here; S2: censuses were UNREACHABLE here (inside the GPL objects block) — relocated so they run on every track; first real measurement: centreline CLEAN 46/46 over 22.7 km — see e70_nurburgring.md |
| E72 | **Watkins Glen** | 8 (S1–S8) | both censuses CLEAN (nearest crowd 13.2 m, 0 footprints crossing); PO crowd block not reproduced; S2: CLEAN on all three censuses at the corrected 5.05 m edge (0 footprints, 16/16 alignment, crowds ≥13.2 m); S3: dedup is NOT broken — only 1 duplicate exists in 2436 rail tris (per-part = global), so the 13% premise does not reproduce; W7 needs re-scoping away from dedup. S4: pit structures ARE placed+kept (not missing) at lat −28..−42. S5: and NOT VISIBLE at their own lapdists — tower1 at 26.9 m should clip the frame and does not; S6: ⭐ ROOT CAUSE — the pit buildings are OFF-HAT and fall back to trkzlo (−8.7 m) while the terrain there is ~20 m, i.e. buried ~29 m; tower1 at 26.9 m is inside the HAT and lands perfectly, so the failure boundary is ~27–29 m lateral. S7: ✅ FIXED — edgez marched toward the lap CENTROID (away from the track for anything inside the loop); now marches to the nearest centreline point. Dunlop grandstand, pit/timing building and S/F crowds restored; Zandvoort regression-checked clean. S8: Spa also gains a structure, but MONZA REGRESSES (tree raised into the sky, 14.6% of frame) — fix now gated to Watkins+Spa pending Monza investigation — see e72_watkins.md |
| E76 | **Nürburgring deleted objects after S/F** (PO 2026-08-26) | 7 (S1–S7) | sprite-stub lead REFUTED — all 37 are degenerate SIGNS (corner-name boards), none near S/F; S2: ✅ REPRODUCED — gold's first km is lined with crowds+hoardings, native is bare past s≈200; Ring loads 184 groups vs Spa's 1679 objects+5132 billboards at 1/5 the length — S3: ⭐ ROOT CAUSE — 2231 of 3109 placements (72%) dropped because getmesh() returns nothing; shrubs/trees/flagger/FAKE/BUSH; S4: objects ARE in the archive and the keys match — S5: ⭐⭐ ROOT CAUSE — all 50 failing names parse to ZERO triangles; they are camera-facing BILLBOARDS (BUSH/strauch*/stree*/flagger/deadtree) and the Ring's scenery loader has no billboard path (Spa gets 5132 billboards, Ring gets 0). Fix = add billboard handling to that loader. S7 CORRECTS S6 twice: the crowd search pattern was invalid (Ring uses people*/pplrow01, not ppl_*), and the crowds do NOT fail — 39 placements load as 6–10 tri objects, i.e. billboards drawn as flat geometry. So the billboard fix plausibly covers crowds too — see e76_ring_deleted.md |
| E73 | **Monza** | 6 (S1–S6) | 0 crowd rows (confirms E68); 23 objects cross asphalt (braking markers + tree strips, NO buildings); S2: ⭐ NO ROAD for s≈350–650 (visual + width census agree, bucket 500 absent); s=4500 likely same; S3: banking lead REFUTED (all mesh at z 2.6–2.9, nothing overhead); real cause = CENTRELINE OFF THE ROAD (road tris at lat +7…+19, none at lat 0) — alignment defect. S5: ✅ FIXED — Monza was hard-excluded from centreline re-centring (no comment saying why); enabling that + the road-only oracle gives 24/24 healthy and the car photographs on asphalt (93.5%→0.7% white). S4: lap-wide map (centreline_on_road.md) — Monza has 2 road GAPS (s=2750 new, s=4500 predicted+confirmed) + s=500 8.2 m off; Watkins clean 16/16; Spa 5 marginal rows suspect (centroid test) |

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


## Cross-track: missing trackside structures (2026-08-26)

The PO's E76 (Nürburgring objects deleted) is **not Ring-specific**. Checked every track's S/F:
Nürburgring **severe**, Zandvoort **severe**, Watkins **pit building absent**, Spa and Monza
populated. Three of five affected. See `missing_structures.md` — next step is running the scenery
census on Watkins and Zandvoort to see whether they share the Ring's drop mechanism.
