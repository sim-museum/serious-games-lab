# PokerIQ Project Notes

## Setup

Before running pokerIQ.py, activate the virtual environment:

```bash
source venv/bin/activate
```

Then run:

```bash
python pokerIQ.py
```

## Project Structure

```
pokerIQ/
├── pokerIQ.py              # Main PyQt6 GUI application
├── poker_iq/               # Modular bot framework
│   ├── __init__.py
│   ├── models.py           # GameState, Action, Card, Hand, etc.
│   ├── constants.py        # Preflop ranges, thresholds, BotType enum
│   ├── evaluator.py        # Hand evaluation (HandRank, DrawEvaluator)
│   ├── equity.py           # Monte Carlo equity calculation
│   ├── utils.py            # Testing utilities
│   ├── bots/
│   │   ├── __init__.py     # Bot exports and create_bot() factory
│   │   ├── base_bot.py     # Abstract BaseBot class
│   │   ├── basic_equity_bot.py
│   │   ├── improved_equity_bot.py
│   │   └── external_engine_bot.py
│   ├── tests/
│   │   └── test_bots.py    # 21 unit tests
│   └── examples/
│       └── simple_demo.py
├── venv/                   # Virtual environment
├── requirements.txt        # PyQt6, eval7
└── claude.md               # This file
```

## poker_iq Bot Module

### Bot Types

| Bot | Class | Cute Name | Description |
|-----|-------|-----------|-------------|
| Basic Equity | `BasicEquityBot` | Equity Eddie | Simple equity + pot odds decisions |
| Improved Equity | `ImprovedEquityBot` | Savvy Sarah | Position-aware with preflop ranges, c-betting, draw detection |
| External Engine | `ExternalEngineBot` | Engine Emma | PyPokerEngine adapter (falls back to Improved if unavailable) |

### Usage

```python
from poker_iq.bots import create_bot, BotType

bot = create_bot(BotType.IMPROVED_EQUITY, seat=1)
action = bot.get_action(game_state)
```

### Running Tests

```bash
source venv/bin/activate
python -m unittest poker_iq.tests.test_bots -v
```

### Running Demo

```bash
python poker_iq/examples/simple_demo.py
```

## GUI Integration

### Preferences Dialog

The Preferences dialog (click "Prefs" button) has two tabs:

1. **Equity** - Controls equity calculation method
2. **AI Opponents** - Select bot type for each non-human seat

Bot preferences are persisted via QSettings and restored on next launch.

### Key Integration Points

- `BOT_TYPE_OPTIONS` - List of available bot types (line ~60 in pokerIQ.py)
- `BOT_CUTE_NAMES` - Maps bot type IDs to display names (line ~78)
- `PokerIQBotAdapter` - Translates between pokerIQ and poker_iq formats (line ~91)
- `Player.set_piq_bot()` - Attaches a poker_iq bot to a player
- `Player.get_bot_action()` - Uses poker_iq bot if configured, else default behavior

### Adding New Bots

1. Create bot class in `poker_iq/bots/` extending `BaseBot`
2. Add to `BotType` enum in `poker_iq/constants.py`
3. Add to factory in `poker_iq/bots/__init__.py`
4. Add entry to `BOT_TYPE_OPTIONS` in `pokerIQ.py`
5. Add cute name to `BOT_CUTE_NAMES` in `pokerIQ.py`

## Original Bot Styles (in pokerIQ.py)

| Style | Name | Strategy |
|-------|------|----------|
| optimal | Optimal Olivia | GTO-aware, balanced |
| tight | Tight Tim | Conservative, folds marginal |
| loose | Loose Bruce | Calls frequently |
| aggressive | Aggro Angela | Raises often, bluffs |
| tom | Fluid Fiona | Theory of Mind, adapts to opponents |

## Command Line Options

```bash
python pokerIQ.py --god        # God Mode (see all cards)
python pokerIQ.py --tells      # Show tells/statistics panel
python pokerIQ.py --textmode   # Text-only mode (no GUI)
```
