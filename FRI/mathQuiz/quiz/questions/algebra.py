"""
Algebra question generators.

Includes equations, matrices, number theory, and complex numbers.
"""

import numpy as np
import sympy as sp
from sympy import Rational, sqrt, Matrix, gcd, lcm, I, re, im, factorial
from math import gcd as math_gcd

from .base import Question, QuestionGenerator, QuestionCategory, PlotData
from ..difficulty import DifficultyLevel


class LinearEquationQuestion(QuestionGenerator):
    """Generate linear equation questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.EASY)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        a = np.random.randint(2, 8)
        x_sol = np.random.randint(-5, 10)
        b = np.random.randint(-10, 10)
        c = a * x_sol + b

        text = "Solve for x:"
        latex = rf"{a}x + {b} = {c}"

        explanation = f"x = {x_sol}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=x_sol,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Isolate x by moving terms.",
            answer_type="numeric"
        )


class QuadraticEquationQuestion(QuestionGenerator):
    """Generate quadratic equation questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        r1 = np.random.randint(-5, 6)
        r2 = np.random.randint(-5, 6)

        b = -(r1 + r2)
        c = r1 * r2
        solutions = sorted([r1, r2])

        text = "Solve the quadratic (enter as [x1, x2]):"
        latex = rf"x^2 {'+' if b >= 0 else ''}{b}x {'+' if c >= 0 else ''}{c} = 0"

        explanation = f"Solutions: x = {r1}, x = {r2}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=solutions,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Factor or use quadratic formula.",
            answer_type="list"
        )


class GCDQuestion(QuestionGenerator):
    """Generate greatest common divisor questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty <= DifficultyLevel.EASY:
            a = np.random.randint(10, 40)
            b = np.random.randint(10, 40)
        else:
            # Keep numbers manageable for pen-and-paper
            a = np.random.randint(24, 72)
            b = np.random.randint(24, 72)

        result = math_gcd(a, b)

        text = "Find the greatest common divisor (GCD):"
        latex = rf"\gcd({a}, {b})"

        explanation = f"GCD({a}, {b}) = {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Use prime factorization or Euclidean algorithm.",
            answer_type="numeric"
        )


class LCMQuestion(QuestionGenerator):
    """Generate least common multiple questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty <= DifficultyLevel.EASY:
            a = np.random.randint(4, 12)
            b = np.random.randint(4, 12)
        else:
            # Keep numbers manageable for pen-and-paper
            a = np.random.randint(6, 18)
            b = np.random.randint(6, 18)

        result = (a * b) // math_gcd(a, b)

        text = "Find the least common multiple (LCM):"
        latex = rf"\text{{lcm}}({a}, {b})"

        explanation = f"LCM({a}, {b}) = {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="LCM(a,b) = (a×b)/GCD(a,b)",
            answer_type="numeric"
        )


class ComplexNumberQuestion(QuestionGenerator):
    """Generate complex number questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty <= DifficultyLevel.EASY:
            # Addition/subtraction
            a1, b1 = np.random.randint(1, 6), np.random.randint(1, 6)
            a2, b2 = np.random.randint(1, 6), np.random.randint(1, 6)
            z1 = a1 + b1*I
            z2 = a2 + b2*I

            op = np.random.choice(['+', '-'])
            if op == '+':
                result = z1 + z2
            else:
                result = z1 - z2

            text = f"Simplify ({a1}+{b1}i) {op} ({a2}+{b2}i):"
            latex = rf"({a1}+{b1}i) {op} ({a2}+{b2}i)"

        elif difficulty == DifficultyLevel.MEDIUM:
            # Multiplication
            a1, b1 = np.random.randint(1, 5), np.random.randint(1, 5)
            a2, b2 = np.random.randint(1, 5), np.random.randint(1, 5)
            z1 = a1 + b1*I
            z2 = a2 + b2*I
            result = sp.expand(z1 * z2)

            text = f"Multiply ({a1}+{b1}i)({a2}+{b2}i):"
            latex = rf"({a1}+{b1}i)({a2}+{b2}i)"

        elif difficulty == DifficultyLevel.HARD:
            # Modulus
            a, b = np.random.randint(3, 8), np.random.randint(3, 8)
            result = sqrt(a**2 + b**2)

            text = f"Find the modulus |{a}+{b}i|:"
            latex = rf"|{a}+{b}i|"

        else:  # VERY_HARD
            # Division of complex numbers
            a1, b1 = np.random.randint(2, 6), np.random.randint(2, 6)
            a2, b2 = np.random.randint(1, 4), np.random.randint(1, 4)
            z1 = a1 + b1*I
            z2 = a2 + b2*I
            result = sp.simplify(z1 / z2)

            text = f"Divide and simplify ({a1}+{b1}i) / ({a2}+{b2}i):"
            latex = rf"\frac{{{a1}+{b1}i}}{{{a2}+{b2}i}}"

        explanation = f"Answer: {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Remember i² = -1. Modulus: |a+bi| = √(a²+b²)",
            answer_type="expression"
        )


class FactorialQuestion(QuestionGenerator):
    """Generate factorial questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty <= DifficultyLevel.EASY:
            n = np.random.randint(3, 7)
            result = int(factorial(n))
            text = f"Calculate {n}!:"
            latex = rf"{n}!"

        else:  # MEDIUM - ratio of factorials
            n = np.random.randint(5, 9)
            k = np.random.randint(2, 4)
            result = int(factorial(n) // factorial(n - k))

            text = f"Simplify:"
            latex = rf"\frac{{{n}!}}{{{n-k}!}}"

        explanation = f"Answer: {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="n! = n × (n-1) × ... × 2 × 1",
            answer_type="numeric"
        )


class EigenvalueQuestion(QuestionGenerator):
    """Generate simple eigenvalue questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # Generate 2x2 matrix with nice eigenvalues
        # Use diagonal or triangular for simple eigenvalues
        if np.random.random() > 0.5:
            # Diagonal matrix - eigenvalues are diagonal entries
            e1 = np.random.randint(-3, 5)
            e2 = np.random.randint(-3, 5)
            M = Matrix([[e1, 0], [0, e2]])
        else:
            # Upper triangular - eigenvalues are diagonal entries
            e1 = np.random.randint(-3, 5)
            e2 = np.random.randint(-3, 5)
            c = np.random.randint(-3, 4)
            M = Matrix([[e1, c], [0, e2]])

        eigenvalues = sorted([e1, e2])

        m = M.tolist()
        # Convert to int for formatting
        m00, m01 = int(m[0][0]), int(m[0][1])
        m10, m11 = int(m[1][0]), int(m[1][1])
        # Display matrix in text since matplotlib doesn't support pmatrix
        text = f"Find the eigenvalues of the matrix (enter as [λ1, λ2]):\n"
        text += f"┌ {m00:3}  {m01:3} ┐\n"
        text += f"└ {m10:3}  {m11:3} ┘"
        latex = ""  # No LaTeX - matrix shown in text

        explanation = f"Eigenvalues: {eigenvalues}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=eigenvalues,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="For triangular matrices, eigenvalues are the diagonal entries.",
            answer_type="list"
        )


class MatrixDeterminantQuestion(QuestionGenerator):
    """Generate matrix determinant questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # 2x2 matrix
        a = np.random.randint(0, 6)
        b = np.random.randint(0, 6)
        c = np.random.randint(0, 6)
        d = np.random.randint(0, 6)

        M = Matrix([[a, b], [c, d]])
        det = int(M.det())

        # Display matrix with vertical bars for determinant
        text = f"Calculate the determinant:\n"
        text += f"│ {a:2}  {b:2} │\n"
        text += f"│ {c:2}  {d:2} │"
        latex = ""  # No LaTeX - matrix shown in text

        explanation = f"det = ad - bc = ({a})({d}) - ({b})({c}) = {det}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=det,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="For 2×2: det = ad - bc",
            answer_type="numeric"
        )


class EliminateVariableQuestion(QuestionGenerator):
    """Generate variable elimination questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x, y = sp.symbols('x y')

        # Generate two equations with integer solution
        x_sol = np.random.randint(-3, 5)
        y_sol = np.random.randint(-3, 5)

        a1 = np.random.randint(1, 4)
        b1 = np.random.randint(1, 4)
        a2 = np.random.randint(1, 4)
        b2 = np.random.randint(1, 4)

        # Ensure non-degenerate
        while a1 * b2 == a2 * b1:
            b2 = np.random.randint(1, 4)

        c1 = a1 * x_sol + b1 * y_sol
        c2 = a2 * x_sol + b2 * y_sol

        text = "Solve the system (enter as [x, y]):"
        latex = rf"{a1}x + {b1}y = {c1}, \quad {a2}x + {b2}y = {c2}"

        explanation = f"Solution: x = {x_sol}, y = {y_sol}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=[x_sol, y_sol],
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Use substitution or elimination.",
            answer_type="list"
        )


class FractionQuestion(QuestionGenerator):
    """Generate fraction arithmetic questions."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.EASY)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        a = np.random.randint(1, 6)
        b = np.random.randint(2, 7)
        c = np.random.randint(1, 6)
        d = np.random.randint(2, 7)

        frac1 = Rational(a, b)
        frac2 = Rational(c, d)

        op = np.random.choice(['+', '-'])
        if op == '+':
            result = frac1 + frac2
        else:
            result = frac1 - frac2

        text = "Calculate:"
        latex = rf"\frac{{{a}}}{{{b}}} {op} \frac{{{c}}}{{{d}}}"

        explanation = f"Answer: {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Find common denominator.",
            answer_type="expression"
        )


class AlgebraQuestions:
    """Factory class for algebra question generators."""

    GENERATORS = [
        LinearEquationQuestion,
        QuadraticEquationQuestion,
        GCDQuestion,
        LCMQuestion,
        ComplexNumberQuestion,
        FactorialQuestion,
        EigenvalueQuestion,
        MatrixDeterminantQuestion,
        EliminateVariableQuestion,
        FractionQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            # Fallback: use a generator appropriate for the difficulty
            if difficulty >= DifficultyLevel.HARD:
                return EigenvalueQuestion().generate(DifficultyLevel.HARD)
            else:
                return LinearEquationQuestion().generate(DifficultyLevel.EASY)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
