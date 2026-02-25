# BEN Bridge (BEN Engine)

A PyQt6 bridge application for Ubuntu 24.04 with classic desktop Bridge interface,
powered by the BEN (Bridge Engine) neural network.

> **IMPORTANT:** Always run from the venv! The BEN engine will not initialize otherwise.
> ```bash
> source venv/bin/activate && python -m ben_bridge.main
> ```

## Project Overview

This application provides a desktop bridge playing and analysis environment,
treating BEN as a pure engine (bidding, play, analysis) while implementing
a classic desktop bridge UI in PyQt6 as a separate layer.

## Architecture

```
ben_bridge/           (~4,200 lines of code)
├── main.py             # Application entry point
├── run.sh              # Startup script
├── test_basic.py       # Test suite
├── README.md           # Documentation
├── ben_backend/        # BEN Engine wrapper
│   ├── engine.py       # BridgeEngine class (bidding, play, analysis)
│   └── models.py       # Data models (Card, Hand, Bid, Board, etc.)
├── ui/      # PyQt6 UI (BEN Bridge style)
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

### BEN Bridge Style UI
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

### Menus (BEN Bridge Style)
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
cd /home/g/sgl/FRI/benBridge/ben_bridge
./run.sh
```

Or manually:
```bash
source /home/g/sgl/FRI/benBridge/venv/bin/activate
export PYTHONPATH="ben_bridge:ben/src:$PYTHONPATH"
python ben_bridge/main.py
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
