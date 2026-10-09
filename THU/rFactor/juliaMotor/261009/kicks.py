import sys, math, glob, os
sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))  # a reader with read_ibt(path, names)
from ibt import read_ibt
G = 9.80665
for f in sorted(glob.glob('/home/g/sgl-jr/THU/rFactor/juliaMotor/data/juliaracer/lotus49_*2026-10-08*.ibt')):
    d, allv, n = read_ibt(f, ["SessionTime","LapDist","VelocityX","VelocityY","LongAccel","LatAccel","YawRate","IsOnTrack"])
    t = d["SessionTime"]; u = d["VelocityX"]; v = d["VelocityY"]
    kicks = []; k = 2
    while k < n - 3:
        dt = t[k+1] - t[k-1]
        if not (0.02 < dt < 0.06) or math.hypot(u[k], v[k]) < 5: k += 1; continue
        # body-frame velocity change predicted by the recorded accelerations (+ the frame's rotation)
        du = (u[k+1] - u[k-1]) / dt; dv = (v[k+1] - v[k-1]) / dt
        pu = d["LongAccel"][k] + d["YawRate"][k] * v[k]; pv = d["LatAccel"][k] - d["YawRate"][k] * u[k]
        err = math.hypot(du - pu, dv - pv) / G
        if err > 3.0:
            j = k
            while j < n - 3 and math.hypot((u[j+1]-u[j-1])/max(t[j+1]-t[j-1],1e-3) - d["LongAccel"][j] - d["YawRate"][j]*v[j],
                                            (v[j+1]-v[j-1])/max(t[j+1]-t[j-1],1e-3) - d["LatAccel"][j] + d["YawRate"][j]*u[j]) / G > 1.0: j += 1
            dV = math.hypot(u[j+1], v[j+1]) - math.hypot(u[k-1], v[k-1])
            kicks.append((k, d["LapDist"][k], 3.6*math.hypot(u[k-1], v[k-1]), 3.6*dV, err, d["IsOnTrack"][k]))
            k = j + 30
        else:
            k += 1
    print(f"{os.path.basename(f)[8:]:48s} {n:6d} frames  {len(kicks):3d} unexplained velocity kicks")
    for kk in kicks[:40]:
        print(f"     frame {kk[0]:6d}  s {kk[1]:7.0f}  {kk[2]:5.0f} km/h  ΔV {kk[3]:+6.1f} km/h  unexplained {kk[4]:5.1f} g  on track {kk[5]:.0f}")
