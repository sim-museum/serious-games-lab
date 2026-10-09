import sys, math, glob, os
sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))  # a reader with read_ibt(path, names)
from ibt import read_ibt
D4 = os.path.expanduser("~/gold standard/julia racer/261004/lotus49_nurburgring nordschleifetourist 2026-10-04 13-34-46.ibt")
WW = os.path.expanduser("~/gold standard/julia racer/261005/lotus49_skidpad 2026-10-06 00-21-30.ibt")
out = []
for f in sorted(glob.glob('/home/g/sgl-jr/THU/rFactor/juliaMotor/data/juliaracer/lotus49_*2026-10-08*.ibt')):
    setup = D4 if "nurburgring" in f else WW
    d, allv, n = read_ibt(f, ["Speed","VelocityX","VelocityY","IsOnTrack","LatAccel","LongAccel"])
    beta = lambda k: abs(math.degrees(math.atan2(d["VelocityY"][k], max(abs(d["VelocityX"][k]), 1))))
    amag = lambda k: math.hypot(d["LatAccel"][k], d["LongAccel"][k]) / 9.81
    k = 120
    while k < n - 400:
        if d["Speed"][k] > 20 and d["IsOnTrack"][k] > 0.5 and beta(k) > 15:
            j = k
            while j < n - 1 and beta(j) > 10: j += 1
            k0 = k - 90                                            # 1.5 s before |β| first passes 15°
            clean = all(amag(i) < 2.5 for i in range(k0, k + 60)) and all(d["IsOnTrack"][i] > 0.5 for i in range(k0, k + 60))
            if clean and beta(k0) < 8 and d["Speed"][k0] > 20:
                out.append((f, k0, setup, max(beta(i) for i in range(k, j)), 3.6 * d["Speed"][k0]))
            k = j + 30
        else:
            k += 1
for f, k0, setup, b, v in out:
    print(f"{f}|{k0}|{setup}|{b:.1f}|{v:.0f}")
