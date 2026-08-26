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
