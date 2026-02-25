"""
Quiz Engine - orchestrates the math quiz session.

The QuizEngine is the central coordinator that:
- Manages question generation and selection
- Tracks session state (time, score, difficulty)
- Handles answer checking and scoring
- Provides session analytics
"""

import time
from typing import Any, Callable, List, Optional
import numpy as np

from .difficulty import DifficultyManager, DifficultyLevel
from .scoring import ScoreManager, ScoreResult, AnswerQuality
from .answer_parser import AnswerParser
from .questions.base import Question, QuestionCategory
from .questions.calculus import CalculusQuestions
from .questions.algebra import AlgebraQuestions
from .questions.physics import PhysicsQuestions
from .questions.estimation import EstimationQuestions
from .questions.graphical import GraphicalQuestions
from .questions.linear_algebra import LinearAlgebraQuestions
from .questions.statistics import StatisticsQuestions
from .questions.accounting import AccountingQuestions
from utils.settings import settings


class QuizEngine:
    """
    Main quiz engine that coordinates the quiz session.

    The engine handles:
    - Question generation with adaptive difficulty
    - Answer validation and scoring
    - Session timing
    - Performance tracking and analytics

    Example usage:
        engine = QuizEngine(duration=600)  # 10 minute session
        engine.start_session()

        while engine.is_active():
            question = engine.get_next_question()
            # Display question to user...
            # Get user answer...
            result = engine.submit_answer(user_answer)
            # Display result...

        summary = engine.get_session_summary()
    """

    # Available question category factories
    QUESTION_FACTORIES = {
        QuestionCategory.CALCULUS: CalculusQuestions,
        QuestionCategory.ALGEBRA: AlgebraQuestions,
        QuestionCategory.PHYSICS: PhysicsQuestions,
        QuestionCategory.ESTIMATION: EstimationQuestions,
        QuestionCategory.LINEAR_ALGEBRA: LinearAlgebraQuestions,
        QuestionCategory.STATISTICS: StatisticsQuestions,
        QuestionCategory.ACCOUNTING: AccountingQuestions,
    }

    def __init__(
        self,
        duration: int = 600,  # 10 minutes default
        starting_difficulty: DifficultyLevel = DifficultyLevel.EASY
    ):
        """
        Initialize the quiz engine.

        Args:
            duration: Session duration in seconds
            starting_difficulty: Initial difficulty level
        """
        self.duration = duration
        self.starting_difficulty = starting_difficulty

        # Managers
        self.difficulty_manager = DifficultyManager(starting_difficulty)
        self.score_manager = ScoreManager()
        self.answer_parser = AnswerParser()

        # Session state
        self._start_time: Optional[float] = None
        self._current_question: Optional[Question] = None
        self._question_history: List[dict] = []
        self._recent_question_signatures: List[str] = []  # For deduplication
        self._active = False

        # Callbacks for UI updates
        self._on_question_generated: Optional[Callable] = None
        self._on_answer_checked: Optional[Callable] = None
        self._on_session_end: Optional[Callable] = None

    def set_callbacks(
        self,
        on_question_generated: Optional[Callable] = None,
        on_answer_checked: Optional[Callable] = None,
        on_session_end: Optional[Callable] = None
    ) -> None:
        """Set callback functions for UI updates."""
        self._on_question_generated = on_question_generated
        self._on_answer_checked = on_answer_checked
        self._on_session_end = on_session_end

    def start_session(self) -> None:
        """Start a new quiz session."""
        self._start_time = time.time()
        self._active = True
        self._question_history.clear()
        self._recent_question_signatures.clear()
        self.difficulty_manager.reset()
        self.score_manager.reset()

    def _get_question_signature(self, question: Question) -> str:
        """
        Get a signature for a question to detect duplicates.

        The signature captures the question type and key parameters
        to avoid asking essentially the same question twice.
        """
        # Include category, difficulty, and a hash of the question text
        # This catches questions with the same structure even if values differ
        text_key = question.text[:50]  # First 50 chars capture question type
        return f"{question.category.value}:{question.difficulty.value}:{text_key}"

    def _is_duplicate_question(self, question: Question) -> bool:
        """Check if a question is too similar to recently asked questions."""
        sig = self._get_question_signature(question)

        # Check against last 5 questions
        for recent_sig in self._recent_question_signatures[-5:]:
            if sig == recent_sig:
                return True
            # Also check category+type match (same first 30 chars of signature)
            if sig[:30] == recent_sig[:30]:
                return True

        return False

    def _record_question(self, question: Question) -> None:
        """Record a question signature for deduplication."""
        sig = self._get_question_signature(question)
        self._recent_question_signatures.append(sig)
        # Keep only last 10 signatures
        if len(self._recent_question_signatures) > 10:
            self._recent_question_signatures.pop(0)

    def stop_session(self) -> None:
        """Stop the current session."""
        self._active = False
        if self._on_session_end:
            self._on_session_end(self.get_session_summary())

    def is_active(self) -> bool:
        """Check if the session is still active."""
        if not self._active or self._start_time is None:
            return False

        elapsed = time.time() - self._start_time
        if elapsed >= self.duration:
            self.stop_session()
            return False

        return True

    def get_time_remaining(self) -> int:
        """Get remaining time in seconds."""
        if self._start_time is None:
            return self.duration

        elapsed = time.time() - self._start_time
        remaining = max(0, self.duration - elapsed)
        return int(remaining)

    def get_current_difficulty(self) -> DifficultyLevel:
        """Get the current difficulty level."""
        return self.difficulty_manager.current_difficulty

    def get_score(self) -> int:
        """Get the current score."""
        return self.score_manager.score

    def get_next_question(self) -> Optional[Question]:
        """
        Generate and return the next question.

        Hard and Very Hard questions only come from advanced categories
        (Linear Algebra, Statistics, Accounting). If no advanced categories
        are enabled, difficulty is capped at Medium.

        Returns:
            Question object, or None if session ended
        """
        if not self.is_active():
            return None

        difficulty = self.difficulty_manager.get_current_difficulty()

        # Check which advanced categories are enabled (for Hard/Very Hard)
        advanced_enabled = []
        if settings.include_physics:
            advanced_enabled.append(QuestionCategory.PHYSICS)
        if settings.include_linear_algebra:
            advanced_enabled.append(QuestionCategory.LINEAR_ALGEBRA)
        if settings.include_statistics:
            advanced_enabled.append(QuestionCategory.STATISTICS)
        if settings.include_accounting:
            advanced_enabled.append(QuestionCategory.ACCOUNTING)

        # For Hard and Very Hard difficulties, only use advanced categories
        # If no advanced categories enabled, cap difficulty at Medium
        is_hard_difficulty = difficulty in (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

        if is_hard_difficulty:
            if not advanced_enabled:
                # Cap difficulty at Medium if no advanced categories
                difficulty = DifficultyLevel.MEDIUM
                is_hard_difficulty = False
            else:
                # Use only advanced categories for hard/very hard
                # Try up to 5 times to get a non-duplicate question
                for attempt in range(5):
                    weights = {cat: 1.0 for cat in advanced_enabled}
                    total = sum(weights.values())
                    weights = {k: v / total for k, v in weights.items()}

                    categories = list(weights.keys())
                    probs = [weights[c] for c in categories]
                    category = np.random.choice(categories, p=probs)

                    factory = self.QUESTION_FACTORIES[category]
                    question = factory.get_random_question(difficulty)

                    if not self._is_duplicate_question(question) or attempt == 4:
                        break

                self._record_question(question)
                self._current_question = question
                if self._on_question_generated:
                    self._on_question_generated(question)
                return question

        # For Easy, Very Easy, and Medium: use standard categories
        weights = {
            QuestionCategory.CALCULUS: 0.45,
            QuestionCategory.ALGEBRA: 0.35,
        }

        # Add estimation if enabled
        if settings.include_estimation:
            weights[QuestionCategory.ESTIMATION] = 0.20

        # Normalize weights
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        # Try up to 5 times to get a non-duplicate question
        for attempt in range(5):
            # 20% chance to get a graphical question (they have their own categories)
            if np.random.random() < 0.20:
                question = GraphicalQuestions.get_random_question(difficulty)
            else:
                categories = list(weights.keys())
                probs = [weights[c] for c in categories]
                category = np.random.choice(categories, p=probs)

                # Generate question
                factory = self.QUESTION_FACTORIES[category]
                question = factory.get_random_question(difficulty)

            if not self._is_duplicate_question(question) or attempt == 4:
                break

        self._record_question(question)
        self._current_question = question

        if self._on_question_generated:
            self._on_question_generated(question)

        return question

    def submit_answer(self, user_answer: str) -> dict:
        """
        Submit an answer for the current question.

        Args:
            user_answer: The user's answer as a string

        Returns:
            Dictionary with result information:
            - correct: bool
            - score_result: ScoreResult
            - correct_answer: display string
            - explanation: str
            - is_trivial: bool
        """
        if self._current_question is None:
            return {
                'correct': False,
                'score_result': None,
                'correct_answer': '',
                'explanation': 'No active question',
                'is_trivial': False
            }

        question = self._current_question
        parsed_answer = self.answer_parser.parse(user_answer)

        # Check the answer based on type
        if question.answer_type == "text":
            # Text answer with units (e.g., "23 m/s")
            correct, accuracy = self.answer_parser.check_answer_with_units(
                user_answer,
                str(question.correct_answer),
                question.tolerance
            )
            accuracy_ratio = accuracy if not correct else None
        elif question.answer_type == "numeric":
            correct, accuracy = self.answer_parser.check_numeric_answer(
                parsed_answer,
                float(question.correct_answer) if not isinstance(question.correct_answer, (int, float)) else question.correct_answer,
                question.tolerance
            )
            accuracy_ratio = accuracy if not correct else None
        elif question.answer_type == "list":
            correct = self.answer_parser.check_symbolic_equivalence(
                parsed_answer,
                question.correct_answer
            )
            accuracy_ratio = None
        else:  # expression
            correct = self.answer_parser.check_symbolic_equivalence(
                parsed_answer,
                question.correct_answer
            )
            accuracy_ratio = None

        # Score the answer
        score_result = self.score_manager.score_answer(
            difficulty=question.difficulty,
            correct=correct,
            user_answer=user_answer,
            expected_complexity=question.answer_type,
            accuracy_ratio=accuracy_ratio
        )

        # Update difficulty manager
        self.difficulty_manager.record_answer(
            difficulty=question.difficulty,
            correct=correct,
            category=question.category.value
        )

        # Record in history
        self._question_history.append({
            'question': question,
            'user_answer': user_answer,
            'correct': correct,
            'score_result': score_result,
            'timestamp': time.time()
        })

        result = {
            'correct': correct,
            'score_result': score_result,
            'correct_answer': question.get_answer_display(),
            'explanation': question.explanation,
            'is_trivial': score_result.is_trivial_warning
        }

        if self._on_answer_checked:
            self._on_answer_checked(result)

        # Clear current question
        self._current_question = None

        return result

    def skip_question(self) -> None:
        """Skip the current question with a small penalty."""
        if self._current_question is None:
            return

        # Small penalty for skipping
        self.score_manager._score -= 2

        # Record as wrong for difficulty adjustment
        self.difficulty_manager.record_answer(
            difficulty=self._current_question.difficulty,
            correct=False,
            category=self._current_question.category.value
        )

        self._question_history.append({
            'question': self._current_question,
            'user_answer': '[SKIPPED]',
            'correct': False,
            'score_result': ScoreResult(-2, AnswerQuality.INCORRECT, "Skipped (-2 points)"),
            'timestamp': time.time()
        })

        self._current_question = None

    def get_question_history(self, n: int = 10) -> List[dict]:
        """Get the last n questions from history."""
        return self._question_history[-n:]

    def get_session_summary(self) -> dict:
        """
        Get a comprehensive summary of the session.

        Returns:
            Dictionary with session statistics and feedback
        """
        total = self.difficulty_manager.get_total_attempted()
        correct = self.difficulty_manager.get_total_correct()
        category_stats = self.difficulty_manager.get_category_stats()
        difficulty_dist = self.difficulty_manager.get_difficulty_distribution()
        weak_categories = self.difficulty_manager.get_weak_categories()

        # Generate feedback
        feedback = self._generate_feedback(
            total, correct, category_stats, weak_categories
        )

        return {
            'final_score': self.score_manager.score,
            'total_questions': total,
            'correct_answers': correct,
            'accuracy': correct / total if total > 0 else 0,
            'category_stats': category_stats,
            'difficulty_distribution': {
                level.display_name(): count
                for level, count in difficulty_dist.items()
            },
            'weak_categories': weak_categories,
            'feedback': feedback,
            'duration_used': int(time.time() - self._start_time) if self._start_time else 0,
        }

    def _generate_feedback(
        self,
        total: int,
        correct: int,
        category_stats: dict,
        weak_categories: List[str]
    ) -> str:
        """Generate qualitative feedback for the session."""
        if total == 0:
            return "No questions attempted. Try again!"

        accuracy = correct / total

        # Overall assessment
        if accuracy >= 0.8:
            overall = "Excellent work! You showed strong mathematical understanding."
        elif accuracy >= 0.6:
            overall = "Good performance! You have solid foundations."
        elif accuracy >= 0.4:
            overall = "Decent effort. There's room for improvement."
        else:
            overall = "Keep practicing! Focus on the fundamentals."

        # Category-specific feedback
        category_feedback = []
        for cat, stats in category_stats.items():
            if stats['total'] >= 2:
                cat_acc = stats['correct'] / stats['total']
                if cat_acc >= 0.7:
                    category_feedback.append(f"Strong in {cat}")
                elif cat_acc < 0.5:
                    category_feedback.append(f"Review needed: {cat}")

        # Suggestions based on weak areas
        suggestions = []
        if "Physics" in weak_categories:
            suggestions.append("Practice more physics-based problems to build intuition.")
        if "Calculus" in weak_categories:
            suggestions.append("Review differentiation and integration rules.")
        if "Estimation" in weak_categories:
            suggestions.append("Work on approximation techniques and order-of-magnitude reasoning.")
        if "Algebra" in weak_categories:
            suggestions.append("Strengthen algebraic manipulation skills.")
        if "Linear Algebra" in weak_categories:
            suggestions.append("Review vectors, matrices, and linear transformations (No BS Linear Algebra).")
        if "Statistics" in weak_categories:
            suggestions.append("Practice probability and statistical inference concepts (No BS Statistics).")
        if "Accounting" in weak_categories:
            suggestions.append("Review double-entry bookkeeping and the accounting equation.")

        feedback = overall + "\n\n"

        if category_feedback:
            feedback += "Category Performance:\n• " + "\n• ".join(category_feedback) + "\n\n"

        if suggestions:
            feedback += "Suggestions:\n• " + "\n• ".join(suggestions)

        return feedback
