#!/usr/bin/env python3
"""Profile & classify an iRacing/JM .ibt: print envelope stats and detect the
three benchmark-test signatures (skidpad peel-out, centripetal engine-braking
downshift, Nurburgring Flugplatz jump).  Reuses parse_ibt.read_channel.

  python3 profile_ibt.py <file.ibt> [--full]
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_ibt import parse, read_channel

def chan(data, m, name):
    try:
        return read_channel(data, m, name)
    except StopIteration:
        return None

def finite(xs):
    return [x for x in xs if x is not None and math.isfinite(x)]

def stats(xs):
    f = finite(xs)
    if not f: return None
    return (min(f), sum(f)/len(f), max(f))

def load(path):
    m = parse(path)
    with open(path, "rb") as f:
        data = f.read()
    return m, data

# RPM channel name differs: iRacing newer = Engine0_RPM, older/JM = RPM.
# Both channels may exist in a file with one left as a zero stub — pick the one
# that actually carries data (nonzero max).
def rpm_chan(data, m):
    best = (None, None, -1.0)
    for n in ("Engine0_RPM", "RPM"):
        v = chan(data, m, n)
        if v is None: continue
        hi = max(finite(v) or [0.0])
        if hi > best[2]: best = (v, n, hi)
    return best[0], best[1]

def downshift_events(gear, rpm, t):
    """Return list of (time, gear_from, gear_to, rpm_before, rpm_peak_after).
    iRacing blips through neutral (gear 0) on every shift, so we track the last
    NON-ZERO gear and treat a step to (last_nonzero - 1) as a downshift."""
    ev = []
    n = len(gear)
    lastnz = next((g for g in gear if g and g >= 1), 1)
    for i in range(1, n):
        g = gear[i]
        if g >= 1:
            if g == lastnz - 1:                # a real downshift into a lower forward gear
                # rpm just before the shift (last few ticks while still in the higher gear)
                j0 = max(0, i-6)
                rb = max(finite(rpm[j0:i]) or [float('nan')])
                # rpm peak in the ~0.5s window after (engine-braking spike)
                rp = max(finite(rpm[i:i+30]) or [float('nan')])
                ev.append((t[i], lastnz, g, rb, rp))
            lastnz = g
    return ev

def airborne_segments(vert, dt, thresh=2.0, min_len=0.15):
    """VertAccel includes gravity; in free-fall the accelerometer reads ~0.
    Segments where |VertAccel| < thresh m/s^2 for >= min_len seconds = airborne."""
    segs = []
    i = 0; n = len(vert)
    minN = max(1, int(min_len/dt))
    while i < n:
        if vert[i] is not None and math.isfinite(vert[i]) and abs(vert[i]) < thresh:
            j = i
            while j < n and vert[j] is not None and math.isfinite(vert[j]) and abs(vert[j]) < thresh:
                j += 1
            if j - i >= minN:
                segs.append((i*dt, (j-i)*dt))
            i = j
        else:
            i += 1
    return segs

def main():
    path = sys.argv[1]
    m, data = load(path)
    dt = 1.0/max(m["tickRate"], 1)
    n = m["nrows"]
    t = [i*dt for i in range(n)]
    speed = chan(data, m, "Speed")
    gear  = chan(data, m, "Gear")
    rpm, rpmname = rpm_chan(data, m)
    thr   = chan(data, m, "Throttle")
    brk   = chan(data, m, "Brake")
    lat   = chan(data, m, "LatAccel")
    lon   = chan(data, m, "LongAccel")
    vert  = chan(data, m, "VertAccel")
    yaw   = chan(data, m, "YawRate")
    steer = chan(data, m, "SteeringWheelAngle")
    rh = {w: chan(data, m, w+"rideHeight") for w in ("LF","RF","LR","RR")}

    print(f"\n=== {os.path.basename(path)} ===")
    print(f"  {n} rows @ {m['tickRate']}Hz = {n*dt:.1f}s   rpm-chan={rpmname}")
    def line(name, xs, sc=1.0, u=""):
        s = stats([x*sc for x in xs]) if xs else None
        if s is None:
            print(f"  {name:14s} —"); return
        print(f"  {name:14s} min {s[0]:9.2f}  mean {s[1]:9.2f}  max {s[2]:9.2f}  {u}")
    line("Speed km/h", speed, 3.6)
    line("Gear", gear)
    line("RPM", rpm)
    line("Throttle", thr)
    line("Brake", brk)
    line("LatAccel g", lat, 1/9.80665)
    line("LongAccel g", lon, 1/9.80665)
    line("VertAccel g", vert, 1/9.80665)
    line("YawRate d/s", yaw, 180/math.pi)
    line("Steer deg", steer, 180/math.pi)

    # --- test signatures ---
    if gear and rpm:
        ev = downshift_events(gear, rpm, t)
        # focus on coasting downshifts (throttle low) — engine-braking spikes
        coast = []
        for (tt, gf, gto, rb, rp) in ev:
            i = int(tt/dt)
            th = thr[i] if thr and i < len(thr) else 1.0
            coast.append((tt, gf, gto, rb, rp, th))
        ds = [e for e in coast if e[5] < 0.2]
        if ds:
            print(f"  -- {len(ds)} coasting downshift(s) (throttle<0.2): RPM spike per shift --")
            for (tt, gf, gto, rb, rp, th) in ds:
                d = rp - rb
                print(f"     t={tt:6.1f}s  {gf}->{gto}  rpm {rb:6.0f} -> {rp:6.0f}  (+{d:5.0f})  thr={th:.2f}")
    if vert:
        segs = airborne_segments(vert, dt)
        if segs:
            longest = max(segs, key=lambda s: s[1])
            print(f"  -- {len(segs)} airborne seg(s) (|VertAccel|<2): longest {longest[1]:.2f}s @ t={longest[0]:.1f}s --")
            # landing spike: max VertAccel within 1s after the longest seg ends
            i = int((longest[0]+longest[1])/dt)
            w = vert[i:i+60]
            land = max(finite(w) or [float('nan')])
            print(f"     landing peak VertAccel {land/9.80665:.2f} g")

if __name__ == "__main__":
    main()
