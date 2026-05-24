# Exemplar diff analysis (2026-05-23)

Generated 100 fresh deals (20 per system) biased toward each
system's signature conventions. User ran them in Q-Plus; we
compared against bridgeIQ on the same deals.

## Honest baseline

| System | Auction match | Contract match | Card play (contract-matching subset) |
|---|---|---|---|
| SAYC | 2/19 (10%) | 4/19 (21%) | 81/208 (38%) |
| TwoOverOne | 0/20 (0%) | 2/20 (10%) | 39/104 (37%) |
| StandardAcol | 1/19 (5%) | 4/19 (21%) | 82/208 (39%) |
| StandardFrench | 2/20 (10%) | 4/20 (20%) | 84/208 (40%) |
| Precision90M | 0/16 (0%) | 1/16 (6%) | 25/52 (48%) |
| **Aggregate** | **5/94 (5%)** | **15/94 (15%)** | **311/780 (39%)** |

**The 40% match rate on the seed=42 corpus was almost entirely
overfitting.** Fresh corpus shows 5% / 15% — the real rates.

Card play stayed close to the seed=42 baseline (38-48%) — the
card-play tie-break is not overfit.

## Why this much overfitting in bidding

The 14 commits I made tuning bidder to seed=42 each fixed a
specific board's auction by adjusting a threshold or adding a
narrow branch. Many of those changes:

* Tightened gates with seed=42-specific HCP thresholds.
* Added branches for shapes that happened to come up.
* Drove specific paths that matched Q-Plus's auction on that
  one deal.

Each individual change was reasonable bridge logic, but the
combined effect was a bidder tuned to the seed=42 hands.

## What's NOT overfit

* The system-flag mechanics (4cM vs 5cM, weak NT vs strong
  NT, 2/1 GF detection, etc.) — these are correct system
  differentiators, not seed=42 artifacts.
* The sanity wrapper — 0 illegal bids escape on the fresh
  corpus same as before.
* Card-play at 39% — stable across corpora.
* Pipeline robustness — 0 exceptions across 94 deals.

## What I observe in the diffs (without fixing)

Common patterns where bridgeIQ differs from Q-Plus:

1. **bridgeIQ opener passes after partner's response.**
   2/1 board 1: `1D-P-2D-P-P` vs Q-Plus's
   `1D-P-2D-P-2H-P-2N-P-3N`. Opener doesn't game-try.

2. **bridgeIQ doesn't open 1NT with 5-card major.**
   SAYC board 13: Q-Plus opens 1NT (E has 14 HCP + 5cS +
   5-3-3-2); bridgeIQ opens 1S. The `B-1NT-style.any-5-spade`
   flag is honored but the HCP gate currently requires 15+.

3. **bridgeIQ doesn't compete after opp's overcall + partner's
   raise.** Several boards. Need "law of total tricks" push
   when fit is known.

4. **bridgeIQ doesn't reopen with X in 4th seat.** Acol board
   9 (in seed=42) was the same pattern.

5. **bridgeIQ uses different opening seat.** Sometimes
   dealer's hand is too weak to open but a later seat could —
   bridgeIQ has 4-pass cases where Q-Plus has someone open
   borderline.

## What I learned about Q-Plus

Important caveat for the user's "don't mimic Q-Plus when it
loses" guidance: Q-Plus actually goes down quite a lot in
the exemplar corpus. Examples from 2/1 session:

| Board | Contract | Result |
|---|---|---|
| 1 | 3NT-N | = (made) |
| 5 | 3♦X-N | -2 = **−500** |
| 7 | 6♣-E | -1 = **−50** (overreach slam) |
| 8 | 4♠X-S | -1 = **−200** |
| 9 | 5♦X-S | -3 = **−500** (terrible) |
| 11 | 6NT-N | = (slam made!) |
| 12 | 3NT-E | -2 = **−200** |
| 16 | 5♣X-W | -3 = **−800** (bad sacrifice) |
| 17 | 3NT-W | -3 = **−150** |

In several boards bridgeIQ's stopping short would beat
Q-Plus's overbid by 200-500 points per board.

## Recommendation

**Don't make further bidder changes** to chase exact-match
rates on this corpus. The realistic improvement path is:

1. **Identify principled rules that are systematically
   underbid in bridgeIQ** (game tries after simple raises,
   reopening doubles, balancing).
2. **Implement those rules across the whole bidder** — not
   gated on specific HCP / shape combos that happened to come
   up in any single corpus.
3. **Re-test against a NEW set of deals** to confirm the
   improvements generalize.

The current 5% / 15% baseline is the honest "shipping" number.
Together with stable card-play at 39%, the engine is producing
*defensible* but not *Q-Plus-matching* auctions across all 5
systems. For a teaching tool, defensible is enough.
