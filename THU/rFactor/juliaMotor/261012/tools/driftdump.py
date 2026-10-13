"""IRGOLD-1 S16: in closed-loop replay dumps, the HELD-DRIFT rows (gold |β| ≥ 3°, throttle ≥ 0.4): gold vs sim body slip,
and the steering correction the sim needed (s_d − g_d, road-wheel degrees). Per file and pooled."""
import glob, os, sys
import numpy as np
D = sys.argv[1]
rows = {}
for f in sorted(glob.glob(os.path.join(D, "*.csv"))):
    a = np.genfromtxt(f, delimiter=",", names=True)
    if a.size < 10: continue
    m = (np.abs(a["g_b"]) >= 3) & (a["thr"] >= 0.4) & (a["k"] > 15)
    if m.sum() < 6: continue
    stem = os.path.basename(f)[:8]
    sg = np.sign(np.median(a["g_ay"][m]))      # orient so + = the drift's own direction
    rows.setdefault(stem, []).append((m.sum(), np.mean(np.abs(a["g_b"][m])), np.mean(a["s_b"][m]*np.sign(a["g_b"][m])),
                                      np.mean((a["s_d"][m] - a["g_d"][m])*sg), np.mean(np.abs(a["g_d"][m])),
                                      np.mean(a["g_kr"][m]), np.mean(a["s_kr"][m]), np.mean(np.abs(a["g_ay"][m])), np.mean(np.abs(a["s_ay"][m]))))
print("file      rows | gold |β|  sim β(same sign) | steer corr (road °, + = more toward the turn) / gold steer | rear κ gold/sim | ay gold/sim")
allr = []
for k, R in rows.items():
    R = np.array(R); w = R[:, 0]; avg = lambda i: np.average(R[:, i], weights=w)
    print(f"{k} {int(w.sum()):5d} | {avg(1):5.2f}°  {avg(2):5.2f}° | {avg(3):+6.2f}° / {avg(4):5.2f}° | {avg(5):.3f}/{avg(6):.3f} | {avg(7):.2f}/{avg(8):.2f}")
    allr.append(R)
