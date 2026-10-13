"""IRGOLD-1 S14: the clutch capacity vs engagement re-measured (CARPHYS-1 S9's method, clutchfit_261009.py) with
(1) per-file mass from CornerWeight, (2) LongAccel's 360 Hz sub-samples averaged (newer files carry 6 per row),
(3) the S14 driveline inertia behind the gearbox (0.1506·final²·η at the rear axle) on the car side, and
(4) every session incl. IRTEST-261012's fixed-pedal starts. Per session and pooled."""
import glob, math, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
R, ETA, IW, CRR, IOUT = 0.334, 0.9, 1.0, 0.0139, float(os.environ.get("IOUT", "0.1506"))
GOLD = os.path.expanduser("~/gold standard/julia racer")
bands = (0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75)
allE, allT, allS = [], [], []
for f in sorted(glob.glob(f"{GOLD}/2610*/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _n = read_ibt(f, ["Clutch", "Speed", "Gear", "RPM", "LongAccel", "LRspeed", "RRspeed", "Brake", "Throttle"])
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception:
        continue
    M = cw/9.81
    cl, v, g, rpm, br = (np.asarray(d[c], float) for c in ("Clutch", "Speed", "Gear", "RPM", "Brake"))
    A = np.asarray(d["LongAccel"], float); A = A.mean(axis=1) if A.ndim == 2 else A
    g = g.astype(int); wr = (d["LRspeed"] + d["RRspeed"])/2; we = rpm*2*math.pi/60
    k1 = (g == 1) & (cl > 0.99) & (wr > 5)
    if k1.sum() < 30: continue
    G = np.median(we[k1]/(wr[k1]/R))
    awr = np.gradient(wr)*60
    k = (g == 1) & (v < 10) & (v > 0.5) & (cl > 0.02) & (cl < 0.98) & (br < 0.01) & ((we - wr/R*G) > 40)
    T = (M*A[k] + CRR*M*9.81 + (2*IW/R/R + 2*IW/R/R + IOUT*fd**2*ETA/R/R)*awr[k])*R/(G*ETA)
    allE += list(cl[k]); allT += list(T); allS += [f.split("/")[-2]]*int(k.sum())
E, T, S = np.array(allE), np.array(allT), np.array(allS)
print(f"{len(E)} slipping launch rows; sessions " + ", ".join(f"{s}:{(S==s).sum()}" for s in sorted(set(S))))
print("engagement |" + "".join(f" {s:>14s}" for s in sorted(set(S))) + " |   pooled (IQR)          | CLUTCH_KNOTS")
ck = dict(((0.0, 0.0), (0.05, 1.0), (0.15, 14.0), (0.25, 71.0), (0.35, 142.0), (0.45, 202.0), (0.55, 321.0), (0.65, 407.0), (1.0, 760.0)))
for c in bands:
    kk = (E >= c - 0.05) & (E < c + 0.05)
    per = "".join(f" {np.median(T[kk & (S==s)]):8.0f} ({(kk & (S==s)).sum():3d})" if (kk & (S==s)).sum() >= 10 else "         -    " for s in sorted(set(S)))
    q = np.percentile(T[kk], [25, 50, 75]) if kk.sum() > 15 else (np.nan,)*3
    print(f"   {c:.2f}    |{per} | {q[1]:6.1f} ({q[0]:4.0f}..{q[2]:4.0f}) n{kk.sum():5d} | {ck.get(c, float('nan')):6.1f}")

# ---- capacity by engagement x SLIP SPEED (engine − gearbox input, rad/s) ----
allW = []
for f in sorted(glob.glob(f"{GOLD}/2610*/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _n = read_ibt(f, ["Clutch", "Speed", "Gear", "RPM", "LRspeed", "RRspeed", "Brake"])
    except Exception:
        continue
    cl, v, g, rpm, br = (np.asarray(d[c], float) for c in ("Clutch", "Speed", "Gear", "RPM", "Brake"))
    g = g.astype(int); wr = (d["LRspeed"] + d["RRspeed"])/2; we = rpm*2*math.pi/60
    k1 = (g == 1) & (cl > 0.99) & (wr > 5)
    if k1.sum() < 30: continue
    G = np.median(we[k1]/(wr[k1]/R))
    k = (g == 1) & (v < 10) & (v > 0.5) & (cl > 0.02) & (cl < 0.98) & (br < 0.01) & ((we - wr/R*G) > 40)
    allW += list((we - wr/R*G)[k])
W = np.array(allW)
print("\ncapacity [N·m] by engagement (rows) x slip speed (cols, rad/s): median (n)")
sb = (40, 100, 200, 400, 700, 1000)
print("            " + "".join(f"  {a:4d}-{b:<4d}    " for a, b in zip(sb[:-1], sb[1:])))
for c in (0.15, 0.25, 0.35, 0.45, 0.55):
    kk = (E >= c - 0.05) & (E < c + 0.05)
    print(f"   {c:.2f}    " + "".join(f"  {np.median(T[kk & (W>=a) & (W<b)]):6.0f} ({(kk & (W>=a) & (W<b)).sum():4d})" if (kk & (W>=a) & (W<b)).sum() >= 10 else "        -       " for a, b in zip(sb[:-1], sb[1:])))

# ---- fine engagement bins x ENGINE rpm ----
allR = []
for f in sorted(glob.glob(f"{GOLD}/2610*/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _n = read_ibt(f, ["Clutch", "Speed", "Gear", "RPM", "LRspeed", "RRspeed", "Brake"])
    except Exception:
        continue
    cl, v, g, rpm, br = (np.asarray(d[c], float) for c in ("Clutch", "Speed", "Gear", "RPM", "Brake"))
    g = g.astype(int); wr = (d["LRspeed"] + d["RRspeed"])/2; we = rpm*2*math.pi/60
    k1 = (g == 1) & (cl > 0.99) & (wr > 5)
    if k1.sum() < 30: continue
    G = np.median(we[k1]/(wr[k1]/R))
    k = (g == 1) & (v < 10) & (v > 0.5) & (cl > 0.02) & (cl < 0.98) & (br < 0.01) & ((we - wr/R*G) > 40)
    allR += list(rpm[k])
RP = np.array(allR)
print("\ncapacity by fine engagement x engine rpm: median (n)")
rb = (0, 2500, 4000, 6000, 10000)
for c in np.arange(0.20, 0.56, 0.03):
    kk = (E >= c) & (E < c + 0.03)
    print(f"   {c:.2f}-{c+0.03:.2f} " + "".join(f"  {np.median(T[kk & (RP>=a) & (RP<b)]):6.0f} ({(kk & (RP>=a) & (RP<b)).sum():4d})" if (kk & (RP>=a) & (RP<b)).sum() >= 8 else "        -      " for a, b in zip(rb[:-1], rb[1:])))
print("   rpm cols: <2500, 2500-4000, 4000-6000, >6000")

print("\nCLUTCH_KNOTS (S14, ±0.02 windows, pooled):")
kn = [(0.0, 0.0)]
for c in np.arange(0.05, 0.66, 0.05):
    kk = (E >= c - 0.02) & (E < c + 0.02)
    if kk.sum() >= 15:
        q = np.percentile(T[kk], [25, 50, 75]); kn.append((round(c, 2), round(max(q[1], 0.0), 1)))
        print(f"   {c:.2f}: {q[1]:6.1f} (IQR {q[0]:.0f}..{q[2]:.0f}, n {kk.sum()})")
print("  ", tuple(kn))
