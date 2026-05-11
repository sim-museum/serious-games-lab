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
    """Q-Plus .score-rubber scorecard view + edit dialog.

    Shows the rubber as the classic 2-column above-line / below-line
    table with games_won and vulnerability indicators. Buttons map
    1-to-1 to the Q-Plus spec (BRIDGE.HLQ 2561-2573):

      • Edit / Delete last  — pop the most recent entry.
      • Clear               — reset the rubber.
      • Save                — write to JSON so File → Restore
                              Score Table can load it later.
      • Load                — read a previously saved rubber back.
      • Close               — dismiss.

    The dialog is non-modal; callers (MainWindow._on_view_scores or
    _show_result in rubber mode) keep a reference and call
    .refresh() after each hand is scored into the underlying
    RubberScore.
    """

    def __init__(self, rubber: 'RubberScore' = None, parent=None):
        super().__init__(parent)
        from ben_backend.scoring import RubberScore
        self.rubber: 'RubberScore' = rubber or RubberScore()
        self.setWindowTitle("Rubber bridge scorecard")
        self.setMinimumWidth(640)
        self.setMinimumHeight(440)
        apply_dialog_style(self)
        self._setup_ui()
        self.refresh()

    def set_rubber(self, rubber: 'RubberScore'):
        self.rubber = rubber
        self.refresh()

    def _setup_ui(self):
        from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem,
                                      QHeaderView)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header — games won + vulnerability indicators.
        self.header_label = QLabel("")
        self.header_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        layout.addWidget(self.header_label)

        # Scorecard table: 4 columns (NS above, NS below, EW below,
        # EW above) so above-the-line points sit AT the outside and
        # below-the-line points sit in the middle two columns —
        # mirrors how the classic paper scorecard is laid out.
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["NS above", "NS below", "EW below", "EW above"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, stretch=1)

        # Totals + a notes line under the table.
        self.totals_label = QLabel("")
        self.totals_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(self.totals_label)

        # Button row.
        btn_row = QHBoxLayout()

        del_btn = QPushButton("Delete last entry")
        del_btn.setToolTip(
            "Pop the most recent rubber row. Mirrors the Q-Plus "
            "Edit button — use to back out a wrong score."
        )
        del_btn.clicked.connect(self._on_delete_last)
        btn_row.addWidget(del_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Wipe the rubber and start fresh.")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)

        save_btn = QPushButton("Save…")
        save_btn.setToolTip(
            "Save the current rubber to JSON so it can be resumed "
            "later via File → Restore Score Table."
        )
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        load_btn = QPushButton("Load…")
        load_btn.setToolTip("Replace the displayed rubber with one "
                            "saved earlier.")
        load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(load_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def refresh(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtGui import QColor
        r = self.rubber

        ns_vul = "VUL" if r.vulnerable('NS') else "—"
        ew_vul = "VUL" if r.vulnerable('EW') else "—"
        header = (f"Games — NS: <b>{r.games_won_ns}</b> ({ns_vul}) "
                  f"&nbsp;|&nbsp; EW: <b>{r.games_won_ew}</b> "
                  f"({ew_vul})")
        if r.rubber_complete:
            winner = "NS" if r.games_won_ns >= 2 else "EW"
            header += f"<br><span style='color:#0a0;'>"\
                      f"Rubber complete — winner: {winner}</span>"
        self.header_label.setText(header)

        self.table.setRowCount(len(r.entries))
        divider_set = set(r.game_dividers)
        for i, e in enumerate(r.entries):
            txt = f"{e.points}  {e.label}".strip()
            item = QTableWidgetItem(txt)
            item.setForeground(QColor(20, 20, 20))
            # Place into the correct column.
            if e.side == 'NS' and e.line == 'above':
                col = 0
            elif e.side == 'NS' and e.line == 'below':
                col = 1
            elif e.side == 'EW' and e.line == 'below':
                col = 2
            else:
                col = 3
            # Subtle background for a game-completing row.
            if i in divider_set:
                item.setBackground(QColor(220, 240, 220))
            self.table.setItem(i, col, item)
            # Blank cells for the other 3 columns so highlighting is
            # consistent.
            for other in range(4):
                if other == col:
                    continue
                cell = QTableWidgetItem("")
                if i in divider_set:
                    cell.setBackground(QColor(220, 240, 220))
                self.table.setItem(i, other, cell)

        self.totals_label.setText(
            f"Totals — NS: {r.total('NS')} "
            f"(above {r.above_total('NS')}, "
            f"below {r.below_total('NS')})  |  "
            f"EW: {r.total('EW')} "
            f"(above {r.above_total('EW')}, "
            f"below {r.below_total('EW')})"
        )

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def _on_delete_last(self):
        if not self.rubber.entries:
            return
        from PyQt6.QtWidgets import QMessageBox
        last = self.rubber.entries[-1]
        reply = QMessageBox.question(
            self,
            "Delete last entry",
            f"Remove the last rubber row?\n\n"
            f"{last.side} {last.line}: {last.points} — {last.label}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rubber.delete_last_entry()
            self.refresh()

    def _on_clear(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Clear rubber",
            "Wipe every row from this rubber and start fresh?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.rubber.clear()
            self.refresh()

    def _on_save(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        default_dir = (Path(__file__).parent.parent.parent
                       / "DATA" / "RUBBERS")
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            default_dir = Path.home()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save rubber",
            str(default_dir / "rubber.json"),
            "Rubber scorecard (*.json);;All files (*)",
        )
        if not filename:
            return
        try:
            self.rubber.save(filename)
        except Exception as ex:
            QMessageBox.warning(self, "Save failed", str(ex))
            return
        QMessageBox.information(
            self, "Saved",
            f"Rubber saved to:\n{filename}\n\n"
            "Use File → Restore Score Table to load it later.")

    def _on_load(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        from ben_backend.scoring import RubberScore
        default_dir = (Path(__file__).parent.parent.parent
                       / "DATA" / "RUBBERS")
        if not default_dir.exists():
            default_dir = Path.home()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load rubber",
            str(default_dir),
            "Rubber scorecard (*.json);;All files (*)",
        )
        if not filename:
            return
        try:
            loaded = RubberScore.load(filename)
        except Exception as ex:
            QMessageBox.warning(self, "Load failed", str(ex))
            return
        self.set_rubber(loaded)


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
