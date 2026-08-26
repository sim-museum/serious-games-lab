# Gold index — Spa (E71)

Oracle: `/home/admin/gold standard/julia racer/spa/260802_spa_nintendo.mp4`
(chase/"nintendo" view, 357 s, 1920x1080). Cockpit companion:
`260802_spa_cockpit.mp4` (388 s).

Built per QA_METHOD_GOLD_PARITY.md step 1 — **inventory the gold as data before rendering
anything**. This is a time → scene map, not yet a time → lapdist map: converting it needs one
`JM_SHOTS` sweep to pin `s` values against these scenes, which is the next step and needs the
display.

Composites: `spa_lap_gold.jpg` (whole lap, 10 s cadence), `spa_village_gold.jpg`
(300–328 s at 2 s cadence — the section E71 is about).

## Whole lap, 10 s cadence

| t (s) | scene |
|---|---|
| 0 | start/finish straight — pit buildings, advertising hoardings and grandstand on the LEFT; road clear |
| 10–20 | hoardings both sides, then downhill right-hander |
| 30–60 | tree-lined descent, armco both sides, open countryside opening out |
| 70–110 | fast open country, hedges and fields, occasional white marker posts |
| 120 | flags (German/other) on the LEFT at a corner; small structures set well back |
| 130–200 | long open country sections, distant farmland, telegraph poles |
| 210 | Italian flag + trees on the LEFT at a corner |
| 220–290 | rolling country, pine stands, guardrail |
| 300–330 | **village section — see the detail table below** |
| 330 | **"CEAT" banner spanning the road overhead**; dense crowd both sides |
| 340 | grandstands packed with spectators on the LEFT; road clear |
| 350 | pit straight approach, flags |

## Village section, 300–328 s at 2 s cadence — the E71 evidence

| t (s) | what is where |
|---|---|
| 300–314 | open road, trees, guardrail; nothing at the roadside |
| 316 | village first visible AHEAD and to the LEFT, still distant |
| 318 | **a house appears on the RIGHT, set back behind a grass verge** |
| 320 | **white house with red roof on the RIGHT, immediately at the roadside but BEHIND the verge**; spectators begin lining the LEFT |
| 322–324 | continuous lines of spectators BOTH sides, standing on the verges behind the road edge; buildings behind them |
| 326–328 | crowd lines continue; road still clear |

## What this establishes for E71

⭐ **In gold, the racing surface is clear for the entire lap.** Houses sit immediately at the
roadside but always BEHIND a grass verge, and spectator lines stand ON THE VERGES, never on the
asphalt. So the JM defect (E68-S2: oversized buildings ON the track that you can drive through and
see inside) is a PLACEMENT error against a gold that is unambiguous — not a judgement call about
how close to the road a building belongs.

The gold houses are also modest single-storey cottages. E68-S2 describes JM's as *oversized*, so
scale is likely wrong as well as position; both need checking against 318–320 s.

## Not yet established

- The `s` (lapdist) values for these scenes — needs a `JM_SHOTS` sweep (display required).
- Whether JM's misplaced buildings are THESE buildings moved, or different instances. Do not
  assume; the fix differs (move an instance vs. delete a duplicate).
- Colour findings are deliberately absent from this pass. Per method step 4 and this project's own
  history (yellow Spa trees, E68-S3, may be authentic autumn sprites), decode the source texture
  before calling any colour wrong.

---

## E71-S2 — native sweep + gold pairing (2026-08-26)

Native capture: one session, chase view, `s` = 0…14000 (17 shots).
**Spa centreline = 14,099 m**, so gold time ↔ lapdist maps as `t = s/14099 × 357`.
Composites: `spa_lap_native.jpg` (native lap), `spa_s12000_house_in_road.jpg` (the defect),
`spa_s8000_s12500_ab.jpg`.

### ⭐ E68-S2 REPRODUCED with an exact location — s = 12000

| | |
|---|---|
| **gold** (t = 303.9 s) | open road descending through trees, guardrail on the left, **no building anywhere near the road** |
| **native** (s = 12000) | **a large grey two-storey house standing directly across the racing surface**; the car drives into it |

The gold has no building at this point of the lap at all, so this is not a house nudged too close to
the road — it is an object at a location where gold has none. That distinction matters for the fix:
**this is not "move it back off the verge"**, and a fix that only offsets it sideways would leave a
house in a stretch of countryside that gold shows as empty.

### s = 8000 — a DIFFERENT problem, do not batch it with the above

| | |
|---|---|
| **gold** (t = 202.6 s) | a real village: red-brick buildings on the LEFT behind a kerb and pavement, spectators on the pavement, road clear and wide |
| **native** (s = 8000) | the same red-brick building family, but looming immediately at the car's left shoulder; the road reads narrower and the building sits at or over the edge |

⚠️ **Gold DOES have buildings here.** So s=8000 is a placement/scale/road-width question, not a
stray object, and it needs a different fix from s=12000. Batching them as "the Spa buildings on the
track" would produce one wrong fix for one of them.

### Correction to this document's own first pass

The first read of the native contact sheet put the house-in-road at s=12500. That was a
miscount of the sheet's columns; the A/B pairing at s=12500 showed open road in BOTH, which is
what caught it. The site is **s = 12000**. Recorded because an off-by-one in a landmark map
propagates into every fix that cites it.

### Still not established

- The exact extent of the s=12000 house (which instance, which `.dat`/OBJECTS entry) — needs a
  finer sweep around 11800–12200 and an object census at that location.
- Whether s=8000 is the building being wrong or the ribbon being wrong.
- Nothing about colour yet, by design.

---

## E71-S3 — the offender is NAMED, and the problem is bigger than one house (2026-08-26)

Ran the existing `JM_OBJDIAG` census (built for the earlier support-in-road defect — reused rather
than rebuilt) against Spa.

### The s=12000 house is `house43`

```
house43   lat = -6.0 m   lapdist = 12010.0   relyaw = +53°
100la     lat = -5.5 m   lapdist = 12006.0   relyaw = +53°
```

So the object to move is **`house43`**, and a **`100la`** distance-marker board is misplaced with it
at the same spot — the "100" sign visible in the native frame. They move together.

### ⚠️ It is NOT one house. 372 objects sit inside the road corridor.

| | count |
|---|---|
| objects with \|lat\| < 13 m (corridor) | 611 |
| objects with \|lat\| < 9 m (ROAD_HALFW) | **372** |
| of those, building instances | **28** (`house4/25/26/28/29/43/46/47/48`, `bu4/bu5/bu5s`) |
| most common single offender | `epolsp3` (telegraph pole) — **132 instances** |

Buildings inside the corridor, by lapdist: 1331, 2758(×4), 3903, 3927, 3951, 5174, 5316, 5675,
6874, 6886(×3), 7078(×3), 8010, **12010**, 13351, 13382, 13393, 13402, 13429, 13451, 13475, 13502.

**`house29` at lapdist 8010** is the s=8000 site from E71-S2 — so that one is now named too.

### ⚠️ Do NOT read "|lat| < 9" as "on the asphalt"

`ROAD_HALFW = 9.0 m` is the CLASSIFIER's corridor, which includes verges; 1967 Spa's asphalt is
much narrower than 18 m. What is established:

- **`house43` at lat −6.0 is visually ON the asphalt** — the E71-S2 photograph proves it, and that
  in turn puts the visual half-width at ≥ 6 m there.
- Objects at |lat| ≲ 6 are therefore almost certainly on the racing surface.
- Objects at |lat| 6–9 are **unconfirmed** and may be legitimately on the verge, where gold puts
  houses and spectators.

Treating all 372 as defects would mass-move scenery that gold shows correctly placed. The census is
a CANDIDATE LIST, not a defect list.

### Next

1. Establish the real asphalt half-width per section (from the ribbon/`.trk`), and re-filter the
   census against THAT rather than against ROAD_HALFW.
2. Spot-photograph the |lat| 6–9 band at a few lapdists to calibrate where the verge begins.
3. Only then decide per instance: move, delete, or leave. `house43` + `100la` at 12010 can be
   actioned now — gold has no building there at all.

---

## E71-S4 — the census criterion is WRONG, and the photographs prove it (2026-08-26)

Photographed the 6–9 m band directly (`spa_band_calibration.jpg`), with `house43` as a
known-on-road control.

| object | lat (m) | lapdist | what the photograph shows |
|---|---|---|---|
| `house43` | −6.0 | 12010 | **ON the road** (control, proven E71-S2) |
| `house29` | +8.1 | 8010 | wall immediately at the car's shoulder — **on/at the edge** |
| `house26` | −7.2 | 6874 | brick wall with garage door immediately alongside — **on/at the edge** |
| `house4` | −8.8 | 2758 | stone wall filling half the frame alongside — **on/at the edge** |
| `house46` | −7.0 | 5174 | narrow village street, buildings both sides at the kerb — **plausibly correct** |
| `house28` | −8.0 | 7078 | **OFF** — road clear, farm buildings distant |
| `bu5` | +6.3 | 13351 | **OFF** — village sits well off to the right, road clear |

### ⭐ Centroid lateral distance does not predict whether an object is on the road

`bu5` at **+6.3 m is clearly OFF**; `house43` at **−6.0 m is ON**. `house28` at −8.0 is OFF while
`house29` at +8.1 is hard against the car. The ordering by |lat| is simply not the ordering by
"is it in the way".

Two reasons, both structural:
1. **The measurement is the instance ORIGIN, not the mesh extent.** A large building whose origin
   is 8 m off can have its wall at 2 m. This project already knew this — the code comment that
   introduced `OBJINSTS` says exactly that ("centroid >13 m off-centreline but the mesh spans the
   road") — and the census I ran in E71-S3 nonetheless sorts by centroid.
2. **Road width varies along the lap.** A single `ROAD_HALFW` cannot be right everywhere, and 9.0 m
   was chosen for PHYSICS robustness (E30: stop centreline wobble reading as "off track"), not to
   describe the asphalt.

### Consequence for E71

**The 372-object candidate list from E71-S3 cannot be used as-is**, and any bulk action driven by
|lat| would move correctly-placed scenery while missing genuine offenders. What is needed is a
census keyed on **mesh extent vs the actual road edge**:

- compute each instance's world-space footprint (its mesh AABB under the instance transform);
- compare the NEAREST footprint corner to the ribbon edge at that lapdist, not the origin to the
  centreline;
- rank by penetration depth into the surface.

That is a real change to the diagnostic, and it is the honest prerequisite for the "move objects off
the road" work the PO asked for.

### Unchanged and still actionable

`house43` + `100la` at lapdist 12010 remain confirmed defects — gold has no building at that point
of the lap at all.

---

## E71-S5 — PO: "spa houses on the road are often also scaled up" (2026-08-26)

PO observation, and it matters because it may collapse two defects into one: **an oversized
building's FOOTPRINT spills onto the road even when its origin is correctly off it.** If that is
what is happening, "move the houses" is the wrong fix and "size the houses" is the right one.

### Hypothesis 1 — per-instance scale is parsed but never applied. **REFUTED.**

The OBJECTS transform is `translate * roty` with **no scale term**, while `ObjInst` carries a
`scale` field parsed from the `.3do` positioner. That looked decisive. Measured instead of assumed:

```
E71-S5 instance scale: n=9086  min=1.0  max=1.0  mean=1.0  non-unity=0 (0.0%)
   buildings only: n=275  min=1.0  max=1.0  mean=1.0
     house43/house29/house26/house4/bu5 — all exactly 1.0
```

**Every instance at Spa authors scale 1.0**, so the missing term changes nothing here. Hypothesis
dead. (Worth keeping the diagnostic: a track that DOES author non-unity scale would render wrong
and silently.)

### Hypothesis 2 — the MESHES themselves are oversized. **SUPPORTED, not yet confirmed.**

Kept-geometry heights, from the same census:

| object | height |
|---|---|
| `house46` | **16.3 m** |
| `house40` | **13.5 m** |
| `house25` | **12.0 m** |
| `eauhotel` | **21.0 m** |

A two-storey Belgian village cottage of the period reaches roughly **7–9 m** to the ridge; a modest
roadside hotel is not 21 m. These read **~1.5–2× oversized**, which matches the PO's report and would
explain footprints reaching the asphalt from origins 6–8 m away.

⚠️ **Not yet confirmed**, and the distinction is the whole fix:
- these are heights of the JM mesh as loaded — they have NOT been compared against the same object
  measured in the gold video;
- "a cottage should be 7–9 m" is domain knowledge, not a measurement of THIS gold;
- if the oversizing were a global unit-conversion error it would inflate the whole world, road
  included, and the road would then also be too wide — which is checkable and has not been checked.

### Next

1. Measure the same building in gold and native using the Lotus 49 as a ruler (≈3.8 m long,
   ≈1.0 m to the roll hoop) — the car appears in both, so it is a scale reference immune to
   perspective differences between the two captures.
2. Measure the JM road width against gold the same way. If the road is right and the houses are
   wrong, it is an object-mesh unit error; if both are inflated, it is global.
3. Only then choose: rescale the meshes, or move the instances. **Do not do both blind.**

---

## E71-S6 — the Lotus as a ruler: one good number, one failed measurement (2026-08-26)

### Gold, measured

At t=316.5 s (open road, car centred), on the row through the car:

```
road span 767 px   car 139 px   ->  road = 5.52 car-widths
```

A Lotus 49 is ≈2.0 m across the tyres, so **gold's Spa road is ≈11 m wide** there. That is right for
the period circuit (a two-lane Belgian main road), and it is a MEASUREMENT of this gold rather than
domain knowledge.

### Native, NOT measured — and why

The same method fails on the native frame: at the car's row the road runs off the right edge of the
image, so there is no right-hand edge to measure. The two chase cameras also sit at different
distances (gold's car is 139 px wide, native's ≈400 px in a similar-width frame), so ratios taken at
different rows are not comparable. **No native road width is claimed.**

### What the gold number nevertheless establishes

`ROAD_HALFW = 9.0 m` — the corridor the on-road classifier uses, and the basis of the 372-object
candidate list — implies an **18 m** road. Gold measures **≈11 m**. So the classifier's corridor is
roughly **1.7× the real road**, which independently confirms the E71-S4 conclusion that the
candidate list is far too permissive, and quantifies it: objects out to ~9 m are being flagged when
the asphalt edge is nearer ~5.5 m.

⚠️ This does NOT show the rendered road is too wide. `ROAD_HALFW` is a physics corridor chosen for
robustness (E30), deliberately wider than the asphalt. It is the CLASSIFIER that is mis-sized for
this purpose, not necessarily the track.

### Next — stop using pixels

Measure the rendered road width in **metres from the track mesh**: at a given lapdist, take the
lateral extent of road-textured triangles (`ROAD_PRED` already identifies them). That is exact,
camera-independent, and answers both open questions at once — whether the visual road matches gold's
11 m, and where the true asphalt edge is for re-filtering the object census.

---

## E71-S7 — the rendered road measures 8.2 m, and it corrects E71-S6 (2026-08-26)

Measured from the mesh (`JM_ROADWIDTH=1`), not from pixels: every `ROAD_TEX` triangle vertex
projected through `JuliaMotor.hat`, bucketed by lapdist, lateral min/max per bucket.

```
ROAD_TEX tris = 9658
median width 8.2 m   min 8.1   max 33.2 (S/F apron)
```

Remarkably uniform — most buckets are **exactly 8.2 m**, so the asphalt half-width is **≈4.1 m**.

### ⚠️ This corrects E71-S6's "gold road ≈ 11 m"

That figure came from 5.52 car-widths × an **assumed 2.0 m** car width. The assumption was doing the
work, and it was not measured. A GPL Lotus 49 with a 1.48 m rear track renders closer to **1.5 m**
across the tyres, which gives 5.52 × 1.5 = **8.3 m** — agreeing with the mesh's 8.2 m almost exactly.

**So the road is probably NOT too narrow, and the two oracles most likely agree.** The honest
statement is that the pixel method could not settle the road width, because its answer swings from
8.3 m to 11 m on an unmeasured input. The mesh measurement is absolute and does not.

### What survives, restated without the assumption

`ROAD_HALFW = 9.0 m` against an asphalt half-width of **≈4.1 m** — the classifier's corridor is
**≈2.2×** the real asphalt. That is now grounded in an absolute measurement rather than a car-width
guess, and it is the strongest form of the E71-S4 finding: the 372-object candidate list flags
everything out to 9 m when the road edge is at ~4.1 m.

### ⭐ And the pieces now fit together

- asphalt edge at **≈4.1 m**
- `house43` origin at **−6.0 m** — i.e. genuinely 1.9 m OFF the asphalt
- yet the photograph shows it **standing in the road**

Those are only consistent if the building's FOOTPRINT reaches inward past its origin — which is
exactly the PO's "the houses are also scaled up" and exactly E71-S4's "centroid is the wrong
measurement". Three independent observations converge on one defect: **oversized building meshes
whose footprints cross a correctly-placed origin onto the road.**

If that holds, the fix is to size the meshes, NOT to move the instances — and moving them would
scatter correctly-placed buildings while leaving them too big.

### Next

Compute per-instance footprints (mesh AABB under the instance transform) and rank by penetration
past the 4.1 m edge. That both tests the synthesis above and produces the actionable list.

---

## E71-S8 — the footprint metric SATURATES; whole-object AABBs are unusable (2026-08-26)

Implemented the E71-S7 plan: store each object's local horizontal AABB, transform its corners by the
instance's own `roty`+translate, project through `hat`, and rank by how far the footprint reaches
past the ±4.1 m asphalt edge.

**It does not discriminate.** 438 instances flagged and **every single one reports penetration
= 8.2 m** — exactly the full road width. `min(edge,hi) − max(−edge,lo)` saturates because the
footprints are enormous:

| instance | lateral span of AABB |
|---|---|
| `eauhotel` | −62.4 … +5.9 m (**68 m wide**) |
| `house9` | −17.3 … +44.6 m (**62 m**) |
| `house43` | saturated, pen = 8.2 |

A village cottage is not 60 m across. **The AABB is being taken over the WHOLE `.3do`**, and GPL
scenery objects are composite — one file can carry several buildings, a ground plane, or a whole
block. A single box around all of that spans the road no matter where the building actually is.

Seventeen instances also report `lapdist = −1, origin_lat = 999` (origin not on the HAT) while their
corners project onto the road — which is the same symptom seen from the other side, and would have
been read as "objects reaching in from off-track" if the saturation had not given it away first.

### What this costs and what it saves

The ranked list this sprint set out to produce **does not exist**, and a "438 objects penetrate the
asphalt" headline would have been false — it is an artefact of the metric, not a property of Spa.
Noticing that every value was identical is what caught it; a list sorted by a saturated key looks
perfectly plausible.

### Next — the fix is small and known

Retain a DECIMATED VERTEX LIST per object (say every 20th vertex) instead of the AABB, transform
those, and take the true lateral min/max. That is accurate for composite meshes, cheap in memory,
and turns the metric back into something that can rank. The diagnostic scaffolding
(`JM_FOOTPRINT`, `JM_ASPHALT_HALFW`) stays as-is — only the extent source changes.

---

## E71-S9 — the metric works, and it CONFIRMS the S7 synthesis (2026-08-26)

Two fixes were needed, not one.

**S9a — decimated vertex list instead of the AABB.** GPL `.3do` objects are composite, so a box
around the whole file spans the road wherever the building stands (E71-S8). Keeping every ~13th real
vertex dropped the flagged set 438 → 198 and tightened the spans — but it still saturated.

**S9b — the metric itself was wrong.** I was taking the lateral SPAN (min…max) and intersecting it
with the road band. Those laterals are measured at **different lapdists**: a 16 m building beside a
curve has one corner projecting at lapdist X and another at Y, so min/max across them describes no
real geometry. A vertex is on the asphalt iff `|lateral| < edge`, so the honest measure is
**`edge − min|lateral|`** — how close the mesh actually gets to the centreline.

### ⭐ Result: the photographed cases are reproduced by geometry

| object | lapdist | origin_lat | nearest vertex | penetration |
|---|---|---|---|---|
| `house43` | 12010 | **−6.0 m** (off the asphalt) | **≈0.3 m** | 3.8 m |
| `house29` | 8010 | **+8.1 m** (well off) | **≈0.1 m** | 4.0 m |
| `house41` | 11663 | −9.4 m | **0.0 m** | 4.1 m |

**`house43`'s origin is 6.0 m from the centreline — clear of the 4.1 m asphalt — while its mesh
reaches to within 0.3 m of the centreline.** That is the S7 synthesis confirmed by an independent
measurement, and it matches the E71-S2 photograph of a house standing squarely across the road.
`house29` reproduces the s=8000 photograph the same way.

**26 building instances** penetrate the asphalt on this measure.

⚠️ **Caveat, not yet resolved:** the top of the list is dominated by `armcow3`/`armco1` barrier runs
reporting `near|lat| = 0.0`. An armco following the road at ~6 m should never have a vertex on the
centreline. These are LONG objects whose vertices span hundreds of metres of track, and the
projection can wrap near tight curves — so they are probably false positives of the same
lapdist-conflation family, one level down. **The building rows are corroborated by photographs; the
barrier rows are not, and should not be actioned until they are.**

### Where E71 now stands

The defect is characterised: **oversized/oversprawling building meshes whose correctly-placed
origins sit off the asphalt while their geometry crosses it.** Moving instances would be the wrong
fix. The candidate list is real but needs the barrier-class false positives filtered before it
drives any edit.

---

## E71-S10 — ⚠️ RETRACTION: "the fix is to size the meshes, not move the instances" was WRONG

Measured the local mesh extents of every flagged building. The population is **mixed**, and the
single most important row refutes the S7/S9 synthesis:

| object | w × d × h (m) | reading |
|---|---|---|
| **`house43`** | **4.4 × 14.4 × 7.2** | **CORRECTLY SIZED.** 7.2 m to the ridge is exactly a two-storey cottage — the figure S5 predicted. Not oversized at all. |
| `house29` | 8.1 × 17.4 × 8.8 | normal |
| `house4` | 13.7 × 10.7 × 8.1 | normal |
| `house46` | 13.4 × 22.2 × 16.3 | genuinely tall — oversized or composite |
| `house1b` | 17.5 × 30.0 × 8.9 | **composite** |
| `house9` | 56.9 × 33.6 × 11.7 | **composite** |
| `eauhotel` | 74.3 × 109.8 × 21.0 | **composite** — a whole block, not a hotel |

### What this means for the house actually photographed in the road

`house43` is a **correctly-sized 4.4 × 14.4 m cottage** whose origin sits 6.0 m from the centreline
with its long axis at **relyaw +53°** to the road. A 14 m building skewed 53° across a 4.1 m
half-width road reaches the centreline from 6 m out — no oversizing required. And gold has **no
building at that lapdist at all** (E71-S2).

**So for `house43` the fix is exactly what the PO originally said: MOVE IT.** My S7 conclusion —
"the fix is to size the meshes, NOT to move the instances" — was wrong, and I stated it to the PO
with more confidence than the evidence carried.

### How the error happened, because it is instructive

S5 measured object HEIGHTS (`house46` 16.3 m, `house40` 13.5 m, `eauhotel` 21.0 m), found them too
tall for cottages, and generalised to "the houses are oversized". Two of those three turn out to be
**composite objects** — `eauhotel` is a 74 × 110 m block whose 21 m height is the tallest thing in
the file, not a hotel. The height statistic was real; the population it was computed over was not
what I thought it was. S7 then built a synthesis on it, and S9's confirmation confirmed only the
GEOMETRY (mesh reaches the road from an origin that does not), which is true under either
explanation and so could not discriminate.

### The corrected picture — there is no single fix

| class | example | fix |
|---|---|---|
| correctly sized, misplaced | `house43` @ 12010 | **move/remove** — gold has nothing there |
| composite `.3do` | `eauhotel`, `house9`, `house1b` | re-anchor or split; a whole block placed by one origin |
| genuinely oversized | `house46` (16.3 m) | rescale — **still unconfirmed against gold** |

Each flagged building needs classifying before it is touched. The census now supports that: extents
are printed alongside penetration.
