#!/usr/bin/env python3
"""
Dual N-Back - Brain Workshop Style
A PyQt6 implementation of the Dual N-Back cognitive training game.
Runs on Ubuntu 24.04 with Python 3.10+
"""

import sys
import json
import random
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QDialog, QSpinBox, QComboBox,
    QCheckBox, QLineEdit, QGroupBox, QFormLayout, QMessageBox,
    QDoubleSpinBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent, QColor, QPalette

# Try to import text-to-speech
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("Warning: pyttsx3 not available. Install with: pip install pyttsx3")


@dataclass
class Settings:
    """Game settings that persist between sessions."""
    n_back_level: int = 2
    game_mode: str = "Dual N-Back"
    trials_per_session: int = 20
    trial_interval: float = 3.0
    position_key: str = "A"
    letter_key: str = "L"
    sound_enabled: bool = True
    adaptive_enabled: bool = True
    advance_threshold: float = 80.0
    fallback_threshold: float = 50.0

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """Load settings from JSON file."""
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self, path: Path) -> None:
        """Save settings to JSON file."""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)


class AudioPlayer:
    """Handles text-to-speech for letter sounds."""

    LETTERS = ['C', 'H', 'K', 'L', 'Q', 'R', 'S', 'T']  # Brain Workshop standard letters

    def __init__(self):
        self.engine = None
        self.enabled = True
        self.use_espeak = False
        self.espeak_path = None

        # Always detect espeak (used for non-blocking speech)
        self.espeak_path = shutil.which('espeak') or shutil.which('espeak-ng')
        if self.espeak_path:
            self.use_espeak = True

        # Try pyttsx3 for synchronous speech
        if TTS_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 0.9)
            except Exception as e:
                print(f"Warning: Could not initialize pyttsx3: {e}")

        if not self.engine and not self.use_espeak:
            print("Warning: No TTS available. Install espeak: sudo apt install espeak")

    def speak(self, letter: str) -> None:
        """Speak a letter."""
        if not self.enabled:
            return

        if self.engine:
            try:
                self.engine.say(letter)
                self.engine.runAndWait()
            except Exception:
                pass
        elif self.use_espeak:
            self._espeak(letter)

    def speak_async(self, letter: str) -> None:
        """Speak a letter without blocking (best effort)."""
        if not self.enabled:
            return

        if self.use_espeak:
            self._espeak_async(letter)

    def _espeak(self, letter: str) -> None:
        """Speak using espeak (blocking)."""
        try:
            subprocess.run(
                [self.espeak_path, '-v', 'en', '-s', '150', letter],
                capture_output=True,
                timeout=2
            )
        except Exception:
            pass

    def _espeak_async(self, letter: str) -> None:
        """Speak using espeak (non-blocking)."""
        try:
            subprocess.Popen(
                [self.espeak_path, '-v', 'en', '-s', '150', letter],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


class GameEngine:
    """Core Dual N-Back game logic."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.reset()

    def reset(self) -> None:
        """Reset game state for a new session."""
        self.positions: list[int] = []  # 0-8 for 3x3 grid
        self.letters: list[str] = []
        self.current_trial = 0
        self.position_responses: list[Optional[bool]] = []  # None=no response, True=pressed
        self.letter_responses: list[Optional[bool]] = []
        self.position_correct: list[bool] = []
        self.letter_correct: list[bool] = []

    def generate_trial(self) -> tuple[int, str]:
        """Generate next position and letter for trial."""
        n = self.settings.n_back_level

        # Generate position with ~25% match probability if possible
        if len(self.positions) >= n and random.random() < 0.25:
            position = self.positions[-n]
        else:
            position = random.randint(0, 8)

        # Generate letter with ~25% match probability if possible
        if len(self.letters) >= n and random.random() < 0.25:
            letter = self.letters[-n]
        else:
            letter = random.choice(AudioPlayer.LETTERS)

        self.positions.append(position)
        self.letters.append(letter)
        self.position_responses.append(None)
        self.letter_responses.append(None)
        self.current_trial += 1

        return position, letter

    def is_position_match(self) -> bool:
        """Check if current position matches N trials ago."""
        n = self.settings.n_back_level
        if len(self.positions) <= n:
            return False
        return self.positions[-1] == self.positions[-n - 1]

    def is_letter_match(self) -> bool:
        """Check if current letter matches N trials ago."""
        n = self.settings.n_back_level
        if len(self.letters) <= n:
            return False
        return self.letters[-1] == self.letters[-n - 1]

    def record_position_response(self) -> None:
        """Record that user pressed position match key."""
        if self.position_responses and self.position_responses[-1] is None:
            self.position_responses[-1] = True

    def record_letter_response(self) -> None:
        """Record that user pressed letter match key."""
        if self.letter_responses and self.letter_responses[-1] is None:
            self.letter_responses[-1] = True

    def evaluate_trial(self) -> tuple[bool, bool]:
        """Evaluate the current trial responses. Returns (position_correct, letter_correct)."""
        pos_match = self.is_position_match()
        letter_match = self.is_letter_match()

        pos_response = self.position_responses[-1] if self.position_responses else None
        letter_response = self.letter_responses[-1] if self.letter_responses else None

        # Correct if: match and pressed, or no match and not pressed
        pos_correct = (pos_match == (pos_response is True))
        letter_correct = (letter_match == (letter_response is True))

        self.position_correct.append(pos_correct)
        self.letter_correct.append(letter_correct)

        return pos_correct, letter_correct

    def get_results(self) -> dict:
        """Get session results."""
        n = self.settings.n_back_level

        # Only count trials where a match was possible (trial > n)
        scoreable_trials = max(0, self.current_trial - n)

        if scoreable_trials == 0:
            return {
                'total_trials': self.current_trial,
                'scoreable_trials': 0,
                'position_correct': 0,
                'letter_correct': 0,
                'position_accuracy': 0.0,
                'letter_accuracy': 0.0,
                'overall_accuracy': 0.0
            }

        # Count correct responses for scoreable trials only
        pos_correct = sum(self.position_correct[n:])
        letter_correct = sum(self.letter_correct[n:])

        pos_accuracy = (pos_correct / scoreable_trials) * 100
        letter_accuracy = (letter_correct / scoreable_trials) * 100
        overall_accuracy = ((pos_correct + letter_correct) / (scoreable_trials * 2)) * 100

        return {
            'total_trials': self.current_trial,
            'scoreable_trials': scoreable_trials,
            'position_correct': pos_correct,
            'letter_correct': letter_correct,
            'position_accuracy': pos_accuracy,
            'letter_accuracy': letter_accuracy,
            'overall_accuracy': overall_accuracy
        }


class GridCell(QLabel):
    """A single cell in the 3x3 grid."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(100, 100)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reset_style()

    def reset_style(self) -> None:
        """Reset to default appearance."""
        self.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: 8px;
            }
        """)

    def highlight(self) -> None:
        """Highlight as active cell."""
        self.setStyleSheet("""
            QLabel {
                background-color: #4a90d9;
                border: 2px solid #6ab0ff;
                border-radius: 8px;
            }
        """)

    def show_correct(self) -> None:
        """Show correct feedback (green flash)."""
        self.setStyleSheet("""
            QLabel {
                background-color: #4caf50;
                border: 2px solid #66bb6a;
                border-radius: 8px;
            }
        """)

    def show_incorrect(self) -> None:
        """Show incorrect feedback (red flash)."""
        self.setStyleSheet("""
            QLabel {
                background-color: #f44336;
                border: 2px solid #ef5350;
                border-radius: 8px;
            }
        """)


class SettingsDialog(QDialog):
    """Settings dialog similar to Brain Workshop's options."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Game settings group
        game_group = QGroupBox("Game Settings")
        game_layout = QFormLayout()

        self.n_back_spin = QSpinBox()
        self.n_back_spin.setRange(1, 9)
        self.n_back_spin.setValue(self.settings.n_back_level)
        game_layout.addRow("N-Back Level:", self.n_back_spin)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Dual N-Back", "Position Only", "Audio Only"])
        self.mode_combo.setCurrentText(self.settings.game_mode)
        game_layout.addRow("Game Mode:", self.mode_combo)

        self.trials_spin = QSpinBox()
        self.trials_spin.setRange(5, 100)
        self.trials_spin.setValue(self.settings.trials_per_session)
        game_layout.addRow("Trials per Session:", self.trials_spin)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(1.0, 10.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(self.settings.trial_interval)
        self.interval_spin.setSuffix(" seconds")
        game_layout.addRow("Trial Interval:", self.interval_spin)

        game_group.setLayout(game_layout)
        layout.addWidget(game_group)

        # Key bindings group
        keys_group = QGroupBox("Key Bindings")
        keys_layout = QFormLayout()

        self.position_key_edit = QLineEdit(self.settings.position_key)
        self.position_key_edit.setMaxLength(1)
        self.position_key_edit.setMaximumWidth(50)
        keys_layout.addRow("Position Match Key:", self.position_key_edit)

        self.letter_key_edit = QLineEdit(self.settings.letter_key)
        self.letter_key_edit.setMaxLength(1)
        self.letter_key_edit.setMaximumWidth(50)
        keys_layout.addRow("Letter Match Key:", self.letter_key_edit)

        keys_group.setLayout(keys_layout)
        layout.addWidget(keys_group)

        # Audio settings group
        audio_group = QGroupBox("Audio")
        audio_layout = QFormLayout()

        self.sound_check = QCheckBox("Enable sounds")
        self.sound_check.setChecked(self.settings.sound_enabled)
        audio_layout.addRow(self.sound_check)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # Adaptive difficulty group
        adaptive_group = QGroupBox("Adaptive Difficulty")
        adaptive_layout = QFormLayout()

        self.adaptive_check = QCheckBox("Enable adaptive difficulty")
        self.adaptive_check.setChecked(self.settings.adaptive_enabled)
        adaptive_layout.addRow(self.adaptive_check)

        self.advance_spin = QDoubleSpinBox()
        self.advance_spin.setRange(50, 100)
        self.advance_spin.setValue(self.settings.advance_threshold)
        self.advance_spin.setSuffix("%")
        adaptive_layout.addRow("Advance threshold:", self.advance_spin)

        self.fallback_spin = QDoubleSpinBox()
        self.fallback_spin.setRange(0, 80)
        self.fallback_spin.setValue(self.settings.fallback_threshold)
        self.fallback_spin.setSuffix("%")
        adaptive_layout.addRow("Fallback threshold:", self.fallback_spin)

        adaptive_group.setLayout(adaptive_layout)
        layout.addWidget(adaptive_group)

        # Buttons
        button_layout = QHBoxLayout()

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def get_settings(self) -> Settings:
        """Return updated settings from dialog values."""
        return Settings(
            n_back_level=self.n_back_spin.value(),
            game_mode=self.mode_combo.currentText(),
            trials_per_session=self.trials_spin.value(),
            trial_interval=self.interval_spin.value(),
            position_key=self.position_key_edit.text().upper() or "A",
            letter_key=self.letter_key_edit.text().upper() or "L",
            sound_enabled=self.sound_check.isChecked(),
            adaptive_enabled=self.adaptive_check.isChecked(),
            advance_threshold=self.advance_spin.value(),
            fallback_threshold=self.fallback_spin.value()
        )


class ResultsDialog(QDialog):
    """Dialog shown at end of session with results."""

    new_session_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, results: dict, n_level: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session Complete")
        self.setModal(True)
        self.setMinimumWidth(350)
        self.setup_ui(results, n_level)

    def setup_ui(self, results: dict, n_level: int) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"Dual {n_level}-Back Session Complete")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        # Results
        results_group = QGroupBox("Results")
        results_layout = QFormLayout()

        results_layout.addRow("Total Trials:", QLabel(str(results['total_trials'])))
        results_layout.addRow("Scoreable Trials:", QLabel(str(results['scoreable_trials'])))

        layout.addSpacing(10)

        pos_label = QLabel(f"{results['position_correct']} / {results['scoreable_trials']} ({results['position_accuracy']:.1f}%)")
        results_layout.addRow("Position Correct:", pos_label)

        letter_label = QLabel(f"{results['letter_correct']} / {results['scoreable_trials']} ({results['letter_accuracy']:.1f}%)")
        results_layout.addRow("Letter Correct:", letter_label)

        overall_label = QLabel(f"{results['overall_accuracy']:.1f}%")
        overall_label.setFont(QFont("", 12, QFont.Weight.Bold))
        results_layout.addRow("Overall Accuracy:", overall_label)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()

        new_session_btn = QPushButton("New Session")
        new_session_btn.clicked.connect(self._on_new_session)
        button_layout.addWidget(new_session_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        button_layout.addWidget(settings_btn)

        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.reject)
        button_layout.addWidget(quit_btn)

        layout.addLayout(button_layout)

    def _on_new_session(self) -> None:
        self.new_session_clicked.emit()
        self.accept()

    def _on_settings(self) -> None:
        self.settings_clicked.emit()
        self.accept()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config_path = Path.home() / ".config" / "dual_nback" / "settings.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        self.settings = Settings.load(self.config_path)
        self.audio = AudioPlayer()
        self.audio.enabled = self.settings.sound_enabled
        self.engine = GameEngine(self.settings)

        self.trial_timer = QTimer()
        self.trial_timer.timeout.connect(self.next_trial)

        self.feedback_timer = QTimer()
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self.clear_feedback)

        self.session_active = False
        self.current_position = -1

        self.setup_ui()
        self.setWindowTitle("Dual N-Back")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Start session after window is shown
        QTimer.singleShot(500, self.start_session)

    def setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with info
        header_layout = QHBoxLayout()

        self.level_label = QLabel(f"Dual {self.settings.n_back_level}-Back")
        self.level_label.setFont(QFont("", 16, QFont.Weight.Bold))
        header_layout.addWidget(self.level_label)

        header_layout.addStretch()

        self.trial_label = QLabel("Trial: 0 / 0")
        self.trial_label.setFont(QFont("", 12))
        header_layout.addWidget(self.trial_label)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        # Grid
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setSpacing(10)

        self.cells: list[GridCell] = []
        for i in range(9):
            cell = GridCell()
            row, col = divmod(i, 3)
            grid_layout.addWidget(cell, row, col)
            self.cells.append(cell)

        main_layout.addWidget(grid_container, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addSpacing(20)

        # Response indicators
        indicator_layout = QHBoxLayout()

        self.position_indicator = QLabel(f"Position ({self.settings.position_key})")
        self.position_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")
        indicator_layout.addWidget(self.position_indicator)

        self.letter_indicator = QLabel(f"Letter ({self.settings.letter_key})")
        self.letter_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.letter_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")
        indicator_layout.addWidget(self.letter_indicator)

        main_layout.addLayout(indicator_layout)
        main_layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        button_layout.addWidget(self.pause_button)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.show_settings)
        button_layout.addWidget(settings_button)

        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.close)
        button_layout.addWidget(quit_button)

        main_layout.addLayout(button_layout)

        # Set dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                padding: 8px 16px;
                border-radius: 4px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
                color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
            }
        """)

    def start_session(self) -> None:
        """Start a new game session."""
        self.engine = GameEngine(self.settings)
        self.engine.reset()
        self.session_active = True
        self.update_display()

        self.level_label.setText(f"Dual {self.settings.n_back_level}-Back")
        self.position_indicator.setText(f"Position ({self.settings.position_key})")
        self.letter_indicator.setText(f"Letter ({self.settings.letter_key})")

        # Clear any previous state
        for cell in self.cells:
            cell.reset_style()

        # Start trial timer
        self.trial_timer.start(int(self.settings.trial_interval * 1000))
        self.next_trial()

    def next_trial(self) -> None:
        """Process next trial in the session."""
        if not self.session_active:
            return

        # Evaluate previous trial if not the first
        if self.engine.current_trial > 0:
            self.engine.evaluate_trial()

        # Check if session is complete
        if self.engine.current_trial >= self.settings.trials_per_session:
            self.end_session()
            return

        # Reset previous cell
        if self.current_position >= 0:
            self.cells[self.current_position].reset_style()

        # Reset indicators
        self.position_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")
        self.letter_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")

        # Generate and display new trial
        position, letter = self.engine.generate_trial()
        self.current_position = position

        # Highlight cell
        self.cells[position].highlight()

        # Speak letter (audio only, not displayed)
        if self.settings.sound_enabled:
            self.audio.speak_async(letter)

        self.update_display()

    def update_display(self) -> None:
        """Update trial counter display."""
        self.trial_label.setText(f"Trial: {self.engine.current_trial} / {self.settings.trials_per_session}")

    def end_session(self) -> None:
        """End the current session and show results."""
        self.session_active = False
        self.trial_timer.stop()

        # Clear display
        if self.current_position >= 0:
            self.cells[self.current_position].reset_style()

        results = self.engine.get_results()

        # Apply adaptive difficulty
        if self.settings.adaptive_enabled:
            overall = results['overall_accuracy']
            if overall >= self.settings.advance_threshold and self.settings.n_back_level < 9:
                self.settings.n_back_level += 1
                QMessageBox.information(self, "Level Up!",
                    f"Great performance! Advancing to {self.settings.n_back_level}-Back")
            elif overall < self.settings.fallback_threshold and self.settings.n_back_level > 1:
                self.settings.n_back_level -= 1
                QMessageBox.information(self, "Level Adjusted",
                    f"Reducing difficulty to {self.settings.n_back_level}-Back")
            self.settings.save(self.config_path)

        # Show results dialog
        dialog = ResultsDialog(results, self.engine.settings.n_back_level, self)
        dialog.new_session_clicked.connect(self.start_session)
        dialog.settings_clicked.connect(self.show_settings)
        dialog.exec()

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        if self.session_active:
            if self.trial_timer.isActive():
                self.trial_timer.stop()
                self.pause_button.setText("Resume")
            else:
                self.trial_timer.start(int(self.settings.trial_interval * 1000))
                self.pause_button.setText("Pause")

    def show_settings(self) -> None:
        """Show settings dialog."""
        was_active = self.session_active
        if was_active:
            self.trial_timer.stop()
            self.session_active = False

        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.get_settings()
            self.settings.save(self.config_path)
            self.audio.enabled = self.settings.sound_enabled
            self.level_label.setText(f"Dual {self.settings.n_back_level}-Back")

        # Start new session after settings change
        self.start_session()

    def clear_feedback(self) -> None:
        """Clear feedback colors."""
        self.position_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")
        self.letter_indicator.setStyleSheet("padding: 10px; background-color: #333; border-radius: 5px;")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key presses for match responses."""
        if not self.session_active:
            return

        key = event.text().upper()

        if key == self.settings.position_key:
            self.engine.record_position_response()
            self.position_indicator.setStyleSheet(
                "padding: 10px; background-color: #4a90d9; border-radius: 5px;")
            self.feedback_timer.start(500)

        elif key == self.settings.letter_key:
            self.engine.record_letter_response()
            self.letter_indicator.setStyleSheet(
                "padding: 10px; background-color: #4a90d9; border-radius: 5px;")
            self.feedback_timer.start(500)

    def closeEvent(self, event) -> None:
        """Save settings on close."""
        self.settings.save(self.config_path)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Set dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(58, 58, 58))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(74, 144, 217))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = MainWindow()
    window.resize(450, 600)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
