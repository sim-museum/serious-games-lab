# E76 — objects deleted just after the Nürburgring start/finish (PO 2026-08-26)

PO: *"restore deleted objects shortly after start-finish line at nurburgring — many of the buildings
and crowds there were simply removed."*

## S1 — the "skipped 37 flat sprite stubs" lead is REFUTED

The load line `scenery… (skipped 37 flat sprite stubs)` looked like a strong candidate. Named all 37
(`JM_SPRITESKIP=1`) with their extents and lap positions:

**They are all SIGNS**, and all degenerate:

| name | count | what it is |
|---|---|---|
| `SIGNX` | 8 | generic signboard |
| `SIGN1` | 5 | generic signboard |
| `s_hatz`, `s_flug`, `s_aden`, `s_fuch`, `s_metz`, `s_karu`, `s_wipp`, `s_brun`, `s_dott`, … | 1 each | the Nordschleife **corner-name boards** (Hatzenbach, Flugplatz, Adenau, Fuchsröhre, Metzgesfeld, Karussell, Wippermann, Brünnchen, Döttinger Höhe …) |

Every one measures **h = 0.00 m, w = 0.10 m** — empty placeholder geometry, correctly skipped. And
the earliest sits at **lapdist 2003**, so **none is "shortly after S/F"**. This skip is not the PO's
missing content.

## But it is a real finding of its own

**The Nordschleife's corner-name signage is entirely absent** — 37 boards, including every famous
corner name, are degenerate stubs in the source and therefore never drawn. Whether GPL displays them
from art held elsewhere is unchecked. Worth a backlog line of its own; it is not E76.

## Where E76 actually has to be looked for

The Ring's scenery bypasses the GPL object pipeline (E70-S2), so its content is filtered by
different code from the other four tracks. Candidates, in order of cheapness:

1. **`treesrb*` is skipped outright** — `startswith(nm,"treesrb") && continue` drops forest-backdrop
   "paintings" before any other test. Count and place those; if buildings/crowds share the prefix
   they vanish silently.
2. **The down-facing-face cull** (E68-S9) skips strongly downward faces 5–30 m off the corridor and
   >3 m above road level. A crowd stand's underside could match.
3. **Compare the gold video directly**: at 904 s for 22.7 km, "shortly after S/F" is roughly the
   first 30–60 s. Frame-grab there and list what gold shows that the native sweep does not.

(3) is the one that answers the PO's question directly rather than by elimination, and it needs no
new instrument.

---

## S2 — ✅ REPRODUCED. The PO is right, and the gap is severe.

Gold (`260802_nurburgring_nintendo.mp4`, t = 10–60 s) against native (s = 200–1200) —
`e76_ring_sf_ab.jpg`:

| | gold | native |
|---|---|---|
| t=10 / s=200 | crowds packed on the left, hoardings right | a small crowd bank, some yellow barriers |
| t=20 / s=400 | **colourful advertising hoardings lining BOTH sides** | bare — fence, guardrail, empty grass |
| t=30 / s=600 | large grandstand + crowd left, hoardings | bare — grass, distant fence |
| t=40 / s=800 | **massive crowd banks BOTH sides**, hundreds of spectators | bare — dark hill, guardrail |
| t=50 / s=1000 | hoardings and crowds | bare — grass, fence |
| t=60 / s=1200 | trackside boards, buildings | bare — road, fence, trees |

**Gold's first kilometre is lined with dense crowds and advertising hoardings. Native has almost
nothing past s≈200.** This is exactly the PO's *"many of the buildings and crowds there were simply
removed"*, and it is not subtle.

## The likely scale of the problem

The Ring's whole scenery load is:

```
scenery… 184 groups / 4065 tris
```

For comparison, **Spa** loads `1679 trackside objects + 5132 billboards + 771 solid`. The Ring — at
**5× the length** — gets 184 groups. That is not a filter removing a few objects; it suggests the
Ring's scenery source is being read only in small part, or that most of its content never enters the
loader at all.

So the question is no longer *"which filter deletes them"* but **"is the Ring's scenery even being
loaded?"** — which is a different investigation from the three candidates listed in S1, and cheaper:
count what the loader is offered versus what it keeps.

⚠️ S1's candidates (`treesrb*` prefix skip, the down-facing cull) remain worth checking, but they
cannot plausibly account for a 5,000-object shortfall.

---

## S3 — ⭐ ROOT CAUSE: 72% of the Ring's scenery has no loadable mesh

Counted what the loader is offered versus what it keeps (`JM_SCENEDIAG=1`):

```
offered              3109
dropped: treesrb*       0
dropped: NO MESH     2231   <-- the placement exists, the object cannot be loaded
dropped: sprite stub   37
reached the renderer  841
distinct object names 595
```

**2,231 of 3,109 placements — 72% — are dropped because `getmesh(nm)` returns nothing.** The
placements are all there in the track data; the objects they refer to fail to load.

Most-placed missing names:

| name | placements | |
|---|---|---|
| `strauch6` | **372** | *Strauch* = shrub |
| `strauch4` | 163 | |
| `strauchy` | 96 | |
| `stree11` | 84 | tree |
| `strauch7` | 65 | |
| `FAKE` | 65 | |
| `stree1` | 60 | |
| `flagger` | **49** | marshals / flag crew |
| `BUSH` | 43 | |

### This settles the shape of E76

It is **not** a filter deleting objects, and not the sprite-stub skip (S1 already refuted that). The
Ring's trackside furniture is simply **never loaded** — which is exactly why its scenery totals
184 groups where Spa gets 1,679 objects + 5,132 billboards at a fifth the length, and why gold's
first kilometre is full while native's is bare.

### Next — and it is a narrow question

Why does `getmesh` fail for these names? The leading suspect is the same class this project has hit
before: **filename case**. GPL ships mixed-case names and Linux is case-sensitive; the `.dat` loader
already carries a `find_ci` helper written for exactly that reason. Note the missing list contains
both lower-case (`strauch6`) and UPPER-case (`FAKE`, `BUSH`) names, so a simple "everything upper
fails" story will not fit — the resolution needs measuring, not assuming.

⚠️ Also unverified: whether the missing names include the *buildings and crowds* the PO described.
The top of the list is vegetation and marshals; 595 distinct names were offered and only the top 15
are shown. Tabulate the whole missing set by name before claiming what content is absent.
