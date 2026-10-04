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

## Live A/B on the fresh deck FRESH64M (runs 20-23, 2026-10-01/02)

"previous" was run as `--previous` after the commits, which resolved to
07256329: the OLD bidder (eb54410fe8) with the NEW card play. Both halves
therefore played the same card engine; this pair measures bidding only.

| Run | System | Version | IMPs | per deal |
|---|---|---|---|---|
| 20 | SAYC | previous (old bidder) | -44 | -0.69 (best SAYC score yet) |
| 21 | SAYC | latest (7f7b72e173), open room only | -73 | -1.14 |
| 22 | Precision | previous (old bidder) | -166 | -2.59 |
| 23 | Precision | latest, open room only | -181 | -2.83 |

Paired latest - previous: SAYC -24 (-0.38/deal, SE 0.46, 30 boards
differ), Precision -14 (-0.22/deal, SE 0.47, 28 differ). Neither
significant. Same-engine card play differed on 23-25 boards per pair
(-17 / +17): that is run-to-run noise, the size of one match's swing.

Bidding differences, board by board:
- New rules: RANDOM-058 weak 2S on KT8643 (-10 in both systems; Q-Plus
  opened the same 2S, the old version's pass was lucky), RANDOM-054 1S-(X)
  raise to only 2S after the pruning (-11; Q-Plus and the old rules bid 3S
  -> restored), RANDOM-055 +8.
- Hybrid simulation overrides (same simulation code, different rule
  bidder inside its rollouts): SAYC 038 P over a 4-trump 3H raise (-7),
  049 2S on 20 HCP (-6), 062 a weak-two opener re-bidding 3H after partner
  passed (-4), 015 +11; Precision 046 P over X with 5-5 majors (-10).
- Both versions: 1D-2NT on a 6-card-club singleton hand (SAYC 048,
  Q-Plus 2C -> 6NT); Precision 1C-2C 19 HCP + 4 clubs stopped in 4C (7C
  cold); 1C-1D-2NT passed with 7 HCP.

Fixed after this analysis (L-* cases, 127 checks): 1M-(X) 3M with four
trumps and 7-9; 1D-2C with 5+ clubs and a singleton/void (not 2NT);
Precision 1C-2m: 19+ with 4-card support asks for keys (also over
partner's 4m); 1C-1D-2NT raised to 3NT with 4+; bid_sim never lets a
preempter bid again after partner passed. Offline A/B vs the committed
bidder (seed 9104): these change 0-8 of 800 biq-vs-biq boards, within
+-0.01 IMP/deal.

All live paired evidence so far for the new bidder: +55 (deck G,
in-sample), -24 and -14 (deck M, held-out) -> about +0.09/deal over 192
boards: no detectable live gain yet from the bidding work. The card-play
work shows in the absolute scores (SAYC -0.69 with the new engine).

## Live A/B pairs A and B (runs 24-27, 2026-10-02/03), analysed 2026-10-03

Plan: ~/Documents/261002/biq_vs_qplus_AB_matches.md, matches 1-4. Runs 25
and 27 were open room only, merged with 24 / 26's closed room (closed rooms
checked identical on all 64 boards). Client logs: run 24 =
tools/runs/ab/261003_013956_*, 25 = 261003_062729_*, 26 = 261003_110431_*,
27 = tools/runs/biq_[NS].log.

| Run | Deck | Version | IMPs | per deal |
|---|---|---|---|---|
| 24 | FRESH64N | b4d9ccd704 (old bidder, old play) | -120 | -1.88 |
| 25 | FRESH64N | 07256329 (old bidder, new play) | -149 | -2.33 |
| 26 | FRESH64O | 07256329 (old bidder eb54410fe8) | -246 | -3.84 |
| 27 | FRESH64O | 893a540b (bidder ad19db8873) | -191 | -2.98 |

**Pair A, card play new - old: -29 IMP (-0.45/deal), but not from biq.**
Auctions identical on all 64 boards. biq's DD tricks given away: 55 -> 53
(declarer, same contract as closed room: 1.00 -> 0.53/deal on 15 deals;
defender 0.64 -> 0.55). Q-Plus E/W's own DD errors in the open room fell
43 -> 32: on RANDOM-056/034/059/052 (-21 IMP) biq lost nothing extra and
Q-Plus simply stopped giving a trick. Third-hand defensive follows lost
12 tricks vs 6, checked one by one: single-dummy judgement (T from KJT
when partner underled an ace, 9 from AT9 with Q in dummy), not the
safe-signal change. Lesson: score card-play A/Bs by biq's DD tricks lost,
not IMPs; Q-Plus's play noise swamps a 64-board IMP comparison.

**Pair B, bidding latest - old: +55 IMP (+0.86/deal, SE 0.49).** Bidding
+38 on 10 boards, same-engine play +17 on 23 (noise; biq DD lost 55 -> 59).
Most of the +38 is the hybrid simulation, not new rules: the rule bidder
inside the rollouts changed, so the overrides changed. Three boards where
run 26 overrode and run 27 kept the rule call: 019 (P over takeout X,
+14 for the rule), 038 (3C over P, +15), 048 (P over 4C, +8). Real rule
wins: 018 1S overcall instead of X left in for penalty (+6), 013 (+6).
Losses: 046 invite 2NT -> 3NT -2 (-5, mostly play), 020 (-3).

**Hybrid simulation overrides.** Same-seed sim is deterministic (runs 24
and 25 made the same 20 overrides). Overrides that cost big live: 029 S
doubles 4S (+5.8 claimed; made, -13/-14 in both 26 and 27), 032 S doubles
4S (made), 055 N passes over the rules' takeout X of 1H (-14, ends in
2Hxx made). Offline re-score of all 80 overrides on the real deals with
biq rules finishing the auction: +134 IMP DD; but on 019/038/048 it said
+3/+3/-3 where live said -14/-15/-8. That check models Q-Plus as biq, as
the sim does, so it cannot settle it. Last clean paired measurement of
hybrid vs rules was FRESH64H (2026-09-28, +1.20/deal), before the alert
fix and two rounds of rule changes: re-measure (hybrid vs --rules-only,
same fresh deck, current code). Penalty doubles of freely bid games
(029, 032) look like the first thing to restrict.

**Wacky / weak audit (tools/runs/mine/wacky_r24_27.txt).** Wacky calls
0.8/100 deals (one: 027 3NT over partner's weak 2H with 15 HCP, false
positive "19-21 shown"; Q-Plus 2NT ask -> 4H), wacky cards 1.6/100, weak
calls 5.9/100 (-154 IMP). Still made by the current rules (checked with
decide_bid, no rule fires -> Pass unless noted):
- N021: 11 HCP, four hearts passes partner's 1NT overcall (Q-Plus 2C, 4H
  makes) -10/-11.
- O034: 16 HCP 4-2-5-2 with K962 in their spades passes over 1S (Q-Plus
  1NT) -11.
- O002: partner overcalls 3S over 3D, 4D, N with four spades and 12 HCP:
  the rule picks "3NT advance", illegal after 4D, sanity -> Pass. Should
  be 4S (Q-Plus 5S making) -13. A real bug.
- O028: 1NT-2C-2D-3S(Smolen)-3NT, responder with 17 HCP passes (6NT
  cold, Q-Plus bid it) -13.
- N026: 12 HCP 4-2-3-4 passes over 1H (Q-Plus X) -6. Borderline after
  the light-double pruning, but this is a normal opening-strength double.
- O055 S after 1H-2H-P-P-X-XX with 5 diamonds and AT of hearts passes
  the redouble (2Hxx made); should run to 3D.
- O029 S: 15 HCP QJ985 passes over 1H (Q-Plus 2D). Judgement.
Already fixed in the current rules: N050 opener answers the lebensohl 3D
cue (3S; the old bidder passed it, -14), O055 N X, O014 S X, N003 S 1S.

Absolute: the gap to Q-Plus is contract choice. Same-contract boards
cost -4 to -53 per run, different-contract boards -103 to -193.

Running live paired totals for the new bidder, held-out decks only:
M SAYC -24, M Precision -14, O SAYC +55 -> +17 over 192 boards
(+0.09/deal, SE ~0.28), and O's +55 rests mostly on sim differences.
Live card-play new vs old, biq DD tricks lost: deck G declarer 0.76 ->
0.65 and defender 0.91 -> 0.81 per deal played in that role; deck N 55 ->
53 tricks over 64 deals. Matches 5/6 (pair C, Precision, FRESH64O) still to
play.

### Fixed after the runs 24-27 analysis (2026-10-03, uncommitted, bidder 14a5b10d27)

- **1NT overcall "systems on"** (`native_bidder._nt_overcall_systems_on`,
  hooked before the overcall routing): after OUR direct 1NT overcall the
  advancer uses the 1NT-opening responses (Stayman, Jacoby / Texas
  transfers, 2NT invite, 3NT) with 15-18 thresholds; the overcaller
  answers Stayman (not opener's major), completes transfers (super-accept
  with four and 17+), accepts 2NT with 17+, places the contract after the
  second round; over a major opening Stayman asks for the other major
  only and no transfer goes into their suit. If they bid after our ask,
  we keep the conventional reading (complete a transfer with 3+, show the
  other major at the 3-level, else pass). N021.
- 1NT overcall also with a five-card minor and no singleton (5-4-2-2 /
  5-3-3-2, no five-card major). O034.
- Advancing partner's 3-level major overcall: 3+ support
  and 9+ HCP raise to game; the 3NT advance only when 3NT is legal. O002.
- After 1NT-2C-...-3NT (Smolen with no fit, or a 2NT invite accepted):
  responder counts points (+1 per five-card suit with 7+ honour points):
  33+ with opener's minimum bids 6NT, 31-32 a quantitative 4NT. O028.
- `bid_sim`: no penalty-double candidate of a game the opponents bid
  freely (`_freely_bid_game`: their game/slam, our side never above the
  2-level). The rules' own double is untouched. O029 / O032.

Regression: N-S021 (a-e), O-S034, O-S002, O-S028 in
test_qplus_match_fixes.py (135 checks pass); test_bid_sim
`test_no_double_of_freely_bid_game`. test_competitive_fit RANDOM-025 still
the known pre-existing failure.
Offline A/B vs the committed bidder (rules only, wire view): SAYC seed 9105
+13, seed 9106 +12, Precision 9105 +13 IMP / 800 boards; 2/1, Acol, French
(400 boards, seed 9107) -2 / -3 / -2; 5-13 boards differ per run, phantom
slams and "doubled into a make" identical. Two A/B boards found the
interference gaps (9105 bd 208, 543) and one the 3S-over-1S Stayman bug
(9106 bd 448), all fixed before these numbers.
The sim change is not measured offline (the hybrid A/B is slow); it only
removes a candidate, in the spot where it lost live.

## Outside data and robots (2026-10-03)

Nothing below is in the repo except the three new tools; the data lives in
~/bridge_data (no license stated for it, or terms that forbid republishing).

**OpenSpiel WBridge5 dataset** (~/bridge_data/openspiel_wbridge5, 1,178,441
deals: WBridge5 5.12 at all four seats, SAYC preset, strongest level, North
deals, nobody vulnerable; its WBRIDGE5.INI is alongside). Decoder and checks:
`tools/openspiel_wb5.py check|dd|show`. Card = rank*4 + suit (C D H S),
dealt round-robin from North; call = action - 52.
- All 1,178,441 deals: no invalid deal, auction or play; no duplicate
  deal within or across train/valid/test; 6,088 passed out. Same flag mix
  as the test split (3.1%). Test split (10,000): 39 passed out. SAYC red flags on 3.0% of openings, all style: 1NT with
  5-4-2-2 (115), 1NT with 18 (35) or 14 (7), strong 2C on 16-17 HCP with
  playing tricks (53), five-card weak twos in 1st/2nd seat (44). No
  four-card major openings.
- `dd`, 2,000 test deals vs par: WBridge5's own table is 3.74 IMP/deal
  from par, biq's rules at all four seats 4.56 (WBridge5 closer on 767
  deals, biq on 508). Its declarers take 0.13 tricks/deal more than double
  dummy (it defends both sides). **Slams: 253 deals have a DD-makeable
  small slam; WBridge5 bid 146 (99 make, 47 DD-down), biq's rules bid 14
  (9 make).** Examples (par_test_2000.jsonl): 1585 opener with AKQJT752 of
  hearts passes partner's 5C; 768 1H-1S-2H-3S with 18 HCP and AKQT76
  (only invitational) passed; 1809 14 HCP negative double then passes 3C.
  Slam bidding and strong-hand continuations are the biggest gap this
  data has shown. Not yet checked with the hybrid simulation on.

**bridge-llm-bench** (~/bridge_data/bridge-llm-bench, MIT stated in the
README, no LICENSE file). Low quality, do not trust its WBridge5 column:
its parser decodes OpenSpiel cards as suit*13+rank (they are rank*4+suit)
and deals players blocks of 13, so its hands are scrambled; 56 of its 150
positions are identifiable test-split hands under that wrong decoding. Its
headline "WBridge5 agrees with SAYC engines only 44%" is that bug. Usable
part: Ben and BBA (EPBot) answers to its 150 hand+auction problems; they
agree on 129, and biq differs from both on 31
(~/bridge_data/bridge-llm-bench/biq_vs_ben_bba.csv). The auctions were
produced by other hands, so read those as quiz problems, not real deals.

**Bridge Baron 12 help** unpacked (WinHelp, no phrase compression) to
~/bridge_data/bb12_help/baron_help.md with hlp.py/topics.py. Teaching
features worth copying in biq's own way: Hand Evaluation (HCP, distribution,
bidding points, quick and playing tricks, each explained), Auction
Interpretation (ranges, controls, convention name per hand), flowcharts
followed with the arrow keys, "Announce When Different" (says only that
your call differs, not what to bid), convention drills with near misses and
reasons, deal generator by auction, player statistics by contract type,
replay-the-deal-against-Baron IMP comparison, 650 ACBL/NABC deals scored
against the human field (scores only, no contracts). Its Standard American
is dated (16-18 1NT default, 13-15 overcalls), so its tables are not a
reference for modern SAYC. Online play is DirectPlay, no Blue Chip
protocol: it cannot be an automated opponent.

**Blue Chip table manager** `tools/biq_bluechip_tm.py` (protocol 18, the
World Computer Bridge Championship protocol). Robots connect per seat;
biq plays the others in-process with the live engine (hybrid bidding,
no-peek card search in a forked child). `--rooms 2` replays the deck
rotated one seat (closed room) so a robot pair keeps its seats and the
teams IMPs still compare like with like. `tools/bluechip_test_client.py`
is a scripted robot; the 2-board loopback (biq N/S vs two scripted
clients) completed both rooms including a robot declarer playing its
partner's dummy. WBridge5's binary has the same message strings
(`Connecting "`, `seated`, `ready for teams`, `ready for Dummy's card to
trick`, heartbeats) and a Connection dialog (team, server, port, seat,
Auto). Its Options offer a SAYC preset. First live WBridge5 run
(tools/runs/bluechip/261003_wb5_smoke, 4 boards x 2 rooms, seed 261003):
completed unattended once both WBridge5 windows were connected, about a
minute per board, no protocol errors or illegal calls; biq 0 IMP (-5, -6,
0, +11). Scoring checked by hand. WBridge5 sends upper-case seat names and
double spaces ("EAST ready for  WEST's bid"); the regexes accept both.

**Vugraph**: not downloaded. BBO's terms (effective 18 May 2026) need
written consent for bulk copying; request drafted in
~/Documents/261003/bbo_vugraph_permission_request.txt.

**Bridge Baron 12 flowcharts decoded** (2026-10-03, private:
~/bridge_data/bb12_flowcharts, 22 charts, ~1,000 boxes, FINDINGS.md has the
format and lessons). Huffman-coded text plus a yes/no link table. Main
lesson for biq: BB starts slam thinking at 32+ combined TOTAL points (31
with a 7-card major; also in competition; 34+ bids slam directly when 4NT
is out of reach); `_maybe_slam_try` counts HCP only, uncontested, at the
3-4 level. Fits the WBridge5 finding that biq's rules bid ~10x fewer slams.

**Slam trigger experiment (2026-10-03, reverted).** Tried Bridge Baron's
rule in `_maybe_slam_try`: count total points (shape) and start RKC at 32+
combined (31 with seven trumps), also in competition, plus a direct 6 at
the five level with 34+. Measured with `openspiel_wb5.py dd --baseline`
(biq at all four seats vs par) on 2,000 test and 2,000 valid deals:
- first version: test +3 slams made, -44 IMP vs par; valid +4 phantom
  slams, +22 IMP worse. Two bugs it exposed (pre-existing, now reachable):
  after interference partner passes 4NT as natural (valid 68, 1653);
  self-sufficient-suit RKC continues in the wrong strain (valid 103 6C, 603
  6S instead of hearts).
- fixed version (uncontested, TP 32 OR HCP 30, self-sufficient on HCP): 2
  boards differ in 4,000 (+11, -11). Noise, so reverted; code in
  ~/bridge_data/experiments/nb_slam_tp_final.py.
Diagnosis (slamdiag2.py): of 239 DD-makeable slams biq missed on the test
split, 211 never reach 32+ as "my points + partner's SHOWN minimum" at any
turn: `_partner_min_hcp` reads only partner's first call (6 for any
one-level response), so later jumps, reverses and accepted invitations never
raise it. Many of those slams are also DD-only (24-28 HCP). The lever is
tracking partner's range through the whole auction (Bridge Baron's
"Auction Interpretation"), then the trigger; plus fixing the two bugs above.

## Overnight match vs WBridge5 and learned partner ranges (2026-10-04)
Overnight Blue Chip match (tools/runs/bluechip/261003_wb5_overnight, 200
boards x 2 rooms, no protocol errors): **biq -891 IMP, -4.46/board.**
Double-dummy split: bidding -397 (game vs partscore -163, doubled
disasters -117, missed slams -80), card play -494 (WBridge5 declaring took
+0.51 tricks/deal over DD against biq's defence; biq declaring -0.19).

Behavioural mining of WBridge5 (private, ~/bridge_data/experiments/
wb5_diverge.py on the OpenSpiel set): biq's rules make WBridge5's call 73.5%
of the time (openings 90%, contested 2nd-round calls 55%). Finishing each
disagreement both ways with biq's rules: the big leak is PASSING where
WBridge5 bids game in our own suit (2,713 cases in 10,000 deals, +9,177 IMP
for the game bid, two thirds of them contested).

The hand-written auction_inference ranges miss biq's own partner's HCP 12-22%
of the time, so they can't drive game decisions. New:
* backend/partner_model.py + backend/data/biq_partner_profiles.json.gz: at
  every turn of 300,000 biq self-play deals (random dealer/vul, wire view),
  partner's HCP percentiles/mean and suit lengths, keyed by the auction seen
  from the seat (K1 exact, K2 no passes, K3 our calls + contest level).
  Rebuild with tools/biq_profile_build.py after bidder edits that change
  what calls mean (test_partner_model.py warns on a fingerprint mismatch).
* native_bidder._learned_game_net (in decide_bid, after the sanity wrap):
  when the rules pass below game, bid 4M with a fit if my TP + partner's
  mean HCP >= 25, 3NT if HCP + mean >= 24 with their suits stopped, 5m at
  29. BIQ_GAME_NET=0 disables, BIQ_GNET_MAJOR/NT/MINOR tune.
* Rule fixes: 1NT-3NT on 9 HCP (was a 2NT invite); opener after a transfer
  and 3NT bids 4M with three; transfer then a new suit is forcing (opener
  passed). W5-* cases in test_qplus_match_fixes.py.

Measured vs the committed bidder (rules only):
| check | result |
|---|---|
| 4000 held-out WBridge5 deals, |IMP from par| | 4.795 -> 4.654, +0.141/deal (SE 0.020) |
| teams A/B seed 9105, 805 bds (DD / robust) | +0.267 / +0.207 per board |
| teams A/B seed 81, 805 bds (DD / robust), dev table | +0.402 / +0.180 per board |
| WBridge5 agreement, 3000 held-out deals | 73.3% -> 73.5% |
(Shipped 300k-deal table; the seed-81 run used the 150k development table.)
test_bid_sim's "simulation acted" check can fail under heavy machine load
(the time cap cuts samples); it passes on an idle machine.
Threshold choice: lower thresholds (major 24-25, 3NT 23) scored closer to
par on the all-NV WBridge5 deals but worse on the robust teams judge.
Tried and NOT adopted (measured ~0 or worse): partner's learned 25th
percentile as the slam-try floor (one phantom 6S, BIQ_SLAM_LEARNED=1 to
retry), penalty doubles of their 4-level bids, takeout X on 11 HCP with
shortness, queen-high NV weak twos in majors. Competitive part-score passes
(the second-largest leak) are left to the live simulation layer for now.
