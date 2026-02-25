"""
Base classes for question generation.

Provides the abstract interface for all question types and
common utilities for generating mathematical content.

How to Add a New Question Type:
-------------------------------
1. Create a new class inheriting from QuestionGenerator
2. Implement generate() to return a Question object
3. Register the generator in the appropriate category
4. Set the DIFFICULTY_RANGE for the question type

Example:
    class MyNewQuestion(QuestionGenerator):
        CATEGORY = QuestionCategory.ALGEBRA
        DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

        def generate(self, difficulty: DifficultyLevel) -> Question:
            # Generate question content
            return Question(
                text="...",
                latex="...",
                correct_answer=...,
                explanation="...",
                category=self.CATEGORY,
                difficulty=difficulty
            )
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple
import numpy as np
import sympy as sp

from ..difficulty import DifficultyLevel
from utils.unicode_math import format_expr


class QuestionCategory(Enum):
    """Categories of questions for tracking and feedback."""
    CALCULUS = "Calculus"
    ALGEBRA = "Algebra"
    PHYSICS = "Physics"
    ESTIMATION = "Estimation"
    GEOMETRY = "Geometry"
    LINEAR_ALGEBRA = "Linear Algebra"
    STATISTICS = "Statistics"
    ACCOUNTING = "Accounting"


@dataclass
class Question:
    """
    Represents a generated quiz question.

    Attributes:
        text: Plain text version of the question
        latex: LaTeX-formatted version for display
        correct_answer: The expected answer (SymPy expression, number, or list)
        explanation: Solution explanation shown after answering
        category: The question category for tracking
        difficulty: The difficulty level
        hint: Optional hint (shown on request or after wrong answer)
        answer_type: Type of expected answer ("expression", "numeric", "list", "multiple_choice")
        tolerance: For numeric answers, acceptable relative error
        plot_data: Optional data for generating a plot
        requires_plot: Whether a plot should be shown with this question
        choices: Optional list of (label, value) tuples for multiple choice
    """
    text: str
    latex: str
    correct_answer: Any
    explanation: str
    category: QuestionCategory
    difficulty: DifficultyLevel
    hint: str = ""
    answer_type: str = "expression"  # "expression", "numeric", "list", "multiple_choice"
    tolerance: float = 0.05  # 5% default tolerance for numeric
    plot_data: Optional[dict] = None
    requires_plot: bool = False
    choices: Optional[List[Tuple[str, Any]]] = None  # [(label, value), ...] for multiple choice

    def get_answer_display(self) -> str:
        """Get a display-friendly version of the correct answer."""
        if isinstance(self.correct_answer, sp.Basic):
            return format_expr(self.correct_answer)
        elif isinstance(self.correct_answer, (list, tuple)):
            return str(self.correct_answer)
        else:
            return str(self.correct_answer)


@dataclass
class PlotData:
    """Data for generating a plot with a question."""
    x_range: Tuple[float, float] = (-5, 5)
    functions: List[Tuple[Callable, str, str]] = field(default_factory=list)  # (func, label, color)
    points: List[Tuple[float, float, str]] = field(default_factory=list)  # (x, y, marker)
    title: str = ""
    xlabel: str = "x"
    ylabel: str = "y"
    grid: bool = True


class QuestionGenerator(ABC):
    """
    Abstract base class for question generators.

    Subclasses should:
    1. Set CATEGORY and DIFFICULTY_RANGE class attributes
    2. Implement the generate() method
    3. Optionally override difficulty_to_params() for fine-grained control
    """

    CATEGORY: QuestionCategory = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE: Tuple[DifficultyLevel, DifficultyLevel] = (
        DifficultyLevel.VERY_EASY,
        DifficultyLevel.VERY_HARD
    )

    def __init__(self):
        """Initialize with SymPy symbols."""
        self.x, self.y, self.z = sp.symbols('x y z')
        self.t, self.n, self.m = sp.symbols('t n m')

    def can_generate(self, difficulty: DifficultyLevel) -> bool:
        """Check if this generator can produce questions at the given difficulty."""
        min_diff, max_diff = self.DIFFICULTY_RANGE
        return min_diff <= difficulty <= max_diff

    @abstractmethod
    def generate(self, difficulty: DifficultyLevel) -> Question:
        """
        Generate a question at the specified difficulty.

        Args:
            difficulty: The target difficulty level

        Returns:
            A Question object
        """
        pass

    def difficulty_to_params(self, difficulty: DifficultyLevel) -> dict:
        """
        Convert difficulty level to generation parameters.

        Override this to customize how difficulty affects question generation.
        Default implementation provides coefficient ranges and complexity flags.

        Args:
            difficulty: The difficulty level

        Returns:
            Dictionary of parameters for question generation
        """
        params = {
            DifficultyLevel.VERY_EASY: {
                'coeff_range': (1, 3),
                'power_range': (1, 2),
                'num_terms': 1,
                'use_trig': False,
                'use_exp': False,
            },
            DifficultyLevel.EASY: {
                'coeff_range': (1, 5),
                'power_range': (1, 3),
                'num_terms': 2,
                'use_trig': False,
                'use_exp': False,
            },
            DifficultyLevel.MEDIUM: {
                'coeff_range': (1, 7),
                'power_range': (1, 4),
                'num_terms': 2,
                'use_trig': True,
                'use_exp': False,
            },
            DifficultyLevel.HARD: {
                'coeff_range': (1, 5),
                'power_range': (1, 4),
                'num_terms': 2,
                'use_trig': True,
                'use_exp': False,
            },
            DifficultyLevel.VERY_HARD: {
                'coeff_range': (1, 6),
                'power_range': (1, 4),
                'num_terms': 2,
                'use_trig': True,
                'use_exp': True,
            },
        }
        return params[difficulty]

    def _random_coefficient(self, params: dict) -> int:
        """Generate a random coefficient based on parameters."""
        low, high = params['coeff_range']
        return np.random.randint(low, high + 1)

    def _random_power(self, params: dict) -> int:
        """Generate a random power based on parameters."""
        low, high = params['power_range']
        return np.random.randint(low, high + 1)

    def _random_polynomial(self, params: dict, symbol=None) -> sp.Expr:
        """Generate a random polynomial based on parameters."""
        if symbol is None:
            symbol = self.x

        terms = []
        for i in range(params['num_terms']):
            coeff = self._random_coefficient(params)
            if i > 0:
                coeff = coeff if np.random.random() > 0.5 else -coeff
            power = self._random_power(params)
            # Avoid duplicate powers
            while any(t.as_coeff_exponent(symbol)[1] == power for t in terms):
                power = self._random_power(params)
            terms.append(coeff * symbol**power)

        return sum(terms)

    def _random_function(self, params: dict, symbol=None) -> sp.Expr:
        """Generate a random function (polynomial, trig, or exponential)."""
        if symbol is None:
            symbol = self.x

        # Start with polynomial
        expr = self._random_polynomial(params, symbol)

        # Maybe add trig
        if params.get('use_trig') and np.random.random() > 0.5:
            coeff = self._random_coefficient(params)
            trig_func = np.random.choice([sp.sin, sp.cos])
            expr = expr + coeff * trig_func(symbol)

        # Maybe add exponential
        if params.get('use_exp') and np.random.random() > 0.5:
            coeff = self._random_coefficient(params)
            sign = 1 if np.random.random() > 0.5 else -1
            expr = expr + coeff * sp.exp(sign * symbol)

        return expr
