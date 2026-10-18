"""DOCGUIDES-1: the GPL / iRacing guides in julia's documentation, readable.

PO 2026-10-17: "add to julia documentation, including graphics, in a readable way that is not smushed into a block of
tiny-font text" -- the five fs_* and five LOR track guides, Skippy's and iRacing's setup guides, the LSD paper and the
Racecraft A-Z.

Each guide is shown as its own pages (layout, maps and diagrams kept), fitted to the width of the reader, with zoom.
The pages are rendered once from the PDFs (`python3 guides.py --export DIR`, pdftoppm): the AppImage build does it into
the image (AppImage rule -- nothing read from ~/sgl at run time, JM_GUIDES_DIR points at the copy); a checkout renders
into docs/guides (gitignored) on first use.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.expanduser("~/sgl/THU/DOC")

# (group, title, slug, source pdf)
GUIDES = [
    ("Track guides (Lights Out Racing)", "Monza", "lor_monza", f"{DOC}/trackGuidesAndSetups_LOR/GPL_trackguide_Monza_by_LOR.pdf"),
    ("Track guides (Lights Out Racing)", "Nürburgring", "lor_ring", f"{DOC}/trackGuidesAndSetups_LOR/GPL_trackguide_Nuerburgring_by_LOR.pdf"),
    ("Track guides (Lights Out Racing)", "Spa", "lor_spa", f"{DOC}/trackGuidesAndSetups_LOR/GPL_trackguide_Spa_by_LOR.pdf"),
    ("Track guides (Lights Out Racing)", "Watkins Glen", "lor_wg", f"{DOC}/trackGuidesAndSetups_LOR/GPL_trackguide_WatkinsGlen_by_LOR.pdf"),
    ("Track guides (Lights Out Racing)", "Zandvoort", "lor_zand", f"{DOC}/trackGuidesAndSetups_LOR/GPL_trackguide_Zandvoort_by_LOR.pdf"),
    ("Track guides (fs)", "Monza", "fs_monza", f"{DOC}/trackGuides_fs/fs_monzaTrackGuide.pdf"),
    ("Track guides (fs)", "Nürburgring", "fs_ring", f"{DOC}/trackGuides_fs/fs_nurburgringTrackGuide.pdf"),
    ("Track guides (fs)", "Spa", "fs_spa", f"{DOC}/trackGuides_fs/fs_spa67TrackGuide.pdf"),
    ("Track guides (fs)", "Watkins Glen", "fs_wg", f"{DOC}/trackGuides_fs/fs_watkinsGlenTrackGuide.pdf"),
    ("Track guides (fs)", "Zandvoort", "fs_zand", f"{DOC}/trackGuides_fs/fs_zandvortTrackGuide.pdf"),
    ("Setup", "Skippy's GPL tuning guide (2011)", "skippy", f"{DOC}/setupGuides/Skippy_Tuning_Guide_2011_S3_080311.pdf"),
    ("Setup", "iRacing setup guide", "iracing_setup", f"{DOC}/setupGuides/iRacing_Setup_Guide.pdf"),
    ("Setup", "Limited-slip differentials", "lsd", f"{DOC}/LSDiffs.pdf"),
    ("Racecraft", "Racecraft A-Z for sim racers", "racecraft", os.path.expanduser("~/Downloads/Racecraft_A-Z_for_Sim_Racers.pdf")),
]
DPI = 120


def guides_dir():
    return os.environ.get("JM_GUIDES_DIR") or os.path.join(HERE, "docs", "guides")


def pages(slug, base=None):
    """Sorted page image paths for a guide ([] if not rendered)."""
    d = os.path.join(base or guides_dir(), slug)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jpg"))


def render(slug, pdf, base=None, dpi=DPI):
    """Render a guide's pages to JPEGs (pdftoppm). Returns the page list; [] if the PDF or pdftoppm is missing."""
    if not os.path.isfile(pdf) or shutil.which("pdftoppm") is None:
        return []
    d = os.path.join(base or guides_dir(), slug)
    os.makedirs(d, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-jpeg", "-jpegopt", "quality=85", pdf, os.path.join(d, "p")],
                   check=False, capture_output=True)
    return pages(slug, base)


def available(base=None):
    """[(group, title, slug, n_pages_or_None, source)] -- None = not rendered yet but the PDF is there."""
    out = []
    for g, t, slug, src in GUIDES:
        n = len(pages(slug, base))
        if n:
            out.append((g, t, slug, n, src))
        elif os.path.isfile(src):
            out.append((g, t, slug, None, src))
    return out


def export(base):
    os.makedirs(base, exist_ok=True)
    index = []
    for g, t, slug, src in GUIDES:
        n = len(render(slug, src, base))
        print(f"  {slug:15s} {n:3d} pages  <- {src}" if n else f"  {slug:15s} MISSING {src}")
        n and index.append(dict(group=g, title=t, slug=slug, pages=n))
    with open(os.path.join(base, "index.json"), "w") as fh:
        json.dump(index, fh, indent=1)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--export":
        export(sys.argv[2])
    else:
        print(__doc__)
