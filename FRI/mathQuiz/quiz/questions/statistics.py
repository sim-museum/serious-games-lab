"""
Statistics question generators.

Questions inspired by "No BS Statistics" by Ivan Savov.
Covers descriptive statistics, probability, distributions, and inference.
Higher point value advanced questions with graphical augmentation.
All questions are multiple choice for pen-and-paper solving.
"""

import numpy as np
import sympy as sp
from sympy import Rational, sqrt, factorial, binomial as sp_binomial
from typing import List, Tuple
from scipy import stats
import random

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


def generate_choices(correct: float, num_choices: int = 4, spread: float = 0.3) -> List[Tuple[str, float]]:
    """Generate multiple choice options with one correct answer and plausible distractors."""
    choices = [(f"{correct:.4f}", correct)]

    # Generate distractors
    attempts = 0
    while len(choices) < num_choices and attempts < 50:
        attempts += 1
        # Create distractor by adding/subtracting a percentage
        offset = random.uniform(-spread, spread)
        if abs(offset) < 0.05:
            offset = 0.1 if random.random() > 0.5 else -0.1
        distractor = correct * (1 + offset)
        distractor = round(distractor, 4)

        # Make sure it's different from existing choices
        if all(abs(distractor - c[1]) > 0.001 for c in choices):
            choices.append((f"{distractor:.4f}", distractor))

    # If we still need more choices, add some fixed offsets
    fixed_offsets = [0.1, -0.1, 0.2, -0.2, 0.15, -0.15]
    for offset in fixed_offsets:
        if len(choices) >= num_choices:
            break
        distractor = round(correct + offset, 4)
        if distractor > 0 and all(abs(distractor - c[1]) > 0.001 for c in choices):
            choices.append((f"{distractor:.4f}", distractor))

    random.shuffle(choices)
    return choices[:num_choices]


def generate_int_choices(correct: int, num_choices: int = 4) -> List[Tuple[str, int]]:
    """Generate multiple choice options for integer answers."""
    choices = [(str(correct), correct)]

    offsets = [-2, -1, 1, 2, 3, -3, 4, -4]
    random.shuffle(offsets)

    for offset in offsets:
        if len(choices) >= num_choices:
            break
        distractor = correct + offset
        if distractor >= 0 and all(d[1] != distractor for d in choices):
            choices.append((str(distractor), distractor))

    random.shuffle(choices)
    return choices[:num_choices]


class DescriptiveStatsQuestion(QuestionGenerator):
    """Generate questions about mean, median, variance, standard deviation."""

    CATEGORY = QuestionCategory.STATISTICS
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # Mean of small dataset
            n = np.random.randint(4, 7)
            data = [np.random.randint(1, 20) for _ in range(n)]
            answer = sum(data) / len(data)

            text = f"Find the mean of the dataset: {data}"
            latex = f"\\bar{{x}} = \\frac{{1}}{{n}}\\sum_{{i=1}}^{{n}} x_i"
            explanation = f"Mean = ({' + '.join(map(str, data))}) / {n} = {answer}"
            hint = "Sum all values and divide by the count."

            # Histogram visualization
            plot_data = {
                'histogram': data,
                'title': f"Dataset (mean = {answer:.2f})",
                'xlabel': 'Value',
                'ylabel': 'Frequency'
            }

        elif difficulty == DifficultyLevel.MEDIUM:
            # Median or mode
            choice = np.random.randint(0, 2)
            n = np.random.randint(5, 9)

            if choice == 0:
                # Median
                data = sorted([np.random.randint(1, 30) for _ in range(n)])
                if n % 2 == 1:
                    answer = data[n // 2]
                else:
                    answer = (data[n // 2 - 1] + data[n // 2]) / 2

                text = f"Find the median of the dataset: {data}"
                latex = ""
                explanation = f"Sorted data: {data}. Median = {answer}"
                hint = "Sort the data and find the middle value(s)."
            else:
                # Standard deviation (population)
                data = [np.random.randint(1, 15) for _ in range(5)]
                mean = sum(data) / len(data)
                variance = sum((x - mean)**2 for x in data) / len(data)
                answer = round(np.sqrt(variance), 2)

                text = f"Find the population standard deviation of: {data}\n(Round to 2 decimal places)"
                latex = f"\\sigma = \\sqrt{{\\frac{{1}}{{n}}\\sum_{{i=1}}^{{n}} (x_i - \\bar{{x}})^2}}"
                explanation = f"Mean = {mean:.2f}, Variance = {variance:.4f}, σ = {answer}"
                hint = "First find the mean, then calculate variance, then take square root."

            plot_data = {
                'histogram': data,
                'title': "Dataset Distribution",
                'xlabel': 'Value',
                'ylabel': 'Frequency'
            }

        else:  # HARD
            # Z-score or percentile
            choice = np.random.randint(0, 2)

            if choice == 0:
                # Z-score calculation
                mean = np.random.randint(50, 100)
                std = np.random.randint(5, 15)
                x = mean + np.random.randint(-2, 3) * std

                answer = round((x - mean) / std, 2)

                text = f"A distribution has mean μ = {mean} and standard deviation σ = {std}.\nFind the z-score for x = {x}"
                latex = f"z = \\frac{{x - \\mu}}{{\\sigma}}"
                explanation = f"z = ({x} - {mean}) / {std} = {answer}"
                hint = "z = (x - μ) / σ"
                plot_data = None
            else:
                # Coefficient of variation
                data = [np.random.randint(10, 50) for _ in range(6)]
                mean = sum(data) / len(data)
                std = np.sqrt(sum((x - mean)**2 for x in data) / len(data))
                answer = round((std / mean) * 100, 1)

                text = f"Find the coefficient of variation (CV) as a percentage for: {data}\n(Round to 1 decimal place)"
                latex = f"CV = \\frac{{\\sigma}}{{\\mu}} \\times 100\\%"
                explanation = f"Mean = {mean:.2f}, Std = {std:.2f}, CV = {answer}%"
                hint = "CV = (standard deviation / mean) × 100%"

                plot_data = {
                    'histogram': data,
                    'title': "Dataset for CV Calculation",
                    'xlabel': 'Value',
                    'ylabel': 'Frequency'
                }

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            tolerance=0.05,
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class ProbabilityQuestion(QuestionGenerator):
    """Generate basic probability questions."""

    CATEGORY = QuestionCategory.STATISTICS
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # Simple probability (dice, coins, cards)
            choice = np.random.randint(0, 3)

            if choice == 0:
                # Dice
                outcomes = np.random.randint(1, 4)
                answer = round(outcomes / 6, 4)
                text = f"What is the probability of rolling {['a 1', 'a 1 or 2', 'a 1, 2, or 3'][outcomes-1]} on a fair six-sided die?"
                explanation = f"P = {outcomes}/6 = {answer}"
            elif choice == 1:
                # Coins
                n_heads = np.random.randint(1, 3)
                answer = 0.5 if n_heads == 1 else 0.25
                text = f"What is the probability of getting {['heads', 'two heads in a row'][n_heads-1]} with a fair coin?"
                explanation = f"P = (1/2)^{n_heads} = {answer}"
            else:
                # Cards
                suit_cards = np.random.choice(['hearts', 'spades', 'face cards'])
                if suit_cards == 'face cards':
                    answer = round(12 / 52, 4)
                    text = "What is the probability of drawing a face card (J, Q, K) from a standard deck?"
                    explanation = "P = 12/52 = 3/13 ≈ 0.2308"
                else:
                    answer = round(13 / 52, 4)
                    text = f"What is the probability of drawing a {suit_cards[:-1]} from a standard deck?"
                    explanation = f"P = 13/52 = 1/4 = 0.25"

            latex = ""
            hint = "P = favorable outcomes / total outcomes"
            plot_data = None

        elif difficulty == DifficultyLevel.MEDIUM:
            # Binomial probability or combinations
            choice = np.random.randint(0, 2)

            if choice == 0:
                # Combinations counting
                n = np.random.randint(5, 8)
                k = np.random.randint(2, n - 1)
                answer = int(sp_binomial(n, k))

                text = f"How many ways can you choose {k} items from {n} distinct items? (Order doesn't matter)"
                latex = f"\\binom{{{n}}}{{{k}}} = \\frac{{{n}!}}{{{k}!({n}-{k})!}}"
                explanation = f"C({n},{k}) = {n}! / ({k}! × {n-k}!) = {answer}"
                hint = "Use the combination formula: n! / (k!(n-k)!)"
            else:
                # Simple conditional probability
                # P(A|B) scenario
                p_b = np.random.choice([0.2, 0.25, 0.3, 0.4, 0.5])
                p_a_and_b = round(p_b * np.random.choice([0.2, 0.3, 0.4, 0.5]), 2)
                answer = round(p_a_and_b / p_b, 2)

                text = f"Given P(B) = {p_b} and P(A ∩ B) = {p_a_and_b}, find P(A|B)"
                latex = f"P(A|B) = \\frac{{P(A \\cap B)}}{{P(B)}}"
                explanation = f"P(A|B) = {p_a_and_b} / {p_b} = {answer}"
                hint = "Conditional probability: P(A|B) = P(A∩B) / P(B)"

            plot_data = None

        else:  # HARD
            # Bayes' theorem
            # Disease testing scenario
            prevalence = np.random.choice([0.01, 0.02, 0.05])
            sensitivity = np.random.choice([0.90, 0.95, 0.99])  # P(+|disease)
            specificity = np.random.choice([0.90, 0.95, 0.98])  # P(-|no disease)

            # P(disease|+) = P(+|disease)P(disease) / P(+)
            # P(+) = P(+|disease)P(disease) + P(+|no disease)P(no disease)
            p_pos = sensitivity * prevalence + (1 - specificity) * (1 - prevalence)
            answer = round((sensitivity * prevalence) / p_pos, 3)

            text = f"A test for a disease has:\n- Sensitivity (true positive rate): {sensitivity*100}%\n- Specificity (true negative rate): {specificity*100}%\n- Disease prevalence: {prevalence*100}%\n\nIf someone tests positive, what's the probability they have the disease?\n(Round to 3 decimal places)"
            latex = f"P(D|+) = \\frac{{P(+|D) \\cdot P(D)}}{{P(+)}}"
            explanation = f"Using Bayes' theorem:\nP(+) = {sensitivity}×{prevalence} + {1-specificity}×{1-prevalence} = {p_pos:.4f}\nP(D|+) = ({sensitivity}×{prevalence})/{p_pos:.4f} = {answer}"
            hint = "Use Bayes' theorem. First calculate P(+) using total probability."
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            tolerance=0.02,
            plot_data=plot_data,
            requires_plot=False
        )


class DistributionQuestion(QuestionGenerator):
    """Generate questions about probability distributions (multiple choice)."""

    CATEGORY = QuestionCategory.STATISTICS
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Normal distribution with well-known z-scores
            # Use the 68-95-99.7 rule
            mu = np.random.choice([50, 60, 70, 80, 100])
            sigma = np.random.choice([5, 10, 15])

            question_type = np.random.randint(0, 3)
            if question_type == 0:
                # P(X < μ) = 0.5
                answer = 0.5
                x = mu
                text = f"For a normal distribution with μ = {mu} and σ = {sigma},\nwhat is P(X < {x})?"
                explanation = f"P(X < μ) = 0.5 by symmetry"
                choices = [("0.50", 0.5), ("0.34", 0.34), ("0.68", 0.68), ("0.16", 0.16)]
            elif question_type == 1:
                # P(μ - σ < X < μ + σ) ≈ 0.68
                answer = 0.68
                a, b = mu - sigma, mu + sigma
                text = f"For a normal distribution with μ = {mu} and σ = {sigma},\nwhat is P({a} < X < {b})? (68-95-99.7 rule)"
                explanation = f"Within 1 standard deviation: ~68% of data"
                choices = [("≈0.68", 0.68), ("≈0.95", 0.95), ("≈0.50", 0.50), ("≈0.34", 0.34)]
            else:
                # P(μ - 2σ < X < μ + 2σ) ≈ 0.95
                answer = 0.95
                a, b = mu - 2*sigma, mu + 2*sigma
                text = f"For a normal distribution with μ = {mu} and σ = {sigma},\nwhat is P({a} < X < {b})? (68-95-99.7 rule)"
                explanation = f"Within 2 standard deviations: ~95% of data"
                choices = [("≈0.95", 0.95), ("≈0.68", 0.68), ("≈0.99", 0.99), ("≈0.50", 0.50)]

            random.shuffle(choices)
            latex = ""
            hint = "Use the 68-95-99.7 rule for normal distributions."
            plot_data = None

        elif difficulty == DifficultyLevel.HARD:
            # Simple expected value or variance
            question_type = np.random.randint(0, 2)

            if question_type == 0:
                # Expected value of simple distribution
                values = [1, 2, 3, 4]
                # Use simple fractions: 1/4 each (uniform) or other simple combos
                prob_type = np.random.randint(0, 2)
                if prob_type == 0:
                    probs = [0.25, 0.25, 0.25, 0.25]  # Uniform
                    expected = 2.5
                else:
                    probs = [0.1, 0.2, 0.3, 0.4]
                    expected = 1*0.1 + 2*0.2 + 3*0.3 + 4*0.4  # = 3.0

                answer = expected
                prob_str = ", ".join([f"P(X={v})={p}" for v, p in zip(values, probs)])
                text = f"Find E[X] for the distribution:\n{prob_str}"
                explanation = f"E[X] = Σx·P(X=x) = {' + '.join([f'{v}×{p}' for v, p in zip(values, probs)])} = {expected}"
                choices = [(f"{expected:.1f}", expected)]
                # Add distractors
                for d in [1.5, 2.0, 2.5, 3.0, 3.5]:
                    if d != expected and len(choices) < 4:
                        choices.append((f"{d:.1f}", d))
            else:
                # Z-score calculation
                mu = np.random.choice([50, 70, 100])
                sigma = np.random.choice([5, 10])
                # Choose x that gives nice z-score
                z = np.random.choice([-2, -1, 1, 2])
                x = mu + z * sigma
                answer = z

                text = f"For μ = {mu} and σ = {sigma}, what is the z-score for x = {x}?"
                explanation = f"z = (x - μ)/σ = ({x} - {mu})/{sigma} = {z}"
                choices = [(str(z), z) for z in [-2, -1, 1, 2]]

            random.shuffle(choices)
            latex = ""
            hint = "z = (x - μ)/σ or E[X] = Σx·P(X=x)"
            plot_data = None

        else:  # VERY_HARD
            # Binomial with simple numbers
            n = np.random.choice([4, 5, 6])
            p = 0.5  # Use p=0.5 for easier calculation
            k = np.random.randint(0, 3)

            # C(n,k) * (0.5)^n
            from math import comb
            prob = comb(n, k) * (0.5 ** n)
            answer = round(prob, 4)

            text = f"For a fair coin flipped {n} times, what is P(exactly {k} heads)?"
            explanation = f"P = C({n},{k}) × (1/2)^{n} = {comb(n,k)} × {0.5**n:.4f} = {answer}"
            choices = generate_choices(answer, 4, 0.5)

            random.shuffle(choices)
            latex = ""
            hint = "Use binomial probability: C(n,k) × p^k × (1-p)^(n-k)"
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="multiple_choice",
            tolerance=0.02,
            plot_data=plot_data,
            requires_plot=plot_data is not None,
            choices=choices
        )


class RegressionQuestion(QuestionGenerator):
    """Generate questions about correlation and linear regression."""

    CATEGORY = QuestionCategory.STATISTICS
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # Use only 3 data points for pen-and-paper calculations
        n = 3

        if difficulty == DifficultyLevel.HARD:
            # Simple slope calculation with nice numbers
            # Use x values that are easy to work with
            x_data = [1, 2, 3]
            # Generate y = mx + b with small noise for integer-ish answers
            slope = np.random.choice([1, 2, -1, -2])
            intercept = np.random.randint(0, 4)
            y_data = [slope * x + intercept for x in x_data]

            # x̄ = 2, so deviations are -1, 0, 1
            x_mean = 2
            y_mean = sum(y_data) / n
            # Slope = Σ(xi - x̄)(yi - ȳ) / Σ(xi - x̄)² = slope (exact for no noise)
            answer = slope

            text = f"Find the slope of the regression line for:\nx: {x_data}\ny: {y_data}"
            latex = ""
            explanation = f"x̄ = {x_mean}, ȳ = {y_mean:.1f}\nWith x deviations of -1, 0, 1:\nSlope = {answer}"
            hint = "Slope = Σ(xi - x̄)(yi - ȳ) / Σ(xi - x̄)². Note: x̄ = 2, so deviations are -1, 0, 1."

        else:  # VERY_HARD
            # Correlation questions with various data patterns
            question_variant = np.random.randint(0, 4)

            if question_variant == 0:
                # Perfect positive correlation: r = 1
                x_data = [1, 2, 3]
                y_data = [2, 4, 6]
                answer = 1.0
                corr_type = "perfect positive"
                hint = "Perfect linear relationship means r = ±1."
            elif question_variant == 1:
                # Perfect negative correlation: r = -1
                x_data = [1, 2, 3]
                y_data = [6, 4, 2]
                answer = -1.0
                corr_type = "perfect negative"
                hint = "Perfect linear relationship means r = ±1."
            elif question_variant == 2:
                # No correlation: r = 0
                x_data = [1, 2, 3]
                y_data = [2, 2, 2]  # Constant y means no correlation
                answer = 0.0
                corr_type = "no"
                hint = "When one variable doesn't change, there's no correlation."
            else:
                # Intercept calculation instead of correlation
                x_data = [0, 1, 2]
                slope = np.random.choice([1, 2, -1, -2])
                intercept = np.random.randint(1, 5)
                y_data = [slope * x + intercept for x in x_data]
                answer = intercept

                text = f"Find the y-intercept of the regression line for:\nx: {x_data}\ny: {y_data}"
                latex = ""
                explanation = f"The regression line is y = {slope}x + {intercept}, so intercept = {answer}"
                hint = "The y-intercept is where the line crosses the y-axis (x=0)."

                # Return early for intercept question
                plot_data = {
                    'scatter': (x_data, y_data),
                    'regression_line': True,
                    'hide_equation': True,
                    'title': "Scatter Plot",
                    'xlabel': 'x',
                    'ylabel': 'y'
                }

                return Question(
                    text=text,
                    latex=latex,
                    correct_answer=answer,
                    explanation=explanation,
                    category=self.CATEGORY,
                    difficulty=difficulty,
                    hint=hint,
                    answer_type="numeric",
                    tolerance=0.05,
                    plot_data=plot_data,
                    requires_plot=True
                )

            text = f"Calculate the correlation coefficient r for:\nx: {x_data}\ny: {y_data}"
            latex = ""
            explanation = f"This is {corr_type} linear correlation.\nr = {answer}"

        # Scatter plot with regression line (hide equation to not reveal the answer)
        plot_data = {
            'scatter': (x_data, y_data),
            'regression_line': True,
            'hide_equation': True,  # Don't show y=mx+b since we're asking for slope/correlation
            'title': "Scatter Plot",
            'xlabel': 'x',
            'ylabel': 'y'
        }

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            tolerance=0.05,
            plot_data=plot_data,
            requires_plot=True
        )


class StatisticsQuestions:
    """Factory class for statistics question generators."""

    GENERATORS = [
        DescriptiveStatsQuestion,
        ProbabilityQuestion,
        DistributionQuestion,
        RegressionQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            # Fallback
            if difficulty >= DifficultyLevel.HARD:
                return RegressionQuestion().generate(DifficultyLevel.HARD)
            elif difficulty >= DifficultyLevel.MEDIUM:
                return DistributionQuestion().generate(DifficultyLevel.MEDIUM)
            else:
                return DescriptiveStatsQuestion().generate(DifficultyLevel.EASY)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
