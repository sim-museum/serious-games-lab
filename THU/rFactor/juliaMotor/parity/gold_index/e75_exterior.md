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
