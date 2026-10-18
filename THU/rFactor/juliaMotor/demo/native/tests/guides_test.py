# DOCGUIDES-1: the Guides tab lists the guides and shows a page fitted to the width (no PDF needed: a fake rendered guide).
import sys, os, tempfile
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="jr_guides_cfg_")
d = tempfile.mkdtemp(prefix="jr_guides_"); os.environ["JM_GUIDES_DIR"] = d
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor
app = QApplication([])
import guides
os.makedirs(os.path.join(d, "lor_spa"))
for k in (1, 2, 3):
    im = QImage(850, 1100, QImage.Format.Format_RGB32); im.fill(QColor(255, 255, 255)); im.save(os.path.join(d, "lor_spa", f"p-{k}.jpg"))
import guides_tab
ok = True
def check(c, m):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + m)
t = guides_tab.GuidesTab(); t.resize(1200, 800); t.show(); app.processEvents()
items = [t.list.item(i) for i in range(t.list.count())]
spa = [it for it in items if it.text().strip().startswith("Spa") and "(3 p.)" in it.text()]
check(len(spa) == 1, "the rendered guide is listed with its page count")
t.list.setCurrentItem(spa[0]); app.processEvents()
check(t.where.text() == "page 1 of 3", f"opens on page 1 ({t.where.text()})")
t.turn(1); t.turn(5); app.processEvents()
check(t.page == 2, "turns pages and stops at the last")
w0 = t.img.pixmap().width()
check(abs(w0 - t.scroll.viewport().width()) < 60, f"fitted to the width ({w0} px in {t.scroll.viewport().width()})")
t.set_zoom(t.zoom * 1.2); app.processEvents()
check(t.img.pixmap().width() > w0 * 1.15, "zooms in")
print("GUIDES TAB:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
