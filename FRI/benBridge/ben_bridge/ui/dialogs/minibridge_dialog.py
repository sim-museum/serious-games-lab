"""
MiniBridge Mode Dialog - Configure and explain MiniBridge mode.
MiniBridge is a simplified version of Bridge without bidding.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QRadioButton, QCheckBox, QPushButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .dialog_style import apply_dialog_style


class MiniBridgeDialog(QDialog):
    """Dialog for configuring MiniBridge mode."""

    def __init__(self, parent=None, enabled: bool = False):
        super().__init__(parent)
        self.minibridge_enabled = enabled

        self.setWindowTitle("MiniBridge Mode")
        self.setMinimumWidth(450)
        apply_dialog_style(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Explanation
        info_group = QGroupBox("What is MiniBridge?")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "MiniBridge is a simplified version of Bridge designed for beginners.\n\n"
            "Key differences from standard Bridge:\n"
            "• No bidding auction - declarer is determined by HCP\n"
            "• The player with the most HCP becomes declarer\n"
            "• Declarer chooses the trump suit after seeing dummy\n"
            "• All four hands are scored at matchpoints\n\n"
            "This allows players to focus on card play without learning\n"
            "complex bidding systems."
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Enable/disable
        mode_group = QGroupBox("Mode Selection")
        mode_layout = QVBoxLayout()

        self.mode_button_group = QButtonGroup(self)

        self.normal_radio = QRadioButton("Standard Bridge (with bidding)")
        self.mode_button_group.addButton(self.normal_radio, 0)
        mode_layout.addWidget(self.normal_radio)

        self.mini_radio = QRadioButton("MiniBridge (no bidding)")
        self.mode_button_group.addButton(self.mini_radio, 1)
        mode_layout.addWidget(self.mini_radio)

        if self.minibridge_enabled:
            self.mini_radio.setChecked(True)
        else:
            self.normal_radio.setChecked(True)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Options when MiniBridge is enabled
        options_group = QGroupBox("MiniBridge Options")
        options_layout = QVBoxLayout()

        self.show_all_hcp = QCheckBox("Show HCP for all hands")
        self.show_all_hcp.setChecked(True)
        options_layout.addWidget(self.show_all_hcp)

        self.auto_declarer = QCheckBox("Automatically select declarer by HCP")
        self.auto_declarer.setChecked(True)
        options_layout.addWidget(self.auto_declarer)

        self.suggest_contract = QCheckBox("Suggest contract based on HCP")
        self.suggest_contract.setChecked(True)
        options_layout.addWidget(self.suggest_contract)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_ok(self):
        """Handle OK button."""
        self.minibridge_enabled = self.mini_radio.isChecked()
        self.accept()

    def is_minibridge_enabled(self) -> bool:
        """Return whether MiniBridge mode is enabled."""
        return self.minibridge_enabled

    def get_options(self) -> dict:
        """Get MiniBridge options."""
        return {
            'show_all_hcp': self.show_all_hcp.isChecked(),
            'auto_declarer': self.auto_declarer.isChecked(),
            'suggest_contract': self.suggest_contract.isChecked()
        }


class RubberScoringDialog(QDialog):
    """Dialog for configuring Rubber Bridge scoring."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Rubber Bridge Scoring")
        self.setMinimumWidth(450)
        apply_dialog_style(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Explanation
        info_group = QGroupBox("Rubber Bridge Scoring")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "Rubber Bridge is the traditional social form of Bridge.\n\n"
            "Scoring rules:\n"
            "• A game requires 100+ points below the line\n"
            "• Only contract tricks count below the line\n"
            "• Overtricks and bonuses count above the line\n"
            "• First side to win two games wins the rubber\n"
            "• Rubber bonus: 700 (2-0) or 500 (2-1)\n\n"
            "Vulnerability:\n"
            "• Start: Both sides not vulnerable\n"
            "• After winning a game: That side is vulnerable\n"
            "• Vulnerable penalties and bonuses are increased"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Current rubber state (would be updated during play)
        state_group = QGroupBox("Current Rubber")
        state_layout = QVBoxLayout()

        self.state_label = QLabel(
            "N/S: 0 games, 0 points below\n"
            "E/W: 0 games, 0 points below\n\n"
            "Neither side vulnerable"
        )
        self.state_label.setFont(QFont("Arial", 12))
        state_layout.addWidget(self.state_label)

        state_group.setLayout(state_layout)
        layout.addWidget(state_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        self.show_scorecard = QCheckBox("Show rubber scorecard during play")
        self.show_scorecard.setChecked(True)
        options_layout.addWidget(self.show_scorecard)

        self.auto_vulnerability = QCheckBox("Automatic vulnerability tracking")
        self.auto_vulnerability.setChecked(True)
        options_layout.addWidget(self.auto_vulnerability)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        new_rubber_btn = QPushButton("New Rubber")
        new_rubber_btn.clicked.connect(self._on_new_rubber)
        button_layout.addWidget(new_rubber_btn)

        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _on_new_rubber(self):
        """Start a new rubber."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "New Rubber",
            "Start a new rubber? Current scores will be reset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.state_label.setText(
                "N/S: 0 games, 0 points below\n"
                "E/W: 0 games, 0 points below\n\n"
                "Neither side vulnerable"
            )


class MultiplayDialog(QDialog):
    """Dialog for computer multiplay (let computer play all hands)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Computer Multiplay")
        self.setMinimumWidth(400)
        apply_dialog_style(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info_group = QGroupBox("Computer Multiplay")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "Let the computer play all four hands automatically.\n"
            "This is useful for:\n"
            "• Watching how the computer bids and plays\n"
            "• Testing bidding systems\n"
            "• Generating sample hands for analysis"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        self.num_deals_label = QLabel("Number of deals to play:")
        options_layout.addWidget(self.num_deals_label)

        from PyQt6.QtWidgets import QSpinBox
        self.num_deals = QSpinBox()
        self.num_deals.setRange(1, 100)
        self.num_deals.setValue(10)
        options_layout.addWidget(self.num_deals)

        self.pause_check = QCheckBox("Pause between deals")
        self.pause_check.setChecked(True)
        options_layout.addWidget(self.pause_check)

        self.show_analysis = QCheckBox("Show analysis after each deal")
        self.show_analysis.setChecked(True)
        options_layout.addWidget(self.show_analysis)

        self.log_results = QCheckBox("Log results to file")
        self.log_results.setChecked(True)
        options_layout.addWidget(self.log_results)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.accept)
        button_layout.addWidget(start_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def get_settings(self) -> dict:
        """Get multiplay settings."""
        return {
            'num_deals': self.num_deals.value(),
            'pause': self.pause_check.isChecked(),
            'show_analysis': self.show_analysis.isChecked(),
            'log_results': self.log_results.isChecked()
        }
