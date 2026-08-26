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
