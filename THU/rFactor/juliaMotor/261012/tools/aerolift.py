"""IRGOLD-1 S20: aerodynamic LIFT per axle, identified from the gold's straight-line suspension (every 2610xx session).
Rows: |ay| < 0.05 g, |ax| < 0.08 g, > 15 m/s, off the brakes. Per corner the spring force change is k_spring·Δshock/MR (the
setup's SpringRate, sim motion ratios 0.78 / 0.648); per axle the sum of L+R. Regression per axle: ΔF = c_file + c_fuel·fuel
+ q·(½ρv²) with a per-file intercept (static ride differs by setup). The drag/thrust couple is subtracted using the sim's
own frame (drag 0.48 m² at the CG height 0.30 m, thrust at the ground, wheelbase 2.41 m): ΔF_front = −D·h/L, rear +D·h/L.
q − couple = the lift area ClA per axle [m²] (+ = downforce)."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer")
rowsF, rowsR, files = [], [], []
for f in sorted(glob.glob(G + "/2610*/*.ibt")):
    if "19-30-13" in f or "skidpad" in f: continue
    try:
        d, y, _ = read_ibt(f, ["Speed", "LatAccel", "LongAccel", "LFshockDefl", "RFshockDefl", "LRshockDefl", "RRshockDefl", "Brake", "FuelLevel", "AirDensity"])
        sr = lambda c: float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "SpringRate")))
        kf, kr = sr("LeftFront")*1000, sr("LeftRear")*1000      # N/m at the spring
    except Exception:
        continue
    d = {k: (a.mean(axis=1) if a.ndim == 2 else a) for k, a in d.items()}
    ok = (np.abs(d["LatAccel"]) < 0.05*9.81) & (np.abs(d["LongAccel"]) < 0.08*9.81) & (d["Speed"] > 15) & (d["Brake"] < 0.01)
    if ok.sum() < 40: continue
    fi = len(files); files.append(os.path.basename(f)[8:-4])
    q = 0.5*d["AirDensity"][ok]*d["Speed"][ok]**2
    Ff = kf*(d["LFshockDefl"] + d["RFshockDefl"])[ok]/0.78; Fr = kr*(d["LRshockDefl"] + d["RRshockDefl"])[ok]/0.648
    for a, b, c, fu in zip(q, Ff, Fr, d["FuelLevel"][ok]):
        rowsF.append((fi, a, fu, b)); rowsR.append((fi, a, fu, c))
for lab, R in (("FRONT", np.array(rowsF)), ("REAR", np.array(rowsR))):
    nf = len(files); fi = R[:, 0].astype(int)
    A = np.zeros((len(R), nf + 2)); A[np.arange(len(R)), fi] = 1; A[:, nf] = R[:, 1]; A[:, nf+1] = R[:, 2]
    x, *_ = np.linalg.lstsq(A, R[:, 3], rcond=None)
    res = R[:, 3] - A @ x
    # bootstrap by file for a CI on the q coefficient
    rng = np.random.default_rng(1); bs = []
    for _ in range(200):
        pick = rng.integers(0, nf, nf); m = np.isin(fi, pick)
        if m.sum() < 100: continue
        xb, *_ = np.linalg.lstsq(A[m], R[m, 3], rcond=None); bs.append(xb[nf])
    couple = (-1 if lab == "FRONT" else 1)*0.48*0.30/2.41
    print(f"{lab}: dF/dq {x[nf]:+.3f} m² (90% CI {np.percentile(bs,5):+.3f}..{np.percentile(bs,95):+.3f}, {nf} files, {len(R)} rows, resid sd {res.std():.0f} N)"
          f"  couple {couple:+.3f} m²  →  ClA {x[nf]-couple:+.3f} m²  (at 216 km/h, ρ 1.15: {(x[nf]-couple)*0.5*1.15*60**2:+.0f} N)")
    # per-file slopes for consistency
    per = []
    for k in range(nf):
        m = fi == k
        if m.sum() > 60 and np.ptp(R[m, 1]) > 500:
            B = np.c_[np.ones(m.sum()), R[m, 1]]; xx, *_ = np.linalg.lstsq(B, R[m, 3], rcond=None); per.append((files[k], xx[1], m.sum()))
    print("   per file dF/dq: " + "  ".join(f"{n[:22]} {s:+.2f}({c})" for n, s, c in per))
