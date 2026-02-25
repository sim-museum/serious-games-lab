"""
Scoring Table Dialog - Display and manage match/session scores.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from ben_backend.scoring import ScoringTable, ScoringType, BoardResult
from typing import Optional

from .dialog_style import apply_dialog_style


class ScoringTableDialog(QDialog):
    """Dialog for viewing and managing scoring table."""

    def __init__(self, scoring_table: Optional[ScoringTable] = None, parent=None):
        super().__init__(parent)
        self.scoring_table = scoring_table or ScoringTable()

        self.setWindowTitle("Scoring Table")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        apply_dialog_style(self)
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Summary group
        summary_group = QGroupBox("Session Summary")
        summary_layout = QGridLayout()

        self.scoring_type_label = QLabel(f"Scoring: {self.scoring_table.scoring_type.value}")
        summary_layout.addWidget(self.scoring_type_label, 0, 0)

        self.boards_label = QLabel(f"Boards: {len(self.scoring_table.results)}")
        summary_layout.addWidget(self.boards_label, 0, 1)

        self.ns_total_label = QLabel("N/S: 0")
        summary_layout.addWidget(self.ns_total_label, 0, 2)

        self.ew_total_label = QLabel("E/W: 0")
        summary_layout.addWidget(self.ew_total_label, 0, 3)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Results table
        self.table = QTableWidget()
        self._setup_table_columns()
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("Save...")
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        load_btn = QPushButton("Load...")
        load_btn.clicked.connect(self._on_load)
        button_layout.addWidget(load_btn)

        export_html_btn = QPushButton("Export HTML...")
        export_html_btn.clicked.connect(self._on_export_html)
        button_layout.addWidget(export_html_btn)

        print_btn = QPushButton("Print...")
        print_btn.clicked.connect(self._on_print)
        button_layout.addWidget(print_btn)

        button_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear)
        button_layout.addWidget(clear_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _setup_table_columns(self):
        """Setup table columns based on scoring type."""
        columns = ["Board", "Deal ID", "Contract", "By", "Result", "N/S", "E/W"]

        if self.scoring_table.scoring_type == ScoringType.TEAMS:
            columns.append("IMPs")
        elif self.scoring_table.scoring_type == ScoringType.PAIRS:
            columns.append("MP")

        columns.append("Notes")

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Board
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Deal ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Contract
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # By
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Result
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # N/S
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # E/W
        if len(columns) > 8:
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # IMPs/MP
            header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)  # Notes
        else:
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Notes

    def _populate_table(self):
        """Populate table with results."""
        self.table.setRowCount(0)

        ns_total = 0
        ew_total = 0
        ns_imps = 0
        ns_mp = 0.0

        for result in self.scoring_table.results:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Board number
            self.table.setItem(row, 0, QTableWidgetItem(str(result.board_number)))

            # Deal ID (truncated Pavlicek)
            deal_id = result.pavlicek_id[:12] if result.pavlicek_id else ""
            self.table.setItem(row, 1, QTableWidgetItem(deal_id))

            # Contract
            contract_str = result.contract.to_str() if result.contract else "Passed"
            self.table.setItem(row, 2, QTableWidgetItem(contract_str))

            # Declarer
            declarer_str = result.declarer.to_char() if result.declarer else ""
            self.table.setItem(row, 3, QTableWidgetItem(declarer_str))

            # Result
            if result.contract:
                target = result.contract.target_tricks()
                diff = result.tricks_made - target
                if diff >= 0:
                    result_str = f"{result.tricks_made} (={diff:+d})" if diff > 0 else f"{result.tricks_made} (=)"
                else:
                    result_str = f"{result.tricks_made} ({diff})"
            else:
                result_str = ""
            self.table.setItem(row, 4, QTableWidgetItem(result_str))

            # N/S score
            ns_item = QTableWidgetItem(str(result.ns_score) if result.ns_score else "")
            if result.ns_score > 0:
                ns_item.setForeground(QColor(0, 128, 0))  # Green for positive
            elif result.ns_score < 0:
                ns_item.setForeground(QColor(192, 0, 0))  # Red for negative
            self.table.setItem(row, 5, ns_item)
            ns_total += result.ns_score

            # E/W score
            ew_item = QTableWidgetItem(str(result.ew_score) if result.ew_score else "")
            if result.ew_score > 0:
                ew_item.setForeground(QColor(0, 128, 0))
            elif result.ew_score < 0:
                ew_item.setForeground(QColor(192, 0, 0))
            self.table.setItem(row, 6, ew_item)
            ew_total += result.ew_score

            col = 7
            # IMPs or Matchpoints
            if self.scoring_table.scoring_type == ScoringType.TEAMS:
                imps_str = f"{result.imps:+d}" if result.imps is not None else ""
                imps_item = QTableWidgetItem(imps_str)
                if result.imps is not None:
                    if result.imps > 0:
                        imps_item.setForeground(QColor(0, 128, 0))
                    elif result.imps < 0:
                        imps_item.setForeground(QColor(192, 0, 0))
                    ns_imps += result.imps
                self.table.setItem(row, col, imps_item)
                col += 1
            elif self.scoring_table.scoring_type == ScoringType.PAIRS:
                mp_str = f"{result.matchpoints:.1f}" if result.matchpoints is not None else ""
                self.table.setItem(row, col, QTableWidgetItem(mp_str))
                if result.matchpoints is not None:
                    ns_mp += result.matchpoints
                col += 1

            # Notes
            self.table.setItem(row, col, QTableWidgetItem(result.notes))

        # Update summary labels
        self.boards_label.setText(f"Boards: {len(self.scoring_table.results)}")

        if self.scoring_table.scoring_type == ScoringType.TEAMS:
            self.ns_total_label.setText(f"N/S IMPs: {ns_imps:+d}")
            self.ew_total_label.setText(f"E/W IMPs: {-ns_imps:+d}")
        elif self.scoring_table.scoring_type == ScoringType.PAIRS:
            self.ns_total_label.setText(f"N/S MP: {ns_mp:.1f}")
            self.ew_total_label.setText("")
        else:
            self.ns_total_label.setText(f"N/S: {ns_total}")
            self.ew_total_label.setText(f"E/W: {ew_total}")

    def add_result(self, result: BoardResult):
        """Add a new result to the table."""
        self.scoring_table.add_result(result)
        self._populate_table()

    def _on_save(self):
        """Save scoring table to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Scoring Table", "",
            "BEN Score Sheet (*.qss);;All Files (*)"
        )
        if filename:
            if not filename.endswith('.qss'):
                filename += '.qss'
            try:
                self.scoring_table.save(filename)
                QMessageBox.information(self, "Saved", f"Scoring table saved to {filename}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not save: {e}")

    def _on_load(self):
        """Load scoring table from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Scoring Table", "",
            "BEN Score Sheet (*.qss);;All Files (*)"
        )
        if filename:
            try:
                self.scoring_table = ScoringTable.load(filename)
                self._setup_table_columns()
                self._populate_table()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load: {e}")

    def _on_export_html(self):
        """Export scoring table to HTML."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export to HTML", "",
            "HTML Files (*.html);;All Files (*)"
        )
        if filename:
            if not filename.endswith('.html'):
                filename += '.html'
            try:
                self._export_html(filename)
                QMessageBox.information(self, "Exported", f"Exported to {filename}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not export: {e}")

    def _export_html(self, filename: str):
        """Generate HTML export."""
        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>BEN Bridge Scoring Table</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }",
            "th { background-color: #4CAF50; color: white; }",
            "tr:nth-child(even) { background-color: #f2f2f2; }",
            ".positive { color: green; }",
            ".negative { color: red; }",
            "</style>",
            "</head><body>",
            f"<h1>BEN Bridge Scoring Table</h1>",
            f"<p>Scoring: {self.scoring_table.scoring_type.value}</p>",
            f"<p>Boards: {len(self.scoring_table.results)}</p>",
            "<table>",
            "<tr><th>Board</th><th>Contract</th><th>By</th><th>Result</th><th>N/S</th><th>E/W</th>",
        ]

        if self.scoring_table.scoring_type == ScoringType.TEAMS:
            html.append("<th>IMPs</th>")
        elif self.scoring_table.scoring_type == ScoringType.PAIRS:
            html.append("<th>MP</th>")

        html.append("</tr>")

        for r in self.scoring_table.results:
            contract = r.contract.to_str() if r.contract else "Passed"
            declarer = r.declarer.to_char() if r.declarer else ""
            result = str(r.tricks_made) if r.contract else ""

            ns_class = "positive" if r.ns_score > 0 else ("negative" if r.ns_score < 0 else "")
            ew_class = "positive" if r.ew_score > 0 else ("negative" if r.ew_score < 0 else "")

            html.append(f"<tr>")
            html.append(f"<td>{r.board_number}</td>")
            html.append(f"<td>{contract}</td>")
            html.append(f"<td>{declarer}</td>")
            html.append(f"<td>{result}</td>")
            html.append(f"<td class='{ns_class}'>{r.ns_score}</td>")
            html.append(f"<td class='{ew_class}'>{r.ew_score}</td>")

            if self.scoring_table.scoring_type == ScoringType.TEAMS and r.imps is not None:
                imp_class = "positive" if r.imps > 0 else ("negative" if r.imps < 0 else "")
                html.append(f"<td class='{imp_class}'>{r.imps:+d}</td>")
            elif self.scoring_table.scoring_type == ScoringType.PAIRS and r.matchpoints is not None:
                html.append(f"<td>{r.matchpoints:.1f}</td>")

            html.append("</tr>")

        html.extend([
            "</table>",
            f"<p><em>Generated by BEN Bridge</em></p>",
            "</body></html>"
        ])

        with open(filename, 'w') as f:
            f.write('\n'.join(html))

    def _on_print(self):
        """Print scoring table."""
        QMessageBox.information(self, "Print", "Print functionality not yet implemented.")

    def _on_clear(self):
        """Clear all results."""
        reply = QMessageBox.question(
            self, "Clear Results",
            "Are you sure you want to clear all results?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.scoring_table.results.clear()
            self._populate_table()
