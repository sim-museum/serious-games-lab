# bridgeIQ

A PyQt6 desktop bridge application for Ubuntu 24.04 with a classic table
interface. **bridgeIQ is neural-network-free** — there is no BEN and no
TensorFlow:

- **Bidding** is rule-based and system-driven (`backend/native_bidder.py`,
  `NativeBiddingEngine`), covering seven Q-Plus-style systems with full
  spec-driven conventions.
- **Card play** uses a no-peek **alpha-mu** engine (`backend/nopeek.py`): DDS run
  on belief-sampled hidden layouts with a single consistent line across
  indistinguishable samples — strong like PIMC but with no strategy-fusion
  "tells", and it never peeks at the hidden cards. A Monte-Carlo + DDS path
  (`get_mc_card_play`) is also available. The double-dummy solver is the system
  `libdds`.

> Older docs that mention "BEN", "the neural network", or "TensorFlow" are
> obsolete — that engine was removed. The canonical engineering notes live in
> `bridgeIQ/bridgeIQ/CLAUDE.md`.

## Features

- **Full bridge play** — rule-based bidding + no-peek/DDS card play opponents.
- **Seven bidding systems** — SAYC, 2/1 (TwoOverOne), Standard Acol, Standard
  French, Precision90M / Precision90P / Precision70 — selectable per pair
  (N/S and E/W can run different systems).
- **Instrumented (teaching / analysis) view** — an alternative table that shows,
  per hand, what is *known* and *inferred*, with counting aids, declarer-plan
  guidance, and live defensive-signal reads. See
  `bridgeIQ/bridgeIQ/docs/instrumented_view.md`.
- **Defensive signalling** — biq emits and reads standard / upside-down
  attitude, count, suit-preference, Smith and trump-echo signals.
- **Closed-room play vs Q-Plus** — play a deal, then replay it as a closed room
  with **biq E/W networked into a Q-Plus N/S table over Q-NET** for an IMP
  comparison (requires a Q-Plus install; see *Q-Plus / closed room* below).
- **Scoring** — IMP, Matchpoints, Rubber.
- **Analysis** — double-dummy analysis, bid simulation, blunder check, hints.
- **Deal management** — random deals, HCP/shape filters, PBN / BDL / QSS import,
  hand logging.
- **Keyboard or mouse** for every bidding and card-play command (works from the
  normal table *and* the instrumented view).

## Requirements

- Ubuntu 24.04 (or compatible Linux)
- Python 3.12+
- PyQt6, numpy
- `libdds0` (system package — provides `libdds.so.0` for double-dummy card play)

No TensorFlow, no GPU, no separately-cloned engine.

## Quick start

```bash
cd /home/h/sgl/FRI/bridgeIQ/bridgeIQ
./run.sh
```

`run.sh` uses the project venv's Python directly (`venv/bin/python`) and sets
`PYTHONPATH` itself, so no manual activation is needed.

## Installation

```bash
cd /home/h/sgl/FRI/bridgeIQ
python3 -m venv venv
source venv/bin/activate
sudo apt update && sudo apt install python3-dev libdds0
pip install PyQt6 numpy colorama
```

Verify:

```bash
cd bridgeIQ
python -c "import PyQt6, backend.models, backend.dds; print('ok')"
```

## Project structure

```
FRI/bridgeIQ/
├── venv/                       # Python virtual environment
├── DOC/                        # this front-door documentation
└── bridgeIQ/                   # the application package
    ├── main.py                 # entry point (splash → MainWindow)
    ├── run.sh                  # launcher (uses venv python)
    ├── CLAUDE.md               # canonical engineering notes / status
    ├── backend/
    │   ├── native_bidder.py    # rule-based, system-driven bidding engine
    │   ├── bidding_systems.py  # the seven system specs
    │   ├── native_lead.py      # rule-based opening lead
    │   ├── nopeek.py           # no-peek alpha-mu card-play engine
    │   ├── signals.py / signal_read.py  # defensive signalling (emit / read)
    │   ├── dds.py              # libdds ctypes binding
    │   ├── auction_inference.py# per-seat constraints from the auction
    │   └── models.py           # data models (Card, Hand, Bid, Board, …)
    ├── ui/
    │   ├── main_window.py      # main window, menus, game control
    │   ├── table_view.py       # 4-hand table + trick area
    │   ├── teaching_view.py    # instrumented (teaching/analysis) view
    │   ├── bidding_box.py      # bidding interface
    │   └── dialogs/            # preferences, player config, scoring, …
    ├── docs/                   # instrumented_view.md, qnet_troubleshooting.md, UML
    ├── tools/                  # Q-NET client/server, harness control, A/B tools
    └── CONFIG/                 # B-INIT / B-MATCH / B-PREFER config files
```

## Usage

### New game
Press `Ctrl+N` or **File → New Deal** — a random deal is dealt with you as
South; bridgeIQ plays N/E/W.

### Bidding (mouse or keyboard)
| Action | Mouse | Keyboard |
|--------|-------|----------|
| Pass | "Pass" | `p` |
| Double / Redouble | "X" / "XX" | `x` / `xx` |
| Bid 1♣ | "1♣" | `1c` |
| Bid 3NT | "3NT" | `3n` |

### Card play (mouse or keyboard)
Click a card, **or** press a suit key (`S`/`H`/`D`/`C`) then a rank
(`A K Q J T 9–2`, `0` = ten) — when you must follow suit the rank alone is
enough. Keyboard play works from the instrumented view too.

### Instrumented view
Toggle with the **Instrumented** toolbar button. Header controls: **Detail**
(Beginner / Intermediate / Expert), **Carding N/S** and **Carding E/W** (per-pair
signalling agreement), and **Smith** (notrump Smith-echo agreement). Full
reference: `bridgeIQ/bridgeIQ/docs/instrumented_view.md`.

## Configuration

**Configuration → Preferences** (saved to `CONFIG/B-PREFER.CFG`):

- **Display** — single/double click, suit colours, show the bid-information
  panel (docked at the upper-left of the bidding screen), etc.
- **Bidding** — bidding engine and the native bidding system (per pair).
- **Signalling convention** — standard or upside-down (UDCA); biq both emits and
  reads it.
- **AI & Network**
  - **Claude Code** — post-hand AI analysis / annotated transcripts / AI hints.
    **Off by default** (it shells out to the `claude` CLI and costs tokens).
  - **Q-Plus availability** — `none` (default) / `demo` / `full`. Closed-room /
    Q-NET / Q-Plus features are hidden unless a Q-Plus build is configured.

## Q-Plus / closed room

With Q-Plus available, **Closed Room** (or the end-of-hand *Generate closed
room*) replays the current deal with **biq E/W vs Q-Plus N/S over Q-NET**, then
**Extras → Ingest Q-Plus closed room** brings the result back for the IMP swing.

The Q-NET server **must run under system wine 9** — under the older TkG runner
Q-Plus accepts the connection but never reads it, so biq E/W can't attach. biq's
launcher pins Q-Plus to wine 9 and warns if it's missing. If a previous session
left a stale socket, use **Extras → Kill all wine processes**. Details:
`bridgeIQ/bridgeIQ/docs/qnet_troubleshooting.md`.

## Troubleshooting

**"Not ready" / engine failed in the status bar** — the DDS library didn't load:
```bash
ldconfig -p | grep libdds   # expect libdds.so.0
sudo apt install libdds0
```

**No window appears** — check `echo $DISPLAY`.

**biq E/W won't attach to Q-Plus** — almost always the wrong wine runner; see
`docs/qnet_troubleshooting.md`.

## License

GPL-3.0.
