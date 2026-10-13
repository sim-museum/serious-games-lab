"""IRTEST-261012 test 1: joint fit of the FREE engine (decoupled, stationary): Ie and drag D(rpm) = (c0 + c1·rpm)·fade.
WOT rise rows: Ie·ω̇ = WOT(rpm) − 0   (WOT_KNOTS = net torque; free drag at WOT assumed absorbed like in gear)
closed decay:  Ie·ω̇ = −D(rpm)
Then the quasi-steady part-throttle fraction f = (Ie·ω̇ + D)/(WOT + D) with the fitted Ie, D."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from freerev import wot, fric, R  # reuses the row extraction (prints its own table first)
rpm, thr, thrraw, dw, thrsd = R[:, 0], R[:, 1], R[:, 2], R[:, 3], R[:, 4]
fade = lambda r: 0.5*(1 + np.tanh((r - 2353)/351))
up = (thr > 0.98) & (rpm > 4500) & (rpm < 8800) & (dw > 0)
dn = (thr < 0.001) & (rpm > 2700) & (rpm < 9200) & (dw < 0)
Ie = np.median(wot(rpm[up])/dw[up])
print(f"\n=== FREE ENGINE ===\nIe (WOT rise, n{up.sum()}): {Ie:.4f}  (IQR {np.percentile(wot(rpm[up])/dw[up],25):.4f}-{np.percentile(wot(rpm[up])/dw[up],75):.4f})")
A = np.c_[fade(rpm[dn]), rpm[dn]*fade(rpm[dn])]; b = -Ie*dw[dn]
c, *_ = np.linalg.lstsq(A, b, rcond=None)
res = b - A @ c
print(f"free drag D = ({c[0]:.2f} + {c[1]:.5f}·rpm)·fade   n{dn.sum()}  resid sd {res.std():.2f} N·m")
print(f"in-gear fric (E91-S10)  = (14.24 + 0.00389·rpm)·fade")
for r in (3000, 4000, 5000, 6000, 7000, 8000, 9000):
    print(f"   {r}: free {(c[0]+c[1]*r)*fade(r):5.1f}   in-gear {fric(r):5.1f}   gap {fric(r)-(c[0]+c[1]*r)*fade(r):5.1f}")
D = (c[0] + c[1]*rpm)*fade(rpm)
f = (Ie*dw + D)/(wot(rpm) + D)
m = (thr > 0.05) & (thr < 0.95) & (thrsd < 0.01) & (rpm > 2700) & (rpm < 9000) & (np.abs(Ie*dw) < 15)
print("\nquasi-steady part throttle (|Ie·ω̇| < 15 N·m): pedal band x rpm band -> median f (n)")
for p0 in np.arange(0.10, 0.70, 0.05):
    line = ""
    for a in range(3000, 9000, 1000):
        mm = m & (thr >= p0) & (thr < p0+0.05) & (rpm >= a) & (rpm < a+1000)
        line += f"  {np.median(f[mm]):5.3f}({mm.sum():4d})" if mm.sum() >= 5 else "       -     "
    print(f"   pedal {p0:4.2f}-{p0+0.05:4.2f}:{line}")
print("   rpm bands:        " + "  ".join(f"{a}-{a+1000}" for a in range(3000, 9000, 1000)))
