"""WW103-GPL-1 (PO 2026-10-08: "ww103 in julia doesn't feel at all like ww103 in GPL. Why not?"): a GPL lap against a
Julia lap at the same track, section by section and by full-throttle acceleration.

GPL side: the GPL Replay Analyser's telemetry export (memory gplra-gui-telemetry: -loadrpy ... -l<lap>; columns
Longitude = lap distance m, Latitude, Gear, Rpm, Orientation, Roll, Pitch, Steering, Speed km/h, Long Acc, Lat Acc,
SlipAngle at 60 Hz; its Long/Lat Acc carry crash spikes, so acceleration is taken from the speed trace). Julia side: a
replay's .jrt, the player's best timed lap (analyser.Replay). Optional iRacing .ibt files give the same acceleration
table for the car the Julia model is fitted to (needs IBTPY_DIR with ibt.read_ibt).

  python3 tools/gplcmp_261009.py GPL_TEL.txt REPLAY.jrt TRACK [IBT ...]
"""
import glob, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "demo", "native"))
import analyser as A, trackguide as G

STEP = 5.0
BANDS = [(60, 100), (100, 140), (140, 180), (180, 220), (220, 260), (260, 300)]


def resample(xs, ys, grid):
    out = []; j = 0
    for q in grid:
        while j < len(xs) - 2 and xs[j + 1] < q:
            j += 1
        x0, x1 = xs[j], xs[j + 1]; f = 0 if x1 <= x0 else min(1, max(0, (q - x0) / (x1 - x0)))
        out.append(ys[j] + f * (ys[j + 1] - ys[j]))
    return out


def gpl_lap(path, L):
    rows = [[float(x) for x in ln.split(",")] for ln in open(path).read().strip().split("\n")[2:]]
    d = [r[0] - L if (i < 100 and r[0] > L - 50) else r[0] for i, r in enumerate(rows)]   # the first sample sits at L
    grid = [i * STEP for i in range(int(L // STEP) + 1)]
    return grid, resample(d, [r[8] for r in rows], grid), resample(d, [k / 60 for k in range(len(rows))], grid), \
        resample(d, [r[2] for r in rows], grid)


def accel(v, k):
    v0, v1 = v[k] / 3.6, v[k + 2] / 3.6
    return (v1 * v1 - v0 * v0) / (2 * 2 * STEP) / 9.81


def wot_table(v, mask=None):
    out = []
    for lo, hi in BANDS:
        a = sorted(accel(v, k) for k in range(5, len(v) - 3) if lo <= v[k] < hi and accel(v, k) > 0.02 and (mask is None or mask[k] > 0.95))
        out.append((a[int(0.9 * len(a)) - 1], len(a)) if len(a) > 5 else (None, len(a)))
    return out


def main(tel, jrt, track, ibts):
    rep = A.Replay(jrt); L = rep.laplen
    lp = min((l for l in rep.laps if l.car == 0), key=lambda l: l.time)
    grid, gv, gt, gg = gpl_lap(tel, L)
    n = min(len(grid), len(lp.dist)); jv, jt, jg = lp.ch["kmh"][:n], lp.ch["time"][:n], lp.ch.get("gear", [0] * n)[:n]
    print(f"GPL lap {gt[n - 1]:.2f} s   Julia lap {jt[n - 1]:.2f} s ({lp.driver}, lap {lp.num})")
    secs = [(0.0, "start")] + G.current_sections(track, L)
    print(f"{'section':16s} {'s':>5s} | time GPL/Julia (Δ)  | slowest km/h | fastest km/h | peak decel g | gear at slowest")
    for i, (s0, nm) in enumerate(secs):
        s1 = secs[i + 1][0] if i + 1 < len(secs) else L - STEP
        a, b = int(s0 // STEP), min(int(s1 // STEP), n - 1)
        ka = min(range(a, b), key=lambda k: gv[k] if gv[k] > 1 else 1e9); kj = min(range(a, b), key=lambda k: jv[k])
        dg = max((-accel(gv, k) for k in range(a, b - 2)), default=0); dj = max((-accel(jv, k) for k in range(a, b - 2)), default=0)
        print(f"{nm[:16]:16s} {s0:5.0f} | {gt[b] - gt[a]:5.2f}/{jt[b] - jt[a]:5.2f} ({jt[b] - jt[a] - gt[b] + gt[a]:+5.2f}) | "
              f"{gv[ka]:4.0f}/{jv[kj]:4.0f}  | {max(gv[a:b]):4.0f}/{max(jv[a:b]):4.0f}  | {dg:4.2f}/{dj:4.2f}  | {gg[ka]:.0f}/{jg[kj]:.0f}")
    fmt = lambda t: "  ".join(f"{lo}-{hi}: " + ("  -  " if a is None else f"{a:4.2f}g") + f" (n{m})" for (lo, hi), (a, m) in zip(BANDS, t))
    print("full-throttle acceleration, 90th percentile by speed band (km/h):")
    print("  GPL     " + fmt(wot_table(gv)))
    print("  Julia   " + fmt(wot_table(jv, lp.ch.get("throttle"))))
    if ibts:
        sys.path.insert(0, os.environ.get("IBTPY_DIR", "."))
        from ibt import read_ibt
        acc = {b: [] for b in BANDS}
        for f in ibts:
            d, _allv, m = read_ibt(f, ["Speed", "LongAccel", "Throttle", "Brake", "Clutch"])
            for k in range(m):
                v = d["Speed"][k] * 3.6
                if d["Throttle"][k] > 0.95 and d["Brake"][k] < 0.02 and d["Clutch"][k] > 0.95:
                    for bb in BANDS:
                        if bb[0] <= v < bb[1]:
                            acc[bb].append(d["LongAccel"][k] / 9.81)
        t = [((sorted(acc[bb])[int(0.9 * len(acc[bb])) - 1]) if len(acc[bb]) > 20 else None, len(acc[bb])) for bb in BANDS]
        print("  iRacing " + fmt(t))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
