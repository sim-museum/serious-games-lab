# BEN Bridge

A PyQt6 bridge application for Ubuntu 24.04 with classic desktop Bridge interface,
powered by the BEN (Bridge Engine) neural network.

## Features

- **Full Bridge Play**: Bidding and card play against BEN AI opponents
- **Classic Interface**: Familiar layout with table view, bidding box, and menus
- **Multiple Game Modes**:
  - 4-player (human South, computer N/E/W)
  - 1-player (single hand visible)
  - All-computer (auto-play)
- **Scoring**: IMP, Matchpoints, and Rubber Bridge scoring
- **Analysis**: Double-dummy analysis, bid simulation, hints
- **Deal Management**: Random deals, deal filters, PBN file support

## Requirements

- Ubuntu 24.04 (or compatible Linux)
- Python 3.12+
- PyQt6
- TensorFlow 2.18+
- BEN engine (cloned separately)

## Quick Start

```bash
# From the bridge directory (parent of ben_bridge and ben)
cd /path/to/bridge

# Activate virtual environment
source venv/bin/activate

# Run the application
./ben_bridge/run.sh
```

## Installation

### 1. Set up the virtual environment

```bash
cd /path/to/bridge
python3 -m venv venv
source venv/bin/activate
```

### 2. Install system dependencies

```bash
sudo apt update
sudo apt install python3-dev libboost-thread-dev
```

### 3. Install Python packages

```bash
pip install PyQt6 tensorflow colorama
```

### 4. Install BEN engine

```bash
# Clone BEN if not already done
git clone https://github.com/lorserker/ben.git

# Install as editable package
pip install -e ./ben
```

### 5. Verify installation

```bash
python ben_bridge/test_basic.py
```

## Running the Application

### Option 1: Run script (recommended)

```bash
./ben_bridge/run.sh
```

### Option 2: Manual execution

```bash
source venv/bin/activate
export PYTHONPATH="ben_bridge:ben/src:$PYTHONPATH"
python ben_bridge/main.py
```

### Option 3: From ben_bridge directory

```bash
cd ben_bridge
source ../venv/bin/activate
export PYTHONPATH=".:../ben/src:$PYTHONPATH"
python main.py
```

## Project Structure

```
bridge/
├── venv/                   # Python virtual environment
├── ben/                     # BEN engine (cloned from GitHub)
├── ben_bridge/            # This application
│   ├── main.py              # Application entry point
│   ├── run.sh               # Startup script
│   ├── test_basic.py        # Test suite
│   ├── ben_backend/         # BEN engine wrapper
│   │   ├── engine.py        # BridgeEngine class
│   │   └── models.py        # Data models (Card, Hand, Bid, Board)
│   ├── ui/       # PyQt6 UI components
│   │   ├── main_window.py   # Main application window
│   │   ├── table_view.py    # 4-hand table display
│   │   ├── bidding_box.py   # Bidding interface
│   │   └── dialogs/         # Configuration dialogs
│   │       ├── player_config.py
│   │       ├── match_control.py
│   │       ├── deal_filter.py
│   │       ├── score_table.py
│   │       └── simulation.py
│   └── data/config/         # Configuration files
└── claude.md                # Project documentation
```

## Usage Guide

### Starting a New Game

1. Launch the application
2. Press `Ctrl+N` or select `File > New Deal`
3. A random deal is generated with you as South
4. BEN plays North, East, and West

### Bidding

| Action | Mouse | Keyboard |
|--------|-------|----------|
| Pass | Click "Pass" | `p` |
| Double | Click "X" | `x` |
| Redouble | Click "XX" | `xx` |
| Bid 1♣ | Click "1♣" | `1c` |
| Bid 3NT | Click "3NT" | `3n` |

- Check "Alert" checkbox before bidding to mark alertable calls
- Enter explanation in the text field

### Card Play

- Click a card in your hand to play it
- Follow suit if possible (legal cards are highlighted)
- Current trick shows in the center
- Trick count updates automatically

### Analysis Features

| Feature | Access |
|---------|--------|
| Double Dummy | `View > Double Dummy Analysis` |
| Bid Simulation | `View > Bid Simulation` |
| Hint | Click "Hint" in toolbar |
| Show All Hands | `F2` or `View > Show All Hands` |

### Menu Reference

- **File**: New deal, Open/Save files, Export HTML, Exit
- **Deal**: Match control, Repeat deal, Random seed, Deal filters
- **Configuration**: Players, Bidding systems, Preferences
- **View**: Show hands, Review deal, Scores, DD analysis, Simulation
- **Extras**: MiniBridge mode, One-player mode
- **Help**: About, Help contents

## Configuration

### Player Types

In `Configuration > Players`:
- **Human**: You control this seat
- **Computer**: BEN plays this seat
- **External**: For network play (not implemented)

### Game Modes

- **4-Player**: Human South, BEN plays N/E/W (default)
- **1-Player**: Only your hand visible, realistic play
- **All-Computer**: BEN plays all seats, for analysis

### Scoring Methods

In `Deal > Match Control`:
- **IMP**: Team match scoring
- **Matchpoints**: Pairs tournament scoring
- **Rubber**: Traditional rubber bridge

## Troubleshooting

### "Engine: Failed" in status bar

TensorFlow failed to load. Check:
```bash
python -c "import tensorflow as tf; print(tf.__version__)"
```

### No window appears

Check if display is available:
```bash
echo $DISPLAY
```

### Segfault on exit

This is a known TensorFlow cleanup issue. The application works correctly;
the crash only occurs when closing.

### Slow startup

First launch loads TensorFlow models (~10-30 seconds).
Subsequent operations are faster.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    PyQt6 UI                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │TableView │  │BiddingBox│  │    Dialogs       │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │             │                  │            │
│       └─────────────┴──────────────────┘            │
│                     │                               │
│              ┌──────┴──────┐                        │
│              │MainWindow   │                        │
│              │GameController│                       │
│              └──────┬──────┘                        │
└─────────────────────┼───────────────────────────────┘
                      │ signals/slots
┌─────────────────────┼───────────────────────────────┐
│              ┌──────┴──────┐     BEN Backend        │
│              │BridgeEngine │                        │
│              └──────┬──────┘                        │
│                     │                               │
│    ┌────────────────┼────────────────┐              │
│    │                │                │              │
│ ┌──┴───┐      ┌─────┴────┐    ┌──────┴─────┐       │
│ │BotBid│      │BotLead   │    │DDSolver    │       │
│ └──────┘      │CardPlayer│    └────────────┘       │
│               └──────────┘                          │
└─────────────────────────────────────────────────────┘
                      │
              ┌───────┴───────┐
              │  TensorFlow   │
              │  Neural Nets  │
              └───────────────┘
```

## Known Limitations

- **Linux only**: PIMC/BBA/SuitC features disabled (Windows DLLs)
- **CPU only**: GPU acceleration not configured
- **Not implemented**:
  - Full bidding system editor
  - Competition/network mode
  - PBN import/export
  - HTML export

## License

This project uses the BEN bridge engine (GPL-3.0).
See the [BEN repository](https://github.com/lorserker/ben) for details.

## Credits

- **BEN Engine**: Neural network bridge engine by lorserker
- **UI Design**: Classic desktop bridge style
- **Framework**: PyQt6, TensorFlow
