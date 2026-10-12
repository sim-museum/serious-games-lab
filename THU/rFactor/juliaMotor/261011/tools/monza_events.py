import glob, os, sys, numpy as np
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer/261010")
for f in sorted(glob.glob(G + "/*monza*.ibt"), key=lambda p: p.split(" 2026-")[1]):
    d, y, t = read_ibt(f, ["Speed", "SteeringWheelAngle", "Throttle", "Brake", "YawRate", "LapDist", "Gear"])
    sw = np.degrees(d["SteeringWheelAngle"]); v = d["Speed"]*3.6; thr = d["Throttle"]
    n = len(v)
    # flicks: |d sw| > 50 deg within 0.15 s (9 samples) starting near straight, then |sw| held > 50 for 0.6 s
    flicks = []
    k = 10
    while k < n - 80:
        if abs(sw[k-3]) < 15 and abs(sw[k+9]) > 50 and np.all(np.abs(sw[k+12:k+60]) > 40):
            flicks.append((k/60, v[k], np.median(sw[k+12:k+60]), thr[k]))
            k += 90
        else:
            k += 1
    # weaving: zero-crossings of sw with |sw|>20 amplitude, on throttle, v>80
    zc = np.where((np.sign(sw[1:]) != np.sign(sw[:-1])) & (v[1:] > 70))[0]
    per = np.diff(zc)/60*2
    print(os.path.basename(f)[8:-4], f"{n/60:.0f}s flicks {len(flicks)}  zero-crossings {len(zc)}  half-period median {np.median(np.diff(zc))/60 if len(zc)>2 else 0:.2f}s")
    for fl in flicks: print("   flick t=%.1f v=%.0f sw=%+.0f thr=%.2f" % fl)
