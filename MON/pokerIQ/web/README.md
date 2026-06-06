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

**Hand Summary** — three views. *Analysis* (default): "Hand #N Analysis" with
every player's hole cards + a category (offsuit junk / suited ace / big slick …),
each human's "held" line, and per-street board + your equity + opponents'
best-hand descriptions. *Stats*: per-street panels — Player · Cards · Hand (best
hand made on that street) · True Equity (god multiway) · vs-Range equity ·
AHEAD/BEHIND · that street's actions — plus a Hand Results strip (net + start→end
per player). *Hand Log*: the raw street-by-street action lines. The Stats view also carries a
per-street **local hindsight** line computed from the equities ("you were a 4%
dog and called $11 — pot odds (21%) didn't justify it"). Equities are computed
lazily when the summary opens (so play stays fast) on a separate RNG.

**Session log (⤓ Log)** — downloads `poker_log_YYYYMMDD_HHMMSS.txt` in the
*exact* PyQt PokerIQ format (`logfile.js`): session header, per-hand GAME STATUS
/ Dealer / Hole Cards / posts / actions / `--- Street ---` + `[STATS]` (true
god-view equity per active player) / `Board:` / showdown hand-types / WINNER /
Final Stacks / Gain-Loss, plus a SESSION SUMMARY (TABLE STATS, HOLE CARD STATS,
CHIP COUNT). Drop it into an AI for the same post-game analysis the desktop app
supports. Equity for the log/advisor uses a separate RNG so it never perturbs
the deal.

**Training mode (Theory of Mind screen)** — a top-bar Training toggle swaps the
table for the full ToM analysis screen (`tomlogic.js` + `tom.js`): no-peek
equity-vs-estimated-ranges, the Phil Gordon "Little Green Book" advisor (hand
tiers, combo nicknames, two-question script + four setup questions), per-opponent
13×13 range grids with board-connection highlighting + betting-history reads, the
Hero pot-commitment / SPR panel with a 4×13 outs board, Outs / Scare-cards, a
range-mode radio (opps weak / neutral / strong), EV-tagged action buttons, and
the 3×3 decision dashboard (MDF, bluff-catch, range advantage, reverse-implied,
Nash push, realized equity, VPIP/PFR/AGF, tilt, risk-of-ruin).

**Hotseat multiplayer (Players menu)** — pass-and-play on one device for up to 6
people (the "⚡ 6 humans" preset seats everyone at once). Set each seat to a Human
(with a name) or a bot; two or more humans turns on a privacy gate ("pass the
device to X — show my cards") that hides every hole card between turns and reveals
only the acting player's. The engine already stops at each human seat; the
controller generalises the act/advisor/equity path from "seat 0" to the acting
seat, so each player gets their own no-peek advisor too. (This is the
zero-infrastructure form of multiplayer — everyone shares the one laptop running
PokerIQ; remote play would need a WebSocket/WebRTC server.)

**Fold → spectator (God view)** — **every** fold drops that player into a God-view
review: all hole cards revealed plus a per-player equity table (Real god-equity /
Thinking vs-ranges / Pot Odds, with +EV/-EV from Real-vs-PotOdds) and ◄ Previous /
Next Street ► over per-street snapshots. Single-player / bots-only: the run-out
starts **paused** (bots act instantly) — ▶ Play streams it at a readable pace,
**Step street ▶** advances one street at a time, and at showdown the spectator
closes and the **Hand Summary opens automatically**. Hotseat with another human
still to act: you review, then **Pass device →** hands off to the next player.
At showdown every hand (including folded) is revealed for a shared review. Folding
to watch is legitimate and **not** flagged.

**God peek & assist flags** — manual God Mode (peeking pre-fold) is **only
available in single-player** (no other humans at the table); in hotseat the God
button is disabled — you only get the God view *after* you fold. When it is
available, using God Mode / Show Tells *while still in the hand* records an assist
attributed to that player and surfaces it in the Hand Summary, which everyone sees.
(Theory of Mind / Training is **not** an assist — it shows your own advisor and
models ranges, never peeking at actual cards.) Peeking is allowed; it's disclosed.

**Intentionally dropped** (cannot run in a sandboxed single file):
- **Remote/LAN multiplayer** — browsers can't open raw TCP sockets (a WebSocket
  or WebRTC build with a small server could do remote play; hotseat covers
  same-device play with zero infrastructure).
- **Claude hand-analysis** — relied on shelling out to the `claude` CLI.
- **TexasSolver** — 86 MB bundled C++ binary, never invoked by the app anyway.

Both dropped features are surfaced honestly in the in-app **?** dialog rather
than failing silently.

## Known gaps / polish backlog

- Hand-history replay browser and per-hand-class P&L table are not yet ported.
- Bot turn pacing is a fixed delay; no chip-movement animation.
- Mobile layout is functional but the felt oval is tuned for desktop widths.
