"""
Difficulty management system for adaptive quiz difficulty.

Implements a Khan Academy / Khanmigo-inspired adaptive difficulty system
that adjusts based on recent user performance.

Difficulty Adjustment Algorithm:
--------------------------------
1. Track the last N answers (default N=5) in a sliding window.
2. Calculate success rate over the window.
3. Adjust difficulty based on thresholds:
   - Success rate >= 80%: Increase difficulty (user is mastering current level)
   - Success rate <= 40%: Decrease difficulty (user is struggling)
   - Otherwise: Maintain current difficulty

This approach is inspired by spaced repetition and mastery-based learning,
where we want to keep users in their "zone of proximal development" - challenged
but not overwhelmed.
"""

from enum import IntEnum
from collections import deque
from dataclasses import dataclass
from typing import List, Optional


class DifficultyLevel(IntEnum):
    """
    Difficulty levels for questions.

    Each level corresponds to increasingly complex problems:
    - VERY_EASY: Basic operations, simple substitutions
    - EASY: Standard textbook problems, single-step solutions
    - MEDIUM: Multi-step problems, some conceptual reasoning
    - HARD: Complex problems requiring multiple concepts
    - VERY_HARD: Challenge problems, approximation, deep understanding
    """
    VERY_EASY = 1
    EASY = 2
    MEDIUM = 3
    HARD = 4
    VERY_HARD = 5

    @classmethod
    def from_int(cls, value: int) -> 'DifficultyLevel':
        """Clamp an integer to valid difficulty range."""
        clamped = max(cls.VERY_EASY, min(cls.VERY_HARD, value))
        return cls(clamped)

    def display_name(self) -> str:
        """Human-readable name for the difficulty level."""
        names = {
            DifficultyLevel.VERY_EASY: "Very Easy",
            DifficultyLevel.EASY: "Easy",
            DifficultyLevel.MEDIUM: "Medium",
            DifficultyLevel.HARD: "Hard",
            DifficultyLevel.VERY_HARD: "Very Hard"
        }
        return names[self]


@dataclass
class PerformanceRecord:
    """Record of a single question attempt."""
    difficulty: DifficultyLevel
    correct: bool
    category: str  # e.g., "calculus", "physics", "algebra"


class DifficultyManager:
    """
    Manages adaptive difficulty based on user performance.

    The manager tracks recent performance and adjusts difficulty
    to keep the user appropriately challenged. It also tracks
    performance by category to provide targeted feedback.

    Example usage:
        dm = DifficultyManager()
        dm.record_answer(DifficultyLevel.MEDIUM, correct=True, category="calculus")
        dm.record_answer(DifficultyLevel.MEDIUM, correct=True, category="calculus")
        next_difficulty = dm.get_current_difficulty()  # May increase

    How to adjust the algorithm:
    ----------------------------
    - Modify WINDOW_SIZE to change how many recent questions affect difficulty
    - Modify INCREASE_THRESHOLD (default 0.8) to require more/fewer correct answers
    - Modify DECREASE_THRESHOLD (default 0.4) to be more/less forgiving
    - Modify STREAK_BONUS to change how consecutive correct/wrong affects jumps
    """

    # Algorithm parameters (easily tunable)
    WINDOW_SIZE = 5  # Number of recent answers to consider
    INCREASE_THRESHOLD = 0.80  # Success rate to increase difficulty
    DECREASE_THRESHOLD = 0.40  # Success rate to decrease difficulty
    STREAK_BONUS = 3  # Consecutive correct/wrong for extra adjustment

    def __init__(self, starting_difficulty: DifficultyLevel = DifficultyLevel.EASY):
        """
        Initialize the difficulty manager.

        Args:
            starting_difficulty: Initial difficulty level for new sessions
        """
        self._current_difficulty = starting_difficulty
        self._history: deque[PerformanceRecord] = deque(maxlen=self.WINDOW_SIZE)
        self._all_records: List[PerformanceRecord] = []
        self._consecutive_correct = 0
        self._consecutive_wrong = 0

    @property
    def current_difficulty(self) -> DifficultyLevel:
        """Get the current difficulty level."""
        return self._current_difficulty

    def record_answer(self, difficulty: DifficultyLevel, correct: bool, category: str) -> None:
        """
        Record a question attempt and update difficulty.

        Args:
            difficulty: The difficulty of the attempted question
            correct: Whether the answer was correct
            category: The category of the question (for analytics)
        """
        record = PerformanceRecord(difficulty=difficulty, correct=correct, category=category)
        self._history.append(record)
        self._all_records.append(record)

        # Update streak counters
        if correct:
            self._consecutive_correct += 1
            self._consecutive_wrong = 0
        else:
            self._consecutive_wrong += 1
            self._consecutive_correct = 0

        # Adjust difficulty based on performance
        self._adjust_difficulty()

    def _adjust_difficulty(self) -> None:
        """
        Adjust difficulty based on recent performance.

        Uses a sliding window of recent answers to determine if the
        user should move up or down in difficulty.

        Key rule: Never increase difficulty immediately after a wrong answer.
        """
        if len(self._history) < 2:
            # Need at least 2 answers before adjusting
            return

        # Get the most recent answer
        last_answer_correct = self._history[-1].correct

        # Calculate success rate over the window
        correct_count = sum(1 for r in self._history if r.correct)
        success_rate = correct_count / len(self._history)

        adjustment = 0

        # Check for streak bonuses (rapid adjustment for consistent performance)
        if self._consecutive_correct >= self.STREAK_BONUS:
            adjustment = 1
        elif self._consecutive_wrong >= self.STREAK_BONUS:
            adjustment = -1
        # Standard threshold-based adjustment
        elif success_rate >= self.INCREASE_THRESHOLD:
            adjustment = 1
        elif success_rate <= self.DECREASE_THRESHOLD:
            adjustment = -1

        # CRITICAL: Never increase difficulty right after a wrong answer
        # This prevents frustrating situations where user misses a hard
        # problem and immediately gets an even harder one
        if adjustment > 0 and not last_answer_correct:
            adjustment = 0

        if adjustment != 0:
            new_level = int(self._current_difficulty) + adjustment
            self._current_difficulty = DifficultyLevel.from_int(new_level)

    def get_current_difficulty(self) -> DifficultyLevel:
        """Get the recommended difficulty for the next question."""
        return self._current_difficulty

    def get_success_rate(self) -> float:
        """Get the success rate over the recent window."""
        if not self._history:
            return 0.0
        correct_count = sum(1 for r in self._history if r.correct)
        return correct_count / len(self._history)

    def get_category_stats(self) -> dict:
        """
        Get performance statistics by category.

        Returns:
            Dictionary mapping category names to (correct, total) tuples
        """
        stats = {}
        for record in self._all_records:
            if record.category not in stats:
                stats[record.category] = {'correct': 0, 'total': 0}
            stats[record.category]['total'] += 1
            if record.correct:
                stats[record.category]['correct'] += 1
        return stats

    def get_difficulty_distribution(self) -> dict:
        """
        Get the distribution of difficulties attempted.

        Returns:
            Dictionary mapping difficulty levels to counts
        """
        distribution = {level: 0 for level in DifficultyLevel}
        for record in self._all_records:
            distribution[record.difficulty] += 1
        return distribution

    def get_total_attempted(self) -> int:
        """Get the total number of questions attempted."""
        return len(self._all_records)

    def get_total_correct(self) -> int:
        """Get the total number of correct answers."""
        return sum(1 for r in self._all_records if r.correct)

    def get_weak_categories(self, threshold: float = 0.5) -> List[str]:
        """
        Identify categories where the user is struggling.

        Args:
            threshold: Success rate below which a category is considered weak

        Returns:
            List of category names where user performance is below threshold
        """
        stats = self.get_category_stats()
        weak = []
        for category, data in stats.items():
            if data['total'] >= 2:  # Need at least 2 attempts
                rate = data['correct'] / data['total']
                if rate < threshold:
                    weak.append(category)
        return weak

    def reset(self) -> None:
        """Reset the difficulty manager for a new session."""
        self._current_difficulty = DifficultyLevel.EASY
        self._history.clear()
        self._all_records.clear()
        self._consecutive_correct = 0
        self._consecutive_wrong = 0
