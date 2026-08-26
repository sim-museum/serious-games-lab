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
