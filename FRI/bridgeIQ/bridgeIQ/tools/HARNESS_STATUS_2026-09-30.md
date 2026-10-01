# biq vs Q-Plus: status, 2026-09-30

Goal of this round: make biq stronger against Q-Plus in both SAYC and
Precision, and make it neither weak nor wacky as a partner or opponent for a
human (calls and cards that go against both textbook practice and Q-Plus,
and cost).

No live match was played in this round. Everything below is offline work on
the 17 recorded matches (894 deals in runs 4-17) plus double-dummy teams
A/B tests. The live check is the next step (decks are ready, see the end).

## The biggest find: alerts never cross Q-NET

Q-NET sends calls with no alert flag. biq's own calls keep their alert in
its own auction record, but **partner's calls arrive unalerted**, and the
rules recognise many conventions by their alert: strong 1C (Precision),
strong 2C, Jacoby 2NT, splinters, Michaels, Truscott ... So live, biq often
misread its partner. The offline A/B kept the alerts, so this never showed
up there.

- `native_bidder._mark_system_alerts` now rebuilds the alert flag on every
  call of biq's own side: a call is alerted when biq's own rules alert it
  in that position (random hands dealt to that seat with a fixed seed per
  position and bid by the rules; the majority of hands making that call
  decides). It is cached, and it runs inside `decide_bid`.
  Opponents' calls are left alone.
- `tools/bidder_teams_ab.py` now strips alerts from other seats' calls by
  default (the wire view). `--keep-alerts` restores the old behaviour.
- The hybrid simulation keeps seeing the wire view (its trigger was tuned
  and measured live that way) but no longer runs when partner's call is
  forcing.

## Precision

- **1C-1NT (8-13 balanced) never set up a game force**: the context code
  skipped NT bids before its game-force check. 1C-1NT-2S-3S was passed
  with 19 + 9 HCP on two boards (-10 IMP each). Fixed in
  `auction_context.derive_context` (with the alert fix, partner's unalerted
  1C is now also known to be strong).
- After 1C-(they bid)-P-(P)-partner's suit, responder raised the
  artificial "clubs" or passed with support. Now it raises partner's real
  suit with three cards and 5+ HCP.
- 1C-2D: an unbalanced opener with four hearts now shows them (the 4-4 fit
  was lost to a 2NT rebid).
- 2C (11-15, six clubs)-(overcall): four clubs and a weak hand jump to 4C.
- 1NT-(2S)-P-(P)-X: a weak hand with a singleton spade and a five-card suit
  runs (2Sx made +2 for -14).

Precision live miner (runs 14, 17): 61 first-divergence boards, -249 real
IMPs; the 1C game-force bug was the largest single item.

## SAYC, from the miner and the wacky audit (all pinned as regression cases)

Weak (too passive):
- Weak twos and preempts on Q-J / K-J headed suits with values outside
  (three openings Q-Plus made, biq passed).
- 1m-(X): 6-9 HCP now bids a four-card major / long minor (was a silent
  pass; -11 IMP).
- 1M-(X): raise light, jump with four trumps.
- 1H-(2S): four trumps and a singleton raise to 3H.
- 1D-(1S): a five-card minor with 10+ bids it (forcing); 13+ cue-bids.
- 1M-1NT-2x: responder with 11-12 invites (2NT / jump preference); opener
  with 15+ accepts the invitation.
- Lebensohl 1NT-(2D)-3D: opener now answers the Stayman cue-bid (was a
  "raise" to 4D).
- Response to a weak two: a six-card major with 13+ bids game, a
  five-card major with 11+ bids it.
- Overcalls: 4H over 3S with a QJT765 suit and 14 HCP; 1H on KQJ75 with 6
  HCP non-vul; a seven-card weak jump on texture; a light takeout double of
  1m with 10 HCP, short in it, both majors.
- 1C-P-P-X: opener rebids a six-card suit. Four-card support for partner's
  rebid minor after they compete: 4m/5m.
- 2/1 responder with 21 HCP bids 6NT (missed 33-point slam three times).

Wacky (against textbook and Q-Plus):
- No takeout double holding four cards in a suit THEY bid (1C-P-1H-X with
  four hearts, 1H-P-1S-X with four spades; -14 and -11).
- QJT74 + 12 HCP overcalls 1S instead of doubling.
- 20 HCP over a weak two doubles first instead of a simple overcall
  (passed out with game cold).
- 1C-1D (not 2NT) with an unbalanced hand and long diamonds.
- No flat 4-4 seven-count Landy balance (vulnerable, -12).
- 2C-(2S): a weak hand passes (waiting); the "waiting 2D" used to be
  legalised into a natural 3D. More generally a pass after an opponent's
  call never drops partner's force (partner bids again).
- Never pass partner's cue-bid (1H-4D splinter-4S was passed: 4S in a 4-1
  fit). Sign off in the trump suit instead.
- Five small trumps and 2 HCP no longer leave partner's takeout double in.

## Wacky audit: `tools/wacky_audit.py`

For every biq call and card in the recorded matches it lists the ones that
differ from Q-Plus (same spot in the closed room, or Q-Plus's profile for
that call), break a named textbook check, and cost (5+ IMPs for a call, a
double-dummy trick that changes the contract's result for a card). It also
lists "weak" calls (missed game/slam, sold out with a fit) at the first
divergence, and whether the CURRENT rules still make each call.
Reports: `tools/runs/mine/wacky_report.txt` (with cards),
`wacky_bid_after.txt` (bidding, after this round's fixes).

Results over 894 deals (runs 4-17):
- Wacky calls: 1.1 per 100 deals (-81 IMPs). The current code still makes
  4 of the 10 (two are judgement calls, one is a false positive: Texas).
- Weak calls: 3.8 per 100 deals (-320 IMPs), the larger problem. The
  current code still makes 19 of the 34 first-divergence calls (several
  of the rest were fixed in a later call of the same auction).
- Wacky cards: 2.0 per 100 deals; 24 result-changing cards per 100 deals,
  almost all with no textbook rule broken.

## Card play (evening session, while the --previous matches ran)

New instrument: `tools/play_replay_bench.py`. `extract` takes every biq
card decision from the recorded matches where the choice mattered
double-dummy (658 where biq lost tricks live + 1589 controls where it did
not; tools/runs/mine/replay_positions.jsonl), `bench` re-asks the current
engine in each real position (real auction, Q-Plus opponents' model,
fixed sampler seed) and scores it. Defence is deterministic; declarer
varies by ~2 tricks run to run (time budget).

Found and fixed (all now default on; env switches to turn them off):
- **Honour "signals"** (`BIQ_SIGNAL_SAFE`): with no spot card to spend,
  the signal routine played the HONOUR (K from K-T under declarer's ace,
  K from K-J third hand): 22 such cards in the matches. Now the lowest
  card; and the can't-win "pure signal" shortcut only applies to holdings
  of 8 and below (9s, tens and honours go to the search, which still breaks
  ties by signal).
- **Touching cards searched once** (`BIQ_AMU_COLLAPSE`): `_collapse` existed
  but was never called, so alpha-mu branched on every card of KQJ etc.
- **Best-first root search** (`BIQ_AMU_ORDER`): the 12 s budget ran out on
  ~120 of 2247 decisions, and the cards never evaluated were simply the
  last in suit order. Now every candidate gets a one-trick score first
  (<= 1/3 of the budget) and the full search runs best-first.

Replay bench, 2247 positions, DD tricks lost: baseline 510; safe signals
-10 (defence follows -16); collapse -14 (declarer leads); all three **455
(-55, -11%; 63 positions better, 17 worse)** and 20% faster per card.
Rejected: 20 sampled layouts (-45, more variance, slower, NT defence leads
worse); signal margin 0.05 (-9 more, but a less reliable signaller for a
human partner; kept 0.15).
Full hands on 31 fresh deals vs a double-dummy opponent: declarer 24 -> 16
tricks lost, defence 21 -> 20.

What is left is single-dummy judgement (which suit to switch to on
defence, declarer's line), not textbook violations.

### Earlier analysis

The card-play gap is real but not "wacky": biq gives away about twice
Q-Plus's double-dummy tricks, mostly by choosing the wrong suit to lead in
mid-hand (defence and declarer), and only ~2 cards per 100 deals break a
textbook rule. A check of "cash your setting tricks" found 4 cases in 894
deals. No card-play change was made this round; a systematic fix needs
the engine (sampling / alpha-mu), not rules. `tools/lead_choice_study.py`
classifies every mid-hand lead of both programs (suit history, right suit
/ wrong suit, cash available): biq's extra losses are spread over many
kinds of wrong-suit leads, which is why no single rule fixes them.

## Measured (double-dummy teams A/B, new vs the committed bidder, wire view)

| Round | Seed | Boards / system | SAYC IMP/bd | Precision IMP/bd |
|---|---|---|---|---|
| alerts only | 31 | 800 | +0.01 (SE 0.02) | +0.02 (SE 0.04) |
| + batch 1 | 41 | 800 | +0.01 (SE 0.04) | +0.08 (SE 0.05) |
| + batch 2 | 51 | 800 | -0.03 (SE 0.05) | +0.07 (SE 0.05) |
| + batch 3 (all) | 61 | 1200 | **+0.18 (SE 0.05)** | **+0.19 (SE 0.05)** |
| + small fix | 71 | 1200 | -0.05 (robust -0.15) | +0.08 (robust +0.01) |
| after pruning (below) | 71 | 1200 | +0.03 (robust 0.00) | |
| **after pruning, held out** | **81** | **1200** | **+0.17 (robust +0.07)** | **+0.16 (robust +0.10)** |

Pruning: an attribution of every A/B swing to the first call where new and
old differ showed some of the new "less passive" rules losing under the
robust judge on two seeds. Removed or narrowed: light takeout double,
thin 7-card preempts, 4m/5m over their bid, cue-bid over an overcall; the
preemptive raise over 1M-(X) now needs shortness, natural bids over
1m-(X) need 7+ HCP, the forcing new minor over an overcall needs 11+ at
the 2-level, 1C-1D needs six diamonds (or five with shortness) and <=12.
Seed 81 was never used to choose rules.

Phantom slams unchanged; "doubled the opponents into a make" down. The
robust judge (opponents reply competently) is smaller but positive
(seed 61: SAYC +0.02, Precision +0.10). biq-vs-biq DD understates the live
effect of the alert fix: both sides of the A/B see the same wire auctions.

Regression tests: `test_qplus_match_fixes.py` 113 checks, all passing;
`test_bid_sim.py`, `test_gf_established.py`, `test_bidding_systems.py`
pass. `test_competitive_fit.py` RANDOM-025 (4S over a competitive 3S
raise) fails, but it fails at the committed HEAD too.

## biq_match.py --version (A/B of two biq versions vs Q-Plus)

`--version latest` (default) = current code; `--version previous` = the
version before it (HEAD while biq's code has uncommitted changes, else the
state before the last commit that touched backend/ or the client); any git
ref works too. Non-latest versions are exported once to
tools/runs/versions/<commit>/ and the clients run from there, so editing
backend/ does not disturb a match on an older version. `--list-versions`
shows both with their bidder fingerprints (the client logs the same
fingerprint). Today: previous = b4d9ccd704 (fp eb54410fe8, played runs
15-17); latest = working tree.

## Next: live check (needs you at Q-Plus)

Fresh decks, never used for tuning, are in Q-Plus OWN-DEALS:
`FRESH64J.BDE` (seed 260930) and `FRESH64K.BDE` (seed 260931).

1. SAYC hybrid on FRESH64J: `python3 tools/biq_match.py --launch`, open
   the deck, set up the match (N/S Extern), Enter.
2. Same deck `--rules-only` (paired).
3. Precision hybrid on FRESH64K (Q-Plus N/S system = Precision).
4. After each: `tools/wacky_audit.py` and `tools/qplus_auction_mine.py
   --live` (add `--system P-P90M-A` for Precision files).

Previous bests were -1.45 (SAYC hybrid) and -1.73 (Precision) per deal.
One 64-deal match has a standard error of about 0.8 per deal, so judge the
change by the paired comparison and by the wacky audit counts, not by one
score.

All changes are uncommitted on branch `biq-qplus-strength`.

## Live A/B, SAYC, 2026-09-30/10-01 (runs 18 and 19)

| Run | Version | Deck | IMPs | per deal |
|---|---|---|---|---|
| 18 | previous (b4d9ccd704, bidder eb54410fe8) | FRESH64K (= G!) | -116 | -1.81 |
| 19 | latest (working tree, bidder a59d51ddf4) | FRESH64K (= G!) | -74 | -1.16 |

Run 19 was played open room only; `tools/qss_merge_closed.py` scored it
against run 18's closed room (the two sheets' deals checked identical).
Run 18's closed room matched runs 10/11 on all 64 boards too.

**Paired latest - previous: +55 IMP (+0.86/deal, SE 0.57), 39 boards
differ.** Bidding +29 on 11 boards, card play +26 on 28 boards.
- Bidding wins: QJT74 overcalls 1S (+8), 4H over partner's weak 2D with
  six hearts and 13 HCP (+8), opener leaves 1NT (+8), balancing 1NT (+6),
  +6, +5. Loss: RANDOM-013 -15 (opener's free 2C rebid let them find 4H).
- Card play, DD tricks given away per deal (play_audit): declarer 0.76 ->
  0.65 (Q-Plus 0.67 on the same deals), defender 0.91 -> 0.81 (Q-Plus 0.56).
  The big play swings (-12 -12 / +17 +10) are mostly Q-Plus's own play and
  one opening lead (unchanged code); two real new-engine errors (a declarer
  lead at trick 10, a defensive lead at trick 11).
- Wacky audit: no wacky calls or cards in either run; weak calls 3 per run
  (RANDOM-012 17 HCP 5-4 no jump shift, RANDOM-010 16 HCP 5 spades in the
  balancing seat, RANDOM-027 sold out), all three judgement spots.

**Caveat — not a held-out deck.** FRESH64J and FRESH64K were generated
with seeds 260930/260931, already used for F and G, so K was byte-identical
to FRESH64G, whose runs 10/11 fed the miner and the replay bench. Directly
tuned from G boards: RANDOM-009 (+8 here) and RANDOM-056 (+1). Without
those, about +47 (+0.73/deal); the card-play fixes are general but 321 of
the 2247 replay positions came from G.
Fixed: gen_test_deck.py now refuses to write a deck that shares any deal
with another deck in OWN-DEALS and lists the seeds already used. J and K
were deleted (exact copies of F and G). New verified-fresh decks:
**FRESH64L** (seed 261001) and **FRESH64M** (seed 261002).

Next: the Precision pair on FRESH64L (previous, then latest open room only),
and a truly held-out SAYC pair on FRESH64M.

## All five systems, offline (2026-10-01) — tools/system_matrix.py

No Q-Plus. Every deal is bid at 25 tables: each (N/S system, E/W system)
pair of SAYC, Precision90M, StandardAcol, StandardFrench, TwoOverOne, biq's
rule bidder at all four seats (wire view), contracts scored double-dummy
and against par. `report` gives the teams matrix and per-system
pathologies; `report --vs SAYC` charges each board's IMP difference to the
first call where system X's auction leaves SAYC's (same seat, same
opponents) — the Q-Plus miner's method with SAYC as the reference.
Double-dummy, not card play: biq's play costs every system the same and is
far too slow for 30,000 auctions.

Starting matrix (1200 deals, seed 9001), mean IMP/deal vs the other four:
SAYC +0.19, 2/1 +0.09, French -0.01, Precision -0.12, Acol -0.15.

Fixed (pinned as M-* cases in test_qplus_match_fixes.py, 123 checks):
- Precision: NAMYATS 4C/4D was passed (4C -7) -> partner completes; the 2D
  three-suiter doubled was "raised" as a weak two (3Dx -5); 1D-2NT (forcing)
  was passed; Bergen 3C/3D read as clubs/diamonds (6C).
- 2/1 (and Precision): the inverted 1m-3m (weak) read as the strong raise
  (6D off a key); opener's rebid after the inverted 2m (balanced -> NT,
  unbalanced -> show a side suit).
- French: 1NT-2S clubs transfer never completed (4S -5); support double
  only as opener's first rebid (a late one was passed for penalty);
  Ghestem / Michaels only over their opening; Truscott 3NT then 4NT is
  keycard (was passed as quantitative, 4NT -4); Garbage Stayman needs
  short clubs (4-4-3-2 passed 2D on three cards).
- Acol: the 5332 "+1 point" 1NT upgrade (tuned for a 15-17 1NT) opened
  11-counts 1NT; a 6+ minor outranks a 4-card major for the opening (but
  not a 5-card minor: 1S with 4-5 did better); up-the-line 1S not with five
  hearts; no-Jacoby systems ask for keys with 17+ (or 15+ and 5 trumps)
  instead of jumping to game.
- Weak twos (Ogust / feature ask): responder places the contract after
  opener's answer (was passed as natural, 3D -4).

Held-out (never-tuned seeds), each system's new bidder vs its bidder from
before this work, biq-vs-biq teams, 800 boards each, IMP/deal:

| System | seed 9101 | seed 9102 | seed 9103 |
|---|---|---|---|
| SAYC | +0.08 | -0.02 | 0.00 |
| Precision | +0.09* | +0.06 | +0.01 |
| Acol | (+0.03) | +0.03** | +0.08 |
| French | +0.04 | +0.01 | 0.00 |
| 2/1 | +0.07 | +0.03 | +0.03 |

\* after the inverted-raise rebid fix, which was chosen on 9101.
\*\* after narrowing the suit-order rule, which was chosen on 9102.
SE about 0.03-0.07 per cell. Phantom slams unchanged. Many fixes are for
conventions biq-vs-biq rarely reaches (NAMYATS, Truscott RKC, clubs
transfer) but a human partner will use.
On fresh deals (seed 9003) SAYC, French and 2/1 are now level (+-0.01);
Precision -0.16 and Acol -0.31 still trail. Most of Acol's gap is the weak
1NT itself under double-dummy scoring against biq's defences (its
continuations were checked and are range-correct), not a rule bug.

Bidder fingerprint after this round: 7f7b72e173 (run 19 was a59d51ddf4).
