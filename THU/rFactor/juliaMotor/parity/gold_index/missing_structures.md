# Missing trackside structures — a cross-track defect, not a Nürburgring one

Prompted by E69-S3 finding Zandvoort's main straight empty, the PO's E76 report was tested at every
track's start/finish. Composite: `sf_all_tracks.jpg`.

| track | gold at S/F | native | verdict |
|---|---|---|---|
| **Nürburgring** | crowds + hoardings for the first km | bare past s≈200 | ⭐ **severe** (E76) |
| **Zandvoort** | grandstands, pits, **Dunlop bridge**, packed crowds | bare grass, empty road | ⭐ **severe** (E69-S3) |
| **Watkins Glen** | Kendall banner + **large multi-storey pit/timing building with people on its balconies** | banner present, **building absent — bare grass** | ⭐ **structure missing** |
| **Spa** | pit wall with Shell/BP signage, timing board, spectators, bridge | green hoardings, tents, flags — **populated but arranged differently** | ◑ differs, not empty |
| **Monza** | pit wall, dark grandstand, hoardings | AUTODROMO building, hoardings, crowds — **populated** | ◑ differs, not empty |

## What this establishes

**Three of five tracks are missing trackside structures at their most prominent location.** The PO
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
