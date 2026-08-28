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

---

## E72-S8 — the cross-track check found a REGRESSION; the fix is now gated

Completing the verification E72-S7 left outstanding:

| track | pixels changed | verdict |
|---|---|---|
| Zandvoort | 2.5% @ S/F, 0.16% @ s=1600 | ✅ no loss, minor height adjustments |
| **Spa** | 1.17% @ S/F, 0.05% @ s=8000 | ✅ **gains a structure** at S/F that was previously buried |
| **Monza** | 1.0% @ S/F, **14.6% @ s=3000** | ❌ **REGRESSION** — a large tree/forest object is raised into the sky and overhangs the road as a dark canopy |

The Nürburgring is unaffected: its scenery uses a different loader that never calls `edgez`.

### Action: gate rather than revert

The fix is now applied on **Watkins and Spa only** — the two tracks where it is verified to help —
and excluded on Monza. Zandvoort neither gains nor loses, so it is left out too.

**Gating by track name is a holding measure, not a design.** The right end state is to understand why
Monza's object rises: the nearest-centreline march is correct in principle, so something else — a
very distant object, an unusually large mesh, or a march that terminates at an atypical height — is
producing the lift there. Until that is understood, the gate keeps two verified wins without shipping
a visible defect.

### Worth noting about the process

E72-S7 shipped this default-on having checked **one** other track, and flagged the remaining three as
outstanding. Two of the three were fine; the third was not. **The flag was the useful part** — had it
been recorded as "verified" rather than "one track checked, three outstanding", the Monza canopy
would have shipped and been found by the PO instead.

---

## E72-S9 — E68-W7 (guardrail "z-fighting"): all three candidate mechanisms are now eliminated

W7 has been carried since 2026-08-09 with "re-scope away from dedup" as its next step. S9 takes the
three mechanisms that could produce it and eliminates each on evidence.

### 1. Coincident faces — refuted (E72-S3, re-confirmed)

`JM_RAILDIAG` bins rail triangles by centroid at **2 cm** and by area, and finds **1 duplicate in
2436**. Two rails stacked within 2 cm do not exist, so duplicate removal was never the cure — which
is what S3 concluded and why W7 needed re-scoping.

### 2. Depth precision — already mitigated BEFORE the report

The renderer uses **reversed-Z** (`perspective_revz`, near→1/far→0) with `glClipControl(ZERO_TO_ONE)`,
`glDepthFunc(GEQUAL)`, `glClearDepth(0)` and a **`GL_DEPTH_COMPONENT32F`** buffer — verified present in
the shipping driver's main pass, not just in the older `drive_native.jl`. Its commit message reads
*"the complete cure for distant z-fight strobe"*.

⭐ **That landed 2026-06-17. The PO's report is 2026-08-09** — nearly two months later. So the fix was
already active when the artifact was seen, and depth precision cannot be the explanation either.
Checking the dates was worth more than any further experiment on this hypothesis.

### 3. Texture aliasing — enabled, verified active, and it changes nothing measurable

For long thin roadside geometry at a grazing angle, trilinear filtering cannot win: the footprint in
texture space is extremely anisotropic, so an isotropic mip choice is either blurred or aliased. That
strobes frame to frame and reads exactly like z-fighting. **Anisotropic filtering had never been
enabled here at all** — so it was a real gap regardless of W7.

Enabled (`JM_ANISO`, default 16) and **read back rather than assumed**:

```
[aniso] requested 16.0 → texture reports 16.0   (driver maximum 16.0)
```

The set succeeds at the driver's maximum. But the image barely moves:

| region | aniso off | aniso 16 | change |
|---|---|---|---|
| far road (most grazing) | 2.872 | 2.889 | **+0.6 %** |
| mid road | 1.796 | 1.770 | −1.5 % |
| near road | 2.232 | 2.231 | −0.0 % |

Guardrail viewpoints changed **0.18 % / 0.26 %** of pixels — at the noise floor. The likely reason is
that **GPL's source textures are tiny** (64–128 px), so there is very little detail for anisotropy to
recover; the mip chain is already near-flat.

**Shipped anyway**, because it is a standard filtering mode, verified active, costs nothing measurable,
and is correct for grazing-angle surfaces in general. Its benefit here is **unmeasured**, and that is
stated rather than implied — `JM_ANISO=1` disables it.

Note the readback exists because of E76-S5: a `catch` that swallowed its reason cost a whole sprint
there. Here the same shape of code would have let "no effect" mean either "no benefit" or "the call
silently failed", and those need opposite responses.

### ⚠️ Consequence: W7 needs the PO, not another mechanism

Three mechanisms, three eliminations, and four guardrail captures showing clean rails. Continuing to
test mechanisms blind is now the wrong move. **W7 should go back to the PO for a pointer** — which
corner, which lap, and ideally a still — or be re-derived from the gold-vs-native video at a named
location. Recorded as blocked on the PO rather than left open as if work remained.

---

## E72-S10 — Watkins' crowds are present and DO render; the cockpit view was hiding them

Gold's Watkins cockpit video shows dense spectator rows at several points. Four native cockpit captures
showed **none**, which looked like a missing-content defect of the E76 kind.

### It is not. Three instrument errors, then the answer

1. **`JM_OBJFIND` returned a confident false negative.** Searching
   `"ppl,crowd,people,spec,stand,grand,tribun"` reported *"0 placed instances — not in this track's
   placement list at all"*. The pattern is a **regex**, and its own comment documents pipe separation
   (`pit|tower|grand`); commas made a literal that could never match. **My error, not the tool's** — but
   a pattern that cannot match is indistinguishable from an absent object, and the tool stated the
   strong form. Commas are now accepted as alternation, and the null now says so and advises checking
   a name known to be placed first.
2. **The crowd family is named `grndpe*`** ("ground people") — the same family as the Ring's `ogrnd2`.
   Searching for it finds **52 placed instances**, at lapdists 51, 135, 229, 236, 253, 558, 587, 1041,
   1094, 1124…, nearly all `fate=mesh`. One is `fate=dropped` at lat 13.2 m — which is precisely the
   "nearest crowd 13.2 m" figure E72-S2 recorded.
3. **Capturing at those lapdists in COCKPIT view still showed nothing** — and that was the real clue.

### ⭐ The chase view settles it

The same lapdists in chase view show **a populated grandstand at s=253 and crowd rows along the right
at s=1094**. The crowds render correctly. What hid them is native's own cockpit.

Using E74-S10's temporal-invariance segmentation (cockpit = pixels static across three points on the
lap, largest component touching the bottom edge):

| | cockpit occupies |
|---|---|
| **gold** | **38.0 %** of frame |
| **native** | **49.4 %** of frame |

⭐ **Native's cockpit blocks about 30 % more of the driver's view than gold's.** That is no longer just
a cosmetic complaint about dial placement — it **hides trackside content that is present and correct**,
and it degrades every parity judgement made from the cockpit view.

### Cross-item consequence

E74's D4 (cockpit obstruction) and E74-S10's finding that the dial cluster sits ~1.8 wheel-radii too
high are the same defect seen from two directions, and this sprint shows it has a cost beyond the
dials: **content parity assessed from the cockpit view will under-report what the track actually
has.** Any future "X is missing" claim from a cockpit capture must be re-checked in chase view before
it is believed — as this one had to be.

---

## E72-S12 (cross-track) — the exposure table, redone with MATCHED views. E69-S11 is withdrawn.

E69-S11 measured exposure on asphalt (a neutral reference needing no location matching) and reported
**"the Nürburgring is 35 % too bright"**. S12 fills in the missing tracks and, in doing so, destroys
that finding.

### ⚠️ A gold frame is only a reference for the video it came from

E69-S11 compared gold **nintendo** frames (asphalt luminance **76.3**) against a native **chase**
frame. But gold's own Nürburgring **cockpit** video measures **104.0** on the same surface — the two
gold videos of the same track were shot in **different conditions**. The "+35 %" was a difference
between two gold videos, not between gold and native.

**This is a new failure mode.** The earlier ones were location mismatch (E69-S4, E69-S7, E73-S9) and
view mismatch. This is **source mismatch**: two gold recordings of the same track, at the same place,
disagree with each other. A gold frame is a valid reference only for **the view and the video it came
from**.

### The corrected table — cockpit view on both sides

| track | gold asphalt lum | native asphalt lum | native vs gold |
|---|---|---|---|
| **Spa** | 120.2 | 149.0 | **+24 %** |
| **Watkins** | 120.0 | 143.8 | **+20 %** |
| Nürburgring | 104.0 | 105.7 | **+2 %** |
| Zandvoort | 128.5 | 131.3 | +2 % |
| **Monza** | 117.5 | 101.3 | **−14 %** |

Both of E69-S11's headline numbers change: the Ring **+35 % → +2 %** (fine), and Spa **+53 % → +24 %**
(the +53 % also came from a chase-vs-cockpit mismatch).

### What survives, and what it costs

- **Withdrawn:** "the Nürburgring is 35 % too bright" and, with it, E70-S7's hypothesis (2) that
  `GRADE_NURB` explains the billboard cyan. **The Ring's exposure is correct.** The cyan therefore has
  *no* remaining explanation — brightness, white balance and now scene exposure are all eliminated.
- **Stands:** the per-track exposure spread is real and one-directional per track. **Spa (+24 %) and
  Watkins (+20 %) render brighter than gold; Monza renders 14 % darker.** Three tracks are off by
  ~20 % in luminance on a neutral surface, which is a concrete, per-track, testable colour defect and
  exactly the kind of thing the PO's *"correct… colour throughout"* covers.
- **Watkins specifically** is otherwise clean — every census, the on-road count (2 marginal), and the
  content check (E72-S10). Its exposure is now its one measured parity gap.

---

## E72-S13 — ⚠️ I shipped a per-track exposure correction, then found the metric that motivated it is invalid. REVERTED.

E72-S12's table said Spa renders **+24 %** brighter than gold, Watkins **+20 %**, Monza **−14 %**. S13
built the correction, shipped it, and then destroyed both the correction and the table.

### The loop, and where it broke

A per-track exposure multiplier was derived from those numbers and applied after the tone curve.
First pass looked like a clean success — every error roughly halved:

| track | before | after pass 1 |
|---|---|---|
| Spa | +24 % | **+7 %** |
| Watkins | +20 % | **+5 %** |
| Monza | −14 % | **−7 %** |

A second pass, re-derived as `old × (gold/measured)`, then produced an **impossible** result:
**Monza went from −7 % to −41 % while its multiplier increased from 1.16 to 1.247.** A larger
multiplier cannot darken a scene — and the frame's overall mean luminance confirmed it had in fact got
*brighter* (123.3 → 128.6).

### ⭐ The metric was measuring its own threshold

The asphalt mask is `sat < 22 && 60 < lum < 200`. Those are **absolute** cuts, so it is **not
exposure-invariant**: brightening lifts dark non-road pixels *above* the `lum > 60` floor and admits
them. Monza's mask grew from ~250 000 to ~380 000 pixels while its median fell 40 points.

**A metric whose population changes with the quantity being measured cannot close a loop** — and it
cannot compare two renderings of different brightness either, which is what the original gold-vs-native
table did.

### Re-measured without thresholds

Using a fixed image region and no colour cuts at all:

| track | gold | native as shipped | after pass 1 | after pass 2 |
|---|---|---|---|---|
| Spa | 53.7 | **50.3 (−6 %)** | 45.7 (−15 %) | 42.7 (−20 %) |
| Watkins | 53.7 | **53.5 (−0 %)** | 44.7 (−17 %) | 42.7 (−20 %) |
| Monza | 54.0 | **50.0 (−7 %)** | 58.0 (+7 %) | 62.7 (+16 %) |

**Native's exposure was already within −7 %…0 % of gold, and my "correction" made Spa and Watkins about
15 % worse.** Reverted to 1.0; verified back at +6 % / −7 %.

### What this costs and what it buys

- ⚠️ **E72-S12's exposure table is withdrawn.** +24/+20/−14 came from the biased metric. There is no
  measured per-track exposure defect.
- The `uExposure` uniform stays behind `JM_EXPOSURE`, unused, so a sounder measurement can drive it.
- Both metrics have limits — the threshold-free box samples a car-fixed region rather than the road —
  so the honest claim is only "no exposure error large enough for either probe to agree on".

**The tell was the impossible result.** Had pass 2 merely looked mediocre instead of self-contradictory,
I would have shipped a regression on three tracks and filed it as an improvement. Building the
correction is what exposed the flaw in the measurement that motivated it.

---

## E72-S14 — Watkins run at last, and the cross-track table corrected

E69-S16 checked a footprint change on Spa, Monza and Zandvoort and said plainly that **Watkins was
not run**, on the grounds that its single recorded intruder sat at 5.4 m and was therefore outside
the 4.1 m threshold either way. Run now:

```
102 instances clear of the road, 2 intruding of which 1 ACTUALLY RENDER
   grndpe1l   nearest |lat| 5.4   base -0.1 m
```

Watkins' measured half-width is **5.05 m** (`road_width.md`), so 5.4 m is off the racing surface.
**Watkins Glen has zero objects on its asphalt** — the cleanest of the four, confirmed rather than
assumed.

### Every track against its OWN half-width

The census corridor is ±6.0 m and `JM_ASPHALT_HALFW` is a single global at 4.1 m — Spa's number.
Neither is any given track's asphalt. Scoring each track against its own measured width:

| track | half-width | census ±6 m | **on its own asphalt** | previously reported |
|---|---|---|---|---|
| Spa | 4.25 | 105 | **25** | 18 |
| Zandvoort | 4.90 | 5 | **4** | 3 |
| Monza | 5.80 | 8 | **7** | 4 |
| Watkins Glen | 5.05 | 1 | **0** | not run |

**Every earlier figure was too low, and all in the same direction**, because E71-S16 and E69-S16
scored every track with Spa's 4.1 m. Monza is the worst affected — 4 becomes 7, nearly double —
which follows from it having the widest road (5.8 m) and therefore the largest undefended band.
Spa gains 7 (shrubs between 4.10 and 4.25).

The corrected total on real racing surface is **36**, not the 25 those two sprints implied. The
error was systematic rather than random, which is the kind that survives review: each individual
number was computed correctly, from a constant that was correct for exactly one of the four tracks.