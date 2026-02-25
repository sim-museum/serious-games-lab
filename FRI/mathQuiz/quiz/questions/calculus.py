"""
Calculus question generators.

Includes derivatives, integrals, and related problems.
"""

import numpy as np
import sympy as sp
from sympy import sin, cos, exp, ln, sqrt, pi, Rational

from .base import Question, QuestionGenerator, QuestionCategory, PlotData
from ..difficulty import DifficultyLevel
from utils.unicode_math import format_expr


class DerivativeQuestion(QuestionGenerator):
    """Generate derivative questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        params = self.difficulty_to_params(difficulty)
        params['num_terms'] = min(params['num_terms'], 3)  # Keep it simple

        f = self._random_function(params, self.x)
        df = sp.diff(f, self.x)

        f_latex = sp.latex(f)

        text = "Find the derivative:"
        latex = rf"\frac{{d}}{{dx}}\left({f_latex}\right)"

        explanation = f"Answer: {format_expr(df)}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=df,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Apply the power rule and sum rule.",
            answer_type="expression"
        )


class IntegralQuestion(QuestionGenerator):
    """Generate indefinite integral questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        params = self.difficulty_to_params(difficulty)
        params['use_trig'] = False
        params['use_exp'] = False
        params['num_terms'] = min(2, params['num_terms'])

        f = self._generate_integrable_function(params)
        F = sp.integrate(f, self.x)

        f_latex = sp.latex(f)

        text = "Find the indefinite integral:"
        latex = rf"\int \, {f_latex} \, dx"

        explanation = f"Answer: {format_expr(F)} + C"

        return Question(
            text=text,
            latex=latex,
            correct_answer=F,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Remember: ∫xⁿ dx = xⁿ⁺¹/(n+1) + C",
            answer_type="expression"
        )

    def _generate_integrable_function(self, params: dict) -> sp.Expr:
        terms = []
        for i in range(params['num_terms']):
            coeff = self._random_coefficient(params)
            if i > 0 and np.random.random() > 0.5:
                coeff = -coeff
            power = self._random_power(params)
            terms.append(coeff * self.x**power)
        return sum(terms)


class DefiniteIntegralQuestion(QuestionGenerator):
    """Generate definite integral questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        coeff1 = np.random.randint(1, 4)
        coeff2 = np.random.randint(1, 4)
        power = np.random.randint(1, 3)

        f = coeff1 * self.x**power + coeff2
        a, b = 0, np.random.randint(1, 4)

        result = sp.integrate(f, (self.x, a, b))
        f_latex = sp.latex(f)

        text = "Evaluate the definite integral:"
        latex = rf"\int_{{{a}}}^{{{b}}} \! {f_latex} \, dx"

        explanation = f"Answer: {result}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=f"Integrate, then evaluate F({b}) - F({a})",
            answer_type="numeric"
        )


class LimitQuestion(QuestionGenerator):
    """Generate limit questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty <= DifficultyLevel.EASY:
            # Simple polynomial limit
            a = np.random.randint(1, 5)
            b = np.random.randint(-3, 4)
            f = a * x + b
            point = np.random.randint(1, 4)
            result = f.subs(x, point)

            f_latex = sp.latex(f)
            text = f"Evaluate the limit as x → {point}:"
            latex = rf"\lim_{{x \to {point}}} \left({f_latex}\right)"

        elif difficulty == DifficultyLevel.MEDIUM:
            # Rational function with cancellation
            a = np.random.randint(1, 4)
            point = np.random.randint(1, 3)
            # (x^2 - a^2)/(x - a) = x + a as x -> a
            f = (x**2 - point**2) / (x - point)
            result = 2 * point

            text = f"Evaluate the limit as x → {point}:"
            latex = rf"\lim_{{x \to {point}}} \frac{{x^2 - {point**2}}}{{x - {point}}}"

        else:  # HARD
            # sin(x)/x type
            a = np.random.randint(2, 5)
            f = sin(a * x) / x
            result = a

            text = "Evaluate the limit as x → 0:"
            latex = rf"\lim_{{x \to 0}} \frac{{\sin({a}x)}}{{x}}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=f"Answer: {result}",
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Try direct substitution first. If 0/0, factor or use L'Hôpital.",
            answer_type="numeric"
        )


class SimpleDiffEqQuestion(QuestionGenerator):
    """Generate simple differential equation questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty <= DifficultyLevel.MEDIUM:
            # dy/dx = ax, solution y = ax²/2 + C
            a = np.random.randint(2, 6)
            rhs = a * x
            solution = a * x**2 / 2

            rhs_latex = sp.latex(rhs)
            sol_latex = sp.latex(solution)

            text = "Solve the differential equation:"
            latex = rf"\frac{{dy}}{{dx}} = {rhs_latex}"
            explanation = f"Integrate both sides: y = {sol_latex} + C"

        else:  # HARD
            # dy/dx = ky, solution y = Ce^(kx)
            k = np.random.randint(2, 5)
            text = f"Solve the differential equation (general solution):"
            latex = rf"\frac{{dy}}{{dx}} = {k}y"
            solution = sp.exp(k * x)
            explanation = f"This is exponential growth/decay. y = Ce^{{{k}x}}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=solution,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Integrate or recognize the form of the equation.",
            answer_type="expression"
        )


class TaylorSeriesQuestion(QuestionGenerator):
    """Generate Taylor series expansion questions."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty <= DifficultyLevel.MEDIUM:
            # Ask for coefficient in known series
            choice = np.random.randint(0, 3)

            if choice == 0:
                # e^x = 1 + x + x²/2! + x³/3! + ...
                # Coefficient of x^n is 1/n!
                n = np.random.randint(2, 5)
                result = Rational(1, int(np.math.factorial(n)))
                text = f"In the Taylor series of e^x around x=0, what is the coefficient of x^{n}?"
                latex = rf"e^x = \sum_{{n=0}}^{{\infty}} \frac{{x^n}}{{n!}}"
                explanation = f"Coefficient of x^{n} is 1/{n}! = {result}"

            elif choice == 1:
                # sin(x) = x - x³/3! + x⁵/5! - ...
                # Ask about x³ coefficient (which is -1/6)
                result = Rational(-1, 6)
                text = "In the Taylor series of sin(x) around x=0, what is the coefficient of x³?"
                latex = rf"\sin(x) = x - \frac{{x^3}}{{3!}} + \frac{{x^5}}{{5!}} - \cdots"
                explanation = "Coefficient of x³ is -1/3! = -1/6"

            else:
                # cos(x) = 1 - x²/2! + x⁴/4! - ...
                # Ask about x² coefficient (which is -1/2)
                result = Rational(-1, 2)
                text = "In the Taylor series of cos(x) around x=0, what is the coefficient of x²?"
                latex = rf"\cos(x) = 1 - \frac{{x^2}}{{2!}} + \frac{{x^4}}{{4!}} - \cdots"
                explanation = "Coefficient of x² is -1/2! = -1/2"

        else:  # HARD
            # Compute first few terms of a series
            choice = np.random.randint(0, 2)

            if choice == 0:
                # 1/(1-x) = 1 + x + x² + x³ + ...
                # Ask: what is the sum of coefficients up to x²?
                result = 3  # 1 + 1 + 1 = 3
                text = "For 1/(1-x), find the sum of coefficients from x⁰ to x²:"
                latex = rf"\frac{{1}}{{1-x}} = 1 + x + x^2 + x^3 + \cdots"
                explanation = "Coefficients are all 1, so sum = 1 + 1 + 1 = 3"

            else:
                # ln(1+x) = x - x²/2 + x³/3 - ...
                # Coefficient of x³ is 1/3
                result = Rational(1, 3)
                text = "In the Taylor series of ln(1+x) around x=0, what is the coefficient of x³?"
                latex = rf"\ln(1+x) = x - \frac{{x^2}}{{2}} + \frac{{x^3}}{{3}} - \cdots"
                explanation = "Coefficient of x³ is 1/3"

        return Question(
            text=text,
            latex=latex,
            correct_answer=result,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Recall the standard Taylor series expansions.",
            answer_type="expression"
        )


class CalculusQuestions:
    """Factory class for calculus question generators."""

    GENERATORS = [
        DerivativeQuestion,
        IntegralQuestion,
        DefiniteIntegralQuestion,
        LimitQuestion,
        SimpleDiffEqQuestion,
        TaylorSeriesQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            return DerivativeQuestion().generate(difficulty)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
