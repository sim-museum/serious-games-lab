"""IRGOLD-1 S17: the part-throttle map (powertrain.jl THROTTLE_KNOTS_LO/HI) refitted in a chosen drivetrain frame.
Crank torque from the car side: T = [R·(M·A + aero + rolling) + (4·Iw + I_out·fd²·η)·a/R] / (G·η) + Ie·G·a/R + I_in·G·a/R
(A = LongAccel, its 6 sub-samples averaged, includes the slope; a = dv/dt; per-file mass; G = total ratio from rpm/speed).
fraction f = (T + EFRIC)/(WOT + EFRIC) per pedal band, in the 4,000-5,500 (lo) and 7,000-8,000 (hi) rpm columns.
  FRAME=axle (0.0522 crank + 0.1482 behind the box, WOT = S14's axle-frame table) | input (0.18 at the crank, S6 table)"""
import glob, math, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
FRAME = os.environ.get("FRAME", "axle")
S6 = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0),
      (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))
AX = tuple((b + 125.0, t) for b, t in ((1750, 219), (2000, 231), (2250, 238), (2500, 242), (2750, 241), (3000, 241), (3250, 243), (3500, 242),
     (3750, 241), (4000, 239), (4250, 241), (4500, 248), (4750, 259), (5000, 268), (5250, 277), (5500, 285), (5750, 292), (6000, 298),
     (6250, 305), (6500, 311), (6750, 315), (7000, 316), (7250, 313), (7500, 311), (7750, 309), (8000, 304), (8250, 296), (8500, 285), (8750, 280)))
K = AX if FRAME == "axle" else S6
IE, IIN, IOUT = (0.0522, 0.0, 0.1482) if FRAME == "axle" else (0.18, 0.0, 0.0)
wot = lambda r: np.interp(r, [k[0] for k in K], [k[1] for k in K])
drag = lambda r: (14.24 + 0.00389*r)*0.5*(1 + np.tanh((r - 2353)/351))
R, ETA, IW, CDA, CRR = 0.334, 0.9, 1.0, 0.480, 0.0139
GOLD = os.path.expanduser("~/gold standard/julia racer")
rows = []
for f in sorted(glob.glob(f"{GOLD}/2610*/*.ibt")):
    if "19-30-13" in f or "skidpad" in f: continue
    try:
        d, y, _ = read_ibt(f, ["Speed", "LongAccel", "Throttle", "Brake", "Clutch", "Gear", "RPM", "LatAccel", "AirDensity"])
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception:
        continue
    d = {k: (a.mean(axis=1) if a.ndim == 2 else a) for k, a in d.items()}
    M = cw/9.81; v = d["Speed"]; rpm = d["RPM"]
    a = np.gradient(v)*60.0; G = (rpm*2*math.pi/60)*R/np.maximum(v, 1)
    k = (v > 15) & (d["Brake"] < 0.01) & (d["Clutch"] > 0.98) & (d["Gear"] >= 2) & (np.abs(d["LatAccel"]) < 3.0) & (rpm > 4000) & (rpm < 8800)
    T = ((R*(M*d["LongAccel"] + 0.5*d["AirDensity"]*CDA*v*v + CRR*M*9.81) + (4*IW + IOUT*fd*fd*ETA)*a/R)/(G*ETA)
         + (IE + IIN)*G*a/R)
    rows.append(np.column_stack([d["Throttle"][k], rpm[k], T[k]]))
thr, rpm, T = np.vstack(rows).T
frac = (T + drag(rpm))/(wot(rpm) + drag(rpm))
print(f"FRAME {FRAME}: {len(thr)} rows")
for lab, lo, hi in (("LO 4,000-5,500", 4000, 5500), ("MID 5,500-7,000", 5500, 7000), ("HI 7,000-8,000", 7000, 8000)):
    kn = [(0.0, 0.0)]
    for c in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        kk = (thr >= c - 0.05) & (thr < c + 0.05) & (rpm >= lo) & (rpm < hi)
        kn.append((c, round(float(np.median(frac[kk])), 2) if kk.sum() > 20 else None))
    kn.append((1.0, 1.0))
    print(f"  {lab}: {kn}")
kk = (thr > 0.98)
print(f"  check: WOT rows fraction median {np.median(frac[kk]):.3f} (should be ~1)")
