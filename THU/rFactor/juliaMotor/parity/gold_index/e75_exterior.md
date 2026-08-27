# E75 — external Lotus 49 gold parity ("the nintendo view has no axles")

Oracle: the five gold **nintendo/chase** lap videos. Pair below is Spa,
`260802_spa_nintendo.mp4` t=316.5 s vs native s=12500 (open road, car unobstructed in both).
Composite: `e75_car_ab.jpg`.

## ⭐ D1 — no suspension geometry at all: the wheels are detached (PO's report, CONFIRMED)

Gold shows a complete rear end: **wishbones, driveshafts and radius rods** running from each hub in
to the gearbox, plus the gearbox/diff casing and two exhaust megaphones. Every wheel is visibly
attached.

Native shows **four grey cylinders floating beside a chassis with nothing connecting them.** There
is no linkage geometry of any kind between hub and tub. This is exactly the PO's "no axles" and it
is the dominant visual defect of the chase view — it is what makes the car read as disassembled.

## D2 — the track is too wide and the wheels sit at odd angles

The native wheels sit markedly further outboard than gold's, which tuck close to the body. The left
rear also appears canted rather than upright.

⚠️ **Track width is already a tuned parameter, not an unknown**: `JM_TRACK_F=0.78` /
`JM_TRACK_R=0.74` (half-track, m), and the code comment records that E62 tried 0.90 and found it
"splayed the fronts well outboard of the tub in the chase gold". So this was measured before and
set deliberately. **Do not re-tune it from this one frame** — if the wheels still look outboard at
0.78, the likelier culprit is D1 (no linkage to visually tie them in) or the camera, not the number.

## D3 — the exhausts appear detached and splayed

Two pipe-like parts project from the lower corners at angles gold does not show; gold's megaphones
exit rearward, close together, behind the gearbox.

## NOT a new defect — already classified

The wheels render **plain grey with no tread or rim detail**, and the run log reports
`11/12 Lotus parts textured`. This is the **asset-capability gap already recorded in
QA_METHOD_GOLD_PARITY.md** ("gold tyres carry tread textures; our wheel mesh is untextured — a
lighting fix can narrow but never close it"). Logged here so the next reader does not re-open it as
a new finding; it is not part of E75's fixable scope.

## Priority

D1 first, and alone if necessary. It is the PO's actual report, it is unambiguous against gold, and
D2's severity cannot be judged until wheels are visually connected to the car.

---

## E75-S2 — ⚠️ D1 RESTATED: the suspension DOES draw. The wheels are in the wrong place.

### Correction to E75-S1

I wrote *"no linkage geometry of any kind between hub and tub"*. **That is wrong.** The rear
suspension is extracted (`RSUSPP_A/B` from groups 27288/39792), is drawn in chase view, and is ON by
default. Toggling `JM_RSUSP` changes **3,250 pixels** — so it renders. What it does not do is
*read* as suspension: the highlight map (`e75_susp_draws.jpg`) shows it sitting **inside and behind
the tyre volume**, not spanning hub to gearbox as gold's does.

I inferred absence from appearance, on one frame, without toggling the switch that would have told
me. The switch cost one run.

### What the evidence now points at: the wheels and the body mesh disagree on width

Gold tucks the wheels close to the tub with the linkage visibly spanning the gap. Native places them
far outboard, and the linkage — authored at GPL's scale — cannot reach across.

Test (`e75_track_ab.jpg`): narrowing the drawn track from the shipped `0.78/0.74` to `0.64/0.60`
tucks the wheels in and the car immediately reads as a coherent assembly, much closer to gold.

⚠️ **That is a diagnosis, NOT the fix.** `JM_TRACK_F/R` is also the **physics** half-track, and
0.78 was set deliberately to match the real Lotus 49's ~1.52 m. Narrowing it to 0.60 would give a
1.20 m track and falsify the handling — buying a picture with a lie. E75-S1 warned against re-tuning
this number and that warning stands; the test above is a probe, not a proposal.

The real defect is that **wheel placement comes from a physics constant while the body and
suspension come from the GPL mesh at its own scale**, and the two disagree by roughly 18%. That is
the "two code paths disagreeing about one fact" shape. The fix is to reconcile them — place the
drawn wheels from the mesh's own hub positions (or scale the imported body to the physics track) —
so the picture and the physics stop being independent claims.

### Next

Measure the lateral position of the suspension mesh's outboard ends (the hub faces in `RSUSPP_A/B`)
and compare with the wheel centres at `WTRACK_R`. That converts "roughly 18%" into the exact
disagreement and says which of the two is wrong.

---

## E75-S3 — ⚠️ the "wheels ~18% too wide" hypothesis is REFUTED

Measured (`JM_WHEELFIT=1`):

```
rear-susp mesh lateral   A: -1.117 … -0.422    B: 0.422 … 1.159
car body (CARP) lateral      -0.442 … 0.442
wheels drawn at half-track   front 0.78   rear 0.74 m
```

and the positioner chain (already dumped in E64-S8, quoted in `rsfix`) places the **hub at
z = ±0.772 with scale 1.0**.

**So the wheels (0.74) and the suspension's own hub line (0.772) agree to 3 cm.** There is no ~18%
disagreement, and E75-S2's diagnosis was wrong. The narrowing probe that "looked better" was moving
the wheels *inboard of the hubs* — it improved the picture by breaking the alignment, which is
exactly the kind of result that flatters a wrong theory.

### What the measurement actually shows

The raw assemblies reach lateral **1.159 m**, well beyond the hub — because they are **authored flat
and horizontal** and `rsfix` folds them ~90° about the hub line (`JM_RS_ROLL`, default 90°). After
the fold, geometry that reached outboard points up/down *at the hub* — i.e. exactly where the tyre
is. That is why the highlight map in E75-S2 showed the linkage inside the tyre volume: it is folded
onto the wheel, by design.

The existing comment even records the symptom without naming it: *"50° vs 90° A/B'd near-identical
from the chase (tyres + gearbox occlude)"*. The authors observed the occlusion and read it as "the
angle doesn't matter", rather than as "whatever we do here is hidden".

### New hypothesis, and it is testable

Gold shows the linkage spanning **inboard** — hub → gearbox, visible in the gap between wheel and
tub. Native folds it **at** the hub, where the tyre hides it. If the fold pivot or axis is wrong,
the arms end up on the wheel instead of reaching across to the chassis.

**Next test:** sweep `JM_RS_ROLL` (0/45/90) and `JM_RS_Z0` (the fold pivot) and photograph each. The
question is whether any setting puts articulated linkage in the wheel-to-tub gap as gold has it. If
none does, the assemblies are being folded when they should be translated, and the fold itself is
the defect.

---

## E75-S4 — no fold setting works. The fold is not the tunable; the SOURCE geometry is wrong.

Swept `JM_RS_ROLL` and photographed each (`e75_roll_sweep.jpg`):

| setting | result |
|---|---|
| **0° (unfolded)** | the assemblies spray outward as flat **spears past the wheels** — this is the original E64-S4 "chrome spider-legs" artefact, reproduced |
| **45°** | nothing visible — indistinguishable from RSUSP off |
| **90° (shipped)** | nothing visible — indistinguishable from RSUSP off |
| RSUSP off | baseline |

**No setting produces gold's articulated rear end.** The choice is between an obvious artefact and
an invisible one; there is no angle in between that yields linkage spanning the wheel-to-tub gap.
So E75-S3's "the fold pivot may be wrong" is answered: the fold is not a tuning problem.

### The likely reason, and it reframes the whole item

The code calls these assemblies *"the runtime-hidden HIGH-DETAIL rear-suspension assemblies"* and
*"GPL runtime-hidden branches"*. If GPL hides them at runtime, then **the suspension visible in the
gold video is not this geometry at all** — gold must be drawing a different, always-visible set,
and JM has been trying to rehabilitate the wrong branch since E64-S4.

That would explain everything observed: why the assemblies are authored in a pose no fold makes
sense of, why 45° and 90° are indistinguishable from off, and why the one setting that shows them
(0°) produces spears no shipped game ever displayed.

### Next — and it is a different question from the last three sprints

Stop tuning the transform. Instead enumerate what the Lotus `.3do` actually contains: every group
and texture, which are excluded by `_LOTBLACK_EXC` / `_EXTRA_EXC` / `_GARBAGE_EXC` /
`exclude_groups`, and which carry wishbone/driveshaft-like geometry near the rear axle at
lateral < 0.8 m. **Gold's linkage has to be in there somewhere; the question is which exclusion is
eating it.**

---

## E75-S5 — the missing parts are NAMED; `maxlat` is not what drops them

Enumerated the Lotus `.3do` unfiltered (`JM_CARPARTS=1`). The suspension parts gold shows are all
present in the file and all **absent from the drawn car**, and — importantly — **none is excluded by
name**:

| texture | tris | lateral z | in CARP? | excluded by name? |
|---|---|---|---|---|
| `lshok` (shocks) | 48 | −1.06 … 1.06 | **NO** | no |
| `lsusp5` | 48 | −1.12 … 1.12 | **NO** | no |
| `lsusp7` | 48 | −1.01 … 1.01 | **NO** | no |
| `lsusp1` | 36 | −1.13 … 1.13 | **NO** | no |
| `lbrdisc` (brake discs) | 120 | −0.61 … 0.61 | **NO** | no |
| `frontlot` | 342 | −1.2 … 1.2 | **NO** | no |
| `axlelot` (axles) | 228 | −0.86 … 0.86 | yes | — |
| `lsusp2` | 60 | −1.02 … 1.02 | yes | — |

Since their lateral extent (±1.0–1.13) exceeds `CARP_MAXLAT = 0.85`, the obvious hypothesis was that
the skinny clip eats them.

**Refuted.** `JM_CARP_MAXLAT=1.2` produces a frame **indistinguishable from the shipped one**
(`e75_maxlat_ab.jpg`) — no new linkage, and no spider-legs either. So `maxlat` is not what removes
them. *(Fourth hypothesis refuted on this item; the previous three were wheels-too-wide, fold-pivot,
and fold-angle.)*

### What remains

By elimination the parts are dropped by **`exclude_groups=(6600, 3560, 27288, 39792)`** — the group
filter overrides `maxlat` entirely. And those are exactly the groups E75-S4 identified as GPL's
"runtime-hidden branches".

That closes the loop on this item's real question, and it is a single decidable one:

> Are `lshok`/`lsusp5`/`lsusp7`/`lbrdisc` **inside** the excluded groups — and if so, is gold
> drawing them (meaning the exclusion is the defect and the earlier "spider legs" were a transform
> bug), or does gold draw a different copy that JM never reaches?

### Next

Report each part's **group id** alongside its texture — one line added to the census. If the missing
suspension sits in 27288/39792, the exclusion is removing geometry gold displays, and the fix is to
include those groups with a corrected transform rather than to drop them. If it sits in 6600/3560,
those exclusions were justified by different evidence (E64-S4's "1.65 m-edge garbage 2 m ahead of
the car") and need re-examining on their own terms.

---

## E75-S6 — ⭐ the FRONT suspension is drawn NOWHERE, and the reason is self-defeating

Extracted each excluded group alone (`JM_CARGROUPS=1`):

| group | side | carries |
|---|---|---|
| **6600 / 3560** | front R / L | **`frontlot` (120 tris each), `lsusp1` (18 each)** — the FRONT suspension |
| **27288 / 39792** | rear L / R | `axlelot` 87, `lbrdisc` 60, `lsusp5` 24, `lsusp7` 24, `lshok` 24, `lsusp2` 24, `lid`, `pipe3` — the REAR end |

### The front suspension asks for geometry it also excludes

```julia
const FSUSPP = Render.extract_gpl_car(LOT3DO; only=("lsusp1",), maxlat=1.3f0,
                                      exclude_groups=(6600,3560,27288,39792))
```

`FSUSPP` wants **only** `lsusp1` — and excludes **every group that contains it**. The unfiltered
census puts all 36 `lsusp1` triangles in 6600+3560 (18 + 18). **So `FSUSPP` is empty and the front
suspension is drawn nowhere at all.** Same for `frontlot`: all 342 triangles live in the four
excluded groups, so none of it is ever drawn either.

The exclusion was added for a real reason — E64-S4 found *"group 6600 carries 1.65 m-edge lsusp1
garbage 2 m ahead of the car"* — but it was applied to the extractor whose entire purpose is to draw
that part. The guard outlived its bug and took the feature with it.

### So E75 splits cleanly into two different defects

| | geometry | why it is invisible | fix |
|---|---|---|---|
| **FRONT** | `lsusp1`, `frontlot` in 6600/3560 | `FSUSPP` excludes the only groups holding its own texture → empty | drop 6600/3560 from `FSUSPP`'s exclusion and re-clip the garbage by extent, not by group |
| **REAR** | `lshok`, `lbrdisc`, `lsusp5/7` in 27288/39792 | re-included as `RSUSPP_A/B` but folded onto the hub where the tyre hides it (E75-S4: no angle works) | needs the transform question settled separately |

The front case is the tractable one and is testable in a single run.

### Note on how long this took to see

Five sprints, four refuted hypotheses (wheels-too-wide, fold-pivot, fold-angle, maxlat). Every one
assumed the geometry was reaching the renderer and something downstream was mishandling it. The
actual answer — *most of it never reaches the renderer at all* — only became visible once the model
was enumerated instead of reasoned about. The census took one run.

---

## E75-S7 — ✅ front-end geometry now renders (partial fix), after two self-corrections

**Change:** `FSUSPP` no longer excludes the groups containing its own geometry. It clips the known
garbage by **extent** instead: `only=("lsusp1","frontlot"), maxedge=1.5`.
`maxedge` now applies to car meshes as well as track meshes (it was track-only; default `Inf`, so no
existing call changes). `JM_FSUSP_OLD=1` restores the empty-FSUSPP behaviour.

**Result:** 7,397 pixels change in the cockpit view (`e75_fsusp_fix.jpg`) — front-end structure
appears at both front corners where none was drawn before.

### Two corrections along the way, both from counting rather than looking

1. **My first clip was `maxedge=1.0`, which dropped ALL of `lsusp1`.** Measured survival:
   `0.5 → 0 tris, 1.0 → 0, 1.5 → 4, 2.0 → 12, Inf → 12`. The real wishbone strips have >1 m edges,
   so a 1.0 m clip is not "conservative", it is total. The A/B changed **0 pixels in both views**
   and I nearly recorded that as "the fix does nothing".
2. **`only=("lsusp1",)` was too narrow.** `frontlot` — 94–114 tris, the bulk of the front end — was
   *also* drawn nowhere, hit by the same self-defeating exclusion. It was missed because the search
   was for parts named like "suspension".

### ⚠️ Honest limits of this fix

- **`maxedge` is a blunt instrument here.** `lsusp1`'s real geometry and its garbage BOTH have long
  edges, so 1.5 separates them only approximately: 4 of 12 triangles survive, and whether the 8
  dropped are all garbage is **unverified**. The precise clip is longitudinal — E64-S4 located the
  garbage ~2 m ahead of the car — and wants a new extractor parameter that does not exist yet.
- **Not yet compared against gold.** The geometry renders; whether it *matches* the gold cockpit's
  front end is a separate check and has not been done.
- The REAR half of E75 (`lshok`, `lbrdisc`, `lsusp5/7` in groups 27288/39792, folded onto the hub)
  is untouched by this.

---

## E75-S8 — the rear suspension parts are authored UNFOLDED. One fold angle can never work.

E75-S7 fixed the FRONT end by taking its parts directly (`only=`, extent clip) instead of excluding
their group and re-placing them with a corrective transform. S8 applied the same recipe to the rear
(`lshok`, `lsusp5`, `lsusp7`, `lbrdisc`, no fold) — and it fails, for a reason worth having.

### What the pictures showed, and why that reading was wrong

Drawn raw, the rear parts appear as trusses and rods spreading outward past the wheels and down to
the road — visually identical to E75-S4's 0° fold failure. I read that as spear triangles surviving
a too-loose clip, and swept `JM_RSUSP2_MAXEDGE` 1.50 → 0.50 → 0.35:

| maxedge | pixels at the car | far tail | max radius |
|---|---|---|---|
| 1.50 | 8815 | 452 | 866 px |
| 0.50 | 1610 | 300 | 866 px |
| 0.35 |  896 | 300 | 866 px |

**The clip destroys the car geometry and leaves the tail untouched** — and a tail invariant to an edge
clip is not made of long edges. The spear reading was wrong. (The tail turned out to be capture
flicker in the treeline; see the noise-floor note below.)

### The measurement that settles it

`JM_RSUSP2_DIAG` prints the bbox and longest edge of exactly what is handed to the renderer:

```
   tex           tris   longitudinal x     lateral z          height y        longest edge
   lbrdisc       120    -1.04…-0.73        -0.61…0.61         -0.12…0.18      0.43
   lsusp7         48    -1.66…-0.77        -1.01…1.01         -0.08…-0.05     1.00
   lshok          48    -1.74…-0.75        -1.06…1.06         -0.10…0.21      1.14
   lsusp5         48    -1.09…-0.77        -1.12…1.12         -0.07…0.23      0.72
```

Every part is compact, at the rear (x negative), at hub height, within the track width. **No edge
exceeds 1.14 m — nothing here can reach the road.** The parts render precisely where the mesh puts
them. The mesh is what is wrong.

⭐ **Look at `lsusp7`: y spans 0.03 m while z spans 2.02 m.** A flat sheet, three centimetres thick,
as wide as the whole car. `lsusp5` is the same shape. Real wishbones and shocks are nothing like
this — **these parts are stored UNFOLDED**, flat strips meant to be articulated into position at
load. That is what `rsfix`/the fold was always for.

### Why E75-S4 could not have succeeded

E75-S4 swept fold angles and found 0° spears while 45°/90° vanish, and concluded "no angle works".
The truer statement: **four parts with four different pivots cannot be articulated by one global
angle.** S4 was not searching a badly-chosen parameter; it was searching a parameter that cannot
express the answer. A correct fix folds each part about its own hinge — which means recovering the
hinge, not tuning a number.

`JM_RSUSP2` is therefore **default OFF** (it lays panels under the car). The code and the diagnostic
stay: the measurement is what identified the authoring, and the next attempt needs it.

### ⚠️ Cross-cutting: this capture harness has a ~0.4% noise floor

The A/B started as "1.02% of the frame changed". A null control — **two runs with identical
settings** — differs by **0.30%**, and a three-baseline mask marks **0.38%** of pixels as unstable,
concentrated in treeline/sky alpha edges. So:

- **Any A/B result under ~1% of frame is at or near the noise floor** and means nothing without a
  null control. Several earlier findings this run were far above it (E73-S6's 14.6%) and are safe,
  but the threshold had never been measured.
- **Diff bounding boxes are worthless without denoising** — the raw bbox here was the entire frame.
- A three-baseline mask is still too weak for sparse flicker: 39% of the surviving "tail" was not
  reproducible between arms.

**Every future pixel A/B on this project runs a null control first.** Cheap, and it converts a
percentage from a rumour into a measurement.

---

## E75-S9 — ⚠️ RETRACTION of S8's "authored unfolded"; and the Ring gap was never a timeout

### 1. The rear suspension is NOT stored unfolded

E75-S8 concluded the rear parts are "flat strips meant to be articulated at load", from this:

```
lsusp7   x -1.66…-0.77   z -1.01…1.01   y -0.08…-0.05     → 0.03 m thick, 2.02 m wide
```

**That is two parts, one per side, measured as one.** S8 selected by TEXTURE, which gathers the left
and right instances into a single bounding box — so the z-span is the whole car's width and the
y-span is the union of two thin objects. Extracted **by group** the same parts are ordinary 3-D
geometry:

| part | size (x×y×z) | |
|---|---|---|
| `axlelot` | 1.04 × 0.30 × 0.44 | the axle |
| `lshok` | 0.99 × 0.31 × 0.57 | **3-D**, not a strip |
| `lsusp5` | 0.32 × 0.30 × 0.69 | **3-D** |
| `lsusp7` | 0.89 × 0.03 × 0.48 | flat — but one brace, 0.89 m, not 2.02 |
| `lbrdisc` | 0.31 × 0.31 × 0.03 | flat, and correctly so — it is a brake **disc** |

So the "unfolded strip" theory is dead, and with it S8's claim that four parts need four hinges.

### 2. But the render still contradicts the geometry — stated, not explained

`JM_RS_ROLL=0` (identity, no fold) still spears the rear end well past the wheels, exactly as
E75-S4 found. Yet:

- **all 17 parts** in each rear group are ≤ 1.04 m in every axis (sorted by SIZE, not triangle count —
  the old top-10-by-count listing hid nothing large, but neither did the full list);
- the drawn mesh spans **|z| ≤ 1.16 m** against wheels drawn at 0.74 m half-track.

Nothing here can reach metres past the wheels, and yet the picture does. **I have not resolved that
conflict**, and the shipped 90° fold "works" only by rotating the parts out of sight. The next step is
to measure the post-transform vertex extent of what is actually submitted to the draw call, rather
than of what the extractor returns.

### 3. ⭐ The Nürburgring census gap was NOT a timeout — I said so twice, wrongly

E71-S13 and E69-S6 both recorded the Ring as *"not measured — load + census exceeds the run window"*.
Both were wrong. The three road censuses lived **inside the GPL-object branch** (`if SKIDPAD || NURB …
else <censuses> end`), so on the Nürburgring they never executed at all. The run exited **cleanly with
no output**, and I read that absence as a timeout instead of as an unreachable block — twice, without
checking the exit code against the hypothesis.

**E70-S2 had already found and fixed this exact class** for the on-road censuses ("censuses were
UNREACHABLE here (inside the GPL objects block) — relocated so they run on every track"). These three
were missed by that sweep. A known trap, re-encountered, and misdiagnosed twice as a resource limit.

Hoisted to top level — and each wrapped in its own `let`, because at top level their loop variables
(`px`, `py`, `b`, `nrt`) **shadow existing globals**, which silently produced **zero stations**. That
was caught only because Monza's known 24/24 became 0/0: a regression check against a previously
measured value, not a fresh number that would have looked plausible.

### 4. Result — every track now reports, and the Ring is the best of them

| track | recognition | verdict | coverage width |
|---|---|---|---|
| **Nürburgring** | **88.2 %** | sound (`shrub_s`, `armco_s` — both median \|lat\| 4.9 m, the edge-band artifact) | **9.5 m, 23/23 stations** |
| Monza | 86.2 % | sound | 12.2 m, 24/24 |
| Watkins | 86.1 % | sound | 11.2 m |
| Spa | 77.7 % | 4 edge-band suspects, rejected | 8.8 m, 57/57 |
| Zandvoort | 73.6 % | sound | — |

⭐ The Ring's 9.5 m is **remarkably uniform** — 20 of 23 stations read exactly 9.5 m — and it
independently corroborates E76-S8: that sprint chose a **5.0 m** half-width for the Ring's on-road
sprite cull from the sprite lateral distribution alone, and half of the measured road is **4.75 m**.
Two unrelated measurements, one derived from vegetation placement and one from road triangles,
agreeing to a quarter of a metre.

---

## E75-S10 — the Lotus paint: hue is RIGHT, but it renders too dark and over-saturated

The PO's E75 asks for *"correct external lotus 49 views per the gold standard"*, and colour is half of
that. Unlike track surfaces, **the car is the same object everywhere**, so its paint can be compared
without pinning location — the trap that invalidated E69-S4 and E69-S7's grass measurement.

### The measurement

Body green, median over the car's engine cover:

| | frames | body green | span (max−min) |
|---|---|---|---|
| **gold** (Spa + Monza + Watkins nintendo) | 6 | **(52, 82, 63)** | **30** |
| native (Spa, dappled shade) | 3 | (36, 79, 48) | 43 |
| native (Monza, open sunlight) | 3 | (37, 76, 49) | 39 |

⭐ **The hue is correct.** British racing green's characteristic blue-green cast shows as B above R by
11 in gold and 12 in native. What differs is *tone*: native is **~17 % darker** and **~35 % more
saturated**.

### Three explanations eliminated

1. **Contamination.** The first pass used a box that swallowed roadside grass — native's "green" counts
   were 5–15 k against gold's 400–1300, and the medians were dune-coloured. Tightened to the engine
   cover and **verified by dumping the mask over the frame**: magenta sits exactly on the bodywork.
2. **Shadow / lighting conditions.** The Spa captures sit under dappled tree shadow, an obvious
   confound. Re-measured on Monza's open sunlit straight: **(37, 76, 49) vs (36, 79, 48)** — the same.
   Location and lighting do not explain it.
3. **The saturation grade.** `JM_SAT` 1.12 → 1.00 moves the span only 38 → 35, about 3 of the ~13
   excess. Not the cause.

### Where it must come from

`JM_TEXCOLOR` shows the source textures are **less** saturated than our render, not more:

| texture | mean RGB | span |
|---|---|---|
| `vlot67e` | (63, 85, 71) | 22 |
| `vlot67a` | (77, 90, 72) | 18 |
| `vlot67d` | (35, 50, 40) | 15 |
| `vlot67b` | (97, 109, 80) | 29 |

So **our shading adds saturation**: a texture at span 22 renders at 39–43, where gold renders the same
texture at 30. Gold expands it too — just half as much. The car draws with `bright=1.2, ambfill=0.78`,
which should *lighten* it, so the remaining candidate is the **contrast shape** of the lighting model —
the `pow(lit, 0.94)` gamma and the sun-to-ambient ratio, which together stretch dark channels away
from the light one.

Not tuned here. E69-S8's white balance earned its place by surviving three eliminations and
cross-validating on tracks it was not fitted to; this one has had three eliminations but no candidate
confirmed yet, and a brightness constant applied now would be exactly the E74-S7 mistake.

---

## E75-S12 — ⭐ the shipped rear-suspension transform buries it 1.2–1.9 m UNDERGROUND

E75-S4 concluded "no fold angle works — 0° spears past the wheels, 45/90° invisible", and E75-S8/S9
argued about unfolded strips and spear triangles. S12 measures what the transform actually does.

### The measurement (`JM_RSUSP_WORLD`)

Bounding box of the rear-suspension parts before and after `RSFIX`, in car space. `bodyModel` is rigid
and cannot stretch anything, so this is the whole story:

| | x | y | z | span |
|---|---|---|---|---|
| `RSUSPP_A` raw | −2.50…−0.73 | **−0.15…0.25** | −1.12…−0.42 | 1.77 m |
| `RSUSPP_A` × `RSFIX_A` (**shipped, roll=90**) | −2.50…−0.73 | **−1.87…−1.17** | 0.54…0.94 | 1.77 m |
| `RSUSPP_A` × `RSFIX_A` (roll=0) | −2.50…−0.73 | −0.15…0.25 | −1.12…−0.42 | 1.77 m |

⭐ **The shipped transform moves the rear suspension to 1.2–1.9 m BELOW the car's origin — underground.**
That is why E75-S4 found 45°/90° "invisible": not occlusion, **burial**. Eight sprints described the
symptom; the cause is one line of the transform.

### Two of my own readings retired

- **"Spears past the wheels" (E75-S4, repeated in S9) is wrong.** The span is **1.77 m at every roll
  angle** — nothing is stretched — and 97.5 % of the pixels the rear-suspension draw adds lie within
  ±30 % of frame width of centre. The far tail is 0.07 % of frame: noise I failed to denoise, exactly
  the mistake E75-S8 established a rule against and I made again.
- **"Authored unfolded" (E75-S8) was already retired in S9**; S12 confirms the parts are ordinary
  compact geometry sitting at hub height once the burial is undone.

### But roll=0 still does not match gold

Gold's Lotus shows **slender wishbones and radius arms contained within the wheel track**. Native at
roll=0 shows **broad specular chrome PANELS** extending toward the wheels. So the fold angle was never
the real question — the parts are in roughly the right place and the wrong *shape*.

**One hypothesis tested and eliminated:** the flat braces `lsusp2` (0.76 × 0.03 × 0.50) and `lsusp7`
(0.89 × 0.03 × 0.48) are thin enough to render as plates under `spec=0.25`. Excluding both changes the
render **almost not at all**, so they are not the panels. Default restored to keeping them
(`JM_RS_NOFLAT=1` drops them for further A/B) — an unjustified exclusion is worse than none.

### Where this leaves E75

The framing changes from *"find the right fold angle"* (eight sprints, no progress) to *"the transform
buries the assembly, and some rear-group part renders as a broad panel"*. The next step is mechanical:
draw the rear group **one part at a time** and identify which produces the panels — `axlelot`, `lid`,
`top` and `rear` are the untested candidates.

---

## E75-S13 — three more causes eliminated; and a 25 % null control in chase view

S12 re-framed E75 to "some rear-group part renders as a broad panel". S13 tries to name it.

### ⚠️ The part-by-part pixel comparison is not viable on this harness

Restricting the rear suspension to one part at a time (`JM_RS_ONLY`, new) and diffing against the
buried-suspension baseline gave **24.7 % and 25.5 % of frame** for `axlelot` and `lid` — against the
**2.78 %** the entire rear suspension contributes. Impossible, and the reason is familiar: **in chase
view the car fills much of the frame, and two runs do not reproduce its position**, so the null control
here is ~25 %, not the ~0.4 % measured for static cockpit captures.

E69-S5 established that a pixel A/B needs a small null *and* a visible change. **In chase view the null
is an order of magnitude larger than the signal**, so no amount of care makes this particular
comparison work. Geometry, not pixels, has to answer it.

### The geometry says the extraction is right

`JM_RSUSP_WORLD` with `JM_RS_ONLY`:

| part | x | y | z | span |
|---|---|---|---|---|
| `axlelot` | −1.80…−0.77 | −0.08…0.23 | ∓0.42…0.86 | **1.04 m** |
| `lid` | −1.73…−0.78 | −0.08…0.23 | ∓0.44…1.01 | **0.95 m** |

Correct sides, hub height, compact. `only=` and `include_groups` compose correctly — worth knowing,
since E75-S8's failure came from `only=` used *without* a group and silently merging both sides.

### Causes eliminated this sprint

| candidate | test | verdict |
|---|---|---|
| oversized geometry | bbox of every rear part | **eliminated** — all ≤ 1.04 m (S9, S12, S13) |
| flat braces as plates | exclude `lsusp2`/`lsusp7` | **eliminated** — render barely changes (S12) |
| specular sheen | `JM_RS_SPEC` 0.25 → 0 | **eliminated** — render barely changes |

### What is left

The parts are ~1 m, correctly placed, and not a shading artifact — so the "broad chrome panels" simply
**are** those parts at chase-camera scale. `lid` and `axlelot` are a gearbox cover and an axle housing:
solid bodies. Gold's rear end shows **slender wishbones and radius arms** and no such covers at this
size.

So the remaining question is not size, placement or material but **which parts gold draws, and at what
level of detail** — quite possibly a LOD question, given E70-S4 found the LOD selector following null
children elsewhere in this same model. That is the next thread, and it is a different kind of question
from the one E75 has been asking for thirteen sprints.

---

## E75-S14 — the panels ARE the suspension, the LOD choice is right, and the assembly sits OUTSIDE the wheels

### A regression check I owed and had not done

E70-S4 changed LOD child selection (skip null children) and I verified it against **track** object
counts only. The Lotus is the same `.3do` machinery. Checked now: with the fix on and off, the car is
**identical** — 12 Lotus body parts, `RSUSPP_A/B` bboxes unchanged to 2 decimal places. **No car
regression from E70-S4.**

### The LOD selection is correct

E64-S4 assumed the smallest range threshold is the closest-range, highest-detail child. `JM_LOD_PICK=max`
(new) tests the opposite: it yields **2 Lotus body parts instead of 12** and an **empty** rear
suspension. Minimum is right; hypothesis eliminated.

### The panels are the suspension — confirmed by removal, not by eye

Given how often a visual reading has misled me here (spears twice, canopy, "missing" crowds), I tested
it by removal rather than inspection:

| arm | result |
|---|---|
| `JM_RSUSP=0` (suspension off) | **no panels** — clean rear end |
| roll=0 | **panels present** |
| roll=90 (shipped) | no panels — buried (S12) |

So the broad chrome structures are genuinely the rear-suspension geometry.

### ⭐ And the measurement now agrees with the picture

The assembly reaches **|z| = 1.16 m**. The drawn rear tyre is centred at 0.74 m (half-track) and is
~0.3 m wide, so its outer face sits at ≈0.89 m. **The suspension therefore protrudes ~0.27 m beyond
the outside of the wheel** — which is exactly what the render shows, and exactly what gold does not:
gold's wishbones and radius arms run *inside* the wheel track.

For scale, |z| = 1.16 m implies a **2.3 m track**, against a real Lotus 49's ~1.5 m. So the outermost
rear parts are ~0.4 m further out than the car's own hub line (0.772 m, E75-S3).

### Where E75 stands after fourteen sprints

Established: the shipped transform **buries** the assembly (S12); the parts are compact and correctly
extracted (S9, S13); size, flat braces, specular and LOD are all **eliminated** as causes; and the
assembly **protrudes outside the wheels** where gold keeps it inside.

The open question is now specific: **which rear parts legitimately extend to 1.16 m, and should they be
there at all?** `lid` (0.95 m) and `axlelot` (1.04 m) are a gearbox cover and axle housing — plausibly
internal parts that gold never shows at this scale. That is a content question about the part list, not
a transform, a material, or a level of detail, and it is the first time this item has had one.

---

## E75-S15: it is not a content question. The FRONT does the same thing.

The enumeration S14 asked for, taken straight from the `.3do` with no run and no capture — all 17 parts
of group 27288, per side, sorted by outer lateral bound:

| | outer | inner | | | outer | inner |
|---|---|---|---|---|---|---|
| `lsusp5` | 1.117 | 0.43 | | `lid` | 1.006 | 0.44 |
| `arms` | 1.113 | 0.44 | | `lsusp7` | 1.006 | 0.53 |
| `top` | 1.113 | 0.44 | | `lexhsup` | 1.006 | 0.84 |
| `pipe3` | 1.099 | 0.99 | | *(untextured)* | 0.913 | 0.43 |
| `lshok` | 1.062 | 0.49 | | `axlelot` | 0.860 | 0.42 |
| `lsusp4` | 1.061 | 0.84 | | `lbrdisc` | 0.610 | 0.58 |
| `lsusp3` | 1.030 | 0.43 | | `frontlot` | 0.603 | 0.54 |
| `lsusp2` | 1.023 | 0.52 | | `lsusp6` | 0.542 | 0.52 |
| `rear` | 1.023 | 0.53 | | | | |

**14 of 17 parts sit outboard of the hub line (0.772 m)** — not one or two. `lid` and `axlelot`, the
two S14 nominated, are not even the worst: `axlelot` at 0.860 is among the *innermost* of the
offenders. Picking a couple of suspicious names out of a list where four-fifths of the entries are
equally suspicious would have removed some geometry and left the assembly still protruding.

### The measurement that decides it

The FRONT assembly — the one **E75-S7 shipped**, with "gold comparison pending" — reaches
**|z| = 1.121** via `lsusp1` (0.590 … 1.130 per side). The rear's worst is **1.117**.

**The two assemblies share an outer bound to within 13 mm.** A content error in the rear part list
cannot explain the front landing on the same number from a different set of parts. One systematic
placement does.

Their *spans* are unremarkable — 0.54 m front, 0.69 m rear, about right for a suspension link
reaching from a chassis pickup to an upright. It is where those spans sit that is wrong: they start
at 0.43–0.59 (a rear inner pickup belongs nearer 0.15) and end 0.25–0.35 m outboard of the hub.
**The geometry is the right size in the wrong place**, front and rear alike.

### Corroboration: the parts are near-planar, as unfolded strips would be

Vertical extents over the whole car, per texture:

| `lsusp2` | `lsusp1` | `lsusp5` | `lshok` | `lid` | `axlelot` |
|---|---|---|---|---|---|
| **0.07 m** | 0.16 m | 0.30 m | 0.31 m | 0.31 m | 0.40 m |

A real shock absorber is ~0.3 m tall and an upright ~0.4 m; `lsusp2` at **7 cm** is a sheet. This is
the unfolded-strip authoring E75-S4 already identified from the fold experiments, now visible
directly in the vertex data, and it is why "which parts belong" was never going to be the question.

### One reading corrected in passing

E64-S4 describes `lsusp1` as "garbage 2 m ahead of the car", and its raw x range is 1.54 … 3.19.
But `frontlot`, the front bodywork, runs to **x = 3.09**, and the whole car spans −2.52 … 3.19 — so
x ≈ 3.1 *is* the nose. `lsusp1` sits inside the front section, not ahead of it; the "2 m ahead" was
measured against a different origin. That matters because `JM_FSUSP_MAXEDGE` was tuned to clip by
edge length on the belief that it was separating near-car geometry from distant garbage, and all 12
`lsusp1` triangles occupy the same place.

### Next step

Test one lateral correction against both assemblies at once, rather than editing either part list:
a single inboard shift of ~0.30 m puts the front at 0.29 … 0.83 and the rear at 0.13 … 0.82 — inner
pickups near the gearbox, outer ends just inside the 0.89 m wheel face, which is where gold keeps
them. If one number fixes both ends of the car, the placement reading is confirmed; if it fixes one
and breaks the other, it is refuted, and that is worth knowing before any part is deleted.
