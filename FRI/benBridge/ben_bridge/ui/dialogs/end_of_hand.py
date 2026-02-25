"""
End of Hand Dialog - Modal dialog shown when a hand is complete.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .dialog_style import apply_dialog_style


class EndOfHandDialog(QDialog):
    """Modal dialog shown when a hand is complete.

    Shows the result, score, and optionally IMP swing for teams matches.
    Provides a button to view the other table's result.
    """

    view_other_table = pyqtSignal()  # Emitted when user wants to see other table

    def __init__(self, contract_str: str, declarer: str, result_str: str,
                 score: int, imp_swing: int = None, is_teams_match: bool = False,
                 parent=None):
        """Initialize the end of hand dialog.

        Args:
            contract_str: Contract string (e.g., "4S", "3NT X")
            declarer: Declarer seat character (e.g., "S", "N")
            result_str: Result string (e.g., "Made", "+1", "-2")
            score: Score for declarer's side
            imp_swing: IMP swing (positive = N/S), None if not teams
            is_teams_match: Whether this is a teams match (shows IMP info)
            parent: Parent widget
        """
        super().__init__(parent)

        self.contract_str = contract_str
        self.declarer = declarer
        self.result_str = result_str
        self.score = score
        self.imp_swing = imp_swing
        self.is_teams_match = is_teams_match

        self.setWindowTitle("Playing Finished")
        self.setMinimumWidth(350)
        self.setModal(True)
        apply_dialog_style(self)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("Playing finished:")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Contract and result frame
        result_frame = QFrame()
        result_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #4080c0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        result_layout = QGridLayout(result_frame)
        result_layout.setSpacing(10)

        # Contract
        contract_label = QLabel("Contract:")
        contract_label.setFont(QFont("Arial", 12))
        result_layout.addWidget(contract_label, 0, 0)

        contract_value = QLabel(f"{self.contract_str} by {self.declarer}")
        contract_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        # Color code the contract
        if 'H' in self.contract_str or 'D' in self.contract_str:
            # Could add color for red suits if desired
            pass
        result_layout.addWidget(contract_value, 0, 1)

        # Result
        result_label = QLabel("Result:")
        result_label.setFont(QFont("Arial", 12))
        result_layout.addWidget(result_label, 1, 0)

        result_value = QLabel(self.result_str)
        result_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        # Color code result
        if self.result_str.startswith("-"):
            result_value.setStyleSheet("color: #cc0000;")  # Red for down
        elif self.result_str.startswith("+") or self.result_str == "Made":
            result_value.setStyleSheet("color: #00aa00;")  # Green for made
        result_layout.addWidget(result_value, 1, 1)

        # Score
        score_label = QLabel("Score:")
        score_label.setFont(QFont("Arial", 12))
        result_layout.addWidget(score_label, 2, 0)

        score_text = f"{self.score:+d}" if self.score != 0 else "0"
        score_value = QLabel(score_text)
        score_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        if self.score > 0:
            score_value.setStyleSheet("color: #00aa00;")
        elif self.score < 0:
            score_value.setStyleSheet("color: #cc0000;")
        result_layout.addWidget(score_value, 2, 1)

        # IMP swing (if teams match and available)
        if self.is_teams_match and self.imp_swing is not None:
            imp_label = QLabel("IMP Swing:")
            imp_label.setFont(QFont("Arial", 12))
            result_layout.addWidget(imp_label, 3, 0)

            imp_text = f"{self.imp_swing:+d}" if self.imp_swing != 0 else "0"
            imp_value = QLabel(imp_text)
            imp_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            if self.imp_swing > 0:
                imp_value.setStyleSheet("color: #00aa00;")  # N/S won IMPs
                imp_value.setText(f"{imp_text} (N/S)")
            elif self.imp_swing < 0:
                imp_value.setStyleSheet("color: #cc0000;")  # E/W won IMPs
                imp_value.setText(f"{-self.imp_swing:+d} (E/W)")
            result_layout.addWidget(imp_value, 3, 1)

        layout.addWidget(result_frame)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        if self.is_teams_match:
            # View other table button
            other_table_btn = QPushButton("View other table")
            other_table_btn.setFont(QFont("Arial", 11))
            other_table_btn.clicked.connect(self._on_view_other_table)
            button_layout.addWidget(other_table_btn)

        button_layout.addStretch()

        # OK/Next Deal button
        ok_btn = QPushButton("Next Deal")
        ok_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _on_view_other_table(self):
        """Handle click on 'View other table' button."""
        self.view_other_table.emit()
        self.accept()


class PassedOutDialog(QDialog):
    """Dialog shown when a hand is passed out."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Passed Out")
        self.setMinimumWidth(300)
        self.setModal(True)
        apply_dialog_style(self)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("Passed Out")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Message
        msg = QLabel("All four players passed.\nNo score for this board.")
        msg.setFont(QFont("Arial", 12))
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_btn = QPushButton("Next Deal")
        ok_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
