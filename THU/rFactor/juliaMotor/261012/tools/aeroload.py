"""IRGOLD-1 S20: aerodynamic load in the gold -- shock deflection vs speed on straights (|ay| < 0.05 g, |ax| < 0.05 g,
steady), per axle, both corners averaged. A deflection that grows (compresses) with v² = downforce, shrinks = lift.
Spring rates from the setup turn it into force at the wheel (motion ratios 0.78 front / 0.648 rear, sim frame)."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer")
for pat in ("261010/*nordschleife*15-03-24*", "261010/*nordschleife*14-52-47*", "261010/*monza*16-53-12*", "261012/*monza*21-41-42*", "261012/*watkinsglen*21-57-57*", "261004/*nordschleifetourist*12-00-29*"):
    fs = glob.glob(os.path.join(G, pat))
    if not fs: continue
    f = fs[0]
    d, y, _ = read_ibt(f, ["Speed", "LatAccel", "LongAccel", "LFshockDefl", "RFshockDefl", "LRshockDefl", "RRshockDefl", "Throttle", "Brake", "FuelLevel"])
    d = {k: (a.mean(axis=1) if a.ndim == 2 else a) for k, a in d.items()}
    sr = lambda c: float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "SpringRate") or "nan"))
    kf, kr = sr("LeftFront"), sr("LeftRear")  # N/mm at the spring
    ok = (np.abs(d["LatAccel"]) < 0.05*9.81) & (np.abs(d["LongAccel"]) < 0.08*9.81) & (d["Speed"] > 15) & (d["Brake"] < 0.01)
    v = d["Speed"][ok]; fr = 0.5*(d["LFshockDefl"] + d["RFshockDefl"])[ok]*1000; rr = 0.5*(d["LRshockDefl"] + d["RRshockDefl"])[ok]*1000
    fuel = d["FuelLevel"][ok]
    A = np.c_[np.ones_like(v), v**2, fuel]
    cf, *_ = np.linalg.lstsq(A, fr, rcond=None); cr, *_ = np.linalg.lstsq(A, rr, rcond=None)
    # force at the wheel per corner: spring N/mm × shock mm / MR (spring at the shock); both corners → axle
    Ff = 2*kf*cf[1]*(60**2)/0.78; Fr = 2*kr*cr[1]*(60**2)/0.648
    print(f"{os.path.basename(f)[8:-4]:52s} n {ok.sum():5d} v {v.min()*3.6:.0f}-{v.max()*3.6:.0f} km/h | shock mm per (m/s)²·1e3: F {cf[1]*1e3:+.3f} R {cr[1]*1e3:+.3f} | axle load at 60 m/s (216 km/h): F {Ff:+.0f} N  R {Fr:+.0f} N  (springs {kf}/{kr} N/mm)")
