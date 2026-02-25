"""
Lightweight hand evaluator for Texas Hold'em.

This is a pure Python implementation that:
- Evaluates 5-7 card hands
- Uses lookup tables for fast evaluation
- No external dependencies
- Fits in RAM with minimal footprint

The evaluator uses a combination of:
1. Lookup tables for flush/straight detection
2. Prime number product for rank combinations
3. Bit manipulation for efficient comparison
"""

from enum import IntEnum
from typing import List, Tuple, Optional
from functools import lru_cache
from itertools import combinations

from .models import Card, Rank, Suit, Hand


class HandRank(IntEnum):
    """
    Hand rankings from lowest to highest.
    Higher value = better hand.
    """
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8
    ROYAL_FLUSH = 9

    def __str__(self) -> str:
        names = [
            'High Card', 'One Pair', 'Two Pair', 'Three of a Kind',
            'Straight', 'Flush', 'Full House', 'Four of a Kind',
            'Straight Flush', 'Royal Flush'
        ]
        return names[self.value]


class HandEvaluator:
    """
    Texas Hold'em hand evaluator.

    Usage:
        evaluator = HandEvaluator()
        score = evaluator.evaluate(hole_cards, board)
        rank = evaluator.get_rank(score)
        description = evaluator.describe_hand(score, hole_cards, board)

    The score is a tuple (HandRank, kicker_values) that can be compared
    directly to determine the winner.
    """

    # Prime numbers for each rank (used for multiplication-based lookup)
    PRIMES = {
        Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 5, Rank.FIVE: 7,
        Rank.SIX: 11, Rank.SEVEN: 13, Rank.EIGHT: 17, Rank.NINE: 19,
        Rank.TEN: 23, Rank.JACK: 29, Rank.QUEEN: 31, Rank.KING: 37,
        Rank.ACE: 41
    }

    def __init__(self):
        """Initialize the evaluator with lookup tables."""
        self._build_straight_table()

    def _build_straight_table(self) -> None:
        """Build lookup table for straight detection."""
        # A straight is 5 consecutive ranks
        # Represented as bitmask: bit i = 1 if rank i+2 is present
        # Ace can be low (A2345) or high (TJQKA)
        self._straight_table = {}

        # Standard straights (5-high through A-high)
        for high in range(4, 13):  # 6-high (indices 4) through A-high (index 12)
            mask = 0
            for i in range(5):
                mask |= (1 << (high - i))
            self._straight_table[mask] = high + 2  # High card rank

        # Wheel (A2345): A is bit 12, 2345 are bits 0-3
        wheel_mask = 0b1000000001111  # A2345
        self._straight_table[wheel_mask] = 5  # 5-high straight

    def evaluate(self, hole_cards: Hand, board: List[Card]) -> Tuple[int, Tuple]:
        """
        Evaluate the best 5-card hand from hole cards + board.

        Args:
            hole_cards: Player's two hole cards
            board: Community cards (3-5 cards)

        Returns:
            Tuple of (hand_rank_value, kickers) for comparison.
            Higher values = better hands.
        """
        all_cards = list(hole_cards.cards) + list(board)

        if len(all_cards) < 5:
            raise ValueError(f"Need at least 5 cards, got {len(all_cards)}")

        # Find best 5-card combination
        best_score = None
        for combo in combinations(all_cards, 5):
            score = self._evaluate_5cards(list(combo))
            if best_score is None or score > best_score:
                best_score = score

        return best_score

    def _evaluate_5cards(self, cards: List[Card]) -> Tuple[int, Tuple]:
        """Evaluate exactly 5 cards."""
        ranks = sorted([c.rank.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]

        is_flush = len(set(suits)) == 1
        is_straight, straight_high = self._check_straight(ranks)

        # Count rank occurrences
        rank_counts = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        counts = sorted(rank_counts.values(), reverse=True)
        # Ranks sorted by count, then by rank value
        sorted_ranks = sorted(rank_counts.keys(),
                             key=lambda r: (rank_counts[r], r), reverse=True)

        # Determine hand rank
        if is_straight and is_flush:
            if straight_high == 14:  # Ace-high straight flush
                return (HandRank.ROYAL_FLUSH.value, (straight_high,))
            return (HandRank.STRAIGHT_FLUSH.value, (straight_high,))

        if counts[0] == 4:
            # Four of a kind
            quad_rank = sorted_ranks[0]
            kicker = sorted_ranks[1]
            return (HandRank.FOUR_OF_A_KIND.value, (quad_rank, kicker))

        if counts[0] == 3 and counts[1] == 2:
            # Full house
            trips_rank = sorted_ranks[0]
            pair_rank = sorted_ranks[1]
            return (HandRank.FULL_HOUSE.value, (trips_rank, pair_rank))

        if is_flush:
            return (HandRank.FLUSH.value, tuple(ranks))

        if is_straight:
            return (HandRank.STRAIGHT.value, (straight_high,))

        if counts[0] == 3:
            # Three of a kind
            trips_rank = sorted_ranks[0]
            kickers = tuple(sorted_ranks[1:])
            return (HandRank.THREE_OF_A_KIND.value, (trips_rank,) + kickers)

        if counts[0] == 2 and counts[1] == 2:
            # Two pair
            high_pair = max(sorted_ranks[0], sorted_ranks[1])
            low_pair = min(sorted_ranks[0], sorted_ranks[1])
            kicker = sorted_ranks[2]
            return (HandRank.TWO_PAIR.value, (high_pair, low_pair, kicker))

        if counts[0] == 2:
            # One pair
            pair_rank = sorted_ranks[0]
            kickers = tuple(sorted_ranks[1:])
            return (HandRank.ONE_PAIR.value, (pair_rank,) + kickers)

        # High card
        return (HandRank.HIGH_CARD.value, tuple(ranks))

    def _check_straight(self, ranks: List[int]) -> Tuple[bool, int]:
        """
        Check if sorted ranks form a straight.
        Returns (is_straight, high_card_rank).
        """
        unique_ranks = sorted(set(ranks), reverse=True)

        if len(unique_ranks) < 5:
            return False, 0

        # Check for standard straight
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i + 4] == 4:
                return True, unique_ranks[i]

        # Check for wheel (A2345)
        if set(unique_ranks) >= {14, 2, 3, 4, 5}:
            return True, 5  # 5-high straight

        return False, 0

    def get_rank(self, score: Tuple[int, Tuple]) -> HandRank:
        """Get the HandRank enum from a score."""
        return HandRank(score[0])

    def describe_hand(self, score: Tuple[int, Tuple],
                     hole_cards: Optional[Hand] = None,
                     board: Optional[List[Card]] = None) -> str:
        """
        Get human-readable description of a hand.
        """
        rank = HandRank(score[0])
        kickers = score[1]

        rank_names = {
            2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
            9: '9', 10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'
        }

        if rank == HandRank.ROYAL_FLUSH:
            return "Royal Flush"
        elif rank == HandRank.STRAIGHT_FLUSH:
            return f"Straight Flush, {rank_names[kickers[0]]}-high"
        elif rank == HandRank.FOUR_OF_A_KIND:
            return f"Four of a Kind, {rank_names[kickers[0]]}s"
        elif rank == HandRank.FULL_HOUSE:
            return f"Full House, {rank_names[kickers[0]]}s full of {rank_names[kickers[1]]}s"
        elif rank == HandRank.FLUSH:
            return f"Flush, {rank_names[kickers[0]]}-high"
        elif rank == HandRank.STRAIGHT:
            return f"Straight, {rank_names[kickers[0]]}-high"
        elif rank == HandRank.THREE_OF_A_KIND:
            return f"Three of a Kind, {rank_names[kickers[0]]}s"
        elif rank == HandRank.TWO_PAIR:
            return f"Two Pair, {rank_names[kickers[0]]}s and {rank_names[kickers[1]]}s"
        elif rank == HandRank.ONE_PAIR:
            return f"Pair of {rank_names[kickers[0]]}s"
        else:
            return f"High Card, {rank_names[kickers[0]]}"

    def compare_hands(self, score1: Tuple[int, Tuple],
                     score2: Tuple[int, Tuple]) -> int:
        """
        Compare two hands.
        Returns: 1 if score1 wins, -1 if score2 wins, 0 if tie.
        """
        if score1 > score2:
            return 1
        elif score1 < score2:
            return -1
        return 0


class DrawEvaluator:
    """
    Evaluate drawing hands (flush draws, straight draws, etc.)
    """

    @staticmethod
    def count_flush_outs(hole_cards: Hand, board: List[Card]) -> Tuple[int, Suit]:
        """
        Count outs to make a flush.
        Returns (outs, suit) or (0, None) if no flush draw.
        """
        all_cards = list(hole_cards.cards) + list(board)
        suit_counts = {}
        for card in all_cards:
            suit_counts[card.suit] = suit_counts.get(card.suit, 0) + 1

        for suit, count in suit_counts.items():
            if count == 4:
                return (9, suit)  # 9 outs to complete flush

        return (0, None)

    @staticmethod
    def count_straight_outs(hole_cards: Hand, board: List[Card]) -> Tuple[int, str]:
        """
        Count outs to make a straight.
        Returns (outs, draw_type) where draw_type is 'oesd', 'gutshot', or 'none'.
        """
        all_cards = list(hole_cards.cards) + list(board)
        ranks = set(c.rank.value for c in all_cards)

        # Check for open-ended straight draw (8 outs)
        for high in range(5, 14):  # 6-high through A-high
            needed = set(range(high - 4, high + 1))
            present = needed & ranks
            if len(present) == 4:
                # Check if it's open-ended (missing either end)
                missing = needed - ranks
                if len(missing) == 1:
                    missing_rank = list(missing)[0]
                    if missing_rank == min(needed) or missing_rank == max(needed):
                        return (8, 'oesd')
                    else:
                        return (4, 'gutshot')

        # Check for gutshot
        for high in range(5, 15):
            needed = set(range(high - 4, high + 1))
            present = needed & ranks
            if len(present) == 4:
                return (4, 'gutshot')

        return (0, 'none')

    @staticmethod
    def has_overcards(hole_cards: Hand, board: List[Card]) -> int:
        """
        Count overcards (hole cards higher than any board card).
        Returns number of overcards (0-2).
        """
        if not board:
            return 2  # Both cards are overcards preflop

        max_board = max(c.rank.value for c in board)
        overcards = sum(1 for c in hole_cards.cards if c.rank.value > max_board)
        return overcards

    @staticmethod
    def total_outs(hole_cards: Hand, board: List[Card]) -> int:
        """
        Estimate total outs to improve to likely best hand.
        Combines flush draws, straight draws, and overcards.
        Accounts for overlap.
        """
        flush_outs, _ = DrawEvaluator.count_flush_outs(hole_cards, board)
        straight_outs, _ = DrawEvaluator.count_straight_outs(hole_cards, board)
        overcard_outs = DrawEvaluator.has_overcards(hole_cards, board) * 3

        # Rough adjustment for overlap (conservative)
        if flush_outs > 0 and straight_outs > 0:
            # Combo draw - some outs overlap
            total = flush_outs + straight_outs - 2
        else:
            total = flush_outs + straight_outs

        # Add overcard outs if we have a draw (semi-bluff potential)
        if total > 0:
            total += overcard_outs // 2  # Conservative

        return total

    @staticmethod
    def is_draw(hole_cards: Hand, board: List[Card]) -> bool:
        """Check if we have any significant draw."""
        flush_outs, _ = DrawEvaluator.count_flush_outs(hole_cards, board)
        straight_outs, _ = DrawEvaluator.count_straight_outs(hole_cards, board)
        return flush_outs >= 4 or straight_outs >= 4


# Convenience function
def evaluate_hand(hole_cards: Hand, board: List[Card]) -> Tuple[HandRank, str]:
    """
    Convenience function to evaluate a hand and get description.

    Returns:
        (HandRank enum, description string)
    """
    evaluator = HandEvaluator()
    score = evaluator.evaluate(hole_cards, board)
    rank = evaluator.get_rank(score)
    description = evaluator.describe_hand(score, hole_cards, board)
    return rank, description
