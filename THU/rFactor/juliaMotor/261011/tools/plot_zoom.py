import sys, os, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer/261010")
f = G + "/lotus49_monza nochicane 2026-10-11 " + sys.argv[1] + ".ibt"; t0, t1 = float(sys.argv[2]), float(sys.argv[3])
d, y, t = read_ibt(f, ["Speed", "SteeringWheelAngle", "Throttle", "Brake", "YawRate", "LatAccel", "VelocityY", "SteeringWheelTorque_ST"])
k0, k1 = int(t0*60), int(t1*60)
tt = np.arange(k0, k1)/60; ts = np.arange(k0*6, k1*6)/360
fig, ax = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
ax[0].plot(tt, np.degrees(d["SteeringWheelAngle"][k0:k1]), ".-", ms=2, label="sw deg"); ax[0].plot(tt, d["Throttle"][k0:k1]*100, label="thr"); ax[0].plot(tt, d["Speed"][k0:k1]*3.6, label="kmh"); ax[0].legend(); ax[0].grid()
ax[1].plot(ts, np.degrees(d["YawRate"][k0:k1].ravel()), label="yaw deg/s 360Hz"); ax[1].plot(ts, d["LatAccel"][k0:k1].ravel()/9.81*10, label="ay g x10"); ax[1].plot(ts, d["SteeringWheelTorque_ST"][k0:k1].ravel(), label="rim Nm"); ax[1].legend(); ax[1].grid()
ax[2].plot(ts, np.degrees(np.arctan2(d["VelocityY"][k0:k1].ravel(), d["Speed"][k0:k1].repeat(6))), label="beta deg"); ax[2].legend(); ax[2].grid()
plt.tight_layout(); plt.savefig("../plots/zoom_%s_%d.png" % (sys.argv[1], t0), dpi=60)
