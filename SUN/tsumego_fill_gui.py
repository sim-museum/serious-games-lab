#!/usr/bin/env python3
"""
Tsumego SGF filler — PyQt6 GUI.

Reads a tsumego SGF, locates the problem stones, and rewrites the board so
everything outside a buffered bounding box becomes a single unconditionally
alive wall (one solid colour with two real eyes). The result is an SGF that
forces an engine to focus on the local life-and-death fight: any move
outside the playable pocket is suicide or fills the wall's territory.

Use with KataGo Human SL or any other engine that wanders off into corners
when given a sparse tsumego on a 19x19 board.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Position:
    size: int
    black: set[tuple[int, int]]   # (row, col), 1-indexed
    white: set[tuple[int, int]]
    to_play: str                  # 'B' or 'W'


def parse_sgf(text: str) -> Position:
    sz_match = re.search(r'SZ\[(\d+)\]', text)
    size = int(sz_match.group(1)) if sz_match else 19

    def coord_list(prop: str) -> list[tuple[int, int]]:
        m = re.search(prop + r'((?:\[[a-z]{2}\])+)', text)
        if not m:
            return []
        return [
            (ord(s[1]) - ord('a') + 1, ord(s[0]) - ord('a') + 1)
            for s in re.findall(r'\[([a-z]{2})\]', m.group(1))
        ]

    pl = re.search(r'PL\[([BW])\]', text)
    return Position(
        size=size,
        black=set(coord_list('AB')),
        white=set(coord_list('AW')),
        to_play=pl.group(1) if pl else 'B',
    )


def to_sgf_coord(r: int, c: int) -> str:
    return chr(ord('a') + c - 1) + chr(ord('a') + r - 1)


def render_ascii(pos: Position) -> str:
    n = pos.size
    cols = ''.join(
        chr(ord('A') + c - 1) if c < 9 else chr(ord('A') + c)
        for c in range(1, n + 1)
    )
    out = ['    ' + ' '.join(cols)]
    for r in range(1, n + 1):
        row = [f'{r:2d} ']
        for c in range(1, n + 1):
            if (r, c) in pos.black:
                row.append(' X')
            elif (r, c) in pos.white:
                row.append(' O')
            else:
                row.append(' .')
        out.append(''.join(row))
    return '\n'.join(out)


@dataclass
class FillSpec:
    buffer: int
    wall_color: str               # 'B' or 'W'


class FillError(Exception):
    pass


def compute_filled(pos: Position, spec: FillSpec) -> Position:
    """Return a new Position with the wall + eyes added."""
    n = pos.size
    stones = pos.black | pos.white
    if not stones:
        raise FillError("input has no stones")

    rs = [r for r, _ in stones]
    cs = [c for _, c in stones]
    pr_rmin = max(1, min(rs) - spec.buffer)
    pr_rmax = min(n, max(rs) + spec.buffer)
    pr_cmin = max(1, min(cs) - spec.buffer)
    pr_cmax = min(n, max(cs) + spec.buffer)

    def in_pocket(r: int, c: int) -> bool:
        return pr_rmin <= r <= pr_rmax and pr_cmin <= c <= pr_cmax

    eyes = _pick_eyes(n, in_pocket)
    if eyes is None:
        raise FillError(
            "couldn't place two non-adjacent eyes — try a smaller buffer "
            "or use a problem that isn't pressed against a board edge"
        )

    new_black = set(pos.black)
    new_white = set(pos.white)
    target = new_black if spec.wall_color == 'B' else new_white
    other = new_white if spec.wall_color == 'B' else new_black
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            if (r, c) in stones:
                continue
            if in_pocket(r, c):
                continue
            if (r, c) in eyes:
                continue
            if (r, c) in other:
                # would conflict with an existing enemy stone; skip
                continue
            target.add((r, c))

    return Position(size=n, black=new_black, white=new_white, to_play=pos.to_play)


def _pick_eyes(n: int, in_pocket) -> set[tuple[int, int]] | None:
    """Find two eye points: each must be off-pocket, on-board, and have all
    four orthogonal neighbours also off-pocket and on-board. The two eyes
    must not be 4-adjacent to each other (else they'd share a wall neighbour
    that's both eyes' adjacent — still works, but cleaner this way)."""
    candidates: list[tuple[int, int]] = []
    for r in range(2, n):
        for c in range(2, n):
            if in_pocket(r, c):
                continue
            ok = True
            for nr, nc in [(r-1, c), (r+1, c), (r, c-1), (r, c+1)]:
                if not (1 <= nr <= n and 1 <= nc <= n):
                    ok = False
                    break
                if in_pocket(nr, nc):
                    ok = False
                    break
            if ok:
                candidates.append((r, c))
    # Prefer corners first (max distance from board centre).
    centre = (n + 1) / 2
    candidates.sort(
        key=lambda rc: -((rc[0] - centre) ** 2 + (rc[1] - centre) ** 2)
    )
    for i, e1 in enumerate(candidates):
        for e2 in candidates[i + 1:]:
            if abs(e1[0] - e2[0]) + abs(e1[1] - e2[1]) <= 1:
                continue   # 4-adjacent
            # also reject if they share a neighbour (i.e. would be diagonally
            # adjacent through a single shared neighbour)
            n1 = {(e1[0]+dr, e1[1]+dc) for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]}
            n2 = {(e2[0]+dr, e2[1]+dc) for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]}
            if n1 & n2:
                continue
            return {e1, e2}
    return None


def position_to_sgf(pos: Position) -> str:
    ab = ''.join(f'[{to_sgf_coord(r, c)}]' for r, c in sorted(pos.black))
    aw = ''.join(f'[{to_sgf_coord(r, c)}]' for r, c in sorted(pos.white))
    parts = [f'GM[1]FF[4]SZ[{pos.size}]']
    if ab:
        parts.append(f'AB{ab}')
    if aw:
        parts.append(f'AW{aw}')
    parts.append(f'PL[{pos.to_play}]')
    return f"(;{''.join(parts)})\n"


class TsumegoFillerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tsumego SGF filler")
        self.resize(900, 700)

        self.input_edit = QLineEdit()
        self.output_edit = QLineEdit()
        input_browse = QPushButton("Browse…")
        output_browse = QPushButton("Browse…")
        input_browse.clicked.connect(self._pick_input)
        output_browse.clicked.connect(self._pick_output)

        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(0, 18)
        self.buffer_spin.setValue(3)
        self.buffer_spin.valueChanged.connect(self._refresh_preview)

        self.wall_combo = QComboBox()
        self.wall_combo.addItems(["Black wall", "White wall"])
        self.wall_combo.currentIndexChanged.connect(self._refresh_preview)

        generate_btn = QPushButton("Generate filled SGF")
        generate_btn.clicked.connect(self._generate)

        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.input_view = QPlainTextEdit()
        self.input_view.setReadOnly(True)
        self.input_view.setFont(mono)
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(mono)

        self.status = QStatusBar()
        self.status.showMessage("Pick an input SGF to begin.")

        # Layout
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Input SGF:"))
        row1.addWidget(self.input_edit, 1)
        row1.addWidget(input_browse)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Output SGF:"))
        row2.addWidget(self.output_edit, 1)
        row2.addWidget(output_browse)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Buffer cells:"))
        row3.addWidget(self.buffer_spin)
        row3.addSpacing(20)
        row3.addWidget(QLabel("Wall colour:"))
        row3.addWidget(self.wall_combo)
        row3.addStretch(1)
        row3.addWidget(generate_btn)

        previews = QHBoxLayout()
        in_col = QVBoxLayout()
        in_col.addWidget(QLabel("Input"))
        in_col.addWidget(self.input_view, 1)
        out_col = QVBoxLayout()
        out_col.addWidget(QLabel("Output preview"))
        out_col.addWidget(self.output_view, 1)
        previews.addLayout(in_col, 1)
        previews.addLayout(out_col, 1)

        main = QVBoxLayout(self)
        main.addLayout(row1)
        main.addLayout(row2)
        main.addLayout(row3)
        main.addLayout(previews, 1)
        main.addWidget(self.status)

        self.input_edit.textChanged.connect(self._on_input_changed)

        self._current_input: Position | None = None

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose input SGF", os.path.expanduser("~"),
            "SGF files (*.sgf);;All files (*)",
        )
        if path:
            self.input_edit.setText(path)

    def _pick_output(self) -> None:
        start = self.output_edit.text() or self._suggested_output()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save filled SGF as", start,
            "SGF files (*.sgf);;All files (*)",
        )
        if path:
            if not path.lower().endswith('.sgf'):
                path += '.sgf'
            self.output_edit.setText(path)

    def _suggested_output(self) -> str:
        ip = self.input_edit.text()
        if not ip:
            return os.path.expanduser("~")
        d, base = os.path.split(ip)
        stem, _ext = os.path.splitext(base)
        return os.path.join(d, f"{stem}_filled.sgf")

    def _on_input_changed(self) -> None:
        path = self.input_edit.text()
        if not path or not os.path.isfile(path):
            self._current_input = None
            self.input_view.setPlainText("")
            self.output_view.setPlainText("")
            self.status.showMessage("Pick an input SGF to begin.")
            return
        try:
            with open(path) as f:
                text = f.read()
            pos = parse_sgf(text)
        except Exception as exc:
            self._current_input = None
            self.input_view.setPlainText("")
            self.output_view.setPlainText("")
            self.status.showMessage(f"Failed to read SGF: {exc}")
            return
        self._current_input = pos
        self.input_view.setPlainText(render_ascii(pos))
        if not self.output_edit.text():
            self.output_edit.setText(self._suggested_output())
        self._refresh_preview()

    def _current_spec(self) -> FillSpec:
        return FillSpec(
            buffer=self.buffer_spin.value(),
            wall_color='B' if self.wall_combo.currentIndex() == 0 else 'W',
        )

    def _refresh_preview(self) -> None:
        if self._current_input is None:
            return
        try:
            filled = compute_filled(self._current_input, self._current_spec())
        except FillError as exc:
            self.output_view.setPlainText("")
            self.status.showMessage(f"Cannot fill: {exc}")
            return
        self.output_view.setPlainText(render_ascii(filled))
        self.status.showMessage(
            f"Preview ready — {len(filled.black)} black, {len(filled.white)} "
            f"white. Click Generate to write the file."
        )

    def _generate(self) -> None:
        if self._current_input is None:
            QMessageBox.warning(self, "No input", "Pick an input SGF first.")
            return
        out_path = self.output_edit.text().strip()
        if not out_path:
            QMessageBox.warning(self, "No output path", "Choose an output path.")
            return
        try:
            filled = compute_filled(self._current_input, self._current_spec())
        except FillError as exc:
            QMessageBox.critical(self, "Fill failed", str(exc))
            return
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w') as f:
                f.write(position_to_sgf(filled))
        except OSError as exc:
            QMessageBox.critical(self, "Write failed", str(exc))
            return
        self.status.showMessage(f"Wrote {out_path}")


def main() -> int:
    app = QApplication(sys.argv)
    win = TsumegoFillerWindow()
    win.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
