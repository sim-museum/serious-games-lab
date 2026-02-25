"""
PokerIQ Bot implementations.

Provides:
- BaseBot: Abstract interface for all bots
- BasicEquityBot: Simple equity + pot odds decisions
- ImprovedEquityBot: Position-aware with ranges and heuristics
- ExternalEngineBot: Adapter for PyPokerEngine bots
"""

from .base_bot import BaseBot
from .basic_equity_bot import BasicEquityBot
from .improved_equity_bot import ImprovedEquityBot
from .external_engine_bot import ExternalEngineBot
from ..constants import BotType

from typing import Optional
from ..models import GameState


def create_bot(
    bot_type: BotType,
    seat: int = 0,
    config: Optional[dict] = None,
    **kwargs
) -> BaseBot:
    """
    Factory function to create a bot instance.

    Args:
        bot_type: Type of bot to create
        seat: Seat index for the bot
        config: Optional configuration override
        **kwargs: Additional bot-specific arguments

    Returns:
        Bot instance ready to use

    Example:
        bot = create_bot(BotType.IMPROVED_EQUITY, seat=2)
        action = bot.get_action(game_state)
    """
    from ..constants import BOT_CONFIGS

    # Merge default config with overrides
    default_config = BOT_CONFIGS.get(bot_type, {})
    if config:
        default_config = {**default_config, **config}

    if bot_type == BotType.BASIC_EQUITY:
        return BasicEquityBot(seat=seat, config=default_config, **kwargs)
    elif bot_type == BotType.IMPROVED_EQUITY:
        return ImprovedEquityBot(seat=seat, config=default_config, **kwargs)
    elif bot_type == BotType.EXTERNAL_ENGINE:
        return ExternalEngineBot(seat=seat, config=default_config, **kwargs)
    else:
        raise ValueError(f"Unknown bot type: {bot_type}")


__all__ = [
    'BaseBot',
    'BasicEquityBot',
    'ImprovedEquityBot',
    'ExternalEngineBot',
    'BotType',
    'create_bot',
]
