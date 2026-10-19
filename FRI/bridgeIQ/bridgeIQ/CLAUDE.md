# biq — Claude Code project notes

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
