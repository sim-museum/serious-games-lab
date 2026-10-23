# biq vs Q-Plus: status, 2026-09-28

## Where biq stands

biq plays 64-board teams matches against Q-Plus 17.1 over Q-NET. Both rooms
play the same cards; the score is in IMPs (0-24 per deal, most of a match's
result comes from a handful of game/slam swings of ~10 IMPs each).

A few days ago biq lost about **3 IMPs per deal**. With SAYC it now loses
about **1.5**. Q-Plus is still stronger, but the gap has roughly halved.

## All live runs

| Run | Deck | biq version | IMPs | per deal |
|---|---|---|---|---|
| 3 | RUN2 | old rules | | −2.89 |
| 4 | FRESH64B | rules, first fixes | | −0.31 |
| 5 | FRESH64C | rules | | −2.47 |
| 6 | FRESH64D | rules | | −3.97 |
| 7 | FRESH64E | first hybrid | | −2.29 |
| 8 | FRESH64E | rules only | | −2.08 |
| 9 | FRESH64F | hybrid | | −2.08 |
| 10 | FRESH64G | revised hybrid | −149 | −2.33 |
| 11 | FRESH64G | rules only | −176 | −2.75 |
| 12 | FRESH64H | hybrid + batch-1 rule fixes + Q-Plus opponent model | −107 | −1.67 |
| 13 | FRESH64H | rules only | −177 | −2.77 |
| 14 | FRESH64H | hybrid, Precision (63 deals) | −236 | −3.75 |
| 15 | FRESH64I | hybrid | −93 | **−1.45** |
| 16 | FRESH64I | rules only | −109 | −1.70 |
| 17 | FRESH64I | hybrid, Precision (deals 2-64) | −109 | −1.73 |

One 64-deal match has a standard error of about 0.8 IMP/deal, so single runs
are noisy. The reliable comparison is a **paired** run: hybrid and rules-only
on the same deck, where Q-Plus's own room is identical (checked: 64/64 on
decks H and I).

**Simulation gain (hybrid minus rules-only, paired):**

| Deck | IMPs | per deal |
|---|---|---|
| E (first hybrid) | | −0.15 |
| G | +18 | +0.28 |
| H | +77 | +1.20 (SE 0.59) |
| I | +20 | +0.31 (SE 0.58) |

By kind of simulation call (decks G/H/I): **pass** instead of the rules' call
21 deals **+84**; **double** 13 deals +1; other bid 8 deals −6.

## What was built

**Hybrid bidding** (`backend/bid_sim.py`): at judgment points, sample the
hidden hands consistent with the auction, finish the auction each way with
the rule bidder, score double-dummy (with competent-opponent scoring), and
replace the rule's call only when another is clearly better. Conventions and
slam sequences stay with the rules. Simulated opening leads
(`backend/lead_sim.py`) and auction-aware card-play sampling.

**Learning from Q-Plus's own records.** Q-Plus logs every deal of both rooms
with all four hands and every card (`DATA/LOG/*.bdl` open room, `*.cdl`
closed room; `.qss` score sheets).
- `tools/qplus_auction_mine.py`: replays each Q-Plus call through biq's rules
  and scores the disagreements. `--live` finds the first call where the two
  rooms' auctions part, i.e. biq's real call against Q-Plus's.
- `backend/qplus_model.py` + `tools/qplus_profile_build.py`: what Q-Plus's
  calls show (HCP and suit-length ranges per situation), used to read Q-Plus
  opponents (`BIQ_OPP_MODEL=qplus`, set by the match client). 469 situation
  profiles from 8,235 Q-Plus calls on 607 deals; 60% of calls covered.
  SAYC data only (Precision files are filtered out).
- `tools/play_audit.py`: card-by-card double-dummy audit of both rooms.
- `tools/qplus_logs_to_qss.py`: rebuilds a score sheet from Q-Plus's room logs
  when the scoring table is empty or a match didn't finish.

**Harness** (`tools/biq_match.py`): runs a match with no clicking; survives
Q-Plus re-dealing a board; `--rules-only` for paired runs.

## Fixes since the last status

- Rule fixes found by the miner: Texas transfer completed (opener used to
  pass 4♦); 1NT with 5-3-3-2 and a five-card minor at 14 HCP; weak jump
  overcalls sized to vulnerability and level; opener's competitive rebid of a
  six-card suit needs 15+ HCP or seven cards; 1M-1NT-2m preference; a weak
  four-card fit passes instead of being turned into a 3-level raise.
- Illegal call that hung the Precision run (North doubled partner's own 2♦):
  doubles and redoubles are now legal only against the opponents' call, and
  the bidder can never output an illegal call. The Precision 1♣-response rule
  now fires only on responder's first answer.
- Simulation doubles: offered only where the rules would pass. Doubles that
  replaced the rules' own bid lost 22 IMPs on four FRESH64I deals (doubling the
  opponents' 4-level sacrifice instead of bidding a making 4♠). Not yet tested
  live.
- Client robustness: ignores calls after the auction ended, recovers the
  contract if play starts on an unfinished auction.

Regression tests: `test_qplus_match_fixes.py` (81 checks), `test_bid_sim.py`,
`test_competitive_fit.py`, all passing except the known RANDOM-025 case.

## What still loses

**Bidding** is still most of the loss (60-70% of each match). On first
divergences in the live matches, biq's calls cost about 1 IMP per deal before
the batch-1 fixes. What remains is spread over many small rule groups (4-9
deals each), so further fixes need Q-Plus's data to show a consistent
pattern first.

**Card play.** Over all matches biq gives away about 1.1 double-dummy tricks
per deal as declarer and 1.1 as defender; Q-Plus about 0.56 in each role.
Opening leads are equal. The gap is in later leads, discards, ruffs and
second-hand play. Tested and rejected:
- More sampled layouts (10 → 20 → 30): no improvement.
- "Second hand low" bonus: 35 vs 32 tricks given away on 58 deals, not
  adopted.
About half of biq's costly cards are systematic (the engine repeats them),
half are sampling luck.

**Precision** has had far less rule work than SAYC. Two matches so far
(−3.75 and −1.73 per deal); its biggest loss is not competing (−109 on
FRESH64H).

## Expected next results

- Hybrid SAYC: about −1.3 per deal; a single match can land anywhere from
  about −0.5 to −2.0.
- Hybrid Precision: about −2 per deal, with a wider range.

## Next steps

1. Paired runs on a fresh deck (FRESH64J): hybrid, then `--rules-only`. Tests
   the doubles change and firms up the simulation's measured gain.
2. After every match: rebuild the Q-Plus profiles, re-run
   `qplus_auction_mine.py` (both modes) and `play_audit.py`.
3. Next bidding batch only where Q-Plus's data show a consistent pattern.
4. Card play: find the systematic defensive errors; any change gets a large
   offline test before a live run.
5. Precision: a few more Q-Plus Precision matches, then the same mining.

## Running a match

From `FRI/bridgeIQ/bridgeIQ`:

1. `python3 tools/biq_match.py --launch` (starts Q-Plus).
2. In Q-Plus: File ▸ Open Own deals ▸ the deck, set up the match (bridge
   server, N/S Extern), then press Enter in the terminal.
3. After the last deal: View ▸ View scoring table ▸ Save and send.
4. Same deck again with `--rules-only` for the paired comparison.

Start the deck at board 1: a false start that uses a board leaves the deck one
deal short, and Q-Plus shows "ran out of deals" at the end. Don't edit
`backend/` while a match is running (the client loads some code lazily);
experiment in a scratch copy.

## Files

- Score sheets: `tools/runs/results/run*.qss`; client logs:
  `tools/runs/ab/run*_{N,S}.log`; miner and audit reports: `tools/runs/mine/`.
  All under `tools/runs/`, which git ignores.
- Decks: Q-Plus `DATA/OWN-DEALS/FRESH64B-I.BDE` (all distinct).
- Code: branch `biq-qplus-strength` in `~/sgl` (5 commits, not pushed, not
  merged into `main`).
- Detailed history: project `CLAUDE.md`, STATUS sections.
