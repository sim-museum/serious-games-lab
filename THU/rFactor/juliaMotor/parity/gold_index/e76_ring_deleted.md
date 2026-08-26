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
