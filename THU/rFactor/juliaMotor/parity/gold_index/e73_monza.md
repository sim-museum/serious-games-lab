# E73 — Monza gold-video parity

Oracle: `260802_monza_nintendo.mp4` / `_cockpit.mp4` (173 s each).
Native: 12-shot chase sweep, s = 0…5500. **Centreline = 5744 m.**
GPL pipeline: `114 trackside objects + 19 billboards + 1 forest panel + 2 solid`.
Composite: `e73_mz_native.jpg`.

## Crowds: none. Confirms the earlier E68 note.

`JM_CROWDDIAG`: **0 crowd rows kept.** E68-M1 already recorded "No misplaced crowds on Monza ✓" and
this independently agrees. Monza is the one track where the PO's on-road-crowd complaint never
applied.

## 23 instances DO cross the asphalt — and none of them is a building

| class | instances |
|---|---|
| braking markers | `brmk100r`, `brmk200r`, `brmk300r`, `brmk400r` (s≈630–870) |
| tree strips | `trees24`, `trees25`, `trees68`, `trees69`, `trees70`, `trees73a`, `trees73b` |
| structures | `paddock` (s=11), `front06`, `bar01`, `tunmid` |
| **buildings** | **0** |

`brmk200r` reaches `near|lat| = 0.0` at s=790 — a braking board on the racing line. `trees24` has its
origin 15.6 m out yet reaches 0.3 m: a long forest strip sprawling across the road, which is the
same shape as E68-M1's "forest" complaint.

⚠️ Same caveat as E71-S9: long objects can trip the lapdist-conflation false-positive. The tree
strips are precisely the long-object class most at risk, so **these rows want a photograph before
they are actioned** — unlike Spa's `house43`, which had one.

## ⭐ VISUAL: large white washed-out regions at s=0 and s=500

At s=500 the car sits on an almost entirely **white** surface with a dark band across the frame; at
s=0 the ground beside the pit building is white too. This is the strongest visual deviation on this
track and is the likely face of **E68-M1** ("translucent haze planes fade whole forests out/in with
view angle; light/dark sheets appear over objects"), suspected there to be `uGraze` applied to real
tree meshes rather than flat panels.

## ⚠️ Cross-track: the road-width instrument does NOT work here (or at Watkins)

Monza: 4,537 `ROAD_TEX` tris over 5,744 m, **only 4 of 12 buckets**, median **0.6 m** — nonsense.
The one healthy bucket (s=5000, n=18) gives 13.1 m.
Watkins: same failure (E72-S1).
Spa: works (9,658 tris, uniform 8.2 m).

`ROAD_TEX` is tuned for GPL/Ring texture names and evidently misses Monza's and Watkins' asphalt.
**Every width-dependent verdict on those two tracks is unsupported until that is fixed** — including
the ±4.1 m edge used by the footprint census above, which is borrowed from Spa. It is conservative
against a 13 m road, so the "23 crossing" result survives, but the number is not calibrated here.

---

## E73-S2 — ⭐ a ~300 m stretch of Monza has NO ROAD (2026-08-26)

Composite: `e73_monza_s500_noroad.jpg`.

At s≈500 the car floats over a **featureless pale sheet with no road surface at all**, with a dark
plane crossing the sky above. Bounded by sampling every 100 m (near-white fraction of the lower
third of the frame):

| s | 200 | 300 | **400** | **500** | **600** | 700 | 800 | 900 |
|---|---|---|---|---|---|---|---|---|
| near-white | 0.5% | 0.5% | **48.8%** | **93.5%** | **29.7%** | 0.8% | 0.5% | 0.5% |

So the defect runs **s ≈ 350–650**, peaks at s=500, and the road is normal either side.

### Corroborated independently by the width census

With the bucket fix in place, Monza's width census reports buckets at 0, 1000, 1500, 2000, 2500,
3000, 3500, 4000, 5000, 5500 — and **no bucket at 500**. Zero road-textured triangles lie within
±12 m of that lapdist. A visual observation and a geometry census, with nothing in common but the
track, agree that there is no road there.

### Related thin sections, same census

`s=1500` (3.7 m, n=12), `s=2000` (3.9 m, n=18) and `s=4000` (3.7 m, n=24) report widths a third of
Monza's 11.6 m median, and **s=4500 is missing entirely** like s=500. These are candidates for the
same defect in milder form — thin or absent road geometry — and should be photographed next.

### What this is NOT

It is not the `groove`-only bucketing artefact that the width fix addressed: that produced *narrow*
buckets, not *missing* ones, and it has since been corrected. And it is not E68-M1's haze-plane
theory as stated — the foreground here is not a forest fading with view angle, it is a missing
running surface. E68-M1 may still be a separate real defect; this is a bigger one that was sitting
underneath it.

### Next

Identify what the pale sheet actually is. The strongest lead is E52's note that **Monza's banking is
a large mesh above the road** that had to be excluded from the collision HAT because "the road
passes under it" — a car passing beneath the banking would see exactly this: its underside filling
the frame while the real road is hidden. If so the fix is a render-side exclusion mirroring the HAT
one, not new geometry.

---

## E73-S3 — the banking hypothesis is REFUTED; the CENTRELINE leaves the road

Added `JM_SPOTMESH=<lapdist>` — lists every track-mesh triangle near a lapdist with its texture,
height and lateral range. Run at the defect (s=500) and at a healthy control (s=1000):

**s = 500 ±40 m, |lat| < 30 m — 43 triangles total**

| texture | tris | z range | lateral range | road? |
|---|---|---|---|---|
| `wiref_s` | 16 | 2.6–2.9 | +5.3 … +22.4 | |
| `grass` | 15 | 2.6–2.9 | +3.8 … +21.3 | |
| `asphalt` | 4 | 2.6–2.9 | **+11.1 … +15.4** | ROAD |
| `aspgrsr` | 4 | 2.6–2.9 | **+7.2 … +8.2** | ROAD |
| `aspgrs` | 4 | 2.6–2.9 | **+18.2 … +19.2** | ROAD |

**s = 1000 (control) — 230 triangles**, with `asphalt` spanning **−29.2 … +8.4** and `concrete`
**−1.5 … +1.5**: road across the centreline, as it should be.

### Two conclusions

**1. The banking hypothesis is dead.** Every mesh at s=500 sits at z = 2.6–2.9 m — a single low
band, nothing overhead. There is no large mesh above the road here, so the pale sheet is not a
banking underside. My E73-S2 lead was wrong.

**2. The real defect is worse: the CENTRELINE IS OFF THE ROAD.** At s=500 every road-textured
triangle lies at lateral **+7.2 to +19.2 m** — none anywhere near lat 0, where the car is placed.
The road exists; the centreline has wandered ~7–19 m to the side of it. And with only 43 triangles
in an 80 × 60 m patch, the ground under the centreline is essentially **unmodelled**, which is why
the frame shows a featureless pale sheet rather than grass.

So this is not a rendering defect at all. It is a **centreline/alignment defect**, in the same
family as the recorded WG4 finding that "the Watkins line strands ~10 m onto the grass at s≈300".
Monza's own load log runs an align + recentre pass; it evidently fails through this section.

### Why this matters more than it looked

A car driven through s≈350–650 is off the circuit, on unmodelled ground, with the real road several
car-widths to one side. That affects the racing line, lap distance and any physics that depends on
being on the surface — not just the picture.

### Next

Inspect the Monza centreline alignment through s=300–700 against the road ribbon: the recentre pass
reports `max shift` per iteration, so the question is whether it failed to converge here or
converged onto the wrong strip. `s=4500` (also a missing width bucket) should be checked the same
way, as should Watkins' known s≈300.

---

## E73-S5 — ✅ FIX SHIPPED: Monza's centreline no longer leaves the circuit

E73-S3 found the car placed on unmodelled ground for ~300 m (s≈350–650) with the road 7–19 m to one
side; E73-S4 added gaps at s=2750 and s=4500. Cause found and fixed.

### The cause was two settings, and neither alone was enough

| configuration | result |
|---|---|
| shipped | 2 gaps, 3 strays, **19/24 healthy** |
| road-only oracle ON alone | **identical** — because Monza was *also* excluded from re-centring, so the oracle had nothing to feed |
| re-centring ON alone (full-terrain oracle, 1 pass) | partial — s=500 improves 8.2→5.4 m, **gaps remain**, 20/24 |
| **both** | ⭐ **24/24 healthy, no gaps, no strays** |

Line 720 read `(haskey(ENV,"JM_NO_RECENTRE") || MONZA) ? a : recentre_on_road(...)` — **Monza was
hard-excluded from centreline re-centring, with no comment explaining why.** That is why enabling the
better oracle changed nothing: the step that would have used it never ran.

### Verified

- Census with defaults, no env overrides: **24 buckets, 0 gaps, 0 strays**.
- Photographs at all three previously-broken sites show the car **on asphalt** with verges, trees and
  trackside signage. Near-white fraction of the lower frame at s=500: **93.5% → 0.7%**
  (`e73_monza_fix.jpg`).

### ⚠️ Risks recorded rather than buried

1. **This changes the racing line**, and therefore lap distance, the AI reference line and anything
   physics-dependent. It is not a cosmetic fix.
2. **The start position moves 2.43 m** (`at-start 2.43 m` in the final pass). Grid placement should be
   checked.
3. **The original exclusion's reason is unknown** — it carried no comment. The likely motive is the
   combined/banked Monza layout (the code elsewhere notes "the broken monza10k banked combined
   circuit" and passes `drop_overpass=MONZA`), and this build uses the road course, so the reason is
   probably stale. **Probably is not certainly**, and if a banking-related regression appears, this
   is the first change to suspect.

`JM_NO_RECENTRE=1` restores the raw `.trk` line on every track.

**Fourth fix shipped in this batch**, after the badge, the front-end geometry and the gauge placement.

---

## E73-S6 — why the height fix regresses on Monza: the march probably hits the BANKING

The E72-S7 grounding fix (march to the nearest centreline point rather than the lap centroid) helps
Watkins and Spa but raises a forest strip on Monza (E72-S8). Traced to a single object:

```
trees03   lapdist 1042   lat 13.1   OFF-HAT
   centroid march -> base 6.3
   nearest  march -> base 9.1     (+2.8 m)
```

`trees03` is a long forest strip — the same class as `trees24`, which the footprint census showed
spanning lateral 0.3…19.2 m. Lifting a strip of that size by 2.8 m is enough to make it overhang the
road as the dark canopy seen at s=3000, even though the object's own origin is at lapdist 1042.

### The likely mechanism

`edgez` returns the height of the **first HAT sample** along the march. **Monza has banking geometry
that sits ABOVE the road** — the code already special-cases it, passing `drop_overpass=MONZA` when
building the collision HAT precisely because "the road passes under it" (E52).

If the HAT used by `edgez` still contains that banking, a march aimed at the nearest centreline point
can strike the **banking surface** before reaching ground level and return its height — roughly the
2.8 m lift observed. The old centroid-aimed march pointed elsewhere and happened to miss it.

**That would make this a Monza-specific interaction, not a flaw in the nearest-centreline idea** —
consistent with the fix being correct on the three tracks without banking.

### Next

Check whether the HAT `edgez` marches over is the overpass-dropped one. If not, use the same
`drop_overpass` treatment for grounding as for collision, then re-test Monza and lift the gate. That
would let the fix ship on all four GPL tracks instead of two.

⚠️ **Not verified.** The banking explanation fits the numbers and the code's own history, but no
measurement yet confirms the march is striking it. The gate stays until one does.

---

## E73-S7 — ⚠️ the banking hypothesis is REFUTED; the real issue is single-point grounding

E73-S6 proposed that Monza's grounding regression came from the march striking the banking, which
sits above the road. **Checked, and it is wrong:**

```julia
const TERRAIN0 = GPLTrack.build_hat(TRACKMESH0; …, drop_overpass=MONZA, …)
const TERRAIN  = isempty(SECTRI) ? TERRAIN0 : GPLTrack.build_hat(TRACKMESH; …, drop_overpass=MONZA, …)
```

**Both terrain builds already drop the overpass**, and `groundz` reads `TERRAIN`. The banking is not
in the surface the march walks over. The hypothesis fitted the numbers and the code's own history and
was still false — which is why it was recorded as unverified rather than acted on.

### What is left, and it is more structural

Two things remain in play, and the second matters more:

1. **`groundz` calls `hat3d(TERRAIN, x, y; ref=Inf)`.** With `ref=Inf` an overlapping-surface query
   returns the **highest** surface at that point. The two marches cross different ground, so they can
   legitimately land on different heights — 9.1 m (probably the road/verge level near lapdist 1042)
   versus 6.3 m from wherever the centroid path happened to strike.

2. ⭐ **An object is grounded at a SINGLE point.** `trees03` is a long forest strip — its sibling
   `trees24` spans 19 m laterally in the footprint census. Grounding a strip of that length by one
   sample means that wherever the terrain varies along it, the far end is wrong by the difference.
   **Raising the sample point by 2.8 m lifts the entire strip**, including the parts over lower
   ground, which is exactly the overhanging canopy.

So the nearest-centreline march may well be returning the *better* height for the object's origin,
and still produce a worse picture, because the object is not a point.

### Consequence for the gate

The gate on Watkins+Spa stays, but the reasoning changes: this is not "Monza is special", it is
**"single-point grounding is inadequate for long strip objects, and Monza has more of them"**. A
proper fix grounds strips at several points along their length, or per-vertex — the same shape as the
E71-S9 finding that a single centroid cannot describe a long object's relationship to the road.

**Twice now on this project a long strip object has broken a per-object measurement.** That is a
pattern worth naming rather than fixing twice.

---

## E73-S8 — ✅ the road gaps are CLOSED; the remaining "missing road" was the INSTRUMENT

Two questions were open on Monza: do the road gaps E73-S4 predicted at s≈2750 and s≈4500 survive the
S5 centreline fix, and why does the width census still report absurd numbers here.

### 1. The gaps are gone

`JM_LINEONROAD` post-fix: **24/24 buckets healthy — 0 with no road, 0 with the line >3 m off it.**
Captures at s=500, 1500, 4500 and 5500 (`mz_gaps.png`) show the car on clean asphalt at every one.
E73-S2's *"NO ROAD for s≈350–650"* and S4's predicted s=4500 gap are both **closed by the S5
centreline fix**, as S5 hoped but could not yet show.

### 2. ⭐ The width census was measuring vertices, not road

`JM_ROADWIDTH` still reported nothing at all at s=500 and s=4500, **0.6 m** at s=5500, and 3.8 m at
three other stations — against captures showing perfectly good road. The cause is in the census:

```julia
b = round(Int, hr.lapdist / step)
r = hr.lapdist - b*step
abs(r) <= halfb || continue          # ±12 m LONGITUDINAL slice — not a lateral bucket
```

It takes the lateral spread of road **VERTICES** falling in a 24 m slice at each station. Monza's
straights are meshed with very large triangles, so such a slice can contain **no road vertices at
all** — the bucket then vanishes — or only two from the narrow `groove` racing-line strip, giving
0.6 m. **Spa's road mesh is dense enough that vertices land in every slice, so Spa's number came out
right for the wrong reason** — and that is exactly why the defect survived: the one track with a
trustworthy oracle was the one track the instrument happened to handle.

A localised texture census (`JM_ROADTEX_AT`) confirmed the road is *classified* correctly at each
suspect station — 42, 148, 29 and 78 recognised road triangles at s=500/1500/4500/5500 — so this was
never a `ROAD_TEX` naming problem either.

### 3. Shipped: `JM_ROADWIDTH2`, width by COVERAGE

March laterally across the centreline in 0.25 m steps and ask, for each offset, whether any road
**triangle covers that point**. Triangle size then cannot matter.

| track | old (vertex) | new (coverage) | stations |
|---|---|---|---|
| **Monza** | median 11.3, **min 0.6**, buckets 500/4500 **missing** | **median 12.2**, min 11.0 | **24/24** |
| **Spa** | median 8.3, min 8.2, max 59.8 | **median 8.0**, min 7.8, max 12.5 | 57/57 |
| **Watkins** | median 10.1, min 3.7 | **median 11.2**, min 1.8 | 16/16 |

⭐ **Spa is the positive control and it passes**: on the dense mesh the two methods agree (8.3 vs
8.0 m). The coverage method changes the answer only where the old one was broken — which is the check
that this is a fix and not a thumb on the scale. Its maxima are also sane (12.5 m vs the old 59.8 m).

`JM_ROADWIDTH` now prints a warning naming its own limitation and pointing at the coverage census.

### ⚠️ A real finding falls out of this: native Spa may be ~27 % too narrow

**Both** instruments now agree that native Spa's road is **8.0–8.3 m**, while E71-S6 measured gold Spa
at **~11 m**. Two independent methods agreeing makes this a track defect rather than an artifact —
but the gold figure is a single earlier measurement and should be re-derived from the gold video
before anything is widened. Logged to **E71**, not acted on here.

---

## E73-S9 — footprint grounding built; it does NOT fix the regression, and gold confirms the gate is right

E73-S7 concluded the Monza `edgez` regression came from **single-point grounding**: `ploz` samples the
terrain at an object's ORIGIN and applies that one height to the whole object, so a long forest strip
gets lifted bodily. S9 built the fix that theory implies and tested it.

### The fix: `JM_FPGROUND`

Sample the terrain across the object's own **footprint** (the decimated local vertex list already used
by `JM_FOOTPRINT`) and take a low quantile, so no part of a long object hovers.

**First implementation silently did nothing.** It sampled `groundz` only — which returns "off the HAT"
for precisely the objects `edgez` exists to place — so every sample failed, `plozfp` fell back to the
origin height, and the arm was effectively identical to no fix:

```
s=3000   NULL 0.43%   regression 14.81%   with "fix" 14.57%   fix-vs-regression 0.74%
```

Caught only because **a fix that changes nothing is as suspicious as one that changes everything**.
Corrected to sample the full grounding path (`groundz`, falling back to `edgez`), it engages properly —
16.20 % different from the regression arm at s=3000.

### ⚠️ But it does not fix the regression

| viewpoint | null | regression (B vs A) | with footprint grounding (D vs A) |
|---|---|---|---|
| s=3000 | 0.43 % | 14.81 % | **19.49 %** |
| s=1042 | 0.14 % | 11.23 % | 10.01 % |

And the picture is unambiguous: the dark canopy overhanging the road is **still there**. Footprint
grounding changes the scene but does not remove the defect.

⭐ **So E73-S7's diagnosis is refuted.** Single-point grounding is a real weakness — it is the same
shape of error as E71-S8 and E69-S5, and the capability is worth having — but it is **not the cause of
this regression**. Three sprints have now proposed a mechanism for this canopy (S6 banking, S7
single-point grounding) and both have been eliminated by building them and measuring.

### ⭐ Gold decides the direction, and the gate is correct

Before writing this off I checked whether the "regression" might be **buried forest emerging** — Monza
sits in a park, so dense trees are plausible, and an object at 6.3 m could be under the terrain while
9.1 m brings it into view. That would have made the baseline the defect.

**Gold refutes it.** The gold Monza cockpit video shows a treeline of *moderate height with open sky
above it*, closely matching the **baseline**; the nearest-march arm's canopy overhanging the road
matches nothing in gold. The gate stays — now justified by the oracle rather than by a pixel
percentage.

`JM_FPGROUND` ships **default OFF**: it is unproven, and it changes 10–19 % of the frame. It is kept
because the origin-vs-footprint weakness is real and this is the machinery to address it when a case
is found that it actually fixes.

---

## E73-S10 — ⭐ the mechanism found at last: overlapping HAT surfaces and `ref=Inf`

Three sprints have proposed a mechanism for the Monza grounding regression and two were eliminated by
building them (S6 banking, S7/S9 single-point grounding). S10 tests the one thing never examined: how
`groundz` chooses among **overlapping** terrain surfaces.

### The trace

`JM_EDGEZ_TRACE` (new) replays both march targets for a named object and enumerates every HAT surface
at the march's first hit — the HAT API allows this by lowering `ref` step by step:

```
[edgez] trees03  nearest-centreline  march 8m → h=9.1   surfaces at hit: 9.1, 6.3
[edgez] trees03  lap-centroid        march 8m → h=6.3   surfaces at hit: 6.3
```

⭐ **The two marches hit different spots 8 m out, and only the nearest-centreline one lands where a
second surface lies 2.8 m above the ground.** `groundz` queries with `ref=Inf`, which returns the
**topmost** layer — so the forest strip was grounded on the upper surface. That is the 2.8 m lift, and
the canopy that has gated this fix since E72-S8.

`ref=Inf` is *right* for placing a car (it drives on the top surface) and *wrong* for grounding a
distant backdrop object, which belongs on the ground. The bug was a correct default applied in the
wrong context.

### Fixed, and measured

`edgez` now takes the **lowest** surface at its hit (`JM_EDGEZ_TOP=1` restores the old behaviour):

| viewpoint | null | old regression | with lowest-surface |
|---|---|---|---|
| **s=1042** (`trees03`'s own location) | 0.14 % | 11.23 % | **1.49 %** |
| s=3000 | 0.43 % | 14.81 % | 15.99 % |

**At the offending object's own location the regression is essentially gone.** s=3000 is unchanged —
it is a *different* object, which three sprints of reasoning about "the Monza canopy" as one thing had
obscured.

### The residual, now named instead of mysterious

`JM_EDGEZ_RANK` (new) ranks every off-HAT object by how much the two march targets disagree:

| object | nearest | centroid | Δ | lapdist |
|---|---|---|---|---|
| `trees18` | 7.4 | 2.0 | **+5.5** | 1873 |
| `trees19` | 6.7 | 3.2 | +3.4 | 2077 |
| `trees69` | 3.9 | 1.3 | +2.7 | 704 |
| `trees73a/b` | 3.1 | 1.1 | +2.0 | 573 |

**9 of 40 off-HAT objects still move more than a metre.** These are not overlapping-surface cases — the
two marches simply reach genuinely different ground in different directions. For an object the HAT does
not cover, "the ground height" is not defined; both marches are estimates. The principled next step is
to sample **several directions and take the lowest**, rather than trusting whichever way one ray
happened to point.

### Status

Gate stays — s=3000 is still wrong. But after three sprints of dead ends the problem is **decomposed**:
one mechanism found and fixed, the residual measured, ranked and attributed to a different cause.
Verified harmless where `edgez` actually ships: Watkins changes **0.19–0.36 %** of frame, so E72-S7's
restored pit complex is untouched.
