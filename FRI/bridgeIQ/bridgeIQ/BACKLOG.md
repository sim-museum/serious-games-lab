# biq — Scrum backlog

Running list of not-yet-started work. Newest items at the top of their
section. Move an item to a STATUS doc under `docs/` when it's picked up.

## Backlog

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
