"""
Linear Algebra question generators.

Questions inspired by "No BS Linear Algebra" by Ivan Savov.
Covers vectors, matrices, determinants, eigenvalues, and linear transformations.
Higher point value advanced questions with graphical augmentation.
"""

import numpy as np
import sympy as sp
from sympy import Matrix, Rational, sqrt, simplify
from typing import List, Tuple

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


def matrix_to_text(m: Matrix) -> str:
    """Convert a sympy Matrix to readable text format."""
    rows = m.tolist()
    return "[" + "; ".join([", ".join(map(str, row)) for row in rows]) + "]"


def matrix_to_rows(m: Matrix) -> str:
    """Convert a sympy Matrix to multi-line text format."""
    rows = m.tolist()
    max_width = max(len(str(item)) for row in rows for item in row)
    lines = []
    for row in rows:
        lines.append("[ " + "  ".join(str(item).rjust(max_width) for item in row) + " ]")
    return "\n".join(lines)


class VectorOperationsQuestion(QuestionGenerator):
    """Generate questions about vector operations (dot product, cross product, magnitude)."""

    CATEGORY = QuestionCategory.LINEAR_ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # 2D vector addition or scalar multiplication
            v1 = [np.random.randint(-5, 6), np.random.randint(-5, 6)]
            v2 = [np.random.randint(-5, 6), np.random.randint(-5, 6)]

            choice = np.random.randint(0, 2)
            if choice == 0:
                # Vector addition
                answer = [v1[0] + v2[0], v1[1] + v2[1]]
                text = f"Find u + v where u = {v1} and v = {v2}"
                latex = f"\\vec{{u}} + \\vec{{v}} = [{v1[0]}, {v1[1]}] + [{v2[0]}, {v2[1]}]"
                explanation = f"Add component-wise: [{v1[0]}+{v2[0]}, {v1[1]}+{v2[1]}] = {answer}"
                hint = "Add corresponding components."
            else:
                # Scalar multiplication
                scalar = np.random.randint(2, 5)
                answer = [scalar * v1[0], scalar * v1[1]]
                text = f"Find {scalar}v where v = {v1}"
                latex = f"{scalar}\\vec{{v}} = {scalar} \\cdot [{v1[0]}, {v1[1]}]"
                explanation = f"Multiply each component: [{scalar}*{v1[0]}, {scalar}*{v1[1]}] = {answer}"
                hint = "Multiply each component by the scalar."

            # Create plot showing the vectors
            plot_data = {
                'x_range': (-10, 10),
                'vectors': [
                    ((0, 0), (v1[0], v1[1]), 'blue', 'u' if choice == 0 else 'v'),
                ],
                'title': "Vector Visualization"
            }
            if choice == 0:
                plot_data['vectors'].append(((0, 0), (v2[0], v2[1]), 'red', 'v'))
                plot_data['vectors'].append(((0, 0), (answer[0], answer[1]), 'green', 'u+v'))

        elif difficulty == DifficultyLevel.MEDIUM:
            # Dot product or magnitude
            v1 = [np.random.randint(-4, 5), np.random.randint(-4, 5), np.random.randint(-4, 5)]
            v2 = [np.random.randint(-4, 5), np.random.randint(-4, 5), np.random.randint(-4, 5)]

            choice = np.random.randint(0, 2)
            if choice == 0:
                # Dot product
                answer = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2]
                text = f"Find u · v (dot product) where u = {v1} and v = {v2}"
                latex = f"\\vec{{u}} \\cdot \\vec{{v}} = [{v1[0]}, {v1[1]}, {v1[2]}] \\cdot [{v2[0]}, {v2[1]}, {v2[2]}]"
                explanation = f"u·v = {v1[0]}*{v2[0]} + {v1[1]}*{v2[1]} + {v1[2]}*{v2[2]} = {answer}"
                hint = "Multiply corresponding components and sum."
            else:
                # Magnitude
                mag_sq = v1[0]**2 + v1[1]**2 + v1[2]**2
                answer = sp.sqrt(mag_sq)
                text = f"Find the magnitude |v| where v = {v1}"
                latex = f"|\\vec{{v}}| = |[{v1[0]}, {v1[1]}, {v1[2]}]|"
                explanation = f"|v| = sqrt({v1[0]}² + {v1[1]}² + {v1[2]}²) = sqrt({mag_sq}) = {answer}"
                hint = "Use sqrt(x² + y² + z²)."

            plot_data = None  # 3D vectors harder to visualize simply

        else:  # HARD
            # Cross product
            v1 = [np.random.randint(-3, 4), np.random.randint(-3, 4), np.random.randint(-3, 4)]
            v2 = [np.random.randint(-3, 4), np.random.randint(-3, 4), np.random.randint(-3, 4)]

            # Cross product: [y1*z2 - z1*y2, z1*x2 - x1*z2, x1*y2 - y1*x2]
            answer = [
                v1[1]*v2[2] - v1[2]*v2[1],
                v1[2]*v2[0] - v1[0]*v2[2],
                v1[0]*v2[1] - v1[1]*v2[0]
            ]
            text = f"Find u × v (cross product) where u = {v1} and v = {v2}"
            latex = f"\\vec{{u}} \\times \\vec{{v}} = [{v1[0]}, {v1[1]}, {v1[2]}] \\times [{v2[0]}, {v2[1]}, {v2[2]}]"
            explanation = f"Using the determinant formula: [{answer[0]}, {answer[1]}, {answer[2]}]"
            hint = "Use the determinant formula with i, j, k unit vectors."
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="list" if isinstance(answer, list) else ("numeric" if isinstance(answer, (int, float)) else "expression"),
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class MatrixOperationsQuestion(QuestionGenerator):
    """Generate questions about matrix operations."""

    CATEGORY = QuestionCategory.LINEAR_ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # 2x2 matrix addition
            A = Matrix([[np.random.randint(-5, 6), np.random.randint(-5, 6)],
                       [np.random.randint(-5, 6), np.random.randint(-5, 6)]])
            B = Matrix([[np.random.randint(-5, 6), np.random.randint(-5, 6)],
                       [np.random.randint(-5, 6), np.random.randint(-5, 6)]])
            answer = A + B

            text = f"Find A + B where:\nA = {matrix_to_text(A)}\nB = {matrix_to_text(B)}"
            latex = ""
            explanation = f"Add element-wise: {matrix_to_text(answer)}"
            hint = "Add corresponding entries."
            answer_list = [[int(answer[i, j]) for j in range(2)] for i in range(2)]

        elif difficulty == DifficultyLevel.MEDIUM:
            # 2x2 matrix multiplication
            A = Matrix([[np.random.randint(-3, 4), np.random.randint(-3, 4)],
                       [np.random.randint(-3, 4), np.random.randint(-3, 4)]])
            B = Matrix([[np.random.randint(-3, 4), np.random.randint(-3, 4)],
                       [np.random.randint(-3, 4), np.random.randint(-3, 4)]])
            answer = A * B

            text = f"Find AB (matrix multiplication) where:\nA = {matrix_to_text(A)}\nB = {matrix_to_text(B)}"
            latex = ""
            explanation = f"Row × Column: {matrix_to_text(answer)}"
            hint = "Multiply rows of A by columns of B."
            answer_list = [[int(answer[i, j]) for j in range(2)] for i in range(2)]

        elif difficulty == DifficultyLevel.HARD:
            # 2x2 determinant
            a, b = np.random.randint(-4, 5), np.random.randint(-4, 5)
            c, d = np.random.randint(-4, 5), np.random.randint(-4, 5)
            A = Matrix([[a, b], [c, d]])
            answer = a*d - b*c

            text = f"Find det(A) where A = {matrix_to_text(A)}"
            latex = ""
            explanation = f"det = ad - bc = ({a})({d}) - ({b})({c}) = {answer}"
            hint = "For 2x2: det = ad - bc"
            answer_list = answer

        else:  # VERY_HARD
            # 2x2 matrix inverse (ensure invertible with nice inverse)
            # Removed 3x3 determinant as it's too tedious for pen and paper
            while True:
                a, d = np.random.randint(1, 4), np.random.randint(1, 4)
                b, c = np.random.randint(-2, 3), np.random.randint(-2, 3)
                det = a*d - b*c
                if det in [1, -1, 2, -2]:  # Nice determinant for integer inverse
                    break

            A = Matrix([[a, b], [c, d]])
            A_inv = A.inv()

            text = f"Find A⁻¹ (matrix inverse) where A = {matrix_to_text(A)}"
            latex = ""
            explanation = f"det = {det}, A⁻¹ = (1/{det}) × [[{d}, {-b}], [{-c}, {a}]] = {matrix_to_text(A_inv)}"
            hint = "For 2x2: A⁻¹ = (1/det) × [[d, -b], [-c, a]]"
            answer_list = [[float(A_inv[i, j]) for j in range(2)] for i in range(2)]

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer_list,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric" if isinstance(answer_list, (int, float)) else "list",
            plot_data=None,
            requires_plot=False
        )


class EigenvalueQuestion(QuestionGenerator):
    """Generate questions about eigenvalues and eigenvectors."""

    CATEGORY = QuestionCategory.LINEAR_ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        # Create matrix with known eigenvalues
        if difficulty == DifficultyLevel.HARD:
            # Diagonal matrix (trivial eigenvalues)
            e1, e2 = np.random.randint(-3, 4), np.random.randint(-3, 4)
            while e1 == e2:
                e2 = np.random.randint(-3, 4)
            A = Matrix([[e1, 0], [0, e2]])
            eigenvalues = sorted([e1, e2])

            text = f"Find the eigenvalues of A where A = {matrix_to_text(A)}"
            latex = ""
            explanation = f"For diagonal matrices, eigenvalues are the diagonal entries: {eigenvalues}"
            hint = "For diagonal matrices, eigenvalues are on the diagonal."

        else:  # VERY_HARD
            # Create matrix with integer eigenvalues using similarity transform
            e1, e2 = np.random.randint(-3, 4), np.random.randint(-3, 4)

            # Simple 2x2 with known eigenvalues: trace = e1 + e2, det = e1 * e2
            # A = [[a, b], [c, d]] where a+d = e1+e2 and ad-bc = e1*e2
            trace = e1 + e2
            det = e1 * e2

            # Choose a = something, then d = trace - a
            a = np.random.randint(-2, 3)
            d = trace - a
            # ad - bc = det => bc = ad - det
            ad_minus_det = a * d - det

            # Factor ad_minus_det into b*c
            if ad_minus_det == 0:
                b, c = 0, np.random.randint(-2, 3)
            elif ad_minus_det > 0:
                # Find factors
                factors = [(i, ad_minus_det // i) for i in range(1, int(np.sqrt(ad_minus_det)) + 1) if ad_minus_det % i == 0]
                if factors:
                    b, c = factors[np.random.randint(len(factors))]
                    if np.random.random() > 0.5:
                        b, c = -b, -c
                else:
                    b, c = 1, ad_minus_det
            else:
                b, c = 1, -abs(ad_minus_det)

            A = Matrix([[a, b], [c, d]])
            eigenvalues = sorted([e1, e2])

            text = f"Find the eigenvalues of A where A = {matrix_to_text(A)}"
            latex = ""
            explanation = f"Solve det(A - λI) = 0: λ² - {trace}λ + {det} = 0. Eigenvalues: {eigenvalues}"
            hint = "Use the characteristic equation: det(A - λI) = 0"

        return Question(
            text=text,
            latex=latex,
            correct_answer=eigenvalues,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="list",
            plot_data=None,
            requires_plot=False
        )


class LinearSystemQuestion(QuestionGenerator):
    """Generate questions about solving systems of linear equations."""

    CATEGORY = QuestionCategory.LINEAR_ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # 2x2 system with integer solution
            x_sol, y_sol = np.random.randint(-5, 6), np.random.randint(-5, 6)

            # Create equations: a1*x + b1*y = c1, a2*x + b2*y = c2
            a1, b1 = np.random.randint(1, 4), np.random.randint(-3, 4)
            a2, b2 = np.random.randint(-3, 4), np.random.randint(1, 4)

            # Ensure non-singular (det != 0)
            while a1*b2 - a2*b1 == 0:
                a2 = np.random.randint(-3, 4)

            c1 = a1*x_sol + b1*y_sol
            c2 = a2*x_sol + b2*y_sol

            text = f"Solve the system:\n{a1}x + {b1}y = {c1}\n{a2}x + {b2}y = {c2}\n\nAnswer as [x, y]"
            latex = ""
            explanation = f"Using elimination or matrices: x = {x_sol}, y = {y_sol}"
            hint = "Use substitution, elimination, or Cramer's rule."
            answer = [x_sol, y_sol]

        else:  # HARD - 2x2 system with slightly harder coefficients
            x_sol, y_sol = np.random.randint(-4, 5), np.random.randint(-4, 5)

            # Create coefficients that are a bit harder but still pen-and-paper friendly
            a1, b1 = np.random.randint(2, 5), np.random.randint(-4, 5)
            a2, b2 = np.random.randint(-4, 5), np.random.randint(2, 5)

            # Ensure non-degenerate
            while a1 * b2 == a2 * b1:
                b2 = np.random.randint(2, 5)

            c1 = a1 * x_sol + b1 * y_sol
            c2 = a2 * x_sol + b2 * y_sol

            text = f"Solve the system:\n{a1}x + {b1}y = {c1}\n{a2}x + {b2}y = {c2}\n\nAnswer as [x, y]"
            latex = ""
            explanation = f"Solution: x = {x_sol}, y = {y_sol}"
            hint = "Use substitution, elimination, or Cramer's rule."
            answer = [x_sol, y_sol]

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="list",
            plot_data=None,
            requires_plot=False
        )


class LinearTransformationQuestion(QuestionGenerator):
    """Generate questions about linear transformations with graphical visualization."""

    CATEGORY = QuestionCategory.LINEAR_ALGEBRA
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Apply transformation matrix to a vector
            # Common transformations: rotation, scaling, reflection
            transform_type = np.random.choice(['scale', 'reflect'])

            if transform_type == 'scale':
                sx, sy = np.random.randint(1, 3), np.random.randint(1, 3)
                A = Matrix([[sx, 0], [0, sy]])
                desc = f"scaling by ({sx}, {sy})"
            else:  # reflect across x-axis
                A = Matrix([[1, 0], [0, -1]])
                desc = "reflection across x-axis"

            v = [np.random.randint(-3, 4), np.random.randint(-3, 4)]
            v_matrix = Matrix(v)
            result = A * v_matrix
            answer = [int(result[0]), int(result[1])]

            text = f"Apply the transformation matrix A to vector v = {v}\nwhere A = {matrix_to_text(A)}"
            latex = ""
            explanation = f"This is {desc}. Result: {answer}"
            hint = "Multiply the matrix by the vector."

            # Visual showing before and after
            plot_data = {
                'x_range': (-6, 6),
                'vectors': [
                    ((0, 0), (v[0], v[1]), 'blue', 'v'),
                    ((0, 0), (answer[0], answer[1]), 'red', 'Av'),
                ],
                'title': f"Linear Transformation: {desc}"
            }

        else:  # HARD
            # Find transformation matrix given input/output pairs
            # T(e1) = [a, c], T(e2) = [b, d] => A = [[a, b], [c, d]]
            a, b = np.random.randint(-3, 4), np.random.randint(-3, 4)
            c, d = np.random.randint(-3, 4), np.random.randint(-3, 4)

            text = f"Find the 2x2 matrix A such that:\nA × [1, 0] = [{a}, {c}]\nA × [0, 1] = [{b}, {d}]\n\nAnswer as [[row1], [row2]]"
            latex = ""
            explanation = f"The columns of A are the images of the standard basis vectors: A = [[{a}, {b}], [{c}, {d}]]"
            hint = "The columns of A are T(e₁) and T(e₂)."
            answer = [[a, b], [c, d]]

            plot_data = {
                'x_range': (-5, 5),
                'vectors': [
                    ((0, 0), (1, 0), 'blue', 'e₁'),
                    ((0, 0), (0, 1), 'green', 'e₂'),
                    ((0, 0), (a, c), 'red', 'T(e₁)'),
                    ((0, 0), (b, d), 'orange', 'T(e₂)'),
                ],
                'title': "Finding the Transformation Matrix"
            }

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="list",
            plot_data=plot_data,
            requires_plot=True
        )


class LinearAlgebraQuestions:
    """Factory class for linear algebra question generators."""

    GENERATORS = [
        VectorOperationsQuestion,
        MatrixOperationsQuestion,
        EigenvalueQuestion,
        LinearSystemQuestion,
        LinearTransformationQuestion,
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
                return EigenvalueQuestion().generate(DifficultyLevel.HARD)
            elif difficulty >= DifficultyLevel.MEDIUM:
                return MatrixOperationsQuestion().generate(DifficultyLevel.MEDIUM)
            else:
                return VectorOperationsQuestion().generate(DifficultyLevel.EASY)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
