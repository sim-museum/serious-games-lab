# Rendered road width per track — and the instrument bug that hid it

## Result

| track | half-width | full width | buckets |
|---|---|---|---|
| **Spa** | ≈4.25 m | **8.5 m** | 24 |
| **Watkins Glen** | ≈5.05 m | **10.1 m** | 7 |
| **Monza** | ≈5.8 m | **11.6 m** | 10 |
| **Zandvoort** | **≈4.9 m** | **9.8 m** | 42 (E69-S17) |
| Nürburgring | — | — | scenery is track-mesh; census does not run |

All three are plausible period-circuit widths. **These supersede the E72/E73 numbers** (Watkins
3.7 m, Monza 0.6 m), which were artefacts.

## The bug was the BUCKET, not the texture names

The obvious hypothesis was that `ROAD_TEX` missed Monza's and Watkins' asphalt names. A census of
the textures on triangles within 5 m of the centreline **refuted it**:

- Monza: `groove` 728, `asphalt` 677, `aspgrs` 528, `concrete` 398 — **all recognised**. The misses
  are `grass`, `armco_s`, `wiref_s`, `shrub_*` — barriers and verge that merely project near the
  centreline, and should not be counted as road.
- Watkins: `groove` 1045, `asphalt` 884, `curb` 201, `sgrid`/`sline`/`start` — 86% recognised.

The real cause: `JM_ROADWIDTH` bucketed vertices within **±3 m** of each sample point. That slice is
thin, and on a road carrying a narrow **`groove`** racing-line strip a bucket can hold groove
vertices *only* — so the reported "width" is the groove's ~0.6 m, not the road's. Spa's road mesh is
dense enough that its buckets always caught asphalt too, which is why Spa alone looked healthy and
the fault read as track-specific.

**Fix:** bucket half-width default 3.0 → **12.0 m** (`JM_ROADWIDTH_BUCKET`).

**The check that it is a fix and not a thumb on the scale:** Spa, which was already sound, moves
only 8.2 → 8.5 m, while the two broken tracks jump to plausible values. A change that "improved"
Spa too would have been suspect.

## Consequence

The ±4.1 m asphalt edge used by the E71-S9 footprint census was derived from Spa and is close to
Spa's true ≈4.25 m — so Spa's results stand. **Monza and Watkins should use their own edges**
(≈5.8 m and ≈5.05 m); the census run against 4.1 m there was conservative, so its "objects crossing"
findings survive, but re-running per-track will catch more.


## E69-S17 — Zandvoort measured, and what the table implies for the on-road filter

Zandvoort by coverage (`JM_ROADWIDTH2_STEP=100`, 42 stations): **median 9.8 m**, min 6.2, max 41.0
→ half-width **≈4.9 m**.

### ⚠️ `JM_ASPHALT_HALFW` is Spa's number applied to every track

`onroad_fp` reads a single global, defaulting to **4.1 m**. Against this table:

| track | measured half-width | filter uses | shortfall |
|---|---|---|---|
| Spa | 4.25 | 4.1 | 0.15 m |
| Zandvoort | 4.9 | 4.1 | **0.8 m** |
| Watkins Glen | 5.05 | 4.1 | **0.95 m** |
| Monza | 5.8 | 4.1 | **1.7 m** |

So on every track but Spa there is a band of real racing surface the footprint filter does not
defend. **This also corrects E71-S16 and E69-S16 in this same session**, which reported per-track
"on the asphalt (<4.1 m)" counts — that threshold is Spa's, and the Monza and Zandvoort figures
derived from it are too low.

It resolves one of the questions E69-S16 left open: Zandvoort's `sign050/100/150` sit at **3.1 m**,
comfortably inside a 4.9 m half-width, so they are **on the racing surface**, not "beside the road"
as the earlier record has it.

**Not changed here.** Making the constant per-track only bites on families the filter actually
scopes (`vegcrowd`/`bldgish`), and Monza's intruders are `bar`/`pitwall`/`trees`/`front`/`tunmid` —
none of them in scope, so widening Monza's threshold would drop nothing. Spa's would newly catch
**27 `shrub` instances at 4.2 m**, on a 0.05 m margin against a half-width written "≈4.25". That is
inside the measurement's own precision, and dropping 27 objects on it would be tuning to noise.

### Fine sweep (`JM_SWEEP=50`, 84 stations): 7 anomalies

```
s=1500  WALL/CLIFF Δh=3.2 m
s=2400  SOLID-ON-ROAD: bushes02(4.4), bushes01(5.3)
s=2600  SOLID-ON-ROAD: bushes03(5.9, 4.9, 4.7, 6.0)
s=2700  SOLID-ON-ROAD: bushes03(4.0, 6.2)
s=3050  SOLID-ON-ROAD: rescu3(-7.0), rescu2(-8.0)
s=3100  SOLID-ON-ROAD: bushes01(-8.4)
s=3250  SOLID-ON-ROAD: bushes01(6.1, 7.5, 6.9)
```

These are **collidable**. The record already had bushes at 2309–2405; this extends the same family
to **2600–2700 and 3250**, and `bushes03(4.0)` at s=2700 is inside the 4.9 m half-width — on the
asphalt, and solid. The 6–8 m ones are off the surface and are only anomalies against the sweep's
wider 9.0 m corridor.

### Centreline: flagged, not claimed

10 of 42 stations put the centreline outside `[left, right]`. **Nine are outside by 0.5–0.8 m**, and
every bound in the table is a multiple of 0.5 — the census quantises at 0.5 m, so those nine are at
the resolution limit and are not evidence of anything.

**s=0 is the exception: 2.2 m outside, road spanning +2.2 … +8.5.** But the width there is
**6.2 m against a 9.8 m median** — the narrowest station on the track. A centreline error moves the
road's bounds; it does not make the road narrower. Both are explained instead by **`ROAD_TEX` not
recognising the start/finish surface** (Watkins needed `sgrid`/`sline`/`start` added for exactly
this), which would drop the S/F triangles and leave only what lies beyond them. That is the check to
run before anyone touches Zandvoort's centreline — the Spa fix (E71-S12) was real, and the temptation
to see the same defect again is precisely why this one needs its own evidence.