# biq — Scrum backlog

Running list of not-yet-started work. Newest items at the top of their
section. Move an item to a STATUS doc under `docs/` when it's picked up.

## Backlog

- **Fixed computational effort per decision, not a fixed time.** biq's
  strength must not depend on machine load or CPU speed. Today several
  searches stop on a wall clock:
  `alphamu.py` (deadline = BIQ_AMU_BUDGET 12 s per card, a third of it
  in one phase; used for defence and the alpha-mu declarer),
  `defender_search.py` (time_budget 5 s), and the safety caps in
  `bid_sim.py` (3 x BIQ_BID_SIM_BUDGET 6 s) and `lead_sim.py`
  (3 x 8 s). Evidence it matters: replaying boards 185-369 of run
  261007 with unchanged defence code, biq's defence gave up 92 DD tricks
  vs 82 the first time (-64 IMP); on 2026-10-09 a benchmark pushed the
  load average to 38 during the 2/1 run. Replace each clock with a
  count (sampled worlds, search nodes / DDS calls, sampler tries),
  calibrated so that an idle machine plays as strongly as now; keep a
  wall clock only as a hang guard at a large multiple, and log when it
  fires. Same counts on any machine = same cards, which also makes
  replays and the agreement benchmark (`tools/qplus_agreement.py`)
  exactly repeatable. Check: the same benchmark sample twice, once
  idle and once under load, gives identical decisions.

- **2/1 match program vs Q-Plus (decided 2026-10-09).** biq's two main
  systems are Precision (primary, also the beginner track) and 2/1 game
  forcing (`TwoOverOne`, Q-Plus `A-2-1-A.RCE`); SAYC/Acol/French stay
  supported but are not a focus. 2/1 has had no live Q-Plus run yet. Steps:
  set the three Q-Plus windows to 2/1 (convention-card / B-PREFER.CFG
  check), run the TM with `--system TwoOverOne --remote N,E,W`, mine the
  bidding divergences as was done for Precision, and add 2/1 par A/Bs next
  to SAYC/Precision in the bidder test runs. Alternate Precision and 2/1
  matches after that.

- **Declarer play after the Monte-Carlo switch (2026-10-09).** decl1
  replay now 987 tricks vs Q-Plus 1005 (alpha-mu was 945). Belief-level
  diagnostic (scratch `decl_diag.py`, 60 samples per costly card):
  "search" losses (card worse on average under biq's own beliefs)
  Monte-Carlo 10 cards / 13 tr, Q-Plus 25 / 28, alpha-mu 62 / 72; "luck"
  losses (card best on average, lost on the actual layout) Monte-Carlo
  78 / 88, Q-Plus 47 / 51. The diagnostic uses biq's sampler, so it
  flatters Monte-Carlo; the remaining gap is in the BELIEFS (what the
  sampler thinks the defenders hold, and DD leaves that assume the
  defence never misguesses), not the search. Next: re-weight samples by
  the defenders' plays so far (signals, which honour they played), and
  measure in the next Q-Plus TM run (play IMPs vs the -21 / -2.26/bd
  baseline).
  Also: does the Monte-Carlo idea help biq's DEFENCE (alpha-mu there was
  an A/B win earlier, so test before switching)?

- **Probe Q-Plus's second-hand play in SUIT contracts.** The 2026-10-05/07
  probes saw Q-Plus in second seat only in 3NT (declarer establishing clubs):
  with a lone A or K it ducks almost always (A-x 30%, A-x-x 16%, longer or a
  lone K ~never), with A-K it always rises. Copying that everywhere
  (`BIQ_SECOND_LOW`, off) won on those positions but lost on 695 random
  deals, nearly all in suit contracts (96 diverged deals, -0.22 tr; NT 40,
  -0.03 tr, -26 IMP). Design a suit-contract family for `tools/qplus_probe.py`
  (e.g. 4S/4H, declarer or dummy leads a low side-suit card toward K-x / K-Q-x
  / Q-x, Q-Plus holds A-x, A-x-x, K-x, K-x-x behind it; also trumps), run it
  through `biq_bluechip_tm.py --script`, and fit Q-Plus's rule. Then try that
  rule (NT + suit) as the default per the "Q-Plus's way unless strong
  evidence against" policy, verified with the scratchpad paired no-peek A/B
  (`secondlow_ab.py`: same deal played twice, all four seats no-peek).

- **"How often does biq look wacky?" audit.** Go through the recorded Q-Plus
  matches (`tools/runs/results/*.qss`, Q-Plus `DATA/LOG/*.bdl`) and list
  every biq call and card that differs from BOTH Q-Plus (closed room / same
  spot) AND textbook practice, and costs a lot (e.g. 5+ IMPs, or 2+
  double-dummy tricks). Output: a count per match / per 100 deals, split into
  bidding and card play, plus the worst examples with the full auction or
  trick for a bridge player to judge. Builds on `tools/qplus_auction_mine.py
  --live` (first auction divergence) and `tools/play_audit.py` (card-by-card
  DD cost); "textbook practice" needs a check of its own (SAYC rules for
  calls; standard carding / second-hand-low / cover-an-honour etc. for
  cards). Gives a real measure in place of today's impression (a few visible
  oddities per 64-deal match).

- **Surface reasons in the Q-NET server play loop too.** The interactive GUI
  now shows biq's actual per-card reason on click (nopeek records a `_why`
  tag/reason; `_on_engine_card` stores it keyed by board+card; the popup shows
  it). The Q-NET server/client play loops (`tools/biq_qnet_server.py`,
  `tools/biq_qnet_client.py`) call `nopeek.decide()` WITHOUT an `explain` sink,
  so they don't capture the reason. Thread an `explain={}` through those call
  sites and expose the reason over the wire / in the server's log so a
  networked opponent (or a replay) can see why biq played each card.
