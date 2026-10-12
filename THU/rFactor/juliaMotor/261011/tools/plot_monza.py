import glob, os, sys, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer/261010")
fs = [f for f in sorted(glob.glob(G + "/*monza*.ibt"), key=lambda p: p.split(" 2026-")[1])]
fig, ax = plt.subplots(len(fs), 1, figsize=(22, 3.2*len(fs)))
for a, f in zip(ax, fs):
    d, y, t = read_ibt(f, ["Speed", "SteeringWheelAngle", "Throttle", "Brake", "YawRate"])
    tt = np.arange(len(d["Speed"]))/60
    a.plot(tt, np.degrees(d["SteeringWheelAngle"]), lw=0.5, label="sw deg")
    a.plot(tt, d["Speed"]*3.6, lw=0.8, label="km/h")
    a.plot(tt, d["Throttle"]*100, lw=0.5, label="thr%")
    a.plot(tt, d["Brake"]*100, lw=0.5, label="brk%")
    a.set_title(os.path.basename(f)); a.set_ylim(-250, 250); a.grid(alpha=.3)
ax[0].legend()
plt.tight_layout(); plt.savefig("../plots/monza_overview.png", dpi=55)
