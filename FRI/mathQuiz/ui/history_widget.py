"""
Question history widget for displaying recent quiz activity.

Shows a scrollable list of recent questions with their
results (correct/incorrect) and point changes.
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtCore import Qt


class HistoryItem(QFrame):
    """Single item in the question history list."""

    def __init__(
        self,
        question_num: int,
        category: str,
        difficulty: str,
        correct: bool,
        points: int,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        # Background color based on result
        if correct:
            self.setStyleSheet("""
                HistoryItem {
                    background-color: #e8f5e9;
                    border: 1px solid #a5d6a7;
                    border-radius: 4px;
                    margin: 2px;
                }
            """)
            icon = "✓"
            icon_color = "#2e7d32"
        else:
            self.setStyleSheet("""
                HistoryItem {
                    background-color: #ffebee;
                    border: 1px solid #ef9a9a;
                    border-radius: 4px;
                    margin: 2px;
                }
            """)
            icon = "✗"
            icon_color = "#c62828"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Question number
        num_label = QLabel(f"Q{question_num}")
        num_label.setFont(QFont("DejaVu Sans", 11, QFont.Weight.Bold))
        num_label.setFixedWidth(35)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("DejaVu Sans", 14))
        icon_label.setStyleSheet(f"color: {icon_color};")
        icon_label.setFixedWidth(20)

        # Category
        cat_label = QLabel(category[:8])  # Truncate long names
        cat_label.setFont(QFont("DejaVu Sans", 10))
        cat_label.setStyleSheet("color: #666666;")
        cat_label.setFixedWidth(70)

        # Difficulty
        diff_label = QLabel(difficulty[:6])
        diff_label.setFont(QFont("DejaVu Sans", 9))
        diff_label.setStyleSheet("color: #888888;")
        diff_label.setFixedWidth(50)

        # Points
        if points >= 0:
            points_text = f"+{points}"
            points_color = "#2e7d32"
        else:
            points_text = str(points)
            points_color = "#c62828"

        points_label = QLabel(points_text)
        points_label.setFont(QFont("DejaVu Sans", 11, QFont.Weight.Bold))
        points_label.setStyleSheet(f"color: {points_color};")
        points_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(num_label)
        layout.addWidget(icon_label)
        layout.addWidget(cat_label)
        layout.addWidget(diff_label)
        layout.addStretch()
        layout.addWidget(points_label)


class HistoryWidget(QWidget):
    """
    Widget displaying recent question history.

    Shows a scrollable list of the most recent questions
    with their results and point changes.
    """

    MAX_ITEMS = 8  # Maximum items to display

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("Recent Questions")
        header.setFont(QFont("DejaVu Sans", 12, QFont.Weight.Bold))
        header.setStyleSheet("""
            QLabel {
                background-color: #424242;
                color: white;
                padding: 8px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
        """)
        layout.addWidget(header)

        # Scroll area for history items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #bdbdbd;
                border-top: none;
                background-color: #fafafa;
            }
        """)

        # Container for items
        self.container = QWidget()
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setContentsMargins(4, 4, 4, 4)
        self.items_layout.setSpacing(2)
        self.items_layout.addStretch()

        scroll.setWidget(self.container)
        layout.addWidget(scroll)

        # Track items
        self._items: List[HistoryItem] = []
        self._question_count = 0

    def add_item(
        self,
        category: str,
        difficulty: str,
        correct: bool,
        points: int
    ) -> None:
        """
        Add a new item to the history.

        Args:
            category: Question category name
            difficulty: Difficulty level name
            correct: Whether the answer was correct
            points: Points earned/lost
        """
        self._question_count += 1

        item = HistoryItem(
            question_num=self._question_count,
            category=category,
            difficulty=difficulty,
            correct=correct,
            points=points
        )

        # Remove stretch, add item, add stretch back
        self.items_layout.takeAt(self.items_layout.count() - 1)  # Remove stretch
        self.items_layout.insertWidget(0, item)  # Add at top
        self.items_layout.addStretch()

        self._items.insert(0, item)

        # Remove old items if over limit
        while len(self._items) > self.MAX_ITEMS:
            old_item = self._items.pop()
            self.items_layout.removeWidget(old_item)
            old_item.deleteLater()

    def clear(self) -> None:
        """Clear all history items."""
        for item in self._items:
            self.items_layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._question_count = 0

    def get_question_count(self) -> int:
        """Get total questions answered."""
        return self._question_count
