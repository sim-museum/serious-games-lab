"""
PokerIQ - Texas Hold'em Poker Engine with Equity-Driven Bots

This module provides:
- Lightweight hand evaluation and equity calculation
- Multiple bot strategies (BasicEquityBot, ImprovedEquityBot)
- External engine integration (PyPokerEngine adapter)
- Easy configuration for bot selection

No heavy dependencies or external solvers required.
Runs comfortably on ~15GB RAM with immediate runtime usage.
"""

from .models import (
    Card, Hand, GameState, Action, ActionType,
    Position, Street, PlayerState
)
from .evaluator import HandEvaluator, HandRank
from .equity import EquityCalculator
from .bots import (
    BaseBot, BasicEquityBot, ImprovedEquityBot,
    ExternalEngineBot, BotType, create_bot
)
from .constants import BOT_CONFIGS

__version__ = "1.0.0"
__all__ = [
    # Models
    'Card', 'Hand', 'GameState', 'Action', 'ActionType',
    'Position', 'Street', 'PlayerState',
    # Evaluation
    'HandEvaluator', 'HandRank',
    # Equity
    'EquityCalculator',
    # Bots
    'BaseBot', 'BasicEquityBot', 'ImprovedEquityBot',
    'ExternalEngineBot', 'BotType', 'create_bot',
    # Config
    'BOT_CONFIGS',
]
