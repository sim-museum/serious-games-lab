"""CARPHYS-1 S9: the clutch's torque capacity against pedal engagement, from the gold's standing starts.

During a slipping launch (1st gear, < 10 m/s, off the brakes, engine clearly faster than the gearbox input) the clutch
torque is what drives the car, so it is measured on the CAR side -- the longitudinal accelerometer, rolling resistance
and the wheels' inertia, through the 1st-gear ratio (from rpm/wheel speed on the fully engaged rows) -- not from the
engine's own acceleration, which the shift blips make useless. While slipping the clutch transmits its capacity, so the
median torque per engagement band IS the capacity curve. iRacing's Clutch channel: 1 = engaged (memory
jr-ibt-clutch-convention). Prints the knots behind powertrain.jl CLUTCH_KNOTS.

  IBTPY_DIR=<dir with ibt.py> python3 tools/clutchfit_261009.py
"""
import glob, math, os, sys
import numpy as np
sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))
from ibt import read_ibt

M, R, ETA, IW, CRR = 617.0, 0.334, 0.9, 1.0, 0.0139
GOLD = os.path.expanduser("~/gold standard/julia racer")


def main():
    E, T = [], []
    for f in sorted(glob.glob(f"{GOLD}/26100[2345]/*.ibt")):
        try:
            d, _a, _n = read_ibt(f, ["Clutch", "Speed", "Gear", "RPM", "LongAccel", "LRspeed", "RRspeed", "Brake"])
        except Exception:
            continue
        cl, v, g, rpm, A, br = (np.array(d[c]) for c in ("Clutch", "Speed", "Gear", "RPM", "LongAccel", "Brake"))
        g = g.astype(int); wr = (np.array(d["LRspeed"]) + np.array(d["RRspeed"])) / 2; we = rpm * 2 * math.pi / 60
        k1 = (g == 1) & (cl > 0.99) & (wr > 5)
        if k1.sum() < 30:
            continue
        G = np.median(we[k1] / (wr[k1] / R))
        awr = np.gradient(wr) * 60
        k = (g == 1) & (v < 10) & (v > 0.5) & (cl > 0.02) & (cl < 0.98) & (br < 0.01) & ((we - wr / R * G) > 40)
        T += list((M * A[k] + CRR * M * 9.81 + 4 * IW / R / R * awr[k]) * R / (G * ETA)); E += list(cl[k])
    E, T = np.array(E), np.array(T)
    print(f"{len(E)} slipping launch rows")
    knots = [(0.0, 0.0)]
    for c in (0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65):
        kk = (E >= c - 0.05) & (E < c + 0.05)
        if kk.sum() > 15:
            q = np.percentile(T[kk], [25, 50, 75])
            print(f"  engagement {c:.2f}: {q[1]:6.1f} N·m (IQR {q[0]:.0f}..{q[2]:.0f}, n {kk.sum()})")
            knots.append((c, round(max(float(q[1]), 0.0))))
    print("CLUTCH_KNOTS (measured part) =", tuple(knots))


if __name__ == "__main__":
    main()
