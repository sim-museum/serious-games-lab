# BridgeIQ

A PyQt6 bridge application for Ubuntu 24.04 with classic desktop Bridge
interface. As of 2026-05, BEN/TensorFlow has been removed; bidding is
rule-based (modeled on Q-Plus's Precision90M and four other systems) and
card play is DDS + Monte-Carlo sampling against libdds.so.0.

## Plan to finish bidding + play (2026-05-23)

Goal: a competent, correct teaching bridge program across 5 systems.
Not parity with Q-Plus; correctness + coverage + no pathological bids.
Once this plan is complete, only teaching tools remain (modeled on
pokerIQ — hand reviewer, "why did you bid that?" explainer using the
`why=` strings already on every Bid, drill modes).

### Phase 1 — Multi-system smoke test
Run 10-deal diff sessions against Q-Plus for the four non-Precision
systems: SAYC, 2/1, Standard Acol, Standard French. Target is *no
illegal bids, no sanity-wrapper firings, no obviously broken auctions*
— NOT match-rate parity. Fix the top 2 issues per system. Stretch:
one second seed for any system showing brittleness.

### Phase 2 — Precision90M polish (optional)
Two known gaps from seed=400: overcall handling (lead-direct overcalls
like 3♦ after partner's 2♦ three-suiter) and Stayman+splinter cascades
(earlier seeds). Target: 20/50 perfect (currently 17/50). Stop there
— diminishing returns.

### Phase 3 — Card-play push
Three concrete gains identified earlier: defender signaling (count +
attitude), declarer entry-aware play, and suit-of-card decisions.
Target: 68-69% → 75%. Verify no "no-valid-samples" sampler failures
remain. Stop if it plateaus.

### Phase 4 — Integration + robustness
End-to-end: deal generation → bid → play → score, with the sanity
wrapper on for ~100 deals across all 5 systems. Record sanity-wrapper
firings as bugs and fix or accept. Confirm save/restore of in-progress
games.

### Phase 5 — Define "done"
Exit criteria: zero illegal bids over a 100-deal cross-system stress
run, zero sanity-wrapper-rescued pathological auctions, card play ≥
70% match rate vs Q-Plus. Tag a `bidding-and-play-complete` release;
move to teaching tools.

---

## Project Overview

This application provides a desktop bridge playing and analysis environment,
treating BEN as a pure engine (bidding, play, analysis) while implementing
a classic desktop bridge UI in PyQt6 as a separate layer.

## Architecture

```
bridgeIQ/           (~4,200 lines of code)
├── main.py             # Application entry point
├── run.sh              # Startup script
├── test_basic.py       # Test suite
├── README.md           # Documentation
├── backend/        # BEN Engine wrapper
│   ├── engine.py       # BridgeEngine class (bidding, play, analysis)
│   └── models.py       # Data models (Card, Hand, Bid, Board, etc.)
├── ui/      # PyQt6 UI (BridgeIQ style)
│   ├── main_window.py  # Main window with menus and game control
│   ├── table_view.py   # 4-hand table display with trick area
│   ├── bidding_box.py  # Bidding interface with keyboard support
│   └── dialogs/        # Configuration dialogs
│       ├── player_config.py   # Human/Computer player settings
│       ├── match_control.py   # Deal source, scoring, comparison
│       ├── deal_filter.py     # HCP/shape filters
│       ├── score_table.py     # IMP/MP/Rubber scoring
│       └── simulation.py      # Bid simulation analysis
└── data/config/        # Configuration files
```

## Key Features

### BEN Backend Integration
- **Direct Python API**: Imports BEN modules directly (no HTTP/WebSocket overhead)
- **Model Loading**: TensorFlow models loaded on startup
- **Bidding**: BEN's `BotBid` class for neural network bid decisions
- **Play**: BEN's `BotLead` and `CardPlayer` for card play
- **Analysis**: BEN's DDS solver for double-dummy analysis
- **Score Calculation**: Contract scoring for IMP/MP/Rubber

### BridgeIQ Style UI
- **Table View**: Four-hand display around central trick area
- **Vulnerability Indicator**: Visual N-S/E-W vulnerability display
- **Bidding Box**: Color-coded buttons with suit symbols (♠♥♦♣)
- **Auction Display**: Bid history in 4-column format
- **HCP Display**: High card points shown for each hand
- **Card Widgets**: Clickable cards with hover effects

### Game Modes
- **4-Player**: Human plays South, BEN plays N/E/W
- **1-Player**: Single hand visible (realistic play)
- **All-Computer**: Auto-play for analysis

### Menus (BridgeIQ Style)
- **File**: New deal, open/save files, export HTML
- **Deal**: Match control, repeat deal, deal filters
- **Configuration**: Players, bidding systems, preferences
- **View**: Show all hands, scores, DD analysis, bid simulation
- **Extras**: MiniBridge mode, one-player mode

### Dialogs
- **Player Configuration**: Human/Computer/External per seat
- **Match Control**: Deal source, scoring method, comparison mode
- **Deal Filter**: HCP ranges, shape constraints, special features
- **Score Table**: IMP/MP/Rubber scoring with history
- **Bid Simulation**: Evaluate candidate bids with samples

## Requirements

- Ubuntu 24.04 (or compatible Linux)
- Python 3.12+
- PyQt6
- TensorFlow 2.18+ (CPU)
- BEN engine (included in `../ben/`)

## Running the Application

**Important:** The app must be run from within the virtual environment.

```bash
cd /home/g/sgl/FRI/bridgeIQ/bridgeIQ
./run.sh
```

Or manually:
```bash
source /home/g/sgl/FRI/bridgeIQ/venv/bin/activate
export PYTHONPATH="bridgeIQ:ben/src:$PYTHONPATH"
python bridgeIQ/main.py
```

The `run.sh` script automatically activates the venv if it exists.

## Usage

1. **New Deal**: Press `Ctrl+N` or File > New Deal
2. **Bidding**: Click buttons or use keyboard (`p`=Pass, `1c`-`7n`=bids)
3. **Play**: Click cards in your hand
4. **Analysis**: View > Double Dummy Analysis or Bid Simulation

## Technical Notes

- BEN's Windows-only features (PIMC/BBA/SuitC) are disabled on Linux
- TensorFlow runs in CPU mode (GPU optional)
- Engine operations run in worker threads to keep UI responsive
- Signals/slots pattern for GUI-backend communication

## Files Modified in BEN

- `pyproject.toml`: Relaxed version constraints for Linux compatibility
  - `tensorflow-intel` → `tensorflow`
  - `numpy==1.26.4` → `numpy>=1.26.4`
  - `keras==3.6.0` → `keras>=3.6.0`
  - `requires-python = "==3.12"` → `requires-python = ">=3.12"`

## Created: January 2025
