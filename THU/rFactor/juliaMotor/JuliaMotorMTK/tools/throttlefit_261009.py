"""CARPHYS-1 S8: the part-throttle engine map from the gold.

The model blended part throttle linearly: T = thr * WOT(rpm) - (1 - thr) * drag(rpm). This measures what iRacing's
Lotus 49 does: from every gold row driven straight-ish (|ay| < 3 m/s^2), clutch in, off the brakes, 4,000-8,800 rpm, the
crank torque from the longitudinal accelerometer (which already includes the slope), aero drag, rolling resistance and
the rotating inertias (engine 0.18, wheels 4 x 1.0 kg m^2 through the total ratio, taken from rpm and speed); then the
torque FRACTION f = (T + drag) / (WOT + drag): 0 = closed (pure engine drag), 1 = WOT. Binned by pedal, by rpm band and
by setup. Prints the knots the model's THROTTLE_KNOTS (powertrain.jl) came from.

  IBTPY_DIR=<dir with ibt.py> python3 tools/throttlefit_261009.py
"""
import glob, math, os, sys
import numpy as np
sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))
from ibt import read_ibt

K = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0),
     (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))   # powertrain.jl WOT_KNOTS
wot = lambda r: np.interp(r, [k[0] for k in K], [k[1] for k in K])
drag = lambda r: (14.24 + 0.00389 * r) * 0.5 * (1 + np.tanh((r - 2353) / 351))            # EFRIC_*
M, R, ETA, IE, IW, RHO, CDA, CRR = 617.0, 0.334, 0.9, 0.18, 1.0, 1.10, 0.480, 0.0139
GOLD = os.path.expanduser("~/gold standard/julia racer")


def main():
    rows = []
    for f in sorted(glob.glob(f"{GOLD}/26100[45]/*.ibt")):
        d, _a, _n = read_ibt(f, ["Speed", "LongAccel", "Throttle", "Brake", "Clutch", "Gear", "RPM", "LatAccel"])
        v, A, thr, br, cl, g, rpm, ay = (np.array(d[c]) for c in ("Speed", "LongAccel", "Throttle", "Brake", "Clutch", "Gear", "RPM", "LatAccel"))
        akin = np.gradient(v) * 60.0; G = (rpm * 2 * math.pi / 60) * R / np.maximum(v, 1)
        k = (v > 15) & (br < 0.01) & (cl > 0.98) & (g >= 2) & (abs(ay) < 3.0) & (rpm > 4000) & (rpm < 8800)
        T = (M * A + 0.5 * RHO * CDA * v * v + CRR * M * 9.81 + (IE * G * G / R / R + 4 * IW / R / R) * akin) * R / (G * ETA)
        rows.append(np.column_stack([thr[k], rpm[k], T[k]]))
    thr, rpm, T = np.vstack(rows).T
    frac = (T + drag(rpm)) / (wot(rpm) + drag(rpm))
    print(f"{len(thr)} rows.  pedal -> torque fraction (median); the linear model would give the pedal itself")
    knots = [(0.0, 0.0)]
    for c in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        kk = (thr >= c - 0.05) & (thr < c + 0.05)
        knots.append((c, round(float(np.median(frac[kk])), 2)))
        print(f"  {c:.2f}: {np.median(frac[kk]):.2f}  (n {kk.sum()})")
    knots.append((1.0, 1.0))
    print("THROTTLE_KNOTS =", tuple(knots))


if __name__ == "__main__":
    main()
