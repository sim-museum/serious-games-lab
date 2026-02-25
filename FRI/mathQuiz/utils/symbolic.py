"""
Symbolic mathematics helper utilities.

Provides wrapper functions for SymPy and optional Maxima integration
for symbolic computation tasks.
"""

import sympy as sp
from typing import Any, List, Optional, Tuple, Union
import subprocess
import tempfile
import os


class SymbolicHelper:
    """
    Helper class for symbolic mathematics operations.

    Provides a unified interface for:
    - Expression simplification
    - Equation solving
    - Differentiation and integration
    - Expression comparison
    - Optional Maxima backend for complex operations
    """

    def __init__(self, use_maxima: bool = False):
        """
        Initialize the symbolic helper.

        Args:
            use_maxima: Whether to use Maxima for certain operations
        """
        self.use_maxima = use_maxima and self._check_maxima_available()
        self._maxima_available = self._check_maxima_available()

    def _check_maxima_available(self) -> bool:
        """Check if Maxima is available on the system."""
        try:
            result = subprocess.run(
                ['maxima', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def simplify(self, expr: Union[str, sp.Basic]) -> sp.Basic:
        """
        Simplify a mathematical expression.

        Args:
            expr: Expression to simplify (string or SymPy expression)

        Returns:
            Simplified SymPy expression
        """
        if isinstance(expr, str):
            expr = sp.sympify(expr)

        # Apply multiple simplification strategies
        result = sp.simplify(expr)
        result = sp.trigsimp(result)
        result = sp.powsimp(result)

        return result

    def are_equivalent(
        self,
        expr1: Union[str, sp.Basic],
        expr2: Union[str, sp.Basic],
        numeric_check: bool = True
    ) -> bool:
        """
        Check if two expressions are mathematically equivalent.

        Args:
            expr1: First expression
            expr2: Second expression
            numeric_check: Whether to use numeric verification as fallback

        Returns:
            True if expressions are equivalent
        """
        if isinstance(expr1, str):
            expr1 = sp.sympify(expr1)
        if isinstance(expr2, str):
            expr2 = sp.sympify(expr2)

        # Try algebraic simplification
        diff = sp.simplify(expr1 - expr2)
        if diff == 0:
            return True

        # Try expanded form
        diff = sp.simplify(sp.expand(expr1) - sp.expand(expr2))
        if diff == 0:
            return True

        # Try trigonometric simplification
        diff = sp.trigsimp(expr1 - expr2)
        if diff == 0:
            return True

        # Numeric check as fallback
        if numeric_check:
            return self._numeric_equivalence(expr1, expr2)

        return False

    def _numeric_equivalence(
        self,
        expr1: sp.Basic,
        expr2: sp.Basic,
        num_points: int = 10,
        tolerance: float = 1e-9
    ) -> bool:
        """Check equivalence by numeric sampling."""
        import numpy as np

        symbols = list(expr1.free_symbols | expr2.free_symbols)
        if not symbols:
            # Constant expressions
            try:
                return abs(float(expr1) - float(expr2)) < tolerance
            except (TypeError, ValueError):
                return False

        # Generate random test points
        np.random.seed(42)
        test_points = np.random.uniform(-2, 2, (num_points, len(symbols)))

        try:
            for point in test_points:
                subs = dict(zip(symbols, point))
                val1 = complex(expr1.subs(subs).evalf())
                val2 = complex(expr2.subs(subs).evalf())

                if abs(val2) < tolerance:
                    if abs(val1) >= tolerance:
                        return False
                elif abs(val1 - val2) / abs(val2) > tolerance:
                    return False

            return True
        except Exception:
            return False

    def solve_equation(
        self,
        equation: Union[str, sp.Basic],
        variable: sp.Symbol = None
    ) -> List[sp.Basic]:
        """
        Solve an equation for a variable.

        Args:
            equation: Equation to solve (assumed equal to 0)
            variable: Variable to solve for

        Returns:
            List of solutions
        """
        if isinstance(equation, str):
            equation = sp.sympify(equation)

        if variable is None:
            # Try to find a variable
            symbols = list(equation.free_symbols)
            if not symbols:
                return []
            variable = symbols[0]

        solutions = sp.solve(equation, variable)
        return solutions

    def differentiate(
        self,
        expr: Union[str, sp.Basic],
        variable: sp.Symbol = None,
        order: int = 1
    ) -> sp.Basic:
        """
        Differentiate an expression.

        Args:
            expr: Expression to differentiate
            variable: Variable to differentiate with respect to
            order: Order of differentiation

        Returns:
            Derivative expression
        """
        if isinstance(expr, str):
            expr = sp.sympify(expr)

        if variable is None:
            symbols = list(expr.free_symbols)
            variable = symbols[0] if symbols else sp.Symbol('x')

        return sp.diff(expr, variable, order)

    def integrate(
        self,
        expr: Union[str, sp.Basic],
        variable: sp.Symbol = None,
        limits: Optional[Tuple[float, float]] = None
    ) -> sp.Basic:
        """
        Integrate an expression.

        Args:
            expr: Expression to integrate
            variable: Variable to integrate with respect to
            limits: Optional (a, b) for definite integral

        Returns:
            Integral result
        """
        if isinstance(expr, str):
            expr = sp.sympify(expr)

        if variable is None:
            symbols = list(expr.free_symbols)
            variable = symbols[0] if symbols else sp.Symbol('x')

        if limits:
            return sp.integrate(expr, (variable, limits[0], limits[1]))
        else:
            return sp.integrate(expr, variable)

    def to_latex(self, expr: Union[str, sp.Basic]) -> str:
        """Convert expression to LaTeX string."""
        if isinstance(expr, str):
            expr = sp.sympify(expr)
        return sp.latex(expr)

    def to_pretty(self, expr: Union[str, sp.Basic]) -> str:
        """Convert expression to pretty-printed string."""
        if isinstance(expr, str):
            expr = sp.sympify(expr)
        return sp.pretty(expr, use_unicode=True)

    def run_maxima(self, command: str) -> Optional[str]:
        """
        Run a Maxima command and return the result.

        Args:
            command: Maxima command to execute

        Returns:
            Result string, or None if Maxima unavailable/failed
        """
        if not self._maxima_available:
            return None

        try:
            # Create temporary file for Maxima batch input
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mac', delete=False) as f:
                f.write(f'{command}$\n')
                temp_file = f.name

            # Run Maxima in batch mode
            result = subprocess.run(
                ['maxima', '--very-quiet', '-b', temp_file],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Clean up
            os.unlink(temp_file)

            if result.returncode == 0:
                # Parse output (remove Maxima prompt artifacts)
                output = result.stdout.strip()
                lines = output.split('\n')
                # Filter out prompt lines
                result_lines = [l for l in lines if not l.startswith('(%')]
                return '\n'.join(result_lines).strip()

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return None
