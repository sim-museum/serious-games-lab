# PokerIQ - Equity-Driven Poker Bots

A pure Python poker bot framework with equity-based decision making.

## Features

- **No external dependencies** for core functionality
- **Monte Carlo equity calculation** with preflop lookup tables
- **Position-aware preflop ranges** (UTG tight to BTN wide)
- **Board texture analysis** (wet vs dry boards)
- **Draw detection** (flush draws, straight draws, outs calculation)
- **Mixed strategies** for balanced play
- **PyPokerEngine integration** with graceful fallback

## Bot Types

### BasicEquityBot
Simple equity + pot odds decisions. Good baseline for comparison.

```python
from poker_iq.bots import BasicEquityBot

bot = BasicEquityBot(seat=0)
action = bot.get_action(game_state)
```

### ImprovedEquityBot
Position-aware with preflop ranges, continuation betting, and draw semi-bluffing.

```python
from poker_iq.bots import ImprovedEquityBot

bot = ImprovedEquityBot(seat=0, config={
    'aggression': 0.6,
    'cbet_frequency': 0.65
})
action = bot.get_action(game_state)
```

### ExternalEngineBot
Uses PyPokerEngine for decisions with fallback to ImprovedEquityBot.

```python
from poker_iq.bots import ExternalEngineBot

bot = ExternalEngineBot(seat=0, external_bot_class='honest')
action = bot.get_action(game_state)
```

Available external bot classes: `honest`, `fish`, `fold`, `call`, `raise`

## Factory Function

```python
from poker_iq.bots import create_bot, BotType

bot = create_bot(BotType.IMPROVED_EQUITY, seat=0, config={'aggression': 0.8})
```

## Testing

```bash
cd pokerIQ
python -m pytest poker_iq/tests/ -v
```

## Demo

```bash
python poker_iq/examples/simple_demo.py
```

## Configuration Options

### BasicEquityBot
- `strong_threshold`: Equity threshold for value betting (default: 0.65)
- `medium_threshold`: Equity for medium strength plays (default: 0.50)
- `bluff_frequency`: How often to bluff (default: 0.10)

### ImprovedEquityBot
- `aggression`: Overall aggression factor (default: 0.6)
- `cbet_frequency`: C-bet frequency (default: 0.65)
- `check_raise_frequency`: Check-raise frequency (default: 0.08)

### ExternalEngineBot
- `bot_class`: PyPokerEngine bot type (default: 'honest')

## Architecture

```
poker_iq/
├── __init__.py          # Package exports
├── models.py            # GameState, Action, Card, etc.
├── constants.py         # Preflop ranges, thresholds
├── evaluator.py         # Hand evaluation
├── equity.py            # Monte Carlo equity calculation
├── utils.py             # Testing utilities
├── bots/
│   ├── __init__.py      # Bot exports and factory
│   ├── base_bot.py      # Abstract base class
│   ├── basic_equity_bot.py
│   ├── improved_equity_bot.py
│   └── external_engine_bot.py
├── tests/
│   └── test_bots.py
└── examples/
    └── simple_demo.py
```

## Requirements

- Python 3.8+
- No external dependencies for core functionality
- Optional: PyPokerEngine (`pip install PyPokerEngine`)
