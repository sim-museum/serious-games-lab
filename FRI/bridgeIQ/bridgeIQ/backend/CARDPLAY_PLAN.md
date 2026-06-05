# Cardplay engine — path to commercial-grade

## Current state (after Phase 15, committed `7782408`)

On 518-deal multi-corpus benchmark vs Q-Plus's recorded play:
- Tricks/deal: **−0.542** (was −0.803 at pre-planner baseline)
- IMP/deal:    **−0.272** (was −0.610)
- Cumulative gain: +0.261 tricks/deal, +0.338 IMP/deal
- W/T/L: 151/162/205

Still ~−0.54 tricks/deal behind the commercial engine. The
bidder is competition-quality; cardplay needs the same depth
of textbook knowledge to deliver the tricks the bidder promises.

## Remaining gap: four architectural pieces

### 1. Entry counting (Phase 23 — in progress)
**Goal**: track top-winner cards per hand to enable plan decisions
that depend on whether we can reach the long hand.

**Implementation status**: SuitAnalysis extended with
`entries_declarer` and `entries_dummy`. `_plan_aware_unblock`
refined to skip when partner has other entries.

**Future**: extend to MID-DEAL entry tracking (cards already
played reduce the entry count); add explicit "blocked length"
detection that triggers the unblock without ambiguity.

### Items tried this iteration (Phases 25-27)

**Phase 25 — K-location inference + suit combinations**: Built
`_opp_who_bid_suit()` + `infer_k_with_rho()` helper. Gated the AQ
finesse rule on RHO-bid-the-suit inference. Result: still regressed
-0.067 tricks/deal vs Phase 23. Reason: biq-vs-biq benchmark
penalises declarer improvements (biq's defender matches biq's
declarer); the rule would help against external opponents but
doesn't show in our metric.

**Phase 26 — Dynamic top-winners**: Extended `_count_top_winners`
to accept `played_ranks`, so that after Ace is played K is
recognised as new boss. Result: regressed -0.428 IMP/deal. The
plan-aware unblock decisions shifted in the wrong direction mid-
deal — the static plan was actually the right input for the
single-shot unblock heuristic.

**Phase 27 — relax_inference=5**: Bumped HCP slack from 3 → 5 in
cardplay-mode auction inference. Result: regressed -0.243 IMP/deal.
Looser constraints accept more implausible MC samples, hurting
decision quality. **relax=3 is the sweet spot**, kept.

### 2. Suit-combination tables (Phase 24 — REGRESSED)
**Goal**: a lookup of common honor patterns → optimal play.

**Status**: First attempt (Phase 24, AQ-no-K finesse blind-lead)
regressed −0.081 tricks/deal on the benchmark. The rule fires
without knowing where the K sits — a critical missing input.
Suit-combination rules need:
- Inference of K location from auction (if RHO bid, K likely
  there) or from played cards.
- Or: only apply combos where both options (cash vs finesse)
  have similar probability.

**Initial patterns** (deferred until inference framework ready):
- **AQ vs no K**: finesse the Q (needs K-location signal).
- **AKJ vs Qxx**: finesse the J after cashing A.
- **AKQJ vs xxxx**: cash all 4 from one side, watch for blocks.
- **KQJ vs Axx**: duck the first round to opp's A; then run.
- **Axxx vs Kxxx**: cash A, then K, watch for 3-3 split.

**Future**: encode the next 20-30 patterns. Each pattern needs:
- Pattern matcher (combined ranks + per-hand distribution).
- Action sequence (lead from X, follow with Y, etc.).
- Order-of-suits priority (which combo to play first).

This is the biggest single piece of textbook knowledge. ETA
1-2 weeks of focused work to encode 50+ patterns with tests.

### 3. Endplay / squeeze recognition (DEFERRED)
**Goal**: detect end positions where forcing opp to lead
costs them a trick.

**Required state**:
- Per-trick history of who has played what suit.
- Inference: opp X is now stripped of suit Y.
- Decision: lead suit Z to force X to give up a trick.

**Examples to encode**:
- Throw-in: opp has only one suit left, force them to lead it.
- Simple squeeze: opp must keep one stopper in each of two
  suits; throw cards from the third suit until they break.
- Trump squeeze: similar but using trumps.

**ETA**: 2-3 weeks. Architecture needs explicit "trick-history
state tracker" — currently the planner re-derives from
`board.tricks` each call, which loses some context.

### 4. Better auction inference (DEFERRED)
**Goal**: match Q-Plus's looser-than-textbook bidding so MC
samples are accepted.

**Current state**: `cardplay_relax_inference = 3` widens HCP
ranges by ±3 and drops shape constraints. Helps but is blunt.

**Per-bid tuning options**:
- 1NT openings: 12-14 vs 15-17 vary by system; allow ±2.
- Stayman: can be 4-card or 5-card major search; loosen
  shape check.
- Overcalls: very wide HCP range vs textbook 8-15. Allow
  5-17 for jump overcalls.
- 2/1 GF responses: can be 13-21 HCP; loose.

**ETA**: 1 week. Needs per-bid hash table and a re-test
on the 518-deal benchmark to confirm fewer no-valid-samples
rejections without regressing solid inference.

## Phase 22 — signaling (DEFERRED)

Defender attitude (high spot = like) and count (high-low = even)
signals require a CONSUMER on partner's side to be useful.
Without that consumer (defender reading partner's signal to
decide future plays), signals are cosmetic and don't change
tricks. Implementation order:

1. Build signal-output (defender plays signal card on follow).
2. Build signal-input (defender on lead reads partner's
   previous play, decides switch vs continue).
3. Validate on benchmark.

Step 1 alone won't help; need 1+2 together. Defer until after
the architectural pieces above.

## Order of operations

1. **Phase 23 — entries** (in progress now).
2. **Phase 24 — finesse pattern** (drafted, awaiting wiring).
3. **Phase 24b — more patterns** (KQJ duck, AKJ finesse, etc.).
4. **Phase 22 — signals with consumer** (after entries + combos).
5. **Phase 26 — auction tuning** (in parallel with above).
6. **Phase 25 — endplays** (after everything else).

Each phase tested on the 10-corpus 518-deal benchmark at
mc-samples=40. Phase kept only if it shows clear gain.
