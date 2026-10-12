import glob, os, numpy as np
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer/261010")
MRF, MRR, TRK = 0.78, 0.648, 1.50
for st in ["17-46-09", "19-18-36", "15-54-13", "15-20-13", "15-24-06", "15-28-20", "16-07-12", "16-12-38", "16-19-11", "16-43-06"]:
    f = glob.glob(G + "/*" + st + ".ibt")[0]
    d, y, t = read_ibt(f, ["Speed", "LatAccel", "LongAccel", "YawRate", "SteeringWheelAngle", "Brake", "VelocityX", "VelocityY", "LFshockDefl", "RFshockDefl", "LRshockDefl", "RRshockDefl", "IsOnTrackCar", "Throttle", "Roll"])
    ay = d["LatAccel"].mean(1)/9.81; v = d["Speed"]; r = d["YawRate"].mean(1)
    ff = lambda n: d[n].mean(1)
    phf = np.degrees((ff("LFshockDefl") - ff("RFshockDefl"))/MRF/TRK); phr = np.degrees((ff("LRshockDefl") - ff("RRshockDefl"))/MRR/TRK)
    beta = np.degrees(np.arctan2(d["VelocityY"].mean(1), d["VelocityX"].mean(1)))
    # steady: smooth ay over 1 s
    k = np.convolve(np.abs(np.gradient(ay))*60, np.ones(60)/60, "same")
    st_ = (d["IsOnTrackCar"] > 0.5) & (v > 20) & (np.abs(ay) > 0.3) & (np.abs(ay) < 1.25) & (k < 0.3) & (d["Brake"] < 0.02) & (np.abs(beta) < 5)
    out = []
    for s in (1, -1):
        m = st_ & (np.sign(ay) == s)
        if m.sum() < 100: out.append("   (none)                       "); continue
        A = np.c_[ay[m], np.ones(m.sum())]
        gf = np.linalg.lstsq(A, phf[m], rcond=None)[0][0]; gr = np.linalg.lstsq(A, phr[m], rcond=None)[0][0]
        # understeer: steer angle (road) vs ay at 1 g band
        sr = 10.0; dl = np.degrees(d["SteeringWheelAngle"][m])/sr
        b = (np.abs(ay[m]) > 0.9) & (np.abs(ay[m]) < 1.1)
        out.append(f"{'L' if s>0 else 'R'} n{m.sum():5d} roll F {gf:+.2f} R {gr:+.2f} deg/g  @1g: v {np.median(v[m][b])*3.6 if b.any() else 0:5.1f} km/h, steer {np.median(dl[b]) if b.any() else 0:+.2f}° β {np.median(beta[m][b]) if b.any() else 0:+.2f}°")
    print(st, f"{yget(y,'CarSetup','Chassis','Front','ArbArms'):5s} {yget(y,'CarSetup','Chassis','Rear','ArbArms'):5s} fuel {yget(y,'CarSetup','Chassis','Rear','FuelLevel'):8s}", " | ".join(out))
