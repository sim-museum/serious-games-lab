# PokerIQ web port — status

**Goal:** transpile the full PyQt6 desktop app (`pokerIQ.py`, ~19K LOC) into a
single self-contained `pokerIQ.html` that runs in any browser — **all**
functionality, not a watered-down demo.

**State:** ✅ full desktop parity reached. Build is one self-contained file
(~307 KB, one inline `<script>` + one `<style>`, nothing loaded at page-load).
Test suite green — 13 files, 0 failures.

Branch: `pokeriq-web-full-parity` · latest: code-review fixes applied.

## Build & test

```bash
cd web
node build.js     # -> ../pokerIQ.html  (concatenates src/* in dependency order)
npm test          # engine + UI + built-file + feature suites (needs dev jsdom)
```

`build.js` guards that no external resource is loaded at page-load; the two
opt-in *runtime* endpoints (api.anthropic.com for Claude, `stun:` for WebRTC)
are allow-listed because they are network *actions the user triggers*, not
bundled resources.

## Modules (`web/src/`)

| Module | Role | Ported from |
|---|---|---|
| `engine.js` | 7-card evaluator + Monte-Carlo equity | `eval7`, `calc_equity_*`, `evaluator.py` |
| `game.js` | betting loop, true side pots, showdown, follower mirror (`applyNet`/`netStateFor`) | `TextModeGame`, `Player` |
| `bots.js` | 9 styles + 2 equity bots | `Player.get_bot_action`, `poker_iq/bots/*` |
| `analytics.js` | board texture, sklansky, nash, EV, session/opponent stats, `DecisionJournal` | `classify_board`, `SessionStats`, `OpponentModel`, `DecisionJournal` |
| `tomlogic.js` / `tom.js` | Theory-of-Mind ranges, Gordon advisor, outs, 9-metric dashboard | `TheoryOfMind*`, `MetricDashboard`, `HeroOutsTab` |
| `logfile.js` | byte-exact PyQt session log | `PokerIQ` log writer |
| `ui.js` | table view + controller (host/guest/hotseat/spectator), keyboard, save/load, journal | `PokerWindow`, widgets |
| `trainers.js` | 8 study modals | `AKQGameDialog`, `JamOrFoldTrainer`, `VarianceDashboard`, … |
| `files.js` | save/load game, buy chips, hand-history replay, hand-class P&L | File menu, `HandClassPnLTable`, `PlayerHistoryDialog` |
| `prefs.js` | Preferences (equity mode, deck colours, per-seat bots) | `Preferences` + `QSettings` |
| `claude.js` | Claude hand-analysis via the Anthropic API in-browser | `ClaudeAnalysisThread` (no `claude` CLI) |
| `netplay.js` | serverless WebRTC online play (host/guest, chat) | `network/{server,client,protocol}.py` (no TCP) |
| `main.js` | boot + menu wiring | `run_gui_mode` |

## Feature parity

Ported and verified: 6-max NL Hold'em engine + true side pots, 9 bot styles +
2 equity bots, live equity / pot-odds / EV advisor, board-texture reads,
opponent tells (ranges / leaks / levels of thinking), God mode, Show Tells, the
full Theory-of-Mind training screen, session + lifetime stats (localStorage),
8 trainers, Hand Summary (Analysis / Stats / Log), byte-exact session log,
hotseat pass-and-play with privacy gates, fold→spectator God view, keyboard
shortcuts (F/K/C/R/B/N/G/S/T/Space/arrows).

Closed the previously-"dropped" gaps:

- **Online multiplayer** (`netplay.js`) — serverless peer-to-peer WebRTC with
  copy/paste SDP signalling. Host runs the authoritative engine and forwards
  every engine event + a per-peer authoritative state blob (each guest sees only
  its own hole cards until a genuine contested showdown); guests mirror state and
  render the full UI locally. Seats, mid-hand join (seated next hand),
  disconnect→bot, table chat.
- **Claude hand-analysis** (`claude.js`) — direct Anthropic Messages API from the
  browser (`claude-opus-4-8`, adaptive thinking, user-supplied key,
  `anthropic-dangerous-direct-browser-access`). Critique + annotate modes.
- **Save/Load** a game to JSON (resumes mid-hand), **Buy chips**,
  **hand-history replay** browser, **hand-class P&L** table.
- **Preferences** — visible-cards-only equity, modern 4-colour vs legacy deck,
  per-seat bot lineup + beat-the-defaults random-pool unlock.
- **Decision journal** feeding the Calibration (Brier) trainer.

Not ported (genuinely N/A to a browser single-page app): the TexasSolver C++
binary (never invoked by the running app) and the CLI-only `--textmode` /
`--replay` (the in-app hand-history replay covers the latter's value).

## Code-review pass

A multi-agent review of the new code fixed real bugs, notably two online-play
issues: a host could fold to peek at remote players' hole cards, and a guest
seated anywhere but seat 0 couldn't act. Also fixed: showdown over-reveal,
prefs-Cancel persisting silently, save/load of replay history, and hotseat
calibration attaching the wrong seat's outcome.

## Backlog (cosmetic)

- Fixed bot-turn delay; no chip-movement animation.
- Mobile layout functional but the felt oval is tuned for desktop widths.
- WebRTC across strict/symmetric NATs may need a TURN relay (STUN covers LAN +
  most home networks).
