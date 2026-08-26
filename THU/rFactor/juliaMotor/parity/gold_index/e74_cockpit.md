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
