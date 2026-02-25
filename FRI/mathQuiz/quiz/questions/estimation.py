"""
Estimation and "Street-Fighting Math" questions.

Inspired by Sanjoy Mahajan's "Street-Fighting Mathematics", these questions
emphasize:
- Order of magnitude reasoning
- Dimensional analysis
- Scaling arguments
- Educated guessing
- Approximation techniques

These questions have wider tolerances for answers (typically 10-20%)
and may award partial credit based on how close the estimate is.
"""

import numpy as np
import sympy as sp
from sympy import sqrt, pi, Rational, log

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


class OrderOfMagnitudeQuestion(QuestionGenerator):
    """Generate order-of-magnitude estimation questions."""

    CATEGORY = QuestionCategory.ESTIMATION
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        questions = []

        if difficulty == DifficultyLevel.EASY:
            # Simple powers of 10
            scenarios = [
                ("seconds in a day", 24 * 60 * 60, "24 × 60 × 60 ≈ 86,400"),
                ("seconds in an hour", 60 * 60, "60 × 60 = 3,600"),
                ("minutes in a week", 7 * 24 * 60, "7 × 24 × 60 = 10,080"),
                ("millimeters in a meter", 1000, "1 m = 1000 mm"),
            ]
            name, answer, hint = scenarios[np.random.randint(0, len(scenarios))]

            text = f"Estimate the number of {name}.\n"
            text += "Give your answer to the nearest power of 10 (e.g., 1000, 10000)."
            latex = ""  # No LaTeX for text questions
            explanation = f"Exact: {answer}\nOrder of magnitude: 10^{int(np.log10(answer))}"

        elif difficulty == DifficultyLevel.MEDIUM:
            # Slightly more involved
            scenarios = [
                ("heartbeats in a day (assume 70 bpm)", 70 * 60 * 24,
                 "70 × 60 × 24 ≈ 100,000"),
                ("steps to walk 5 km (assume 0.7m stride)", int(5000 / 0.7),
                 "5000m / 0.7m ≈ 7,000 steps"),
                ("breaths in 8 hours (assume 15/min)", 15 * 60 * 8,
                 "15 × 60 × 8 = 7,200"),
            ]
            name, answer, hint = scenarios[np.random.randint(0, len(scenarios))]

            text = f"Estimate: {name}\n"
            text += "Give an approximate numeric answer."
            latex = ""  # No LaTeX for text questions
            explanation = hint

        else:  # HARD
            # Fermi-style questions
            scenarios = [
                ("piano tuners in Chicago (pop ~2.7M)", 100,
                 "~500k households, ~5% have pianos → 25k pianos\n"
                 "Each tuned ~1/year, tuner does ~4/day × 250 days → ~1000/year\n"
                 "25k/1000 ≈ 25-100 tuners"),
                ("golf balls that fit in a school bus", 500000,
                 "Bus ~2.5m × 2m × 10m = 50 m³\n"
                 "Golf ball ~4cm diameter, packing ~60%\n"
                 "50 × 0.6 / (4/100)³ ≈ 500,000"),
            ]
            name, answer, hint = scenarios[np.random.randint(0, len(scenarios))]

            text = f"Fermi estimation: {name}\n"
            text += "Show your reasoning in your estimate. Accept ±50% error."
            latex = ""  # No LaTeX for text questions
            explanation = hint

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Break the problem into smaller, estimable pieces.",
            answer_type="numeric",
            tolerance=0.5 if difficulty == DifficultyLevel.HARD else 0.2
        )


class DimensionalAnalysisQuestion(QuestionGenerator):
    """Generate dimensional analysis questions."""

    CATEGORY = QuestionCategory.ESTIMATION
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Simple unit conversion chain
            conversions = [
                ("km/h to m/s", 1000/3600, "1 km/h × (1000 m/km) × (1 h/3600 s) ≈ 0.278 m/s",
                 "Convert 1 km/h to m/s"),
                ("mph to m/s", 1609.34/3600, "1 mph × (1609 m/mile) × (1 h/3600 s) ≈ 0.447 m/s",
                 "Convert 1 mph to m/s (approximately)"),
            ]
            name, answer, expl, text = conversions[np.random.randint(0, len(conversions))]

            latex = ""  # No LaTeX for text questions
            explanation = expl

        elif difficulty == DifficultyLevel.HARD:
            # Deduce formula from dimensions
            questions_list = [
                ("The period T of a pendulum depends on length L and gravity g.\n"
                 "Using dimensional analysis, T should be proportional to:",
                 "sqrt(L/g)",
                 "[T] = [L]^a [g]^b where [g] = L/T²\n"
                 "T¹ = L^a × (L/T²)^b = L^(a+b) × T^(-2b)\n"
                 "So -2b = 1 → b = -1/2, a + b = 0 → a = 1/2\n"
                 "T ∝ √(L/g)"),
                ("The drag force F on a sphere depends on velocity v, density ρ, and radius r.\n"
                 "F should be proportional to:",
                 "rho*v^2*r^2",
                 "[F] = MLT⁻² = [ρ]^a [v]^b [r]^c\n"
                 "M: a = 1; L: -3a + b + c = 1; T: -b = -2\n"
                 "So a=1, b=2, c=2 → F ∝ ρv²r²"),
            ]
            text, answer, explanation = questions_list[np.random.randint(0, len(questions_list))]
            latex = ""  # No LaTeX for text questions

        else:  # VERY_HARD
            # More complex dimensional reasoning
            text = ("The speed of waves on a string depends on tension T (force) "
                    "and linear mass density μ (kg/m).\n"
                    "Using dimensional analysis, wave speed v is proportional to:")
            answer = "sqrt(T/mu)"
            explanation = ("[v] = L/T, [T] = MLT⁻², [μ] = M/L\n"
                          "v = T^a × μ^b\n"
                          "L/T = (MLT⁻²)^a × (M/L)^b\n"
                          "M: a + b = 0 → b = -a\n"
                          "L: a - b = 1 → 2a = 1 → a = 1/2\n"
                          "T: -2a = -1 → a = 1/2 ✓\n"
                          "v ∝ √(T/μ)")
            latex = ""  # No LaTeX for text questions

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer if difficulty <= DifficultyLevel.MEDIUM else sp.sympify(answer.replace("mu", "mu")),
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Match dimensions on both sides. [length]=L, [time]=T, [mass]=M",
            answer_type="numeric" if difficulty == DifficultyLevel.MEDIUM else "expression",
            tolerance=0.1
        )


class ScalingQuestion(QuestionGenerator):
    """Generate scaling and proportionality questions."""

    CATEGORY = QuestionCategory.ESTIMATION
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Simple scaling
            scenarios = [
                ("If a cube's side length doubles, by what factor does its volume increase?",
                 8, "Volume ∝ L³, so 2³ = 8"),
                ("If a sphere's radius triples, by what factor does its surface area increase?",
                 9, "Area ∝ r², so 3² = 9"),
                ("If you double the radius of a pipe, by what factor does flow rate increase (laminar flow)?",
                 16, "Flow ∝ r⁴ (Hagen-Poiseuille), so 2⁴ = 16"),
            ]
            text, answer, explanation = scenarios[np.random.randint(0, len(scenarios))]
            latex = ""  # No LaTeX for text questions

        elif difficulty == DifficultyLevel.HARD:
            # Physical scaling
            scenarios = [
                ("A pendulum has period 2s. If its length is quadrupled, what's the new period?",
                 4, "T ∝ √L, so T_new = 2 × √4 = 4 s"),
                ("A car traveling at 30 mph has kinetic energy E. What's its KE at 60 mph relative to E?",
                 4, "KE ∝ v², so (60/30)² = 4"),
                ("A satellite orbits at height h with period T. At height 4h (from center doubled), new period?",
                 "2*sqrt(2)*T", "T ∝ r^(3/2), so T_new = T × 2^(3/2) = 2√2 T ≈ 2.83T"),
            ]
            text, answer, explanation = scenarios[np.random.randint(0, len(scenarios))]
            latex = ""  # No LaTeX for text questions

        else:  # VERY_HARD
            # Complex scaling argument
            text = ("An ant can lift 50 times its body weight. If we scaled an ant to human size "
                    "(keeping density the same), could it still lift 50× its weight?\n"
                    "By what factor would the weight-to-strength ratio change if we 100× the linear size?")
            answer = 100
            explanation = ("Strength ∝ muscle cross-section ∝ L²\n"
                          "Weight ∝ volume ∝ L³\n"
                          "Strength/Weight ∝ L²/L³ = 1/L\n"
                          "100× larger → 1/100 the relative strength\n"
                          "The giant ant could only lift 0.5× its weight!")
            latex = ""  # No LaTeX for text questions

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Identify what power of length each quantity scales with.",
            answer_type="numeric" if isinstance(answer, (int, float)) else "expression",
            tolerance=0.1
        )


class ApproximationQuestion(QuestionGenerator):
    """Generate approximation technique questions."""

    CATEGORY = QuestionCategory.ESTIMATION
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Simple approximations
            scenarios = [
                ("Approximate √(99) without a calculator.", 9.95,
                 "√99 ≈ √100 × √(1 - 1/100) ≈ 10 × (1 - 1/200) = 9.95"),
                ("Approximate √(50) without a calculator.", 7.07,
                 "√50 = √(49 × 50/49) ≈ 7 × √(1 + 1/49) ≈ 7 × 1.01 ≈ 7.07"),
                ("Approximate e^0.1 using first-order Taylor.", 1.1,
                 "e^x ≈ 1 + x for small x, so e^0.1 ≈ 1.1"),
            ]
            text, answer, explanation = scenarios[np.random.randint(0, len(scenarios))]
            latex = ""  # No LaTeX for text questions

        elif difficulty == DifficultyLevel.HARD:
            # Taylor series approximations
            scenarios = [
                ("Using sin(x) ≈ x for small x, approximate sin(0.1) radians.",
                 0.1, "For small x (in radians): sin(x) ≈ x\nsin(0.1) ≈ 0.1 (exact: 0.0998)"),
                ("Using cos(x) ≈ 1 - x²/2, approximate cos(0.2).",
                 0.98, "cos(0.2) ≈ 1 - (0.2)²/2 = 1 - 0.02 = 0.98"),
                ("Using (1+x)^n ≈ 1 + nx for small x, approximate 1.02^5.",
                 1.1, "(1.02)^5 ≈ 1 + 5×0.02 = 1.1 (exact: 1.104)"),
            ]
            text, answer, explanation = scenarios[np.random.randint(0, len(scenarios))]
            latex = ""  # No LaTeX for text questions

        else:  # VERY_HARD
            # Integration by estimation
            text = ("Estimate ∫₀¹ e^(-x²) dx using the trapezoid rule with just 2 points "
                    "(x=0 and x=1).")
            answer = (1 + 1/np.e) / 2  # ≈ 0.684
            explanation = ("f(0) = e^0 = 1\n"
                          "f(1) = e^(-1) ≈ 0.368\n"
                          "Trapezoid: (1/2)(f(0) + f(1)) × 1 = (1 + 0.368)/2 ≈ 0.684\n"
                          "(Exact value: ≈ 0.746)")
            latex = r"\int_0^1 \! e^{-x^2} \, dx"  # Pure math only

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Use Taylor series: e^x ≈ 1+x, sin(x) ≈ x, cos(x) ≈ 1-x²/2, (1+x)^n ≈ 1+nx",
            answer_type="numeric",
            tolerance=0.15  # Wider tolerance for approximations
        )


class QuickMentalMathQuestion(QuestionGenerator):
    """Generate quick mental math questions for warm-up."""

    CATEGORY = QuestionCategory.ESTIMATION
    DIFFICULTY_RANGE = (DifficultyLevel.VERY_EASY, DifficultyLevel.EASY)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.VERY_EASY:
            # Simple products
            a = np.random.randint(2, 10)
            b = np.random.randint(2, 10)
            answer = a * b
            text = f"Quick: {a} × {b} = ?"
            latex = rf"{a} \times {b}"  # Pure math, no $ delimiters
            explanation = f"{a} × {b} = {answer}"
        else:
            # Slightly harder
            ops = [
                lambda: (np.random.randint(10, 50), np.random.randint(10, 50), "+"),
                lambda: (np.random.randint(50, 100), np.random.randint(10, 40), "-"),
                lambda: (np.random.randint(2, 12), np.random.randint(10, 20), "×"),
            ]
            a, b, op = ops[np.random.randint(0, len(ops))]()

            if op == "+":
                answer = a + b
                latex_op = "+"
            elif op == "-":
                answer = a - b
                latex_op = "-"
            else:
                answer = a * b
                latex_op = r"\times"

            text = f"Quick: {a} {op} {b} = ?"
            latex = rf"{a} {latex_op} {b}"  # Pure math, no $ delimiters
            explanation = f"{a} {op} {b} = {answer}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Mental math - no calculator needed!",
            answer_type="numeric",
            tolerance=0.001  # Exact answer required
        )


class EstimationQuestions:
    """Factory class for estimation question generators."""

    GENERATORS = [
        OrderOfMagnitudeQuestion,
        DimensionalAnalysisQuestion,
        ScalingQuestion,
        ApproximationQuestion,
        QuickMentalMathQuestion,
    ]

    @classmethod
    def get_generators(cls) -> list:
        """Get all estimation question generators."""
        return [gen() for gen in cls.GENERATORS]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        """Generate a random estimation question at the given difficulty."""
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            return QuickMentalMathQuestion().generate(difficulty)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
