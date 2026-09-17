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
7. **Know your capture's repeat spread BEFORE quoting any difference — and it is not the
   same for every port.** Measured 2026-09-17 across all four:
   - **MiG Alley** (`parity_2d.sh`, headless 2-D, pinned save/resolution): **byte-identical on
     repeat**, 0 px of 2,073,600. Any difference at all is signal.
   - **Battle of Britain** (`bob_parity.sh`): **byte-identical**, 14 screens. One capture even
     matched a reference seeded five hours later by a different harness, bit for bit.
   - **julia** (3-D, live physics): **not** byte-reproducible. Chase views repeat at
     `mean|diff| ≈ 0.58`; the cockpit is unmeasured.
   - **FreeFalcon**: untested.
   A port with a byte-exact oracle can act on a 1-px change. A port without one needs a
   tolerance, and the tolerance must come from a measured floor, not a guess. **Never inherit
   another port's determinism claim** — three of these four differ.
8. **A repeat comparison must hold EVERYTHING constant except the thing under test — including
   the capture's POSITION IN ITS OWN SWEEP.** Learned the hard way (julia PARITYGATE-JR-1 S1→S3):
   a multi-shot harness like `JM_SHOTS` teleports and settles *from wherever the previous shot
   left the car*, so the 6th capture of one sweep and the 3rd of another are **not** the same
   experiment. A 53.4 `mean|diff|` that looked like a view-dependent render defect was view and
   sequence-position confounded, and the headline had to be withdrawn two sprints later.
   **Capture the reference and the candidate at the same ordinal in the same sweep** — or, better,
   capture the same point twice *within one run*, which removes launch, JIT, session state and
   sequence in one move.
9. **A gate that cannot execute is worse than a missing gate.** It reports coverage that does not
   exist. Three examples from one day: a gate whose assert fired at the same second as its own
   timeout; a probe placed inside an opt-in branch that was off; and a suite entry deferred
   "until the machine has memory" that then sat in the list unrun for eleven days while the suite
   counted it. **Assert your own preconditions** — before believing "no difference", prove the
   instrument can produce one.
