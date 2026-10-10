# TRACKGUIDE-1 (PO 2026-10-09: "for the julia racer post-race analysis, use GPL track guides under ~/sgl/THU"). Checks the
# guide reader (demo/native/trackguide.py) on the real guides and a synthetic lap:
#   * each of the five tracks' Lights Out Racing guide parses to its corners, with speeds and times (the Ring's
#     "1 minute 1.68 seconds" format included), and the Ring's 23 board-photo groups map onto the sim's sections;
#   * placed on a lap, every corner lands in lap order, and each section's first corner within 400 m of where the
#     sim's section of that name starts;
#   * the AppImage copy (text exported at build time, JM_TRACKGUIDE_DIR) reads the same as the PDFs.
# Needs the guides (~/sgl/THU/DOC or JM_GPL_DOC) and pdftotext; without them it reports SKIP and passes.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
py = raw"""
import os, sys, tempfile
sys.path.insert(0, os.getcwd()); import trackguide as G
class Lap: pass
def lap_for(L, v=40.0):
    lp = Lap(); lp.dist = [i * 5.0 for i in range(int(L // 5) + 1)]; lp.ch = {"time": [d / v for d in lp.dist], "kmh": [3.6 * v] * len(lp.dist)}
    return lp
LAPS = {"nurburgring": 22809.5, "watglen": 3753.0, "monza": 5745.0, "spa": 14100.0, "zandvoort": 4187.0}
WANT = {"nurburgring": 70, "watglen": 5, "monza": 5, "spa": 7, "zandvoort": 9}
if G.guide_paths("watglen")[0] is None or G.pdf_text(G.guide_paths("watglen")[0]) is None:
    print("SKIP: no track guides or no pdftotext here"); sys.exit(0)
fails = 0
def chk(name, ok, detail=""):
    global fails; fails += 0 if ok else 1; print(f"  {name:66s} {'PASS' if ok else 'FAIL'}   {detail}")
chk("time formats: 5.63 s, 2:19.70, 1 minute 1.68 s, 7 minutes 39.26 s",
    [G._secs(x) for x in ("5.63 seconds", "2:19.70 seconds", "1 minute 1.68 seconds", "7 minutes 39.26 seconds")] == [5.63, 139.7, 61.68, 459.26])
for trk, L in LAPS.items():
    secs = G.current_sections(trk, L)
    es, src = G.load(trk, [n for _s, n in secs])
    ok = es is not None and len(es) == WANT[trk]
    chk(f"{trk}: {WANT[trk]} corners parsed", ok, f"{0 if es is None else len(es)}")
    if not ok: continue
    timed = [e for e in es if e["arrive"] is not None]
    chk(f"{trk}: speeds and times read, arrivals in lap order", all(e["entry"] for e in timed) and
        all(a["arrive"] < b["arrive"] for a, b in zip(timed, timed[1:])), f"{len(timed)} timed")
    lp = lap_for(L); G.place(es, lp, secs, L, G.guide_lap(G._text(trk, "lor")[0]))
    s = [e["s_arrive"] for e in es if e.get("s_arrive") is not None]
    chk(f"{trk}: placed corners in lap order", all(a <= b + 1e-6 for a, b in zip(s, s[1:])), f"{len(s)} placed")
    start = {n: x for x, n in secs}
    off = [abs(e["s_arrive"] - start[e["section"]]) for e in es if e.get("anchor") and e["section"] in start and e.get("s_arrive") is not None and start[e["section"]] > 1]
    chk(f"{trk}: each section's first corner within 400 m of the section start", all(o <= 400 for o in off), f"max {max(off or [0]):.0f} m")
ring, _ = G.load("nurburgring", [n for _s, n in G.current_sections("nurburgring", 22809.5)])
chk("the Ring: 23 groups, Südkehre first, Tiergarten last", sum(1 for e in ring if e["title"].startswith(("FIRST", "THE MAIN"))) == 23
    and ring[0]["section"] == "Südkehre" and ring[-1]["section"] == "Tiergarten")
with tempfile.TemporaryDirectory() as d:
    os.system(f"{sys.executable} trackguide.py --export {d} > /dev/null")
    a, _ = G.load("watglen", ["Esses", "Carousel", "Big Bend", 'The "90"'])
    os.environ["JM_TRACKGUIDE_DIR"] = d
    b, src = G.load("watglen", ["Esses", "Carousel", "Big Bend", 'The "90"'])
    del os.environ["JM_TRACKGUIDE_DIR"]
    chk("the AppImage's exported text reads the same as the PDF", a == b and "watglen_lor.txt" in src, src)
print("ALL PASS" if fails == 0 else f"FAILURES: {fails}"); sys.exit(1 if fails else 0)
"""
ok = success(pipeline(setenv(`python3 -I -c $py`; dir = D), stdout = stdout, stderr = stderr))
exit(ok ? 0 : 1)
