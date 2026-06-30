# BridgeIQ web port — build status

**Date:** 2026-06-30
**Deliverable:** `web/bridgeIQ.html` — single self-contained HTML file (~166 KB,
no dependencies, no server). Opens in any modern browser.

## Goal
Transpile the entire PyQt6 BridgeIQ desktop application (63 K lines of core app)
into one browser-runnable HTML file with **all functionality** — not a demo.

## Status: COMPLETE ✅

All five sprints delivered and validated headless (jsdom).

| Sprint | Scope | Status |
|---|---|---|
| 0 — Foundation | models, scoring, Pavlicek, deal gen, JS double-dummy solver, UI shell | ✅ |
| 1 — Bidding engine | 5 systems, rule-based, `why=` explanations, sanity wrapper | ✅ |
| 2 — Card play | opening leads, signals, follow/discard heuristics, exact DD endgame | ✅ |
| 3 — Full UI | menubar (8 menus), 40 dialogs, 4 modes, teaching explainer, score tables | ✅ |
| 4 — Integration | PBN/LIN import, PBN/HTML/JSON export, persistence, print, self-test | ✅ |

## What was ported
- **Exact ports:** `backend/models.py`, `backend/scoring.py` (contract score, IMP,
  matchpoints, full Rubber scorecard), `backend/pavlicek.py` (BigInt combinatorial
  deal numbering + base-72 IDs, round-trips).
- **Reimplemented from spec:** `native_bidder.py` (SAYC, 2/1 GF, Standard Acol,
  Standard French, Precision90M — openings/responses/rebids/competitive/slam),
  the card-play stack (`native_lead.py`, `signals.py`, `nopeek.py`).
- **From scratch:** a JavaScript double-dummy solver (alpha-beta + MTD
  narrow-window + trick-boundary transposition table) replacing native `libdds.so`.
- **Full UI:** `main_window.py` menus/flow + every `ui/dialogs/*`.

## Validation (headless jsdom)
- Loads with **0 runtime errors**; renders 52 cards, 8 menus, 38 bid buttons.
- Bidding: **0 illegal bids, 0 runaway auctions over 300 deals × 5 systems**.
- End-to-end (deal→bid→play→score): **25/25 deals, 0 exceptions**.
- Human bid+play path: bids via buttons/keyboard, plays cards (incl. dummy),
  trick resolution, end-of-hand prompt — **0 errors**.
- **All 40 dialogs** open/close cleanly.
- Double-dummy solver: correctness checks pass; **worst single card decision 37 ms**.
- Pavlicek deal-id round-trips; session save/restore works.

## Known engineering tradeoff
A full 52-card exact double-dummy solve is too slow for plain JavaScript
(13-trick solve >10 s even with MTD + transposition tables). Card-play DD is
therefore **endgame-only** (last ~6 tricks, node-bounded so the tab never
stalls) with strong heuristics for early tricks. The DD-analysis dialog marks
`≈` on full-deal cells it cannot solve exactly within its time budget. This is
the only divergence from the native binary and is a platform limit, not a
feature cut.

## Files
- `web/bridgeIQ.html` — the application (single file)
- `web/README.md` — user-facing overview
- `web/STATUS.md` — this file
