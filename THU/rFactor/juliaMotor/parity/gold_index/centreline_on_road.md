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

---

## Extent-based on-road census, each track at ITS OWN measured edge

Prompted by E69-S2: two of three "not reproduced" verdicts were overturned once the census measured
mesh EXTENT rather than instance ORIGIN, so every track was re-run at its own asphalt edge.

| track | edge | instances crossing | buildings | dominant classes |
|---|---|---|---|---|
| **Spa** | 4.25 m | 366 | 26 | houses, armco (armco rows suspect — see E71-S9) |
| **Zandvoort** | **4.6 m** | **57** | 0 | `bushes01–04` @ 2309–2405; **`ppl_m1` @3851, `ppl_l3` @3256 — spectator rows on the line** |
| **Monza** | **5.8 m** | **32** | 0 | `brmk100–400r` braking boards @630–870; `trees24/25/68/69/70/73` strips |
| **Watkins Glen** | 5.05 m | **0** | 0 | — genuinely clean |
| Nürburgring | — | **census cannot run** | — | scenery bypasses the object pipeline (E70-S2) |

Watkins is the only track that is clean, and the Ring is the only one that cannot be measured at all.

---

## The road-only oracle makes every track's census perfect — and that is NOT sufficient to ship it

After E73-S5 fixed Monza by enabling the road-only oracle plus re-centring, the same was tested on
the two remaining tracks:

| track | oracle OFF (shipped) | oracle ON |
|---|---|---|
| **Spa** | 52/57 healthy, 5 strays | **57/57** |
| **Zandvoort** | 16/17 healthy, 1 stray | **17/17** |

Every track would then have a clean centreline. **It is still not being shipped for these two.**

### Why not — two reasons, both about the evidence rather than the result

**1. The census is being optimised in exactly the band where I already know it is unreliable.**
`centreline_on_road.md` records that this test measures triangle **centroids**, so rows reporting
3–5 m are *suspect* — a large road triangle centred 4 m off the line can still cover it. Spa's five
"strays" are all in that band, including **s=0 on the pit straight where the grid manifestly sits on
the road.** The oracle "fixes" precisely those rows. Improving a metric at the point where the metric
is known to lie is not evidence of improving the track.

**2. Zandvoort's current line was PO-verified.** The code records the previous check as
"pass-1 mean 0.12 m", against **2.19 m** under the oracle. That is a real change to a line a human
signed off on.

### Why Monza was different, and why shipping it was justified

Monza had evidence **independent of the census**: two outright road GAPS, and a photograph of the car
floating over unmodelled ground with the white-sheet fraction at 93.5%. The census agreed, but the
case did not rest on it. Spa and Zandvoort have neither gaps nor a photograph — only marginal rows in
the untrustworthy band.

### What would justify shipping it

Either (a) fix the census to test triangle **coverage** of lat 0 rather than centroid distance — the
work already named in this document — and re-run; or (b) photograph Spa at its five flagged lapdists
before and after, and show the after is genuinely better on the road. **Until one of those, the
current lines stay.**
