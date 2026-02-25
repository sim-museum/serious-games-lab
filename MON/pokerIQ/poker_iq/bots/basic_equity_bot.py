"""
Basic Equity Bot for PokerIQ.

Simple decision-making based on:
- Hand equity estimation
- Pot odds comparison
- Basic betting patterns

No position awareness or opponent modeling.
Good baseline for comparison and debugging.
"""

from typing import Optional, Dict, Any

from .base_bot import BaseBot
from ..models import GameState, Action, ActionType, Street
from ..evaluator import HandEvaluator, HandRank
from ..equity import EquityCalculator, PreflopEquity, quick_equity


class BasicEquityBot(BaseBot):
    """
    Simple equity-based poker bot.

    Decision algorithm:
    1. Calculate equity (win probability)
    2. Compare to pot odds for calling
    3. Bet/raise with strong hands, call with marginal, fold weak

    Thresholds:
    - Strong hand: equity > 0.65 -> bet/raise
    - Marginal: equity > pot_odds -> call
    - Weak: equity < pot_odds -> fold

    This bot does NOT consider:
    - Position
    - Opponent tendencies
    - Board texture
    - Draw potential
    """

    def __init__(
        self,
        seat: int = 0,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(seat=seat, config=config, **kwargs)

        self.evaluator = HandEvaluator()
        self.equity_calc = EquityCalculator(self.evaluator)

        # Thresholds (configurable)
        cfg = config or {}
        self.strong_threshold = cfg.get('strong_threshold', 0.65)
        self.medium_threshold = cfg.get('medium_threshold', 0.50)
        self.bluff_frequency = cfg.get('bluff_frequency', 0.10)

    def get_action(self, state: GameState) -> Action:
        """
        Main decision method using equity-based logic.
        """
        hole_cards = self.get_hole_cards(state)
        if hole_cards is None:
            return self.default_action(state)

        # Calculate equity
        num_opponents = state.players_in_pot() - 1
        equity = quick_equity(hole_cards, state.board, max(1, num_opponents))

        self.log(f"Street: {state.street.name}, Equity: {equity:.2f}")

        # Route to appropriate decision method
        if state.street == Street.PREFLOP:
            return self._preflop_action(state, equity)
        else:
            return self._postflop_action(state, equity)

    def _preflop_action(self, state: GameState, equity: float) -> Action:
        """
        Preflop decision based on hand strength.
        """
        to_call = self.get_to_call(state)
        pot = state.pot

        # Premium hands - always raise/reraise
        if equity >= 0.75:  # AA, KK, QQ, AK
            if to_call == 0 or to_call == state.big_blind:
                # Open raise or raise limpers
                raise_amount = state.big_blind * 3
                return self.make_bet(raise_amount, state)
            else:
                # 3-bet
                raise_to = state.current_bet * 3
                return self.make_raise(raise_to, state)

        # Strong hands - raise or call
        if equity >= 0.60:  # JJ, TT, AQ, etc.
            if to_call == 0:
                # Open raise
                raise_amount = state.big_blind * 2.5
                return self.make_bet(int(raise_amount), state)
            elif to_call <= state.big_blind * 3:
                # Call reasonable raises
                return self.make_call(state)
            else:
                # Large raise - call with best, fold rest
                if equity >= 0.70:
                    return self.make_call(state)
                return self.make_fold()

        # Playable hands
        if equity >= 0.45:
            if to_call == 0:
                # Check/limp
                return self.make_check() if self.can_check(state) else self.make_call(state)
            elif to_call <= state.big_blind * 2:
                # Call small raise
                return self.make_call(state)
            else:
                return self.make_fold()

        # Weak hands
        if to_call == 0:
            return self.make_check() if self.can_check(state) else self.make_fold()

        return self.make_fold()

    def _postflop_action(self, state: GameState, equity: float) -> Action:
        """
        Postflop decision using equity vs pot odds.
        """
        to_call = self.get_to_call(state)
        pot = state.pot
        pot_odds = self.get_pot_odds(state)

        self.log(f"Pot odds: {pot_odds:.2f}, To call: {to_call}")

        # No bet to face - check or bet
        if to_call == 0:
            return self._decide_bet(state, equity)

        # Facing a bet - call, raise, or fold
        return self._decide_vs_bet(state, equity, pot_odds)

    def _decide_bet(self, state: GameState, equity: float) -> Action:
        """
        Decide whether to bet when checked to.
        """
        pot = state.pot

        # Strong hand - value bet
        if equity >= self.strong_threshold:
            # Bet 60-80% of pot
            bet_size = int(pot * 0.70)
            return self.make_bet(bet_size, state)

        # Medium hand - sometimes bet for value/protection
        if equity >= self.medium_threshold:
            if self.random_choice(0.5):
                bet_size = int(pot * 0.50)
                return self.make_bet(bet_size, state)
            return self.make_check()

        # Weak hand - occasionally bluff
        if self.random_choice(self.bluff_frequency):
            bet_size = int(pot * 0.50)
            return self.make_bet(bet_size, state)

        return self.make_check()

    def _decide_vs_bet(self, state: GameState, equity: float, pot_odds: float) -> Action:
        """
        Decide action when facing a bet.
        """
        # Strong hand - raise for value
        if equity >= 0.75:
            raise_to = int(state.current_bet * 2.5)
            return self.make_raise(raise_to, state)

        # Have enough equity to call
        if equity > pot_odds + 0.05:  # Small margin for implied odds
            # Raise sometimes with strong-ish hands
            if equity >= 0.60 and self.random_choice(0.25):
                raise_to = int(state.current_bet * 2.5)
                return self.make_raise(raise_to, state)
            return self.make_call(state)

        # Marginal situation - sometimes call with draws
        if equity > pot_odds - 0.10:
            # Call with implied odds consideration
            spr = self.get_stack_to_pot_ratio(state)
            if spr > 2.0:  # Deep stacks = more implied odds
                if self.random_choice(0.4):
                    return self.make_call(state)

        return self.make_fold()

    def get_name(self) -> str:
        return "BasicEquityBot"
