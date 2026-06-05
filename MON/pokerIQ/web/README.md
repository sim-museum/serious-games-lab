# PokerIQ — single-file web port

A self-contained `pokerIQ.html` (no server, no dependencies, no network) that
ports the PyQt6 desktop trainer to the browser. Open the file and play.

## Build

```bash
node build.js            # -> ../pokerIQ.html  (inlines src/* into one file)
npm test                 # engine + UI + built-file tests (needs dev jsdom)
```

`src/` holds the source modules; `build.js` concatenates them (in dependency
order) into one HTML file with inline `<style>`/`<script>` and verifies there
are zero external references.

## Architecture (`src/`)

| Module | Role | Ported from |
|---|---|---|
| `engine.js` | 7-card evaluator + Monte-Carlo equity | `eval7` C-ext, `calc_equity_*`, `poker_iq/evaluator.py` |
| `game.js` | betting loop, **true side pots**, showdown | `TextModeGame`, `Player` |
| `bots.js` | 9 styles + 2 equity bots | `Player.get_bot_action`, `poker_iq/bots/*` |
| `analytics.js` | board texture, sklansky, nash, EV, session/opponent stats | `classify_board`, `sklansky_distance`, `SessionStats`, `OpponentModel`, … |
| `ui.js` | table view + controller (paced turns) | `PokerWindow`, `PokerTableWidget`, custom widgets |
| `trainers.js` | 8 study modals | `AKQGameDialog`, `JamOrFoldTrainer`, `VarianceDashboard`, … |
| `main.js` | boot + menu wiring + dropped-feature notices | `run_gui_mode` |

## Verification

- **Evaluator**: 20,000 random showdowns agree with `eval7`, 0 mismatches
  (`../prototype/`).
- **Equity**: within 0.6% of `eval7` `calc_equity_hidden` across 8 scenarios.
- **Engine**: 4,000 simulated hands (545 all-ins) — perfect chip conservation,
  side-pot math asserted.
- **Built file**: loaded in jsdom exactly as a browser would, boots and plays
  hands through real button clicks; all 8 trainers + stats open. 17/17.

## Parity status vs the desktop app

**Ported:** 6-max NL Hold'em engine, all 9 bot styles + 2 equity bots, live
equity / pot-odds / EV advisor, board-texture reads, opponent tells (ranges,
leaks, levels-of-thinking), god mode, session + lifetime stats (localStorage),
and 8 trainers (AKQ, Jam-or-Fold, Indifference, MTT/ICM, Variance·Edge·Bankroll,
Calibration, Mindset, Range-narrowing).

**Training mode (Theory of Mind screen)** — a top-bar Training toggle swaps the
table for the full ToM analysis screen (`tomlogic.js` + `tom.js`): no-peek
equity-vs-estimated-ranges, the Phil Gordon "Little Green Book" advisor (hand
tiers, combo nicknames, two-question script + four setup questions), per-opponent
13×13 range grids with board-connection highlighting + betting-history reads, the
Hero pot-commitment / SPR panel with a 4×13 outs board, Outs / Scare-cards, a
range-mode radio (opps weak / neutral / strong), EV-tagged action buttons, and
the 3×3 decision dashboard (MDF, bluff-catch, range advantage, reverse-implied,
Nash push, realized equity, VPIP/PFR/AGF, tilt, risk-of-ruin).

**Intentionally dropped** (cannot run in a sandboxed single file):
- **LAN multiplayer** — browsers can't open raw TCP sockets.
- **Claude hand-analysis** — relied on shelling out to the `claude` CLI.
- **TexasSolver** — 86 MB bundled C++ binary, never invoked by the app anyway.

Both dropped features are surfaced honestly in the in-app **?** dialog rather
than failing silently.

## Known gaps / polish backlog

- Hand-history replay browser and per-hand-class P&L table are not yet ported.
- Bot turn pacing is a fixed delay; no chip-movement animation.
- Mobile layout is functional but the felt oval is tuned for desktop widths.
