import sys, glob, math, os
sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))  # a reader with read_ibt(path, names)
from ibt import read_ibt
G = 9.80665
def bins(files, tag):
    acc = {}
    for f in files:
        d, allv, n = read_ibt(f, ["VelocityX","VelocityY","LatAccel","LongAccel","Speed","Brake","Throttle","YawRate"])
        for k in range(n):
            u, v = d["VelocityX"][k], d["VelocityY"][k]; sp = math.hypot(u, v)
            if sp < 12: continue
            beta = abs(math.degrees(math.atan2(v, abs(u))))
            a = math.hypot(d["LatAccel"][k], d["LongAccel"][k]) / G
            b = min(int(beta // 5) * 5, 60)
            acc.setdefault(b, []).append((a, d["Brake"][k], d["Throttle"][k]))
    print(tag)
    for b in sorted(acc):
        xs = sorted(a for a, _, _ in acc[b]); m = len(xs)
        if m < 5: continue
        print(f"  |beta| {b:2d}-{b+5:2d} deg  n {m:6d}  |a| median {xs[m//2]:.2f} g  p90 {xs[int(0.9*m)]:.2f} g")
gold = glob.glob("/home/g/gold standard/julia racer/26100*/lotus49_skidpad*.ibt") + glob.glob("/home/g/gold standard/julia racer/261004/lotus49_skidpad*.ibt")
bins(gold, "iRacing gold skidpad (261002/261004/261005)")
ring = glob.glob("/home/g/gold standard/julia racer/261004/lotus49_nurburgring*.ibt") + glob.glob("/home/g/gold standard/julia racer/261005/lotus49_nurburgring*.ibt")
bins(ring, "iRacing gold Ring (261004/261005)")
jr = sorted(glob.glob('/home/g/sgl-jr/THU/rFactor/juliaMotor/data/juliaracer/lotus49_*2026-10-08*.ibt'))
bins(jr, "Julia, the PO's 10-08 races")
