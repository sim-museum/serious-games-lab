"""
Matplotlib canvas widget for embedding plots in PyQt.

Provides a reusable widget for displaying mathematical plots
within the quiz interface.
"""

import numpy as np
from typing import Callable, List, Optional, Tuple

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class PlotWidget(QWidget):
    """
    Widget for displaying Matplotlib plots in PyQt6.

    Supports:
    - Multiple function plots with labels
    - Point markers
    - Grid and axis customization
    - Dynamic resizing

    Example usage:
        plot = PlotWidget()
        plot.plot_function(lambda x: x**2, label="f(x) = x²")
        plot.add_point(1, 1, "o")
        plot.update_plot()
    """

    # Default style settings for clear visibility
    DEFAULT_STYLE = {
        'figure.facecolor': '#f0f0f0',
        'axes.facecolor': 'white',
        'axes.grid': True,
        'grid.alpha': 0.3,
        'font.size': 14,
        'axes.labelsize': 14,
        'axes.titlesize': 16,
        'legend.fontsize': 12,
        'lines.linewidth': 2.5,
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Apply style
        for key, value in self.DEFAULT_STYLE.items():
            plt.rcParams[key] = value

        # Create figure and canvas
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        # Size policy - allow expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Storage for plot elements
        self._functions: List[Tuple[Callable, str, str]] = []
        self._points: List[Tuple[float, float, str, str]] = []
        self._x_range = (-5, 5)
        self._title = ""
        self._xlabel = "x"
        self._ylabel = "y"

        # Initialize with empty plot
        self.clear()

    def clear(self) -> None:
        """Clear all plot elements."""
        self._functions.clear()
        self._points.clear()
        self.ax.clear()
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel(self._xlabel)
        self.ax.set_ylabel(self._ylabel)
        self.canvas.draw()

    def set_range(self, x_min: float, x_max: float) -> None:
        """Set the x-axis range."""
        self._x_range = (x_min, x_max)

    def set_title(self, title: str) -> None:
        """Set the plot title."""
        self._title = title

    def set_labels(self, xlabel: str = "x", ylabel: str = "y") -> None:
        """Set axis labels."""
        self._xlabel = xlabel
        self._ylabel = ylabel

    def plot_function(
        self,
        func: Callable[[np.ndarray], np.ndarray],
        label: str = "",
        color: str = 'blue',
        linestyle: str = '-'
    ) -> None:
        """
        Add a function to plot.

        Args:
            func: Function that takes numpy array and returns array
            label: Legend label
            color: Line color
            linestyle: Line style ('-', '--', ':', '-.')
        """
        self._functions.append((func, label, color, linestyle))

    def add_point(
        self,
        x: float,
        y: float,
        marker: str = 'o',
        color: str = 'red',
        size: int = 100
    ) -> None:
        """
        Add a point marker.

        Args:
            x, y: Point coordinates
            marker: Marker style ('o', 'x', '+', '*', etc.)
            color: Marker color
            size: Marker size
        """
        self._points.append((x, y, marker, color, size))

    def update_plot(self) -> None:
        """Render all plot elements."""
        self.ax.clear()

        # Generate x values
        x_vals = np.linspace(self._x_range[0], self._x_range[1], 500)

        # Plot functions
        for func, label, color, *style in self._functions:
            linestyle = style[0] if style else '-'
            try:
                y_vals = func(x_vals)
                # Handle complex or invalid values
                y_vals = np.real(y_vals)
                y_vals = np.where(np.isfinite(y_vals), y_vals, np.nan)
                self.ax.plot(x_vals, y_vals, color=color, linestyle=linestyle,
                           label=label, linewidth=2.5)
            except Exception:
                pass  # Skip functions that fail

        # Plot points
        for x, y, marker, color, size in self._points:
            self.ax.scatter([x], [y], marker=marker, c=color, s=size, zorder=5)

        # Styling
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlabel(self._xlabel, fontsize=14)
        self.ax.set_ylabel(self._ylabel, fontsize=14)

        if self._title:
            self.ax.set_title(self._title, fontsize=16)

        if any(f[1] for f in self._functions):  # If any labels
            self.ax.legend(loc='best', fontsize=12)

        # Auto-scale y-axis with some padding
        self.ax.autoscale(axis='y')
        y_min, y_max = self.ax.get_ylim()
        padding = (y_max - y_min) * 0.1
        self.ax.set_ylim(y_min - padding, y_max + padding)

        self.figure.tight_layout()
        self.canvas.draw()

    def plot_from_data(self, plot_data: dict) -> None:
        """
        Plot from a plot_data dictionary (from Question objects).

        Args:
            plot_data: Dictionary with keys:
                - x_range: (min, max)
                - functions: [(func, label, color), ...]
                - points: [(x, y, marker), ...]
                - vectors: [((x0, y0), (x1, y1), color, label), ...]
                - histogram: [data values]
                - bar_chart: (x_vals, y_vals, highlight_index)
                - scatter: (x_data, y_data)
                - regression_line: bool
                - normal_curve: (x_vals, y_vals, mu, sigma)
                - title: str
                - xlabel, ylabel: str
        """
        self.clear()

        if 'x_range' in plot_data:
            self.set_range(*plot_data['x_range'])

        if 'title' in plot_data:
            self.set_title(plot_data['title'])

        if 'xlabel' in plot_data:
            self._xlabel = plot_data['xlabel']
        if 'ylabel' in plot_data:
            self._ylabel = plot_data['ylabel']

        # Handle vectors (for linear algebra)
        if 'vectors' in plot_data:
            self._plot_vectors(plot_data['vectors'])
            self._finalize_plot()
            return

        # Handle histogram (for statistics)
        if 'histogram' in plot_data:
            self._plot_histogram(plot_data['histogram'], plot_data.get('title', ''))
            return

        # Handle bar chart (for statistics/accounting)
        if 'bar_chart' in plot_data:
            x_vals, y_vals, highlight = plot_data['bar_chart']
            self._plot_bar_chart(x_vals, y_vals, highlight, plot_data.get('title', ''))
            return

        # Handle scatter plot with optional regression line
        if 'scatter' in plot_data:
            x_data, y_data = plot_data['scatter']
            self._plot_scatter(x_data, y_data, plot_data.get('regression_line', False),
                              plot_data.get('title', ''),
                              plot_data.get('hide_equation', False))
            return

        # Handle normal curve (for statistics)
        if 'normal_curve' in plot_data:
            x_vals, y_vals, mu, sigma = plot_data['normal_curve']
            self._plot_normal_curve(x_vals, y_vals, mu, sigma, plot_data.get('title', ''))
            return

        # Handle balance comparison (for accounting)
        if 'balance_comparison' in plot_data:
            assets, liabilities = plot_data['balance_comparison']
            self._plot_balance_comparison(assets, liabilities, plot_data.get('title', ''))
            return

        # Handle profit/loss visualization (for accounting)
        if 'profit_loss' in plot_data:
            revenue, expenses = plot_data['profit_loss']
            self._plot_profit_loss(revenue, expenses, plot_data.get('title', ''))
            return

        # Standard function plots
        for func_data in plot_data.get('functions', []):
            func, label, color = func_data[:3]
            self.plot_function(func, label, color)

        for point_data in plot_data.get('points', []):
            x, y, marker = point_data[:3]
            self.add_point(x, y, marker)

        self.update_plot()

    def _plot_vectors(self, vectors: list) -> None:
        """Plot 2D vectors as arrows from origin."""
        self.ax.clear()
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'cyan']

        max_val = 1
        for i, vec_data in enumerate(vectors):
            origin, end, color, label = vec_data
            self.ax.annotate('', xy=end, xytext=origin,
                           arrowprops=dict(arrowstyle='->', color=color, lw=2.5))
            # Add label near the arrowhead
            mid_x = (origin[0] + end[0]) / 2
            mid_y = (origin[1] + end[1]) / 2
            self.ax.annotate(label, xy=(mid_x, mid_y), fontsize=12, color=color,
                           fontweight='bold')
            max_val = max(max_val, abs(end[0]), abs(end[1]))

        # Set equal aspect ratio and grid
        limit = max_val * 1.3
        self.ax.set_xlim(-limit, limit)
        self.ax.set_ylim(-limit, limit)
        self.ax.set_aspect('equal')
        self.ax.axhline(y=0, color='k', linewidth=0.5)
        self.ax.axvline(x=0, color='k', linewidth=0.5)
        self.ax.grid(True, alpha=0.3)

    def _plot_histogram(self, data: list, title: str) -> None:
        """Plot a histogram of data values."""
        self.ax.clear()
        self.ax.hist(data, bins='auto', color='steelblue', edgecolor='white', alpha=0.8)
        self.ax.set_xlabel('Value', fontsize=12)
        self.ax.set_ylabel('Frequency', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.grid(True, alpha=0.3, axis='y')
        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_bar_chart(self, x_vals: list, y_vals: list, highlight: int, title: str) -> None:
        """Plot a bar chart with optional highlighted bar."""
        self.ax.clear()
        colors = ['steelblue'] * len(x_vals)
        if highlight is not None and 0 <= highlight < len(colors):
            colors[highlight] = 'orange'

        bars = self.ax.bar(x_vals, y_vals, color=colors, edgecolor='white')
        self.ax.set_xlabel('k', fontsize=12)
        self.ax.set_ylabel('P(X=k)', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.grid(True, alpha=0.3, axis='y')
        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_scatter(self, x_data: list, y_data: list, show_regression: bool, title: str,
                       hide_equation: bool = False) -> None:
        """Plot scatter points with optional regression line."""
        self.ax.clear()
        self.ax.scatter(x_data, y_data, c='steelblue', s=80, alpha=0.8, edgecolors='white')

        if show_regression and len(x_data) > 1:
            # Calculate regression line
            x_arr = np.array(x_data)
            y_arr = np.array(y_data)
            slope, intercept = np.polyfit(x_arr, y_arr, 1)
            x_line = np.linspace(min(x_data) - 0.5, max(x_data) + 0.5, 100)
            y_line = slope * x_line + intercept
            if hide_equation:
                self.ax.plot(x_line, y_line, 'r-', linewidth=2, label='Regression line')
            else:
                self.ax.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {slope:.2f}x + {intercept:.2f}')
            self.ax.legend(loc='best', fontsize=10)

        self.ax.set_xlabel('x', fontsize=12)
        self.ax.set_ylabel('y', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_normal_curve(self, x_vals: list, y_vals: list, mu: float, sigma: float, title: str) -> None:
        """Plot a normal distribution curve."""
        self.ax.clear()
        self.ax.plot(x_vals, y_vals, 'b-', linewidth=2.5)
        self.ax.fill_between(x_vals, y_vals, alpha=0.3, color='steelblue')

        # Mark mean
        self.ax.axvline(x=mu, color='red', linestyle='--', linewidth=1.5, label=f'μ = {mu}')

        self.ax.set_xlabel('x', fontsize=12)
        self.ax.set_ylabel('Density', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.legend(loc='best', fontsize=10)
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_balance_comparison(self, assets: float, liabilities: float, title: str) -> None:
        """Plot balance comparison bar chart for accounting."""
        self.ax.clear()
        categories = ['Current\nAssets', 'Current\nLiabilities']
        values = [assets, liabilities]
        colors = ['#4CAF50', '#F44336']

        bars = self.ax.bar(categories, values, color=colors, edgecolor='white', width=0.5)

        # Add value labels on bars
        for bar, val in zip(bars, values):
            self.ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                        f'${val:,.0f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        self.ax.set_ylabel('Amount ($)', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.grid(True, alpha=0.3, axis='y')
        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_profit_loss(self, revenue: float, expenses: float, title: str) -> None:
        """Plot profit and loss visualization."""
        self.ax.clear()
        profit = revenue - expenses

        categories = ['Revenue', 'Expenses', 'Profit']
        values = [revenue, expenses, profit]
        colors = ['#4CAF50', '#F44336', '#2196F3' if profit >= 0 else '#FF9800']

        bars = self.ax.bar(categories, values, color=colors, edgecolor='white', width=0.5)

        # Add value labels on bars
        for bar, val in zip(bars, values):
            y_pos = bar.get_height() + max(values)*0.02 if val >= 0 else bar.get_height() - max(values)*0.05
            self.ax.text(bar.get_x() + bar.get_width()/2, y_pos,
                        f'${val:,.0f}', ha='center', va='bottom' if val >= 0 else 'top',
                        fontsize=11, fontweight='bold')

        self.ax.set_ylabel('Amount ($)', fontsize=12)
        if title:
            self.ax.set_title(title, fontsize=14)
        self.ax.axhline(y=0, color='black', linewidth=0.5)
        self.ax.grid(True, alpha=0.3, axis='y')
        self.figure.tight_layout()
        self.canvas.draw()

    def _finalize_plot(self) -> None:
        """Finalize and draw the current plot."""
        if self._title:
            self.ax.set_title(self._title, fontsize=14)
        self.ax.set_xlabel(self._xlabel, fontsize=12)
        self.ax.set_ylabel(self._ylabel, fontsize=12)
        self.figure.tight_layout()
        self.canvas.draw()

    def hide_plot(self) -> None:
        """Hide the plot (show blank)."""
        self.ax.clear()
        self.ax.text(0.5, 0.5, "No plot for this question",
                    ha='center', va='center', fontsize=14,
                    color='gray', transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()
