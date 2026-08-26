# E70 — Nürburgring gold-video parity

Oracle: `260802_nurburgring_nintendo.mp4` (904 s) + `_cockpit.mp4` (909 s) — a full Nordschleife lap.
Native: 12-shot chase sweep, s = 0…22000. **Centreline = 22,756 m.**
Composite: `e70_ring_native.jpg`.

## ⭐ STRUCTURAL: the Ring's scenery does not go through the GPL object pipeline

Load line: `scenery… (skipped 37 flat sprite stubs) 184 groups / 4065 tris` and
`242 track parts`. Spa/Zandvoort instead report `N trackside objects + M billboards + … solid`.

Consequence, and it governs all further E70 work: **`insts` is empty for this track**, so
`JM_CROWDDIAG`, `JM_OBJDIAG` and the E71-S9 footprint census **produce no output at all here** —
confirmed this sprint: both diagnostics were requested and neither printed a single row.

So any spectator block sitting on the Ring's road is **authored into the track mesh**, not a
misplaced instance. That is the same class as the Zandvoort Z3 grandstand jut, which S13 already
classified as track-mesh authored geometry. **The E71 toolchain cannot be pointed at this track**,
and an object-move fix has nothing to move.

⚠️ Worth noting how this could have gone wrong: the censuses returned *zero rows*, which reads
exactly like "no crowds near the road — clean track". It is not a clean bill; it is an instrument
that was never connected. The load line is what distinguishes them.

## The PO's reported block: not reproduced, but sampling is far too sparse to matter

PO: *"a block intruding between the Karussell and the back straight."* All 12 sweep shots show a
clear road. **But 12 shots over 22,756 m is one sample every 1.9 km** — for a single localised
block that is essentially no coverage. This is NOT evidence of absence.

## Sky: blue with cloud here, versus flat overcast at Zandvoort

Both are correct — the project carries per-track grades (`GRADE_BYTRACK`), and the Ring's gold is a
brighter day than Zandvoort's. Recorded so the two tracks are never "made consistent" with each
other.

## Next, and it is specific

Locate the **Karussell** by its own material — the code notes `Concrete = the Karussell banking`
(the E64-S9 road-texture work). Find the lapdist range of the concrete-textured road triangles, then
sweep densely (every 50–100 m) from there to the following straight. That turns "somewhere between
the Karussell and the back straight" into a bounded search, which at 1.9 km sampling it is not.

---

## E70-S2 — the censuses were unreachable here; relocated, and the Ring measures CLEAN

### Why E70 had no instrumentation at all

Every census built during E71–E73 (`JM_ROADWIDTH`, `JM_ROADTEX_CENSUS`, `JM_SPOTMESH`,
`JM_LINEONROAD`, `JM_FOOTPRINT`, plus the pre-existing `JM_CROWDDIAG`/`JM_OBJDIAG`) sat **inside the
GPL objects-building block**, after `OBJINSTS`. The Ring never enters that block — its scenery loads
by a different path. Proof: the census header printed on Monza and **not once** on the Ring.

E70-S1 read that silence as "no crowd rows near the road". It was an instrument that was never
connected — the same failure this project has now logged four times, and the second time on this
very track.

**Fix:** anything needing only `TRACKMESH` + `TRKSURF` now runs **before** the GPL/rFactor split,
right after `println(TERRAIN, "  ", TRKSURF)`, which every track reaches.

### ⭐ First real measurement on the Nordschleife: the centreline is clean

```
46 buckets: 0 with no road, 0 with the line >3 m off the road, 46 healthy
```

Across **22.7 km** the racing line never leaves the road and there are no road gaps — in contrast
with Monza, which has both. Regression control on Monza after the move: `s=500` 8.2 m off,
`s=2000` 3.1 m off, `s=4500` a gap — the known findings reproduce.

### ⚠️ A bug that only fires when there is something to report

The relocation put the census at **top level**, where Julia's soft scope makes a bare `bad += 1`
inside the loop bind a *new local* — `UndefVarError`. Monza hit it on its first bad bucket and
crashed; the Ring, having no bad buckets, **ran to completion and printed a clean summary**.

So the failure mode was: *the broken track crashes, the clean track passes.* Had the Ring been the
only track tested, the census would have looked healthy while being incapable of reporting a single
defect. Fixed with explicit `local`, and both tracks re-run.
