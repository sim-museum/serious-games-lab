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
