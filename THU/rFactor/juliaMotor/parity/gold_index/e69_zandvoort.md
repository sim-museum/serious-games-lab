# E69 — Zandvoort gold-video parity

Oracle: `260801_zandervoort_nintendo.mp4` (144 s) + `_cockpit.mp4` (181 s).
Native: 11-shot chase sweep, s = 0…4000. **Zandvoort centreline = 4181 m.**
Composites: `e69_zand_gold.jpg`, `e69_zand_native.jpg`.

## The PO's reported defect does NOT reproduce here

PO (E68-CROWD): *"perpendicular spectator rows FLOAT above or sit ON the track — Zandvoort several
places."*

- `JM_CROWDDIAG`: **96 crowd rows kept, only 2 within 6 m of the centreline** — `ppl_s3` at
  lat +5.2 (s=750) and `ppl_m1` at lat −5.5 (s=3851). Both are outside a ~4.5 m asphalt edge, i.e.
  on the verge where gold puts them.
- All 11 sweep shots show crowds **on the banks and verges, none on the asphalt.**

The renderer already carries filters for this (`onroad_crowd`, `perp_crowd`, and the E68-S8b rule
that drops billboard crowds when on the road), so the likeliest reading is that E68-CROWD was
**already fixed for Zandvoort** by that work.

⚠️ **NOT claimed: "fixed".** 11 shots over 4181 m is one sample every ~380 m, and a floating block
can sit between samples — the PO saw these while driving the whole lap, which is far denser coverage
than this sweep. The honest statement is **not reproduced at 11 sample points, with a census that
finds only 2 rows near the road.** Closing it needs either a denser sweep or the PO pointing at a
location.

## Sky grade: MATCHES gold — do not "fix" it

Native renders a flat overcast sky. So does gold, in every frame sampled. **This is correct.**
Recorded emphatically because this project has form here: an earlier autonomous pass graded the
Zandvoort sky toward a superseded gold set (QA_METHOD_GOLD_PARITY.md step 5), and the washed-out
look invites exactly that mistake again.

## Candidate deviations, unverified

1. **Kerbs** — gold shows red/white striped kerbing at the corner apexes (clear at t=24/32/40/48 s);
   the native sweep shows pale edges with no obvious striping at this sampling resolution.
2. **Crowd density and proximity** — gold's spectator rows are dense and stand right at the track
   edge; native's read sparser and set further back.
3. **Road tone** — gold's asphalt is a darker grey; native's is paler.

All three need a matched-landmark pair before they are treated as defects; (3) especially, since
tone judgements from unmatched frames are exactly what step 4 of the method warns about.

## Already classified — do not re-open

The cyan block at s≈4000 is GPL's own teal pond texture, classified as an authentic-asset surprise
in QA_METHOD_GOLD_PARITY.md.

---

## E69-S2 — ⚠️ CORRECTION: the PO's on-track spectators ARE reproduced

E69-S1 concluded the crowd report *"does not reproduce"*, on the strength of `JM_CROWDDIAG` finding
only 2 of 96 rows within 6 m of the centreline. **That census measures instance ORIGINS.** Running
the extent-based footprint census (E71-S9) instead:

| object | lapdist | origin lat | **nearest vertex** |
|---|---|---|---|
| `ppl_m1` | 3851 | −5.5 m | **0.2 m** |
| `ppl_l3` | 3256 | **+12.3 m** | **0.8 m** |

**Two spectator rows have geometry reaching the centreline from origins 5.5 and 12.3 m away.** The
PO reported *"perpendicular spectator rows float above or sit ON the track — Zandvoort several
places"*, and that is exactly what this is.

This is the E71-S4 lesson repeating on a different object class: **centroid distance is not the
"is it in the way" ordering**, and `JM_CROWDDIAG` — which predates that finding — still sorts by
origin. A row whose origin is 12 m out looks perfectly innocent by that measure while its mesh lies
across the racing line.

**So E69-S1's negative was an artefact of the instrument, not a fact about the track**, and the
sweep photographs that appeared to corroborate it simply did not sample s≈3256 or s≈3851.

## Also found: a bank of bushes ON the racing surface

`bushes01/02/03/04` × ~12 instances cluster at **lapdist 2309–2405**, reaching `near|lat|` of
**0.1–1.4 m** — i.e. onto the road. Origins sit at 1.8–5.8 m. Same shape as the spectators: modest
origin offset, mesh across the line.

## Other measurements this sprint

- **Road width 9.2 m** (asphalt edge ≈4.6 m) — Zandvoort's own figure; the footprint run above used
  the borrowed 4.1 m, so it is **conservative** and a re-run at 4.6 m will flag more.
- **Centreline alignment: 16 of 17 buckets healthy.** The single flagged bucket (s=250, 4.6 m, 52
  tris) sits right at the asphalt half-width and is very likely the centroid artefact recorded in
  `centreline_on_road.md`, not a real defect.
- **Rail/fence triangles: 8 in total, 0 duplicates.** Zandvoort barely uses the `railfam` textures,
  so the guardrail dedup is irrelevant here.

---

## E69-S3 — gold pairing at the three flagged sites: one render bug, one MISSING-CONTENT hole

Paired each on-track object from E69-S2 against gold at the same lap fraction
(`e69_zand_ab.jpg`).

### s=3256 — `ppl_l3`: a crowd row rendered as a WALL

- **gold:** a line of spectators standing on the **right verge**, behind a low barrier. Road clear.
- **native:** a **huge yellow-green crowd texture filling the entire left of the frame** and
  overhanging the road edge.

The census said this row's mesh reaches 0.8 m from the centreline from an origin 12.3 m out. This is
what that looks like: not a small object nudged onto the track, but a **billboard drawn at the wrong
scale and orientation** — flat geometry where GPL draws a camera-facing sprite. **Same family as the
Nürburgring's billboard defect (E76-S5/S7)**, one step further along: the Ring's don't draw at all,
Zandvoort's draw wrongly.

### ⭐ s=3851 — the main straight: gold is full, native is EMPTY

- **gold:** grandstands, pit buildings, the **Dunlop bridge**, advertising, packed crowds — the
  busiest scene on the lap.
- **native:** **bare grass and an empty road.** No grandstand, no pits, no bridge, no crowds.

**This is the same defect the PO reported on the Nürburgring, on a second track.** Zandvoort's main
straight is missing its buildings and crowds entirely. It was not caught earlier because the E69-S1
sweep sampled s=3600 and s=4000 and stepped over it, and because the crowd census (origin-based)
could not see it.

### s=2350 — `bushes01–04`: no defect visible

Gold shows a clean road through the dunes with a hedge line; native likewise. The flagged bushes are
not visibly on the racing surface here. The census flags them at 0.1–1.4 m, so either they are
low/thin enough not to read, or this is a footprint false positive of the kind E71-S9 warned about
for long objects.

### Consequence

E76 should be **widened beyond the Nürburgring**: *"objects deleted"* now has a confirmed second
instance on Zandvoort's main straight. And the billboard-rendering defect now has two tracks'
evidence with **opposite symptoms** — absent on the Ring, oversized-and-flat here — which is a
strong hint they share one cause in how sprite objects are treated.
