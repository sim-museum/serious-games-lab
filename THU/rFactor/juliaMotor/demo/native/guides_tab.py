"""DOCGUIDES-1: the launcher's Guides tab -- each guide's own pages, fitted to the width, with zoom.

The list on the left groups the guides (track guides by Lights Out Racing and by fs, setup guides, racecraft); the page
on the right fills the reader's width (so the text is as large as the window allows), and zooms with the buttons, Ctrl+
wheel or +/-; PageUp/PageDown or the arrows turn pages."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSplitter,
                             QVBoxLayout, QWidget)

import guides


class GuidesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slug = None
        self.pages = []
        self.page = 0
        self.zoom = 1.0
        lay = QHBoxLayout(self)
        split = QSplitter()
        lay.addWidget(split)
        self.list = QListWidget()
        self.list.setMinimumWidth(220)
        self.list.currentItemChanged.connect(self._pick)
        split.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        bar = QHBoxLayout()
        self.prev_b = QPushButton("◀ Page")
        self.next_b = QPushButton("Page ▶")
        self.zoom_out = QPushButton("−")
        self.zoom_in = QPushButton("+")
        self.fit_b = QPushButton("Fit width")
        self.where = QLabel("")
        for b, f in ((self.prev_b, lambda: self.turn(-1)), (self.next_b, lambda: self.turn(1)),
                     (self.zoom_out, lambda: self.set_zoom(self.zoom / 1.2)), (self.zoom_in, lambda: self.set_zoom(self.zoom * 1.2)),
                     (self.fit_b, lambda: self.set_zoom(1.0))):
            b.clicked.connect(f)
        for w in (self.prev_b, self.next_b, self.where):
            bar.addWidget(w)
        bar.addStretch(1)
        for w in (self.zoom_out, self.zoom_in, self.fit_b):
            bar.addWidget(w)
        rl.addLayout(bar)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.img = QLabel("Pick a guide on the left.")
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.img)
        self.scroll.setWidgetResizable(False)
        rl.addWidget(self.scroll, 1)
        split.addWidget(right)
        split.setStretchFactor(1, 4)
        self.fill()

    def fill(self):
        self.list.clear()
        group = None
        for g, t, slug, n, src in guides.available():
            if g != group:
                hdr = QListWidgetItem(g)
                hdr.setFlags(Qt.ItemFlag.NoItemFlags)
                f = hdr.font(); f.setBold(True); hdr.setFont(f)
                self.list.addItem(hdr)
                group = g
            it = QListWidgetItem("   " + t + (f"  ({n} p.)" if n else ""))
            it.setData(Qt.ItemDataRole.UserRole, (slug, src))
            self.list.addItem(it)
        if self.list.count() == 0:
            self.img.setText("No guides here: they come from ~/sgl/THU/DOC (python3 guides.py --export docs/guides).")

    def _pick(self, cur, _prev=None):
        if cur is None or cur.data(Qt.ItemDataRole.UserRole) is None:
            return
        slug, src = cur.data(Qt.ItemDataRole.UserRole)
        ps = guides.pages(slug) or guides.render(slug, src)        # first use in a checkout renders the pages
        self.slug, self.pages, self.page = slug, ps, 0
        self.show_page()

    def turn(self, d):
        if self.pages:
            self.page = max(0, min(len(self.pages) - 1, self.page + d))
            self.show_page()
            self.scroll.verticalScrollBar().setValue(0)

    def set_zoom(self, z):
        self.zoom = max(0.4, min(4.0, z))
        self.show_page()

    def show_page(self):
        if not self.pages:
            self.img.setText("This guide could not be rendered (missing PDF or pdftoppm).")
            self.img.adjustSize()
            return
        pm = QPixmap(self.pages[self.page])
        sb = self.scroll.verticalScrollBar().sizeHint().width()
        w = max(200, int((self.scroll.viewport().width() - sb - 4) * self.zoom))   # fit: no sideways scroll
        self.img.setPixmap(pm.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation))
        self.img.adjustSize()
        self.where.setText(f"page {self.page + 1} of {len(self.pages)}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.pages and self.show_page()

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_PageDown, Qt.Key.Key_Right):
            self.turn(1)
        elif k in (Qt.Key.Key_PageUp, Qt.Key.Key_Left):
            self.turn(-1)
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.set_zoom(self.zoom * 1.2)
        elif k == Qt.Key.Key_Minus:
            self.set_zoom(self.zoom / 1.2)
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1))
        else:
            super().wheelEvent(e)
