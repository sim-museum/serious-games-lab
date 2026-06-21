#!/usr/bin/env python3
"""Diagnostic: stream the TX wheel through GLFW (joyserver.jl) for ~40 s, then report
each axis's range and an ORDER-of-movement timeline, so we can map control→axis
regardless of the axes' wildly different raw scales."""
import json, subprocess, sys, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
julia = os.path.expanduser("~/.juliaup/bin/julia")
if not os.path.exists(julia):
    julia = "julia"

p = subprocess.Popen([julia, "--project=.", "joyserver.jl", "1"],
                     cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     text=True, bufsize=1)

DUR = 60.0
BASELINE = 4.0
samples = []          # (t, axes)
t0 = None
print("waiting for joystick stream…", file=sys.stderr, flush=True)
try:
    for line in p.stdout:
        line = line.strip()
        if not line.startswith("{"):
            continue
        d = json.loads(line)
        if not d.get("present"):
            continue
        ax = [float(x) for x in d.get("axes", [])]
        if not ax:
            continue
        now = time.time()
        if t0 is None:
            t0 = now
            print(f"streaming {len(ax)} axes — GO (keep hands off ~3 s first)", file=sys.stderr, flush=True)
        t = now - t0
        samples.append((t, ax))
        if t > DUR:
            break
finally:
    p.kill()

if not samples:
    print("NO SAMPLES — joystick not detected"); sys.exit(1)

n = len(samples[0][1])
# rest = mean over the baseline window
base = [s for t, s in ((t, s) for t, s in samples) if t < BASELINE]
rest = [sum(s[i] for s in base) / len(base) for i in range(n)] if base else samples[0][1]
mn = [min(s[i] for _, s in samples) for i in range(n)]
mx = [max(s[i] for _, s in samples) for i in range(n)]
span = [max(1e-6, mx[i] - mn[i]) for i in range(n)]

print("\n=== per-axis range over the capture ===")
for i in range(n):
    print(f"  axis {i+1}: rest={rest[i]:+8.2f}  min={mn[i]:+8.2f}  max={mx[i]:+8.2f}  span={span[i]:7.2f}")

# ordered movement timeline: for each sample the dominant axis by RELATIVE deviation
print("\n=== movement timeline (control order) ===")
segs = []   # (axis, t_start, peak_dev, peak_raw)
cur = None
for t, s in samples:
    if t < BASELINE:
        continue
    rel = [abs(s[i] - rest[i]) / span[i] for i in range(n)]
    j = max(range(n), key=lambda i: rel[i])
    if rel[j] < 0.30:        # nothing pressed
        cur = None
        continue
    raw = s[j]
    if cur != j:
        segs.append([j, t, rel[j], raw])
        cur = j
    else:
        if rel[j] > segs[-1][2]:
            segs[-1][2] = rel[j]; segs[-1][3] = raw

# collapse tiny stutter segments (same axis within 0.4 s)
merged = []
for sg in segs:
    if merged and merged[-1][0] == sg[0] and sg[1] - merged[-1][1] < 1.5:
        if sg[2] > merged[-1][2]:
            merged[-1][2] = sg[2]; merged[-1][3] = sg[3]
    else:
        merged.append(sg)
for j, t, dev, raw in merged:
    print(f"  t={t:5.1f}s   axis {j+1}   peak_raw={raw:+8.2f}   (rest {rest[j]:+.2f})")

# raw CSV so we can see every axis at every moment
with open("/tmp/joyraw.csv", "w") as f:
    f.write("t," + ",".join(f"a{i+1}" for i in range(n)) + "\n")
    for t, s in samples:
        f.write(f"{t:.2f}," + ",".join(f"{v:.3f}" for v in s) + "\n")
print("\nraw → /tmp/joyraw.csv")
print("Done.")
