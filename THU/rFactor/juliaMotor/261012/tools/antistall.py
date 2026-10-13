"""IRGOLD-1: iRacing's anti-stall clutch. In nearly every gold launch the driver's pedal (ClutchRaw, 1 = released) is out
further than the clutch's actual engagement (Clutch) while the engine sits at ~1,600-2,100 rpm: the sim limits the
engagement to keep the engine running. Here: the held rows' engagement against engine rpm, throttle and the slip."""
import glob, os, sys, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer")
H = []
for f in sorted(glob.glob(G + "/2610*/*.ibt")):
    try:
        d, y, _ = read_ibt(f, ["Clutch", "ClutchRaw", "Speed", "Gear", "RPM", "Throttle", "LRspeed", "RRspeed"])
    except Exception:
        continue
    if "ClutchRaw" not in d: continue
    c, r, v, rpm, thr, gear = d["Clutch"], d["ClutchRaw"], d["Speed"], d["RPM"], d["Throttle"], d["Gear"]
    drpm = np.gradient(rpm)*60
    for i in np.where((gear >= 1) & (c < 0.98) & (r > 0.02))[0]:
        H.append((r[i], c[i], rpm[i], thr[i], v[i], drpm[i], gear[i]))
H = np.array(H); raw, clu, rpm, thr, v, drpm, gear = H.T
held = raw > clu + 0.05
print(f"in-gear partly-engaged rows {len(H)}; held (raw > engagement + 0.05) {held.sum()}; follows the pedal {(~held).sum()}")
print("\nheld rows: engagement by engine rpm (median, IQR, n) -- and how often raw is fully out (> 0.95)")
for a in range(1000, 4000, 200):
    m = held & (rpm >= a) & (rpm < a+200)
    if m.sum() >= 20:
        q = np.percentile(clu[m], [25, 50, 75])
        print(f"   {a:4d}-{a+200:4d}: {q[1]:.2f} ({q[0]:.2f}-{q[2]:.2f}) n{m.sum():5d}  raw>0.95 {np.mean(raw[m] > 0.95):.2f}  drpm/dt med {np.median(drpm[m]):6.0f}")
print("\nnot held (engagement follows the pedal): rpm distribution")
print("   ", np.percentile(rpm[~held], [5, 25, 50, 75, 95]).round())
print("\nheld rows: lowest rpm reached per bin of throttle")
for t0 in (0.0, 0.2, 0.4, 0.6, 0.8):
    m = held & (thr >= t0) & (thr < t0+0.2)
    if m.sum() > 20: print(f"   thr {t0:.1f}-{t0+0.2:.1f}: rpm p5 {np.percentile(rpm[m],5):5.0f} median {np.median(rpm[m]):5.0f}  engagement median {np.median(clu[m]):.2f}  n{m.sum()}")
print("\ndoes the engagement rise when rpm rises? held rows, engagement vs rpm slope (rpm in 1400-2600):")
m = held & (rpm > 1400) & (rpm < 2600) & (v < 10)
A = np.c_[np.ones(m.sum()), rpm[m], thr[m]]
c, *_ = np.linalg.lstsq(A, clu[m], rcond=None)
print(f"   engagement ≈ {c[0]:.3f} + {c[1]*1000:.4f}/krpm·rpm + {c[2]:.3f}·throttle   (n {m.sum()}, resid sd {np.std(clu[m] - A@c):.3f})")
