# Rendered road width per track — and the instrument bug that hid it

## Result

| track | half-width | full width | buckets |
|---|---|---|---|
| **Spa** | ≈4.25 m | **8.5 m** | 24 |
| **Watkins Glen** | ≈5.05 m | **10.1 m** | 7 |
| **Monza** | ≈5.8 m | **11.6 m** | 10 |
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
