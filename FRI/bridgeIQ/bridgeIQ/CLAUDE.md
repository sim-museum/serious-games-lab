# biq — Claude Code project notes

## STATUS — 2/1 catch-all rules from Q-Plus's recorded calls (2026-10-16 night, committed 10-17)
* New plan (user, 10-16): map bidding weaknesses in groups instead of fixing the worst boards of each
  run. New tool `tools/qplus_rules_ab.py`: `scan` = biq's RULES on every recorded Q-Plus call (17,420
  2/1 calls in ~8 min on 2 cores; "origin" = function that returned a reasonless pass), `changed` =
  old vs new call on the changed calls only, both rolled out with the new code (no drift, unlike
  qplus_agreement's IMP totals). Data: tools/runs/agreement/261016_{21,prec}_rules_*.jsonl.
* Costliest 2/1 catch-alls (rules rollouts vs Q-Plus's call): reasonless pass at the end of
  `_generic_responder_rebid` -463 / 162, `_opener_rebid` (weak-two opener after 2NT) -255, "Overcaller
  rebid - no clear extras, pass" -218, `_opener_suit_rebid` end -202, `_advance_partner_overcall` -167,
  "Sanity: illegal -> pass" -143, "Sanity: raise partner's suit" -138.
* Fixes in native_bidder (each behind a switch): `_cue_continuation` (BIQ_CUE_CONT): partner's new
  suit at 4+ after a fit / my weak two = cue (cue an ace below game, else back to trumps), 5NT = GSF,
  contested version after my overcall when partner cue-bids their suit; `_minors_4nt_advance`
  (BIQ_MINORS_4NT): (4M)-4NT = minors; opener rebid (BIQ_OPENER_FALLBACK): reverse with 16+ (Q-Plus
  5/5), 4-4-4-1 shows the 1-level suit, best-lie 1NT to 15, no reverse into a 1-level suit or with a
  balanced hand; forced fallback (BIQ_FORCED_NT_FIRST): responder's new suit at the 3 level is forcing,
  NT before raising partner's new suit with 3 (or a minor past 3NT with 4), two-card raise of
  partner's rebid suit, passed partner's 1-level new suit passable.
* Result (rules only): 2/1 87 calls changed, agreement 12,931 -> 12,989, +489 IMP (SE 79; 55 better,
  12 worse); Precision 52 changed, 8,024 -> 8,046, +205 (SE 46). T-* cases, 259 checks. Not yet
  run with the simulation or live.
* First full 2/1 qplus_agreement benchmark (code before these fixes, 08adaf9c):
  tools/runs/agreement/261016_21_bid.{jsonl,txt}: 74.6% agreement, -183 IMP (-0.011/call); competitive
  -522 / 6,491. Reasonless pass -795 / 847: responder rebid -386/129, weak-two opener -218/56,
  advance overcall -168/69, opener suit rebid -133/41, openings Q-Plus makes -73/81.
* Simulation on (10-17), changed positions only, old = benchmark code, new = af3873bb: 2/1 80 calls
  changed, +462 IMP (SE 76; agreement there 9 -> 60); Precision 49 changed, +181 (SE 47). The
  rules-only gain holds. `qplus_rules_ab.py scan --sim --only ROWS.jsonl` does this in minutes
  (export the commit with `git archive` to a scratch dir; run the old code from tools/runs/code/).
* Committed 10-17: `_answer_opener_double` (BIQ_ANSWER_OPENER_DBL): 1x-P-1y-(2z)-X is takeout,
  with <=3 of their suit bid partner's suit with 4+, else my suit, else partner's with 3, at most
  the 3 level (Q-Plus bid 15 of 20, biq passed all). Weak twos the Q-Plus way (BIQ_WEAK_TWO_QPLUS):
  any 6-card major 5-9 HCP non-vul, vul 7-9 with suit-HCP 2+, no weak 2D under 7 HCP (Q-Plus 0/10),
  7-card major with suit-HCP <=3 and 5-6 HCP opens 2M. Rules only: 2/1 +43 IMP / 42 changed (SE 40,
  agreement +22), Precision +45 / 17 (SE 26). T-dbl-a..d, 263 checks.
* Remaining responder-rebid and overcaller-rebid passes are scattered single hands (slam and
  high-level competitive judgment); uncontested responder-rebid passes are net positive by the
  benchmark.
* Illegal-call -> pass group (2/1, 270 calls): Q-Plus also passes 168 of them; the losses are high
  competitive raises over their jumps (left alone) and my strong 2C's later rounds, where
  `_opener_rebid`'s 2C branch (no round check) re-fires its first-rebid 2H/2S/3NT. Fix:
  `_strong_2c_slam_ask` (BIQ_STRONG_2C_ASK): that illegal call -> pass becomes 4NT over partner's
  4-level suit call (Q-Plus 4NT; not over 3NT or 3-level calls). 2/1 rules +109 IMP / 13 changed
  (SE 33), sim on +105 (SE 32). T-2c-ask, 264 checks. Partner's 4NT reply after 2C is weak: in 3
  rollouts partner passed 4NT (2C-2S-2NT-3C-3H-3S-4H-4S-4NT; after 3NT-4C). Committed 10-17; played from board 1 of
  run 261017_qplus_21_prec_biqS (planner family s2c_slam).
* Next: partner's answer to the strong 2C opener's 4NT; unassuming cue-bid limit raise (-106/22);
  pulls of partner's high doubles (Q-Plus sits 33/43, no clean rule).

## STATUS — 2/1 + Precision 10 h run (2026-10-15/16, committed)
* Run `tools/runs/bluechip/261015_qplus_21_prec_biqS` (seed 261015, RESUME.txt there) played 20:33-09:47:
  310 boards -918 IMP. 2/1 1-128 -408 (random -2.64/bd); Precision 129-310 -510 (random -0.71 before the
  board-227 swap, -2.41 after). Stopped: Precision West window froze on board 311 (TM SeatTimeout 900 s).
* Precision strong 1C the Q-Plus way: opener over 1C-1H (balanced, switch) bids 1S with five spades, 1NT
  16-21, 2NT 22 (BIQ_REBID_1C1H); 1C-1M with 3+ trumps raises 2M, then RKC with 19+ / 17+ and 6 controls
  (BIQ_RAISE_1C1M); responder's second call `_prec_1c_resp2` (BIQ_RESP2_1C): raise opener's major, 4-card
  major at the 2 level, raise a minor, rebid six, new suit, else 2NT (agreement on 200 recorded Q-Plus
  responder calls 71 -> 117; p1c_resp -4.00 -> -1.57/bd). Splinter has_ace KeyError fixed.
* Agreement benchmark (10,924 Q-Plus Precision calls) 73.4% -> 73.6%; it found 5-level jumps from the
  agreed-cue rule in `_safe_forced_bid` (1D-2D-2H-5D); fixed after the run (BIQ_CUE_AGREED_STRICT), not
  yet played. Weak spots still: preempt_save -6.78/bd (5-level saves vs their making slam), p1c_pos
  -3.54/bd (missed slams after 1C-1M). 240 checks.

## STATUS — French (Benjamin) made playable; Acol + French 10 h run (2026-10-14/15, committed)
* Run 261014_qplus_acol_french_biqS played 20:42-06:53: 245 boards, Acol 1-128 -2.69/bd (random -2.83,
  last code -1.67 over 18), French 129-245 -1.97/bd (random -3.52, last code -2.36 over 42). 11 live
  swaps (RESUME.txt there): Acol strong-two raise = 4+ HCP (4M = no ace), 2C with 22+ / 20+ and 8 playing
  tricks, 2C answers per negative-2D (3NT 11-13, 2NT 8-10...), 2C-2D long-minor rebid, 1M-2m natural
  without forcing 1NT, splinter reply 4M; French 1NT-(Landy)-2M = stopper, GF jump shift to 2, no
  legalized simple raise, splinter slam eval. 229 checks. The French North window began logging at
  ~06:20 (log-057.bdl) and slowed the table to a stop: check B-PREFER no_logging for every window.
* The SAYC + Acol run below played 00:37-10:43 (260 boards; random SAYC -2.33, Acol -2.59 IMP/bd).
* Run `tools/runs/bluechip/261014_qplus_acol_french_biqS` (seed 261014, RESUME.txt there): Acol
  windows first, French (F-FRA-M) spares, handover after 128 boards; French planner families
  benj2d_resp/open, benj2c_resp/open, gamb3nt, nt_minor, wk2m_resp/open.
* biq read Q-Plus's French as SAYC: weak 2D (Q-Plus: Benjamin game force), 2C with 24+ (Q-Plus:
  passable), partner's 2D "preemptively raised". Fixed (`_benjamin`, BIQ_BENJAMIN=0 to disable):
  Benjamin 2C/2D openings, answers, rebids; later 2D rounds read as a GF 2C (`_benj_view`, like
  `_switch_1c_view`); minor transfers 1NT-2S/3C, Stayman 2NT = both majors, 1NT-4D, gambling 3NT
  (4C pass-or-correct; not Gerber in auction_context). All strong-2C systems: 2C-2D-2M-? no longer
  "prefers" the artificial 2C (`_strong_2c_second`); 2D waiting floor 0. Acol: X after partner's
  overcalled strong two; over a weak 1NT 6-4 majors bid the six-card major, Landy / 2M from 8 HCP.
  test_qplus_match_fixes.py 211 checks (A-/S-/F- cases).

## STATUS — Standard Acol made playable vs Q-Plus; SAYC + Acol run prepared (2026-10-14, UNCOMMITTED)
* Run `tools/runs/bluechip/261013_qplus_sayc_acol_biqS` (seed 261013, RESUME.txt there): SAYC
  windows first, Standard Acol (B-ACL-S) spares, handover after 128 boards; plan.json
  families_by_segment (planner `active_segment()`); new Acol families wnt_ovc, wnt_x, wnt_5spade,
  s2_open, s2_resp. Not started yet: `bash restart_continuous.sh`, user joins N/E/W twice.
* biq's Acol had read Q-Plus's strong twos (2D/2H/2S 18-22, forcing) as weak twos and played
  transfers Q-Plus's Acol doesn't. Fixed, all gated by the .RCE flags (`_strong_two`,
  `_nt_transfers`; BIQ_STRONG_TWOS=0 / BIQ_NAT_NT_ANSWERS=0): strong twos (open, 2NT negative,
  positives, rebids, defence, inference), no weak 2D, 1NT without a 5-card major (rebid 2M with
  12-14), natural 1NT/2NT answers, 2NT 21-22 / 2C 23+, rebid ranges 15-16 / 17-18 / 19+.
  bidder_teams_ab Acol +94 / +72 IMP per 800; other systems 0 boards differ. A-* regression cases.
* Open: SAYC 1m-2NT (Q-Plus file 13-15, biq 10-12); 1NT-X weak runouts in Acol (wnt_x family).

## STATUS — continuous Q-Plus match, live code swaps, 11 h unattended (2026-10-13)
* Run `tools/runs/bluechip/261009_qplus_21_biqS` (RESUME.txt there): boards
  755-1038 unattended 00:06-11:12, 2/1 for 100 boards then a scheduled
  handover to a second set of Q-Plus windows playing Precision; stopped when
  a Precision window froze 185 boards in (the known Q-Plus limit). Random
  boards: 2/1 -2.78/bd (SE 0.87, 49), Precision -3.38 (SE 0.75, 65); the
  match before was -2.46 over 754: no measurable change either way.
* TM (`biq_bluechip_tm.py --continuous`): queue.jsonl deals, hot code swap
  from immutable snapshots (tools/runs/code/, `tools/biq_deploy.py` with
  regression gates), spare windows + failover, segments.json (bidding
  system per window set, scheduled or on-failure handover).
  `tools/biq_planner.py`: random + Thompson-sampled targeted families,
  report.md per segment / code version; targeted deals now use natural
  shape frequencies (uniform shapes dealt 10-13 card suits).
* Bidding fixes deployed live (each with benchmark evidence, in
  native_bidder): double-their-save only over our constructive game, their
  first 5-level call, not after their 4NT (boards 1-962: 31 spots, 22 down,
  +88 IMP); game on 8.5+ playing tricks over a preempt; sanity 2l never
  passes partner's cue-bid of their suit (benchmark: 18 spots, Q-Plus bid
  on in all). Also from 10-11/12: Multi-Landy for 2/1, weak-two 2NT
  forcing, save over partner's preempt raise, 3rd/4th-seat strong 4-card
  majors, no 1NT with a strong 5-card spade suit.
* Open: hand evaluation on wild distribution (overcaller passes 7-5 /
  two-suiters, missed slams); GF after interference (877: 1NT-(2S)-3H-(3S)
  -P-(P)-4D passed); defence giving 1-3 tricks over DD (758, 797, 858).

## STATUS — forced-pass and advancer bidding fixes (2026-10-10)
* 2/1 run boards 187-292 sorted by contract vs play (DD): bidding -265 IMP,
  play -36. Two bugs, fixed in `native_bidder.py`:
  - partner's forcing call with no rule fell through to a reasonless pass
    (4m after my NT, 1NT-2C-x-3m, cue after a super-accept, 2NT game try
    after 1x-1M-2M): `_forced_continuation` via sanity check 2k; its
    "Forcing:" calls are kept from the bidding simulation;
  - the advancer was routed to `_overcaller_rebid` ("no clear extras,
    pass"): `_advancer_rebid`; also leaping Michaels in `_michaels_by` and
    the takeout X after our 1NT overcall (Q-Plus C-1NT-takeout.after-nat-2).
* Only the decisions whose rule call changed were rerun (simulation + cost):
  Precision 29 of 10924, same call as Q-Plus 6 -> 15, IMP vs Q-Plus's call
  -107 -> +53; 2/1 21 of 5007, 4 -> 12, -102 -> -7. Live in the 2/1 run
  from board 320 (RESUME.txt there).
* Open: biq reads 4NT after a cue-bid as quantitative (so the 4m slam try
  signs off in 5m); the TM does not pass Q-Plus's alerts to biq.
* A worktree outside FRI/ finds no Q-Plus .RCE files (bidding_systems walks
  up for WP/): export WINEPREFIX=~/sgl/FRI/WP there.

## STATUS — defence searches 40 layouts; agreement benchmark (2026-10-10)
* `nopeek._AMU_WORLDS` default 10 -> 40 (defence alpha-mu; declarer uses the
  Monte-Carlo branch). Card benchmark, 4000 Q-Plus cards: defence after the
  opening lead 56 DD tricks given up vs 78 / 74 with 10 layouts (two runs,
  noise ~6), Q-Plus 45; all cards 126 vs 145 / 139, Q-Plus 125. Live 12 s
  budget: 2.6 s mean, 7 s p90, 2 / 150 budget hits. Opening leads (26 vs
  Q-Plus 19, lead_sim) unchanged: next card-play target.
* Agreement benchmark `tools/qplus_agreement.py`: biq vs
  every recorded Q-Plus Precision call (73.4% same call; competitive 63.7%,
  uncontested 57.5%) and a fixed 4000-card sample (65.8% same card, 96.9%
  DD-equal). Results in tools/runs/agreement/.
* 2/1 run `tools/runs/bluechip/261009_qplus_21_biqS`: -593 / 186 boards
  (-3.19/bd) on the 10-layout code; from board 187 on, 40 layouts.
  Q-Plus windows froze twice when the user touched them (RESUME.txt).

## STATUS — Monte-Carlo declarer; run 2 at 369 boards (2026-10-09, UNCOMMITTED)
* Run `tools/runs/bluechip/261007_qplus_biqS` resumed at 185 and stopped
  again at 370 (the East window hung, as before; RESUME.txt there): boards
  185-369 -281 IMP, total -697 / 369 (-1.89/bd).
* biq's DECLARER now plays plain Monte-Carlo (`nopeek._DECL_PIMC`,
  BIQ_DECL_PIMC=60 layouts, DD average, natural tie-break) instead of
  alpha-mu; BIQ_DECL_PIMC=0 restores alpha-mu. Defence is unchanged.
  decl1 replay (96 x 3NT vs scripted Q-Plus defence): 987 tricks / 89 made
  vs alpha-mu 945 / 83 (Q-Plus 1005 / 93, DD 978). Alpha-mu worlds 30,
  depth 3, longer budget and a long-suit lead tie-break: 939-952, so not a
  tuning problem. Belief-level diagnostic (60 samples per costly card):
  biq's card was >= 0.5 tr worse than the best on average 13 times vs
  Q-Plus 4. Paired A/B on 298 random SAYC deals (no-peek, all four seats,
  seed 91): +0.218 tr/deal (SE 0.056), +185 IMP, 99 wins / 42 losses; NT
  +0.27 (SE 0.12), suit +0.19 (SE 0.06). About 8x faster per card.
  test_decl_pimc.py (branch taken, legal, no peek).
* test_competitive_fit.py and test_multi_client.py fail with or without
  this change (pre-existing).

## STATUS — biq + 3 Q-Plus run 2; 1C answer switch; declarer probe (2026-10-08, UNCOMMITTED)
* Run `tools/runs/bluechip/261007_qplus_biqS` (biq South, Q-Plus N/E/W,
  Precision, seed 261009): -416 IMP / 184 boards (-2.26/bd); bidding -395
  by DD, play -21. Stopped when the East window hung on board 185
  (RESUME.txt there).
* Q-Plus's Precision swaps the positive answers to 1C
  (`A-artificial-1C.switch-1NT-1H`): 1C-1H = 8+ balanced, 1C-1NT = 5+
  hearts. biq had the flag but read 1H as hearts (board 58: 1C-1H-4NT-7NT
  X, -16). `native_bidder._switch_1c_view`: rules see the answer swapped
  back, biq's own answer is swapped out, opener's 1C-1H-1NT (16-21) <->
  rules' 2NT; balanced 14+ answers 1H too. BIQ_SWITCH_1C=0 disables.
  NTX_RUN escape now 0-2 HCP only (Q-Plus passes with 3-4). Q4-* tests,
  174 checks. Rules-only Precision par A/B, 2000 deals: +0.006/deal (SE
  0.013), neutral as expected; the gain is with a Q-Plus partner.
* Declarer probe (decl1, 96 x 3NT): biq declaring the same contracts takes
  945 tricks vs Q-Plus 1005 (DD 978); the gap is NOT the probed club
  combinations but leads/third-hand play in the other suits. BACKLOG top.

## STATUS — biq + 3 Q-Plus; selective signalling (2026-10-05)
Full write-up: tools/HARNESS_STATUS_2026-09-30.md, last section.
* biq South with Q-Plus N/E/W (`--remote N,E,W`): -2.72 IMP/board over 87
  boards (bidding -158, play -79). TM: ready/card timeouts, board replay,
  no alert relay, mixed-seat score sign fixed.
* Bidding fixes behind BIQ_* switches (QUANT_NO_GERBER, NTX_RUN,
  BALANCE_ACT, GF_3NT, SHAPE_ACT, DBL_RESCUE, GF_MAJOR, PREC_4M_RAISE,
  PRE_X_MAJORS; TOX_PULL off). Par A/B +0.01 IMP/deal both systems.
* Signals like Q-Plus: count only when partner may hold the A/K (a
  decision), attitude only with the honour that matters, first round only;
  the signal margin never swaps a winning/honour card for a spot.
  BIQ_SIGNAL_SELECTIVE / BIQ_SIGNAL_SAME_CLASS. Reader mirrors the emitter.

## STATUS — fixes mined from the Precision run vs Q-Plus (2026-10-04 night)
Full write-up: tools/HARNESS_STATUS_2026-09-30.md, last section. Legalizer
no longer bumps artificial / repeated calls, Landy gate, light 3rd-seat
majors, 1M-1NT-2M invites, simulation keeps the rules' overcalls and
takeout-double advances, card-play sampler uses the match system and the
suit lengths natural calls promised. Offline ~+0.01 IMP/deal; card play
neutral. Biggest play gap: biq's DECLARER play (0.77 vs 0.42 tricks/board).

## STATUS — slam bidding, mostly Precision (2026-10-04 evening)
Full write-up: tools/HARNESS_STATUS_2026-09-30.md, "Slam bidding, mostly
Precision".
* Precision strong-club auctions now reach slam: 1C-1NT/3NT ranges, 1C-3NT,
  quantitative 4NT accepted on the right range, system-aware slam floors,
  partner's rebid suit as a fit for RKC. BIQ_SLAM_* switches disable parts.
* Precision: +0.050 IMP/deal closer to par (slams 54 -> 73 of 508, phantoms
  41 -> 37); teams +0.11/board. SAYC +0.011. Partner tables rebuilt.

## STATUS — learned partner ranges + game check (2026-10-04)
Full write-up: tools/HARNESS_STATUS_2026-09-30.md, "Overnight match vs
WBridge5 and learned partner ranges". Overnight
Blue Chip match vs WBridge5: -4.46 IMP/board (bidding -2.0, play -2.5).
* backend/partner_model.py: partner's HCP / suit lengths at every turn,
  LEARNED from 300k biq self-play deals (backend/data/biq_partner_profiles
  .json.gz). Rebuild with tools/biq_profile_build.py after bidder changes
  that alter what calls mean; test_partner_model.py warns when stale.
* native_bidder._learned_game_net: rules pass below game -> 4M / 3NT / 5m
  when my points + partner's learned mean reach 25 / 24 / 29.
  BIQ_GAME_NET=0 disables.
* A/B vs previous bidder: +0.14 IMP/deal closer to par on 4000 held-out
  WBridge5 deals; teams +0.27 / +0.40 per board DD, +0.21 / +0.18 robust.

## STATUS — alerts over Q-NET, Precision GF, wacky audit (2026-09-30, UNCOMMITTED)
Full write-up: tools/HARNESS_STATUS_2026-09-30.md. Offline only; no live run.
* Q-NET carries NO alerts: partner's strong 1C / 2C, Jacoby 2NT, splinters,
  Michaels ... arrived unalerted and the rules (which key on `.alert`) misread
  them live; the offline A/B kept alerts so it never showed. Fix:
  `native_bidder._mark_system_alerts` (in decide_bid) re-alerts every call of
  MY side that biq's own rules would alert there (`_rules_alert`: 400 seeded
  random hands, majority vote, cached). bidder_teams_ab now strips other
  seats' alerts by default (`--keep-alerts` = old). bid_sim still gets the
  WIRE state (its gate was tuned live) and is skipped when partner forced.
* Precision: 1C-1NT never set GF (auction_context skipped NT before the GF
  check) -> 1C-1NT-2S-3S passed twice live. Plus 1C-(X)-P-(P)-1S raise, 1C-2D
  4-card major, 2C-(ovc) 4C LAW, run from 1NT opener's double of 2S.
* ~30 SAYC rule fixes from the miner + `tools/wacky_audit.py` (W-* cases in
  test_qplus_match_fixes.py, 113 checks). Sanity: a pass after an OPPONENT's
  call never drops partner's force (`partner_spoke_last`); never pass
  partner's cue-bid in an agreed major.
* wacky audit (894 deals): wacky calls 1.1/100 deals (-81), weak calls
  3.8/100 (-320, the bigger leak), wacky cards 2/100. Card play loss is
  diffuse (wrong-suit mid-hand leads; tools/lead_choice_study.py), no rule fix.
* A/B vs committed bidder (wire view), held-out seed 81, 1200 bds/system:
  SAYC +0.17, Precision +0.16 IMP/bd (SE 0.05); some new rules pruned after
  an attribution showed them losing on the robust judge.
* Card play: tools/play_replay_bench.py replays 2247 real biq decisions from
  the matches. Fixed: honour "signals" (K from K-T), alpha-mu never collapsed
  touching cards, budget stop dropped the last cards in suit order (now
  best-first). 510 -> 455 DD tricks (-11%). Env: BIQ_SIGNAL_SAFE,
  BIQ_AMU_COLLAPSE, BIQ_AMU_ORDER (all default 1).
* biq_match.py --version latest|previous|<git ref>|<bidder fingerprint>
  (--previous/--latest, --list-versions): runs the clients from a git export
  in tools/runs/versions/<commit>/ so a live A/B half can run while backend/
  is being edited. Run 18 (previous, SAYC, FRESH64J): -116 = -1.81/bd
  One closed room per system per A/B set is enough (Q-Plus is deterministic;
  tools/qss_merge_closed.py scores an open-room-only sheet).
* LIVE A/B SAYC (runs 18 prev -1.81, 19 latest -1.16): paired +55 IMP
  (+0.86/bd, SE 0.57; bidding +29, play +26). BUT deck "FRESH64K" was a copy
  of FRESH64G (seed reuse) = in-sample; ~+47 without directly tuned boards.
  gen_test_deck.py now refuses decks that repeat any deal; fresh decks
  FRESH64L (261001), FRESH64M (261002). J/K deleted.
* All five systems offline: tools/system_matrix.py (25 N/S x E/W tables,
  DD + par; `report --vs SAYC` = first-divergence attribution). Fixed
  Precision NAMYATS/2D-doubled/1D-2NT/Bergen, inverted minors (2/1, Prec),
  French clubs transfer/support X/Ghestem/Truscott RKC/Garbage Stayman,
  Acol weak-NT upgrade/suit order/big raise, Ogust continuation. Held-out
  per-system A/B 0 to +0.08 IMP/bd, none negative after two corrections.

## STATUS — FRESH64I live runs (2026-09-28)
Run 15 hybrid SAYC -93 / 64 = -1.45/bd (best yet); run 16 rules-only -109 =
-1.70/bd (best rules score; earlier -2.1..-2.8); run 17 Precision hybrid
-109 / 63 = -1.73 (boards 2-64; a false start used board 1, so Q-Plus ran
out of deals at the harness's 64th). PAIRED hybrid - rules +20 (+0.31/bd,
SE 0.58); per deck so far: G +0.28, H +1.20, I +0.31.
Simulation calls by type over paired decks G(part)/H/I: PASS instead of the
rules' call 21 boards +84 IMP; DOUBLE 13 boards +1 (I: -32); other bid 8
boards -6. Doubles that REPLACED the rules' own bid lost 22 on 4 boards (bds
42/43: X of their 4m save instead of our making 4S); doubles instead of a
pass won 11 on 5. Change: bid_sim.candidates offers X only when the rule
call is pass/double. Profiles rebuilt with deck I.
Results tools/runs/results/run15-17*.qss, logs tools/runs/ab/run15-17*.

## STATUS — FRESH64H live runs (2026-09-27/28)
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
