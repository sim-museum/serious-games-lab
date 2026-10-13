"""IRGOLD-1 S16: axle slip angles in the held-drift rows of closed-loop dumps (gold vs sim), oriented to the turn.
α_f = δ − (β + a·r/u), α_r = −(β − b·r/u) (rad, small-angle), a/b the CG arms (1.314/1.096 sim frame)."""
import glob, os, sys
import numpy as np
D = sys.argv[1]; A, B = 1.314, 1.096
acc = {}
for f in sorted(glob.glob(os.path.join(D, "*.csv"))):
    a = np.genfromtxt(f, delimiter=",", names=True)
    if a.size < 10: continue
    m = (np.abs(a["g_b"]) >= 3) & (a["thr"] >= 0.4) & (a["k"] > 15)
    if m.sum() < 6: continue
    sg = np.sign(np.median(a["g_ay"][m]))
    out = []
    for p in ("g", "s"):
        u = a[p + "_v"][m]/3.6; r = np.radians(a[p + "_r"][m]); b = np.radians(a[p + "_b"][m]); d = np.radians(a[p + "_d"][m])
        af = d - (b + A*r/u); ar = -(b - B*r/u)
        out += [np.degrees(af*sg), np.degrees(ar*sg)]
    acc.setdefault(os.path.basename(f)[:8], []).append([m.sum()] + [x.mean() for x in out])
print("file       rows |  α_front gold / sim  |  α_rear gold / sim   (deg, + = toward the turn's force)")
for k, R in acc.items():
    R = np.array(R); w = R[:, 0]; av = lambda i: np.average(R[:, i], weights=w)
    print(f"{k} {int(w.sum()):6d} |   {av(1):5.2f} / {av(3):5.2f}     |   {av(2):5.2f} / {av(4):5.2f}")
