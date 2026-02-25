"""
Graph-based question generators.

These questions display plots and ask users to identify functions,
find intersections, roots, or analyze graph features.
"""

import numpy as np
import sympy as sp
from sympy import sin, cos, exp, sqrt, Rational
from typing import List, Tuple

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


class FunctionIdentificationQuestion(QuestionGenerator):
    """Generate questions where user identifies a function from its graph."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty == DifficultyLevel.EASY:
            # Linear functions
            a = np.random.randint(1, 4)
            b = np.random.randint(-3, 4)
            f = a * x + b
            func_type = "linear"

        elif difficulty == DifficultyLevel.MEDIUM:
            # Quadratic or simple trig
            choice = np.random.randint(0, 3)
            if choice == 0:
                a = np.random.randint(1, 3)
                b = np.random.randint(-2, 3)
                f = a * x**2 + b
                func_type = "quadratic"
            elif choice == 1:
                a = np.random.randint(1, 3)
                b = np.random.randint(0, 2)
                f = a * sin(x) + b
                func_type = "sine"
            else:
                a = np.random.randint(1, 3)
                b = np.random.randint(0, 2)
                f = a * cos(x) + b
                func_type = "cosine"

        else:  # HARD
            # Exponential or combined
            choice = np.random.randint(0, 3)
            if choice == 0:
                a = np.random.randint(1, 3)
                f = a * exp(x / 2)
                func_type = "exponential"
            elif choice == 1:
                a = np.random.randint(1, 2)
                b = np.random.randint(1, 3)
                f = a * x**2 + b * x
                func_type = "quadratic"
            else:
                a = np.random.randint(1, 2)
                b = np.random.randint(1, 3)
                f = a * cos(x) + b * exp(-x)
                func_type = "combined"

        # Create lambda for plotting
        f_lambda = sp.lambdify(x, f, modules=['numpy'])

        # Generate sample points to show
        sample_points = []
        for xi in [0, 1, 2]:
            yi = float(f.subs(x, xi))
            sample_points.append((xi, yi))

        text = "Identify the function from the graph.\n"
        text += "Sample values: " + ", ".join(f"f({p[0]})={p[1]:.2f}" for p in sample_points)
        latex = ""  # No LaTeX needed

        plot_data = {
            'x_range': (-3, 5),
            'functions': [(f_lambda, "f(x)", 'blue')],
            'title': "Identify this function"
        }

        explanation = f"The function is f(x) = {sp.latex(f)}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=f,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=f"This is a {func_type} function. Look at the shape and sample values.",
            answer_type="expression",
            plot_data=plot_data,
            requires_plot=True
        )


class IntersectionQuestion(QuestionGenerator):
    """Generate questions about finding function intersections."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        # Generate two functions that intersect nicely
        attempts = 0
        while attempts < 20:
            attempts += 1

            if difficulty == DifficultyLevel.MEDIUM:
                # Two lines or line and parabola
                choice = np.random.randint(0, 2)
                if choice == 0:
                    # Two lines: ax + b and cx + d
                    a = np.random.randint(1, 4)
                    b = np.random.randint(-3, 4)
                    c = np.random.randint(-3, 0)  # Different slope
                    d = np.random.randint(-3, 4)
                    f = a * x + b
                    g = c * x + d
                else:
                    # Line and simple parabola
                    f = x**2
                    b = np.random.randint(1, 5)
                    g = b * x
            elif difficulty == DifficultyLevel.HARD:
                # Quadratic and line
                a1 = np.random.randint(1, 3)
                b1 = np.random.randint(-2, 3)
                a2 = np.random.randint(1, 3)
                f = a1 * x**2 + b1
                g = a2 * x + np.random.randint(-2, 3)
            else:  # VERY_HARD
                # Two quadratics
                a1 = np.random.randint(1, 2)
                c1 = np.random.randint(-2, 3)
                a2 = -np.random.randint(1, 2)  # Opposite direction
                c2 = np.random.randint(-2, 3)
                f = a1 * x**2 + c1
                g = a2 * x**2 + c2

            # Find intersections
            try:
                solutions = sp.solve(f - g, x)
                # Filter for real solutions
                real_solutions = [s for s in solutions if s.is_real]
                # Filter for reasonable range
                real_solutions = [s for s in real_solutions if abs(float(s)) < 10]

                if len(real_solutions) >= 1:
                    break
            except:
                continue

        if attempts >= 20:
            # Fallback: simple intersection
            f = x**2
            g = 4 * sp.Integer(1)
            real_solutions = [sp.Integer(-2), sp.Integer(2)]

        # Create lambdas for plotting
        f_lambda = sp.lambdify(x, f, modules=['numpy'])
        g_lambda = sp.lambdify(x, g, modules=['numpy'])

        text = f"Find the x-coordinate(s) where f(x) and g(x) intersect.\n"
        text += f"f(x) = {f}\n"
        text += f"g(x) = {g}\n"
        if len(real_solutions) > 1:
            text += "Enter as [x1, x2] in ascending order."
        else:
            text += "Enter the x value."

        latex = ""  # No LaTeX, the functions are in the text

        plot_data = {
            'x_range': (-5, 5),
            'functions': [
                (f_lambda, f"f(x) = {f}", 'blue'),
                (g_lambda, f"g(x) = {g}", 'red')
            ],
            'title': "Find the intersection(s)"
        }

        # Format answer
        if len(real_solutions) == 1:
            answer = real_solutions[0]
        else:
            answer = sorted([float(s) for s in real_solutions])

        explanation = f"Setting f(x) = g(x): {f} = {g}\nSolutions: {real_solutions}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Set f(x) = g(x) and solve for x.",
            answer_type="list" if len(real_solutions) > 1 else "numeric",
            plot_data=plot_data,
            requires_plot=True
        )


class RootFindingQuestion(QuestionGenerator):
    """Generate questions about finding roots/zeros from a graph."""

    CATEGORY = QuestionCategory.ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty == DifficultyLevel.MEDIUM:
            # Quadratic with integer roots
            r1 = np.random.randint(-3, 4)
            r2 = np.random.randint(-3, 4)
            f = (x - r1) * (x - r2)
            f = sp.expand(f)
            roots = sorted(set([r1, r2]))

        else:  # HARD
            # Cubic with at least one integer root
            r1 = np.random.randint(-2, 3)
            r2 = np.random.randint(-2, 3)
            r3 = np.random.randint(-2, 3)
            f = (x - r1) * (x - r2) * (x - r3)
            f = sp.expand(f)
            roots = sorted(set([r1, r2, r3]))

        # Create lambda for plotting
        f_lambda = sp.lambdify(x, f, modules=['numpy'])

        f_latex = sp.latex(f)

        text = f"Find all x-intercepts (roots) of the function from the graph."
        if len(roots) > 1:
            text += "\nEnter as [x1, x2, ...] in ascending order."

        latex = f"f(x) = {f_latex}"

        plot_data = {
            'x_range': (-5, 5),
            'functions': [(f_lambda, f"f(x)", 'blue')],
            'title': "Find the roots (where f(x) = 0)"
        }

        answer = roots if len(roots) > 1 else roots[0]

        explanation = f"The roots are where f(x) = 0: x = {roots}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Look where the curve crosses the x-axis.",
            answer_type="list" if len(roots) > 1 else "numeric",
            plot_data=plot_data,
            requires_plot=True
        )


class GraphAnalysisQuestion(QuestionGenerator):
    """Generate questions about analyzing graph features (max, min, etc.)."""

    CATEGORY = QuestionCategory.CALCULUS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        x = self.x

        if difficulty == DifficultyLevel.MEDIUM:
            # Simple parabola - find vertex
            a = np.random.choice([-1, 1]) * np.random.randint(1, 3)
            h = np.random.randint(-2, 3)  # x of vertex
            k = np.random.randint(-2, 3)  # y of vertex
            f = a * (x - h)**2 + k
            f = sp.expand(f)

            if a > 0:
                question_type = "minimum"
                answer = k
            else:
                question_type = "maximum"
                answer = k

            text = f"From the graph, find the y-value of the {question_type}."

        else:  # HARD
            # Cubic - find local extrema
            # f(x) = x³ - 3x has extrema at x = ±1
            a = np.random.randint(1, 3)
            f = x**3 - 3 * a**2 * x

            # Derivative: 3x² - 3a² = 0 => x = ±a
            # f(a) = a³ - 3a³ = -2a³ (local min)
            # f(-a) = -a³ + 3a³ = 2a³ (local max)

            choice = np.random.randint(0, 2)
            if choice == 0:
                question_type = "local maximum"
                answer = 2 * a**3
                text = f"From the graph, find the y-value of the local maximum."
            else:
                question_type = "local minimum"
                answer = -2 * a**3
                text = f"From the graph, find the y-value of the local minimum."

        # Create lambda for plotting
        f_lambda = sp.lambdify(x, f, modules=['numpy'])

        f_latex = sp.latex(f)

        latex = f"f(x) = {f_latex}"

        plot_data = {
            'x_range': (-4, 4),
            'functions': [(f_lambda, f"f(x)", 'blue')],
            'title': f"Find the {question_type}"
        }

        explanation = f"The {question_type} value is y = {answer}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=f"Look for the highest or lowest point on the graph.",
            answer_type="numeric",
            plot_data=plot_data,
            requires_plot=True
        )


class GraphicalQuestions:
    """Factory class for graphical question generators."""

    GENERATORS = [
        FunctionIdentificationQuestion,
        IntersectionQuestion,
        RootFindingQuestion,
        GraphAnalysisQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            # Fallback: use appropriate difficulty
            if difficulty >= DifficultyLevel.HARD:
                return GraphAnalysisQuestion().generate(DifficultyLevel.HARD)
            elif difficulty >= DifficultyLevel.MEDIUM:
                return RootFindingQuestion().generate(DifficultyLevel.MEDIUM)
            else:
                return FunctionIdentificationQuestion().generate(DifficultyLevel.EASY)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
