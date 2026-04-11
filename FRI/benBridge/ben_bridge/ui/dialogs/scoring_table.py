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

        # Results table (click a row to review that hand)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
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
        """Setup table columns — Q-Plus style with open room (left) and closed room (right)."""
        columns = [
            "Contract 1", "N/S 1", "IMP",  # Open room (human)
            "Board",                         # Center
            "Contract 2", "N/S 2", "IMP",  # Closed room (AI)
        ]

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        header = self.table.horizontalHeader()
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        if len(columns) > 0:
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Notes

    def _populate_table(self):
        """Populate table — one row per board, open room left, closed room right."""
        self.table.setRowCount(0)
        self._board_rows = {}  # Map row -> (open_result, closed_result)

        ns_imps_total = 0

        # Group results by board number, separating open and closed room
        boards = {}
        for result in self.scoring_table.results:
            bn = result.board_number
            if bn not in boards:
                boards[bn] = {'open': None, 'closed': None}
            if result.notes and "Closed room" in result.notes:
                boards[bn]['closed'] = result
            elif boards[bn]['open'] is None:
                boards[bn]['open'] = result
            else:
                boards[bn]['closed'] = result

        num_boards = 0
        for bn in sorted(boards.keys()):
            open_r = boards[bn]['open']
            closed_r = boards[bn]['closed']
            if not open_r:
                continue

            num_boards += 1
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._board_rows[row] = (open_r, closed_r)

            # --- Left: Open room (human) ---
            contract_str = self._format_contract(open_r)
            diff = self._format_diff(open_r)
            self.table.setItem(row, 0, QTableWidgetItem(f"{contract_str} {diff}"))
            ns_item = self._colored_item(open_r.ns_score)
            self.table.setItem(row, 1, ns_item)

            imp_val = open_r.imps
            if imp_val is not None:
                ns_imps_total += imp_val
            imp_item = self._colored_item(imp_val, fmt="+d") if imp_val is not None else QTableWidgetItem("")
            self.table.setItem(row, 2, imp_item)

            # --- Center: Board ---
            board_item = QTableWidgetItem(str(bn))
            board_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            board_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(row, 3, board_item)

            # --- Right: Closed room (AI) ---
            if closed_r:
                contract_str2 = self._format_contract(closed_r)
                diff2 = self._format_diff(closed_r)
                self.table.setItem(row, 4, QTableWidgetItem(f"{contract_str2} {diff2}"))
                ns_item2 = self._colored_item(closed_r.ns_score)
                self.table.setItem(row, 5, ns_item2)
                closed_imp = closed_r.imps
                imp_item2 = self._colored_item(closed_imp, fmt="+d") if closed_imp is not None else QTableWidgetItem("")
                self.table.setItem(row, 6, imp_item2)
            else:
                for c in (4, 5, 6):
                    self.table.setItem(row, c, QTableWidgetItem(""))

        # Update summary
        self.boards_label.setText(f"Boards: {num_boards}")
        self.ns_total_label.setText(f"N/S IMPs: {ns_imps_total:+d}")
        self.ew_total_label.setText(f"E/W IMPs: {-ns_imps_total:+d}")

    def _format_contract(self, result):
        if not result or not result.contract:
            return "Pass"
        decl = result.declarer.to_char() if result.declarer else ""
        return f"{decl} {result.contract.to_str()}"

    def _format_diff(self, result):
        if not result or not result.contract:
            return ""
        target = result.contract.target_tricks()
        diff = result.tricks_made - target
        if diff > 0: return f"+{diff}"
        elif diff == 0: return "="
        return str(diff)

    def _colored_item(self, value, fmt="d"):
        if value is None:
            return QTableWidgetItem("")
        text = f"{value:{fmt}}" if fmt == "+d" else str(value)
        item = QTableWidgetItem(text)
        if value > 0:
            item.setForeground(QColor(0, 128, 0))
        elif value < 0:
            item.setForeground(QColor(192, 0, 0))
        return item

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

    def _on_row_double_clicked(self, row, col):
        """Double-click a row to review that hand with full replay.
        Left columns (0-2) → open room, right columns (4-6) → closed room."""
        if row not in self._board_rows:
            return

        open_r, closed_r = self._board_rows[row]
        # Pick open or closed based on which column was clicked
        if col >= 4 and closed_r is not None:
            result = closed_r
        else:
            result = open_r
        if result is None:
            return

        # If we have a BenBoardRun, show the full replay dialog
        if result.board_run is not None and hasattr(result.board_run, 'played') and result.board_run.played:
            try:
                from .replay_view import ReplayViewDialog
                dialog = ReplayViewDialog(result.board_run, self)
                dialog.exec()
                return
            except Exception as e:
                print(f"Replay error: {e}")

        # Fallback: show summary dialog with hand reconstruction from pavlicek_id
        contract_str = result.contract.to_str() if result.contract else "Passed out"
        declarer_str = result.declarer.to_char() if result.declarer else "—"
        target = result.contract.target_tricks() if result.contract else 0
        diff = result.tricks_made - target

        if diff > 0:
            result_text = f"made with {diff} overtrick{'s' if diff > 1 else ''}"
        elif diff == 0:
            result_text = "made exactly"
        else:
            result_text = f"down {abs(diff)}"

        review = QDialog(self)
        review.setWindowTitle(f"Board {result.board_number} — Review")
        review.setMinimumSize(550, 450)
        review.setStyleSheet("QDialog { background-color: #e8e8f0; color: #000; }")
        layout = QVBoxLayout(review)

        # Result summary (yellow highlight like Q-Plus)
        summary = QLabel(
            f"<div style='background-color: #ffffcc; padding: 15px; border: 1px solid #ccc; "
            f"border-radius: 5px; text-align: center;'>"
            f"<p style='font-size: 20px; font-weight: bold;'>Board {result.board_number}</p>"
            f"<p style='font-size: 18px;'>{declarer_str} {contract_str} — {result_text}</p>"
            f"<p style='font-size: 16px;'>N/S: {result.ns_score:+d}    E/W: {result.ew_score:+d}</p>"
            f"</div>"
        )
        summary.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(summary)

        # Reconstruct and show hands from pavlicek_id
        try:
            from ben_backend.pavlicek import parse_deal_number
            from ben_backend.models import Seat, Suit
            hands = parse_deal_number(result.pavlicek_id)
            if hands:
                suit_symbols = {'SPADES': '♠', 'HEARTS': '♥', 'DIAMONDS': '♦', 'CLUBS': '♣'}
                hand_text = "<pre style='font-size: 14px; font-family: monospace;'>\n"
                for seat in [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]:
                    hand = hands.get(seat)
                    if hand:
                        suits = []
                        for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]:
                            cards = sorted([c for c in hand.cards if c.suit == suit],
                                           key=lambda c: c.rank, reverse=True)
                            sym = suit_symbols.get(suit.name, '?')
                            suits.append(f"{sym} {''.join(c.rank.to_char() for c in cards)}")
                        winner = " ★" if seat == result.declarer else ""
                        hand_text += f"  {seat.to_char()}: {' '.join(suits)}{winner}\n"
                hand_text += "</pre>"
                hands_label = QLabel(hand_text)
                hands_label.setTextFormat(Qt.TextFormat.RichText)
                hands_label.setStyleSheet("background-color: #fff; padding: 10px; "
                                          "border: 1px solid #aaa; border-radius: 3px;")
                layout.addWidget(hands_label)
        except Exception:
            pass

        # Details
        details = QLabel(
            f"<p>Deal ID: {result.pavlicek_id}    "
            f"Dealer: {result.dealer.to_char()}    "
            f"Vuln: {result.vulnerability.name}</p>"
        )
        details.setFont(QFont("Arial", 11))
        details.setStyleSheet("padding: 5px;")
        layout.addWidget(details)

        # Notes / Claude commentary
        if result.notes:
            notes_label = QLabel(f"<b>Claude:</b> {result.notes}")
            notes_label.setFont(QFont("Arial", 11))
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("background-color: #f0f8f0; padding: 10px; "
                                      "border: 1px solid #aaa; border-radius: 3px;")
            layout.addWidget(notes_label)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(100, 35)
        close_btn.clicked.connect(review.accept)
        layout.addWidget(close_btn)

        review.exec()
