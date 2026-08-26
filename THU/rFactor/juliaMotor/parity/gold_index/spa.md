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
