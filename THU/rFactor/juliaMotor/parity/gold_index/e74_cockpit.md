# E74 — cockpit gold parity ("the dials look like a Salvador Dali painting")

Oracle: the five gold **cockpit** lap videos. All five are cockpit view, so every track's video is
evidence for this item — it has more independent oracles than any other backlog entry.
Pairs below are Spa, `260802_spa_cockpit.mp4`, at s=500/3000 (t = s/14099 × 388).

Composites: `e74_cockpit_ab.jpg`, `e74_dash_ab.jpg`, `e74_badge_ab.jpg`.

## ⭐ D1 — the Lotus wheel badge is ROTATED 180°

Gold: green roundel, leaf pointing **up**, "LOTUS" reading left-to-right along the bottom.
Native: leaf pointing **down**, "LOTUS" **upside-down**.

Crisp, specific and independent of the rest — a texture-orientation or UV flip on the boss face.
This is the most actionable thing in E74 and does not depend on any of the findings below.

## D2 — the gauge faces are washed out and illegible

Gold: black-faced instruments, white numerals, **red needles**, a large central tachometer flanked
by two gauges left and three right — all readable.
Native: pale, low-contrast ghosts. No needle is discernible; the numerals are a smear. This is what
reads as "melted" — the faces are present as geometry but their texture is not resolving.

Candidates, untested: wrong mip/LOD on a small high-frequency texture; the dash lit to near-white so
the black face washes out; or the gauge texture failing to bind (cf. the `glTex=0` class seen in BoB
this week). **Not yet diagnosed — do not guess between these.**

## D3 — the steering wheel is oversized and its spokes are fragmented

Gold: slim red rim, three polished spokes, continuous.
Native: the rim reads as **disconnected red blocks**, the spokes as **large chrome slabs/shards**,
and the whole wheel is much larger in frame than gold's.

## D4 — camera/FOV differs

The native cockpit sits closer and lower: the dash slab fills far more of the frame and the horizon
sits higher. Some of D2/D3's severity may be D4 magnifying them, so **fix D4 before judging D2/D3's
scale** — otherwise a correct wheel could be "fixed" to compensate for a camera error.

## Not yet examined

Prior known items to fold in: E68-W4 (bottom half of the dash occluded by a green block) and
E68-W3 (sleeves not meeting gloves); the driverless footwell and tub-side gap recorded in STATUS.md.

---

## E74-S2 — ✅ D1 FIXED: the Lotus badge is upright and legible

**First actual repair in this batch** (everything before it was diagnosis).

Cause: `extract_gpl_steering` (render.jl:1059) V-flipped the UVs of **every** steering texture
alike — `append!(v, (…, uv[1], 1f0-uv[2]))`. That is harmless for `sterlot`, the plain red wheel
face, which has no readable orientation. Only `lsterlog`, the badge, exposes it.

Fixing it took **two** steps, and the intermediate result is the interesting part:

1. **Un-flip V for the badge only.** The leaf came upright, matching gold — but the lettering was
   still mirrored left-to-right. So the badge was transposed in *both* axes, not one. Had I stopped
   at the first improvement, the leaf would have looked right and the word would still have been
   wrong: a half-fix that photographs well.
2. **Flip U as well.** Badge now reads `LOTUS` left-to-right under an upright leaf — matches gold.

`JM_BADGE_VFLIP=1` restores the old behaviour for A/B.

Composites: `e74_badge_fix_steps.jpg` (gold | before | V-only), `e74_badge_fixed.jpg` (gold | fixed).

**Scope note:** this fixes the badge alone. D2 (washed-out gauge faces), D3 (oversized wheel,
fragmented spokes) and D4 (camera/FOV) are untouched, and D4 should still be settled before
judging D3's scale.

---

## E74-S3 — D2: brightness is NOT the cause; the gauges are MINIFIED

Swept the dash lighting against gold (`e74_dash_sweep.jpg`): shipped `1.2/0.9`, `0.9/0.45`,
`0.7/0.2`.

**Refuted.** Darkening does not make the dials legible — at every setting they remain the same pale
circular outlines with a faint grid where numerals should be. The E62 note that raised these values
("1.0/0.60 left ours dim — lift fill so the dial faces are legible") was treating a symptom that
brightness cannot reach.

### What the comparison actually shows

Gold's cockpit puts a **large, dominant tachometer** just above the wheel hub — white face, black
bezel, red needle, numerals readable. Native's dials are **small and set far back**, behind a wheel
that fills the frame.

So the likely cause of "melted" is **minification**: the gauge cluster is drawn small enough that
its dial-face texture collapses into a mip-blurred smear. That is consistent with everything seen —
the faces are *present* (the circular rims and a grid of markings resolve), just too few pixels
across to read.

**This folds D2 into D4.** The camera/FOV difference is not merely magnifying a separate gauge
problem; it may *be* the gauge problem. E74-S1 already warned that D4 should be settled before
judging D2 and D3 — that ordering now looks essential rather than cautious.

### Incidental confirmation

The **badge fix from E74-S2 is visibly holding** in all three arms: `LOTUS` reads left-to-right
under an upright leaf. A fix from an earlier sprint surviving unrelated later runs is worth noting.

### Next

Test minification directly: grow the gauge cluster (or bring it toward the eye) and see whether the
numerals resolve. If they do, D2 is not a texture or lighting defect at all and the fix is
positional. `JM_GAUGE_X`/`JM_GAUGE_Y` exist for position; there is **no scale knob**, so one may
need adding to test it.

---

## E74-S4 — the minification test FAILED to isolate, and revealed a positional error instead

Added `JM_GAUGE_S` (default 1.0, shipped look untouched) and swept 1.0 / 1.8 / 2.6.

**The test does not work.** Growing the cluster makes the dials *disappear*, not enlarge: at 1.8 they
are mostly gone, at 2.6 entirely. The scale is applied about the cluster's own centre inside
`GAUGEFLIP`, so it **displaces** the dials as well as magnifying them — they move out of the visible
window behind the wheel. Magnification and movement are confounded, so **the minification hypothesis
from E74-S3 is neither confirmed nor refuted.** The knob stays (default 1.0) but a proper test needs
scale about the *eye direction*, or scale plus a compensating translation.

### What the sweep did show: the cluster is in the wrong PLACE

Comparing scale 1.0 with gold:

- **Gold:** the tachometer sits **directly above the wheel hub**, centred on the driver's eye line,
  large and unobstructed.
- **Native:** the dials sit **up and to the LEFT**, partly cut off at the frame edge, with the wheel
  rim across them.

So the cluster is offset from where gold puts it. That is a different defect from "too small", and it
may account for much of the "melted" impression on its own — a dial half-hidden behind a spoke and
clipped at the edge reads as a smear regardless of its texture.

`JM_GAUGE_X` (−0.04) and `JM_GAUGE_Y` (+0.16) already exist to position it, and their comment says
they were set to lift the mesh-low dash "onto the cowl". **Nobody appears to have checked the lateral
placement against gold.**

### Next

Sweep `JM_GAUGE_X` against gold's dial position — cheap, existing knob, no new code. Only once the
cluster is where gold puts it does the "are the faces legible" question become answerable, because
until then legibility is confounded by occlusion and clipping.

---

## E74-S5 — the missing axis: added `JM_GAUGE_Z`, and the fix needs TWO axes not one

There was no lateral control at all. `JM_GAUGE_X` is longitudinal (its own comment: *"nudge it back
toward the eye"*), `JM_GAUGE_Y` is height, and the third component was a hard `0`. **The axis E74-S4
identified as wrong was the one nobody could adjust** — which is a good reason it stayed wrong.

Added `JM_GAUGE_Z` (default 0.0, shipped behaviour unchanged) and swept 0.0 / 0.10 / 0.20
(`e74_gauge_z.jpg`):

| z | result |
|---|---|
| 0.00 | dials far left, partly clipped at the frame edge |
| 0.10 | dials nearer centre, **markedly more visible — dial faces and markings resolve** |
| 0.20 | dials centred but now **behind the wheel spokes and rim** |

### What this establishes

1. **Occlusion and clipping are a large part of the "melted" impression.** At z=0.10 the faces
   resolve visibly better with no change to texture, lighting or scale — supporting E74-S4's reading
   over E74-S3's minification theory, though not settling it.
2. **One axis is not enough.** Gold puts the tachometer **above the wheel rim**, clear of the spokes.
   Native's cluster sits at rim height, so moving it inboard just trades a clipped dial for an
   occluded one. The cluster needs to go **right AND up** together.

### Next

Sweep `JM_GAUGE_Z` × `JM_GAUGE_Y` as a small grid against gold, and pick the pair that puts the dial
above the rim and centred on the hub as gold has it. Both knobs now exist, so this is a photograph
exercise with no new code.

⚠️ Default unchanged pending that sweep. A knob that improves one frame is not yet a value worth
shipping — and this cockpit already carries one setting (the E62 brightness lift) that was chosen to
fix a symptom whose real cause was elsewhere.

---

## E74-S6 — the two-axis sweep lands it: `JM_GAUGE_Z=0.10 JM_GAUGE_Y=0.28`

| setting | result |
|---|---|
| z=0.10, y=0.16 (shipped height) | dials hidden behind the wheel rim and scuttle |
| **z=0.10, y=0.28** | ⭐ **cluster sits ABOVE the rim, several dial faces and their markings clearly visible** — the gold arrangement |
| z=0.12, y=0.38 | too high; cluster leaves the visible dash |

Gold puts a large tachometer above the wheel hub with smaller gauges either side. At **z=0.10,
y=0.28** the native cockpit shows exactly that arrangement for the first time: a row of readable
dials above the rim rather than a pale smear at the frame edge.

### What this means for the PO's report

The *"dials look like a Salvador Dali painting"* is, to a large degree, **a placement defect**. The
cluster was sitting at rim height and to one side, so it was clipped at the frame edge and occluded
by the spokes — which reads as melted no matter how good the texture is. Three earlier candidates
(texture binding, mip/LOD, dash lighting) are not needed to explain it.

### ⚠️ NOT shipped as the default yet, and why

1. **One viewpoint, one track.** Tested at Spa s=3000 only. A cockpit placement must hold at other
   lapdists and on other cars/tracks before it becomes the default.
2. **Size is still unverified.** Gold's tachometer is visibly larger relative to the wheel than
   ours even at the corrected position. That may be the E74-S3 minification question resurfacing —
   and `JM_GAUGE_S` cannot test it cleanly (E74-S4: scaling displaces).
3. This cockpit already carries one setting chosen to fix a symptom whose cause lay elsewhere
   (the E62 brightness lift). **Adding a second tuned constant before the geometry is understood is
   how that happened.**

### Next

Re-shoot z=0.10/y=0.28 at two more lapdists and in a second cockpit context; if it holds, flip the
defaults and re-check the dial SIZE against gold as a separate question.

---

## E74-S7 — ✅ SHIPPED: gauge placement corrected (`JM_GAUGE_Y` 0.16 → 0.28, `JM_GAUGE_Z` 0.0 → 0.10)

Verified before flipping the defaults, at **four viewpoints across two tracks** —
Spa s=500 / 8000 / 12500 and Zandvoort s=1000 (`e74_gauge_verify.jpg`). In every one the cluster
sits above the wheel rim with a row of dial faces and their markings legible. The placement is a
car-space transform, so track-independence was expected; confirming it cost one extra run and would
have caught the opposite.

`JM_GAUGE_Y=0.16 JM_GAUGE_Z=0.0` restores the previous placement.

**Third fix shipped in this batch**, after the badge orientation (E74-S2) and the front-end geometry
(E75-S7).

### What is fixed and what is not

**Fixed:** the dials are no longer clipped at the frame edge or cut through by the spokes. The
PO's "Salvador Dali" description was, in large part, a description of *occlusion* — and no amount of
texture or lighting work would have addressed it.

**Not fixed — and deliberately left open:**
- **Dial size.** Gold's tachometer is still visibly larger relative to the wheel than ours. This is
  E74-S3's minification question, and `JM_GAUGE_S` cannot test it cleanly because scaling also
  displaces (E74-S4). It needs scale-about-the-eye, or scale plus compensating translation.
- **D3 (wheel oversized, spokes fragmented)** and **D4 (camera/FOV)** are untouched. D4 in particular
  may still be shifting everything; the gauge fix compensates for its effect on one part only.

⚠️ Which means this fix carries the same risk as the E62 brightness lift it partly supersedes: **a
constant tuned to make one thing look right while an underlying geometry error remains.** Recorded
here so that when D4 is settled, this value is re-derived rather than inherited.
