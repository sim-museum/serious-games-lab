"""
Improved Equity Bot for PokerIQ.

More sophisticated decision-making including:
- Position-aware preflop ranges
- Board texture analysis
- Draw recognition and semi-bluffing
- Continuation betting
- Check-raising
- Mixed strategies for balance

This bot implements a more GTO-aware strategy while
remaining computationally lightweight.
"""

from typing import Optional, Dict, Any, Set, Tuple
import random

from .base_bot import BaseBot
from ..models import GameState, Action, ActionType, Street, Position, Hand, Card
from ..evaluator import HandEvaluator, HandRank, DrawEvaluator
from ..equity import EquityCalculator, PreflopEquity, quick_equity
from ..constants import (
    PREMIUM_HANDS, STRONG_HANDS, PLAYABLE_HANDS,
    OPEN_RANGES, THREE_BET_RANGES, CALL_3BET_RANGE,
    EQUITY_THRESHOLDS, BET_SIZING, MIXED_STRATEGIES,
    canonicalize_hand
)


class ImprovedEquityBot(BaseBot):
    """
    Position-aware poker bot with preflop ranges and postflop heuristics.

    Key improvements over BasicEquityBot:
    1. Position-dependent opening ranges
    2. Board texture analysis (wet vs dry)
    3. Draw detection and semi-bluffing
    4. Continuation betting with appropriate sizing
    5. Check-raising for value and as bluff
    6. Mixed strategies for unpredictability

    The bot uses a mix of:
    - Equity calculations (Monte Carlo)
    - Preflop range charts
    - Heuristic rules for common spots
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

        # Track aggression for this hand
        self.was_preflop_raiser = False
        self.last_aggressor = False

        # Config
        cfg = config or {}
        self.aggression = cfg.get('aggression', 0.6)
        self.cbet_frequency = cfg.get('cbet_frequency', 0.65)
        self.check_raise_frequency = cfg.get('check_raise_frequency', 0.08)

    def on_hand_start(self, state: GameState) -> None:
        """Reset per-hand tracking."""
        super().on_hand_start(state)
        self.was_preflop_raiser = False
        self.last_aggressor = False

    def get_action(self, state: GameState) -> Action:
        """
        Main decision method with street-specific logic.
        """
        hole_cards = self.get_hole_cards(state)
        if hole_cards is None:
            return self.default_action(state)

        if state.street == Street.PREFLOP:
            return self._preflop_action(state, hole_cards)
        else:
            return self._postflop_action(state, hole_cards)

    # ========================================================================
    # PREFLOP LOGIC
    # ========================================================================

    def _preflop_action(self, state: GameState, hole_cards: Hand) -> Action:
        """
        Preflop decision using position-based ranges.
        """
        position = state.get_position(self.seat)
        hand_str = self._canonicalize_hand(hole_cards)
        to_call = self.get_to_call(state)
        pot = state.pot

        self.log(f"Preflop: {hand_str} in {position.name}, to_call={to_call}")

        # Determine situation
        is_unopened = (state.current_bet == state.big_blind)
        facing_raise = (state.current_bet > state.big_blind)
        facing_3bet = (state.current_bet >= state.big_blind * 6)

        # --- Unopened pot: Open or fold ---
        if is_unopened and to_call <= state.big_blind:
            return self._open_raise_decision(state, hand_str, position)

        # --- Facing open raise: Call, 3-bet, or fold ---
        if facing_raise and not facing_3bet:
            return self._vs_raise_decision(state, hand_str, position)

        # --- Facing 3-bet: Call, 4-bet, or fold ---
        if facing_3bet:
            return self._vs_3bet_decision(state, hand_str)

        # Fallback
        if to_call == 0:
            return self.make_check()
        return self.make_fold()

    def _open_raise_decision(self, state: GameState, hand_str: str, position: Position) -> Action:
        """
        Decide whether to open raise from this position.
        """
        pos_name = self._position_to_range_key(position)
        open_range = OPEN_RANGES.get(pos_name, set())

        if hand_str in open_range:
            # Open raise
            self.was_preflop_raiser = True
            self.last_aggressor = True

            # Size based on position
            if position.is_late():
                raise_size = int(state.big_blind * 2.5)
            else:
                raise_size = int(state.big_blind * 3)

            return self.make_bet(raise_size, state)

        # Not in open range - fold or limp speculative hands
        if hand_str in PLAYABLE_HANDS and position.is_late():
            # Sometimes limp speculative hands
            if self.random_choice(0.3):
                return self.make_call(state)

        return self.make_fold()

    def _vs_raise_decision(self, state: GameState, hand_str: str, position: Position) -> Action:
        """
        Decide action when facing an open raise.
        """
        to_call = self.get_to_call(state)
        raise_size = state.current_bet

        # 3-bet value hands
        if hand_str in THREE_BET_RANGES['value']:
            if self.random_choice(MIXED_STRATEGIES['3bet_with_value_hand']):
                self.last_aggressor = True
                raise_to = int(state.current_bet * 3)
                return self.make_raise(raise_to, state)
            # Sometimes just call to trap
            return self.make_call(state)

        # 3-bet bluff hands (with position)
        if hand_str in THREE_BET_RANGES['bluff'] and position.is_late():
            if self.random_choice(MIXED_STRATEGIES['3bet_with_bluff_hand']):
                self.last_aggressor = True
                raise_to = int(state.current_bet * 3)
                return self.make_raise(raise_to, state)

        # Call with calling range
        if hand_str in CALL_3BET_RANGE:
            return self.make_call(state)

        # Call with suited connectors and small pairs if good odds
        if hand_str in PLAYABLE_HANDS:
            if to_call <= state.big_blind * 3:
                return self.make_call(state)

        return self.make_fold()

    def _vs_3bet_decision(self, state: GameState, hand_str: str) -> Action:
        """
        Decide action when facing a 3-bet.
        """
        # Only continue with premium hands
        if hand_str in PREMIUM_HANDS:
            if hand_str in {'AA', 'KK'}:
                # 4-bet
                self.last_aggressor = True
                raise_to = int(state.current_bet * 2.5)
                return self.make_raise(raise_to, state)
            # Call with other premiums
            return self.make_call(state)

        if hand_str in CALL_3BET_RANGE:
            return self.make_call(state)

        return self.make_fold()

    # ========================================================================
    # POSTFLOP LOGIC
    # ========================================================================

    def _postflop_action(self, state: GameState, hole_cards: Hand) -> Action:
        """
        Postflop decision with board texture and draw awareness.
        """
        # Calculate hand strength and draws
        equity = quick_equity(hole_cards, state.board, state.players_in_pot() - 1)
        hand_score = self.evaluator.evaluate(hole_cards, state.board)
        hand_rank = self.evaluator.get_rank(hand_score)

        # Analyze draws
        has_draw = DrawEvaluator.is_draw(hole_cards, state.board)
        total_outs = DrawEvaluator.total_outs(hole_cards, state.board)

        # Board texture
        is_wet = self._is_wet_board(state.board)

        to_call = self.get_to_call(state)
        pot_odds = self.get_pot_odds(state)

        self.log(f"{state.street.name}: equity={equity:.2f}, rank={hand_rank}, "
                 f"draw={has_draw}, wet={is_wet}")

        # --- No bet facing ---
        if to_call == 0:
            return self._act_when_checked_to(
                state, equity, hand_rank, has_draw, total_outs, is_wet
            )

        # --- Facing a bet ---
        return self._act_vs_bet(
            state, equity, hand_rank, has_draw, total_outs, pot_odds
        )

    def _act_when_checked_to(
        self,
        state: GameState,
        equity: float,
        hand_rank: HandRank,
        has_draw: bool,
        outs: int,
        is_wet: bool
    ) -> Action:
        """
        Decide action when checked to us.
        """
        pot = state.pot

        # --- Continuation bet logic ---
        if state.street == Street.FLOP and self.was_preflop_raiser:
            return self._continuation_bet(state, equity, hand_rank, is_wet)

        # --- Value betting with strong hands ---
        if equity >= EQUITY_THRESHOLDS['value_bet_flop']:
            # Sometimes check to trap with monsters
            if equity >= 0.85 and self.random_choice(MIXED_STRATEGIES['check_strong_hand']):
                return self.make_check()

            bet_size = self._choose_bet_size(state, equity, is_wet)
            self.last_aggressor = True
            return self.make_bet(bet_size, state)

        # --- Semi-bluff with draws ---
        if has_draw and outs >= 8:
            if self.random_choice(0.6):
                bet_size = int(pot * BET_SIZING['bluff_medium'])
                self.last_aggressor = True
                return self.make_bet(bet_size, state)

        # --- Bluff with weak hands (occasionally) ---
        if equity < 0.30 and self.random_choice(self.aggression * 0.3):
            bet_size = int(pot * BET_SIZING['bluff_small'])
            return self.make_bet(bet_size, state)

        return self.make_check()

    def _continuation_bet(
        self,
        state: GameState,
        equity: float,
        hand_rank: HandRank,
        is_wet: bool
    ) -> Action:
        """
        Decide on continuation bet.
        """
        pot = state.pot
        heads_up = state.players_in_pot() == 2

        # More c-bets heads-up
        cbet_threshold = EQUITY_THRESHOLDS['cbet_heads_up'] if heads_up else EQUITY_THRESHOLDS['cbet_multiway']

        # C-bet with equity or sometimes as bluff
        if equity >= cbet_threshold or self.random_choice(MIXED_STRATEGIES['cbet_when_missed']):
            if is_wet:
                bet_size = int(pot * BET_SIZING['cbet_wet'])
            else:
                bet_size = int(pot * BET_SIZING['cbet_dry'])

            self.last_aggressor = True
            return self.make_bet(bet_size, state)

        return self.make_check()

    def _act_vs_bet(
        self,
        state: GameState,
        equity: float,
        hand_rank: HandRank,
        has_draw: bool,
        outs: int,
        pot_odds: float
    ) -> Action:
        """
        Decide action when facing a bet.
        """
        to_call = self.get_to_call(state)

        # --- Strong value raise ---
        if equity >= 0.75:
            self.last_aggressor = True
            raise_to = int(state.current_bet * 2.5)
            return self.make_raise(raise_to, state)

        # --- Check-raise with very strong hands ---
        if equity >= EQUITY_THRESHOLDS['check_raise_value']:
            if self.random_choice(self.check_raise_frequency):
                raise_to = int(state.current_bet * 3)
                self.last_aggressor = True
                return self.make_raise(raise_to, state)

        # --- Standard equity vs pot odds ---
        if equity > pot_odds:
            # Raise sometimes for value
            if equity >= 0.55 and self.random_choice(0.25):
                raise_to = int(state.current_bet * 2.5)
                self.last_aggressor = True
                return self.make_raise(raise_to, state)
            return self.make_call(state)

        # --- Draw odds ---
        if has_draw:
            # Calculate draw equity from outs
            draw_equity = self._outs_to_equity(outs, state.street)
            implied_equity = draw_equity * 1.3  # Implied odds bonus

            if implied_equity > pot_odds:
                return self.make_call(state)

            # Semi-bluff raise with big draws
            if outs >= 12 and self.random_choice(0.3):
                raise_to = int(state.current_bet * 2.5)
                self.last_aggressor = True
                return self.make_raise(raise_to, state)

        # --- River bluff catch ---
        if state.street == Street.RIVER:
            if equity > pot_odds - 0.05:  # Slightly worse than odds but can catch bluffs
                if self.random_choice(0.3):
                    return self.make_call(state)

        return self.make_fold()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _canonicalize_hand(self, hole_cards: Hand) -> str:
        """Convert hole cards to canonical string."""
        if len(hole_cards.cards) != 2:
            return ""
        c1, c2 = hole_cards.cards
        return canonicalize_hand(str(c1), str(c2))

    def _position_to_range_key(self, position: Position) -> str:
        """Map position enum to range chart key."""
        mapping = {
            Position.BTN: 'BTN',
            Position.SB: 'SB',
            Position.BB: 'BB',
            Position.UTG: 'UTG',
            Position.UTG1: 'UTG1',
            Position.MP: 'MP',
            Position.MP1: 'MP1',
            Position.CO: 'CO',
        }
        return mapping.get(position, 'UTG')

    def _is_wet_board(self, board: list) -> bool:
        """
        Determine if board is wet (draw-heavy) or dry.
        """
        if len(board) < 3:
            return False

        # Check for flush draws
        suits = [c.suit for c in board]
        suit_counts = {}
        for s in suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        if max(suit_counts.values()) >= 2:
            return True

        # Check for straight draws
        ranks = sorted([c.rank.value for c in board])
        for i in range(len(ranks) - 1):
            if ranks[i+1] - ranks[i] <= 2:  # Connected or one-gap
                return True

        return False

    def _choose_bet_size(self, state: GameState, equity: float, is_wet: bool) -> int:
        """
        Choose bet size based on situation.
        """
        pot = state.pot

        if state.street == Street.RIVER:
            # Larger bets on river for value
            if equity >= 0.80:
                return int(pot * BET_SIZING['value_bet_large'])
            return int(pot * BET_SIZING['value_bet_medium'])

        if is_wet:
            # Larger on wet boards to deny draws equity
            return int(pot * BET_SIZING['cbet_wet'])

        return int(pot * BET_SIZING['value_bet_small'])

    def _outs_to_equity(self, outs: int, street: Street) -> float:
        """
        Convert number of outs to approximate equity.
        Uses the "rule of 2 and 4":
        - Flop: outs * 4 (two cards to come)
        - Turn: outs * 2 (one card to come)
        """
        if street == Street.FLOP:
            return min(outs * 0.04, 0.50)  # Cap at 50%
        elif street == Street.TURN:
            return min(outs * 0.02, 0.50)
        return 0.0

    def get_name(self) -> str:
        return "ImprovedEquityBot"
