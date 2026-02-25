"""
Base bot interface for PokerIQ.

All bot implementations should inherit from BaseBot.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import random

from ..models import GameState, Action, ActionType, Hand, Card, PlayerState


class BaseBot(ABC):
    """
    Abstract base class for all poker bots.

    Subclasses must implement:
    - get_action(): Main decision method

    Optional overrides:
    - preflop_action(): Preflop-specific logic
    - postflop_action(): Postflop-specific logic
    - on_hand_start(): Called when a new hand begins
    - on_hand_end(): Called when hand is complete
    """

    def __init__(
        self,
        seat: int = 0,
        config: Optional[Dict[str, Any]] = None,
        random_seed: Optional[int] = None,
        verbose: bool = False
    ):
        """
        Initialize the bot.

        Args:
            seat: Seat index (0-indexed)
            config: Bot configuration parameters
            random_seed: Seed for reproducibility
            verbose: Enable debug output
        """
        self.seat = seat
        self.config = config or {}
        self.verbose = verbose

        # Initialize random state
        self.rng = random.Random(random_seed)

        # Track state across hand
        self.hand_history: List[Dict[str, Any]] = []
        self.current_hand_id = 0

    @abstractmethod
    def get_action(self, state: GameState) -> Action:
        """
        Determine the action to take given the game state.

        Args:
            state: Current game state with all relevant information

        Returns:
            Action to take (fold, check, call, bet, raise, all_in)
        """
        pass

    def get_name(self) -> str:
        """Return bot name for display."""
        return self.__class__.__name__

    def get_hole_cards(self, state: GameState) -> Optional[Hand]:
        """Get this bot's hole cards from the game state."""
        player = state.players[self.seat]
        return player.hole_cards

    def get_player(self, state: GameState) -> PlayerState:
        """Get this bot's player state."""
        return state.players[self.seat]

    def on_hand_start(self, state: GameState) -> None:
        """
        Called when a new hand begins.
        Override to initialize per-hand state.
        """
        self.current_hand_id += 1
        self.hand_history.append({
            'hand_id': self.current_hand_id,
            'actions': []
        })

    def on_hand_end(self, state: GameState, result: Dict[str, Any]) -> None:
        """
        Called when hand is complete.
        Override to learn from results.

        Args:
            state: Final game state
            result: Dict with 'winner', 'pot', 'showdown_hands', etc.
        """
        if self.hand_history:
            self.hand_history[-1]['result'] = result

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{self.get_name()}@{self.seat}] {message}")

    # ========================================================================
    # Utility methods for decision making
    # ========================================================================

    def get_legal_actions(self, state: GameState) -> List[Action]:
        """Get all legal actions for this bot."""
        return state.get_legal_actions(self.seat)

    def can_check(self, state: GameState) -> bool:
        """Check if checking is legal."""
        return state.get_to_call(self.seat) == 0

    def get_to_call(self, state: GameState) -> int:
        """Get amount needed to call."""
        return state.get_to_call(self.seat)

    def get_pot_odds(self, state: GameState) -> float:
        """Get pot odds for calling."""
        return state.get_pot_odds(self.seat)

    def get_stack(self, state: GameState) -> int:
        """Get current stack size."""
        return state.players[self.seat].stack

    def get_effective_stack(self, state: GameState) -> int:
        """Get effective stack (including current bet)."""
        return state.get_effective_stack(self.seat)

    def get_stack_to_pot_ratio(self, state: GameState) -> float:
        """
        Get stack-to-pot ratio (SPR).
        Lower SPR = more committed to pot.
        """
        if state.pot == 0:
            return float('inf')
        return self.get_effective_stack(state) / state.pot

    def random_choice(self, probability: float) -> bool:
        """
        Make a random choice with given probability.
        Used for mixed strategies.
        """
        return self.rng.random() < probability

    def weighted_choice(self, options: List[Any], weights: List[float]) -> Any:
        """
        Choose from options with given weights.
        """
        return self.rng.choices(options, weights=weights, k=1)[0]

    # ========================================================================
    # Action construction helpers
    # ========================================================================

    def make_fold(self) -> Action:
        """Create fold action."""
        return Action.fold()

    def make_check(self) -> Action:
        """Create check action."""
        return Action.check()

    def make_call(self, state: GameState) -> Action:
        """Create call action with correct amount."""
        to_call = min(self.get_to_call(state), self.get_stack(state))
        return Action.call(to_call)

    def make_bet(self, amount: int, state: GameState) -> Action:
        """Create bet action, ensuring it's legal."""
        stack = self.get_stack(state)
        if amount >= stack:
            return Action.all_in(stack)
        return Action.bet(max(amount, state.big_blind))

    def make_raise(self, raise_to: int, state: GameState) -> Action:
        """Create raise action, ensuring it's legal."""
        stack = self.get_stack(state)
        current_bet = state.players[self.seat].current_bet

        if raise_to >= stack + current_bet:
            return Action.all_in(stack + current_bet)

        min_raise = state.current_bet + state.min_raise
        return Action.raise_to(max(raise_to, min_raise))

    def make_pot_sized_bet(self, state: GameState, multiplier: float = 1.0) -> Action:
        """
        Create a bet/raise that is a fraction of the pot.

        Args:
            state: Game state
            multiplier: Fraction of pot (1.0 = pot-sized)
        """
        bet_amount = int(state.pot * multiplier)
        if state.current_bet == 0:
            return self.make_bet(bet_amount, state)
        else:
            # For raise, calculate total to put in
            raise_to = state.current_bet + bet_amount
            return self.make_raise(raise_to, state)

    # ========================================================================
    # Default fallback behavior
    # ========================================================================

    def default_action(self, state: GameState) -> Action:
        """
        Default action when bot can't decide.
        Checks if possible, otherwise folds.
        """
        if self.can_check(state):
            return self.make_check()
        return self.make_fold()
