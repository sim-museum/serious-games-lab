"""
LaTeX rendering widget for displaying mathematical expressions.

Uses Matplotlib's mathtext renderer to display LaTeX-formatted
mathematics within PyQt labels.
"""

import io
import re
from typing import Optional

from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt6.QtGui import QPixmap, QFont, QImage, QPainter
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['mathtext.fontset'] = 'cm'
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np


def render_latex_to_pixmap(latex: str, fontsize: int = 18, dpi: int = 120) -> Optional[QPixmap]:
    """
    Render a LaTeX math expression to a QPixmap.

    Args:
        latex: LaTeX math string (without $ delimiters)
        fontsize: Font size for rendering
        dpi: Resolution

    Returns:
        QPixmap or None if rendering fails
    """
    try:
        fig = Figure(dpi=dpi)
        fig.patch.set_facecolor('white')
        fig.patch.set_alpha(0)

        # Add the math text
        text = fig.text(0, 0.5, f"${latex}$", fontsize=fontsize,
                       verticalalignment='center', color='black')

        # Draw to calculate size
        canvas = FigureCanvasAgg(fig)
        canvas.draw()

        bbox = text.get_window_extent(renderer=canvas.get_renderer())

        # Resize figure to fit text
        width = (bbox.width + 20) / dpi
        height = max((bbox.height + 10) / dpi, 0.4)
        fig.set_size_inches(width, height)

        # Reposition and redraw
        text.set_position((10 / (width * dpi), 0.5))
        canvas.draw()

        # Convert to QPixmap
        buf = canvas.buffer_rgba()
        w = int(fig.get_figwidth() * dpi)
        h = int(fig.get_figheight() * dpi)
        arr = np.asarray(buf).copy()

        qimage = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimage.copy())

        matplotlib.pyplot.close(fig)
        return pixmap

    except Exception as e:
        print(f"LaTeX render error: {e}")
        return None


class LatexLabel(QLabel):
    """
    Widget that renders LaTeX math expressions.

    For pure math expressions, renders using matplotlib.
    For text, displays as plain text.
    """

    def __init__(self, text: str = "", font_size: int = 18, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._font_size = font_size
        self._text = text

        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        font = QFont("DejaVu Sans", font_size)
        self.setFont(font)
        self.setStyleSheet("color: #1a1a1a;")

        if text:
            self.set_latex(text)

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        font = QFont("DejaVu Sans", size)
        self.setFont(font)

    def set_latex(self, text: str) -> None:
        """Set text, rendering LaTeX if it's pure math."""
        self._text = text.strip()

        # Check if this is a pure LaTeX expression (starts and ends with $)
        if self._is_pure_math(self._text):
            math_content = self._text.strip('$')
            pixmap = render_latex_to_pixmap(math_content, self._font_size)
            if pixmap and not pixmap.isNull():
                self.setPixmap(pixmap)
                return

        # Otherwise display as text
        self.setText(self._text)

    def _is_pure_math(self, text: str) -> bool:
        """Check if text is pure LaTeX math (single $...$)."""
        text = text.strip()
        if text.startswith('$') and text.endswith('$'):
            # Check it's not mixed text+math
            inner = text[1:-1]
            if '$' not in inner:
                return True
        return False

    def set_plain_text(self, text: str) -> None:
        self._text = text
        self.setText(text)


class MathDisplay(QWidget):
    """
    Widget for displaying math questions with LaTeX formulas.

    Shows question text and renders math formulas separately.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Question text label
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.title_label.setFont(QFont("DejaVu Sans", 16))
        self.title_label.setStyleSheet("color: #1a1a1a;")

        # Math formula display
        self.math_label = QLabel()
        self.math_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.math_label.setMinimumHeight(50)

        # Hint label
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        hint_font = QFont("DejaVu Sans", 13)
        hint_font.setItalic(True)
        self.hint_label.setFont(hint_font)
        self.hint_label.setStyleSheet("color: #666;")
        self.hint_label.hide()

        layout.addWidget(self.title_label)
        layout.addWidget(self.math_label)
        layout.addWidget(self.hint_label)
        layout.addStretch()

    def set_content(self, title: str = "", latex: str = "", hint: str = "") -> None:
        """
        Set the question content.

        Args:
            title: Question description text
            latex: LaTeX formula (will be rendered if valid)
            hint: Optional hint
        """
        self.title_label.setText(title)

        # Try to render LaTeX formula
        if latex and latex.strip():
            # Extract math content - handle $...$ or raw math
            math_content = latex.strip()
            if math_content.startswith('$') and math_content.endswith('$'):
                math_content = math_content[1:-1]

            pixmap = render_latex_to_pixmap(math_content, fontsize=20)
            if pixmap and not pixmap.isNull():
                self.math_label.setPixmap(pixmap)
                self.math_label.show()
            else:
                # Fallback to text display
                self.math_label.setText(latex)
                self.math_label.setFont(QFont("DejaVu Sans", 18))
                self.math_label.setStyleSheet("color: #1a1a1a;")
                self.math_label.show()
        else:
            self.math_label.hide()

        if hint:
            self.hint_label.setText(f"Hint: {hint}")
            self.hint_label.show()
        else:
            self.hint_label.hide()

    def clear(self) -> None:
        self.title_label.clear()
        self.math_label.clear()
        self.hint_label.clear()
        self.hint_label.hide()

    def show_hint(self, hint: str) -> None:
        self.hint_label.setText(f"Hint: {hint}")
        self.hint_label.show()
