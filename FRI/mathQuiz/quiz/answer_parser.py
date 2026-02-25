"""
Safe answer parsing module that avoids using eval().

Provides secure parsing of user mathematical input using SymPy's
sympify with restricted namespace and custom list/tuple handling.

Security Note:
--------------
This module explicitly avoids using Python's eval() or exec() on user input.
Instead, it uses SymPy's sympify() which has built-in safety measures and
restricts the available namespace to mathematical functions only.
"""

import re
from typing import Any, List, Optional, Tuple, Union
import sympy as sp
from sympy import (
    sin, cos, tan, exp, log, ln, sqrt, pi, E, I,
    sinh, cosh, tanh, asin, acos, atan, atan2,
    Abs, sign, floor, ceiling, factorial
)


class AnswerParser:
    """
    Safe parser for mathematical answers.

    Supports:
    - Numeric values (integers, floats, fractions)
    - Symbolic expressions (using SymPy syntax)
    - Lists/tuples for multi-part answers (e.g., [x, y] for systems)
    - Common mathematical functions (sin, cos, exp, sqrt, etc.)

    Example usage:
        parser = AnswerParser()
        result = parser.parse("sqrt(2)/2")  # Returns SymPy expression
        result = parser.parse("[3, -2]")    # Returns [3, -2]
        result = parser.parse("exp(-t)")    # Returns SymPy expression
    """

    # Safe namespace for sympify - only mathematical functions
    SAFE_NAMESPACE = {
        # Trigonometric
        'sin': sin, 'cos': cos, 'tan': tan,
        'asin': asin, 'acos': acos, 'atan': atan, 'atan2': atan2,
        'sinh': sinh, 'cosh': cosh, 'tanh': tanh,
        # Exponential and logarithmic
        'exp': exp, 'log': log, 'ln': ln,
        # Powers and roots
        'sqrt': sqrt, 'Abs': Abs, 'abs': Abs,
        # Constants
        'pi': pi, 'e': E, 'E': E, 'I': I, 'i': I,
        # Other functions
        'sign': sign, 'floor': floor, 'ceiling': ceiling,
        'factorial': factorial,
    }

    # Common variable symbols
    COMMON_SYMBOLS = 'x y z t n m a b c'

    def __init__(self):
        """Initialize the parser with predefined symbols."""
        self._symbols = sp.symbols(self.COMMON_SYMBOLS)
        self._symbol_dict = {str(s): s for s in self._symbols}

    def parse(self, user_input: str) -> Optional[Any]:
        """
        Parse user input into a mathematical object.

        Args:
            user_input: String input from the user

        Returns:
            Parsed result (SymPy expression, number, or list)
            None if parsing fails
        """
        if not user_input or not user_input.strip():
            return None

        text = user_input.strip()

        # Try to parse as a list/tuple first
        if self._looks_like_list(text):
            return self._parse_list(text)

        # Try to parse as a symbolic expression
        return self._parse_expression(text)

    def _looks_like_list(self, text: str) -> bool:
        """Check if the input looks like a list or tuple."""
        text = text.strip()
        return (
            (text.startswith('[') and text.endswith(']')) or
            (text.startswith('(') and text.endswith(')') and ',' in text)
        )

    def _parse_list(self, text: str) -> Optional[List]:
        """
        Safely parse a list/tuple of values.

        Args:
            text: String that looks like "[a, b, c]" or "(a, b, c)"

        Returns:
            List of parsed values, or None on failure
        """
        # Remove outer brackets/parentheses
        inner = text.strip()[1:-1]

        # Split by comma (handling nested expressions)
        elements = self._split_by_comma(inner)

        result = []
        for elem in elements:
            parsed = self._parse_expression(elem.strip())
            if parsed is None:
                return None
            result.append(parsed)

        return result

    def _split_by_comma(self, text: str) -> List[str]:
        """
        Split text by commas, respecting nested parentheses.

        Args:
            text: String to split

        Returns:
            List of comma-separated parts
        """
        parts = []
        current = []
        depth = 0

        for char in text:
            if char in '([{':
                depth += 1
                current.append(char)
            elif char in ')]}':
                depth -= 1
                current.append(char)
            elif char == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)

        if current:
            parts.append(''.join(current))

        return parts

    def _parse_expression(self, text: str) -> Optional[sp.Basic]:
        """
        Parse a single expression using SymPy.

        Args:
            text: Expression string

        Returns:
            SymPy expression, or None on failure
        """
        if not text.strip():
            return None

        text = self._preprocess(text)

        # Build local namespace with symbols and safe functions
        local_dict = {**self._symbol_dict, **self.SAFE_NAMESPACE}

        try:
            # Use sympify with explicit local_dict (safe approach)
            result = sp.sympify(text, locals=local_dict, evaluate=True)
            return result
        except (sp.SympifyError, SyntaxError, TypeError, ValueError):
            return None

    def _preprocess(self, text: str) -> str:
        """
        Preprocess input for better parsing.

        Handles common notation variations that users might enter.
        """
        # Handle currency format: $14,000 -> 14000
        # Strip dollar signs
        text = text.replace('$', '')
        # Remove commas used as thousand separators in numbers
        # Match patterns like 1,000 or 14,000,000
        text = re.sub(r'(\d),(\d{3})', r'\1\2', text)
        # Apply multiple times for numbers like 1,000,000
        while re.search(r'(\d),(\d{3})', text):
            text = re.sub(r'(\d),(\d{3})', r'\1\2', text)

        # Replace ^ with ** for exponentiation
        text = text.replace('^', '**')

        # Handle implicit multiplication: 2x -> 2*x, xy -> x*y
        # (but be careful not to break function names like 'sin', 'exp')
        text = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', text)

        # Handle cases like (x)(y) -> (x)*(y)
        text = re.sub(r'\)(\()', r')*(', text)

        # Handle coefficient before function: 2sin(x) -> 2*sin(x)
        for func in ['sin', 'cos', 'tan', 'exp', 'log', 'ln', 'sqrt',
                     'sinh', 'cosh', 'tanh', 'asin', 'acos', 'atan']:
            text = re.sub(rf'(\d)({func})', rf'\1*\2', text)

        return text

    def parse_numeric(self, user_input: str) -> Optional[float]:
        """
        Parse input as a numeric value.

        Args:
            user_input: String input

        Returns:
            Float value, or None if not purely numeric
        """
        result = self.parse(user_input)
        if result is None:
            return None

        try:
            # Try to convert to float
            return float(result)
        except (TypeError, ValueError):
            # Try SymPy numeric evaluation
            try:
                return float(sp.N(result))
            except (TypeError, ValueError):
                return None

    def check_symbolic_equivalence(
        self,
        user_answer: Any,
        correct_answer: Any,
        symbols: Optional[List[sp.Symbol]] = None
    ) -> bool:
        """
        Check if two expressions are symbolically equivalent.

        Uses algebraic simplification first, then falls back to
        numeric sampling if simplification is inconclusive.

        Args:
            user_answer: Parsed user answer
            correct_answer: Expected correct answer
            symbols: List of symbols to test (for numeric sampling)

        Returns:
            True if expressions are equivalent
        """
        if user_answer is None:
            return False

        # Handle list answers
        if isinstance(correct_answer, (list, tuple)):
            if not isinstance(user_answer, (list, tuple)):
                return False
            if len(user_answer) != len(correct_answer):
                return False
            return all(
                self.check_symbolic_equivalence(u, c, symbols)
                for u, c in zip(sorted(map(str, user_answer)),
                               sorted(map(str, correct_answer)))
            )

        # Try algebraic simplification
        try:
            user_expr = sp.sympify(user_answer) if not isinstance(user_answer, sp.Basic) else user_answer
            correct_expr = sp.sympify(correct_answer) if not isinstance(correct_answer, sp.Basic) else correct_answer

            diff = sp.simplify(user_expr - correct_expr)
            if diff == 0:
                return True

            # Also try expand and trigsimp
            if sp.simplify(sp.expand(user_expr - correct_expr)) == 0:
                return True
            if sp.simplify(sp.trigsimp(user_expr - correct_expr)) == 0:
                return True

        except Exception:
            pass

        # Fall back to numeric sampling
        return self._check_numeric_equivalence(user_answer, correct_answer, symbols)

    def _check_numeric_equivalence(
        self,
        user_answer: Any,
        correct_answer: Any,
        symbols: Optional[List[sp.Symbol]] = None,
        num_samples: int = 5,
        tolerance: float = 1e-6
    ) -> bool:
        """
        Check equivalence by evaluating at random points.

        Args:
            user_answer: User's expression
            correct_answer: Expected expression
            symbols: Symbols to substitute
            num_samples: Number of test points
            tolerance: Relative tolerance for comparison

        Returns:
            True if values match at all sample points
        """
        import numpy as np

        if symbols is None:
            # Extract symbols from expressions
            try:
                user_expr = sp.sympify(user_answer) if not isinstance(user_answer, sp.Basic) else user_answer
                correct_expr = sp.sympify(correct_answer) if not isinstance(correct_answer, sp.Basic) else correct_answer
                symbols = list(user_expr.free_symbols | correct_expr.free_symbols)
            except Exception:
                return False

        if not symbols:
            # No symbols - just compare numeric values
            try:
                user_val = float(sp.N(user_answer))
                correct_val = float(sp.N(correct_answer))
                return abs(user_val - correct_val) < tolerance * max(1, abs(correct_val))
            except Exception:
                return False

        # Generate random test points
        np.random.seed(42)  # Reproducible
        test_points = np.random.uniform(-2, 2, (num_samples, len(symbols)))

        try:
            user_expr = sp.sympify(user_answer) if not isinstance(user_answer, sp.Basic) else user_answer
            correct_expr = sp.sympify(correct_answer) if not isinstance(correct_answer, sp.Basic) else correct_answer

            for point in test_points:
                subs = dict(zip(symbols, point))
                user_val = complex(user_expr.subs(subs).evalf())
                correct_val = complex(correct_expr.subs(subs).evalf())

                # Compare with tolerance
                if abs(correct_val) < tolerance:
                    if abs(user_val) >= tolerance:
                        return False
                elif abs(user_val - correct_val) / abs(correct_val) > tolerance:
                    return False

            return True

        except Exception:
            return False

    def check_numeric_answer(
        self,
        user_answer: Any,
        correct_answer: float,
        tolerance: float = 0.05
    ) -> Tuple[bool, float]:
        """
        Check if a numeric answer is within tolerance.

        Args:
            user_answer: User's answer
            correct_answer: Expected numeric value
            tolerance: Relative tolerance (default 5%)

        Returns:
            Tuple of (is_correct, accuracy_ratio)
            accuracy_ratio is 1.0 for exact, approaching 0.0 for very wrong
        """
        try:
            user_val = float(sp.N(user_answer)) if isinstance(user_answer, sp.Basic) else float(user_answer)
        except (TypeError, ValueError):
            return False, 0.0

        if correct_answer == 0:
            is_correct = abs(user_val) < tolerance
            accuracy = 1.0 if is_correct else max(0, 1 - abs(user_val))
        else:
            relative_error = abs(user_val - correct_answer) / abs(correct_answer)
            is_correct = relative_error <= tolerance
            accuracy = max(0, 1 - relative_error)

        return is_correct, accuracy

    def check_answer_with_units(
        self,
        user_answer: str,
        correct_answer: str,
        tolerance: float = 0.05
    ) -> Tuple[bool, float]:
        """
        Check a text answer that includes units (e.g., "23 m/s").

        Args:
            user_answer: User's answer string with units
            correct_answer: Expected answer string with units

        Returns:
            Tuple of (is_correct, accuracy_ratio)
        """
        import re

        # Normalize whitespace
        user_answer = ' '.join(user_answer.strip().split())
        correct_answer = ' '.join(correct_answer.strip().split())

        # Parse number and unit from correct answer
        correct_match = re.match(r'^([-+]?\d*\.?\d+)\s*(.*)$', correct_answer)
        if not correct_match:
            # Can't parse, do string comparison
            return user_answer.lower() == correct_answer.lower(), 1.0 if user_answer.lower() == correct_answer.lower() else 0.0

        correct_num = float(correct_match.group(1))
        correct_unit = correct_match.group(2).strip().lower()

        # Parse user answer
        user_match = re.match(r'^([-+]?\d*\.?\d+)\s*(.*)$', user_answer)
        if not user_match:
            return False, 0.0

        try:
            user_num = float(user_match.group(1))
        except ValueError:
            return False, 0.0

        user_unit = user_match.group(2).strip().lower()

        # Check units match (with some normalization)
        unit_aliases = {
            'm/s': ['m/s', 'ms^-1', 'ms-1', 'meters/second', 'meters per second'],
            'm/s^2': ['m/s^2', 'm/s2', 'ms^-2', 'ms-2', 'meters/second^2'],
            'm': ['m', 'meters', 'meter'],
            's': ['s', 'sec', 'seconds', 'second'],
            'j': ['j', 'joules', 'joule'],
            'n': ['n', 'newtons', 'newton'],
            'w': ['w', 'watts', 'watt'],
            'kg': ['kg', 'kilograms', 'kilogram'],
        }

        def normalize_unit(unit):
            unit = unit.lower().strip()
            for canonical, aliases in unit_aliases.items():
                if unit in aliases:
                    return canonical
            return unit

        if normalize_unit(user_unit) != normalize_unit(correct_unit):
            return False, 0.0

        # Check numeric value
        if correct_num == 0:
            is_correct = abs(user_num) < tolerance
            accuracy = 1.0 if is_correct else 0.0
        else:
            relative_error = abs(user_num - correct_num) / abs(correct_num)
            is_correct = relative_error <= tolerance
            accuracy = max(0, 1 - relative_error)

        return is_correct, accuracy
