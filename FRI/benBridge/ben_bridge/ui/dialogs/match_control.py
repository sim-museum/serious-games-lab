"""
Match Control Dialog
Configure deal source, scoring method, and comparison settings.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
    QLabel, QComboBox, QSpinBox, QLineEdit, QPushButton,
    QRadioButton, QButtonGroup, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt

from .dialog_style import apply_dialog_style


class MatchControlDialog(QDialog):
    """
    Dialog for match/tournament control settings.
    Similar to BEN Bridge Match Control.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Match Control")
        self.setMinimumWidth(450)
        apply_dialog_style(self)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Deal Source
        source_group = QGroupBox("Deal Source")
        source_layout = QVBoxLayout(source_group)

        self.source_buttons = QButtonGroup(self)

        # Random deals
        random_row = QHBoxLayout()
        self.random_radio = QRadioButton("Random deals, starting from number:")
        self.random_radio.setChecked(True)
        self.source_buttons.addButton(self.random_radio, 0)
        random_row.addWidget(self.random_radio)

        self.start_number = QSpinBox()
        self.start_number.setRange(1, 999999)
        self.start_number.setValue(1)
        random_row.addWidget(self.start_number)
        random_row.addStretch()
        source_layout.addLayout(random_row)

        # From file
        file_row = QHBoxLayout()
        self.file_radio = QRadioButton("From deal file:")
        self.source_buttons.addButton(self.file_radio, 1)
        file_row.addWidget(self.file_radio)

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        file_row.addWidget(self.file_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(browse_btn)
        source_layout.addLayout(file_row)

        layout.addWidget(source_group)

        # Scoring Method
        scoring_group = QGroupBox("Scoring Method")
        scoring_layout = QVBoxLayout(scoring_group)

        self.scoring_buttons = QButtonGroup(self)

        self.rubber_radio = QRadioButton("Rubber Bridge")
        self.scoring_buttons.addButton(self.rubber_radio, 0)
        scoring_layout.addWidget(self.rubber_radio)

        self.imp_radio = QRadioButton("IMP (Team Match)")
        self.imp_radio.setChecked(True)
        self.scoring_buttons.addButton(self.imp_radio, 1)
        scoring_layout.addWidget(self.imp_radio)

        self.mp_radio = QRadioButton("Matchpoints (Pairs)")
        self.scoring_buttons.addButton(self.mp_radio, 2)
        scoring_layout.addWidget(self.mp_radio)

        layout.addWidget(scoring_group)

        # Comparison
        comparison_group = QGroupBox("Comparison")
        comparison_layout = QVBoxLayout(comparison_group)

        self.comparison_buttons = QButtonGroup(self)

        self.closed_room_radio = QRadioButton("Against Closed Room (BEN vs BEN)")
        self.closed_room_radio.setChecked(True)
        self.comparison_buttons.addButton(self.closed_room_radio, 0)
        comparison_layout.addWidget(self.closed_room_radio)

        self.file_results_radio = QRadioButton("Against results from file")
        self.comparison_buttons.addButton(self.file_results_radio, 1)
        comparison_layout.addWidget(self.file_results_radio)

        self.no_comparison_radio = QRadioButton("No comparison")
        self.comparison_buttons.addButton(self.no_comparison_radio, 2)
        comparison_layout.addWidget(self.no_comparison_radio)

        layout.addWidget(comparison_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.auto_advance = QCheckBox("Auto-advance to next deal")
        self.auto_advance.setChecked(True)
        options_layout.addWidget(self.auto_advance)

        boards_row = QHBoxLayout()
        boards_row.addWidget(QLabel("Number of boards:"))
        self.num_boards = QSpinBox()
        self.num_boards.setRange(1, 1000)
        self.num_boards.setValue(16)
        boards_row.addWidget(self.num_boards)
        boards_row.addStretch()
        options_layout.addLayout(boards_row)

        layout.addWidget(options_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        start_btn = QPushButton("Start Match")
        start_btn.clicked.connect(self.accept)
        button_layout.addWidget(start_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _on_browse(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Deal File", "",
            "PBN Files (*.pbn);;BEN Files (*.ben);;All Files (*)"
        )
        if filename:
            self.file_path.setText(filename)
            self.file_radio.setChecked(True)

    def get_settings(self) -> dict:
        """Return the configured settings"""
        return {
            'source': 'random' if self.random_radio.isChecked() else 'file',
            'start_number': self.start_number.value(),
            'file_path': self.file_path.text(),
            'scoring': ['rubber', 'imp', 'mp'][self.scoring_buttons.checkedId()],
            'comparison': ['closed_room', 'file', 'none'][self.comparison_buttons.checkedId()],
            'auto_advance': self.auto_advance.isChecked(),
            'num_boards': self.num_boards.value()
        }
