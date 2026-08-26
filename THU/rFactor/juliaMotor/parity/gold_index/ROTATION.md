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
| E73 | **Monza** | 0 | |

**Rotation order:** E74 → E75 → E69 → E70 → E72 → E73 → (E71) → repeat.

Update the "sprints so far" column at the end of each sprint. If an item stalls (blocked on the PO,
or on a GL run that cannot get the display), skip to the next and record why — a stalled item must
not consume its slot silently.
