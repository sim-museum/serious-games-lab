"""IRTEST-261012 test 3: find the held power drifts (body slip β = atan(−vy/vx) ≥ 3°, throttle ≥ 0.4, ≥ 0.8 s) per file."""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, header
G = os.path.expanduser("~/gold standard/julia racer/261012")
for f in sorted(glob.glob(G + "/*.ibt")):
    _, _, y, *_ = header(f); setup = "WW " if "ww103" in y else "DEF"
    d, _, _ = read_ibt(f, ["SessionTime", "Speed", "VelocityX", "VelocityY", "YawRate", "Throttle", "SteeringWheelAngle", "LatAccel", "Gear", "RPM", "LapDist"])
    d = {k: (a.mean(axis=1) if a.ndim == 2 else a) for k, a in d.items()}   # 360 Hz channels carry 6 sub-samples per row
    vx, vy = d["VelocityX"], d["VelocityY"]
    beta = np.degrees(np.arctan2(-vy, np.maximum(vx, 1)))   # sign as yaw: + when sliding the rear out to the left? reported raw
    lat = d["LatAccel"]; lat = lat.mean(axis=1) if lat.ndim == 2 else lat
    ok = (np.abs(beta) >= 3) & (d["Throttle"] >= 0.4) & (d["Speed"] > 15)
    # runs
    t = d["SessionTime"]; t0 = t[0]; i = 0; n = len(ok); out = []
    while i < n:
        if ok[i]:
            j = i
            while j < n and ok[j]: j += 1
            if (j - i) >= 48:
                s = slice(i, j)
                out.append(f"   t {t[i]-t0:6.1f}-{t[j-1]-t0:6.1f} ({(j-i)/60:.1f}s) β {np.median(beta[s]):+5.1f}° (max {np.max(np.abs(beta[s])):4.1f}) r {np.degrees(np.median(d['YawRate'][s])):+5.1f}°/s ay {np.median(lat[s])/9.81:+.2f}g v {np.median(d['Speed'][s])*3.6:5.1f} thr {np.median(d['Throttle'][s]):.2f} steer {np.degrees(np.median(d['SteeringWheelAngle'][s])):+5.0f}° g{np.median(d['Gear'][s]):.0f} rpm {np.median(d['RPM'][s]):5.0f} s {np.median(d['LapDist'][s]):5.0f}")
            i = j
        else:
            i += 1
    print(f"{setup} {os.path.basename(f)[8:-4]}: {len(out)} held drifts")
    for o in out: print(o)
