# E72 — Watkins Glen gold-video parity

Oracle: `260802_watkinsGlen_nintendo.mp4` (118 s), `_cockpit.mp4` (112 s), plus
`260823_gpl_watkin_glen_race_gold.mp4` (617 s) — a full race, a third and denser oracle.
Native: 11-shot chase sweep, s = 0…4000. **Centreline = 3750 m.**
Loads through the GPL object pipeline: `113 trackside objects + 13 billboards + 5 solid`.
Composite: `e72_wg_native.jpg`.

## Both censuses come back clean

- **Crowd rows** (`JM_CROWDDIAG`): the nearest is `grndpe1l` at **lat 13.2 m** (s=229); everything
  else is 14–29 m out. Nothing is near the road.
- **Footprints** (E71-S9 census, edge ±4.1 m): **0 instances** cross the asphalt. No buildings.
- The 11 sweep shots show a clear road throughout — KENDALL banner at S/F, autumn trees, guardrails,
  all trackside.

So the PO's *"crowd block at the big bend"* (E68-CROWD, Watkins part) **does not reproduce**. Unlike
the Ring, the instruments here genuinely ARE connected — 113 objects and 13 billboards were
enumerated — so this is a real negative rather than an unplugged probe.

⚠️ Still not "fixed": 11 shots over 3750 m is one per 340 m, and the 617 s race video is a far
denser oracle than my sweep. The PO's report came from driving.

## ⚠️ The road-width instrument is UNRELIABLE on this track — do not quote its number

`JM_ROADWIDTH` reports a **median of 3.7 m**, which would be a single lane. It is an artefact:

- only **3,124 `ROAD_TEX` triangles** were recognised over 3,750 m, against **9,658** over Spa's
  14,099 m — roughly a quarter of the density;
- only **3 of 8 buckets** reported at all, two of them on **n = 6 and n = 12 samples**;
- the one well-populated bucket (s=0, n=41) gives **10.9 m**, which is plausible for the circuit.

This matches the known WG4/E64-S6 finding that the Watkins road oracle is partial. **The real width
is probably ~10.9 m; the 3.7 m median is sparse recognition, not a narrow road.** The ±4.1 m edge
used by the footprint census above was borrowed from Spa and is therefore unverified here — though
since it is conservative against 10.9 m, the "0 crossing" result survives either way.

## Next

Fix `ROAD_TEX` coverage for Watkins (which texture names does its asphalt use?) before any
width-dependent verdict on this track. Then use the 617 s race video for a dense landmark map — it
is the best oracle in the whole gold set and is currently unused.

---

## E72-S2 — clean on every census at the CORRECTED geometry; but the guardrail dedup does nothing

Re-ran with Watkins' own asphalt edge (**5.05 m**, from the fixed road-width instrument) instead of
the 4.1 m borrowed from Spa, and with the censuses now reachable on every track (E70-S2):

| census | result |
|---|---|
| centreline alignment | **16 buckets, all healthy** — no gaps, line never >3 m off the road |
| object footprints (edge ±5.05 m) | **0 instances**, 0 buildings |
| crowd rows | nearest **13.2 m** from the centreline |

Watkins Glen is the cleanest of the five tracks measured. The PO's *"crowd block at the big bend"*
does not reproduce on any instrument — and unlike the Ring, these instruments are demonstrably
connected here (113 objects and 13 billboards enumerated).

⚠️ Still not "closed": 11 shots over 3,750 m, and the PO saw it while driving. The **617 s race
video** remains the densest unused oracle in the gold set.

## ⚠️ E68-W7 (guardrail z-fighting): the fix that was supposed to solve it drops ONE triangle

The load line reads:

```
E68 S10: rail/fence dedup dropped 1 coplanar-duplicate tris
```

But E68-S10's own justification was *"13% of Watkins Armco tris and 10% of its fence tris are EXACT
coplanar duplicates that the track path never collapsed"*. Thirteen percent should be dozens to
hundreds of triangles, not **one**. Spa, which was not the motivating case, drops 4.

So either the dedup's quantized centroid+area key is not matching the duplicates it was written for,
or the 13% measurement referred to something the key does not capture. **Those need different
fixes**, and the guardrail z-fighting the PO reported is very likely still present because the
remedy is not firing.

⚠️ I have **not** independently verified the 13% figure — it is quoted from the code comment. The
next step is to count Watkins' `railfam` triangles and its actual coplanar-duplicate pairs directly,
which settles whether the claim or the key is wrong.

---

## E72-S3 — the dedup is not broken; the 13% premise does not reproduce

Counted directly (`JM_RAILDIAG=1`), reporting per-part and global duplicates side by side so
"wrong key" and "wrong scope" could be told apart:

| track | rail/fence parts | triangles | dup (per-part) | dup (global) |
|---|---|---|---|---|
| **Watkins** | 2 | **2,436** | **1** (0.0%) | **1** (0.0%) |
| Spa | 4 | 580 | 4 (0.7%) | 4 (0.7%) |

**Both counts are identical**, so the per-part `seen` set is not hiding cross-part duplicates — my
hypothesis going in. And there is **no 13%**: one duplicate in 2,436 triangles.

So E68-S10's dedup is doing exactly what it can, and the claim that motivated it —
*"13% of Watkins Armco tris and 10% of its fence tris are EXACT coplanar duplicates"* — **does not
reproduce against the mesh the dedup actually sees**.

### Leading explanation, not yet confirmed

`TRACKMAIN0` is produced by `extract_gpl_car(...; track=true)`, which **already contains a
coplanar-panel dedup** for GPL's double-sided signs/awnings/walls. If that stage removes the
duplicates first, the rail dedup downstream finds nothing left — the 13% would have been real when
measured on raw `.3do` data and is stale by the time this code runs. That makes the rail dedup
**redundant rather than broken**, which is a different conclusion from "the fix is not firing" that
E72-S2 recorded.

### Consequence for E68-W7 (the PO's guardrail z-fighting)

If there are no duplicate faces left, **duplicate removal cannot be the cure**. The z-fighting the
PO sees must come from something else — near-coplanar but non-identical faces (offset by
millimetres, which the 2 cm centroid quantisation would merge but the extractor's exact test would
not), or depth-buffer precision at distance. Those need different work, and W7 should be re-scoped
before more dedup effort goes into it.

⚠️ Confirming this means counting duplicates in the RAW parse rather than in `TRACKMAIN0`. Not done.

---

## E72-S5 — the pit structures are placed, kept, and NOT VISIBLE at their own lapdists

Photographed Watkins at each structure's recorded position (`e72_pit_sites.jpg`):

| shot | expected there | what is there |
|---|---|---|
| s=3550 | `pitfill2` (lat −28.7) | bare road, grass, distant treeline |
| s=3650 | `newpit` (lat −41.9) | bare road, guardrail, treeline |
| s=3720 | approach to S/F | Kendall banner, a distant structure on the far horizon |
| s=578 | `tower1` (lat −26.9) | trees left, fence right — **no tower** |

**Every one is absent from the frame.** They are placed (E72-S4 confirmed fate=mesh, no filter drops
them) yet nothing renders where they should be.

### Two candidate explanations, and the lateral offset does not fully cover it

1. **Too far to one side to enter a forward-facing view.** At 28–42 m lateral and the car's own
   lapdist, an object sits nearly abeam the camera — outside a ~60° forward FOV. This explains
   `newpit` at 42 m plausibly.
2. **But `tower1` at 26.9 m should clip the frame edge**, and does not. A tower is tall; at 27 m it
   should be visible above the verge even when abeam. Its absence is not explained by lateral offset
   alone.

### Next — check the vertical, which nothing has looked at

`OBJINSTS` carries each instance's base height (`ploz`). If these structures are placed **below the
terrain** they would be invisible regardless of lateral distance, and the E70-S2 note about objects
being snapped to "OUR terrain (the HAT) instead of their authored GPL height" is a plausible
mechanism — a snap that fails or lands wrong buries the object.

That is one diagnostic line away: report base height against `groundz(x,y)` for these four instances.
**Until then "the pit building is misplaced laterally" remains a hypothesis, not a finding** — E72-S4
already had to retract one confident claim about these objects.

---

## E72-S6 — ⭐ ROOT CAUSE: the pit buildings are OFF-HAT and sunk to `trkzlo` — buried ~29 m

Reported each instance's base height against the terrain under it:

| object | lapdist | lat | base | ground | verdict |
|---|---|---|---|---|---|
| `tower1` | 578 | −26.9 | 20.6 | 20.6 | **Δ=0 — correctly snapped, on the ground** |
| `newpit` | 3651 | −41.9 | **−8.7** | — | **OFF-HAT** |
| `pitfill2` | 3551 | −28.7 | **−8.7** | — | **OFF-HAT** |
| `pitgrnd1` | 3604 | −32.4 | **−8.7** | — | **OFF-HAT** |
| `grand` ×1 | — | — | 33.5 | 33.5 | Δ=0 — fine |
| `grand`, `grandl` | — | — | 11.5 / 0.7 | — | OFF-HAT |

**−8.7 m is Watkins' `trkzlo`** — the lowest elevation on the track (`JM_OBJDIAG` reports
`trkzlo=-8.7 trkzhi=40.7`). Objects that fall outside the terrain HAT get that value as a fallback.
The terrain around the pits sits near **20 m**, so these buildings are placed roughly **29 metres
underground**. That is why they are invisible, and it is nothing to do with their lateral offset.

### The mechanism

Objects are **snapped to our terrain rather than their authored GPL height** — a deliberate fix for
floaters, since GPL placed scenery on dune terrain this port does not reproduce. But when a point
lies **outside** the HAT, `groundz` returns a sentinel and the code falls back to `trkzlo`. For an
object 28–42 m off the road — beyond the modelled terrain — the fallback is catastrophic: it drops
the object to the circuit's lowest point.

**A guard against floating objects is burying them instead.** `tower1` at 26.9 m is inside the HAT
and lands perfectly; `pitfill2` at 28.7 m is outside it and sinks. **The failure boundary is roughly
27–29 m of lateral offset**, i.e. the edge of the terrain mesh.

### What the fix should be

An off-HAT object should **keep its authored GPL height**, not take `trkzlo`. The snap exists to
correct heights where the terrain is known; where it is unknown there is nothing to correct toward,
and the authored value is the best estimate available.

⚠️ Before changing it: this fallback is presumably load-bearing somewhere (it was chosen over
"leave it floating"), and other off-HAT objects — `tree8`, `treesrb1`, `tree6/7`, `grandl` — are
currently sunk by the same path. Fixing it will make **all** of them reappear at their authored
heights, which is a large visual change and needs photographing, not just reasoning.

---

## E72-S7 — ✅ FIX SHIPPED: Watkins' pit buildings and grandstands are restored

**The bug was the march TARGET.** `edgez` grounds an off-terrain object by marching from it toward
the **lap's geometric centre** until it finds terrain. That works for objects *outside* the loop. For
anything *inside* it — Watkins' pit complex, 29 m off the road — the direction points **away** from
the track, deeper into unmodelled infield, so the march finds nothing and falls back to `trkzlo`.
That is how three buildings ended up ~29 m underground while `tower1`, just inside the terrain at
26.9 m, landed perfectly.

**Fix:** march toward the **nearest centreline point** instead. Correct from either side of the
circuit. `JM_EDGEZ_CENTROID=1` restores the old target.

### Result — measured and photographed

| object | before | after |
|---|---|---|
| `newpit` | −8.7 (buried) | **3.9** |
| `pitfill2` | −8.7 | **7.2** |
| `pitgrnd1` | −8.7 | **6.2** |

Photographs (`e72_pit_restored.jpg`) show, appearing where there was bare grass:
- **s=3600** — the blue/white **Dunlop Tires grandstand with crowds**
- **s=3700** — the **multi-storey pit/timing building**, which is exactly what gold shows at S/F
- **s=0** — trackside crowds and a **Total Performance** hoarding

This closes the "Watkins pit building missing" thread from `missing_structures.md`, which began as
*"the building is absent"*, was corrected to *"placed but invisible"*, then to *"buried"*, and is now
fixed.

### Cross-track regression check — done, not assumed

This changes every off-terrain object on every track, so Zandvoort was photographed before and
after: **grandstand, Dunlop hoardings and crowds all present in both**, 2.5% of pixels changed at
S/F (minor height adjustments), 0.16% at s=1600. **No object lost, none left floating.**

⚠️ Spa, Monza and the Nürburgring have **not** been re-photographed. The change is default-on and
revertable with one env var; a sweep on those three is the outstanding verification.

**Sixth fix shipped in this batch.**
