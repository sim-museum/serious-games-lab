"""
External Engine Bot Adapter for PokerIQ.

Integrates with PyPokerEngine (or similar lightweight poker libraries)
to provide bot decisions.

This adapter:
1. Translates PokerIQ game state to the external engine's format
2. Queries the external engine's bot for an action
3. Translates the action back to PokerIQ format
4. Falls back to ImprovedEquityBot if external engine fails

PyPokerEngine:
- Pure Python implementation
- No large dependencies
- Provides example bots (honest_player, fish_player, etc.)
- Install: pip install PyPokerEngine

Documentation: https://github.com/ishikota/PyPokerEngine
"""

from typing import Optional, Dict, Any, Tuple, List
import logging

from .base_bot import BaseBot
from .improved_equity_bot import ImprovedEquityBot
from ..models import GameState, Action, ActionType, Street, Hand, Card, Suit, Rank


logger = logging.getLogger(__name__)


class ExternalEngineBot(BaseBot):
    """
    Bot that uses PyPokerEngine for decisions.

    Falls back to ImprovedEquityBot if:
    - PyPokerEngine is not installed
    - Any error occurs during translation or decision
    """

    def __init__(
        self,
        seat: int = 0,
        config: Optional[Dict[str, Any]] = None,
        external_bot_class: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the external engine bot.

        Args:
            seat: Seat index
            config: Configuration dict
            external_bot_class: Name of PyPokerEngine bot class to use.
                Options: 'honest', 'fish', 'fold', 'call', 'raise'
                Default: 'honest' (plays based on hand strength)
        """
        super().__init__(seat=seat, config=config, **kwargs)

        cfg = config or {}
        self.external_bot_class = external_bot_class or cfg.get('bot_class', 'honest')
        self.fallback_bot = ImprovedEquityBot(seat=seat, config=config, **kwargs)

        # Try to import PyPokerEngine
        self._engine_available = False
        self._external_bot = None
        self._initialize_external_bot()

    def _initialize_external_bot(self) -> None:
        """
        Try to initialize PyPokerEngine bot.
        """
        try:
            # Import PyPokerEngine components
            from pypokerengine.players import BasePokerPlayer

            # Create the appropriate bot type
            if self.external_bot_class == 'honest':
                self._external_bot = HonestPlayerAdapter()
            elif self.external_bot_class == 'fish':
                self._external_bot = FishPlayerAdapter()
            elif self.external_bot_class == 'fold':
                self._external_bot = FoldPlayerAdapter()
            elif self.external_bot_class == 'call':
                self._external_bot = CallPlayerAdapter()
            elif self.external_bot_class == 'raise':
                self._external_bot = RaisePlayerAdapter()
            else:
                # Default to honest player
                self._external_bot = HonestPlayerAdapter()

            self._engine_available = True
            self.log(f"PyPokerEngine initialized with {self.external_bot_class} player")

        except ImportError:
            logger.warning("PyPokerEngine not installed. Using fallback bot. "
                          "Install with: pip install PyPokerEngine")
            self._engine_available = False

        except Exception as e:
            logger.warning(f"Failed to initialize PyPokerEngine: {e}")
            self._engine_available = False

    def get_action(self, state: GameState) -> Action:
        """
        Get action from external engine, with fallback.
        """
        if not self._engine_available or self._external_bot is None:
            return self.fallback_bot.get_action(state)

        try:
            # Translate state to PyPokerEngine format
            ppe_state = self._translate_state_to_ppe(state)
            valid_actions = self._translate_actions_to_ppe(state)

            # Query external bot
            ppe_action = self._external_bot.declare_action(
                valid_actions,
                ppe_state['hole_card'],
                ppe_state
            )

            # Translate action back
            action = self._translate_action_from_ppe(ppe_action, state)
            return action

        except Exception as e:
            logger.warning(f"External engine error: {e}. Using fallback.")
            return self.fallback_bot.get_action(state)

    def _translate_state_to_ppe(self, state: GameState) -> Dict[str, Any]:
        """
        Translate PokerIQ GameState to PyPokerEngine round_state format.
        """
        hole_cards = self.get_hole_cards(state)

        # Card format: ['SA', 'HK'] for Spade Ace, Heart King
        def card_to_ppe(card: Card) -> str:
            suit_map = {Suit.SPADES: 'S', Suit.HEARTS: 'H',
                       Suit.DIAMONDS: 'D', Suit.CLUBS: 'C'}
            rank_map = {
                Rank.TWO: '2', Rank.THREE: '3', Rank.FOUR: '4', Rank.FIVE: '5',
                Rank.SIX: '6', Rank.SEVEN: '7', Rank.EIGHT: '8', Rank.NINE: '9',
                Rank.TEN: 'T', Rank.JACK: 'J', Rank.QUEEN: 'Q',
                Rank.KING: 'K', Rank.ACE: 'A'
            }
            return suit_map[card.suit] + rank_map[card.rank]

        # Build round state
        round_state = {
            'street': self._street_to_ppe(state.street),
            'pot': {
                'main': {'amount': state.pot},
                'side': []
            },
            'community_card': [card_to_ppe(c) for c in state.board],
            'dealer_btn': state.button_seat,
            'next_player': state.action_seat,
            'small_blind_pos': (state.button_seat + 1) % state.num_players,
            'big_blind_pos': (state.button_seat + 2) % state.num_players,
            'round_count': 1,
            'small_blind_amount': state.small_blind,
            'seats': [],
            'hole_card': [card_to_ppe(c) for c in hole_cards.cards] if hole_cards else [],
            'action_histories': {}
        }

        # Build seats
        for player in state.players:
            round_state['seats'].append({
                'uuid': f'player_{player.seat}',
                'stack': player.stack,
                'name': f'Player {player.seat}',
                'state': 'participating' if player.is_active else 'folded'
            })

        return round_state

    def _translate_actions_to_ppe(self, state: GameState) -> List[Dict[str, Any]]:
        """
        Translate legal actions to PyPokerEngine format.
        """
        valid_actions = []
        to_call = self.get_to_call(state)
        stack = self.get_stack(state)

        if to_call == 0:
            # Can check
            valid_actions.append({'action': 'call', 'amount': 0})
        else:
            # Can fold or call
            valid_actions.append({'action': 'fold', 'amount': 0})
            valid_actions.append({'action': 'call', 'amount': min(to_call, stack)})

        # Raise/bet
        min_raise = state.current_bet + state.min_raise if state.current_bet > 0 else state.big_blind
        max_raise = stack + state.players[self.seat].current_bet

        if max_raise > min_raise:
            valid_actions.append({
                'action': 'raise',
                'amount': {'min': min_raise, 'max': max_raise}
            })

        return valid_actions

    def _translate_action_from_ppe(
        self,
        ppe_action: Tuple[str, int],
        state: GameState
    ) -> Action:
        """
        Translate PyPokerEngine action back to PokerIQ format.
        """
        action_type, amount = ppe_action

        if action_type == 'fold':
            return Action.fold()
        elif action_type == 'call':
            if amount == 0:
                return Action.check()
            return Action.call(amount)
        elif action_type == 'raise':
            stack = self.get_stack(state)
            if amount >= stack:
                return Action.all_in(stack)
            if state.current_bet == 0:
                return Action.bet(amount)
            return Action.raise_to(amount)
        else:
            return self.default_action(state)

    def _street_to_ppe(self, street: Street) -> str:
        """Convert street enum to PyPokerEngine string."""
        mapping = {
            Street.PREFLOP: 'preflop',
            Street.FLOP: 'flop',
            Street.TURN: 'turn',
            Street.RIVER: 'river',
            Street.SHOWDOWN: 'showdown'
        }
        return mapping.get(street, 'preflop')

    def get_name(self) -> str:
        if self._engine_available:
            return f"ExternalEngineBot({self.external_bot_class})"
        return "ExternalEngineBot(fallback)"


# ============================================================================
# PyPokerEngine Bot Adapters
# ============================================================================

class BasePPEAdapter:
    """Base adapter for PyPokerEngine-style players."""

    def declare_action(
        self,
        valid_actions: List[Dict],
        hole_card: List[str],
        round_state: Dict
    ) -> Tuple[str, int]:
        """
        Declare action in PyPokerEngine format.
        Returns (action_type, amount).
        """
        raise NotImplementedError


class HonestPlayerAdapter(BasePPEAdapter):
    """
    Plays honestly based on hand strength.
    Raises with strong hands, calls with medium, folds weak.
    """

    def declare_action(self, valid_actions, hole_card, round_state) -> Tuple[str, int]:
        try:
            from pypokerengine.utils.card_utils import gen_cards, estimate_hole_card_win_rate

            community = gen_cards(round_state.get('community_card', []))
            hole = gen_cards(hole_card)

            # Estimate win rate with Monte Carlo (100 simulations for speed)
            win_rate = estimate_hole_card_win_rate(
                nb_simulation=100,
                nb_player=len([s for s in round_state.get('seats', [])
                              if s['state'] == 'participating']),
                hole_card=hole,
                community_card=community
            )

            # Decision logic
            if win_rate >= 0.7:
                # Strong - raise
                for action in valid_actions:
                    if action['action'] == 'raise':
                        amount = action['amount']
                        if isinstance(amount, dict):
                            raise_amount = int(amount['min'] * 1.5)
                            raise_amount = min(raise_amount, amount['max'])
                            return ('raise', raise_amount)
                        return ('raise', amount)

            if win_rate >= 0.4:
                # Medium - call
                for action in valid_actions:
                    if action['action'] == 'call':
                        return ('call', action['amount'])

            # Weak - check or fold
            for action in valid_actions:
                if action['action'] == 'call' and action['amount'] == 0:
                    return ('call', 0)  # Check

            return ('fold', 0)

        except Exception:
            # Fallback: just call
            for action in valid_actions:
                if action['action'] == 'call':
                    return ('call', action['amount'])
            return ('fold', 0)


class FishPlayerAdapter(BasePPEAdapter):
    """Loose passive player - calls too much, rarely raises."""

    def declare_action(self, valid_actions, hole_card, round_state) -> Tuple[str, int]:
        import random

        # 80% call, 15% fold, 5% raise
        roll = random.random()

        if roll < 0.80:
            for action in valid_actions:
                if action['action'] == 'call':
                    return ('call', action['amount'])
        elif roll < 0.95:
            for action in valid_actions:
                if action['action'] == 'call' and action['amount'] == 0:
                    return ('call', 0)
            return ('fold', 0)
        else:
            for action in valid_actions:
                if action['action'] == 'raise':
                    amount = action['amount']
                    if isinstance(amount, dict):
                        return ('raise', amount['min'])
                    return ('raise', amount)

        # Fallback
        for action in valid_actions:
            if action['action'] == 'call':
                return ('call', action['amount'])
        return ('fold', 0)


class FoldPlayerAdapter(BasePPEAdapter):
    """Always folds (or checks if possible)."""

    def declare_action(self, valid_actions, hole_card, round_state) -> Tuple[str, int]:
        for action in valid_actions:
            if action['action'] == 'call' and action['amount'] == 0:
                return ('call', 0)  # Check
        return ('fold', 0)


class CallPlayerAdapter(BasePPEAdapter):
    """Always calls (or checks)."""

    def declare_action(self, valid_actions, hole_card, round_state) -> Tuple[str, int]:
        for action in valid_actions:
            if action['action'] == 'call':
                return ('call', action['amount'])
        return ('fold', 0)


class RaisePlayerAdapter(BasePPEAdapter):
    """Always raises when possible."""

    def declare_action(self, valid_actions, hole_card, round_state) -> Tuple[str, int]:
        for action in valid_actions:
            if action['action'] == 'raise':
                amount = action['amount']
                if isinstance(amount, dict):
                    return ('raise', amount['min'])
                return ('raise', amount)

        for action in valid_actions:
            if action['action'] == 'call':
                return ('call', action['amount'])
        return ('fold', 0)


# ============================================================================
# Convenience function for external bot creation
# ============================================================================

def create_external_bot(
    bot_type: str = 'honest',
    seat: int = 0,
    **kwargs
) -> ExternalEngineBot:
    """
    Create an external engine bot with specified type.

    Args:
        bot_type: One of 'honest', 'fish', 'fold', 'call', 'raise'
        seat: Seat index
        **kwargs: Additional arguments passed to bot

    Returns:
        ExternalEngineBot instance

    Example:
        bot = create_external_bot('honest', seat=2)
        action = bot.get_action(game_state)
    """
    return ExternalEngineBot(
        seat=seat,
        external_bot_class=bot_type,
        **kwargs
    )
