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

---

## S4 — ⭐ the objects ARE in the archive. The `.3do` PARSER fails on them.

Two hypotheses tested this sprint, both mine, one refuted and one replaced by something better.

**Hypothesis: the content is missing from the install.** Refuted. `strings nurburg.dat` finds 137
matches for `strauch* / stree* / flagger / bush`, in both cases. The objects are there.

**Hypothesis: filename case — a lowercase lookup against a mixed-case archive.** Also refuted, and
by the cleanest possible measurement:

```
archive keys: 858 total, 858 already lowercase, 0 mixed/upper
of 2231 failed placements, 1865 WOULD resolve with a case-insensitive archive lookup
```

Since every key is already lowercase, a case-insensitive lookup is **identical** to the current one.
So that second line does not mean what it first appears to: it means **1,865 of the failed
placements have their object present in the archive under exactly the key `getmesh` asks for.**

### What that leaves

`getmesh` is:

```julia
v = get(datpack, lowercase(nm*".3do"), nothing); v === nothing && return nothing
write(tp, v)
m = try Render.GPL3DO.parse_3do(tp) catch; nothing end
m === nothing ? nothing : dedup_scenery(m.tris)
```

The key lookup succeeds for 1,865 of them, so they must be failing at **`parse_3do` throwing**, or
at `dedup_scenery` returning empty. **The Nürburgring's scenery is not missing and not filtered —
it is unparseable by this loader.**

The remaining **366** failed placements (2231 − 1865) genuinely have no archive entry and are a
separate, smaller problem.

### Next — narrow and high-value

Instrument the `catch` in `getmesh`: record the exception per object name. One run says whether it is
a single parser limitation hitting 1,865 placements (likely, given `strauch6` alone accounts for
372) or a scatter of unrelated failures. If it is one bug, fixing it restores the bulk of the Ring's
trackside content in a single change — the largest single content win available on this project.

⚠️ Note the pattern in this item: three sprints, three of my own hypotheses discarded (sprite stubs,
missing content, filename case). Each was refuted by measuring the thing itself rather than
reasoning from the symptom — and each refutation narrowed the search rather than restarting it.

---

## S5 — ⭐⭐ ROOT CAUSE CONFIRMED: the Ring's scenery path has no BILLBOARD support

Instrumented the swallowed `catch`. **Not one object throws.** All 50 failing names report the same
thing:

```
[mesherr] BUSH       parsed OK but EMPTY after dedup (0 raw tris)
[mesherr] strauch6   parsed OK but EMPTY after dedup (0 raw tris)
[mesherr] flagger    parsed OK but EMPTY after dedup (0 raw tris)
[mesherr] deadtree   parsed OK but EMPTY after dedup (0 raw tris)
[mesherr] stree9     parsed OK but EMPTY after dedup (0 raw tris)
```

`parse_3do` **succeeds and returns zero triangles**. These objects carry no triangle geometry at all.

### Why: they are camera-facing BILLBOARDS, and this loader only understands triangles

Look at the names — `BUSH`, `strauch*` (shrub), `stree*` (tree), `deadtree`, `flagger` (marshals),
`FAKE`. These are exactly the class GPL draws as **camera-facing sprites**, not meshes. The other
four tracks handle them: Spa loads `1679 trackside objects + **5132 billboards**`. The Ring's
scenery path (E70-S2: a different loader entirely) produces `184 groups` and **no billboards at
all** — because it has no billboard branch.

So the chain is complete:

| step | evidence |
|---|---|
| PO: buildings/crowds missing after S/F | reproduced side-by-side (S2) |
| 2231 of 3109 placements dropped | census (S3) |
| 1865 of those have their object in the archive | key test (S4) |
| every one parses to **0 triangles** | this sprint |
| they are sprite/billboard objects; the Ring's loader has no billboard path | names + the Spa comparison |

**This is not a filter, a case bug, missing content, or a parser fault.** It is a missing feature in
the Ring-specific scenery loader.

### What the fix is

Give the Ring's scenery path the billboard handling the GPL object path already has — the same
`bbinfo` / camera-facing quad treatment that produces Spa's 5,132 billboards. That single addition
should restore the vegetation, marshals and crowd rows across the **whole** Nordschleife, not just
the PO's stretch after S/F.

⚠️ Scope check before building it: **50 distinct names / 1,865 placements** are billboard-class. The
remaining 366 failed placements have no archive entry and are unrelated. And whether the PO's
*buildings* (as distinct from crowds and vegetation) are in the 50 has **not** been verified — the
names visible are vegetation and marshals.

---

## S6 — scoping the fix: it restores VEGETATION, not the crowds

All 50 billboard-class names, by kind:

| kind | names | count |
|---|---|---|
| shrubs | `strauch`, `strauch1/2/4/5/6/7/8/9`, `straucha/b/x/y`, `busch01/02`, `BUSH`, `bush2` | **17** |
| trees | `stree1–12/15/15k`, `STREE2`, `baum01`, `Baum20`, `Tanne1/3`, `TROWTREE`, `XK_TREE3`, `deadtree`, `DEADTR_2/3` | **~23** |
| marshals | `flagger` | 1 |
| unidentified | `A1`, `A2`, `A3`, `FAKE`, `GIN_B`, `ogrnd2`, `t60`, `t60b`, `wehr-l4` | 9 |

**There is not one crowd or grandstand name in the set.** So the billboard fix (S5) will restore the
Ring's vegetation and its marshals — a large visual change — but **will not restore the crowds the
PO reported**.

### Where the crowds are, or are not

The Ring's archive contains essentially **no crowd objects**: a search for
`ppl*/crowd*/spec*/zusch*/tribun*/grand*/stand*.3do` in `nurburg.dat` returns exactly **one** name,
`grand116.3do`. Gold's first kilometre shows crowd banks of hundreds of spectators on both sides.

So the crowds are either baked into the track mesh / terrain textures, or supplied by a mechanism
this loader does not read at all. **That is a separate investigation from the billboard fix**, and
the PO should know that fixing S5 will visibly improve the Ring without closing their report.

⚠️ The comparison search on Spa returned nothing for the same pattern, so Spa's crowd rows
(`ppl_m1`, `ppl_l3` — seen in the Zandvoort/Spa censuses) are evidently named or stored differently.
**My search pattern is therefore not proven adequate**, and "the Ring has no crowd objects" should be
re-tested with a pattern validated against a track known to have them before it is relied on.

### Revised plan for E76

1. **Billboard support in the Ring's scenery loader** (S5) — restores ~1,865 placements of
   vegetation + marshals. Large, well-understood, independent.
2. **Crowds: separate and unscoped** — find how gold draws the Nordschleife's spectator banks, using
   a search pattern first validated on a track whose crowds are known.
3. The 366 placements with no archive entry remain a third, smaller thread.

---

## S7 — ⚠️ TWO corrections to S6, and the crowds turn out to be a billboard problem too

### Correction 1: the search pattern was wrong, exactly as flagged

S6 concluded *"the Ring has essentially no crowd objects"* from a search returning only `grand116`,
and flagged that the pattern was unvalidated. Validating it changed the answer:

- **Control (Zandvoort):** `ppl_*` returns `ppl_l1…l5, ppl_m1, ppl_s1…s4` — exactly the names its
  census found. **Pattern works.**
- **Ring, same pattern:** nothing.
- **Ring, broader:** `people`, `peopledk`, `peoplefl`, `peoplelt`, `pplrow01`, `PPLv` — **the Ring
  has crowd objects**, under different naming.

The unvalidated null was wrong. Validating it against a track known to have the thing is what caught
it — and that check took one command.

### Correction 2: they are not failing. They load.

Placed crowd objects on the Ring, with load status:

| object | placements | geometry |
|---|---|---|
| `peoplefl` | 16 | **6 tris** — loads |
| `peoplelt` | 15 | **6 tris** — loads |
| `people` | 5 | 10 tris — loads |
| `peopledk` | 2 | 10 tris — loads |
| `grand116` | 1 | 76 tris — loads |

**39 crowd placements across 22.7 km, every one loading successfully.** So S6's other conclusion —
that the billboard fix "will not restore the crowds" — is also wrong, but for a reason neither of us
would have guessed: the crowds were never in the failing set because **they never failed**.

### What this actually means

A **6-triangle** crowd object is two quads. That is a *billboard* — a camera-facing sprite carrying a
crowd-row texture, which GPL draws as a wall of spectators and this loader draws as six flat
triangles lying wherever their authored orientation puts them. Same defect as the vegetation, one
step further along: those objects fail to parse to geometry, these parse to geometry that is
meaningless without billboard treatment.

**So the billboard fix (S5) plausibly addresses the crowds as well** — not by restoring missing
objects, but by drawing the present ones correctly. That is a materially better outcome than S6's
scoping suggested.

⚠️ Still unverified: whether 39 placements at proper billboard scale would look like gold's crowd
banks, or whether gold draws additional crowds from the terrain textures. **Do not promise the PO a
full restoration on the strength of this** — the honest claim is that the crowds are present,
loading, and almost certainly rendered wrong.

---

## E76-S8 — ✅ THE RING'S BILLBOARD PATH SHIPS (1773 placements restored) + the S/F crowd is a separate object

E76-S5 identified the cause and named the fix: the Ring's own `gpl_scenery()` loader has no billboard
path, so every placement whose `.3do` carries no geometry was dropped. S8 collected the evidence and
implemented it.

### The evidence (JM_MESHERR on the Ring)

All **50** distinct failing object names report the *same* thing — **parsed OK, 0 raw triangles**:
`BUSH`, `strauch*`/`stree*` (shrubs and trees), `deadtree`, `flagger` (marshals), `FAKE`. Not a
parser fault, not scattered corruption, not missing archive entries: they are **billboard stubs**,
which GPL draws as camera-facing sprites from a texture and which carry no faces by design. The
count matches E76-S4 exactly: **1865 placements**.

### What shipped

`gpl_scenery()` now returns sprite placements alongside its triangles, and the Nürburgring branch
builds them with the same construction the GPL object pipeline uses. **1773 placed, every one
finding its texture.** Three rules were needed, each measured rather than assumed:

**1. The on-road cull is Ring-specific (`JM_RING_BB_HALFW`, 5.0 m).** The shared `ROAD_HALFW` is
9.0 m — deliberately generous so centreline wobble through Watkins' esses doesn't read as "on
grass". Applied here it dropped **847 of 1825** stubs. The lateral distribution says why that is
wrong:

| percentile | \|lateral\| | | cutoff | dropped |
|---|---|---|---|---|
| p5 | 5.5 m | | < 3 m | 3 |
| p25 | 7.1 m | | < 4 m | 6 |
| p50 | 9.5 m | | < 5 m | **30** |
| p90 | 20.3 m | | < 9 m | 847 |

Only **3** stubs sit within 3 m of the centreline — the authors planted nothing on the racing
surface. The foliage band *starts* at p5 = 5.5 m. A 9 m corridor on a forest circuit **~8–9 m wide**
does not delete objects "on the road", it deletes the treeline. 5.0 m drops the 30 genuinely over
the asphalt.

**2. Never bind a sprite to a collision-hull texture.** The tall families list their textures as
`collision | stree8`. `collision` *resolves in the texture index*, so a naive first-match bound every
14–24 m tree to it — which is what rendered the first capture as giants. Markers (`collision`,
`fake`, `shadow`, `lshad`) are skipped; a stub with nothing else is dropped (61, all `FAKE`).

**3. A camera-facing quad is only meaningful for a NARROW sprite** — the `JM_WIDE_PANEL` rule the
object pipeline already applies.

### ⚠️ The PO's actual complaint is NOT yet fixed, and the honest measurement says so

The PO reported crowds and buildings missing **shortly after the start/finish line**. With the wide
panel dropped, the restored billboards change **0.48 % of the frame against a 0.24 % null control at
S/F — i.e. nothing.** The vegetation came back; the crowds did not.

⭐ The S/F crowd is **one object**: `ogrnd2`, a single placement **209.3 m wide × 25.1 m tall** on the
`Grndpp1` ("ground people") sheet. It is the grandstand crowd terrace. Both flat-quad paths fail it:

- **camera-facing** → swung to face the eye it becomes a 209 m **wall of giant spectators** towering
  over the fence (the first capture);
- **static authored-yaw panel** → it renders **floating above the skyline**.

Neither is a tuning problem. A 209 × 25 m terrace is not a billboard in any orientation. Its `.3do`
carries **vertices with no faces**, so the real fix is to **triangulate the stub's own SZYX vertex
list into geometry** rather than substitute a quad — the same conclusion E65 reached for Monza's
folded panoramas ("build the strip from the stub's REAL vertex geometry, as GPL draws it"). That is
now the top E76 item, and it is a *content* fix worth more than any number of shrubs.

Default is therefore to **drop** the wide panel (`JM_RING_WIDE_DROP=0` re-enables the static path for
study). Shipping a wall or a sky-crowd to claim the PO's item would be worse than shipping neither.

### Result

| viewpoint | null control | scenery adds |
|---|---|---|
| s ≈ 400 (just after S/F) | 0.24 % | 0.48 % — vegetation only, crowds still absent |
| s ≈ 900 | 0.06 % | 1.95 % |

**1773 placements** of shrubs, trees and marshals restored across a 22.7 km lap that previously
loaded 184 scenery groups and zero billboards.

---

## E70-S4 / E76-S9 — ⭐ ROOT CAUSE: the LOD selector picks NULL children

E76-S8 left the PO's actual complaint open: `ogrnd2`, the Nürburgring's start/finish crowd terrace, is
209 × 25 m, carries the `Grndpp1` ("ground people") sheet, and parses to **zero triangles** — so it
could only be faked as a sprite, which produced either a wall of giants or a sky-crowd. S9 finds why.

### First hypothesis: triangulate the raw vertices — REFUTED before implementation

`ogrnd2` has **178 vertices** and its first groups looked like clean vertical quads (v0,v1 at z=2;
v2,v3 at z=0, x/y matching). Tempting: emit two triangles per group of four. **Checked first, and it
does not hold** — only **4 of 44** groups conform, and panel widths include zeros. The vertex order is
not face order, so any triangulation built on it would have been invented geometry.

### The instrument, and what it found

`JM_PRIMDIAG` (new) tallies every PRIM node type the walker reaches and flags the unhandled ones. It
exists because E76-S5 lost a sprint to a `catch` that swallowed its reason; "0 triangles" should never
again be a silent result. For `ogrnd2`:

```
[primdiag] ogrnd2.3do: 0 tris from 1 nodes
   type 0x011  x1   handled
```

**One node, and the walk stops.** Type `0x11` is the LOD/distance list. Printing its children:

```
child 1: dist 4.0e7    off -1      (null)
child 2: dist 7.0e6    off 6384    ← the only real geometry
child 3: dist 0.0      off -1      (null)
child 4: dist -6000.0  off -1      (null)
```

⭐ **GPL pads its LOD lists with NULL entries carrying sentinel distances, and `argmin` over the raw
distance array selects one of them.** The minimum is −6000.0, whose offset is **−1**; the walker
follows a null child and returns nothing — from an object that plainly has geometry.

E64-S4 introduced the argmin to pick the closest-range child, and it is right to do so. It simply
never asked whether the child it picked **exists**.

### Fix and measured effect

Choose the nearest-range child **with a real offset**. `JM_LOD_NULLS=1` restores the old behaviour.

| | before | after |
|---|---|---|
| `ogrnd2` | **0 tris** | **156 tris from 160 nodes** |
| Ring scenery | 184 groups / 4065 tris | 185 groups / 4116 tris |
| Ring sprite path | 1 wide panel faked | **0** — it is geometry now |

### ⚠️ Cross-track effect: measured by CONTROLLED A/B, after I first got it wrong

My first cross-track comparison used counts recorded **earlier in the session**, before several other
changes, and appeared to show Spa losing 8 objects — which this fix cannot do, since it only ever adds
candidates. Running both arms in the same build settles it:

| track | old | fixed |
|---|---|---|
| **Spa** | 1686 objects + 5167 bb | **identical** — unaffected |
| **Monza** | 114 objects, 1 forest panel | **118 objects, 0 forest panels** |
| Watkins | 113 objects | unchanged |

So the fix is real but **narrow**: the Ring's terrace, and 4 Monza objects plus one wide strip that
becomes true geometry instead of a faked panel. **A stale baseline is not a control** — the A/B cost
two runs and corrected a claim I would otherwise have published.

### The PO's item is advanced, not closed

Only **51 of ogrnd2's 156 triangles** survive the scenery filters (edge-length, road-corridor, dedup),
and the terrace is still not visible at s=400. The object is no longer fake, which was the blocker;
what remains is finding which filter is eating it.

---

## E76-S10 — ✅ THE PO'S CROWDS ARE BACK, as real geometry

E70-S4 fixed the LOD null-child selection and left one question: 156 triangles now parse, but the
terrace was not visible at s=400.

### It was never being filtered — I was looking in the wrong place

`JM_SCENEDROP` (new) counts, per object, what each scenery filter removes:

```
[scenedrop] ogrnd2: mesh has 156 tris; placed at lapdist 463 lat 48.4  origin z=611.5
[scenedrop] ogrnd: dropped 0 by the stretched-edge rule, 0 by the road-corridor rule
```

**Nothing is dropped.** Two corrections to E70-S4's closing note:

1. The "51 of 156 triangles survived" claim was wrong. The Ring's `scenery… N tris` figure is the
   **collision HAT** count, not the render set — the render geometry goes into *groups*, which went
   184 → 185. All 156 triangles are in the scene.
2. The terrace sits at **lapdist 463, lateral 48.4 m**. A capture at s=400 looking forward simply does
   not frame an object 48 m to the side. **The object was fine; the viewpoint was wrong.**

### Verified where it actually is

A/B at the terrace's own lapdist, old LOD selection vs fixed (Ring null control 0.00–0.33 %):

| viewpoint | frame changed |
|---|---|
| s=380 | 0.91 % |
| **s=463** (the terrace) | **0.50 %** |
| s=774 (`ogrnd11`, 60 tris) | 0.47 % |

Small percentages, because a terrace 48 m away is small on screen — but the picture is unambiguous:
**a bank of spectator figures now stands beyond the fence**, at credible scale and position, where
before there was bare hillside.

Compare the three attempts at this one object:

| attempt | result |
|---|---|
| camera-facing sprite (E76-S8) | 209 m **wall of giant spectators** over the fence |
| static authored-yaw panel (E76-S8) | crowd **floating above the skyline** |
| **real geometry (E70-S4 LOD fix)** | **a crowd terrace on the bank, correctly scaled** |

The first two were attempts to fake an object that only looked empty because our LOD walker followed a
null child. **The fix was never a rendering choice — it was a parsing bug**, and E76-S8's instinct to
ship neither fake rather than claim the item was right.

### Status of the PO's item

*"Restore deleted objects shortly after start-finish line at nurburgring — many of the buildings and
crowds there were simply removed."* The **crowds are restored** (`ogrnd2` at s=463, `ogrnd11` at
s=774), along with E76-S8's 1773 vegetation and marshal billboards. **Buildings have not been
separately verified** and remain open.

---

## E70-S5 / E76-S11 — the S/F grandstand IS there; my query window did not wrap the lap

E76-S10 closed the **crowds** half of the PO's item and left the **buildings** half unverified. S5
verifies it, and finds three separate things.

### 1. ⚠️ My own query excluded the answer

`JM_SCENE_AT=400` (new) listed only **15 scenery objects within ±250 m** of the start/finish — 12 crowd
rows, one small house, `land1` and the terrace — which looked like damning confirmation that the
buildings are gone.

**It was wrong.** `grand116`, the grandstand, is placed at **lapdist 22753** on a **22766 m** lap —
i.e. **13 m before the start/finish line**. A ±250 m window around s=400 does not **wrap** past s=0, so
it silently excluded the very object being looked for. Same class as E69-S9's truncated `JM_OBJFIND`
listing: a query whose scope quietly omits the answer reads exactly like an absence.

### 2. ⚠️ The grandstand is being partly eaten

```
[scenedrop] grand116: mesh has 76 tris; placed at lapdist 22753 lat 30.4
[scenedrop] grand116: dropped 16 by the stretched-edge rule, 0 by the road-corridor rule
```

**16 of 76 triangles (21 %) are discarded** by the "stretched garbage" heuristic (`emax > 70 &&
emax > 10×emin`) — the rule written for vertices parsed at junk coordinates. A grandstand is long and
low, so its roof and terrace spans are legitimately stretched. `ogrnd2` lost none to this rule; the
grandstand loses a fifth.

### 3. What is genuinely present, and what is not

| gold shows at S/F | native |
|---|---|
| long roofed grandstand, packed | `grand116` — **present**, 76 tris, 21 % eaten |
| **Continental timing tower** | `tower2` is at **lapdist 1494**, not S/F — **no tower at the line** |
| continuous wall of hoardings (BARDAHL, BOSCH, CASTROL, MARTINI, COCA-COLA…) | 13 Bosch signs + 14 others, **2 triangles each** |
| dense crowds both sides | ✅ restored, E76-S8/S10 |

The archive **does** hold `grand116.3do`, `tower2.3do`, `bosch*.3do` and `h-tower.mip` — so this was
never missing content, it is sparse placement plus a filter eating part of what is placed.

### 4. The 37 skipped stubs are the Nordschleife's CORNER-NAME boards

`JM_SPRITESKIP` names them: `s_hatz` (Hatzenbach), `s_aden` (Adenau), `s_fuch` (Fuchsröhre), `s_metz`
(Metzgesfeld), `s_berg` (Bergwerk), `s_kess` (Kesselchen)… all **h = 0.0, w = 0.1** — degenerate, so
they cannot render as meshes. These are iconic track furniture and are **restorable via the billboard
path E76-S8 already built** for the vegetation stubs. A named, scoped next step.

### 5. `JM_TEXDIAG` was also unreachable on the Ring — the third instance

It sat inside the GPL-object branch, like the three road censuses hoisted in E75-S9. **My first attempt
to hoist it landed before the branch's real close and left it just as unreachable** — and produced no
output, which I nearly read as "no signage in the mesh". Now genuinely at top level: the Ring's track
mesh carries **87 textures and essentially no signage** (one `boschb`, 14 tris), confirming the
hoardings are scenery objects rather than baked mesh.

---

## E70-S6 — ✅ SHIPPED: the junk filter is now object-relative. +745 triangles, and the S/F gantry is back.

E76-S11 found the Ring's start/finish grandstand losing **16 of its 76 triangles** to the
"stretched garbage" rule. S6 fixes the rule.

### Why the old rule was wrong in principle

```julia
emax > 150 || (emax > 70 && emax > 10*emin)     # absolute thresholds
```

It was written to kill triangles built from **vertices parsed at junk coordinates** — the "giant
jagged Star Destroyer shapes floating off in the sky". But it tests the triangle in *absolute* metres,
so it cannot tell a nonsense vertex from a **legitimately long span**. A grandstand roof beam and a
misparsed vertex both make a long thin triangle.

⭐ The distinguishing property is not length, it is **being an outlier relative to the object's own
extent**. A junk vertex lands far outside its object's bbox; a roof beam lies inside it. So the test is
now: a vertex more than 3× the object's own robust half-extent (+20 m) from its median centre is junk;
a long edge wholly within the object is architecture. The extent is median/percentile-based, so a
single junk vertex cannot inflate the very reference used to detect it. `JM_EDGE_ABS=1` restores the
old rule.

### Result

| | old (absolute) | new (object-relative) |
|---|---|---|
| `grand116` triangles dropped | **16 of 76** | **0** |
| Ring scenery | 185 groups / 4116 tris | **201 groups / 4861 tris** |

**+745 triangles and 16 more scenery groups** — and the visible win is the **start/finish gantry**, the
overhead structure spanning the track, absent before and present now. Its long low spans are exactly
what the absolute rule mistook for junk.

### Verified against the thing the old rule existed to prevent

Junk geometry does **not** return: captures at s=6000, 13000 and 18000 are indistinguishable between
the two rules. And `gpl_scenery` is Nürburgring-only, so no other track is touched by this change.

### Observation for later

The start/finish view is richer than E76-S11 implied — Continental hoardings, pit buildings and flags
are all present just before the line; my earlier captures at s=400 were simply past them. Two smaller
defects are visible there and are **not** addressed here: the gantry's lettering renders **mirrored**,
and roadside vegetation at s=13000/18000 shows a **cyan/turquoise cast** in both arms.
