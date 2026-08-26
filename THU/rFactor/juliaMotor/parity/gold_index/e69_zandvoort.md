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
