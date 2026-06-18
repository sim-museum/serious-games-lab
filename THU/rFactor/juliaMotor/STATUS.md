# juliaMotor — status (2026-06-17)

Branch: `julia-racer`. A Julia physics engine (`JuliaMotorMTK`, ModelingToolkit) + a
native OpenGL renderer (`demo/native`) for a 1967 Lotus 49 on GPL tracks (Zandvoort,
skidpad, Nürburgring Nordschleife). End goal "Path B": physics-based Lotus 49 tuned vs
gold-standard iRacing telemetry.

## Apps / how to run
```
cd demo/native
TRACK=nurburgring JM_NOSOUND=1 julia -t 2 --project=. drive_native_mtk.jl   # 3 tracks (1 Zandvoort / 2 skidpad / 3 Nürburgring)
JM_IBT=1 …                                                                   # also emit an iRacing-format .ibt
julia -t 2 --project=. drive_native.jl                                       # standalone Zandvoort app (packaged as zand_racer)
JM_SMOKE=1 …                                                                 # headless self-test → /tmp/zand_hud.ppm (Zandvoort only), auto-exit
```
Driver is GL 4.6 (NVIDIA GTX 1660). First load ~3–4 min. JM_NOSOUND=1 skips audio.

## Physics — DONE this session
- **Energy-conserving, physics-based combined-slip tyre** (`5721f32`) replacing the empirical
  Gyκ snap-oversteer hack. The friction force has magnitude μ·Fz·MF(σ) over combined slip
  σ=√(κ²+sin²α), **directed along the slip vector** (opposite the contact-patch slip velocity).
  One law gives: energy dissipated at any heading (a spin scrubs off and STOPS — no more
  speed-up-while-braking pinwheel), power-on snap oversteer for free, and the fitted pure-slip
  curves preserved. Files: `JuliaMotorMTK/src/components/{tyre.jl,tyre_law.jl,vehicle_rt.jl}`.
- Tests pass: launch 0→121 km/h, brake 121→40 in 2 s, steady grip 1.17 g, driven replay 1.27 g
  trail-braking. (`test_launch.jl`, `test_drive_rt.jl`, `test_vehicle_driven.jl`.)
- **`.ibt` comparison tool** `JuliaMotorMTK/tools/ibt_compare.jl` (`4f83480`): iRacing gold vs a
  JM_IBT run, per-channel min/mean/max + skidpad grip + energy-runaway check.

## Rendering — DONE this session
- **Reversed-Z depth** (`3d52f16`,`3cf8e72`): GL 4.5 context + glClipControl(ZERO_TO_ONE) +
  reversed projection (`perspective_revz`, near→1/far→0) + GEQUAL + clearDepth 0. Per-pass: the
  shadow pass stays standard so the shadow map/sampler are untouched. Killed the sign-on-fence
  *depth* z-fight. Both apps. (NOTE: this app renders to the DEFAULT framebuffer, so the earlier
  32F-depth-FBO change `3ff9896` is inert — reversed-Z runs on the default 24-bit depth.)
- **Cutout alpha pipeline** for chain-link/foliage shimmer: per-texture classification by alpha
  histogram (`b7e1355`,`99758ec` — incl. the `load_dds` path the fences actually use), edge
  sharpening gated to cutouts only (groove stays soft), distance-fade of unresolved far alpha
  (`d2b5f96`), 8× MSAA. Reduced the strobe a lot but did NOT eliminate it (see open issues).
- **Scenery cleanup**: de-dup GPL double-sided panels + drop stray "Star Destroyer" tris
  (`6d0b2ac`); skip flat horizontal sprite stubs (`f329b07`).
- **Cockpit**: additive ambient fill lifts pure-black tub/dash to a visible dark grey
  (`60ccbd1`,`c7c5630`); excluded the tan scuttle `windlot` (the "shining rug") (`f329b07`).

## OPEN ISSUES (user still sees these on the Nürburgring)
1. **Fence flicker — RESIDUAL.** Four layered fixes applied (reversed-Z, cutout sharpening,
   8× MSAA, distance fade). Down from "epilepsy-inducing" to a persistent residual. This is the
   inherent distant alpha-cutout aliasing of forward rendering; the only complete cures are
   temporal AA (needs motion vectors + history) or supersampling (big perf hit) — both large
   architectural changes, not yet done.
2. **"Shining rug" — STILL REPORTED on Nürburgring.** Excluding `windlot` removed the tan
   cockpit scuttle and was VERIFIED on the Zandvoort cockpit (SMOKE). But the user still sees a
   "shining rug" on the Nürburgring that earlier was described as "lined up with the racing
   groove, sometimes on the right" — which sounds like a GROUND/track artifact (a specular or
   shadow-box stripe following the racing line), NOT the cockpit scuttle. **Needs re-diagnosis
   with a fresh Nürburgring screenshot** (SMOKE can't reach Nürburgring — it forces Zandvoort).
3. **Horizontal floating people — STILL THERE.** The flat-sprite-stub skip (`f329b07`) targets
   `SIGN1/SIGNX/sign2m/s_aden` (UP≈0 quads). But the `flagger` marshals are billboard stubs with
   **0 triangles** — they never render via `gpl_scenery`, so the floating *people* come from a
   DIFFERENT path (the trackside-object / crowd / billboard system in `drive_native_mtk.jl`).
   **Not yet chased.** Next step: instrument which code path emits the horizontal people on the
   Nürburgring (the `OBJECTS`/`BILLBOARDS` build near the trackside-object loader).
- **Mirrors render black** (no render-to-texture). Separate feature, not started.

## Physics tuning workflow (Path B, next)
- Re-drive the skidpad with the FIXED tyre (`TRACK=skidpad JM_IBT=1 …`), then
  `julia --project=. JuliaMotorMTK/tools/ibt_compare.jl "<iRacing skidpad.ibt>" "<new.ibt>"`.
- Known data gaps: iRacing skidpad peaks ~1.5 g (target may be higher than the fitted 1.2–1.3 g);
  the JM `.ibt` writes the ROAD-wheel angle as SteeringWheelAngle (±17°) vs iRacing's steering-
  wheel angle (±385° via the ~15:1 ratio) — apply the ratio for the steering trace to line up.

## Memory
Assistant memory `juliamotor-project.md` and `demo/native/CLAUDE.md` track the longer history.
