"""IRGOLD-1 (PO, 261012 summary: "the iRacing Watkins Glen was slower than the julia racer Watkins Glen"): speed by lap
fraction, iRacing Glen Classic gold laps (WW103 21-57-57) vs the PO's own julia racer WG laps (data/juliaracer), lap times
from the LapDist wrap. Sector table: corner minima and straight maxima per 1/20 of the lap."""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt
def laps(f):
    d, _, _ = read_ibt(f, ["Speed", "LapDist", "SessionTime"])
    ld, v, t = d["LapDist"], d["Speed"], d["SessionTime"]
    L = np.nanmax(ld); cut = np.where(np.diff(ld) < -0.5*L)[0]
    out = []
    for a, b in zip(cut[:-1], cut[1:]):
        if (t[b] - t[a]) > 60 and np.nanmax(ld[a+1:b]) > 0.95*L:
            out.append((t[b] - t[a], ld[a+1:b+1]/L, v[a+1:b+1]))
    return L, out
G = os.path.expanduser("~/gold standard/julia racer/261012")
gL, glaps = laps(glob.glob(G + "/*21-57-57*.ibt")[0])
print(f"iRacing Glen Classic (WW103): length {gL:.0f} m, laps {[round(x[0],2) for x in glaps]}")
J = []
for f in [g for s in ("10-08 20-56-12", "10-08 21-05-16", "10-08 21-22-22", "10-08 21-55-45", "10-10 19-07-13") for g in glob.glob(f"data/juliaracer/lotus49_watglen 2026-{s}.ibt")]:   # the PO's drives (the rest are gate runs)
    try:
        L, lp = laps(f)
    except Exception:
        continue
    if lp: print(f"julia {os.path.basename(f)[16:-4]}: length {L:.0f} m, laps {[round(x[0],2) for x in lp]}"); J += lp
if not J: sys.exit()
J = [x for x in J if x[0] > 75]                     # restart fragments out
gb = min(glaps, key=lambda x: x[0]); jb = min(J, key=lambda x: x[0])
# the two LapDist origins differ: resample both on 1000 fraction points and align julia's by circular cross-correlation
X = np.linspace(0, 1, 1000, endpoint=False)
gv = np.interp(X, gb[1], gb[2]); jv = np.interp(X, jb[1], jb[2])
sh = max(range(1000), key=lambda k: np.corrcoef(gv, np.roll(jv, k))[0, 1])
jv = np.roll(jv, sh); print(f"alignment: julia shifted by {sh/1000:.3f} of a lap (corr {np.corrcoef(gv, jv)[0,1]:.3f})")
gb = (gb[0], X, gv); jb = (jb[0], X, jv)
print(f"\nbest laps: iRacing {gb[0]:.2f} s, julia {jb[0]:.2f} s")
print("sector (1/20) | iRacing min/max km/h | julia min/max km/h | Δmin  Δmax")
for k in range(20):
    a, b = k/20, (k+1)/20
    gm = (gb[1] >= a) & (gb[1] < b); jm = (jb[1] >= a) & (jb[1] < b)
    if gm.sum() and jm.sum():
        g1, g2 = gb[2][gm].min()*3.6, gb[2][gm].max()*3.6; j1, j2 = jb[2][jm].min()*3.6, jb[2][jm].max()*3.6
        print(f"  {a:.2f}-{b:.2f}   | {g1:5.0f} / {g2:5.0f}       | {j1:5.0f} / {j2:5.0f}     | {j1-g1:+5.0f} {j2-g2:+5.0f}")
