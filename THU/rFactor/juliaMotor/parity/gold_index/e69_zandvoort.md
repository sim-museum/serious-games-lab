# E69 — Zandvoort gold-video parity

Oracle: `260801_zandervoort_nintendo.mp4` (144 s) + `_cockpit.mp4` (181 s).
Native: 11-shot chase sweep, s = 0…4000. **Zandvoort centreline = 4181 m.**
Composites: `e69_zand_gold.jpg`, `e69_zand_native.jpg`.

## The PO's reported defect does NOT reproduce here

PO (E68-CROWD): *"perpendicular spectator rows FLOAT above or sit ON the track — Zandvoort several
places."*

- `JM_CROWDDIAG`: **96 crowd rows kept, only 2 within 6 m of the centreline** — `ppl_s3` at
  lat +5.2 (s=750) and `ppl_m1` at lat −5.5 (s=3851). Both are outside a ~4.5 m asphalt edge, i.e.
  on the verge where gold puts them.
- All 11 sweep shots show crowds **on the banks and verges, none on the asphalt.**

The renderer already carries filters for this (`onroad_crowd`, `perp_crowd`, and the E68-S8b rule
that drops billboard crowds when on the road), so the likeliest reading is that E68-CROWD was
**already fixed for Zandvoort** by that work.

⚠️ **NOT claimed: "fixed".** 11 shots over 4181 m is one sample every ~380 m, and a floating block
can sit between samples — the PO saw these while driving the whole lap, which is far denser coverage
than this sweep. The honest statement is **not reproduced at 11 sample points, with a census that
finds only 2 rows near the road.** Closing it needs either a denser sweep or the PO pointing at a
location.

## Sky grade: MATCHES gold — do not "fix" it

Native renders a flat overcast sky. So does gold, in every frame sampled. **This is correct.**
Recorded emphatically because this project has form here: an earlier autonomous pass graded the
Zandvoort sky toward a superseded gold set (QA_METHOD_GOLD_PARITY.md step 5), and the washed-out
look invites exactly that mistake again.

## Candidate deviations, unverified

1. **Kerbs** — gold shows red/white striped kerbing at the corner apexes (clear at t=24/32/40/48 s);
   the native sweep shows pale edges with no obvious striping at this sampling resolution.
2. **Crowd density and proximity** — gold's spectator rows are dense and stand right at the track
   edge; native's read sparser and set further back.
3. **Road tone** — gold's asphalt is a darker grey; native's is paler.

All three need a matched-landmark pair before they are treated as defects; (3) especially, since
tone judgements from unmatched frames are exactly what step 4 of the method warns about.

## Already classified — do not re-open

The cyan block at s≈4000 is GPL's own teal pond texture, classified as an authentic-asset surprise
in QA_METHOD_GOLD_PARITY.md.

---

## E69-S2 — ⚠️ CORRECTION: the PO's on-track spectators ARE reproduced

E69-S1 concluded the crowd report *"does not reproduce"*, on the strength of `JM_CROWDDIAG` finding
only 2 of 96 rows within 6 m of the centreline. **That census measures instance ORIGINS.** Running
the extent-based footprint census (E71-S9) instead:

| object | lapdist | origin lat | **nearest vertex** |
|---|---|---|---|
| `ppl_m1` | 3851 | −5.5 m | **0.2 m** |
| `ppl_l3` | 3256 | **+12.3 m** | **0.8 m** |

**Two spectator rows have geometry reaching the centreline from origins 5.5 and 12.3 m away.** The
PO reported *"perpendicular spectator rows float above or sit ON the track — Zandvoort several
places"*, and that is exactly what this is.

This is the E71-S4 lesson repeating on a different object class: **centroid distance is not the
"is it in the way" ordering**, and `JM_CROWDDIAG` — which predates that finding — still sorts by
origin. A row whose origin is 12 m out looks perfectly innocent by that measure while its mesh lies
across the racing line.

**So E69-S1's negative was an artefact of the instrument, not a fact about the track**, and the
sweep photographs that appeared to corroborate it simply did not sample s≈3256 or s≈3851.

## Also found: a bank of bushes ON the racing surface

`bushes01/02/03/04` × ~12 instances cluster at **lapdist 2309–2405**, reaching `near|lat|` of
**0.1–1.4 m** — i.e. onto the road. Origins sit at 1.8–5.8 m. Same shape as the spectators: modest
origin offset, mesh across the line.

## Other measurements this sprint

- **Road width 9.2 m** (asphalt edge ≈4.6 m) — Zandvoort's own figure; the footprint run above used
  the borrowed 4.1 m, so it is **conservative** and a re-run at 4.6 m will flag more.
- **Centreline alignment: 16 of 17 buckets healthy.** The single flagged bucket (s=250, 4.6 m, 52
  tris) sits right at the asphalt half-width and is very likely the centroid artefact recorded in
  `centreline_on_road.md`, not a real defect.
- **Rail/fence triangles: 8 in total, 0 duplicates.** Zandvoort barely uses the `railfam` textures,
  so the guardrail dedup is irrelevant here.

---

## E69-S3 — gold pairing at the three flagged sites: one render bug, one MISSING-CONTENT hole

Paired each on-track object from E69-S2 against gold at the same lap fraction
(`e69_zand_ab.jpg`).

### s=3256 — `ppl_l3`: a crowd row rendered as a WALL

- **gold:** a line of spectators standing on the **right verge**, behind a low barrier. Road clear.
- **native:** a **huge yellow-green crowd texture filling the entire left of the frame** and
  overhanging the road edge.

The census said this row's mesh reaches 0.8 m from the centreline from an origin 12.3 m out. This is
what that looks like: not a small object nudged onto the track, but a **billboard drawn at the wrong
scale and orientation** — flat geometry where GPL draws a camera-facing sprite. **Same family as the
Nürburgring's billboard defect (E76-S5/S7)**, one step further along: the Ring's don't draw at all,
Zandvoort's draw wrongly.

### ⭐ s=3851 — the main straight: gold is full, native is EMPTY

- **gold:** grandstands, pit buildings, the **Dunlop bridge**, advertising, packed crowds — the
  busiest scene on the lap.
- **native:** **bare grass and an empty road.** No grandstand, no pits, no bridge, no crowds.

**This is the same defect the PO reported on the Nürburgring, on a second track.** Zandvoort's main
straight is missing its buildings and crowds entirely. It was not caught earlier because the E69-S1
sweep sampled s=3600 and s=4000 and stepped over it, and because the crowd census (origin-based)
could not see it.

### s=2350 — `bushes01–04`: no defect visible

Gold shows a clean road through the dunes with a hedge line; native likewise. The flagged bushes are
not visibly on the racing surface here. The census flags them at 0.1–1.4 m, so either they are
low/thin enough not to read, or this is a footprint false positive of the kind E71-S9 warned about
for long objects.

### Consequence

E76 should be **widened beyond the Nürburgring**: *"objects deleted"* now has a confirmed second
instance on Zandvoort's main straight. And the billboard-rendering defect now has two tracks'
evidence with **opposite symptoms** — absent on the Ring, oversized-and-flat here — which is a
strong hint they share one cause in how sprite objects are treated.

---

## E69-S4 — ⚠️ RETRACTION: Zandvoort's main straight is NOT empty. I compared the wrong point.

E69-S3 reported *"s=3851: gold has grandstands, pits, Dunlop bridge and packed crowds; native has
bare grass"* and concluded the PO's E76 defect had a second instance on Zandvoort. **That is wrong.**

`JM_OBJFIND` shows Zandvoort places `tower` at **lapdist 12** and `pitbldg` at **lapdist 89** — both
at start/finish, both kept as meshes. So the buildings are there. Photographing native **s=0**
(`e69_mapcheck.jpg`) shows a **packed grandstand, Dunlop hoardings, Caltex/Havoline signage and
spectators lining both sides** — a close match for gold.

**The error was mine, in the lapdist mapping.** I converted gold video time to lapdist linearly
(`s = t/144 × 4181`), which put t=132.6 s at s=3851. But the gold car accelerates and brakes, and the
video's start is not the lap's start — so near the end of the lap that mapping drifts by hundreds of
metres. s=3851 is **330 m before** the straight, out in the dunes, where gold's *own* footage would
also show empty dunes.

### Consequences

1. **Zandvoort has no missing-structures defect.** The cross-track table in `missing_structures.md`
   must drop it: the count is **two of five affected (Nürburgring, Watkins), not three**.
2. **Every finding derived from a linear time→lapdist map is suspect**, and several exist. The Spa
   pairings (E71-S2) used the same method — though there the objects were confirmed independently by
   the object census, which does not depend on the mapping.
3. **E76 (Nürburgring) survives**, because its evidence is not the video pairing: the scenery census
   found 2,231 of 3,109 placements dropped and 50 objects parsing to zero triangles. That is
   mapping-independent.

### The lesson worth keeping

A video-to-lapdist map is only trustworthy where speed is roughly constant and the start is pinned.
**Pairings should be anchored on landmarks, not arithmetic** — which is exactly what
QA_METHOD_GOLD_PARITY.md step 3 already says ("landmark-map the lap by sweep, then pin gold↔native
pairs"), and which I did not do.

---

## E69-S5 — ✅ the on-road filters all tested the ORIGIN. Footprint test ships; the spectator wall is gone.

The PO's standing instruction is *"move any objects (lines of people, houses) that are on the actual
road to the places they belong"*. E69-S3 reported `ppl_l3` as a wall across the left and attributed
it to *"a billboard drawn flat"*. **That attribution was wrong** — `JM_OBJDIAG` lists only 5
billboards on Zandvoort (`haie001`, `tree2`, `tree1`, `pine1`, `pine3`, all 2.5 m), no crowds. The
crowd rows are MESH objects.

### The real defect

Every existing on-road filter — `onroad_crowd`, `perp_crowd`, `onroad_bldg` — projects the object's
**origin**. `JM_FOOTPRINT` finds **45 instances whose geometry crosses the asphalt**:

| object | nearest \|lat\| | lapdist | ORIGIN lat |
|---|---|---|---|
| `ppl_m1` | **0.2 m** | 3851 | −5.5 m |
| `ppl_l3` | **0.8 m** | 3256 | **12.3 m** |
| `bushes01` ×many | 0.1–1.1 m | 2309–2416 | ~2.0 m |
| `ppl_l5` | 2.3 m | 818 | 9.8 m |

⭐ `ppl_l3` reaches **0.8 m from the centreline from an origin 12.3 m away**. No origin-based test can
ever catch that — which is the third time this run a single-point measure has failed on an extended
object (E71-S8 footprint-vs-origin, E73-S7 single-point grounding).

### What shipped

`onroad_fp(i)` — the nearest transformed footprint vertex, the same measure `JM_FOOTPRINT` reports —
scoped to **vegetation and crowd families**, where the evidence is. Buildings keep their origin rule
and overhead spans are untouched (a bridge across the road is authored, not a defect). `JM_ONROAD_FP=0`
reverts.

**Result at s=3250: the wall of spectators across the track is gone**, replaced by a crowd line
beside the road — null control 0.16 %, change 14.44 %, and visually unambiguous.

### ⚠️ Two things I could not show, stated plainly

1. **The bush thicket has no visual evidence.** 41 instances hit the filter but only **6** survive the
   other filters to be removed. At s=2380/2590 the frames are visually identical apart from car
   position.
2. **My "grass bank engulfing the car" reading was wrong.** That mass is Zandvoort's **dune terrain** —
   the circuit runs through dunes — not a misplaced object. Retracted.

### ⚠️⚠️ The null control varies from 0.16 % to 55 % ON THE SAME TRACK

E75-S8 established this harness has a ~0.4 % noise floor. Zandvoort shows that figure is **not a
constant**:

| viewpoint | null control | treatment | verdict |
|---|---|---|---|
| s=2380 | **55.09 %** | 57.65 % | **no evidence whatsoever** |
| s=2590 | 4.87 % | 58.04 % | looked real; frames are visually IDENTICAL — jitter |
| s=3250 | 0.16 % | 14.44 % | real, confirmed by eye |

The auto-drive reaches a given lapdist at a slightly different position each run; where the frame is
filled by near-field geometry (a dune two metres from the camera) a centimetre of car movement
repaints most of the screen. **The jitter magnitude itself varies between runs**, so even a measured
null at one viewpoint does not license the number at that viewpoint — s=2590's 4.87 % null would have
"confirmed" a 58 % change that is not there.

**Rule: a pixel A/B is only admissible where the null control is small AND the change is visible.**
Number and picture must agree, or neither counts.

### ⚠️ An invalid TRACK name silently loads a FALLBACK

`TRACK=watkinsglen` ran to completion reporting "track: Watkinsglen" — and a **4181 m centreline,
which is Zandvoort's**. Its object counts matched Zandvoort exactly (215/39/296). The real name is
`watglen` (3750 m). A regression suite that used the wrong name would have "passed" every track while
testing one track five times.

### Cross-track effect (real names, all verified by centreline length)

| track | objects removed |
|---|---|
| Zandvoort | 6 |
| Spa | 1 |
| Monza, Watkins (watglen, 3750 m), Nürburgring | 0 |

---

## E69-S6 — Zandvoort's classifier is SOUND; and the new verdict tool immediately caught me about to repeat a mistake

After E71-S13 fixed Spa's road classifier, Zandvoort had the lowest recognition of the measured tracks
(73.6 %) and looked like the next defect. **It is not one.**

### Zandvoort: 73.6 % is correct

Everything unrecognised near the centreline is genuinely not road:

| texture | on-road | off-road |
|---|---|---|
| `grass` | 529 | **3178** |
| `sand`, `sand2`, `sand2a` | 685 | 1283 — the dune run-offs |
| `wiref_s` | 46 | **2708** — fence |
| `wall_*`, `armco_s`, `hayba_e` | ~80 | ~120 — barriers |

The road here really is `groove` + `asphalt` + `curb` + `sgrid`, all recognised. **The recognition
PERCENTAGE is not a quality metric** — Spa scored 43.9 % and was badly wrong; Zandvoort scores 73.6 %
and is right. What matters is whether any *missed* texture is predominantly on the racing surface.

### Shipped: the census now returns a verdict, not a table to eyeball

It flags every missed texture with ≥65 % of its instances on-road, and reports **where each one lives**
— lapdist range, nearest and median |lateral|.

| track | recognition | verdict |
|---|---|---|
| Zandvoort | 73.6 % | **none — sound** |
| Monza | 86.2 % | **none — sound** |
| Watkins | 86.1 % | **none — sound** |
| Spa | 77.7 % | 4 flagged — see below |
| Nürburgring | — | **not measured**; load + census exceeds the run window |

### ⭐ The tool's first act was to stop a confirmation trap

On Spa it flagged four textures at 65–96 % on-road (`haudrtr1` 96.4 %, `brndrtr3` 88.2 %, `stvdrtr9`
69.3 %, `maldrtr6` 65.3 %) — which on the S13 rule would have been added as road. The location check
says otherwise:

```
stvdrtr9  nearest |lat| 3.4   median 4.8      maldrtr6  nearest 4.2   median 4.8
haudrtr1  nearest |lat| 4.5   median 4.9      brndrtr3  nearest 4.0   median 4.4
```

They sit **at the road edge**. Spa's half-width is ~4.4 m, so the census's fixed 5 m "on-road" window
is *wider than the road itself* — and any edge strip therefore scores highly. The percentages are an
artifact of the threshold, not evidence of road. **Not added.**

Adding them would have widened measured Spa toward the unverified "gold ~11 m" figure — i.e. the change
would have appeared to confirm a target that E71-S13 had just established is unverified. That is
exactly the shape of a confirmation trap, and the only thing that stopped it was asking *where* the
triangles are rather than *how many* are inside a threshold.

### ⚠️ The same doubt applies to my own S13 additions — stated plainly

| texture | median \|lat\| | |
|---|---|---|
| `groove` | 1.9 m | racing line |
| `asphr` / `asph` | 1.4 / 3.3 | asphalt |
| `griline` | 2.6 | grid markings |
| **`borcem` / `borcem_k`** | **4.4 / 4.3** | **the same band as the four just rejected** |
| `asfa` | 4.8 | same band |
| `bordo` (rejected) | 6.2 | outside |

**Lateral position cannot separate `borcem` from `haudrtr1` — both are edge strips.** The split rests
entirely on a semantic reading: `borcem` = *bordure ciment*, a PAVED cement edging, versus `drt` =
DIRT, a loose verge. That is a judgement, not a measurement, and it is recorded here as one.

**Consequence for every future width claim on Spa:** the honest quotation is **8.0 m of asphalt plus
~0.4 m of cement edging per side = 8.8 m paved**. A width figure for Spa is meaningless unless it says
which of the two it means — and the 0.8 m between them is precisely the difference the S13 addition
made.

---

## E69-S7 — ⭐ a real cross-track COLOUR defect: native's neutral surfaces are warm where gold's are cool

The PO's brief asks for *"correct object placement and color throughout"*, and colour has had far less
attention than placement. S7 measures it.

### ⚠️ First attempt was invalid — the same trap as E69-S4

Classifying pixels into sky / grass / sand / asphalt and comparing medians gave a dramatic result:
grass gold (29, 93, 69) vs native (93, 109, 60) — native's grass apparently far too red. **That
comparison is worthless.** Putting the two frames side by side shows they are at *different places*:
gold's frame has a **green verge**, native's a **khaki dune bank**. The classifier compared marram
grass against grass and called the difference a rendering error.

Zandvoort is a dune circuit with both surfaces, so "grass" is not one population here. Same lesson as
E69-S4: **a comparison that does not pin location measures the location, not the renderer.**

### What survives: asphalt, which is asphalt everywhere

Asphalt's neutrality is location-independent — a road is grey wherever you stand. Measured as R−B
(0 = neutral, + = warm/yellow, − = cool/blue):

| | frames | asphalt median | R−B per frame | mean |
|---|---|---|---|---|
| **gold** Monza | 4 | (118, 119, 123) | −8, −10, 0, 7 | **−2.8** |
| **gold** Spa | 6 | (125, 124, 129) | −6, −6, −7, −7, −3, −3 | **−5.3** |
| **gold** Zandvoort | 4 | (128, 127, 131) | −2, −4, −3, −1 | **−2.5** |
| **native** Zandvoort | 4 | (134, 135, 124) | 9, 10, 9, 10 | **+9.5** |
| **native** Monza | 3 | (106, 105, 93) | 15, 10, 13 | **+12.7** |
| **native** Watkins | 4 | (127, 129, 120) | 8, 9, 6, 8 | **+7.8** |

⭐ **Gold's asphalt leans slightly COOL on all three tracks; native's leans WARM on all three** — a
consistent swing of roughly **13 units**, with native's per-frame spread far tighter than gold's. This
is systematic, cross-track, and independent of viewpoint, so it is a genuine rendering defect and not
a sampling artifact. It will be tinting *every* neutral surface in the game.

### One candidate eliminated

The shader adds a **non-neutral additive fill**: `lit += uAmbFill*vec3(0.13, 0.135, 0.125)` — blue
lowest, so warm by construction, and the track draws with `ambfill=0.34`. An obvious suspect.

**Measured, not assumed:** `JM_TRACK_AMB` 0.34 → 0.00 leaves asphalt R−B at **8–10**, unchanged.
The ambient fill is **not** the cause. (Knobs `JM_TRACK_BRIGHT` / `JM_TRACK_AMB` added for this test
and kept.)

### Remaining candidates, in order

1. **`sat` = 1.12** in the overcast grade — a saturation boost amplifies whatever cast exists rather
   than creating one, but it would scale a small bias into a visible one.
2. **`suncol`** — Zandvoort's is (1.0, 1.0, 0.98), only 2 % warm, so it cannot explain +9.5 alone;
   but Monza's grade is warmer and Monza measures the warmest (+12.7), which is suggestive.
3. **The texture load path** — if GPL's textures arrive with a warm bias, everything downstream
   inherits it. This is testable directly by sampling a loaded asphalt texture before shading, and is
   the cleanest next measurement because it separates "our lighting" from "our texture decode".
