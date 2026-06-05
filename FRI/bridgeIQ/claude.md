# bridgeIQ

A PyQt6 bridge application with a classic desktop interface, powered by a
**tuned custom rule-based engine** for bidding, opening leads, and play —
no neural network or TensorFlow dependency.

History: the project began as a front-end for the BEN neural-network engine;
that integration has been dropped in favor of the native rule-based engine.
Internal module names (`ben_bridge/`, `ben_backend/`, `ben/DATA/LOG`)
survive from that era.

> **IMPORTANT:** Always run from the venv!
> ```bash
> source venv/bin/activate && python -m ben_bridge.main
> ```

## Project Overview

This application provides a desktop bridge playing and analysis environment:
a custom rule-based engine (bidding, lead, play, analysis) behind a classic
desktop bridge UI implemented in PyQt6 as a separate layer.

## Architecture

```
ben_bridge/           (~4,200 lines of code)
├── main.py             # Application entry point
├── run.sh              # Startup script
├── test_basic.py       # Test suite
├── README.md           # Documentation
├── ben_backend/        # Engine layer
│   ├── engine.py       # BridgeEngine class (bidding, play, analysis)
│   ├── native_bidder.py# NativeBiddingEngine — rule-based, system-driven bidding
│   ├── native_lead.py  # Rule book for opening leads
│   ├── bidding_rules.py / bidding_systems.py  # System definitions
│   └── models.py       # Data models (Card, Hand, Bid, Board, etc.)
├── ui/      # PyQt6 UI
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

### Engine
- **Rule-based bidding**: `native_bidder.NativeBiddingEngine`, system-driven
  (bidding systems under `CONFIG/BIDRULE/`: SAYC, Two-over-One, Precision,
  Acol, Standard French, ...)
- **Opening leads**: `native_lead` rule book
- **Analysis**: DDS solver for double-dummy analysis
- **Score Calculation**: Contract scoring for IMP/MP/Rubber

### Desktop UI
- **Table View**: Four-hand display around central trick area
- **Vulnerability Indicator**: Visual N-S/E-W vulnerability display
- **Bidding Box**: Color-coded buttons with suit symbols (♠♥♦♣)
- **Auction Display**: Bid history in 4-column format
- **HCP Display**: High card points shown for each hand
- **Card Widgets**: Clickable cards with hover effects

### Game Modes
- **4-Player**: Human plays South, the engine plays N/E/W
- **1-Player**: Single hand visible (realistic play)
- **All-Computer**: Auto-play for analysis

### Menus
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

- Ubuntu 24.04+ (or compatible Linux)
- Python 3.12+
- PyQt6, colorama (no TensorFlow)

## Running the Application

**Important:** The app must be run from within the virtual environment.

```bash
cd /home/g/sgl/FRI/bridgeIQ
./run.sh
```

Or manually:
```bash
source /home/g/sgl/FRI/bridgeIQ/venv/bin/activate
cd ben_bridge && python3 main.py
```

The `run.sh` script automatically activates the venv if it exists.

## Usage

1. **New Deal**: Press `Ctrl+N` or File > New Deal
2. **Bidding**: Click buttons or use keyboard (`p`=Pass, `1c`-`7n`=bids)
3. **Play**: Click cards in your hand
4. **Analysis**: View > Double Dummy Analysis or Bid Simulation

## Technical Notes

- Engine operations run in worker threads to keep UI responsive
- Signals/slots pattern for GUI-backend communication
- Deal logs (.bdl/.pbn/.ppl) are written to `ben/DATA/LOG/`

## Created: January 2025 · Renamed benBridge → bridgeIQ: June 2026
