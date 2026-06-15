# Phase 3 scope — the SAYC/Precision "underbidding" leak is mostly COMPETITIVE

Scoped 2026-06-08 from the first clean closed-room baselines (biq −2.5/deal on
both systems). Phase-2 attribution flagged "underbidding" as #1; reading the
actual **auctions** (not just the final contracts, via `tools/show_underbids.py`
on the qss D1 grids) corrects the cause:

> **The losses look like underbids, but the root is COMPETITIVE bidding: when an
> opponent interferes or biq uses a 2-suited convention, biq loses its fit and
> lands in the wrong STRAIN and/or wrong LEVEL.** This single fault produces
> BOTH the under-bids (miss the fit/game) AND the over-bid tail (e.g. 3♥−5,
> 4♠−4 in the wrong strain). 6 of 8 sampled disaster auctions are competitive;
> only 2 are uncontested constructive. So the `gf_established`/drive-to-game work
> (uncontested, already live) is NOT the lever — competitive fit-finding is.

This realigns with [[project_biq_competitive_passivity]] /
[[plan_biq_competitive_rework]] and the known Michaels-dies-in-wrong-strain bug,
and it means matrix row **P3-F1 (competitive) is the confirmed #1 fix**, not a
drive-to-game run.

## Evidence (8 sampled disaster auctions)

### A. COMPETITIVE — lose the fit / wrong strain / pass with values (6)
| Board | biq did | should have | biq side holds | code target |
|---|---|---|---|---|
| RANDOM-019 | after partner's neg-dbl (shows ♥), rebid **3♣** | support the **9-card ♥ fit** → 4♥ | N 6♥ + S AJT♥, 20 HCP | responder-to-neg-double |
| RANDOM-043 | after own Michaels 2♦ (both majors), **passed** opp 3♣ | compete **3♥/4♥** (fit + values) | N 5-5 majors 16, S 3♥+4♥ | `_advance...michaels` |
| RANDOM-055 | 2♣ overcall of opp 1NT, then **2NT** | find the **8-card ♥ fit** → 4♥ | AKQJ 8-card ♥, 21 HCP | `_overcall_over_1nt` 6613 + advance |
| RANDOM-010 | 1♠-2♣-2♠-(x)-2NT, rebid **3♥ on a singleton** | rebid **spades** (8-fit) → 4♠ | E 5♠ + W 3♠, 23 HCP | `_overcaller_rebid` 7245 |
| RANDOM-025 | **passed** partner's 3♠ raise | bid **4♠** (11 HCP, 5♠, 10-card fit, LAW) | E KQ542 + W AJ983 | `_law_competitive_bid` 1955 |
| RANDOM-039 | **penalty-doubled** opp 2♦ (17 HCP, 4♥ support) | drive to **6♥** | 9-card ♥ fit, 29 HCP | double-vs-support judgment |

### B. UNCONTESTED constructive (2)
| Board | biq did | should have | code target |
|---|---|---|---|
| RANDOM-020 | **2NT rebid with a 1-5-6-1 freak** (singleton in partner's ♠ + own ♣) | show the 6-card ♦ suit → 3NT/5♦ | `_opener_rebid` 4376 / `_generic_responder_rebid` 5833 |
| RANDOM-004 | opener **signed off 4♠** over a limit raise, 15 HCP + 6♠ + 10-fit | slam try (cuebid/RKC) → 6♠ | opener raise-acceptance/slam path |

## Ranked fixes (do in order; #1 is most of the IMP)

1. **Competitive fit-finding (the big lever).** After partner's negative
   double / Michaels / 1NT-overcall convention, or a fit-showing raise: locate
   the implied/known fit and bid/support it to the LAW level. Rules:
   (a) don't PASS with a known 8+ fit and competitive values;
   (b) support the fit the convention/double IMPLIES rather than rebidding a
   side suit; (c) compete to the LAW level with 9-10 card fits.
   Targets: `_advance_partner_overcall` (7396), `_overcaller_rebid` (7245),
   the negative-double responder, `_law_competitive_bid` (1955), Michaels
   advance.
2. **Wrong-strain / singleton guard (also kills over-bids).** A `_sanity_wrap`
   net: never introduce/rebid a 3-card-or-shorter suit at the 3-level+ in a
   competitive auction when a known fit exists (RANDOM-010's 3♥-on-a-singleton).
   This is the SAME fix that prevents the over-bid tail (right strain ⇒ no
   3♥−5 / 4♠−4).
3. **Penalty-double vs support judgment** (RANDOM-039): with 4-card support and
   slam-ish values for partner's opened suit, do not convert to a low penalty
   double — show the fit.
4. **NT-rebid shape guard** (RANDOM-020, uncontested): don't rebid NT with a
   singleton in partner's suit or an unshown 6-card suit; bid the suit.
5. **Slam try after a fit-raise with extras** (RANDOM-004, uncontested):
   opener with a 6-card suit + extras opposite a limit/jump raise (≥9-card fit)
   should cuebid/RKC, not sign off in game.

## Why this also fixes the over-bid tail
The bimodal "under AND over compete" is ONE fault. RANDOM-010 is simultaneously
an over-bid (3♥−5) and a missed game (4♠) — both because biq chose the wrong
strain in competition. Fixes #1 and #2 (find the right strain/level) cut both
directions, so Phase-3 should show under- and over-bids dropping together.

## Validation
- Build a **competitive fit-finding truth-table** unit test from these 8
  auctions (assert the right call at biq's decision point) — the regression
  guard, like `test_gf_established.py`.
- Pre-screen with the M1 decision probe (0 Q-Plus cost), then the live A/B
  **P3-F1-B vs P3-BASE-SAYC** on `RNDS2.BDE` (and a Precision variant — this is
  system-agnostic). Acceptance: net IMP/deal improves AND the over-bid count
  does not rise (same bar as the gf rework).
- Keep every change **textbook** ([[feedback_biq_textbook]]): each is a named,
  standard treatment (negative-double fit support, Michaels advance, LAW
  competing, slam try) — not an eccentric IMP-chasing hack.
