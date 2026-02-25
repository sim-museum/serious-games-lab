"""
Equity calculation for Texas Hold'em.

Provides Monte Carlo simulation for hand equity estimation.
Pure Python implementation with no external dependencies.
Lightweight and runs in memory without large lookup tables.
"""

import random
from typing import List, Tuple, Optional, Set
from functools import lru_cache

from .models import Card, Hand, GameState, Street, Rank, Suit, create_deck
from .evaluator import HandEvaluator


class EquityCalculator:
    """
    Monte Carlo equity calculator for Texas Hold'em.

    Estimates win probability by simulating random runouts.

    Usage:
        calc = EquityCalculator()
        equity = calc.calculate_equity(hole_cards, board, num_opponents=2)
        # equity is a float between 0.0 and 1.0
    """

    def __init__(self, evaluator: Optional[HandEvaluator] = None):
        """
        Initialize the calculator.

        Args:
            evaluator: Hand evaluator instance. Created if not provided.
        """
        self.evaluator = evaluator or HandEvaluator()

    def calculate_equity(
        self,
        hole_cards: Hand,
        board: List[Card],
        num_opponents: int = 1,
        num_simulations: int = 1000,
        opponent_ranges: Optional[List[Set[Tuple[Card, Card]]]] = None,
        seed: Optional[int] = None
    ) -> float:
        """
        Calculate equity (win probability) against random opponent hands.

        Args:
            hole_cards: Hero's hole cards
            board: Current board (0-5 cards)
            num_opponents: Number of opponents
            num_simulations: Number of Monte Carlo simulations
            opponent_ranges: Optional list of hand ranges for each opponent
            seed: Random seed for reproducibility

        Returns:
            Float between 0.0 and 1.0 representing win probability
        """
        if seed is not None:
            random.seed(seed)

        # Build deck of remaining cards
        used_cards = set(hole_cards.cards) | set(board)
        remaining_deck = [
            Card.from_code(i) for i in range(52)
            if Card.from_code(i) not in used_cards
        ]

        wins = 0
        ties = 0
        total = 0

        for _ in range(num_simulations):
            # Shuffle remaining deck
            random.shuffle(remaining_deck)
            deck_idx = 0

            # Deal opponent hands
            opponent_hands = []
            for _ in range(num_opponents):
                opp_hand = Hand([remaining_deck[deck_idx], remaining_deck[deck_idx + 1]])
                deck_idx += 2
                opponent_hands.append(opp_hand)

            # Complete the board if needed
            sim_board = list(board)
            while len(sim_board) < 5:
                sim_board.append(remaining_deck[deck_idx])
                deck_idx += 1

            # Evaluate all hands
            hero_score = self.evaluator.evaluate(hole_cards, sim_board)

            hero_wins = True
            hero_ties = True
            for opp_hand in opponent_hands:
                opp_score = self.evaluator.evaluate(opp_hand, sim_board)
                if opp_score > hero_score:
                    hero_wins = False
                    hero_ties = False
                    break
                elif opp_score == hero_score:
                    hero_wins = False
                else:
                    hero_ties = False

            if hero_wins:
                wins += 1
            elif hero_ties:
                ties += 1
            total += 1

        # Equity = wins + ties/2 (split pot assumption)
        equity = (wins + ties * 0.5) / total if total > 0 else 0.0
        return equity

    def calculate_equity_vs_range(
        self,
        hole_cards: Hand,
        board: List[Card],
        opponent_range: Set[str],
        num_simulations: int = 500
    ) -> float:
        """
        Calculate equity against a specific range of hands.

        Args:
            hole_cards: Hero's hole cards
            board: Current board
            opponent_range: Set of hand strings like {'AA', 'KK', 'AKs', ...}
            num_simulations: Number of simulations

        Returns:
            Equity as float 0.0-1.0
        """
        from .constants import canonicalize_hand

        used_cards = set(hole_cards.cards) | set(board)
        remaining_deck = [
            Card.from_code(i) for i in range(52)
            if Card.from_code(i) not in used_cards
        ]

        # Generate all possible opponent hands in range
        valid_opp_hands = []
        for i, c1 in enumerate(remaining_deck):
            for c2 in remaining_deck[i+1:]:
                hand_str = canonicalize_hand(str(c1), str(c2))
                if hand_str in opponent_range:
                    valid_opp_hands.append((c1, c2))

        if not valid_opp_hands:
            return 0.5  # No valid opponent hands, assume 50%

        wins = 0
        ties = 0
        total = 0

        for _ in range(num_simulations):
            # Pick random opponent hand from range
            opp_cards = random.choice(valid_opp_hands)
            opp_hand = Hand(list(opp_cards))

            # Build deck without used cards
            sim_deck = [c for c in remaining_deck if c not in opp_cards]
            random.shuffle(sim_deck)

            # Complete board
            sim_board = list(board)
            deck_idx = 0
            while len(sim_board) < 5:
                sim_board.append(sim_deck[deck_idx])
                deck_idx += 1

            # Compare hands
            hero_score = self.evaluator.evaluate(hole_cards, sim_board)
            opp_score = self.evaluator.evaluate(opp_hand, sim_board)

            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            total += 1

        return (wins + ties * 0.5) / total if total > 0 else 0.5

    def pot_odds_to_equity(self, pot: int, to_call: int) -> float:
        """
        Calculate required equity to call based on pot odds.

        Args:
            pot: Current pot size
            to_call: Amount needed to call

        Returns:
            Minimum equity needed to call profitably
        """
        if to_call <= 0:
            return 0.0
        return to_call / (pot + to_call)

    def implied_odds_equity(
        self,
        pot: int,
        to_call: int,
        implied_winnings: int
    ) -> float:
        """
        Calculate required equity considering implied odds.

        Args:
            pot: Current pot
            to_call: Amount to call
            implied_winnings: Expected additional winnings when hitting

        Returns:
            Minimum equity considering implied odds
        """
        if to_call <= 0:
            return 0.0
        total_potential = pot + to_call + implied_winnings
        return to_call / total_potential


class PreflopEquity:
    """
    Preflop hand strength estimation using simplified lookup.

    Uses precomputed approximate equity values for common matchups.
    Fast enough for real-time use without Monte Carlo simulation.
    """

    # Approximate equity for hand categories vs random hand
    # Based on statistical averages
    HAND_EQUITY_VS_RANDOM = {
        # Premium pairs
        'AA': 0.85, 'KK': 0.82, 'QQ': 0.80, 'JJ': 0.77,
        # Medium pairs
        'TT': 0.75, '99': 0.72, '88': 0.69, '77': 0.66,
        # Small pairs
        '66': 0.63, '55': 0.60, '44': 0.57, '33': 0.54, '22': 0.51,
        # Ace-high suited
        'AKs': 0.67, 'AQs': 0.66, 'AJs': 0.65, 'ATs': 0.64,
        'A9s': 0.62, 'A8s': 0.61, 'A7s': 0.60, 'A6s': 0.59,
        'A5s': 0.60, 'A4s': 0.59, 'A3s': 0.58, 'A2s': 0.57,
        # Ace-high offsuit
        'AKo': 0.65, 'AQo': 0.63, 'AJo': 0.62, 'ATo': 0.61,
        'A9o': 0.58, 'A8o': 0.57, 'A7o': 0.56, 'A6o': 0.55,
        'A5o': 0.56, 'A4o': 0.55, 'A3o': 0.54, 'A2o': 0.53,
        # King-high suited
        'KQs': 0.63, 'KJs': 0.62, 'KTs': 0.61, 'K9s': 0.59,
        'K8s': 0.57, 'K7s': 0.56, 'K6s': 0.55, 'K5s': 0.54,
        # King-high offsuit
        'KQo': 0.60, 'KJo': 0.59, 'KTo': 0.57, 'K9o': 0.55,
        # Queen-high suited
        'QJs': 0.60, 'QTs': 0.59, 'Q9s': 0.57, 'Q8s': 0.54,
        # Queen-high offsuit
        'QJo': 0.57, 'QTo': 0.55, 'Q9o': 0.53,
        # Suited connectors
        'JTs': 0.57, 'T9s': 0.54, '98s': 0.51, '87s': 0.49,
        '76s': 0.47, '65s': 0.45, '54s': 0.44, '43s': 0.41,
        # Offsuit connectors
        'JTo': 0.53, 'T9o': 0.50, '98o': 0.47, '87o': 0.45,
        '76o': 0.43, '65o': 0.41, '54o': 0.40,
        # Suited gappers
        'J9s': 0.53, 'T8s': 0.51, '97s': 0.48, '86s': 0.46,
        '75s': 0.44, '64s': 0.42, '53s': 0.41,
    }

    # Default equity for hands not in lookup
    DEFAULT_EQUITY = 0.35

    @classmethod
    def get_equity(cls, hand_str: str) -> float:
        """
        Get preflop equity vs random hand.

        Args:
            hand_str: Canonical hand string like 'AKs', 'JJ', 'T9o'

        Returns:
            Equity as float 0.0-1.0
        """
        return cls.HAND_EQUITY_VS_RANDOM.get(hand_str, cls.DEFAULT_EQUITY)

    @classmethod
    def get_equity_from_cards(cls, hole_cards: Hand) -> float:
        """
        Get preflop equity from actual cards.
        """
        from .constants import canonicalize_hand

        if len(hole_cards.cards) != 2:
            return 0.35

        c1, c2 = hole_cards.cards
        hand_str = canonicalize_hand(str(c1), str(c2))
        return cls.get_equity(hand_str)

    @classmethod
    def adjust_for_opponents(cls, base_equity: float, num_opponents: int) -> float:
        """
        Adjust equity based on number of opponents.

        More opponents = lower equity.
        """
        if num_opponents <= 1:
            return base_equity

        # Approximate adjustment: equity decreases as more opponents
        # but not linearly (hands that dominate still do well multiway)
        factor = 1.0 / (1.0 + 0.15 * (num_opponents - 1))
        return base_equity * factor


# Convenience function
def quick_equity(hole_cards: Hand, board: List[Card], num_opponents: int = 1) -> float:
    """
    Quick equity estimation combining preflop lookup and Monte Carlo.

    Uses preflop tables for speed, Monte Carlo for postflop accuracy.

    Args:
        hole_cards: Hero's hole cards
        board: Community cards (empty for preflop)
        num_opponents: Number of active opponents

    Returns:
        Equity as float 0.0-1.0
    """
    num_opponents = max(1, num_opponents)

    if not board:
        # Preflop - use lookup table (much faster)
        equity = PreflopEquity.get_equity_from_cards(hole_cards)
        # Only apply mild multiway adjustment (hands stay relatively strong)
        if num_opponents > 1:
            # Less aggressive adjustment for preflop
            factor = 1.0 / (1.0 + 0.08 * (num_opponents - 1))
            equity = equity * factor
        return equity
    else:
        # Postflop - use Monte Carlo
        calc = EquityCalculator()
        # Fewer sims for speed, more for river accuracy
        sims = 300 if len(board) < 5 else 200
        return calc.calculate_equity(hole_cards, board, num_opponents, sims)
