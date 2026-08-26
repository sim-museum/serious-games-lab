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
