"""
Physics-flavored math questions.

These are optional questions that can be enabled in preferences.
All physics questions clearly specify whether units are required.
"""

import numpy as np
import sympy as sp
from sympy import sin, cos, exp, sqrt, pi, Rational

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


class KinematicsQuestion(QuestionGenerator):
    """Generate kinematics problems with varied formulas."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # Choose from different kinematics formulas
        formula_type = np.random.randint(0, 4)

        if formula_type == 0:
            # v = v0 + at (find final velocity)
            v0 = np.random.randint(5, 20)
            a = np.random.randint(2, 8)
            t = np.random.randint(2, 5)
            answer = v0 + a * t

            text = "Find the final velocity (answer as number only, no units):"
            latex = rf"v_0 = {v0} \text{{ m/s}}, \quad a = {a} \text{{ m/s}}^2, \quad t = {t} \text{{ s}}"
            explanation = f"v = v₀ + at = {v0} + {a}×{t} = {answer} m/s"
            hint = "Use v = v₀ + at"

        elif formula_type == 1:
            # x = x0 + v0*t + 0.5*a*t^2 (find displacement)
            v0 = np.random.randint(0, 10)
            a = np.random.randint(2, 6)
            t = np.random.randint(2, 4)
            answer = v0 * t + (a * t * t) // 2

            text = "Find the displacement (answer as number only, no units):"
            latex = rf"v_0 = {v0} \text{{ m/s}}, \quad a = {a} \text{{ m/s}}^2, \quad t = {t} \text{{ s}}"
            explanation = f"x = v₀t + ½at² = {v0}×{t} + ½×{a}×{t}² = {answer} m"
            hint = "Use x = v₀t + ½at²"

        elif formula_type == 2:
            # v = v0 + at (find acceleration given v, v0, t)
            v0 = np.random.randint(5, 15)
            v = v0 + np.random.randint(2, 6) * np.random.randint(2, 5)
            t = np.random.randint(2, 5)
            # Ensure integer acceleration
            a = (v - v0) // t
            v = v0 + a * t  # Recalculate to ensure consistency
            answer = a

            text = "Find the acceleration (answer as number only, no units):"
            latex = rf"v_0 = {v0} \text{{ m/s}}, \quad v = {v} \text{{ m/s}}, \quad t = {t} \text{{ s}}"
            explanation = f"a = (v - v₀)/t = ({v} - {v0})/{t} = {answer} m/s²"
            hint = "Rearrange v = v₀ + at to find a"

        else:
            # v = v0 + at (find time given v, v0, a)
            v0 = np.random.randint(5, 15)
            a = np.random.randint(2, 6)
            t = np.random.randint(2, 5)
            v = v0 + a * t
            answer = t

            text = "Find the time (answer as number only, no units):"
            latex = rf"v_0 = {v0} \text{{ m/s}}, \quad v = {v} \text{{ m/s}}, \quad a = {a} \text{{ m/s}}^2"
            explanation = f"t = (v - v₀)/a = ({v} - {v0})/{a} = {answer} s"
            hint = "Rearrange v = v₀ + at to find t"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric"
        )


class WorkEnergyQuestion(QuestionGenerator):
    """Generate work and energy problems."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        F = np.random.randint(10, 50)
        d = np.random.randint(2, 10)
        W = F * d

        text = "Calculate the work done (answer as number only, no units):"
        latex = rf"F = {F} \text{{ N}}, \quad d = {d} \text{{ m}}"

        explanation = f"W = F × d = {F} × {d} = {W} J"

        return Question(
            text=text,
            latex=latex,
            correct_answer=W,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Work = Force × Distance",
            answer_type="numeric"
        )


class VectorMagnitudeQuestion(QuestionGenerator):
    """Generate vector magnitude problems."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # Use Pythagorean triples for nice answers
        triples = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (6, 8, 10)]
        a, b, c = triples[np.random.randint(0, len(triples))]

        text = "Find the magnitude of the vector (answer as number only):"
        latex = rf"\vec{{v}} = ({a}, {b})"

        explanation = f"|v| = √({a}² + {b}²) = √{a**2 + b**2} = {c}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=c,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="|v| = √(x² + y²)",
            answer_type="numeric"
        )


class SimpleHarmonicMotionQuestion(QuestionGenerator):
    """Generate simple harmonic motion questions."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        A = np.random.randint(2, 6)
        omega = np.random.randint(2, 5)

        # Maximum velocity = A * omega
        v_max = A * omega

        text = f"An oscillator has x(t) = {A}cos({omega}t). Find maximum speed (number only):"
        latex = rf"x(t) = {A}\cos({omega}t)"

        explanation = f"v(t) = -{A}×{omega}×sin({omega}t), so |v|_max = {A}×{omega} = {v_max}"

        return Question(
            text=text,
            latex=latex,
            correct_answer=v_max,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint="Maximum speed = Amplitude × Angular frequency",
            answer_type="numeric"
        )


class ProjectileMotionQuestion(QuestionGenerator):
    """Generate projectile motion problems (2D kinematics)."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        g = 10  # Use g=10 for cleaner numbers

        if difficulty == DifficultyLevel.HARD:
            # Find max height or range with simple angles
            problem_type = np.random.randint(0, 2)

            if problem_type == 0:
                # Max height: h = v0^2 sin^2(θ) / (2g)
                # Use θ = 90° (straight up) for simplicity
                v0 = np.random.choice([10, 20, 30, 40])
                h_max = (v0 * v0) // (2 * g)
                answer = h_max

                text = f"A ball is thrown straight up with initial speed {v0} m/s.\nFind the maximum height (use g = {g} m/s², answer as number only):"
                latex = rf"v_0 = {v0} \text{{ m/s}}, \quad g = {g} \text{{ m/s}}^2"
                explanation = f"h_max = v₀²/(2g) = {v0}²/(2×{g}) = {answer} m"
                hint = "At max height, all kinetic energy converts to potential energy: ½mv₀² = mgh"

            else:
                # Time of flight for vertical throw: t = 2v0/g
                v0 = np.random.choice([10, 20, 30, 40, 50])
                t_total = (2 * v0) // g
                answer = t_total

                text = f"A ball is thrown straight up with initial speed {v0} m/s.\nFind the total time in the air (use g = {g} m/s², answer as number only):"
                latex = rf"v_0 = {v0} \text{{ m/s}}, \quad g = {g} \text{{ m/s}}^2"
                explanation = f"t_total = 2v₀/g = 2×{v0}/{g} = {answer} s"
                hint = "Time up = v₀/g, total time = 2 × time up"

        else:  # VERY_HARD
            # 2D projectile with 45° angle (max range)
            v0 = np.random.choice([10, 20, 30, 40])
            # Range at 45°: R = v0^2/g
            R = (v0 * v0) // g
            answer = R

            text = f"A projectile is launched at 45° with initial speed {v0} m/s.\nFind the horizontal range (use g = {g} m/s², answer as number only):"
            latex = rf"v_0 = {v0} \text{{ m/s}}, \quad \theta = 45°, \quad g = {g} \text{{ m/s}}^2"
            explanation = f"R = v₀²sin(2θ)/g = {v0}²×sin(90°)/{g} = {v0}²/{g} = {answer} m"
            hint = "Range formula: R = v₀²sin(2θ)/g. At 45°, sin(90°) = 1"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric"
        )


class EnergyConservationQuestion(QuestionGenerator):
    """Generate energy conservation problems."""

    CATEGORY = QuestionCategory.PHYSICS
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        g = 10  # Use g=10 for cleaner numbers

        if difficulty == DifficultyLevel.HARD:
            # Object dropped from height - find final velocity
            h = np.random.choice([5, 10, 20, 45, 80])
            # v = sqrt(2gh)
            v_squared = 2 * g * h
            v = int(np.sqrt(v_squared))
            answer = v

            text = f"An object is dropped from height {h} m.\nFind its speed just before hitting the ground (use g = {g} m/s², answer as number only):"
            latex = rf"h = {h} \text{{ m}}, \quad g = {g} \text{{ m/s}}^2"
            explanation = f"Using mgh = ½mv²: v = √(2gh) = √(2×{g}×{h}) = √{v_squared} = {answer} m/s"
            hint = "Use energy conservation: mgh = ½mv², solve for v"

        else:  # VERY_HARD
            # Pendulum or ramp with initial velocity
            problem_type = np.random.randint(0, 2)

            if problem_type == 0:
                # Object with initial velocity going up a ramp - find max height
                v0 = np.random.choice([10, 20, 30])
                # h = v0^2 / (2g)
                h = (v0 * v0) // (2 * g)
                answer = h

                text = f"An object slides up a frictionless ramp with initial speed {v0} m/s.\nHow high does it rise? (use g = {g} m/s², answer as number only):"
                latex = rf"v_0 = {v0} \text{{ m/s}}, \quad g = {g} \text{{ m/s}}^2"
                explanation = f"Using ½mv₀² = mgh: h = v₀²/(2g) = {v0}²/(2×{g}) = {answer} m"
                hint = "Initial kinetic energy converts entirely to potential energy at max height"

            else:
                # Object sliding down then up - find final height
                h1 = np.random.choice([10, 20, 30, 40])
                # Energy conserved: mgh1 = mgh2, so h2 = h1 (frictionless)
                answer = h1

                text = f"A ball rolls down a frictionless hill of height {h1} m, then up another hill.\nWhat maximum height does it reach on the second hill? (answer as number only):"
                latex = rf"h_1 = {h1} \text{{ m}}"
                explanation = f"Energy conservation: mgh₁ = mgh₂, so h₂ = h₁ = {answer} m"
                hint = "On a frictionless surface, mechanical energy is conserved"

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric"
        )


class PhysicsQuestions:
    """Factory class for physics question generators."""

    GENERATORS = [
        KinematicsQuestion,
        WorkEnergyQuestion,
        VectorMagnitudeQuestion,
        SimpleHarmonicMotionQuestion,
        ProjectileMotionQuestion,
        EnergyConservationQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            return KinematicsQuestion().generate(difficulty)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
