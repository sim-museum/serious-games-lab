# Scope — single-dummy cardplay engine for biq

Status: SCOPING (2026-06-09). No code committed beyond the measurement
harness. This document decides whether to build, what to build, and the
gates that kill it early if the prize isn't there.

## TL;DR / honest prize bound (read this first)

biq's current cardplay is **PIMC** (Perfect-Information Monte Carlo): sample
N hidden layouts consistent with the auction + play, double-dummy-solve each
with DDS, average the per-card trick counts, play the max. This has two
*known, named* flaws (Frank & Basin 1998): **strategy fusion** and
**non-locality**. A single-dummy engine fixes them. That is the theory.

The catch, from this session's fixability audit (`cardplay_eval.py
--audit-declarer / --audit-defense`): **biq's PIMC is already near the
double-dummy ceiling on average** — declarer ~10–15% of its 0.75 tr/deal
leak is single-dummy-fixable, defense only ~3% of 0.93. A single-dummy
engine *cannot exceed* the double-dummy trick count (perfect info is the
upper bound); it can only recover the part of the gap that PIMC throws away
through strategy fusion. That part is the **~10% two-way-guess class** plus
some discard/timing — realistically **~0.1 tr/deal on declarer**, the same
modest order as the vacant-places fix already shipped (d750922).

So the honest framing is: this is the *theoretically correct* next step and
the only thing that can move biq off the PIMC ceiling, **but the expected
payoff is modest and uncertain, and biq's PIMC is a STRONG PIMC** (good
sampling constraints already), which is exactly the regime where alpha-mu's
published gains shrink. **Therefore Phase 0 (a bounded prize-measuring
experiment) gates everything.** Do not build the full engine before Phase 0
clears its bar.

## The two PIMC flaws, with biq-specific evidence

1. **Strategy fusion.** In every sampled world DDS plays the *rest of the
   hand* with full knowledge of that world. So biq's model of its own future
   self is omniscient — it assumes it will always guess right later. Effect:
   (a) gathering information has **zero value** (you already "know"), so biq
   never delays a two-way guess to take a count; (b) cards whose payoff hinges
   on a later guess are over-credited. Evidence: RANDOM-049 — biq cashed AK
   ("nine-never") trick 2 instead of cashing side suits for a count then
   finessing the marked 4-1; Q-Plus deferred and finessed.
2. **Non-locality.** In every world the *opponents* also play double-dummy —
   they "see" biq's cards. So biq's defenders look superhuman; declarer plays
   too much for the worst case and under-exploits the defenders' real
   uncertainty. Effect: biq leaves tricks that a real opponent would give it.

Both are inherent to averaging independent perfect-information solves. No
amount of better *sampling* (the vacant-places work, #1) fixes them — that
improves the world distribution; these are about how each world is solved.

## Approach survey

| Approach | What it is | Fixes fusion? | Reuses biq infra | Cost | Risk |
|---|---|---|---|---|---|
| **Alpha-mu** (Cazenave & Ventos 2017–19) | depth-limited search; player must pick ONE move across all indistinguishable worlds; Pareto front of outcome-vectors; DDS at the frontier | **Yes** (the designed-for-bridge fix) | High — reuses MC world-sampler + `dds.solve` as leaf oracle | Med–High (DDS at many nodes; param M=worlds, depth) | Med — proven for bridge *declarer*; defense less so |
| **ISMCTS** (Cowling 2012) | MCTS over information sets; one determinization per iteration, shared tree → consistent strategy | Yes | Med — new tree search, sampler reused, DDS optional for rollouts | High (many iterations) | Higher — general, less proven for bridge declarer, tuning-heavy |
| **Heuristic deferral** | rule: detect a two-way guess + a safe count-gathering line, play the count first | Partially, narrowly | Low — rules in `cardplay_planner` | Low | Med — misfire risk (cf. the off-suit-discard override), low ceiling |
| **Single-dummy rollout** | in each world, play forward with a *policy* (not DDS) so future self isn't omniscient | Partially | Med | Med | High — need a decent policy; weak without one |

## Recommended: TARGETED alpha-mu (hybrid)

Keep PIMC as the default fast path. Invoke alpha-mu **only at detected
critical decision nodes** — points where strategy fusion actually bites:
a broachable two-way guess (the `--audit-declarer` "deferrable" detector
already finds these) or a close top-two PIMC decision. This caps the cost
(alpha-mu is expensive) to the handful of tricks per deal where it can pay,
and bounds the blast radius for regressions. Alpha-mu (not ISMCTS) because
it is the published bridge fix, it's a *bounded* search (depth + M), and it
slots onto the two pieces biq already has:
- the **MC world-sampler** (lift out of `engine.py` `get_mc_card_play`
  ~lines 779–890 into a reusable `sample_worlds(board, seat, k)`),
- **`dds.solve(strain_i, leader, trick52, [world_pbn], solutions=1)`** as the
  leaf evaluator at the search horizon (one world at a time).

The alpha-mu logic itself (alternating MAX/MIN nodes, outcome-vector
propagation, Pareto-front pruning, "one move for all worlds at MAX") is new
code — a self-contained `backend/alphamu.py` (~200–400 lines), independent of
the GUI and the bidder, A/B-able in an isolated worktree like every cardplay
change.

## Build plan with kill-gates (validation FIRST, per project doctrine)

**Phase 0 — bound the prize (DO THIS BEFORE ANYTHING ELSE).**
Build a *minimal* consistent-strategy probe: on the `--audit-declarer`
deferrable boards + the RANDOM-049/-037/-009 regression set, for each
critical node enumerate biq's top-2 PIMC moves and evaluate each under a
*consistent* policy across the sampled worlds (cheap: 2-ply, M≈8–16, DDS
leaves) — i.e. force the same move in every world and average, instead of
per-world-optimal. Measure tricks recovered vs PIMC.
GATE: if it recovers **≥0.10 tr/deal on declarer** (or clearly fixes the
named regression boards), proceed. If <0.05, **STOP** — the prize isn't
there; accept the ceiling, bank vacant-places, write it up. Effort: ~1–2 days.

**Phase 1 — alpha-mu core (declarer).** Implement `backend/alphamu.py`:
iterative deepening to depth D (start 2 tricks), MAX = biq seat, MIN =
defenders, outcome-vectors over M worlds, Pareto pruning, DDS frontier.
Unit-test on constructed two-way-guess deals (build a `tools/twoway_probe`
fixture set from the audit's broach boards). Effort: ~3–5 days.

**Phase 2 — targeted wiring + A/B.** Invoke alpha-mu from `get_mc_card_play`
only at critical nodes (reuse the deferrable-node detector); PIMC elsewhere.
A/B vs baseline d750922 with `cardplay_eval --audit-declarer` and the split
(declarer leak) at 200+ deals. GATE: net positive declarer, no defense
regression, acceptable runtime. Effort: ~2–3 days.

**Phase 3 — cost/quality tuning.** Sweep M, depth, critical-node trigger
threshold; measure tricks-gained vs wall-clock; confirm on the Q-Plus
regression boards (`cardplay_vs_qplus`). Effort: ~2–3 days.

**Phase 4 (STRETCH) — defense.** Alpha-mu with biq as a defender (hidden
partner). Harder (partner cooperation, signals); only if Phases 1–3 paid off
*and* the defense prize re-measures as worthwhile (currently ~3% fixable, so
likely skip). Effort: open-ended.

## Effort / risk / kill criteria

- **Effort:** ~2–3 focused weeks to a tuned declarer engine (Phases 0–3),
  defense extra and probably not worth it.
- **Top risk:** the prize is genuinely small (audit says ~0.1 tr/deal) — Phase
  0 exists to fail fast before the weeks are spent.
- **Perf risk:** alpha-mu runs DDS at many nodes; targeted invocation +
  small M/depth mitigate, but live-play latency must be checked (Phase 2 gate).
- **Architecture risk:** LOW for the GUI/bidder — it's an additive
  `alphamu.py` behind `get_mc_card_play`, default-off, isolated-worktree
  A/B'd. The proven measurement harness (`cardplay_eval`) already exists.
- **Kill criteria:** Phase 0 <0.05 tr/deal; or Phase 2 net-negative / too slow;
  or defense (Phase 4) re-measures <0.05.

## Reconciliation with "where does −2.6 come from?"

This engine targets the strategy-fusion slice of the *cardplay* gap. It does
NOT by itself explain the full −2.6 IMP/deal vs Q-Plus (cardplay-technique is
near-ceiling; bidding is DD-neutral). If Phase 0 shows a small prize, that is
itself evidence that the −2.6 lives elsewhere (bidding-in-practice or baseline
noise) — which becomes the next question. See
[[project_biq_cardplay_is_the_leak]], [[plan_biq_cardplay_engine]].
