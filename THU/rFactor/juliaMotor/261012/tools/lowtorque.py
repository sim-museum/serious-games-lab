"""IRGOLD-1 S14: crank WOT torque below 3,500 rpm and the in-gear inertia split, from IRTEST-261012's launches + pulls.
Clutch fully in (Clutch > 0.98), throttle > 0.98, gears 1-3, rows 0.5 s clear of a shift. Torquefit's equation:
  T = Ie·ω̇e + Igb·ω̇e + [ 2Iw·ω̇e/gr + Rw_r·( (m + 2Iw/Rw_f²)·a + ½ρ·CdA·v² + Crr·m·g ) ] / (gr·η)
ω̇e from the measured RPM slope (wheelspin-proof). Scans the gearbox inertia's REFLECTION: Igb on the input shaft
(reflected ×gr², torquefit's frame) vs a gear-independent share; reports T by gear per rpm band for each."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, header, yget
G = os.path.expanduser("~/gold standard/julia racer/261012")
RWF, RWR, IW, ETA, CDA, CRR, g0 = 0.30, 0.334, 1.0, 0.9, 0.480, 0.0139, 9.80665
def lslope(y, dt, hw=8):
    k = np.arange(-hw, hw+1); w = k/(dt*(k**2).sum())
    return np.convolve(y, w[::-1], mode="same")
rows = []
for f in sorted(glob.glob(G + "/*.ibt")):
    d, y, tick = read_ibt(f, ["SessionTime", "Speed", "RPM", "Gear", "Throttle", "Clutch", "AirDensity", "Alt", "IsOnTrack"])
    cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
    m = cw/9.81  # N -> kg (as mass_from_corner_weights)
    ratios = [float(yget(y, "CarSetup", "Drivetrain", "Transmission", k).split(",")[0]) for k in ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear")]
    fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    dt = 1/60; v = d["Speed"]; we = d["RPM"]*2*np.pi/60
    a = lslope(v, dt) - g0*lslope(lslope(d["Alt"], dt), dt)*0  # Monza/WG: slope from Alt is too noisy at 60 Hz; flat-ish
    a = lslope(v, dt) - g0*np.gradient(d["Alt"], v.clip(1)*dt + 1e-9)*0
    wdot = lslope(we, dt)
    gear = d["Gear"].astype(int)
    ok = (d["Clutch"] > 0.98) & (d["Throttle"] > 0.98) & (gear >= 1) & (gear <= 3) & (v > 1.0)
    # 0.5 s clear of any gear change
    chg = np.r_[False, np.diff(gear) != 0]; near = np.convolve(chg.astype(float), np.ones(61), mode="same") > 0
    ok &= ~near
    for i in np.where(ok)[0]:
        gr = ratios[gear[i]-1]*fd
        road = 0.5*d["AirDensity"][i]*CDA*v[i]**2 + CRR*m*g0
        Tbody = (2*IW*wdot[i]/gr + RWR*((m + 2*IW/RWF**2)*a[i] + road))/(gr*ETA)
        rows.append((gear[i], d["RPM"][i], wdot[i], Tbody, gr, os.path.basename(f)[-12:-4]))
R = np.array([r[:5] for r in rows], dtype=float)
gear, rpm, wdot, Tb, gr = R.T
print(f"rows {len(R)}  by gear: " + " ".join(f"g{k} {int((gear==k).sum())}" for k in (1, 2, 3)))
WOT = np.array([(3500, 235.5), (4400, 236.5), (4900, 255.0), (5400, 273.5), (5900, 288.5), (6400, 302.5), (6850, 311.0), (7150, 312.0), (7650, 307.5), (8100, 300.5), (8650, 284.5), (8900, 278.5)])
for label, Ie_in, Iconst in (("all 0.18 on the input shaft (shipped)", 0.18, 0.0), ("engine 0.052 only", 0.0522, 0.0),
                             ("0.052 + 0.128 at the WHEELS (×4.22²/gr²)", 0.0522, 0.128)):
    # Iconst: gearbox share reflected as if at the final drive's input (gr-independent at the axle: Igb·fd²)
    T = Ie_in*wdot + Iconst*wdot*(4.22**2)/(gr**2)*0 + Iconst*(4.22**2)*wdot/gr**2  # same as Igb·fd²·ω̇r/(gr) at the crank
    T = T + Tb
    print(f"\n== {label}")
    print("   rpm band  |" + "".join(f"   gear {k} (n)  " for k in (1, 2, 3)) + "| WOT_KNOTS")
    for b in range(1500, 9000, 500):
        line = ""
        for k in (1, 2, 3):
            mm = (gear == k) & (rpm >= b) & (rpm < b+500)
            line += f"  {np.median(T[mm]):6.1f} ({mm.sum():4d})" if mm.sum() >= 8 else "        -      "
        print(f"   {b:4d}-{b+500:4d} |{line} | {np.interp(b+250, WOT[:,0], WOT[:,1]):6.1f}")
