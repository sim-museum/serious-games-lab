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
