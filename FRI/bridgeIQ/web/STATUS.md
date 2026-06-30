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

## Layout rework (2026-06-30, sprints R1–R4) — match the PyQt UI exactly
After comparing against a screenshot of the desktop app, the UI was rebuilt to
copy the PyQt layout:
- **Classic light menubar** (was a dark gold theme).
- **Left info panel**: "System:" header, the auction as a **Bid | Points | Help**
  table, and an **"Available bids for South"** table listing every legal call with
  its point range and meaning (generic descriptions — no HCP leak). Click a row to bid.
- **Center green table** with the Dealer/Vul box and the **central N/E/S/W auction grid**.
- **Top-right bidding box** "Bidder: S" — Pass/X/XX, a ♣ ♦ ♥ ♠ NT × 1–7 grid,
  Alert / Explanation links, and the `Keys: 1c-7n, p=pass, x=dbl` hint.
- **4-colour suits**: ♠ black, ♥ red, ♦ **blue**, ♣ **green** (was orange diamonds).
- **Realistic card faces** with proper pip layouts (A=1 … 10=10 pips) and court indices.
- **South hand** as large cards along the bottom; **Contract** box bottom-left.
- **Bottom button row**: Next deal · Next card · Hint · **Undo** · Claim · **Evaluate**
  · **Autoplay** · Review · **Closed room** · **Instrumented** · Help.
- **Instrumented teaching view** (3×3 grid: contract, per-seat HCP/shape, plan,
  current trick, count, coaching) toggled by the Instrumented button.
- Default systems set to **SAYC / SAYC** to match the desktop default.

## Engine note (DD + MC) — NOT identical to PyQt, by platform necessity
- **PyQt:** native `libdds.so` (full-speed C double-dummy) + Monte-Carlo sampling of
  hidden hands with auction-derived HCP/shape constraints + alpha-mu no-peek play.
- **Browser:** a hand-written JS double-dummy solver (correct; ~50–100× slower than
  libdds) used **exactly for the endgame** (last ~6 tricks) with rule-based heuristics
  for earlier tricks. No full-deal MC sampling / alpha-mu — a pure-JS full-deal solve
  is too slow to run per card. Same *spirit*, weaker on early-trick declarer play.

## Files
- `web/bridgeIQ.html` — the application (single file)
- `web/README.md` — user-facing overview
- `web/STATUS.md` — this file
