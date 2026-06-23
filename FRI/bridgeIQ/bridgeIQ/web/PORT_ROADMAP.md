# bridgeIQ → single-file web port (full transpile)

Goal: a free, full-strength bridgeIQ that runs as one self-contained `biq.html`
in any browser — **everything** except network / external closed-room. This is
a faithful transpile of the ~16.5k-line Python engine, ported module-by-module,
each **cross-validated against the Python** so it's true parity, not an
approximation.

## How it's built
- Source of truth: `web/src/engine/*.js` (faithful module transpiles) + the app
  UI in `biq.html`.
- `node web/build.js` injects the engine modules into `biq.html` between the
  `/*ENGINE-START*/ … /*ENGINE-END*/` markers. `biq.html` stays the shippable
  single file.
- `npm test` (in `web/`) runs the cross-validation tests against the Python.

## Status

| Module (Python) | Lines | JS | Validation | State |
|---|---|---|---|---|
| `scoring.py` | 886 | `engine/scoring.js` | exact vs Python, 2940 contracts + IMP table | ✅ done |
| Bayesian shape/honour estimator (`teaching_view.bayes_distribution`, `honour_placement`) | ~200 | `engine/bayes.js` | invariants + convergence (RNG can't byte-match) | ✅ done |
| `models.py` (Card/Hand/Suit/Rank, hcp, pavlicek deal#) | 793 | `engine/models.js` | — | ⏳ partial (helpers inline in app) |
| `auction_inference.py` (SeatConstraints + infer_constraints) | 1674 | `engine/auction.js` | per-seat constraints vs Python on N deals | ⬜ next |
| `bidding_systems.py` (7 system specs) | 647 | `engine/systems.js` | — | ⬜ |
| `native_bidder.py` (the 7-system bidder — the long pole) | 8350 | `engine/bidder.js` | bid-for-bid vs Python on a deal corpus | ⬜ |
| `native_lead.py` (opening leads) | 395 | `engine/lead.js` | vs Python | ⬜ |
| `dds.py` + a JS double-dummy solver | 282 + new | `engine/dds.js` | DD trick count vs libdds on deals | ⬜ |
| `nopeek.py` (alpha-mu no-peek cardplay) | 600 | `engine/play.js` | card choice vs Python on positions | ⬜ |
| `signals.py` / `signal_read.py` (defensive carding) | 281 | `engine/signals.js` | vs Python | ⬜ |
| `teaching_view.py` (full instrumented view) | 2626 | app/engine | feature-by-feature | ⏳ subset live (Known/Other, losers, counting, **Bayes**) |
| Bidding simulator (candidate-bid evaluation) | — | app | — | ⬜ |

## Phase plan
1. **Foundation + estimator** (done): pipeline, `scoring.js`, the Bayesian
   estimator wired into the instrument view.
2. **Auction inference + systems**: port `auction_inference.js` + the 7 system
   specs; feed real constraints into the Bayesian estimator (tighter shapes).
3. **The bidder**: port `native_bidder.js` (biggest piece) — likely split by
   function group (opening / response / rebid / competition / slam) and the
   per-system spec tables; cross-validate bid-for-bid against the Python over a
   deal corpus. Wire in `native_lead.js`.
4. **Cardplay**: a JS double-dummy solver (alpha-beta + transposition table),
   validated vs libdds; then the no-peek alpha-mu engine on belief samples.
5. **Full instrumented view + bidding simulator**: port the remaining teaching
   panels (signals, hold-up, danger hand, squeeze types, finesse odds, entries)
   and the candidate-bid simulator.

Until a module is ported, `biq.html` uses an interim standalone engine for that
part (competent SAYC-family bidding + heuristic cardplay) so the app is fully
playable at every step.
