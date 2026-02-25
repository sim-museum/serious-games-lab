"""
Session summary dialog displayed at the end of a quiz session.

Shows comprehensive statistics and feedback about the user's performance.
"""

from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QScrollArea,
    QSizePolicy, QWidget
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class SummaryDialog(QDialog):
    """Dialog showing comprehensive session summary."""

    def __init__(self, summary_data: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("Quiz Complete!")
        self.setMinimumSize(700, 600)
        self.resize(750, 650)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 15)
        main_layout.setSpacing(0)

        # Header with score
        header = self._create_header(summary_data)
        main_layout.addWidget(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(25, 20, 25, 20)
        content_layout.setSpacing(20)

        # Stats summary
        stats_widget = self._create_stats_widget(summary_data)
        content_layout.addWidget(stats_widget)

        # Performance breakdown
        breakdown_widget = self._create_breakdown_widget(summary_data)
        content_layout.addWidget(breakdown_widget)

        # Feedback
        feedback_widget = self._create_feedback_widget(summary_data)
        content_layout.addWidget(feedback_widget)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(25, 10, 25, 0)

        new_quiz_btn = QPushButton("New Quiz")
        new_quiz_btn.setFont(QFont("DejaVu Sans", 13))
        new_quiz_btn.setMinimumHeight(40)
        new_quiz_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 30px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        new_quiz_btn.clicked.connect(self.accept)

        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("DejaVu Sans", 13))
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 30px;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        close_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(new_quiz_btn)
        button_layout.addSpacing(10)
        button_layout.addWidget(close_btn)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

    def _create_header(self, data: Dict) -> QWidget:
        """Create the header with final score."""
        header = QFrame()
        header.setStyleSheet("background-color: #1976d2;")
        header.setMinimumHeight(120)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(5)

        title = QLabel("Quiz Complete!")
        title.setFont(QFont("DejaVu Sans", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        score = data.get('final_score', 0)
        score_label = QLabel(f"Final Score: {score}")
        score_label.setFont(QFont("DejaVu Sans", 32, QFont.Weight.Bold))
        score_label.setStyleSheet("color: white;")
        score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        duration = data.get('duration_used', 0)
        mins, secs = divmod(duration, 60)
        time_label = QLabel(f"Time: {mins}:{secs:02d}")
        time_label.setFont(QFont("DejaVu Sans", 12))
        time_label.setStyleSheet("color: rgba(255,255,255,0.8);")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(score_label)
        layout.addWidget(time_label)

        return header

    def _create_stats_widget(self, data: Dict) -> QWidget:
        """Create the stats summary widget."""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        total = data.get('total_questions', 0)
        correct = data.get('correct_answers', 0)
        accuracy = data.get('accuracy', 0) * 100

        stats = [
            ("Questions", str(total), "#1976d2"),
            ("Correct", str(correct), "#2e7d32"),
            ("Incorrect", str(total - correct), "#c62828"),
            ("Accuracy", f"{accuracy:.0f}%", "#2e7d32" if accuracy >= 70 else "#f57c00" if accuracy >= 50 else "#c62828"),
        ]

        for label, value, color in stats:
            stat_widget = QWidget()
            stat_layout = QVBoxLayout(stat_widget)
            stat_layout.setContentsMargins(10, 5, 10, 5)
            stat_layout.setSpacing(2)

            value_lbl = QLabel(value)
            value_lbl.setFont(QFont("DejaVu Sans", 24, QFont.Weight.Bold))
            value_lbl.setStyleSheet(f"color: {color};")
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            label_lbl = QLabel(label)
            label_lbl.setFont(QFont("DejaVu Sans", 11))
            label_lbl.setStyleSheet("color: #666;")
            label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            stat_layout.addWidget(value_lbl)
            stat_layout.addWidget(label_lbl)
            layout.addWidget(stat_widget)

        return widget

    def _create_breakdown_widget(self, data: Dict) -> QWidget:
        """Create the performance breakdown widget."""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        title = QLabel("Performance Breakdown")
        title.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #333;")
        layout.addWidget(title)

        # Difficulty distribution
        diff_dist = data.get('difficulty_distribution', {})
        if diff_dist:
            diff_text = "By Difficulty:  " + ",  ".join(f"{k}: {v}" for k, v in diff_dist.items() if v > 0)
            diff_label = QLabel(diff_text)
            diff_label.setFont(QFont("DejaVu Sans", 12))
            diff_label.setStyleSheet("color: #444;")
            diff_label.setWordWrap(True)
            layout.addWidget(diff_label)

        # Category performance
        cat_stats = data.get('category_stats', {})
        if cat_stats:
            cat_title = QLabel("By Category:")
            cat_title.setFont(QFont("DejaVu Sans", 12, QFont.Weight.Bold))
            cat_title.setStyleSheet("color: #444;")
            layout.addWidget(cat_title)

            for cat, stats in cat_stats.items():
                total = stats['total']
                correct = stats['correct']
                pct = (correct / total * 100) if total > 0 else 0
                cat_label = QLabel(f"    {cat}: {correct}/{total} ({pct:.0f}%)")
                cat_label.setFont(QFont("DejaVu Sans", 12))
                cat_label.setStyleSheet("color: #555;")
                layout.addWidget(cat_label)

        return widget

    def _create_feedback_widget(self, data: Dict) -> QWidget:
        """Create the feedback widget."""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        title = QLabel("Feedback")
        title.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #333;")
        layout.addWidget(title)

        feedback_text = data.get('feedback', 'Keep practicing!')
        feedback = QLabel(feedback_text)
        feedback.setFont(QFont("DejaVu Sans", 12))
        feedback.setStyleSheet("color: #444;")
        feedback.setWordWrap(True)
        layout.addWidget(feedback)

        weak = data.get('weak_categories', [])
        if weak:
            weak_label = QLabel(f"Focus areas: {', '.join(weak)}")
            weak_label.setFont(QFont("DejaVu Sans", 12, QFont.Weight.Bold))
            weak_label.setStyleSheet("color: #c62828;")
            layout.addWidget(weak_label)

        return widget
