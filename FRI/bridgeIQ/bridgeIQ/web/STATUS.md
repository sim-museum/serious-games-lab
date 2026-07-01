# bridgeIQ web-port — STATUS (paused 2026-06-20)

Paused awaiting more token budget. This file is the resume point for the full
transpile of bridgeIQ to a single self-contained `biq.html`.

## The goal (user's words)
A free, **full-strength** bridgeIQ that runs as one stand-alone `biq.html` in a
browser — **everything** except network / external closed-room. A faithful
transpile of the whole Python engine (~16.5k lines), **not** an approximation —
"even the Bayesian shape and honours estimator, and the bidding simulator …
Everything — that's what makes bridgeIQ great."

## How the build works (already set up)
- Source of truth: `web/src/engine/*.js` (faithful module transpiles) + the app
  UI/CSS inside `biq.html`.
- `node web/build.js` injects every `web/src/engine/*.js` into `biq.html`
  between the `/*ENGINE-START*/ … /*ENGINE-END*/` markers. `biq.html` is the
  shippable single file (open it directly in a browser).
- `cd web && npm test` runs the cross-validation suite (node vs the Python in
  `../../venv/bin/python`, run from the `bridgeIQ/` dir so `backend` imports).
- Module load order is fixed in `web/build.js` `ORDER[]`.
- Engine modules publish onto `window.BIQ` (browser) and `module.exports` (node
  tests). The app calls them via `BIQ.*`.

## DONE (Phase 1) — committed
- `web/build.js`, `web/package.json`, `web/PORT_ROADMAP.md`.
- `web/src/engine/scoring.js` — faithful transpile of `backend/scoring.py`
  (`calculate_contract_score` + `diff_to_imps` + IMP table). **EXACT parity vs
  Python** over 2940 contract cases + IMP table (`web/test/scoring.test.js`).
  Wired into the app (`scoreContract` delegates to `BIQ.contractScore`).
- `web/src/engine/bayes.js` — the **Bayesian shape & honour estimator**
  (transpile of `teaching_view.bayes_distribution`): MC posterior over hidden
  hands honouring voids / suit-length caps / HCP windows. Invariants +
  convergence validated (`web/test/bayes.test.js`; RNG can't byte-match Python
  so we assert the algorithm's invariants). Wired into the instrument view:
  Missing-honours (colour-coded %), Likely-shape, per-suit ≈likely-count +
  honour hints.
- `biq.html` itself: a fully-playable standalone (deal/bid/play/score +
  instrumented view + pokerIQ theme), all 5 systems selectable. Bidding +
  cardplay are still the **interim standalone engines** (competent SAYC-family
  bidder + heuristic cardplay) — to be REPLACED by the faithful ports below.

Validation snapshot (all green):
- `node web/test/scoring.test.js` → SCORING PARITY OK
- `node web/test/bayes.test.js` → BAYES ESTIMATOR INVARIANTS OK
- DOM-shim drive of the app across all 5 systems → no runtime errors.

## TO DO (resume here) — see web/PORT_ROADMAP.md for the table
Port each module to `web/src/engine/`, add a `web/test/<m>.test.js` that
cross-checks against the Python, then `node web/build.js` and wire into the app.

Order (smallest/foundational → biggest):
1. `models.py` (793) → `engine/models.js` — Card/Hand/Suit/Rank, hcp, lengths,
   Pavlicek deal number. (Helpers are currently inline in the app; consolidate.)
2. `auction_inference.py` (1674) → `engine/auction.js` — `SeatConstraints` +
   `infer_constraints`. Validate per-seat (hcp_min/max, suit_len) vs Python on a
   deal+auction corpus. Then FEED these constraints into `bayes.js`
   (`hcp`/`suitMin`/`suitMax`/`fixedLen`/`fixedHcp` inputs already supported) so
   the estimator tightens like the desktop.
3. `bidding_systems.py` (647) → `engine/systems.js` — the 7 system spec tables.
4. **`native_bidder.py` (8350) → `engine/bidder.js`** — THE LONG POLE. Split by
   function group (opening / response / opener-rebid / competition / slam /
   conventions) + per-system spec lookups. Cross-validate **bid-for-bid** vs the
   Python `NativeBiddingEngine` over a seeded deal corpus, per system. Replace
   the app's interim `decideBid`.
5. `native_lead.py` (395) → `engine/lead.js` — opening leads, vs Python.
6. DDS: write a JS double-dummy solver (alpha-beta + transposition table),
   validate trick counts vs `backend/dds.py`/libdds on sample deals →
   `engine/dds.js`.
7. `nopeek.py` (600) → `engine/play.js` — alpha-mu no-peek cardplay on belief
   samples (uses bayes.js sampler + dds.js). Replace the app's heuristic
   `chooseCard`. Validate card choice vs Python on saved positions.
8. `signals.py`/`signal_read.py` (281) → `engine/signals.js` — defensive
   carding emit/read; wire into the instrument Coaching/Signals panel.
9. Full instrumented view (`teaching_view.py`, 2626): port the remaining panels
   (hold-up/Rule-of-7, danger hand + knock-out, squeeze types + rectified
   count, finesse odds, entries/transportation, suit-pref honesty, Smith/trump
   echo). A subset is already live (Known/Other, losers, counting, Bayes).
10. **Bidding simulator** — candidate-bid evaluation (the desktop's bid
    simulation): for each legal call, sample layouts (bayes.js) + score the
    likely contract (DDS), rank the calls. New UI panel.

## Gotchas / notes
- Cross-validation harness pattern: `web/test/*.test.js` shells out to
  `../../venv/bin/python -c "<py>"` with `cwd` = `bridgeIQ/` and JSON over
  stdin/stdout. Skips gracefully if Python is unavailable.
- Bayesian sampler is rejection-based: fully-determined / very tight scenarios
  can return `null` (both ports) → caller falls back to vacant-space. Use
  mid-hand-sized scenarios in tests.
- Suit/rank order matches Python: Suit S=0,H=1,D=2,C=3,NT=4; Rank A high.
- biq.html is git-tracked and regenerated by build.js — after editing engine
  modules always re-run `node web/build.js` before committing.
- Pre-existing uncommitted WIP in the repo (table_view.py etc.) is NOT part of
  this work — leave it unstaged.
