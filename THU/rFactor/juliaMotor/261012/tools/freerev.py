"""IRTEST-261012 test 1 (free revs, stationary, clutch out / neutral): engine inertia, drag and part-throttle fraction.
Ie·dω/dt = T(rpm, pedal) with the gearbox decoupled. Model (powertrain.jl): T = f·WOT − (1−f)·fric,
fric = (14.24 + 0.00389·rpm)·½(1+tanh((rpm−2353)/351)), WOT = WOT_KNOTS."""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, header
import re
G = os.path.expanduser("~/gold standard/julia racer/261012")
K = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0),
     (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))
kx = np.array([k[0] for k in K]); ky = np.array([k[1] for k in K])
def wot(r):
    s0 = (ky[1]-ky[0])/(kx[1]-kx[0]); s1 = (ky[-1]-ky[-2])/(kx[-1]-kx[-2])
    return np.where(r < kx[0], ky[0], np.where(r > kx[-1], ky[-1] + s1*(r-kx[-1]), np.interp(r, kx, ky)))
def fric(r): return (14.24 + 0.00389*r)*0.5*(1 + np.tanh((r - 2353)/351))
rows = []
for f in sorted(glob.glob(G + "/*.ibt")):
    _, _, y, *_ = header(f)
    setup = "WW" if "ww103" in y else "DEF"
    d, _, tick = read_ibt(f, ["SessionTime", "Speed", "RPM", "Gear", "Throttle", "ThrottleRaw", "Clutch"])
    t = d["SessionTime"]; w = d["RPM"]*2*np.pi/60
    dw = np.gradient(w, t)
    # free: standing, and decoupled (neutral, or clutch disengaged: .ibt Clutch 1 = engaged)
    free = (d["Speed"] < 0.3) & ((d["Gear"] == 0) | (d["Clutch"] < 0.05))
    # require free for ±3 samples so gradients do not straddle engagement
    fr = free.copy()
    for k in range(1, 4): fr &= np.roll(free, k) & np.roll(free, -k)
    for i in np.where(fr)[0]:
        rows.append((setup, os.path.basename(f)[-12:-4], t[i], d["RPM"][i], d["Throttle"][i], d["ThrottleRaw"][i], dw[i],
                     d["Throttle"][i-3:i+4].std()))
R = np.array([r[3:] for r in rows]); S = np.array([r[0] for r in rows]); F = np.array([r[1] for r in rows])
rpm, thr, thrraw, dw, thrsd = R[:, 0], R[:, 1], R[:, 2], R[:, 3], R[:, 4]
print(f"free rows: {len(R)}  files: {sorted(set(F))}")
print(f"Throttle vs ThrottleRaw max |diff| {np.abs(thr-thrraw).max():.3f}")
# 1) WOT rise
m = (thr > 0.98) & (rpm > 3700) & (rpm < 8800) & (dw > 0)
print("\n1) WOT rise: Ie = WOT(rpm)/dω/dt   [by 500 rpm band; median]")
for a in range(3500, 9000, 500):
    mm = m & (rpm >= a) & (rpm < a+500)
    if mm.sum() >= 3: print(f"   {a:5d}-{a+500:5d} n{mm.sum():4d}  dω/dt {np.median(dw[mm]):7.1f}  Ie {np.median(wot(rpm[mm])/dw[mm]):.4f}")
print(f"   all: Ie {np.median(wot(rpm[m])/dw[m]):.4f}  n{m.sum()}")
# 2) closed-throttle decay
m = (thr < 0.01) & (rpm > 2600) & (dw < 0)
print("\n2) closed decay: drag·(Ie=0.18) vs model fric   [by 500 rpm band]")
for a in range(2500, 9500, 500):
    mm = m & (rpm >= a) & (rpm < a+500)
    if mm.sum() >= 3:
        T = -0.18*np.median(dw[mm]); Tm = np.median(fric(rpm[mm]))
        print(f"   {a:5d}-{a+500:5d} n{mm.sum():4d}  dω/dt {np.median(dw[mm]):8.1f}  drag@Ie.18 {T:6.1f}  model {Tm:6.1f}  Ie-implied {Tm/-np.median(dw[mm]):.4f}")
# 3) part throttle, quasi-steady pedal
m = (thr > 0.05) & (thr < 0.95) & (thrsd < 0.02) & (rpm > 2600)
print("\n3) part throttle: f = (Ie·dω/dt + fric)/(WOT + fric), Ie 0.18   [pedal band x rpm band, median f, n]")
fr_ = (0.18*dw + fric(rpm))/(wot(rpm) + fric(rpm))
for p0 in np.arange(0.05, 0.95, 0.05):
    line = ""
    for a in range(3000, 9500, 1000):
        mm = m & (thr >= p0) & (thr < p0+0.05) & (rpm >= a) & (rpm < a+1000)
        line += f"  {np.median(fr_[mm]):5.3f}({mm.sum():3d})" if mm.sum() >= 5 else "      -     "
    print(f"   pedal {p0:4.2f}-{p0+0.05:4.2f}:{line}")
print("   columns rpm: " + " ".join(f"{a}-{a+1000}" for a in range(3000, 9500, 1000)))
np.save(os.path.join(os.path.dirname(__file__), "freerev_rows.npy"), R)
