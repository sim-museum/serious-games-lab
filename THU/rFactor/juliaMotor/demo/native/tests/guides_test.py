# DOCGUIDES-2: the Guides tab shows only the CURRENT track's guide (+ the glossary), follows the track choice, renders the
# guide with its map; the setup guide opens from the Garage tab; no guide names its source or another game.
import sys, os, re, tempfile
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="jr_guides_cfg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import guides, guides_tab
ok = True
def check(c, m):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + m)
cur = ["spa"]
t = guides_tab.GuidesTab(lambda: cur[0]); t.resize(1200, 800); t.show(); app.processEvents()
titles = [t.list.item(i).text() for i in range(t.list.count())]
check(titles == ["Track guide: Spa-Francorchamps", "Racing glossary"], f"Spa: this track's guide + the glossary ({titles})")
check("Eau Rouge" in t.view.toPlainText(), "the Spa guide is shown")
cur[0] = "monza"; t.fill(); app.processEvents()
titles = [t.list.item(i).text() for i in range(t.list.count())]
check(titles[0] == "Track guide: Monza" and not any("Spa" in x for x in titles), f"follows the track ({titles})")
cur[0] = "skidpad"; t.fill(); app.processEvents()
check([t.list.item(i).text() for i in range(t.list.count())] == ["Racing glossary"], "the skidpad has no track guide")
# every guide: present, its images exist, no provenance or other games named
names = ["track_" + k for k in guides.TRACK_NAMES] + ["glossary", "setup"]
bad = re.compile(r"iRacing|\bGPL\b|Grand Prix Legends|Lights Out|LOR\b|Skippy|Skip Barber|Papyrus|rFactor|You Suck", re.I)
for n in names:
    p = guides.doc_path(n); txt = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
    check(len(txt) > 500, f"{n}.md present")
    check(not bad.search(txt), f"{n}.md names no source or other game" + (f" ({bad.search(txt).group(0)})" if bad.search(txt) else ""))
    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", txt)
    missing = [i for i in imgs if not os.path.isfile(os.path.join(guides.TEXT_DIR, i))]
    check(not missing, f"{n}.md: all {len(imgs)} pictures exist" + (f" (missing {missing[:3]})" if missing else ""))
g = open(guides.doc_path("glossary"), encoding="utf-8").read()
check(len(re.findall(r"^### ", g, re.M)) <= 16 and '"' not in g, "glossary: at most 16 entries, no quotations")
import garage_tab
gt = garage_tab.GarageTab(lambda: 0); gt.show(); app.processEvents()
d = gt.show_guide(); app.processEvents()
check("Spring perch offset" in d.findChild(guides_tab.QTextBrowser).toPlainText(), "the Garage tab opens the setup guide")
print("GUIDES TAB:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
