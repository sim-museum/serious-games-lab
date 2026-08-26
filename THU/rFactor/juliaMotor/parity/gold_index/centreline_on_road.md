# Where the centreline leaves the road — lap-wide map (`JM_LINEONROAD`)

E73-S3 found Monza's centreline 7–19 m off the asphalt at s≈500, with the car placed on unmodelled
ground. This maps the whole lap on every GPL track by asking a binary question per 250 m bucket:
**how near is the closest road-textured triangle to lateral 0?**

## Results

| track | buckets | no road at all | line >3 m off | healthy |
|---|---|---|---|---|
| **Monza** | 24 | **2** (s=2750, s=4500) | **3** (s=500 → 8.2 m, s=750 → 3.1 m, s=2000 → 3.1 m) | 19 |
| **Spa** | 57 | 0 | 5 (max 5.1 m at s=9500) | 52 |
| **Watkins Glen** | 16 | 0 | 0 | **16 — clean** |

## What is solid

- **Monza s=500 — the line is 8.2 m off the road.** Corroborated three ways now: the photograph
  (car on a featureless sheet, E73-S2), the missing width bucket, and this census. Solid.
- **Monza s=4500 — no road within ±20 m.** This was *predicted* in E73-S2 from a missing width
  bucket, before this census existed, and is now confirmed independently.
- **Monza s=2750 — a second gap, newly found.** Not previously suspected.
- **Watkins Glen is clean across all 16 buckets.** Notable because the recorded WG4 finding said its
  line "strands ~10 m onto the grass at s≈300" — either that has since been fixed, or it is finer
  than 250 m sampling can see.

## ⚠️ What is NOT solid — the 3–5 m rows

This census tests triangle **centroids**. A large road triangle whose centroid sits 4 m off the line
can still *cover* lateral 0. So the rows reporting 3–5 m (Monza s=750/2000, all five Spa rows,
including s=0 on the pit straight where the grid manifestly is on the road) are **suspect** and
should not be treated as defects. Only the large offsets and the outright gaps survive that
objection — s=500's 8.2 m does, a 3.1 m does not.

Fixing this properly means testing triangle *coverage* of lat 0 rather than centroid distance. Left
undone deliberately rather than quietly reporting eight defects when three are real.

## Also recorded: the first version of this census silently "found nothing"

It referenced `CLINE`, which is not defined that early in the load, so every run died with
`UndefVarError` and printed **no census output at all** — indistinguishable from a clean result. The
exit status was what gave it away. Third instance this week of an empty diagnostic that was a
failure, not a pass.
