# Gold skidpad, steady circles: axle slip angles vs |ay|, left vs right turns. In a LEFT turn (ay>0) the loaded outside
# tyres are the RIGHT ones (207 kPa), in a right turn the left ones (152 kPa). Compare with Monza (152 all round).
import glob, os, numpy as np
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer")
L = 2.41
def sm(x, n): return np.convolve(x, np.ones(n)/n, "same")
rows = []
for f in sorted(glob.glob(G+"/26100[45]/*skidpad*.ibt")) + sorted(glob.glob(G+"/261010/*.ibt")):
    d, y, t = read_ibt(f, ["Speed", "LatAccel", "YawRate", "VelocityX", "VelocityY", "IsOnTrackCar", "Brake", "SteeringWheelAngle", "LFpressure", "RFpressure", "LongAccel", "Throttle"])
    if float(yget(y, "CarSetup", "Chassis", "LeftFront", "SpringRate").split()[0]) < 24: continue   # default setup only
    cw = [float(yget(y, "CarSetup", "Chassis", c, "CornerWeight").split()[0]) for c in ["LeftFront", "RightFront", "LeftRear", "RightRear"]]
    if sum(cw) > 6000: continue
    ff = (cw[0]+cw[1])/sum(cw); a = (1-ff)*L; b = ff*L
    ay = d["LatAccel"].mean(1); r = d["YawRate"].mean(1); vx = d["VelocityX"].mean(1); vy = d["VelocityY"].mean(1); v = d["Speed"]
    sw = d["SteeringWheelAngle"]/10.0
    q = (d["IsOnTrackCar"] > .5) & (v > 15) & (np.abs(sm(np.gradient(r)*60, 30)) < 0.05) & (np.abs(sm(np.gradient(ay)*60, 30)) < 0.5) & (d["Brake"] < .02) & (np.abs(d["LongAccel"].mean(1)) < 1.0)
    af = np.degrees(sw - np.arctan2(vy + a*r, vx)); ar = np.degrees(-np.arctan2(vy - b*r, vx))
    pr = np.median(d["RFpressure"][v > 15])
    kind = "monza" if "monza" in f else "skid"
    for k in np.where(q)[0][::6]:
        rows.append((kind, pr, ay[k]/9.81, af[k], ar[k]))
R = np.array([(r[1], r[2], r[3], r[4]) for r in rows]); K = np.array([r[0] for r in rows])
print("default setup, steady: axle slip angle (deg, signed with ay) per |ay| band")
for kind in ("skid", "monza"):
    for s, lab in ((1, "LEFT turn (outside = right tyres)"), (-1, "RIGHT turn (outside = left tyres)")):
        m = (K == kind) & (np.sign(R[:, 1]) == s)
        if m.sum() < 50: continue
        out = []
        for lo in (0.3, 0.5, 0.7, 0.9, 1.05, 1.15):
            b_ = m & (np.abs(R[:, 1]) >= lo) & (np.abs(R[:, 1]) < lo + 0.1)
            if b_.sum() > 20: out.append("%.2fg: F %4.2f R %4.2f (n%d)" % (lo+0.05, np.median(R[b_, 2]*s), np.median(R[b_, 3]*s), b_.sum()))
        print(f"  {kind:5s} {lab:35s} " + " | ".join(out))
