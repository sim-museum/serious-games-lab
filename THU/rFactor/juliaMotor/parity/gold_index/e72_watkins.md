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
