"""IRGOLD-1 S14: the gold's straight-line DRIVE force against rear slip, by speed band -- does iRacing's longitudinal
tyre work on slip RATIO (κ = Δv/v) or slip VELOCITY (Δv)? WOT, clutch in, gears 1-3, |LatAccel| < 0.15 g, 0.5 s clear
of shifts. Fx_rear ≈ m·a + aero + rolling (front rolling small), Fz_rear = static + m·a·h/L (h 0.30, L 2.41, sim frame)."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer"); g0 = 9.80665
def lslope(y, dt, hw):
    k = np.arange(-hw, hw+1); w = k/(dt*(k**2).sum()); return np.convolve(y, w[::-1], mode="same")
rows = []
for f in sorted(glob.glob(G + "/2610*/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _ = read_ibt(f, ["Speed", "Gear", "Throttle", "Clutch", "LatAccel", "LRspeed", "RRspeed", "LFspeed", "RFspeed", "Alt", "AirDensity"])
        cwv = {c: float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear")}
    except Exception:
        continue
    m = sum(cwv.values())/9.81; Fzr0 = cwv["LeftRear"] + cwv["RightRear"]
    v = d["Speed"]; dt = 1/60; gear = d["Gear"].astype(int)
    lat = d["LatAccel"]; lat = lat.mean(axis=1) if lat.ndim == 2 else lat
    a = lslope(v, dt, 6) + g0*lslope(d["Alt"], dt, 60)/np.maximum(v, 1)
    vr = (d["LRspeed"] + d["RRspeed"])/2; vf = (d["LFspeed"] + d["RFspeed"])/2
    ok = (d["Throttle"] > 0.98) & (d["Clutch"] > 0.98) & (gear >= 1) & (gear <= 3) & (np.abs(lat) < 0.15*g0) & (v > 3)
    chg = np.r_[False, np.diff(gear) != 0]; ok &= ~(np.convolve(chg.astype(float), np.ones(31), mode="same") > 0)
    for i in np.where(ok)[0]:
        Fx = m*a[i] + 0.5*d["AirDensity"][i]*0.48*v[i]**2 + 0.0139*m*g0*0.45   # rear drive force (front rolling share)
        Fz = Fzr0 + m*a[i]*0.30/2.41
        rows.append((vf[i], vr[i] - vf[i], (vr[i] - vf[i])/max(vf[i], 0.5), Fx/Fz))
R = np.array(rows); V, DV, K, MU = R.T
print(f"rows {len(R)}")
kb = (-0.01, 0.005, 0.01, 0.02, 0.04, 0.08, 0.15, 0.3, 0.6, 2.0)
vb = (3, 8, 15, 25, 45, 90)
print("Fx/Fz (median, n) by slip RATIO (rows) x speed (cols m/s)")
print("  κ band       " + "".join(f"   {a:2d}-{b:<3d}       " for a, b in zip(vb[:-1], vb[1:])))
for k0, k1 in zip(kb[:-1], kb[1:]):
    print(f"  {k0:6.3f}-{k1:5.3f}" + "".join(f"  {np.median(MU[(K>=k0)&(K<k1)&(V>=a)&(V<b)]):5.2f} ({((K>=k0)&(K<k1)&(V>=a)&(V<b)).sum():5d})" if ((K>=k0)&(K<k1)&(V>=a)&(V<b)).sum() >= 10 else "        -      " for a, b in zip(vb[:-1], vb[1:])))
db = (-0.2, 0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0, 6.0, 20.0)
print("\nFx/Fz by slip VELOCITY Δv [m/s] (rows) x speed (cols)")
for k0, k1 in zip(db[:-1], db[1:]):
    print(f"  {k0:5.2f}-{k1:5.2f} " + "".join(f"  {np.median(MU[(DV>=k0)&(DV<k1)&(V>=a)&(V<b)]):5.2f} ({((DV>=k0)&(DV<k1)&(V>=a)&(V<b)).sum():5d})" if ((DV>=k0)&(DV<k1)&(V>=a)&(V<b)).sum() >= 10 else "        -      " for a, b in zip(vb[:-1], vb[1:])))
