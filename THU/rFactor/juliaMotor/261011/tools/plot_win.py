import sys, glob, os, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fs = sys.argv[2:]; out = sys.argv[1]
fig, ax = plt.subplots(len(fs), 4, figsize=(24, 3.2*len(fs)), squeeze=False)
for i, f in enumerate(fs):
    d = np.genfromtxt(f, delimiter=",", names=True); t = d["k"]/60
    for j, (a, b, lab) in enumerate([("g_r","s_r","yaw deg/s"),("g_ay","s_ay","ay g"),("g_b","s_b","beta deg"),("g_tau","s_tau","rim Nm")]):
        ax[i,j].plot(t, d[a], "k", lw=1, label="gold"); ax[i,j].plot(t, d[b], "r", lw=1, label="sim")
        if j == 0: ax[i,j].plot(t, d["g_d"]*5, "g", lw=.6, label="road steer x5 deg")
        ax[i,j].set_title(os.path.basename(f)+" "+lab, fontsize=8); ax[i,j].grid(alpha=.3)
ax[0,0].legend(fontsize=7); plt.tight_layout(); plt.savefig(out, dpi=55)
