"""IRGOLD-1 S18 prototype: road bank/camber from the gold. The accelerometer reads SPECIFIC force; the kinematic lateral
acceleration is dVy/dt + Vx·r (body frame). Their difference is gravity's lateral component: g·sin(bank + roll), and the
body roll is measured (Roll channel, if world-referenced it already holds the bank). Prints per-file the distribution of
(a_kin − a_meas)/g in degrees, by track position band, for flat Monza (control) vs the Glen and the Ring."""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt
G = os.path.expanduser("~/gold standard/julia racer"); g0 = 9.80665
def lslope(y, dt, hw):
    k = np.arange(-hw, hw+1); w = k/(dt*(k**2).sum()); return np.convolve(y, w[::-1], mode="same")
for pat in ("261012/*monza*21-41-42*", "261012/*watkinsglen*21-57-57*", "261010/*nordschleife*15-03-24*"):
    f = glob.glob(os.path.join(G, pat))[0]
    d, _, _ = read_ibt(f, ["Speed", "VelocityX", "VelocityY", "YawRate", "LatAccel", "Roll", "LapDist", "IsOnTrack"])
    d = {k: (a.mean(axis=1) if a.ndim == 2 else a) for k, a in d.items()}
    vx, vy, r, ay = d["VelocityX"], d["VelocityY"], d["YawRate"], d["LatAccel"]
    akin = lslope(vy, 1/60, 6) + vx*r
    ok = (d["Speed"] > 20) & (d["IsOnTrack"] > 0)
    bank = np.degrees(np.arcsin(np.clip((akin - ay)/g0, -1, 1)))
    roll = np.degrees(d["Roll"]) if "Roll" in d else np.zeros_like(bank)
    print(f"\n== {os.path.basename(f)[8:-4]}  rows {ok.sum()}")
    print(f"   (a_kin − a_meas)/g  as deg: p5 {np.percentile(bank[ok],5):5.2f} median {np.median(bank[ok]):5.2f} p95 {np.percentile(bank[ok],95):5.2f}   Roll channel p5/p50/p95 {np.percentile(roll[ok],5):5.2f}/{np.median(roll[ok]):5.2f}/{np.percentile(roll[ok],95):5.2f}")
    # repeatability lap to lap: bin by LapDist (50 m), compare medians across laps
    s = d["LapDist"]; bins = (s // 50).astype(int)
    lapid = np.cumsum(np.r_[0, np.diff(s) < -500])
    tab = {}
    for b, l, x in zip(bins[ok], lapid[ok], bank[ok]): tab.setdefault(b, {}).setdefault(l, []).append(x)
    rep = [(b, np.median([np.median(v) for v in L.values()]), np.std([np.median(v) for v in L.values()]), len(L)) for b, L in tab.items() if len(L) >= 2]
    rep.sort(key=lambda t: -abs(t[1]))
    print("   most banked 50 m bins seen on ≥2 laps (bin start m: median° ± lap-to-lap sd, laps):", "  ".join(f"{b*50}:{m:+.1f}±{sd:.1f}({n})" for b, m, sd, n in rep[:8]))
    if rep: print(f"   lap-to-lap sd median over bins: {np.median([t[2] for t in rep]):.2f}°  (n bins {len(rep)})")
