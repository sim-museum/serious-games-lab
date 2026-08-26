# E69–E75 rotation ledger

PO directive (2026-08-26): cycle through the backlog items so that within ~7 hours **every track and
the car (cockpit + exterior) has had progress**. Several sprints may sit on one item, but no item
may be starved.

At ~10 min/sprint, 7 h ≈ 42 sprints ≈ 6 per item. **Spa has had 10 already** — it is ahead, not
behind, so the rotation starts elsewhere and returns to it last.

| item | subject | sprints so far | status |
|---|---|---|---|
| E71 | **Spa** | 10 (S1–S10) | characterised: `house43` @12010 to move; 26 buildings classified by extent; census built |
| E74 | **Cockpit** (the "Dali dials") | 1 (S1) | D1 badge rotated 180° (actionable); D2 gauges washed out; D3 wheel oversized; D4 FOV — see e74_cockpit.md |
| E75 | **Exterior Lotus 49** (missing axles) | 1 (S1) | D1 no suspension geometry — wheels detached (PO confirmed); D2 track wide (already tuned, do not re-tune); D3 exhausts splayed; grey tyres = known asset gap — see e75_exterior.md |
| E69 | **Zandvoort** | 1 (S1) | on-track crowds NOT reproduced (2/96 rows near road, 11 shots clean); sky grade CORRECT; kerbs/crowd-density/road-tone candidates — see e69_zandvoort.md |
| E70 | **Nürburgring** | 1 (S1) | STRUCTURAL: Ring scenery is track-mesh, not instances — E71 censuses produce NOTHING here; PO block not reproduced but 1.9 km sampling is no coverage — see e70_nurburgring.md |
| E72 | **Watkins Glen** | 1 (S1) | both censuses CLEAN (nearest crowd 13.2 m, 0 footprints crossing); PO crowd block not reproduced; ⚠️ road-width instrument unreliable here (3.7 m is an artefact) — see e72_watkins.md |
| E73 | **Monza** | 1 (S1) | 0 crowd rows (confirms E68); 23 objects cross asphalt (braking markers + tree strips, NO buildings); white washed-out regions at s=0/500 = likely E68-M1 — see e73_monza.md |

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

Fixing `ROAD_TEX`'s coverage for Monza and Watkins is a prerequisite for any width-dependent verdict
on those tracks, and is the highest-value shared fix found in the first pass.
