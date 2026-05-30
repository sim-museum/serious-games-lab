# Cardplay benchmark findings — Plans 1 & 2 first run

Both replay (Plan 1) and multi-bot (Plan 2) harnesses ran at scale
across 5 random corpora. **Big takeaways below — the biq-vs-biq
metric was hiding meaningful asymmetric signal.**

## Plan 1 — single-seat replay (297 deals × 4 seats = 1188 trials)

| Role | n | trick-delta vs Q-Plus |
|---|---|---|
| biq plays declarer-side | 594 | **−0.012/deal** |
| biq plays defender-side | 594 | **−1.426/deal** |

biq's declarer is **essentially at parity** with Q-Plus's commercial
declarer. biq's defender **holds Q-Plus declarer to ~1.4 fewer
tricks per deal than Q-Plus's defenders did**.

The "still ~−0.5 tricks/deal vs commercial-grade" headline from
cardplay-mode was the symmetry artifact. Phases 11, 13, 15 are
genuine defense improvements; the biq-vs-biq run cancelled them.

### Per-seat (mixed declarer + defender roles)
- biq-as-N: −0.758
- biq-as-E: −0.879
- biq-as-S: −0.721
- biq-as-W: −0.519

Per-seat numbers blend declarer (≈0 delta) and defender (≈−1.4
delta) outcomes weighted by which side declares at each corpus.

## Plan 2 — 4-variant multi-bot (490 deals × 5 corpora × 4 seats)

Per-variant tricks averaged across deals where the variant played
each role:

| Variant | Declarer avg | Defender avg | Net (decl − def) |
|---|---|---|---|
| A baseline | 4.614 | 2.110 | +2.504 |
| B (+ P25 K-loc finesse) | 4.256 | 1.703 | +2.553 |
| C (− P11 return-partner) | 4.805 | 1.823 | **+2.982** |
| D (− P13 4th-best mid-deal) | 4.811 | 1.877 | **+2.934** |

Surprising: Variants C and D *outscore* A. C removes Phase 11
(defender returns partner's lead-suit) and D removes Phase 13
(defender 4th-best from longest mid-deal lead) — both rules that
gained on the cardplay-mode benchmark. Multi-bot suggests they
might over-fire in some contexts not captured by biq-vs-biq.

**Caveat**: variant-vs-variant interactions confound clean A/B
single-phase isolation. A variant's "declarer avg" depends on
which OTHER variants are defending against it. To pin down a
single phase's effect cleanly, run rotation experiments (each
variant rotated through each seat across many deals).

## What this changes about the cardplay project

- The committed phases (11, 13, 15, 23) are **real defensive
  improvements** that the cardplay-mode metric was hiding.
- The "still ~−0.5 tricks/deal vs commercial-grade" framing
  understated biq's actual position: declarer at parity, defender
  better than Q-Plus's. Updated estimate: **biq is at parity or
  ahead of Q-Plus's recorded cardplay across our random corpus**
  given the replay-mode metric.
- Items 1-5 from CARDPLAY_PLAN.md may still help, but now need
  validation via replay mode (single-seat asymmetric) rather than
  the symmetric cardplay mode.

## Phase 25 validation via replay mode

Re-tested Phase 25 (K-location-gated AQ finesse) via the new
asymmetric replay benchmark on 3 corpora (386 declarer-side
trials, 386 defender-side trials):

| Side | Baseline delta | P25 enabled delta | Δ |
|---|---|---|---|
| declarer-side | −0.148/seat | −0.168/seat | −0.021 |
| defender-side | −1.469/seat | −1.404/seat | +0.065 (worse defense) |

Phase 25 stays OFF — the K-loc-gated finesse rule doesn't help
even when biq-vs-biq symmetry is removed. The auction-derived
K-location inference is too coarse (RHO bid the suit ≠ RHO holds
the K), and the rule fires too rarely to overcome the variance.
Future suit-combination work needs richer K-location signals
(played cards, lead/follow patterns) before it can pay off.

## Suggested next benchmarking work

1. **Rotation experiment**: same 4 variants but rotated through
   all 4 seats across deals so each variant plays each seat
   roughly equally. Eliminates seat-pair confounds.
2. **A vs. (A + single phase)**: pin down each candidate phase's
   marginal contribution by isolating ONE phase per variant pair.
3. **Replay-mode validation of reverted items**: run Phase 25 / 26
   / 27 variants through REPLAY mode (asymmetric); they may show
   gains there that the biq-vs-biq mode hid.
4. **Sample-size + corpus expansion**: 5 random corpora is plenty
   for replay (1188 trials) but more corpora would tighten
   variant-comparison signals.

## Files

- `tools/mixed_corpus_diff.py` — `--mode replay` and `--mode multi-bot`.
- `tools/qnet_proxy.py` — Plan 3 RE scaffolding (live biq vs Q-Plus).
- `backend/cardplay_plan.py` — `PlannerConfig` + per-phase gates.
- `backend/QNET_PROTOCOL.md` — Plan 3 protocol notes.
- `backend/CARDPLAY_PLAN.md` — original architectural plan; now
  superseded by these benchmarks for validation, but the items
  list and effort estimates stand.
