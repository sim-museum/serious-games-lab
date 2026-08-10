# Status — Julia Racer scrum run, 2026-08-08 → 09 (E64–E68, 30+ sprints)

Branch `julia-racer`, all work pushed to `origin/julia-racer`
(sim-museum/serious-games-lab, PO-approved push). Ceremonies pre-approved and logged;
every GL run through `gl-lock` shared with the MA/BoB/FreeFalcon sessions. Per-sprint
detail: `SCREEN_PARITY.md` (§E64 onward); evidence composites: `parity/*_ab.jpg`;
cross-project rollup: `~/SCRUM_STATUS.md`.

## Epics closed

### E64 — cockpit/chase parity (S1–S11) ✅
- **Live mirrors**: per-disc rear-view RTT at the cowl positions — road-dominated, tail at
  the inner edge, gold's composition (`JM_MIRROR_*`, `JM_MIRCAM_*`).
- **Hands**: gold 10-and-2 gloved fists riding the wheel + sleeves via the ARMFIX
  wrist-pivot correction (`JM_HANDS` on, `JM_ARM_*`, `JM_HAND_GRIP`).
- **Chase de-spidered + articulated rear suspension**: PRIM node 0x11 identified as GPL's
  LOD switch (was drawing every LOD at once — fixed parser-wide, `JM_LOD_ALL` A/Bs);
  the runtime-hidden suspension halves placed via the positioner-chain dump (hub-line
  fold, `JM_RSUSP` on). D12 → CLOSE-minus.
- **Watkins forest + placement**: WG3 "asset-limited" overturned; the road-only HAT that
  never was (WG4) — true road-texture oracle for Watkins + the Ring, car on tarmac at
  every surveyed position; Ring tree-row textures (`trowgl` archive-prefix fallback).

### E65 — Monza/Watkins scenery (S1–S5) ✅
Tree strips are **real folded meshes** now (the treeish() flattening was the root of the
canopy/slab/"distant strips" family): Monza's Lesmos ≈ gold, the E52 underpass reads as a
bridge, Watkins dense close autumn forest with the E22 pit straight clean.
Zandvoort/Spa/Nürburgring cleared by probe (byte-identical — never affected).

### E66 — wrap-up (S1–S2) ✅
Dark sail verified fixed (shared root cause with the strip flattening). **E46 crowd smear
closed**: 256×32 one-row crowd MIPs; GPL's point sampling = crisp pixel-people; NEAREST
magnification for crowd textures reproduces gold.

### E67 — launch time (S1) ◑
Measured (`JM_TIMING`): ≈2:45 = 19 s JIT + 5 s parse + 6.5 s extraction + **37 s texture
decode** + **97 s mtkcompile**. Texture cache landed **opt-in** (`JM_TEXCACHE=1`) pending
its A/B; the one-time `jlracer.so` sysimage build deferred to a quiet box (**new fleet
rule, learned by being killed twice: long CPU builds run UNLOCKED at nice-19, never as a
40-min gl-lock hold** — recorded in CONCURRENCY.md).

## E68 — PO 5-track re-drive feedback (S1–S13)

### Shipped ✅
1. **Perpendicular/floating spectator rows** dropped at every reported spot (`perp_crowd`,
   mesh-path only after the honest S8 correction that restored Spa's Eau Rouge line).
2. **Monza fading forests/translucent sheets**: uGraze off for mesh trees — solid at
   every angle.
3. **Sleeve–glove junction** closed (ARMFIX re-tune baked).
4. **Green dash block**: footwell charcoal like gold (height-split cowl harmonizer,
   `JM_FOOTWELL_Z`); cowl BRG preserved.
5. **Spa drive-through buildings**: `lasad1`/`chut` off the corridor (on-road building
   rule, logged); hut/house family now solid (705→771 solids).
6. **Ring floating block** (Karussell→back straight): landmass sections cull single-sided
   like GPL; Adenau bridge + hillsides verified intact.
7. **Guardrail z-fighting**: rail-family parts draw single-sided (offset front/back faces
   were poking through); nothing culled from the road side at four vantages. Motion
   confirmation = the PO's next drive.
8. **Spa stands at s≈13 850 verified rendering** (stree billboards kept; structures in
   frame).

### Investigations banked with exact resume state ◑
- **Moving white highlight**: precisely mapped by motion-pair static mask (camera-anchored
  sheen oval; two hypotheses honestly refuted — the first two by a contaminated
  measurement, lesson recorded: *profile the artifact, not the frame*). Next:
  `JM_DEBUG_SHADE` false-colour mode to attribute the term.
- **Per-face road-facing selection** — implementation spec in `PRODUCT_BACKLOG.md` with
  THREE customers: the D6 blank sign boards (Zandvoort at scale), the white shrubs, the
  Watkins veil (grass mega-sheet backs; blanket terrain cull disproven by regression —
  reverted byte-identical). Verification sites listed per customer.
- **W5 chase axles**: D12 fine-tune family (`JM_RS_*` knobs live).

### PO decision queue (evidence linked in SCREEN_PARITY.md)
1. Waive **V8** (cok board's authentic unpainted back) and **board-backs** (D6 family).
2. Waive **yellow Spa trees** — the SPAOLD grade A/B exonerates our pipeline; the sprite
   art is autumn-coloured.
3. **Z3 S/F grandstand**: track-mesh authored geometry — waive, or fence/verge
   investigation?
4. **Spa gap before La Source**: on your next drive, note the lap-timer second when the
   gap is ahead — that pins the capture.

## Standing state
- DoD held on every code sprint: race+5-AI smoke + `test_brush_slip` +
  `test_vehicle_driven` green throughout; every fix capture-verified vs the gold lap
  videos; regressions (terrain cull, crowd sprites) caught by counts/captures and
  reverted byte-identical before shipping.
- Next sprints when the loop resumes: per-face selection implementation (fresh context),
  `JM_DEBUG_SHADE`, the E67 texture-cache A/B + nice-19 sysimage build in a quiet window.
