"""
Main window for the Math Quiz application.

Provides the primary user interface with:
- Question display area with LaTeX rendering
- Plot display for graphical questions
- Answer input with submission
- Score, difficulty, and timer displays
- Question history panel
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QSplitter,
    QMessageBox, QSizePolicy, QProgressBar, QApplication,
    QMenuBar, QMenu, QDialog, QCheckBox, QDialogButtonBox,
    QFormLayout, QScrollArea
)
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QAction
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .plot_widget import PlotWidget
from .latex_label import MathDisplay, LatexLabel, render_latex_to_pixmap
from .history_widget import HistoryWidget
from .summary_dialog import SummaryDialog

from quiz.engine import QuizEngine
from quiz.difficulty import DifficultyLevel
from quiz.questions.base import Question
from utils.settings import settings


class PreferencesDialog(QDialog):
    """Dialog for editing application preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Standard Categories Title
        title = QLabel("Standard Categories (Easy to Medium)")
        title.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Standard category checkboxes
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.estimation_checkbox = QCheckBox("Estimation questions")
        self.estimation_checkbox.setChecked(settings.include_estimation)
        self.estimation_checkbox.setFont(QFont("DejaVu Sans", 12))
        self.estimation_checkbox.setToolTip("Order-of-magnitude reasoning and approximation")
        form_layout.addRow(self.estimation_checkbox)

        layout.addLayout(form_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #cccccc;")
        layout.addWidget(separator)

        # Advanced Topics Title
        advanced_title = QLabel("Advanced Topics (Hard & Very Hard)")
        advanced_title.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
        advanced_title.setStyleSheet("color: #1565c0;")
        layout.addWidget(advanced_title)

        # Advanced explanation
        advanced_note = QLabel("Hard and Very Hard questions come exclusively from these topics.\nDisabling all limits max difficulty to Medium.")
        advanced_note.setFont(QFont("DejaVu Sans", 10))
        advanced_note.setStyleSheet("color: #666666;")
        layout.addWidget(advanced_note)

        # Advanced category checkboxes
        advanced_layout = QFormLayout()
        advanced_layout.setSpacing(10)

        self.physics_checkbox = QCheckBox("Physics")
        self.physics_checkbox.setChecked(settings.include_physics)
        self.physics_checkbox.setFont(QFont("DejaVu Sans", 12))
        self.physics_checkbox.setToolTip("Mechanics, thermodynamics, waves, electricity")
        advanced_layout.addRow(self.physics_checkbox)

        self.linear_algebra_checkbox = QCheckBox("Linear Algebra (No BS Linear Algebra)")
        self.linear_algebra_checkbox.setChecked(settings.include_linear_algebra)
        self.linear_algebra_checkbox.setFont(QFont("DejaVu Sans", 12))
        self.linear_algebra_checkbox.setToolTip("Vectors, matrices, eigenvalues, linear transformations")
        advanced_layout.addRow(self.linear_algebra_checkbox)

        self.statistics_checkbox = QCheckBox("Statistics (No BS Statistics)")
        self.statistics_checkbox.setChecked(settings.include_statistics)
        self.statistics_checkbox.setFont(QFont("DejaVu Sans", 12))
        self.statistics_checkbox.setToolTip("Probability, distributions, regression, hypothesis testing")
        advanced_layout.addRow(self.statistics_checkbox)

        self.accounting_checkbox = QCheckBox("Accounting for Computer Scientists")
        self.accounting_checkbox.setChecked(settings.include_accounting)
        self.accounting_checkbox.setFont(QFont("DejaVu Sans", 12))
        self.accounting_checkbox.setToolTip("Double-entry bookkeeping, balance sheets, P&L")
        advanced_layout.addRow(self.accounting_checkbox)

        layout.addLayout(advanced_layout)

        # Note
        note = QLabel("Changes take effect on the next quiz session.")
        note.setFont(QFont("DejaVu Sans", 10))
        note.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(note)

        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        """Save settings when OK is clicked."""
        settings.include_physics = self.physics_checkbox.isChecked()
        settings.include_estimation = self.estimation_checkbox.isChecked()
        settings.include_linear_algebra = self.linear_algebra_checkbox.isChecked()
        settings.include_statistics = self.statistics_checkbox.isChecked()
        settings.include_accounting = self.accounting_checkbox.isChecked()
        super().accept()


class StatusPanel(QFrame):
    """Panel showing current score, difficulty, and time."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setStyleSheet("""
            StatusPanel {
                background-color: #37474f;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Score
        score_header = QLabel("SCORE")
        score_header.setFont(QFont("DejaVu Sans", 10))
        score_header.setStyleSheet("color: #90a4ae;")

        self.score_label = QLabel("0")
        self.score_label.setFont(QFont("DejaVu Sans", 32, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color: white;")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Difficulty
        diff_header = QLabel("DIFFICULTY")
        diff_header.setFont(QFont("DejaVu Sans", 10))
        diff_header.setStyleSheet("color: #90a4ae;")

        self.difficulty_label = QLabel("Easy")
        self.difficulty_label.setFont(QFont("DejaVu Sans", 16, QFont.Weight.Bold))
        self.difficulty_label.setStyleSheet("color: #4fc3f7;")
        self.difficulty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Time
        time_header = QLabel("TIME LEFT")
        time_header.setFont(QFont("DejaVu Sans", 10))
        time_header.setStyleSheet("color: #90a4ae;")

        self.time_label = QLabel("10:00")
        self.time_label.setFont(QFont("DejaVu Sans", 24, QFont.Weight.Bold))
        self.time_label.setStyleSheet("color: #81c784;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Progress bar
        self.time_progress = QProgressBar()
        self.time_progress.setTextVisible(False)
        self.time_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #263238;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #81c784;
                border-radius: 4px;
            }
        """)

        layout.addWidget(score_header)
        layout.addWidget(self.score_label)
        layout.addSpacing(10)
        layout.addWidget(diff_header)
        layout.addWidget(self.difficulty_label)
        layout.addSpacing(10)
        layout.addWidget(time_header)
        layout.addWidget(self.time_label)
        layout.addWidget(self.time_progress)
        layout.addStretch()

    def update_score(self, score: int) -> None:
        """Update the displayed score."""
        self.score_label.setText(str(score))

        # Color based on score
        if score >= 100:
            color = "#81c784"  # Green
        elif score >= 0:
            color = "white"
        else:
            color = "#ef5350"  # Red

        self.score_label.setStyleSheet(f"color: {color};")

    def update_difficulty(self, difficulty: DifficultyLevel) -> None:
        """Update the displayed difficulty."""
        name = difficulty.display_name()
        self.difficulty_label.setText(name)

        # Color based on difficulty
        colors = {
            DifficultyLevel.VERY_EASY: "#b3e5fc",
            DifficultyLevel.EASY: "#4fc3f7",
            DifficultyLevel.MEDIUM: "#ffb74d",
            DifficultyLevel.HARD: "#ff8a65",
            DifficultyLevel.VERY_HARD: "#ef5350",
        }
        color = colors.get(difficulty, "#4fc3f7")
        self.difficulty_label.setStyleSheet(f"color: {color};")

    def update_time(self, seconds: int, total_seconds: int) -> None:
        """Update the displayed time."""
        mins = seconds // 60
        secs = seconds % 60
        self.time_label.setText(f"{mins}:{secs:02d}")

        # Update progress bar
        self.time_progress.setMaximum(total_seconds)
        self.time_progress.setValue(seconds)

        # Color based on time remaining
        if seconds < 60:
            color = "#ef5350"  # Red
            chunk_color = "#ef5350"
        elif seconds < 180:
            color = "#ffb74d"  # Orange
            chunk_color = "#ffb74d"
        else:
            color = "#81c784"  # Green
            chunk_color = "#81c784"

        self.time_label.setStyleSheet(f"color: {color};")
        self.time_progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: #263238;
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: 4px;
            }}
        """)


class FeedbackPanel(QFrame):
    """Panel showing answer feedback."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setMinimumHeight(120)
        self.setStyleSheet("""
            FeedbackPanel {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        self.status_label = QLabel()
        self.status_label.setFont(QFont("DejaVu Sans", 18, QFont.Weight.Bold))
        self.status_label.setWordWrap(True)

        self.explanation_label = QLabel()
        self.explanation_label.setFont(QFont("DejaVu Sans", 14))
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setStyleSheet("color: #1a1a1a;")

        # Answer display with LaTeX support
        self.answer_container = QWidget()
        answer_layout = QHBoxLayout(self.answer_container)
        answer_layout.setContentsMargins(0, 0, 0, 0)
        answer_layout.setSpacing(5)

        self.answer_prefix = QLabel("Correct answer: ")
        self.answer_prefix.setFont(QFont("DejaVu Sans", 14))
        self.answer_prefix.setStyleSheet("color: #000000;")

        self.answer_label = QLabel()
        self.answer_label.setFont(QFont("DejaVu Sans", 16, QFont.Weight.Bold))
        self.answer_label.setStyleSheet("color: #000000;")

        answer_layout.addWidget(self.answer_prefix)
        answer_layout.addWidget(self.answer_label)
        answer_layout.addStretch()

        layout.addWidget(self.status_label)
        layout.addWidget(self.explanation_label)
        layout.addWidget(self.answer_container)

        self.clear()

    def show_correct(self, points: int, explanation: str) -> None:
        """Show feedback for a correct answer."""
        self.setStyleSheet("""
            FeedbackPanel {
                background-color: #e8f5e9;
                border: 2px solid #66bb6a;
                border-radius: 8px;
            }
        """)
        self.status_label.setText(f"Correct! +{points} points")
        self.status_label.setStyleSheet("color: #1b5e20;")
        self.explanation_label.setText(explanation)
        self.explanation_label.setStyleSheet("color: #1a1a1a;")
        self.answer_container.hide()

    def show_incorrect(self, points: int, correct_answer: str, explanation: str) -> None:
        """Show feedback for an incorrect answer."""
        self.setStyleSheet("""
            FeedbackPanel {
                background-color: #ffebee;
                border: 2px solid #ef5350;
                border-radius: 8px;
            }
        """)
        self.status_label.setText(f"Incorrect. {points} points")
        self.status_label.setStyleSheet("color: #b71c1c;")
        self.explanation_label.setText(explanation)
        self.explanation_label.setStyleSheet("color: #1a1a1a;")

        # Try to render answer as LaTeX
        self.answer_container.show()
        pixmap = render_latex_to_pixmap(correct_answer, fontsize=16)
        if pixmap and not pixmap.isNull():
            self.answer_label.setPixmap(pixmap)
        else:
            self.answer_label.setText(correct_answer)
            self.answer_label.setStyleSheet("color: #000000; font-weight: bold;")

    def show_trivial_warning(self) -> None:
        """Show warning for trivial answer."""
        self.setStyleSheet("""
            FeedbackPanel {
                background-color: #fff3e0;
                border: 2px solid #ffb74d;
                border-radius: 8px;
            }
        """)
        self.status_label.setText("Trivial Answer Detected")
        self.status_label.setStyleSheet("color: #e65100;")
        self.explanation_label.setText(
            "Your answer appears too simple for this difficulty level. "
            "Extra penalty applied."
        )
        self.explanation_label.setStyleSheet("color: #1a1a1a;")

    def clear(self) -> None:
        """Clear feedback display."""
        self.setStyleSheet("""
            FeedbackPanel {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        self.status_label.clear()
        self.explanation_label.setText("Submit your answer to see feedback")
        self.explanation_label.setStyleSheet("color: #666666;")
        self.answer_label.clear()
        self.answer_container.hide()


class MainWindow(QMainWindow):
    """
    Main application window for the Math Quiz.

    Layout:
    +----------------------------------+----------------+
    |  Question Display (LaTeX)        |  Status Panel  |
    |  [Plot Area if needed]           |  - Score       |
    |                                  |  - Difficulty  |
    |  [Answer Input]                  |  - Time        |
    |  [Submit] [Skip] [Hint]          |                |
    |                                  |  History       |
    |  Feedback Area                   |  Panel         |
    +----------------------------------+----------------+
    """

    def __init__(self, duration: int = 600):
        super().__init__()

        self.setWindowTitle("Math Quiz - Practical Mathematics")
        self.setMinimumSize(1400, 900)

        # Default to 1920x1080 optimization
        self.resize(1600, 950)

        # Quiz engine
        self.engine = QuizEngine(duration=duration)
        self.total_duration = duration

        # Timer for updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_time)

        # Build UI
        self._setup_ui()
        self._setup_shortcuts()

        # Show start screen
        self._show_start_screen()

    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        # Create menu bar
        self._setup_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)

        # Main horizontal layout
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Left side - quiz area
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # Question display with scroll area
        self.question_scroll = QScrollArea()
        self.question_scroll.setWidgetResizable(True)
        self.question_scroll.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)

        self.question_frame = QWidget()
        self.question_frame.setStyleSheet("background-color: white;")
        question_layout = QVBoxLayout(self.question_frame)
        question_layout.setContentsMargins(20, 20, 20, 20)

        self.math_display = MathDisplay()
        question_layout.addWidget(self.math_display)

        # Plot widget
        self.plot_widget = PlotWidget()
        self.plot_widget.setMinimumHeight(300)
        self.plot_widget.hide()
        question_layout.addWidget(self.plot_widget)

        self.question_scroll.setWidget(self.question_frame)
        left_layout.addWidget(self.question_scroll, 3)

        # Answer input area
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(20, 15, 20, 15)

        self.input_label = QLabel("Your Answer:")
        self.input_label.setFont(QFont("DejaVu Sans", 14))

        self.answer_input = QLineEdit()
        self.answer_input.setFont(QFont("DejaVu Sans Mono", 18))
        self.answer_input.setPlaceholderText("Enter your answer (e.g., x^2, sqrt(2)/2, [1, 2])")
        self.answer_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #bdbdbd;
                border-radius: 6px;
                padding: 12px;
                background-color: #fafafa;
            }
            QLineEdit:focus {
                border-color: #1976d2;
                background-color: white;
            }
        """)
        self.answer_input.returnPressed.connect(self._submit_answer)

        # Multiple choice container
        self.choice_container = QWidget()
        choice_layout = QVBoxLayout(self.choice_container)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(8)
        self.choice_buttons = []
        self._selected_choice = None

        # Create 4 choice buttons (A, B, C, D)
        choice_style = """
            QPushButton {
                background-color: #f5f5f5;
                color: #333;
                border: 2px solid #bdbdbd;
                border-radius: 6px;
                padding: 12px 20px;
                text-align: left;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
                border-color: #1976d2;
            }
            QPushButton:checked {
                background-color: #bbdefb;
                border-color: #1976d2;
            }
        """
        for i, letter in enumerate(['A', 'B', 'C', 'D']):
            btn = QPushButton(f"{letter})")
            btn.setFont(QFont("DejaVu Sans", 14))
            btn.setStyleSheet(choice_style)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._select_choice(idx))
            choice_layout.addWidget(btn)
            self.choice_buttons.append(btn)

        self.choice_container.hide()

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.submit_btn = QPushButton("Submit (Enter)")
        self.submit_btn.setFont(QFont("DejaVu Sans", 14))
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 25px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:disabled {
                background-color: #bdbdbd;
            }
        """)
        self.submit_btn.clicked.connect(self._submit_answer)

        self.skip_btn = QPushButton("Skip (Esc)")
        self.skip_btn.setFont(QFont("DejaVu Sans", 14))
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 25px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        self.skip_btn.clicked.connect(self._skip_question)

        self.hint_btn = QPushButton("Hint (Ctrl+H)")
        self.hint_btn.setFont(QFont("DejaVu Sans", 14))
        self.hint_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 25px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self.hint_btn.clicked.connect(self._show_hint)

        button_layout.addWidget(self.submit_btn)
        button_layout.addWidget(self.skip_btn)
        button_layout.addWidget(self.hint_btn)
        button_layout.addStretch()

        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.answer_input)
        input_layout.addWidget(self.choice_container)
        input_layout.addLayout(button_layout)

        left_layout.addWidget(input_frame)

        # Feedback panel
        self.feedback_panel = FeedbackPanel()
        left_layout.addWidget(self.feedback_panel)

        main_layout.addWidget(left_panel, 3)

        # Right side - status and history
        right_panel = QWidget()
        right_panel.setFixedWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Status panel
        self.status_panel = StatusPanel()
        right_layout.addWidget(self.status_panel)

        # History panel
        self.history_widget = HistoryWidget()
        right_layout.addWidget(self.history_widget, 1)

        # Start/Stop buttons
        self.start_btn = QPushButton("Start Quiz")
        self.start_btn.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #43a047;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.start_btn.clicked.connect(self._start_quiz)
        right_layout.addWidget(self.start_btn)

        main_layout.addWidget(right_panel)

        # Track current question
        self._current_question: Optional[Question] = None

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # Enter is handled by answer_input.returnPressed (line 533)
        # Do NOT add a duplicate QShortcut for Enter

        # Escape to skip
        skip_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        skip_shortcut.activated.connect(self._skip_question)

        # Ctrl+H for hint (plain "H" would fire while typing answers)
        hint_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        hint_shortcut.activated.connect(self._show_hint)

        # Ctrl+N for next question (plain "N" would fire while typing answers)
        next_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        next_shortcut.activated.connect(self._next_question)

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar."""
        menu_bar = self.menuBar()

        # Change Problem Mix menu
        advanced_menu = menu_bar.addMenu("&Change Problem Mix")

        # Preferences action
        preferences_action = QAction("&Preferences...", self)
        preferences_action.setShortcut(QKeySequence("Ctrl+,"))
        preferences_action.triggered.connect(self._show_preferences)
        advanced_menu.addAction(preferences_action)

    def _show_preferences(self) -> None:
        """Show the preferences dialog."""
        dialog = PreferencesDialog(self)
        dialog.exec()

    def _show_start_screen(self) -> None:
        """Show the initial start screen."""
        self.math_display.set_content(
            title="Welcome to Math Quiz!",
            latex="",
            hint=""
        )
        self.math_display.title_label.setText(
            "Welcome to Math Quiz!\n\n"
            "This quiz adapts to your skill level, featuring practical "
            "mathematics problems for physics and engineering.\n\n"
            "• Answer correctly to increase difficulty and earn more points\n"
            "• Use hints sparingly (no penalty, but shows you're learning)\n"
            "• Trivial answers on hard questions are penalized extra\n\n"
            "Press 'Start Quiz' when ready!"
        )
        self.plot_widget.hide()
        self.answer_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.hint_btn.setEnabled(False)

        # Initialize status
        self.status_panel.update_time(self.total_duration, self.total_duration)
        self.status_panel.update_score(0)
        self.status_panel.update_difficulty(DifficultyLevel.EASY)

    def _start_quiz(self) -> None:
        """Start a new quiz session."""
        # Reset UI
        self.history_widget.clear()
        self.feedback_panel.clear()

        # Start engine
        self.engine = QuizEngine(duration=self.total_duration)
        self.engine.start_session()

        # Enable controls
        self.answer_input.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.hint_btn.setEnabled(True)

        # Change button to "End Quiz"
        self.start_btn.setText("End Quiz")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #e53935;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #c62828;
            }
        """)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self._end_quiz)

        # Start timer
        self.update_timer.start(1000)

        # Get first question
        self._next_question()

    def _end_quiz(self) -> None:
        """End the current quiz session."""
        self.update_timer.stop()
        self.engine.stop_session()
        self._show_summary()

    def _next_question(self) -> None:
        """Load and display the next question."""
        if not self.engine.is_active():
            self._end_quiz()
            return

        question = self.engine.get_next_question()
        if question is None:
            self._end_quiz()
            return

        self._current_question = question

        # Update display
        self.math_display.set_content(
            title=question.text,
            latex=question.latex if question.latex != question.text else "",
            hint=""
        )

        # Handle plot
        if question.requires_plot and question.plot_data:
            self.plot_widget.plot_from_data(question.plot_data)
            self.plot_widget.show()
        else:
            self.plot_widget.hide()

        # Handle multiple choice vs text input
        if question.choices:
            self.answer_input.hide()
            self.choice_container.show()
            self.input_label.setText("Select your answer:")
            self._selected_choice = None
            # Update choice button labels
            for i, (label, value) in enumerate(question.choices):
                if i < len(self.choice_buttons):
                    self.choice_buttons[i].setText(f"{chr(65+i)}) {label}")
                    self.choice_buttons[i].setChecked(False)
                    self.choice_buttons[i].show()
            # Hide unused buttons
            for i in range(len(question.choices), len(self.choice_buttons)):
                self.choice_buttons[i].hide()
        else:
            self.answer_input.show()
            self.choice_container.hide()
            self.input_label.setText("Your Answer:")

        # Clear input and feedback, re-enable controls
        self.answer_input.clear()
        self.answer_input.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.answer_input.setFocus()
        self.feedback_panel.clear()

        # Update status
        self._update_status()

    def _select_choice(self, idx: int) -> None:
        """Handle multiple choice selection."""
        self._selected_choice = idx
        # Uncheck other buttons
        for i, btn in enumerate(self.choice_buttons):
            btn.setChecked(i == idx)

    def _submit_answer(self) -> None:
        """Submit the current answer."""
        if not self.engine.is_active() or self._current_question is None:
            return

        # Handle multiple choice
        if self._current_question.choices:
            if self._selected_choice is None:
                return
            # Get the value for the selected choice
            answer = str(self._current_question.choices[self._selected_choice][1])
        else:
            answer = self.answer_input.text().strip()
            if not answer:
                return

        # Save question info before submission clears engine state
        question = self._current_question
        self._current_question = None  # Prevent re-submission

        # Disable input during feedback delay
        self.answer_input.setEnabled(False)
        self.submit_btn.setEnabled(False)

        result = self.engine.submit_answer(answer)

        # Show feedback
        if result['score_result'] is not None:
            if result['correct']:
                self.feedback_panel.show_correct(
                    result['score_result'].points,
                    result['explanation']
                )
            else:
                if result['is_trivial']:
                    self.feedback_panel.show_trivial_warning()
                self.feedback_panel.show_incorrect(
                    result['score_result'].points,
                    result['correct_answer'],
                    result['explanation']
                )

            # Add to history
            self.history_widget.add_item(
                category=question.category.value,
                difficulty=question.difficulty.display_name(),
                correct=result['correct'],
                points=result['score_result'].points
            )

        # Update status
        self._update_status()

        # Auto-advance after delay (longer for reading feedback)
        QTimer.singleShot(4000, self._next_question)

    def _skip_question(self) -> None:
        """Skip the current question."""
        if not self.engine.is_active() or self._current_question is None:
            return

        self.engine.skip_question()

        # Add to history
        self.history_widget.add_item(
            category=self._current_question.category.value,
            difficulty=self._current_question.difficulty.display_name(),
            correct=False,
            points=-2
        )

        self._update_status()
        self._next_question()

    def _show_hint(self) -> None:
        """Show hint for the current question."""
        if self._current_question and self._current_question.hint:
            self.math_display.show_hint(self._current_question.hint)

    def _update_time(self) -> None:
        """Update the time display (called every second)."""
        remaining = self.engine.get_time_remaining()
        self.status_panel.update_time(remaining, self.total_duration)

        if remaining <= 0:
            self._end_quiz()

    def _update_status(self) -> None:
        """Update all status displays."""
        self.status_panel.update_score(self.engine.get_score())
        self.status_panel.update_difficulty(self.engine.get_current_difficulty())

    def _show_summary(self) -> None:
        """Show the session summary dialog."""
        summary = self.engine.get_session_summary()
        dialog = SummaryDialog(summary, self)

        # Disable quiz controls
        self.answer_input.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.hint_btn.setEnabled(False)

        # Reset start button
        self.start_btn.setText("Start Quiz")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #43a047;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self._start_quiz)

        if dialog.exec() == dialog.DialogCode.Accepted:
            # User wants to start new quiz
            self._start_quiz()
        else:
            self._show_start_screen()
