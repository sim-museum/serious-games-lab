# biq — Claude Code project notes

## STATUS — tester's laptop report fixes (2026-10-23, UNCOMMITTED)
A strong player tested biq on a laptop (1366x768 + 1920x1080 HDMI) on 10-22. Bundle unpacked
in the session scratchpad (laptop_bundle/). The laptop ran origin/main (a585eeaa), which split
from this work on 09-22 (fd85220b): none of sprints 1-185 were in it. biq work lives on
biq-qplus-strength. Also: with no Q-Plus install, get_system() uses the hand-coded fallbacks
(0 RCE flags on vs 177 for 2/1, 199 for Precision; RKC 1430), so any machine without Q-Plus
plays a much weaker biq. Fixed here:
- bid_descriptions: WJO label only on a JUMP and only on the side's first action (1H-2C was
  "weak jump overcall"; so were partner's raises). Advances: raise / own-suit rebid labels.
- coach_notes: X/negative double only suggested when X is legal; partner-acted branch.
- Available-bids list offered X/XX after partner's call; bidding box enabled XX over
  partner's double. Both now need an opponent's call (0 or 2 passes since).
- Hint used engine.get_card_play (lowest-card FALLBACK). Hint and blunder check now share
  nopeek.decide via _biq_card_choice (cached per position); blunder measured vs that card.
- Closed room (match_controller) played every card but the lead with get_card_play
  (first legal = high cards). Now nopeek.decide (~1.5 s/card, runs during the human's play).
- Claude calls: stdin=DEVNULL everywhere; hand analysis + deal analysis got Cancel + elapsed
  time; deal_analysis crash (RuntimeError QDialog deleted, the 22:51 log) guarded.
- Score table rows in play order (random boards carry random numbers 1-999).
- After each hand, the score sheet no longer pops over the end-of-hand summary.
- Trick counter reads "NS 5 – EW 4".
Then (user: vector cards, layout pass, own convention settings, signalling dialog, merge):
- Cards: public-domain vector deck (Byron Knoll via notpeter/Vector-Playing-Cards) in
  ui/assets/deck/svg/*.svgz, rendered per size x devicePixelRatio; four-colour by swapping the
  SVG fills; vector-drawn back. The 100x140 PNGs stay only as a fallback.
- Layout (1920x1080 is the target): the bidding box is a table overlay beside the felt (next
  to the auction), the bid-info panel runs top-left down to South's label with most of its
  height for the available bids (labels were boxed by a cascading border style). The hidden
  analysis view no longer forces the window's minimum height (it was 1061 px, taller than a
  1080 screen); it sits in a scroll area. Cards scale below 1920x1080 (set_card_scale); at
  1366x768 the bidding screen fits, East dummy still clips in play (laptop is nice-to-have).
- Systems: biq NEVER reads Q-Plus files (user rule). get_system() loads biq's own
  backend/data/systems/<name>.json (flags identical to the .RCE files they came from; 54 system
  tests + 528 match checks pass without WINEPREFIX), else the hand-coded fallbacks. The .RCE
  parser and Q-Plus path search were removed.
- Signalling: the first time a human defender's card doesn't fit biq's conventions, a one-time
  dialog (pref signal_help_shown) shows the card expected and biq's carding agreements.
- BUILD INTEGRITY CHECK at startup (backend/build_check.py; `python3 main.py --check`): file
  hashes vs BUILD_MANIFEST.json (in a git checkout only files git shows as edited may differ),
  module origins (no second biq copy on the path), deps (PyQt6 + QtSvg, numpy, libdds), and
  smoke tests (systems from biq's files, two known openings per system, DDS, a legal lead).
  Any problem: an error dialog and exit; biq never plays a broken build.
  BEFORE EVERY COMMIT: `python3 tools/write_build_manifest.py` (test_build_integrity.py fails
  while the manifest is stale; a stale manifest would stop every user's biq).
- signal_read.mis_signals (trust counter, the dialog, the analysis view's honesty log) now judges
  DIRECTION (lowest spot vs a higher one), not the exact card: biq vs biq it flagged biq's own
  6 from 10-8-6-4 (count, 4th seat; the exact rule wants the 8). consistent() (the sampler's
  hard filter) still demands the exact card, so it can drop the true layout when biq keeps a
  spot the play needs: worth a sprint.

## STATUS — analysis view reads the signalling convention (2026-10-21, UNCOMMITTED)
- Toolbar button "Instrumented" is now "Analysis view"; it reads "Default view"
  while the analysis page is up (`_on_toggle_teaching_view`).
- New carding preset `AS_BIQ_PLAYS` ("As biq plays", the default for both pairs;
  Preferences stores it as ""): Preferences polarity, Lavinthal discards, no
  trump echo, no Smith, `signals=False` when "Play defensive signals" is off
  (then nothing is read). The old default was "Standard" with attitude
  discards, which misread biq's Lavinthal pitches.
- `signal_likelihood()` weights each Bayesian world by whether its holding
  would have produced the played signal (signal_read._convention_card under the
  pair's polarity; Lavinthal discards via signals._like_suit). Miss weight 0.2.
- `signalling_conventions_text()` goes into the Claude hint (play phase), hand
  analysis, compare critique (all scopes) and action-grading prompts.
- Tests: test_teaching_view.py adds test_signals_weight_the_posterior and
  test_signalling_conventions_text. Docs: docs/instrumented_view.md.
- Not done: biq.html (web page) still says "Instrumented".

## STATUS — progress curve (2026-10-18)
* Live IMPs vs Q-Plus can't gauge progress: ~100 random boards per system = SE ~0.7 IMP/bd, and card
  play swings up to ±1.9 IMP/bd between runs (261017 Precision -3.37 as played, -1.46 DD-scored; bidding
  unchanged from 261015's -1.52). New tool `tools/biq_progress.py`: per version a teams match vs a
  fixed reference (A: version N/S, B: reference N/S), same 3000 random deals (seed 1018), both tables
  DD-scored, rules only; each version runs from its own `git archive` snapshot
  (tools/runs/code/progress_<sha>), so all modules count; working tree via `git stash create`. SE of
  a step ~0.01-0.04. Results: tools/runs/progress/{TwoOverOne,Precision90M}_1018_3000/summary.md.
* Curve vs 893a540b (10-02): 2/1 +0.43, Precision +0.52 IMP/bd at 3fb1715a. Big steps were 9ff8bf65
  (10-04, Precision +0.27) and 1856c003 (10-10, 2/1 partner tables +0.28). Old loop's last week
  (bf28628b->cec66658): 2/1 +0.015 (SE 0.032), Precision +0.034 (0.021). New plan (cec66658->3fb1715a,
  2 days): 2/1 +0.026 (0.025), Precision +0.136 (0.035).
* Limits: biq vs biq, so Q-Plus-convention fixes (queen-ask answer, partner's 4NT read) move 0 boards;
  rules only, no simulation. Use it next to qplus_rules_ab (Q-Plus judge), not instead.
* Found by it: 8d404b3d's strong-2C ask cost -0.025 (SE 0.010, 9 boards): 4NT over a weak partner's
  2C-2D-2H-(3C-3H)-4H sign-off with 20-23 HCP -> failing 6M. Fix (uncommitted,
  BIQ_STRONG_2C_ASK_WEAK_RAISE): after 2D (and 3C) then 4 of my major, ask only with 25+. +0.022 (SE
  0.009); recorded Q-Plus calls unchanged (a first version that also covered 4m lost 2C-2D-3C-4C,
  where Q-Plus cue-bids). Test prog-1904 (268 checks).
* Strong 2C opener's later rounds (10-18, uncommitted). In biq's own auctions (41 of 3000 curve deals)
  the later-round passes are mostly right (2C-2D-2NT-3NT, Stayman 4M, weak 4M); the bad ones come from
  calls a Q-Plus partner makes. Fixes, each with a switch:
  - BIQ_RKC_VOID_ANSWER: after my 4NT, partner's 5NT or 6 of a suit below trumps -> 6 trump (was pass).
  - BIQ_STRONG_2C_LONG_MINOR: 2C-..-3m (7+ m) - 3NT -> 4m; - 4m - 5m -> 6m.
  - BIQ_STRONG_2C_ASK_CONTESTED: 2C-(their bid)-partner's free 4-level suit, 4+ support -> 4NT (live bd 62).
  - BIQ_STRONG_2C_LATER_FIT: later round, partner's 3M with my 4+ -> cue 4C/4D (minor ace or void), else
    4M (live bd 48; also fires over partner's 3M raise of my major, both recorded cases better).
  - BIQ_RKC_ASKER_PLACES: partner asked 4NT, I answered, partner bid 6/7 -> pass (biq pulled 6S to 7D).
  Q-Plus judge: 2/1 +72 IMP / 6 changed (6 better), Precision +27 / 3; all 9 = Q-Plus; sim keeps the
  2C ones. Curve: 2/1 +0.007 (SE 0.005, 3 boards), Precision 0. Tests 261017-48/62/65, T-2c-8d(-5d),
  T-rkc-void, prog-1711 (275 checks). Committed f0bbb611.

## Sprints (autonomous, 2026-10-18; user: "run scrum autonomously"; nothing committed without asking)
Each sprint: one weakness group, fix the Q-Plus way behind a switch, measure on the Q-Plus judge
(`qplus_rules_ab.py` scan+changed, both systems, sim check) and the progress curve (`biq_progress.py`,
both systems, step vs the last commit); keep only if the judge gains and the curve doesn't drop.
* Sprint 1 — RKC trump choice + king-ask answers. Of the recorded 4NT askers' placing calls, biq's
  trump matched Q-Plus's on 23/43 (2/1) and 16/19 (Precision): cue bids after a minor raise read as
  trump (1D-2C-2D-4D-4H-4NT), splinters missed (1D-1H-3S-4S-4NT), partner's weak two ignored
  (2D-2NT-3H-4C-4H-4NT). `_rkc_trump` (BIQ_RKC_TRUMP), used by every RKC step: partner's weak two /
  preempt; splinter; formal agreement unless an unconfirmed splinter; then both-partners suit /
  most bid / latest, 4-level new suits after a fit are cues, alerted calls never. Now 37/43, 17/19.
  King ask (BIQ_KING_ASK_STEPS): Q-Plus answers 5NT in steps 6C/6D/6H = 0/1/2 side kings (9/9);
  biq named a king. Asker reads the steps; grand on its own source even with 0 kings (Q-Plus 2/2;
  curve 9 made / 3 failed). Judge: 2/1 +227 IMP / 32 changed (17 better, 1 worse), Precision +30 / 9;
  sim keeps all 41. Curve: 2/1 +0.003 (SE 0.008), Precision 0.000 (SE 0.015). Tests T-rkct-cue,
  T-rkct-splinter, T-kask-steps (278 checks).
* Cost map (10-18 evening): every current disagreement scored vs Q-Plus's call (`changed` with OLD =
  the scan with biq := Q-Plus; files tools/runs/agreement/261018_*_rules_rkct3_cost.jsonl): 2/1 -2187 /
  4408, Precision -1104 / 2864. Top: reasonless pass at the end of `_generic_responder_rebid` (2/1 -609
  / 170, Precision -140 / 92), `_opener_suit_rebid` end (-238 / 91), `_opener_rebid` (-185 / 49),
  "LAW compete" (-162 / 39 and -113 / 27), Precision "Sanity: raise partner's suit" (-163 / 51) and
  "Precision 1x: no clear rebid" (-158 / 38).
* Sprint 2 — `_generic_responder_rebid` passes, two clusters: (C1) partner's weak two / preempt / 2NT
  and my forcing call (-243 / 34), (C2) partner's cue after a fit (-131 / 17). Fixes: weak 2D -
  2NT - answer had no continuation (BIQ_WEAK_2D_ASK_CONT: 3NT, 5D with an unbalanced 16+ and a fit,
  pass 3D below 17); `_cue_continuation` takes the suit both partners bid when no formal trump
  (BIQ_CUE_CONT_FIT; minor raises set none). Judge: 2/1 +73 / 10 (8 better), Precision +46 / 3; sim
  keeps all 13. Curve: 2/1 0, Precision +0.004 (SE 0.002). Tests T-2d-ask, T-cue-mfit (280 checks).
  Left: preempt follow-ups (3D-3S-4C, 3S-4C-4D, 3NT-4C-4H: Q-Plus 4NT / 5D), Q-Plus's 4C slam move
  after 2D-2NT.
* Sprint 3 — `_opener_suit_rebid` passes (-238 / 91): opener over partner's 3NT. Q-Plus (all recorded
  opener-vs-3NT calls, both systems) bids 4M with a singleton / void and either its own 6+ major or 3+
  in partner's natural major (raised or not); passes balanced hands, after 2M-3NT direct, and as the
  strong 1C opener. `_opener_3nt_to_major` (BIQ_OPENER_3NT_TO_MAJOR), weak twos only after the 2NT
  ask. Judge: 2/1 +26 / 15 (SE 27), Precision -5 / 6 (SE 20) (neutral; agreement +6). Curve: 2/1 +0.004 (SE
  0.012), Precision +0.010 (0.008). Kept as the Q-Plus way. Tests T-3nt-4m, T-3nt-bal (282 checks).
  Left in this group: cue continuations after a fit where partner's cue is in my own suit (1D-1H-3S-4S),
  partner's 4-level new suit after my 2-suiter (1S-2D-2S-4H).
* Sprint 4 — "LAW compete" (2/1 -162 / 39, Precision -113 / 27; Q-Plus passes 50 of 66). BIQ_LAW_TIGHT:
  no LAW raise of partner's answer to my takeout double (it is not a 5-card overcall: (1H)-X-(P)-1S-
  (1NT) 2S), none over their 1NT. Judge: 2/1 +12 / 7, Precision +32 / 4; sim keeps all 11; curve 2/1 0,
  Precision -0.002 (SE 0.007). Test T-law-tox (283 checks). Unresolved, switch OFF by default:
  BIQ_LAW_NO_SAVE_OVER_3NT (no 4M "compete" over their 3NT). Q-Plus passes 10 of 10 recorded and the
  judge says +55 / 6 (2/1) + 5 (Prec), but the curve (biq opponents bid 3NT more freely) says 2/1 -0.007
  (SE 0.004, 4 boards: 4H -1/-2 beat 3NT made). Decide with a live check or a bigger sample.
* Sprint 5 — "Sanity: raise partner's suit" (Precision -163 / 51, 2/1 -67 / 40): `_safe_forced_bid`
  raised partner's last suit after misjudged forces. BIQ_FORCING_FIXES: (1) only the opener reverses
  (responder's 1C-1D-2D-2H isn't one), except after my strong 1C where partner's suit stays forcing
  (Q-Plus never passed 1C-1D-2x-2M); (2) auction_context A1: a 3-level raise of opener's rebid suit
  (1D-1H-2C-3C) is a limit raise, not GF; (3) stage 2d': after our NT opening a free bid over their
  interference is competitive (1NT-(2H)-2S: pass); (4) stage 2d: partner's suit over Precision 2D is
  to play; (5) partner's forcing 3C with the unbid suits stopped -> 3NT, not 4C (clubs only: over 3D
  3NT lost, the 3D is often artificial). Judge: 2/1 +7 / 16, Precision +72 / 22 (SE 29, agreement
  +10); sim keeps all 38. Curve: 2/1 +0.005 (SE 0.010), Precision +0.037 (SE 0.014), the largest step
  since 10-16. Tests T-1nt-free, T-p2d-2s, T-3c-3nt (286 checks).
* Sprint 6 — Precision 1C opener's "no clear rebid" (-158 / 38): diffuse (half contested, many slam
  sequences). Fixed the one structural gap: 1C-1D-2NT (20-24) now reads as a 2NT opening for both
  hands, like 1C-1D-1NT (BIQ_NT2_AFTER_1C, in `_nt_after_1c_view`): Q-Plus answers in its 2NT system
  (3C Stayman, 3H transfer, opener 3D); biq bid 3NT at once or passed 3C. In the view the opener
  counts at most 21 (it had jumped 3NT to 6NT with 23-24); responder counts +1, passes with 0-2
  instead of Stayman, and after Stayman / a transfer bids game with 4+ (it passed 3C-3D with 4-7).
  The first version without those two guards cost the curve -0.023 (SE 0.011). Judge: Precision +53
  / 10 (7 better, 1 worse), 2/1 0; sim keeps all 10. Curve: Precision +0.002 (SE 0.006). Tests P-8
  (now also accepts 3C, Q-Plus's call), T-1c2n-st (287 checks).
* Run 261018_qplus_prec_21_biqS started 22:01 on 7f586b2e (sprints 1-6). User: "run scrum
  autonomously. Continuously improve biq - don't wait for the run to finish": sprints 7-12 meanwhile,
  deployed into the live run with biq_deploy.py when judge + curve accept.
* Sprint 7 — live board 1: 2NT-3C-3H passed with 5 HCP. `_opening_min_hcp`'s strong-club branch
  counted a Precision 2NT as 5 (a preempt): now two_nt_min_hcp (BIQ_PREC_2NT_FLOOR). Judge 0 (no
  record); the curve can't see it either: biq's Precision never opened 2NT (see sprint 10). T-2n-st.
* Sprint 8 — passes of partner's cue (2/1 `_generic_responder_rebid` cluster -182 / 29):
  `_cue_continuation` takes partner's weak two / preempt as trump via `_rkc_trump` and "I just cued"
  no longer needs a formal agreement (BIQ_CUE_CONT_RKCT): 2S-2NT-3S-4C-4H, 2S-3D-3S-4C-4H-5C. Judge
  2/1 +138 / 14 (12 better, 0 worse), Precision +12 / 3. Curve 0 / 0 (never arises biq vs biq).
  Tests T-cue-wk2, T-cue-rep.
* Sprint 9 — defence to their strong 1C (BIQ_STRONG1C_DEF, `_overcall_strong_1c`): Q-Plus is natural
  and light: 2C = clubs (biq played Michaels, and as advancer bid partner's "majors"); X = 4+4+
  majors, hearts >= spades, 8+; 15+ passes (no 1NT); suit quality gates (5-card overcall with 5+ in
  the suit, 6-card weak jump 6-8 with 4+, 7-card 3-level with 3+); advancer raises to the LoTT level
  (3C with four, 4C with five, 3-10 HCP). `_michaels_by(system)` returns None over a strong-club 1C.
  Judge Precision -21 / 68 (SE 67) but agreement +46: the losses are mostly calls now EQUAL to
  Q-Plus's (rollouts continue with biq). Kept as the Q-Plus way. Tests T-s1c-*.
* Sprint 10 — Q-Plus P90M opens 2NT 20-21 balanced (`B-2NT.strong-balanced.range-20-21`; biq 1C on
  all 15 records): no 5-card major, 5-6 minor ok, no bare Qx (BIQ_PREC_2NT_OPEN). Judge +14 / 12.
  Curve for sprints 7-10: Precision +0.035 (SE 0.026, 59 better / 47 worse); losses = missed slams
  after 2NT-transfer (sprint 12). Tests T-p2n-open, T-p2n-qx.
* Sprint 11 — Q-Plus's 1NT counts a 5-card suit as a point (13 HCP 5-3-3-2 with a 5-card minor 1NT
  9/9; 16 with a 5-card suit 1C 12/15); BIQ_PREC_NT_LEN, exactly-5 only (6-card minors lost). Judge
  +32 / 38 (agreement +13). 5-4-2-2 left alone (Q-Plus 8 1NT / 9 1D). Tests T-p1n-*.
* Sprint 12 — after 2NT-3D-3H / 2NT-3H-3S responder with five and no shortness offers 3NT (Q-Plus
  2/2; biq bid 4M or passed with 4 HCP), floor 24 combined; opener corrects with three
  (`_opener_xfer_3nt`). BIQ_NT2_XFER_CONT. Tests T-2n-x3n, T-2n-x3n-o (302 checks). Left: Q-Plus's
  4C slam try with a 6-card major and 8+ (2NT-3H-3S-4C); biq has no opener answer to it yet.
* Sprint 13 — partner's 3M preempt (live board 9: 3S-4S with KJ85.A4.AJT83.KJ, 13 tricks; Q-Plus
  6S): 17+ with 3 trumps and 2+ keycards asks RKC (the preemptor answers, asker places: 3S-4NT-5D-6S);
  15+ always raises to game, void or not (Q-Plus 2/2; biq passed). BIQ_PREEMPT_RESP. Tests
  T-pre-rkc, T-pre-rkc2, T-pre-void (305 checks).
* Judge sprints 11-13 (Precision, vs sp11): -17 / 8 but all 8 new calls = Q-Plus's (agreement +8);
  2/1 +1 / 3. Curve step for 11-13: Precision +0.017 (SE 0.024), 2/1 +0.001. Deployed sprints 7-13
  into the live run 22:41 (snapshot 261018_224103_aff68db030, verify p1c_ovc, pre_strong, slam_rkc).
* Sprint 14 — opener's 3-level minor rebid over responder's 2-level sign-off ("Rebid 5+m at
  3-level" -113 / 47): the 2-level block in the opener's rebid treated responder's SECOND-round
  2-level call as a 2/1 response. Now: responder repeats their suit, or bids a lower new suit after
  my 1NT, my rebid not a reverse, 16 or less -> pass (BIQ_OPENER_SIGNOFF_PASS). Judge 2/1 +111 / 20
  (15 now = Q-Plus), Precision +12 / 7. Tests T-ob-sign, T-ob-sign2, T-ob-rev.
* Sprint 15 — Bergen (`A-1MA-Bergen-3C.range-8-10`, 2/1 and P90M): biq's responder bid the weak 3M
  but its opener "accepted the limit raise" with 14+; Q-Plus passes 1M-3M with 14-17. Opener passes
  below 18 (BIQ_BERGEN_OPENER). Judge 2/1 +13 / 2, Precision +5 / 3 (all = Q-Plus). Curve step 14-15:
  Precision 0.000, 2/1 -0.004 (SE 0.011): the losses were 8-9 HCP 3M raises passed with game on ->
  Sprint 17: responder ranges set to Q-Plus's (3C 8-10, 3D 11-12, 3M 7 or less; under the same
  switch). Test T-bergen-o, T-bergen-r.
* Sprint 16 — partner's cue after my overcall: their suit is never natural (1D-(1S)-2D-(X)-3S-4D is
  a second cue), and partner's new 4-level suit after raising me is a cue ((1D)-1H-3D-3H-4C):
  back to trumps / cue an ace (BIQ_OVC_CUE2). Tests T-ovc-cue2, T-ovc-cue3 (312 checks).
* Judge 16-17: 2/1 +109 / 22 (cues +63 / 3, Bergen 3C +32 / 14), Precision +93 / 31 (incl. sprint
  18's +44). Curve 16-17 vs 0b224720: Precision -0.002 (SE 0.013), 2/1 +0.017 (SE 0.016).
* Sprint 18 — raising partner's answer to my takeout double: Q-Plus passes with 12-17 and four
  trumps (1D-X-P-2S jump with A652.J53.A65.K96; 1H-X-XX-1S with KQ94.5.AQ5.KQT93); biq raised from
  ~21 "combined". BIQ_TOX_RAISE_TIGHT: shortness counted half, thresholds +2. Judge 2/1 +42 / 27,
  Precision (in the 16-17 scan) +44 / 11. Test T-tox-pass.
* Deployed sprints 14-18 into the live run 23:05 (snapshot 261018_230516_9935df2fbe).
* Sprint 18 follow-up: curve 2/1 -0.010 (SE 0.013), losses incl. 23 HCP stopping in 3S opposite a
  1S answer -> tight thresholds only with 18 HCP or less (curve then 0.000 / +0.003). A "opponents
  silent" condition was tried and dropped (judge: Q-Plus passes in competition too).
* Sprint 19 — `A-2NT-transfer-level-3.spades-for-minors` (both systems): 2NT-3S = both minors
  (5-4+, no 4-card major; Q-Plus 3S with 5.K4.A872.K97643 and 93.-.KJ953.987542, biq 3NT); opener
  names the better minor at four (Q-Plus 4C; biq raised to 4S); responder 10+ asks RKC, else 5m
  (`_nt2_minors_cont`). BIQ_NT2_MINORS. Tests T-2n-3s, T-2n-3s-o.
* Sprint 20 — 1NT jumps the Q-Plus way (BIQ_NT1_JUMPS): `A-1NT-3-minor.is-inviting` (both): 1NT-3m
  = 6+ minor with 4+ in it and 6+ HCP; opener 3NT with the other three suits stopped, else pass
  (exempt from stage 2d's forced raise and `_partner_was_forcing`; biq raised to 4m). Weak long
  minor: Q-Plus PASSES 1NT (5/5; biq's 3m preempt). 1NT-2S (spades-for-minors) answered 3C, then
  responder 3D with diamonds (biq raised partner's relay to 3S). P90M
  `direct-3MA-is-three-suiter`: 1NT-3M = short M, 4+ in the others, 10-15 (Q-Plus 3H with
  8743.J.AK92.KQ95); opener 4 of the other major with four, 3NT with M stopped, else 5m. Tests
  T-1n-*. Judge (first version) 2/1 -6 / 10 (the 2S relay for weak minors; replaced by pass),
  Precision +54 / 17. Curve 18b-20 vs 9f8e3473: Precision +0.003, 2/1 +0.000.
* Sprint 21 — over their strong 1C, 5-4 majors with spades too weak to overcall double (Q-Plus X
  with K9632.QJT5.A42.3, live board 18 -11; 1S with AKQ73.QT65). Test T-s1c-x54 (322 checks).
* Judge 18b-21: Precision +114 / 20 (13 better, 2 worse), 2/1 -34 / 10 (the weak-minor pass, all =
  Q-Plus). Curve vs 9f8e3473: -0.002 / -0.002 (SE 0.012).
* Sprint 22 — responder's "don't abandon it" rebid of a 6-card suit over partner's game in partner's
  own suit / 3NT: Q-Plus passes (1H-2C-2D-3H-4H with KQ.AK73.7.Q98765). BIQ_RESPECT_GAME; not when our
  side already bid at the 4 level (slam exploration: 1NT-3H-4C-4S-5C is a cue, Q-Plus 6H) nor with 7
  cards. Judge 2/1 +17 / 6, Precision +43 / 10.
* Deployed sprints 19-22 into the live run 23:37 (snapshot 261018_233729_5e87f37965; swapped at
  board 41).
* Sprint 23 — "LAW compete": Q-Plus agreed with biq's LAW raise on 7 of 66 recorded calls. It
  competes once, at its first chance; not after I already raised or passed partner's suit; as
  opener (after partner's raise) only with a singleton / void (BIQ_LAW_ONCE). Judge 2/1 +82 / 14,
  Precision +64 / 10 (7 better, 0 worse). Test T-law-once (323 checks). Curve step (with 19-22):
  Precision +0.003 (SE 0.009), 2/1 -0.004 (SE 0.007; the losses are second competes vs biq
  opponents). Kept (judge +146 / 24); watch item.
* Live board 35 (-12): the bidding simulation replaced the strong-1C defence's 1S with a pass (its
  KEEP_ACTION keeps rule calls whose reason says "overcall"). Reasons now say "overcall", and "their
  strong 1c" is in bid_sim's _CONVENTIONAL list (no simulation over the Q-Plus defence).
  Simulation check of sprints 9-23's changed calls (`scan --sim --only`): kept 94 / 100 (2/1),
  182 / 192 (Precision); it replaced 2NT-3S-4C with 3NT -> "2nt-3s", "both minors",
  "three-suiter" also in _CONVENTIONAL. Deployed sprint 23 + these 00:04 (261019_000439_711a0397c0).
* Sprint 24 — forced raises of non-forcing calls (Precision "Sanity: raise partner's suit"):
  (a) Precision 2C (11-15) raised by partner: auction_context reads an alerted 2C as the strong 2C
  (GF on any response) -> stage 2 skips partner's club raise when the system is strong-club
  (Q-Plus passed 2C-(X)-3C); (b) Bergen 1M-3C / 3D (alerted) was taken by auction_context's
  splinter detector (trump + GF) and by the alerted jump-shift branch -> excluded
  (BIQ_BERGEN_OPENER; Q-Plus passes 1S-3C-3S). Tests T-p2c-raise, T-bergen-so (325 checks).
* Fresh cost map 10-19 (`changed` with OLD = sp23 scan with biq := Q-Plus; 7 min on 2 cores):
  Precision -1140 / 2729 (tools/runs/agreement/261019_prec_cost.jsonl); 2/1 in 261019_21_cost.jsonl.
* Sprint 25 — Precision openings by shape (BIQ_PREC_OPEN_SHAPE): 14-15 HCP with HCP + length points
  (one per card past four) >= 18 opens 1C (Q-Plus 7 of 8: AKQT65.-.KQJ642.3, A.AQ3.AJT9754.95);
  6+ clubs longer than any major opens 2C from 10 HCP (Q-Plus 8 of 8 10-counts; biq passed) and
  over a 5-card major (T.QJ875.9.AKQJ93 2C). 9-counts left (Q-Plus mixed). Tests T-p1c-shape,
  T-p2c-10 (327 checks).
* Sprint 26 — RKC after one cue exchange: Q-Plus signs off in game with 12-14 (6 of 7: 1H-2H-3S-4D 4H
  with 5.AJT985.4.AQJ74; biq 4NT). BIQ_RKC_CUE_GATE: 15+ and 27+ with partner's shown minimum (not
  after a strong 2C). Test T-rkc-cue (328 checks).
* Judge 24-26: Precision +114 / 42 (agreement +24; the cue gate +89 / 8), 2/1 +22 / 9. Curve 24-25
  vs 47593eff: Precision +0.012 (SE 0.021), 2/1 -0.005 (SE 0.012).
* Sprint 27 — once Bergen 3C / 3D stopped counting as GF (sprint 24) responder passed opener's game
  try (1S-3C-3D) and cue (1H-3C-4C): `_bergen_cont` answers 3M with a minimum, 4M with the top or
  over a 4-level cue (Q-Plus 3H / 4H). Judge Precision +55 / 4, 2/1 +11 / 1. Test T-bergen-try.
  Deployed sprints 24-27 00:36 (261019_003609_0d34c80295).
* Fresh 2/1 cost map: -2248 / 4351 (261019_21_cost.jsonl). Top: `_generic_responder_rebid` -483 /
  154, `_opener_suit_rebid` -223 / 82, `_opener_rebid` -132 / 43, illegal -> pass -110 / 26,
  "Overcaller rebid - no clear extras" -105 / 75.
* Sprint 28 — sprint 1's king-ask grand ("source of tricks, any king count") cost -59 net on the
  cost map; Q-Plus stayed in six after a 1-2 king answer on 7 of 9 recorded. BIQ_KING_GRAND_STRICT:
  grand only with all three side kings between us. test_bidding_systems' Board-405 grand (spade
  king out) now accepts 6H or 7H.
* Sprint 29 — "support raise after partner's negative X" (-83 / 16): biq answered penalty-ish
  doubles as negative ones (partner's late X after passing, X of their 1NT, 1S-(3D)-X-(5D)).
  BIQ_NEG_X_STRICT: negative = partner's first call after the opening, over a suit overcall at
  the 3 level or lower, no 4-level bid by them since. Tests T-negx-late, T-negx-5d (331 checks).
* Judge 28-29: 2/1 +115 / 20, Precision +54 / 9. Deployed 00:48 (261019_004855_47573abd0d).
* Sprint 30 — (a) no save over their slam after partner's preempt + my game raise (Q-Plus saved
  over a 6-level bid on 7 of 22, over the 5 level on 28 of 35; BIQ_SAVE_NO_SLAM); (b) partner's
  4NT over their 4M after my takeout double asks for a minor (BIQ_X_4NT_MINOR; biq passed 4NT,
  Q-Plus 5C / 5D). Tests T-x-4nt, T-save-slam.
* Sprint 31 — over their weak two with 17-19 balanced and a stopper Q-Plus doubles first (8 of 11;
  biq jumped 3NT), BIQ_WEAK2_X_NT; after the double and a minor answer the balanced hand bids 3NT
  (not a raise to 4m; weak-two openings only). Tests T-w2-x, T-w2-x-3n (335 checks).
* Judge 30-31: 2/1 +224 / 36 (28 better, 7 worse; the weak-two X +106 / 12), Precision 0 / 1.
  Curve 28-29: 0 boards changed either system (these auctions don't arise biq vs biq).
* Deployed 30-31 00:59 (261019_005922_fa99fce25c).
* Sprint 32 — opener's reopening X (2/1 -69 / 64): Q-Plus agreed with 14 of 78; its reopening
  doubles are short (singleton / void) in their suit, biq's allowed a doubleton. BIQ_REOPEN_SHORT.
  Tests T-reopen-2, T-reopen-1.
  Judge 2/1 +109 / 43 (agreement +29), Precision +14 / 9 (+8). Curve 30-32 vs e380b5ef:
  Precision +0.023 (SE 0.015), 2/1 +0.024 (SE 0.013). Deployed ~01:20.
* Sprint 33 — Precision 1C-1M-2M (or switch 1NT = hearts) then partner's call: biq asked RKC with
  17 HCP + 6 controls (live board 69: 6H -1, -11); Q-Plus never asked: 17-18 game / pass 3NT, 22-23
  a slow 3M. BIQ_P1C_RAISE_SLAM: RKC from 21, balanced passes 3NT. Test T-p1c-raise.
  Judge Precision +14 / 2. Deployed 01:17 (261019_011718_574b401a1d).
* Sprint 34 — advancing a takeout double: (a) partner's X of their 1NT is penalty: pass with 5+
  (Q-Plus; biq ran to 2S) BIQ_X1NT_PEN; (b) the longer major first, and 6+ cards with 4-8 HCP jump
  to three (Q-Plus 3H / 4H with seven hearts where biq bid 1S on four) BIQ_TOX_ADV_LONG. Tests
  T-x1nt-pen, T-tox-long.
  Judge Precision +26 / 13, 2/1 +3 / 4. Curve for sprint 33: Precision +0.045 (SE 0.017, the
  largest step of the night; Precision now +0.713 vs 893a540b), 2/1 -0.004 (SE 0.006). Deployed 34.
* Sprint 35 — the strong 1C opener's "no clear rebid" passes (-154 / 33): partner's bid of THEIR
  suit is a cue; `_strong_1c_cue_net` bids 3NT with it stopped (no 6-card suit) or my longest 5+ suit
  (Q-Plus 1C-(1H)-2C-2S-(3H)-4H 4S, 1C-(1S)-3S-4C-4S 5C). BIQ_S1C_CUE_NET. Tests T-s1c-cue*.
  Judge Precision +46 / 3 (all better). Deployed 01:32 (261019_013157_ff1dcc6ab9).
* Sprint 36 — same net: partner's own new suit, or a raise at the 3 level, below game is forcing
  opposite the strong 1C: `_safe_forced_bid` (Q-Plus 1C-1D-2S-3C 3NT, 1C-1D-2S-3D 3S, 1C-1D-1H-3H
  4H; biq passed). Test T-s1c-new.
  Judge Precision +42 / 6 (5 better, 1 worse). Curve 34-35: Precision +0.012 (SE 0.008; now
  +0.725 vs 893a540b), 2/1 0. Deployed 36.
* Sprint 37 — raises of partner's 3-level preempt: Q-Plus raises with three trumps and 8+ HCP or
  four trumps (3S-4S with K75.J7.952.AJ652, 3D-4D with Q8.T863.Q83.A863; biq passed). Major to game,
  minor one level, uncontested. BIQ_PREEMPT_RAISE. Judge Precision +17 / 3, 2/1 +17 / 6. Test
  T-pre-raise (344 checks). Deployed.
* Sprint 38 — Precision 5-3-3-2 with a five-card major in 1NT range: Q-Plus opens 1M with 5+ HCP
  in the major (13 of 22) and 1NT with less (13 of 15). BIQ_PREC_NT_5M_Q. Judge +27 / 22 (10 better,
  7 worse) but the curve: -93 IMP over the 39 boards it changed (biq's own 1M-1S-1NT / 1M-3C
  continuations stop below the games 1NT-Stayman found). Switch OFF by default; not deployed.
* Curve 36-37 (+38 in the snapshot): Precision -0.037 (SE 0.015) = sprint 38's -93 plus sprint 37's
  preempt raises -19 / 5 boards; 2/1 -0.006 (SE 0.004, preempt raises). Sprint 37 kept (judge +34 /
  9 calls, Q-Plus's recorded raises); watch item.
* Sprint 39 — Precision's limited opener ran into the 2/1 "2NT balanced rebid (GF)" over partner's
  repeated suit / jump / contested 2-level call; Q-Plus passed (1D-1H-1S-2H). BIQ_PREC_LIMITED_PASS.
  Test T-p1d-pass.
  Judge Precision +55 / 6 (5 better, 0 worse). Clean curve with 38 off (ecfaeff7): Precision +0.719,
  2/1 +0.495 vs 893a540b; 36-37 step -0.006 / -0.006 (SE 0.004, the preempt raises). Deployed 39.
* Sprint 40 — the 1NT opener after interference (`_nt_opener_x`, BIQ_NT_OPENER_X): 1NT-(2x)-X-(P)
  is takeout, bid a four-card unbid major (Q-Plus 2S with AK32.QT9.T95.AK3); 1NT-P-P-(2x) doubles with
  four of their suit and 5+ HCP in it (Q-Plus X with KQ543 over 2C). biq passed both. Tests
  T-1n-x-tko, T-1n-bal-x.
  Judge 2/1 +14 / 7, Precision -12 / 3; all 10 new calls = Q-Plus's (agreement +10). Deployed.
* Sprint 41 — my weak two, partner's new suit below game is forcing (`_partner_was_forcing`,
  BIQ_WEAK2_NEW_FORCING): live board 89 (-10) the simulation passed the rules' 3H over 2H-2S and
  2S made 10 tricks; forcing auctions are not simulated. Test T-w2-new.
  Judge 0 changed (rules-only scans; the fix is about the simulation). Deployed 02:2x.
* Curve 39-40 vs ecfaeff7: Precision -0.008 (SE 0.009), 2/1 -0.003. The losses are sprint 40 in
  biq-vs-biq play: biq's OWN responder doubles 1NT-(2x) for penalties, so the opener's pull to a
  major (Q-Plus's takeout reading) loses there. Live partner is Q-Plus (takeout), judge +2 with all
  calls = Q-Plus; kept. Open item: make biq's responder X over 1NT-(2x) takeout like Q-Plus's.
* Sprint 42 — that open item: Q-Plus's responder X over 1NT-(2x) is negative (6-12 HCP, a four-card
  or weak five-card unbid major: QJ2.7642.K42.AJ6 X over 2D; biq 3NT / Lebensohl 2NT), and with no
  major it doesn't double for penalties. Wrapper `_respond_to_1nt_competitive` (rules renamed
  `_rules`), BIQ_NT_RESP_NEGX. Cost map: -71 / 73 in this spot. Judge 2/1 +36 / 31 (agreement +14),
  Precision +16 / 10. But the curve: -0.012 / -0.010, then with continuations (`_nt_opener_x` answers
  2NT / 3NT / a minor without a major, `_negx_responder_cont` bids game with 10+) -0.008 / -0.010:
  the X loses the old 3D-cue-to-3NT route when they compete again (1NT-(2D)-X-(2H)-P-(3D) stuck).
  Switch OFF by default (test removed); needs responder follow-ups in competition before it pays.
* Sprint 43 — live nt_save family (9 boards, -4.0): biq passed East's 1NT with a six-card spade suit
  and 8 HCP where Q-Plus overcalled 2S (boards 26 / 33 / 56). Six-card major from 8 HCP over the
  strong NT with an ace or king (J75432.Q7.Q64.QJ: Q-Plus passed). BIQ_OVC1NT_8. Test T-1n-ovc8.
  Judge Precision +10 / 2, 2/1 0 (2/1 uses Multi-Landy 2D there). Deployed ~02:50.
* Cost maps refreshed 02:45 (261019b_*_cost.jsonl, current code): Precision -917 / 2669 (from -1140),
  2/1 -2082 / 4289 (from -2248).
* Sprint 44 — 2/1 `_opener_suit_rebid` passes (-234 / 89): partner's 4-level new suit after a fit is
  a cue but sprint 8's rule needed a both-bid trump and silent opponents. BIQ_CUE_CONT_ANY: at the 4
  level, trump = `_rkc_trump` (any suit we bid, not theirs), or my major after partner's alerted
  Bergen 3C / 3D; contested allowed (1S-3C-(3D)-4D-4H 4S, 1S-2D-2S-4C-4D-4H 4S). Test T-cue-any.
  First version took partner's natural game (1D-4S, (1S)-2D-4H) and 5NT as cues (judge 2/1 -15 / 25);
  now: not 5NT, not partner's 4M game unless partner supported us / Bergen / a cue round happened.
  Judge 2/1 +19 / 13, Precision +20 / 10. Curve (41-44, 42 off) -0.001 / -0.001. Deployed 03:1x.
* Sprint 45 — "don't abandon it" rebids: pass partner's return to another suit of mine (preference)
  and stop rebidding with 4 HCP or less (Q-Plus 1C-1D-1S-1NT-2S pass with 92.93.Q97654.954).
  BIQ_ABANDON_GATES. Judge Precision +34 / 4, 2/1 +16 / 8. Deployed 03:2x.
* Sprint 46 — "accept limit raise" after a competitive 3M (cheapest level over their bid) or a passed
  partner's 1M-3M: Q-Plus passes below 17 (1S-(2C)-2S-(3D)-P-3S with AKJ63.A94.74.Q82, P-1S-3S with
  AK54.T875.AQ6.J3). BIQ_COMPETE_RAISE_PASS. Judge 2/1 -2 / 16, Precision -22 / 3: switch OFF, test
  removed, not deployed.
* Sprint 47 — compete rebid of a six-card major to game after partner's raise / cue raise (Q-Plus 4H
  with A53.KQ9652.AJ98.-): judge 2/1 -59 / 37 (agreement -14), Precision -16 / 23; switch
  BIQ_COMPETE_GAME OFF, not deployed. (The examples are real but the trigger is too broad.)
* Sim check of sprints 24-45's changed calls: kept 138 / 146 (2/1), 104 / 112 (Precision). The
  simulation passed the 1NT opener's 2S answer to partner's takeout X (x2), the strong-1C opener's
  5C over partner's cue, and the 1NT opener's balancing X: their reasons ("for partner's takeout x",
  "cue of theirs", "behind them") added to bid_sim `_CONVENTIONAL`. Deployed ~04:00.
* Night summary (curve, 3000 deals vs 893a540b, paired steps): live code 9c24e52f (04:02) vs the
  run's start 7f586b2e: Precision +0.138 IMP/board (SE 0.052; 216 boards better / 181 worse), 2/1
  +0.019 (SE 0.029). vs f0bbb611 (before sprints 1-6): Precision +0.190 (SE 0.054), 2/1 +0.032.
  Levels: Precision +0.711, 2/1 +0.491. Cost maps: Precision -1140 -> -917, 2/1 -2248 -> -2082.
  Switches left OFF (measured, rejected): BIQ_PREC_NT_5M_Q (38), BIQ_NT_RESP_NEGX (42),
  BIQ_COMPETE_RAISE_PASS (46), BIQ_COMPETE_GAME (47), BIQ_LAW_NO_SAVE_OVER_3NT (4).
  Live: handover to 2/1 at board 150 not possible (spares North 2, West 1: no East) -> Precision
  continues; the 2/1 segment needs an East spare window joined.
* Live: the 2/1 spare windows joined as North, North, West (no East): the TM logs "handover not
  possible" at board 150 and keeps playing Precision until an East spare joins.
* Run end: West's Q-Plus window stopped answering at 05:21 (board 186, mid-play); the TM's
  handover failed (no East spare) and it stopped at 05:23 after 185 boards (biq -562 IMP raw).
  Committed + pushed as 09dd6eac (10-19 morning); Q-Plus windows and planner stopped on request.
* Offline sprints (10-19 day, user: "keep improving biq offline with sprints"). Fresh cost maps
  (261019c_*_cost.jsonl, code 09dd6eac): Precision -908 / 2663, 2/1 -2126 / 4284. Probe helper:
  scratchpad reprobe.py SYSTEM ROWS.jsonl (re-decides scan rows with the working tree).
* Sprint 48 — opener's answer to partner's 2NT after a two-level rebid (1C-1S-2D-2NT with
  J.A3.AKQ6.KQ7432, 1C-1D-2C-2NT with 92.Q82.K6.AQJ763): biq passed (no rule); Q-Plus never
  passes unless partner answered 1NT. `_rebid_2nt_answer` (pass hook, BIQ_REBID_2NT_ANS): 13+
  balanced (or no shortness and one long suit) 3NT, three cards in partner's major 3M, a six-card
  suit with 12 or less three of it, 13+ with a six-card suit 3NT, else 13+ back to my first suit.
  Judge 2/1 +56 / 11 (9 better), Precision +3 / 3. Curve (with 50-51): 2/1 boards +10 x4.
  The 1x-1y-1NT-2NT accept at 13 (BIQ_NT_REBID_ACCEPT; Q-Plus 3NT 3 of 4) lost on the curve
  (2/1 -17 / 4 boards, Precision at 12: -31 / 11): switch OFF (biq's own 2NT invite is lighter).
* Sprint 49 — strong 1C opener not passing below game after partner's positive when they bid
  in (BIQ_S1C_FORCE_COMP): judge Precision -14 / 5 (3NT without a stopper, 4S where Q-Plus
  doubled): switch OFF.
* Sprint 50 — "don't abandon it" rebid of a long minor (Precision -79 / 36): after an uncontested
  two-level response no jump (1H-2D-3C 3D, not 4D), 3NT from 23 combined with the unbid suits
  stopped (1D-2C-2D 3NT with K4.A9.QT2.KT7543), and three-card preference to opener's major first
  (1S-2C-3H 3S with A75.52.Q4.AJT964). BIQ_ABANDON_NOJUMP. Judge 2/1 +8 / 3, Precision +33 / 5.
* Sprint 51 — overcaller after partner's competitive X (their 2/3-level suit, next hand pass or
  XX; biq always passed, 2/1 -93 / 25): four-card unbid suit at the cheapest level up to 3, else
  rebid a five-card overcall ((1D)-1S-(2D)-X-(P) 2S, (1NT)-P-P-2H-(3C)-X-(XX) 3D). BIQ_OVC_X_ANSWER.
  Judge 2/1 +37 / 4 (all better), Precision -17 / 5 with all 5 now equal to Q-Plus (agreement +9).
* Curve 48+50+51 (7bfcca62, NT accept still on) vs 09dd6eac: 2/1 +0.015 (SE 0.009, +9 / -6),
  Precision -0.006 (SE 0.008, +4 / -13; 11 of the 13 losses were the NT accept, now off).
* Sprints 52-55 — Q-Plus judges raises by losing tricks, not points (all recorded 1M-2M and
  raise-to-3 spots tabulated by LTC). Judged together against a base with all four off, then
  attributed by reason: 2/1 +263 / 72 (50 better, 12 worse, agreement +48), Precision +65 / 28.
  - 52 BIQ_RAISE_TRY_LTC: opener after the direct 1M-2M (their double allowed, not their suit):
    try with 5 losers, or 6 with a small singleton / void and six trumps or 14+; game with 5 and
    16+; else pass (exempt from the learned game net). 1S-2S 3S with KQJ965.8.KJ73.J2, pass with
    AK432.QT.AK9.T85. First version also fired on preferences (1S-1NT-2H-2S): restricted. +32 / 13,
    Precision +1 / 5.
  - 53 BIQ_LIMIT_ACCEPT_LTC: opener over partner's raise to 3M accepts with 5 losers, or 6 when
    they stayed out; overcaller over partner's raise to 3 with 5 losers. P-1S-3S pass with
    AK54.T875.AQ6.J3. +104 / 26, Precision +17 / 13.
  - 54 BIQ_ADV_SAVE_5M: partner's 4M overcall, their raise to 4: 5M with 3+ trumps and a
    singleton / void in theirs (or 4+ and a doubleton), 6M with a void, 4+ trumps and 8+; pass
    with 3 trumps, a doubleton and 9 or less. +56 / 21, agreement +20.
  - 55 BIQ_LAW_NO_4: no LAW compete to the four level (Q-Plus passed 11 of 12) or on 2 HCP or
    less (RUN2-049's 3 HCP raise stays). +71 / 12, Precision +47 / 10.
* Sprint 56 — advancer over a one-level overcall. (a) BIQ_UCB_LEVEL_FIX: the unassuming cue
  came out at level 1 (or 0 after their X), illegal, and the sanity check passed it (2/1 -22 /
  16; Q-Plus 2D over (1D)-1S-(P) with KQ5.AJT63.T7.962): cheapest legal level, none above 3
  (the uncapped fix cued 5C / 5H, -24 / 2). (b) BIQ_ADV_JUMP_RAISE: four trumps and 6-9 HCP jump
  to 3M, five and a singleton 4M (K976.J6.J97.KJ84 (1H)-1S-(P) 3S); only after RHO's pass (after
  their X it lost 2/1 -29 / 13, where Q-Plus often uses a 3-minor jump cue instead).
* Sprint 57 — responder after opener's 3M (BIQ_JUMPRAISE_GATE): game needs 8 HCP (7 with a
  singleton) opposite the jump raise, and opener's 3M after his own 2M and my try is a decline:
  pass (1D-1S-3S pass with 9872.QJ7.T63.K97; 1D-1S-2S-2NT-3S pass with A985.985.A5.QT95; biq
  bid 4M from 6 HCP). Judge 2/1 +17 / 5, Precision +21 / 5, all now equal to Q-Plus.
* Sprint 58 — Precision 1C-1D-2C / 2D (BIQ_P1C1D_CONT, `_prec_1c1d_resp2`): Q-Plus answers
  opener's natural minor: over 2D four spades 2S / four hearts 2H / balanced 2NT, over 2C a
  five-card major else 2D waiting; pass with 3 HCP or less, support and 5 or less, or a six-card
  minor with a singleton in opener's suit. biq passed with 4-5 or jumped to 3NT with 6-8 (the
  learned net). Re-probe: 20 of 23 recorded calls now equal Q-Plus's. Extended to 1C-1D-1M (also
  forcing for Q-Plus): four trumps 2M (3M with 7), four spades over 1H 1S, a six-card suit from 5
  at two, else 1NT with 6 or less (biq passed, or the learned net bid 4H with 98.K8643.96.T843):
  13 of 15 recorded calls now equal.
  The 1NT-with-nothing part (J8.T8653.852.964, 1C-1D-1S-1NT) was dropped: judge -45 / 4, the
  rollouts show biq's own strong-1C opener driving to a failing game over it.
* Sprint 59 — 1NT opener and transfers (BIQ_TRANSFER_ONCE). The accept rule had no
  first-answer guard: after 1NT-2H-2S-P-P-X biq "accepted" again, legalized to 3S (Q-Plus
  passes), and it read 1NT-2C-2D-2H as a transfer (2S). Now: accept only as my first answer to
  partner's first call; over their bid after the transfer bid the major only with four; on my
  second turn compete only with four trumps; and the sanity rule "4-card support for partner's
  free major" skips notrump openings (it read the transfer as natural hearts and bid 4H).
  Cost map: about -70 / 15 (both systems). Re-probe: 15 rows now equal Q-Plus, 3 differ.
* Curve 52-58 (518cca64) vs 7bfcca62, 2/1: -0.019 (SE 0.023, 111 boards, +59 / -52). By first
  differing call: single-raise tries (52) +33, cue-level fix +11, NT accept off +17; losers were
  4M -> pass in competition (53/55) ~-43, opener passing 1M-1NT-2M-3M (53) ~-43, responder passing
  the jump raise with 6-7 (57) ~-26. Switch-off variants vs 518cca64: LIMIT_ACCEPT_LTC off +0.002
  (SE 0.015, neutral; kept on the judge's +121), JUMPRAISE_GATE off +0.011 (SE 0.006, 4 / 0: 4M
  made opposite biq's own 1D-1S-3S on all four), LAW_NO_4 off +0.013 (SE 0.009, 12 / 8).
  Rule used: a decision that depends on PARTNER's range follows the curve (live partner is biq);
  one that depends on the OPPONENTS' bidding follows the judge (live opponents are Q-Plus).
  So 57 keeps only the "declined my try" pass (the jump-raise threshold is back to biq's 6) and
  55 stays (Q-Plus passed 11 of 12 recorded spots; the curve's opponents are old biq).
  53 then skips 1M-1NT-2M-3M (partner's invite after the 1NT answer): the gate lost ~-40 / 6
  curve boards there (biq's own invite), +0.013 (SE 0.008, +7 / -3) after the exemption.
* Curve after sprints 48-59 (2/1 67822734, Precision 4a46217c) vs the committed 09dd6eac: 2/1
  +0.020 (SE 0.023, +61 / -43), Precision +0.038 (SE 0.024, +66 / -45). Precision by pattern vs
  7bfcca62: 1M-2M tries +49, 1NT transfers +31, raises to 3M +3, 1C-1D continuations -4 (neutral).
* Cost maps refreshed (261019d_*_cost.jsonl, code after sprint 59): Precision -908 -> -822 /
  2598 (agreement 8261 -> 8326), 2/1 -2126 -> -1756 / 4205 (13136 -> 13215).
* Sprint 60 — weak-two responses (BIQ_W2_RESP; 2/1 -95 / 30): Q-Plus asks 2NT with balanced
  13-14 (T97.A542.AK2.K97 over 2H; biq passed) and needs 13+ for a new suit (passes 2D with
  KQJT9.AQ87.3.T65; biq 2S). Re-probe: 13 of 14 changed rows now equal Q-Plus.
* Sprint 61 — opener after responder's 2-level call (BIQ_OPENER_21_REBID): the uncontested 2/1
  over 1M with a five-card major: four-card support for the minor raises to 3m, three hearts
  over 2H raise to 3H, 5-3-3-2 bids 2NT (Q-Plus 2NT on 7 of 9 recorded 5332 hands; biq rebid
  2M); and 1M-1NT-2x-2y is a sign-off (pass with 16 or less and five trumps). The "Rebid 5+
  (2/1 GF)" reason fired on non-2/1 auctions (2/1 -57 / 29). Re-probe: 15 rows now equal.
* Judge 60-61 vs a base with both off: 2/1 +93 / 30 (16 better, 4 worse; 60 +59 / 12, 61
  +34 / 18), Precision +10 / 12. Curve (d8ff879f vs 67822734): 2/1 -0.006 (SE 0.013), Precision
  +0.003. The 2/1 loss was the new 2NT ask: after 2S-2NT-3S (minimum, no feature) the sign-off
  3S was illegal and the continuation fell through to 4S (-45 / 10 boards). Fixed: pass opener's
  3M (exempt from the learned net). Other 2/1 boards: new-suit threshold +18, opener after the
  2/1 +10. The fix recovered only +0.003 (577d1319): the balanced ask itself loses opposite
  biq's weak two (2S-2NT-3S one down where 2S made; ~-30 / 10 boards) though the judge has it
  +16 / 7. Partner-dependent, so the curve decides: BIQ_W2_ASK_BAL OFF (the new-suit threshold
  and the 3M pass stay).
* Offline batch summary (sprints 48-61, uncommitted on top of 09dd6eac): curve vs 09dd6eac
  2/1 +0.029 (02742e67, SE 0.025, +72 / -49), Precision +0.041 (577d1319, SE 0.025, +77 / -54).
  Cost maps (scan of 261019d, after 59): Precision -908 -> -822, 2/1 -2126 -> -1756.
  Switches OFF (measured, rejected): BIQ_NT_REBID_ACCEPT (48), BIQ_S1C_FORCE_COMP (49),
  BIQ_W2_ASK_BAL (60). Narrowed on the curve: 52 (direct raise only), 53 (not after 1NT),
  56 (cue at most 3, jump raise only after RHO's pass), 57 (decline part only), 58 (no 1NT).
* Judge 56 (revised) + 58 vs a base with both off: 2/1 +71 / 20 (11 better, 3 worse), Precision
  -4 / 33 (agreement +21): 58 +13 / 17 (agreement +16); the cue-level fix 2/1 +67, Precision -36
  with agreement +5 (rollouts continue with biq's overcaller); jump raise +4 / 5, Precision +19 / 3.
* Live run 261019_qplus_prec_21_biqS (user: "set up a 10 hr run"), started 23:19 from snapshot
  261019_231908_44a2ac0705 (sprints 48-61, uncommitted): Precision 150 boards then 2/1; stop_after.sh
  ends it 10 h after the first finished board. New planner families for the sprint changes: p1c1d,
  raise_ltc, rev_2nt, ovc_jr, xfer_comp, wk2_mid, two_one (hit rates in its RESUME.txt).
* Run end: stop_after.sh stopped it at 09:26 (10-20) after 246 boards, no window froze; handover to
  2/1 at board 151 (05:35). Random boards: Precision -1.64 IMP/bd (SE 0.88, 61), 2/1 -1.97 (0.89, 38).
  Targeted (IMP/bd): ovc_jr Precision -5.68 (25), wk2_mid 2/1 -5.57 (14), xfer_comp Precision -3.80 (10).
* Judge now includes the run (both systems). Gotcha: its Precision rows are tagged "Precision90M" and
  bid_decisions filters on the --system name, so `scan Precision` silently dropped them: use
  `scan Precision90M` (scratchpad judge.sh / costmap2.sh / mkcode.sh: frozen git-archive copies of the
  tree with tools/runs linked, so edits during a scan don't leak). Base 261020a (code = live run's):
  Precision -1120 / 3284 of 13268 (agreement 75.2%), 2/1 -1748 / 4559 of 18917 (75.9%).
* Sprint 62 - partner's 1M overcall, RHO's new suit. Live bds 23 / 38 / 44: biq raised 2S or the sim
  passed, then on later turns retried the stale 2S, illegal -> sanity pass (19 "Sanity: illegal"
  calls in the run). (a) BIQ_ADV_JR_OVER_BID (jump to 3M / 4M with a void over their 2-level suit,
  as Q-Plus): judge 2/1 -47 / 8 (0 better; after the jump the rollouts' opponents reach a making 4M),
  Precision +4 / 1 -> OFF. (b) BIQ_ADV_RAISE_STALE: an illegal simple raise competes at the cheapest
  level <= 3 with four trumps, else an explicit pass. Kept.
* Sprint 63 - BIQ_XFER_PASSED: 1NT opener who passed over their bid after the transfer no longer
  "accepts" later (live bd 133: 1NT-2D-(2S)-P-(3C)-P-P-3H with T9, -8); four trumps compete <= 3.
  Note state.my_bids omits passes (count my calls from state.bids). Judge 62+63: 0 / 0 and 2/1 0 / 1;
  curve 947d1179: 2/1 +0.004 (SE 0.003, 2 boards), Precision +0.008 (0.006, 11). Tests T-ovc-stale,
  T-xf-passed (T-jr-overbid / T-jr-void removed with the switch).
* Sprint 64 - BIQ_FALSE_PREF: 1x-1y-2z (z lower, uncontested), 6-10 -> 2x with 2+ x, z <= 4, and
  x >= z-1 or 7+ HCP (Q-Plus: KJ63.843.Q98.Q75 / K6.Q9532.Q7.JT65 2D over 1D-1S/1H-2C, K8742.Q3.K9.T753
  2H over 1H-1S-2D; pass with 964.A652.75.Q985). Not after a 1NT response (Q-Plus mixed there). Judge
  Precision +18 / 3 (3 better), 2/1 +28 / 10 (5 / 4); curve 84168d15: 2/1 +0.008 (SE 0.009, 27
  boards), Precision -0.002 (0.011, 34). Kept.
* Sprint 65 - BIQ_OVC_RAISE_GATE, "Overcaller rebid — raising partner's suit with support" (-83 / 17 in
  each system): no raise once it is illegal (it was legalized a level up after their 3NT), pass over
  partner's non-jump answer to my later double with <= 16 (Q-Plus 3 / 3: KQ8.A94.KJ843.J7 over
  (1C)-1D-(3C)-P-(P)-X-(P)-3S), no raise of partner's non-jump suit after my 1NT overcall or unusual
  2NT over a one-level opening (2.J87.AQJ7.AJ973 passes 1NT-2NT-P-3D). Helper
  _cheapest_level_over_auction_before (was partner's call a jump). Judge (alone, net of 64): Precision
  ~+34 / 8, 2/1 ~+15 / 9; curve fcf9267b: 2/1 -0.001 (SE 0.009, 11 boards), Precision -0.003 (0.003,
  7). Kept. Tests T-ovr-xans, T-ovr-unus, T-ovr-legal.
* Sprint 66 - BIQ_REVERSE_STRICT: `_partner_was_forcing` read opener's 2S over my negative X
  (1D-(1H)-X-(2H)-2S) and partner's third-call suits as forcing reverses, and the sanity net raised
  ("Sanity: raise partner's suit", 6-7 HCP; Q-Plus passes). A reverse is now partner's second call
  only, not over my negative X. Judge (alone): Precision ~+37 / 7, 2/1 ~+21 / 6; curve 34b8bf66: 2/1
  -0.003 (SE 0.009, 15 boards), Precision -0.002 (0.011, 22). Kept; deployed live ~22:55 (the run
  started without it). Test T-negx-norev.
* Sprint 67 - BIQ_RKC_QUEEN_ASK (asker with 4/5 keys and no trump queen bids the next step over 5C/5D
  as Q-Plus does, 7 more recorded calls matched; follow-up reads 5T = stop, 5S/5NT = 6T; not over a
  3-level preempt). Judge Precision +34 / 8, 2/1 -9 / 6; curve c7af59e9: Precision -0.007 (SE 0.005,
  2 boards, both 6S making without the queen stopped in 5S), 2/1 0. Partner-dependent -> OFF.
* Sprint 68 - BIQ_COMPETE_WEAK6: "Compete: rebid own 6+ (don't sell out below game)" at the 3 level
  with six cards, <= 8 HCP and partner never bid the suit -> pass (Q-Plus 11 of 13 records pass,
  e.g. 8.KJ9754.J64.JT5 over 1D-(1NT)-2H-(2S)-P-(P); also after partner's X / XX). Judge Precision
  +19 / 3, 2/1 +39 / 11 (8 better, 0 worse); curve 04e10a90: 2/1 -0.005 (SE 0.003, 5 boards, 1 / 4),
  Precision 0 (7 boards). Opponent-dependent (their partscore) -> judge rules; kept. Test T-cmp-weak6.
* Sprint 69 - BIQ_OPENER_4M (pass-hook `_opener_4m_raised`): I opened 1m (not a strong 1C), partner
  raised to 4m, uncontested, I never bid NT: cue the cheapest control above 4m, else 5m (Q-Plus never
  passes: 1D-2C-2D-4D 4H with AKQ5.KJ6.T8654.8). Judge (net of 68): Precision +6 / 1, 2/1 +5 / 2
  after excluding auctions where I bid NT (1D-..-3NT-4D-4H was passed in a 4-1 fit, -12). Curve
  f5dd6491: 0 boards either system. Kept. Test T-op-4m.
* Sprint 70 - BIQ_P1D_LIGHT: Precision 1D-(P), 3-5 HCP with a five-card major -> 1M when diamonds <= 2
  (4+ HCP) or <= 1 (3 HCP); Q-Plus 8 / 8 on its records, passes with three diamonds or 2 HCP (its 1D
  can be two cards). Judge (alone) Precision ~+61 / 8; curve 7528cd85: Precision +0.006 (SE 0.005,
  7 boards, 5 / 2), 2/1 0. Kept. Test T-p1d-light.
* Sprint 71 - BIQ_LEGALIZE_2ND: `_legalize` no longer bumps a "Second suit" rebid the opponents bid
  past (1D-(P)-1S-(2H) 3C with J8.8652.AT6.AKT6): pass, or the compete-rebid of a six-card major.
  28 of 32 such records now = Q-Plus. Judge (alone) Precision ~+46 / 14, 2/1 ~+37 / 18; curve
  d7e1be06: 2/1 +0.014 (SE 0.007, 9 boards, 7 / 2), Precision +0.006 (0.006, 8). Kept. Test
  T-2nd-legal. Sprints 70-71 deployed live 23:44 from the frozen copy (biq_deploy --src
  scratchpad/code_s71: git-archive copies lack only __pycache__).
* Sprint 72 - BIQ_WEAK2_X_SHAPE: no direct takeout X of a weak 2M with a doubleton in it and 11-14
  unless four in the other major and 13+ (Q-Plus passes 7 / 7 with three in the other major:
  95.J54.AKQ76.QJ4 over 2S; 3 / 3 with 11-12). Judge (alone) Precision ~+17, 2/1 ~+26; curve
  311278e0: +0.006 both (SE 0.006, 4 boards each). Kept. Test T-w2x-shape.
* Sprint 73 - BIQ_X_SLAM_VOID: my takeout X of their 3-level+ preempt, partner's 5-level suit, a void
  in their suit, 4+ of partner's suit, 13+ -> 6 of partner's suit (Q-Plus: -.AKJT643.AT.A942
  (3S)-X-(4S)-5C 6C, 4 of 5 records). Judge (alone) 2/1 ~+28 / 5; curve cdf30773: 0 boards. Kept.
  Test T-x-slamvoid. Sprints 72-73 deployed live 23:55.
* Cost maps 261020c (code after sprint 73): Precision -890 / 13268 decisions (was -1103 at 261020b),
  2/1 -1473 (was -1677).
* Sprint 74 - BIQ_FLAT_NO_STAYMAN: 1NT-(P), 4-3-3-3 with the four-card major, below quant values: no
  Stayman; pass at invite_lo, 2NT at invite_hi, else 3NT (Q-Plus never used Stayman there below 16:
  J853.A42.T87.K94 passes, Q72.AK82.JT5.J62 3NT). Judge +22 / 5 (Precision), +22 / 7 (2/1), 0 worse;
  curve 0b827e32: 2/1 +0.007 (SE 0.004, 3 boards, 3 / 0), Precision +0.003 (0.007, 9). Kept. Test
  T-flat-nostay.
* Sprint 75 - BIQ_NEGX_SUPPORT_FIRST (1M-(2-level suit), 3+ support and 6-12: raise / limit raise
  before a negative X of the other major; Q-Plus raises or cues 28 of 32 records, 11 more exact
  matches). Judge 2/1 ~+53, Precision ~-28; curve 63ee773f: 2/1 -0.009 (SE 0.009, 8 / 9), Precision
  -0.011 (0.009, 4 / 9). Partner-dependent -> OFF.
* Sprint 76 - BIQ_NEW3_NT (pass-hook `_partner_new3_nt`): partner opened, uncontested, partner's new
  suit at the 3 level that biq's forcing test misses, 10+ HCP -> 3NT (Q-Plus never passes there with
  10+: 1D-2NT-3C 3NT with K84.A75.T76.AJT6; passes only with 2-3 HCP). Skips when
  `_partner_was_forcing` (the forced-bid net handles splinters better). Judge (alone) Precision ~+18
  / 3, 2/1 ~+22 / 5; curve ae73b1d8: 1 board each way. Kept. Test T-new3-nt.
* Sprint 77 - BIQ_STAYMAN_3NT_S (pass-hook): 1NT-2C-2H-3NT with four spades -> 4S (Q-Plus with
  AJ63.AQJ8.J7.Q75). Judge Precision +22 / 2; curve d5d2392d: 3 boards, all better. Kept. Test
  T-stay-3nt-s.
* Sprint 78 - BIQ_WEAK2_COMPETE4 (hook when the opponents spoke last): partner's weak 2M, RHO jumps
  to four of another suit, 3+ trumps and (10+ HCP or <= 1 in their suit) -> 4M (Q-Plus 2S-(4H)-4S
  with Q93.Q.AJ754.JT42; biq's point count passed). Judge 2/1 +10 / 5 (agreement +4); curve 0. Kept.
  Test T-w2-comp4. (The partner-spoke-last hook list does not run when an opponent bid last.)
* Sprint 79 - BIQ_LEGALIZE_MORE: `_legalize` also refuses to bump natural overcalls, UCB declines,
  Landy answers, weak jump overcalls and Truscott sign-offs (Q-Plus passes every recorded case; 30 of
  36 such records now match, 3 before). Judge (alone) Precision ~+44 / 15, 2/1 ~+25 / 21; curve
  2d28d27f: Precision +0.039 (SE 0.015, 27 boards, 18 / 9), 2/1 +0.010 (0.013, 26). Kept, live
  00:42. Test T-leg-ovc.
* Sprint 80 - BIQ_X_LONG_MAJOR (sanity step 0): a "Takeout double" holding an unbid major of 6+ cards
  (<= 16 HCP, up to the 3 level) or 5 cards (<= 13 HCP, 2 level) becomes the cheapest bid in it
  (Q-Plus never doubles with six: K87654.4.AQ3.A43 3S over (1H)-P-(3H); 17 of 21 changed calls =
  Q-Plus). Judge (alone) Precision ~+21, 2/1 ~+15; curve 32dae455: 2/1 +0.008 (SE 0.006, 4 / 2),
  Precision 0 (1 / 3). Kept, live 00:48. Test T-x-longM.
* Cost maps 261021a (code after sprint 80): Precision -900 / 13268 (agreement 10053), 2/1 -1437
  (agreement 14433).
* Sprint 81 - BIQ_LEGALIZE_3RD: no bump of a third bid of my suit ("Rebid N-card suit", six cards or
  fewer) when the opponents doubled within the last three calls or bid at the 3 level (1H-P-1NT-P-2H-
  P-P-X: pass, not 3H; Q-Plus 10 of 10; it does compete 3C over their 2-level suit). Judge Precision
  +18 / 4, 2/1 +22 / 5; curve 8c3030ed: +0.007 both (3 / 0 each). Kept, live 01:06. Test T-leg-3rd.
* Sprint 82 - BIQ_OVC_RAISE4: the advancer's "Simple raise of overcall" to the 4 level or higher with
  three trumps -> pass (Q-Plus passes 27 of 36 records: JT4.KQT32.J532.J over (1D)-3S). Judge
  Precision +25 / 10 (10 better, 1 worse), 2/1 -17 / 26 (14 / 12; the rollouts liked biq's old saves
  where Q-Plus also passed); curve f911352f: +0.008 both (2/1 5 / 1, Precision 8 / 3). Net positive on
  both measures: kept, live 01:12. Test T-ovr4-pass.
* Checkpoint 01:25 (10-21), code f911352f (sprints 62-82, uncommitted): curve vs 02742e67 / 577d1319
  (end of 10-20 day): 2/1 +0.064 IMP/bd (SE 0.025, 71 / 49 boards), Precision +0.075 (0.027, 90 /
  64); vs the commit 09dd6eac: 2/1 +0.093 (0.035), Precision +0.116 (0.035). Agreement (261021b):
  Precision 9984 -> 10064 / 13268, 2/1 14358 -> 14451 / 18917 since 261020a. Live run: 47 boards, no
  errors, one legalized call (fine). preempt_save dropped from the plan (noise).
* Sim check of sprints 62-82's changed calls (scan --sim --only): kept 126 / 138 (2/1), 96 / 100
  (Precision). The simulation reverted sprint 64's preference (6, all = Q-Plus), sprint 80's major
  instead of X (3, all = Q-Plus) and one sprint 82 pass: "preference to partner's first suit",
  "instead of a takeout double", "no raise to the" added to bid_sim _CONVENTIONAL. Live 01:50.
* Sprint 83 - BIQ_PREEMPT_ONCE: "rebid N-card suit, not X" with <= 11 HCP no longer competes again at
  the 3-4 level (Q-Plus 20 / 20 pass: 952.AJ976532.7.8 3H-(X)-P-(4D), QJT9874.6.AJ.854 3S-(X)-P-(4C));
  16 changed calls, all = Q-Plus. Judge Precision +4 / 6, 2/1 +14 / 10; curve ba158feb: 7 boards,
  6 better. Kept, live 01:58. Test T-preempt-once.
* Overbid scan (biq bids, Q-Plus passes, by rule) also found: "Game raise after partner's support"
  (1m-1M-2M-4M with 10-16: Q-Plus tries 2NT / a new suit, passes with 10 in Precision) and "Better
  minor" 10-HCP openings (Q-Plus preempts 3C with seven, passes a poor six). Left: partner-dependent,
  too few clean records.
* Sprint 84 - BIQ_PULL_LOWX: no "pull partner's doubled suit" after RHO's immediate double of
  partner's weak two or 1-2 level overcall (takeout / negative) with < 10 HCP, unless a 7-card suit
  with 6+ in it (Q-Plus 10 of 11 pass: QT8732.J4.KJT.93 over P-2H-(X); pulls KQJT983). 9 changed
  calls, all = Q-Plus. Judge Precision +18 / 10, 2/1 +33 / 15; curve f61053da: 2/1 +0.017 (SE 0.009,
  6 / 2), Precision +0.009 (0.007, 4 / 4). Kept, live 02:05. Test T-pull-lowx.
* Sprint 85 - BIQ_NT_OVC_16 (direct 1NT overcall from 16, not 15: Q-Plus passed 26 of 43 balanced
  15s; 29 more exact matches). Judge Precision ~+59, 2/1 ~+12; curve bafc7053: 2/1 -0.004 (SE 0.007,
  8 / 11), Precision -0.008 (0.007, 7 / 13). Partner answers by the 15-18 range -> curve rules: OFF.
* Sprint 86 - BIQ_X_TWICE: no second takeout double with <= 13 HCP after my first one (Q-Plus 8 of 9
  pass: AT75.JT94.K9.AJ4 over (1D)-X-(2NT)-P-(3C)). Judge (alone) Precision ~+11, 2/1 ~+3; curve
  ef4bffec: flat (2/1 3 / 3, Precision 1 / 3, SE 0.004). Opponent-dependent -> judge: kept. Test
  T-x-twice.
* Sprint 87 - BIQ_LEB_DIRECT: over their 2-level overcall of our 1NT, a weak responder (5-8) bids a
  five-card suit that fits at the 2 level directly (Q-Plus 9 / 10: 432.752.KQT862.4 2D over (2C)),
  and passes with 0-5 and no six-card suit (9 / 9); the 2NT relay stays for 3-level suits. 22 more
  matches, 2 lost. Judge (alone) Precision ~+23, 2/1 ~+11; curve d9ede44a: 1 board each. Kept, live
  02:22. Test T-leb-direct.
* Sprint 88 - BIQ_SUPERACC_8: after 1NT-2D/2H and opener's 3M (super-accept, or a competitive 3M after
  their bid) game needs 8+ with five trumps (4+ with six); the explicit pass is exempt from the
  forced-bid net (Q-Plus 10 / 10 pass with 4-7: KJT84.962.94.875 1NT-2H-3S, J8752.A2.842.954
  1NT-2H-(3D)-3S). Judge (alone) Precision ~+25 / 6, 2/1 ~+21 / 3; curve e6d708cf: 3 boards (2 / 1).
  Kept, live 02:28. Test T-superacc-4.
* Cost maps 261021c (code after sprint 88): Precision -793 / 13268 (agreement 10094), 2/1 -1351 / 18917
  (agreement 14482); at 261020a they were -1120 (9984) and -1748 (14358).
* Sprint 89 - BIQ_CUE_NOT_AGREED: sanity 2j ("partner's new suit is a cue-bid: sign off in trumps")
  no longer fires when both of us have bid partner's suit (1D-1S-2C-3C-...-5C: Q-Plus passes 4 / 4,
  biq "signed off" in 5S). Judge Precision -2 / 2, 2/1 +10 / 2 (agreement +4); curve 0. Kept, live
  02:46. Test T-cue-agreed.
* Sprint 90 - BIQ_P2NT_LIMIT: Precision's 1M-2NT is a limit raise (A-1MA-2NT.support-3-10-13), but
  the continuation treated it as Jacoby and bid game; now opener's 3M is passed with <= 11 (Q-Plus 5 /
  5), exempt from the forced-bid net. Judge Precision ~+33 / 5; curve 0 boards. Kept, live 02:53.
  Test T-p2nt-limit. Left: opener's answers to that 2NT also follow Jacoby (Q-Plus 4M with six, 3C
  with a minimum: too few records).
* Checkpoint 02:55 (10-21), code 363c7b29 (sprints 62-90 kept ones, uncommitted): curve vs end of
  10-20 day (02742e67 / 577d1319): 2/1 +0.082 IMP/bd (SE 0.026, 84 / 54 boards), Precision +0.083
  (0.028, 98 / 70); vs commit 09dd6eac: 2/1 +0.111 (0.036), Precision +0.124 (0.036). Live run: 74
  boards, no errors. Rejected tonight (switches off): ADV_JR_OVER_BID (62), RKC_QUEEN_ASK (67),
  NEGX_SUPPORT_FIRST (75), NT_OVC_16 (85).
* Sprint 91 - BIQ_SUPPORT_X_FIRST: the early "N-card support for partner over the overcall" raise in
  `_opener_rebid` pre-empted the support double; now 1m-1M-(overcall <= 2 level, not a cue of my suit)
  with exactly three trumps and 10+ doubles first (Q-Plus ~30 records; 29 more matches, 1 lost).
  Judge Precision ~+53 (curve ec828a61 +0.003, 4 / 1); 2/1 ~-16 / 21 with the curve flat (10 / 9) ->
  restricted to strong-club systems. Live 03:00. Test T-support-x.
* Sprint 92 - BIQ_P1C_BOTH_OPPS (Precision 1C-(opps)-P, opener's first rebid): with 5+ clubs and no
  five-card red suit / major, rebid clubs naturally (<= 3 level, <= 2 when both opponents bid) before
  any takeout X (Q-Plus 3 / 3); when both opponents bid and partner passed, pass with <= 19 unless a
  5+ red suit or major (Q-Plus 8 / 8: AJ85.K832.Q82.AK over 1C-(X)-P-(1D)). 10 more matches, 0 lost.
  Judge Precision ~+40 / 12; curve 492e2539: Precision -0.013 (SE 0.010, 9 / 13; the pass -27 IMP,
  clubs -12 against biq opponents). Competing after both opponents bid depends on them -> judge:
  kept, live 03:13 (watch: second curve dip after sprint 68). Test T-p1c-both.
* Checkpoint 03:25, code 492e2539 (through sprint 92): curve vs end of 10-20 day: 2/1 +0.082 (SE 0.026),
  Precision +0.073 (0.031; was +0.083 before sprint 92's -0.013); vs commit 09dd6eac: 2/1 +0.111,
  Precision +0.115. Cost maps 261021d: Precision -786 (agreement 10123 / 13268), 2/1 -1365 (14484 /
  18917). Live: 85 boards, no errors.
* Sprint 93 - BIQ_OVC_OVER_XFER: after their 1NT and responder's transfer, no natural overcall in the
  transfer's target suit (1NT-2D: no 2H; Q-Plus passed KJ5.AKQ752.-.T953); over their Stayman 2C a
  six-card natural overcall needs 10+ unless 6-5 (Q-Plus passed 865432.Q.Q64.A83). 8 more matches.
  Judge Precision +15 / 7, 2/1 +6 / 2; curve 4ebdc005: -0.001 / -0.002 (3 and 1 boards). Kept (judge
  rules for competitive calls), live 03:32. Test T-ovc-xfer.
* Run stop 06:17: the handover to 2/1 at board 151 used a stale East spare (the window first joined as
  East at 22:54, then rejoined as West); it sent abort_connection on "Start of board" and the TM stopped
  (SeatGone). 150 Precision boards played (-405 IMP raw; random 45 boards -1.67, SE 0.98). The TM never
  re-checked spares after registration: `_prune_spares` (repo tools/biq_bluechip_tm.py) now drops
  closed / aborted spares before a handover and on every lobby poll (socketpair test: closed and
  aborted dropped, live kept). Not restarted: joining windows needs the user.
* Sprint 94 - BIQ_XFER_MINOR_3M (pass-hook): 1NT-2D/2H-2M-3m (my forcing second suit)-3M -> 4M (Q-Plus
  2 / 2: K8764.-.J52.AJT64 over 1NT-2H-2S-3C-3S). Judge Precision ~+10 / 2; curve 0. Kept (repo only:
  the run had stopped). Test T-xf-3m-3M.
* Sprint 95 - BIQ_RESP_LONG_M: 1x-1M-1NT (uncontested), responder with seven of the major and 9-15 ->
  4M (before NMF and the 2NT invite), with six and <= 9 -> 2M sign-off (Q-Plus 3 / 3 each:
  QJ98532.KT4.-.QJ5 4S, QJ8762.J.A984.95 2S). Judge 2/1 ~+19 / 5, Precision ~+3; curve 81f660fb: 2/1
  +0.009 (SE 0.005, 9 / 1), Precision +0.001 (3 / 0). Kept (repo). Tests T-long-M-2, T-long-M-4.
* Sprint 96 - BIQ_ACCEPT_3M_INV (pass-hook): 1M-1NT-3M uncontested -> 4M with 3+ trumps and 6+ or two
  and 9+ (Q-Plus 2 / 2: JT2.AT3.J872.T63, 62.AT76.Q763.A42; passes weaker). Judge 2/1 +13 / 2; curve 0.
  Kept (repo). Test T-1nt-3m-acc.
* Checkpoint 06:45, code 0bdc169c (through sprint 96, uncommitted): curve vs end of 10-20 day: 2/1
  +0.090 IMP/bd (SE 0.027, 94 / 57), Precision +0.072 (0.031, 114 / 85); vs commit 09dd6eac: 2/1
  +0.119 (0.036), Precision +0.114 (0.038). Cost maps 261021e: Precision -778 (agreement 10131 /
  13268; 9984 at 261020a), 2/1 -1346 (14493 / 18917; 14358).
* Sim checks: sprints 83-91 kept 37 / 44 (2/1), 55 / 58 (Precision; the sim overrides some of sprint 87's
  direct 2-level suits, neutral vs Q-Plus); 92-93 kept 39 / 40; 94-96 kept 17 / 19 ("accept the
  invitation (" added to _CONVENTIONAL for sprint 96).
* Live run 261020_qplus_prec_21_biqS (user: "set up a new 10 hour autonomous run"), started 22:46
  from snapshot 261020_224557_dd8cb3e5b8 (sprints 48-65); sprints continue during it and passing
  ones deploy live (biq_deploy.py). New planner families false_pref, negx_rev.
* Committed c35379d5 (10-21, sprints 48-96). Offline sprints continue from cost maps 261021e.
* Sprint 97 - BIQ_OVC_RAISE4_4T: "Simple raise of overcall" to the 4+ level with four trumps when
  partner's overcall is still the last bid (1H-4S-P 5S with Q842.Q8.T982.Q64, 3S-4H-P 5H with
  A.Q842.9543.QJ97: Q-Plus 9 / 10 pass; still competes 4S over their 4H), and no 6-level raise
  without a void (4S-5H-5S, AT5.QJ752.4.T654). Judge Precision +11 / 3, 2/1 -9 / 6 (agreement +9);
  curve +6 / 1 board each. Kept. Tests T-ovr4-4t, T-ovr4-4t-comp, T-ovr6-pass.
* Sprint 98 - BIQ_PREEMPT_NO_REBID: "Compete: rebid own 6+" skipped when my opening was a weak two /
  preempt in that suit (not clubs), partner silent, <= 11 HCP (2H-X-P-2S with J.AT76543.542.92,
  2S-3H-P-P with KJT9763.T3.72.QJ: Q-Plus pass 4 / 4). Judge alone Precision +4 / 2, 2/1 +20 / 2;
  curve 0. Kept. Tests T-weak2-norebid, T-weak2-norebid2.
* Sprint 99 - BIQ_RAISE_TRY_2NT: 1x-1M-2M uncontested, responder with exactly four trumps and 10-16:
  2NT game try instead of 4M (Q-Plus 2NT / help-suit tries / 3NT; 4M only with five); Precision
  (limited opener, not 1C) passes with 10-11. biq's opener already answers the 2NT try. Judge alone
  Precision +44 / 12 calls, 2/1 +6 / 12; curve 2/1 +0.003 (21 boards), Precision +0.008 (19). Kept.
  Tests T-raise-2nt, T-raise-2nt-4s, T-raise-pass-p.
* Sprint 100 - BIQ_WJO_SHAPE: no weak jump overcall on a six-card suit with three+ of their suit
  (3-level jump) or a side four-card major (7.T984.K8.A98765 over 1H, 9.QJ98.42.KQT743 over 1S,
  Q754.942.A76543.- over 1C: Q-Plus pass 6 / 6; 6.87.KQ9754.K752 3D over 1S kept). Judge alone
  Precision -8 / 5, 2/1 +27 / 14; curve 2/1 -0.005 (SE 0.008, 6 boards), Precision +0.012 (0.007,
  9). Kept on the judge (opponent-dependent); 2/1 dip a watch item. Tests T-wjo-theirs, T-wjo-major,
  T-wjo-keep.
* Sprint 101 - BIQ_FSF_OPENER: 1x-1M-1y-2z (fourth suit): opener shows partner's major with three, or
  a doubleton honour and no stopper in the fourth suit (A632.A4.AJ93.532 2H; Q-Plus 3 / 3, biq 2NT);
  1x-1M-1y-2y (raise of my second suit) is passed with <= 15 (QT32.K82.KQ84.KT). Judge alone +1 / 2,
  +1 / 3; curve +13 / 1 board each. Kept. Tests T-fsf-2h, T-fsf-2h-3, T-2nd-raise-pass.
* Sprint 102 - BIQ_CHECKBACK_2NT (`_checkback_2nt`, sanity step 0b; not Precision): 1D/1H-1M-2NT,
  responder with five of the major (or six and four of the other major), <= 12: 3C checkback (Q-Plus
  4 / 4, biq 3NT). Opener: 3H with four hearts, else 3M with three, else 3NT (A83.AK53.A432.A7 3H,
  K3.Q86.AKQ5.AJ84 3NT); responder 4M / 3S (five spades over 3H) / 4M with six over 3NT / pass;
  opener 4S or 3NT over 3S. "checkback" reasons added to bid_sim._CONVENTIONAL. Judge alone 2/1
  -6 / 10 (agreement +8); curve 2/1 +0.005 (2 boards). Kept (partner's range: curve). Tests
  T-cb2nt-ask, T-cb2nt-4h, T-cb2nt-nofit, T-cb2nt-3s.
* Sprint 103 - BIQ_D1_NT_REBID: 1D-1M uncontested, four clubs, no singleton, <= 15, diamonds <= 5
  (<= 4 in Precision): 1NT instead of 2C (2/1 Q-Plus 9 / 9 with 4-4 minors, 3 / 4 with 2-2-5-4), or
  1S with four spades over 1H (Precision 4 / 4). Judge alone Precision +49 / 9, 2/1 +31 / 13; curve
  2/1 -0.004 (SE 0.009, 18 boards), Precision +0.012 (0.010, 23). Kept. Tests T-d1-1nt, T-d1-1s.
* Sprint 104 - BIQ_RB_MINOR_2NT: opener's five-card minor already shown, partner's new suit or my
  reverse, uncontested: 2NT instead of three of the minor (AK2.9.9432.KJ732 1C-1H-2C-2S; Q-Plus
  11 / 13). Judge alone 2/1 +10 / 8; curve +0.001 (1 board). Kept. Tests T-rb-minor-2nt(-rev).
* Sprint 105 - BIQ_PASSED_2NT_RAISE (`_passed_2nt_raise`, sanity step 0c): (P)-1M-2NT by a passed
  hand = four-trump limit raise 9-12 instead of Bergen (Q-Plus 16 / 16); opener 3M (<= 13) / 4M.
  First version (responder always passed opener's answer): judge 2/1 -87 / 32, Precision -3 / 12;
  responder now bids 4M over 3M with 11-12 and over opener's new suit (Q-Plus 4S over 3H / 4D).
  Re-measured as 105b with 106-108 (frozen stepwise by flipping switch defaults): judge alone
  Precision -4 / 9, 2/1 -36 / 26 (agreement +21); curve Precision -0.003 (7 boards). OFF.
* Sprint 106 - BIQ_P1C_1H_STAYMAN (`_p1c_1h_stayman`, hooked in decide_bid / _rules_call on the
  REAL auction - the 1C-1H switched view turns 1C-1H-1NT into 1C-1NT-2NT): responder with a four-card
  major 2C Stayman (Q-Plus 14 / 14, biq 3NT), opener 2D / 2H / 2S (Q-Plus 10 / 11; biq read 2C as a
  1C-2C answer), responder 3M / 2NT (<= 9) or 4M / 3NT. Judge alone Precision 0 / 32 (agreement
  +22); curve -0.003 (16 boards). OFF.
* Sprint 107 - BIQ_W2_RAISE_FLAT: no preemptive raise of partner's weak two with three trumps and
  4-3-3-3 (Q-Plus pass 3 hands / 7 calls; it raised every three-trump hand with a doubleton). Judge
  alone Precision +19 / 4, 2/1 +8 / 4; curve -6 / -10 over 2-3 boards. Kept (judge; competitive).
  Tests T-w2-flat, T-w2-raise-dbl.
* Sprint 108 - BIQ_JR_CUE: 1x-1M-3M uncontested, responder 12-14: cheapest side-suit cue with the A
  or K below 4M (A7.A974.852.A987 3S, AJT86.T4.K542.A5 4C; Q-Plus 8 / 8, biq 4M); biq's cue
  machinery continues (opener cues back or signs off, responder passes 4M). Judge 0 / 3 each;
  curve 2/1 +0.004 (1 board). Kept. Tests T-jr-cue, T-jr-cue-4c, T-jr-cue-stop.
* Checkpoint 10:50 (10-21), code 9f13db61 (sprints 97-108, 105/106 off; uncommitted): curve vs
  0bdc169c (this morning, sprint 96): 2/1 +0.008 IMP/bd (SE 0.017, 53 boards), Precision +0.035
  (0.017, 56); vs commit 09dd6eac: 2/1 +0.127 (0.040), Precision +0.149 (0.041). Judge vs 261021e:
  Precision +120 / 43 (agreement 10131 -> 10166), 2/1 +88 / 75 (14493 -> 14559). costmap2.sh now
  exports WINEPREFIX (without it the scan's agreement came out ~90 / 300 calls low).
  Cost maps 261021f: Precision -787 (10166 / 13268), 2/1 -1281 (14559 / 18917).
* Sprint 109 - BIQ_ML_BACK_MAJOR: (1NT)-2H/2S (Multi-Landy major + minor)-P-2NT-P-3m-P: advancer
  goes back to the major with three (4M with four and 9+), else passes (Q-Plus 9 / 9; biq passed
  all). Judge 2/1 +30 / 5; curve 0. Kept. Tests T-ml-back-3h, T-ml-back-pass.
* Sprint 110 - BIQ_WEAK_ESCAPE_1NT (pass-hook): 1x-1y-1NT uncontested, responder <= 9 with a
  singleton / void: 2H with 5-5 spades-hearts, else 2y with a 5-5 or a six-card y, else 2 of
  partner's minor with five (Q-Plus 5-5+: 8 / 8; T632.K84.A8753.9 2D). Judge alone 2/1 +17 / 10,
  Precision +6 / 1; curve 2/1 +0.003, Precision +0.001. Kept. Tests T-esc-55, T-esc-minor, T-esc-none.
* Sprint 111 - BIQ_MINOR_3NT_STOP: responder who has rebid a minor, partner's new suit at the 3 level
  (stopper bid) in an uncontested forcing auction, unbid suits stopped: 3NT instead of four of the
  minor (Q9.92.74.AQJT876 1D-2C-2H-3C-3S; Q-Plus 5 / 5). Judge alone 0 / 1 and -3 / 1 (agreement
  +2); curve 0. Kept (Q-Plus's way, no evidence against). Test T-minor-3nt.
* Sprint 112 - BIQ_TEXAS_LOW: Texas (1NT-4D/4H) from 8 HCP (+ the NT-range offset; Precision 9)
  instead of 10 (Q-Plus 9 / 9 with a six-card major and 8-10: AKT985.643.Q6.T9, 8.AT9764.AJ.T643;
  biq Jacoby). Q-Plus 2/1 bids 3M with 11+ (slam interest) - not copied. Judge alone 2/1 +12 / 7,
  Precision 0 / 2; curve 2/1 +0.008 (SE 0.005), Precision +0.010 (0.005). Kept. Tests T-texas-8,
  T-texas-p9. (New hunting tool: samesp.py = auction prefixes with recurring disagreement.)
* Sprint 113 - BIQ_XDBL_MAJOR: 1m-(X), responder 4-9 with a five-card major (or four with a
  singleton outside opener's suit, 6+; any singleton from 8; not with a six-card minor): 1M at the
  one level instead of pass (Q-Plus 12 / 13: Q6432.J97.54.A93, JT98.9.Q975.K843; still passes
  QJ32.T5.832.K943 and W-I44b JT85.Q73.86432.K). Judge alone Precision +6 / 5, 2/1 +20 / 10;
  curve 0. Kept. Tests T-xdbl-5m, T-xdbl-4m-short, T-xdbl-flat.
* Sprint 114 - BIQ_STAYMAN_MINOR (`_stayman_minor`, sanity step 0b'): 1NT-P, game values, no four-card
  major, a singleton / void: 2C first (Q-Plus 9 / 9, biq 3NT), then 3m with six (forcing) unless
  opener's major is my short suit, else 3NT. Judge alone 0 / 13 calls (agreement +13); curve 2/1
  -0.004 (1 board). OFF (judge no gain).
* Sprint 115 - BIQ_NEGX_THEIR_MAJOR + BIQ_NEGX_1S_HEARTS: 1H-(1S): biq's "other major" was THEIR
  spades, so it doubled "4+ S" holding their suit; now pass with four+ of it (Q-Plus 8 / 8:
  QJ62.96.Q96.QJ75, KQ975.A76.K63.T5). 1m-(1S) with five+ hearts: negative X, not 2H (Q-Plus 9 / 9:
  KT3.KQ752.93.K83, QT.AKQ964.KT2.Q4). Judge alone 2/1 +15 / 26, Precision -1 / 22; curve 2/1
  +0.030 (SE 0.013, 22 boards), Precision +0.018 (0.012, 16). Kept. Tests T-negx-their, T-negx-1s-h.
* Sprint 116 - BIQ_W2D_NO_4D: over a weak 2D the "Game in major preempt" rule bid 4D (not a game)
  with 16+; now majors only, and balanced 15+ over 2D asks 2NT instead of 3NT (Q-Plus 2NT 7 / 7;
  responder bids 3NT over any answer). Judge alone 2/1 -26 / 13 (agreement +9); curve 2/1 +0.011
  (SE 0.006, 4 boards). Kept (partner's range: curve). Tests T-w2d-no4d, T-w2d-ask-unbal.
* Sprint 117 - BIQ_OPENER_F1NT (`_opener_after_f1nt`, sanity step 0a'; not Precision): 1M-1NT
  (forcing): six-card major 15-17 (seven 14+) 3M (Q-Plus 7 / 7, biq 2M); 5-3-3-2 12-17 a three-card
  minor, clubs first (6 / 6, biq 2M / 2NT); 18-19 balanced 2NT (4 / 4, biq 3NT); 5-3-3-2 with 11 pass.
  Responder: 3NT over 2NT with 7+, 4M over 3M with three and 6+ or two and 9+, 2M preference with a
  doubleton and <= 10 over 2m (Q-Plus 2 / 2). Judge alone 2/1 -4 / 35 (agreement +10); curve 2/1
  +0.009 (29 boards, +19 / -10). Kept (partner's range). Tests T-f1nt-3s, -2c, -2nt, -pref.
* Checkpoint 12:20 (10-21), code de66ea57 (sprints 97-117; 105 / 106 / 114 off; uncommitted):
  curve vs 0bdc169c (= commit c35379d5's bidding, this morning): 2/1 +0.069 IMP/bd (SE 0.025, 124
  boards, +79 / -45), Precision +0.065 (0.021, 79, +51 / -28); vs 9f13db61 (10:50 checkpoint): 2/1
  +0.061 (0.018), Precision +0.029 (0.013); vs 09dd6eac: 2/1 +0.188 (0.043), Precision +0.178 (0.043).
* Sprint 118 - Precision defence to their 1NT (Landy system): BIQ_P_NT_DEF = no Landy 2C on 4-4
  (Q-Plus 14 / 14 passed; biq 2C 6 times): curve +0.006 (11 boards). Kept. BIQ_P_NT_DEF5 = natural
  2-level overcall on a five-card suit with 6+ HCP in it and 9-14 (Q-Plus 5 / 5): judge positive
  (the pair: Precision +35 / 17) but curve -0.018 (SE 0.007, +4 / -15): OFF (strong evidence).
  Test T-p-nolandy44. Judge of the kept half: Precision +34 / 8.
* Sprint 119 - BIQ_P1D_2H_MAJORS (`_p1d_2h_majors`): Precision 1D-(P) 2H = five spades + four/five
  hearts, 5-9 (Q-Plus 6 / 6, biq 1S); opener 2S with two+ spades, 3D with six diamonds, else pass
  (Q-Plus 72.KT7.A9743.KQ9 2S, 5.Q73.AQJ74.JT62 pass). Judge +14 / 9; curve -0.003 (8 boards,
  +3 / -5). OFF (partner's range: curve).
* Cost maps 261021g 2/1: -1201 (14609 / 18917; 14559 at 261021f).
* Sprint 117b (refinement, measured with 120): six-card 3M jump only 16-17 (Q-Plus 2S with
  AQJ654.KQ.K6.953 15); 5-3-3-2 with 16-19 rebids 2NT (Q-Plus 7 / 8: K9843.KQT.A94.A4,
  AKT74.T9.A83.KQ8), the three-card minor only 12-15.
* Sprint 120 - BIQ_RESP_55_SPADES: 1m-(P) with 5-5 majors responds 1S (Q-Plus 6 / 6, biq 1H);
  BIQ_RESP_1D_1NT11 (2/1): 1D-(P) 10-11 balanced, no four-card major: 1NT, not 2NT / inverted 2D
  (Q-Plus 9 / 9). Tried and dropped before measuring: NMF reply 2H before 3-card spade support
  (Q-Plus does it, but biq's responder then bid 2NT with five spades and lost the 5-3 fit).
  Judge 2/1 (with 117b) +54 / 19 (9 better, 3 worse); curve 2/1 +0.000 (11 boards). Kept.
  Tests T-resp-55, T-1d-1nt11, T-f1nt-2nt16.
* Sprint 121 - BIQ_OVC1_SIX: one-level overcall on a six-card major with 8-10 HCP whatever the suit
  texture (Q-Plus 7 / 7: T97632.87.KJ6.AJ, K76432.JT.5.AT53, KT9832.-.9532.AJ5 1S; biq passed).
  Judge alone Precision +6 / 3, 2/1 +19 / 8; curve 2/1 +0.013 (15 boards, +10 / -5), Precision
  +0.010 (12, +8 / -4). Kept. Test T-ovc1-six.
* Sprint 122 - BIQ_ML_2D_DOUBLED (`_ml_2d_doubled`, sanity step): my Multi-Landy 2D (one six-card
  major) over their 1NT doubled, partner passed: bid 2 of my major (Q-Plus 5 / 5: AJ85.AKQ973.64.8
  2H, KT8753.J3.Q87.Q9 2S); biq passed and played 2D doubled. Judge 2/1 +18 / 5 (all 5 now agree);
  curve 0. Kept. Test T-ml2d-dbl.
* Sprint 123 - BIQ_P1C_1H_MINOR (`_p1c_1h_minor`, real-auction hook beside 106's): Precision 1C-1H
  (balanced positive), opener with a singleton / void, a six-card minor or 5-4 minors (<= 21): 2m
  instead of 1NT (Q-Plus 14 / 15: A9.63.AQJT8.AJ73 2D, 5.AKQ.Q43.AQJ873 2C; balanced 5-3-3-2 still
  1NT). biq's responder already shows four-card majors over it, as Q-Plus does. Old test S-1N3D
  widened to {3D, 2D}. Judge alone Precision +17 / 12 (agreement +12); curve Precision +0.014 (12
  boards, +7 / -5). Kept. Tests T-p1c1h-2d, T-p1c1h-bal.
* Checkpoint 12:57 (10-21), code cda55434 (sprints 97-123; 105 / 106 / 114 / 118-half / 119 off;
  uncommitted): curve vs 0bdc169c (this morning's commit c35379d5): 2/1 +0.082 IMP/bd (SE 0.027,
  144 boards, +92 / -52), Precision +0.095 (0.026, 114, +71 / -43); vs de66ea57 (12:20): 2/1 +0.014
  (0.011), Precision +0.030 (0.015); vs 09dd6eac: 2/1 +0.201 (0.044), Precision +0.208 (0.045).
  Sim check 118-123 (vs 261021g): 2/1 kept 32 / 32, Precision 23 / 23.
* Cost maps 261021h (code cda55434): Precision -735 (10201 / 13268), 2/1 -1102 (14637 / 18917).
* Sprint 124 - BIQ_M1H_1S (`_m1h_1s`): 2/1 1m-1H, opener with four spades rebids 1S up the line
  (Q-Plus 31 / 33 incl. balanced and three-heart hands; biq 1NT / 2NT / 2H / 2D). Judge -12 / 20
  (agreement +20); curve 2/1 -0.011 (18 boards, +8 / -10). OFF.
* Sprint 125 - BIQ_SANDWICH_2S6: sandwich seat (1x-P-1y, my first call), six spades and 6-10: 2S
  weak jump (Q-Plus 9 / 9: KQT954.8.72.QT96, AQ8542.T7.9.8762, KJT873.52.A2.Q84; biq pass / 1S;
  placed ahead of the one-level overcall). Judge 2/1 +27 / 13, Precision +2 / 4; curve 2/1 -0.005
  (2 boards), Precision -0.003 (5). Kept (preempt, opponent-dependent: judge); watch item.
  Test T-sandwich-2s.
* Sprint 126 - BIQ_ML_ADVANCER_FIX: `_multi_landy_mine` ignored "my" 2-level suit call made after
  partner's (1NT-2C-P-2D-P-2S: biq read its own pass-or-correct 2D as a Multi 2D and "corrected"
  to 3H with 765.Q63.T98.9764; Q-Plus passes 4 / 4; 2NT asks still count, sprint 109).
  BIQ_OVR1NT_RUN6: 1m-(1NT), 3-9 with a six-card suit and a singleton: 2 of it to play (Q-Plus 6 / 6:
  T72.AKJT86.954.2 2H; passes with 1 HCP). Judge alone 2/1 +77 / 11; curve 2/1 +0.005. Kept.
  Tests T-ml-adv-fix, T-ovr1nt-run6. (Process note: a `pkill -f` on a pattern in my own command
  killed my shell; kill by PID only.)
* Sprint 127 - BIQ_CUE_RAISE: 1M-(natural 1/2-level overcall), four trumps and 10+: cue-bid their
  suit instead of the competitive jump to 3M (Q-Plus 0 / 17 jumps: AQ5.J865.A83.J72 1H-(1S)-2S,
  KQ85.43.AQ74.976 1S-(2H)-3H); over a 3-level overcall 4M (Q6.KQ43.J986.K85 1H-(3C)-4H). Opener
  (`_cue_raise_answer`): over the 3-level cue 3M with <= 13 (Precision) / 14, else 4M (biq read it as
  a splinter and bid 4M). Judge alone Precision +17 / 12, 2/1 +43 / 8; curve +0.006 each. Kept.
  Tests T-cue-raise, T-cue-raise-ans, T-cue-raise-3lvl.
* Sprint 128 - BIQ_BERGEN_QP: weak raises with a void, six trumps or a 5-5 jump to 4M (Q-Plus
  QT82.J9862.A986.- 4S, T7542.94.AQT62.8 4S); flat 4-3-3-3 / 5-3-3-2 with <= 6 raise to 2M
  (AJ98.862.T93.762 2S); 2/1 constructive 3C from 7 HCP (or 6 with five trumps; Q-Plus
  KT84.Q98.J.J6542, 963.KT72.J3.K765). Precision's Bergen (flag range-10-13, records mixed: 3C at
  8-10, 3D at 7) left as is. Judge alone 2/1 +34 / 17, Precision -16 / 6; curve 2/1 +0.015 (16
  boards, +11 / -5), Precision +0.001. Kept (partner's range). Tests T-bergen-7, -flat, -void.
* Checkpoint 14:35 (10-21), code 7520176f (sprints 97-128): curve vs 0bdc169c (this morning's
  commit): 2/1 +0.104 IMP/bd (SE 0.029, 169 boards, +107 / -62), Precision +0.099 (0.027, 125,
  +76 / -49); vs cda55434 (12:57): 2/1 +0.021 (0.012), Precision +0.004 (0.009).
* BUG FIX bid_sim.should_simulate lowercases the reason and compared it with _CONVENTIONAL as is,
  so every entry with a capital ("Checkback answer", "Stayman answer", "No weak jump overcall",
  "Cue raise: ", "2NT inquiry ...", "natural over the balanced 1H", ...) never matched: the sim
  checks of sprints 97-127 ran without those protections. Now `k.lower() in why`. Sim check
  124-128 (before the fix): 2/1 42 / 49, Precision 22 / 22; the 1NT escapes (sprint 126) it
  overrode are protected now.
* Sprint 128b: BERGEN_QP's 4M jump only uncontested (it fired over 1S-(X) and 1S-(1NT): Q-Plus 2S).
  Judge vs 128: Precision +14, 2/1 +3; curve 0. Kept (code e32096f6).
* Full-day sim check (all calls changed since 261021e, protections working): 2/1 kept 240 / 245,
  Precision 115 / 116; of the overrides 3 / 6 match Q-Plus. Added "balanced with four clubs" (103)
  and "game try after the raise (" (99), which the sim had passed against Q-Plus.
* Sprint 129 - BIQ_PREC_NT_5M_7: sprint 38 again with a narrower trigger (7+ HCP in the five-card
  major: Q-Plus 1M 12 / 12). Judge Precision +48 / 12 but curve -0.008 (15 boards, +6 / -9). OFF:
  biq's continuations after 1M lose what 1NT-Stayman finds (as in sprint 38).
* Sprint 130 - BIQ_FORCED_CUE: the sanity wrapper's forced game raise of partner's major replaced by a
  4-level cue in the cheapest side suit with the A or K (Q-Plus 4C on 13 calls: 54.Q83.A84.AKJ87
  1NT-3H). Judge 2/1 +25 / 22, Precision +2 / 22 (agreement -7); curve 2/1 -0.007 (+1 / -5),
  Precision -0.019 (SE 0.009, +2 / -10). OFF.
* Sprint 131 - BIQ_NFB_NOT_FORCING: Precision (C-negative-free-bid) 1m/1M-(2x)-2y is not forcing:
  exempted from the contested forced-bid net in _sanity_wrap and from _partner_was_forcing (Q-Plus
  passed 1D-(2C)-2S with K94.KJT5.AJ9.T73 / K96.KQT9.KT5.T43; biq 2NT). BIQ_M_OVR1NT_PASS: 1M-(1NT),
  <= 7 and fewer than three trumps: pass (Q-Plus AT63.4.K843.7632, KQ985.5.T8642.J8; biq answered 2S
  as if uncontested - NT overcalls fell through to _respond_to_major). Judge alone Precision +37 / 5,
  2/1 +10 / 1; curve Precision +0.004, 2/1 -0.005 (2 boards). Kept. Tests T-nfb-pass, T-m-ovr1nt.
* Checkpoint 14:10 (10-21), code a2f62b24 (sprints 97-131): curve vs 0bdc169c (this morning's
  commit c35379d5): 2/1 +0.099 IMP/bd (SE 0.029, 171 boards, +107 / -64), Precision +0.103 (0.028,
  131, +80 / -51); vs cda55434 (12:57): 2/1 +0.016, Precision +0.009; vs 09dd6eac: 2/1 +0.218
  (0.046), Precision +0.217 (0.046).
* Cost maps 261021i (code 365fd5e7 = a2f62b24 bidding; Precision judge now also reads run 261020's 150
  boards, so 15643 positions): Precision -1023 (11987 / 15643), 2/1 -927 (14668 / 18917). Judge base for
  sprints 132+ is 261021i (judge.sh / costmap2.sh RP list includes 261020_qplus_prec_21_biqS).
* Sprint 132 - BIQ_CUE_NO_PASS (`_cue_no_pass`, last step after _sanity_wrap in decide_bid): opponents
  silent, a suit one of us bid and the other raised (or derive_context's trump), partner's 4-level new
  suit below game in it: never pass, sign off in game (1S-2C-4C-4D-4H with K97.QJ8.KQT85.82, biq
  passed 4H; Q-Plus bids on 12 / 12 in such spots). Not when partner's suit is one I bid or partner's
  own suit again (first version: curve Precision -0.011, 5 boards: 1C-1D-2H-2S-3D-4D-4H is natural);
  alerted minor openings (strong 1C / 2C) are no agreement. Judge 2/1 +9 / 2, Precision 0; curve 0 / 0.
  Kept. Tests T-cue-nopass, T-cue-nopass-1c.
* Sprint 133 - BIQ_NEGX_RAISE_COMP (`_negx_raise_comp`, beside 132's last step): 1x-(1y)-X-(..)-2z-
  (they bid again), my negative X and partner's suit answer: with four trumps and 6-10 HCP raise
  partner's suit one level (to 3 at most); biq passed without a reason (live 261021 board 3, -7:
  J842.K5.A82.Q854 over 1D-(1H)-X-(P)-2S-(3H), Q-Plus 3S; records: Q-Plus raises 7 / 11). Judge
  (net of 132) 2/1 about -4 / 8 (agreement +3), Precision +3 / 2; curve 2/1 +0.015 (SE 0.009, +10 /
  -5), Precision +0.019 (SE 0.008, +9 / -2). Kept (partner's range: curve). Test T-negx-raise-comp.
* Sim check 132-133 (scan --sim --only the judge's changed calls): the simulation passed 7 / 10 of the
  new 2/1 calls (6 away from Q-Plus's call); bid_sim._CONVENTIONAL gains "is a cue below game" and
  "in competition after my negative x": kept 10 / 10, Precision 2 / 2.
* Sprint 134 - BIQ_P1D_2D_RELAY (`_p1d_2d_relay`, sanity step 0a, Precision only, uncontested): 1D-2D,
  opener balanced 11-14 bids 2H, not 2NT (Q-Plus 6 / 6: AJ76.KT4.QJ5.Q53, KT5.QT64.K5.A862); responder
  relays 2S (5 / 7); opener 2NT balanced (4 / 4), else 3C with four clubs / 3D; over 2NT responder 3NT
  with 12+, else 3D. Judge Precision +67 / 16 (agreement +12, 11 better / 1 worse); curve Precision
  +0.002 (+11 / -4). Sim keeps 18 / 18. Kept. Tests T-p1d2d-2h, -2s, -2nt.
* Sprint 135 - BIQ_CUE_RAISE3: 1H-(1S) with four+ hearts and 10+ no longer takes the "four+ of their
  S: pass" rule (Q-Plus cue-bids AT54.KQ84.J9543.-, 6542.KQJT9.QJ2.J), and three trumps with 14+ over a
  one-level overcall (at most three of their suit) cue-raises too (Q-Plus 2S with Q63.Q32.A6.AKJ53,
  AQ8.J62.T8.AQJ52; biq 2NT). Judge Precision +21 / 5 (agreement +5); curve Precision +0.0023 (+2 /
  -0), 2/1 +0.0003. Kept. Tests T-cue-raise3, T-cue-raise-4s.
* Sprint 136 - BIQ_P1D_MINORS_3C: Precision 1D-1M-3C with five-five+ minors and 13+ (Q-Plus 5 / 5; it
  plays 3C game forcing, responder 3S / 3NT on 8+). Judge Precision +15 / 7 (agreement +5) but curve
  -0.0047 (SE 0.0043, +1 / -2: 1D-1S-3C-3NT down where 2D made). OFF (partner's range: curve).
* Sprint 137 - BIQ_P1D_1H_1S (`_p1d_1h_1s`, Precision only): 1D-1H, opener with four spades (at most
  three hearts) and a balanced hand rebids 1S, not 1NT (Q-Plus 7 / 7: QJ43.KT.Q963.KQ6,
  KJ82.T6.AKT7.743). Unlike 2/1's sprint 124 (curve -0.011) the Precision curve gains: +0.0033 (+2 /
  -0); judge +12 / 7 (agreement +7). Kept. Test T-p1d1h-1s.
* Sprint 138 - BIQ_MAJOR_1C1D re-measured (Precision 1C-1D-1M with a five-card major in a 5-3-3-2; Q-Plus
  7 / 7, biq 1NT): judge +7 / 7 (agreement +6) but curve -0.010 (SE 0.009, +5 / -6), as on the WBridge5
  deals: later rounds still read 1M as unbalanced. Left OFF. (Q-Plus also shows a four-card major
  before five clubs after 1C-1D, AQ83.A.A95.QT742 1S, KQ63.AQJ5.AQ54.3 1H: same later-round risk, not
  tried.)
* Sprint 139 - BIQ_P_2NT_LIMIT_ANS: Precision's 1M-2NT is a three-card limit raise (10-13; system flag
  A-1MA-2NT.support-3-10-13, biq's own responder bids it that way) but opener answered it as Jacoby
  (shortness / 4M on a minimum). Now: 4M with six trumps, 13+, or 12+ unbalanced; else 3M sign-off
  (Q-Plus 3S with AQ854.K92.K3.853, AJT94.Q62.62.A32; responder passes 3M, already coded). Judge
  Precision +53 / 13 (agreement +5); curve Precision +0.014 (SE 0.006, +12 / -1). Sim keeps 43 / 43.
  Kept. Test T-p2nt-limit. (Q-Plus also uses 3C over the 2NT as a try, 3D = minimum; not copied.)
* Sprint 140 - BIQ_RESP_1S_3H (`_resp_1s_3h`, not Precision): 1H-(P) with three hearts, four+ spades
  and 6-12: 1S first, not the simple raise / forcing 1NT (Q-Plus 2/1: 1S on every such record,
  KQ7642.QT2.3.QT2, KJ854.K86.T7.KQ6; Precision mixed 5 / 9, left alone). Judge 2/1 +30 / 19
  (agreement +17); curve 2/1 +0.005 (+8 / -6). Sim keeps 29 / 29. Kept. Test T-1h-1s-3h.
* Sprint 141 - BIQ_1M1N2M_GAME: 1M-1NT-2M (opener's six-card major), responder with three trumps bids
  game with 11+ or with 8-10 and a singleton, else passes (Q-Plus 4S 6 / 7 with 973.AJ3.A84.Q852,
  K65.A8764.JT98.8; passes A72.Q642.Q3.JT95; biq invited 3M). Two trumps: the 11-12 invite stays.
  Judge 2/1 +9 / 7 (agreement +7); curve 2/1 +0.0017 (+3 / -2). Kept. Test T-1m1n2m-game.
* Sprint 142 - BIQ_W2_SINGLETON_PASS: partner's weak two, a singleton (or void) in it and <= 16 HCP:
  pass, not the 2NT ask (Q-Plus 3 / 3: KQJ8.5.AQ987.A75, 4.K54.AKQ2.KJ842, 6.K93.AQ62.KQ987); the
  learned game net skips this pass (it bid 3NT). Judge 2/1 +19 / 4, Precision +6 / 2; curve 2/1 +0.0020
  (+3 / -0), Precision +0.0030 (+3 / -0). Kept. Test T-w2-misfit. Sim check 141-142: kept 39 / 40 2/1
  (it raised A72.Q642.Q3.JT95 to 3S over 1S-1NT-2S, Q-Plus passes) and 45 / 45 Precision;
  _CONVENTIONAL gains "hcp, no shortness" and "pass the weak two: misfit".
* Checkpoint 00:40 (10-22), code 406e7b24 (sprints 97-142; 136 / 138 off; uncommitted): curve vs
  a2f62b24 (start of the night): 2/1 +0.024 IMP/bd (SE 0.013, +25 / -13), Precision +0.044 (SE 0.014,
  +39 / -7); vs 0bdc169c (commit c35379d5): 2/1 +0.123 (SE 0.032), Precision +0.147 (SE 0.030); vs
  09dd6eac: 2/1 +0.242 (0.047), Precision +0.261 (0.047). All deployed live (run 261021).
* Sprint 143 - BIQ_OVC_JUMP_4T (Precision only): partner's 1M overcall doubled (negative X), four
  trumps and 6-10: jump to 3M, not the simple raise (Q-Plus 3M with QT.T975.A864.K73,
  A762.K753.J72.73; about 3 of 20 raise one level). Judge Precision +24 / 20 (agreement +7), 2/1 -32 /
  8 (curve 2/1 -0.0037, Precision +0.0003): a preempt, opponent-dependent, so the judge decides per
  system: kept for Precision, off for 2/1. Test T-ovc-jump4. Sim keeps 62 / 65 (its 3 overrides go
  back to 2S; 2 of them = Q-Plus).
* Sprint 144 - BIQ_S1C_RAISE3 (Precision, defending their strong 1C): partner's natural overcall, three
  trumps and 4+ HCP: raise one level (to 2 at most; Q-Plus 2H with KT9.J84.32.J9654,
  95.854.A832.J432 over 1C-(1H)-1S, 2D over 1C-(1D)-X; biq passed below 6 HCP). Judge Precision
  +12 / 9 (agreement +7); curve -0.0050 (SE 0.0071, +1 / -2: both losses were old freak wins, a
  lucky 1C-1D-P-P-X-P-1H-4NT). Competitive raise, opponent-dependent: judge decides. Kept. Test
  T-s1c-raise3.
* Cost maps 261022a (code 629e73a8, sprints through 144): Precision -849 (12031 / 15643; -1023 at
  261021i), 2/1 -911 (14699 / 18917; -927).
* Sprint 145 - BIQ_KOKISH_QP: Q-Plus's 1C-1D rebids have no Kokish 2H on 22-23 balanced (2NT, 4 / 4)
  nor on 16-19 hearts (1H); its 2H was a 24 balanced. Judge Precision -19 / 7 (agreement +7), curve
  -0.011 (+10 / -10). OFF.
* Sprint 146 - opener after 1m-1M: (a) BIQ_OPENER_RAISE_QP: no 3-card raise holding a six-card minor,
  rebid the minor (Q-Plus 2C with 92.Q82.K6.AQJ763, K94.J65.5.AKQJT4 over 1C-1H); (b)
  BIQ_OPENER_JUMP_SINGLETON: 3M with four trumps, a singleton and 13-14 (Q-Plus 5.QJ72.A93.KQJ52).
  Together: judge Precision +39 / 7, 2/1 +12 / 10 but curve 2/1 -0.0037 (+6 / -12), Precision -0.0023.
  (a) alone: judge 2/1 +18 / 4 (agreement +4), curve 2/1 +0.0037 (+3 / -4): kept; (b) OFF. Test
  T-op-raise-qp.
* Sprint 147 - BIQ_X_54_MAJOR (sanity step 0x): over their 1M, a five-card minor, four of the other
  major, a singleton in theirs and 11+: takeout X, not the 2m overcall (Q-Plus 3.6543.AKJ95.AK7,
  6.QT52.AKJ93.J85; with a six-card minor it overcalls). Judge 2/1 +21 / 3, Precision -6 / 2
  (agreement +3 / +2); curve 0 / 0. Kept. Test T-x-54.
* Sprint 148 - BIQ_LEGALIZE_1NT_OVC: the legalizer no longer lifts a "1NT overcall" (15-18) to 2NT when
  the auction has reached the 2 level (fourth seat after their 1x-1y-2z: Q-Plus passes 6 / 7,
  KQ5.Q76.KQ98.KT8, 864.AK4.A653.AT7). Judge Precision +51 / 10, 2/1 +27 / 11 (agreement +7 / +7);
  curve Precision +0.0043, 2/1 -0.0023 (+1 / -2). Competitive, judge decides: kept. Test T-leg-1nt-ovc.
* Sprint 148b - BIQ_LEGALIZE_NT_ADV_ONLY: the 1NT-to-2NT legalizer bump kept only for the advance of
  partner's takeout double (Q-Plus 2NT 3 / 4); opener / responder 1NT rebids lifted to 2NT never
  matched (Q-Plus pass or X, 9 records). Judge Precision +5 / 5, 2/1 +4 / 4; curve 2/1 +0.007 (+8 /
  -3), Precision 0 (+5 / -2). Kept.
* Sprint 149 - BIQ_OVC_REBID_SILENT: the overcaller's "6+ own suit" rebid over anything but partner's
  raise goes to the cheapest level only, at most 3, and at the 3 level only with 13+ (it jumped to 4S
  over partner's competitive 3C: Q-Plus passed KJ9862.K86.A9.42, AJT852.A8.86.Q65 after
  1NT-P-2D-2S-P-3C; 3S with AKJT96.QJT.K87.5); the general compete rule skips that pass. Judge
  Precision +26 / 11 (agreement +2), 2/1 +14 / 16; curve Precision +0.004, 2/1 -0.0003. Kept. Test
  T-ovc-rebid-silent.
* Sprint 150 - BIQ_2C_REBID_MINOR: strong 2C opener shows a long minor over any answer (Q-Plus 3D with
  KJ.AQJ5.AKJT952.- over 2S) and 2NT with a balanced 20-21 instead of the catch-all 3NT. Judge 2/1
  +19 / 5 (agreement +5) but curve -0.0013 (+2 / -3: 2C-2S-3D-4S-RKC slams on misfits, 7H down). OFF
  until responder's continuation after 2C-2M-3m stops driving to slam without a fit.
* Sprint 151 - BIQ_UCB_DECLINE_CHEAP: overcaller declines partner's cue raise at the cheapest level of
  the suit (Q-Plus 2S over a 2D cue, 3S over 3D; biq one level higher). Judge Precision -16 / 22, 2/1
  -19 / 26; curve 2/1 -0.012, Precision -0.022 (SE 0.013): biq's advancer reads the higher decline.
  OFF.
* Checkpoint 02:25 (10-22), code 3f9cfb07 (sprints 97-149; 136 / 138 / 145 / 146b / 150 / 151 off;
  uncommitted, all deployed): curve vs a2f62b24 (start of the night): 2/1 +0.032 IMP/bd (SE 0.016,
  +37 / -23), Precision +0.047 (SE 0.017, +52 / -14); vs 0bdc169c (commit c35379d5): 2/1 +0.131 (SE
  0.033), Precision +0.151 (SE 0.032).
* Sim check 143-149 (all of s149's changed calls): kept 2/1 73 / 78, Precision 95 / 102; 5 of the 12
  overrides go toward Q-Plus (mostly the silent-partner rebid, left alone); protected the two that
  went away from it: "three trumps opposite a six-card major" (141) and the 4-5 takeout X (147).
* Sprint 152 - BIQ_P2C_ASK11 (Precision): over partner's 2C, any 11+ hand without a five-card major asks
  with 2D (Q-Plus 10 / 10; biq asked only with 13+ balanced, else 2NT or even pass: A3.KT43.K9863.K2,
  AK96.A7.Q9853.J8 passed). Judge Precision +19 / 8 (agreement +8); curve Precision +0.011 (SE
  0.008, +5 / -3). Sim keeps 8 / 8. Kept. Test T-p2c-ask11.
* Sprint 153 - BIQ_RESP_1NT_MISFIT (2/1, last step after _sanity_wrap): 1S-(P) with 4-5 HCP, at most
  one spade and a five-card suit: forcing 1NT, not pass (Q-Plus 3 / 3). Judge 2/1 +1 / 2 (agreement
  +2); curve 2/1 +0.0023 (+4 / -2). Kept. Test T-1nt-misfit.
* Sprint 154 - BIQ_GNET_21_PLUS: the learned game net one point stricter in 2/1 (it bid 72 games Q-Plus
  did not, -113 on the judge). Judge 2/1 -24, curve 2/1 -0.110 IMP/bd (SE 0.023, +24 / -57): the
  net's thresholds are right for biq's own auctions. Default 0 (unchanged).
* Sprint 155 - the other way, BIQ_GNET_21_PLUS=-1: judge 2/1 -169 (agreement -26), curve +0.030 (SE
  0.029, +67 / -90). Not taken: within one SE on the curve and a large judge loss; thresholds stay.
* Cost maps 261022b (code 5d3bfc06, sprints through 153): Precision -721 (12055 / 15643), 2/1 -808
  (14717 / 18917). Since 261021i (start of the night): Precision +302, 2/1 +119 IMP.
* Sprint 156 (not kept, not measured): 2C over their strong 1C needs six clubs: the records split
  (Q-Plus 2C with JT54.Q5.Q2.AK965, pass with KQ942 / KQ743), BIQ_S1C_CLUBS6 off.
* Sprint 157 - 149's silent-partner / new-suit pass not with a seven-card suit (Q-Plus rebids
  KJ76.K.KJ87654.4 3D, KQ3.63.AKT86542.- 4D). Judge Precision +14, 2/1 +13 (agreement +2 / +1);
  curve 0 / 0. Kept.
* Sprint 158 - BIQ_P_W2_RAISE4 (Precision): partner's weak two in a major, four trumps and 8+: game
  (Q-Plus 9 / 9: 964.AT97.AJ5.872 4H over 2H-(2S), K985.Q9.K64.AT96 4S over 2S-(3H); biq 3M). 2/1
  records are split (6 / 12), left alone. Judge Precision +14 / 10 (agreement +8); curve +0.0013 (+6
  / -5). Kept. Test T-p-w2-raise4.
* Sprint 159 - BIQ_COMP_SHOW_MAJOR: opener in competition shows a four-card unbid major before
  rebidding the minor (Q-Plus 2S with AKJ7.T8.Q6532.K7 over 1D-(1H)-2C). Judge 2/1 +32, Precision -17;
  curve 2/1 -0.012 (+1 / -6), Precision -0.006. OFF.
* Sprint 160 - BIQ_CUE_ANSWER_SHAPE: opener over partner's 3-level cue raise also accepts (4M) with a
  six-card suit or a singleton / void (Q-Plus 4S with AT9732.JT8.T5.AK, KJT87.J6.9.AQ874; 3S only with
  a flat 10-12). Judge Precision +10 / 4, 2/1 +9 / 2; curve 2/1 +0.0033, Precision 0. Kept. Test
  T-cue-ans-shape.
* Checkpoint 03:55 (10-22), code aeffc141 (sprints 97-160; off: 136 / 138 / 145 / 146b / 150 / 151 /
  154-156 / 159; uncommitted, all deployed): curve vs a2f62b24 (start of the night): 2/1 +0.038 IMP/bd
  (SE 0.017, +42 / -25), Precision +0.060 (SE 0.020, +63 / -22); vs 0bdc169c (commit c35379d5): 2/1
  +0.136 (SE 0.033), Precision +0.163 (SE 0.033); vs 09dd6eac: 2/1 +0.255, Precision +0.277.
* Sprint 161 - BIQ_X_PASS_6: penalty pass of partner's one-level takeout X only with six trumps (Q-Plus
  bid 1NT / 2C with AQ63, JT975, QT972, Q9762). Judge Precision -6, 2/1 +4; curve -0.006 / -0.0013.
  OFF.
* Sprint 162 - BIQ_OPEN_4NT_ANS: partner's 4NT opening (Q-Plus: solid minor in 2/1, both minors in
  Precision) is answered 1430 by aces, 5C = 1 / 4, 5D = 0 / 3, 5H = 2 (Q-Plus 5C with one ace 3 / 3,
  5D with none); then pass partner's placement. biq passed the 4NT. Judge Precision +15, 2/1 +22
  (agreement +1 / +4); curve 0 (biq never opens 4NT). Kept. Tests T-4nt-open(-0 / -place).
* Sprint 163 - from live board 95 (-1100): 1H-(P)-1S-(X)-P-(2C)-2S-(P) biq rebid 3H with KJ.KJ853.872.A75,
  then repeated "3H" over 3H-(X)-P-(P) and the legaliser made it 4H doubled. (a) BIQ_LEGALIZE_SAME: a
  rule call that repeats the contract I bid myself is a pass, never bumped. (b) BIQ_OPENER_PASS_REBID:
  partner rebid their own one-level suit at the 2 level, I'm 15- with two or fewer of it: pass, not
  3 of my suit (also exempt from the forcing sanity step 2). With minors too (Q-Plus passes
  T.KQ76.A82.QJ632, KQ93.2.A9852.A76): judge 2/1 +43 but curve 2/1 -0.0013 (8 boards, +4 / -4; the
  losses were 1m openings whose 3m rebid biq's responder raised to a making 5m). Majors only (163b):
  judge 2/1 +13 (agreement +2), curve 2/1 +0.0037, Precision +0.0037 (2 boards each, +2 / -0). Kept,
  deployed. Tests T-op-pass-rebid, T-legal-same.
* Sim check 162-163b (their changed calls, scan --sim --only): kept 2/1 5 / 5, Precision 1 / 1.
* Sprint 164 - BIQ_PRE_OVC_11: over their 3-level preempt a six-card major with 5+ HCP in it (or
  seven cards) overcalls on 11+, not 14+ (Q-Plus acts on 9 / 9 of its 11-13 HCP six-heart hands over
  3S: 4H 7, X 2; biq passed: "No safe action", -201 IMP over 27 live Precision boards). Judge
  Precision +1, 2/1 -2 (agreement +3 / +3: the one 4H Q-Plus doubled instead cost 13, one pass
  scored 10 better); curve 0 boards. Sim keeps 11 / 11. Kept on agreement (opponent-dependent,
  judge neutral). Test T-pre-ovc-11.
* Cost maps 261022c (code fd848924, sprints through 164; 2/1 runs + tonight's 261021 live run, 21226
  calls): Precision -640 (from -721), 2/1 -850 (2309 new calls).
* Sprint 165 - BIQ_RAISE_FREE_MAJOR: 1x-(1y)-2M-(P), opener with three or more of partner's free major
  raises to 3M (4M with 16+), not 3 of the minor via the 2/1 fallback (Q-Plus 3H on 6 / 6:
  QT53.Q74.A.A9653, 92.762.AK532.A95, 2.AT2.QJT973.KJ3). Not after a strong 1C. Judge 2/1 +17,
  Precision -7 (agreement +1 / +4; net +8 over the 6 calls); curve 0 boards (biq's responder doubles
  instead of the free 2H). Kept, deployed. Tests T-raise-free-M(-p).
* Sprint 166 - BIQ_FREE_2H_21: 2/1 1m-(1S) with a good heart hand bids 2H, not the negative X (261022c
  records incl. tonight's run: five hearts 10+ with 4+ HCP in them 6 / 7, six 9+ 4 / 4, seven 8+ 3 / 3).
  Judge 2/1 +2 (agreement +9), curve 2/1 -0.0127 (SE 0.0071, +4 / -7): biq's opener still treats the
  free 2H as forcing to game (rebids 3m via the 2/1 fallback with a minimum, responder bids 4H). OFF;
  needs the opener's non-forcing rebids first (2NT with a stopper, Q-Plus's 2S cue, pass).
* Sprint 167 - BIQ_NEGX_SUPPORT_21: sprint 75 again (support for partner's major before the negative X
  over 1M-(2-level suit)), 2/1 only, three trumps only up to 10 HCP (Q-Plus 2S with AT8.J843.QJT7.Q9,
  X with Q53.AQ52.J86.QT5 11); the 10-count with three trumps now raises (it fell through to a
  reasonless pass). Judge 2/1 +121 (agreement +7, 23 calls); curve 2/1 +0.0073 (SE 0.0070, +9 / -4).
  Sim check 19 calls: it lowered one "Competitive jump raise (4 trumps)" to 2H (Q-Plus 3H) -> that
  reason added to bid_sim._CONVENTIONAL; one 3S became 4S (Q-Plus 3D cue), left. Kept, deployed.
  Test T-negx-support-21.
* Sprint 168 - BIQ_NEGX_SUPPORT_P: the same for Precision (four+ trumps, or three with 9-; Q-Plus 8 /
  10). Judge Precision -13 (agreement +5; biq's X rolls out better, as in sprint 75), curve +0.0017
  (+4 / -3). OFF.
* Sprint 169 - BIQ_CUE_REPLY_ORDER: the doubler's "Reply to cuebid" (partner bid the opening suit
  higher) fired on partner's natural 3C over their strong 1C long before my X of 4H, and "showed"
  their spades at the 5 and 6 level (J87432.AQT.A85.Q; Q-Plus pass). Now the cue must follow my
  double and never shows a major the opponents bid. Judge Precision +46, 2/1 +4 (agreement +3 / +1);
  curve 0. Kept, deployed. Test T-cue-reply-order.
* Sprint 170 - sprint 166's free 2H again with BIQ_FREE_BID_2NT (opener over partner's free 2-level
  suit: no fit, 14-, their suit stopped -> 2NT, Q-Plus 2NT with A93.4.K8764.A842; biq 3m): judge 2/1
  +32 (agreement +10), curve 2/1 -0.0090 (+5 / -6). The losses: responder read 1D-(1S)-2H-(P)-3H as a
  JUMP raise ("16-19 + fit") and bid 4H with 10 HCP. With that fixed too (170b): 2/1 judge +56,
  curve -0.0167 (+6 / -8). FREE_2H_21 stays OFF.
* Sprint 171 - BIQ_JR_ONE_LEVEL (responder's "game after opener's jump-raise" only when I bid the major
  at the one level) + BIQ_FREE_BID_2NT, without the free 2H. Judge 2/1 +36, Precision -13 (agreement
  +4 / +2; the Precision calls themselves net 0, now passing 3H like Q-Plus: AJ4.KT9865.K8.87,
  T.QT983.JT9.KQJ2); curve 2/1 -0.0043 (4 boards, +2 / -2), Precision +0.013 (SE 0.010, +10 / -4).
  Kept (responder's continuation: the curve leads), deployed. Tests T-jr-one-level, T-free-bid-2nt.
* Sprint 172 - BIQ_LEGALIZE_GF_RAISE (live board 160, -19): Precision 1C-(1H)-1S-(4H), the "1C-1S
  raise, trumps agreed (GF)" 2S was illegal and became a pass with AKQ98764.AQ.2.64 (then pass of 4H
  doubled; Q-Plus 6S). An illegal GF raise of partner's suit now bids it at the cheapest legal level up
  to game (4S). Judge 0 / 0, curve 0 (no recorded case). Kept, deployed. Test T-legal-gf-raise.
  Still open: over 5H the raise passes (X or 5S would be better).
* Committed 97637273 (10-22 09:00, sprints 97-173 + the analysis-view work). Offline sprints continue.
* Cost maps 261022d (code 97637273) with EVERY Q-Plus run (adds 261017, 261018 to 2/1 and 261015 /
  261017 / 261018 / 261021 to Precision): 2/1 -738 over 23423 calls, Precision -1356 over 25446. New
  judge = scratchpad judge2.sh / sprint_eval2.sh, base 261022d (deltas read directly per sprint);
  simcheck2.sh runs the sim over a sprint's changed calls.
* Sprint 174 - BIQ_ADV_5M_VALUES: partner's four-level major overcall, their 4-level raise of their
  preempt (3S-4H-4S, mostly probe deals): 5M with three+ trumps and 10+ (Q-Plus 5H with
  A42.AQ9.J862.Q92, K8.J85.AK53.Q974; biq passed: the stale 4M game raise was illegal), 6M with two
  trumps, a seven-card side suit and a void in theirs or 15+ (-.63.KT42.AKJ9654, AT5.A7.AKJT9873.-).
  Judge 2/1 +33 / 3, Precision +84 / 12 (14 better, 1 worse); curve 0. Sim check: it passed 3 of the
  5H (Q-Plus 5H / 6H) -> reasons "with values: " and "seven-card side suit," added to _CONVENTIONAL.
  Kept. Test T-adv-5m-values.
* Sprint 175 - BIQ_ADV_6M_VOID: partner's 5M over their 4-level preempt, their raise to five: a void
  in their suit, two+ trumps and 10+ bid 6M (Q-Plus 6H on 6 / 6 over 4S-5H-5S: -.A72.KQ92.JT7652,
  93.K5432.AKJ543.-; pass without the void or a trump). Judge 2/1 +75 / 7 (all better); curve 0; sim
  keeps all (with 174: 2/1 10 / 10, Precision 12 / 12). Kept. Test T-adv-6m-void.
* Sprint 176 - BIQ_KOKISH_21 (2/1 only): Q-Plus plays 2C-2D-2H as Kokish: responder relays 2S on 9 / 9
  records whatever the hand (biq raised to 4H / 3H: K54.A642.975.872), and opener's 2NT after the relay
  is the big balanced hand (with four or five hearts: AK5.AQT5.AK3.A63, KJ2.AKJ72.AJ.KQ8), answered
  as over 2C-2D-2NT (3D transfer with T.98432.J7.K9542, 3C Stayman with Q.Q964.97642.A92): the step
  replays decide_bid on the auction without 2H-2S. First version: judge 2/1 +40, curve -0.0140 (0 / 5):
  biq's opener took responder's weak 4H after the relay as a slam try (4NT, 6H -1); the strong-2C
  ask's weak-raise exception now treats the relay like the 3C second negative (176b): judge 2/1 +21
  (agreement +11), curve 2/1 -0.0047 (2 boards: 2C-2D-2H-2S-3S-4S stopped short of 6S once). Kept:
  live, Q-Plus's 2H can be a balanced 25 without five hearts, so raising it is a real mismatch.
  Tests T-kokish-21, T-kokish-21-2nt.
* Sprint 177 - BIQ_W2_OVC_GAME7: over their weak two a seven-card major (6+ HCP in it) with 14-17
  bids game at once (Q-Plus 4H on 8 of 10 over 2S: 5.AKJT432.6.AK63, 4.AKQ8762.Q873.A; biq 3H).
  Judge 2/1 +4, Precision +31 (agreement +2 / +4); curve +0.0067 / +0.0067 (2 boards each, +2 / -0).
  Sim lowered one 4H to 3H (Q-Plus 4H) -> "seven-card major, " added to _CONVENTIONAL. Kept. Test
  T-w2-game7.
* Sprint 178 - BIQ_ADV_5M_2T: sprint 174's 5M also with two trumps, two or fewer of their suit and
  8+ (Q-Plus 5H with KT.A6.JT2.T98763 over 2S-4H-4S, 6.T5.AT.AJ976543 over 3S-4H-4S; pass with
  83.J4.AJT9853.93, 6 HCP); the "Pass their 4S" rule no longer catches those 8-9 counts (178b).
  Judge 2/1 +5, Precision +34 (agreement +1 / +2); curve 0. Kept. Test T-adv-5m-2t.
* Sprint 179 - BIQ_P1C_INT_1NT: Precision 1C-(one-level overcall) with 8-11 balanced and a stopper
  answers 1NT, not 2NT (Q-Plus 8 / 8: QJ8.J93.A93.9854 over (1D), K43.QJ65.QJ2.Q97 over (1H)); opener
  reads it like 1C-1NT. Judge Precision IMP 0, agreement +11 (12 calls); curve Precision +0.0013 (+2 /
  -0). Kept. Test T-p1c-int-1nt. Also seen, not done: Q-Plus doubles 1C-(1x) with 5-7 HCP (8 records,
  biq passes) and with 8+ and a five-card minor (biq bids it); 1C-(X) step answers (1D / 1H / XX).
* Sprint 180 - BIQ_OVC_4M_ON: my four-level major overcall of their preempt, their raise to four,
  partner silent: seven+ trumps, one or none of theirs and 15+ (or a void, a five-card side suit and
  13+) bid five (Q-Plus acts on 7 / 7: 5H with -.AQJT872.QT95.AK, 7.AKJ8543.K95.KJ, 4NT twice; pass
  with six trumps or a doubleton of theirs). Judge 2/1 +16 / 4 (all better), Precision +7 (agreement
  +3 / +1); curve 0. Sim passed one 5H -> "-card suit, short in their" added to _CONVENTIONAL.
  Kept. Test T-ovc-4m-on.
* Sprint 181 - BIQ_P2C_ASK_MAJ: Precision 2C, responder with five spades and four hearts and 11+ asks
  with 2D, not 2S (Q-Plus 3 / 3: KQ632.AQ92.A3.Q8, AQ842.KQ52.T75.2). Judge Precision +13 (agreement
  +3); curve 0. Kept. Test T-p2c-ask-maj. Not done: Q-Plus also asks with 8-10 (QJT84.JT87.K4.JT,
  54.KT53.Q975.KQ7) and relays again (2S) after 2C-2D-2H; biq's continuations after 2D are GF.
* Sprint 182 - BIQ_P2D_GAME_LONG: Precision 2D-2NT-3m, responder bids game in the LONGER major with
  four trumps and 12, or with six (Q-Plus 4H with J64.AJ93.J95.AJT, 4S with AKJ987.85.972.86; biq
  "suggested" 3S on three spades). Judge Precision +30 (agreement +3); curve 0. Kept. Test
  T-p2d-game-long.
* Sprint 183 - BIQ_MINOR_PROBE: Precision, partner's three-level raise of my minor in a forcing
  auction: probe 3H / 3S for 3NT instead of the sanity raise to 4m (Q-Plus 3H 5 / 5:
  AJ86.AQ3.J.AJT65 1C-1H-2C-3C). Judge Precision +58 / 21 (agreement +4) but curve -0.032 (SE 0.012,
  +8 / -15): biq's partner doesn't read the probe. OFF; would need the answer side first.
* Looked at, not redone (261022d): Precision 1C-1H-1NT Stayman (= sprint 106, judge IMP 0).
* Sprint 184 - BIQ_DOUBLE_SLAM_SAVE: I bid a six-level suit slam, LHO and partner passed, RHO saved
  at the six level (their first call that high, undoubled): double (Q-Plus 8 / 8 in Precision:
  -.753.AT54.AKQJ84 over 3S-4H-4S-6H-P-P-6S; 6 / 9 in 2/1; biq passed). The first version (any of
  our slams) cost 2/1 agreement -10: right after partner's slam Q-Plus mostly passes. 184b: judge
  2/1 +93 / 14 (agreement 0), Precision +127 / 15 (+1); curve 0; sim keeps all. Kept. Test
  T-dbl-slam-save.
* Commit 6c9cdd0b (10-22 evening, pushed): sprints 174-184.
* Sprint 185 - BIQ_F1NT_MAJOR (found writing the 2/1 guide, ~/Documents/261022): 1M-1NT-2m, responder
  with three of the major and four of the minor jumped to 4m ("4+ fit + game values", K54.Q62.KJ74.Q52
  4D). Now three of opener's major with 10+ comes first: 4M with 12+ (Q-Plus 4S with J87.A973.A6.QJ74,
  biq 4C, -10; 543.K973.A76.AK7, biq 3S), else the 3M jump preference. Judge 2/1 +3 / 3 (agreement +1),
  Precision 0; curve 2/1 +0.0017 (9 boards, +6 / -3), Precision 0; sim keeps all. Kept. Tests
  T-f1nt-major-game, T-f1nt-major-lr. Rules 8ef931a6.
* Live run 261022_qplus_prec_21_biqS (user: "set up a 10 hour run"), prepared 22:01 (10-22): Precision
  first (100 boards), then 2/1; new planner families p1c_int, p2c_maj, f1nt_lr, kokish.
* Checkpoint (10-22, after sprint 183), rules ac2eec57 (sprints 174-182 since commit 97637273;
  uncommitted): judge vs 261022d 2/1 +154 IMP / 32 calls, Precision +199 / 42; curve vs the commit
  (60359511) 2/1 +0.002 (+2 / -2), Precision +0.008 (+4 / -0); vs a2f62b24 (start of 10-21 night)
  2/1 +0.046, Precision +0.085.
* Live run 261021_qplus_21_prec_biqS ended 08:30 (10-22) on schedule, 200 boards, no errors, code swapped
  in after each accepted sprint: 2/1 150 boards -212 IMP (-1.41 / bd, SE 0.55; earlier runs -2.4),
  Precision 50 boards -180 (-3.60 / bd, SE 0.95; earlier -2.8). Worst Precision boards: 160 (fixed,
  sprint 172), 186, 185 (opener's competitive 4NT read as RKC, not done).
* Checkpoint 08:10 (10-22), code 60359511 (sprints 97-173; off: 136 / 138 / 145 / 146b / 150 / 151 /
  154-156 / 159 / 161 / 166 / 168 / 170; uncommitted, all deployed): curve vs a2f62b24 (start of the
  night) 2/1 +0.044 IMP/bd (SE 0.019, +52 / -29), Precision +0.077 (SE 0.022, +74 / -26); vs 0bdc169c
  (commit c35379d5) 2/1 +0.143 (SE 0.034), Precision +0.180 (SE 0.035).
* Sprint 173 - BIQ_MINORS_4NT_LOW: partner's direct 4NT over their 2- or 3-level major (our side's
  first call) is for the minors, like over 4M (Q-Plus 5C with AQJ92.9863.Q.965 over (2H)-4NT; biq
  passed). Judge Precision agreement +1, IMP 0; curve 0. Kept, deployed. Test T-4nt-minors-low.
  Not done: live board 185, 1D-(2S)-X-(3S)-P-(P)-X-(P)-4NT by the opener (5-5 minors): biq answered
  RKC (5H, -300); no records of that 4NT.
* Checkpoint 07:20 (10-22), code 4a09a0bc (rules = cf29cfc0; sprints 97-167, off: 136 / 138 / 145 /
  146b / 150 / 151 / 154-156 / 159 / 161 / 166 / 168; uncommitted, all deployed): curve vs a2f62b24
  (start of the night) 2/1 +0.049 IMP/bd (SE 0.018, +50 / -27), Precision +0.064 (SE 0.020, +64 /
  -22); vs 0bdc169c (commit c35379d5) 2/1 +0.147 (SE 0.034), Precision +0.167 (SE 0.034); since the
  03:55 checkpoint (aeffc141) 2/1 +0.011, Precision +0.004.
* Live Precision reasons (1041 boards, all runs): "LAW raise of partner's preempt" -6.7 / board over
  52, but Q-Plus makes the same raise on every record (selection: preempt boards are bad boards).
* Looked at and skipped (261022b): Lebensohl - Q-Plus plays slow shows (direct 3NT denies a stopper:
  KJ.T862.KJT42.J5 over 2C), biq fast shows; the final contract is the same 3NT and the opener passes
  either way, the positions after 2NT-3C exist only from Q-Plus's relay. 1m-(1S) with five hearts
  (Q-Plus 2H vs X split). Precision 5-3-3-2 AK-major 1M opening (= sprint 129).
* Looked at and skipped (261021i): 1NT-(Multi-Landy 2C/2D) responder X (= sprint 42, curve lost);
  defence to their strong 1C (Q-Plus overcalls weak 5-card suits only 3 / 6; jumps with KQJxx /
  6-card 8-10 cost 0); 7-card-major game jump in competition (Q-Plus 5 / 17); illegal-call legaliser
  leftovers (127 mixed spots); Stayman with a GF minor (= sprint 114).
* Not done (yet): 1x-(2NT unusual): responder falls through to the uncontested code (Bergen 3M /
  illegal 2-level answers passed); Q-Plus's cue meanings there are inconsistent in the records.
* Not done (needs opener work first): 1S-(2m) with five+ hearts and 8-10, Q-Plus bids 2H (6 / 6,
  biq X); biq's opener reads that 2H as a 2/1 game force (rebids 2S without raising three hearts,
  responder then drives to game), so copying the call alone would overbid.
* Cost maps 261021g (code de66ea57): Precision -777 (10185 / 13268).
* Sim check sprints 111-117 (vs 261021f): 2/1 kept 104 / 107, Precision 30 / 31. The sim passed two
  of sprint 113's 1S over the double (Q-Plus 1S): reasons added to _CONVENTIONAL; its third
  override (pass instead of 3NT over 1H-(1S) with Q9532) matches Q-Plus.
* Sim check sprints 97-110 (calls changed vs 261021e, scan --sim --only): 2/1 kept 85 / 90,
  Precision 40 / 44. The sim overrode WJO_SHAPE passes (1D / 2C), Precision's "Pass the raise: 4
  trumps" (4S / 3H) and the 5-5 escape (4S), all away from Q-Plus's call: those reasons added to
  bid_sim._CONVENTIONAL (verified with the sim on).

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
* Partner's 4NT reply after strong 2C (10-18, uncommitted): those passes came from auction_context's
  Gate 2 (opener rebid NT -> 4NT quantitative; only strong 1C was exempt), then "Partner's NT rebid:
  no game or slam move". `_suit_at_4_after_strong_2c_nt` (BIQ_STRONG_2C_4NT_RKC): an alerted 2C, the
  NT rebid, then a 4-level suit by our side -> 4NT asks keycards (Q-Plus answers 5C in
  2C-2D-2H-2S-2NT-3D-3H-4C-4D-4H-4NT). Recorded calls changed: 0 of 17,420 2/1 and 0 of 10,924 Precision
  (only partner's model moves). The 13 strong-2C ask positions re-scored: rules +104 (SE 27), sim on +100
  (SE 26), vs +109 / +105; the 3 former passes now reach slam (+15, +8, -28: 2C-...-4H-4S-4NT picks
  spades; Q-Plus's Kokish 2H/2S/2NT prefix, which biq doesn't play). T-2c-4nt, 265 checks.
  Live run 261017 s2c_slam (Q-Plus answers biq's 4NT there): -62 IMP / 17 boards; see its report.
* Queen ask (10-18, uncommitted): biq never answered partner's next step after its 5C/5D RKC answer
  and passed it (live 261017 bd 68: 2C-2NT-4H-4NT-5C-5D played in 5D, -15). `_answer_queen_ask`
  (BIQ_QUEEN_ASK_ANSWER), Q-Plus's way from 17 recorded calls: no queen 5 trump; queen with hearts
  5S, with spades 5NT (5S with 0 keycards); majors only, real queen only. Rules: 2/1 +17 / 1,
  Precision +42 / 5 (SE 26), all 6 now = Q-Plus, sim on keeps them. Tests 261017-68, T-qask-5nt (267).
  Still open from s2c_slam: my 2C's later rounds hit the stale-rebid illegal -> pass in other shapes
  (bd 62 2C-(4C)-4H pass, 13 tricks; bd 65 after the 4NT-5NT answer) and "2C catch-all 3NT" with a
  4-card fit for partner's 3S (bd 48).
* Next: unassuming cue-bid limit raise (-106/22);
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
