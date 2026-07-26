# QA method note — gold-oracle screen parity (from julia-racer E59, 2026-07-25)

Method-level findings from running per-screen parity of a native renderer against
"gold" screenshots of the original game (GPL under Wine). Engine-agnostic; shared for
the other port projects' QA.

1. **Inventory the gold set FIRST, as data.** Before rendering anything, classify every
   gold shot: camera type (cockpit/chase/TV/menu), landmark, signage text, sky/lighting
   character. Two things fall out immediately: (a) the *dominant view* to prioritise
   (all 43 of our Zandvoort golds turned out to be cockpit — TV/chase work would have
   been wasted); (b) *global* deviations (a sky-grade mismatch showed in every shot —
   one fix moved the whole set closer, before any per-shot iteration).

2. **Batch captures per launched session.** If engine startup is expensive (ours: ~2 min
   Julia/track load), a one-shot smoke harness makes each screenshot cost a full launch.
   We added a `JM_SHOTS="s:view:name;…"` multi-shot mode: teleport → N settle frames →
   framebuffer dump → next shot, all in one session. 21 screenshots ≈ 1 launch + ~40 s.
   The settle-frame count matters: teleporting mid-session needs physics/camera/HUD
   smoothing to settle or you photograph transients (we reuse the same 38-frame warmup
   the single-shot smoke used).

3. **Landmark-map the lap by sweep, then pin gold↔native pairs.** A uniform `s` sweep
   (every ~250 m) captured in one session gives a lapdist→landmark map; each gold shot
   then gets a repro recipe (`s`, view) rather than a vague "somewhere in the dunes".
   Commit the map — reruns become regression checks.

4. **Distinguish four deviation classes** — they route differently:
   - renderer/grade bugs (fix in code; verify by re-capture);
   - authentic-asset surprises (our "cyan slab" was GPL's own teal pond texture —
     decode the source texture and check its average colour BEFORE "fixing" scenery);
   - asset-capability gaps (gold tyres carry tread textures; our wheel mesh is
     untextured — a lighting fix can narrow but never close it; log as asset-limited);
   - prior-owner decisions (hidden driver figure, HUD kept) — waive, don't churn.
5. **Beware oracle drift between gold sets.** Two ref-shot batches disagreed on the
   Zandvoort sky (blue vs overcast); an earlier autonomous pass "fixed" toward the
   wrong one. When gold sources conflict, the newest PO-designated set + recorded PO
   decisions win — and write the A/B toggle (`JM_GRADE=<NAME>`) so the losing look
   stays one env var away.
6. **Commit small side-by-side composites** (gold left, native right, same height,
   JPEG ~200 KB) next to the parity table. Verdicts without the composite rot fast.
