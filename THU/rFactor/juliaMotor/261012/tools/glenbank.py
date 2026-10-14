"""IRGOLD-1 S24: why the PO corners at 1.5 g in iRacing's Glen and at 1.24 g in julia's. Per 1/20 of the lap (laps aligned
as glencompare.py, by speed-trace cross-correlation): median |lateral g| and body roll in the corners, iRacing (WW103 Glen
Classic, 21-57-57) vs the PO's julia WG drives. A banked corner reads as more lateral g on an accelerometer (g·sin θ) and
as roll INTO the turn."""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt
def laps(f):
    d, _, _ = read_ibt(f, ["Speed", "LapDist", "SessionTime", "LatAccel", "Roll"])
    c = lambda k: (lambda a: a.reshape(len(a), -1)[:, 0])(np.asarray(d[k], float))
    ld, v, t, ay, ro = c("LapDist"), c("Speed"), c("SessionTime"), c("LatAccel"), c("Roll")
    L = np.nanmax(ld); cut = np.where(np.diff(ld) < -0.5*L)[0]
    return [(t[b] - t[a], ld[a+1:b+1]/L, v[a+1:b+1], ay[a+1:b+1], ro[a+1:b+1]) for a, b in zip(cut[:-1], cut[1:])
            if (t[b] - t[a]) > 75 and np.nanmax(ld[a+1:b]) > 0.95*L]
G = os.path.expanduser("~/gold standard/julia racer/261012")
gl = laps(glob.glob(G + "/*21-57-57*.ibt")[0])
jl = [x for s in ("10-08 20-56-12", "10-08 21-05-16", "10-08 21-22-22", "10-08 21-55-45", "10-10 19-07-13")
      for g in glob.glob(f"data/juliaracer/lotus49_watglen 2026-{s}.ibt") for x in laps(g)]
X = np.linspace(0, 1, 1000, endpoint=False)
res = lambda lp: [np.interp(X, lp[1], lp[k]) for k in (2, 3, 4)]
gb = res(min(gl, key=lambda x: x[0])); jb = res(min(jl, key=lambda x: x[0]))
sh = max(range(1000), key=lambda k: np.corrcoef(gb[0], np.roll(jb[0], k))[0, 1])
jb = [np.roll(a, sh) for a in jb]
print(f"best laps aligned (shift {sh/1000:.3f}, corr {np.corrcoef(gb[0], jb[0])[0,1]:.3f})")
print("sector | v min km/h iR/ju | |lat g| p90 iR/ju | roll° at peak lat, signed into the turn iR/ju")
for k in range(20):
    m = (X >= k/20) & (X < (k+1)/20)
    out = []
    for v, ay, ro in (gb, jb):
        i = np.argmax(np.abs(ay[m])); s = np.sign(ay[m][i])
        out.append((v[m].min()*3.6, np.percentile(np.abs(ay[m]), 90)/9.81, np.degrees(ro[m][i])*s))
    (v1, a1, r1), (v2, a2, r2) = out
    if max(a1, a2) > 0.6:
        print(f"  {k/20:.2f}  | {v1:4.0f} / {v2:4.0f}     |  {a1:.2f} / {a2:.2f}     |  {r1:+5.1f} / {r2:+5.1f}")
