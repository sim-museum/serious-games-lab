# biq — Scrum backlog

Running list of not-yet-started work. Newest items at the top of their
section. Move an item to a STATUS doc under `docs/` when it's picked up.

## Backlog

- **[DONE 2026-09-06 14:40, Fable 5.1] Defensive signalling overrides winning the trick (PO, 2026-09-06).** Cause: `nopeek._follow` judged "our side is winning" from partner's card being the CURRENT winner, in third hand too, where fourth hand (declarer) has not played -- so biq signalled a low spot and declarer won cheaply. Fix: `_unseen_higher` (any card above X still unplayed and not in a hand this no-peek board exposes); in third hand the free signal is kept only when partner's card is a SURE winner, otherwise biq plays the cheapest sure winner ("Wins the trick") or third-hand-high (bottom of its top sequence). Gate `test_third_hand_wins.py`: K over dummy's 2 with A/Q out (plays K, not a signal), A takes the trick (reason "Wins the trick"), control with partner's sure K (still a Signal). 6/6; existing test scripts unchanged. PO, verbatim: "bridgeIQ
  was trained using Q-Plus Bridge 17.1 as a sparring partner, but I added signalling after the
  training; unfortunately bridgeIQ now signals on defense even when it could win a trick instead,
  which spoils its cardplay." Expected order of business on defence: if a card WINS the trick (or
  is the only card that beats the current winner), play it; signal (attitude/count/suit-preference)
  only with the cards that cannot win. Acceptance: a gate with authored defensive positions where
  biq holds the winning card and a signalling alternative, asserting it wins the trick; plus the
  `_why` reason showing "wins trick" rather than a signal tag. Regression: the existing signalling
  gates still pass when no winning card is available.

- **Surface reasons in the Q-NET server play loop too.** The interactive GUI
  now shows biq's actual per-card reason on click (nopeek records a `_why`
  tag/reason; `_on_engine_card` stores it keyed by board+card; the popup shows
  it). The Q-NET server/client play loops (`tools/biq_qnet_server.py`,
  `tools/biq_qnet_client.py`) call `nopeek.decide()` WITHOUT an `explain` sink,
  so they don't capture the reason. Thread an `explain={}` through those call
  sites and expose the reason over the wire / in the server's log so a
  networked opponent (or a replay) can see why biq played each card.
