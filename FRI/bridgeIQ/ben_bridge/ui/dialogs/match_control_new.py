"""
Match Control Dialog - Configure deal source, scoring method, and match settings.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QRadioButton, QSpinBox, QComboBox, QPushButton, QLineEdit,
    QFileDialog, QButtonGroup, QGridLayout, QCheckBox
)
from PyQt6.QtCore import Qt

from ben_backend.config import (
    ConfigManager, MatchConfig, ScoringMethod, ComparisonMode,
    get_config_manager
)


class MatchControlDialog(QDialog):
    """Dialog for configuring match settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.match_config = self.config_manager.config.match

        self.setWindowTitle("Match Control")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Deal Source group
        source_group = QGroupBox("Deal Source")
        source_layout = QVBoxLayout()

        self.source_button_group = QButtonGroup(self)

        # Random deals
        self.random_radio = QRadioButton("Random deals")
        self.source_button_group.addButton(self.random_radio, 0)
        source_layout.addWidget(self.random_radio)

        # Deal number
        deal_num_layout = QHBoxLayout()
        self.deal_num_radio = QRadioButton("Deal number:")
        self.source_button_group.addButton(self.deal_num_radio, 1)
        deal_num_layout.addWidget(self.deal_num_radio)
        self.deal_num_spin = QSpinBox()
        self.deal_num_spin.setRange(1, 999999)
        self.deal_num_spin.setValue(1)
        deal_num_layout.addWidget(self.deal_num_spin)
        deal_num_layout.addStretch()
        source_layout.addLayout(deal_num_layout)

        # Deal file
        file_layout = QHBoxLayout()
        self.file_radio = QRadioButton("Deal file:")
        self.source_button_group.addButton(self.file_radio, 2)
        file_layout.addWidget(self.file_radio)
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        file_layout.addWidget(self.file_path)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        source_layout.addLayout(file_layout)

        # Own deals
        self.own_deals_radio = QRadioButton("Own deals")
        self.source_button_group.addButton(self.own_deals_radio, 3)
        source_layout.addWidget(self.own_deals_radio)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Scoring group
        scoring_group = QGroupBox("Scoring Method")
        scoring_layout = QGridLayout()

        self.scoring_button_group = QButtonGroup(self)

        self.rubber_radio = QRadioButton("Rubber Bridge")
        self.scoring_button_group.addButton(self.rubber_radio, 0)
        scoring_layout.addWidget(self.rubber_radio, 0, 0)

        self.chicago_radio = QRadioButton("Chicago (4-deal)")
        self.scoring_button_group.addButton(self.chicago_radio, 1)
        scoring_layout.addWidget(self.chicago_radio, 0, 1)

        self.pairs_radio = QRadioButton("Pairs (Matchpoints)")
        self.scoring_button_group.addButton(self.pairs_radio, 2)
        scoring_layout.addWidget(self.pairs_radio, 1, 0)

        self.teams_radio = QRadioButton("Teams (IMPs)")
        self.scoring_button_group.addButton(self.teams_radio, 3)
        scoring_layout.addWidget(self.teams_radio, 1, 1)

        scoring_group.setLayout(scoring_layout)
        layout.addWidget(scoring_group)

        # Match settings group
        match_group = QGroupBox("Match Settings")
        match_layout = QGridLayout()

        match_layout.addWidget(QLabel("Number of boards:"), 0, 0)
        self.num_boards_spin = QSpinBox()
        self.num_boards_spin.setRange(1, 999)
        self.num_boards_spin.setValue(8)
        match_layout.addWidget(self.num_boards_spin, 0, 1)

        match_layout.addWidget(QLabel("Starting board:"), 0, 2)
        self.start_board_spin = QSpinBox()
        self.start_board_spin.setRange(1, 999)
        self.start_board_spin.setValue(1)
        match_layout.addWidget(self.start_board_spin, 0, 3)

        match_layout.addWidget(QLabel("Comparison:"), 1, 0)
        self.comparison_combo = QComboBox()
        self.comparison_combo.addItems(["None", "Pair Tournament", "Closed Room"])
        match_layout.addWidget(self.comparison_combo, 1, 1)

        self.use_filter_check = QCheckBox("Use deal filter")
        match_layout.addWidget(self.use_filter_check, 1, 2)

        self.filter_btn = QPushButton("Filter...")
        self.filter_btn.clicked.connect(self._open_filter_dialog)
        match_layout.addWidget(self.filter_btn, 1, 3)

        match_group.setLayout(match_layout)
        layout.addWidget(match_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

    def _load_current_settings(self):
        """Load current configuration into dialog."""
        # Deal source
        source = self.match_config.deal_source
        if source == "Random":
            self.random_radio.setChecked(True)
        elif source.startswith("N "):
            self.deal_num_radio.setChecked(True)
            try:
                num = int(source.split()[2])
                self.deal_num_spin.setValue(num)
            except (IndexError, ValueError):
                pass
        elif source.startswith("File:"):
            self.file_radio.setChecked(True)
            self.file_path.setText(source[5:])
        else:
            self.random_radio.setChecked(True)

        # Scoring method
        method = self.match_config.scoring_method
        if method == ScoringMethod.RUBBER:
            self.rubber_radio.setChecked(True)
        elif method == ScoringMethod.CHICAGO:
            self.chicago_radio.setChecked(True)
        elif method == ScoringMethod.PAIRS:
            self.pairs_radio.setChecked(True)
        else:
            self.teams_radio.setChecked(True)

        # Comparison
        comp = self.match_config.comparison
        if comp == ComparisonMode.NONE:
            self.comparison_combo.setCurrentIndex(0)
        elif comp == ComparisonMode.PAIR_TOURNAMENT:
            self.comparison_combo.setCurrentIndex(1)
        else:
            self.comparison_combo.setCurrentIndex(2)

    def _save_settings(self):
        """Save dialog settings to configuration."""
        # Deal source
        if self.random_radio.isChecked():
            self.match_config.deal_source = "Random"
        elif self.deal_num_radio.isChecked():
            num = self.deal_num_spin.value()
            self.match_config.deal_source = f"N 9 {num}"
            self.match_config.deal_number = float(num)
        elif self.file_radio.isChecked():
            self.match_config.deal_source = f"File:{self.file_path.text()}"
        else:
            self.match_config.deal_source = "OwnDeals"

        # Scoring method
        if self.rubber_radio.isChecked():
            self.match_config.scoring_method = ScoringMethod.RUBBER
        elif self.chicago_radio.isChecked():
            self.match_config.scoring_method = ScoringMethod.CHICAGO
        elif self.pairs_radio.isChecked():
            self.match_config.scoring_method = ScoringMethod.PAIRS
        else:
            self.match_config.scoring_method = ScoringMethod.TEAMS

        # Comparison
        idx = self.comparison_combo.currentIndex()
        if idx == 0:
            self.match_config.comparison = ComparisonMode.NONE
        elif idx == 1:
            self.match_config.comparison = ComparisonMode.PAIR_TOURNAMENT
        else:
            self.match_config.comparison = ComparisonMode.CLOSED_ROOM

        # Save to file
        self.config_manager.save_match_config()

    def _browse_file(self):
        """Open file browser for deal files."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Deal File",
            "",
            "PBN Files (*.pbn);;BDL Files (*.bdl);;All Files (*)"
        )
        if filename:
            self.file_path.setText(filename)
            self.file_radio.setChecked(True)

    def _open_filter_dialog(self):
        """Open deal filter dialog."""
        from .deal_filter import DealFilterDialog
        dialog = DealFilterDialog(self)
        dialog.exec()

    def _on_ok(self):
        """Handle OK button."""
        self._save_settings()
        self.accept()

    def _on_apply(self):
        """Handle Apply button."""
        self._save_settings()

    def get_settings(self) -> dict:
        """Get current dialog settings as dict."""
        return {
            'deal_source': self.match_config.deal_source,
            'scoring_method': self.match_config.scoring_method,
            'comparison': self.match_config.comparison,
            'num_boards': self.num_boards_spin.value(),
            'start_board': self.start_board_spin.value(),
            'use_filter': self.use_filter_check.isChecked(),
        }
