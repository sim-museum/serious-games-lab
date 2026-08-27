# Missing trackside structures — a cross-track defect, not a Nürburgring one

Prompted by E69-S3 finding Zandvoort's main straight empty, the PO's E76 report was tested at every
track's start/finish. Composite: `sf_all_tracks.jpg`.

| track | gold at S/F | native | verdict |
|---|---|---|---|
| **Nürburgring** | crowds + hoardings for the first km | bare past s≈200 | ⭐ **severe** (E76) |
| ~~Zandvoort~~ | grandstands, pits, Dunlop bridge, crowds | **native s=0 matches gold — NOT affected** | ❌ **RETRACTED (E69-S4): the comparison used a mis-mapped lapdist 330 m before the straight** |
| **Watkins Glen** | Kendall banner + large multi-storey pit/timing building | ✅ **FIXED (E72-S7)** — buildings were buried ~29 m by the `edgez` march target; now restored | ✅ |
| **Spa** | pit wall with Shell/BP signage, timing board, spectators, bridge | green hoardings, tents, flags — **populated but arranged differently** | ◑ differs, not empty |
| **Monza** | pit wall, dark grandstand, hoardings | AUTODROMO building, hoardings, crowds — **populated** | ◑ differs, not empty |

## What this establishes

**TWO of five tracks are missing trackside structures** (revised from three — see the Zandvoort retraction in `e69_zandvoort.md`). The PO
reported it on one; it is on at least three. Watkins is the sharpest single case — its banner draws
while the building behind it does not, at the same location, which rules out "the whole area is
unloaded" and points at per-object failure.

**Two tracks are NOT affected** (Spa, Monza), and that matters: whatever the cause is, it is not
universal. Spa and Monza both load through the GPL object pipeline and both show populated pit
areas, so the defect is not simply "the loader drops buildings".

## Relation to the billboard thread

E76-S5/S7 established that the Ring's vegetation, marshals and crowds are **billboard-class objects
the loader cannot draw**. Zandvoort's `ppl_l3` renders as a flat wall — the same class, drawn wrongly
rather than not at all. Watkins' missing pit building is **not obviously billboard-class**, so it may
be a third variant or a different defect entirely.

⚠️ **Do not merge these into one item yet.** The evidence supports "several tracks are missing
structures"; it does not yet support "one cause". Watkins' building in particular has not been
traced to any loader stage.

## Next

Run the E76-S3 scenery census (`JM_SCENEDIAG`) on **Watkins and Zandvoort**. It reported
2231-of-3109 dropped on the Ring; if those two show comparable drop rates, the tracks share a
mechanism. If they show none, the missing structures have a different cause and E76 must stay
Ring-specific.

---

## Follow-up: object counts, and Watkins' pit building

### Density does NOT explain it

| track | lap | trackside objects | billboards | objects/km | billboards/km |
|---|---|---|---|---|---|
| **Spa** | 14.1 km | 1679 | **5132** | 119 | **364** |
| Zandvoort | 4.2 km | 221 | 39 | 53 | 9.3 |
| Watkins | 3.75 km | 113 | 13 | 30 | 3.5 |
| Monza | 5.7 km | 114 | 19 | 20 | 3.3 |

**Spa is an extreme outlier — 364 billboards/km against 3–9 elsewhere.** But density does not explain
the missing structures: **Monza is the sparsest track of all (20 objects/km) and its pit area looks
populated**, while Watkins at 30/km is missing its building. So this is about *specific objects*, not
how many there are.

### Watkins: the pit building exists in the archive and is not in the render

- The archive contains **`pit.3do`, `pitfill2.3do`, `pitgrnd1.3do`, `tower1.3do`**.
- `JM_OBJDIAG`'s tallest-25 and highest-placed-22 lists contain **no `pit`, `tower` or `timing`
  entry** — they are dominated by trees (27–39 m).
- **Grandstands ARE placed**: `grand` (y=33.5), `grndpe1l` / `grndpeo1` (y≈38.2). So the track is not
  wholesale missing structures — the pit building specifically is absent from the render.

⚠️ **Not proven absent.** Both diagnostic lists are truncated (top 25 / top 22), so a shorter `pit`
object could be placed and simply not shown. Confirming needs a full dump of placed names for the
GPL pipeline — the equivalent of `JM_SCENEFIND`, which currently exists only on the Ring's path.

### Incidental observation worth its own check

Watkins' trees measure **27–39 m tall**. That is 90–130 feet — plausible for mature American
hardwoods, but it is the same shape as the Spa "oversized houses" question (E71-S5/S10), and nobody
has measured Watkins' vegetation against gold. Logged, not claimed.

### Next

Add a placed-name search to the GPL object pipeline (mirroring `JM_SCENEFIND`) and ask directly
whether `pit`/`tower1` are placed at Watkins. That distinguishes **"not placed in the track data"**
from **"placed and dropped by a filter"** — which need entirely different fixes.

---

## E72-S4 — ⚠️ CORRECTION: Watkins' pit building is NOT missing. It is placed 28–42 m off the track.

Added a placed-name search to the GPL pipeline (`JM_OBJFIND`), reading `OBJINSTS` — every instance
with the fate the render filters gave it. Result:

| object | fate | lapdist | lateral |
|---|---|---|---|
| `newpit` | **mesh (kept)** | 3651 | **−41.9 m** |
| `tower1` | **mesh (kept)** | 578 | **−26.9 m** |
| `pitfill2` | mesh (kept) | 3551 | −28.7 m |
| `pitgrnd1` | mesh (kept) | 3604 | −32.4 m |
| `grand`, `grandl` ×3 | mesh (kept) | — | off-ribbon |

**Every pit structure is placed and kept.** None is dropped by any filter. So the earlier verdict —
*"the building is absent from the render"* — was wrong, and it was wrong for a reason worth naming:
it rested on **absence from two truncated diagnostic lists** (tallest 25, highest 22). Absence from a
top-N list is not absence.

### What is actually wrong

They sit **28 to 42 metres from the centreline**, all on the same side. Gold shows the Watkins pit
and timing building **immediately beside the track**, close enough to read the people on its
balconies. At 28–42 m it is far back across the grass — which is exactly what the native S/F frame
shows.

Also note `tower1` sits at **lapdist 578**, nowhere near start/finish, while gold's tower is at the
pit straight.

So this is a **placement** defect, not a loading one — and it therefore has nothing to do with the
Ring's billboard problem, despite both presenting as "the buildings are gone". **Two tracks, two
different causes, one symptom.**

### ⚠️ What is not yet established

- Whether −28 to −42 m is *wrong* or merely *further than gold's camera makes it look*. The lateral
  sign convention has not been checked, so "on the wrong side" is possible and untested.
- Whether Zandvoort's empty main straight is this same placement class or the Ring's loading class.
  **It has not been checked, and the two need different fixes.**

### Next

Run `JM_OBJFIND` on Zandvoort for its grandstand/pit names. That splits the three affected tracks
into "placement" and "loading" groups, which is the fork the whole cross-track investigation now
turns on.
