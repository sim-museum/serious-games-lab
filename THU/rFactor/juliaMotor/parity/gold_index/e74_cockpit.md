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

---

## E74-S8 — ⭐ D4 MEASURED: the cockpit eye point is wrong, and the shipped gauge constants sit downstream of it

E74-S7 shipped `JM_GAUGE_Y` 0.16→0.28 with an explicit warning: *"a constant tuned to make one thing
look right while an underlying geometry error remains… when D4 is settled, this value is re-derived
rather than inherited."* S8 settles enough of D4 to say that warning was justified.

### Method

Extracted the gold Monza cockpit video (`260802_monza_cockpit.mp4`, 1920×1080/60), located the game
viewport inside the wine desktop (x 0–1279, scene rows 143–954 → **1280×812**), and captured native
Monza cockpit (view **0**, not view 1) at the same straight. Two car-space measurements were used
because they are **independent of FOV and frame size**:

- **wheel size** = red rim width as a fraction of frame width;
- **foreshortening** = hub (Lotus badge) drop below rim top, in rim widths. A wheel seen face-on gives
  ≈0.5; one seen from above is squashed below that.

Both detectors were **rendered as masks and checked by eye** before any number was used — the first
two attempts were contaminated (gold's "rim" spanned the full frame width, catching red kerbs and the
driver's striped sleeves; native's "badge" landed on the tan bodywork at x=1380).

### Result

| | gold | native (shipped) |
|---|---|---|
| wheel rim width | **0.559** of frame width | **0.273** |
| hub drop below rim top | **0.254** rim widths | **0.473** |

⭐ **Native renders the steering wheel almost perfectly face-on and at half gold's apparent size.**
Gold's driver sits high and *looks down* on a foreshortened wheel, seeing the road over the cowl.
Native's eye is low and far back: the wheel reads as a flat circle and **the dash slab blocks the
centre of the view**, floating high with a gap between it and the wheel.

### The knobs, and what each does

| knob | effect (measured) |
|---|---|
| `JM_EYE_Y` (0.40) | 0.50 drops the cockpit in frame and **opens up the road much as gold shows it**; 0.58/0.66 overshoot. Does **not** change wheel size (0.273→0.271). |
| `JM_EYE_X` (0.46) | Drives apparent wheel size hard: 0.20→**0.149**, 0.46→**0.273**, 0.70→**eye past the wheel entirely** (dash and wheel vanish). |

So the size error is **eye-to-wheel distance, not FOV** — a pure FOV error would shrink the world
equally, and the world does not move with `JM_EYE_X`. Gold's 0.559 lies between `EYE_X` 0.46 and 0.70.
(Aspect differs — gold 1.576, native 1.778 — which accounts for ~13 % horizontally, not a factor of 2.)

### ⚠️ Consequence for what is already shipped

**The E74-S7 gauge constants were fitted against a camera that is itself wrong.** Gold puts the dial
cluster *below* the rim top — you read the dials **through the top arc of the wheel**. Native now puts
them *above* the rim top, floating clear of it. The S7 fix made the dials legible by moving them
**away from gold's placement**, compensating for the low eye. When the camera is corrected,
`JM_GAUGE_Y`/`JM_GAUGE_Z` must be **re-derived from zero, not adjusted**.

### ⚠️ No camera constants shipped — the fit instrument is not sound

A 2-D probe of (`EYE_X`,`EYE_Y`) returned **foreshortening = −0.287** at (0.55, 0.44): the hub *above*
the rim top, which is geometrically impossible. The rim-top percentile picks up other red pixels
(sleeves, a lower rim arc) once the pose changes, so the metric is only valid for the two frames whose
masks were verified. **Fitting two camera constants on a metric that returns impossible values would
produce another tuned-to-look-right number — the exact failure this sprint exists to stop.**

Next: a rim detector robust across poses (fit an ellipse to the rim annulus rather than take extremes),
then solve (`EYE_X`,`EYE_Y`) against both targets, then re-derive the gauge offsets.

### Bonus finding — the wheel's colour is wrong too (PO: *"correct object placement and color throughout"*)

Sampled rim pixels: **gold (130, 42, 33)** vs **native (105, 59, 47)**. Native's red is both darker and
much less saturated — R−G of **46** against gold's **88**. That is why the first detector, tuned on
gold, found almost nothing on native.

---

## E74-S9 — ⚠️⚠️ RETRACTION: E74-S8's headline finding was an artifact. The wheel is NOT wrong.

E74-S8 reported that native renders the steering wheel **at half gold's size and face-on** where gold
sees it foreshortened, and named the cockpit eye point as the cause. **That is wrong, and the cause is
instructive.**

S8's width came from percentiles over red pixels in a central zone. In **gold the driver's overalls
carry RED SLEEVE STRIPES** that run diagonally to the bottom corners; in native the driver's arms are
white-grey. So the 2nd/98th percentile in gold landed on the *sleeves*, not the wheel — inflating
gold's "rim" from ~382 px to 716 px. Native had no such stripes, so its measurement was honest. **The
comparison measured a costume difference and reported it as a camera defect.**

I did render and inspect that mask. The rim was traced correctly, and I wrote "both masks trace their
wheel rims well" — while the sleeve bands were plainly visible in the same image. **Checking that the
target is detected is not the same as checking that nothing else is.** A mask can be right about what
it includes and still be wrong about what it adds.

### The sound instrument (`parity/tools/rimfit.py`, kept)

Anchor on the **Lotus badge** (found reliably in both), cast rays outward at 3° intervals, take the
outermost red pixel per ray, reject radius outliers, and least-squares fit an axis-aligned ellipse.
Sleeves and kerbs cannot move it because they are not radius-consistent about the hub. Verified by
dumping the ray endpoints over each frame — they sit on the rim in both.

| | gold | native (shipped) |
|---|---|---|
| wheel width | **0.298** of frame width | **0.264** |
| ellipse b/a | **1.020** | **1.069** |

The wheel is within **13 %** of gold, which is what the aspect difference (1.576 vs 1.778 → 1.128)
predicts, and both wheels are essentially circular in the image. **S8's "half size" and "face-on vs
foreshortened" are both refuted.** So is its conclusion that the eye is too far back — that rested
entirely on the inflated width.

### What survives from S8, and what does not

- ❌ **Refuted:** wheel half-size; wheel face-on vs foreshortened; eye-to-wheel distance wrong;
  the specific claim that gold's driver "looks down on the wheel".
- ✅ **Still true:** `JM_EYE_Y` 0.50 visibly opens up the road much as gold shows it, and native's dash
  slab does sit high and block the centre of the view where gold's cowl does not — that is visible in
  the captures and does not depend on the wheel measurement.
- ✅ **Still true:** the rim colour differs — gold (130, 42, 33), native (105, 59, 47), R−G of 88 vs 46.
- ⚠️ **Unresolved:** the dial-cluster height above the hub. Two attempts were contaminated by **sky**:
  a bright neutral cloud beside dark trees passes both a "bright bezel" test and a "dark face nearby"
  test. Both returned gold ≈ native (1.60 vs 1.72 radii), which is not credible given the captures.
  The next attempt must restrict to the cockpit's **connected component** rather than a box in wheel
  radii — no threshold on colour alone can separate cockpit from sky here.

### The lesson, stated for the next time

E74-S8 was careful in every respect except one: it verified the detector found its target and not that
the target was all it found. **The correct check is not "does the mask cover the wheel" but "is
everything the mask covers a wheel."** The ellipse fit is robust precisely because it tests a
*structural* property (radius consistency about a known centre) rather than a *colour* property.

**Nothing was shipped from S8** — its camera constants were withheld because the fit metric returned an
impossible negative value. That caution is the only reason this retraction costs a document edit
rather than a regression.

---

## E74-S10 — the dial-cluster measurement, unblocked: gold 0.14 radii, native 1.95

E74-S9 left this measurement blocked: *"no colour threshold alone separates cockpit from sky here"* —
two attempts had been contaminated by bright cloud beside dark trees, both returning gold ≈ native
(1.60 vs 1.72), which the captures plainly contradicted.

### ⭐ The unblock: segment the cockpit by TEMPORAL INVARIANCE, not colour

The cockpit is **car-fixed**; the world is not. Take three frames from different points on the lap and
the pixels that barely change *are* the cockpit. No colour assumption at all:

- gold (Monza cockpit video, t = 22 / 48 / 74 s) → 38.0 % of frame static
- native (Monza, s = 200 / 1200 / 5500) → 49.4 % static

Static treeline survives that test too, so take the **largest connected component touching the bottom
edge** — the cockpit is one connected body reaching the frame edge; distant scenery is not.

### The measurement

Dial bezels = bright, near-neutral, with a dark dial face within ~14 px, **inside the cockpit
component**, above the hub and within 1.2 wheel-radii horizontally (which excludes the mirror rims —
they were dragging the first attempt's centroid down to −0.02).

| | dial cluster above hub |
|---|---|
| **gold** | **0.14 wheel-radii** |
| **native** | **1.95 wheel-radii** |

⭐ **Native's dial cluster sits about 1.8 wheel-radii too high.** Gold's dials nestle just above the
hub — read *through the top arc of the wheel*, as E74-S9 described. This is the first number for a
defect that has been qualitative since E74-S1's "Dali dials".

**It also confirms E74-S8's warning with data:** E74-S7 shipped `JM_GAUGE_Y` 0.16 → **0.28**, moving the
dials **up** — directly away from gold. The fix made them legible by escaping occlusion, and in doing
so moved them further from where gold puts them.

### ⚠️ No constant re-derived — the metric will not support a fit

Sweeping the gauge offset does not give a monotonic response:

| `JM_GAUGE_Y` | dials above hub | bezel px |
|---|---|---|
| 0.28 (shipped) | 2.03 | 3888 |
| 0.14 | **1.46** | 1513 |
| 0.00 | 1.92 | 2398 |

Bezel counts swing between 1513 and 3888, because moving the cluster changes **what is occluded** — at
each offset the mask sees a different subset of bezel, and the centroid moves for reasons unrelated to
the cluster's true position. Fitting a constant to that would produce a number that satisfies the
metric rather than the geometry.

So: **the direction is established and the magnitude is not.** The dials must come down substantially;
by how much needs a stable estimator — most likely fitting the tachometer's own circle (the same
ellipse-fit trick that made the rim measurement sound in E74-S9) rather than a centroid over a
bezel mask whose visible extent changes with the thing being measured.
