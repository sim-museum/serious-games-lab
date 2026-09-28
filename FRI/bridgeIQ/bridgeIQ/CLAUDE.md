# biq — Claude Code project notes

## STATUS — FRESH64H live runs (2026-09-27/28, UNCOMMITTED)
Run 12 hybrid (batch-1 rule fixes + Q-Plus opponent model): -107 / 64 = -1.67/bd
(best hybrid so far; runs 7/9/10 were -2.29/-2.08/-2.33). Run 13 --rules-only:
-177 = -2.77/bd. PAIRED hybrid - rules +77 IMP (+1.20/bd, SE 0.59; closed
room identical 64/64): the 16 simulation boards +59 (won 9 12 39 48 55 ...,
lost 6 -2, 18 -5), same-auction boards +18 (card-play variance). G+H paired:
+0.74/bd. Run 14 Precision90M hybrid: -236 / 63 = -3.75/bd, under-compete
-109; hung on board 64 when N DOUBLED PARTNER'S 2D (1C-(1S)-P-(P)-2D-(P)-X).
Fixed: _is_legal_bid now requires X/XX to be of the OPPONENTS' call;
decide_bid never returns an illegal call (-> pass); the Precision 1C-response
branch only on responder's first answer (len(partner_bids)==1). Regression
cases added to test_qplus_match_fixes.py (81 checks). Precision/log files are
kept out of the SAYC miners/profiles (file_system() filter). Profiles rebuilt:
410 situations, 59% coverage. Results: tools/runs/results/run12-14*.qss, logs
tools/runs/ab/run12-14*. Second-hand-low card tweak tested offline (58 deals:
35 vs 32 tricks given away) - NOT adopted (working copy only, scratchpad biqwork).

## STATUS — learning from Q-Plus's own records (2026-09-26 evening, UNCOMMITTED)
Q-Plus writes every deal of both rooms with all four hands and every card
(.qss sheets; DATA/LOG/*.bdl open room, *.cdl closed room). Three tools use it:
* tools/qplus_auction_mine.py — every Q-Plus call replayed through biq's
  rules; disagreements finished twice by biq's rules and scored DD (plain +
  robust). `--live`: the FIRST call where the two rooms' auctions part, i.e.
  biq's real call vs Q-Plus's with each program's real continuation (the
  unflattered measure). Reports in tools/runs/mine/.
  Finding: in auctions biq's partnership could reach ("on-path") biq's rule
  calls cost only ~-92 IMP / 650 disagreements (biq-continuation DD, which
  flatters biq); live first divergences: 374 boards, -880 real / -693 DD.
* backend/qplus_model.py + tools/qplus_profile_build.py — per-situation HCP /
  suit-length ranges of Q-Plus's calls (backend/data/qplus_call_profiles.json,
  360 profiles, 57% of calls covered). BIQ_OPP_MODEL=qplus makes the bid_sim
  sampler, lead sim and card-play sampling read OPPONENTS' calls with it
  (biq_qnet_client sets it). Held-out test: suit-length error 3.97 -> 3.75,
  HCP error unchanged. Small gain; grows with more recorded matches.
* tools/play_audit.py — card-by-card DD audit of both rooms. Over runs 1-11:
  biq gives away 1.11 DD tricks/deal declaring and 1.14 defending; Q-Plus
  0.57 / 0.56. Opening leads equal; the gap is in later leads (defence and
  declarer), discards, ruffs, 2nd-hand play.
Rule fixes (batch 1, snapshot scratchpad nb_batch1.py): Texas completion
(opener passed 4D!), 1NT with 5332 + five-card minor at 14 HCP, weak jump
overcalls (no 3-level jump on 4-6 HCP, vul 2-level needs 6+, 9-10 -> simple
2-level overcall), opener's competitive rebid of a 6-card suit (3-level needs
15+ or 7 cards; second rebid needs 7), sanity "don't sell out" the same,
1M-1NT-2m preference / 2H, weak 4-card fit after 1M-1NT-2x passes (was
legalized into a 3-level raise). Miner: agreement 74.0 -> 74.8%, on-path
-92 -> +38 IMP (in-sample).

## STATUS — hybrid simulation bidding + simulated leads (2026-09-25 night, UNCOMMITTED)

**Bidding = rules + simulation** (`backend/bid_sim.py`, entry `decide_bid(..., hand=...)`).
The rule bidder proposes; at JUDGMENT points (`should_simulate`: not openings,
not the uncontested first response, not conventions/slam machinery/forcing
situations, not alerted calls) simulation checks it:
1. *Sampler* — hidden hands are dealt so that biq's OWN rule bidder, holding
   them, makes every call those seats made (passes included). Meaning = what
   the rules do, so maker and reader can't drift. Soft HCP/length limits,
   LEARNED by rejection-sampling the bidder per seat (hand-written
   `auction_inference` only as fallback — it misreads e.g. Michaels), guide a
   local search; a Metropolis card-swap chain then yields samples. Fixed-count
   work → the same position always gets the same call (time is a safety cap).
2. *Candidates* — rule call, pass, double, partnership suits (cheapest level and
   game), 3NT.
3. *Rollouts* — each candidate on each layout, auction finished by the rule
   bidder at all four seats (partner's reaction is part of the value).
4. *Scoring* — batched double-dummy (`DDSolver.solve_dd_tables`, libdds
   CalcAllTablesPBN, only needed strains) with ±1-trick uncertainty; contracts
   failing by 2+ scored doubled (rule bidders rarely penalty-double); IMPs vs
   the rule call; override only if ≥ MARGIN (0.8) IMP better on average.
Defaults 64 samples, ~2–5 s per simulated call. Switches: Preferences ▸ Mouse &
Play ▸ "Simulation"; env BIQ_BID_SIM=0, BIQ_BID_SIM_SAMPLES/BUDGET/MARGIN.
Q-NET client passes the hand and logs every "Simulation:" override.

**Opening leads** (`backend/lead_sim.py`, hooked into nopeek + GUI engine):
same sampler, every lead solved double-dummy on each layout, best average for
the defence in IMPs vs the table lead; conventional card kept within a suit.
BIQ_LEAD_SIM=0 disables.

**Card play now uses the bidding** (`declarer_search._sample_defenders`): it
oversamples ×8 and keeps the layouts whose original hands biq's rules would
have bid as those seats did (it used only counts + shown-out suits before).
BIQ_PLAY_AUCTION=0 disables. `tools/nopeek_eval.py` now passes the real
auction (`--no-auction` for the old measurement).

**Measured (double-dummy teams A/B, both directions).** Hybrid vs the SAME code
rules-only: seed 101 **+1.92 IMP/bd** over 240 boards (SE 0.31; ±1-trick judge
+1.75), won 81 / lost 24; seed 202 +1.44 over 160 (SE 0.38; ±1 +1.32) →
**+1.73 IMP/bd over 400 boards**. Hybrid vs the bidder committed on the morning
of 2026-09-25: +1.57 over 160 boards (SE 0.40; ±1 +1.73). Overrides also need gain ≥ 2 SE (T_MIN) — without it
coin-flip 3NT-over-4H choices slipped through. Card play (nopeek_eval with the
auction, 80 deals, tricks lost vs DD): old 121 → auction sampling + sim leads +
10 layouts / 12 s search 106; declarer diagnostic showed auction sampling itself
neutral for declarer (318 vs 319 tricks), its gain is on defence. Defaults now
BIQ_AMU_WORLDS=10, BIQ_AMU_BUDGET=12; Q-NET card timeout 60 s, biq_match idle 90 s.
**Live paired check (FRESH64E, 2026-09-26): hybrid run 7 −2.29, rules-only run 8
−2.08 vs Q-Plus; paired hybrid − rules = −9 IMP / 62 bds (−0.15, SE 0.68) —
the offline +1.7 did NOT carry over.** Cause: rollouts use biq's rule bidder as
the opponents, and it gets confused after interference, so junk calls scored
well (3NT on 4 HCP, X on 2, 3H on 2: −45 IMP live); the offline A/B shared the
same flaw. Fixes: `robust_result` — the OPPONENTS of the decider reply
competently (double when it pays, outbid with their best DD contract, which can
be doubled back); candidates must be justified by values / fit / length; the
A/B now also reports a "robust judge" (`rsw` in the jsonl). A Q-Plus crash in
the rules run (06:06, QBRIDGE.EXE exited while East chose a card) is now
detected by biq_match (QPlusGone) instead of waiting for a click; previous
client logs are archived to tools/runs/ab/. biq_match can send keys through a
uinput virtual keyboard (no GNOME consent) if /dev/uinput is made accessible
(a system change left to the user).
Revised hybrid, offline seed 101 (160 held-out boards, vs same-code rules):
pure DD +1.12 IMP/bd (SE 0.39), ±1 +0.98, robust judge +1.75 (SE 0.40); won 40
/ lost 17. ~10 s per simulated call on an idle machine (full DD tables).
Next live check: paired runs on FRESH64F.BDE (hybrid, then --rules-only).

**Run 10 (FRESH64G, revised hybrid, 2026-09-26): −149 IMP / 64 = −2.33/bd.**
Played in two halves (boards 1–24, then 24–64 after Q-Plus re-dealt board 24
mid-run; see tools/HARNESS_STATUS_2026-09-25.md). Q-Plus's scoring table was
empty for the second half, so the sheet was rebuilt from Q-Plus's own room
logs (DATA/LOG/log-023.bdl = open room, .cdl = closed room) with
tools/qplus_logs_to_qss.py, merged with the autosaved boards 1–24
(M2026-09-26-K.qss) → tools/runs/results/run10_fresh64g_hybrid.qss; 39 boards
cross-checked against report_score in the client logs, 0 mismatches. Buckets:
bidding −136 (under-compete −76, overbid −40), cardplay −55, defence −28.
16 simulation calls; the two 3NT jumps (bds 12, 56) were right (Q-Plus bid the
same and made them) but biq's declarer play went down. Rule flaw seen, NOT yet
fixed (bidder frozen until the paired rules-only run on FRESH64G): bd 21 South
T.AQ753.A43.T876 passes 3S after 1C-1S-2H-2S-3C-3S (12 HCP, 4 clubs).
**Run 11 (FRESH64G, --rules-only): −176 / 64 = −2.75/bd**
(tools/runs/results/run11_fresh64g_rules.qss). Closed room identical 64/64.
PAIRED hybrid − rules: +18 IMP (+0.28/bd, SE ≈ 0.49): the 13 boards where the
simulation changed the auction +19 (won 5 10 13 38 45 = +38; lost 12 56 = −13
where 3NT was right but biq's declarer play went down, 21 −3, 51 −3); the 51
same-auction boards −1 (card-play run-to-run variation, lead sim ≈ 0).
Promising, not yet significant. Biggest remaining leaks: rule bidding (−178
in run 11) and notrump declarer play (bds 12, 56).

Tests: `test_bid_sim.py` (sampler exactness, conventions untouched,
determinism, budget, candidates legal, scoring, lead). Measurement:
`tools/bidder_teams_ab.py current --new-hybrid` (hybrid vs same-code rules
only), shardable with `--start/--jsonl`.

## STATUS — fixes from the 2×64-board Q-Plus runs (2026-09-25, UNCOMMITTED)

Every losing auction in runs 2/3 was replayed offline (the bidder reproduces
all logged calls: `tools/competitive_decision_probe.py tools/runs/ab/run_*.log`)
and traced to the rule that produced it. Fixed in `backend/native_bidder.py`
(each fix names its board in a comment; all pinned in `test_qplus_match_fixes.py`):
quant-4NT used the 1NT-OPENING range for a 12-14 REBID (RUN2-007); no
game when responder would pass partner with 25+ combined (`_game_values_net`,
RUN2-009); partner's reopening/competitive X after I passed was never answered
→ penalty pass with 2 HCP (`_answer_partner_reopening_double`, RUN2-015); 17-count
with 3 small in their suit silent (RUN2-017); illegal rebid → pass with 4-card
support for partner's free bid (sanity 2g, RUN2-019); lebensohl relay not completed
by either hand (RUN2-021); advancer without a raise always passed (`_advance_new_suit_or_nt`,
RUN2-025/027); partner's competitive 3M read as a jump-raise / forcing new major /
2nd-suit preference, and a RAISE of my suit read as a forcing reverse (RUN2-030/038);
no balancing X over 3-level preempts + forced advances gated by HCP (RUN2-035);
Truscott read on a later 2NT, 8-count invites over 12-14 (RUN2-046); no slam try
with 19 opposite a limit raise (RUN2-047); 1S response capped at 18 HCP → "Jacoby
2NT? No support — fallback", and RKC asker using opener's suit as trump (RUN2-053);
no sandwich weak jump (RUN2-054); 4m instead of 3NT (RUN2-057); opener passing a
negative X with a singleton (RUN2-060); plus preference (RUN2-008), 5-HCP 5-card
major response (RUN2-050), responsive X of a double (illegal), 6NT at 33 over 2NT.
**Measured:** `tools/bidder_teams_ab.py <baseline native_bidder.py>` (new, DD-scored
teams match NEW vs BASELINE on random deals, both directions): +0.52 / +0.43 /
+0.46 IMP/bd on seeds 7/11/23 (1000 boards each); phantom slams 15 vs 14,
"doubled them into a make" 22 vs 76. Overfitting check on a FRESH deck
(`OWN-DEALS/FRESH64.BDE`, gen_test_deck seed 260925, never used in tuning):
+0.42 IMP/bd after three fixes it exposed (F64-* cases in the test file).

**Card play — DDS wrapper bug (backend/dds.py):** `SolveBoardPBN` was called in
mode 0, which returns score **-2** instead of searching when the hand to play has
one distinct card. alpha-mu treated -2 as a trick count at every such leaf, so
e.g. RUN2-004 dummy led c3 from J932 into partner's c6 (3 tricks). Now mode 1
(`BIQ_DDS_MODE=0` restores the old behaviour for A/B only). `nopeek_eval.py`
40 deals × seeds 5/9, mode 0 → 1: declarer leak 0.85/0.85 → 0.65/0.48 tr/deal,
defence 1.13/0.93 → 0.83/0.80. Also: declarer
tie-break among EXACTLY tied cards (`nopeek._natural_declarer_card` — no more
DD-neutral ace discards), lead engine reads Unusual 2NT / Michaels suits (RUN2-062).

**Live run 4 (blind deck FRESH64B.BDE, fixed code, bidder fp 69a3625b72):
−0.31 IMP/board** (`tools/runs/results/run4_fresh64b_fixed.qss`; runs 2/3 were
≈ −3.0 on other deals). DD card audit: biq 3.2 tricks lost /100 cards vs Q-Plus 2.4
(runs 2/3: biq 4–6.7). Its losses drove a second round of fixes (R4-* cases in
`test_qplus_match_fixes.py`, 50 checks): "forcing" free new suit with 2-3 HCP;
contested 2NT read as Jacoby by both hands; opener passing a forcing contested new
suit / natural 2NT; no Michaels advance (+ 2NT ask); doubler rebid now estimates
partner from the answer type (jump / free / forced / balancing); 4-trump competitive
jump raise + opener's 4M over their 4-level with shortness; 1NT opener never
answered transfer-invites; 2/1 GF prefers 3NT with unbid suits stopped; lone 5-level
rebids and reopening X of their game capped; king-ask (grand) needs the real trump
queen unless trumps are partner's own suit; RKC after a limit raise needs 19+.
Teams A/B vs committed bidder now **+0.74 / +0.73 / +0.66 IMP/bd** (seeds 7/11/23),
+0.66 / +0.75 on FRESH64 / FRESH64B; phantom slams equal (13 vs 13).

`tools/biq_match.py` is now unattended after one click: Q-Plus's "Information about
the bids done" window steals focus once per deal; the script closes it with Escape
(only when it is focused), which returns focus to Q-Plus.

**Live run 5 (blind FRESH64C.BDE, seed 260927, bidder fp 8695f4e184): −2.47
IMP/board** (`run5_fresh64c.qss`). A hard deck — offline the new bidder is still
+0.62/bd vs the old on these deals — but it exposed more gaps, fixed (R5-* / AB-*
cases, 68 checks): no 2M rebid with 7 cards; strong hand passing a weak two;
Landy advance required an alert flag (Q-NET carries no alerts); reopening X with a
5-card 2nd suit (≤16 HCP); no LAW raise of partner's preempt; pulling partner's X
of a 4-level preempt with a flat hand; 1-level overcall suit-quality gate too strict
for 6-card suits; lebensohl relay by a passed hand; no raise of partner's minor;
minor overcaller never accepting UCB; limit raise declined with a void; 4M on
3 trumps instead of 3NT after a negative X; cuebid reply repeated every round; the
6-card-rebid cap now first-round ≤4 (15+), second round only as a shape save;
opener's "opponents' suit" now in auction order and excluding cue-bids of ours.
Opening leads: `native_lead._opp_suits` infers ARTIFICIAL opponent bids (cue of
our suit, anything after their NT, after their 4NT, strong 2C/2D) and leading
declarer's own suit is penalised; own 5-card bid suit gets a bonus vs NT
(R5-018/033 now lead what Q-Plus led). Run 5 card audit: biq 3.8 tricks/100 cards
vs Q-Plus 2.3; opening leads were the largest bucket.
Teams A/B now **+0.84 / +0.79 / +0.69 IMP/bd**; phantom slams 12 vs 14.

**Live run 6 (blind FRESH64D, seed 260928, fp 3b215a3185): −3.97 IMP/board.**
Fixed after: super-accept → 3NT; 18-count 2C over 1NT (now jump shift); 1NT rebid
"legalized" to 2NT instead of raising partner's major over interference; no slam
gear in the game net (now RKC at 32 with a major fit); answerer passing doubler's
raise; 8-card major overcall (now 4M preempt); new 3-level minor over a reverse
(now 3NT, except with a bid 5-card major); Michaels advance to the 4-level with 4
HCP. 76 checks. Teams A/B +0.84 / +0.85 / +0.69.

**Methodology (read before the next run).** One 64-board live match has SE ≈ 0.8
IMP/bd, so single runs can't show progress: old code −3.07 (runs 2/3), fixed code
runs 4–6 −0.31/−2.47/−3.97 = −2.25 ± 0.45. Each run exposes 10–15 NEW distinct rule
gaps (few repeats): a long tail, so board-by-board patching has diminishing returns.
The regression guard (bidder_teams_ab) is biq-vs-old-biq scored double-dummy —
not Q-Plus, and DD flatters aggressive bidding. Better: paired runs (old vs new code
on the SAME deck vs Q-Plus), longer unattended matches, separate "find" decks from
held-out "measure" decks, and prioritise by frequency over thousands of deals.
Plot of today's runs: ~/Documents/260925/biq_vs_qplus_runs_260925.pdf.

## STATUS — whole-system analysis + minimal harness (2026-09-25)

**Why biq loses (~3 IMP/board to Q-Plus, same 61 deals twice):** see
`~/Documents/260925/biq_vs_qplus_analysis.md` (+ `dd_audit.py`, a double-dummy
audit of every card in both rooms). Bidding ≈ 2/3: biq misses 18/36 makeable
games and 8/8 slams (Q-Plus 4 and 2), leaves long suits unbid, and partner
doesn't recognise conventions (lebensohl 2NT passed when doubled, penalty pass
with 2 HCP). The bidder has 13 "fallback" bids for hands no rule matches, e.g.
`native_bidder.py` ~L4170 "Jacoby 2NT? No support — fallback" fires for a
21-count with 6 spades because the 1S response is capped at 18 HCP.
Card play: 4× Q-Plus's DD error rate, mostly declarer's mid-hand lead choice.
Nothing in bidder/card engine changed since 2026-06-14; whole-system has been
≈ −2.6…−3 IMP/board since that mode was first measured. Signalling ON is better
(paired A/B +25 IMP) — keep it.

**Harness: use `tools/biq_match.py`** (terminal script, keyboard only). User sets
Q-Plus up by hand; script connects biq N+S on Enter, then presses Return at each
phase (deal / start bidding / start play / each trick / next deal) only while
Q-Plus has real keyboard focus. No mouse, no calibration, no virtual desktop.
The control panel / button_loop / mixed_corpus click tooling is superseded.

## STATUS — slam bidding + harness cleanup (2026-06-14)

Shipped on branch **24.04** and merged to **main** (merge `a01ef7a`). Run the app
with `./run.sh` (just fixed: it now uses the venv python directly — bare `python`
isn't always on PATH). Default seating is human-South + biq N/E/W; config uses the
`native` bidder (N/S Precision90M, E/W SAYC) + no-peek cardplay — i.e. all the
latest engine, no setup needed.

**Slam bidding — five safe fixes (all in `backend/native_bidder.py`).** Each gated
so 256-512-deal random regressions hold ZERO NEW phantoms (the hard rule; any
blind HCP bump over-fires — measured repeatedly):
- Jacoby 2NT responder continuation: place the contract in the agreed major,
  never raise opener's shortness reply (was `1S-2NT-3H-4H`, a 4-card heart fit).
- Killed phantom 7-level grands: the 5NT king-ask now needs ALL 5 keycards (was
  ≥4 = off a key); plus a hard total-keycards-=-5 clamp in `_asker_after_rkc`.
- Opener Jacoby-2NT reply only fires on a DIRECT 2NT (not a natural 2NT after a
  2/1) — stopped opener bidding 3-of-shortness in a VOID suit.
- Strong balanced responder (19+) bids 4NT quant instead of parking in 3NT.
- Don't pass opener's jump-rebid (1X-1Y-3X) with game values — drive to game / RKC.
Measured live: slam-deck OVERBID bucket −91→−39, ZERO phantom grands / wrong-strain
in the latest run (M2026-06-14-O, −2.91/bd — best slam-deck number yet). Remaining
frontier = the MISSED-SLAM bucket (NT/minor/distributional slams biq stops short
of); needs control-showing, NOT HCP gates — a crude attempt re-adds phantoms, so
DEFERRED. Also fixed a pre-existing `_opener_rebid` crash (`KeyError None` when
reopening a takeout double, `opp_suit` is None). A ~0.4% baseline phantom-slam rate
on wide random sampling is pre-existing + still open.

**Test-harness GUI simplified** (`tools/qplus_control_panel.py`): four groups
(1 Configure · 2 Mode · 3 Run · 4 Result); a single **Mode** dropdown
{Whole-system, A/B, Double-pair, No-peek} replaces the four scattered boxes / the
no-peek pop-up; one **▶ Start** path (+ the Step/Autopilot debugger); calibration +
utilities moved to Setup/Tools menus. The manual-startup trio + advanced knobs are
gated by the run flow, so they stay (Setup ▸ Advanced settings). Embedded
LiveMatchWidget tab in `qplus_mixed_corpus.py` unaffected.

**UML docs** under `docs/uml/` (app flows) and `docs/uml/harness/` (test harness) —
PlantUML + PNGs, READMEs with `file:line` anchors. The harness diagrams include a
colour-coded cleanup map and the proposed layout that's now implemented.

**Validation/measurement reminders.** `tools/run_preflight.py` grades a run vs the
locked rig → INVALID / VALID-with-warnings / VALID; the common "VALID with
warnings" is just the deck-source WARN (deal-number labels, an A/B-pair concern).
Slam-bidding changes: validate offline with `tools/slam_bidding_eval.py` + a
random-deal phantom sweep BEFORE trusting; the live truth is a whole-system run
through `tools/whole_system_analyze.py`. NB pre-existing uncommitted WIP in the
tree (`bidding_systems.py`, `table_view.py`, a `probes.pbn` deletion, …) is NOT
mine and was left untouched.

## STATUS — no-peek cardplay engine (2026-06-12)

biq's no-peek cardplay (`backend/nopeek.py`) is now an **alpha-mu** engine: DDS
on belief-sampled hidden layouts + a CONSISTENT line across indistinguishable
samples — strong like PIMC but with **no strategy-fusion tells** (the user's
requirement: "DDS on representative samples is fine; the tells are what they'd
scoff at"). Live-viable: per-decision time budget ≤5s/card; the Q-NET client
forks every card so a libdds crash can't wedge a match.

**Measured LIVE vs Q-Plus 17.1** (forced-contract rig, 61 paired boards,
`nopeek_qss_compare`): from a per-seat engine 1.5–1.8 tr/board behind, now
**declarer ≈−0.6, defence −0.56 tr/board** — and legible.

Shipped this arc (all A/B-gated with the SEEDED `tools/nopeek_eval.py --rng`):
- Alpha-mu declarer (1.484→~1.06 vs DD) and defence (1.219→~0.80, edges PIMC).
- **Defensive signalling** (`backend/signals.py`): standard attitude/count/
  suit-pref among trick-equivalent cards; emitted via the alpha-mu `tiebreak`.
- **Reliable signaller**: `AlphaMu.signal_margin` (default 0.15) so biq plays the
  convention card among near-equal spots — trick-neutral-to-positive.
- **Signalling ON/OFF switch (2026-09-22)**: Preferences ▸ Defensive Signalling ▸
  "Play defensive signals" (`preferences.signalling_enabled`, env `BIQ_SIGNALLING=0`
  for the harness clients; `signals.set_enabled()`). OFF = `choose_signal_card`
  returns the plain lowest card, nopeek skips its pure-signal shortcut, the alpha-mu
  signal margin is 0 with no tie-break, and partner-signal reading is off. Added
  because a signal was taking precedence over winning a trick; A/B it with
  `tools/qplus_loop_sessions.sh` (`BIQ_SIGNALLING=1` vs `0`, `NOPEEK=1`).
  Test: `test_signalling_switch.py`.
- Interior-sequence opening-lead fix (KJTx/AJTx/AT9x → J/J/T, was the bottom).

Measured + SHELVED (default-off, documented negatives): defence rollout
(`defender_search`), rollout-leaf alpha-mu, hard-filter signal-READING
(`signal_read`; biq isn't a reliable enough signaller for hard filters in
self-play). Env knobs: `BIQ_AMU_WORLDS/DEPTH/BUDGET/DEFENSE`, `BIQ_DEF_ROLLOUT`,
`BIQ_DEF_ROLLOUT_LEAF`, `BIQ_READ_SIGNALS`, `BIQ_SIGNAL_MARGIN`.

DEFERRED (user's signal-reading design): convention config setting, end-of-hand
mis-signal admonition bar, auto-disable counter (`signal_read.mis_signals` is
built + tested). See memory `plan_biq_singledummy_engine`,
`project_biq_defensive_signalling`.

## Cardplay engine — DO NOT confuse with BEN

biq is **NN-free**. Bidding goes through `native_bidder.NativeBiddingEngine`
(rule-based, system-driven), opening leads through `native_lead`, and
follow-on cards through `get_mc_card_play` (Monte Carlo + DDS).
`BridgeEngine` only loads the DDS solver. **BEN has been REMOVED** —
ignore any older docstring or comment that mentions it.

## To-do — per-tab comparison-mode widget

Each corpus tab in `tools/qplus_mixed_corpus.py` (Random, Bidding-system
matrix, Slam-eligible) should expose a tri-state widget (radio group or
combo box) that selects what's being compared in the run:

1. **Compare bidding only** — current behaviour. The diff tool feeds
   the deal hands to both biq's bidder and Q-Plus's recorded bidding,
   reaches a contract on each side, and scores both via DDS. Tells us
   nothing about cardplay strength because DDS plays both sides
   omnisciently.

2. **Compare cardplay only** — Q-Plus's recorded bidding is used as
   the contract for BOTH sides. Q-Plus's cardplay engine plays the
   deal as recorded; biq's MC+DDS engine plays the same contract on
   the same deal. Compare actual tricks taken. This isolates cardplay
   strength.

3. **Compare end-to-end performance** — deal → biq bids → biq plays
   vs deal → Q-Plus bids → Q-Plus plays. The fullest comparison;
   conflates bidding and cardplay strength but matches what a user
   would see at the table.

### Implementation notes

* The widget belongs on each corpus tab (not in Calibration / Help).
* State 2 needs Q-Plus's bidding history extractable from the
  `savescore.qss` per-deal blocks — `parse_bdl_with_systems` in
  `tools/qplus_mixed_corpus.py` already returns this; expose the
  per-deal auction tokens so biq's cardplay engine gets the same
  auction inferences Q-Plus's declarer used.
* State 2 and 3 require Q-Plus's actual played-tricks count to be
  parsed from the QSS. Q-Plus writes this on `save match and exit`;
  the current `mixed_corpus_diff.py` ignores it in favour of
  re-running DDS on the contract. The parser would need to surface
  the trick count per deal so the comparison report can show
  Q-Plus-actual vs biq-MC+DDS.
* `tools/mixed_corpus_diff.py` would grow a `--mode {bidding,
  cardplay, end-to-end}` flag matching the widget state.
* For state 2 the report header should make it explicit that BOTH
  sides played the same contract — otherwise it's not interpretable.

### Why this matters

The current diff tool produces **bidding-only** numbers. All the
"+1.82 IMP/deal" / "+0.59 IMP/deal" results from the polish session
are pure bidding gaps. We have no measurement of whether biq's
MC+DDS cardplay is competitive with Q-Plus's commercial engine.
Until states 2 and 3 exist, end-to-end strength claims are
extrapolations.

## Cardplay benchmarking — three planned harnesses

The current `tools/mixed_corpus_diff.py --mode cardplay` plays biq
on ALL four seats vs Q-Plus's recorded play, then scores by IMP.
This biq-vs-biq symmetry CANCELS declarer-side improvements:
biq's improved defender plays equally well against biq's improved
declarer, so trick-delta barely shifts. Confirmed empirically —
defender-only rules show positive gains, declarer rules don't.

To measure asymmetric improvements honestly we need harnesses
where biq plays ONE side and a different engine plays the other.

### Plan 1 — QSS replay harness (single-seat biq vs recorded Q-Plus)
**File**: `tools/mixed_corpus_diff.py` — add `--mode replay`.

For each deal × each of the 4 seats:
- Replay the deal trick-by-trick from the QSS.
- For the 3 non-biq seats, play Q-Plus's recorded card.
- For biq's seat, biq's planner/MC decides.
- Validate biq's card is legal; track wins/losses.
- Aggregate per-seat trick-delta vs Q-Plus's seat performance.

Yields 4 isolated measurements per deal:
- biq-as-N declarer/defender tricks vs Q-Plus's N tricks.
- Same for E, S, W.

Each is an HONEST measure of biq's skill at that seat. Symmetric
biq-vs-biq cancelation gone.

**Effort**: ~100 lines harness, reuses QSS parser, planner, MC.
**Status**: TO BUILD FIRST.

### Plan 2 — Multi-biq-bot self-play (4 distinct configs)
**File**: new `tools/multi_bot_diff.py`.

Run cardplay with 4 different biq configs at the 4 seats:
- biq-A = Phase 15 baseline (committed best)
- biq-B = Phase 15 + Phase 23 entries
- biq-C = Phase 15 + Phase 23 + 25 (K-loc finesse)
- biq-D = all attempted items

For this to work, the planner must accept a config object per
call (currently it's module-global). ~50 lines of refactor.

Each variant is biased to fire/suppress different phases. Across
many deals, the variant taking the most declarer tricks on its
contracts wins. Head-to-head comparison.

Useful for:
- A/B testing planner additions without biq-vs-biq symmetry.
- AlphaZero-style training later (loser's config trains toward
  winner's, if/when we add learned components).

**Effort**: ~50 lines planner refactor + ~150 lines harness.
**Status**: TO BUILD SECOND.

### Plan 3 — Q-NET TCP protocol RE (live biq vs Q-Plus over network)
Q-Plus 17.1 ships `Q-NET.EXE` (2.8 MB, beside `QBRIDGE.EXE`).
Architecture: `QBRIDGE.EXE` ←DDE→ `Q-NET.EXE` ←TCP→ remote
`Q-NET.EXE` ←DDE→ remote `QBRIDGE.EXE`. Commands recovered from
strings:
```
DDE_CMD_CONNECT / DISCONNECT / START_SERVER / STOP_SERVER
DDE_CMD_DIRECT_MESSAGE / NET_COMMAND / RESEND_MESSAGE
DDE_REQ_STATE / EXIT
```

No documentation ships for the wire protocol. Reverse-engineering
path:
1. Run two Q-Plus instances locally under Wine.
2. Configure one as bridge server, the other as client.
3. Capture TCP traffic with tcpdump/Wireshark.
4. Decode message format (probably framed binary with a header
   indicating command type).
5. biq implements a client speaking that protocol.

Enables LIVE interactive play between biq and Q-Plus — biq's bids
get factored into Q-Plus's auction; Q-Plus's cardplay adapts to
biq's plays. Useful for genuine competitive testing.

**Effort**: 2-3 days RE + ~500 lines of protocol client.
**Status**: TO BUILD THIRD.

## biq as Q-NET SERVER, Q-Plus as client (DEFERRED 2026-06-06)

The mirror of Plan 3: make **biq host** a live match that a **Q-Plus
client** joins over Q-NET, rendered in biq's GUI. Paused mid-build; this
section captures the design, what's done, and what's left so it can be
resumed cleanly.

### Critical gotcha — two DIFFERENT server protocols

biq's GUI **"Network → Start bridge server"** (`network/server.py`,
`client.py`, the lobby dialog) speaks biq's **NATIVE protocol: JSON
objects, newline-delimited** (`network/protocol.py`). It is for **biq↔biq**
play only (one biq client per seat). **Q-Plus CANNOT join it** — Q-Plus
speaks Q-NET (plain-text bracketed tokens, `"cmd" [arg]...`). A Q-Plus
client connects the TCP socket ("Connected to server") but its `join_game`
handshake is unintelligible to biq's JSON server, so the seat stays "not
conn." and Join does nothing. Confirmed live 2026-06-06. **Keep the two
paths separate: biq-native lobby stays for biq↔biq; the Q-NET host path is
additive and must never break it.**

### Architecture chosen (and why)

Do NOT marry Q-NET into the event-driven `NetworkGameController` (high
risk, untestable without live Q-Plus). Instead **wrap the proven
`tools/biq_qnet_server.py` `BiqServer` (synchronous Q-NET match loop) in a
`QThread`**; its callbacks emit Qt signals that drive the GUI table +
status strip live. biq↔biq native server and the `biq_qnet_server` CLI are
both untouched. Validate via the biq-client↔biq-server loopback
(`biq_qnet_client` stands in for Q-Plus — same wire format).

### Status

- **DONE — `BiqServer` callbacks** (committed-pending). `__init__` takes
  `callbacks={}` (no-ops by default → CLI unchanged); `_emit()` fires
  `status`/`deal`/`bid`/`contract`/`card`/`board_done`; `stop()` for
  thread shutdown. Verified: constructs + emits.
- **TO BUILD — `QNetServerThread`**: QThread running
  `accept()`/`handshake()`/`run_match()`, callbacks → queued Qt signals.
- **TO BUILD — GUI action + handlers**: a menu action ("Start Q-NET server
  (Q-Plus client)…"), handlers that render deal/auction/contract/running
  score, East shown as 🖧 Network (reuse `table_view.set_seat_types` +
  the new status strip).

### The THREE setups and their MEASUREMENT value (decision context)

Measurement quality tracks how FEW seats are biq (less biq-vs-biq
cancellation — see the cardplay-benchmarking section above):

1. **biq host + 1 Q-Plus client** — biq plays 3 seats (N/S/W), Q-Plus 1
   (E). Closed room = all-biq, double-dummy. **Poor measurement**: biq is
   3/4 → cancellation dominates; baseline re-bids + is DD (muddy). Value is
   only as a **protocol/GUI proof + demo**. This is the in-progress build.
2. **Q-Plus host + 1 biq client** (the PROVEN `biq_qnet_client` runs) — biq
   1 seat (E), Q-Plus 3 + its own all-Q-Plus real-play closed room. **Clean
   single-seat** biq-vs-Q-Plus (no cancellation, biq is 1/4). Caveat: biq's
   partner is a Q-Plus bot, so limited bidding signal; mind the deal-
   rotation trap (use a fixed BDE deck).
3. **biq host + Q-Plus E/W pair** (multi-client, TO BUILD) — biq N/S pair
   vs Q-Plus E/W pair (2 bots). All-biq closed room (N/S held biq) isolates
   the WHOLE E/W pair → **best measurement** (full external pair, no
   cancellation). Needs: multi-client `BiqServer` (seat→conn map + per-seat
   routing; currently 1 client) and EITHER two Q-Plus client instances
   (one joins E, one W) OR one client driving both. For a clean pair number
   upgrade the closed room from all-biq-DD to real biq E/W play, or use the
   double-pair swap (`tools/double_pair_compare.py`).

### Open Q-Plus-side unknowns (verify live before Setup 3)

- Will a Q-Plus **client** auto-play a **Computer bot** at its joined seat,
  or insist on a human there? (In proven runs biq was the bot; Q-Plus-
  client-as-bot is unconfirmed.)
- Can **two Q-Plus client instances** connect to one server (for the E/W
  pair)? If either fails, the pair comparison stays on Setup 2 (Q-Plus as
  server).

### Resume order

Finish Setup 1 (QThread + GUI handlers) as the plumbing/demo proof → quick
live Q-Plus-client-as-bot check → if it passes, build multi-client for
Setup 3 (the real measurement target). See memory
[[project_biq_qnet_server]] and [[project_biq_validation_plan]].

## Related memory

* `plan_option1_semantic_state.md` — AuctionContext architecture
* `project_biq_qplus_parity.md` — corpus baseline + polish history
* `plan_slam_bidding_architecture.md` — the original 5-phase plan
  (superseded by Option 1)
