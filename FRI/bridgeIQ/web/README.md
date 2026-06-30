# BridgeIQ — single-file browser edition

`bridgeIQ.html` is a complete transpilation of the PyQt6 BridgeIQ desktop
program into **one self-contained HTML file** that runs in any modern browser
with no server, no build step and no external dependencies. Just open the file.

```
open web/bridgeIQ.html          # or double-click it / drag into a browser tab
```

## What's inside (all functionality, no demo cut-downs)

| Desktop subsystem | Browser port |
|---|---|
| `backend/models.py` | Suit/Rank/Seat/Card/Hand/Bid/Contract/Trick/BoardState (exact port) |
| `backend/scoring.py` | contract scoring, IMP table, matchpoints, full **Rubber** scorecard |
| `backend/pavlicek.py` | BigInt combinatorial deal numbering + base-72 deal IDs (round-trip) |
| `backend/native_bidder.py` | rule-based bidder for **SAYC, 2/1 GF, Standard Acol, Standard French, Precision90M** — openings, responses, rebids, competitive bidding, slam (RKC 1430 / Gerber / quantitative), sanity wrapper, `why=` explanations on every bid |
| `backend/native_lead.py` + `signals.py` + `nopeek.py` | opening leads (4th-best / top-of-sequence / ace-from-AK …), 2nd-hand-low / 3rd-hand-high / cover-honours / win-cheaply, discard signals |
| `libdds.so` (native) | **a from-scratch JavaScript double-dummy solver** — alpha-beta + MTD narrow-window search + trick-boundary transposition table. Exact for endgames (used for card play & claim verification); node-bounded so it never stalls the tab |
| `ui/main_window.py` + all `ui/dialogs/*` | full menubar (File / Configuration / Deal / Own Deals / View / Extras / Network / Help), table view, bidding box, auction grid, teaching explainer, every dialog |

### Features
- **Play**: bid by clicking buttons or typing (`p`, `x`, `1`–`7` then `c d h s n`); play cards by clicking; follow-suit enforced.
- **Modes**: 4-Player (you sit South), 1-Player, All-Computer, **MiniBridge** (no auction).
- **Scoring**: Teams (IMP), Pairs (matchpoints), **Rubber**, Chicago.
- **Analysis**: Double-Dummy trick table, Bid Simulation (Monte-Carlo make %), Interpret Auction, hand log, IMP / probability / scoring reference tables.
- **Teaching**: click any bid to see the rule that fired; the engine narrates each card; Hint asks the engine.
- **Import / export**: PBN and BBO LIN deal files in; PBN, HTML, JSON session out; Pavlicek deal codes; print.
- **Persistence**: match + config auto-saved to `localStorage` (gracefully degrades to File ▸ Save when storage is unavailable).

## Engine notes
- Card play uses **rule-based heuristics for the early tricks and exact double-dummy
  for the endgame** (last ~6 tricks), which is the browser-feasible balance — a full
  52-card exact solve is too slow for plain JS, so it is reserved for small positions
  (and the DD-analysis dialog marks `≈` where a full-deal cell is too large to solve
  exactly in the time budget).
- The bidder is competent and legal, not expert: validated at **0 illegal bids and 0
  runaway auctions across 300+ deals × all 5 systems**, with sensible auctions and a
  full explanation string on every call.

## Tested
End-to-end (deal → bid → play → score) verified headless via jsdom: full-deal
play with 0 exceptions, all 40 dialogs open/close cleanly, human bid+play path,
Pavlicek round-trip, worst single card decision **37 ms**.
