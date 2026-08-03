# Status — Julia Racer graphics, E62–E63 (2026-08-02/03)

Branch `julia-racer`. Session goal (PO): make the graphics on all 5 tracks match the gold-standard
lap videos (`~/gold standard/julia racer/<track>/`). PO reprioritised mid-session: **trackside
objects (colour · location · orientation) for all tracks are the HIGHEST priority, then cockpit +
chase.** Run as an autonomous scrum (PO pre-approves planning + reviews). Every render/capture went
through `gl-lock` as `julia-racer`, sequential, one display at a time.

## Key correction
**E61 (prior session) matched only per-track colour GRADES** (sky/saturation/verge). It did NOT match
trackside objects, cockpit furniture, or the chase car — those were logged open/waived. E62/E63 are the
real object + cockpit + chase pass.

## E62 — Zandvoort cockpit/chase (depth-first, done first)
- `2f6a744` — scuttle de-glared to muted matte TAN (`WIND_B/A`=0.45); front wheel track tucked in
  (`WTRACK_F`=0.78); **D12 skeletal chase body ROOT-CAUSED** as asset-LOD-limited (GPL hides rear
  suspension/axle via large positioner offsets `posmat` clamps to origin → chrome "spider-legs"; a
  parser drop-by-hide-marker was tried and reverted — it cut the car 2253→387 tris). `JM_CARP_MAXLAT`
  A/B knob added (default 0.85). `JM_HANDS=1` confirmed unusable (giant silver arms — needs a mesh refit).
- `bd427f3` — gauge dials brightened (`JM_DASH_B/A`=1.2/0.9) → legible white-on-black like the gold.

## E63 — trackside-object parity (all 5 tracks, PO's #1 priority) — achievable scope DELIVERED
Biggest win = crowds. Every track captured vs its gold video.
- `ebda286` — **Crowds restored, all tracks.** The gold shows dense crowds lining every fence/bank; the
  crowd rows exist in the data (Zandvoort `ppl_l/m/s*`, Spa `p_s*/people*/pelf*`) but `drop()` removed
  them as "loose spectators" (old D8 remove-crowds, now superseded by PO). Reclassified as kept crowd via
  `standcrowd()`; the `onroad_crowd` filter still drops any on the pavement; single loose figures
  (marshals/photographers) stay dropped.
- `45d393d` — **Crowd colour** de-blued (`CROWD_TINT` TB 0.78→0.66, TR→1.16; `is_crowd_obj` extended to
  the restored rows) → gold's warm tan/khaki tones, not garish blue.
- `4b34143` — **Monza MZ3 dark "banking" slab FIXED.** It was never the E52 banking geometry — it's a
  wide forest STRIP (`trees01-23`) seen EDGE-ON collapsing to a tall dark triangle. The `STATICTREES`
  draw always claimed graze-fade in its comment but never passed `graze=` → added `graze=true` (uGraze)
  so edge-on strips fade while face-on tree-lines still fill the roadside void.

### Per-track object state after E63
| track | state |
|---|---|
| Zandvoort | signage correct (D6 uBackFlip holds); crowds restored+warm. Minor: a few blank far-side board BACKS, V8/E45 floaters |
| Watkins | crowds render; sky hazy pale. **WG3 tall roadside autumn forest still missing — asset-limited** (`JM_DROP_FOREST=0` panels are distant strips, not the tall close trees GPL places as scenery objects; needs tree-OBJECT placement) |
| Nürburgring | **E44 right-side carbonized RESOLVED** (both sides lit); crowds both sides; sky bright partly-cloudy. Minor: N2 floating quad |
| Monza | tree-curtain gone; MZ3 slab fixed; signage/crowds/sky good |
| Spa | `p_s*` crowds render; sky hazy-blue; **E41 90° storefronts NOT reproduced** (garages ~parallel at S/F/pit) |

## Verified via captures/composites (scratchpad)
`cmp_zand_cockpit` (cockpit gold vs native), `cmp_crowd_tint` (blue vs de-blued crowds), Monza slab
before/after, Watkins forest vs gold, Nürburgring/Spa crowd confirmations.

## Remaining (asset-deep or next phase)
- **E64 cockpit/chase** (next per PO priority): **mirror RTT reflections** (explicitly requested — a real
  extra render pass, FBO infra exists in `make_scene_fbo`; invasive, multi-block), driver-hands mesh
  refit, chase-body LOD (D12).
- Asset-limited objects: Watkins WG3 forest (tree-object placement), chase body.
- Minor: Zandvoort blank board-backs, Nürburgring N2 floating quad.

## How to resume
Per-track grades LIVE at next launch (no `jlracer.so` rebuild). Object/crowd knobs: `standcrowd`/`drop`/
`is_crowd_obj`/`CROWD_TINT` in `drive_native_mtk.jl`. Diagnostics: `JM_OBJDIAG` (names/relyaw/OFF-HAT),
`JM_DROPTEST=<prefix>`. Method + per-track verdicts in `SCREEN_PARITY.md` §E62/§E63.
