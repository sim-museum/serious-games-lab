"""
Scoring system for the Math Quiz application.

Implements a power-test style scoring where:
- Harder questions give more points when correct
- Wrong answers incur penalties proportional to difficulty
- Trivial/throwaway answers on hard questions are detected and penalized extra

Scoring Formula:
----------------
For correct answers:
    points = BASE_POINTS * DIFFICULTY_MULTIPLIER[difficulty]

For incorrect answers:
    penalty = BASE_PENALTY * DIFFICULTY_PENALTY_MULTIPLIER[difficulty]

For partial credit (estimation questions):
    points = full_points * accuracy_factor  (0.0 to 1.0)

Trivial Answer Detection:
-------------------------
For hard questions, if the answer appears trivially simple (e.g., single digit
for a complex derivation), the penalty is increased by TRIVIAL_PENALTY_FACTOR.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from .difficulty import DifficultyLevel


class AnswerQuality(Enum):
    """Quality classification of an answer attempt."""
    CORRECT = "correct"
    PARTIAL = "partial"  # For estimation questions with tolerance
    INCORRECT = "incorrect"
    TRIVIAL = "trivial"  # Detected as throwaway/trivial attempt


@dataclass
class ScoreResult:
    """Result of scoring an answer."""
    points: int
    quality: AnswerQuality
    message: str
    is_trivial_warning: bool = False


class ScoreManager:
    """
    Manages scoring for the quiz session.

    The scoring system is designed to encourage genuine attempts while
    appropriately rewarding difficulty. It implements a power-test philosophy
    where guessing or giving up on hard questions has meaningful consequences.

    Configuration:
    --------------
    All scoring parameters are class constants and can be easily modified:
    - BASE_POINTS: Foundation for point calculations
    - DIFFICULTY_MULTIPLIERS: Points multiplier per difficulty level
    - PENALTY_MULTIPLIERS: Penalty multiplier per difficulty level
    - TRIVIAL_PENALTY_FACTOR: Extra penalty for trivial answers on hard questions
    - PARTIAL_CREDIT_THRESHOLDS: Accuracy thresholds for partial credit
    """

    # Base scoring values
    BASE_POINTS = 10
    BASE_PENALTY = 5

    # Multipliers by difficulty (easily adjustable)
    # Format: {DifficultyLevel: multiplier}
    DIFFICULTY_MULTIPLIERS = {
        DifficultyLevel.VERY_EASY: 0.5,   # 5 points
        DifficultyLevel.EASY: 1.0,        # 10 points
        DifficultyLevel.MEDIUM: 2.0,      # 20 points
        DifficultyLevel.HARD: 3.5,        # 35 points
        DifficultyLevel.VERY_HARD: 5.0,   # 50 points
    }

    # Penalty multipliers (wrong answers)
    PENALTY_MULTIPLIERS = {
        DifficultyLevel.VERY_EASY: 0.5,   # -2.5 points
        DifficultyLevel.EASY: 1.0,        # -5 points
        DifficultyLevel.MEDIUM: 1.5,      # -7.5 points
        DifficultyLevel.HARD: 2.0,        # -10 points
        DifficultyLevel.VERY_HARD: 2.5,   # -12.5 points
    }

    # Extra penalty factor for trivial answers on hard questions
    TRIVIAL_PENALTY_FACTOR = 1.5

    # Partial credit thresholds for estimation questions
    # (accuracy_ratio, credit_ratio)
    PARTIAL_CREDIT_THRESHOLDS = [
        (0.95, 1.0),   # Within 5%: full credit
        (0.90, 0.8),   # Within 10%: 80% credit
        (0.80, 0.5),   # Within 20%: 50% credit
        (0.70, 0.25),  # Within 30%: 25% credit
    ]

    def __init__(self):
        """Initialize the score manager."""
        self._score = 0
        self._history = []  # List of ScoreResult for session review

    @property
    def score(self) -> int:
        """Get the current score."""
        return self._score

    def calculate_points(self, difficulty: DifficultyLevel, correct: bool) -> int:
        """
        Calculate points for a correct/incorrect answer.

        Args:
            difficulty: The difficulty level of the question
            correct: Whether the answer was correct

        Returns:
            Points to add (positive) or subtract (negative)
        """
        if correct:
            multiplier = self.DIFFICULTY_MULTIPLIERS[difficulty]
            return int(self.BASE_POINTS * multiplier)
        else:
            multiplier = self.PENALTY_MULTIPLIERS[difficulty]
            return -int(self.BASE_PENALTY * multiplier)

    def calculate_partial_points(
        self,
        difficulty: DifficultyLevel,
        accuracy_ratio: float
    ) -> int:
        """
        Calculate partial credit for estimation questions.

        Args:
            difficulty: The difficulty level of the question
            accuracy_ratio: How close the answer was (1.0 = exact, 0.0 = completely off)

        Returns:
            Points earned (can be 0 or positive, never negative for partials)
        """
        full_points = self.calculate_points(difficulty, correct=True)

        # Find the appropriate credit tier
        for threshold, credit_ratio in self.PARTIAL_CREDIT_THRESHOLDS:
            if accuracy_ratio >= threshold:
                return int(full_points * credit_ratio)

        # Below all thresholds: no credit
        return 0

    def is_trivial_answer(
        self,
        user_answer: str,
        difficulty: DifficultyLevel,
        expected_complexity: str = "expression"
    ) -> bool:
        """
        Detect if an answer appears to be a trivial/throwaway attempt.

        This helps implement the power-test behavior by detecting when users
        submit obviously inadequate answers on hard questions.

        Args:
            user_answer: The user's submitted answer
            difficulty: The difficulty of the question
            expected_complexity: What kind of answer is expected
                                 ("expression", "numeric", "list")

        Returns:
            True if the answer appears trivially simple for the question type
        """
        # Only check for HARD and VERY_HARD questions
        if difficulty < DifficultyLevel.HARD:
            return False

        answer = user_answer.strip()

        # Empty or very short answers
        if len(answer) <= 1:
            return True

        # Single digit for complex expressions
        if expected_complexity == "expression" and answer.isdigit():
            return True

        # Just "0" or "1" for hard questions
        if answer in ("0", "1", "-1") and expected_complexity == "expression":
            return True

        # Just "x" for complex questions expecting full expressions
        if answer == "x" and difficulty >= DifficultyLevel.HARD:
            return True

        return False

    def score_answer(
        self,
        difficulty: DifficultyLevel,
        correct: bool,
        user_answer: str = "",
        expected_complexity: str = "expression",
        accuracy_ratio: Optional[float] = None
    ) -> ScoreResult:
        """
        Score an answer and update the session score.

        Args:
            difficulty: The difficulty level of the question
            correct: Whether the answer was correct
            user_answer: The user's answer (for trivial detection)
            expected_complexity: Type of expected answer
            accuracy_ratio: For partial credit on estimation questions (0.0-1.0)

        Returns:
            ScoreResult with points earned and quality assessment
        """
        # Check for trivial answers on hard questions
        if not correct and user_answer:
            is_trivial = self.is_trivial_answer(user_answer, difficulty, expected_complexity)
        else:
            is_trivial = False

        # Calculate points
        if correct:
            points = self.calculate_points(difficulty, True)
            quality = AnswerQuality.CORRECT
            message = f"+{points} points"
        elif accuracy_ratio is not None and accuracy_ratio > 0.7:
            # Partial credit for estimation questions
            points = self.calculate_partial_points(difficulty, accuracy_ratio)
            quality = AnswerQuality.PARTIAL
            pct = int(accuracy_ratio * 100)
            message = f"+{points} points (partial credit - {pct}% accurate)"
        elif is_trivial:
            # Extra penalty for trivial answers
            base_penalty = self.calculate_points(difficulty, False)
            points = int(base_penalty * self.TRIVIAL_PENALTY_FACTOR)
            quality = AnswerQuality.TRIVIAL
            message = f"{points} points (trivial answer penalty)"
        else:
            points = self.calculate_points(difficulty, False)
            quality = AnswerQuality.INCORRECT
            message = f"{points} points"

        # Update total score
        self._score += points

        # Record result
        result = ScoreResult(
            points=points,
            quality=quality,
            message=message,
            is_trivial_warning=is_trivial
        )
        self._history.append(result)

        return result

    def get_history(self) -> list:
        """Get the scoring history for the session."""
        return self._history.copy()

    def reset(self) -> None:
        """Reset the score manager for a new session."""
        self._score = 0
        self._history.clear()
