# Status — Julia Racer graphics, E64 S1 "Mirrors show the road behind" (2026-08-08)

Branch `julia-racer`. Sprint run under the standing scrum mandate (ceremonies pre-approved,
logged); every GL run through `gl-lock` per `CONCURRENCY.md`. Sprint goal — the PO-requested
**live mirror reflections** (Z-CK3), the top E64 item — **MET, 8/8**.

## What landed
- **Live mirror RTT.** In cockpit view the world renders a second time per frame from the
  driver's eye looking backward into a 384×192 FBO, X-mirrored in clip space like a real
  mirror (same reversed-Z conventions as the main pass). A round-masked glass quad on each
  disc samples its half of that view (left disc ← left half); the quads are derived from
  the mirror mesh's own per-disc bbox at load — no hand-placed geometry.
- **render.jl:** `make_mirror_fbo` (RGBA8 tex + 32F depth); `uMirrorGlass` shader path
  (unlit round-masked RTT sample; disc-local coords ride the colour attribute); `draw(...;
  mirrorglass=true)`.
- **drive_native_mtk.jl:** `mirror_glass_quads` (per-disc bbox → glass quad), `PROJ_MIRROR`
  + `mirror_camera` (rear view, X-flip), the mirror pass, and the enabling refactor — the
  world draw (horizon/track/objects/forest panels/billboards/AI) is now one shared closure
  `drawworld(vp, eye, flip)`; `flip` swaps the object-pass culled side because the X flip
  reverses winding.
- Knobs: `JM_MIRROR_RTT=0` restores the old static silver discs; `JM_MIRROR_FOV` (78°).

## Verified
- Cockpit captures at s=600 and s=1500 (Zandvoort): both discs show the live rear world —
  pit complex behind at s=600, dune bank at s=1500 (content changes with position ⇒ live,
  not baked), own tail + wheels in frame, horizon level, seen through the plexiglass tint
  as in the gold video. Crops: session scratchpad `mirror_rtt/`.
- Chase capture clean after the `drawworld` refactor (no world-draw regression).
- DoD: Zandvoort `JM_SMOKE` race + 5-AI exit 0 (known benign `.ibt` warning);
  `test_brush_slip` ✓, `test_vehicle_driven` ✓ (`test_corner_tyre:44` legacy-MF failure
  pre-existing, unchanged). All changes are `include`d source — LIVE at next launch, no
  sysimage rebuild (none present on this box).

## E64 remaining (next sprints)
Driver-hands mesh refit (Z-CK4); chase-body LOD (D12, asset-limited); mirror polish A/B
against the gold cockpit video at speed (own-tail dominance, per-disc FOV). Then the
cross-track cockpit/chase replication pass.
