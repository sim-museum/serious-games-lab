# BridgeIQ

A PyQt6 bridge application for Ubuntu 24.04 with a classic desktop Bridge
interface. Bidding is rule-based (Q-Plus-style); card play uses Monte-Carlo
sampling on top of the libdds double-dummy solver. No neural networks, no
TensorFlow.

## Features

- **Full Bridge Play**: Rule-based bidding + DDS/MC card play opponents
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
- PyQt6, numpy
- libdds0 (system package — provides libdds.so.0 for DDS card play)

## Quick Start

```bash
# From the bridge directory (parent of the bridgeIQ package)
cd /path/to/bridgeIQ

# Activate virtual environment
source venv/bin/activate

# Run the application
./bridgeIQ/run.sh
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
sudo apt install python3-dev libdds0
```

### 3. Install Python packages

```bash
pip install PyQt6 colorama numpy
```

### 4. Verify installation

```bash
python bridgeIQ/test_basic.py
```

## Running the Application

### Option 1: Run script (recommended)

```bash
./bridgeIQ/run.sh
```

### Option 2: Manual execution

```bash
source venv/bin/activate
export PYTHONPATH="bridgeIQ:$PYTHONPATH"
python bridgeIQ/main.py
```

## Project Structure

```
bridgeIQ/
├── venv/                   # Python virtual environment
├── bridgeIQ/               # This application
│   ├── main.py              # Application entry point
│   ├── run.sh               # Startup script
│   ├── test_basic.py        # Test suite
│   ├── backend/         # Engine + DDS bindings
│   │   ├── engine.py        # BridgeEngine class
│   │   ├── dds.py           # libdds ctypes binding
│   │   ├── native_bidder.py # Rule-based bidder
│   │   ├── native_lead.py   # Rule-based opening lead
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
4. bridgeIQ plays North, East, and West

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
- **Computer**: bridgeIQ plays this seat
- **External**: For network play (not implemented)

### Game Modes

- **4-Player**: Human South, bridgeIQ plays N/E/W (default)
- **1-Player**: Only your hand visible, realistic play
- **All-Computer**: bridgeIQ plays all seats, for analysis

### Scoring Methods

In `Deal > Match Control`:
- **IMP**: Team match scoring
- **Matchpoints**: Pairs tournament scoring
- **Rubber**: Traditional rubber bridge

## Troubleshooting

### "Engine: Failed" in status bar

DDS library failed to load. Verify libdds0 is installed:
```bash
ldconfig -p | grep libdds
sudo apt install libdds0
```

### No window appears

Check if display is available:
```bash
echo $DISPLAY
```

### Segfault on exit

libdds spawns worker threads that outlive Python's interpreter shutdown;
the harmless segfault only occurs at process exit, never mid-game.

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
│              ┌──────┴──────┐     Backend            │
│              │BridgeEngine │                        │
│              └──────┬──────┘                        │
│                     │                               │
│    ┌────────────────┼────────────────┐              │
│    │                │                │              │
│ ┌──┴─────────┐ ┌────┴─────┐    ┌─────┴──────┐      │
│ │NativeBidder│ │NativeLead│    │DDSolver    │      │
│ └────────────┘ └──────────┘    └─────┬──────┘      │
│                                      │              │
└──────────────────────────────────────┼──────────────┘
                                       │
                              ┌────────┴────────┐
                              │ libdds.so.0     │
                              │ (system C lib)  │
                              └─────────────────┘
```

## Known Limitations

- **Linux only**: tested on Ubuntu 24.04
- **Not implemented**:
  - Full bidding system editor
  - Competition/network mode
  - PBN import/export
  - HTML export

## Credits

- **libdds**: Double-dummy solver by dds-bridge
- **UI Design**: Classic desktop bridge style
- **Framework**: PyQt6
