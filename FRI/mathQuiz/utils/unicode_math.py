"""
Unicode math formatter for displaying expressions as single-line text.

Converts SymPy expressions to readable single-line strings using
Unicode superscript/subscript characters.
"""

import re
import sympy as sp


# Unicode superscript mapping
SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

# Unicode subscript mapping
SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ',
    'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'n': 'ₙ',
}


def to_superscript(text: str) -> str:
    """Convert text to Unicode superscript characters."""
    result = []
    for char in str(text):
        result.append(SUPERSCRIPT_MAP.get(char, char))
    return ''.join(result)


def to_subscript(text: str) -> str:
    """Convert text to Unicode subscript characters."""
    result = []
    for char in str(text):
        result.append(SUBSCRIPT_MAP.get(char, char))
    return ''.join(result)


def format_expr(expr) -> str:
    """
    Format a SymPy expression as a readable single-line Unicode string.

    Args:
        expr: SymPy expression or string

    Returns:
        Formatted string with Unicode math symbols
    """
    if expr is None:
        return ""

    # Convert to string first
    if isinstance(expr, sp.Basic):
        text = str(expr)
    else:
        text = str(expr)

    # Replace ** with superscript
    # Handle patterns like x**2, x**10, (x+1)**2
    def replace_power(match):
        base = match.group(1)
        exp = match.group(2)
        # If exponent is simple (digits or single letter), use superscript
        if exp.isdigit() or (len(exp) <= 2 and exp.lstrip('-').isdigit()):
            return base + to_superscript(exp)
        else:
            return base + '^' + exp

    # Match: something**something (greedy for base, non-greedy for exp)
    text = re.sub(r'(\w+)\*\*(\d+)', replace_power, text)
    text = re.sub(r'\)\*\*(\d+)', lambda m: ')' + to_superscript(m.group(1)), text)

    # Replace remaining ** with ^
    text = text.replace('**', '^')

    # Replace * with · (middle dot) for multiplication
    text = text.replace('*', '·')

    # Replace sqrt with √
    text = re.sub(r'sqrt\(([^)]+)\)', r'√(\1)', text)

    # Replace common functions
    text = text.replace('pi', 'π')
    text = text.replace('exp(', 'e^(')

    return text


def format_derivative(func_expr, var='x') -> str:
    """
    Format a derivative expression nicely.

    Args:
        func_expr: The function expression
        var: Variable name

    Returns:
        Formatted string like "f(x) = 3x² + 2x"
    """
    formatted = format_expr(func_expr)
    return f"f({var}) = {formatted}"


def format_integral(func_expr, var='x', definite=False, lower=None, upper=None) -> str:
    """
    Format an integral expression nicely.

    Args:
        func_expr: The integrand
        var: Variable of integration
        definite: Whether it's a definite integral
        lower: Lower bound (for definite)
        upper: Upper bound (for definite)

    Returns:
        Formatted string like "∫ 3x² dx" or "∫₀¹ x² dx"
    """
    formatted = format_expr(func_expr)

    if definite and lower is not None and upper is not None:
        lower_sub = to_subscript(str(lower))
        upper_sup = to_superscript(str(upper))
        return f"∫{lower_sub}{upper_sup} {formatted} d{var}"
    else:
        return f"∫ {formatted} d{var}"


def format_question_text(question_type: str, **kwargs) -> str:
    """
    Format a complete question text.

    Args:
        question_type: Type of question ('derivative', 'integral', etc.)
        **kwargs: Parameters for the question

    Returns:
        Formatted question string
    """
    if question_type == 'derivative':
        func = kwargs.get('function')
        var = kwargs.get('variable', 'x')
        func_str = format_expr(func)
        return f"Find the derivative d/d{var} of: f({var}) = {func_str}"

    elif question_type == 'integral':
        func = kwargs.get('function')
        var = kwargs.get('variable', 'x')
        func_str = format_expr(func)
        return f"Find the integral: ∫ {func_str} d{var}"

    elif question_type == 'definite_integral':
        func = kwargs.get('function')
        var = kwargs.get('variable', 'x')
        lower = kwargs.get('lower', 0)
        upper = kwargs.get('upper', 1)
        func_str = format_expr(func)
        return f"Evaluate: ∫ from {lower} to {upper} of {func_str} d{var}"

    else:
        return str(kwargs.get('text', ''))
