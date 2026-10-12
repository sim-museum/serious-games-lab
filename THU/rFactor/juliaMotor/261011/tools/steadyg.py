import glob, os, numpy as np
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer")
def sm(x, n): return np.convolve(x, np.ones(n)/n, "same")
for f in sorted(glob.glob(G+"/26100[45]/*.ibt"))+sorted(glob.glob(G + "/261010/*.ibt"), key=lambda p: p.split(" 2026-")[1]):
    d, y, t = read_ibt(f, ["Speed", "LatAccel", "YawRate", "VelocityX", "VelocityY", "IsOnTrackCar", "Brake", "LFpressure", "RFpressure"])
    ay = sm(d["LatAccel"].mean(1)/9.81, 30); r = d["YawRate"].mean(1); v = d["Speed"]
    rd = np.abs(np.gradient(sm(r, 15))*60); beta = np.degrees(np.abs(np.arctan2(d["VelocityY"].mean(1), d["VelocityX"].mean(1))))
    # quasi-steady 0.5 s: yaw accel < 0.15 rad/s^2, beta < 6, on track
    q = (d["IsOnTrackCar"] > .5) & (v > 15) & (sm(rd, 30) < 0.15) & (beta < 6) & (d["Brake"] < 0.05)
    tr = (d["IsOnTrackCar"] > .5) & (v > 15) & (beta < 8)
    if not q.any(): continue
    p = "%3.0f/%3.0f" % (np.median(d["LFpressure"][v>15]), np.median(d["RFpressure"][v>15]))
    print("%-48s %s  steady |ay| p99 %.3f max %.3f | any(0.5s) max %.3f  @v %3.0f" % (os.path.basename(f)[8:-4][:48], p, np.percentile(np.abs(ay[q]), 99.5), np.abs(ay[q]).max(), np.abs(ay[tr]).max(), 3.6*v[tr][np.argmax(np.abs(ay[tr]))]))
