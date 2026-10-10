# TRACKSEG-5 (PO 2026-10-09: "look for track maps under ~/sgl/THU which contain more names of track sections"):
# place every name printed on a BAPOM track map (the printable maps GPL ships, ~/sgl/THU/DOC/trackMaps/map-*.pdf and
# tracks/<t>/map-<t>.pdf) at a lap distance on the sim's ribbon.
#   1. the map's track line = its thick black stroke (text strokes are thinner: a 5-px erosion removes them);
#   2. the ribbon (tools/section_signs.jl's CSV) is fitted onto that line by a similarity transform (ICP from 24
#      start orientations, with and without a mirror; the mean two-way gap in px is printed -- Ring: 2.4 px);
#   3. each label goes to the ribbon point nearest its text box.
# A label stands BESIDE its corner, so a name's section starts a little before the printed s (at the Ring the add-on's
# section boards stand a median 70 m before the map's labels). Check the known names against the table first.
#   pdftoppm -r 100 -png -singlefile map.pdf map && pdftotext -bbox map.pdf map.html
#   python3 tools/bapom_names.py map.png map.html rib.csv 100
import sys, re, math
from PIL import Image, ImageFilter
import numpy as np
png, bbox, rib = sys.argv[1], sys.argv[2], sys.argv[3]
dpi = float(sys.argv[4]) if len(sys.argv) > 4 else 100.0
k = dpi/72.0
im = Image.open(png).convert('L')
dark = im.point(lambda p: 255 if p < 100 else 0)
thick = dark.filter(ImageFilter.MinFilter(5))            # keep strokes >= 5 px wide: the track, not the text
A = np.array(thick) > 0
ys, xs = np.nonzero(A)
M = np.stack([xs, ys], 1).astype(float)
M = M[::3]
R = np.loadtxt(rib, delimiter=',')
s, X, Z = R[:,0], R[:,1], R[:,2]
P = np.stack([X, Z], 1)
from scipy.spatial import cKDTree
tm = cKDTree(M)
def fit(refl, rot0):
    Q = P.copy()
    if refl: Q[:,1] = -Q[:,1]
    c, sn = math.cos(rot0), math.sin(rot0)
    Q = Q @ np.array([[c, -sn],[sn, c]]).T
    # initial scale/translation from bounding boxes
    sc = (M[:,1].max()-M[:,1].min())/(Q[:,1].max()-Q[:,1].min())
    Q = (Q - Q.mean(0))*sc + M.mean(0)
    T = np.eye(3)
    for it in range(60):
        d, j = tm.query(Q)
        tgt = M[j]
        w = d < np.percentile(d, 90)
        a, b = Q[w], tgt[w]
        ma, mb = a.mean(0), b.mean(0)
        H = (a-ma).T @ (b-mb)
        U, S_, Vt = np.linalg.svd(H)
        Rm = Vt.T @ U.T
        if np.linalg.det(Rm) < 0: Vt[1] *= -1; Rm = Vt.T @ U.T
        scl = S_.sum()/((a-ma)**2).sum()
        Q = (Q-ma) @ Rm.T * scl + mb
    d, _ = tm.query(Q)
    tq = cKDTree(Q); d2, _ = tq.query(M)
    return d.mean() + d2.mean(), Q
best = None
for refl in (False, True):
    for r in range(0, 360, 30):
        e, Q = fit(refl, math.radians(r))
        if best is None or e < best[0]: best = (e, Q, refl, r)
e, Q, refl, r = best
print(f"fit error {e:.2f} px (refl {refl}, rot0 {r})", file=sys.stderr)
words = re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', open(bbox).read())
# join words on the same line that are close: label = consecutive words with gap < 6 pt and same yMin
labels = []
for w in words:
    x0, y0, x1, y1, t = float(w[0]), float(w[1]), float(w[2]), float(w[3]), w[4]
    if labels and abs(labels[-1][1]-y0) < 0.5 and x0 - labels[-1][2] < 6:
        L = labels[-1]; labels[-1] = (L[0], L[1], x1, max(L[3], y1), L[4]+' '+t)
    else:
        labels.append((x0, y0, x1, y1, t))
tq = cKDTree(Q)
for (x0, y0, x1, y1, t) in labels:
    # nearest ribbon point to the label's box (in px)
    bx0, by0, bx1, by1 = x0*k, y0*k, x1*k, y1*k
    cx = np.clip(Q[:,0], bx0, bx1); cy = np.clip(Q[:,1], by0, by1)
    d = np.hypot(Q[:,0]-cx, Q[:,1]-cy)
    i = int(np.argmin(d))
    print(f"{s[i]:8.1f}  d {d[i]:5.1f}px  {t}")
